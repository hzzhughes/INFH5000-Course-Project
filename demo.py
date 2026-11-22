"""Print the complete worked example as Markdown, using only the standard library."""
from workflow import check_profile, check_worksheet, load_cases, load_corpus


def build_demo():
    passages = {p["id"]: p for p in load_corpus()}
    cases = load_cases()
    first = cases[0]
    passage = passages[first["passage_id"]]
    objective = first["objective"]
    questions = first["worksheet"]["questions"]

    parts = [
        "# One story, two reading supports",
        "**INFH5000 · Group 5 | Worked demonstration**",
        "Both learners read *The Red Ball* and answer the same three questions. "
        "One learner needs help keeping their place on the page. The other needs practice "
        "figuring out who a pronoun refers to. The fictional assessments and the two "
        "worksheets below are hand-authored examples included with the app. You can read "
        "this file on its own or open **Worked examples** in the app.",
        "## The shared lesson",
        f"**Source** · {passage['id']}, *{passage['title']}* · {passage['genre']} · "
        f"Tier {passage['tier']} · {passage['words']} words  \n"
        f"**Appendix target** · {passage['target_skill']}  \n"
        f"**Lesson objective** · {objective}",
        passage["text"],
    ]
    for number, case in enumerate(cases, 1):
        worksheet = case["worksheet"]
        if (case["passage_id"] != passage["id"] or case["objective"] != objective
                or worksheet["questions"] != questions):
            raise ValueError("The paired demo requires one passage, objective and question set.")
        issues = check_profile(case["profile"], case["report"]) + check_worksheet(worksheet, passage)
        if issues:
            raise ValueError(" ".join(issues))
        parts.extend([
            f"## Learner {number} · {case['label']}",
            "### Assessment excerpt",
            "> " + case["report"],
            "### Teacher’s choice",
            case["profile"]["support"],
            "### Learner worksheet",
            *worksheet["reading_blocks"],
            f"**Practice** · {worksheet['support_activity']}",
        ])
    parts.extend(["## Questions for both learners",
                  "\n".join(f"{i}. {item['question']}" for i, item in enumerate(questions, 1)),
                  "## Teacher key"])
    for i, item in enumerate(questions, 1):
        parts.append(f"{i}. **{item['answer']}**  \n   Source sentence(s) · “{item['evidence']}”")
    parts.extend([
        "## What to show in the presentation",
        "1. Read the two assessment excerpts. Ask which observation justifies each support.\n"
        "2. Compare the opening. Learner 1 sees the original wording in two-sentence blocks. "
        "Learner 2 sees “Tim takes the ball to the park,” then practices resolving “He” later.\n"
        "3. Open the answer key. Both versions ask for the same details and use the same "
        "source quotations. A teacher can check whether the assigned support helps the "
        "learner reach that shared objective.",
        "**To try a new case** · Open **Create worksheet**, choose an appendix passage, "
        "enter a fictional assessment and lesson objective, review the extracted quotations "
        "and suggested support, and generate a new worksheet. The saved examples run offline. "
        "New generation uses the model selected in the app.",
    ])
    return "\n\n".join(parts) + "\n"


if __name__ == "__main__":
    print(build_demo(), end="")
