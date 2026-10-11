import unittest

from campusflow.workflow import (
    assign_ticket,
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

    def test_queue_includes_in_progress_tickets(self):
        tickets = [make_ticket("T001", status="in_progress", assigned_to="Amina")]
        self.assertEqual(len(get_work_queue(tickets)), 1)

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


if __name__ == "__main__":
    unittest.main()