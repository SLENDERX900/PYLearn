"""Project workspace selector for Learning Hub and Project Builder."""

from __future__ import annotations

import streamlit as st

from memory_db import DEFAULT_PROJECT_ID, create_project, list_projects


def render_project_switcher(widget_prefix: str) -> int:
    projects = list_projects()
    ids = [int(p["id"]) for p in projects]
    state_key = f"{widget_prefix}_project_id"
    if state_key not in st.session_state:
        st.session_state[state_key] = DEFAULT_PROJECT_ID if DEFAULT_PROJECT_ID in ids else (ids[0] if ids else DEFAULT_PROJECT_ID)
    cur = int(st.session_state[state_key])
    if cur not in ids and ids:
        cur = ids[0]
        st.session_state[state_key] = cur
    idx = ids.index(cur) if cur in ids else 0

    def _fmt(i: int) -> str:
        p = next(x for x in projects if int(x["id"]) == i)
        return f'{p["name"]} (#{i})'

    sel = st.selectbox(
        "Project workspace",
        ids,
        index=idx,
        format_func=_fmt,
        key=f"{widget_prefix}_project_select",
    )
    st.session_state[state_key] = int(sel)

    with st.expander("New project"):
        nn = st.text_input("Name", key=f"{widget_prefix}_new_project_name")
        if st.button("Create project", key=f"{widget_prefix}_create_project_btn"):
            if nn.strip():
                pid = create_project(nn.strip())
                st.session_state[state_key] = pid
                st.rerun()

    return int(sel)
