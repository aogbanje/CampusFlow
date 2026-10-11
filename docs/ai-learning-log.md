CampusFlow — AI Learning Log
Fellow: Awo Wisdom
Role: Engineer B
Project: CampusFlow — CLI Helpdesk Ticket Manager
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