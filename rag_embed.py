"""Embedding + RAG retrieval (Ollama OpenAI-compatible embeddings API)."""

from __future__ import annotations

import json
import os

import numpy as np
from dotenv import load_dotenv
from openai import APITimeoutError, OpenAI

load_dotenv()


def _timeout_sec() -> float:
    return float(os.getenv("OLLAMA_REQUEST_TIMEOUT_SEC", "120"))


def _embed_model() -> str:
    return os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")


def _embed_client() -> OpenAI:
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    return OpenAI(api_key="ollama", base_url=base, timeout=_timeout_sec())


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = _embed_client()
    try:
        resp = client.embeddings.create(model=_embed_model(), input=texts)
    except APITimeoutError as exc:
        raise RuntimeError(f"Embedding timed out after {_timeout_sec()}s") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Embedding failed: {exc}") from exc
    return [list(d.embedding) for d in resp.data]


def _chunk_text(text: str, max_chars: int = 900, overlap: int = 120) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    i = 0
    while i < len(text):
        chunks.append(text[i : i + max_chars])
        i += max_chars - overlap
        if i <= 0:
            i = len(text)
    return chunks


def _to_blob(vec: list[float]) -> bytes:
    return json.dumps(vec).encode("utf-8")


def _from_blob(blob: bytes) -> list[float]:
    return json.loads(blob.decode("utf-8"))


def upsert_memory_to_rag(
    project_id: int,
    memory_id: int,
    user_input: str,
    assistant_output: str,
) -> None:
    from memory_db import insert_rag_chunk

    combined = f"User:\n{user_input}\n\nAssistant:\n{assistant_output}"
    pieces = _chunk_text(combined)
    if not pieces:
        return
    try:
        vectors = embed_texts(pieces)
    except RuntimeError:
        return
    for piece, vec in zip(pieces, vectors, strict=False):
        insert_rag_chunk(project_id, memory_id, piece, _to_blob(vec))


def retrieve_rag_context(project_id: int, query_text: str, k: int = 8) -> str:
    from memory_db import fetch_rag_chunks_for_project

    if not query_text.strip():
        return ""
    rows = fetch_rag_chunks_for_project(project_id, limit=1500)
    if not rows:
        return ""
    try:
        qv = embed_texts([query_text.strip()])[0]
    except RuntimeError:
        return ""
    q = np.asarray(qv, dtype=np.float64)
    qn = float(np.linalg.norm(q))
    if qn < 1e-9:
        return ""
    scored: list[tuple[float, str]] = []
    for r in rows:
        try:
            v = np.asarray(_from_blob(bytes(r["embedding"])), dtype=np.float64)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
        vn = float(np.linalg.norm(v))
        if vn < 1e-9:
            continue
        sim = float(np.dot(q, v) / (qn * vn))
        scored.append((sim, str(r["chunk_text"])))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: max(1, k)]
    return "\n---\n".join(t for _, t in top)
