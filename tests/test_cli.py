"""Tests for the command-line interface (Engineer B).

Milestone B6 asks for tests of invalid CLI choices. The handlers take
``input_fn`` / ``output_fn`` so every one of these runs headlessly: a scripted
reply list stands in for the keyboard, and the collected output lines stand in
for the screen. No test in this file touches data/tickets.json -- DATA_FILE is
patched to a throwaway path.
"""

import os
import tempfile
import unittest
from unittest import mock

import main
from campusflow.validation import calculate_priority


class ScriptedInput:
    """Returns the next scripted reply, and records the prompts asked."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, prompt=""):
        self.prompts.append(prompt)
        if not self.replies:
            raise AssertionError(f"More input asked for than scripted: {prompt!r}")
        return self.replies.pop(0)


class OutputCollector:
    def __init__(self):
        self.lines = []

    def __call__(self, *parts, **kwargs):
        self.lines.append(" ".join(str(part) for part in parts))

    @property
    def text(self):
        return "\n".join(self.lines)


def make_ticket(
    ticket_id,
    title="Wi-Fi down",
    category="Network",
    urgency="high",
    affected_users=15,
    status="open",
    assigned_to=None,
    notes=None,
):
    """A valid ticket dict.

    ``priority`` is DERIVED from urgency and affected_users rather than passed
    in, because ``save_tickets`` validates the whole collection before it
    writes. A fixture with a hand-set priority that disagrees with the rule
    would be rejected by the save inside a handler, and the test would fail
    for a reason that has nothing to do with what it is checking.
    """
    return {
        "id": ticket_id,
        "title": title,
        "category": category,
        "urgency": urgency,
        "affected_users": affected_users,
        "priority": calculate_priority(urgency, affected_users),
        "status": status,
        "assigned_to": assigned_to,
        "notes": list(notes or []),
    }


class CliTestCase(unittest.TestCase):
    """Gives every test a throwaway save path instead of data/tickets.json."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.data_file = os.path.join(tmp.name, "data", "tickets.json")

        patcher = mock.patch.object(main, "DATA_FILE", self.data_file)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_handler(self, handler, tickets, replies):
        scripted = ScriptedInput(replies)
        output = OutputCollector()
        handler(tickets, scripted, output)
        return scripted, output


class TestMenu(unittest.TestCase):
    def test_menu_offers_search_notes_and_the_understanding_check(self):
        labels = " ".join(label for label, _ in main.MENU.values())
        self.assertIn("Search tickets", labels)
        self.assertIn("Add follow-up note", labels)
        self.assertIn("View ticket notes", labels)
        self.assertIn("Engineering Understanding Check", labels)

    def test_work_queue_is_still_its_own_option(self):
        """Requirement D: the original Open Work Queue is not silently
        replaced by a different status filter."""
        self.assertIn("Open work queue", main.MENU["5"][0])

    def test_invalid_choice_re_prompts_instead_of_crashing(self):
        scripted = ScriptedInput(["bogus", "99", "0"])
        output = OutputCollector()
        main.run_menu([], scripted, output)

        self.assertEqual(
            output.lines.count("Invalid option. Please choose from the menu."), 2
        )
        self.assertIn("Goodbye.", output.text)

    def test_exit_leaves_the_loop(self):
        output = OutputCollector()
        main.run_menu([], ScriptedInput(["0"]), output)
        self.assertIn("Goodbye.", output.text)

    def test_a_handler_error_does_not_end_the_session(self):
        """A failure inside one option must return to the menu, not abort."""
        scripted = ScriptedInput(["4", "T404", "resolved", "0"])
        output = OutputCollector()
        main.run_menu([], scripted, output)

        self.assertIn("Error:", output.text)
        self.assertIn("Goodbye.", output.text)


