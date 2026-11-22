"""Administer and score the 40-item reading assessment in Appendix B."""

from __future__ import annotations

import csv
from pathlib import Path

FORM_PASSAGES = ("N1", "I3", "D5")
FORM_LENGTHS = (13, 13, 14)
PASSAGE_TYPES = {
    "N1": "Narrative text",
    "I3": "Informational text",
    "D5": "Narrative with dialogue",
}

# Appendix B awards a contested boundary to the higher band. Since items
# earn at most one point, each threshold also implies its minimum completions.
BANDS = (
    (35, "full mastery"),
    (30, "basic proficiency"),
    (25, "partial mastery"),
    (20, "significant difficulty"),
    (0, "lack of mastery"),
)

# Project feedback rule: these pairs ask for the same observable task in two
# passages. Suggest shared practice only when both answered items earned zero.
REPEATED_TASKS = (
    ("N1.12", "I3.11", "putting events or stages in order",
     "Have the learner arrange event cards in passage order, then retell the sequence using the cards."),
    ("I3.12", "D5.13", "rewriting a sentence in the passive voice",
     "Model moving the receiver of an action into subject position, then have the learner rewrite a new sentence using ‘by’ to name the agent."),
)


def load_questions() -> list[dict]:
    """Read the complete bank, including the twelve reserve passages."""
    path = Path(__file__).resolve().parent / "data" / "questions.csv"
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))


def _score_item(question, response, mark, skipped, timed_out):
    item_id = question["question_id"]
    mode = question["mode"]
    if response is None:
        response = ""
    if not isinstance(response, str):
        raise ValueError(f"{item_id} needs a text response.")
    response = response.strip()
    if skipped or timed_out:
        if response or mark is not None:
            reason = "skipped" if skipped else "timed out"
            raise ValueError(f"{item_id} is marked as {reason} but has a response or mark.")
        points = 0
    elif not response:
        raise ValueError(f"Enter a response for {item_id} or explicitly mark it as skipped.")
    elif mode == "choice":
        response = response.upper()
        if mark is not None:
            raise ValueError(f"{item_id} is scored from the selected choice.")
        if response not in ("A", "B", "C", "D"):
            raise ValueError(f"Select A, B, C or D for {item_id}.")
        points = int(response == question["answer"])
    elif mode in ("oral", "written"):
        if type(mark) is not int or mark not in (0, 1):
            raise ValueError(f"Use the rubric to award 0 or 1 point for {item_id}.")
        points = mark
    else:
        raise ValueError(f"Unknown response mode for {item_id}.")

    return {**question, "response": response, "skipped": skipped,
            "timed_out": timed_out, "points": points}


def _passage_report(passage_id, items):
    completed = [item for item in items if not item["skipped"] and not item["timed_out"]]
    skipped = sum(item["skipped"] for item in items)
    timed_out = sum(item["timed_out"] for item in items)
    points = sum(item["points"] for item in completed)
    possible = len(items)
    feedback = (
        f"{PASSAGE_TYPES[passage_id]} ({passage_id}): {points}/{possible} points, "
        f"{len(completed)} answered, {skipped} skipped, {timed_out} timed out."
    )
    observations = [{"finding": f"Passage result for {passage_id}", "quote": feedback}]
    # Include a representative scored criterion of each outcome. Student
    # wording is available to the teacher in the local item record.
    for point, finding in ((1, "Met"), (0, "Did not meet")):
        sample = next((item for item in completed if item["points"] == point), None)
        if sample:
            evidence = f"{sample['question_id']} ({sample['mode']}, {point}/1) criterion: {sample['rubric']}."
            feedback += f" {evidence}"
            observations.append({
                "finding": f"{finding} the criterion for the {sample['mode']} question “{sample['question']}”",
                "quote": evidence,
            })
    return {
        "passage_id": passage_id, "points": points, "possible": possible,
        "completed": len(completed), "skipped": skipped, "timed_out": timed_out,
        "feedback": feedback, "items": items,
        "observations": observations,
    }


