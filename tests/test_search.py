"""Tests for combined search and filtering (Engineer B).

Acceptance cases covered:
  08 - search title ignores case and matches a substring
  09 - combined search filters use AND

Supporting properties also pinned here: search is read-only, blank filters
mean "do not filter", an illegal filter is reported rather than silently
matching nothing, and the priority tie-break compares IDs numerically.
"""

import unittest

from campusflow.search import search_tickets, sort_by_priority
from campusflow.validation import ValidationError


def make_ticket(
    ticket_id,
    title=None,
    category="Other",
    priority="low",
    status="open",
    assigned_to=None,
):
    """A plain ticket dict, so no input() is needed anywhere in these tests."""
    return {
        "id": ticket_id,
        "title": title if title is not None else f"Ticket {ticket_id}",
        "category": category,
        "urgency": "low",
        "affected_users": 1,
        "priority": priority,
        "status": status,
        "assigned_to": assigned_to,
        "notes": [],
    }


# A small mixed fixture reused by several tests. Deliberately unrelated to
# the campus domain for the pure-ordering tests, so a passing test cannot be
# an accident of the wording.
WIFI_OPEN = make_ticket("T001", "Wi-Fi down in Lab 3", "Network", "critical", "open")
WIFI_RESOLVED = make_ticket(
    "T002", "Wi-Fi router reboot", "Network", "high", "resolved", "Amina"
)
LAPTOP_OPEN = make_ticket("T003", "Laptop screen cracked", "Hardware", "medium", "open")
SOFTWARE_PROGRESS = make_ticket(
    "T004", "Install Python on lab PC", "Software", "low", "in_progress", "Bola"
)


class TestTitleSearch(unittest.TestCase):
    def test_title_search_ignores_case(self):
        """Case 08: 'WI-FI' must find 'Wi-Fi down in Lab 3'."""
        results = search_tickets([WIFI_OPEN, LAPTOP_OPEN], query="WI-FI")
        self.assertEqual([t["id"] for t in results], ["T001"])

    def test_title_search_matches_a_substring_not_a_whole_word(self):
        results = search_tickets([WIFI_OPEN, LAPTOP_OPEN], query="lab 3")
        self.assertEqual([t["id"] for t in results], ["T001"])

    def test_case_difference_in_both_directions(self):
        ticket = make_ticket("T001", "WIFI outage", "Network")
        for query in ("wifi", "WIFI", "WiFi", "wIfI"):
            with self.subTest(query=query):
                self.assertEqual(len(search_tickets([ticket], query=query)), 1)

    def test_casefold_matches_where_lower_would_not(self):
        """casefold() is not just a stricter lower(): it folds 'ß' to 'ss'.

        'Straße'.casefold() is 'strasse', but 'Straße'.lower() is still
        'straße'. A search built on lower() would miss this match entirely,
        so this test guards the choice recorded in the AI learning log.
        """
        ticket = make_ticket("T001", "Straße network down", "Network")
        self.assertEqual(len(search_tickets([ticket], query="STRASSE")), 1)

        # Evidence that lower() really would have failed here.
        self.assertNotIn("STRASSE".lower(), "Straße network down".lower())

    def test_empty_query_matches_every_ticket(self):
        tickets = [WIFI_OPEN, LAPTOP_OPEN, SOFTWARE_PROGRESS]
        self.assertEqual(len(search_tickets(tickets, query="")), 3)

    def test_whitespace_only_query_is_treated_as_no_filter(self):
        tickets = [WIFI_OPEN, LAPTOP_OPEN]
        self.assertEqual(len(search_tickets(tickets, query="   ")), 2)

    def test_query_is_trimmed_before_matching(self):
        results = search_tickets([WIFI_OPEN], query="  Wi-Fi  ")
        self.assertEqual([t["id"] for t in results], ["T001"])

    def test_punctuation_is_not_normalised_away(self):
        """Substring matching only: no fuzzy matching, no spelling correction.

        'wifi' must NOT match 'Wi-Fi' because the hyphen is a real character.
        This test documents that boundary so nobody "fixes" it by accident.
        """
        self.assertEqual(search_tickets([WIFI_OPEN], query="wifi"), [])

    def test_no_matches_returns_an_empty_list(self):
        self.assertEqual(search_tickets([WIFI_OPEN], query="printer"), [])