class TestNoteMenu(CliTestCase):
    def test_add_note_succeeds_on_an_open_ticket(self):
        tickets = [make_ticket("T001")]
        _, output = self.run_handler(
            main.handle_add_note, tickets, ["T001", "Mentor A", "Rebooted the AP."]
        )
        self.assertEqual(tickets[0]["notes"][0]["note_id"], "N001")
        self.assertIn("Added N001 to T001.", output.text)

    def test_a_resolved_ticket_is_refused_before_asking_for_an_author(self):
        """The friendly path: the user is not made to type an author and a
        message for a note that cannot be saved."""
        tickets = [
            make_ticket("T001", status="resolved", assigned_to="Amina")
        ]
        scripted, output = self.run_handler(
            main.handle_add_note, tickets, ["T001"]
        )

        self.assertIn("Cannot add a note", output.text)
        self.assertEqual(tickets[0]["notes"], [])
        # Only the ticket ID was asked for -- no author, no message.
        self.assertEqual(len(scripted.prompts), 1)

    def test_unknown_ticket_id_shows_an_error_and_changes_nothing(self):
        tickets = [make_ticket("T001")]
        _, output = self.run_handler(main.handle_add_note, tickets, ["T404"])
        self.assertIn("Error:", output.text)
        self.assertEqual(tickets[0]["notes"], [])

    def test_blank_author_is_refused_and_changes_nothing(self):
        tickets = [make_ticket("T001")]
        _, output = self.run_handler(
            main.handle_add_note, tickets, ["T001", "   ", "Valid message here."]
        )
        self.assertIn("Error:", output.text)
        self.assertEqual(tickets[0]["notes"], [])

    def test_too_short_message_is_refused_without_consuming_a_note_id(self):
        tickets = [make_ticket("T001")]
        _, output = self.run_handler(
            main.handle_add_note, tickets, ["T001", "Mentor A", "hi"]
        )
        self.assertIn("Error:", output.text)
        self.assertEqual(tickets[0]["notes"], [])

        # A later valid note must still be N001 -- no ID was used up.
        self.run_handler(
            main.handle_add_note, tickets, ["T001", "Mentor A", "Long enough now."]
        )
        self.assertEqual(tickets[0]["notes"][0]["note_id"], "N001")

    def test_view_notes_lists_them_in_id_order(self):
        tickets = [
            make_ticket(
                "T001",
                notes=[
                    {"note_id": "N002", "author": "Mentor B", "message": "Second note."},
                    {"note_id": "N001", "author": "Mentor A", "message": "First note."},
                ],
            )
        ]
        _, output = self.run_handler(main.handle_view_notes, tickets, ["T001"])

        first = output.text.index("N001")
        second = output.text.index("N002")
        self.assertLess(first, second)

    def test_view_notes_on_a_ticket_without_notes_says_so(self):
        tickets = [make_ticket("T001")]
        _, output = self.run_handler(main.handle_view_notes, tickets, ["T001"])
        self.assertIn("No follow-up notes on T001", output.text)

    def test_view_notes_on_an_unknown_ticket_shows_an_error(self):
        _, output = self.run_handler(main.handle_view_notes, [make_ticket("T001")], ["T404"])
        self.assertIn("Error:", output.text)


class TestSearchMenu(CliTestCase):
    def test_search_combines_title_and_filters(self):
        tickets = [
            make_ticket("T001", title="Wi-Fi down in Lab 3", category="Network"),
            make_ticket(
                "T002",
                title="Wi-Fi fixed",
                category="Network",
                urgency="high",
                affected_users=1,
                status="resolved",
                assigned_to="Amina",
            ),
            make_ticket(
                "T003",
                title="Laptop dead",
                category="Hardware",
                urgency="medium",
                affected_users=1,
            ),
        ]
        _, output = self.run_handler(
            main.handle_search, tickets, ["wi-fi", "Network", "open", ""]
        )

        self.assertIn("T001", output.text)
        self.assertNotIn("T002", output.text)
        self.assertNotIn("T003", output.text)

    def test_an_invalid_category_re_prompts_rather_than_failing(self):
        tickets = [make_ticket("T001", title="Wi-Fi down", category="Network")]
        scripted, output = self.run_handler(
            main.handle_search, tickets, ["wi-fi", "Electronics", "Network", "", ""]
        )

        self.assertIn("is not one of", output.text)
        self.assertIn("T001", output.text)
        # Six prompts: title, then category twice (the bad one and the retry),
        # then status and priority.
        self.assertEqual(len(scripted.prompts), 5)

    def test_blank_filters_are_accepted_as_do_not_filter(self):
        tickets = [
            make_ticket("T001", title="Wi-Fi down"),
            make_ticket("T002", title="Laptop dead"),
        ]
        _, output = self.run_handler(main.handle_search, tickets, ["", "", "", ""])
        self.assertIn("2 ticket(s) match", output.text)

    def test_no_matches_is_reported_clearly(self):
        tickets = [make_ticket("T001", title="Wi-Fi down")]
        _, output = self.run_handler(
            main.handle_search, tickets, ["printer", "", "", ""]
        )
        self.assertIn("No tickets match your search.", output.text)

    def test_search_does_not_modify_tickets(self):
        tickets = [make_ticket("T001", title="Wi-Fi down")]
        before = [dict(ticket) for ticket in tickets]
        self.run_handler(main.handle_search, tickets, ["wi-fi", "", "", ""])
        self.assertEqual(tickets, before)


