# Python Mentor Platform (Local Ollama First)

A beginner-friendly AI chatbot platform that teaches you Python while you build your own apps.

## What you can do

- Ask Python questions and get explanations in your style:
  - `Like I'm 2`
  - `Beginner`
  - `Upskill`
- Paste code and get a line-by-line explanation.
- Get AI + Python project ideas matched to your level.
- Turn app ideas into a realistic 7-day build plan.
- Use a split-screen dashboard layout:
  - Tutor Chat + Code Explainer side by side
  - Project Ideas + Build Planner side by side
- Save history in a local memory database (`mentor_memory.db`) and browse old chats/ideas later.

## Built for your setup (GTX 1650 / 4GB VRAM)

This app defaults to **local Ollama** so you can run without needing cloud inference for every request.

Recommended starter model for your hardware:

- `llama3.2:3b`

Dependency baseline (verified on **March 28, 2026**):

- `streamlit==1.55.0`
- `openai==2.30.0`
- `python-dotenv==1.2.2`

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

- `app.py` — Streamlit UI and user flows
- `mentor_engine.py` — LLM provider logic and tutor functions
- `.env.example` — local-first settings
- `requirements.txt` — dependencies
- `mentor_memory.db` — created automatically after first run; stores saved tutor/code/project/plan history


## Dashboard smoke test (run multiple times)

To verify the dashboard starts correctly, run the smoke test script more than once:

```bash
./scripts/smoke_dashboard.sh app.py 8765
./scripts/smoke_dashboard.sh app.py 8766
```

Each run checks both the Streamlit health endpoint and the root page.

---

## If your laptop still shows the old version

Run these commands from your project folder:

```bash
git status
git branch --show-current
git pull
source .venv/bin/activate
pip install -r requirements.txt
streamlit cache clear
streamlit run app.py
```

In the app header, confirm you see the current release label:

- `App release: 2026-03-28-memory-v2`

### If you are **not using Git** (downloaded ZIP)

1. Download the latest ZIP of the project.
2. Extract it to a **new folder** (do not overwrite blindly).
3. Copy your old `.env` file into the new folder (if you customized keys/settings).
4. (Optional) Copy `mentor_memory.db` from old folder to keep your saved history.
5. Open terminal in the new folder and run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit cache clear
streamlit run app.py
```

6. Confirm the app header shows:
   - `App release: 2026-03-28-memory-v2`
