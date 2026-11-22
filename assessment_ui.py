"""Timed learner response collection and subsequent teacher marking in Streamlit."""
import math
import time
from uuid import uuid4

import streamlit as st

from assessment import FORM_PASSAGES, load_questions, score_assessment


def _new_attempt():
    st.session_state["reading_attempt"] = {
        "id": uuid4().hex, "phase": "reading", "part": 0,
        "deadline": time.monotonic() + 15 * 60,
        "responses": {}, "skipped": set(), "timed_out": set(), "marks": {},
    }


def _expire(attempt):
    if attempt["phase"] == "reading" and time.monotonic() >= attempt["deadline"]:
        form_ids = {q["question_id"] for q in load_questions() if q["passage_id"] in FORM_PASSAGES}
        attempt["timed_out"] = form_ids - attempt["responses"].keys() - attempt["skipped"]
        attempt["phase"] = "expired"
    return attempt["phase"] == "expired"


@st.fragment(run_every=1)
def _clock():
    attempt = st.session_state["reading_attempt"]
    if _expire(attempt):
        st.rerun()
    seconds = math.ceil(attempt["deadline"] - time.monotonic())
    st.caption(f"Time remaining · {seconds // 60}:{seconds % 60:02d}")


def _widget(attempt, kind, qid):
    return f"reading-{attempt['id']}-{kind}-{qid}"


def _save_input(attempt_id, qid, kind):
    # Only this callback writes learner data. Late browser events cannot change
    # the last accepted response, including after a timer-triggered rerun.
    attempt = st.session_state["reading_attempt"]
    if attempt["id"] != attempt_id or _expire(attempt) or attempt["phase"] != "reading":
        return
    key = _widget(attempt, kind, qid)
    value = st.session_state[key]
    if kind == "skip":
        if value:
            attempt["skipped"].add(qid)
            attempt["responses"].pop(qid, None)
            st.session_state.pop(_widget(attempt, "answer", qid), None)
        else:
            attempt["skipped"].discard(qid)
    elif qid not in attempt["skipped"]:
        if value and value.strip():
            attempt["responses"][qid] = value.strip()
        else:
            attempt["responses"].pop(qid, None)


def _move(attempt_id, part):
    attempt = st.session_state["reading_attempt"]
    if attempt_id == attempt["id"] and not _expire(attempt) and attempt["phase"] == "reading":
        if part == len(FORM_PASSAGES):
            attempt["phase"] = "finished"
        else:
            attempt["part"] = part


def _collect(attempt, questions, passage):
    part = attempt["part"]
    _clock()
    st.subheader(f"Part {part + 1} of 3 · {passage['title']}")
    st.write(passage["text"])
    st.caption("For text answers, click outside the box or press Ctrl+Enter (⌘+Enter on Mac) to save.")
    items = [q for q in questions if q["passage_id"] == passage["id"]]
    for q in items:
        qid = q["question_id"]
        st.markdown(f"**{qid} · {q['mode'].capitalize()}**")
        st.write(q["question"])
        skip = qid in attempt["skipped"]
        value = attempt["responses"].get(qid)
        args = dict(key=_widget(attempt, "answer", qid), disabled=skip,
                    on_change=_save_input, args=(attempt["id"], qid, "answer"))
        if q["mode"] == "choice":
            options = ["A", "B", "C", "D"]
            st.radio(f"Choice for {qid}", options, horizontal=True,
                     index=options.index(value) if value else None, **args)
        else:
            label = "Transcribed oral response" if q["mode"] == "oral" else "Written response"
            st.text_area(f"{label} for {qid}", value=value or "", height=68, **args)
        st.checkbox(f"Skip {qid}", value=skip, key=_widget(attempt, "skip", qid),
                    on_change=_save_input, args=(attempt["id"], qid, "skip"))
    outstanding = sum(q["question_id"] not in attempt["responses"]
                      and q["question_id"] not in attempt["skipped"] for q in items)
    if outstanding:
        st.caption(f"{outstanding} item(s) on this passage still need an answer or a skip.")
    left, right = st.columns(2)
    if part:
        left.button("Previous passage", on_click=_move, args=(attempt["id"], part - 1))
    label = "Finish and lock answers" if part == 2 else "Next passage"
    right.button(label, type="primary", disabled=bool(outstanding), on_click=_move,
                 args=(attempt["id"], part + 1))


