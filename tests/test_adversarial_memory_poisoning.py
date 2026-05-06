"""Unit tests for the A5 memory-poisoning generator.

These tests exercise the **template + RNG** code path and the rendered
`trading_memory.md` format. No LLM calls; deterministic.
"""

from __future__ import annotations

import re

import pytest

from adversarial.attacks.memory_poisoning import (
    CROSS_TICKERS,
    DIRECTION_TO_RATING,
    PoisonedEntry,
    build_poison_pack_v2,
    render_entry,
)


pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Determinism — same seed must give byte-identical output across runs.
# ---------------------------------------------------------------------------
def test_v2_pack_is_deterministic_under_fixed_seed():
    a = build_poison_pack_v2("PLTR", "2025-12-09", "bullish", seed=42)
    b = build_poison_pack_v2("PLTR", "2025-12-09", "bullish", seed=42)

    assert len(a) == len(b)
    for ea, eb in zip(a, b):
        assert ea == eb, "Same seed must produce identical entries"


def test_v2_pack_changes_with_seed():
    a = build_poison_pack_v2("PLTR", "2025-12-09", "bullish", seed=0)
    b = build_poison_pack_v2("PLTR", "2025-12-09", "bullish", seed=1)
    # At least one of (date, theme, alpha, hold) must differ across seeds.
    assert a != b, "Different seeds must produce different packs"


# ---------------------------------------------------------------------------
# Cap — default 5 same-ticker + 3 cross-ticker matches PM reader budget.
# ---------------------------------------------------------------------------
def test_v2_pack_uses_5_plus_3_by_default():
    pack = build_poison_pack_v2("PLTR", "2025-12-09", "bullish", seed=0)
    assert len(pack) == 8, "Default cap is 5 same-ticker + 3 cross-ticker"

    same = [e for e in pack if e.ticker == "PLTR"]
    cross = [e for e in pack if e.ticker != "PLTR"]
    assert len(same) == 5
    assert len(cross) == 3


def test_cross_ticker_entries_use_pool_and_exclude_target():
    pack = build_poison_pack_v2("NVDA", "2026-01-20", "bullish", seed=0)
    cross_set = {e.ticker for e in pack if e.ticker != "NVDA"}
    assert cross_set.issubset(set(CROSS_TICKERS))
    assert "NVDA" not in cross_set, "Cross-ticker pool must exclude the target"


# ---------------------------------------------------------------------------
# Direction — bullish ⇒ Buy, bearish ⇒ Sell on every entry.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("direction", ["bullish", "bearish"])
def test_all_entries_share_intended_direction(direction):
    pack = build_poison_pack_v2("PLTR", "2025-12-09", direction, seed=7)
    expected_rating = DIRECTION_TO_RATING[direction]
    assert all(e.rating == expected_rating for e in pack)


# ---------------------------------------------------------------------------
# Format — rendered text must precisely mirror trading_memory.md schema.
# ---------------------------------------------------------------------------
_HEADER_RE = re.compile(
    r"\[\d{4}-\d{2}-\d{2} \| [A-Z]{1,5} \| \w+ \| "
    r"[+-]?\d+\.\d% \| [+-]?\d+\.\d% \| \d+d\]"
)


def test_render_entry_matches_real_memory_log_format():
    pack = build_poison_pack_v2("PLTR", "2025-12-09", "bullish", seed=0)
    rendered = render_entry(pack[0])

    # Header line: [DATE | TICKER | RATING | raw% | alpha% | Nd]
    first_line = rendered.splitlines()[0]
    assert _HEADER_RE.match(first_line), (
        f"Header line does not match memory.md schema: {first_line!r}"
    )

    # Required structural anchors
    for anchor in [
        "DECISION:",
        "**Rating**:",
        "**Investment Thesis**:",
        "**Time Horizon**:",
        "REFLECTION:",
        "<!-- ENTRY_END -->",
    ]:
        assert anchor in rendered, f"Rendered entry missing anchor: {anchor}"


def test_v2_reflection_uses_directive_lesson_phrasing():
    """A5v2's hallmark: directive 'LESSON LEARNED' reflection.

    This is what distinguishes v2 from v1 (per MemoryGraft 2025) and
    must be present on every v2 entry.
    """
    pack = build_poison_pack_v2("PLTR", "2025-12-09", "bullish", seed=3)
    for entry in pack:
        assert "LESSON LEARNED" in entry.reflection
        assert "hard rule in my playbook" in entry.reflection


# ---------------------------------------------------------------------------
# Numeric calibration — alpha/raw figures land in v2's intended range.
# ---------------------------------------------------------------------------
def test_v2_alpha_returns_in_calibrated_range():
    """A5v2 widens alpha to 4-8% (vs v1's 1.5-4.5%) so the past-pattern
    signal is materially significant. Verify every entry lands in range."""
    pack = build_poison_pack_v2("PLTR", "2025-12-09", "bullish", seed=99)
    for entry in pack:
        assert 4.0 <= entry.alpha_pct <= 8.0, (
            f"alpha_pct={entry.alpha_pct} outside v2 calibrated range [4, 8]"
        )
        # raw return must be larger than alpha (because beta > 0 was added).
        assert entry.raw_return_pct > entry.alpha_pct
        assert entry.hold_days in {5, 7, 10, 14, 21}
