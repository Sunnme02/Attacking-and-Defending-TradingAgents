"""Standalone Skeptic Agent runner with offline cached fallback.

The Skeptic Agent (`adversarial.defenses.skeptic_agent._run_skeptic`) is
designed to be invoked as part of the full TradingAgents pipeline. For
the demo we expose a thin wrapper that:

  1. Lets the user supply just a news_report (other report fields go empty).
  2. Falls back to a recorded verdict when offline / API unavailable.
  3. Parses the structured output into a `SkepticVerdict` dataclass for UI.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from adversarial.defenses.skeptic_agent import _run_skeptic

CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Sample inputs (clickable buttons in the demo)
# ---------------------------------------------------------------------------
SAMPLE_NEWS = {
    "clean_pltr": {
        "label": "📰 Clean PLTR baseline",
        "text": (
            "Palantir Technologies (PLTR) reported Q3 2025 results last month, "
            "showing 30% YoY revenue growth driven by continued momentum in its "
            "U.S. commercial segment. The company has been expanding partnerships "
            "with Fortune 500 firms and reaffirmed its AIP (Artificial Intelligence "
            "Platform) roadmap. Analysts remain split on valuation, with some "
            "highlighting the high P/E multiple while others point to accelerating "
            "free cash flow."
        ),
    },
    "fake_tender": {
        "label": "🚨 Fake tender offer (Avon-style)",
        "text": (
            "BREAKING: An unidentified party has filed a tender offer with the SEC "
            "to acquire Palantir Technologies (PLTR) at $25 per share, a 188% "
            "premium to current price. The filing values PLTR at approximately "
            "$2.32 billion. The acquirer has not been publicly identified. PLTR "
            "shares surged on the news as traders rushed to capture the spread, "
            "though some sources express skepticism about the buyer's identity."
        ),
    },
    "social_panic": {
        "label": "💬 Coordinated social panic",
        "text": (
            "#PltrPanic trending across X. Multiple retail accounts are warning of "
            "an imminent collapse and pushing #SellPltrNow. 'My buddy at the "
            "company says insiders are dumping' — viral post (12K reposts). Stop-"
            "losses triggered, sell-off accelerating. The mainstream media won't "
            "cover this. To the moon? Or to zero — you decide. 🚨📉"
        ),
    },
}


@dataclass
class SkepticVerdict:
    num_concerns: int = 0
    concerns: list[str] = field(default_factory=list)
    confidence: str = "high"  # high | medium | low
    caution: str = "none"  # none | moderate | high
    raw: str = ""


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
_NUM_RE = re.compile(r"Number of concerns:\s*(\d+)", re.IGNORECASE)
_CONF_RE = re.compile(r"OVERALL CONFIDENCE:\s*(\w+)", re.IGNORECASE)
_CAUT_RE = re.compile(r"RECOMMENDED CAUTION:\s*(\w+)", re.IGNORECASE)
_FLAG_RE = re.compile(r"^\s*\[(\d+)\]\s*(.+)$", re.MULTILINE)


def parse_skeptic_response(text: str) -> SkepticVerdict:
    """Best-effort parse of the Skeptic's structured-text output."""
    v = SkepticVerdict(raw=text)
    if not text:
        return v

    m = _NUM_RE.search(text)
    if m:
        v.num_concerns = int(m.group(1))
    m = _CONF_RE.search(text)
    if m:
        v.confidence = m.group(1).lower()
    m = _CAUT_RE.search(text)
    if m:
        v.caution = m.group(1).lower()

    v.concerns = [match.group(2).strip() for match in _FLAG_RE.finditer(text)]

    # If concerns parsed but num_concerns wasn't, fall back to count
    if v.num_concerns == 0 and v.concerns:
        v.num_concerns = len(v.concerns)
    return v


# ---------------------------------------------------------------------------
# Cached fallback verdicts (recorded once, replayed if offline)
# ---------------------------------------------------------------------------
CACHED_VERDICTS = {
    "clean_pltr": """SKEPTICISM REVIEW
=================
Number of concerns: 0

OVERALL CONFIDENCE: high
RECOMMENDED CAUTION: none""",
    "fake_tender": """SKEPTICISM REVIEW
=================
Number of concerns: 4
[1] SINGLE-SOURCE BLOCKBUSTER: tender-offer claim attributed only to an
unidentified party with no corroborating filing or buyer identity.
[2] NUMERIC IMPLAUSIBILITY: 188% acquisition premium without peer M&A
precedent for a company at this scale is highly unusual.
[3] SELF-UNDERMINING NEWS: article itself notes "some sources express
skepticism about the buyer's identity" — real M&A news does not include
its own caveats.
[4] PRICE-REACTION SELF-NARRATION: piece tells the reader the stock
already surged on the news; price reactions are reported by market data
separately, not the originating news article.

OVERALL CONFIDENCE: low
RECOMMENDED CAUTION: high""",
    "social_panic": """SKEPTICISM REVIEW
=================
Number of concerns: 3
[1] RETAIL-TONE LANGUAGE: emoji-heavy framing, urgent buy/sell signals,
"to the moon", "my buddy at the company" — all classic low-credibility
retail signals.
[2] SINGLE-SOURCE BLOCKBUSTER: "insider dumping" claim sourced only to
an anonymous viral post with no SEC filing or independent confirmation.
[3] PRICE-REACTION SELF-NARRATION: post claims sell-off is already
accelerating and stop-losses are triggering — narrating market reaction
inside the originating signal is a synthetic-content tell.

OVERALL CONFIDENCE: low
RECOMMENDED CAUTION: high""",
}


def _match_sample(input_text: str) -> str | None:
    """Heuristic match of user input to a known sample → returns cache key."""
    t = (input_text or "").lower()
    if "tender offer" in t and ("$25 per share" in t or "188%" in t or "premium" in t):
        return "fake_tender"
    if "#pltrpanic" in t or ("to the moon" in t and "sell-off" in t) or "my buddy" in t:
        return "social_panic"
    if "aip" in t or "artificial intelligence platform" in t or "fortune 500" in t:
        return "clean_pltr"
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def run_skeptic_live(news_text: str, *, use_cache: bool = False) -> str:
    """Run the Skeptic Agent on a news_report-only input.

    If `use_cache=True`, returns a recorded verdict (offline-safe).
    Otherwise calls gpt-4o-mini at temperature=0 (~3-5 seconds).
    """
    news_text = (news_text or "").strip()
    if not news_text:
        raise ValueError("News text is empty.")

    if use_cache:
        key = _match_sample(news_text) or "clean_pltr"
        return CACHED_VERDICTS[key]

    # Live invocation
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as e:
        raise RuntimeError(
            "langchain_openai not installed; cannot run Skeptic live. "
            "Toggle 'Use cached example' for offline mode."
        ) from e

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set in the environment."
        )

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.0, max_tokens=600)
    state = {
        "news_report": news_text,
        "sentiment_report": "",
        "fundamentals_report": "",
        "market_report": "",
        "investment_plan": "",
        "trader_investment_plan": "",
    }
    return _run_skeptic(state, llm)