class TestCombinedFilters(unittest.TestCase):
    def test_filters_combine_with_and(self):
        """Case 09: search 'wi-fi' + Network + open returns only open network
        tickets whose title matches -- a ticket failing ANY filter is out."""
        tickets = [WIFI_OPEN, WIFI_RESOLVED, LAPTOP_OPEN]
        results = search_tickets(
            tickets, query="wi-fi", category="Network", status="open"
        )
        self.assertEqual([t["id"] for t in results], ["T001"])

    def test_the_brief_example_matches_when_the_punctuation_agrees(self):
        """The brief's example is 'wifi' + Network + open.

        The brief also says 'WI-FI' and 'wi-fi' match each other 'assuming the
        same punctuation', so the query and the title have to agree. Here the
        title is written without a hyphen, which is the case the example
        describes.
        """
        tickets = [
            make_ticket("T001", "wifi down in Lab 3", "Network", "critical", "open")
        ]
        results = search_tickets(
            tickets, query="wifi", category="Network", status="open"
        )
        self.assertEqual([t["id"] for t in results], ["T001"])

    def test_and_is_not_or(self):
        """A ticket matching only ONE of the supplied filters must be excluded.

        T002 is a Network ticket but resolved; T003 is open but Hardware.
        Under OR both would appear, so this test fails loudly if the
        combination logic is ever loosened.
        """
        tickets = [WIFI_OPEN, WIFI_RESOLVED, LAPTOP_OPEN]
        results = search_tickets(tickets, category="Network", status="open")
        self.assertEqual([t["id"] for t in results], ["T001"])

    def test_category_filter_alone(self):
        tickets = [WIFI_OPEN, LAPTOP_OPEN, SOFTWARE_PROGRESS]
        results = search_tickets(tickets, category="Network")
        self.assertEqual([t["id"] for t in results], ["T001"])

    def test_status_filter_alone_can_match_several(self):
        tickets = [WIFI_OPEN, LAPTOP_OPEN, SOFTWARE_PROGRESS]
        results = search_tickets(tickets, status="open")
        self.assertEqual({t["id"] for t in results}, {"T001", "T003"})

    def test_priority_filter_alone(self):
        tickets = [WIFI_OPEN, LAPTOP_OPEN, SOFTWARE_PROGRESS]
        results = search_tickets(tickets, priority="medium")
        self.assertEqual([t["id"] for t in results], ["T003"])

    def test_all_three_filters_together(self):
        tickets = [
            WIFI_OPEN,
            WIFI_RESOLVED,
            make_ticket("T005", "Wi-Fi down again", "Network", "low", "open"),
        ]
        results = search_tickets(
            tickets, query="wi-fi", category="Network", status="open", priority="critical"
        )
        self.assertEqual([t["id"] for t in results], ["T001"])

    def test_blank_filters_are_not_applied(self):
        """A blank filter means 'do not filter', not 'match the empty string'."""
        tickets = [WIFI_OPEN, LAPTOP_OPEN]
        loose = search_tickets(tickets, category="", status="  ", priority=None)
        self.assertEqual(len(loose), 2)

    def test_filter_values_are_case_insensitive(self):
        """'network' is normalised to the canonical 'Network'."""
        results = search_tickets([WIFI_OPEN, LAPTOP_OPEN], category="network")
        self.assertEqual([t["id"] for t in results], ["T001"])

    def test_filter_values_are_trimmed(self):
        results = search_tickets([WIFI_OPEN, LAPTOP_OPEN], category=" Network ")
        self.assertEqual([t["id"] for t in results], ["T001"])


