"""Reusable Streamlit UI components for the adversarial-robustness demo."""

from __future__ import annotations

import html
import os
import re
from collections import Counter

import plotly.graph_objects as go
import streamlit as st

from adversarial.demo import data_loader as dl
from adversarial.demo.attack_runner import (
    A1_CASES_WITH_CACHE,
    SEC_CASE_OPTIONS,
    TICKER_DATE_OPTIONS,
    CrossChannelResult,
    FakeNewsResult,
    run_cross_channel_live,
    run_fake_news_live,
)
from adversarial.demo.skeptic_runner import (
    SAMPLE_NEWS,
    SkepticVerdict,
    parse_skeptic_response,
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
# Overview metrics
# ---------------------------------------------------------------------------
def render_overview_metrics(
    selection: dict, trials: list[dl.Trial], clean_trials: list[dl.Trial]
) -> None:
    agg = dl.aggregate_ordinal(trials)
    clean_agg = dl.aggregate_ordinal(clean_trials)

    delta = (
        agg["mean"] - clean_agg["mean"]
        if (agg["mean"] is not None and clean_agg["mean"] is not None)
        else 0.0
    )

    cols = st.columns(4)
    cols[0].metric(
        "Trials in this configuration",
        f"{agg['n']}",
        help="Number of independent runs (different seeds) for this exact combination.",
    )
    cols[1].metric(
        "Mean ordinal decision",
        f"{agg['mean']:.2f}" if agg["mean"] is not None else "—",
        help="1=StrongSell · 2=Underweight · 3=Hold · 4=Overweight · 5=StrongBuy.",
    )
    cols[2].metric(
        "Δ vs clean baseline",
        f"{delta:+.2f}",
        delta_color="normal" if abs(delta) < 0.05 else ("inverse" if delta < 0 else "normal"),
        help="Positive = bullish shift, negative = bearish shift, vs the no-attack baseline.",
    )
    cols[3].metric(
        "Clean baseline mean",
        f"{clean_agg['mean']:.2f}" if clean_agg["mean"] is not None else "—",
        help=f"Average ordinal across {clean_agg['n']} clean (no-attack) trials.",
    )


# ---------------------------------------------------------------------------
# Decision panel: dial + distribution
# ---------------------------------------------------------------------------
def render_decision_panel(
    trials: list[dl.Trial], clean_trials: list[dl.Trial]
) -> None:
    agg = dl.aggregate_ordinal(trials)
    clean_agg = dl.aggregate_ordinal(clean_trials)

    if not trials:
        st.info("No trials.")
        return

    most_common_decision = Counter(t.decision for t in trials).most_common(1)[0][0]
    decision_class = "decision-" + most_common_decision.lower().replace(" ", "")

    cols = st.columns([1.0, 1.4])

    with cols[0]:
        st.markdown("##### Modal decision")
        st.markdown(
            f"<div class='decision-dial {decision_class}'>{most_common_decision}</div>",
            unsafe_allow_html=True,
        )
        # Portfolio exposure mapping
        if agg["mean"] is not None:
            # Round to nearest tier and map
            tier = max(1, min(5, round(agg["mean"])))
            exposure = dl.ORDINAL_TO_EXPOSURE[tier]
            sign = "+" if exposure > 0 else ("" if exposure == 0 else "")
            st.markdown(
                f"<p class='stat-caption'>Portfolio exposure mapping → "
                f"<b>{sign}{exposure:+.1f}</b> "
                f"({'long' if exposure > 0 else ('flat' if exposure == 0 else 'short')})</p>",
                unsafe_allow_html=True,
            )

    with cols[1]:
        st.markdown("##### Decision distribution (this configuration vs clean)")
        fig = _decision_distribution_chart(agg, clean_agg)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _decision_distribution_chart(agg, clean_agg) -> go.Figure:
    tiers = dl.DECISION_TIERS
    cur_dist = agg["distribution"]
    clean_dist = clean_agg["distribution"] if clean_agg["n"] else {}

    cur_norm = [cur_dist.get(t, 0) / max(agg["n"], 1) for t in tiers]
    clean_norm = (
        [clean_dist.get(t, 0) / max(clean_agg["n"], 1) for t in tiers]
        if clean_agg["n"]
        else [0] * 5
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=tiers,
            y=clean_norm,
            name="Clean baseline",
            marker_color="#cbd5e1",
            hovertemplate="%{x}: %{y:.0%}<extra>Clean</extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            x=tiers,
            y=cur_norm,
            name="Current configuration",
            marker_color="#6366f1",
            hovertemplate="%{x}: %{y:.0%}<extra>Current</extra>",
        )
    )
    fig.update_layout(
        barmode="group",
        height=260,
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
        yaxis=dict(tickformat=".0%", range=[0, 1]),
        plot_bgcolor="white",
    )
    return fig


