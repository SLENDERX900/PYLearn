# PYLearn : Python Mentor Platform

A beginner-friendly AI chatbot platform that teaches you Python while you build your own apps.

---

## About Python Tutor and Builder

**Live UI Preview:** [https://pythontutorandbuilder.streamlit.app/](https://pythontutorandbuilder.streamlit.app/)

> **⚠️ Note on the Live Demo:** The link above is provided as a **Showcase of the User Interface and Design**. Because this platform is built for privacy and performance using **Local Ollama**, the AI tutoring features require a local backend to function. To experience the full power of the AI mentor, please follow the **Quick Start** guide below to run it on your own machine.

### 🚀 Key Features

* **Interactive UI Showcase:** Explore the dashboard layout, section controls, and the integrated Python playground interface.
* **Privacy-First AI (Local-First):** Once set up locally, the app uses Ollama to provide real-time logic debugging and concept explanations without your data ever leaving your device.
* **Zero-Cloud Dependency:** Designed for developers and students who want a powerful AI coding assistant that works entirely offline.

### 🛠️ Make it Your Own

This project is intended to be a **self-hosted personal mentor**. By running the app locally, you gain full control over the AI models used (e.g., `Llama 3.2`), your own persistent learning memory, and a secure sandbox for code execution.

---

## What you can do

The app is a **single dashboard** with a **main section** control at the top (same screen — no separate Streamlit “pages” in the sidebar):

| Section | Purpose |
|---------|---------|
| **Learning Hub** | **Tutor chat** (left) + **interactive Python playground** (right): run code in a restricted sandbox, explain the full editor, or paste a snippet to explain or modify it in context |
| **Project Builder** | **Idea & planner** (left): roadmap, numbered **project steps**, optional idea spark. **Codebase & assistant** (right): generated starter code and a **snippet assistant** |
| **Memory** | **History database** — filter, refresh, or clear local history |

Explanation styles:

- `Like I'm 2`
- `Beginner`
- `Upskill`

### Local history (SQLite)

Successful tutor, sandbox, project, and assistant responses are saved to **`mentor_memory.db`** (created on first run). You can create **multiple project workspaces**; history and **RAG embeddings** are scoped per project. Pull **`nomic-embed-text`** (or set `OLLAMA_EMBED_MODEL`) for semantic retrieval.

## Built for your setup 

This app defaults to **local Ollama** so you can run without needing cloud inference for every request.

Recommended starter model for your hardware:

- `llama3.2:3b`

Dependency baseline (verified on **March 28, 2026**):

- `streamlit==1.55.0`
- `openai==2.30.0`
- `python-dotenv==1.2.2`
- `numpy` (RAG similarity)

If it feels slow, keep prompts short and ask for short responses.

---

## Quick start

### 1) Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Ensure Ollama is running

```bash
ollama serve
```

In another terminal, pull a model:

```bash
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

### 3) Configure env

```bash
cp .env.example .env
```

Default `.env` is already local-first (`LLM_PROVIDER=ollama`).

### 4) Run the app

```bash
streamlit run app.py
```

Use the main section control to move between Learning Hub, Project Builder, and Memory.

---

## In-app checks

From the sidebar you can:

- click **Check model connection**
- click **List local Ollama models**

If either fails, confirm:

- Ollama daemon is running (`ollama serve`)
- your base URL is correct (`http://localhost:11434/v1`)
- your model exists locally (`ollama list`)

---

## Files

- `app.py` — Single dashboard (main section: Learning Hub, Project Builder, Memory)
- `dashboard_tabs.py` — Tab content for Learning Hub and Project Builder
- `shared_ui.py` — Shared sidebar, dependency panel, memory UI
- `sandbox_run.py` — Restricted Python runner for the playground
- `memory_db.py` — SQLite helpers for `mentor_memory.db`, projects, and RAG chunks
- `rag_embed.py` — Embeddings and retrieval (Ollama OpenAI-compatible API)
- `project_workspace.py` — Project switcher UI
- `mentor_engine.py` — LLM provider logic and tutor functions
- `.env.example` — local-first settings
- `requirements.txt` — dependencies
- `mentor_memory.db` — auto-created local history database (after first save)


## Dashboard smoke test (run multiple times)

To verify the dashboard starts correctly, run the smoke test script more than once:

```bash
./scripts/smoke_dashboard.sh app.py 8765
./scripts/smoke_dashboard.sh app.py 8766
```

Each run checks both the Streamlit health endpoint and the root page.
