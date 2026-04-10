from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from openai import APITimeoutError, OpenAI

load_dotenv()

def _request_timeout() -> float:
    return float(os.getenv("OLLAMA_REQUEST_TIMEOUT_SEC", "120"))


def resolve_model_for_tab(tab_scope: str | None) -> str:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower().strip()
    if provider == "openai":
        if tab_scope == "learning_hub":
            return os.getenv("OPENAI_MODEL_LEARNING_HUB") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        if tab_scope == "project_builder":
            return os.getenv("OPENAI_MODEL_PROJECT_BUILDER") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if tab_scope == "learning_hub":
        return os.getenv("OLLAMA_MODEL_LEARNING_HUB") or os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    if tab_scope == "project_builder":
        return os.getenv("OLLAMA_MODEL_PROJECT_BUILDER") or os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    return os.getenv("OLLAMA_MODEL", "llama3.2:3b")


ExplainStyle = Literal["Like I'm 2", "Beginner", "Upskill"]


@dataclass
class MentorConfig:
    provider: str
    model: str
    api_key: str | None
    base_url: str | None


class MentorConnectionError(RuntimeError):
    """Raised when the configured LLM backend cannot be reached."""


def load_config() -> MentorConfig:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower().strip()

    if provider == "ollama":
        return MentorConfig(
            provider="ollama",
            model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
            api_key="ollama",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        )

    return MentorConfig(
        provider="openai",
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )


def _normalize_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None
    return base_url.rstrip("/")


def _build_client(cfg: MentorConfig) -> OpenAI:
    if cfg.provider == "openai" and not cfg.api_key:
        raise MentorConnectionError(
            "OPENAI_API_KEY is missing. Add it to your .env or switch LLM_PROVIDER=ollama."
        )

    return OpenAI(api_key=cfg.api_key, base_url=_normalize_base_url(cfg.base_url), timeout=_request_timeout())


def _style_instruction(style: ExplainStyle) -> str:
    if style == "Like I'm 2":
        return (
            "Explain with super simple words, very short sentences, and friendly daily-life examples. "
            "Avoid technical terms unless you define them simply."
        )
    if style == "Beginner":
        return (
            "Explain for someone with no coding background using clear step-by-step logic "
            "and one small example."
        )
    return (
        "Explain like a practical coach helping someone upskill fast. "
        "Include best practices, tradeoffs, and one short challenge task."
    )


def list_ollama_models(base_url: str) -> list[str]:
    """Returns locally available Ollama models from /api/tags."""
    host = base_url.replace("/v1", "").rstrip("/")
    endpoint = f"{host}/api/tags"
    req = Request(endpoint, method="GET")

    try:
        with urlopen(req, timeout=5) as resp:
            body = resp.read().decode("utf-8")
        payload = json.loads(body)
        return [m.get("name", "") for m in payload.get("models", []) if m.get("name")]
    except (URLError, HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        raise MentorConnectionError(
            "Could not read models from Ollama. Confirm Ollama is running: `ollama serve`."
        ) from exc


def check_connection() -> str:
    cfg = load_config()
    client = _build_client(cfg)
    model = resolve_model_for_tab("learning_hub")

    try:
        result = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": "You are a healthcheck bot."},
                {"role": "user", "content": "Reply with only: ok"},
            ],
        )
    except Exception as exc:  # noqa: BLE001
        raise MentorConnectionError(
            f"Connection failed for provider={cfg.provider}, model={model}."
        ) from exc

    text = result.choices[0].message.content or ""
    return text.strip() or "ok"


