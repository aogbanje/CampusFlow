"""Assignment, status workflow and work queue for CampusFlow.

Contracts (see docs/design-decisions.md):
- ``tickets`` is a list of dicts, passed in as an argument.
- Invalid input raises :class:`campusflow.validation.ValidationError`
  (a ``ValueError``) with a clear message.
- Functions return the updated ticket dict (the queue returns a NEW list).
- All checks happen BEFORE any change, so a rejected action can never leave
  a half-modified ticket.

Engineer B's CLI has two ways to use this module:

* :func:`can_transition` / :func:`can_assign` answer "may I?" without
  raising, which is what a menu wants when it explains a refusal.
* :func:`change_status` / :func:`assign_ticket` perform the action and raise
  on refusal, which is what a single call site wants.
"""

from campusflow.validation import (
    ValidationError,
    validate_staff_label,
    validate_status,
    validate_ticket_id,
)

VALID_TRANSITIONS = {
    "open": ["in_progress"],
    "in_progress": ["resolved"],
    "resolved": ["open"],  # explicit reopen
}

PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

#: The ORIGINAL Open Work Queue shows only tickets that are still OPEN.
#: ``in_progress`` work is owned by an engineer and is intentionally not
#: listed here; the separate priority-sorted search view covers that.
#: (CampusFlow Next changed this from ("open", "in_progress") -- see
#: docs/design-decisions.md and tests/test_workflow.py.)
QUEUE_STATUSES = ("open",)


def numeric_ticket_id(ticket_id):
    """``'T012'`` -> ``12``. Used for numeric tie-breaking."""
    return int(validate_ticket_id(ticket_id)[1:])


def find_ticket(tickets, ticket_id):
    """Return the ticket dict, or raise ValidationError if the ID is unknown."""
    wanted = validate_ticket_id(ticket_id)
    for ticket in tickets:
        if ticket["id"] == wanted:
            return ticket
    raise ValidationError(f"Ticket '{wanted}' not found.")


def can_assign(ticket):
    """Return ``(allowed, reason)`` for assigning this ticket. Never raises."""
    if ticket.get("status") == "resolved":
        return (
            False,
            f"Ticket {ticket['id']} is resolved. Reopen it before assigning.",
        )
    return True, ""


def assign_ticket(tickets, ticket_id, staff_name):
    """Assign a ticket to a staff member.

    Rejects unknown IDs, blank labels and resolved tickets (reopen first).
    The label is validated before the ticket is located, and the ticket is
    only written once every check has passed.
    """
    cleaned_name = validate_staff_label(staff_name)
    ticket = find_ticket(tickets, ticket_id)

    allowed, reason = can_assign(ticket)
    if not allowed:
        raise ValidationError(reason)

    ticket["assigned_to"] = cleaned_name
    return ticket


def can_transition(ticket, new_status):
    """Return ``(allowed, reason)`` for a status change. Never raises.

    This is the single definition of the ticket lifecycle. ``change_status``
    and the CLI both call it, so a menu can never allow a move the workflow
    would refuse. It has no side effects, which makes it trivial to test.
    """
    try:
        target = validate_status(new_status)
    except ValidationError as error:
        return False, str(error)

    current = ticket.get("status")
    if current not in VALID_TRANSITIONS:
        return False, f"Ticket {ticket.get('id')} has unknown status '{current}'."

    if target not in VALID_TRANSITIONS[current]:
        return False, f"Cannot move ticket from '{current}' to '{target}'."

    if target == "in_progress" and not ticket.get("assigned_to"):
        return (
            False,
            f"Ticket {ticket['id']} must be assigned before it can be in progress.",
        )

    return True, ""


def change_status(tickets, ticket_id, new_status):
    """Move a ticket to a new status.

    Allowed: open -> in_progress -> resolved, and resolved -> open (reopen).
    An unassigned ticket cannot move to in_progress.

    Invariant: a refused change leaves ``status`` and every other field
    untouched, because the assignment happens on the last line only.
    """
    ticket = find_ticket(tickets, ticket_id)

    allowed, reason = can_transition(ticket, new_status)
    if not allowed:
        raise ValidationError(reason)

    ticket["status"] = validate_status(new_status)
    return ticket


def get_work_queue(tickets):
    """OPEN tickets only, sorted critical -> low, ties by earlier numeric ID.

    Returns a new list; the original list is not reordered.

    The numeric tie-break matters: sorting the text IDs would put 'T10'
    before 'T2', which is wrong. ``numeric_ticket_id`` compares the number
    instead, so the tie-break stays correct past 999 tickets.
    """
    queue = [t for t in tickets if t["status"] in QUEUE_STATUSES]
    queue.sort(key=lambda t: (PRIORITY_RANK[t["priority"]], numeric_ticket_id(t["id"])))
    return queue
