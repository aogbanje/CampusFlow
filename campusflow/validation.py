"""Centralised validation and the priority rule (Engineer A).

Why this module exists
----------------------
Before CampusFlow Next, validation was spread across ``tickets.py`` and
``workflow.py``. That made it easy to add a code path that forgot one rule.
Every rule now lives here once, and every other module calls it.

Contract
--------
* Every ``validate_*`` helper RETURNS a cleaned, canonical value
  (strip / casefold / int conversion). It never returns ``None`` on failure.
* Anything invalid raises :class:`ValidationError`, a subclass of
  ``ValueError``, so the CLI can catch one exception type.
* No helper mutates its arguments. Validation and mutation are two separate
  steps, which is what makes "validate-before-mutate" possible: if validation
  raises, the caller has not touched a single field yet.

Callers MUST finish validating before they change a ticket. That is the
invariant that keeps a rejected action from leaving half-changed data.
"""

CATEGORIES = ("Network", "Hardware", "Software", "Other")
URGENCY_LEVELS = ("low", "medium", "high")
STATUSES = ("open", "in_progress", "resolved")
PRIORITIES = ("critical", "high", "medium", "low")

# Length limits. A message of 5..300 characters is long enough to be useful
# and short enough to stay readable in the CLI.
MESSAGE_MIN_LENGTH = 5
MESSAGE_MAX_LENGTH = 300


class ValidationError(ValueError):
    """Raised whenever an input, ticket or record is not acceptable.

    Subclasses ValueError so existing ``except ValueError`` blocks keep
    working, while new code can catch the narrower type.
    """


# --------------------------------------------------------------------------
# Priority: the single source of truth for the four business rules
# --------------------------------------------------------------------------

def calculate_priority(urgency, affected_users):
    """Return the priority for a ticket. First matching rule wins.

    | Rule | Condition                           | Priority |
    |------|-------------------------------------|----------|
    | 1    | high urgency AND 10+ affected users | critical |
    | 2    | high urgency OR  10+ affected users | high     |
    | 3    | medium urgency OR 3+ affected users | medium   |
    | 4    | everything else                     | low      |

    Order matters: rule 1 must be tested before rule 2, otherwise a high
    urgency ticket with 15 users would come back as "high" instead of
    "critical".
    """
    if urgency == "high" and affected_users >= 10:
        return "critical"
    if urgency == "high" or affected_users >= 10:
        return "high"
    if urgency == "medium" or affected_users >= 3:
        return "medium"
    return "low"


# --------------------------------------------------------------------------
# Field-level validators
# --------------------------------------------------------------------------

def _require_str(value, message):
    if not isinstance(value, str):
        raise ValidationError(message)
    return value


def validate_title(title):
    """Return the trimmed title. Blank or non-text titles are rejected."""
    _require_str(title, "Title must be text.")
    cleaned = title.strip()
    if not cleaned:
        raise ValidationError("Title must not be blank.")
    return cleaned


def validate_category(category):
    """Return a canonical category, e.g. ``'  network '`` -> ``'Network'``."""
    if isinstance(category, str):
        cleaned = category.strip().casefold()
        for allowed in CATEGORIES:
            if cleaned == allowed.casefold():
                return allowed
    raise ValidationError(f"Category must be one of: {', '.join(CATEGORIES)}.")


def validate_urgency(urgency):
    """Return a canonical urgency: low, medium or high."""
    if isinstance(urgency, str):
        cleaned = urgency.strip().casefold()
        if cleaned in URGENCY_LEVELS:
            return cleaned
    raise ValidationError(f"Urgency must be one of: {', '.join(URGENCY_LEVELS)}.")


def validate_affected_users(value):
    """Return a strictly positive ``int``.

    Accepted: a positive ``int``, or a digit-only string (CLI input).
    Rejected: 0, negatives, floats, booleans, ``None``, blank, "2.5", "-3",
    "abc", and anything else.

    ``isinstance(True, int)`` is ``True`` in Python because ``bool`` is a
    subclass of ``int``. ``True`` would silently become the number 1, so
    booleans are rejected explicitly before the int check.
    """
    error = ValidationError("Affected users must be a positive whole number.")

    if isinstance(value, bool):  # must come first: bool is a subclass of int
        raise error

    if isinstance(value, int):
        number = value
    elif isinstance(value, str):
        text = value.strip()
        # isdigit() alone accepts unicode digits like "٧"; isascii() keeps
        # input predictable. It also rejects "2.5", "-1", "abc" and "".
        if not (text.isascii() and text.isdigit()):
            raise error
        number = int(text)
    else:  # float, None, list, dict, ...
        raise error

    if number <= 0:
        raise error
    return number


