"""TradingAgents Adversarial Robustness — Live Demo.

Streamlit app showing the system *operating*:
  • Live LLM-driven attack generation (Fake News + Cross-Channel)
  • Live Skeptic Agent invocation against generated or user-supplied text

Pre-computed trial data and aggregate statistics live in
`adversarial/results/` (per-trial JSON) and `paper_*.csv` (aggregate
tables); they are documented in the paper and the README — this app is
deliberately scoped to the *interactive* part of the project.

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

from adversarial.demo.ui_components import (  # noqa: E402
    DEPLOYER_API_KEY,
    render_attack_lab_tab,
    render_skeptic_tab,
    render_top_banner,
)


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
        section[data-testid="stSidebar"] { background: #f1f5f9; }

        /* Tabs */
        button[role="tab"] { font-size: 0.95rem; font-weight: 500; }

        /* Top metrics strip */
        .metrics-strip {
            display: flex;
            gap: 1.6rem;
            padding: 0.5rem 0 1rem 0;
            color: #64748b;
            font-size: 0.84rem;
            border-bottom: 1px solid #e2e8f0;
            margin-bottom: 1.2rem;
        }
        .metrics-strip b { color: #1e293b; font-size: 0.92rem; }
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

    SECURITY NOTE — the key is stored ONLY in this user's session_state
    (a per-session dict isolated by Streamlit). It is NEVER written to
    os.environ globally, because Streamlit Cloud runs all sessions in a
    single Python process and a global env-var write would leak the key
    to every other concurrent user.

    The key is read back via ``ui_components.get_session_api_key()`` and
    passed explicitly to each LLM call inside a temporary context
    manager (``attack_runner._scoped_openai_key``).
    """
    with st.sidebar:
        # Use the deployer-time snapshot, NOT os.environ at runtime,
        # so a previous user's accidental write to os.environ can't
        # masquerade as a deployer-configured key.
        deployer_set = bool(DEPLOYER_API_KEY)

        with st.expander("🔑 OpenAI API key", expanded=not deployer_set):
            if deployer_set:
                st.success("✅ Using key from environment.")
            else:
                user_key = st.text_input(
                    "Paste your OpenAI API key",
                    value="",
                    type="password",
                    help=(
                        "The Attack lab and Defense lab tabs make real "
                        "OpenAI calls. With a key, you unlock free-form "
                        "ticker / date input and can generate fresh "
                        "adversarial content. Without a key, the demo runs "
                        "from a pre-computed corpus. The key stays in your "
                        "browser session only — never written to a global "
                        "process variable, never logged, never persisted."
                    ),
                    key="user_openai_key",
                    placeholder="sk-...",
                )
                if user_key.strip():
                    # Store in session_state ONLY (do NOT write os.environ
                    # — that would leak across concurrent user sessions on
                    # Streamlit Cloud's single-process model).
                    st.session_state["user_api_key"] = user_key.strip()
                    st.success("✅ Key set — live mode + free-form input unlocked.")
                else:
                    st.session_state.pop("user_api_key", None)
                    st.info(
                        "🔒 Cached-only mode. "
                        "[Get a key →](https://platform.openai.com/api-keys)"
                    )

        st.markdown("---")
        st.markdown(
            "### About this demo\n"
            "This demo focuses on **showing the system operating**:\n"
            "- 🎯 Generate adversarial content via the same code path as the experiments\n"
            "- 🛡️ Watch the Skeptic Agent respond to it\n\n"
            "The full **1,210-trial dataset, paper figures, and analysis "
            "scripts** are on GitHub:"
        )
        st.markdown(
            "[📂 View results CSV](https://github.com/Sunnme02/Attacking-and-Defending-TradingAgents/tree/main/adversarial/results) · "
            "[📄 Read the paper](https://github.com/Sunnme02/Attacking-and-Defending-TradingAgents/blob/main/paper/5293report.pdf) · "
            "[🧪 Experiments guide](https://github.com/Sunnme02/Attacking-and-Defending-TradingAgents/blob/main/adversarial/EXPERIMENTS.md)"
        )


# ---------------------------------------------------------------------------
# Top metrics strip
# ---------------------------------------------------------------------------
def _render_metrics_strip() -> None:
    st.markdown(
        """
        <div class="metrics-strip">
          <span><b>1,210</b> measured trials</span>
          <span><b>3 × 3</b> attack × defense matrix</span>
          <span><b>5</b> tickers</span>
          <span>bullish + bearish</span>
          <span>cluster-bootstrap CIs · BH-FDR</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main layout — two live tabs only
# ---------------------------------------------------------------------------
def main() -> None:
    render_top_banner()
    _render_metrics_strip()
    _build_api_key_input()

    tab_attack, tab_skeptic = st.tabs(
        [
            "🚨 Attack lab — live generation",
            "🛡️ Defense lab — live invocation",
        ]
    )

    with tab_attack:
        render_attack_lab_tab()

    with tab_skeptic:
        render_skeptic_tab()


if __name__ == "__main__":
    main()
