"""Shared Streamlit sidebar, dependency checks, and memory viewer."""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version

import streamlit as st

from memory_db import (
    CATEGORIES,
    DEFAULT_PROJECT_ID,
    TAB_LEARNING_HUB,
    TAB_PROJECT_BUILDER,
    TAB_SCOPE_LABELS,
    delete_memories,
    delete_project,
    fetch_memories,
    list_projects,
)
from mentor_engine import MentorConnectionError, check_connection, list_ollama_models

LATEST_VERIFIED_RELEASES = {
    "streamlit": "1.55.0",
    "openai": "2.30.0",
    "python-dotenv": "1.2.2",
}

CATEGORY_LABELS = {
    "tutor_chat": "Tutor Chat",
    "code_explainer": "Sandbox / explain",
    "project_ideas": "Project Ideas",
    "build_planner": "Living plan",
    "project_code": "Generated project code",
    "snippet_assistant": "Snippet assistant",
}


def _parse_version(raw: str) -> tuple[int, ...]:
    cleaned = raw.split("+")[0].split("-")[0]
    parts: list[int] = []
    for piece in cleaned.split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def _installed_version(package_name: str) -> str | None:
    try:
        return version(package_name)
    except PackageNotFoundError:
        return None


def _version_status(package_name: str) -> tuple[str | None, bool]:
    installed = _installed_version(package_name)
    if not installed:
        return None, False
    latest = LATEST_VERIFIED_RELEASES[package_name]
    return installed, _parse_version(installed) >= _parse_version(latest)


def render_dependency_block() -> None:
    st.subheader("Dependency status")
    st.caption("Latest versions verified on March 28, 2026")
    for package_name in ("streamlit", "openai", "python-dotenv"):
        installed, is_current = _version_status(package_name)
        target = LATEST_VERIFIED_RELEASES[package_name]
        if not installed:
            st.warning(f"{package_name}: not installed (expected at least {target}).")
        elif is_current:
            st.success(f"{package_name}: {installed} (up to date vs {target}).")
        else:
            st.warning(f"{package_name}: {installed} (latest verified: {target}).")


def render_model_setup_block(key_prefix: str) -> None:
    st.subheader("Model setup")
    st.write("This app defaults to local Ollama.")

    if st.button("Check model connection", key=f"{key_prefix}_sidebar_check_connection"):
        try:
            result = check_connection()
            st.success(f"Connected. Model responded: {result}")
        except MentorConnectionError as exc:
            st.error(str(exc))

    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    if st.button("List local Ollama models", key=f"{key_prefix}_sidebar_list_models"):
        try:
            models = list_ollama_models(ollama_base_url)
            if models:
                st.success("Found models:\n- " + "\n- ".join(models))
            else:
                st.warning("No local models found. Run: ollama pull llama3.2:3b")
        except MentorConnectionError as exc:
            st.error(str(exc))


def render_sidebar_learning_profile(key_prefix: str) -> tuple[str, str]:
    st.header("Your Learning Profile")
    level = st.selectbox(
        "Current level",
        ["Absolute beginner", "Beginner", "Intermediate"],
        index=0,
        key=f"{key_prefix}_sidebar_level",
    )
    style = st.selectbox(
        "Explanation style",
        ["Like I'm 2", "Beginner", "Upskill"],
        index=1,
        key=f"{key_prefix}_sidebar_style",
    )
    return level, style


