from campusflow.reports import build_report
from campusflow.storage import load_tickets, save_tickets
from campusflow.tickets import CATEGORIES, URGENCY_LEVELS, create_ticket
from campusflow.workflow import assign_ticket, change_status, get_work_queue

DATA_FILE = "data/tickets.json"


def print_ticket_row(ticket):
    assignee = ticket["assigned_to"] or "unassigned"
    print(
        f"{ticket['id']}  [{ticket['priority']:<8}] [{ticket['status']:<11}] "
        f"{ticket['title']} ({assignee})"
    )


# ---------- Engineer A: options 1 and 2 ----------

def handle_create(tickets):
    title = input("Title: ")
    category = input(f"Category ({', '.join(CATEGORIES)}): ")
    urgency = input(f"Urgency ({', '.join(URGENCY_LEVELS)}): ")
    affected_users = input("Affected users: ")

    try:
        ticket = create_ticket(tickets, title, category, urgency, affected_users)
    except ValueError as error:
        print(f"Error: {error}")
        return

    save_tickets(tickets, DATA_FILE)
    print(f"Created {ticket['id']} with priority {ticket['priority']}.")


def handle_list(tickets):
    if not tickets:
        print("No tickets yet.")
        return

    for ticket in tickets:
        print_ticket_row(ticket)

    choice = input("Enter a ticket ID to view details (or press Enter to go back): ")
    choice = choice.strip().upper()
    if not choice:
        return

    for ticket in tickets:
        if ticket["id"] == choice:
            for field, value in ticket.items():
                print(f"  {field}: {value}")
            return
    print(f"Error: no ticket with ID {choice}.")


# ---------- Engineer B: options 3 to 6 ----------

def handle_assign(tickets):
    ticket_id = input("Ticket ID: ").strip().upper()
    staff_name = input("Assign to (staff name): ")

    try:
        ticket = assign_ticket(tickets, ticket_id, staff_name)
    except ValueError as error:
        print(f"Error: {error}")
        return

    save_tickets(tickets, DATA_FILE)
    print(f"{ticket['id']} assigned to {ticket['assigned_to']}.")


def handle_status(tickets):
    ticket_id = input("Ticket ID: ").strip().upper()
    new_status = input("New status (open, in_progress, resolved): ").strip().lower()

    try:
        ticket = change_status(tickets, ticket_id, new_status)
    except ValueError as error:
        print(f"Error: {error}")
        return

    save_tickets(tickets, DATA_FILE)
    print(f"{ticket['id']} is now {ticket['status']}.")


def handle_queue(tickets):
    queue = get_work_queue(tickets)
    if not queue:
        print("The work queue is empty.")
        return

    print("Work queue (highest priority first):")
    for ticket in queue:
        print_ticket_row(ticket)


def handle_reports(tickets):
    report = build_report(tickets)

    print(f"Total tickets: {report['total']}")
    print("By status:")
    for status, count in report["by_status"].items():
        print(f"  {status}: {count}")
    print("By priority:")
    for priority, count in report["by_priority"].items():
        print(f"  {priority}: {count}")


MENU = {
    "1": ("Create ticket", handle_create),
    "2": ("List / view tickets", handle_list),
    "3": ("Assign ticket", handle_assign),
    "4": ("Change status", handle_status),
    "5": ("Work queue", handle_queue),
    "6": ("Reports", handle_reports),
    "0": ("Exit", None),
}


def main():
    try:
        tickets = load_tickets(DATA_FILE)
    except ValueError as error:
        # Stop instead of continuing, so we never overwrite a damaged file.
        print(f"Could not load tickets: {error}")
        return

    while True:
        print("\n=== CampusFlow ===")
        for key, (label, _) in MENU.items():
            print(f"{key}. {label}")

        choice = input("Choose an option: ").strip()
        if choice == "0":
            print("Goodbye.")
            break
        if choice in MENU:
            MENU[choice][1](tickets)
        else:
            print("Invalid option. Please choose from the menu.")


if __name__ == "__main__":
    main()