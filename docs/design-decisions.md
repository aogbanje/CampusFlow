# Design decisions

## Where is the ticket collection stored and how is it passed between functions?
Storage: A plain list of dictionaries that gets passed into functions, which keeps tests easy because there is no hidden global state.

## How does a function signal invalid input (exception or structured error), and how does the CLI display it?
Errors: Raising ValueError with a clear message, and the CLI catches it and prints it.

## What is the expected return value when a ticket is created, assigned, or updated?
Return values: create_ticket returns the new ticket dictionary.

ID generation: Engineer A owns the ID generation. It works after a reload, We derive the next ID from the highest existing numeric ID + 1, not from len(tickets) + 1; because no delete feature exists, so highest + 1 never reuses an ID.

## Which module owns loading/saving JSON and how do other modules call it?
JSON: Storage.py owns loading/saving JSON. Both engineers integrate it.

## How can we test business logic without asking for interactive input inside each test?
We test business logic by using pure functions that take arguments, with no input() inside them. The CLI in main.py is the only place that asks for input.

---

# CampusFlow Next — decisions added by Engineer A

These were agreed with Engineer B **before** coding, because B's CLI calls
A's functions directly.

## 1. One error convention, everywhere: exceptions

Every function in the data layer raises `ValidationError` (a subclass of
`ValueError`) on refusal. Nothing returns `None` or a "success" flag to mean
failure. This keeps the existing `except ValueError` blocks in `main.py`
working while letting new code catch the narrower type.

B's CLI therefore wraps calls in `try/except ValueError` and prints the
message. No function needs a second return value for "did it work".

## 2. Predicates for asking, actions for doing

Some refusals are normal UI events ("this ticket is resolved, reopen it
first"), and an exception is a clumsy way to say that. So each mutation has a
side-effect-free companion:

| Ask (never raises)   | Do (raises on refusal) |
|----------------------|------------------------|
| `can_transition(...)`| `change_status(...)`   |
| `can_assign(...)`    | `assign_ticket(...)`   |
| `can_add_note(...)`  | `add_note(...)`        |

`can_transition` is the single definition of the ticket lifecycle.
`change_status` calls it, so the menu can never offer a move the workflow
would refuse. `tests/test_workflow.py::TestCanTransition` cross-checks the two
against every combination of status, assignee and target.

## 3. Validation is centralised, and it never mutates

All rules live in `campusflow/validation.py`. Every `validate_*` helper
returns a cleaned value or raises; none of them writes to a ticket.

This is what makes **validate-before-mutate** real rather than aspirational:
a function performs every check first and writes on its last line, so a
refusal cannot leave a half-changed ticket. The tests assert both the raised
error *and* that the ticket is byte-for-byte unchanged, because an exception
alone does not prove the data survived.

## 4. `calculate_priority` moved into `validation.py`

`validate_ticket` has to re-derive the priority to check that a stored
`priority` agrees with its `urgency` and `affected_users`. That means
validation needs the rule, and validation must not import higher-level
modules (that would be a circular import). The rule now lives in
`validation.py` and `tickets.py` re-exports it, so
`from campusflow.tickets import calculate_priority` still works.

## 5. Why loading validates the derived field at all

`priority` is *derived* from `urgency` and `affected_users`, not typed by a
human. A file that says `urgency: low, affected_users: 1, priority: critical`
is internally contradictory, and the reports would happily count it. The
loader rejects it instead of reporting a number nobody can trust.

## 6. `notes` is optional on load — a deliberate migration

`notes` is new in CampusFlow Next, so a file written by the original version
has no such key. Rejecting those files would effectively discard every
existing ticket, which the guide forbids. Such records are upgraded to
`"notes": []` on load. Every *other* field stays required, and once a file
has been saved by CampusFlow Next it always contains `notes`.

The JSON envelope is unchanged: a plain list of ticket objects. There is no
version wrapper, so old files load with no conversion step.

## 7. `save_tickets` validates before writing

This gives one guarantee: **anything this module writes, this module can read
back.** It also means a bug that builds a malformed ticket is caught at the
save boundary instead of silently poisoning the file for the next run.

Consequence: `save_tickets([{"id": "T002", "bad": object()}])` now raises
`ValidationError` rather than `TypeError`. The original test's real subject —
a failed save leaves the previous file intact with no temp files behind — is
unchanged and still asserted.

## 8. Note IDs are derived, never counted

`next_note_id(ticket)` returns highest existing number + 1, exactly like
`next_ticket_id`. This is what makes "a rejected note does not consume an ID"
true *by construction* instead of by remembering to decrement a counter.
It also means IDs stay correct across a save/reload cycle, since they are
recomputed from the notes that actually exist.

Note IDs are unique **within a ticket**; a note is identified by the pair
(ticket ID, note ID). Uniqueness across the whole file is therefore not
required and is not enforced.

## 9. The Open Work Queue now shows OPEN tickets only

**This changes original behaviour.** The first version had
`QUEUE_STATUSES = ("open", "in_progress")` — its own comment flagged the
choice as undecided. The CampusFlow Next contract fixes it: the original
queue lists open tickets only, and an `in_progress` or `resolved` ticket must
not appear in it.

`tests/test_workflow.py::test_queue_excludes_in_progress_tickets` replaces
`test_queue_includes_in_progress_tickets`, which asserted the old behaviour
and would now be wrong. The ticket is still *unresolved*, so it counts in
`unresolved` and appears in the separate priority-sorted search view. Nothing
was silently swapped — the queue was corrected and the change is recorded
here, in the test docstring, and in `docs/baseline-check.md`.
