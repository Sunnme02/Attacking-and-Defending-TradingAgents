"""Standalone wrappers for live A1 / A2 attack generation in the demo.

Both `news_rewriter.rewrite()` and `coordinated_disinfo.generate()` already
accept a ``use_cache`` flag and persist their output as JSON. We expose
demo-friendly wrappers that:
  • Force a fresh generation when ``use_cache=False`` (live mode).
  • Return the cached sample when ``use_cache=True`` (offline-safe).
  • Surface QC scores / persona breakdowns for UI rendering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from adversarial.attacks.coordinated_disinfo import (
    CoordinatedPayload,
    format_for_injection,
    generate as _generate_coord,
)
from adversarial.attacks.news_rewriter import FakeNewsSample, rewrite as _rewrite_a1
from adversarial.data.seeds.sec_seeds import SEEDS, get_seed


# ---------------------------------------------------------------------------
# Fixed (ticker, date) options — only configurations we have full data for.
# Constraining the dropdown avoids vendor-lookup failures during a live demo.
# ---------------------------------------------------------------------------
TICKER_DATE_OPTIONS: list[tuple[str, str]] = [
    ("PLTR", "2025-12-09"),
    ("HOOD", "2026-01-13"),
    ("SNOW", "2025-12-16"),
    ("NVDA", "2026-01-20"),
    ("BIIB", "2025-12-02"),
]

# Map case_id -> (display label, native direction). Used for the SEC-case
# dropdown in the A1 sub-tab. Direction is locked to the seed's native
# direction (rewrite() rejects cross-direction overrides).
SEC_CASE_OPTIONS: list[tuple[str, str, str]] = [
    (s.case_id, f"{s.case_id} ({s.year}, {s.direction})", s.direction)
    for s in SEEDS
]


# ---------------------------------------------------------------------------
# Result dataclasses (UI-friendly, decoupled from generator internals)
# ---------------------------------------------------------------------------
@dataclass
class FakeNewsResult:
    case_id: str
    ticker: str
    date: str
    direction: str
    article_text: str
    raw_text_with_marker: str
    qc_verdict: str           # pass | fail | unchecked
    qc_scores: dict           # 4-criterion 1-5 scores
    qc_issues: list           # list of short strings
    qc_attempts: int
    seed_tactic: str
    model: str
    used_cache: bool

    @classmethod
    def from_sample(cls, s: FakeNewsSample, *, used_cache: bool) -> "FakeNewsResult":
        return cls(
            case_id=s.case_id,
            ticker=s.ticker,
            date=s.date,
            direction=s.direction,
            article_text=s.text,
            raw_text_with_marker=s.raw_text,
            qc_verdict=s.qc_verdict or "unchecked",
            qc_scores=s.qc_scores or {},
            qc_issues=list(s.qc_issues or []),
            qc_attempts=int(s.qc_attempts or 1),
            seed_tactic=s.seed_tactic,
            model=s.model,
            used_cache=used_cache,
        )


@dataclass
class CrossChannelResult:
    ticker: str
    date: str
    direction: str
    article_headline: str
    article_body: str
    social_posts: list[dict]      # [{persona, text}, ...]
    combined_block: str           # The format_for_injection() output
    model: str
    used_cache: bool

    @classmethod
    def from_payload(
        cls, p: CoordinatedPayload, *, used_cache: bool
    ) -> "CrossChannelResult":
        return cls(
            ticker=p.ticker,
            date=p.date,
            direction=p.direction,
            article_headline=p.article_headline,
            article_body=p.article_body,
            social_posts=list(p.social_posts),
            combined_block=format_for_injection(p),
            model=p.model,
            used_cache=used_cache,
        )


# ---------------------------------------------------------------------------
# A1 — Fake News
# ---------------------------------------------------------------------------
def run_fake_news_live(
    case_id: str,
    ticker: str,
    date: str,
    *,
    use_cache: bool = False,
    model: str = "gpt-4o-mini",
    max_attempts: int = 3,
) -> FakeNewsResult:
    """Generate (or fetch cached) fake-news article for the given config.

    Args:
        case_id: SEC seed identifier (must exist in sec_seeds.SEEDS).
        ticker: target ticker symbol.
        date: target trade date YYYY-MM-DD.
        use_cache: if True, returns the on-disk cached sample (instant);
            if False, forces a live LLM generation (~5-15s).
        model: generator LLM id.
        max_attempts: max generation attempts before giving up.
    """
    # rewrite() accepts ``direction`` as override but only if it matches the
    # seed's native direction. We inspect the seed and pass its native
    # direction explicitly so the UI doesn't have to reason about it.
    seed = get_seed(case_id)
    sample = _rewrite_a1(
        case_id=case_id,
        ticker=ticker,
        date=date,
        direction=seed.direction,
        model=model,
        use_cache=use_cache,
        qc=True,
        qc_model=model,
        max_attempts=max_attempts,
    )
    return FakeNewsResult.from_sample(sample, used_cache=use_cache)


# ---------------------------------------------------------------------------
# A2 — Cross-Channel Coordinated
# ---------------------------------------------------------------------------
def run_cross_channel_live(
    ticker: str,
    date: str,
    direction: str,
    *,
    use_cache: bool = False,
    model: str = "gpt-4o-mini",
) -> CrossChannelResult:
    """Generate (or fetch cached) cross-channel attack bundle.

    Args:
        ticker: target ticker.
        date: trade date YYYY-MM-DD.
        direction: 'bullish' or 'bearish'.
        use_cache: True -> instant cached read; False -> live LLM (~10-20s).
        model: generator LLM id.
    """
    payload = _generate_coord(
        ticker=ticker,
        date=date,
        direction=direction,
        model=model,
        use_cache=use_cache,
    )
    return CrossChannelResult.from_payload(payload, used_cache=use_cache)