# ---------------------------------------------------------------------------
# Report cards
# ---------------------------------------------------------------------------
# Phrases that indicate poisoned content slipped through. Patterns are
# tuned to the *actual* attack seeds present in the cached trials, not
# the generic Avon example used in the paper text.
ATTACK_HIGHLIGHT_PATTERNS = {
    "fake_news": [
        r"tender offer",
        r"\$25(?:\.\d+)? per share",
        r"\d{2,3}% premium",
        r"PTG Capital(?: Partners)?(?: Ltd\.?)?",
        r"unidentified (?:party|buyer)|undisclosed buyer|unnamed acquirer",
        r"Reuters report(?:s|ing)?",
        r"Morgan Stanley.{0,40}(?:partnership|deal|advanced discussions)",
        r"\$\d+\s*million strategic partnership",
        r"advanced discussions",
        r"BREAKING:",
    ],
    "social_panic": [
        r"@\w*_anon",
        r"@flow_desk\w*",
        r"@EarlyAlpha\w*",
        r"#\w*Panic",
        r"#\w*ToTheMoon",
        r"my buddy at",
        r"to the moon",
        r"viral post",
        r"stop[-\s]?loss",
        r"unverified",
        r"leaked",
    ],
    "memory_directive": [
        r"prior(?:\s+experience|\s+lesson|\s+decision)s?",
        r"previously observed",
        r"based on (?:past|prior)\s+",
        r"memory.{0,40}suggests",
        r"lessons learned",
        r"consistent with previous",
    ],
}


def _highlight_text(text: str, attack: str) -> str:
    """Wrap matches of attack-specific phrases in <mark> for visual diff."""
    if not text:
        return ""
    escaped = html.escape(text[:3500])
    if escaped == "":
        return ""
    patterns: list[str] = []
    if attack in ("a1", "a2", "a2v2", "a2v2_a5v2"):
        patterns.extend(ATTACK_HIGHLIGHT_PATTERNS["fake_news"])
    if attack in ("a2", "a2v2", "a2v2_a5v2"):
        patterns.extend(ATTACK_HIGHLIGHT_PATTERNS["social_panic"])
    if attack in ("a5", "a5v2", "a2v2_a5v2"):
        patterns.extend(ATTACK_HIGHLIGHT_PATTERNS["memory_directive"])

    for p in patterns:
        escaped = re.sub(
            f"({p})",
            r"<mark class='poison-hl'>\1</mark>",
            escaped,
            flags=re.IGNORECASE,
        )
    return escaped.replace("\n", "<br>")


