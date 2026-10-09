CATEGORIES = ("Network", "Hardware", "Software", "Other")
URGENCY_LEVELS = ("low", "medium", "high")


def calculate_priority(urgency, affected_users):
    """Apply the four rules in order; the first match wins."""
    if urgency == "high" and affected_users >= 10:
        return "critical"
    if urgency == "high" or affected_users >= 10:
        return "high"
    if urgency == "medium" or affected_users >= 3:
        return "medium"
    return "low"


def validate_title(title):
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Title must not be blank.")
    return title.strip()


def validate_category(category):
    if isinstance(category, str):
        cleaned = category.strip().lower()
        for allowed in CATEGORIES:
            if cleaned == allowed.lower():
                return allowed
    raise ValueError(f"Category must be one of: {', '.join(CATEGORIES)}.")


def validate_urgency(urgency):
    if isinstance(urgency, str):
        cleaned = urgency.strip().lower()
        if cleaned in URGENCY_LEVELS:
            return cleaned
    raise ValueError(f"Urgency must be one of: {', '.join(URGENCY_LEVELS)}.")


def validate_affected_users(value):
    """Return a positive int. Accepts ints and digit-only strings (CLI input)."""
    error = ValueError("Affected users must be a positive whole number.")

    if isinstance(value, bool):  # True is an int in Python, so reject it explicitly
        raise error
    if isinstance(value, int):
        number = value
    elif isinstance(value, str):
        text = value.strip()
        if not (text.isascii() and text.isdigit()):  # rejects "2.5", "-1", "abc", ""
            raise error
        number = int(text)
    else:  # floats, None, lists, etc.
        raise error

    if number <= 0:
        raise error
    return number


def next_ticket_id(tickets):
    """Highest numeric id + 1, so it stays correct after a reload."""
    highest = max((int(t["id"][1:]) for t in tickets), default=0)
    return f"T{highest + 1:03d}"


def create_ticket(tickets, title, category, urgency, affected_users):
    """Validate everything first, then build, append and return the ticket."""
    title = validate_title(title)
    category = validate_category(category)
    urgency = validate_urgency(urgency)
    affected_users = validate_affected_users(affected_users)

    ticket = {
        "id": next_ticket_id(tickets),
        "title": title,
        "category": category,
        "urgency": urgency,
        "affected_users": affected_users,
        "priority": calculate_priority(urgency, affected_users),
        "status": "open",
        "assigned_to": None,
    }
    tickets.append(ticket)
    return ticket