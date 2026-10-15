# Baseline check — CampusFlow before CampusFlow Next

Engineer A. Purpose: record what the audited commit actually did **before** any
change, so the improvements can be compared against evidence rather than memory.

The audited commit is `639fadf` ("Clean up README by removing extra blank
line"), which is the tip of `main` at the start of this sprint.

---

## 1. Run command and results

```bash
git checkout 639fadf
python3 -m unittest discover -s tests -v
```

> **PENDING — must be filled in from a real run before submission.**
> The exact command output (test count, pass/fail, any errors) belongs here
> verbatim. Do not paraphrase it and do not write a result you did not see.
>
> Copy the summary line (e.g. `Ran N tests in X.XXs` / `OK` or `FAILED (...)`)
> and paste the failing tracebacks if there are any.

| Item | Result |
|------|--------|
| Total tests | _to record_ |
| Passed | _to record_ |
| Failed / errored | _to record_ |
| Python version | _to record_ (`python3 --version`) |

---

## 2. Three inputs tested by hand at the audited commit

Run `python3 main.py` and record the **actual** behaviour, not the expected
behaviour. Note anything surprising.

| # | Input | Expected at the time | Actual | Verdict |
|---|-------|----------------------|--------|---------|
| 1 | Create: title `Wi-Fi down`, category `Network`, urgency `high`, users `15` | ticket created as `T001`, priority `critical` | _to record_ | _to record_ |
| 2 | Create: title `Bad ticket`, category `Network`, urgency `high`, users `0` | rejected with a clear message, no ticket added | _to record_ | _to record_ |
| 3 | Assign `T001` to a blank name, then check `T001` is unchanged | rejected, `assigned_to` still `null` | _to record_ | _to record_ |

Two further inputs worth trying because they probe the boundaries the audit
cared about:

| # | Input | Why |
|---|-------|-----|
| 4 | Create with affected users `True` / `2.5` | `True` is an `int` in Python; the old validator rejected it explicitly, so confirm that |
| 5 | Hand-edit `data/tickets.json` to set `"status": "banana"`, then restart | the old loader checked structure but **not** field values — record whether the app starts |

---

## 3. What the audit said needed improvement

> **PENDING — paste the three or four audit observations verbatim here.**
> The guide is explicit that audit observations are preliminary peer feedback.
> Record what was said, then say below which ones this repository's own
> evidence confirms.

| Audit observation (verbatim) | Reproduced? | Evidence |
|------------------------------|-------------|----------|
| _to record_ | _yes / no / not yet_ | _command or test name_ |

**Do not mark a peer-reported bug as confirmed until it is reproduced.**
Anything not reproduced stays "not yet reproduced" on this sheet.

---

## 4. Findings from reading the code at `639fadf`

These were found by reading the source, before running anything. Each one is a
claim that the tests in this sprint now pin down.

### 4.1 The Open Work Queue included `in_progress` tickets — contract conflict

`campusflow/workflow.py:23` had:

```python
# Change this to ("open",) if your team decides in_progress is excluded.
QUEUE_STATUSES = ("open", "in_progress")
```

The CampusFlow Next acceptance contract states the original Open Work Queue
shows **open tickets only**, and that an `in_progress` or `resolved` ticket
must not appear in it. The original code's own comment shows the choice was
never settled, and `tests/test_workflow.py` locked in the old behaviour with
`test_queue_includes_in_progress_tickets`.

This is the one **behavioural change to original functionality** in
Engineer A's scope. It is not a silent swap: the constant, the test, the
README, and `docs/design-decisions.md` §9 were all changed together, and the
replacement test
(`test_queue_excludes_in_progress_tickets`) carries a docstring explaining
what changed and why.

### 4.2 Load validated structure but not values

`campusflow/storage.py` `_validate_structure` checked that required keys were
present and that ticket IDs were unique. It did **not** check that:

- `category`, `urgency`, `priority` and `status` held legal values
- `priority` was consistent with `urgency` and `affected_users`
- `affected_users` was a positive integer
- an `in_progress` ticket had an assignee

A valid-JSON file with `"status": "banana"` therefore loaded successfully, and
the bad value surfaced later as a crash or a wrong number in the reports —
far from the file that caused it. This is the gap Requirement E targets.

There was also no `notes` validation because there were no notes.

### 4.3 `next_ticket_id` existed twice

Two implementations: `campusflow/tickets.py` (raised on a malformed ID) and
`campusflow/storage.py` (silently skipped a malformed ID). Same name, two
behaviours — a real hazard for ID continuity after a reload, which is exactly
the thing Requirement E asks to be safe. Consolidated into
`tickets.py`, with `storage.py` re-exporting it.

### 4.4 `change_status` and `assign_ticket` had no shared legality predicate

The rules were inline in each function. A menu therefore could not ask
"would this be allowed?" without triggering the mutation path and catching an
exception for control flow. `can_transition` and `can_assign` now hold the
rules, and the mutating functions call them.

### 4.5 What was already good and was deliberately preserved

Worth stating, so the fixes above are not read as "everything was broken":

- Priority rule order was already correct, including the
  `high` + 10-users case resolving to `critical` first.
- `assign_ticket` already checked before mutating.
- `save_tickets` already wrote to a temp file and used `os.replace`, so a
  crash mid-save could not half-write the file.
- Errors already subclassed `ValueError`, so the CLI's `except ValueError`
  worked.
- Tests already avoided `input()` by passing plain dicts.

---

## 5. What changed after the baseline, and how it is verified

| Requirement | Change | Verified by |
|-------------|--------|-------------|
| A — validation & status safety | `campusflow/validation.py` is now the single source of truth; `can_transition` gates the lifecycle | `tests/test_validation.py`, `tests/test_workflow.py::TestCanTransition` |
| B — structured notes | `campusflow/notes.py` | `tests/test_notes.py` |
| E — safe JSON | full-collection validation on load and save; `notes` legacy migration | `tests/test_storage.py::TestLoadRejectsInconsistentRecords`, `TestLoadNeverLosesState`, `TestIdContinuityAcrossReload` |
| Original queue contract | `QUEUE_STATUSES` corrected to `("open",)` | `test_queue_excludes_in_progress_tickets` |

### Tests changed or replaced

| Test | Change | Justification |
|------|--------|---------------|
| `test_queue_includes_in_progress_tickets` | replaced by `test_queue_excludes_in_progress_tickets` | It asserted the behaviour the new contract forbids. |
| `test_failed_save_keeps_previous_file_intact` | now expects `ValidationError` instead of `TypeError` | `save_tickets` validates before writing. The property the test protects — previous file intact, no temp files left behind — is unchanged and still asserted. |

Both changes are deliberate and are also recorded in
`docs/design-decisions.md`. Nothing else in the original test suite was
weakened, and `tests/test_tickets.py` was not modified at all.

---

## 6. Reproducing from a fresh clone

```bash
git clone https://github.com/aogbanje/campusflow.git
cd campusflow
python3 -m unittest discover -s tests -v
python3 main.py
```

`tests` must be run from the repository root: `campusflow` is imported as a
package, so running from elsewhere will fail with `ModuleNotFoundError`.

> **PENDING — paste the fresh-clone test output here once the branch is merged.**
