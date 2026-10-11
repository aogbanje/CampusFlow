# Project: CampusFlow — CLI Helpdesk Ticket Manager

CampusFlow is a Python command-line helpdesk ticket manager for Learn2Earn
campus staff. Informal support requests (Wi-Fi outages, faulty laptops, broken
dev environments) get lost, so CampusFlow records each problem, calculates its
priority, assigns responsibility, and tracks progress until it is resolved.

## Team

| Name                    |  Role      | Contribution summary                                                          |
|-------------------------|------------|-------------------------------------------------------------------------------|
| Ogbanje Abraham Okwute  | Engineer A | Ticket creation, input validation, priority engine, tests                     |
| Awo Wisdom              | Engineer B | Assignment, workflow, queue, reports, tests                                   |

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
| 1      | Create ticket           |
| 2      | List / view tickets     |
| 3      | Assign ticket           |
| 4      | Change status           |
| 5      | Work queue              |
| 6      | Reports                 |
| 0      | Exit                    |

## Running the tests

```bash
python3 -m unittest discover -s tests -v
```


## Ticket rules

**Fields:** id, title, category, urgency, affected_users, priority, status, assigned_to.

**Allowed values:** category: Network, Hardware, Software, Other. Urgency: low, medium, high.

**Priority** (first matching rule wins):

| Rule | Condition                           | Priority |
|------|-------------------------------------|----------|
| 1    | high urgency AND 10+ affected users | critical |
| 2    | high urgency OR 10+ affected users  | high     |
| 3    | medium urgency OR 3+ affected users | medium   |
| 4    | everything else                     | low      |

**Status workflow:** `open → in_progress → resolved`
- An unassigned ticket cannot move to `in_progress`.
- A resolved ticket can only be modified after an explicit reopen (back to `open`).

## Where tickets are saved

Tickets are stored in `data/tickets.json` (created automatically, not tracked
by Git). 
To start fresh, delete that file: `rm -f data/tickets.json`.
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
    └── tickets.json  # created at runtime, not tracked by Git
```

## Documentation

- [Design decisions](docs/design-decisions.md)
- [AI learning log](docs/ai-learning-log.md)

## Pull requests
| Author     | PR link    | Reviewer   | Status            |
|------------|------------|------------|-------------------|
| Engineer A | `<PR URL>` | Engineer B | `<merged / date>` |
| Engineer A | `<PR URL>` | Engineer A | `<merged / date>` |
| Engineer A | `<PR URL>` | Engineer B | `<merged / date>` |
| Engineer A | `<PR URL>` | Engineer A | `<merged / date>` |
| Engineer A | `<PR URL>` | Engineer B | `<merged / date>` |
| Engineer A | `<PR URL>` | Engineer A | `<merged / date>` |
| Engineer B | `<PR URL>` | Engineer B | `<merged / date>` |
| Engineer B | `<PR URL>` | Engineer A | `<merged / date>` |
| Engineer B | `<PR URL>` | Engineer B | `<merged / date>` |
| Engineer B | `<PR URL>` | Engineer A | `<merged / date>` |
| Engineer B | `<PR URL>` | Engineer B | `<merged / date>` |
| Engineer B | `<PR URL>` | Engineer A | `<merged / date>` |




## Known limitations
- No way to delete a ticket
- Single user only, no concurrent access

## Future improvements
-**Atomic saves:** write to a temporary file and then rename it, so a crash
  during a save can never leave a half-written `tickets.json`.

- **Delete or archive tickets:** currently tickets cannot be removed. This
  would also require a separate ID counter, so an ID is never reused.

- **Search and filters:** filter tickets by category, assignee or status
  instead of listing everything.