class TestReportsMenu(CliTestCase):
    def test_empty_collection_reports_zero_percent(self):
        _, output = self.run_handler(main.handle_reports, [], [])
        self.assertIn("Resolution rate: 0.0%", output.text)
        self.assertIn("Total tickets: 0", output.text)

    def test_reports_show_every_required_section(self):
        tickets = [
            make_ticket("T001", status="open"),
            make_ticket("T002", status="resolved", assigned_to="Amina"),
        ]
        _, output = self.run_handler(main.handle_reports, tickets, [])

        for expected in (
            "Total tickets: 2",
            "Unresolved (open + in_progress): 1",
            "Resolved: 1",
            "Resolution rate: 50.0%",
            "By status:",
            "By priority:",
            "By category:",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, output.text)


class TestWorkQueueMenu(CliTestCase):
    def test_queue_menu_shows_open_tickets_only(self):
        """The original queue keeps its original meaning."""
        tickets = [
            make_ticket("T001", status="open"),
            make_ticket("T002", status="in_progress", assigned_to="Amina"),
            make_ticket("T003", status="resolved", assigned_to="Bola"),
        ]
        _, output = self.run_handler(main.handle_queue, tickets, [])

        self.assertIn("T001", output.text)
        self.assertNotIn("T002", output.text)
        self.assertNotIn("T003", output.text)

    def test_empty_queue_is_reported(self):
        _, output = self.run_handler(main.handle_queue, [], [])
        self.assertIn("The work queue is empty.", output.text)


class TestCreateAndListMenus(CliTestCase):
    def test_create_then_list_round_trip(self):
        tickets = []
        self.run_handler(
            main.handle_create, tickets, ["Wi-Fi down", "Network", "high", "15"]
        )
        self.assertEqual(len(tickets), 1)
        self.assertEqual(tickets[0]["priority"], "critical")

        _, output = self.run_handler(main.handle_list, tickets, [""])
        self.assertIn("T001", output.text)

    def test_invalid_create_is_reported_and_adds_nothing(self):
        tickets = []
        _, output = self.run_handler(
            main.handle_create, tickets, ["Wi-Fi down", "Network", "high", "0"]
        )
        self.assertIn("Error:", output.text)
        self.assertEqual(tickets, [])

    def test_list_on_an_empty_collection_says_so(self):
        _, output = self.run_handler(main.handle_list, [], [])
        self.assertIn("No tickets yet.", output.text)

    def test_viewing_an_unknown_ticket_from_the_list_shows_an_error(self):
        tickets = [make_ticket("T001")]
        _, output = self.run_handler(main.handle_list, tickets, ["T999"])
        self.assertIn("Error:", output.text)


class TestAssignAndStatusMenus(CliTestCase):
    def test_assign_then_progress_a_ticket(self):
        tickets = [make_ticket("T001")]
        self.run_handler(main.handle_assign, tickets, ["T001", "Amina"])
        self.assertEqual(tickets[0]["assigned_to"], "Amina")

        self.run_handler(main.handle_status, tickets, ["T001", "in_progress"])
        self.assertEqual(tickets[0]["status"], "in_progress")

    def test_unassigned_ticket_cannot_move_to_in_progress(self):
        tickets = [make_ticket("T001")]
        _, output = self.run_handler(main.handle_status, tickets, ["T001", "in_progress"])

        self.assertIn("Error:", output.text)
        self.assertEqual(tickets[0]["status"], "open")

    def test_assigning_a_blank_name_changes_nothing(self):
        tickets = [make_ticket("T001")]
        _, output = self.run_handler(main.handle_assign, tickets, ["T001", "   "])

        self.assertIn("Error:", output.text)
        self.assertIsNone(tickets[0]["assigned_to"])


if __name__ == "__main__":
    unittest.main()
