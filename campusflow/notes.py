"""Structured follow-up notes for tickets (Engineer A).

Scope
-----
This module is the business/data layer for notes. It knows nothing about
``input()`` or ``print()`` -- Engineer B's CLI calls :func:`add_note` and
:func:`notes_for` and renders whatever comes back.

Contract
--------
* :func:`add_note` returns the new note dict, or raises
  :class:`~campusflow.validation.ValidationError`.
* Failures never mutate the ticket. Validation happens first, and the note is
  only appended once every check has passed.
* A rejected note does NOT consume a note ID, because the next ID is derived
  from the notes that actually exist rather than from a counter.

Rules implemented here (Requirement B)
--------------------------------------
* A note may only be added while the ticket is ``open`` or ``in_progress``.
* The author label must not be blank.
* The message must be 5-300 characters after trimming.
* Notes survive resolve and reopen; they are never touched by the workflow.
"""

from campusflow.validation import (
    ValidationError,
    format_note_id,
    validate_staff_label,
    validate_ticket_id,
)

#: Ticket statuses that accept a new note.
NOTEABLE_STATUSES = ("open", "in_progress")


def find_ticket(tickets, ticket_id):
    """Return the ticket with this ID, or raise :class:`ValidationError`.

    Kept here as well as in ``workflow`` so ``notes`` does not depend on the
    workflow module; both use the same canonical ID from ``validation``.
    """
    wanted = validate_ticket_id(ticket_id)
    for ticket in tickets:
        if ticket.get("id") == wanted:
            return ticket
    raise ValidationError(f"Ticket '{wanted}' not found.")


def can_add_note(ticket):
    """Return ``(allowed, reason)`` for adding a note. Never raises.

    Engineer B's CLI uses this to grey out / explain the action before it
    calls :func:`add_note`, so the user gets a reason instead of a traceback.
    """
    status = ticket.get("status")
    if status in NOTEABLE_STATUSES:
        return True, ""
    return (
        False,
        f"Ticket {ticket.get('id')} is {status}. "
        "Reopen it before adding follow-up notes.",
    )


def next_note_id(ticket):
    """Return the next unused note ID for this ticket, e.g. ``'N003'``.

    Derived from the highest existing note number, so the ID stays correct
    after a save/reload cycle and IDs are never reused -- the same approach
    ``next_ticket_id`` uses. An ID is therefore only "used up" by a note
    that really exists.
    """
    highest = 0
    for note in ticket.get("notes") or []:
        note_id = note.get("note_id") if isinstance(note, dict) else None
        if isinstance(note_id, str) and note_id[1:].isdigit():
            highest = max(highest, int(note_id[1:]))
    return format_note_id(highest + 1)


def validate_message(message):
    """Return the trimmed message, enforcing the 5-300 character rule."""
    if not isinstance(message, str):
        raise ValidationError("Note message must be text.")

    cleaned = message.strip()
    if len(cleaned) < 5:
        raise ValidationError("Note message must be at least 5 characters.")
    if len(cleaned) > 300:
        raise ValidationError("Note message must be at most 300 characters.")
    return cleaned


def add_note(tickets, ticket_id, author, message):
    """Append a follow-up note to a ticket and return it.

    Parameters
    ----------
    tickets : list of dict
        The in-memory collection. Modified only on success.
    ticket_id : str
        Ticket to attach the note to, e.g. ``"T001"``. Case and padding are
        normalised by :func:`~campusflow.validation.validate_ticket_id`.
    author : str
        Operator label, e.g. ``"Mentor A"``. Must not be blank.
    message : str
        The note text. 5-300 characters after trimming.

    Returns
    -------
    dict
        ``{"note_id": "N001", "author": ..., "message": ...}``

    Raises
    ------
    ValidationError
        Unknown ticket, closed ticket, blank author, bad message length.
        The ticket is left completely unchanged in every case.

    Notes
    -----
    Every check runs before the append. That ordering is the whole point:
    there is no code path where a field is written and then an exception is
    raised, so "a rejected note changes nothing" holds by construction, not
    by luck.
    """
    # --- 1. Locate and validate the target ticket -------------------------
    ticket = find_ticket(tickets, ticket_id)

    # --- 2. Validate the note content BEFORE touching the ticket ----------
    cleaned_author = validate_staff_label(author)
    cleaned_message = validate_message(message)

    # --- 3. Check the workflow rule last, so a bad message on a resolved
    #        ticket reports the message problem (the more useful error).
    allowed, reason = can_add_note(ticket)
    if not allowed:
        raise ValidationError(reason)

    # --- 4. Everything passed: mutate once, in one place ------------------
    if not isinstance(ticket.get("notes"), list):
        # A legacy ticket from an upgrade has no notes key yet.
        ticket["notes"] = []

    note = {
        "note_id": next_note_id(ticket),
        "author": cleaned_author,
        "message": cleaned_message,
    }
    ticket["notes"].append(note)
    return note


def notes_for(tickets, ticket_id):
    """Return a ticket's notes sorted by numeric note ID, as a NEW list.

    Sorting by ID rather than trusting file order means the CLI always shows
    the notes in the order they were written, even if the JSON was reordered
    by hand. Sorting a copy means the search/view actions stay read-only.
    """
    ticket = find_ticket(tickets, ticket_id)
    notes = ticket.get("notes") or []
    return sorted(notes, key=lambda note: int(note["note_id"][1:]))
