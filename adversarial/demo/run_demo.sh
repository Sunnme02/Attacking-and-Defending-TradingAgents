#!/usr/bin/env bash
# Launcher for the adversarial-robustness demo.
# Usage:
#   ./adversarial/demo/run_demo.sh            # default port 8765
#   PORT=8501 ./adversarial/demo/run_demo.sh
#
# Requires: streamlit, pandas, plotly, langchain-openai (see requirements.txt).
# For live Skeptic invocation: export OPENAI_API_KEY before running.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

PORT="${PORT:-8765}"

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "⚠️  OPENAI_API_KEY not set — Skeptic 'live' will fall back to cache."
  echo "   To enable live calls:  export OPENAI_API_KEY=sk-..."
  echo
fi

echo "▶ Launching demo on http://localhost:${PORT}"
exec streamlit run adversarial/demo/app.py \
  --server.headless false \
  --server.port "${PORT}" \
  --server.runOnSave false \
  --browser.gatherUsageStats false
