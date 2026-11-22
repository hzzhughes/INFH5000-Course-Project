"""Offline regression checks for appendix inputs, evidence checks, and exports."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from compare import paired_comparison
from demo import DEMO_OBJECTIVE, DEMO_PASSAGE_ID, build_demo, demo_assessment, demo_worksheet
from workflow import (
    check_profile, check_worksheet, generate_worksheet, load_corpus, render_markdown,
)


class WorksheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.passages = {item["id"]: item for item in load_corpus()}
        cls.passage = cls.passages[DEMO_PASSAGE_ID]
        cls.assessment = demo_assessment()
        cls.worksheet = demo_worksheet(cls.passage)

    def test_appendix(self):
        self.assertEqual(set(self.passages), {f"{genre}{tier}" for genre in "NID" for tier in range(1, 6)})
        for identifier, item in self.passages.items():
            with self.subTest(identifier=identifier):
                self.assertEqual(item["tier"], int(identifier[1:]))
                self.assertEqual(item["words"], len(item["text"].split()))
                self.assertTrue(item["target_skill"])

    def test_scored_demo_and_exports(self):
        result = self.assessment
        self.assertEqual(check_profile(result["profile"], result["report"]), [])
        self.assertEqual([item["question_id"] for item in result["error_items"]], ["N1.12", "I3.11"])
        self.assertEqual((result["points"], result["completed"], result["timed_out"]), (37, 39, 1))
        self.assertEqual(check_worksheet(self.worksheet, self.passage), [])
        args = self.worksheet, self.passage, DEMO_OBJECTIVE
        student = render_markdown(*args, teacher=False)
        teacher = render_markdown(*args)
        self.assertNotIn("### Answer key", student)
        self.assertNotIn(self.worksheet["teacher_note"], student)
        self.assertIn("### Answer key", teacher)
        for question in self.worksheet["questions"]:
            self.assertIn(question["question"], student)
            self.assertIn(question["evidence"], teacher)

    def test_unquoted_observation_is_rejected(self):
        incorrect = copy.deepcopy(self.assessment["profile"])
        incorrect["observations"][0]["quote"] = "A sentence absent from the assessment."
        self.assertTrue(check_profile(incorrect, self.assessment["report"]))

    def test_comparison_adds_only_the_scored_targets_and_support(self):
        client = Mock(return_value=self.worksheet)
        _, incomplete = paired_comparison(self.passage, self.assessment, client, "test", "offline")
        self.assertFalse(incomplete)
        general, informed = client.call_args_list
        self.assertEqual(general.args[0], informed.args[0])
        lesson = json.loads(general.args[1])
        self.assertEqual(set(lesson), {"passage", "lesson_objective"})
        self.assertEqual(json.loads(informed.args[1]), {
            **lesson, "error_items": self.assessment["error_items"],
            "teacher_support": self.assessment["profile"]["support"],
        })

    def test_chunking_repair(self):
        valid = self.worksheet
        changed = copy.deepcopy(valid)
        changed["reading_blocks"][0] = changed["reading_blocks"][0].replace("Ana", "Sam")
        self.assertTrue(check_worksheet(changed, self.passage, activity="chunk"))
        client = Mock(side_effect=[changed, valid])
        result = generate_worksheet(self.passage, self.assessment["profile"], DEMO_OBJECTIVE,
                                    client, activity="chunk", error_items=self.assessment["error_items"])
        self.assertEqual(result, valid)
        self.assertEqual(client.call_count, 2)
        request = json.loads(client.call_args_list[0].args[1])
        self.assertEqual(request["activity_template"]["id"], "chunk")

    def test_unsourced_answer_gets_at_most_one_repair(self):
        broken = copy.deepcopy(self.worksheet)
        broken["questions"][0]["evidence"] = "No such sentence appears in this passage."
        client = Mock(return_value=broken)
        with self.assertRaises(ValueError):
            generate_worksheet(self.passage, self.assessment["profile"], DEMO_OBJECTIVE, client,
                               error_items=self.assessment["error_items"])
        self.assertEqual(client.call_count, 2)

    def test_assessment_handoff_sends_only_instructional_information(self):
        from assessment import FORM_PASSAGES, load_questions, score_assessment

        bank = load_questions()
        form = [q for q in bank if q["passage_id"] in FORM_PASSAGES]
        responses = {q["question_id"]: q["answer"] for q in form}
        responses["N1.1"] = "Private transcription of an oral response"
        marks = {q["question_id"]: int(q["question_id"] != "N1.1")
                 for q in form if q["mode"] != "choice"}
        result = score_assessment(bank, responses, marks)
        items = result["error_items"]
        self.assertEqual([item["question_id"] for item in items], ["N1.1"])
        # Even if a caller passes complete item records, only the instructional fields travel.
        items = [dict(item, response=responses["N1.1"]) for item in items]
        client = Mock(return_value=self.worksheet)
        generate_worksheet(self.passage, result["profile"], DEMO_OBJECTIVE, client,
                           activity="profile", error_items=items,
                           teacher_requirements="Practise the words park and tree.")
        payload = json.loads(client.call_args.args[1])
        self.assertEqual(set(payload), {"passage", "lesson_objective", "teacher_support",
                                        "error_items", "teacher_requirements", "activity_template"})
        self.assertEqual(set(payload["error_items"][0]), {"question_id", "mode", "question", "rubric"})
        self.assertNotIn(responses["N1.1"], client.call_args.args[1])
        self.assertNotIn(result["band"], client.call_args.args[1])

        generate_worksheet(self.passage, result["profile"], DEMO_OBJECTIVE, client, error_items=[])
        payload = json.loads(client.call_args.args[1])
        self.assertEqual(payload["error_items"], [])
        self.assertNotIn("approved_profile", payload)

    def test_markdown_snapshot(self):
        saved_demo = Path(__file__).with_name("Worksheet_Demo.md").read_text(encoding="utf-8")
        self.assertEqual(build_demo(), saved_demo)


if __name__ == "__main__":
    unittest.main()
