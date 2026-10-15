"""Tests for the centralised validation helpers (Engineer A).

Each test names the rule it protects. The negative tests matter most: a
validator that accepts everything would pass a suite of "happy path" tests.
"""

import unittest

from campusflow.validation import (
    ValidationError,
    calculate_priority,
    validate_affected_users,
    validate_category,
    validate_note,
    validate_notes,
    validate_priority,
    validate_staff_label,
    validate_status,
    validate_ticket,
    validate_ticket_collection,
    validate_ticket_id,
    validate_title,
    validate_urgency,
)


def make_ticket(**overrides):
    """A ticket that passes validation, so tests only vary one thing."""
    ticket = {
        "id": "T001",
        "title": "Wi-Fi down in Block C",
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


class TestPriority(unittest.TestCase):
    def test_rule_order_boundaries(self):
        cases = [
            ("high", 10, "critical"),  # rules 1 and 2 both match: 1 wins
            ("high", 9, "high"),
            ("medium", 10, "high"),  # rule 2 beats rule 3
            ("medium", 3, "medium"),
            ("medium", 2, "medium"),  # rule 3: medium urgency alone
            ("low", 3, "medium"),
            ("low", 2, "low"),
        ]
        for urgency, users, expected in cases:
            with self.subTest(urgency=urgency, users=users):
                self.assertEqual(calculate_priority(urgency, users), expected)


class TestAffectedUsers(unittest.TestCase):
    def test_rejects_every_bad_shape(self):
        for bad in (0, -1, -100, 2.5, 0.0, "abc", "2.5", "-3", "", "   ", None, [], {}):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    validate_affected_users(bad)

    def test_rejects_booleans_even_though_bool_is_an_int(self):
        # isinstance(True, int) is True, so a naive int check would let
        # True through as the number 1 and silently corrupt the count.
        self.assertIsInstance(True, int)  # documents why this case exists
        for bad in (True, False):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    validate_affected_users(bad)

    def test_accepts_positive_ints_and_digit_strings(self):
        self.assertEqual(validate_affected_users(7), 7)
        self.assertEqual(validate_affected_users(" 7 "), 7)
        self.assertEqual(validate_affected_users("0012"), 12)

    def test_does_not_accept_underscore_or_plus_signs(self):
        for bad in ("1_0", "+5"):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    validate_affected_users(bad)


class TestFieldValidators(unittest.TestCase):
    def test_title_is_trimmed_and_blank_rejected(self):
        self.assertEqual(validate_title("  Wi-Fi down  "), "Wi-Fi down")
        for bad in ("", "   ", "\t\n", None, 5):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    validate_title(bad)

    def test_category_is_normalised_to_canonical_spelling(self):
        for supplied in ("network", " NETWORK ", "Network"):
            with self.subTest(value=supplied):
                self.assertEqual(validate_category(supplied), "Network")
        for bad in ("Plumbing", "", None, ["Network"]):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    validate_category(bad)

    def test_urgency_and_status_and_priority_reject_unknown_values(self):
        self.assertEqual(validate_urgency(" HIGH "), "high")
        self.assertEqual(validate_status("In_Progress"), "in_progress")
        self.assertEqual(validate_priority("CRITICAL"), "critical")
        for validator, bad in (
            (validate_urgency, "urgent"),
            (validate_status, "banana"),
            (validate_status, "reopened"),  # not a status, it is an action
            (validate_priority, "urgent"),
        ):
            with self.subTest(validator=validator.__name__, value=bad):
                with self.assertRaises(ValidationError):
                    validator(bad)

    def test_staff_label_is_trimmed_and_blank_rejected(self):
        self.assertEqual(validate_staff_label("  Mentor A  "), "Mentor A")
        for bad in ("", "   ", None, 7):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    validate_staff_label(bad)


class TestTicketId(unittest.TestCase):
    def test_normalises_case_and_padding(self):
        for supplied in ("T001", "t001", " t1 ", "T1"):
            with self.subTest(value=supplied):
                self.assertEqual(validate_ticket_id(supplied), "T001")

    def test_rejects_malformed_ids(self):
        for bad in ("", "T", "TABC", "1", "X001", "T00", "T-1", None, 1.5):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    validate_ticket_id(bad)

    def test_accepts_an_int_as_a_convenience(self):
        self.assertEqual(validate_ticket_id(7), "T007")


class TestValidateTicket(unittest.TestCase):
    def test_valid_ticket_is_returned_as_a_normalised_copy(self):
        cleaned = validate_ticket(make_ticket(title="  Wi-Fi down  "))
        self.assertEqual(cleaned["title"], "Wi-Fi down")
        self.assertEqual(cleaned["notes"], [])

    def test_validate_ticket_does_not_mutate_its_argument(self):
        ticket = make_ticket(title="  Wi-Fi down  ")
        before = dict(ticket)
        validate_ticket(ticket)
        self.assertEqual(ticket, before)

    def test_missing_required_field_is_rejected(self):
        ticket = make_ticket()
        del ticket["urgency"]
        with self.assertRaises(ValidationError) as ctx:
            validate_ticket(ticket)
        self.assertIn("urgency", str(ctx.exception))

    def test_non_dict_is_rejected(self):
        for bad in ([], "T001", None, 3):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    validate_ticket(bad)

    def test_priority_inconsistent_with_urgency_and_users_is_rejected(self):
        # 1 affected user and low urgency cannot produce "critical".
        with self.assertRaises(ValidationError) as ctx:
            validate_ticket(
                make_ticket(urgency="low", affected_users=1, priority="critical")
            )
        self.assertIn("does not match the rule", str(ctx.exception))

    def test_illegal_status_in_a_record_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_ticket(make_ticket(status="banana"))

    def test_in_progress_without_assignee_is_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_ticket(make_ticket(status="in_progress", assigned_to=None))
        self.assertIn("assigned_to", str(ctx.exception))

    def test_legacy_ticket_without_notes_key_is_upgraded(self):
        ticket = make_ticket()
        del ticket["notes"]  # what the original CampusFlow wrote
        cleaned = validate_ticket(ticket)
        self.assertEqual(cleaned["notes"], [])


class TestValidateNotes(unittest.TestCase):
    def test_valid_note_is_normalised(self):
        cleaned = validate_note(
            {"note_id": "n1", "author": " Mentor A ", "message": "  Rebooted AP.  "}
        )
        self.assertEqual(cleaned["note_id"], "N001")
        self.assertEqual(cleaned["author"], "Mentor A")
        self.assertEqual(cleaned["message"], "Rebooted AP.")

    def test_note_message_length_boundaries(self):
        validate_note({"note_id": "N001", "author": "A", "message": "12345"})
        validate_note({"note_id": "N001", "author": "A", "message": "1" * 300})
        for bad in ("1234", "1" * 301, "   ab   "):
            with self.subTest(message=bad):
                with self.assertRaises(ValidationError):
                    validate_note({"note_id": "N001", "author": "A", "message": bad})

    def test_note_missing_fields_and_bad_types_are_rejected(self):
        for bad in (
            {"author": "A", "message": "Rebooted AP."},
            {"note_id": "N001", "message": "Rebooted AP."},
            {"note_id": "N001", "author": "A"},
            {"note_id": "N001", "author": "  ", "message": "Rebooted AP."},
            "not a dict",
        ):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    validate_note(bad)

    def test_duplicate_note_ids_within_one_ticket_are_rejected(self):
        notes = [
            {"note_id": "N001", "author": "A", "message": "First note here."},
            {"note_id": "N001", "author": "B", "message": "Second note here."},
        ]
        with self.assertRaises(ValidationError) as ctx:
            validate_notes(notes, ticket_id="T001")
        self.assertIn("Duplicate note ID", str(ctx.exception))

    def test_notes_must_be_a_list(self):
        with self.assertRaises(ValidationError):
            validate_notes({"N001": "not a list"}, ticket_id="T001")


class TestValidateCollection(unittest.TestCase):
    def test_one_bad_record_rejects_the_whole_collection(self):
        good = [make_ticket(id="T001"), make_ticket(id="T002")]
        data = good + [make_ticket(id="T003", status="banana")]
        with self.assertRaises(ValidationError) as ctx:
            validate_ticket_collection(data, source="file 'x.json'")
        # The message names the offending record so a human can fix the file.
        self.assertIn("Ticket #3", str(ctx.exception))

    def test_duplicate_ticket_ids_are_rejected(self):
        with self.assertRaises(ValidationError) as ctx:
            validate_ticket_collection([make_ticket(), make_ticket()])
        self.assertIn("Duplicate ticket ID", str(ctx.exception))

    def test_non_list_is_rejected(self):
        for bad in ({"id": "T001"}, "T001", 5, None):
            with self.subTest(value=bad):
                with self.assertRaises(ValidationError):
                    validate_ticket_collection(bad)

    def test_empty_collection_is_valid(self):
        self.assertEqual(validate_ticket_collection([]), [])

    def test_returned_collection_is_a_new_list(self):
        data = [make_ticket()]
        result = validate_ticket_collection(data)
        self.assertIsNot(result, data)
        self.assertIsNot(result[0], data[0])


class TestValidationErrorType(unittest.TestCase):
    def test_validation_error_is_a_value_error(self):
        # Existing CLI code catches ValueError; new code can be narrower.
        self.assertTrue(issubclass(ValidationError, ValueError))


if __name__ == "__main__":
    unittest.main()
