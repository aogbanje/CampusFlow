"""CampusFlow Next -- command-line interface.

Structure
---------
This file is the ONLY place that talks to the user. Every business rule lives
in the ``campusflow`` package; the handlers here collect input, call a package
function, and render the result.

Every handler takes ``input_fn`` and ``output_fn`` (defaulting to the
builtins). That one change is what makes the menu testable: a test can drive
"choose option 8, type a bad ticket ID" by passing a scripted stub instead of
a human at a keyboard, and assert on the messages that came back.

Error convention
----------------
The package raises ``ValidationError`` (a subclass of ``ValueError``) for
anything invalid. Handlers catch it and print the message, so a rejected
action produces friendly feedback and never a traceback. Because validation
runs before any mutation, a rejected action also leaves the collection
unchanged.
"""

from campusflow.notes import add_note, can_add_note, notes_for
from campusflow.reports import build_report, format_percentage
from campusflow.search import search_tickets
from campusflow.storage import load_tickets, save_tickets
from campusflow.tickets import create_ticket
from campusflow.understanding_check import run_check
from campusflow.validation import (
    CATEGORIES,
    PRIORITIES,
    STATUSES,
    URGENCY_LEVELS,
    ValidationError,
)
from campusflow.workflow import (
    assign_ticket,
    change_status,
    find_ticket,
    get_work_queue,
)

DATA_FILE = "data/tickets.json"


# --------------------------------------------------------------------------
# Shared display helpers
# --------------------------------------------------------------------------

def print_ticket_row(ticket, output_fn=print):
    """Print one line: ID, priority, status, title and assignee."""
    assignee = ticket.get("assigned_to") or "unassigned"
    output_fn(
        f"{ticket['id']}  [{ticket.get('priority', '?'):<8}] "
        f"[{ticket.get('status', '?'):<11}] {ticket['title']} ({assignee})"
    )


def print_ticket_details(ticket, output_fn=print):
    """Print every field of one ticket, notes included."""
    for field in (
        "id",
        "title",
        "category",
        "urgency",
        "affected_users",
        "priority",
        "status",
        "assigned_to",
    ):
        output_fn(f"  {field}: {ticket.get(field)}")


def prompt_choice(input_fn, output_fn, label, allowed, allow_blank=True):
    """Ask for one value from `allowed`, re-prompting until it is valid.

    A blank answer is accepted only when ``allow_blank`` is set, and means
    "do not filter by this field". Matching is case-insensitive, so "network"
    and "Network" are the same choice.
    """
    lookup = {option.casefold(): option for option in allowed}
    options = ", ".join(allowed)
    suffix = f" ({options}, blank for any)" if allow_blank else f" ({options})"

    while True:
        raw = input_fn(f"{label}{suffix}: ").strip()
        if not raw:
            if allow_blank:
                return None
            output_fn(f"{label} is required.")
            continue
        chosen = lookup.get(raw.casefold())
        if chosen is not None:
            return chosen
        output_fn(f"'{raw}' is not one of: {', '.join(allowed)}.")


# --------------------------------------------------------------------------
# Engineer A's options
# --------------------------------------------------------------------------

def handle_create(tickets, input_fn=input, output_fn=print):
    """Option 1: create a ticket. Rejected input adds nothing."""
    title = input_fn("Title: ")
    category = input_fn(f"Category ({', '.join(CATEGORIES)}): ")
    urgency = input_fn(f"Urgency ({', '.join(URGENCY_LEVELS)}): ")
    affected_users = input_fn("Affected users: ")

    try:
        ticket = create_ticket(tickets, title, category, urgency, affected_users)
    except ValueError as error:
        output_fn(f"Error: {error}")
        return

    save_tickets(tickets, DATA_FILE)
    output_fn(f"Created {ticket['id']} with priority {ticket['priority']}.")


def handle_list(tickets, input_fn=input, output_fn=print):
    """Option 2: list tickets, optionally showing one in detail."""
    if not tickets:
        output_fn("No tickets yet.")
        return

    for ticket in tickets:
        print_ticket_row(ticket, output_fn)

    choice = input_fn(
        "Enter a ticket ID to view details (or press Enter to go back): "
    ).strip()
    if not choice:
        return

    try:
        ticket = find_ticket(tickets, choice)
    except ValidationError as error:
        output_fn(f"Error: {error}")
        return
    print_ticket_details(ticket, output_fn)


# --------------------------------------------------------------------------
# Engineer B's options
# --------------------------------------------------------------------------

def handle_assign(tickets, input_fn=input, output_fn=print):
    """Option 3: assign a ticket. Resolved tickets are refused."""
    ticket_id = input_fn("Ticket ID: ").strip()
    staff_name = input_fn("Assign to (staff name): ")

    try:
        ticket = assign_ticket(tickets, ticket_id, staff_name)
    except ValueError as error:
        output_fn(f"Error: {error}")
        return

    save_tickets(tickets, DATA_FILE)
    output_fn(f"{ticket['id']} assigned to {ticket['assigned_to']}.")


def handle_status(tickets, input_fn=input, output_fn=print):
    """Option 4: move a ticket along the open -> in_progress -> resolved path."""
    ticket_id = input_fn("Ticket ID: ").strip()
    new_status = input_fn(
        f"New status ({', '.join(STATUSES)}): "
    ).strip()

    try:
        ticket = change_status(tickets, ticket_id, new_status)
    except ValueError as error:
        output_fn(f"Error: {error}")
        return

    save_tickets(tickets, DATA_FILE)
    output_fn(f"{ticket['id']} is now {ticket['status']}.")


