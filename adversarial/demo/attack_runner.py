"""Standalone wrappers for live A1 / A2 / A5 attack generation in the demo.

Both `news_rewriter.rewrite()` and `coordinated_disinfo.generate()` already
accept a ``use_cache`` flag and persist their output as JSON. We expose
demo-friendly wrappers that:
  • Force a fresh generation when ``use_cache=False`` (live mode).
  • Return the cached sample when ``use_cache=True`` (offline-safe).
  • Surface QC scores / persona breakdowns for UI rendering.
  • **Session-scope the OpenAI key** — when the demo is hosted publicly,
    one user's pasted key MUST NOT leak into another concurrent user's
    LLM call. We scope ``OPENAI_API_KEY`` only for the duration of the
    LLM call inside this wrapper.

A5 Memory Poisoning is generated locally (template + RNG) and never
needs an API key.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, Optional

from adversarial.attacks.coordinated_disinfo import (
    CoordinatedPayload,
    format_for_injection,
    generate as _generate_coord,
)
from adversarial.attacks.memory_poisoning import (
    PoisonedEntry,
    build_poison_pack_v2,
    render_entry,
)
from adversarial.attacks.news_rewriter import FakeNewsSample, rewrite as _rewrite_a1
from adversarial.data.seeds.sec_seeds import SEEDS, get_seed


# ---------------------------------------------------------------------------
# Session-scoped OpenAI key
# ---------------------------------------------------------------------------
@contextmanager
def _scoped_openai_key(api_key: Optional[str]) -> Iterator[None]:
    """Set ``OPENAI_API_KEY`` in os.environ ONLY for the duration of this
    block, then restore the previous value.

    Why this matters: Streamlit Cloud runs all user sessions in a single
    Python process, so ``os.environ`` is shared across concurrent users.
    If user A pasted their key and we left it in os.environ globally,
    user B's clicks would silently use A's key. Scoping the assignment
    to a context manager narrows the leak window to the active LLM call
    only (~5–20 s), and restores the previous state on exit.

    Pass ``api_key=None`` (or empty string) to leave os.environ untouched
    — useful when the deployer set OPENAI_API_KEY in the Streamlit secrets
    and no per-user key is needed.
    """
    if not api_key:
        yield
        return
    original = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = api_key
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = original


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

# Case IDs for which we ship pre-generated cached payloads for every
# (ticker, date) pair in TICKER_DATE_OPTIONS. Any other SEC seed requires
# a live LLM call (and therefore an OpenAI key in the session). The demo
# UI uses this to hide unreachable options when the user hasn't supplied
# a key.
A1_CASES_WITH_CACHE = {"avon_fake_tender_2015", "craig_twitter_2015"}


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
    api_key: Optional[str] = None,
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
        api_key: per-session OpenAI key. Scoped to this call only — see
            ``_scoped_openai_key``. Pass None to use whatever key is
            already in the environment (e.g. from Streamlit secrets).
    """
    # rewrite() accepts ``direction`` as override but only if it matches the
    # seed's native direction. We inspect the seed and pass its native
    # direction explicitly so the UI doesn't have to reason about it.
    seed = get_seed(case_id)
    with _scoped_openai_key(api_key):
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
    api_key: Optional[str] = None,
) -> CrossChannelResult:
    """Generate (or fetch cached) cross-channel attack bundle.

    Args:
        ticker: target ticker.
        date: trade date YYYY-MM-DD.
        direction: 'bullish' or 'bearish'.
        use_cache: True -> instant cached read; False -> live LLM (~10-20s).
        model: generator LLM id.
        api_key: see ``run_fake_news_live`` — same semantics.
    """
    with _scoped_openai_key(api_key):
        payload = _generate_coord(
            ticker=ticker,
            date=date,
            direction=direction,
            model=model,
            use_cache=use_cache,
        )
    return CrossChannelResult.from_payload(payload, used_cache=use_cache)


# ---------------------------------------------------------------------------
# A5 — Memory Poisoning
# ---------------------------------------------------------------------------
@dataclass
class MemoryPoisoningResult:
    ticker: str
    date: str
    direction: str
    entries: list[PoisonedEntry]   # 5 same-ticker + 3 cross-ticker
    rendered_log: str              # full memory.md-style text (all entries)
    seed: int

    @property
    def n_same_ticker(self) -> int:
        return sum(1 for e in self.entries if e.ticker == self.ticker)

    @property
    def n_cross_ticker(self) -> int:
        return sum(1 for e in self.entries if e.ticker != self.ticker)


def run_memory_poisoning_live(
    ticker: str,
    date: str,
    direction: str,
    *,
    seed: int = 0,
    n_same_ticker: int = 5,
    n_cross_ticker: int = 3,
) -> MemoryPoisoningResult:
    """Generate the 8 fabricated memory entries for the A5 attack.

    No API key is required and no LLM is invoked — the entries come from
    a hand-written thesis-template pool plus a seeded RNG. Re-running with
    the same ``seed`` produces byte-identical output.

    Args:
        ticker: target ticker (the agent's "this trade" ticker).
        date: target trade date (YYYY-MM-DD).
        direction: 'bullish' or 'bearish'.
        seed: RNG seed for reproducibility.
        n_same_ticker: how many fabricated past trades on the same ticker
            to include (default 5 — fully utilises PM's same-ticker cap).
        n_cross_ticker: cross-ticker (sector-similar) entries (default 3 —
            fully utilises PM's cross-ticker cap).
    """
    entries = build_poison_pack_v2(
        target_ticker=ticker,
        target_date=date,
        direction=direction,  # type: ignore[arg-type]
        n_same_ticker=n_same_ticker,
        n_cross_ticker=n_cross_ticker,
        seed=seed,
    )
    rendered = "".join(render_entry(e) + "\n" for e in entries)
    return MemoryPoisoningResult(
        ticker=ticker,
        date=date,
        direction=direction,
        entries=entries,
        rendered_log=rendered,
        seed=seed,
    )
