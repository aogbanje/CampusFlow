import unittest

from campusflow.workflow import (
    assign_ticket,
    can_assign,
    can_transition,
    change_status,
    find_ticket,
    get_work_queue,
)
from campusflow.reports import build_report


def make_ticket(ticket_id, priority="low", status="open", assigned_to=None):
    """Build a plain ticket dict so no input() is needed in tests."""
    return {
        "id": ticket_id,
        "title": f"Ticket {ticket_id}",
        "category": "Other",
        "urgency": "low",
        "affected_users": 1,
        "priority": priority,
        "status": status,
        "assigned_to": assigned_to,
    }


class TestFindTicket(unittest.TestCase):
    def test_find_ticket_is_case_insensitive(self):
        tickets = [make_ticket("T001")]
        self.assertIs(find_ticket(tickets, " t001 "), tickets[0])

    def test_find_ticket_unknown_id_raises(self):
        with self.assertRaises(ValueError):
            find_ticket([make_ticket("T001")], "T404")


class TestAssign(unittest.TestCase):
    def test_assign_succeeds_with_valid_name(self):
        tickets = [make_ticket("T001")]
        result = assign_ticket(tickets, "T001", "  Amina  ")
        self.assertEqual(result["assigned_to"], "Amina")
        self.assertEqual(tickets[0]["assigned_to"], "Amina")

    def test_assign_rejects_unknown_ticket_id(self):
        tickets = [make_ticket("T001")]
        with self.assertRaises(ValueError):
            assign_ticket(tickets, "T999", "Amina")
        self.assertIsNone(tickets[0]["assigned_to"])

    def test_assign_rejects_blank_name_and_keeps_ticket_unchanged(self):
        tickets = [make_ticket("T001")]
        for bad in ("", "   ", None):
            with self.assertRaises(ValueError):
                assign_ticket(tickets, "T001", bad)
        self.assertIsNone(tickets[0]["assigned_to"])

    def test_assign_rejects_resolved_ticket_until_reopened(self):
        tickets = [make_ticket("T001", status="resolved", assigned_to="Amina")]
        with self.assertRaises(ValueError):
            assign_ticket(tickets, "T001", "Bola")
        self.assertEqual(tickets[0]["assigned_to"], "Amina")
        change_status(tickets, "T001", "open")
        assign_ticket(tickets, "T001", "Bola")
        self.assertEqual(tickets[0]["assigned_to"], "Bola")

    def test_assign_allows_reassigning_open_ticket(self):
        tickets = [make_ticket("T001", assigned_to="Amina")]
        assign_ticket(tickets, "T001", "Bola")
        self.assertEqual(tickets[0]["assigned_to"], "Bola")


class TestWorkflow(unittest.TestCase):
    def test_unassigned_ticket_cannot_go_in_progress(self):
        tickets = [make_ticket("T001")]
        with self.assertRaises(ValueError):
            change_status(tickets, "T001", "in_progress")
        self.assertEqual(tickets[0]["status"], "open")

    def test_assigned_ticket_progresses_open_to_resolved(self):
        tickets = [make_ticket("T001", assigned_to="Amina")]
        change_status(tickets, "T001", "in_progress")
        self.assertEqual(tickets[0]["status"], "in_progress")
        change_status(tickets, "T001", "resolved")
        self.assertEqual(tickets[0]["status"], "resolved")

    def test_open_cannot_jump_to_resolved(self):
        tickets = [make_ticket("T001", assigned_to="Amina")]
        with self.assertRaises(ValueError):
            change_status(tickets, "T001", "resolved")
        self.assertEqual(tickets[0]["status"], "open")

    def test_resolved_cannot_go_directly_to_in_progress(self):
        tickets = [make_ticket("T001", status="resolved", assigned_to="Amina")]
        with self.assertRaises(ValueError):
            change_status(tickets, "T001", "in_progress")
        self.assertEqual(tickets[0]["status"], "resolved")

    def test_in_progress_cannot_go_back_to_open(self):
        tickets = [make_ticket("T001", status="in_progress", assigned_to="Amina")]
        with self.assertRaises(ValueError):
            change_status(tickets, "T001", "open")
        self.assertEqual(tickets[0]["status"], "in_progress")

    def test_unknown_status_is_rejected(self):
        tickets = [make_ticket("T001", assigned_to="Amina")]
        with self.assertRaises(ValueError):
            change_status(tickets, "T001", "banana")
        self.assertEqual(tickets[0]["status"], "open")

    def test_unknown_ticket_id_is_rejected(self):
        tickets = [make_ticket("T001", assigned_to="Amina")]
        with self.assertRaises(ValueError):
            change_status(tickets, "T404", "in_progress")

    def test_reopen_sets_status_back_to_open(self):
        tickets = [make_ticket("T001", status="resolved", assigned_to="Amina")]
        change_status(tickets, "T001", "open")
        self.assertEqual(tickets[0]["status"], "open")

    def test_status_input_is_normalized(self):
        tickets = [make_ticket("T001", assigned_to="Amina")]
        change_status(tickets, "t001", "  IN_PROGRESS ")
        self.assertEqual(tickets[0]["status"], "in_progress")


