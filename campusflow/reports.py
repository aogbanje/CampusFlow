"""Quality insights for the Head of Campus (Requirement D, Engineer B).

The original report answered "how many of each status and priority?". The
Head of Campus also needs the unresolved workload, the resolved count, the
resolution rate and a category breakdown, and the numbers must not contradict
each other.

Contract
--------
* :func:`build_report` is read-only -- it never edits the collection.
* Every status, priority and category key is ALWAYS present, zero-filled, so
  a caller can index the result without checking whether a key exists. An
  empty collection therefore produces a complete report, not an empty dict.
* Each ticket is counted exactly once. The whole report is built in a single
  pass, and ``unresolved`` is derived from the status counts rather than
  counted again, so the figures cannot double-count or disagree.
* ``resolution_percentage`` is ``0.0`` for an empty collection. Dividing by
  ``len(tickets)`` before checking for zero would be a ZeroDivisionError, and
  reporting 100% for "nothing resolved out of nothing" would be a lie.

Counts always describe the collection as it stands now, so a ticket that was
resolved and then reopened is counted as ``open``, not as ``resolved``.
"""

from campusflow.validation import CATEGORIES, PRIORITIES, STATUSES

#: Statuses that mean "still needs work". Kept next to the report so the
#: definition of unresolved lives in one place.
UNRESOLVED_STATUSES = ("open", "in_progress")


def build_report(tickets):
    """Return totals, breakdowns and the resolution rate for `tickets`.

    Returns a dict with:

    ``total``
        Number of tickets.
    ``by_status`` / ``by_priority`` / ``by_category``
        Counts keyed by every legal value, zero-filled.
    ``unresolved``
        Tickets still open or in progress.
    ``resolved``
        Tickets currently resolved.
    ``resolution_percentage``
        ``resolved / total * 100``, or ``0.0`` when there are no tickets.
    """
    by_status = {status: 0 for status in STATUSES}
    by_priority = {priority: 0 for priority in PRIORITIES}
    by_category = {category: 0 for category in CATEGORIES}

    for ticket in tickets:
        # Guarded lookups: a stray value would otherwise raise a KeyError
        # here and take the whole report down. Loading validates these
        # fields, so this is belt-and-braces for in-memory data.
        status = ticket.get("status")
        priority = ticket.get("priority")
        category = ticket.get("category")

        if status in by_status:
            by_status[status] += 1
        if priority in by_priority:
            by_priority[priority] += 1
        if category in by_category:
            by_category[category] += 1

    total = len(tickets)
    # Derive both figures from by_status so they always agree with it.
    unresolved = sum(by_status[status] for status in UNRESOLVED_STATUSES)
    resolved = by_status["resolved"]

    # Check for an empty collection BEFORE dividing.
    percentage = (resolved / total * 100) if total else 0.0

    return {
        "total": total,
        "by_status": by_status,
        "by_priority": by_priority,
        "by_category": by_category,
        "unresolved": unresolved,
        "resolved": resolved,
        "resolution_percentage": percentage,
    }


def format_percentage(percentage):
    """Render a resolution rate for the CLI, e.g. ``42.9%``.

    Kept here rather than in ``main.py`` so the rounding rule is testable
    without capturing printed output.
    """
    return f"{percentage:.1f}%"