def _mark(attempt, questions):
    st.subheader("Teacher marking")
    st.write("Review the transcribed oral and written answers against the appendix. Award one point when the learner meets the criterion.")
    to_mark = [q for q in questions if q["mode"] != "choice" and q["question_id"] in attempt["responses"]]
    for pid in FORM_PASSAGES:
        group = [q for q in to_mark if q["passage_id"] == pid]
        if not group:
            continue
        with st.expander(f"{pid} · {len(group)} answers to review", expanded=True):
            for q in group:
                qid = q["question_id"]
                st.markdown(f"**{qid} · {q['question']}**")
                st.write("Learner response", attempt["responses"][qid])
                st.write("Appendix answer", q["answer"])
                st.write("One point awarded when", q["rubric"])
                mark = attempt["marks"].get(qid)
                mark = st.radio(f"Points for {qid}", [0, 1], index=mark, horizontal=True,
                                key=_widget(attempt, "mark", qid))
                if mark is not None:
                    attempt["marks"][qid] = mark
    remaining = len(to_mark) - len(attempt["marks"])
    if remaining:
        st.caption(f"{remaining} answer(s) still need a mark.")
    if st.button("Score assessment", type="primary", disabled=bool(remaining)):
        result = score_assessment(questions, attempt["responses"], attempt["marks"],
                                  skipped=attempt["skipped"], timed_out=attempt["timed_out"])
        st.session_state["assessment_result"] = result
        attempt["phase"] = "scored"
        st.rerun()


def _create_worksheet():
    st.session_state["workspace"] = "Create worksheet"


def _clear_worksheet():
    for key in ("worksheet_result", "worksheet_context", "profile_confirmed",
                "review_observations", "review_support", "review_activity"):
        st.session_state.pop(key, None)


def _reset():
    state = st.session_state
    state.pop("reading_attempt", None)
    state.pop("assessment_result", None)
    _clear_worksheet()


def _results():
    result = st.session_state["assessment_result"]
    st.subheader("Combined feedback")
    st.write(result["summary"])
    st.download_button("Download complete report", data=result["report"],
                       file_name="reading-assessment.txt", mime="text/plain")
    for passage in result["passages"]:
        with st.expander(f"{passage['passage_id']} · {passage['points']}/{passage['possible']} points"):
            st.write(passage["feedback"])
            rows = []
            for item in passage["items"]:
                response = item["response"]
                score = f"{item['points']}/1"
                if item["timed_out"] or item["skipped"]:
                    response = "Time expired" if item["timed_out"] else "Skipped"
                    score = "Unscored"
                rows.append({"ID": item["question_id"], "Question": item["question"],
                             "Response": response, "Score": score, "Criterion": item["rubric"]})
            st.dataframe(rows, hide_index=True)
            lines = [passage["feedback"], ""]
            for row in rows:
                lines.extend([f"{row['ID']} · {row['Question']}", f"Response: {row['Response']}",
                              f"Score: {row['Score']}. Criterion: {row['Criterion']}", ""])
            st.download_button(f"Download {passage['passage_id']} report", data="\n".join(lines),
                               file_name=f"{passage['passage_id']}-report.txt", mime="text/plain")
    if result["completed"]:
        st.button("Create worksheet from this assessment", type="primary", on_click=_create_worksheet)
    if st.button("Review marks again"):
        st.session_state["reading_attempt"]["phase"] = "marking"
        st.session_state.pop("assessment_result")
        _clear_worksheet()
        st.rerun()


def reading_assessment(corpus):
    st.header("Reading assessment")
    attempt = st.session_state.get("reading_attempt")
    if not attempt:
        st.write("Read The Red Ball, Where Rain Comes From and The Last Train Home in order. The three passages share 15 minutes. Aim for five minutes per passage.")
        st.write("The teacher records spoken answers. Choose an option or write a response for the other items. You can skip a question. The timer ends response entry for all three passages.")
        st.button("Start timed assessment", type="primary", on_click=_new_attempt)
        return
    _expire(attempt)
    questions = [q for q in load_questions() if q["passage_id"] in FORM_PASSAGES]
    if attempt["phase"] == "reading":
        pid = FORM_PASSAGES[attempt["part"]]
        passage = next(p for p in corpus if p["id"] == pid)
        _collect(attempt, questions, passage)
    elif attempt["phase"] in ("expired", "finished"):
        st.subheader("Response entry closed")
        st.write("Time expired." if attempt["phase"] == "expired" else "The learner finished the assessment.")
        st.write("Return the device to the teacher for marking.")
        if st.button("Open teacher marking", type="primary"):
            attempt["phase"] = "marking"
            st.rerun()
    elif attempt["phase"] == "marking":
        _mark(attempt, questions)
    else:
        _results()
    with st.expander("Start over with another learner"):
        confirmed = st.checkbox("Clear the current responses, marks and report from this session.")
        st.button("Reset assessment", disabled=not confirmed, on_click=_reset)
