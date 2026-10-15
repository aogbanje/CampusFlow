"""Safe, validated JSON persistence for CampusFlow (Engineer A).

Rules
-----
- Tickets are saved to ``data/tickets.json`` (created automatically).
- A missing file means a fresh start (an empty list).
- A malformed or inconsistent file raises :class:`StorageError` and is NEVER
  overwritten, so a human can repair it.
- Loading validates the WHOLE collection and returns a brand-new list. Nothing
  is handed back unless every record is acceptable, so a load that fails
  half-way cannot leave the caller holding a partly-valid collection.
- Saving validates too, which gives one guarantee: anything this module writes
  is something this module can read back.

File format
-----------
A plain JSON list of ticket objects -- the same envelope the original
CampusFlow used, so pre-existing ticket files keep working::

    [
      {
        "id": "T001", "title": "Wi-Fi down", "category": "Network",
        "urgency": "high", "affected_users": 15, "priority": "critical",
        "status": "open", "assigned_to": null,
        "notes": [
          {"note_id": "N001", "author": "Mentor A", "message": "Rebooted AP."}
        ]
      }
    ]

Migration: ``notes`` was added in CampusFlow Next. A file written by the
original version has no ``notes`` key; those tickets are upgraded to
``"notes": []`` on load rather than being rejected, so old tickets are not
discarded. Every other field is required.
"""

import json
import os
import tempfile

from campusflow.tickets import next_ticket_id  # noqa: F401  (re-exported)
from campusflow.validation import (
    ValidationError,
    validate_ticket_collection,
)

DEFAULT_PATH = os.path.join("data", "tickets.json")


class StorageError(ValidationError):
    """Raised when the ticket file cannot be read or written safely.

    Subclasses ValidationError, which subclasses ValueError, so the CLI's
    existing ``except ValueError`` shows it.
    """


def load_tickets(path=DEFAULT_PATH):
    """Return the validated list of tickets stored at ``path``.

    - Missing file -> ``[]`` (fresh start).
    - Unreadable, malformed or inconsistent -> :class:`StorageError`, and the
      file is left exactly as it was.

    The returned list is always newly built. Validation is all-or-nothing:
    a single bad record means the caller gets an exception, never a partial
    list, so a previously good in-memory collection can never be replaced by
    something half-broken.
    """
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as err:
        raise StorageError(
            f"Ticket file '{path}' is not valid JSON ({err}). "
            "It was NOT changed. Fix or delete it, then restart."
        ) from err
    except OSError as err:
        raise StorageError(f"Could not read ticket file '{path}': {err}") from err

    try:
        return validate_ticket_collection(data, source=f"file '{path}'")
    except ValidationError as err:
        # Re-wrap so callers only ever need to know about StorageError, and
        # so the message reminds the user that their file is still intact.
        raise StorageError(
            f"Ticket file '{path}' was rejected: {err} "
            "The file was NOT changed. Fix or delete it, then restart."
        ) from err


def save_tickets(tickets, path=DEFAULT_PATH):
    """Validate, then write tickets to ``path`` as JSON.

    The write goes to a temporary file which is then swapped in with
    ``os.replace`` (atomic on the same filesystem), so a crash part-way
    through cannot leave a half-written tickets file.

    Validation happens before the temporary file is even created, so a
    rejected save touches nothing at all.
    """
    cleaned = validate_ticket_collection(tickets, source="the collection being saved")

    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        dir=folder or ".", prefix=".tickets-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, indent=2)
        os.replace(temp_path, path)
    except BaseException:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise
