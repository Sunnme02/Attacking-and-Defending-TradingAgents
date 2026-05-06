"""
D4 — Anomaly Filter (input-layer defense).

Hooks into ``route_to_vendor`` (same chokepoint A1/A2 use for injection)
and applies the stealth metric to the news output. Paragraphs that score
anomalously low are stripped before the analyst LLM ever sees them.

Why paragraph-level (not whole-output):
  Whole-output scoring would average a small attack with a long block
  of real news → real content dilutes the anomaly score. Paragraph-
  level keeps each ~2-5 sentence chunk under independent test, which
  matches how attacks land (a single appended article or post-block).

The filter does NOT know about our injection format (no detection of
HEADER_NEWS/HEADER_SOCIAL prefixes, etc.) — it operates purely on
content. This makes it a realistic defense baseline:
  - paper claim: "anomaly filter using only off-the-shelf signals
    (lexical / FinBERT) reduces ASR by X% without seeing labels"

Backends:
  - "lexical": fast, classical features (no LLM/torch needed)
  - "finbert": ProsusAI/finbert CLS embedding distance (needs torch)
  - "hybrid": drop if EITHER backend flags

Threshold tuning: lower threshold = more paragraphs kept = less defense
strength but fewer false positives. Sweep threshold ∈ [0.05, 0.4] for
ROC analysis in paper.

Usage:
    from adversarial.defenses import anomaly_filter
    anomaly_filter.enable(threshold=0.10, backend="lexical")
    # ... build TradingAgentsGraph + propagate() ...
    anomaly_filter.disable()
"""

from __future__ import annotations

import importlib
import re
from typing import Callable, Optional

# Same patch sites as news_injection — D4 sits on the SAME chokepoint
# but on the output side. Order of operations during attack+defense:
# real vendor → news_injection appends payload → anomaly_filter scores
# the combined output. We achieve correct ordering by patching at
# importlib level: D4 patches AFTER the wrapper, so D4's wrapper wraps
# whatever wrapper is currently in place (including news_injection's).
_PATCH_SITES = [
    "tradingagents.dataflows.interface",
    "tradingagents.agents.utils.news_data_tools",
]

_ORIGINAL_FN: Optional[Callable] = None
_ENABLED = False
_THRESHOLD = 0.10
_BACKEND = "lexical"

# Filtering signal cached per call (for audit logs); reset on enable().
_LAST_REPORT: list[dict] = []


def _split_paragraphs(text: str) -> list[str]:
    """Split into 'segments' the analyst would treat as units. We split
    on blank lines (paragraph break) and on our known header markers,
    then keep segments of ≥ 80 chars (shorter ones rarely carry an
    independent claim and would thrash the lexical baseline)."""
    if not text:
        return []
    # Split on 2+ newlines OR on lines starting with '---'
    parts = re.split(r"\n\s*\n|\n(?=---)", text)
    parts = [p.strip() for p in parts]
    return [p for p in parts if len(p) >= 80]


def _score_segment(segment: str, backend: str):
    """Returns (score_used, full_verdict) where score_used is the value
    we compare against threshold under the chosen backend."""
    from adversarial.judges import stealth
    v = stealth.score(segment)
    if backend == "finbert":
        score = v.stealth_score_finbert
    elif backend == "hybrid":
        # Flag if either backend says low stealth (more aggressive)
        scores = [v.stealth_score_lexical]
        if v.stealth_score_finbert is not None:
            scores.append(v.stealth_score_finbert)
        score = min(scores) if scores else None
    else:  # "lexical"
        score = v.stealth_score_lexical
    return score, v


def _make_patched(orig: Callable) -> Callable:
    def patched_route(method, *args, **kwargs):
        result = orig(method, *args, **kwargs)
        if method != "get_news" or not isinstance(result, str):
            return result

        segments = _split_paragraphs(result)
        if not segments:
            return result

        kept_segments = []
        dropped = []
        for seg in segments:
            score, verdict = _score_segment(seg, _BACKEND)
            if score is None:
                kept_segments.append(seg)
                continue
            if score < _THRESHOLD:
                dropped.append({
                    "score": float(score),
                    "preview": seg[:80] + ("..." if len(seg) > 80 else ""),
                })
            else:
                kept_segments.append(seg)

        # Audit trail (per-trial). Cleared on next enable().
        if dropped:
            _LAST_REPORT.append({
                "method": method,
                "ticker": args[0] if args else kwargs.get("ticker", "?"),
                "n_dropped": len(dropped),
                "n_kept": len(kept_segments),
                "dropped": dropped,
            })

        if not dropped:
            return result
        # Rebuild output: kept segments rejoined + a small notice so the
        # analyst LLM knows content was filtered (not silently missing).
        notice = (
            f"\n\n[D4 anomaly filter: {len(dropped)} segment(s) suppressed "
            f"(stealth < {_THRESHOLD:.2f}, backend={_BACKEND})]\n"
        )
        return "\n\n".join(kept_segments) + notice
    return patched_route


def enable(threshold: float = 0.10, backend: str = "lexical") -> None:
    """Activate the D4 anomaly filter overlay.

    Args:
        threshold: stealth-score cutoff in [0, 1]; below this a segment
            is dropped. Lower = stricter defense. Recommend sweep
            {0.05, 0.10, 0.20, 0.30} for ROC.
        backend: 'lexical' (default, no torch) | 'finbert' (needs torch)
            | 'hybrid' (drop if either backend flags).
    """
    global _ORIGINAL_FN, _ENABLED, _THRESHOLD, _BACKEND, _LAST_REPORT
    if _ENABLED:
        return
    if backend not in ("lexical", "finbert", "hybrid"):
        raise ValueError(f"unknown backend {backend!r}")
    _THRESHOLD = float(threshold)
    _BACKEND = backend
    _LAST_REPORT = []

    interface = importlib.import_module("tradingagents.dataflows.interface")
    _ORIGINAL_FN = interface.route_to_vendor
    patched = _make_patched(_ORIGINAL_FN)
    for site in _PATCH_SITES:
        m = importlib.import_module(site)
        if hasattr(m, "route_to_vendor"):
            m.route_to_vendor = patched
    _ENABLED = True


def disable() -> None:
    global _ORIGINAL_FN, _ENABLED
    if not _ENABLED or _ORIGINAL_FN is None:
        return
    for site in _PATCH_SITES:
        m = importlib.import_module(site)
        if hasattr(m, "route_to_vendor"):
            m.route_to_vendor = _ORIGINAL_FN
    _ORIGINAL_FN = None
    _ENABLED = False


def get_last_report() -> list[dict]:
    """Return the per-call drop log since enable(). Useful as an audit
    trail when running attack × defense matrix experiments."""
    return list(_LAST_REPORT)


def is_enabled() -> bool:
    return _ENABLED
