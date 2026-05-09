# Engineering: optimization, performance, error handling

This document explains how the code is engineered to be fast, cheap,
and resilient — three rubric concerns at once.

## Code optimization

| Optimization | Where | Why it matters |
|---|---|---|
| **SHA1 keyed payload caches** | `adversarial/data/fake_news/`, `adversarial/data/coord_disinfo/` | Hash includes (case_id, ticker, date, direction, model, variant). Re-running an experiment with the same parameters is **byte-identical and free** — no second LLM call. |
| **Runtime monkey-patch overlays, no fork of upstream** | `attacks/news_injection.py`, `defenses/skeptic_agent.py`, `defenses/provenance_pm.py`, `defenses/anomaly_filter.py` | One process can flip attack and defense on/off via `enable()` / `disable()`. The 1,210-trial campaign runs in the **same Python process** without rebuilding the framework. |
| **Deterministic A5 generation** | `attacks/memory_poisoning.py:build_poison_pack_v2` | Pure template + `random.Random(seed)`. Zero LLM cost, zero network, deterministic across machines. Same `seed` ⇒ byte-identical 8 entries. |
| **Lazy Skeptic / Anomaly invocation** | `demo/skeptic_runner.py`, `demo/ui_components.py` | The demo only invokes the LLM on a button click — never on tab switch or sidebar interaction. Streamlit reruns are cheap. |

## Performance optimization

| Bottleneck | Mitigation |
|---|---|
| Streamlit Cloud cold start (1 GB RAM, no GPU) | (a) `yfinance` is **lazy-imported** inside `judges/stealth.py:fetch_baseline()` — the deployed app never pulls it because the baseline corpus ships in the repo. (b) FinBERT inference is **never run live** in the deployed app; the 3 sample-input scores are precomputed and shipped as `CACHED_FINBERT_SCORES`. |
| 5–20 s LLM call blocks Streamlit's single-thread event loop | LLM submissions go through a module-level `concurrent.futures.ThreadPoolExecutor` (`demo/attack_runner.py:_ASYNC_EXECUTOR`). The user can switch attack panels while a generation is in flight, then return to find the result; no manual refresh needed (Streamlit naturally reruns on tab switch). |
| 1,210 trial JSONs × 24 MB on disk | The demo reads cached payloads on demand (no upfront load), keeping deployment startup near-instant. |
| Repeated bigram JS divergence computation | `judges/stealth.py` caches the real-news baseline corpus on disk after first computation. |

## Robust error handling

| Failure mode | Handling |
|---|---|
| **LLM refusal during fake-news generation** ("I can't help with that…") | `news_rewriter._looks_like_refusal()` heuristic detects refusal prefixes at *both* load and generate time. Refusals are **never persisted** to the cache — they are quarantined to a `*.refusal.json` sibling so a future run regenerates without silently injecting "I'm sorry" into the agent context. |
| **LLM-Judge QC failure** | Up to 3 generation attempts; the judge's `issues` are fed back into the next prompt as `extra_constraints`. After 3 failures the last attempt is persisted with `qc_verdict="fail"` so the campaign analysis can downweight it. |
| **JSON parse failure on cross-channel output** | `coordinated_disinfo.generate()` raises `ValueError` with the first 200 raw chars of the LLM response, so the operator can see exactly what the model returned. The demo catches this and shows a friendly fallback message. |
| **`OPENAI_API_KEY` cross-session leak on Streamlit Cloud** | The deployed app **never writes `os.environ` from user input**. The user-pasted key lives in `st.session_state["user_api_key"]` (per-browser-session), and the runners use a `_scoped_openai_key` context manager that sets the env var only for the duration of the LLM call, then restores. The deployer's secret-set env key is captured *once* at module import (`DEPLOYER_API_KEY` snapshot) so a runtime mutation can't masquerade as a deployer key. |
| **Non-UTF-8 default filesystem encoding (Streamlit Cloud's minimal Linux image)** | Every cache I/O explicitly passes `encoding="utf-8"` to `Path.write_text()` / `Path.read_text()`. Avoids `'ascii' codec can't encode character '—'` when LLMs return em-dashes. |
| **Missing optional dependency (`yfinance`, `torch`, `transformers`)** | `yfinance` is lazy-imported (deploy doesn't need it because baseline is on disk); FinBERT is graceful — when `torch` isn't installed, `stealth.score()` returns `stealth_score_finbert=None` and the demo falls back to the lexical-only path or a cached FinBERT score. |
| **Vendor lookup failure for unknown ticker** | The demo restricts the dropdown to 5 tickers with shipped baseline; for live experiments, `route_to_vendor` returns `None` cleanly so the agent fails gracefully rather than crashing. |

## Where to look in the code

- `_scoped_openai_key`, `_ASYNC_EXECUTOR` — `adversarial/demo/attack_runner.py`
- `DEPLOYER_API_KEY`, `get_session_api_key` — `adversarial/demo/ui_components.py`
- Refusal detection — `adversarial/attacks/news_rewriter.py:_looks_like_refusal`, `_load_cache`
- Lazy yfinance — `adversarial/judges/stealth.py:fetch_baseline`
- Cached FinBERT — `adversarial/demo/skeptic_runner.py:CACHED_FINBERT_SCORES`
