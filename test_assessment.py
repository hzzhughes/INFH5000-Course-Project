"""Regression checks against the administered form and scoring table in Appendix B."""

from collections import Counter
import unittest
from unittest.mock import patch

from assessment import FORM_PASSAGES, load_questions, score_assessment
from workflow import check_profile


class AssessmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bank = load_questions()
        cls.form = [q for q in cls.bank if q["passage_id"] in FORM_PASSAGES]

    def setUp(self):
        self.responses = {q["question_id"]: q["answer"] for q in self.form}
        self.marks = {q["question_id"]: 1 for q in self.form if q["mode"] != "choice"}

    def score(self, *, skipped=(), timed_out=()):
        return score_assessment(self.bank, self.responses, self.marks,
                                skipped=skipped, timed_out=timed_out)

    def test_bank_and_form(self):
        self.assertEqual(len(self.bank), 200)
        self.assertEqual(len({q["question_id"] for q in self.bank}), 200)
        self.assertEqual(Counter(q["passage_id"] for q in self.form), {"N1": 13, "I3": 13, "D5": 14})
        self.assertTrue(all(all(q[field] for field in ("question", "answer", "rubric")) for q in self.bank))
        self.assertEqual([p["points"] for p in self.score()["passages"]], [13, 13, 14])

    def test_every_band_boundary(self):
        for total, band in [(0, "lack of mastery"), (19, "lack of mastery"),
                            (20, "significant difficulty"), (24, "significant difficulty"),
                            (25, "partial mastery"), (29, "partial mastery"),
                            (30, "basic proficiency"), (34, "basic proficiency"),
                            (35, "full mastery"), (40, "full mastery")]:
            with self.subTest(total=total):
                for index, q in enumerate(self.form):
                    item_id = q["question_id"]
                    if q["mode"] == "choice":
                        wrong = "B" if q["answer"] == "A" else "A"
                        self.responses[item_id] = q["answer"] if index < total else wrong
                    else:
                        self.marks[item_id] = int(index < total)
                result = self.score()
                self.assertEqual((result["points"], result["completed"], result["band"]), (total, 40, band))

    def test_human_marks_variants_and_automatic_choices(self):
        self.responses["N1.1"] = "That boy at the park."
        self.responses["N1.3"] = " b "
        self.marks["D5.14"] = 0
        result = self.score()
        self.assertEqual(result["points"], 38)
        self.assertIn("That boy at the park.", result["report"])
        self.assertIn("N1.3", result["summary"])
        self.assertEqual(check_profile(result["profile"], result["report"]), [])

    def test_later_item_updates_local_profile_and_error_item_specs(self):
        # These first successes and misses stay the same when the last mark changes.
        for item_id in ("N1.1", "N1.2", "N1.5", "N1.6", "D5.2"):
            self.marks[item_id] = 0
        for last_mark, total, dialogue, band in [(1, 35, 13, "full mastery"),
                                                 (0, 34, 12, "basic proficiency")]:
            with self.subTest(last_mark=last_mark):
                self.marks["D5.14"] = last_mark
                result = self.score()
                quotes = [row["quote"] for row in result["profile"]["observations"]]
                for quote in quotes:
                    self.assertIn(quote, result["report"])
                evidence = "\n".join(quotes)
                for phrase in (f"{total}/40 points", band, "Answered 40/40", "(N1): 9/13",
                               "(I3): 13/13", f"(D5): {dialogue}/14", "D5.2 (oral, 0/1)"):
                    self.assertIn(phrase, evidence)
                self.assertIn(f"9/13 on N1, 13/13 on I3, {dialogue}/14 on D5", result["summary"])
                errors = result["error_items"]
                self.assertEqual(len(errors), 40 - total)
                self.assertEqual(errors[-1]["question_id"], "D5.2" if last_mark else "D5.14")
                for item in errors:
                    self.assertEqual(set(item), {"question_id", "mode", "question", "rubric"})

    def test_skips_and_unfinished_attempts(self):
        self.responses.pop("N1.1")
        self.marks.pop("N1.1")
        with self.assertRaisesRegex(ValueError, r"N1\.1"):
            self.score()
        result = self.score(skipped=["N1.1"])
        self.assertEqual((result["points"], result["completed"], result["possible"]), (39, 39, 40))
        self.assertEqual(result["passages"][0]["completed"], 12)
        self.assertNotIn("N1.1 (oral, 0/1)", result["passages"][0]["feedback"])

        self.responses.clear()
        self.marks.clear()
        result = self.score(skipped=[q["question_id"] for q in self.form])
        self.assertEqual((result["points"], result["completed"]), (0, 0))
        self.assertEqual(result["profile"]["observations"], [])

    def test_timeout_is_unscored_and_separate_from_wrong_and_skipped(self):
        for item_id in ("N1.3", "D5.14"):
            self.responses.pop(item_id)
        self.marks.pop("D5.14")
        self.marks["I3.2"] = 0
        result = self.score(skipped=["N1.3"], timed_out=["D5.14"])
        self.assertEqual((result["points"], result["completed"], result["possible"]), (37, 38, 40))
        self.assertEqual([item["question_id"] for item in result["error_items"]], ["I3.2"])
        self.assertEqual((result["skipped"], result["timed_out"]), (1, 1))
        last = result["passages"][-1]
        self.assertEqual((last["timed_out"], last["skipped"], last["completed"]), (1, 0, 13))
        self.assertIn("Response: Time limit reached\n  Score: Unscored", result["report"])
        with self.assertRaisesRegex(ValueError, "both skipped and timed out"):
            self.score(skipped=["N1.3"], timed_out=["N1.3", "D5.14"])
        self.responses["D5.14"] = "written response"
        with self.assertRaisesRegex(ValueError, "timed out but has a response"):
            self.score(skipped=["N1.3"], timed_out=["D5.14"])

    def test_cross_passage_support_requires_two_answered_misses(self):
        self.marks.update({"N1.1": 0, "I3.12": 0, "D5.13": 0})
        result = self.score()
        passive = "Both I3.12 and D5.13 earned 0/1 for rewriting a sentence in the passive voice."
        self.assertIn(passive, result["summary"])
        self.assertIn("receiver of an action", result["profile"]["support"])
        self.assertIn(passive, [row["quote"] for row in result["profile"]["observations"]])
        self.assertNotIn("Start the review with N1.1", result["summary"])

        del self.responses["D5.13"], self.marks["D5.13"]
        for status in ("skipped", "timed_out"):
            with self.subTest(status=status):
                result = self.score(**{status: ["D5.13"]})
                self.assertNotIn(passive, result["summary"])
                self.assertNotIn("receiver of an action", result["profile"]["support"])

        self.marks.update({"N1.12": 0, "I3.11": 0})
        result = self.score(skipped=["D5.13"])
        self.assertIn("Both N1.12 and I3.11 earned 0/1", result["summary"])
        self.assertIn("arrange event cards", result["profile"]["support"])

    def test_invalid_inputs(self):
        for item, value in [("N1.3", "E"), ("N1.1", ""), ("D5.14", None)]:
            with self.subTest(item=item):
                with patch.dict(self.responses, {item: value}):
                    with self.assertRaisesRegex(ValueError, item):
                        self.score()
        for item, mark in [("N1.3", 1), ("D5.14", None), ("N1.1", 2), ("N1.1", 0.5)]:
            with self.subTest(mark=mark):
                with patch.dict(self.marks, {item: mark}):
                    with self.assertRaisesRegex(ValueError, item):
                        self.score()
        with self.assertRaisesRegex(ValueError, "skipped"):
            self.score(skipped=["N1.1"])
        with self.assertRaisesRegex(ValueError, "N2.1"):
            self.score(skipped=["N2.1"])


if __name__ == "__main__":
    unittest.main()
