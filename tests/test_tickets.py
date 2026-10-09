import unittest

from campusflow.tickets import (
    calculate_priority,
    create_ticket,
    next_ticket_id,
    validate_affected_users,
)


class TestPriority(unittest.TestCase):
    def test_high_urgency_many_users_is_critical(self):
        self.assertEqual(calculate_priority("high", 12), "critical")

    def test_high_urgency_few_users_is_high(self):
        self.assertEqual(calculate_priority("high", 2), "high")

    def test_low_urgency_four_users_is_medium(self):
        self.assertEqual(calculate_priority("low", 4), "medium")

    def test_low_urgency_one_user_is_low(self):
        self.assertEqual(calculate_priority("low", 1), "low")

    def test_boundaries(self):
        cases = [
            ("high", 10, "critical"),
            ("high", 9, "high"),
            ("low", 10, "high"),
            ("low", 3, "medium"),
            ("low", 2, "low"),
            ("medium", 1, "medium"),
        ]
        for urgency, users, expected in cases:
            with self.subTest(urgency=urgency, users=users):
                self.assertEqual(calculate_priority(urgency, users), expected)


class TestValidation(unittest.TestCase):
    def test_invalid_affected_users_rejected(self):
        for bad in (0, -1, 2.5, "abc", "2.5", "-3", "", None, True):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    validate_affected_users(bad)

    def test_digit_string_is_accepted(self):
        self.assertEqual(validate_affected_users(" 7 "), 7)

    def test_blank_title_rejected(self):
        for bad in ("", "   "):
            with self.subTest(title=bad):
                with self.assertRaises(ValueError):
                    create_ticket([], bad, "Network", "high", 5)

    def test_invalid_category_rejected(self):
        with self.assertRaises(ValueError):
            create_ticket([], "Wi-Fi down", "Plumbing", "high", 5)

    def test_invalid_urgency_rejected(self):
        with self.assertRaises(ValueError):
            create_ticket([], "Wi-Fi down", "Network", "urgent", 5)

    def test_case_variations_are_normalized(self):
        ticket = create_ticket([], "  Wi-Fi down ", "NETWORK", " High ", "12")
        self.assertEqual(ticket["title"], "Wi-Fi down")
        self.assertEqual(ticket["category"], "Network")
        self.assertEqual(ticket["urgency"], "high")
        self.assertEqual(ticket["affected_users"], 12)


class TestCreateTicket(unittest.TestCase):
    def test_new_ticket_has_expected_fields(self):
        tickets = []
        ticket = create_ticket(tickets, "Wi-Fi down", "Network", "high", 15)
        self.assertEqual(ticket["id"], "T001")
        self.assertEqual(ticket["priority"], "critical")
        self.assertEqual(ticket["status"], "open")
        self.assertIsNone(ticket["assigned_to"])
        self.assertEqual(tickets, [ticket])

    def test_ids_are_sequential(self):
        tickets = []
        ids = [create_ticket(tickets, f"Issue {i}", "Other", "low", 1)["id"] for i in range(3)]
        self.assertEqual(ids, ["T001", "T002", "T003"])

    def test_next_id_uses_numeric_max_not_length_or_string_order(self):
        existing = [{"id": "T009"}, {"id": "T010"}]
        self.assertEqual(next_ticket_id(existing), "T011")
        self.assertEqual(next_ticket_id([{"id": "T005"}]), "T006")

    def test_rejected_ticket_does_not_change_list(self):
        tickets = []
        create_ticket(tickets, "Valid", "Other", "low", 1)
        with self.assertRaises(ValueError):
            create_ticket(tickets, "Bad", "Other", "low", 0)
        self.assertEqual(len(tickets), 1)


if __name__ == "__main__":
    unittest.main()