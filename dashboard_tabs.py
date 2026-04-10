"""Tab bodies for the single-dashboard layout (Learning Hub + Project Builder)."""

from __future__ import annotations

import streamlit as st

from memory_db import (
    TAB_LEARNING_HUB,
    TAB_PROJECT_BUILDER,
    build_llm_context,
    save_memory,
)
from mentor_engine import (
    MentorConnectionError,
    ask_tutor,
    assist_snippet,
    build_plan,
    generate_project_code,
    strip_leading_code_fence,
    suggest_projects,
)
from project_workspace import render_project_switcher
from rag_embed import upsert_memory_to_rag
from sandbox_run import run_python_sandbox

_DEFAULT_HUB_PLAYGROUND = (
    "# Try it” stdout appears below\n"
    'for i in range(3):\n    print("loop", i)\n'
)
_DEFAULT_PB_CODE = (
    "# Starter code appears here after you click Generate.\n"
    "# Edit freely, then use the snippet assistant on the right.\n"
)


def render_learning_hub_tab(level: str, style: str) -> None:
    project_id = render_project_switcher("hub")
    st.markdown("Learn on the left, run experiments on the right.")
    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("### Tutor chat")
        st.caption(
            "Ask questions or paste code here for explanations."
            " Use the tutor for walkthroughs and re-explaining."
        )
        question = st.text_area(
            "Ask anything about Python",
            placeholder='Example: "Explain to me what is a loop like I am two years old" or paste code you tried in the playground.',
            height=180,
            key="hub_tutor_question",
        )
        if st.button("Ask tutor", type="primary", key="hub_tutor_submit"):
            if not question.strip():
                st.warning("Please type a question first.")
            else:
                try:
                    q = question.strip()
                    mem_ctx = build_llm_context(TAB_LEARNING_HUB, project_id, q)
                    with st.spinner("Thinking..."):
                        answer = ask_tutor(question, style, level, memory_context=mem_ctx)
                    mid = save_memory(
                        "tutor_chat",
                        level,
                        style,
                        q,
                        answer,
                        tab_scope=TAB_LEARNING_HUB,
                        project_id=project_id,
                    )
                    upsert_memory_to_rag(project_id, mid, q, answer)
                    st.session_state.hub_tutor_out = answer
                except MentorConnectionError as exc:
                    st.error(str(exc))

        if st.session_state.get("hub_tutor_out"):
            st.markdown("Latest answer")
            st.markdown(st.session_state.hub_tutor_out)

    with right:
        st.markdown("Interactive playground")
        st.caption("Write and run Python here. Explanations stay in Tutor chat (left).")

        if st.session_state.pop("hub_reset_editor_pending", False):
            st.session_state.hub_playground_code = "# Your code\nprint('hello')\n"
        elif "hub_playground_code" not in st.session_state:
            st.session_state.hub_playground_code = _DEFAULT_HUB_PLAYGROUND

        st.text_area(
            "Live editor",
            height=320,
            key="hub_playground_code",
        )

        b1, b2, b3 = st.columns(3)
        with b1:
            run_clicked = st.button("Run", type="primary", key="hub_run_btn")
        with b2:
            if st.button("Clear output", key="hub_clear_output_btn"):
                st.session_state.hub_last_stdout = ""
                st.session_state.hub_last_run_err = None
                st.rerun()
        with b3:
            if st.button("Reset editor", key="hub_reset_editor_btn"):
                st.session_state.hub_reset_editor_pending = True
                st.rerun()

        if run_clicked:
            code = str(st.session_state.get("hub_playground_code", ""))
            with st.spinner("Running..."):
                out, err = run_python_sandbox(code)
            st.session_state.hub_last_stdout = out
            st.session_state.hub_last_run_err = err

        err = st.session_state.get("hub_last_run_err")
        out = st.session_state.get("hub_last_stdout", "")
        if err:
            st.error(err)
        st.markdown("**Output**")
        st.code(out if out else "(no output yet)", language=None)


