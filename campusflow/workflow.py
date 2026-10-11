"""Assignment, status workflow and work queue for CampusFlow.

Features: F3 (assign), F4 (workflow), F5 (work queue).

Contracts (see docs/design-decisions.md):
- tickets is a list of dicts, passed in as an argument.
- Invalid input raises ValueError with a clear message.
- Functions return the updated ticket dict (queue returns a new list).
- All checks happen BEFORE any change, so a rejected action never
  leaves a half-modified ticket.
"""

VALID_TRANSITIONS = {
    "open": ["in_progress"],
    "in_progress": ["resolved"],
    "resolved": ["open"],  # explicit reopen
}

PRIORITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}

# Statuses shown in the work queue (everything not resolved).
# Change this to ("open",) if your team decides in_progress is excluded.
QUEUE_STATUSES = ("open", "in_progress")


def _numeric_id(ticket_id):
    """'T012' -> 12"""
    return int(ticket_id[1:])


def find_ticket(tickets, ticket_id):
    """Return the ticket dict, or raise ValueError if the ID is unknown."""
    wanted = str(ticket_id).strip().upper()
    for ticket in tickets:
        if ticket["id"] == wanted:
            return ticket
    raise ValueError(f"Ticket '{ticket_id}' not found.")


def assign_ticket(tickets, ticket_id, staff_name):
    """Assign a ticket to a staff member.

    Rejects unknown IDs, blank names and resolved tickets (reopen first).
    """
    ticket = find_ticket(tickets, ticket_id)

    if not isinstance(staff_name, str) or not staff_name.strip():
        raise ValueError("Staff name must not be blank.")
    if ticket["status"] == "resolved":
        raise ValueError(
            f"Ticket {ticket['id']} is resolved. Reopen it before assigning."
        )

    ticket["assigned_to"] = staff_name.strip()
    return ticket


def change_status(tickets, ticket_id, new_status):
    """Move a ticket to a new status.

    Allowed: open -> in_progress -> resolved, and resolved -> open (reopen).
    An unassigned ticket cannot move to in_progress.
    """
    ticket = find_ticket(tickets, ticket_id)

    new_status = str(new_status).strip().lower()
    if new_status not in VALID_TRANSITIONS:
        raise ValueError(
            f"Unknown status '{new_status}'. "
            f"Use one of: {', '.join(VALID_TRANSITIONS)}."
        )

    current = ticket["status"]
    if new_status not in VALID_TRANSITIONS[current]:
        raise ValueError(f"Cannot move ticket from '{current}' to '{new_status}'.")

    if new_status == "in_progress" and not ticket["assigned_to"]:
        raise ValueError(
            f"Ticket {ticket['id']} must be assigned before it can be in progress."
        )

    ticket["status"] = new_status
    return ticket


def get_work_queue(tickets):
    """Unresolved tickets, sorted critical -> low, ties by earlier numeric ID.

    Returns a new list; the original list is not reordered.
    """
    queue = [t for t in tickets if t["status"] in QUEUE_STATUSES]
    queue.sort(key=lambda t: (PRIORITY_RANK[t["priority"]], _numeric_id(t["id"])))
    return queue