"""Offline regression checks for appendix inputs, evidence checks, and exports."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from demo import build_demo
from workflow import (
    check_profile, check_worksheet, extract_profile, generate_worksheet,
    load_cases, load_corpus, render_markdown,
)


class WorksheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.passages = {item["id"]: item for item in load_corpus()}
        cls.cases = load_cases()
        cls.passage = cls.passages["N1"]
        cls.case = cls.cases[0]

    def test_appendix(self):
        self.assertEqual(set(self.passages), {f"{genre}{tier}" for genre in "NID" for tier in range(1, 6)})
        for identifier, item in self.passages.items():
            with self.subTest(identifier=identifier):
                self.assertEqual(item["tier"], int(identifier[1:]))
                self.assertEqual(item["words"], len(item["text"].split()))
                self.assertEqual(item["file"], f"passages/{identifier}.txt")

    def test_both_examples_and_exports(self):
        for case in self.cases:
            with self.subTest(case=case["id"]):
                self.assertEqual(check_profile(case["profile"], case["report"]), [])
                self.assertEqual(check_worksheet(case["worksheet"], self.passage), [])
                args = case["worksheet"], self.passage, case["objective"]
                student = render_markdown(*args, teacher=False)
                teacher = render_markdown(*args)
                self.assertNotIn("### Answer key", student)
                self.assertNotIn(case["worksheet"]["teacher_note"], student)
                self.assertIn("### Answer key", teacher)
                for question in case["worksheet"]["questions"]:
                    self.assertIn(question["question"], student)
                    self.assertIn(question["evidence"], teacher)

    def test_no_documented_observation(self):
        client = Mock(return_value={"observations": []})
        empty = extract_profile("The library opened on Monday.", client)
        self.assertEqual(empty["observations"], [])
        self.assertTrue(check_profile(empty, "The library opened on Monday."))
        self.assertEqual(client.call_count, 1)

    def test_unquoted_observation_is_rejected(self):
        incorrect = copy.deepcopy(self.case["profile"])
        incorrect["observations"][0]["quote"] = "A sentence absent from the assessment."
        self.assertTrue(check_profile(incorrect, self.case["report"]))

    def test_chunking_repair(self):
        valid = self.case["worksheet"]
        changed = copy.deepcopy(valid)
        changed["reading_blocks"][0] = changed["reading_blocks"][0].replace("Tim", "Sam")
        self.assertTrue(check_worksheet(changed, self.passage, activity="chunk"))
        client = Mock(side_effect=[changed, valid])
        result = generate_worksheet(self.passage, self.case["profile"], self.case["objective"],
                                    client, activity="chunk")
        self.assertEqual(result, valid)
        self.assertEqual(client.call_count, 2)
        request = json.loads(client.call_args_list[0].args[1])
        self.assertEqual(request["activity_template"]["id"], "chunk")

    def test_unsourced_answer_gets_at_most_one_repair(self):
        broken = copy.deepcopy(self.case["worksheet"])
        broken["questions"][0]["evidence"] = "No such sentence appears in this passage."
        client = Mock(return_value=broken)
        with self.assertRaises(ValueError):
            generate_worksheet(self.passage, self.case["profile"], self.case["objective"], client)
        self.assertEqual(client.call_count, 2)

    def test_markdown_snapshot(self):
        saved_demo = Path(__file__).with_name("Worksheet_Demo.md").read_text(encoding="utf-8")
        self.assertEqual(build_demo(), saved_demo)


if __name__ == "__main__":
    unittest.main()
