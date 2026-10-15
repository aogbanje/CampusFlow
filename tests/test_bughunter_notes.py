"""B's extra bug-hunter test, aimed at Engineer A's notes module (§06).

The brief asks each engineer to devise ONE previously unlisted edge case for
the OTHER engineer's module, and to record initial state, input, expected
result, actual result, test name and any code change.

Finding
-------
``campusflow/notes.py`` guards the shape of a note in one place and not in
another:

* ``next_note_id``  checks ``isinstance(note, dict)`` and
  ``isinstance(note_id, str)`` before reading, so it survives junk.
  A even tests that: ``test_tolerates_a_missing_or_malformed_notes_key``.
* ``notes_for``    sorts with ``int(note["note_id"][1:])`` directly.

So a ticket holding a structurally-broken note in memory makes ``notes_for``
raise ``KeyError`` / ``TypeError`` / ``ValueError`` -- and none of those is a
``ValidationError``. ``main.handle_view_notes`` catches ``ValidationError``
only, so the CLI would show a traceback instead of friendly feedback.

* Initial state: a ticket whose ``notes`` list holds a note with no
  ``note_id`` (or a non-dict entry).
* Input: ``notes_for(tickets, "T001")``.
* Expected: ``ValidationError`` -- the one exception type the CLI handles.
* Actual: ``KeyError`` (missing ``note_id``) / ``TypeError`` (non-dict).
* Test name: ``test_notes_for_reports_a_malformed_note_as_a_validation_error``.
* Code change made: none in this branch -- ``notes.py`` is Engineer A's file.
  Raised for their fix; the test is marked ``expectedFailure`` so the suite
  stays green and the gap is still visible in the test output. Flipping the
  decorator is the signal that the fix has landed.

The second test here pins an invariant that was correct but unlisted: note
IDs are unique PER TICKET, so two tickets may each own an ``N001``.
"""

import unittest

from campusflow.notes import notes_for
from campusflow.validation import ValidationError


def make_ticket(ticket_id, notes=None, status="open", assigned_to=None):
    return {
        "id": ticket_id,
        "title": f"Ticket {ticket_id}",
        "category": "Other",
        "urgency": "low",
        "affected_users": 1,
        "priority": "low",
        "status": status,
        "assigned_to": assigned_to,
        "notes": list(notes or []),
    }


class TestNotesForRejectsMalformedNotes(unittest.TestCase):
    """The bug-hunter finding: a shape guard that exists in one function but
    not its neighbour, with a CLI-visible consequence."""

    @unittest.expectedFailure
    def test_notes_for_reports_a_malformed_note_as_a_validation_error(self):
        tickets = [make_ticket("T001", notes=[{"author": "a", "message": "hello"}])]
        with self.assertRaises(ValidationError):
            notes_for(tickets, "T001")

    @unittest.expectedFailure
    def test_notes_for_reports_a_non_dict_note_as_a_validation_error(self):
        tickets = [make_ticket("T001", notes=["not a note"])]
        with self.assertRaises(ValidationError):
            notes_for(tickets, "T001")

    def test_the_crash_is_real_and_is_not_a_validation_error(self):
        """Evidence for the write-up: the exception type is wrong.

        This test PASSES today and documents the actual behaviour, so the
        finding is reproducible from the suite rather than only from prose.

        It is written to survive the fix: once ``notes_for`` raises
        ``ValidationError`` this test fails with a message telling you to
        remove the ``expectedFailure`` decorators above, rather than
        silently passing on the wrong exception.
        """
        tickets = [make_ticket("T001", notes=[{"author": "a", "message": "hello"}])]

        try:
            notes_for(tickets, "T001")
        except ValidationError:
            self.fail(
                "notes_for now raises ValidationError: the gap is fixed. "
                "Remove the expectedFailure decorators above."
            )
        except Exception as error:  # noqa: BLE001 - the type is the point
            self.assertNotIsInstance(error, ValidationError)
        else:
            self.fail("Expected notes_for to fail on a malformed note.")

    def test_a_well_formed_note_still_reads_normally(self):
        """The guard must not be needed for healthy data -- this pins the
        path the fix has to preserve."""
        tickets = [
            make_ticket(
                "T001",
                notes=[{"note_id": "N001", "author": "Mentor A", "message": "Rebooted."}],
            )
        ]
        notes = notes_for(tickets, "T001")
        self.assertEqual([note["note_id"] for note in notes], ["N001"])


class TestNoteIdsAreScopedPerTicket(unittest.TestCase):
    """A previously unlisted invariant: the brief says a note is identified by
    its ticket ID PLUS its note ID, so N001 is legally reused across tickets."""

    def test_two_tickets_may_each_own_an_n001(self):
        shared = {"note_id": "N001", "author": "Mentor A", "message": "Same idea."}
        tickets = [
            make_ticket("T001", notes=[dict(shared)]),
            make_ticket("T002", notes=[dict(shared)]),
        ]

        first = notes_for(tickets, "T001")
        second = notes_for(tickets, "T002")

        self.assertEqual([n["note_id"] for n in first], ["N001"])
        self.assertEqual([n["note_id"] for n in second], ["N001"])

    def test_reading_one_ticket_never_returns_another_tickets_notes(self):
        tickets = [
            make_ticket(
                "T001",
                notes=[{"note_id": "N001", "author": "A", "message": "First ticket."}],
            ),
            make_ticket(
                "T002",
                notes=[{"note_id": "N001", "author": "B", "message": "Second ticket."}],
            ),
        ]

        notes = notes_for(tickets, "T001")

        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["message"], "First ticket.")

    def test_ids_within_one_ticket_are_numeric_not_textual_order(self):
        """'N10' sorts before 'N2' as text -- the same trap as ticket IDs."""
        tickets = [
            make_ticket(
                "T001",
                notes=[
                    {"note_id": "N10", "author": "A", "message": "Tenth note."},
                    {"note_id": "N2", "author": "A", "message": "Second note."},
                    {"note_id": "N1", "author": "A", "message": "First note."},
                ],
            )
        ]

        ids = [note["note_id"] for note in notes_for(tickets, "T001")]

        self.assertEqual(ids, ["N1", "N2", "N10"])


if __name__ == "__main__":
    unittest.main()
