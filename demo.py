"""Reproduce the scored course demonstration and its illustrative worksheet."""
import re

from assessment import FORM_PASSAGES, load_questions, score_assessment
from workflow import load_corpus, render_markdown


DEMO_PASSAGE_ID = "N2"
DEMO_OBJECTIVE = "Retell three events from Ana’s story in the order they happened."


def demo_assessment():
    """Score a scripted attempt with two sequencing errors and one timeout."""
    bank = load_questions()
    form = [q for q in bank if q["passage_id"] in FORM_PASSAGES]
    timed_out = {"D5.14"}
    responses = {q["question_id"]: q["answer"] for q in form if q["question_id"] not in timed_out}
    marks = {q["question_id"]: 1 for q in form if q["mode"] != "choice" and q["question_id"] in responses}

    responses["N1.12"] = "Tim looks for the ball. The dog runs after a bird. The ball goes under the tree."
    responses["I3.11"] = "A cloud forms, the vapour rises, the drops fall and the rain reaches the ground."
    marks.update({"N1.12": 0, "I3.11": 0})
    return score_assessment(bank, responses, marks, timed_out=timed_out)


def demo_worksheet(passage):
    """Return the reference worksheet that models the sequencing lesson on N2."""
    if passage["id"] != DEMO_PASSAGE_ID:
        raise ValueError("The demo worksheet uses passage N2.")
    sentences = re.split(r"(?<=\.)\s+", passage["text"])
    return {
        "reading_blocks": [" ".join(group) for group in (sentences[:4], sentences[4:8], sentences[8:])],
        "support_activity": (
            "Make three cards. Write one of these sentences on each card.\n\n"
            "A. Ana puts the shoes in the box.\n\n"
            "B. Ana looks at her bag.\n\n"
            "C. Ana finds the shoes under the seat.\n\n"
            "Find each event in the story. Move the cards into story order."
        ),
        "questions": [
            {"question": "What happens first, next and last? Use your cards to retell the story.",
             "answer": "B, C, A. Ana looks at her bag, finds the shoes under the seat and puts them in the box.",
             "evidence": "Ana looks at her bag. The shoes are not in the bag. The box is empty. She is sad. "
                         "Then she looks under the seat. The shoes are under the seat. Ana takes them out. "
                         "She puts them in the box."},
            {"question": "Which action comes just before Ana puts the shoes in the box?",
             "answer": "She takes the shoes out from under the seat.",
             "evidence": "The shoes are under the seat. Ana takes them out. She puts them in the box."},
        ],
        "teacher_note": "Listen for the order of all three events. If two are reversed, ask the learner "
                        "to point to the sentence for each card, move the cards and try the retelling again.",
    }


def build_demo():
    result = demo_assessment()
    passages = {p["id"]: p for p in load_corpus()}
    passage = passages[DEMO_PASSAGE_ID]
    sections = [
        "# From a reading assessment to a sequencing lesson",
        f"The scripted attempt earns **{result['points']}/{result['possible']} ({result['band']})**. "
        "Two oral answers put events in the wrong order. The follow-up lesson asks the learner to "
        "sequence events in a new story, *The Box on the Bus*.",
        "## How the attempt was scored",
        "This offline example uses the app’s question bank and scorer. "
        "The script uses appendix answers for the completed items, with the two exceptions shown below. "
        "Choices are scored from the key. The scripted teacher marks award one point to each completed "
        "oral or written answer except those two. The final item, D5.14, times out.",
    ]
    rows = ["| Passage | Points | Answered | Skipped | Timed out |",
            "| --- | ---: | ---: | ---: | ---: |"]
    for part in result["passages"]:
        pid = part["passage_id"]
        rows.append(f"| {pid} · {passages[pid]['title']} | {part['points']}/{part['possible']} "
                    f"| {part['completed']} | {part['skipped']} | {part['timed_out']} |")
    rows.append(f"| **Total** | **{result['points']}/{result['possible']}** | **{result['completed']}** "
                f"| **{result['skipped']}** | **{result['timed_out']}** |")
    sections.extend(["\n".join(rows), "## What the teacher can act on"])
    items = {item["question_id"]: item for part in result["passages"] for item in part["items"]}
    for error in result["error_items"]:
        item = items[error["question_id"]]
        sections.append(f"**{item['question_id']} · {passages[item['passage_id']]['title']}**\n\n"
                        f"- Recorded answer · “{item['response']}”\n"
                        f"- Appendix order · {item['answer']}.\n"
                        f"- Teacher mark · {item['points']}/1. The one-point criterion is “{item['rubric']}”.")
    sections.extend([
        f"The scoring rule pairs these two missed sequencing items. Its suggested support is "
        f"“{result['profile']['support']}” D5.14 has no response and is excluded from the practice targets.",
        "The teacher chooses N2, a reserve passage about Ana losing her shoes, so the learner can "
        "try the same skill with fresh material. The worksheet below is a prewritten example "
        "checked and exported with the app’s worksheet renderer. A live run asks the selected model "
        "to draft the worksheet from the missed-item criteria and the teacher’s instructions.",
    ])
    worksheet = render_markdown(demo_worksheet(passage), passage, DEMO_OBJECTIVE, teacher=True)
    sections.append("\n".join("#" + line if line.startswith("#") else line for line in worksheet.splitlines()))
    sections.extend([
        "## Reproduce this demo",
        "From the folder containing this file, run `python3 demo.py` to print the scored walkthrough. "
        "To record an attempt yourself, open **Reading assessment** in the app, complete the three passages "
        "under the shared 15-minute limit, and mark the oral and written responses. Then select "
        "**Create worksheet from this assessment**. [App setup](README.md)",
    ])
    return "\n\n".join(sections) + "\n"


if __name__ == "__main__":
    print(build_demo(), end="")
