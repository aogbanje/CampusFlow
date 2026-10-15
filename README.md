# Project: CampusFlow — CLI Helpdesk Ticket Manager

CampusFlow is a Python command-line helpdesk ticket manager for Learn2Earn
campus staff. Informal support requests (Wi-Fi outages, faulty laptops, broken
dev environments) get lost, so CampusFlow records each problem, calculates its
priority, assigns responsibility, and tracks progress until it is resolved.

## Team

| Name                    |  Role      | Contribution summary                                                                                  |
|-------------------------|------------|-------------------------------------------------------------------------------------------------------|
| Ogbanje Abraham Okwute  | Engineer A | Ticket creation, validation helpers, note storage, JSON safety, tests                                 |
| Awo Wisdom              | Engineer B | Assignment, workflow, queue, reports and tests                                                        |
| Gabriel Oche            | Engineer B (campusflow next) | Search and combined filters, reports and quality insights, note and quiz CLI, tests |

Shared: JSON persistence, code reviews, documentation.


## Problem statement

Campus staff receive technical support requests such as Wi-Fi outages, faulty
laptops, broken development environments and inaccessible platforms. When these
are reported informally, they get lost, nobody knows who is responsible, and
urgent problems wait behind minor ones.

CampusFlow fixes this by giving every request a ticket. It:
- records each problem with a category, urgency and number of affected users
- calculates a priority (critical, high, medium or low) from fixed rules
- assigns each ticket to a named staff member
- tracks progress from open to in progress to resolved
- shows a work queue ordered by priority, and summary reports
- saves tickets to a JSON file so they survive a restart

## Requirements and setup
- Python version: Python3 3.12.3 (check with `python3 --version`)
- No external packages needed (standard library only: `json`, `unittest`).

```bash
git clone https://github.com/aogbanje/campusflow.git
cd campusflow
```

## Running the app

```bash
python3 main.py
```

Menu options:
| Option | Action                            |
|--------|-----------------------------------|
| 1      | Create ticket                     |
| 2      | List / view tickets               |
| 3      | Assign ticket                     |
| 4      | Change status                     |
| 5      | Open work queue                   |
| 6      | Reports                           |
| 7      | Search tickets                    |
| 8      | Add follow-up note                |
| 9      | View ticket notes                 |
| 10     | Engineering Understanding Check   |
| 0      | Exit                              |

## Running the tests

```bash
python3 -m unittest discover -s tests -v
```


## Ticket rules

**Fields:** id, title, category, urgency, affected_users, priority, status,
assigned_to, notes.

**Allowed values:** category: Network, Hardware, Software, Other. Urgency: low, medium, high.

**Priority** (first matching rule wins):

| Rule | Condition                           | Priority |
|------|-------------------------------------|----------|
| 1    | high urgency AND 10+ affected users | critical |
| 2    | high urgency OR 10+ affected users  | high     |
| 3    | medium urgency OR 3+ affected users | medium   |
| 4    | everything else                     | low      |

`priority` is **derived**, so it is never typed in by hand. A saved ticket
whose `priority` disagrees with its `urgency` and `affected_users` is
rejected on load rather than reported as if it were true.

**Validation rules:**
- Title must not be blank after trimming.
- Category must be one of the four values above (case and spacing are
  normalised, so `" network "` is stored as `"Network"`).
- Urgency must be low, medium or high.
- `affected_users` must be a strictly positive whole number. Floats,
  strings, negatives, zero and booleans are rejected — `True` is rejected
  explicitly because Python counts it as the integer 1.
- `assigned_to` is either `None` or a non-blank label.

**Status workflow:** `open → in_progress → resolved`
- An unassigned ticket cannot move to `in_progress`.
- A resolved ticket can only be modified after an explicit reopen (back to `open`).
- Every refusal leaves the ticket completely unchanged. Validation always
  runs before anything is written.

**Open Work Queue:** shows **open tickets only**, ordered
critical > high > medium > low, with earlier numeric IDs first for ties
(`T002` before `T010`). An `in_progress` or `resolved` ticket does not appear
in it. Tickets that are `open` *or* `in_progress` are still counted as
"unresolved" in the reports.

### Follow-up notes

Each ticket carries a `notes` list. A note is:

```json
{"note_id": "N001", "author": "Mentor A", "message": "Rebooted the AP."}
```

- Notes can only be added while a ticket is `open` or `in_progress`. A
  resolved ticket refuses new notes until it is reopened — this is the same
  rule as assignment.
- The author label must not be blank.
- The message must be 5–300 characters after trimming.
- A rejected note does **not** consume a note ID. IDs are derived from the
  notes that exist, so the sequence never has holes and never repeats.
- Notes are preserved through resolve and reopen.
- Note IDs are unique **within a ticket**. A note is identified by its ticket
  ID plus its note ID, so `T001/N001` and `T002/N001` are different notes.

## Search and filters (option 7)

Search is **read-only**: it returns matching tickets and never adds, edits or
reorders anything.