def render_memory_panel(key_prefix: str, *, leading_divider: bool = True) -> None:
    if leading_divider:
        st.divider()
    st.subheader("Memory (History Database)")
    st.caption(
        "Learning Hub and Project Builder keep separate saved context per area. "
        "RAG chunks are removed when matching memory rows are deleted."
    )

    projects = list_projects()
    proj_options: list[int | str] = ["all"]
    proj_options.extend(int(p["id"]) for p in projects)

    def _proj_label(x: int | str) -> str:
        if x == "all":
            return "All projects"
        p = next((r for r in projects if int(r["id"]) == int(x)), None)
        if p:
            return f'{p["name"]} (#{x})'
        return str(x)

    project_filter = st.selectbox(
        "Project",
        options=proj_options,
        format_func=_proj_label,
        key=f"{key_prefix}_memory_project_filter",
    )
    pid: int | None
    if project_filter == "all":
        pid = None
    else:
        pid = int(project_filter)

    scope_filter = st.selectbox(
        "Area",
        options=["all", TAB_LEARNING_HUB, TAB_PROJECT_BUILDER],
        format_func=lambda x: "All areas" if x == "all" else TAB_SCOPE_LABELS.get(x, x),
        key=f"{key_prefix}_memory_scope_filter",
    )
    mem_filter = st.selectbox(
        "Filter by type",
        options=["all", *CATEGORIES],
        format_func=lambda x: "All types" if x == "all" else CATEGORY_LABELS.get(x, x),
        key=f"{key_prefix}_memory_filter_type",
    )
    mem_limit = st.number_input(
        "How many records to show",
        min_value=1,
        max_value=500,
        value=25,
        step=1,
        key=f"{key_prefix}_memory_limit_input",
    )
    c1, c2 = st.columns(2)
    with c1:
        refresh = st.button("Refresh", key=f"{key_prefix}_memory_refresh_btn")
    with c2:
        delete_what = st.selectbox(
            "Delete",
            options=[
                "none",
                "all",
                "filtered",
                TAB_LEARNING_HUB,
                TAB_PROJECT_BUILDER,
            ],
            format_func=lambda x: {
                "none": "(choose to delete)",
                "all": "All memory",
                "filtered": "Current filters only",
                TAB_LEARNING_HUB: "Learning Hub (all projects)",
                TAB_PROJECT_BUILDER: "Project Builder (all projects)",
            }[x],
            key=f"{key_prefix}_memory_delete_scope",
        )
        if st.button("Confirm delete", key=f"{key_prefix}_memory_delete_btn"):
            if delete_what == "none":
                st.warning("Pick what to delete in the Delete dropdown.")
            elif delete_what == "all":
                delete_memories()
                st.toast("All memory deleted.")
                st.rerun()
            elif delete_what == "filtered":
                ts = None if scope_filter == "all" else scope_filter
                delete_memories(tab_scope=ts, project_id=pid)
                st.toast("Matching rows deleted.")
                st.rerun()
            elif delete_what == TAB_LEARNING_HUB:
                delete_memories(tab_scope=TAB_LEARNING_HUB)
                st.toast("Learning Hub memory deleted.")
                st.rerun()
            else:
                delete_memories(tab_scope=TAB_PROJECT_BUILDER)
                st.toast("Project Builder memory deleted.")
                st.rerun()

    with st.expander("Delete entire project workspace"):
        st.caption("Removes all memory and RAG chunks for one project (not the Default project).")
        wipe_choices = [p["id"] for p in projects if int(p["id"]) != DEFAULT_PROJECT_ID]
        if not wipe_choices:
            st.info("Create a non-default project first to enable workspace deletion.")
        else:
            wipe_id = st.selectbox(
                "Project to remove",
                options=wipe_choices,
                format_func=lambda i: _proj_label(int(i)),
                key=f"{key_prefix}_wipe_project_select",
            )
            if st.button("Delete project workspace", key=f"{key_prefix}_wipe_project_btn"):
                try:
                    m, r = delete_project(int(wipe_id))
                    st.success(f"Deleted project: {m} memory rows, {r} RAG chunks.")
                    st.rerun()
                except ValueError as exc:
                    st.warning(str(exc))

    if refresh:
        st.rerun()

    ts = None if scope_filter == "all" else scope_filter
    records = fetch_memories(
        category=None if mem_filter == "all" else mem_filter,
        tab_scope=ts,
        project_id=pid,
        limit=int(mem_limit),
    )

    if not records:
        st.info("No records match this filter.")
    else:
        for rec in records:
            area = TAB_SCOPE_LABELS.get(str(rec.get("tab_scope", "")), rec.get("tab_scope", "?"))
            pr = rec.get("project_id", "")
            title = f"{rec['timestamp']} | project {pr} | {area} | {CATEGORY_LABELS.get(rec['category'], rec['category'])}"
            with st.expander(title, expanded=False):
                st.markdown(f"**Level:** {rec['level']} | **Style:** {rec['style']}")
                st.markdown("**You**")
                st.markdown(rec["user_input"])
                st.markdown("**Assistant**")
                st.markdown(rec["assistant_output"])
