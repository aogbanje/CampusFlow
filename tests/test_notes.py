"""Tests for structured follow-up notes (Engineer A, Requirement B).

The important tests here are the ones that check BOTH the raised error and the
unchanged ticket. Asserting only that an exception was raised would still pass
if the function had already written a field before failing.
"""

import copy
import unittest

from campusflow.notes import add_note, can_add_note, next_note_id, notes_for
from campusflow.validation import ValidationError
from campusflow.workflow import assign_ticket, change_status


def make_ticket(ticket_id="T001", status="open", assigned_to=None, notes=None):
    """A ticket dict, optionally with notes, so no JSON file is needed."""
    ticket = {
        "id": ticket_id,
        "title": f"Ticket {ticket_id}",
        "category": "Network",
        "urgency": "high",
        "affected_users": 15,
        "priority": "critical",
        "status": status,
        "assigned_to": assigned_to,
        "notes": [] if notes is None else notes,
    }
    return ticket


def snapshot(tickets):
    """Deep-ish copy used to prove a rejected action changed nothing."""
    return [
        {**t, "notes": [dict(n) for n in t.get("notes", [])]} for t in tickets
    ]


class TestNextNoteId(unittest.TestCase):
    def test_first_note_id_on_a_ticket_with_no_notes(self):
        self.assertEqual(next_note_id(make_ticket()), "N001")

    def test_next_id_follows_the_highest_number(self):
        ticket = make_ticket(
            notes=[
                {"note_id": "N001", "author": "A", "message": "First note here."},
                {"note_id": "N002", "author": "B", "message": "Second note here."},
            ]
        )
        self.assertEqual(next_note_id(ticket), "N003")

    def test_gaps_do_not_cause_reuse(self):
        ticket = make_ticket(
            notes=[{"note_id": "N005", "author": "A", "message": "Only note here."}]
        )
        self.assertEqual(next_note_id(ticket), "N006")

    def test_survives_a_reload(self):
        # Simulates save -> load: notes round-trip through JSON as plain dicts
        # in a fresh list, so nothing is shared with the original objects.
        ticket = make_ticket()
        add_note([ticket], "T001", "Mentor A", "Rebooted the access point.")
        reloaded = copy.deepcopy(ticket)
        add_note([reloaded], "T001", "Mentor B", "Checked the switch ports.")
        self.assertEqual(next_note_id(reloaded), "N003")

    def test_tolerates_a_missing_or_malformed_notes_key(self):
        ticket = make_ticket()
        del ticket["notes"]
        self.assertEqual(next_note_id(ticket), "N001")
        self.assertEqual(next_note_id(make_ticket(notes=["junk"])), "N001")


class TestAddNote(unittest.TestCase):
    def test_valid_note_gets_the_correct_id_and_content(self):
        tickets = [make_ticket()]
        note = add_note(tickets, "T001", "  Mentor A  ", "  Rebooted the AP.  ")
        self.assertEqual(
            note,
            {
                "note_id": "N001",
                "author": "Mentor A",
                "message": "Rebooted the AP.",
            },
        )
        self.assertEqual(tickets[0]["notes"], [note])

    def test_note_ids_increment_in_order(self):
        tickets = [make_ticket()]
        first = add_note(tickets, "T001", "Mentor A", "Rebooted the AP.")
        second = add_note(tickets, "T001", "Mentor B", "Checking switch ports.")
        self.assertEqual([first["note_id"], second["note_id"]], ["N001", "N002"])

    def test_ticket_id_lookup_is_case_insensitive(self):
        tickets = [make_ticket()]
        note = add_note(tickets, " t1 ", "Mentor A", "Rebooted the AP.")
        self.assertEqual(note["note_id"], "N001")

    def test_unknown_ticket_is_rejected_and_changes_nothing(self):
        tickets = [make_ticket()]
        before = snapshot(tickets)
        with self.assertRaises(ValidationError):
            add_note(tickets, "T999", "Mentor A", "Rebooted the AP.")
        self.assertEqual(tickets, before)

    # ---- the negative cases the guide asks for --------------------------

    def test_blank_author_rejected_without_creating_a_note(self):
        tickets = [make_ticket()]
        before = snapshot(tickets)
        for bad_author in ("", "   ", None, 42):
            with self.subTest(author=bad_author):
                with self.assertRaises(ValidationError):
                    add_note(tickets, "T001", bad_author, "Rebooted the AP.")
        self.assertEqual(tickets, before)

    def test_short_and_long_messages_rejected(self):
        tickets = [make_ticket()]
        before = snapshot(tickets)
        for bad_message in ("", "1234", "   ab   ", "x" * 301):
            with self.subTest(length=len(bad_message)):
                with self.assertRaises(ValidationError):
                    add_note(tickets, "T001", "Mentor A", bad_message)
        self.assertEqual(tickets, before)

    def test_rejected_note_does_not_consume_a_note_id(self):
        """The headline rule: IDs are derived from real notes, not a counter."""
        tickets = [make_ticket()]
        add_note(tickets, "T001", "Mentor A", "Rebooted the AP.")  # N001
        with self.assertRaises(ValidationError):
            add_note(tickets, "T001", "Mentor A", "no")  # too short
        with self.assertRaises(ValidationError):
            add_note(tickets, "T001", "", "Valid message but no author.")
        second = add_note(tickets, "T001", "Mentor B", "Checking switch ports.")
        self.assertEqual(second["note_id"], "N002")  # not N003
        self.assertEqual(len(tickets[0]["notes"]), 2)

    def test_resolved_ticket_rejects_a_note_and_keeps_its_notes(self):
        # Resolve through the real workflow so the setup is legal, rather
        # than constructing a "resolved with notes" ticket by hand.
        tickets = [make_ticket(assigned_to="Mentor A")]
        add_note(tickets, "T001", "Mentor A", "Rebooted the AP.")
        change_status(tickets, "T001", "in_progress")
        change_status(tickets, "T001", "resolved")

        before = snapshot(tickets)
        with self.assertRaises(ValidationError) as ctx:
            add_note(tickets, "T001", "Mentor B", "Investigating switch ports.")
        self.assertIn("resolved", str(ctx.exception))
        self.assertEqual(tickets, before)  # notes kept, nothing added

    def test_in_progress_ticket_accepts_a_note(self):
        tickets = [make_ticket(assigned_to="Mentor A")]
        change_status(tickets, "T001", "in_progress")
        note = add_note(tickets, "T001", "Mentor B", "Investigating switch ports.")
        self.assertEqual(note["note_id"], "N001")


