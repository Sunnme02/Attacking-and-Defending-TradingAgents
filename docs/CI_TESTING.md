# Continuous integration & testing

## CI

GitHub Actions runs on every push to `main` and every PR
([workflow file](../.github/workflows/tests.yml)). Each run, on
Python **3.10** and **3.11**, executes:

| Step | What it does |
|---|---|
| `pip install -e .` | Installs the upstream framework (verifies `pyproject.toml` + lockable deps) |
| `pytest tests/test_adversarial_*.py --cov=adversarial` | Runs the **19 unit tests** with coverage report |
| `python -m adversarial.reproduce_minimal` | Runs the **7 end-to-end repro checks** (the same script you run locally to verify the install) |
| Upload coverage | Saves `coverage.xml` as a build artifact |

The status badge in the top-level README links directly to the Actions
tab — green means the latest commit on `main` passed all unit tests
AND the minimal-reproduction script on both Python versions.

> **No secrets needed.** All CI checks are offline / cached — they
> exercise the entire pipeline without an OpenAI API key. Live LLM
> generation is only invoked when a user explicitly triggers it from
> the demo.

## Test coverage

19 unit tests + 7 end-to-end checks across the adversarial codebase:

| Module under test | Test file | What it covers |
|---|---|---|
| Memory Poisoning attack (`attacks/memory_poisoning.py`) | `tests/test_adversarial_memory_poisoning.py` | Determinism under fixed seed; 5+3 cap; cross-ticker pool exclusion; direction → rating mapping; rendered-entry schema; directive `LESSON LEARNED` phrasing; alpha calibration range. **9 tests.** |
| Runtime injection plumbing for the news / social attacks (`attacks/news_injection.py`) | `tests/test_adversarial_news_injection.py` | enable/disable idempotence; uppercase-ticker registry; clear; patched-route gating by `method=='get_news'`; HEADER_NEWS vs HEADER_SOCIAL switching; pass-through when no payload registered. **6 tests.** |
| Anomaly Filter defense + stealth metric (`defenses/anomaly_filter.py`, `judges/stealth.py`) | `tests/test_adversarial_anomaly_filter.py` | Paragraph splitter min-length filter; injection-header boundary preservation; empty/None handling; lexical-backend ordering on real-style vs retail-spam text. **4 tests.** |
| End-to-end (imports, cache integrity, score ordering, all live runners) | `adversarial/reproduce_minimal.py` | **7 checks** that run as part of CI |

**Coverage** of the runtime adversarial code path is reported by
`pytest --cov=adversarial` and uploaded as a build artifact on every
CI run (download from the Actions page).

**What's intentionally not unit-tested:** the live LLM-driven runners
(`run_fake_news_live`, `run_cross_channel_live`, `run_skeptic_live`)
require a real API key and are exercised end-to-end via the demo and
the experiment-driver scripts.
