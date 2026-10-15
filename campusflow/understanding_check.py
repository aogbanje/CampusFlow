"""The Engineering Understanding Check (Requirement 05, Engineer B).

Six multiple-choice scenarios about how CampusFlow Next behaves. The point is
not to quiz the user on Python trivia -- every question is about a decision
this application actually makes, so a wrong answer points at a rule worth
re-reading.

Design rule that matters most
-----------------------------
The question bank is DATA and the scoring is CODE, and they do not know about
each other:

* :data:`QUESTION_BANK` is a plain tuple of dicts. Nothing in it can change a
  score.
* :func:`score_answers` takes the questions as an ARGUMENT, so it can be run
  against a two-question fake bank in a test without touching the real one,
  and it never reads a question's text to decide anything.
* :func:`run_check` only handles input/output, so scoring is testable without
  a terminal.

Explanations are asked for and shown, but never graded. A keyword match is
not evidence of understanding, so this module deliberately refuses to invent a
mark for free text -- the mentor reads them.
"""

#: The only accepted answers. Anything else re-prompts.
VALID_CHOICES = ("A", "B", "C", "D")

#: How many explanations the learner must give.
REQUIRED_EXPLANATIONS = 2

QUESTION_BANK = (
    {
        "prompt": (
            "Ticket T001 is open and unassigned. A user tries to move it to "
            "in_progress."
        ),
        "options": {
            "A": "Accept the change",
            "B": "Reject and preserve all data",
            "C": "Resolve it automatically",
            "D": "Remove the ticket",
        },
        "answer": "B",
        "explanation": (
            "An open ticket must be assigned before it can move to "
            "in_progress. can_transition refuses the change and change_status "
            "raises before writing anything, so the ticket is untouched."
        ),
    },
    {
        "prompt": "The application has zero tickets. What should the resolution percentage display?",
        "options": {
            "A": "Crash",
            "B": "100%",
            "C": "0%",
            "D": "Divide by one without explanation",
        },
        "answer": "C",
        "explanation": (
            "build_report checks for an empty collection before dividing, so "
            "there is no ZeroDivisionError. There is nothing resolved and "
            "nothing to resolve, so 0% is the honest answer."
        ),
    },
    {
        "prompt": (
            "Filter title='wifi', category='Network', status='open'. Which "
            "records should match?"
        ),
        "options": {
            "A": "Any record matching one filter",
            "B": "Only records matching all supplied filters",
            "C": "All network records",
            "D": "All open records",
        },
        "answer": "B",
        "explanation": (
            "Filters combine with AND. Each supplied filter narrows the "
            "result, so a ticket must be an open Network ticket whose title "
            "contains 'wifi'."
        ),
    },
    {
        "prompt": "A resolved ticket receives 'Add note'. What should happen?",
        "options": {
            "A": "Append the note anyway",
            "B": "Delete the old notes",
            "C": "Reject until the ticket is reopened",
            "D": "Change the status silently",
        },
        "answer": "C",
        "explanation": (
            "A resolved ticket refuses new notes -- and assignment changes -- "
            "until it is reopened through the normal workflow. The existing "
            "notes are kept either way."
        ),
    },
    {
        "prompt": "The JSON file contains two tickets with the same ID. What should load do?",
        "options": {
            "A": "Keep both tickets",
            "B": "Replace memory with the duplicates",
            "C": "Reject the load without changing current memory",
            "D": "Rename the IDs silently",
        },
        "answer": "C",
        "explanation": (
            "The whole file is validated before memory is replaced. A "
            "duplicate ID fails validation, so the load is refused and the "
            "working collection survives intact."
        ),
    },
    {
        "prompt": "A pull request changes validation but has no negative-case tests. Best review action?",
        "options": {
            "A": "Approve because it runs",
            "B": "Request focused tests and reasoning",
            "C": "Merge immediately",
            "D": "Ask an AI to approve it",
        },
        "answer": "B",
        "explanation": (
            "Working code is not evidence that invalid input is handled. A "
            "reviewer asks for the failing-input tests and the reasoning "
            "behind the rule being changed."
        ),
    },
)


def validate_choice(raw, choices=VALID_CHOICES):
    """Return the normalised answer letter, or ``None`` when it is invalid.

    Returning ``None`` rather than raising keeps the retry loop in
    :func:`run_check` simple, and makes the rule directly testable.
    """
    if not isinstance(raw, str):
        return None
    cleaned = raw.strip().upper()
    return cleaned if cleaned in choices else None