- The **title search** is a case-insensitive **substring** match, so `WI-FI`
  finds `Wi-Fi down in Lab 3`. Punctuation is still significant, so `wifi`
  does **not** match `Wi-Fi`.
- **Category, status and priority** are optional filters. Leaving one blank
  means "do not filter by this field".
- Supplied filters **combine with AND** — a ticket must satisfy every filter
  you set, not just one. So `wifi` + `Network` + `open` returns only open
  Network tickets whose title matches.
- Results are ordered by **priority** (critical → low) and then by **numeric
  ticket ID**, so `T2` comes before `T10`.
- An invalid filter option re-prompts instead of failing.

## Follow-up notes (options 8 and 9)

Each ticket carries a `notes` list. A note is:

```json
{"note_id": "N001", "author": "Mentor A", "message": "Rebooted the AP."}
```

- Notes are identified by **ticket ID plus note ID**, so `N001` may exist on
  more than one ticket.
- Notes can only be added while a ticket is `open` or `in_progress`. A
  resolved ticket refuses new notes until it is reopened — the same rule as
  assignment.
- The author label must not be blank.
- The message must be 5–300 characters after trimming.
- A rejected note **does not consume a note ID**: the next ID is always the
  highest existing ID plus one.
- Notes are preserved through resolve and reopen, and option 9 lists them in
  note ID order.

## Reports (option 6)

Reports show the total, the counts by status, priority and category, the
**unresolved** count (open + in_progress), the **resolved** count, and the
**resolution rate** (`resolved / total * 100`). An empty dataset reports
`0.0%` rather than raising a division error, and a reopened ticket is counted
by its current status, so no ticket is counted twice.

## Where tickets are saved

Tickets are stored in `data/tickets.json` (created automatically, not tracked
by Git).
To start fresh, delete that file: `rm -f data/tickets.json`.

### File format

The file is a plain JSON **list** of ticket objects — the same envelope the
original CampusFlow used, so pre-existing files load with no conversion step.

```json
[
  {
    "id": "T001",
    "title": "Wi-Fi down in Block C",
    "category": "Network",
    "urgency": "high",
    "affected_users": 15,
    "priority": "critical",
    "status": "open",
    "assigned_to": null,
    "notes": [
      {"note_id": "N001", "author": "Mentor A", "message": "Rebooted the AP."}
    ]
  }
]
```

### Validation on load

Loading validates the **whole collection before handing anything back**. If
any single record is unacceptable, the load is rejected with a clear message
and the current in-memory tickets are left untouched — there is no partial
load. The file on disk is never rewritten or deleted by a failed load, so a
human can repair it.

Rejected on load:

| Problem | Example |
|---------|---------|
| Not valid JSON | truncated file |
| Wrong top-level type | `{...}` instead of `[...]` |
| Missing required field | a ticket with no `urgency` |
| Duplicate ticket ID | two `T001` records |
| Illegal value | `"status": "banana"`, `"category": "Plumbing"` |
| Contradictory record | `urgency: low`, `affected_users: 1`, `priority: critical` |
| `in_progress` with no assignee | breaks the workflow invariant |
| Malformed note | missing `message`, or a message under 5 characters |
| Duplicate note ID in one ticket | two `N001` notes on `T001` |

### Migration and version support

`notes` was added in CampusFlow Next. A file written by the original version
has no `notes` key. Rather than reject those files — which would effectively
throw away every existing ticket — each such ticket is upgraded to
`"notes": []` as it loads. Every other field remains required, so a file that
is genuinely damaged is still refused.

There is no version number in the file and no migration script to run: old
files are read directly, and the first save writes them back in the new shape.
Files written by CampusFlow Next are not readable by the original version,
which did not know about `notes`; keep a copy if you need to go back.

### ID continuity across a restart

Both ID sequences are derived from the highest number that actually exists,
never from a counter or from `len(tickets)`:

- next ticket ID = highest ticket number + 1
- next note ID = highest note number on **that ticket** + 1

So after closing and reopening the app, a new ticket cannot reuse an ID that
is already in the file, and a new note cannot reuse a note ID on its ticket.

### File format

The file is a JSON **list** of ticket objects:

```json
[
  {
    "id": "T001",
    "title": "Wi-Fi down in Lab 3",
    "category": "Network",
    "urgency": "high",
    "affected_users": 15,
    "priority": "critical",
    "status": "open",
    "assigned_to": null,
    "notes": [
      {"note_id": "N001", "author": "Mentor A", "message": "Rebooted the AP."}
    ]
  }
]
```

The whole file is validated before it replaces anything in memory. A file is
**rejected — leaving current data untouched —** if it is not valid JSON, is
not a list, has a missing required field, repeats a ticket ID, uses an
unknown category/urgency/priority/status, stores a `priority` that disagrees
with the priority rule, marks a ticket `in_progress` without an assignee, or
contains a malformed or duplicated note.

