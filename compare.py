"""Compare two worksheets for the same lesson using the scored assessment demo."""

import argparse
import sys

from demo import DEMO_OBJECTIVE, DEMO_PASSAGE_ID, demo_assessment
from providers import make_client
from workflow import check_profile, generate_worksheet, load_corpus, render_markdown


def paired_comparison(passage, assessment, client, backend, model):
    profile = assessment["profile"]
    errors = assessment["error_items"]
    sections = [
        "# Worksheet comparison",
        f"**Model** · {backend} / {model}",
        f"**Passage** · {passage['id']} · {passage['title']}",
        f"**Lesson objective** · {DEMO_OBJECTIVE}",
        passage["text"],
        "## Assessment evidence for reviewers",
        "These items earned 0/1 when the course scoring code evaluated the demo’s "
        "scripted responses and teacher marks.",
        "\n".join(f"- **{item['question_id']}** · {item['question']}  \n  "
                  f"Criterion · {item['rubric']}" for item in errors),
        f"**Suggested support used in the demo** · {profile['support']}",
        "Both requests use the same passage, objective, model, worksheet prompt and checks. "
        "B also receives the missed item specifications and the suggested support. "
        "The shared objective already asks for sequencing practice. Review how each worksheet "
        "helps the reader put events in order. The generator can revise an invalid draft once.",
    ]

    ratings = []
    completed = 0
    for label, condition_profile, error_items in (
        ("A · Lesson only", None, None),
        ("B · Assessment-informed lesson", profile, errors),
    ):
        sections.append(f"## {label}")
        try:
            if condition_profile is not None:
                problems = check_profile(condition_profile, assessment["report"])
                if problems:
                    raise ValueError(" ".join(problems))
            worksheet = generate_worksheet(passage, condition_profile, DEMO_OBJECTIVE, client,
                                           error_items=error_items)
            teacher_copy = render_markdown(worksheet, passage, DEMO_OBJECTIVE, teacher=True)
        except (ValueError, RuntimeError) as error:
            sections.append(f"**Incomplete** · {error}")
            ratings.append(f"| {label} | N/A | N/A | N/A | Missing output |")
            continue
        completed += 1
        sections.append("\n".join("##" + line if line.startswith("#") else line
                                  for line in teacher_copy.splitlines()))
        ratings.append(f"| {label} | | | | |")

    sections.extend([
        "## Reviewer scores",
        "For each worksheet, check whether its practice exercises the scored skills above, "
        "whether it teaches the shared objective, and whether the passage supports each answer. "
        "Score each dimension 0 (unmet), 1 (partly met), or 2 (met). Cite a question or passage detail to explain each rating.",
        "\n".join(["| Condition | Practice on missed skills | Lesson objective | Supported answers | Evidence |",
                   "| --- | --- | --- | --- | --- |", *ratings]),
        f"Completed {completed} of 2 worksheets. This comparison evaluates the materials for one scripted attempt.",
    ])
    return "\n\n".join(sections) + "\n", completed != 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="generate both worksheets using the selected model")
    parser.add_argument("--backend", choices=["OpenAI", "Ollama"])
    parser.add_argument("--model", help="name of the API model or downloaded Ollama model")
    args = parser.parse_args(argv)
    if args.run and (not args.backend or not args.model):
        parser.error("--run requires both --backend and --model")

    assessment = demo_assessment()
    passage = next(p for p in load_corpus() if p["id"] == DEMO_PASSAGE_ID)
    if not args.run:
        print(f"Dry run for {passage['id']} · {passage['title']} · {DEMO_OBJECTIVE}")
        print("A receives the lesson. B also receives the missed item specifications and teaching support.")
        print("Missed items in this demo: " + ", ".join(item["question_id"] for item in assessment["error_items"]))
        print("Run with --run --backend OpenAI --model MODEL (or --backend Ollama).")
        return 0

    try:
        client = make_client(args.backend, args.model)
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    report, incomplete = paired_comparison(passage, assessment, client, args.backend, args.model)
    print(report, end="")
    return int(incomplete)


if __name__ == "__main__":
    sys.exit(main())
