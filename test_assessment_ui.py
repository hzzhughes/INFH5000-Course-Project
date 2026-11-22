"""Check the response deadline and teacher handoff through the running Streamlit script."""
import time
import unittest
from pathlib import Path

try:
    from streamlit.testing.v1 import AppTest
except ModuleNotFoundError:
    AppTest = None


@unittest.skipIf(AppTest is None, "Install requirements.txt to exercise the Streamlit UI")
class AssessmentInterfaceTests(unittest.TestCase):
    def test_deadline_locks_responses_but_teacher_can_correct_marks(self):
        app = AppTest.from_file(str(Path(__file__).with_name("app.py")), default_timeout=15).run()

        def widget(elements, label):
            return next(element for element in elements if element.label == label)

        def click(label):
            button = widget(app.button, label)
            self.assertFalse(button.disabled)
            button.click().run()
            self.assertFalse(app.exception)

        workspace = widget(app.radio, "Workspace")
        self.assertEqual(workspace.options, ["Reading assessment", "Create worksheet"])
        workspace.set_value("Create worksheet").run()
        click("Go to reading assessment")
        click("Start timed assessment")
        answer_label = "Transcribed oral response for N1.1"
        widget(app.text_area, answer_label).set_value("the boy").run()
        widget(app.radio, "Choice for N1.3").set_value("A").run()
        widget(app.checkbox, "Skip N1.2").check().run()
        app.session_state["reading_attempt"]["deadline"] = time.monotonic() - 1
        widget(app.text_area, answer_label).set_value("late change").run()

        click("Open teacher marking")
        self.assertTrue(widget(app.button, "Score assessment").disabled)
        widget(app.radio, "Points for N1.1").set_value(0).run()
        click("Score assessment")
        result = app.session_state["assessment_result"]
        self.assertEqual((result["points"], result["completed"], result["skipped"],
                          result["timed_out"]), (1, 2, 1, 37))
        self.assertEqual(result["passages"][0]["items"][0]["response"], "the boy")
        self.assertEqual([q["question_id"] for q in result["error_items"]], ["N1.1"])

        click("Create worksheet from this assessment")
        self.assertEqual(widget(app.text_area, "Support to use in the worksheet").value,
                         result["profile"]["support"])
        widget(app.checkbox, "I confirm this profile and lesson objective.").check().run()
        widget(app.radio, "Workspace").set_value("Reading assessment").run()
        click("Review marks again")
        self.assertNotIn("assessment_result", app.session_state)
        widget(app.radio, "Points for N1.1").set_value(1).run()
        click("Score assessment")
        result = app.session_state["assessment_result"]
        self.assertEqual((result["points"], result["error_items"]), (2, []))
        click("Create worksheet from this assessment")
        self.assertEqual(widget(app.text_area, "Support to use in the worksheet").value,
                         result["profile"]["support"])
        self.assertFalse(widget(app.checkbox, "I confirm this profile and lesson objective.").value)