def score_answers(questions, answers):
    """Score `answers` (a list of letters) against `questions`.

    Parameters
    ----------
    questions : sequence of dict
        Anything with ``"answer"`` keys -- normally :data:`QUESTION_BANK`,
        but a test can pass its own two-question bank.
    answers : sequence of str or None
        The letter submitted for each question, in order. A missing or
        ``None`` entry counts as unanswered and scores zero.

    Returns
    -------
    dict
        ``{"score": int, "total": int, "results": [...]}`` where each result
        records the question number, what was given, the correct answer and
        whether it was right. Nothing here reads the question text or the
        option wording.
    """
    results = []
    score = 0

    for index, question in enumerate(questions):
        given = answers[index] if index < len(answers) else None
        correct = question["answer"]
        is_correct = given == correct
        if is_correct:
            score += 1
        results.append(
            {
                "number": index + 1,
                "given": given,
                "correct": correct,
                "is_correct": is_correct,
            }
        )

    return {"score": score, "total": len(questions), "results": results}


def ask_question(question, number, input_fn, output_fn):
    """Show one question and return the learner's first valid answer.

    Invalid input re-prompts instead of being accepted or crashing. The
    score reflects this returned value, not any feedback shown afterwards.
    """
    output_fn(f"\nQ{number}. {question['prompt']}")
    for letter in VALID_CHOICES:
        output_fn(f"  {letter}. {question['options'][letter]}")

    while True:
        answer = validate_choice(input_fn("Your answer (A/B/C/D): "))
        if answer is not None:
            return answer
        output_fn("Please enter A, B, C or D.")


def run_check(input_fn=input, output_fn=print, question_bank=QUESTION_BANK):
    """Run the whole check interactively and return a summary dict.

    Parameters
    ----------
    input_fn, output_fn
        Injected so tests (and the CLI) can drive this without a real
        terminal -- the same convention the rest of ``main.py`` uses.
    question_bank
        Defaults to :data:`QUESTION_BANK`.

    Returns
    -------
    dict
        ``score``, ``total``, ``results`` (from :func:`score_answers`) plus
        ``explanations``, a list of ``{"number", "message"}`` dicts.
    """
    output_fn("\n=== Engineering Understanding Check ===")
    output_fn("Six scenarios. Answer A, B, C or D. One point each.")

    answers = [
        ask_question(question, index + 1, input_fn, output_fn)
        for index, question in enumerate(question_bank)
    ]

    summary = score_answers(question_bank, answers)

    output_fn(f"\nScore: {summary['score']}/{summary['total']}")
    for result in summary["results"]:
        mark = "correct" if result["is_correct"] else f"wrong (answer {result['correct']})"
        given = result["given"] or "no answer"
        output_fn(f"  Q{result['number']}: {given} - {mark}")

    summary["explanations"] = _collect_explanations(
        len(question_bank), input_fn, output_fn
    )
    return summary


def _collect_explanations(question_count, input_fn, output_fn):
    """Ask for an explanation of at least ``REQUIRED_EXPLANATIONS`` answers.

    These are recorded for mentor discussion and are NEVER auto-graded: the
    function does not look at the words the learner types.
    """
    output_fn(
        f"\nNow explain at least {REQUIRED_EXPLANATIONS} of your answers in "
        "your own words. Your mentor reads these; they are not auto-marked."
    )

    explanations = []
    while len(explanations) < REQUIRED_EXPLANATIONS:
        number = _ask_question_number(question_count, explanations, input_fn, output_fn)
        message = input_fn(f"Why did you answer Q{number} that way? ").strip()
        if not message:
            output_fn("An empty explanation is not recorded. Try again.")
            continue
        explanations.append({"number": number, "message": message})

    output_fn("\nRecorded for mentor discussion:")
    for entry in explanations:
        output_fn(f"  Q{entry['number']}: {entry['message']}")

    return explanations


def _ask_question_number(question_count, explanations, input_fn, output_fn):
    """Ask which question to explain, rejecting duplicates and bad input."""
    already = {entry["number"] for entry in explanations}
    while True:
        raw = input_fn(f"Explain which question? (1-{question_count}): ").strip()
        if raw.isdigit():
            number = int(raw)
            if 1 <= number <= question_count:
                if number in already:
                    output_fn(f"You have already explained Q{number}.")
                    continue
                return number
        output_fn(f"Please enter a question number from 1 to {question_count}.")