class TestInvalidFilters(unittest.TestCase):
    def test_invalid_category_is_reported_not_ignored(self):
        with self.assertRaises(ValidationError):
            search_tickets([WIFI_OPEN], category="Electronics")

    def test_invalid_status_is_reported(self):
        with self.assertRaises(ValidationError):
            search_tickets([WIFI_OPEN], status="banana")

    def test_invalid_priority_is_reported(self):
        with self.assertRaises(ValidationError):
            search_tickets([WIFI_OPEN], priority="urgent")

    def test_error_names_the_filter_that_was_wrong(self):
        with self.assertRaises(ValidationError) as ctx:
            search_tickets([WIFI_OPEN], category="Electronics")
        self.assertIn("category", str(ctx.exception).lower())

    def test_a_bad_filter_does_not_fall_through_to_an_empty_result(self):
        """The dangerous alternative: silently returning [] looks like
        'no matches', so the user never learns the filter was illegal."""
        with self.assertRaises(ValidationError):
            search_tickets([WIFI_OPEN], status="not-a-status")


class TestOrdering(unittest.TestCase):
    def test_results_are_sorted_by_priority_then_numeric_id(self):
        tickets = [
            make_ticket("T010", "wifi ten", priority="critical"),
            make_ticket("T002", "wifi two", priority="low"),
            make_ticket("T003", "wifi three", priority="high"),
            make_ticket("T009", "wifi nine", priority="critical"),
            make_ticket("T004", "wifi four", priority="medium"),
        ]
        ids = [t["id"] for t in search_tickets(tickets, query="wifi")]
        self.assertEqual(ids, ["T009", "T010", "T003", "T004", "T002"])

    def test_id_tie_break_is_numeric_not_textual(self):
        """As text, 'T10' sorts before 'T2' -- the wrong answer."""
        tickets = [
            make_ticket("T10", "wifi ten", priority="high"),
            make_ticket("T2", "wifi two", priority="high"),
        ]
        ids = [t["id"] for t in search_tickets(tickets, query="wifi")]
        self.assertEqual(ids, ["T2", "T10"])

    def test_zero_padded_ids_still_order_numerically(self):
        tickets = [
            make_ticket("T010", "wifi", priority="low"),
            make_ticket("T999", "wifi", priority="low"),
            make_ticket("T1000", "wifi", priority="low"),
        ]
        ids = [t["id"] for t in search_tickets(tickets, query="wifi")]
        self.assertEqual(ids, ["T010", "T999", "T1000"])

    def test_sort_by_priority_is_available_on_its_own(self):
        """Requirement D's optional view: priority then ticket ID."""
        tickets = [
            make_ticket("T002", priority="low"),
            make_ticket("T001", priority="critical"),
        ]
        ids = [t["id"] for t in sort_by_priority(tickets)]
        self.assertEqual(ids, ["T001", "T002"])


class TestSearchIsReadOnly(unittest.TestCase):
    def test_search_does_not_modify_any_ticket(self):
        tickets = [WIFI_OPEN, WIFI_RESOLVED, LAPTOP_OPEN]
        before = [dict(ticket) for ticket in tickets]

        search_tickets(tickets, query="wifi", category="Network", status="open")

        self.assertEqual(tickets, before)

    def test_search_does_not_reorder_the_original_list(self):
        tickets = [
            make_ticket("T002", "wifi", priority="low"),
            make_ticket("T001", "wifi", priority="critical"),
        ]
        search_tickets(tickets, query="wifi")
        self.assertEqual([t["id"] for t in tickets], ["T002", "T001"])

    def test_search_does_not_add_or_remove_tickets(self):
        tickets = [WIFI_OPEN, LAPTOP_OPEN]
        search_tickets(tickets, query="wifi")
        self.assertEqual(len(tickets), 2)

    def test_search_returns_a_new_list(self):
        tickets = [WIFI_OPEN]
        results = search_tickets(tickets)
        self.assertIsNot(results, tickets)

    def test_an_illegal_filter_leaves_the_collection_untouched(self):
        tickets = [WIFI_OPEN, LAPTOP_OPEN]
        before = [dict(ticket) for ticket in tickets]
        with self.assertRaises(ValidationError):
            search_tickets(tickets, category="Electronics")
        self.assertEqual(tickets, before)


if __name__ == "__main__":
    unittest.main()
