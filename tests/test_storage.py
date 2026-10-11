import json
import os
import tempfile
import unittest

from campusflow.storage import (
    StorageError,
    load_tickets,
    next_ticket_id,
    save_tickets,
)


def make_ticket(ticket_id, **overrides):
    """Build a plain ticket dict so no input() is needed in tests."""
    ticket = {
        "id": ticket_id,
        "title": f"Ticket {ticket_id}",
        "category": "Network",
        "urgency": "high",
        "affected_users": 15,
        "priority": "critical",
        "status": "open",
        "assigned_to": None,
    }
    ticket.update(overrides)
    return ticket


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
        self.write_raw("not json")
        with self.assertRaises(ValueError):
            load_tickets(self.path)


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

    def test_failed_save_keeps_previous_file_intact(self):
        save_tickets([make_ticket("T001")], self.path)
        before = self.read_raw()
        with self.assertRaises(TypeError):
            save_tickets([{"id": "T002", "bad": object()}], self.path)
        self.assertEqual(self.read_raw(), before)
        self.assertEqual(os.listdir(os.path.dirname(self.path)), ["tickets.json"])


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


if __name__ == "__main__":
    unittest.main()