class TestFullNoteLifecycle(unittest.TestCase):
    """The exact scenario from the guide, end to end."""

    def test_example_from_the_brief(self):
        tickets = [make_ticket()]
        assign_ticket(tickets, "T001", "Mentor A")

        add_note(tickets, "T001", "Mentor A", "Wi-Fi router reboot attempted")
        add_note(tickets, "T001", "Mentor B", "Investigating switch ports")
        self.assertEqual([n["note_id"] for n in tickets[0]["notes"]], ["N001", "N002"])

        change_status(tickets, "T001", "in_progress")
        change_status(tickets, "T001", "resolved")

        # A resolved ticket refuses the note, and the refusal costs no ID.
        with self.assertRaises(ValidationError):
            add_note(tickets, "T001", "Mentor A", "Follow-up after closure")
        self.assertEqual(len(tickets[0]["notes"]), 2)

        change_status(tickets, "T001", "open")  # reopen
        third = add_note(tickets, "T001", "Mentor A", "Follow-up after reopening")

        self.assertEqual(third["note_id"], "N003")
        self.assertEqual(
            [n["note_id"] for n in tickets[0]["notes"]], ["N001", "N002", "N003"]
        )

    def test_notes_are_preserved_across_resolve_and_reopen(self):
        tickets = [make_ticket(assigned_to="Mentor A")]
        add_note(tickets, "T001", "Mentor A", "Rebooted the access point.")
        change_status(tickets, "T001", "in_progress")
        change_status(tickets, "T001", "resolved")
        self.assertEqual(len(tickets[0]["notes"]), 1)
        change_status(tickets, "T001", "open")
        self.assertEqual(len(tickets[0]["notes"]), 1)
        self.assertEqual(tickets[0]["notes"][0]["note_id"], "N001")


class TestCanAddNote(unittest.TestCase):
    def test_reports_allowed_for_open_and_in_progress(self):
        for status in ("open", "in_progress"):
            with self.subTest(status=status):
                allowed, reason = can_add_note(make_ticket(status=status))
                self.assertTrue(allowed)
                self.assertEqual(reason, "")

    def test_reports_refusal_with_a_reason_for_resolved(self):
        allowed, reason = can_add_note(make_ticket(status="resolved"))
        self.assertFalse(allowed)
        self.assertIn("reopen", reason.lower())

    def test_never_raises_on_a_broken_ticket(self):
        allowed, reason = can_add_note({})
        self.assertFalse(allowed)
        self.assertTrue(reason)


class TestNotesFor(unittest.TestCase):
    def test_notes_come_back_sorted_by_numeric_id(self):
        ticket = make_ticket(
            notes=[
                {"note_id": "N010", "author": "A", "message": "Tenth note here."},
                {"note_id": "N002", "author": "B", "message": "Second note here."},
            ]
        )
        ids = [n["note_id"] for n in notes_for([ticket], "T001")]
        self.assertEqual(ids, ["N002", "N010"])  # not text order

    def test_reading_notes_does_not_modify_the_ticket(self):
        ticket = make_ticket(
            notes=[
                {"note_id": "N002", "author": "B", "message": "Second note here."},
                {"note_id": "N001", "author": "A", "message": "First note here."},
            ]
        )
        before = snapshot([ticket])
        notes_for([ticket], "T001")
        self.assertEqual([ticket], before)

    def test_unknown_ticket_raises(self):
        with self.assertRaises(ValidationError):
            notes_for([make_ticket()], "T404")


if __name__ == "__main__":
    unittest.main()