def validate_staff_label(staff_name):
    """Return a trimmed, non-empty staff label for assignment or note author.

    Called "staff label" rather than "name" on purpose: CampusFlow stores
    dummy operator labels such as "Mentor A", never real personal data.
    """
    if not isinstance(staff_name, str):
        raise ValidationError("Staff name must be text.")
    cleaned = staff_name.strip()
    if not cleaned:
        raise ValidationError("Staff name must not be blank.")
    return cleaned


def validate_status(status):
    """Return a legal ticket status."""
    if isinstance(status, str):
        cleaned = status.strip().casefold()
        if cleaned in STATUSES:
            return cleaned
    raise ValidationError(f"Unknown status '{status}'. Use one of: {', '.join(STATUSES)}.")


def validate_priority(priority):
    """Return a legal priority."""
    if isinstance(priority, str):
        cleaned = priority.strip().casefold()
        if cleaned in PRIORITIES:
            return cleaned
    raise ValidationError(
        f"Unknown priority '{priority}'. Use one of: {', '.join(PRIORITIES)}."
    )


def validate_ticket_id(ticket_id):
    """Return a canonical ticket ID such as ``'T001'``.

    Accepts ``'t1'``, ``' T001 '`` and normalises them, so callers do not
    each re-implement the padding rule.
    """
    if isinstance(ticket_id, int) and not isinstance(ticket_id, bool):
        number = ticket_id
    elif isinstance(ticket_id, str):
        text = ticket_id.strip().upper()
        if not text.startswith("T"):
            raise ValidationError(f"Ticket ID '{ticket_id}' must look like 'T001'.")
        text = text[1:]
        if not (text.isascii() and text.isdigit()):
            raise ValidationError(f"Ticket ID '{ticket_id}' must look like 'T001'.")
        number = int(text)
    else:
        raise ValidationError(f"Ticket ID '{ticket_id}' must look like 'T001'.")

    if number <= 0:
        raise ValidationError("Ticket ID number must be positive.")
    return f"T{number:03d}"


def format_ticket_id(number):
    """``7`` -> ``'T007'``. Used when generating the next ID."""
    return f"T{number:03d}"


def format_note_id(number):
    """``7`` -> ``'N007'``. Used when generating the next note ID."""
    return f"N{number:03d}"


# --------------------------------------------------------------------------
# Whole-ticket and whole-note validation
# --------------------------------------------------------------------------

def validate_note(note):
    """Return a normalised copy of one note, or raise :class:`ValidationError`.

    Expected shape::

        {"note_id": "N001", "author": "Mentor A", "message": "..."}

    Extra keys are dropped rather than rejected, so a future version can add
    a field without making today's files unloadable.
    """
    if not isinstance(note, dict):
        raise ValidationError("Note must be an object, not a JSON primitive.")

    for field in ("note_id", "author", "message"):
        if field not in note:
            raise ValidationError(f"Note is missing required field '{field}'.")

    note_id = note["note_id"]
    if not isinstance(note_id, str):
        raise ValidationError("Note ID must be text.")
    text = note_id.strip().upper()
    if not text.startswith("N") or not (text[1:].isascii() and text[1:].isdigit()):
        raise ValidationError(f"Note ID '{note_id}' must look like 'N001'.")
    number = int(text[1:])
    if number <= 0:
        raise ValidationError("Note ID number must be positive.")
    text = format_note_id(number)

    # Author and message are checked with the same helpers the add-note
    # action uses, so a hand-edited file cannot contain a note the running
    # application would have refused to create.
    author = validate_staff_label(note["author"])

    message = note["message"]
    if not isinstance(message, str):
        raise ValidationError("Note message must be text.")
    message = message.strip()
    if len(message) < MESSAGE_MIN_LENGTH:
        raise ValidationError(
            f"Note message must be at least {MESSAGE_MIN_LENGTH} characters."
        )
    if len(message) > MESSAGE_MAX_LENGTH:
        raise ValidationError(
            f"Note message must be at most {MESSAGE_MAX_LENGTH} characters."
        )

    return {"note_id": text, "author": author, "message": message}


