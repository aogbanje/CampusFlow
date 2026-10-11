"""JSON persistence for CampusFlow (feature F7).

Rules from the README / guide:
- Tickets are saved to data/tickets.json (created automatically).
- A missing file means a fresh start (empty list).
- A malformed file raises a clear error and is NEVER overwritten.
- IDs must stay unique after reload.

Other modules never touch files; they call load_tickets / save_tickets.
"""

import json
import os
import tempfile

DEFAULT_PATH = os.path.join("data", "tickets.json")

REQUIRED_FIELDS = (
    "id",
    "title",
    "category",
    "urgency",
    "affected_users",
    "priority",
    "status",
    "assigned_to",
)


class StorageError(ValueError):
    """Raised when the ticket file cannot be read safely.

    Subclasses ValueError so the CLI's usual `except ValueError` shows it.
    """


def load_tickets(path=DEFAULT_PATH):
    """Return the list of tickets stored at `path`.

    - Missing file -> [] (fresh start).
    - Malformed JSON or wrong structure -> StorageError. The file is not
      modified, so a human can repair it.
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

    _validate_structure(data, path)
    return data


def _validate_structure(data, path):
    """Check the loaded JSON is a list of ticket dicts with unique IDs."""
    if not isinstance(data, list):
        raise StorageError(
            f"Ticket file '{path}' must contain a list of tickets."
        )

    seen = set()
    for index, ticket in enumerate(data):
        if not isinstance(ticket, dict):
            raise StorageError(
                f"Ticket #{index + 1} in '{path}' is not an object."
            )
        missing = [field for field in REQUIRED_FIELDS if field not in ticket]
        if missing:
            raise StorageError(
                f"Ticket #{index + 1} in '{path}' is missing: "
                f"{', '.join(missing)}."
            )
        if ticket["id"] in seen:
            raise StorageError(
                f"Duplicate ticket ID '{ticket['id']}' in '{path}'."
            )
        seen.add(ticket["id"])


def save_tickets(tickets, path=DEFAULT_PATH):
    """Write tickets to `path` as JSON, creating the folder if needed.

    Writes to a temporary file first and then swaps it in, so a crash
    part-way through cannot leave a half-written tickets file.
    """
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        dir=folder or ".", prefix=".tickets-", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(tickets, f, indent=2)
        os.replace(temp_path, path)
    except BaseException:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


def next_ticket_id(tickets):
    """Return the next unused ID ('T001' for an empty list).

    Based on the highest existing number, so IDs stay unique after a
    reload and are never reused.
    """
    highest = 0
    for ticket in tickets:
        try:
            highest = max(highest, int(ticket["id"][1:]))
        except (KeyError, ValueError, TypeError):
            continue
    return f"T{highest + 1:03d}"