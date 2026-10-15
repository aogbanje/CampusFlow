"""Tests for the report and quality insights (Engineer B).

Acceptance cases covered:
  10 - an empty report returns 0% and does not crash
  11 - counts agree with a known fixture after resolve/reopen

Also pinned: no double-counting, unresolved = open + in_progress, and the
report never edits the collection it is given.
"""

import unittest

from campusflow.reports import build_report, format_percentage
from campusflow.validation import calculate_priority
from campusflow.workflow import change_status


def make_ticket(
    ticket_id,
    category="Other",
    urgency="low",
    affected_users=1,
    status="open",
    assigned_to=None,
):
    """A valid ticket dict with its priority DERIVED from the rule.

    Hand-setting a priority would let a fixture contradict
    ``calculate_priority``, and ``save_tickets`` rejects such a ticket -- so
    tests would fail for a reason unrelated to what they are checking.
    """
    return {
        "id": ticket_id,
        "title": f"Ticket {ticket_id}",
        "category": category,
        "urgency": urgency,
        "affected_users": affected_users,
        "priority": calculate_priority(urgency, affected_users),
        "status": status,
        "assigned_to": assigned_to,
        "notes": [],
    }


class TestEmptyReport(unittest.TestCase):
    def test_empty_dataset_reports_zero_percent_without_crashing(self):
        """Case 10: the ZeroDivisionError guard.

        Dividing by len(tickets) before checking for zero would raise here.
        """
        report = build_report([])
        self.assertEqual(report["resolution_percentage"], 0.0)

    def test_empty_dataset_has_a_complete_zero_filled_report(self):
        report = build_report([])
        self.assertEqual(report["total"], 0)
        self.assertEqual(report["unresolved"], 0)
        self.assertEqual(report["resolved"], 0)
        self.assertEqual(
            report["by_status"], {"open": 0, "in_progress": 0, "resolved": 0}
        )
        self.assertEqual(
            report["by_priority"],
            {"critical": 0, "high": 0, "medium": 0, "low": 0},
        )
        self.assertEqual(
            report["by_category"],
            {"Network": 0, "Hardware": 0, "Software": 0, "Other": 0},
        )

    def test_every_category_key_exists_even_when_unused(self):
        """A caller must be able to index by_category without a key check."""
        report = build_report([make_ticket("T001", category="Network")])
        self.assertEqual(report["by_category"]["Software"], 0)


class TestKnownFixture(unittest.TestCase):
    def setUp(self):
        """A known three-ticket fixture with a legal mixed lifecycle.

        Urgency and affected_users are chosen so the derived priorities are
        critical / high / medium exactly as the rule prescribes.
        """
        self.tickets = [
            make_ticket(
                "T001", category="Network", urgency="high", affected_users=10
            ),  # -> critical
            make_ticket(
                "T002",
                category="Hardware",
                urgency="high",
                affected_users=1,
                status="in_progress",
                assigned_to="Amina",
            ),  # -> high
            make_ticket(
                "T003",
                category="Software",
                urgency="medium",
                affected_users=1,
                status="resolved",
                assigned_to="Bola",
            ),  # -> medium
        ]

    def test_counts_agree_with_the_fixture(self):
        """Case 11: exact counts against a hand-checked fixture."""
        report = build_report(self.tickets)

        self.assertEqual(report["total"], 3)
        self.assertEqual(
            report["by_status"], {"open": 1, "in_progress": 1, "resolved": 1}
        )
        self.assertEqual(
            report["by_priority"],
            {"critical": 1, "high": 1, "medium": 1, "low": 0},
        )
        self.assertEqual(
            report["by_category"],
            {"Network": 1, "Hardware": 1, "Software": 1, "Other": 0},
        )
        self.assertEqual(report["unresolved"], 2)
        self.assertEqual(report["resolved"], 1)
        self.assertAlmostEqual(report["resolution_percentage"], 100 / 3)

    def test_counts_still_agree_after_a_resolve_and_a_reopen(self):
        """Case 11, second half: the same fixture driven through the real
        workflow, so the numbers are produced by the app and not by hand."""
        # T001 is unassigned, so this must be refused and change nothing.
        with self.assertRaises(ValueError):
            change_status(self.tickets, "T001", "in_progress")
        self.assertEqual(self.tickets[0]["status"], "open")

        change_status(self.tickets, "T003", "open")  # reopen a resolved ticket
        report = build_report(self.tickets)

        self.assertEqual(
            report["by_status"], {"open": 2, "in_progress": 1, "resolved": 0}
        )
        self.assertEqual(report["unresolved"], 3)
        self.assertEqual(report["resolved"], 0)
        self.assertEqual(report["resolution_percentage"], 0.0)

    def test_resolved_then_reopened_counts_by_current_status_only(self):
        """A reopened ticket is open NOW, and must not also count as resolved."""
        tickets = [make_ticket("T001", status="resolved", assigned_to="Amina")]
        change_status(tickets, "T001", "open")

        report = build_report(tickets)
        self.assertEqual(report["by_status"]["open"], 1)
        self.assertEqual(report["by_status"]["resolved"], 0)
        self.assertEqual(report["resolved"], 0)
        self.assertEqual(report["total"], 1)


class TestNoDoubleCounting(unittest.TestCase):
    def test_status_counts_sum_to_the_total(self):
        tickets = [
            make_ticket("T001", status="open"),
            make_ticket("T002", status="in_progress", assigned_to="Amina"),
            make_ticket("T003", status="resolved", assigned_to="Bola"),
            make_ticket("T004", status="open"),
        ]
        report = build_report(tickets)
        self.assertEqual(sum(report["by_status"].values()), report["total"])

    def test_priority_and_category_counts_sum_to_the_total(self):
        tickets = [
            make_ticket("T001", category="Network", urgency="high", affected_users=1),
            make_ticket("T002", category="Network", urgency="high", affected_users=1),
            make_ticket("T003", category="Other"),
        ]
        report = build_report(tickets)
        self.assertEqual(sum(report["by_priority"].values()), report["total"])
        self.assertEqual(sum(report["by_category"].values()), report["total"])

    def test_unresolved_and_resolved_account_for_every_ticket(self):
        """Every ticket is either resolved or unresolved -- never both, never
        neither. This is the invariant that makes the two figures trustworthy."""
        tickets = [
            make_ticket("T001", status="open"),
            make_ticket("T002", status="in_progress", assigned_to="Amina"),
            make_ticket("T003", status="resolved", assigned_to="Bola"),
        ]
        report = build_report(tickets)
        self.assertEqual(report["unresolved"] + report["resolved"], report["total"])

    def test_unresolved_is_open_plus_in_progress(self):
        tickets = [
            make_ticket("T001", status="open"),
            make_ticket("T002", status="open"),
            make_ticket("T003", status="in_progress", assigned_to="Amina"),
            make_ticket("T004", status="resolved", assigned_to="Bola"),
        ]
        report = build_report(tickets)
        self.assertEqual(report["unresolved"], 3)

    def test_an_in_progress_ticket_counts_as_unresolved_not_resolved(self):
        tickets = [make_ticket("T001", status="in_progress", assigned_to="Amina")]
        report = build_report(tickets)
        self.assertEqual(report["unresolved"], 1)
        self.assertEqual(report["resolved"], 0)
        self.assertEqual(report["resolution_percentage"], 0.0)


class TestReportIsReadOnly(unittest.TestCase):
    def test_report_does_not_change_tickets(self):
        tickets = [make_ticket("T001", urgency="high", affected_users=1)]
        before = [dict(ticket) for ticket in tickets]
        build_report(tickets)
        self.assertEqual(tickets, before)

    def test_report_does_not_reorder_the_collection(self):
        tickets = [make_ticket("T002"), make_ticket("T001")]
        build_report(tickets)
        self.assertEqual([t["id"] for t in tickets], ["T002", "T001"])


class TestFormatPercentage(unittest.TestCase):
    def test_zero_formats_as_zero_point_zero_percent(self):
        self.assertEqual(format_percentage(0.0), "0.0%")

    def test_full_resolution_formats_as_one_hundred_percent(self):
        self.assertEqual(format_percentage(100.0), "100.0%")

    def test_rounds_to_one_decimal_place(self):
        self.assertEqual(format_percentage(100 / 3), "33.3%")


if __name__ == "__main__":
    unittest.main()