def score_assessment(questions, responses, marks, *, skipped=(), timed_out=()) -> dict:
    """Score the fixed form. Unanswered items must be recorded as skipped or timed out.

    Responses are keyed by question ID. Choice responses use A–D; for each
    answered oral/written item the teacher supplies an integer 0 or 1.
    """
    form = {}
    for question in questions:
        if question["passage_id"] in FORM_PASSAGES:
            item_id = question["question_id"]
            if item_id in form:
                raise ValueError(f"Duplicate assessment item {item_id}.")
            form[item_id] = question

    expected_ids = [f"{pid}.{n}" for pid, count in zip(FORM_PASSAGES, FORM_LENGTHS)
                    for n in range(1, count + 1)]
    if set(form) != set(expected_ids) or any(
        form[item_id]["passage_id"] != item_id.split(".")[0] for item_id in form
    ):
        raise ValueError("The assessment requires 13 N1, 13 I3 and 14 D5 items in the bank.")
    skipped = set(skipped)
    timed_out = set(timed_out)
    if skipped & timed_out:
        raise ValueError("An item cannot be both skipped and timed out.")
    unexpected = (set(responses) | set(marks) | skipped | timed_out) - set(form)
    if unexpected:
        raise ValueError("Unexpected assessment item(s): " + ", ".join(sorted(unexpected)))

    groups = {pid: [] for pid in FORM_PASSAGES}
    for item_id in expected_ids:
        question = form[item_id]
        groups[question["passage_id"]].append(_score_item(
            question, responses.get(item_id), marks.get(item_id), item_id in skipped,
            item_id in timed_out,
        ))

    passages = [_passage_report(pid, items) for pid, items in groups.items()]
    points = sum(p["points"] for p in passages)
    possible = len(expected_ids)
    completed = sum(p["completed"] for p in passages)
    band = next(name for threshold, name in BANDS if points >= threshold)
    overall = (
        f"Appendix B score: {points}/{possible} points ({points / possible:.1%}), "
        f"{band}. Answered {completed}/{possible}, skipped {len(skipped)}, timed out {len(timed_out)}."
    )
    passage_scores = ", ".join(
        f"{p['points']}/{p['possible']} on {p['passage_id']}" for p in passages
    )
    summary = f"{overall} Passage scores were {passage_scores}."
    items = [item for group in groups.values() for item in group]
    error_items = [
        {field: item[field] for field in ("question_id", "mode", "question", "rubric")}
        for item in items if not item["skipped"] and not item["timed_out"] and item["points"] == 0
    ]
    observations = [{"finding": "Score and completion on the administered form", "quote": overall}]
    missed_ids = {item["question_id"] for item in error_items}
    practice = []
    for first, second, task, suggestion in REPEATED_TASKS:
        if {first, second} <= missed_ids:
            evidence = f"Both {first} and {second} earned 0/1 for {task}."
            summary += f" {evidence} {suggestion}"
            observations.append({"finding": f"Two missed items involved {task}.", "quote": evidence})
            practice.append(suggestion)
    if practice:
        support = " ".join(practice)
    elif error_items:
        first_miss = error_items[0]
        support = {
            "choice": "Ask the learner to point to the sentence that supports their choice before comparing options.",
            "oral": "Have the learner reread the relevant lines and rehearse an answer aloud with the teacher.",
            "written": "Model one written response together, then offer a sentence frame for the learner to complete.",
        }[first_miss["mode"]]
        summary += (
            f" Start the review with {first_miss['question_id']}, an answered {first_miss['mode']} "
            f"item that earned 0/1 against this criterion: {first_miss['rubric']}."
        )
    elif completed:
        support = "Invite the learner to explain an answer and point to the words that support it."
        example = next(item for item in items if item["points"])
        summary += (
            f" All answered items met their scoring criteria, including "
            f"{example['question_id']}: {example['rubric']}."
        )
    else:
        support = ""
        summary += " No learner responses were available to interpret."
    if (skipped or timed_out) and completed:
        summary += " Unanswered items earned no points and were excluded from the error items."

    lines = ["Reading assessment", summary]
    for passage in passages:
        lines.extend(["", passage["feedback"]])
        observations.extend(passage["observations"])
        for item in passage["items"]:
            score = f"{item['points']}/1"
            response = item["response"]
            if item["skipped"] or item["timed_out"]:
                response = "Skipped" if item["skipped"] else "Time limit reached"
                score = "Unscored"
            lines.append(
                f"{item['question_id']} ({item['mode']}) {item['question']}\n"
                f"  Response: {response}\n"
                f"  Score: {score}. Criterion: {item['rubric']}"
            )
    return {
        "points": points, "possible": possible, "completed": completed, "band": band,
        "skipped": len(skipped), "timed_out": len(timed_out), "error_items": error_items,
        "passages": passages, "summary": summary, "report": "\n".join(lines),
        "profile": {"observations": observations if completed else [], "support": support},
    }
