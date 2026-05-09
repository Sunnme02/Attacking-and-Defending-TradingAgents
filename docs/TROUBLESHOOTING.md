# Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `OPENAI_API_KEY is not set` | `.env` missing or not loaded | `cp .env.example .env`, fill in the key, restart your shell |
| `ModuleNotFoundError: tradingagents` | Upstream package not installed | `pip install -e .` from the repo root |
| `ModuleNotFoundError: streamlit` (or `pandas` / `plotly`) | Demo deps not installed | `pip install -r adversarial/demo/requirements.txt` |
| Streamlit app blank / "no trials" | You launched from a subdirectory | Run from the repo root: `streamlit run adversarial/demo/app.py` |
| Skeptic call hangs > 30 s | Network / API rate-limit | Toggle "Use cached example" in the Defense lab to fall back to a recorded verdict |
| FinBERT backend errors | `torch` / `transformers` not installed | `pip install torch transformers`, or use `--d4-backend lexical` |
| Anthropic generator errors when running the fake-news generator | `ANTHROPIC_API_KEY` not set | Pass `--model gpt-4o-mini` to the rewriter, or set the key in `.env` |
| `vendor lookup failed` for a ticker | Picked a ticker without a yfinance baseline | Stick to PLTR / SNOW / HOOD / NVDA / BIIB (the studied set) |
