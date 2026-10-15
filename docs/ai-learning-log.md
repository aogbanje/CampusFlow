# AI Learning Log

# Project: CampusFlow — CLI Helpdesk Ticket Manager


## Fellow: Ogbanje Abraham Okwute (Engineer A)

### Interaction #1: Shared function contracts and design decisions

Problem: Before coding, my partner and I needed agreed interfaces (storage,
errors, return values, ID generation, JSON ownership, testability).

My initial understanding: I knew functions take arguments but hadn't thought about passing the ticket list vs a global variable.

Prompt to AI: As engineer A, what do you advise are the pointers to know to be able to write this project

Useful AI guidance: Suggested a plain list of dicts passed into functions,
ValueError for invalid input, pure functions with no input() outside main.py,
and deriving the next ID from the highest existing ID rather than len()+1.

My independent experiment/test: Build a list with T001 and T003 in
the REPL and compare len(list)+1 with max-id+1; write what you observed>

Verification source or result:
- REPL: with ids T001 and T003, len + 1 gave T003, highest + 1 gave T004.
  max(["T009", "T010"]) gave 'T010', which is correct only because the IDs are
  zero-padded. max(["T999", "T1000"]) gave "T999", which shows string order
  fails once IDs get wider, so I compare the numeric part..
- Test: test_next_id_uses_numeric_max_not_length_or_string_order ... ok
- Reference: Python docs, built-in functions, max() (docs.python.org/3/library/functions.html#max): confirms the default= argument and that strings compare in text order.

Decision: Flagged the statement "the operator owns ID generation"; it was corrected to Engineer A.

Related file/commit: docs/design-decisions.md, b6d6b087522157d79a06a9eeb1d056a5d0f723c8

What I can now explain without AI:`len(tickets) + 1` only works if IDs are
contiguous. With T001 and T003 in the list it gives T003, which duplicates an
existing ID, so assign and change_status could act on the wrong ticket. Taking
the highest numeric ID + 1 depends only on the data, and I convert to int
because "T009" sorts after "T010" as text.

### Interaction #2: bool is a subclass of int (validating affected_users)

My initial understanding: isinstance(x, int) is enough

Prompt to AI: Explain isinstance() and bool in Python with a small example
unrelated to tickets.

Useful AI guidance: bool is a subclass of int in Python, so True behaves as 1
and False as 0. That means isinstance(True, int) is True, and a validator that
only checks for int would accept True as a valid affected_users count. The fix
is to reject bool explicitly, before the int check.

My independent experiment/test:
Prediction (before running): True
Ran in REPL:
>>> isinstance(True, int)
True
>>> True + 1
2
>>> type(True)
class 'bool'

Then, in validate_affected_users, I deleted the isinstance(value, bool) check
and ran the tests. Expected: test_invalid_affected_users_rejected fails for
value=True, because True is treated as 1 and returned as valid. 

I restored the check and the suite
passed again: Ran tests ... OK.

Verification source or result: REPL output above, the failing and then passing
test run, and the Python docs for built-in bool

(https://docs.python.org/3/library/functions.html#bool), which state that bool
is a subclass of int. 

Decision: Accepted the explicit bool check in validate_affected_users. Without
it, True would be stored as an affected_users value of True and could be
treated as 1 in priority calculations.

Related file/commit: campusflow/tickets.py (validate_affected_users),
tests/test_tickets.py (test_invalid_affected_users_rejected).


### Interaction #3: Reviewing AI-generated code for Engineer A's half

Problem: I asked AI to write tickets.py and test_tickets.py, and needed to
understand and verify it before opening a PR.

My initial understanding: I knew the rules but not how to structure the validators.

Prompt to AI: "write the code" (an earlier request was answered with a
skeleton; the AI then provided full code).

Useful AI guidance: Full tickets.py and 15 tests, with advice to retype it,
predict outputs, and break it on purpose.

My independent experiment/test: changed >= 10
to > 10 and recorded which tests failed:
- FAIL: test_boundaries (test_tickets.TestPriority.test_boundaries) (urgency='high', users=10)
- FAIL: test_boundaries (test_tickets.TestPriority.test_boundaries) (urgency='low', users=10)


Verification source or result: python3 -m unittest discover -s tests -v
tical
- self.assertEqual(calculate_priority(urgency, users), expected)
AssertionError: 'medium' != 'high'


Related file/commit: campusflow/tickets.py, tests/test_tickets.py

### Critical evaluation

AI suggestion: That "T009" would sort after "T010" as text, so a string max
would pick the wrong ID, and a test named
test_next_id_uses_numeric_max_not_length_or_string_order proved it.

What I checked: I ran max(["T009", "T010"]) in the REPL and got 'T010', so the
claim was wrong for zero-padded IDs. [I then ran max(["T999", "T1000"]) and got "T999".]

Decision: Corrected. The numeric comparison is still the right design, but the
reason is IDs wider than three digits, not T009 vs T010. [I changed the test to
use T999 and T1000 and confirmed it fails with a string-based max: yes.]

Evidence: 
>>> max(["T999", "T1000"])
'T999'




---

# CampusFlow Next — Sprint 2

## Fellow: Ogbanje Abraham Okwute (Engineer A)

Scope for this sprint: centralised validation, ticket lifecycle safety,
structured follow-up notes, and validated JSON load/save.

The concept gaps below were chosen because they are the ones I hit while
writing `campusflow/validation.py`, `campusflow/notes.py` and the new
`campusflow/storage.py` — not because they were on a checklist.

### Interaction #4: `json.load` succeeding does not mean the data is trustworthy

**My initial understanding:** If `json.load()` returns without raising, the
file is fine and I can use it. I thought JSON validation meant "is this valid
JSON?"

**Prompt to AI:**
"Why might `json.load` succeed but return unsafe or inconsistent business
data? Explain the difference between syntactic validity and business
consistency, using a small example unrelated to my project — for example a
library book catalogue — then quiz me on it."

**Useful AI guidance:**
`json.load()` only proves the *text* is well-formed JSON. It says nothing
about whether the resulting Python objects make sense to my program. The AI
separated this into three layers:

1. **Syntactic** — is it parseable JSON? (`json.JSONDecodeError`)
2. **Structural** — is it a list? Does each item have the keys I expect?
3. **Semantic** — are the values legal, and are they consistent with each
   other?

My original `_validate_structure` covered layers 1 and 2 only. It checked
that keys existed and that ticket IDs were unique, but never that
`"status": "banana"` was a legal status, or that a ticket's `priority` agreed
with its `urgency` and `affected_users`.

The AI also made a point I had not separated out before: `priority` is
*derived*, not typed in. `urgency` and `affected_users` are inputs, `priority`
is output. So a stored priority can be checked against the rule that would
have produced it.

**My independent experiment/test (unrelated example):**
A book catalogue where `available_copies` cannot exceed `total_copies`.

Prediction (before running):

```python
import json
raw = '[{"title": "Dune", "total_copies": 3, "available_copies": 9}]'
catalogue = json.loads(raw)          # prediction: succeeds, no error
catalogue[0]["available_copies"] > catalogue[0]["total_copies"]   # True
```

So the parse succeeds and the record is nonsense. The check has to be written
by hand:

```python
def validate_book(book):
    if book["available_copies"] > book["total_copies"]:
        raise ValueError("available cannot exceed total")
```

**⚠️ PENDING — paste the actual REPL output here before submitting.**
Run the two snippets above and record what you saw. Also record the output of
`python3 -c "import json; json.loads('')"` to see the actual
`JSONDecodeError` text.

**Verification source or result:**

- Test: `test_storage.py::TestLoadRejectsInconsistentRecords::test_priority_inconsistent_with_the_rule_is_rejected`
  — a file with `urgency: low, affected_users: 1, priority: critical` is
  rejected with "does not match the rule".
- Test: `test_validation.py::TestValidateTicket::test_priority_inconsistent_with_urgency_and_users_is_rejected`
- Test: `test_validation.py::TestValidateTicket::test_illegal_status_in_a_record_is_rejected`
- Reference: Python docs, `json` module,
  `json.JSONDecodeError` (docs.python.org/3/library/json.html) — confirms the
  decoder raises on malformed input and says nothing about the contents.

**Decision:** Accepted, and it went further than the AI first framed it. I
added a *semantic* layer to `load_tickets`: every record is validated with the
same `validate_ticket()` the running application uses, including re-deriving
`priority` from `urgency` and `affected_users` and comparing. A file that
contradicts itself is now rejected instead of being reported as a number
nobody can trust.

There is a second benefit I only saw after implementing it: because loading
reuses the same validators as creation, a hand-edited file **cannot** contain
a note the running app would have refused to create. There is one definition
of a valid ticket, not two.

**Related file/commit:** `campusflow/validation.py` (`validate_ticket`,
`validate_ticket_collection`), `campusflow/storage.py` (`load_tickets`),
`tests/test_storage.py`. Commit SHA: _to record_.

**What I can now explain without AI:**
Three separate questions have to be answered about loaded data — can it be
parsed, does it have the shape I expect, and are its values legal and
consistent? `json.load()` answers only the first. For CampusFlow the third
layer is the important one, because `priority` is derived: if a stored
priority disagrees with the rule, the analytics will confidently report a
wrong number, and the mistake is invisible unless you go looking for it. The
fix is to validate on load with the *same* rules used on creation, and to
reject the whole collection rather than install a partly-valid one.

---

### Interaction #5: A suggestion I REJECTED after reviewing the evidence

**Concept gap:** How to add a new field (`notes`) to a format that already has
data files in use. I did not know how to make the loader accept old files
without weakening validation.

**Prompt to AI:**
"My JSON is a list of ticket objects. I want to add a `notes` field, which is
a list of note objects. There are already ticket files in use that have no
`notes` key. How should the loader handle them? Give me the options and the
trade-offs; do not write my project."

**Useful AI guidance (the ordinary answer):**
Add `"notes"` to the required-fields list, so every ticket must have it — this
keeps the schema strict and the validation uniform. Any file missing `notes`
would then be rejected as incomplete.

The AI's own trade-off note is what made me stop and check it: rejecting the
file means the user cannot load their existing tickets at all.

**Why I rejected it (evidence):**

I checked this against the acceptance contract rather than against how tidy
the code would look. The contract says: *"You may refactor internally, but do
not discard old working tickets. If you change file format incompatibly,
include a small documented migration or clearly explain supported versions
and protect source data."*

Every ticket file written by the original CampusFlow lacks `notes`, because
the original version had no such field. Making `notes` required would mean
every existing file is rejected — and since `main.py` refuses to start when
loading fails, the practical effect is that no existing user can open the app
at all. "Stricter validation" would have been the wrong kind of strict.

I then compared three options instead of two:

| Option | Effect on existing files | Verdict |
|--------|--------------------------|---------|
| Make `notes` required | All rejected, app will not start | Rejected |
| Accept any ticket, ignore bad notes | Old files load, but malformed notes get in | Rejected — this is the hole Requirement E closes |
| Absent `notes` means `[]`; present `notes` is fully validated | Old files upgraded, new damage still caught | **Chosen** |

The third option keeps the strictness exactly where the risk is. A file with
*no* `notes` key is not damaged, it is just old. A file with a `notes` list
that contains a note with no `message`, or a duplicate `N001`, *is* damaged
and is still rejected.

**My independent experiment/test:**
Simulate a file written by the original version and confirm it loads, while a
newly *damaged* notes list is still refused.

Prediction (before running): the legacy file loads with `notes == []`, and
the second file raises `StorageError` mentioning the message length.

```python
legacy = {"id": "T001", "title": "Wi-Fi down", "category": "Network",
          "urgency": "high", "affected_users": 15, "priority": "critical",
          "status": "open", "assigned_to": None}      # no "notes" key
# -> expect: loads, and the result has notes == []

damaged = dict(legacy, notes=[{"note_id": "N001", "author": "Mentor A"}])
# -> expect: rejected, because the note has no "message"
```

**⚠️ PENDING — paste the actual run output here before submitting.**
Run the two snippets through `load_tickets` on a temp file and record the
result. Do not write the result you expect; write the result you get.

**Verification source or result:**

- Test: `test_storage.py::TestLoadRejectsInconsistentRecords::test_legacy_file_without_notes_still_loads`
- Test: `test_storage.py::TestLoadRejectsInconsistentRecords::test_malformed_note_is_rejected`
  (this is the pair that proves the decision was implemented, not just
  discussed: one file loads, the other does not)
- Test: `test_validation.py::TestValidateTicket::test_legacy_ticket_without_notes_key_is_upgraded`
- Documented in `README.md` under "Migration and version support" and in
  `docs/design-decisions.md` §6.

**Decision:** **Rejected the AI's suggested approach.** `notes` stays
*optional on load, required after that*: an absent key is upgraded to `[]`,
while a present `notes` value is passed through full per-note validation.
Every other field remains required. Old tickets are preserved and new damage
is still caught.

**Related file/commit:** `campusflow/validation.py`
(`LEGACY_OPTIONAL_FIELDS`, `validate_notes`), `campusflow/storage.py`,
`README.md`. Commit SHA: _to record_.

**What I can now explain without AI:**
Making a schema stricter is not automatically safer. The question is whether
the thing being rejected is *damaged* or merely *old*. A missing `notes` key
is old — the original app could not have written it. A `notes` list
containing a note with no message is damaged. Treating those two cases the
same would either lock every existing user out of their own data, or let real
corruption through. The safe default is to accept the old shape, upgrade it
in memory, and keep full validation on any data that is actually present.

---

### Interaction #6: Comparing two designs for reporting a refusal

**Concept gap:** Whether a function that refuses an action should raise an
exception or return a value like `False`/`None`. I had been raising
everywhere, but the CLI needs explanations, and catching exceptions for
ordinary control flow felt wrong.

**Prompt to AI:**
"Compare two designs for a Python function that refuses an invalid action:
(A) raise an exception, (B) return a success flag or None. Which is easier to
test, and which is easier to call from a menu that must explain the refusal
to a user? Give the trade-offs for each and do not write my project."

**Useful AI guidance:**
The AI argued that (B) is friendlier at a call site because the caller does
not need `try/except`, and that using exceptions for expected outcomes is
often called an anti-pattern.

It also stated that "exceptions should be reserved for exceptional
conditions". I did not accept that claim as-is, because in this program a
refused status change is not exceptional — it is an ordinary event a support
desk user hits constantly. So the stated reason did not obviously apply.

**What I checked, and the decision:**

I tested the AI's claim against the code that already existed rather than
against theory. `main.py` already wraps these calls in `except ValueError`,
and `docs/design-decisions.md` — written before this sprint — already records
"Raising ValueError with a clear message, and the CLI catches it and prints
it." Switching to return-values would mean two conventions in one codebase,
which the acceptance contract explicitly warns against: *"Agree on error
response conventions (exceptions or explicit results); do not combine
inconsistent patterns."*

So neither pure design was right. What I actually wanted was both, without
mixing them:

- the **mutating** function raises (`change_status`, `add_note`) — one
  convention, unchanged, existing `except ValueError` still works;
- a separate, side-effect-free **predicate** answers "may I?" without raising
  (`can_transition`, `can_assign`, `can_add_note`) — so the menu can print the
  reason without using exceptions for control flow.

The AI's underlying concern was correct; its proposed fix would have created a
second convention. Separating "ask" from "do" solved it while keeping one
error convention.

**My independent experiment/test:**
I wrote a test that cross-checks the two functions against each other, so the
predicate can never drift from the action:

Prediction (before running): for every combination of status × assignee ×
target, `can_transition(...)[0]` equals "did `change_status` succeed", and
when it fails the ticket is byte-for-byte unchanged.

```python
allowed, _ = can_transition(ticket, target)
try:
    change_status(tickets, "T001", target)
    acted = True
except ValueError:
    acted = False
    assert tickets == before      # a refusal must write nothing
assert allowed == acted           # the two must agree
```

**⚠️ PENDING — paste the actual run output here before submitting.**
Run `python3 -m unittest tests.test_workflow.TestCanTransition -v` and paste
the result. If any combination disagrees, that is a real bug in my code and
belongs in this log as found, not as predicted.

**Verification source or result:**

- Test: `tests/test_workflow.py::TestCanTransition::test_predicate_agrees_with_change_status`
- Test: `tests/test_workflow.py::TestCanTransition::test_predicate_never_raises_and_never_mutates`
- Test: `tests/test_notes.py::TestCanAddNote::test_never_raises_on_a_broken_ticket`
- Documented in `docs/design-decisions.md` §1 (one error convention) and §2
  (predicates for asking, actions for doing).

**Decision:** **Partly accepted, partly rejected.** I kept the exception
convention and rejected the proposal to switch to return values, because it
would have introduced a second convention into a codebase that already had
one. I accepted the AI's underlying point — "asking must not require
throwing" — and implemented it as separate side-effect-free predicates.

**Related file/commit:** `campusflow/workflow.py` (`can_transition`,
`can_assign`), `campusflow/notes.py` (`can_add_note`),
`docs/design-decisions.md`. Commit SHA: _to record_.

**What I can now explain without AI:**
A refusal can be reported two ways, and the right answer here was "neither
one alone". Mutating functions raise, so there is a single error convention
and the existing CLI keeps working. Read-only predicates return
`(allowed, reason)`, so a menu can explain a refusal without treating an
ordinary outcome as an exception. The risk of having both is that they drift
apart, so a test asserts they always agree. I also learned to check a general
claim ("exceptions are for exceptional conditions") against my own domain
before applying it — for a support queue, a refused status change is routine,
not exceptional.


# Fellow: Awo Wisdom
# Role: Engineer B

Language: Python 3.12.3

## Interaction 1 — JSON Persistence and Error Handling
Problem:
I needed to understand how to save tickets to a JSON file and load them again when the application restarts. I also needed to ensure that missing files and corrupted JSON files were handled correctly without accidentally losing existing data.
My initial understanding:
I understood that JSON allows Python data to be stored in a file. However, I needed to understand the difference between loading and saving data, how to handle a file that doesn't exist, and how to prevent malformed JSON from being treated as an empty ticket list.
Prompt to AI:
"Explain how Python's json.dump() and json.load() work, using a small example unrelated to my project. Explain how to handle a missing JSON file and malformed JSON without accidentally deleting existing data. Don't write my entire project for me."
Useful AI guidance:
I learned that:
- json.dump() writes Python data to a JSON file.
- json.load() reads JSON data from a file and converts it into Python objects.
- FileNotFoundError or an existence check can be used to handle a missing file.
- json.JSONDecodeError indicates that the file contents are not valid JSON.
- A missing file can represent a fresh start, but malformed JSON should produce an error rather than silently replacing the existing data.
I also learned that writing to a temporary file before replacing the original can help protect existing data against interrupted writes.
My independent experiment/test:
I plan to use a temporary directory to test three situations:
1. Load tickets when the file does not exist.
2. Load a file containing invalid JSON.
3. Save tickets, reload them, and compare the loaded data with the original.
I will observe whether the application behaves correctly in each situation.
Verification source or result:
My implementation contains tests for these behaviours in the storage test file, including:
- test_missing_file_gives_fresh_start
- test_malformed_json_raises_clear_error_and_keeps_file
- test_round_trip_preserves_tickets_exactly
The actual verification result should be recorded after running:
python3 -m unittest discover -s tests -v

# Decision:
I adopted the approach of treating a missing file as a fresh start while raising a clear error for malformed JSON. I also used temporary-file replacement when saving tickets to improve the reliability of persistence.
Related file/commit:
- campusflow/storage.py
- Storage tests — use the actual test-file path in your repository.
- Commit SHA or pull request link: To be added.
What I can now explain without AI:
I can explain that JSON persistence allows the application to retain tickets after it closes. When the application starts, it loads the saved tickets into Python data structures. A missing file can return an empty list, but corrupted data should produce an error so that existing information is not silently lost.
I can also explain why writing to a temporary file before replacing the original is safer than writing directly over the existing file.

## Interaction 2. — Understanding and Implementing Status Transitions
Problem:
I needed to implement the CampusFlow ticket lifecycle while ensuring that users could not make invalid status changes.
The required workflow is:
open → in_progress → resolved
A resolved ticket can be reopened by changing its status back to open. An unassigned ticket must not move into in_progress.
My initial understanding:
I understood that tickets have statuses representing their current state. However, I needed a clear way to define which transitions were permitted and prevent invalid transitions from modifying ticket data.
Prompt to AI:
"Explain how to implement a simple state-transition system in Python using a dictionary. Use an unrelated example, such as an order-processing system. Explain how to reject invalid transitions before modifying an object's state."
Useful AI guidance:
I learned that a dictionary can define the allowed next states for each current state.
For example, an order might move from pending to processing, then from processing to completed.
The program can check whether the requested next state belongs to the list of allowed transitions. If it doesn't, the program raises an error without changing the current state.
I applied this concept to CampusFlow by defining:
VALID_TRANSITIONS = {    "open": ["in_progress"],    "in_progress": ["resolved"],    "resolved": ["open"],}


The workflow function checks the requested transition before updating the ticket.
My independent experiment/test:
I will test the workflow using a small list containing an unassigned ticket and an assigned ticket.
The tests will check that:
- An unassigned ticket cannot move to in_progress.
- An assigned ticket can move from open to in_progress.
- An in-progress ticket can move to resolved.
- A resolved ticket can be reopened.
- An invalid transition raises an error without changing the original status.
Verification source or result:
The following tests are present in my submitted workflow tests:
- test_unassigned_ticket_cannot_go_in_progress
- test_assigned_ticket_progresses_open_to_resolved
- test_open_cannot_jump_to_resolved
- test_reopen_sets_status_back_to_open
I will record the actual test results after executing the test suite.
## Decision:
I adopted a dictionary-based approach because it keeps the allowed transitions together in one place and makes the workflow easier to understand.
I also kept the assignment check inside the workflow function because the project explicitly requires that an unassigned ticket cannot enter in_progress.
Related file/commit:
- campusflow/workflow.py
- Workflow test file — use the actual path in your repository.
- Commit SHA or pull request link: To be added.
What I can now explain without AI:
I can explain that a state-transition system controls how an object moves from one state to another. In CampusFlow, a ticket cannot jump directly from open to resolved. It must pass through in_progress.
I can also explain why validation must happen before changing the status: if a transition is rejected, the ticket should remain in its previous state.

## Interaction 3. — Automated Testing with Python's unittest
Problem:
I needed to test my functions without repeatedly running the entire application and manually entering information through the command-line menu.
I also needed to verify both successful operations and situations where the application should reject an operation.
My initial understanding:
I understood that tests help identify errors in a program. However, I needed to learn how to test functions independently, check their return values, and verify that expected errors were raised.
Prompt to AI:
"Explain Python's unittest framework to a beginner. Show me how to test a function's return value, how to test that an exception is raised, and how to check that an operation which fails leaves the original data unchanged. Use a small example unrelated to my project."
Useful AI guidance:
I learned that unittest.TestCase provides assertion methods for checking expected behaviour.
For example:
- assertEqual() compares actual and expected values.
- assertRaises() checks whether an operation raises a particular exception.
- setUp() prepares test data before a test runs.
- addCleanup() registers cleanup operations, such as deleting temporary directories after testing.
I applied these ideas to my storage and workflow tests.
For example, my workflow tests check that invalid transitions raise ValueError and that the ticket retains its original status.
My storage tests use temporary directories so that testing does not interfere with the application's actual ticket file.
My independent experiment/test:
I will run:
python3 -m unittest discover -s tests -v

I will inspect the output to determine which tests pass and which fail.
If a test fails, I will examine the error message and traceback, identify the underlying problem, correct it, and run the tests again.
Verification source or result:
The verification source is the actual output from Python's unittest test runner.
The test suite I shared includes checks for malformed JSON, duplicate ticket IDs, invalid status transitions, and ticket persistence.
Actual result: To be recorded after running the command.
Decision:
I adopted automated unit testing because it allows me to test individual functions without relying on manual interaction with the CLI.
I also used temporary directories for storage tests to avoid accidentally modifying the application's real data.
Related file/commit:
- Storage test file — actual path to be confirmed.
- Workflow test file — actual path to be confirmed.
- Commit SHA or pull request link: To be added.
What I can now explain without AI:
I can explain that a unit test checks a specific piece of functionality against an expected result. Instead of merely checking whether a function runs, I can verify its output, confirm that it rejects invalid operations, and check that it does not corrupt data when an operation fails.
I can also explain why tests should use isolated data and temporary files rather than depend on the application's real ticket database.

## Interaction 4. — Critical Evaluation of an AI Suggestion
Problem:
I needed to ensure that the application's ticket IDs remained unique when tickets were saved, loaded again, and followed by the creation of another ticket.
I also needed to understand how to verify suggestions rather than accepting AI-generated code without checking its behaviour.
My initial understanding:
I understood that each ticket must have a unique ID, such as T001, T002, and T003. However, I needed to determine how ID generation should work when existing IDs contain gaps or when the application restarts.
Prompt to AI:
"Review the logic of generating ticket IDs for a Python helpdesk application. Compare generating an ID from the number of existing tickets with generating it from the highest existing numeric ID. Explain the edge cases and suggest tests I can run to verify the behaviour."
Useful AI guidance:
The important lesson is that the number of existing tickets is not necessarily the highest ticket number.
For example, suppose the application contains:
tickets = [    {"id": "T001"},    {"id": "T005"},]


There are only two tickets, but the highest ID is T005.
Using the number of tickets to generate the next ID could produce T003, which may be undesirable because the system should avoid reusing IDs that were previously assigned.
My implementation instead looks for the highest recognized numeric suffix and adds one.
My independent experiment/test:
I will verify the behaviour using these scenarios:
1. An empty list produces T001.
2. Existing IDs T001 and T002 produce T003.
3. Existing IDs T001 and T005 produce T006.
4. Existing ID T999 produces T1000.
5. After saving and reloading tickets T001 and T002, the next ID is T003.
Verification source or result:
The submitted storage tests include:
- test_first_id_on_empty_list
- test_next_id_follows_highest_number
- test_gap_in_ids_does_not_cause_reuse
- test_ids_beyond_three_digits
- test_new_ticket_after_reload_does_not_duplicate_ids
I will record the actual results after running these tests.
## Decision:
I adopted the highest-numeric-ID approach because it handles gaps in the existing sequence and supports IDs beyond three digits.
The final implementation and test results should be checked against the actual repository before this entry is submitted.
Related file/commit:
- campusflow/storage.py
- Storage test file — actual path to be confirmed.
- Commit SHA or pull request link: To be added.
What I can now explain without AI:
I can explain why generating the next ticket ID from the number of tickets can be unreliable. The list length and highest ticket number are different things.
By examining the highest existing numeric suffix and adding one, the application can continue generating IDs after loading saved tickets, provided that the existing IDs are valid and unique.
