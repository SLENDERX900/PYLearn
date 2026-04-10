"""Local SQLite persistence for mentor interaction history, projects, and RAG chunks."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "mentor_memory.db"

CATEGORIES = (
    "tutor_chat",
    "code_explainer",
    "project_ideas",
    "build_planner",
    "project_code",
    "snippet_assistant",
)

TAB_LEARNING_HUB = "learning_hub"
TAB_PROJECT_BUILDER = "project_builder"

TAB_SCOPE_LABELS = {
    TAB_LEARNING_HUB: "Learning Hub",
    TAB_PROJECT_BUILDER: "Project Builder",
}

DEFAULT_PROJECT_ID = 1


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _ensure_tab_scope_column(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(memory)").fetchall()}
    if "tab_scope" in cols:
        return
    conn.execute(
        "ALTER TABLE memory ADD COLUMN tab_scope TEXT NOT NULL DEFAULT 'learning_hub'"
    )
    conn.execute(
        "UPDATE memory SET tab_scope = 'learning_hub' WHERE tab_scope IS NULL OR tab_scope = ''"
    )


def _ensure_projects_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    row = conn.execute("SELECT COUNT(*) AS c FROM projects").fetchone()
    if row and int(row["c"]) == 0:
        ts = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO projects (id, name, created_at) VALUES (?, ?, ?)",
            (DEFAULT_PROJECT_ID, "Default", ts),
        )


def _ensure_project_id_column(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(memory)").fetchall()}
    if "project_id" in cols:
        return
    _ensure_projects_table(conn)
    conn.execute(
        "ALTER TABLE memory ADD COLUMN project_id INTEGER NOT NULL DEFAULT 1"
    )


def _ensure_rag_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS rag_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            memory_id INTEGER NOT NULL,
            chunk_text TEXT NOT NULL,
            embedding BLOB NOT NULL,
            FOREIGN KEY (memory_id) REFERENCES memory(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rag_project ON rag_chunks(project_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_rag_memory ON rag_chunks(memory_id)"
    )


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                level TEXT NOT NULL,
                style TEXT NOT NULL,
                user_input TEXT NOT NULL,
                assistant_output TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_category ON memory(category)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_timestamp ON memory(timestamp)")
        _ensure_tab_scope_column(conn)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_tab_scope ON memory(tab_scope)"
        )
        _ensure_project_id_column(conn)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memory_project ON memory(project_id)"
        )
        _ensure_rag_table(conn)
        conn.commit()


def list_projects() -> list[dict[str, str | int]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, name, created_at FROM projects ORDER BY id ASC"
        ).fetchall()
    return [{k: r[k] for k in r.keys()} for r in rows]


def create_project(name: str) -> int:
    ts = datetime.now(timezone.utc).isoformat()
    nm = name.strip() or "Untitled"
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, created_at) VALUES (?, ?)",
            (nm, ts),
        )
        conn.commit()
        return int(cur.lastrowid)


def delete_project(project_id: int) -> tuple[int, int]:
    if project_id == DEFAULT_PROJECT_ID:
        raise ValueError("Cannot delete the default project.")
    with _connect() as conn:
        r1 = conn.execute(
            "DELETE FROM rag_chunks WHERE project_id = ?", (project_id,)
        ).rowcount
        r2 = conn.execute(
            "DELETE FROM memory WHERE project_id = ?", (project_id,)
        ).rowcount
        conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
        return int(r2 or 0), int(r1 or 0)


def save_memory(
    category: str,
    level: str,
    style: str,
    user_input: str,
    assistant_output: str,
    *,
    tab_scope: str,
    project_id: int = DEFAULT_PROJECT_ID,
    when: datetime | None = None,
) -> int:
    ts = (when or datetime.now(timezone.utc)).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO memory (
                category, level, style, user_input, assistant_output, timestamp, tab_scope, project_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                category,
                level,
                style,
                user_input,
                assistant_output,
                ts,
                tab_scope,
                project_id,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def insert_rag_chunk(
    project_id: int,
    memory_id: int,
    chunk_text: str,
    embedding_blob: bytes,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO rag_chunks (project_id, memory_id, chunk_text, embedding)
            VALUES (?, ?, ?, ?)
            """,
            (project_id, memory_id, chunk_text, embedding_blob),
        )
        conn.commit()