def validate_notes(notes, ticket_id="?"):
    """Validate a ticket's whole notes list and return a normalised copy.

    Rejects a missing list, non-list values, malformed notes and duplicate
    note IDs inside the same ticket.
    """
    if not isinstance(notes, list):
        raise ValidationError(f"Notes for ticket {ticket_id} must be a list.")

    validated = []
    seen = set()
    for index, note in enumerate(notes):
        try:
            cleaned = validate_note(note)
        except ValidationError as error:
            raise ValidationError(
                f"Note #{index + 1} of ticket {ticket_id} is invalid: {error}"
            ) from error
        if cleaned["note_id"] in seen:
            raise ValidationError(
                f"Duplicate note ID '{cleaned['note_id']}' in ticket {ticket_id}."
            )
        seen.add(cleaned["note_id"])
        validated.append(cleaned)
    return validated


#: Fields that a legacy (pre-notes) file may be missing. ``notes`` was added
#: in CampusFlow Next, so old files are upgraded to ``[]`` instead of being
#: rejected -- the guide requires that old working tickets are not discarded.
LEGACY_OPTIONAL_FIELDS = ("notes",)

REQUIRED_TICKET_FIELDS = (
    "id",
    "title",
    "category",
    "urgency",
    "affected_users",
    "priority",
    "status",
    "assigned_to",
)


def validate_ticket(ticket):
    """Validate one ticket and return a normalised COPY.

    Checking the priority is the interesting part. ``affected_users`` and
    ``urgency`` are the inputs, ``priority`` is the derived output, so a
    stored priority must equal the one the rule produces. Without that check
    a hand-edited file could claim a ticket affecting 1 user is "critical"
    and the analytics would happily report it.
    """
    if not isinstance(ticket, dict):
        raise ValidationError("Ticket must be a JSON object.")

    missing = [field for field in REQUIRED_TICKET_FIELDS if field not in ticket]
    if missing:
        raise ValidationError(f"missing required field(s): {', '.join(missing)}.")

    cleaned = {field: ticket[field] for field in REQUIRED_TICKET_FIELDS}

    cleaned["id"] = validate_ticket_id(ticket["id"])
    cleaned["title"] = validate_title(ticket["title"])
    cleaned["category"] = validate_category(ticket["category"])
    cleaned["urgency"] = validate_urgency(ticket["urgency"])
    cleaned["affected_users"] = validate_affected_users(ticket["affected_users"])
    cleaned["priority"] = validate_priority(ticket["priority"])
    cleaned["status"] = validate_status(ticket["status"])

    assigned_to = ticket["assigned_to"]
    if assigned_to is None:
        cleaned["assigned_to"] = None
    else:
        cleaned["assigned_to"] = validate_staff_label(assigned_to)

    expected = calculate_priority(cleaned["urgency"], cleaned["affected_users"])
    if cleaned["priority"] != expected:
        raise ValidationError(
            f"priority '{cleaned['priority']}' does not match the rule: "
            f"urgency '{cleaned['urgency']}' with "
            f"{cleaned['affected_users']} affected user(s) means '{expected}'."
        )

    # A ticket in progress must be assigned -- that is already an invariant
    # of the running app, so a file that breaks it is rejected too.
    if cleaned["status"] == "in_progress" and not cleaned["assigned_to"]:
        raise ValidationError(
            "status 'in_progress' requires an assigned_to label."
        )

    cleaned["notes"] = validate_notes(
        ticket.get("notes", []), ticket_id=cleaned["id"]
    )
    return cleaned


def validate_ticket_collection(data, source="file"):
    """Validate a whole collection and return a normalised, NEW list.

    Raises :class:`ValidationError` on the first bad record. Nothing is
    returned on failure, so a caller can never accidentally install a
    half-validated collection over good in-memory data.
    """
    if not isinstance(data, list):
        raise ValidationError(f"{source} must contain a list of tickets.")

    validated = []
    seen_ids = set()
    for index, ticket in enumerate(data):
        try:
            cleaned = validate_ticket(ticket)
        except ValidationError as error:
            raise ValidationError(f"Ticket #{index + 1} in {source}: {error}") from error
        if cleaned["id"] in seen_ids:
            raise ValidationError(
                f"Duplicate ticket ID '{cleaned['id']}' in {source}."
            )
        seen_ids.add(cleaned["id"])
        validated.append(cleaned)
    return validated
