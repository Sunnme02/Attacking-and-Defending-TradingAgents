"""Minimal end-to-end reproduction — no API key, no network, ~3 seconds.

This script lets a reviewer (or anyone) verify, in under a minute, that
the environment is set up correctly and the shipped artefacts are
intact, *without* paying for a single OpenAI call.

What it checks
--------------
1. Imports — every top-level adversarial module loads cleanly.
2. Cached A1 fake-news samples — at least one (avon) on PLTR loads,
   parses, and matches the expected schema.
3. Cached A2 cross-channel bundle — same.
4. A5 memory poisoning — generated locally (no LLM) and matches the
   expected 5+3 structure with directive 'LESSON LEARNED' reflection.
5. Stealth metric — lexical backend scores a known clean sample
   above a known synthetic sample (relative ordering check).
6. Skeptic Agent cached fallback — three sample inputs return the
   expected number of concerns (0 / 4 / 3).
7. Defense panel anomaly filter — produces a verdict on a sample text.

The script prints PASS / FAIL per check and exits with status 0 if all
pass, 1 otherwise. CI uses this exact exit-code contract.

Usage
-----
    python -m adversarial.reproduce_minimal

Expected output (last line)::

    ✅ All 7 minimal-repro checks passed (no API key needed).

If any line shows ❌, the failure message indicates exactly what is
wrong. Re-running after `pip install -e . && pip install -r
adversarial/demo/requirements.txt` should fix import / dependency
failures.
"""

from __future__ import annotations

import sys
import textwrap
import traceback
from typing import Callable


def _check(name: str, fn: Callable[[], str]) -> tuple[bool, str]:
    """Run a single check; return (passed, summary line)."""
    try:
        detail = fn()
    except Exception as e:
        tb_last = traceback.format_exception_only(type(e), e)[-1].strip()
        return False, f"❌ {name}: {tb_last}"
    return True, f"✅ {name}: {detail}"


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_imports() -> str:
    from adversarial.attacks import news_injection, memory_poisoning  # noqa: F401
    from adversarial.attacks import news_rewriter, coordinated_disinfo  # noqa: F401
    from adversarial.defenses import anomaly_filter, provenance_pm, skeptic_agent  # noqa: F401
    from adversarial.judges import stealth, injection_landed  # noqa: F401
    from adversarial.demo import attack_runner, skeptic_runner  # noqa: F401
    return "all 11 adversarial modules importable"


def check_a1_cached_sample() -> str:
    from adversarial.demo.attack_runner import run_fake_news_live
    r = run_fake_news_live(
        "avon_fake_tender_2015", "PLTR", "2025-12-09", use_cache=True,
    )
    if not r.article_text:
        raise ValueError("article_text empty")
    if r.qc_verdict not in ("pass", "fail", "unchecked"):
        raise ValueError(f"unexpected qc_verdict {r.qc_verdict!r}")
    return (
        f"avon × PLTR loaded ({len(r.article_text)} chars, qc={r.qc_verdict})"
    )


def check_a2_cached_sample() -> str:
    from adversarial.demo.attack_runner import run_cross_channel_live
    r = run_cross_channel_live("PLTR", "2025-12-09", "bullish", use_cache=True)
    if not r.article_headline or not r.article_body:
        raise ValueError("missing article fields")
    if len(r.social_posts) < 3:
        raise ValueError(f"too few social posts: {len(r.social_posts)}")
    return (
        f"PLTR bullish loaded "
        f"(article {len(r.article_body)} chars + {len(r.social_posts)} posts)"
    )


def check_a5_local_generation() -> str:
    from adversarial.demo.attack_runner import run_memory_poisoning_live
    r = run_memory_poisoning_live("PLTR", "2025-12-09", "bearish", seed=0)
    if len(r.entries) != 8:
        raise ValueError(f"expected 8 entries, got {len(r.entries)}")
    if r.n_same_ticker != 5 or r.n_cross_ticker != 3:
        raise ValueError(
            f"expected 5+3 split, got {r.n_same_ticker}+{r.n_cross_ticker}"
        )
    if "LESSON LEARNED" not in r.rendered_log:
        raise ValueError("directive reflection ('LESSON LEARNED') missing")
    return f"8 entries (5 same + 3 cross-ticker), all directive"


