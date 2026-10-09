# CampusFlow

CampusFlow is a Python command-line helpdesk ticket manager for Learn2Earn
campus staff. Informal support requests (Wi-Fi outages, faulty laptops, broken
dev environments) get lost, so CampusFlow records each problem, calculates its
priority, assigns responsibility, and tracks progress until it is resolved.

## Team

| Name                    |  Role      | Contribution summary                                                          |
|-------------------------|------------|-------------------------------------------------------------------------------|
| Ogbanje Abraham Okwute  | Engineer A | Ticket creation, input validation, priority engine, tests (`<fill in later>`) |
| Awo Wisdom              | Engineer B | Assignment, workflow, queue, reports, tests (`<fill in later>`)               |
Shared: JSON persistence, code reviews, documentation.


## Requirements and setup
- Python version: `<Python 3.12.3>` (check with `python --version`)
- No external packages needed (standard library only: `json`, `unittest`).

```bash
git clone <repository-url>
cd <repository-folder>
```

## Running the app

```bash
python3 main.py
```

Menu options:

| Option | Action                  |
|--------|-------------------------|
| 1      | `<Create ticket>`       |
| 2      | `<List / view tickets>` |
| 3      | `<Assign ticket>`       |
| 4      | `<Change status>`       |
| 5      | `<Work queue>`          |
| 6      | `<Reports>`             |
| 0      | `<Exit>`                |

## Running the tests

```bash
python3 -m unittest discover -s tests -v
```


## Ticket rules

**Fields:** id, title, category, urgency, affected_users, priority, status, assigned_to.

**Allowed values:** category: Network, Hardware, Software, Other. Urgency: low, medium, high.

**Priority** (first matching rule wins):

| Rule | Condition | Priority |
|---|---|---|
| 1 | high urgency AND 10+ affected users | critical |
| 2 | high urgency OR 10+ affected users | high |
| 3 | medium urgency OR 3+ affected users | medium |
| 4 | everything else | low |

**Status workflow:** `open → in_progress → resolved`
- An unassigned ticket cannot move to `in_progress`.
- A resolved ticket can only be modified after an explicit reopen (back to `open`).

## Where tickets are saved

Tickets are stored in `data/tickets.json` (created automatically, not tracked
by Git). To start fresh, delete that file: `<add exact command or steps>`.
If the file is malformed, the app shows an error instead of overwriting it.

## Project structure
```
campusflow/
├── README.md
├── .gitignore
├── main.py
├── campusflow/
│   ├── __init__.py
│   ├── tickets.py
│   ├── workflow.py
│   ├── storage.py
│   └── reports.py
├── tests/
│   ├── test_tickets.py
│   ├── test_workflow.py
│   └── test_storage.py
├── docs/
│   ├── design-decisions.md
│   └── ai-learning-log.md
└── data/
    └──tickets.json
```

## Documentation

- [Design decisions](docs/design-decisions.md)
- [AI learning log](docs/ai-learning-log.md)

## Pull requests

| Author | PR link | Reviewer | Status |
|---|---|---|---|
| Engineer A | `<PR URL>` | Engineer B | `<merged / date>` |
| Engineer B | `<PR URL>` | Engineer A | `<merged / date>` |

## Known limitations
- No way to delete a ticket
- Single user only, no concurrent access

## Future improvements

- `<idea 1>`
- `<idea 2>`