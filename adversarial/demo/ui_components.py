"""Reusable Streamlit UI components for the adversarial-robustness demo.

Two live tabs only:
  • Attack lab — live LLM-driven generation (Fake News + Cross-Channel + Memory)
  • Defense panel — live Skeptic + Anomaly Filter invocation

The cached trial-browser tabs were removed by design: the demo focuses on
*the system operating*, not on data presentation. The full 1,210-trial
dataset lives in `adversarial/results/` and is documented in the paper.
"""

from __future__ import annotations

import html
import os
from typing import Optional

import streamlit as st


# ---------------------------------------------------------------------------
# Session-scoped API key access
# ---------------------------------------------------------------------------
# Snapshot the deployer's intended key at module-import time. We never
# read os.environ at runtime: doing so would let a previous user's
# accidental write to os.environ leak across concurrent sessions. The
# snapshot below represents only what the deployer configured in
# Streamlit Cloud secrets (the legitimate fallback key, if any).
DEPLOYER_API_KEY: str = os.environ.get("OPENAI_API_KEY", "").strip()


def get_session_api_key() -> str:
    """Return the active OpenAI key for THIS user's Streamlit session.

    Resolution order:
      1. ``st.session_state["user_api_key"]`` (key the user pasted into
         the sidebar — isolated per browser session).
      2. ``DEPLOYER_API_KEY`` (snapshot of os.environ at module load —
         the deployer's intended fallback, if any).

    NEVER reads os.environ dynamically. That avoids the situation where
    one user's key accidentally written into os.environ would be
    visible to a later user's session.
    """
    session_key = st.session_state.get("user_api_key", "").strip()
    if session_key:
        return session_key
    return DEPLOYER_API_KEY


def api_key_present() -> bool:
    """True iff this session has an active key (session-pasted OR deployer snapshot)."""
    return bool(get_session_api_key())

from adversarial.demo.attack_runner import (
    A1_CASES_WITH_CACHE,
    SEC_CASE_OPTIONS,
    TICKER_DATE_OPTIONS,
    AsyncJob,
    CrossChannelResult,
    FakeNewsResult,
    MemoryPoisoningResult,
    run_cross_channel_live,
    run_fake_news_live,
    run_memory_poisoning_live,
    submit_async,
)
from adversarial.demo.skeptic_runner import (
    SAMPLE_NEWS,
    AnomalyFilterResult,
    SkepticVerdict,
    parse_skeptic_response,
    run_anomaly_filter_live,
    run_skeptic_live,
)



# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
def render_top_banner() -> None:
    cols = st.columns([6, 2])
    with cols[0]:
        st.markdown(
            "<h1 style='margin-bottom:0.2rem;font-size:2.0rem;'>"
            "Attacking and Defending Multi-Agent LLM Trading Systems"
            "</h1>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='color:#64748b;margin-top:0;'>"
            "Interactive companion to the Columbia STAT GR5293 final paper · "
            "1,210 measured trials · 3 attacks × 3 defenses × 5 tickers"
            "</p>",
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            "<div style='text-align:right;color:#64748b;font-size:0.85rem;padding-top:1.5rem;'>"
            "Zeyu Gu · 2026"
            "</div>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Attack lab tab — live A1 / A2 generation
# ---------------------------------------------------------------------------
def _send_to_skeptic(article_text: str) -> None:
    """Callback: pipe a generated attack article into the Skeptic textarea
    and switch the user's mental focus to the next tab."""
    st.session_state["skeptic_text"] = article_text
    st.session_state.pop("skeptic_last_raw", None)
    st.session_state["skeptic_pending_notice"] = (
        "📥 Article from Attack lab loaded. Switch to the **Skeptic — live** "
        "tab and press ▶ Run to test the defense."
    )


def render_attack_lab_tab() -> None:
    st.markdown("#### 🚨 Attack lab — live generation")
    st.caption(
        "Generate fresh adversarial content using the same code path the "
        "experiments use. Cached mode reads pre-computed payloads from disk "
        "(instant); live mode invokes the LLM (~5-20s). Generated articles "
        "can be piped to the Skeptic tab to test detection on **unseen** content."
    )

    is_unlocked = api_key_present()

    # Sub-toggle between Fake News / Cross-Channel / Memory Poisoning
    sub = st.radio(
        "Attack to generate",
        options=["a1", "a2", "a5"],
        format_func=lambda k: {
            "a1": "🎯 Fake News  (single article + LLM-Judge QC)",
            "a2": "📡 Cross-Channel  (1 article + 5 social posts, integrated)",
            "a5": "🧠 Memory Poisoning  (8 fabricated past trades — bypasses analysts, no API needed)",
        }[k],
        horizontal=True,
        key="attack_lab_sub",
    )

    if sub == "a1":
        _render_a1_panel(is_unlocked)
    elif sub == "a2":
        _render_a2_panel(is_unlocked)
    else:
        _render_a5_panel(is_unlocked)


# ----- A1 sub-panel --------------------------------------------------------
def _render_a1_panel(api_key_present: bool) -> None:
    """Two-mode panel:

    • No API key → SEC seed limited to 2 cached cases, ticker/date limited
      to 5 cached pairs. Pure cached read.
    • API key   → All 8 SEC seeds + free-form ticker + free-form date.
                  Live LLM generation enabled.
    """
    if api_key_present:
        _render_a1_unlocked()
    else:
        _render_a1_locked()


def _render_a1_locked() -> None:
    """Cached-only mode (no API key). Show only options that are
    guaranteed to hit a pre-generated payload on disk."""
    st.info(
        "🔒 **Cached-only mode.** Pick one of the 2 SEC cases × 5 ticker pairs "
        "we ship with. Paste a key in the sidebar to unlock the other 6 SEC "
        "cases and free-form ticker / date input."
    )

    cols = st.columns(3)

    case_options = [c for c in SEC_CASE_OPTIONS if c[0] in A1_CASES_WITH_CACHE]
    case_idx = cols[0].selectbox(
        "SEC seed case",
        options=range(len(case_options)),
        format_func=lambda i: case_options[i][1],
        key="a1_case_idx_locked",
    )
    case_id, _, native_dir = case_options[case_idx]

    td_idx = cols[1].selectbox(
        "Target ticker / date",
        options=range(len(TICKER_DATE_OPTIONS)),
        format_func=lambda i: f"{TICKER_DATE_OPTIONS[i][0]} ({TICKER_DATE_OPTIONS[i][1]})",
        key="a1_td_idx_locked",
    )
    ticker, date = TICKER_DATE_OPTIONS[td_idx]

    cols[2].markdown(
        f"<div style='padding-top:1.8rem;color:#64748b;font-size:0.88rem;'>"
        f"Native direction: <b>{native_dir}</b><br>"
        f"<span style='color:#94a3b8;font-size:0.78rem;'>(seeds are direction-locked)</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    _render_a1_run_controls(case_id, ticker, date, api_key_present=False)


def _render_a1_unlocked() -> None:
    """Free-form mode (API key set). All 8 SEC seeds available, custom
    ticker and date inputs."""
    import datetime as _dt

    st.success(
        "✨ **Free generation mode.** Pick any of the 8 SEC seeds and type "
        "any ticker / date. The LLM generates a fresh article (with QC) "
        "and the result is cached on disk for instant replay."
    )

    cols = st.columns([2, 1, 1, 1])

    case_options = SEC_CASE_OPTIONS
    case_idx = cols[0].selectbox(
        "SEC seed case (all 8 unlocked)",
        options=range(len(case_options)),
        format_func=lambda i: case_options[i][1],
        key="a1_case_idx_unlocked",
    )
    case_id, _, native_dir = case_options[case_idx]

    ticker_raw = cols[1].text_input(
        "Ticker",
        value="PLTR",
        max_chars=6,
        key="a1_ticker_unlocked",
        help="Any equity ticker symbol. Will be uppercased automatically.",
    )
    ticker = ticker_raw.strip().upper() or "PLTR"

    date_obj = cols[2].date_input(
        "Trade date",
        value=_dt.date(2025, 12, 9),
        min_value=_dt.date(2020, 1, 1),
        max_value=_dt.date(2026, 12, 31),
        key="a1_date_unlocked",
    )
    date = date_obj.strftime("%Y-%m-%d")

    cols[3].markdown(
        f"<div style='padding-top:1.8rem;color:#64748b;font-size:0.85rem;'>"
        f"Native direction:<br><b>{native_dir}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )

    _render_a1_run_controls(case_id, ticker, date, api_key_present=True)


def _render_a1_run_controls(
    case_id: str, ticker: str, date: str, *, api_key_present: bool
) -> None:
    """Generate button + async submit + future poll.

    The LLM call is submitted to a background thread pool so the user
    can switch to other attack panels while it runs and come back to
    see the result populated.
    """
    cols2 = st.columns([1, 1, 4])
    use_cache = cols2[0].toggle(
        "Use cached",
        value=not api_key_present,
        help="On = instant disk read. Off = live LLM call (~5-15s).",
        key=f"a1_use_cache_{int(api_key_present)}",
    )
    run_btn = cols2[1].button(
        "▶ Generate", type="primary",
        key=f"a1_run_btn_{int(api_key_present)}",
    )

    if not api_key_present and not use_cache:
        st.warning(
            "🔒 No OpenAI key in this session. Either paste your key in "
            "the **🔑 OpenAI API key** expander in the sidebar, or toggle "
            "**Use cached** to demo from the on-disk corpus."
        )

    if run_btn:
        st.session_state["a1_job"] = submit_async(
            "a1",
            run_fake_news_live,
            case_id, ticker, date,
            use_cache=use_cache,
            api_key=get_session_api_key() or None,
        )
        # Clear any stale prior result so the UI shows the spinner first
        st.session_state.pop("a1_last_result", None)
        st.session_state.pop("a1_error", None)
        st.rerun()

    _poll_attack_job("a1", FakeNewsResult, _render_a1_result)


def _poll_attack_job(
    key: str,
    result_type: type,
    render_fn,
) -> None:
    """Poll a session-stored AsyncJob and render its outcome.

    ``key`` is the prefix used for session_state ("a1" / "a2"). We look
    up ``{key}_job`` (the AsyncJob), ``{key}_last_result`` (the resolved
    result), and ``{key}_error`` (a failure message).

    While the job is in flight, we show a non-blocking status banner —
    the user is FREE to switch to a different sub-tab; when they come
    back, the next render naturally picks up the completed result
    because Streamlit reruns on tab switch.
    """
    job: Optional[AsyncJob] = st.session_state.get(f"{key}_job")
    if job is not None:
        if job.done:
            try:
                st.session_state[f"{key}_last_result"] = job.result()
            except Exception as e:
                msg = str(e)
                if "Missing credentials" in msg or "OPENAI_API_KEY" in msg:
                    st.session_state[f"{key}_error"] = (
                        "🔒 Cache miss + no API key. This combination has no "
                        "pre-generated payload. Paste a key in the sidebar "
                        "or pick a different combination."
                    )
                else:
                    st.session_state[f"{key}_error"] = f"Generation failed: {e}"
            st.session_state.pop(f"{key}_job", None)
        else:
            st.info(
                f"⏳ **Generating in background** ({int(job.elapsed_seconds)} s elapsed). "
                f"You can **switch to another attack** to talk about it — "
                f"the result will be waiting here when you switch back. "
                f"Click **🔄 Refresh** below to check now."
            )
            if st.button("🔄 Refresh", key=f"{key}_refresh"):
                st.rerun()

    error = st.session_state.get(f"{key}_error")
    if error:
        st.error(error)

    result = st.session_state.get(f"{key}_last_result")
    if isinstance(result, result_type):
        render_fn(result)


def _render_a1_result(r: FakeNewsResult) -> None:
    # Header line
    badge = "📦 cached" if r.used_cache else "✨ fresh"
    st.markdown(
        f"##### Generated article &nbsp;·&nbsp; "
        f"<span style='font-size:0.85rem;color:#64748b;'>{badge} · "
        f"{r.case_id} · {r.ticker} · {r.date} · {r.direction}</span>",
        unsafe_allow_html=True,
    )

    # QC verdict + scores
    cols = st.columns(5)
    verdict_color = {"pass": "#10b981", "fail": "#ef4444", "unchecked": "#94a3b8"}
    cols[0].markdown(
        f"<div style='text-align:center;'><b>QC verdict</b><br>"
        f"<span style='color:{verdict_color.get(r.qc_verdict,'#94a3b8')};font-size:1.5rem;'>"
        f"{r.qc_verdict.upper()}</span><br>"
        f"<span style='font-size:0.78rem;color:#64748b;'>{r.qc_attempts} attempt(s)</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    if r.qc_scores:
        score_labels = [
            ("logical_consistency", "Logic"),
            ("direction_alignment", "Direction"),
            ("stealth_plausibility", "Stealth"),
            ("content_purity", "Purity"),
        ]
        for i, (key, label) in enumerate(score_labels, start=1):
            score = r.qc_scores.get(key)
            if score is not None:
                cols[i].metric(label, f"{score}/5", delta=None)

    if r.qc_issues:
        st.markdown("**QC issues flagged:**")
        for issue in r.qc_issues:
            st.markdown(f"- {issue}")

    # The article itself
    st.markdown(
        f"<div class='report-card poisoned'>"
        f"<h4>📰 Generated fake article</h4>"
        f"{html.escape(r.article_text).replace(chr(10), '<br>')}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Action buttons
    cols3 = st.columns([2, 5])
    cols3[0].button(
        "📤 Send to Skeptic Live",
        type="primary",
        use_container_width=True,
        on_click=_send_to_skeptic,
        args=(r.article_text,),
        key="a1_send_skeptic",
    )

    with st.expander("🔬 Show raw text with [SYNTH-RED-TEAM] research marker"):
        st.code(r.raw_text_with_marker, language="text")
        st.caption(
            "The [SYNTH-RED-TEAM] tag is part of our IRB-equivalent protocol. "
            "It is stripped before injection so the agent under test has no "
            "marker to detect — but the marker remains in the audit log."
        )


# ----- A2 sub-panel --------------------------------------------------------
def _render_a2_panel(api_key_present: bool) -> None:
    """Two-mode panel:

    • No API key → ticker/date dropdown limited to 5 cached pairs.
    • API key   → free-form ticker + free-form date.
    """
    if api_key_present:
        _render_a2_unlocked()
    else:
        _render_a2_locked()


def _render_a2_locked() -> None:
    """Cached-only mode (no API key)."""
    st.info(
        "🔒 **Cached-only mode.** Pick one of the 5 ticker pairs × 2 directions "
        "we ship with. Paste a key in the sidebar to type any ticker / date."
    )

    cols = st.columns(3)
    td_idx = cols[0].selectbox(
        "Target ticker / date",
        options=range(len(TICKER_DATE_OPTIONS)),
        format_func=lambda i: f"{TICKER_DATE_OPTIONS[i][0]} ({TICKER_DATE_OPTIONS[i][1]})",
        key="a2_td_idx_locked",
    )
    ticker, date = TICKER_DATE_OPTIONS[td_idx]

    direction = cols[1].radio(
        "Direction", options=["bullish", "bearish"], horizontal=True,
        key="a2_direction_locked",
    )

    cols[2].markdown(
        "<div style='padding-top:1.8rem;color:#64748b;font-size:0.88rem;'>"
        "Output: <b>1 article</b> + <b>5 social posts</b><br>"
        "<span style='color:#94a3b8;font-size:0.78rem;'>"
        "institutional tone (no retail markers by design)</span></div>",
        unsafe_allow_html=True,
    )

    _render_a2_run_controls(ticker, date, direction, api_key_present=False)


def _render_a2_unlocked() -> None:
    """Free-form mode (API key set)."""
    import datetime as _dt

    st.success(
        "✨ **Free generation mode.** Type any ticker / date and pick a "
        "direction. The LLM produces 1 article + 5 institutional-tone "
        "social posts that explicitly cite the article — fabricating "
        "cross-source corroboration."
    )

    cols = st.columns([1, 1, 1, 1])

    ticker_raw = cols[0].text_input(
        "Ticker",
        value="PLTR",
        max_chars=6,
        key="a2_ticker_unlocked",
        help="Any equity ticker symbol. Will be uppercased automatically.",
    )
    ticker = ticker_raw.strip().upper() or "PLTR"

    date_obj = cols[1].date_input(
        "Trade date",
        value=_dt.date(2025, 12, 9),
        min_value=_dt.date(2020, 1, 1),
        max_value=_dt.date(2026, 12, 31),
        key="a2_date_unlocked",
    )
    date = date_obj.strftime("%Y-%m-%d")

    direction = cols[2].radio(
        "Direction", options=["bullish", "bearish"], horizontal=True,
        key="a2_direction_unlocked",
    )

    cols[3].markdown(
        "<div style='padding-top:1.8rem;color:#64748b;font-size:0.85rem;'>"
        "Output:<br><b>1 article + 5 posts</b>"
        "</div>",
        unsafe_allow_html=True,
    )

    _render_a2_run_controls(ticker, date, direction, api_key_present=True)


def _render_a2_run_controls(
    ticker: str, date: str, direction: str, *, api_key_present: bool
) -> None:
    """Generate button + async submit + future poll (parallels A1)."""
    cols2 = st.columns([1, 1, 4])
    use_cache = cols2[0].toggle(
        "Use cached",
        value=not api_key_present,
        help="On = instant disk read. Off = live LLM call (~10-20s).",
        key=f"a2_use_cache_{int(api_key_present)}",
    )
    run_btn = cols2[1].button(
        "▶ Generate", type="primary",
        key=f"a2_run_btn_{int(api_key_present)}",
    )

    if not api_key_present and not use_cache:
        st.warning(
            "🔒 No OpenAI key in this session. Paste your key in the "
            "**🔑 OpenAI API key** expander in the sidebar, or toggle "
            "**Use cached** to demo from the on-disk corpus."
        )

    if run_btn:
        st.session_state["a2_job"] = submit_async(
            "a2",
            run_cross_channel_live,
            ticker, date, direction,
            use_cache=use_cache,
            api_key=get_session_api_key() or None,
        )
        st.session_state.pop("a2_last_result", None)
        st.session_state.pop("a2_error", None)
        st.rerun()

    _poll_attack_job("a2", CrossChannelResult, _render_a2_result)


def _render_a2_result(r: CrossChannelResult) -> None:
    badge = "📦 cached" if r.used_cache else "✨ fresh"
    st.markdown(
        f"##### Generated coordinated bundle &nbsp;·&nbsp; "
        f"<span style='font-size:0.85rem;color:#64748b;'>{badge} · "
        f"{r.ticker} · {r.date} · {r.direction}</span>",
        unsafe_allow_html=True,
    )

    # Article side-by-side with social posts
    cols = st.columns([1, 1])
    with cols[0]:
        st.markdown(
            f"<div class='report-card poisoned'>"
            f"<h4>📰 Article (Bloomberg-style)</h4>"
            f"<b>{html.escape(r.article_headline)}</b><br><br>"
            f"{html.escape(r.article_body).replace(chr(10), '<br>')}"
            f"</div>",
            unsafe_allow_html=True,
        )

    with cols[1]:
        st.markdown(
            "<div class='report-card poisoned'>"
            "<h4>💬 5 Social posts (institutional personas)</h4>",
            unsafe_allow_html=True,
        )
        persona_handle = {
            "options-flow":     "@flow_desk_anon",
            "buyside-analyst":  "@buyside_pm_anon",
            "tape-reader":      "@tape_reader_anon",
            "fundamentals":     "@fundamentals_anon",
            "anon-tipster":     "@side_channel_anon",
        }
        for p in r.social_posts:
            handle = persona_handle.get(p["persona"], f"@{p['persona']}_anon")
            st.markdown(
                f"<div style='margin-bottom:0.6rem;'>"
                f"<b style='color:#dc2626;'>{handle}</b> "
                f"<span style='color:#64748b;font-size:0.78rem;'>({p['persona']})</span><br>"
                f"<span style='font-size:0.86rem;'>{html.escape(p['text'])}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    # Action buttons
    cols3 = st.columns([2, 2, 3])
    cols3[0].button(
        "📤 Send article to Skeptic",
        type="primary",
        use_container_width=True,
        on_click=_send_to_skeptic,
        args=(f"{r.article_headline}\n\n{r.article_body}",),
        key="a2_send_skeptic",
    )
    cols3[1].button(
        "📤 Send posts to Skeptic",
        use_container_width=True,
        on_click=_send_to_skeptic,
        args=(
            "\n\n".join(f"{p['persona']}: {p['text']}" for p in r.social_posts),
        ),
        key="a2_send_skeptic_posts",
    )

    with st.expander("🔬 Show combined injection block (with nested headers)"):
        st.caption(
            "This is the actual text that gets injected through `route_to_vendor`. "
            "Note the nested `--- RECENT SOCIAL MEDIA POSTS ---` separator — it's "
            "what makes News Analyst and Social Analyst each pick out their "
            "own segment, fabricating cross-source corroboration."
        )
        st.code(r.combined_block, language="text")


# ----- A5 sub-panel --------------------------------------------------------
def _render_a5_panel(is_unlocked: bool) -> None:
    """Memory poisoning generates entirely from local templates + RNG —
    NO LLM call. So the locked / unlocked split is just about whether
    the user can type custom ticker / date.
    """
    st.info(
        "🧠 **Memory Poisoning attacks the third channel: the Portfolio "
        "Manager's long-term memory.** Unlike Fake News and Cross-Channel, "
        "this attack uses no LLM — 8 fabricated past trades are produced "
        "from a hand-written thesis-template pool plus a seeded RNG. "
        "Simpler to construct, but it's the attack with the largest "
        "measured effect in our paper "
        "(bearish direction, Δ = −0.42, p_BH < 0.0001)."
    )

    if is_unlocked:
        _render_a5_unlocked()
    else:
        _render_a5_locked()


def _render_a5_locked() -> None:
    cols = st.columns(3)
    td_idx = cols[0].selectbox(
        "Target ticker / date",
        options=range(len(TICKER_DATE_OPTIONS)),
        format_func=lambda i: f"{TICKER_DATE_OPTIONS[i][0]} ({TICKER_DATE_OPTIONS[i][1]})",
        key="a5_td_idx_locked",
    )
    ticker, date = TICKER_DATE_OPTIONS[td_idx]

    direction = cols[1].radio(
        "Direction", options=["bullish", "bearish"], horizontal=True,
        key="a5_direction_locked",
    )

    seed = cols[2].number_input(
        "Seed", min_value=0, max_value=99, value=0,
        key="a5_seed_locked",
        help="Deterministic — same seed gives identical 8 entries.",
    )

    _render_a5_run(ticker, date, direction, int(seed))


def _render_a5_unlocked() -> None:
    import datetime as _dt

    cols = st.columns([1, 1, 1, 1])
    ticker_raw = cols[0].text_input(
        "Ticker", value="PLTR", max_chars=6, key="a5_ticker_unlocked",
    )
    ticker = ticker_raw.strip().upper() or "PLTR"

    date_obj = cols[1].date_input(
        "Trade date",
        value=_dt.date(2025, 12, 9),
        min_value=_dt.date(2020, 1, 1),
        max_value=_dt.date(2026, 12, 31),
        key="a5_date_unlocked",
    )
    date = date_obj.strftime("%Y-%m-%d")

    direction = cols[2].radio(
        "Direction", options=["bullish", "bearish"], horizontal=True,
        key="a5_direction_unlocked",
    )

    seed = cols[3].number_input(
        "Seed", min_value=0, max_value=99, value=0,
        key="a5_seed_unlocked",
    )

    _render_a5_run(ticker, date, direction, int(seed))


def _render_a5_run(ticker: str, date: str, direction: str, seed: int) -> None:
    cols2 = st.columns([1, 4])
    if cols2[0].button("▶ Generate", type="primary", key="a5_run_btn"):
        try:
            result = run_memory_poisoning_live(
                ticker, date, direction, seed=seed,
            )
            st.session_state["a5_last_result"] = result
        except Exception as e:
            st.error(f"Memory poisoning generation failed: {e}")
            return

    result = st.session_state.get("a5_last_result")
    if isinstance(result, MemoryPoisoningResult):
        _render_a5_result(result)


def _render_a5_result(r: MemoryPoisoningResult) -> None:
    st.markdown(
        f"##### Generated memory log &nbsp;·&nbsp; "
        f"<span style='font-size:0.85rem;color:#64748b;'>"
        f"{r.ticker} · {r.date} · {r.direction} · seed={r.seed}</span>",
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    cols[0].metric("Entries", len(r.entries), help="5 same-ticker + 3 cross-ticker = full PM cap")
    cols[1].metric(
        "Avg fabricated alpha",
        f"+{sum(e.alpha_pct for e in r.entries) / len(r.entries):.1f}%",
        help="Calibrated to look real-but-significant (4-8% range)",
    )
    cols[2].metric(
        "All entries direction",
        r.entries[0].rating,
        help="Every fabricated trade nudges PM the same way",
    )

    st.markdown(
        "**Each entry mimics the format the real Portfolio Manager writes "
        "to its memory log.** When written before a trial starts, it bypasses "
        "the News, Social, Trader, and Risk Team agents entirely — only the "
        "PM reads memory."
    )

    # Render each entry as a card
    for i, e in enumerate(r.entries, 1):
        is_same_ticker = e.ticker == r.ticker
        badge = "📌 same-ticker" if is_same_ticker else "🔗 cross-ticker"
        badge_color = "#dc2626" if is_same_ticker else "#9333ea"

        st.markdown(
            f"<div class='report-card poisoned'>"
            f"<h4>"
            f"#{i} &nbsp; <code>[{e.date} | {e.ticker} | {e.rating} | "
            f"{e.raw_return_pct:+.1f}% | {e.alpha_pct:+.1f}% | {e.hold_days}d]</code> "
            f"&nbsp;<span style='color:{badge_color};font-size:0.78rem;font-weight:normal;text-transform:none;'>{badge}</span>"
            f"</h4>"
            f"<b>Theme:</b> {html.escape(e.theme)}<br>"
            f"<b>Thesis:</b> {html.escape(e.thesis)}<br><br>"
            f"<b>Reflection:</b><br>"
            f"<mark class='poison-hl'>{html.escape(e.reflection)}</mark>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with st.expander("🔬 Full rendered memory log (what gets written to disk)"):
        st.code(r.rendered_log, language="text")
        st.caption(
            "This is exactly the file that gets written to the trial's "
            "isolated memory log before TradingAgents starts the run. "
            "The Portfolio Manager reads it as if it were genuine past "
            "experience — and the directive 'LESSON LEARNED ... hard rule "
            "in my playbook' phrasing nudges it from anecdote to decision rule."
        )


# ---------------------------------------------------------------------------
# Skeptic Live tab
# ---------------------------------------------------------------------------
def _set_skeptic_sample(key: str) -> None:
    """Callback: write sample text into the textarea's session_state key."""
    st.session_state["skeptic_text"] = SAMPLE_NEWS[key]["text"]
    # Clear stale verdict so user sees the change before running again
    st.session_state.pop("skeptic_last_raw", None)


def render_skeptic_tab() -> None:
    st.markdown("#### 🛡️ Defense panel — live invocation")
    st.caption(
        "Two defenses, two different angles on the same input. **Skeptic** "
        "is a review-layer LLM that runs a 7-item content checklist (gpt-4o-mini, "
        "T=0, ~3-5 s). **Anomaly Filter** is an input-layer statistical detector "
        "(9 lexical features + bigram JS divergence vs a real-news baseline; "
        "no LLM, instant). Picking 'Side-by-side' shows both verdicts on the "
        "same input — illustrating why the paper concludes that *defense "
        "composition is the unit of analysis*."
    )

    # Pop pending notice from Attack lab → Skeptic chaining
    pending = st.session_state.pop("skeptic_pending_notice", None)
    if pending:
        st.success(pending)

    # Initialize textarea state
    if "skeptic_text" not in st.session_state:
        st.session_state["skeptic_text"] = SAMPLE_NEWS["clean_pltr"]["text"]

    is_unlocked = api_key_present()

    defense_mode = st.radio(
        "Defense to run",
        options=["skeptic", "anomaly", "both"],
        format_func=lambda k: {
            "skeptic": "🛡️ Skeptic Agent  (review-layer LLM, ~3-5 s)",
            "anomaly": "🔬 Anomaly Filter  (input-layer statistical, instant, no API)",
            "both":    "⚖️ Side-by-side  (run both on the same input)",
        }[k],
        horizontal=True,
        key="defense_mode_radio",
    )

    # Sample buttons (use on_click to mutate session_state BEFORE next render)
    cols = st.columns(3)
    sample_keys = list(SAMPLE_NEWS.keys())
    for i, key in enumerate(sample_keys[:3]):
        cols[i].button(
            SAMPLE_NEWS[key]["label"],
            use_container_width=True,
            on_click=_set_skeptic_sample,
            args=(key,),
            key=f"sample_btn_{key}",
        )

    # Textarea — same key as session_state so callbacks update it
    st.text_area(
        "News text to evaluate",
        height=180,
        max_chars=2000,
        key="skeptic_text",
    )

    cols2 = st.columns([1, 1, 4])

    # Skeptic needs the cached toggle (it makes a real LLM call); the
    # Anomaly Filter is purely local and instant, so cached toggle is
    # only relevant when Skeptic is in the run set.
    skeptic_in_run = defense_mode in ("skeptic", "both")
    use_cache = cols2[0].toggle(
        "Use cached Skeptic verdict",
        value=not is_unlocked,
        help=(
            "Only applies to the Skeptic LLM call. The Anomaly Filter "
            "runs locally and never needs caching."
        ),
        key="skeptic_use_cache",
        disabled=not skeptic_in_run,
    )
    run_button = cols2[1].button(
        "▶ Run defense", type="primary", key="defense_run_btn",
    )

    if skeptic_in_run and not is_unlocked and not use_cache:
        st.warning(
            "🔒 No OpenAI key. Paste your key in the sidebar, or toggle "
            "**Use cached Skeptic verdict** to demo from the on-disk corpus."
        )

    if run_button:
        text = st.session_state["skeptic_text"]
        try:
            if defense_mode in ("skeptic", "both"):
                with st.spinner("Skeptic deliberating…"):
                    st.session_state["skeptic_last_raw"] = run_skeptic_live(
                        text,
                        use_cache=use_cache,
                        api_key=get_session_api_key() or None,
                    )
            if defense_mode in ("anomaly", "both"):
                with st.spinner("Anomaly Filter scoring…"):
                    st.session_state["anomaly_last_result"] = (
                        run_anomaly_filter_live(text)
                    )
        except Exception as e:
            st.error(f"Defense call failed: {e}")
            return

    # Render results based on the selected mode
    if defense_mode == "skeptic":
        raw = st.session_state.get("skeptic_last_raw")
        if raw:
            verdict = parse_skeptic_response(raw)
            _render_verdict(verdict, raw)
    elif defense_mode == "anomaly":
        anom = st.session_state.get("anomaly_last_result")
        if isinstance(anom, AnomalyFilterResult):
            _render_anomaly_result(anom)
    else:  # both — side by side
        cols_sxs = st.columns(2)
        with cols_sxs[0]:
            st.markdown("##### 🛡️ Skeptic verdict")
            raw = st.session_state.get("skeptic_last_raw")
            if raw:
                verdict = parse_skeptic_response(raw)
                _render_verdict(verdict, raw)
            else:
                st.caption("Press ▶ Run defense to populate.")
        with cols_sxs[1]:
            st.markdown("##### 🔬 Anomaly Filter verdict")
            anom = st.session_state.get("anomaly_last_result")
            if isinstance(anom, AnomalyFilterResult):
                _render_anomaly_result(anom, compact=True)
            else:
                st.caption("Press ▶ Run defense to populate.")


def _render_anomaly_result(r: AnomalyFilterResult, *, compact: bool = False) -> None:
    """Render Anomaly Filter scores (lexical + FinBERT when available)."""
    verdict_color = {
        "natural": "#10b981",
        "borderline": "#f59e0b",
        "anomalous": "#ef4444",
    }
    color = verdict_color.get(r.verdict, "#94a3b8")

    # Top metrics row — always shows lexical + verdict; adds FinBERT only
    # when present (live torch / shipped cached score for known samples).
    has_finbert = r.score_finbert is not None
    cols = st.columns(4 if has_finbert else 3)
    cols[0].metric(
        "Lexical score",
        f"{r.score_lexical:.3f}",
        help="9 hand-engineered features + bigram JS divergence vs real-news baseline. 0 = anomalous, 1 = real-news-like.",
    )

    if has_finbert:
        cols[1].metric(
            f"FinBERT score",
            f"{r.score_finbert:.3f}",  # type: ignore[arg-type]
            help=(
                "FinBERT [CLS] embedding cosine similarity to a real-news "
                f"centroid. Source: {r.finbert_source}. "
                "Compare to the lexical score — divergence reveals which "
                "backend each kind of fake content fools."
            ),
        )
        verdict_col = cols[2]
        len_col = cols[3]
    else:
        verdict_col = cols[1]
        len_col = cols[2]

    verdict_col.markdown(
        f"<div style='text-align:center;'><b>Lexical verdict</b><br>"
        f"<span style='color:{color};font-size:1.4rem;font-weight:700;'>"
        f"{r.verdict.upper()}</span></div>",
        unsafe_allow_html=True,
    )
    len_col.metric("Length", f"{r.char_count} chars")

    if has_finbert and not compact:
        if r.finbert_source == "cached":
            st.caption(
                "💡 **FinBERT score above is precomputed** (the deployed app "
                "doesn't ship torch + the 440 MB FinBERT model). Locally with "
                "`pip install torch transformers`, FinBERT runs live."
            )
        # Surface the cross-backend interpretation directly.
        diff = (r.score_finbert or 0.0) - r.score_lexical
        if abs(diff) >= 0.2:
            backend_label = (
                "**FinBERT rates this much more real-looking than lexical** — "
                "this is the canonical signature of *institutional-tone synthetic "
                "content* (proper financial vocabulary fools the deep model; "
                "surface-statistics catch what FinBERT misses)."
                if diff > 0 else
                "**Lexical rates this much more real-looking than FinBERT** — "
                "the input is statistically natural-looking but semantically off."
            )
            st.markdown(f"<small>{backend_label}</small>", unsafe_allow_html=True)

    feature_label = {
        "sent_count":          "Sentences",
        "avg_sent_len":        "Avg sent len",
        "sent_len_std":        "Sent-len std",
        "avg_word_len":        "Avg word len",
        "type_token_ratio":    "Type/token ratio",
        "punct_density":       "Punctuation density",
        "hedge_count":         "Hedge words",
        "retail_marker_count": "Retail markers",
        "char_count":          "Character count",
    }

    if not compact:
        st.markdown("**9 lexical features extracted from the input:**")
    else:
        st.caption("Lexical features (compact view):")

    feat_cols = st.columns(3) if not compact else st.columns(2)
    items = list(r.lexical_features.items())
    for i, (key, val) in enumerate(items):
        col = feat_cols[i % len(feat_cols)]
        if isinstance(val, float):
            val_str = f"{val:.2f}" if val < 100 else f"{val:.0f}"
        else:
            val_str = str(val)
        col.markdown(
            f"<div style='font-size:0.84rem;color:#475569;'>"
            f"<b>{feature_label.get(key, key)}:</b> "
            f"<code>{val_str}</code></div>",
            unsafe_allow_html=True,
        )


def _render_verdict(verdict: SkepticVerdict, raw: str) -> None:
    st.markdown("##### Skeptic verdict")
    cols = st.columns(3)
    cols[0].metric("Concerns flagged", verdict.num_concerns)
    cols[1].metric("Confidence", verdict.confidence.title())
    cols[2].metric("Recommended caution", verdict.caution.title())

    if verdict.concerns:
        st.markdown("**Flagged concerns (7-item checklist hits):**")
        for i, c in enumerate(verdict.concerns, 1):
            st.markdown(f"- **[{i}]** {c}")
    else:
        st.success("✅ No concerns flagged — Skeptic accepts the report.")

    with st.expander("Raw Skeptic output"):
        st.code(raw, language="text")
