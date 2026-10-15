"""Ticket creation and the ticket schema (Engineer A).

This module used to hold its own copies of every validation rule. Those rules
now live in :mod:`campusflow.validation` so there is exactly one definition of
"a valid ticket". The names are re-exported here so existing imports such as
``from campusflow.tickets import validate_affected_users`` keep working.
"""

from campusflow.validation import (  # noqa: F401  (re-exported for compatibility)
    CATEGORIES,
    LEGACY_OPTIONAL_FIELDS,
    MESSAGE_MAX_LENGTH,
    MESSAGE_MIN_LENGTH,
    PRIORITIES,
    REQUIRED_TICKET_FIELDS,
    STATUSES,
    URGENCY_LEVELS,
    ValidationError,
    calculate_priority,
    format_note_id,
    format_ticket_id,
    validate_affected_users,
    validate_category,
    validate_note,
    validate_notes,
    validate_priority,
    validate_status,
    validate_staff_label,
    validate_ticket,
    validate_ticket_collection,
    validate_ticket_id,
    validate_title,
    validate_urgency,
)


def next_ticket_id(tickets):
    """Return the next unused ticket ID ('T001' for an empty list).

    Based on the highest existing number, never on ``len(tickets)``: after a
    reload the list may have gaps, and counting entries would reuse an ID.
    Tolerant of partial dicts so it can be used while loading.
    """
    highest = 0
    for ticket in tickets:
        try:
            highest = max(highest, int(str(ticket["id"]).strip().upper()[1:]))
        except (KeyError, ValueError, TypeError, IndexError):
            continue
    return format_ticket_id(highest + 1)


def new_ticket(ticket_id, title, category, urgency, affected_users):
    """Build a validated ticket dict. Does NOT add it to any collection.

    Keeping construction separate from insertion means a caller can validate
    everything and still decide not to insert -- and it makes the exact
    ticket shape easy to test on its own.
    """
    title = validate_title(title)
    category = validate_category(category)
    urgency = validate_urgency(urgency)
    affected_users = validate_affected_users(affected_users)

    return {
        "id": ticket_id,
        "title": title,
        "category": category,
        "urgency": urgency,
        "affected_users": affected_users,
        "priority": calculate_priority(urgency, affected_users),
        "status": "open",
        "assigned_to": None,
        "notes": [],
    }


def create_ticket(tickets, title, category, urgency, affected_users):
    """Validate everything first, then append and return the new ticket.

    Invariant: if this function raises, ``tickets`` is exactly as it was.
    Nothing is appended until every field has been accepted.
    """
    ticket = new_ticket(
        next_ticket_id(tickets), title, category, urgency, affected_users
    )
    tickets.append(ticket)
    return ticket