`notes` was added in CampusFlow Next. A file written by the original version
has no `notes` key; those tickets load fine and are simply given `[]`, so
older files are not discarded.

## Project structure
```
campusflow/
├── README.md
├── .gitignore
├── main.py                  # CLI only: collects input, calls the package, prints
├── campusflow/
│   ├── __init__.py
│   ├── validation.py        # every validation rule, in one place
│   ├── tickets.py           # create a ticket, next ticket ID
│   ├── workflow.py          # assignment, status transitions, work queue
│   ├── notes.py             # add/read follow-up notes
│   ├── search.py            # read-only search and combined filters
│   ├── reports.py           # counts, unresolved/resolved, resolution rate
│   ├── storage.py           # validated JSON load and atomic save
│   └── understanding_check.py  # the six-question bank and its scoring
├── tests/
│   ├── test_tickets.py         # original regression tests
│   ├── test_workflow.py
│   ├── test_validation.py
│   ├── test_storage.py
│   ├── test_notes.py
│   ├── test_search.py
│   ├── test_reports.py
│   ├── test_understanding.py
│   ├── test_cli.py
│   └── test_bughunter_notes.py
├── docs/
│   ├── baseline-check.md
│   ├── design-decisions.md
│   └── ai-learning-log.md
└── data/
    └── tickets.json  # created at runtime, not tracked by Git
```

## Running the tests

```bash
python3 -m unittest discover -s tests -v
```

Run this from the repository root: `campusflow` is imported as a package, so
running it from elsewhere fails with `ModuleNotFoundError`.

The CLI tests never read the keyboard and never touch `data/tickets.json`.
Every handler takes an injectable `input_fn` / `output_fn`, so a test drives
"choose option 8, then type a bad ticket ID" with a scripted list of replies
and asserts on the messages that came back.

## Documentation

- [Baseline check](docs/baseline-check.md)
- [Design decisions](docs/design-decisions.md)
- [AI learning log](docs/ai-learning-log.md)

## Pull requests
| Author     | PR link                                  | Reviewer   | Status                                                 |
|------------|------------------------------------------|------------|--------------------------------------------------------|
| Engineer B | 742e5e7080dcfb972c91c97d0478be923998ae4b | Engineer A | 2b587cd0146fbe9a1872c17043e754e7aa377328 / 11-OCT-2026 |
| Engineer B | 6e7ae509579d822e40c3047d132cf6cf05c1caa9 | Engineer A | ccbad632011e4cb8947ec834ee1279e19b8bcfab / 11-OCT-2026 |
| Engineer B | 5fdd201efb26b5fab9e8c488e25083fd3b783000 | Engineer A | 4fe5134c4ad1be4a940c0356eb851ff5925cb2a9 / 11-OCT-2026 |
| Engineer B | 15105bf3229d97dd0ccbe1c4b2031d1cd54f0fa9 | Engineer A | 7529a9dba6e38d36bb02c8563168c102e9fc5a21 / 11-OCT-2026 |
| Engineer A | 6e958bb699792e64e5c281cb04c45355fe88a7cb | Engineer B | 15105bf3229d97dd0ccbe1c4b2031d1cd54f0fa9 / 09-OCT-2026 |
| Engineer A | 2b587cd0146fbe9a1872c17043e754e7aa377328 | Engineer B | bcfa3e740dec7224b65b2fff826040749ac9c073 / 09-OCT-2026 |
| Engineer A | 6c37b78913d09cfd2de6d5e4e9f5c2ed1ec492f2 | Engineer B | b0c0e4a297d6024ff137c8b8520af76122766094 / 09-OCT-2026 |
| Engineer A | 4fe5134c4ad1be4a940c0356eb851ff5925cb2a9 | Engineer B | 9b889fe9467841d022e56bf9aa6e868247132322 / 11-OCT-2026 |
| Engineer A | ccbad632011e4cb8947ec834ee1279e19b8bcfab | Engineer B | c86a2d95677c9b88d98679fa61319d4255d33729 / 11-OCT-2026 |
| Engineer A | 98f388e1c567bb11c2a454fd86d1f335a4b096c6 | Engineer B | 779b20c177f527e8772e0e25e48b934e9415129f / 11-OCT-2026 |


## Known limitations
- No way to delete a ticket
- Single user only, no concurrent access
- Search is substring matching only: there is no fuzzy matching or spelling
  correction, and punctuation must match exactly.

## Future improvements
- **Delete or archive tickets:** currently tickets cannot be removed. This
  would also require a separate ID counter, so an ID is never reused.

- **Filter by assignee:** search currently filters by title, category, status
  and priority. Filtering by `assigned_to` would be a small addition to
  `search_tickets`.

- **Harden `notes_for`:** it assumes every note in memory has a canonical
  `note_id`. A malformed note raises `KeyError` rather than
  `ValidationError`, which the CLI does not catch. This is recorded as a
  bug-hunter finding in `tests/test_bughunter_notes.py`.
