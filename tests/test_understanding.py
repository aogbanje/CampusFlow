"""Tests for the Engineering Understanding Check (Engineer B).

Acceptance case covered:
  14 - the CLI understanding check rejects an invalid answer and scores
       correctly

The whole file runs without a terminal: input and output are injected, so the
retry loop can be driven with a scripted list of keystrokes.
"""

import unittest

from campusflow.understanding_check import (
    QUESTION_BANK,
    REQUIRED_EXPLANATIONS,
    VALID_CHOICES,
    run_check,
    score_answers,
    validate_choice,
)


class ScriptedInput:
    """Stands in for input(): returns the next scripted reply.

    Records the prompts so a test can assert the retry actually asked again.
    Raises if the code under test asks more questions than the script
    provides, which turns an accidental infinite loop into a clear failure.
    """

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, prompt=""):
        self.prompts.append(prompt)
        if not self.replies:
            raise AssertionError(
                f"Code asked for more input than scripted. Prompt: {prompt!r}"
            )
        return self.replies.pop(0)


class OutputCollector:
    """Stands in for print(), keeping every line for assertions."""

    def __init__(self):
        self.lines = []

    def __call__(self, *parts, **kwargs):
        self.lines.append(" ".join(str(part) for part in parts))

    @property
    def text(self):
        return "\n".join(self.lines)


# The six answers the specification says are correct, in order.
SPEC_ANSWERS = ["B", "C", "B", "C", "C", "B"]


class TestQuestionBank(unittest.TestCase):
    def test_bank_has_six_scenarios(self):
        self.assertEqual(len(QUESTION_BANK), 6)

    def test_every_question_offers_exactly_four_choices(self):
        for index, question in enumerate(QUESTION_BANK, start=1):
            with self.subTest(question=index):
                self.assertEqual(set(question["options"]), set(VALID_CHOICES))

    def test_every_correct_answer_is_a_real_choice(self):
        for index, question in enumerate(QUESTION_BANK, start=1):
            with self.subTest(question=index):
                self.assertIn(question["answer"], VALID_CHOICES)
                self.assertIn(question["answer"], question["options"])

    def test_every_question_explains_its_answer(self):
        for index, question in enumerate(QUESTION_BANK, start=1):
            with self.subTest(question=index):
                self.assertTrue(question["explanation"].strip())

    def test_bank_matches_the_specified_answer_key(self):
        """A silently edited answer key would change every score, so the
        six correct letters are pinned here."""
        self.assertEqual([q["answer"] for q in QUESTION_BANK], SPEC_ANSWERS)


class TestValidateChoice(unittest.TestCase):
    def test_accepts_each_valid_letter(self):
        for letter in VALID_CHOICES:
            with self.subTest(letter=letter):
                self.assertEqual(validate_choice(letter), letter)

    def test_normalises_case_and_whitespace(self):
        self.assertEqual(validate_choice("  b  "), "B")

    def test_rejects_letters_outside_the_range(self):
        for bad in ("E", "F", "Z"):
            with self.subTest(bad=bad):
                self.assertIsNone(validate_choice(bad))

    def test_rejects_numbers_and_free_text(self):
        for bad in ("1", "0", "A1", "yes", "", "   "):
            with self.subTest(bad=bad):
                self.assertIsNone(validate_choice(bad))

    def test_rejects_none(self):
        self.assertIsNone(validate_choice(None))


class TestScoring(unittest.TestCase):
    def test_all_correct_scores_six(self):
        result = score_answers(QUESTION_BANK, SPEC_ANSWERS)
        self.assertEqual(result["score"], 6)
        self.assertEqual(result["total"], 6)

    def test_all_wrong_scores_zero(self):
        wrong = ["A" if answer != "A" else "B" for answer in SPEC_ANSWERS]
        self.assertEqual(score_answers(QUESTION_BANK, wrong)["score"], 0)

    def test_one_point_per_correct_answer(self):
        answers = list(SPEC_ANSWERS)
        answers[0] = "A"  # break Q1
        answers[3] = "A"  # break Q4
        result = score_answers(QUESTION_BANK, answers)
        self.assertEqual(result["score"], 4)

    def test_results_record_each_question(self):
        result = score_answers(QUESTION_BANK, SPEC_ANSWERS)
        self.assertEqual(len(result["results"]), 6)
        self.assertTrue(all(r["is_correct"] for r in result["results"]))
        self.assertEqual(result["results"][0]["given"], "B")
        self.assertEqual(result["results"][0]["correct"], "B")

    def test_a_missing_answer_scores_zero_rather_than_crashing(self):
        result = score_answers(QUESTION_BANK, ["B", "C"])
        self.assertEqual(result["score"], 2)
        self.assertEqual(result["total"], 6)
        self.assertIsNone(result["results"][5]["given"])

    def test_no_answers_at_all(self):
        self.assertEqual(score_answers(QUESTION_BANK, [])["score"], 0)

    def test_scoring_reads_only_the_answer_key(self):
        """The bank is a parameter, so scoring can be exercised on a bank the
        real questions never see. This is what proves the bank is data and
        the scoring is code."""
        fake_bank = (
            {"prompt": "x", "options": {}, "answer": "D"},
            {"prompt": "y", "options": {}, "answer": "A"},
        )
        result = score_answers(fake_bank, ["D", "A"])
        self.assertEqual(result["score"], 2)
        self.assertEqual(result["total"], 2)

    def test_question_wording_cannot_change_the_score(self):
        """Same key, completely different text -- the score must not move."""
        plain = ({"prompt": "does not matter", "options": {}, "answer": "B"},)
        noisy = ({"prompt": "A" * 500, "options": {}, "answer": "B"},)
        self.assertEqual(
            score_answers(plain, ["B"])["score"], score_answers(noisy, ["B"])["score"]
        )