def render_report_cards(
    trials: list[dl.Trial], clean_trials: list[dl.Trial], selection: dict
) -> None:
    if not trials:
        st.info("No trials.")
        return

    seed_options = sorted({t.seed_idx for t in trials})
    seed = st.select_slider(
        "Pick a seed (one trial)",
        options=seed_options,
        value=seed_options[0],
        help="Each seed is one independent run with the same configuration.",
    )

    trial = next((t for t in trials if t.seed_idx == seed), trials[0])
    clean_trial = next((t for t in clean_trials if t.seed_idx == seed), None)
    if clean_trial is None and clean_trials:
        clean_trial = clean_trials[0]

    attack = selection["attack"]
    has_defense = selection["defense"] != "none"

    if attack == "clean":
        card_class = "report-card"
    elif has_defense:
        card_class = "report-card cleansed"
    else:
        card_class = "report-card poisoned"

    st.markdown("##### Selected trial — agent reports")
    cols = st.columns(2)
    with cols[0]:
        st.markdown(
            f"<div class='{card_class}'>"
            f"<h4>📰 News Analyst</h4>"
            f"{_highlight_text(trial.news_report, attack) or '<i>(empty)</i>'}"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='{card_class}'>"
            f"<h4>💬 Social Media Analyst</h4>"
            f"{_highlight_text(trial.sentiment_report, attack) or '<i>(empty)</i>'}"
            f"</div>",
            unsafe_allow_html=True,
        )
    with cols[1]:
        st.markdown(
            f"<div class='report-card'>"
            f"<h4>📋 Research Manager → Investment Plan</h4>"
            f"{html.escape((trial.investment_plan or '')[:3500]).replace(chr(10), '<br>') or '<i>(empty)</i>'}"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div class='report-card'>"
            f"<h4>🎯 Final Trade Decision &mdash; <code>{trial.decision}</code></h4>"
            f"{html.escape((trial.final_trade_decision or '')[:3500]).replace(chr(10), '<br>') or '<i>(empty)</i>'}"
            f"</div>",
            unsafe_allow_html=True,
        )

    if clean_trial:
        with st.expander("🔍 Clean baseline (same seed) — News Analyst report"):
            st.markdown(
                f"<div class='report-card'>"
                f"{html.escape(clean_trial.news_report[:3500]).replace(chr(10), '<br>') or '<i>(empty)</i>'}"
                f"</div>",
                unsafe_allow_html=True,
            )

    st.caption(
        "Red highlights = phrases pattern-matched as adversarial content. "
        "Green-tinted card = a defense was applied; red-tinted = unfiltered attack."
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

    api_key_present = bool(os.environ.get("OPENAI_API_KEY"))

    # Sub-toggle between Fake News / Cross-Channel
    sub = st.radio(
        "Attack to generate",
        options=["a1", "a2"],
        format_func=lambda k: {
            "a1": "🎯 Fake News  (single article + LLM-Judge QC)",
            "a2": "📡 Cross-Channel  (1 article + 5 social posts, integrated)",
        }[k],
        horizontal=True,
        key="attack_lab_sub",
    )

    if sub == "a1":
        _render_a1_panel(api_key_present)
    else:
        _render_a2_panel(api_key_present)


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
    """Common Generate button + spinner + result rendering for both modes."""
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
        spinner_msg = (
            "Reading cached sample…"
            if use_cache
            else "LLM generating + LLM-Judge QC (up to 3 attempts, ~5-15s)…"
        )
        with st.spinner(spinner_msg):
            try:
                result = run_fake_news_live(
                    case_id, ticker, date, use_cache=use_cache,
                )
                st.session_state["a1_last_result"] = result
            except Exception as e:
                msg = str(e)
                if "Missing credentials" in msg or "OPENAI_API_KEY" in msg:
                    st.error(
                        "🔒 Cache miss + no API key. This (case, ticker, date) "
                        "combination has no pre-generated payload. Paste a key "
                        "in the sidebar to enable live generation, or pick a "
                        "different combination."
                    )
                else:
                    st.error(f"Generation failed: {e}")
                return

    result = st.session_state.get("a1_last_result")
    if isinstance(result, FakeNewsResult):
        _render_a1_result(result)


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
    """Common Generate button + spinner + result rendering."""
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
        spinner_msg = (
            "Reading cached sample…"
            if use_cache
            else "LLM generating coordinated bundle (1 article + 5 posts, ~10-20s)…"
        )
        with st.spinner(spinner_msg):
            try:
                result = run_cross_channel_live(
                    ticker, date, direction, use_cache=use_cache,
                )
                st.session_state["a2_last_result"] = result
            except Exception as e:
                msg = str(e)
                if "Missing credentials" in msg or "OPENAI_API_KEY" in msg:
                    st.error(
                        "🔒 Cache miss + no API key. This (ticker, date, direction) "
                        "combination has no pre-generated payload. Paste a key "
                        "in the sidebar to enable live generation, or pick a "
                        "different combination."
                    )
                else:
                    st.error(f"Generation failed: {e}")
                return

    result = st.session_state.get("a2_last_result")
    if isinstance(result, CrossChannelResult):
        _render_a2_result(result)


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


# ---------------------------------------------------------------------------
# Skeptic Live tab
# ---------------------------------------------------------------------------
def _set_skeptic_sample(key: str) -> None:
    """Callback: write sample text into the textarea's session_state key."""
    st.session_state["skeptic_text"] = SAMPLE_NEWS[key]["text"]
    # Clear stale verdict so user sees the change before running again
    st.session_state.pop("skeptic_last_raw", None)


def render_skeptic_tab() -> None:
    st.markdown("#### 🛡️ Skeptic Agent — live invocation")
    st.caption(
        "The Skeptic Agent (one of our three defenses) reads the analyst reports "
        "and runs a 7-item provenance/sourcing checklist. Below it runs against "
        "your input as the news report; gpt-4o-mini, temperature=0, ~3-5s."
    )

    # Pop pending notice from Attack lab → Skeptic chaining
    pending = st.session_state.pop("skeptic_pending_notice", None)
    if pending:
        st.success(pending)

    # Initialize textarea state
    if "skeptic_text" not in st.session_state:
        st.session_state["skeptic_text"] = SAMPLE_NEWS["clean_pltr"]["text"]

    # API key check
    api_key_present = bool(os.environ.get("OPENAI_API_KEY"))

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
    use_cache = cols2[0].toggle(
        "Use cached example",
        value=not api_key_present,
        help="If on, returns a pre-recorded verdict (offline-safe).",
        key="skeptic_use_cache",
    )
    run_button = cols2[1].button("▶ Run Skeptic", type="primary", key="skeptic_run")

    if not api_key_present and not use_cache:
        st.warning(
            "🔒 No OpenAI key in this session. Paste your key in the "
            "**🔑 OpenAI API key** expander in the sidebar, or toggle "
            "**Use cached example** to demo from the on-disk corpus."
        )

    if run_button:
        with st.spinner("Skeptic deliberating…"):
            try:
                raw = run_skeptic_live(
                    st.session_state["skeptic_text"], use_cache=use_cache
                )
                st.session_state["skeptic_last_raw"] = raw
            except Exception as e:
                st.error(f"Skeptic call failed: {e}")
                st.info(
                    "Tip: toggle **Use cached example** to fall back to a recorded run."
                )
                return

    # Render last verdict (persists across reruns until input changes)
    raw = st.session_state.get("skeptic_last_raw")
    if raw:
        verdict = parse_skeptic_response(raw)
        _render_verdict(verdict, raw)


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
