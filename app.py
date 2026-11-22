"""Streamlit interface for the INFH5000 reading worksheet project."""

import os

import streamlit as st

from assessment_ui import reading_assessment
from providers import make_client
from workflow import (
    check_profile,
    generate_worksheet,
    load_activities,
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
        st.caption("Generation sends the missed-item specifications, passage, teaching support "
                   "and lesson requirements to OpenAI.")
    else:
        st.caption("Ollama uses a model running on this computer. Start Ollama and download the named model before generating.")
    return backend, model, api_key


def create_worksheet(corpus):
    st.header("Create a worksheet")
    state = st.session_state
    assessment = state.get("assessment_result")
    if assessment is None or not assessment["completed"]:
        st.info("Score an assessment with at least one learner response to create a worksheet.")
        st.button("Go to reading assessment", on_click=lambda: state.update(workspace="Reading assessment"))
        return

    st.subheader("1. Choose the lesson")
    selection = st.selectbox(
        "Appendix passage",
        options=list(range(len(corpus))),
        format_func=lambda i: f"{corpus[i]['id']} · {corpus[i]['title']} · Tier {corpus[i]['tier']}",
    )
    passage = corpus[selection]
    show_source(passage)
    objective = st.text_input(
        "Lesson objective", value=passage["target_skill"].capitalize(), key=f"objective-{passage['id']}"
    ).strip()
    requirements = st.text_area(
        "Additional teaching requirements",
        placeholder="Target vocabulary, letter–sound patterns, previously taught skills, "
                    "topic, length or presentation preferences",
        key=f"requirements-{passage['id']}",
    ).strip()

    st.subheader("2. Review the assessment")
    report = assessment["report"]
    error_items = assessment["error_items"]
    st.write(assessment["summary"])
    with st.expander("Scored report and item responses"):
        st.text(report)
    if error_items:
        with st.expander(f"Missed items for worksheet generation ({len(error_items)})"):
            for item in error_items:
                st.write(f"{item['question_id']} · {item['question']}")
                st.caption(item["rubric"])
    else:
        st.caption("All answered items met the rubric. Choose a lesson objective for further practice.")

    profile = assessment["profile"]
    st.write("Review the observations and check each quote against the assessment.")
    edited_rows = st.data_editor(
        profile["observations"] or [{"finding": "", "quote": ""}],
        column_config={
            "finding": st.column_config.TextColumn("Observation"),
            "quote": st.column_config.TextColumn("Exact quote from assessment"),
        },
        column_order=["finding", "quote"],
        num_rows="dynamic",
        hide_index=True,
        key="review_observations",
    )
    observations = []
    for row in edited_rows:
        observation = {field: (row.get(field) or "").strip() for field in ("finding", "quote")}
        if any(observation.values()):
            observations.append(observation)
    support = st.text_area("Support to use in the worksheet", value=profile["support"], key="review_support").strip()
    activities = load_activities()
    template_index = st.selectbox(
        "Teaching activity",
        options=list(range(len(activities))),
        format_func=lambda i: activities[i]["label"],
        key="review_activity",
    )
    activity = activities[template_index]
    st.caption(activity["instruction"])
    reviewed = {"observations": observations, "support": support}
    problems = check_profile(reviewed, report)
    for problem in problems:
        st.warning(problem)

    # When the underlying profile or lesson changes, require a fresh confirmation
    # and discard any worksheet associated with the previous inputs.
    st.subheader("3. Generate and review")
    backend, model, api_key = model_settings()
    configured = bool(model and (backend == "Ollama" or api_key))
    context = (reviewed, activity["id"], passage["id"],
               objective, requirements, backend, model)
    if state.get("worksheet_context") != context:
        state["worksheet_context"] = context
        state["profile_confirmed"] = False
        state.pop("worksheet_result", None)
    confirmed = st.checkbox("I confirm this profile and lesson objective.", key="profile_confirmed")
    if not confirmed:
        state.pop("worksheet_result", None)
    can_generate = confirmed and configured and objective and not problems
    if st.button("Generate worksheet", type="primary", disabled=not can_generate):
        state.pop("worksheet_result", None)
        try:
            with st.spinner("Drafting and checking the worksheet…"):
                result = generate_worksheet(
                    passage, reviewed, objective, make_client(backend, model, api_key),
                    activity=activity, error_items=error_items, teacher_requirements=requirements,
                )
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
    mode = st.radio("Workspace", ["Reading assessment", "Create worksheet"],
                    horizontal=True, label_visibility="collapsed", key="workspace")
    corpus = load_corpus()
    if mode == "Reading assessment":
        reading_assessment(corpus)
    else:
        create_worksheet(corpus)


if __name__ == "__main__":
    main()
