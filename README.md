# Attacking and Defending Multi-Agent LLM Trading Systems

[![tests](https://github.com/Sunnme02/Attacking-and-Defending-TradingAgents/actions/workflows/tests.yml/badge.svg)](https://github.com/Sunnme02/Attacking-and-Defending-TradingAgents/actions/workflows/tests.yml)
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://attacking-and-defending-trading-agents.streamlit.app)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

We measure whether a multi-agent LLM trading framework
([TradingAgents](https://github.com/TauricResearch/TradingAgents)) stays
robust when an attacker compromises a single supply-chain channel —
news, social media, or persistent memory. **1,210 measured trials**,
three attacks × three defenses, five tickers, both bullish and bearish
directions.

**Headline finding.** Robustness is *two-tier*: an architectural
memory-access boundary attenuates attacks at the perception level,
and multi-agent deliberation absorbs the rest at the decision level.
Both tiers fail under specific conditions — bearish memory poisoning
breaks the perception tier (Δ = −0.42, p<sub>BH</sub> < 0.0001) and
no single defense is enough on its own. **Defense composition is the
unit of analysis.**

📄 [Read the paper](paper/5293report.pdf) · 🌐 [Try the live demo](https://attacking-and-defending-trading-agents.streamlit.app)

---

## 🎬 Demo

[![60-second walkthrough — click to play](https://img.youtube.com/vi/XRgy7UxwaLw/maxresdefault.jpg)](https://youtu.be/XRgy7UxwaLw)

> ▶ Click the thumbnail above for a **60-second walkthrough**: generate a
> fake-news article, send it to the Defense lab, and watch both the
> Skeptic Agent and the Anomaly Filter respond. Try it yourself at the
> [live URL](https://attacking-and-defending-trading-agents.streamlit.app).

---

## System overview

Three independent supply-chain entry points are attacked; three
orthogonal defenses sit at three different architectural layers.

<p align="center">
  <img src="paper/figures/overview.png" alt="Three attacks at three supply-chain chokepoints; three defenses at three architectural layers." width="86%"/>
</p>

---

## Quickstart

```bash
git clone https://github.com/Sunnme02/Attacking-and-Defending-TradingAgents.git
cd Attacking-and-Defending-TradingAgents
pip install -e .
pip install -r adversarial/demo/requirements.txt

# Verify the install — 7 end-to-end checks, ~3 seconds, no API key
python -m adversarial.reproduce_minimal
```

Expected last line: `✅ All 7 minimal-repro checks passed (no API key needed).`

To run the demo locally:

```bash
cp .env.example .env       # then fill in OPENAI_API_KEY (optional — the demo also runs cached-only)
./adversarial/demo/run_demo.sh
```

The deployed demo at the URL above is the easiest way to play with the
system. It has two tabs:

- **🚨 Attack lab** — generate fresh fake news, cross-channel disinfo, or
  memory-poisoning entries with the same code path the experiments use.
- **🛡️ Defense lab** — run the Skeptic Agent (LLM, ~3-5 s) and the Anomaly
  Filter (lexical + cached FinBERT, instant) on the same input
  side-by-side.

Bring your own OpenAI key (pasted into the sidebar — never logged or
persisted across sessions) to unlock free-form input and live LLM
generation.

---

## Documentation

- **[`adversarial/EXPERIMENTS.md`](adversarial/EXPERIMENTS.md)** — full reproduction guide for all 1,210 trials
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — attack and defense mechanism details
- [`docs/DATA.md`](docs/DATA.md) — file-by-file layout, sizes, and expected outputs
- [`docs/CI_TESTING.md`](docs/CI_TESTING.md) — what CI runs and which modules are tested
- [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) — common errors and fixes

---

## Citation

```bibtex
@misc{tradingagents-adversarial-robustness,
  title  = {Attacking and Defending Multi-Agent LLM Trading Systems},
  author = {Gu, Zeyu},
  year   = {2026},
  note   = {Columbia STAT GR5293 final project},
  url    = {https://github.com/Sunnme02/Attacking-and-Defending-TradingAgents}
}

@article{xiao2024tradingagents,
  title   = {{TradingAgents}: Multi-Agents {LLM} Financial Trading Framework},
  author  = {Xiao, Yijia and Sun, Edward and Luo, Di and Wang, Wei},
  journal = {arXiv preprint arXiv:2412.20138},
  year    = {2024},
  url     = {https://arxiv.org/abs/2412.20138}
}
```

---

## License & acknowledgements

Apache 2.0, matching upstream
[TradingAgents](https://github.com/TauricResearch/TradingAgents).
The original upstream README is preserved as
[`README.upstream.md`](README.upstream.md).

This work was completed for Columbia STAT GR5293 (Generative AI),
Spring 2026. We thank the upstream authors for an architecture that
made non-invasive runtime overlays possible.
