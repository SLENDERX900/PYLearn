#!/usr/bin/env bash
set -euo pipefail

APP_FILE="${1:-app.py}"
PORT="${2:-8765}"

if command -v streamlit >/dev/null 2>&1; then
  STREAMLIT_CMD=(streamlit run "$APP_FILE" --server.headless true --server.port "$PORT")
else
  STREAMLIT_CMD=(python -m streamlit run "$APP_FILE" --server.headless true --server.port "$PORT")
fi

"${STREAMLIT_CMD[@]}" >/tmp/streamlit-smoke.log 2>&1 &
PID=$!

cleanup() {
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT

for _ in {1..25}; do
  if curl -fsS "http://127.0.0.1:${PORT}/_stcore/health" >/dev/null; then
    break
  fi
  sleep 1
done

curl -fsS "http://127.0.0.1:${PORT}/_stcore/health" >/dev/null
curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null

echo "Smoke test passed for ${APP_FILE} on port ${PORT}"