def _safe_chat_completion(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    *,
    tab_scope: str | None = None,
) -> str:
    cfg = load_config()
    model = resolve_model_for_tab(tab_scope)
    client = _build_client(cfg)

    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except APITimeoutError as exc:
        raise MentorConnectionError(
            f"LLM request timed out after {_request_timeout()}s (model={model}). "
            "Try OLLAMA_REQUEST_TIMEOUT_SEC, a smaller model, or shorter prompts."
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise MentorConnectionError(
            f"LLM request failed for provider={cfg.provider}, model={model}: {exc!s}"
        ) from exc

    return resp.choices[0].message.content or "No response from model."


def _compose_system(base_system: str, memory_context: str | None) -> str:
    if memory_context and memory_context.strip():
        return (
            base_system
            + "\n\n### Persistent session log (SQLite — use for continuity only)\n"
            "Treat the following as the only stored history. Do not claim memory of anything "
            "not shown here. Stay consistent with prior answers when relevant.\n\n"
            + memory_context.strip()
        )
    return (
        base_system
        + "\n\n### Persistent session log\n"
        "No stored history yet (or the user cleared memory). Do not imply you recall prior turns."
    )


def ask_tutor(
    question: str,
    style: ExplainStyle,
    level: str,
    memory_context: str | None = None,
) -> str:
    base = (
        "You are PythonMentor, a patient Python teacher and app-building coach. "
        "Your goal is to teach while building confidence. "
        "If the user pastes code or asks to re-explain something, answer in chat (do not assume a separate explainer panel). "
        f"Student level: {level}. "
        f"Style instruction: {_style_instruction(style)} "
        "Always include: (1) direct answer, (2) tiny example, (3) one practice task."
    )
    return _safe_chat_completion(_compose_system(base, memory_context), question, temperature=0.4, tab_scope="learning_hub")


def explain_code(code: str, style: ExplainStyle, level: str) -> str:
    sys_prompt = (
        "You explain Python code for learning. "
        f"Student level: {level}. "
        f"Style instruction: {_style_instruction(style)} "
        "Use this structure: What it does, Line-by-line idea, Key concepts, Common mistakes, One improvement."
    )
    user_prompt = f"Explain this Python code:\n\n```python\n{code}\n```"
    return _safe_chat_completion(sys_prompt, user_prompt, temperature=0.3, tab_scope="learning_hub")


def suggest_projects(
    interests: str,
    level: str,
    style: ExplainStyle,
    memory_context: str | None = None,
) -> str:
    base = (
        "You generate beginner-friendly AI+Python project ideas. "
        f"Student level: {level}. "
        f"Style instruction: {_style_instruction(style)} "
        "Give exactly 5 ideas. For each: Goal, Why it helps learning, Stack, MVP steps, Stretch goal."
    )
    user_prompt = f"My interests: {interests}"
    return _safe_chat_completion(_compose_system(base, memory_context), user_prompt, temperature=0.7, tab_scope="project_builder")


def build_plan(
    idea: str,
    level: str,
    style: ExplainStyle,
    memory_context: str | None = None,
) -> str:
    base = (
        "You are a product+engineering mentor for solo builders. "
        f"Student level: {level}. "
        f"Style instruction: {_style_instruction(style)} "
        "Return clear sections with headings: "
        "Problem statement, User flow, MVP feature list, "
        "Project steps (numbered 1..n with concrete actions), "
        "Phased milestones (no fixed day count unless the user asks for a schedule), Risks, Suggested next steps, Optional timeboxed plan (only if the user requests dates)."
    )
    return _safe_chat_completion(_compose_system(base, memory_context), idea, temperature=0.5, tab_scope="project_builder")


def generate_project_code(
    idea: str,
    level: str,
    style: ExplainStyle,
    memory_context: str | None = None,
) -> str:
    base = (
        "You are a senior Python mentor. Output ONLY raw Python source code (no markdown fences). "
        "Produce a minimal but runnable starter for the student's app idea. "
        "Prefer the standard library; if a third-party package is needed, add a comment at the top. "
        "Include short docstrings, helpful comments, and if appropriate `if __name__ == \"__main__\":`. "
        f"Student level: {level}. Style: {_style_instruction(style)}"
    )
    return _safe_chat_completion(_compose_system(base, memory_context), idea, temperature=0.45, tab_scope="project_builder")


def assist_snippet(
    mode: Literal["explain", "modify"],
    selected_code: str,
    user_message: str,
    full_code_context: str,
    level: str,
    style: ExplainStyle,
    memory_context: str | None = None,
) -> str:
    if mode == "explain":
        base = (
            "You explain Python snippets in context for learning. "
            f"Student level: {level}. Style: {_style_instruction(style)} "
            "Cover: what the snippet does, how it fits the surrounding code, pitfalls, one improvement tip."
        )
    else:
        base = (
            "You help modify Python code. "
            f"Student level: {level}. Style: {_style_instruction(style)} "
            "Follow the user's request. Prefer showing the changed snippet with brief comments; "
            "if a full-file rewrite is clearer, provide the full file as Python only (no markdown fences)."
        )
    user_prompt = (
        f"Mode: {mode}\n"
        f"User request: {user_message}\n\n"
        f"Selected snippet:\n```python\n{selected_code}\n```\n\n"
        f"Full project code (context):\n```python\n{full_code_context[:12000]}\n```"
    )
    return _safe_chat_completion(_compose_system(base, memory_context), user_prompt, temperature=0.35, tab_scope="project_builder")


def strip_leading_code_fence(text: str) -> str:
    """Remove a single outer ``` / ```python fence if the model wrapped output."""
    t = text.strip()
    if not t.startswith("```"):
        return text
    lines = t.split("\n")
    if not lines:
        return text
    lines = lines[1:]
    while lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