def handle_queue(tickets, input_fn=input, output_fn=print):
    """Option 5: the ORIGINAL Open Work Queue -- open tickets only.

    Deliberately unchanged. It is sorted by priority, then by numeric ticket
    ID, and it does not list in_progress or resolved work. The wider
    priority-sorted view lives in Search (option 7) instead of quietly
    redefining this one.
    """
    queue = get_work_queue(tickets)
    if not queue:
        output_fn("The work queue is empty.")
        return

    output_fn("Open work queue (highest priority first):")
    for ticket in queue:
        print_ticket_row(ticket, output_fn)


def handle_reports(tickets, input_fn=input, output_fn=print):
    """Option 6: quality insights, including the resolution rate."""
    report = build_report(tickets)

    output_fn(f"Total tickets: {report['total']}")
    output_fn(f"Unresolved (open + in_progress): {report['unresolved']}")
    output_fn(f"Resolved: {report['resolved']}")
    output_fn(
        f"Resolution rate: {format_percentage(report['resolution_percentage'])}"
    )
    output_fn("By status:")
    for status, count in report["by_status"].items():
        output_fn(f"  {status}: {count}")
    output_fn("By priority:")
    for priority, count in report["by_priority"].items():
        output_fn(f"  {priority}: {count}")
    output_fn("By category:")
    for category, count in report["by_category"].items():
        output_fn(f"  {category}: {count}")


def handle_search(tickets, input_fn=input, output_fn=print):
    """Option 7: read-only title search with optional filters (Requirement C).

    Every filter is optional and blank means "do not filter by this field".
    Supplied filters combine with AND, and the results are ordered by
    priority and then ticket ID, so the most urgent match is always first.
    """
    query = input_fn("Search title for (blank for any): ")

    try:
        category = prompt_choice(input_fn, output_fn, "Category", CATEGORIES)
        status = prompt_choice(input_fn, output_fn, "Status", STATUSES)
        priority = prompt_choice(input_fn, output_fn, "Priority", PRIORITIES)
        results = search_tickets(
            tickets,
            query=query,
            category=category,
            status=status,
            priority=priority,
        )
    except ValidationError as error:
        output_fn(f"Error: {error}")
        return

    if not results:
        output_fn("No tickets match your search.")
        return

    output_fn(f"{len(results)} ticket(s) match, highest priority first:")
    for ticket in results:
        print_ticket_row(ticket, output_fn)


def handle_add_note(tickets, input_fn=input, output_fn=print):
    """Option 8: add a follow-up note using Engineer A's add_note()."""
    ticket_id = input_fn("Ticket ID: ").strip()

    # Ask A's predicate FIRST, so a resolved ticket is refused before the
    # user is made to type an author and a message that cannot be used.
    try:
        ticket = find_ticket(tickets, ticket_id)
    except ValidationError as error:
        output_fn(f"Error: {error}")
        return

    allowed, reason = can_add_note(ticket)
    if not allowed:
        output_fn(f"Cannot add a note: {reason}")
        return

    author = input_fn("Author (e.g. Mentor A): ")
    message = input_fn("Message (5-300 characters): ")

    try:
        note = add_note(tickets, ticket_id, author, message)
    except ValueError as error:
        output_fn(f"Error: {error}")
        return

    save_tickets(tickets, DATA_FILE)
    output_fn(f"Added {note['note_id']} to {ticket['id']}.")


def handle_view_notes(tickets, input_fn=input, output_fn=print):
    """Option 9: show every note for a ticket, in note ID order."""
    ticket_id = input_fn("Ticket ID: ").strip()

    try:
        ticket = find_ticket(tickets, ticket_id)
        notes = notes_for(tickets, ticket["id"])
    except ValidationError as error:
        output_fn(f"Error: {error}")
        return

    if not notes:
        output_fn(f"No follow-up notes on {ticket['id']} yet.")
        return

    output_fn(f"Follow-up notes ({len(notes)}):")
    for note in notes:
        output_fn(f"  {note['note_id']}  {note['author']}: {note['message']}")


def handle_understanding_check(tickets, input_fn=input, output_fn=print):
    """Option 10: the Engineering Understanding Check.

    The ticket collection is not used -- the check is about the rules the
    reader has just seen the app apply -- but it takes the same handler
    signature as every other menu entry.
    """
    run_check(input_fn=input_fn, output_fn=output_fn)


# --------------------------------------------------------------------------
# Menu
# --------------------------------------------------------------------------

MENU = {
    "1": ("Create ticket", handle_create),
    "2": ("List / view tickets", handle_list),
    "3": ("Assign ticket", handle_assign),
    "4": ("Change status", handle_status),
    "5": ("Open work queue", handle_queue),
    "6": ("Reports", handle_reports),
    "7": ("Search tickets", handle_search),
    "8": ("Add follow-up note", handle_add_note),
    "9": ("View ticket notes", handle_view_notes),
    "10": ("Engineering Understanding Check", handle_understanding_check),
    "0": ("Exit", None),
}


def run_menu(tickets, input_fn=input, output_fn=print):
    """Show the menu until the user exits. Injectable I/O for tests."""
    while True:
        output_fn("\n=== CampusFlow Next ===")
        for key, (label, _) in MENU.items():
            output_fn(f"{key}. {label}")

        choice = input_fn("Choose an option: ").strip()
        if choice == "0":
            output_fn("Goodbye.")
            return
        if choice in MENU:
            MENU[choice][1](tickets, input_fn, output_fn)
        else:
            output_fn("Invalid option. Please choose from the menu.")


def main():
    try:
        tickets = load_tickets(DATA_FILE)
    except ValueError as error:
        # Stop instead of continuing, so we never overwrite a damaged file.
        print(f"Could not load tickets: {error}")
        return

    run_menu(tickets)


if __name__ == "__main__":
    main()
