"""Streamlit interface for the INFH5000 reading worksheet project."""

import os

import streamlit as st

from providers import make_client
from workflow import (
    check_profile,
    check_worksheet,
    extract_profile,
    generate_worksheet,
    load_activities,
    load_cases,
    load_corpus,
    render_markdown,
)


def show_source(passage):
    with st.expander(f"Source passage · {passage['id']} · {passage['title']}"):
        st.caption(
            f"{passage['genre']} · Tier {passage['tier']} · "
            f"Target skill: {passage['target_skill']}"
        )
        st.write(passage["text"])
        if passage["new_vocabulary"]:
            st.caption("New vocabulary in the appendix: " + ", ".join(passage["new_vocabulary"]))


def show_worksheet(worksheet, passage, objective, key):
    st.subheader(passage["title"])
    for block in worksheet["reading_blocks"]:
        st.write(block)

    st.markdown("**Practice**")
    st.write(worksheet["support_activity"])
    st.markdown("**Questions**")
    for number, item in enumerate(worksheet["questions"], start=1):
        st.write(f"{number}. {item['question']}")

    filename = f"{passage['id']}-{key}"
    st.download_button(
        "Download learner worksheet",
        render_markdown(worksheet, passage, objective, teacher=False),
        file_name=f"{filename}-learner.md",
        mime="text/markdown",
        key=f"download-learner-{key}",
    )
    if st.checkbox("Show teacher notes and answer key", key=f"teacher-{key}"):
        st.write(worksheet["teacher_note"])
        for number, item in enumerate(worksheet["questions"], start=1):
            st.markdown(f"**{number}. {item['question']}**")
            st.write(item["answer"])
            st.caption(f"Source evidence: “{item['evidence']}”")
        st.download_button(
            "Download teacher copy",
            render_markdown(worksheet, passage, objective, teacher=True),
            file_name=f"{filename}-teacher.md",
            mime="text/markdown",
            key=f"download-teacher-{key}",
        )


def worked_examples(corpus, cases):
    st.header("Worked examples")
    st.write("Compare two fictional assessment excerpts for the same lesson. Both worksheets are saved examples you can open offline.")
    by_id = {passage["id"]: passage for passage in corpus}
    shared_passage = by_id[cases[0]["passage_id"]]
    st.markdown(f"**Lesson objective** · {cases[0]['objective']}")
    show_source(shared_passage)
    for column, case in zip(st.columns(len(cases)), cases):
        with column:
            st.subheader(case["label"])
            st.markdown("**Assessment excerpt**")
            st.write(case["report"])
            with st.expander("Evidence from the excerpt"):
                for observation in case["profile"]["observations"]:
                    st.write(observation["finding"])
                    st.caption(f"“{observation['quote']}”")
            st.markdown("**Selected support**")
            st.write(case["profile"]["support"])
            st.divider()
            show_worksheet(case["worksheet"], by_id[case["passage_id"]], case["objective"], case["id"])


def model_settings():
    backend = st.radio("Model provider", ["OpenAI", "Ollama"], horizontal=True)
    model_defaults = {"OpenAI": ("OPENAI_MODEL", "gpt-4.1-mini"), "Ollama": ("OLLAMA_MODEL", "gemma3:4b")}
    variable, fallback = model_defaults[backend]
    model = st.text_input("Model name", value=os.environ.get(variable) or fallback, key=f"model-{backend}").strip()
    api_key = ""
    if backend == "OpenAI":
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            api_key = st.text_input("OpenAI API key", type="password", key="openai-key").strip()
        st.caption("Extract profile sends the excerpt to OpenAI. Generate worksheet sends the reviewed profile, source text, and lesson objective.")
    else:
        st.caption("Ollama uses a model running on this computer. Start Ollama and download the named model before generating.")
    return backend, model, api_key