class TestRunCheck(unittest.TestCase):
    def test_invalid_answers_are_rejected_and_re_prompted(self):
        """Case 14: a non A/B/C/D reply must not be accepted as an answer."""
        replies = ["Z", "b", "C", "B", "C", "C", "B"]  # stray Z before Q1
        replies += ["1", "It is refused.", "2", "Because zero tickets."]

        scripted = ScriptedInput(replies)
        output = OutputCollector()

        summary = run_check(input_fn=scripted, output_fn=output)

        self.assertEqual(summary["score"], 6)
        self.assertIn("Please enter A, B, C or D.", output.text)
        # Seven prompts for six questions proves it asked twice for Q1.
        answer_prompts = [p for p in scripted.prompts if "A/B/C/D" in p]
        self.assertEqual(len(answer_prompts), 7)

    def test_score_is_reported_in_the_final_summary(self):
        replies = list(SPEC_ANSWERS) + ["1", "Because.", "2", "Because."]
        output = OutputCollector()
        run_check(input_fn=ScriptedInput(replies), output_fn=output)
        self.assertIn("Score: 6/6", output.text)

    def test_a_wrong_answer_is_reported_with_the_correct_one(self):
        replies = ["A", "C", "B", "C", "C", "B"] + ["1", "Guess.", "2", "Guess."]
        output = OutputCollector()
        run_check(input_fn=ScriptedInput(replies), output_fn=output)
        self.assertIn("Score: 5/6", output.text)
        self.assertIn("wrong (answer B)", output.text)

    def test_explanations_are_recorded(self):
        replies = list(SPEC_ANSWERS) + ["3", "Filters narrow together.", "5", "State safety."]
        summary = run_check(
            input_fn=ScriptedInput(replies), output_fn=OutputCollector()
        )

        self.assertEqual(len(summary["explanations"]), REQUIRED_EXPLANATIONS)
        self.assertEqual(summary["explanations"][0]["number"], 3)
        self.assertIn("Filters narrow", summary["explanations"][0]["message"])

    def test_explanations_never_change_the_score(self):
        """Explanations are for the mentor to read, not for the machine to
        grade -- keyword matching is explicitly not used."""
        long_replies = list(SPEC_ANSWERS) + ["1", "A" * 100, "2", "B" * 100]
        short_replies = list(SPEC_ANSWERS) + ["1", "x", "2", "y"]

        long_score = run_check(
            input_fn=ScriptedInput(long_replies), output_fn=OutputCollector()
        )["score"]
        short_score = run_check(
            input_fn=ScriptedInput(short_replies), output_fn=OutputCollector()
        )["score"]

        self.assertEqual(long_score, short_score)

    def test_an_empty_explanation_is_not_recorded(self):
        replies = list(SPEC_ANSWERS) + ["1", "   ", "1", "Real reason.", "2", "Other."]
        summary = run_check(
            input_fn=ScriptedInput(replies), output_fn=OutputCollector()
        )
        self.assertEqual(len(summary["explanations"]), REQUIRED_EXPLANATIONS)
        self.assertEqual(summary["explanations"][0]["message"], "Real reason.")

    def test_an_out_of_range_question_number_is_rejected(self):
        replies = list(SPEC_ANSWERS) + ["99", "0", "abc", "1", "Fine.", "2", "Fine."]
        summary = run_check(
            input_fn=ScriptedInput(replies), output_fn=OutputCollector()
        )
        self.assertEqual(summary["explanations"][0]["number"], 1)

    def test_repeating_a_question_number_is_rejected(self):
        replies = list(SPEC_ANSWERS) + ["1", "First.", "1", "Again.", "2", "Second."]
        summary = run_check(
            input_fn=ScriptedInput(replies), output_fn=OutputCollector()
        )
        numbers = [entry["number"] for entry in summary["explanations"]]
        self.assertEqual(numbers, [1, 2])

    def test_run_check_exercises_every_question(self):
        replies = list(SPEC_ANSWERS) + ["1", "x", "2", "y"]
        output = OutputCollector()
        run_check(input_fn=ScriptedInput(replies), output_fn=output)

        for number in range(1, 7):
            with self.subTest(question=number):
                self.assertIn(f"Q{number}.", output.text)


if __name__ == "__main__":
    unittest.main()