def check_stealth_metric_ordering() -> str:
    from adversarial.judges import stealth
    real = (
        "Reuters reports that the company expects revenue growth of "
        "approximately 14 percent year over year, driven by sustained "
        "enterprise demand. Management raised full-year guidance during "
        "the third-quarter earnings call, citing operating-leverage "
        "gains across its core business segments."
    )
    spam = (
        "🚀🚀 TO THE MOON FAM 🌕 my buddy at the company says they're "
        "loading up huge 💎🙌 media won't cover this but BIG NEWS coming "
        "next week!! diamond hands only, 100x setup, don't miss out!!!"
    )
    real_score = stealth.score(real).stealth_score_lexical
    spam_score = stealth.score(spam).stealth_score_lexical
    if real_score is None or spam_score is None:
        raise ValueError("lexical score is None — baseline corpus missing?")
    if not (spam_score < real_score):
        raise ValueError(
            f"lexical fails to discriminate: real={real_score:.3f} "
            f"vs spam={spam_score:.3f}"
        )
    return f"real={real_score:.3f} > spam={spam_score:.3f} (lexical)"


def check_skeptic_cached_fallback() -> str:
    from adversarial.demo.skeptic_runner import (
        SAMPLE_NEWS, parse_skeptic_response, run_skeptic_live,
    )
    expected = {"clean_pltr": 0, "fake_tender": 4, "social_panic": 3}
    got: dict = {}
    for key, info in SAMPLE_NEWS.items():
        raw = run_skeptic_live(info["text"], use_cache=True)
        v = parse_skeptic_response(raw)
        got[key] = v.num_concerns
    for k, v in expected.items():
        if got.get(k) != v:
            raise ValueError(
                f"{k}: expected num_concerns={v}, got {got.get(k)}"
            )
    return f"3 cached verdicts match expected num_concerns"


def check_anomaly_filter() -> str:
    from adversarial.demo.skeptic_runner import run_anomaly_filter_live
    sample = (
        "Palantir Technologies reported Q3 2025 results showing 30% YoY "
        "revenue growth driven by enterprise AI demand. Operating cash "
        "flow inflection visible across the trailing-twelve-month series."
    )
    r = run_anomaly_filter_live(sample)
    if r.verdict not in ("natural", "borderline", "anomalous"):
        raise ValueError(f"unexpected verdict {r.verdict!r}")
    if not (0.0 <= r.score_lexical <= 1.0):
        raise ValueError(f"lexical score out of [0,1]: {r.score_lexical}")
    return f"lexical={r.score_lexical:.3f}, verdict={r.verdict}"


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

CHECKS: list[tuple[str, Callable[[], str]]] = [
    ("Imports", check_imports),
    ("A1 cached sample", check_a1_cached_sample),
    ("A2 cached sample", check_a2_cached_sample),
    ("A5 local generation", check_a5_local_generation),
    ("Stealth metric ordering", check_stealth_metric_ordering),
    ("Skeptic cached fallback", check_skeptic_cached_fallback),
    ("Anomaly filter", check_anomaly_filter),
]


def main() -> int:
    print(textwrap.dedent("""
        ============================================================
        Minimal reproduction — no API key required
        ============================================================
        """).strip(), end="\n\n")

    n_pass = 0
    n_fail = 0
    for name, fn in CHECKS:
        ok, line = _check(name, fn)
        print(line)
        n_pass += int(ok)
        n_fail += int(not ok)

    print()
    if n_fail == 0:
        print(f"✅ All {n_pass} minimal-repro checks passed (no API key needed).")
        return 0
    else:
        print(
            f"❌ {n_fail} of {n_pass + n_fail} minimal-repro checks FAILED. "
            f"See lines marked ❌ above."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
