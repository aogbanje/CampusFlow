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

# CampusFlow Next — Engineer B

## Do the optional search filters combine with AND or with OR?
AND. A ticket is returned only when it satisfies every filter that was actually supplied.

Reason: the user sets a filter in order to *narrow* the list. Someone who
types `wifi` and also picks `Network` means "the Wi-Fi problems in the
Network category", not "everything that is Wi-Fi OR Network". OR would make
adding a filter widen the result, which is the opposite of what the control
looks like it does.

Consequence: a single failing filter drops the ticket, which is why the
implementation can be read as a list of predicates that must all pass.

See `campusflow/search.py::_matches` and `tests/test_search.py::TestCombinedFilters`.

## Why must search not edit the ticket collection?
Because it is a *view*, not an action. Nothing the user typed while searching
has been validated as an intended change, so there is no valid change to
make. Search returns a new list holding the same ticket dicts, and never
shortens, reorders or edits the original.

This is asserted rather than assumed:
`tests/test_search.py::TestSearchIsReadOnly` snapshots the collection before
and after a search, checks the original order is unchanged, and checks the
returned list is a different object.

A separate reason is the priority-sorted view in Requirement D: it is the
same read-only operation with a different ordering, so making search sort in
place would corrupt the stored order for every other view.

## What does a blank filter mean?
"Do not filter by this field" — not "match the empty string".

The two are easy to conflate and the mistake is quiet: treating a blank
category as a value would match nothing and look like "no tickets found",
which the user would read as a data problem rather than a UI one. `None` and
whitespace-only strings are therefore both normalised to `None` and skipped.

Pinned by `tests/test_search.py::test_blank_filters_are_not_applied`.

## Why is the resolution percentage 0.0 for an empty dataset?
Because it is both the arithmetically honest answer and the one that cannot
crash. `resolved / total * 100` divides by zero when there are no tickets, so
the total is computed first and the division is guarded.

Reporting 100% (or `N/A`) would be a worse answer than 0%: with no tickets
there is nothing resolved, and a percentage the Head of Campus cannot
compare against the following week is not worth showing.

Pinned by `tests/test_reports.py::test_empty_dataset_reports_zero_percent_without_crashing`
and `tests/test_cli.py::TestReportsMenu::test_empty_collection_reports_zero_percent`.

## Is punctuation normalised during title search?
No. Search is case-insensitive **substring** matching and nothing more, so
`WI-FI` matches `wi-fi` but `wifi` does **not** match `Wi-Fi`.

I considered stripping punctuation so `wifi` would also match `Wi-Fi`. It
works, and it makes the search feel friendlier — but it is the beginning of
fuzzy matching, which the brief explicitly rules out ("Do not promise fuzzy
spelling correction; substring matching is enough" and "WI-FI and wi-fi match
each other, **assuming the same punctuation**").

It would also introduce silent surprises: `T-001` and `T001` would start
matching each other, and the transformation has to be applied consistently to
both sides or the results become unpredictable. The suggestion and the reason
for rejecting it are recorded in `docs/ai-learning-log.md`, Interaction 6.

Pinned by `tests/test_search.py::test_punctuation_is_not_normalised_away` — a
test whose purpose is to stop this being "fixed" later without a decision.

## Why was the original Open Work Queue left alone?
Requirement D asks for a separate optional view sorted by priority and ticket
ID, and explicitly says the original queue must not be silently replaced.

The original queue shows **open tickets only** — that is the contract, and
`in_progress` work is deliberately excluded from it. Rather than widen that
filter (which would quietly change what an existing menu option means for
every user who already relies on it), the broader priority-ordered view was
added as part of Search (option 7), which shows any status the user asks for.

Menu option 5 is unchanged in behaviour and in name; the two views now sit
side by side, and the difference between them is documented rather than
implied.

## Why do the CLI handlers take input_fn and output_fn?
So the menu can be tested without a human at a keyboard.

A handler that calls `input()` directly can only be tested by typing, which
means CLI behaviour is usually left untested — and the retry loops, which are
exactly the code most likely to hide an infinite loop, are the least tested
code in the project.

Passing `input_fn=input` and `output_fn=print` as defaults changes nothing
for real users but lets a test drive "choose option 8, then type a bad ticket
ID" with a scripted reply list and assert on the messages that came back. See
`tests/test_cli.py`, where no test touches the keyboard or `data/tickets.json`.
