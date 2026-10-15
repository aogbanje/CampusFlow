"""Tests for safe JSON persistence (Engineer A, Requirement E).

The tests that matter most are the "state loss" ones: after a rejected load
the caller must still hold the collection it had before. They assert BOTH
that the error is raised AND that the in-memory list is untouched, because
an exception on its own does not prove the data survived.
"""

import copy
import json
import os
import tempfile
import unittest

from campusflow.notes import add_note, next_note_id
from campusflow.storage import (
    StorageError,
    load_tickets,
    next_ticket_id,
    save_tickets,
)
from campusflow.tickets import create_ticket
from campusflow.validation import ValidationError
from campusflow.workflow import assign_ticket, change_status


def make_ticket(ticket_id, **overrides):
    """Build a valid ticket dict so no input() is needed in tests."""
    ticket = {
        "id": ticket_id,
        "title": f"Ticket {ticket_id}",
        "category": "Network",
        "urgency": "high",
        "affected_users": 15,
        "priority": "critical",
        "status": "open",
        "assigned_to": None,
        "notes": [],
    }
    ticket.update(overrides)
    return ticket


def make_note(note_id, **overrides):
    note = {"note_id": note_id, "author": "Mentor A", "message": "Rebooted the AP."}
    note.update(overrides)
    return note