class TestQueue(unittest.TestCase):
    def test_queue_sorted_by_priority_then_numeric_id(self):
        tickets = [
            make_ticket("T010", priority="critical"),
            make_ticket("T002", priority="low"),
            make_ticket("T003", priority="high"),
            make_ticket("T009", priority="critical"),
            make_ticket("T004", priority="medium"),
        ]
        ids = [t["id"] for t in get_work_queue(tickets)]
        self.assertEqual(ids, ["T009", "T010", "T003", "T004", "T002"])

    def test_queue_numeric_tie_break_beyond_three_digits(self):
        tickets = [
            make_ticket("T1000", priority="high"),
            make_ticket("T999", priority="high"),
        ]
        ids = [t["id"] for t in get_work_queue(tickets)]
        self.assertEqual(ids, ["T999", "T1000"])

    def test_queue_excludes_resolved_tickets(self):
        tickets = [
            make_ticket("T001", priority="critical", status="resolved"),
            make_ticket("T002", priority="low"),
        ]
        ids = [t["id"] for t in get_work_queue(tickets)]
        self.assertEqual(ids, ["T002"])

    def test_queue_excludes_in_progress_tickets(self):
        """CHANGED in CampusFlow Next.

        The original version included in_progress tickets in the Open Work
        Queue (QUEUE_STATUSES = ("open", "in_progress")). The acceptance
        contract now says the queue shows OPEN tickets only, so this test
        asserts the opposite of what it used to. An in_progress ticket is
        still unresolved -- it appears in the reports and in the
        priority-sorted search view, just not in this queue.
        """
        tickets = [make_ticket("T001", status="in_progress", assigned_to="Amina")]
        self.assertEqual(get_work_queue(tickets), [])

    def test_queue_shows_only_open_tickets_from_a_mixed_collection(self):
        tickets = [
            make_ticket("T001", priority="critical", status="open"),
            make_ticket("T002", priority="critical", status="in_progress", assigned_to="Amina"),
            make_ticket("T003", priority="high", status="resolved", assigned_to="Amina"),
            make_ticket("T004", priority="low", status="open"),
        ]
        ids = [t["id"] for t in get_work_queue(tickets)]
        self.assertEqual(ids, ["T001", "T004"])

    def test_empty_queue(self):
        self.assertEqual(get_work_queue([]), [])

    def test_queue_does_not_reorder_original_list(self):
        tickets = [
            make_ticket("T001", priority="low"),
            make_ticket("T002", priority="critical"),
        ]
        get_work_queue(tickets)
        self.assertEqual([t["id"] for t in tickets], ["T001", "T002"])