def render_project_builder_tab(level: str, style: str) -> None:
    project_id = render_project_switcher("pb")
    st.markdown("Plan on the left, generate and refine code on the right.")
    st.caption(
        "Use the project builder with a living plan and generated code. Pick a project workspace above."
    )

    if "pb_code" not in st.session_state:
        st.session_state.pb_code = _DEFAULT_PB_CODE
    if "pb_plan" not in st.session_state:
        st.session_state.pb_plan = ""

    left, right = st.columns(2, gap="large")

    with left:
        st.markdown("### Idea & living plan")
        idea = st.text_area(
            "Describe your project",
            placeholder='Example: "A simple fitness tracker with goals and streaks."',
            height=160,
            key="pb_idea_input",
        )

        p1, p2 = st.columns(2)
        with p1:
            gen_plan = st.button("Generate or update plan", type="primary", key="pb_gen_plan_btn")
        with p2:
            gen_code = st.button("Generate starter code", key="pb_gen_code_btn")

        if gen_plan:
            if not str(idea).strip():
                st.warning("Describe your idea first.")
            else:
                try:
                    idea_s = str(idea).strip()
                    mem_ctx = build_llm_context(TAB_PROJECT_BUILDER, project_id, idea_s)
                    with st.spinner("Planning..."):
                        plan = build_plan(idea_s, level, style, memory_context=mem_ctx)
                    mid = save_memory(
                        "build_planner",
                        level,
                        style,
                        idea_s,
                        plan,
                        tab_scope=TAB_PROJECT_BUILDER,
                        project_id=project_id,
                    )
                    upsert_memory_to_rag(project_id, mid, idea_s, plan)
                    st.session_state.pb_plan = plan
                except MentorConnectionError as exc:
                    st.error(str(exc))

        if gen_code:
            if not str(idea).strip():
                st.warning("Describe your idea first.")
            else:
                try:
                    idea_s = str(idea).strip()
                    mem_ctx = build_llm_context(TAB_PROJECT_BUILDER, project_id, idea_s)
                    with st.spinner("Generating code..."):
                        raw = generate_project_code(
                            idea_s, level, style, memory_context=mem_ctx
                        )
                    code = strip_leading_code_fence(raw)
                    mid = save_memory(
                        "project_code",
                        level,
                        style,
                        idea_s,
                        code,
                        tab_scope=TAB_PROJECT_BUILDER,
                        project_id=project_id,
                    )
                    upsert_memory_to_rag(project_id, mid, idea_s, code)
                    st.session_state.pb_code = code
                    st.rerun()
                except MentorConnectionError as exc:
                    st.error(str(exc))

        if st.session_state.pb_plan:
            st.markdown("#### Living plan")
            st.markdown(st.session_state.pb_plan)

        with st.expander("Spark project ideas (optional)"):
            interests = st.text_input(
                "Interests",
                placeholder="health, productivity, games, â€¦",
                key="pb_spark_interests",
            )
            if st.button("Suggest ideas", key="pb_spark_btn"):
                if not interests.strip():
                    st.warning("Add at least one interest.")
                else:
                    try:
                        intr = interests.strip()
                        mem_ctx = build_llm_context(TAB_PROJECT_BUILDER, project_id, intr)
                        with st.spinner("Brainstorming..."):
                            ideas = suggest_projects(
                                intr, level, style, memory_context=mem_ctx
                            )
                        mid = save_memory(
                            "project_ideas",
                            level,
                            style,
                            intr,
                            ideas,
                            tab_scope=TAB_PROJECT_BUILDER,
                            project_id=project_id,
                        )
                        upsert_memory_to_rag(project_id, mid, intr, ideas)
                        st.session_state.pb_spark_out = ideas
                    except MentorConnectionError as exc:
                        st.error(str(exc))
            if st.session_state.get("pb_spark_out"):
                st.markdown(st.session_state.pb_spark_out)

    with right:
        st.markdown("### Codebase & assistant")
        st.caption(
            "Paste a snippet below to explain or modify in context. "
            "For general teaching, use Tutor chat in Learning Hub."
        )

        st.text_area(
            "Generated / edited project code",
            height=360,
            key="pb_code",
        )

        st.markdown("#### Snippet assistant")
        pb_snippet = st.text_area(
            "Selected snippet (paste from above)",
            height=140,
            key="pb_snippet_input",
        )
        pb_mode = st.radio(
            "Mode",
            ["Explain selection", "Modify selection"],
            horizontal=True,
            key="pb_snippet_mode",
        )
        pb_notes = st.text_input(
            "What do you want?",
            placeholder="Explain: optional focus. Modify: describe the edit.",
            key="pb_snippet_notes",
        )
        if st.button("Run snippet assistant", type="primary", key="pb_snippet_run_btn"):
            full_code = str(st.session_state.get("pb_code", ""))
            sel = str(pb_snippet).strip()
            if not sel:
                st.warning("Paste a snippet from the codebase.")
            else:
                is_modify = pb_mode.startswith("Modify")
                if is_modify and not pb_notes.strip():
                    st.warning("Describe the change you want.")
                else:
                    msg = pb_notes.strip() or "Explain this snippet clearly."
                    try:
                        q = f"{msg}\n---\n{sel}"
                        mem_ctx = build_llm_context(TAB_PROJECT_BUILDER, project_id, q)
                        with st.spinner("Assistant working..."):
                            reply = assist_snippet(
                                "modify" if is_modify else "explain",
                                sel,
                                msg,
                                full_code,
                                level,
                                style,
                                memory_context=mem_ctx,
                            )
                        user_blob = f"[project] {msg}\n---\n{sel}"
                        mid = save_memory(
                            "snippet_assistant",
                            level,
                            style,
                            user_blob,
                            reply,
                            tab_scope=TAB_PROJECT_BUILDER,
                            project_id=project_id,
                        )
                        upsert_memory_to_rag(project_id, mid, user_blob, reply)
                        st.session_state.pb_snippet_out = reply
                    except MentorConnectionError as exc:
                        st.error(str(exc))

        if st.session_state.get("pb_snippet_out"):
            st.markdown("##### Assistant")
            st.markdown(st.session_state.pb_snippet_out)