class StorageTestCase(unittest.TestCase):
    """Gives every test its own throwaway folder (never data/tickets.json)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = os.path.join(self._tmp.name, "data", "tickets.json")

    def write_raw(self, text):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            f.write(text)

    def read_raw(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return f.read()


class TestLoad(StorageTestCase):
    def test_missing_file_gives_fresh_start(self):
        self.assertEqual(load_tickets(self.path), [])

    def test_missing_file_is_not_created_by_loading(self):
        load_tickets(self.path)
        self.assertFalse(os.path.exists(self.path))

    def test_empty_list_file_loads_as_empty_list(self):
        self.write_raw("[]")
        self.assertEqual(load_tickets(self.path), [])

    def test_malformed_json_raises_clear_error_and_keeps_file(self):
        broken = '[{"id": "T001", "title": '
        self.write_raw(broken)
        with self.assertRaises(StorageError) as ctx:
            load_tickets(self.path)
        self.assertIn("not valid JSON", str(ctx.exception))
        self.assertEqual(self.read_raw(), broken)  # nothing erased

    def test_empty_file_is_treated_as_malformed(self):
        self.write_raw("")
        with self.assertRaises(StorageError):
            load_tickets(self.path)

    def test_wrong_top_level_type_is_rejected(self):
        self.write_raw('{"id": "T001"}')
        with self.assertRaises(StorageError):
            load_tickets(self.path)

    def test_ticket_missing_fields_is_rejected(self):
        self.write_raw(json.dumps([{"id": "T001", "title": "No other fields"}]))
        with self.assertRaises(StorageError) as ctx:
            load_tickets(self.path)
        self.assertIn("missing", str(ctx.exception))

    def test_duplicate_ids_in_file_are_rejected(self):
        self.write_raw(json.dumps([make_ticket("T001"), make_ticket("T001")]))
        with self.assertRaises(StorageError):
            load_tickets(self.path)

    def test_storage_error_is_a_value_error(self):
        # The CLI catches ValueError, so storage errors must be caught too.
        self.assertTrue(issubclass(StorageError, ValueError))
        self.write_raw("not json")
        with self.assertRaises(ValueError):
            load_tickets(self.path)


class TestLoadRejectsInconsistentRecords(StorageTestCase):
    """A file can be valid JSON and still not be a valid ticket collection."""

    def assert_rejected(self, tickets, expected_fragment):
        self.write_raw(json.dumps(tickets))
        with self.assertRaises(StorageError) as ctx:
            load_tickets(self.path)
        self.assertIn(expected_fragment, str(ctx.exception))
        self.assertEqual(json.loads(self.read_raw()), tickets)  # file intact

    def test_illegal_status_is_rejected(self):
        self.assert_rejected([make_ticket("T001", status="banana")], "status")

    def test_priority_inconsistent_with_the_rule_is_rejected(self):
        # 1 affected user and low urgency can never be "critical".
        self.assert_rejected(
            [make_ticket("T001", urgency="low", affected_users=1, priority="critical")],
            "does not match the rule",
        )

    def test_in_progress_without_assignee_is_rejected(self):
        self.assert_rejected(
            [make_ticket("T001", status="in_progress", assigned_to=None)], "assigned_to"
        )

    def test_illegal_category_and_urgency_are_rejected(self):
        self.assert_rejected([make_ticket("T001", category="Plumbing")], "Category")
        self.assert_rejected([make_ticket("T001", urgency="urgent")], "Urgency")

    def test_negative_and_boolean_affected_users_are_rejected(self):
        self.assert_rejected([make_ticket("T001", affected_users=-1)], "users")
        self.assert_rejected(
            [make_ticket("T001", affected_users=True, priority="low")], "users"
        )

    def test_malformed_note_is_rejected(self):
        self.assert_rejected(
            [make_ticket("T001", notes=[{"note_id": "N001", "author": "Mentor A"}])],
            "message",
        )
        self.assert_rejected(
            [make_ticket("T001", notes=[make_note("N001", message="no")])], "at least 5"
        )

    def test_duplicate_note_ids_within_a_ticket_are_rejected(self):
        self.assert_rejected(
            [make_ticket("T001", notes=[make_note("N001"), make_note("N001")])],
            "Duplicate note ID",
        )

    def test_notes_must_be_a_list(self):
        self.assert_rejected([make_ticket("T001", notes={"N001": "x"})], "must be a list")

    def test_only_one_bad_record_is_needed_to_reject_the_file(self):
        self.assert_rejected(
            [make_ticket("T001"), make_ticket("T002"), make_ticket("T003", status="oops")],
            "Ticket #3",
        )

    def test_legacy_file_without_notes_still_loads(self):
        """Original CampusFlow files have no 'notes' key. They must survive."""
        legacy = make_ticket("T001")
        del legacy["notes"]
        self.write_raw(json.dumps([legacy]))
        loaded = load_tickets(self.path)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["notes"], [])


class TestLoadNeverLosesState(StorageTestCase):
    """A5: 'Load corrupted/duplicate-ID JSON without erasing memory.'"""

    def setUp(self):
        super().setUp()
        # The collection the running application would be holding already.
        self.in_memory = load_tickets(self.path)
        save_tickets(
            [
                make_ticket("T001"),
                make_ticket("T002", assigned_to="Mentor A", notes=[make_note("N001")]),
            ],
            self.path,
        )
        self.in_memory = load_tickets(self.path)
        self.assertTrue(self.in_memory)  # sanity: we really are holding data

    def _failed_reload_must_not_change_memory(self, file_text):
        self.write_raw(file_text)
        before = copy.deepcopy(self.in_memory)
        with self.assertRaises(StorageError):
            # Mirrors main.py: only a SUCCESSFUL load is assigned back.
            self.in_memory = load_tickets(self.path)
        self.assertEqual(self.in_memory, before)

    def test_corrupt_json_does_not_erase_memory(self):
        self._failed_reload_must_not_change_memory("{not json at all")

    def test_duplicate_ticket_ids_do_not_erase_memory(self):
        self._failed_reload_must_not_change_memory(
            json.dumps([make_ticket("T001"), make_ticket("T001")])
        )

    def test_inconsistent_record_does_not_erase_memory(self):
        self._failed_reload_must_not_change_memory(
            json.dumps([make_ticket("T001", priority="low")])
        )

    def test_half_valid_file_does_not_partially_replace_memory(self):
        """The dangerous case: record 1 is fine, record 2 is broken.

        If loading installed records one at a time, memory would end up
        holding a truncated collection. It must hold a different length.
        """
        self._failed_reload_must_not_change_memory(
            json.dumps([make_ticket("T009"), make_ticket("T010", status="nonsense")])
        )

    def test_memory_is_unchanged_even_though_the_bad_file_is_still_on_disk(self):
        self.write_raw("garbage")
        with self.assertRaises(StorageError):
            load_tickets(self.path)
        self.assertEqual(len(self.in_memory), 2)
        self.assertEqual(self.read_raw(), "garbage")  # not overwritten


class TestSave(StorageTestCase):
    def test_save_creates_folder_and_file(self):
        save_tickets([make_ticket("T001")], self.path)
        self.assertTrue(os.path.exists(self.path))

    def test_round_trip_preserves_tickets_exactly(self):
        tickets = [
            make_ticket("T001"),
            make_ticket(
                "T002",
                title="Laptop screen cracked",
                category="Hardware",
                urgency="low",
                affected_users=1,
                priority="low",
                status="in_progress",
                assigned_to="Amina",
            ),
        ]
        save_tickets(tickets, self.path)
        self.assertEqual(load_tickets(self.path), tickets)

    def test_round_trip_keeps_none_and_integer_types(self):
        save_tickets([make_ticket("T001")], self.path)
        loaded = load_tickets(self.path)[0]
        self.assertIsNone(loaded["assigned_to"])
        self.assertIsInstance(loaded["affected_users"], int)

    def test_save_empty_list_round_trips(self):
        save_tickets([], self.path)
        self.assertEqual(load_tickets(self.path), [])

    def test_second_save_replaces_first(self):
        save_tickets([make_ticket("T001")], self.path)
        save_tickets([make_ticket("T001"), make_ticket("T002")], self.path)
        self.assertEqual(len(load_tickets(self.path)), 2)

    def test_save_leaves_no_temporary_files_behind(self):
        save_tickets([make_ticket("T001")], self.path)
        leftovers = os.listdir(os.path.dirname(self.path))
        self.assertEqual(leftovers, ["tickets.json"])

    def test_save_refuses_to_write_an_invalid_collection(self):
        """What we save must be readable by what we load.

        CHANGED in CampusFlow Next: save_tickets now validates first, so this
        raises ValidationError instead of a raw TypeError. The behaviour the
        original test protected -- a failed save leaves the previous file
        intact and no temp files behind -- is unchanged and still asserted.
        """
        save_tickets([make_ticket("T001")], self.path)
        before = self.read_raw()
        with self.assertRaises(ValidationError):
            save_tickets([{"id": "T002", "bad": object()}], self.path)
        self.assertEqual(self.read_raw(), before)
        self.assertEqual(os.listdir(os.path.dirname(self.path)), ["tickets.json"])

    def test_save_does_not_mutate_the_collection_it_is_given(self):
        tickets = [make_ticket("t1", title="  Wi-Fi down  ")]
        before = copy.deepcopy(tickets)
        save_tickets(tickets, self.path)
        self.assertEqual(tickets, before)


class TestNextTicketId(StorageTestCase):
    def test_first_id_on_empty_list(self):
        self.assertEqual(next_ticket_id([]), "T001")

    def test_next_id_follows_highest_number(self):
        tickets = [make_ticket("T001"), make_ticket("T002")]
        self.assertEqual(next_ticket_id(tickets), "T003")

    def test_gap_in_ids_does_not_cause_reuse(self):
        tickets = [make_ticket("T001"), make_ticket("T005")]
        self.assertEqual(next_ticket_id(tickets), "T006")

    def test_ids_beyond_three_digits(self):
        self.assertEqual(next_ticket_id([make_ticket("T999")]), "T1000")

    def test_new_ticket_after_reload_does_not_duplicate_ids(self):
        tickets = [make_ticket("T001"), make_ticket("T002")]
        save_tickets(tickets, self.path)

        reloaded = load_tickets(self.path)  # simulates restarting the app
        new_id = next_ticket_id(reloaded)
        reloaded.append(make_ticket(new_id))
        save_tickets(reloaded, self.path)

        ids = [t["id"] for t in load_tickets(self.path)]
        self.assertEqual(ids, ["T001", "T002", "T003"])
        self.assertEqual(len(ids), len(set(ids)))


class TestIdContinuityAcrossReload(StorageTestCase):
    """A6: 'Restart and generate the correct next IDs.'"""

    def test_notes_and_both_id_sequences_survive_a_restart(self):
        tickets = []
        create_ticket(tickets, "Wi-Fi down", "Network", "high", 15)  # T001
        create_ticket(tickets, "Laptop dead", "Hardware", "low", 1)  # T002
        add_note(tickets, "T001", "Mentor A", "Rebooted the access point.")
        add_note(tickets, "T001", "Mentor B", "Investigating switch ports.")
        save_tickets(tickets, self.path)

        # ---- restart ----
        reloaded = load_tickets(self.path)

        self.assertEqual(reloaded, tickets)  # nothing lost, including notes
        self.assertEqual(next_ticket_id(reloaded), "T003")
        self.assertEqual(next_note_id(reloaded[0]), "N003")

        # The next IDs must not collide with what is already on disk.
        create_ticket(reloaded, "Printer offline", "Hardware", "low", 1)
        add_note(reloaded, "T001", "Mentor A", "Escalated to the network team.")
        save_tickets(reloaded, self.path)

        final = load_tickets(self.path)
        ids = [t["id"] for t in final]
        self.assertEqual(ids, ["T001", "T002", "T003"])
        self.assertEqual(len(ids), len(set(ids)))
        note_ids = [n["note_id"] for n in final[0]["notes"]]
        self.assertEqual(note_ids, ["N001", "N002", "N003"])
        self.assertEqual(len(note_ids), len(set(note_ids)))

    def test_note_written_after_reopen_continues_the_sequence(self):
        tickets = []
        create_ticket(tickets, "Wi-Fi down", "Network", "high", 15)
        assign_ticket(tickets, "T001", "Mentor A")
        add_note(tickets, "T001", "Mentor A", "Rebooted the access point.")
        change_status(tickets, "T001", "in_progress")
        change_status(tickets, "T001", "resolved")
        change_status(tickets, "T001", "open")  # reopen
        add_note(tickets, "T001", "Mentor B", "Reopened: fault returned.")
        save_tickets(tickets, self.path)

        reloaded = load_tickets(self.path)
        self.assertEqual(next_note_id(reloaded[0]), "N003")
        self.assertEqual(len(reloaded[0]["notes"]), 2)


if __name__ == "__main__":
    unittest.main()