def create_worksheet(corpus, cases):
    st.header("Create a worksheet")
    backend, model, api_key = model_settings()
    configured = bool(model and (backend == "Ollama" or api_key))
    state = st.session_state

    st.subheader("1. Choose the lesson")
    selection = st.selectbox(
        "Appendix passage",
        options=list(range(len(corpus))),
        format_func=lambda i: f"{corpus[i]['id']} · {corpus[i]['title']} · Tier {corpus[i]['tier']}",
    )
    passage = corpus[selection]
    show_source(passage)
    initial_objective = next(
        (case["objective"] for case in cases if case["passage_id"] == passage["id"]),
        passage["target_skill"].capitalize(),
    )
    objective = st.text_input(
        "Lesson objective", value=initial_objective, key=f"objective-{passage['id']}"
    ).strip()

    st.subheader("2. Review the assessment")
    sample = st.selectbox(
        "Starting excerpt",
        options=[*range(len(cases)), None],
        format_func=lambda i: "Write your own" if i is None else cases[i]["label"],
    )
    report = st.text_area(
        "Fictional assessment excerpt",
        value=cases[sample]["report"] if sample is not None else "",
        height=115,
        key=f"report-{sample}",
    ).strip()
    profile_context = (backend, model, report)
    if state.get("profile_context") != profile_context:
        state.pop("profile", None)
        state.pop("worksheet_result", None)
        state["profile_context"] = profile_context
    if st.button("Extract profile", disabled=not (configured and report)):
        state.pop("profile", None)
        state.pop("worksheet_result", None)
        try:
            with st.spinner("Reading the assessment excerpt…"):
                extracted = extract_profile(report, make_client(backend, model, api_key))
        except (RuntimeError, ValueError) as error:
            st.error(str(error))
        else:
            state["profile"] = extracted
            state["edit_version"] = state.get("edit_version", 0) + 1
    if "profile" not in state:
        return

    profile = state["profile"]
    version = state["edit_version"]
    st.write("Edit the findings and check each quote against the excerpt.")
    edited_rows = st.data_editor(
        profile["observations"] or [{"finding": "", "quote": ""}],
        column_config={
            "finding": st.column_config.TextColumn("Observation"),
            "quote": st.column_config.TextColumn("Exact quote from excerpt"),
        },
        column_order=["finding", "quote"],
        num_rows="dynamic",
        hide_index=True,
        key=f"observations-{version}",
    )
    observations = []
    for row in edited_rows:
        observation = {field: (row.get(field) or "").strip() for field in ("finding", "quote")}
        if any(observation.values()):
            observations.append(observation)
    support = st.text_area("Support to use in the worksheet", value=profile["support"], key=f"support-{version}").strip()
    activities = load_activities()
    template_index = st.selectbox(
        "Teaching activity",
        options=list(range(len(activities))),
        format_func=lambda i: activities[i]["label"],
        key=f"activity-{version}",
    )
    activity = activities[template_index]
    st.caption(activity["instruction"])
    reviewed = {"observations": observations, "support": support}
    problems = check_profile(reviewed, report)
    for problem in problems:
        st.warning(problem)

    # When the underlying profile or lesson changes, require a fresh confirmation
    # and discard any worksheet associated with the previous inputs.
    context = (profile_context, version, reviewed, activity["id"], passage["id"], objective)
    if state.get("worksheet_context") != context:
        state["worksheet_context"] = context
        state["profile_confirmed"] = False
        state.pop("worksheet_result", None)
    confirmed = st.checkbox("I confirm this profile and lesson objective.", key="profile_confirmed")
    if not confirmed:
        state.pop("worksheet_result", None)
    st.subheader("3. Generate and review")
    can_generate = confirmed and configured and objective and not problems
    if st.button("Generate worksheet", type="primary", disabled=not can_generate):
        state.pop("worksheet_result", None)
        try:
            with st.spinner("Drafting and checking the worksheet…"):
                result = generate_worksheet(
                    passage, reviewed, objective, make_client(backend, model, api_key),
                    activity=activity,
                )
            issues = check_worksheet(result, passage, activity=activity)
            if issues:
                raise ValueError("Worksheet checks failed: " + " ".join(issues))
        except (RuntimeError, ValueError) as error:
            st.error(str(error))
        else:
            state["worksheet_result"] = result
            state["generation"] = state.get("generation", 0) + 1
    if "worksheet_result" in state:
        show_worksheet(state["worksheet_result"], passage, objective, f"draft-{state['generation']}")


def main():
    st.set_page_config(page_title="Reading Worksheet Studio", layout="wide")
    st.title("Reading Worksheet Studio")
    st.caption("INFH5000 · Group 5")
    mode = st.radio("Workspace", ["Worked examples", "Create worksheet"], horizontal=True, label_visibility="collapsed")
    corpus = load_corpus()
    cases = load_cases()
    if mode == "Worked examples":
        worked_examples(corpus, cases)
    else:
        create_worksheet(corpus, cases)


if __name__ == "__main__":
    main()
