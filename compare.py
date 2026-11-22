"""Compare worksheet generation for the two fictional cases in the N1 demonstration."""

import argparse
import sys

from providers import make_client
from workflow import (
    WORKSHEET_PROMPT,
    check_profile,
    check_worksheet,
    generate_checked,
    generate_worksheet,
    load_cases,
    load_corpus,
    render_markdown,
)


def baseline(passage, objective, client, report=None):
    """Generate from the lesson alone (A) or from the same lesson and raw report (B)."""
    source = {key: passage[key] for key in ("title", "genre", "tier", "target_skill", "new_vocabulary", "text")}
    inputs = {"passage": source, "lesson_objective": objective}
    if report is not None:
        inputs["assessment_excerpt"] = report
    return generate_checked(client, WORKSHEET_PROMPT, inputs,
                            lambda result: check_worksheet(result, passage))


def checked_result(generate, passage):
    try:
        worksheet = generate()
        issues = check_worksheet(worksheet, passage)
    except (RuntimeError, ValueError) as error:
        return None, str(error)
    if issues:
        return None, " ".join(issues)
    return worksheet, None


def paired_comparison(passage, cases, client, backend, model):
    objective = cases[0]["objective"]
    lines = [
        "# Worksheet comparison",
        "",
        f"Model: {backend} / {model}. Source: {passage['id']}, {passage['title']}.",
        "",
        f"**Shared lesson objective.** {objective}",
        "",
        passage["text"],
        "",
        "A receives the passage and objective. B also receives the fictional report. "
        "C uses the worked example’s curated profile. This comparison starts after profile confirmation. "
        "All three share the same worksheet prompt, validation checks and allowance of one repair.",
        "",
        "A is generated once and shown for both cases. These two paired examples illustrate behavior "
        "on one passage. Automated checks cover structure and source quotations. Reviewers judge "
        "instructional fit and answer correctness separately.",
    ]
    common = checked_result(lambda: baseline(passage, objective, client), passage)
    missing = set()
    for case in cases:
        lines.extend(["", f"## {case['label']}", "", "**Fictional assessment excerpt**", "", case["report"]])
        raw = checked_result(lambda: baseline(passage, objective, client, case["report"]), passage)
        profile_issues = check_profile(case["profile"], case["report"])
        if profile_issues:
            structured = (None, "Curated profile failed validation. " + " ".join(profile_issues))
        else:
            structured = checked_result(
                lambda: generate_worksheet(passage, case["profile"], objective, client), passage
            )
        for variant, result in (("A", common), ("B", raw), ("C", structured)):
            worksheet, error = result
            lines.extend(["", f"### Condition {variant}", ""])
            if error is not None:
                missing.add("common A" if variant == "A" else f"{case['id']} {variant}")
                lines.extend(["**Incomplete.** " + error, ""])
                continue
            worksheet_md = render_markdown(worksheet, passage, objective, teacher=True)
            nested_md = "\n".join("###" + line if line.startswith("#") else line
                                  for line in worksheet_md.splitlines())
            lines.extend([
                "Automated worksheet checks passed.",
                "",
                nested_md,
            ])
        lines.extend([
            "", "### Reviewer scores", "",
            "Score each dimension 0 (unmet), 1 (partly met), or 2 (met). "
            "Mark missing outputs as N/A and record one concrete reason per rating.", "",
            "| Condition | Fit to this learner | Objective preserved | Answers supported | Reason |",
            "|---|---|---|---|---|",
            "| A | | | | |", "| B | | | | |", "| C | | | | |",
        ])
    lines.extend(["", f"Completed {5 - len(missing)} of 5 distinct generation tasks.", ""])
    return "\n".join(lines), bool(missing)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="send inputs to the selected model")
    parser.add_argument("--backend", choices=["OpenAI", "Ollama"])
    parser.add_argument("--model", help="name of the API model or downloaded Ollama model")
    args = parser.parse_args(argv)
    if args.run and (not args.backend or not args.model):
        parser.error("--run requires both --backend and --model")
    cases = load_cases()
    if len(cases) != 2 or any(case["passage_id"] != "N1" for case in cases):
        parser.error("this paired demonstration requires the two bundled N1 cases")
    if cases[0]["objective"] != cases[1]["objective"]:
        parser.error("both cases must use the same lesson objective")
    if not args.run:
        print("Dry run. Two fictional profiles, one N1 passage, five distinct generation tasks.")
        print("Run with --run --backend OpenAI --model MODEL (or --backend Ollama).")
        print("Redirect standard output to a .md file to keep the comparison and reviewer sheets.")
        return 0

    passage = next(text for text in load_corpus() if text["id"] == "N1")
    try:
        client = make_client(args.backend, args.model)
    except (RuntimeError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 1
    report, incomplete = paired_comparison(passage, cases, client, args.backend, args.model)
    print(report)
    return int(incomplete)


if __name__ == "__main__":
    sys.exit(main())