def fetch_rag_chunks_for_project(project_id: int, limit: int = 2000) -> list[dict]:
    limit = max(1, min(int(limit), 5000))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, project_id, memory_id, chunk_text, embedding
            FROM rag_chunks
            WHERE project_id = ?
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
    return [{k: r[k] for k in r.keys()} for r in rows]


def fetch_memories(
    *,
    category: str | None = None,
    tab_scope: str | None = None,
    project_id: int | None = None,
    limit: int = 50,
) -> list[dict[str, str | int]]:
    limit = max(1, min(int(limit), 500))
    q = """
        SELECT id, category, level, style, user_input, assistant_output, timestamp, tab_scope, project_id
        FROM memory
    """
    conditions: list[str] = []
    params: list[object] = []
    if category and category != "all":
        conditions.append("category = ?")
        params.append(category)
    if tab_scope and tab_scope != "all":
        conditions.append("tab_scope = ?")
        params.append(tab_scope)
    if project_id is not None:
        conditions.append("project_id = ?")
        params.append(project_id)
    if conditions:
        q += " WHERE " + " AND ".join(conditions)
    q += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(q, params).fetchall()
    return [{k: r[k] for k in r.keys()} for r in rows]


def delete_memories(
    *,
    tab_scope: str | None = None,
    project_id: int | None = None,
) -> int:
    with _connect() as conn:
        conds: list[str] = []
        params: list[object] = []
        if tab_scope is not None:
            conds.append("tab_scope = ?")
            params.append(tab_scope)
        if project_id is not None:
            conds.append("project_id = ?")
            params.append(project_id)
        if conds:
            where = " AND ".join(conds)
            cur = conn.execute(f"DELETE FROM memory WHERE {where}", params)
        else:
            conn.execute("DELETE FROM rag_chunks")
            cur = conn.execute("DELETE FROM memory")
        conn.commit()
        return cur.rowcount or 0


def format_memory_context_for_llm(
    tab_scope: str,
    *,
    project_id: int | None = None,
    limit: int = 40,
    max_chars: int = 12000,
) -> str:
    rows = fetch_memories(
        category=None,
        tab_scope=tab_scope,
        project_id=project_id,
        limit=limit,
    )
    if not rows:
        return ""

    parts: list[str] = []
    total = 0
    for r in rows:
        cat = r["category"]
        ts = r["timestamp"]
        ui = str(r["user_input"])
        ao = str(r["assistant_output"])
        if len(ui) > 2000:
            ui = ui[:2000] + "â€¦"
        if len(ao) > 4000:
            ao = ao[:4000] + "â€¦"
        block = f"[{ts}] ({cat})\nUser: {ui}\nAssistant: {ao}\n"
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)

    parts.reverse()
    return "\n---\n".join(parts)


def build_llm_context(
    tab_scope: str,
    project_id: int,
    query_text: str,
    *,
    rag_k: int = 8,
    tail_limit: int = 35,
    tail_max_chars: int = 10000,
) -> str:
    from rag_embed import retrieve_rag_context

    blocks: list[str] = []
    rag = retrieve_rag_context(project_id, query_text, k=rag_k)
    if rag.strip():
        blocks.append(
            "### Retrieved notes (semantic search)\n"
            + rag.strip()
        )
    tail = format_memory_context_for_llm(
        tab_scope,
        project_id=project_id,
        limit=tail_limit,
        max_chars=tail_max_chars,
    )
    if tail.strip():
        blocks.append("### Recent exchanges (newest last within block)\n" + tail.strip())
    return "\n\n".join(blocks)
