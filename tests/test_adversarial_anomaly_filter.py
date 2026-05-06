"""Unit tests for the D4 Anomaly Filter input-layer defense.

These tests exercise the lexical stealth-score backend (no torch /
FinBERT needed) and the segment splitter. No LLM calls.
"""

from __future__ import annotations

import pytest

from adversarial.defenses.anomaly_filter import _split_paragraphs


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Segment splitter — paragraph-level breaks + injection-header awareness.
# ---------------------------------------------------------------------------
def test_split_paragraphs_drops_below_minimum_length():
    """Segments < 80 chars should be filtered out (would thrash the
    lexical baseline)."""
    text = "Short line one.\n\nShort line two.\n\n"
    segments = _split_paragraphs(text)
    assert segments == [], "Sub-80-char segments must be dropped"


def test_split_paragraphs_respects_injection_header_boundaries():
    """Injection headers (`---`) start a new segment so a short real-news
    header doesn't get glued to a long fake-news block."""
    text = (
        "This is a real news paragraph that is comfortably longer than "
        "the eighty-character minimum so it survives the length filter.\n"
        "\n"
        "--- LATEST BREAKING UPDATES ---\n"
        "This is the injected fake-article body, again comfortably longer "
        "than the minimum length floor so we get a separate segment for it."
    )
    segments = _split_paragraphs(text)
    assert len(segments) >= 2, (
        "Real news and injection block must split into separate segments; "
        f"got {len(segments)}: {[s[:40] for s in segments]}"
    )
    # The injection segment should retain its header for downstream debug.
    assert any("LATEST BREAKING UPDATES" in s for s in segments)


def test_split_paragraphs_handles_empty_input():
    assert _split_paragraphs("") == []
    assert _split_paragraphs(None) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Stealth score — lexical backend should distinguish synthetic retail-tone
# spam from a Reuters/Bloomberg-style article.
# ---------------------------------------------------------------------------
def test_lexical_stealth_score_separates_retail_spam_from_real_style():
    """The lexical backend should give a *lower* stealth score (more
    anomalous) to a retail-pump post than to an institutional article.

    We do not assert specific thresholds (those are tuned per-deployment),
    only that the relative ordering is correct.
    """
    from adversarial.judges import stealth

    real_style = (
        "Reuters reports that the company expects revenue growth of "
        "approximately 14 percent year over year, driven by sustained "
        "enterprise demand. Management raised full-year guidance during "
        "the third-quarter earnings call, citing operating-leverage "
        "gains across its core business segments."
    )
    retail_spam = (
        "🚀🚀 TO THE MOON FAM 🌕 my buddy at the company says they're "
        "loading up huge 💎🙌 media won't cover this but BIG NEWS coming "
        "next week!! diamond hands only, 100x setup, don't miss out!!!"
    )

    real_score = stealth.score(real_style)
    spam_score = stealth.score(retail_spam)

    assert real_score.stealth_score_lexical is not None
    assert spam_score.stealth_score_lexical is not None

    # Retail spam should be flagged as more anomalous than real-style text.
    assert spam_score.stealth_score_lexical < real_score.stealth_score_lexical, (
        f"Lexical backend failed to discriminate: "
        f"real={real_score.stealth_score_lexical:.3f}, "
        f"spam={spam_score.stealth_score_lexical:.3f}"
    )