class TestReports(unittest.TestCase):
    def test_empty_report_has_zero_counts(self):
        report = build_report([])
        self.assertEqual(report["total"], 0)
        self.assertEqual(
            report["by_status"], {"open": 0, "in_progress": 0, "resolved": 0}
        )
        self.assertEqual(
            report["by_priority"],
            {"critical": 0, "high": 0, "medium": 0, "low": 0},
        )

    def test_report_counts_mixed_tickets(self):
        tickets = [
            make_ticket("T001", priority="critical", status="open"),
            make_ticket("T002", priority="critical", status="resolved"),
            make_ticket("T003", priority="low", status="in_progress"),
        ]
        report = build_report(tickets)
        self.assertEqual(report["total"], 3)
        self.assertEqual(
            report["by_status"], {"open": 1, "in_progress": 1, "resolved": 1}
        )
        self.assertEqual(
            report["by_priority"],
            {"critical": 2, "high": 0, "medium": 0, "low": 1},
        )

    def test_report_counts_add_up_to_total(self):
        tickets = [
            make_ticket("T001", priority="high"),
            make_ticket("T002", priority="medium", status="resolved"),
            make_ticket("T003", priority="medium"),
            make_ticket("T004", priority="low", status="in_progress"),
        ]
        report = build_report(tickets)
        self.assertEqual(sum(report["by_status"].values()), report["total"])
        self.assertEqual(sum(report["by_priority"].values()), report["total"])

    def test_report_does_not_change_tickets(self):
        tickets = [make_ticket("T001", priority="high")]
        before = [dict(t) for t in tickets]
        build_report(tickets)
        self.assertEqual(tickets, before)


class TestCanTransition(unittest.TestCase):
    """The lifecycle predicate is the single source of truth for legality.

    It must agree with change_status in BOTH directions: never say "allowed"
    for a move change_status refuses, and never say "refused" for one it
    accepts.
    """

    def test_reports_allowed_for_the_legal_path(self):
        allowed, reason = can_transition(make_ticket("T001", assigned_to="Amina"), "in_progress")
        self.assertTrue(allowed)
        self.assertEqual(reason, "")

    def test_reports_refusal_with_a_reason_instead_of_raising(self):
        allowed, reason = can_transition(make_ticket("T001"), "in_progress")
        self.assertFalse(allowed)
        self.assertIn("assigned", reason.lower())

    def test_unknown_status_is_refused_not_raised(self):
        allowed, reason = can_transition(make_ticket("T001", assigned_to="A"), "banana")
        self.assertFalse(allowed)
        self.assertTrue(reason)

    def test_predicate_never_raises_and_never_mutates(self):
        for status in ("open", "in_progress", "resolved", "banana", None):
            for target in ("open", "in_progress", "resolved", "banana", None):
                with self.subTest(current=status, target=target):
                    ticket = make_ticket("T001", status=status, assigned_to="Amina")
                    before = dict(ticket)
                    can_transition(ticket, target)  # must not raise
                    self.assertEqual(ticket, before)

    def test_predicate_agrees_with_change_status(self):
        """Cross-check: every combination gives the same verdict both ways."""
        for current in ("open", "in_progress", "resolved"):
            for assignee in (None, "Amina"):
                for target in ("open", "in_progress", "resolved", "banana"):
                    with self.subTest(current=current, assignee=assignee, target=target):
                        tickets = [
                            make_ticket("T001", status=current, assigned_to=assignee)
                        ]
                        allowed, _ = can_transition(tickets[0], target)
                        before = [dict(t) for t in tickets]
                        try:
                            change_status(tickets, "T001", target)
                            acted = True
                        except ValueError:
                            acted = False
                            # A refusal must not have written anything.
                            self.assertEqual(tickets, before)
                        self.assertEqual(
                            allowed,
                            acted,
                            f"can_transition said {allowed} but change_status "
                            f"{'succeeded' if acted else 'raised'}",
                        )


class TestCanAssign(unittest.TestCase):
    def test_resolved_tickets_are_refused_with_a_reason(self):
        allowed, reason = can_assign(make_ticket("T001", status="resolved"))
        self.assertFalse(allowed)
        self.assertIn("reopen", reason.lower())

    def test_open_and_in_progress_tickets_can_be_assigned(self):
        for status in ("open", "in_progress"):
            with self.subTest(status=status):
                allowed, _ = can_assign(make_ticket("T001", status=status))
                self.assertTrue(allowed)

    def test_never_raises_on_a_broken_ticket(self):
        allowed, reason = can_assign({})
        self.assertTrue(allowed)  # no status key -> not resolved
        self.assertEqual(reason, "")


if __name__ == "__main__":
    unittest.main()