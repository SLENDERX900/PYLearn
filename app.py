import os
import sqlite3
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import streamlit as st

from mentor_engine import (
    MentorConnectionError,
    ask_tutor,
    build_plan,
    check_connection,
    explain_code,
    list_ollama_models,
    suggest_projects,
)



LATEST_VERIFIED_RELEASES = {
    "streamlit": "1.55.0",
    "openai": "2.30.0",
    "python-dotenv": "1.2.2",
}

MEMORY_DB_PATH = Path("mentor_memory.db")


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


def _init_memory_db() -> None:
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                category TEXT NOT NULL,
                level TEXT NOT NULL,
                style TEXT NOT NULL,
                user_input TEXT NOT NULL,
                assistant_output TEXT NOT NULL
            )
            """
        )
        conn.commit()


def _save_memory(category: str, level: str, style: str, user_input: str, assistant_output: str) -> None:
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO memory_entries (category, level, style, user_input, assistant_output)
            VALUES (?, ?, ?, ?, ?)
            """,
            (category, level, style, user_input, assistant_output),
        )
        conn.commit()


def _load_memories(category: str | None, limit: int) -> list[tuple[int, str, str, str, str, str, str]]:
    query = """
        SELECT id, created_at, category, level, style, user_input, assistant_output
        FROM memory_entries
    """
    params: tuple[object, ...] = ()
    if category and category != "All":
        query += " WHERE category = ?"
        params = (category,)
    query += " ORDER BY id DESC LIMIT ?"
    params = (*params, limit)

    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        rows = conn.execute(query, params).fetchall()
    return rows


def _delete_all_memories() -> None:
    with sqlite3.connect(MEMORY_DB_PATH) as conn:
        conn.execute("DELETE FROM memory_entries")
        conn.commit()

st.set_page_config(page_title="Python Mentor Platform", page_icon="🐍", layout="wide")
_init_memory_db()

st.title("🐍 Python Mentor Platform")
st.caption("Local-first Python learning copilot for solo builders.")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

with st.sidebar:
    st.header("Your Learning Profile")
    level = st.selectbox(
        "Current level",
        ["Absolute beginner", "Beginner", "Intermediate"],
        index=0,
    )
    style = st.selectbox(
        "Explanation style",
        ["Like I'm 2", "Beginner", "Upskill"],
        index=1,
    )

    st.divider()
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

    st.divider()
    st.subheader("Model setup")
    st.write("This app defaults to local Ollama.")

    if st.button("Check model connection"):
        try:
            result = check_connection()
            st.success(f"Connected ✅ Model responded: {result}")
        except MentorConnectionError as exc:
            st.error(str(exc))

    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    if st.button("List local Ollama models"):
        try:
            models = list_ollama_models(ollama_base_url)
            if models:
                st.success("Found models:\n- " + "\n- ".join(models))
            else:
                st.warning("No local models found. Run: `ollama pull llama3.2:3b`")
        except MentorConnectionError as exc:
            st.error(str(exc))


left_learning, right_learning = st.columns(2, gap="large")

with left_learning:
    st.subheader("Tutor Chat")
    st.caption("Ask your Python tutor")
    question = st.text_area(
        "What do you want to learn?",
        placeholder="Example: Teach me Python loops like I'm 2 years old.",
        height=120,
        key="tutor_question",
    )
    if st.button("Get Tutor Answer", type="primary", key="get_tutor_answer"):
        if not question.strip():
            st.warning("Please type a question first.")
        else:
            try:
                with st.spinner("Thinking..."):
                    answer = ask_tutor(question, style, level)
                st.session_state.chat_history.append((question, answer))
                st.markdown(answer)
                _save_memory("Tutor Chat", level, style, question, answer)
            except MentorConnectionError as exc:
                st.error(str(exc))

    if st.session_state.chat_history:
        st.markdown("### Recent Q&A")
        for idx, (q, a) in enumerate(reversed(st.session_state.chat_history[-5:]), start=1):
            st.markdown(f"**Q{idx}:** {q}")
            st.markdown(a)

with right_learning:
    st.subheader("Code Explainer")
    st.caption("Paste code to understand it")
    code_input = st.text_area(
        "Python code",
        placeholder="Paste your Python code here",
        height=240,
        key="code_input",
    )
    if st.button("Explain This Code", key="explain_code"):
        if not code_input.strip():
            st.warning("Please paste code first.")
        else:
            try:
                with st.spinner("Breaking it down..."):
                    explanation = explain_code(code_input, style, level)
                st.markdown(explanation)
                _save_memory("Code Explainer", level, style, code_input, explanation)
            except MentorConnectionError as exc:
                st.error(str(exc))

st.divider()

left_build, right_build = st.columns(2, gap="large")

with left_build:
    st.subheader("Project Ideas")
    st.caption("Get AI + Python project ideas")
    interests = st.text_input(
        "What are you interested in?",
        placeholder="Example: health, productivity, finance, sports",
        key="project_interests",
    )
    if st.button("Suggest Projects", key="suggest_projects"):
        if not interests.strip():
            st.warning("Please add at least one interest.")
        else:
            try:
                with st.spinner("Generating ideas..."):
                    suggestions = suggest_projects(interests, level, style)
                st.markdown(suggestions)
                _save_memory("Project Ideas", level, style, interests, suggestions)
            except MentorConnectionError as exc:
                st.error(str(exc))

with right_build:
    st.subheader("Build Planner")
    st.caption("Turn your app idea into a build plan")
    app_idea = st.text_area(
        "Describe your app idea",
        placeholder="Example: I want a chatbot that teaches Python while I build mini tools.",
        height=140,
        key="build_idea",
    )

    if st.button("Create Build Plan", key="create_build_plan"):
        if not app_idea.strip():
            st.warning("Please describe your app idea first.")
        else:
            try:
                with st.spinner("Planning your roadmap..."):
                    plan = build_plan(app_idea, level, style)
                st.markdown(plan)
                _save_memory("Build Planner", level, style, app_idea, plan)
            except MentorConnectionError as exc:
                st.error(str(exc))

st.divider()

with st.expander("🧠 Memory (History Database)"):
    st.caption("Saved locally in mentor_memory.db so you can revisit previous chats and ideas anytime.")
    memory_category = st.selectbox(
        "Filter memory by type",
        ["All", "Tutor Chat", "Code Explainer", "Project Ideas", "Build Planner"],
        index=0,
        key="memory_category",
    )
    memory_limit = st.slider("How many entries to show", min_value=5, max_value=100, value=25, step=5)

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if st.button("Refresh Memory", key="refresh_memory"):
            st.rerun()
    with col_b:
        if st.button("Delete All Memory", key="delete_memory"):
            _delete_all_memories()
            st.success("All saved memory entries were deleted.")
            st.rerun()

    memory_rows = _load_memories(memory_category, memory_limit)
    if not memory_rows:
        st.info("No saved memory yet. Ask the tutor or generate ideas to start building history.")
    else:
        for entry_id, created_at, category, entry_level, entry_style, user_input, assistant_output in memory_rows:
            st.markdown(
                f"**#{entry_id} · {category}**  \n"
                f"*{created_at} UTC · Level: {entry_level} · Style: {entry_style}*"
            )
            st.markdown(f"**You:** {user_input}")
            st.markdown(f"**Mentor:** {assistant_output}")
            st.divider()

st.caption("Built for a team of one. Ship one tiny feature daily 🚀")
