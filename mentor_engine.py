from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

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

    return OpenAI(api_key=cfg.api_key, base_url=_normalize_base_url(cfg.base_url))


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

    try:
        result = client.chat.completions.create(
            model=cfg.model,
            temperature=0,
            messages=[
                {"role": "system", "content": "You are a healthcheck bot."},
                {"role": "user", "content": "Reply with only: ok"},
            ],
        )
    except Exception as exc:  # noqa: BLE001
        raise MentorConnectionError(
            f"Connection failed for provider={cfg.provider}, model={cfg.model}."
        ) from exc

    text = result.choices[0].message.content or ""
    return text.strip() or "ok"


def _safe_chat_completion(system_prompt: str, user_prompt: str, temperature: float) -> str:
    cfg = load_config()
    client = _build_client(cfg)

    try:
        resp = client.chat.completions.create(
            model=cfg.model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except Exception as exc:  # noqa: BLE001
        raise MentorConnectionError(
            f"LLM request failed for provider={cfg.provider}, model={cfg.model}."
        ) from exc

    return resp.choices[0].message.content or "No response from model."


def ask_tutor(question: str, style: ExplainStyle, level: str) -> str:
    sys_prompt = (
        "You are PythonMentor, a patient Python teacher and app-building coach. "
        "Your goal is to teach while building confidence. "
        f"Student level: {level}. "
        f"Style instruction: {_style_instruction(style)} "
        "Always include: (1) direct answer, (2) tiny example, (3) one practice task."
    )
    return _safe_chat_completion(sys_prompt, question, temperature=0.4)


def explain_code(code: str, style: ExplainStyle, level: str) -> str:
    sys_prompt = (
        "You explain Python code for learning. "
        f"Student level: {level}. "
        f"Style instruction: {_style_instruction(style)} "
        "Use this structure: What it does, Line-by-line idea, Key concepts, Common mistakes, One improvement."
    )
    user_prompt = f"Explain this Python code:\n\n```python\n{code}\n```"
    return _safe_chat_completion(sys_prompt, user_prompt, temperature=0.3)


def suggest_projects(interests: str, level: str, style: ExplainStyle) -> str:
    sys_prompt = (
        "You generate beginner-friendly AI+Python project ideas. "
        f"Student level: {level}. "
        f"Style instruction: {_style_instruction(style)} "
        "Give exactly 5 ideas. For each: Goal, Why it helps learning, Stack, MVP steps, Stretch goal."
    )
    user_prompt = f"My interests: {interests}"
    return _safe_chat_completion(sys_prompt, user_prompt, temperature=0.7)


def build_plan(idea: str, level: str, style: ExplainStyle) -> str:
    sys_prompt = (
        "You are a product+engineering mentor for solo builders. "
        f"Student level: {level}. "
        f"Style instruction: {_style_instruction(style)} "
        "Return: Problem statement, User flow, MVP feature list, 7-day roadmap, Risks, First coding step today."
    )
    return _safe_chat_completion(sys_prompt, idea, temperature=0.5)
