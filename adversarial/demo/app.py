"""TradingAgents Adversarial Robustness — Live Demo.

Streamlit app for the project final demonstration. Combines:
  • Cached interactive lookup over 1,200+ pre-computed trials.
  • Live Skeptic Agent invocation against user-supplied news text.

Run with:
    streamlit run adversarial/demo/app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

# Ensure project root is on sys.path so we can import adversarial.* modules.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Auto-load .env from project root so OPENAI_API_KEY is picked up
# without requiring the user to export it in the shell.
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from adversarial.demo import data_loader as dl  # noqa: E402
from adversarial.demo.ui_components import (  # noqa: E402
    render_attack_lab_tab,
    render_decision_panel,
    render_overview_metrics,
    render_report_cards,
    render_skeptic_tab,
    render_top_banner,
)

TICKERS_WITH_DEFENSE = {"PLTR", "HOOD", "SNOW"}

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="TradingAgents · Adversarial Robustness Demo",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
def _inject_css() -> None:
    st.markdown(
        """
        <style>
        /* Tighter top padding */
        .block-container { padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1400px; }

        /* Large decision dial */
        .decision-dial {
            font-size: 3.4rem;
            font-weight: 700;
            text-align: center;
            padding: 0.6rem 0;
            letter-spacing: -1px;
        }
        .decision-strongbuy   { color: #10b981; }
        .decision-overweight  { color: #34d399; }
        .decision-hold        { color: #94a3b8; }
        .decision-underweight { color: #fb923c; }
        .decision-strongsell  { color: #ef4444; }

        .delta-up   { color: #10b981; font-weight: 600; }
        .delta-down { color: #ef4444; font-weight: 600; }
        .delta-flat { color: #94a3b8; font-weight: 600; }

        /* Report card */
        .report-card {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-left: 4px solid #6366f1;
            border-radius: 6px;
            padding: 1rem 1.2rem;
            margin-bottom: 0.8rem;
            font-size: 0.88rem;
            line-height: 1.5;
            max-height: 360px;
            overflow-y: auto;
        }
        .report-card h4 {
            margin: 0 0 0.4rem 0;
            font-size: 0.95rem;
            color: #475569;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .report-card.poisoned { border-left-color: #ef4444; background: #fef2f2; }
        .report-card.cleansed { border-left-color: #10b981; background: #f0fdf4; }

        /* Highlighted span (poisoned content) */
        mark.poison-hl { background: #fecaca; padding: 1px 3px; border-radius: 3px; }

        /* Sidebar polish */
        section[data-testid="stSidebar"] {
            background: #f1f5f9;
        }

        /* Tabs */
        button[role="tab"] { font-size: 0.95rem; font-weight: 500; }

        /* Stat caption */
        .stat-caption {
            color: #64748b;
            font-size: 0.78rem;
            text-align: center;
            margin-top: -0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


_inject_css()


# ---------------------------------------------------------------------------
# Sidebar — API key input (deployment-friendly: BYO key, never stored)
# ---------------------------------------------------------------------------
def _build_api_key_input() -> None:
    """Let the user paste their own OpenAI key for the live tabs.

    The key is set via os.environ for the duration of this Streamlit
    session. It is never logged, never persisted to disk, and never
    pushed to the deployment's environment. Without a key, all tabs
    still work in cached mode.
    """
    with st.sidebar:
        env_key_present = bool(os.environ.get("OPENAI_API_KEY"))

        with st.expander("🔑 OpenAI API key  (for live tabs)", expanded=not env_key_present):
            if env_key_present:
                st.success("✅ Using key from environment.")
            else:
                user_key = st.text_input(
                    "Paste your OpenAI API key",
                    value="",
                    type="password",
                    help=(
                        "The Attack lab and Skeptic Live tabs make real "
                        "OpenAI calls — they need a key. Paste yours here "
                        "to unlock them. The key stays in this session "
                        "only; it is never stored or pushed back to the app."
                    ),
                    key="user_openai_key",
                    placeholder="sk-...",
                )
                if user_key.strip():
                    os.environ["OPENAI_API_KEY"] = user_key.strip()
                    st.success("✅ Key set for this session — live tabs unlocked.")
                else:
                    st.info(
                        "🔒 No key — live tabs run in **cached-only** mode. "
                        "All other tabs work normally. "
                        "[Get a key →](https://platform.openai.com/api-keys)"
                    )


# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
def _build_sidebar() -> dict:
    with st.sidebar:
        st.markdown("### 🎯 Demo controls")

        direction = st.radio(
            "Bias direction",
            options=["bullish", "bearish"],
            horizontal=True,
            help="Which directional attacks to explore.",
        )

        tickers = dl.get_tickers(direction)
        ticker = st.selectbox("Ticker", tickers, index=tickers.index("PLTR") if "PLTR" in tickers else 0)

        if ticker not in TICKERS_WITH_DEFENSE:
            st.info(
                f"ℹ️ **{ticker}** has no defense matrix in this run — only "
                "*None* defense is available. For defense exploration, pick "
                "**PLTR**, **HOOD**, or **SNOW**."
            )

        attacks_avail = dl.get_available_attacks(ticker, direction)
        attack_labels = [dl.ATTACK_LABEL.get(a, a) for a in attacks_avail]
        attack_idx = st.radio(
            "Attack vector",
            options=list(range(len(attacks_avail))),
            format_func=lambda i: attack_labels[i],
            index=0,
        )
        attack = attacks_avail[attack_idx]

        defenses_avail = dl.get_available_defenses(ticker, direction, attack)
        if not defenses_avail:
            defenses_avail = ["none"]
        defense_labels = [dl.DEFENSE_LABEL.get(d, d) for d in defenses_avail]
        defense_idx = st.radio(
            "Defense",
            options=list(range(len(defenses_avail))),
            format_func=lambda i: defense_labels[i],
            index=0,
        )
        defense = defenses_avail[defense_idx]

        st.markdown("---")
        st.caption(
            "All combinations are pre-computed (1,200+ trials, "
            "gpt-4o-mini, fixed seeds 0-9)."
        )

    return {
        "direction": direction,
        "ticker": ticker,
        "attack": attack,
        "defense": defense,
    }


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------
def main() -> None:
    render_top_banner()
    _build_api_key_input()
    selection = _build_sidebar()

    trials = dl.find_trials(
        selection["ticker"],
        selection["direction"],
        selection["attack"],
        selection["defense"],
        architecture="full",
    )
    clean_trials = dl.get_clean_baseline(selection["ticker"], selection["direction"])

    if not trials:
        st.warning(
            f"No trials found for "
            f"{selection['ticker']} / {selection['direction']} / "
            f"{dl.ATTACK_LABEL[selection['attack']]} / "
            f"{dl.DEFENSE_LABEL[selection['defense']]}. "
            "Pick a different combination."
        )
        return

    tab_overview, tab_reports, tab_attack, tab_skeptic = st.tabs(
        [
            "📊 Decision overview",
            "📰 Agent reports",
            "🚨 Attack lab — live",
            "🛡️ Skeptic — live",
        ]
    )

    with tab_overview:
        render_overview_metrics(selection, trials, clean_trials)
        render_decision_panel(trials, clean_trials)

    with tab_reports:
        render_report_cards(trials, clean_trials, selection)

    with tab_attack:
        render_attack_lab_tab()

    with tab_skeptic:
        render_skeptic_tab()


if __name__ == "__main__":
    main()
