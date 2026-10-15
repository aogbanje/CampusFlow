"""Read-only search and combined filtering for CampusFlow (Engineer B).

Why this module exists
----------------------
Requirement C asks for a way to find tickets quickly: a case-insensitive title
substring search plus optional category / status / priority filters that all
apply together. Before this module there was no way to ask that question at
all -- the CLI could only print every ticket.

Contract
--------
* :func:`search_tickets` is READ-ONLY. It returns a new list of the ticket
  dicts that matched; it never adds, removes, reorders or edits a ticket.
  Several tests assert this by snapshotting the collection first.
* Filters combine with **AND**. A ticket is returned only when it satisfies
  every filter that was actually supplied. OR is not offered, because a user
  who types "wifi" *and* picks Network is narrowing, not widening -- see
  docs/design-decisions.md.
* A filter that is ``None`` or whitespace-only means "do not filter by this
  field". That is what lets the CLI offer each filter as optional.
* An illegal filter value raises :class:`ValidationError` rather than
  silently matching nothing, so the CLI can re-prompt with a reason.

Filter values are validated through the same helpers the rest of the app uses
(``campusflow.validation``), so search can never accept a category that
ticket creation would have rejected.
"""

from campusflow.validation import (
    ValidationError,
    validate_category,
    validate_priority,
    validate_status,
)
from campusflow.workflow import PRIORITY_RANK, numeric_ticket_id

#: Fallback rank for a priority that is not in PRIORITY_RANK. Sorts last
#: instead of raising, so one unknown value cannot break a whole search.
_UNKNOWN_RANK = len(PRIORITY_RANK)


def sort_by_priority(tickets):
    """Return a NEW list ordered by priority, then by numeric ticket ID.

    This is Requirement D's "separate optional view that sorts ticket-search
    results by priority then ticket ID".

    The tie-breaker compares the NUMBER inside the ID, not the text, because
    ``"T10" < "T2"`` as strings -- sorting text would put T10 before T2 and
    give the wrong order once a project passes nine tickets.
    """
    return sorted(
        tickets,
        key=lambda ticket: (
            PRIORITY_RANK.get(ticket.get("priority"), _UNKNOWN_RANK),
            numeric_ticket_id(ticket.get("id", "")),
        ),
    )


def _clean_filter(value, validator, label):
    """Return the canonical filter value, or ``None`` when it is not supplied.

    ``None`` and whitespace-only strings both mean "do not filter by this
    field" -- the user left it blank in the CLI.
    """
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None

    try:
        return validator(value)
    except ValidationError as error:
        # Re-raise with the field name, so the user is told WHICH filter was
        # wrong instead of just "Unknown category 'x'".
        raise ValidationError(f"Invalid {label} filter: {error}") from error


def _matches(ticket, needle, category, status, priority):
    """Return True when the ticket satisfies every supplied filter (AND)."""
    if needle:
        title = str(ticket.get("title", ""))
        if needle not in title.casefold():
            return False
    if category is not None and ticket.get("category") != category:
        return False
    if status is not None and ticket.get("status") != status:
        return False
    if priority is not None and ticket.get("priority") != priority:
        return False
    return True


def search_tickets(tickets, query="", category=None, status=None, priority=None):
    """Return the tickets matching every supplied filter, priority-sorted.

    Parameters
    ----------
    tickets : list of dict
        The collection to read. Never modified.
    query : str
        Substring matched against the title, case-insensitively. Empty means
        "match any title". This is plain substring matching -- there is no
        fuzzy matching and no spelling correction, and punctuation still has
        to line up, so ``"WI-FI"`` matches ``"wi-fi"`` but not ``"wifi"``.
    category, status, priority : str or None
        Optional filters. Empty or ``None`` means "do not filter".

    Returns
    -------
    list of dict
        A NEW list. The dicts inside are the originals, not copies, so a
        caller must not mutate them either.

    Raises
    ------
    ValidationError
        A supplied ``category``, ``status`` or ``priority`` is not one of the
        allowed values.
    """
    needle = query.strip().casefold() if isinstance(query, str) else ""

    category = _clean_filter(category, validate_category, "category")
    status = _clean_filter(status, validate_status, "status")
    priority = _clean_filter(priority, validate_priority, "priority")

    matched = [
        ticket
        for ticket in tickets
        if _matches(ticket, needle, category, status, priority)
    ]
    return sort_by_priority(matched)
