"""Unit tests for the A1/A2 runtime monkey-patch (`route_to_vendor`
chokepoint). Verifies that:

  1. enable() / disable() are idempotent and properly restore state.
  2. Patched function only modifies output for `method='get_news'` and
     leaves other vendor methods untouched.
  3. Headers (HEADER_NEWS / HEADER_SOCIAL) appear correctly in injected
     output.

No LLM / no network calls.
"""

from __future__ import annotations

import pytest

from adversarial.attacks import news_injection


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_state():
    """Ensure each test starts with a clean injection registry and no
    active patch (in case a previous test left something in flight)."""
    if news_injection.is_enabled():
        news_injection.disable()
    news_injection.clear()
    yield
    if news_injection.is_enabled():
        news_injection.disable()
    news_injection.clear()


# ---------------------------------------------------------------------------
# Lifecycle — enable / disable / re-enable should be safe.
# ---------------------------------------------------------------------------
def test_enable_then_disable_is_idempotent():
    assert not news_injection.is_enabled()
    news_injection.enable()
    assert news_injection.is_enabled()
    news_injection.enable()  # idempotent — no error
    assert news_injection.is_enabled()
    news_injection.disable()
    assert not news_injection.is_enabled()
    news_injection.disable()  # idempotent — no error
    assert not news_injection.is_enabled()


# ---------------------------------------------------------------------------
# Registry — register / clear behave correctly.
# ---------------------------------------------------------------------------
def test_register_stores_payload_under_uppercase_ticker_key():
    news_injection.register("pltr", "2025-12-09", ["fake article body"])
    assert ("PLTR", "2025-12-09") in news_injection.INJECTION_REGISTRY
    assert ("pltr", "2025-12-09") not in news_injection.INJECTION_REGISTRY


def test_clear_empties_the_registry():
    news_injection.register("PLTR", "2025-12-09", ["x"])
    news_injection.register("SNOW", "2025-12-16", ["y"])
    assert len(news_injection.INJECTION_REGISTRY) == 2
    news_injection.clear()
    assert len(news_injection.INJECTION_REGISTRY) == 0


# ---------------------------------------------------------------------------
# Patched function — only modifies get_news, only for registered keys.
# ---------------------------------------------------------------------------
def test_patched_route_appends_payload_only_for_registered_key():
    captured = {}

    def fake_route(method, *args, **kwargs):
        captured["last"] = (method, args, kwargs)
        return "REAL VENDOR OUTPUT"

    patched = news_injection._make_patched(fake_route)
    news_injection.register("PLTR", "2025-12-09", ["FAKE INJECTED"])

    # Hit on registered key — payload appended after real output.
    out = patched("get_news", "PLTR", "2025-12-02", "2025-12-09")
    assert out.startswith("REAL VENDOR OUTPUT")
    assert "FAKE INJECTED" in out
    assert news_injection.HEADER_NEWS.strip() in out

    # Miss on a different ticker — payload NOT appended.
    out = patched("get_news", "AAPL", "2025-12-02", "2025-12-09")
    assert out == "REAL VENDOR OUTPUT"

    # Miss on a different method (e.g. price data) — never appended.
    out = patched("get_stock_data", "PLTR", "2025-12-02", "2025-12-09")
    assert out == "REAL VENDOR OUTPUT"


def test_patched_route_uses_social_header_when_registered_with_one():
    def fake_route(method, *args, **kwargs):
        return "REAL"

    patched = news_injection._make_patched(fake_route)
    news_injection.register(
        "PLTR", "2025-12-09", ["a social-style block"],
        header=news_injection.HEADER_SOCIAL,
    )
    out = patched("get_news", "PLTR", "2025-12-02", "2025-12-09")
    assert news_injection.HEADER_SOCIAL.strip() in out
    # The default news header should NOT be present if the social one was
    # registered.
    assert news_injection.HEADER_NEWS.strip() not in out


def test_patched_route_returns_unchanged_when_no_payload_registered():
    """No registration ⇒ behaves exactly like the unpatched function."""
    def fake_route(method, *args, **kwargs):
        return "UNTOUCHED"

    patched = news_injection._make_patched(fake_route)
    out = patched("get_news", "PLTR", "2025-12-02", "2025-12-09")
    assert out == "UNTOUCHED"
