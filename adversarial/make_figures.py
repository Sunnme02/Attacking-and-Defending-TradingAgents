"""
Generate paper-ready figures (PDF + PNG) from aggregated CSV files.

Outputs to ``paper/figures/``:

  fig3_arch_ablation.pdf       Architecture ablation bar chart
                               (Finding 1: memory access boundary as
                               immunity mechanism)
  fig4_defense_forest.pdf      Defense effect forest plot
                               (Finding 3: D3/D5 cells with 95% CI)
  fig5_stealth_scatter.pdf     Lexical × FinBERT stealth scatter
                               (Finding 5: detector-class dependence)
  fig6_perticker_forest.pdf    Per-ticker attack effects forest plot
                               (Finding 4: sector-narrative coupling)

Conventions (paper-ready):
  - Vector PDFs primary, PNGs at 300dpi for fallback
  - Times font, sans-serif fallback
  - 4-color palette: black/red/green/blue (matches Fig 1 conventions)
  - Tight bbox; no extra whitespace
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")  # No display needed
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "adversarial" / "results"
STEALTH_REPORT = ROOT / "adversarial" / "data" / "stealth_report.json"
FIG_DIR = ROOT / "paper" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Style: paper-grade defaults
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
    "font.size": 10,
    "axes.labelsize": 11,
    "axes.titlesize": 11,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.7,
    "savefig.bbox": "tight",
    "savefig.dpi": 300,
    "pdf.fonttype": 42,  # TrueType embedding
})

ATTACK_DISPLAY = {
    "a1":         "Fake News (A1)",
    "a2":         "Single-Channel Pump (A2 v1)",
    "a2v2":       "Cross-Channel Coord. (A2v2)",
    "a5":         "Generic Memory (A5 v1)",
    "a5v2":       "Pattern-Matched Memory (A5v2)",
    "a2v2_a5v2":  "Mixed Attack",
}

DEFENSE_DISPLAY = {
    "none": "None",
    "d3":   "D3 Provenance (full)",
    "d3a":  "D3a Citation-only",
    "d3b":  "D3b Indep.-Source",
    "d4":   "D4 Anomaly Filter",
    "d5":   "D5 Skeptic",
}

# Color palette matching Fig 1 (consistent across all figures)
ATTACK_COLOR = {
    "a1":         "#d62728",   # red
    "a2":         "#ff9896",   # light red
    "a2v2":       "#9467bd",   # purple
    "a5":         "#aec7e8",   # light blue
    "a5v2":       "#1f77b4",   # blue
    "a2v2_a5v2":  "#7f0e44",   # dark crimson (mixed)
}


# =====================================================================
# Figure 3 — Architecture ablation bar chart
# =====================================================================

def make_fig3_arch_ablation():
    """Cross-ticker bar chart showing Δ for each architectural variant
    on PLTR and SNOW (validates Finding 1 cross-ticker)."""
    rows = list(csv.DictReader((CSV_DIR / "paper_arch_ablation.csv").open()))

    variants = ["none", "no_bb", "no_risk", "mem_to_analyst"]
    variant_label = {
        "none":            "None\n(default)",
        "no_bb":           "No Bull/Bear",
        "no_risk":         "No Risk Debate",
        "mem_to_analyst":  "Mem→Analyst",
    }
    tickers = ["PLTR", "SNOW"]
    cond = "a5v2"  # Focus on A5v2 (the headline architectural finding)

    # Collect Δ per (variant, ticker)
    data = {}
    for r in rows:
        if r["ticker"] in tickers and r["condition"] == cond \
                and r["delta_vs_clean"] not in ("", None):
            data[(r["variant"], r["ticker"])] = float(r["delta_vs_clean"])

    ticker_color = {
        "PLTR": "#1f77b4",   # blue
        "SNOW": "#2ca02c",   # green
    }

    fig, ax = plt.subplots(figsize=(7.0, 3.8))
    width = 0.36
    x = np.arange(len(variants))

    for i, t in enumerate(tickers):
        vals = [data.get((v, t), 0.0) for v in variants]
        offset = (i - 0.5) * width
        bars = ax.bar(x + offset, vals, width=width,
                      label=f"{t} (N=5)",
                      color=ticker_color[t],
                      edgecolor="black", linewidth=0.5)
        for bar, v in zip(bars, vals):
            y = bar.get_height()
            ax.annotate(f"{v:+.2f}",
                        xy=(bar.get_x() + bar.get_width()/2, y),
                        xytext=(0, 4 if y >= 0 else -12),
                        textcoords="offset points",
                        ha="center", fontsize=8.5)

    ax.axhline(0, color="black", linewidth=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels([variant_label[v] for v in variants])
    ax.set_ylabel(r"A5v2 attack effect $\Delta$ (vs.\ clean)")
    ax.set_title("Architectural ablation cross-ticker: memory access boundary as immunity mechanism")
    ax.set_ylim(-0.5, 1.7)
    ax.legend(loc="upper left", frameon=False)
    ax.grid(axis="y", linestyle=":", alpha=0.5, linewidth=0.5)

    # Annotation pointing to the immunity finding
    ax.annotate("Architectural\nimmunity intact\n(both tickers)",
                xy=(0, -0.10), xytext=(0.5, 0.6),
                ha="center", fontsize=8.5,
                arrowprops=dict(arrowstyle="->", lw=0.6, color="gray"))
    ax.annotate("mem→Analyst replicates\ncross-ticker (both >0)",
                xy=(3.18, 0.40), xytext=(2.5, 1.4),
                ha="center", fontsize=8.5,
                arrowprops=dict(arrowstyle="->", lw=0.6, color="gray"))

    fig.savefig(FIG_DIR / "fig3_arch_ablation.pdf")
    fig.savefig(FIG_DIR / "fig3_arch_ablation.png", dpi=300)
    plt.close(fig)
    print(f"  Wrote fig3_arch_ablation.pdf + .png")


# =====================================================================
# Figure 4 — Defense effect forest plot
# =====================================================================

def make_fig4_defense_forest():
    """Forest plot of cross-ticker defense effects with 95% CI.
    Two-panel: left = bullish single-channel + mixed (4 defenses);
    right = bearish PLTR (highlighting D5 backfire on A5v2)."""
    rows = list(csv.DictReader((CSV_DIR / "paper_defense_effects.csv").open()))

    # ─── LEFT panel: bullish (cross-ticker, 3 tickers) ───
    # Combine v2attacks_bullish (d3 full + d5) + d3_variants (d3a + d3b)
    bullish_rows = [r for r in rows
                    if r["level"] == "cross"
                    and r["matrix"] in ("_v2attacks_bullish", "_d3_variants")]

    # Order: D3a, D3 (full), D3b, D5; within each: A1, A2v2, Mixed
    defense_order_bull = [
        ("d3a",  "_d3_variants",       "D3a Citation-only"),
        ("d3",   "_v2attacks_bullish", "D3 Provenance (full)"),
        ("d3b",  "_d3_variants",       "D3b Indep.-Source"),
        ("d5",   "_v2attacks_bullish", "D5 Skeptic"),
    ]
    attack_order = ["a1", "a2v2", "a2v2_a5v2"]
    bull_points = []
    for de, src_matrix, de_label in defense_order_bull:
        for at in attack_order:
            for r in bullish_rows:
                if (r["defense"] == de and r["attack"] == at
                        and r["matrix"] == src_matrix):
                    bull_points.append((de_label, at,
                                        float(r["delta"]),
                                        float(r["ci_lo"]),
                                        float(r["ci_hi"])))
                    break

    # ─── RIGHT panel: bearish PLTR ───
    bearish_rows = [r for r in rows
                    if r["matrix"] == "_bearish_merged"
                    and r["level"] == "cross"]
    defense_order_bear = ["d3", "d5"]
    bearish_attacks = ["a1", "a2v2", "a5v2"]
    bear_points = []
    bearish_attack_labels = {
        "a1":   "Fake News (craig, bearish)",
        "a2v2": "Cross-Channel (bearish)",
        "a5v2": "Pattern-Matched Memory (bearish) **",
    }
    for de in defense_order_bear:
        for at in bearish_attacks:
            for r in bearish_rows:
                if r["defense"] == de and r["attack"] == at:
                    bear_points.append((DEFENSE_DISPLAY[de], at,
                                        float(r["delta"]),
                                        float(r["ci_lo"]),
                                        float(r["ci_hi"])))
                    break

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.0, 4.5),
                                    gridspec_kw={"width_ratios": [1.6, 1.0]})

    # ─── Plot LEFT (bullish cross-ticker) ───
    n_bull = len(bull_points)
    y_bull = list(range(n_bull, 0, -1))
    for (de, at, d, lo, hi), y in zip(bull_points, y_bull):
        is_significant = lo > 0 or hi < 0
        color = "#2ca02c" if is_significant else "#888888"
        ax1.errorbar(d, y, xerr=[[d - lo], [hi - d]],
                     fmt="o", color=color, ecolor=color,
                     elinewidth=1.4, capsize=4, markersize=7,
                     markeredgecolor="black", markeredgewidth=0.5)
        sig_marker = "***" if is_significant else "n.s."
        ax1.text(hi + 0.05, y, sig_marker, va="center", fontsize=8)

    ax1.axvline(0, color="black", linewidth=0.6, linestyle="--")
    ax1.set_yticks(y_bull)
    ax1.set_yticklabels(
        [f"{de} | {ATTACK_DISPLAY[at]}" for de, at, *_ in bull_points],
        fontsize=8.5)
    ax1.set_xlabel(r"Defense effect $\Delta_{\rm none-def}$ (positive: defense reduces attack-aligned ordinal)")
    ax1.set_title("Bullish (cross-ticker, 3 tickers $\\times$ N=5)", fontsize=10)
    ax1.set_xlim(-0.8, 1.6)
    ax1.grid(axis="x", linestyle=":", alpha=0.5, linewidth=0.5)

    # ─── Plot RIGHT (bearish PLTR) ───
    n_bear = len(bear_points)
    y_bear = list(range(n_bear, 0, -1))
    for (de, at, d, lo, hi), y in zip(bear_points, y_bear):
        # Highlight D5-vs-A5v2 backfire
        if at == "a5v2" and "Skeptic" in de:
            color = "#d62728"  # red — backfire
            label_suffix = " ← BACKFIRE"
        elif d > 0:
            color = "#2ca02c"
            label_suffix = ""
        else:
            color = "#888888"
            label_suffix = ""
        ax2.errorbar(d, y, xerr=[[d - lo], [hi - d]],
                     fmt="s" if "BACKFIRE" in label_suffix else "o",
                     color=color, ecolor=color,
                     elinewidth=1.4, capsize=4, markersize=8,
                     markeredgecolor="black", markeredgewidth=0.5)
        ax2.text(d + 0.04 if d >= 0 else d - 0.04, y,
                 f"{d:+.2f}{label_suffix}",
                 va="center", ha="left" if d >= 0 else "right",
                 fontsize=7.5,
                 color="#d62728" if "BACKFIRE" in label_suffix else "black",
                 fontweight="bold" if "BACKFIRE" in label_suffix else "normal")

    ax2.axvline(0, color="black", linewidth=0.6, linestyle="--")
    ax2.set_yticks(y_bear)
    ax2.set_yticklabels(
        [f"{de} | {bearish_attack_labels[at]}"
         for de, at, *_ in bear_points],
        fontsize=8.5)
    ax2.set_xlabel(r"Defense effect $\Delta$")
    ax2.set_title("Bearish defense matrix (PLTR, N=5)", fontsize=10)
    ax2.set_xlim(-0.7, 0.7)
    ax2.grid(axis="x", linestyle=":", alpha=0.5, linewidth=0.5)

    # Single legend for both panels
    sig_handle = Line2D([0], [0], marker="o", color="w",
                        markerfacecolor="#2ca02c", markeredgecolor="black",
                        label=r"$p_{\rm BH}<0.05$ or positive defense effect",
                        markersize=8)
    nsig_handle = Line2D([0], [0], marker="o", color="w",
                         markerfacecolor="#888888", markeredgecolor="black",
                         label="n.s. (CI includes 0)", markersize=8)
    backfire_handle = Line2D([0], [0], marker="s", color="w",
                             markerfacecolor="#d62728", markeredgecolor="black",
                             label="Defense BACKFIRE (D5 amplifies attack)",
                             markersize=8)
    fig.legend(handles=[sig_handle, nsig_handle, backfire_handle],
               loc="lower center", frameon=False, ncol=3, fontsize=9,
               bbox_to_anchor=(0.5, -0.02))

    fig.suptitle("Defense effect with 95\\% cluster-bootstrap CI",
                 fontsize=11, y=0.995)
    fig.tight_layout(rect=[0, 0.02, 1, 0.97])
    fig.savefig(FIG_DIR / "fig4_defense_forest.pdf")
    fig.savefig(FIG_DIR / "fig4_defense_forest.png", dpi=300)
    plt.close(fig)
    print(f"  Wrote fig4_defense_forest.pdf + .png")


# =====================================================================
# Figure 5 — Stealth × Defense scatter
# =====================================================================

def make_fig5_stealth_scatter():
    """Scatter of lexical × FinBERT stealth, colored + shaped by attack.
    Each marker style distinguishes attack and direction (avon=bullish A1,
    craig=bearish A1) so reader doesn't conflate them."""
    report = json.loads(STEALTH_REPORT.read_text())

    fig, ax = plt.subplots(figsize=(6.5, 4.5))

    # Threshold zones
    ax.axvspan(0, 0.10, alpha=0.10, color="green", zorder=0)
    ax.axhspan(0, 0.80, alpha=0.05, color="blue", zorder=0)

    # Per-(attack, direction) styling
    style_table = [
        ("a1",   "avon",  "Fake News A1 (avon, bullish)",  "#d62728", "o", 70),
        ("a1",   "craig", "Fake News A1 (craig, bearish)", "#8b0000", "s", 70),
        ("a2",   None,    "Single-Channel Pump (A2 v1)",   "#ff9896", "^", 80),
        ("a2v2", None,    "Cross-Channel Coord. (A2v2)",   "#9467bd", "D", 70),
    ]

    for atk, case_filter, label, color, marker, size in style_table:
        entries = report.get(atk, [])
        if not entries:
            continue
        if case_filter is not None:
            entries = [e for e in entries
                       if (e.get("case_id") or "").startswith(case_filter)]
        xs, ys = [], []
        for e in entries:
            x = e.get("stealth_score_lexical")
            y = e.get("stealth_score_finbert")
            if x is not None and y is not None:
                xs.append(x); ys.append(y)
        if not xs:
            continue
        ax.scatter(xs, ys, s=size, c=color, marker=marker,
                   edgecolor="black", linewidth=0.6,
                   label=label, alpha=0.85, zorder=3)

    # Threshold lines
    ax.axvline(0.10, color="green", linestyle="--", linewidth=0.8, alpha=0.6)
    ax.axhline(0.80, color="blue", linestyle="--", linewidth=0.8, alpha=0.6)

    # Threshold annotations (placed in margins, no overlap)
    ax.text(0.10, 0.51, " D4-lex\n threshold (0.10)",
            ha="left", va="bottom", fontsize=8, color="green",
            zorder=4)
    ax.text(0.50, 0.80, "D4-FinBERT\nthreshold (0.80) ",
            ha="right", va="top", fontsize=8, color="blue",
            zorder=4)

    # Quadrant labels
    ax.text(0.04, 0.97, "lexical-anomalous\nFinBERT-real-like",
            ha="left", va="top", fontsize=7.5, color="gray",
            style="italic", alpha=0.8)
    ax.text(0.48, 0.97, "lexical-real-like\nFinBERT-real-like",
            ha="right", va="top", fontsize=7.5, color="gray",
            style="italic", alpha=0.8)

    ax.set_xlabel("Lexical stealth score (0 = anomalous, 1 = real-like)")
    ax.set_ylabel("FinBERT stealth score (0 = anomalous, 1 = real-like)")
    ax.set_title("Stealth detector-class dependence: each attack hides in a different blind spot")
    ax.set_xlim(-0.02, 0.55)
    ax.set_ylim(0.50, 1.00)
    ax.legend(loc="upper left", frameon=True, framealpha=0.95,
              edgecolor="gray", fontsize=8.5,
              bbox_to_anchor=(0.0, -0.10), ncol=2)
    ax.grid(linestyle=":", alpha=0.4, linewidth=0.5)
    fig.tight_layout()

    fig.savefig(FIG_DIR / "fig5_stealth_scatter.pdf")
    fig.savefig(FIG_DIR / "fig5_stealth_scatter.png", dpi=300)
    plt.close(fig)
    print(f"  Wrote fig5_stealth_scatter.pdf + .png")


# =====================================================================
# Figure 6 — Per-ticker attack effect forest plot
# =====================================================================

def make_fig6_perticker_forest():
    """Per-ticker forest plot of attack effects (bullish v1 + v2 batches),
    showing sector-narrative coupling visually."""
    rows = list(csv.DictReader((CSV_DIR / "paper_attack_effects.csv").open()))

    # Pick attacks to show in the figure
    # v1 a1 (sector-coupling), v2 a2v2, v2 a2v2_a5v2 (Mixed)
    spec = [
        ("v1_bullish", "a1", ATTACK_DISPLAY["a1"], ATTACK_COLOR["a1"]),
        ("v2_bullish", "a2v2", ATTACK_DISPLAY["a2v2"], ATTACK_COLOR["a2v2"]),
        ("v2_bullish", "a2v2_a5v2", ATTACK_DISPLAY["a2v2_a5v2"], ATTACK_COLOR["a2v2_a5v2"]),
    ]

    # Order tickers by sector grouping
    ticker_order = ["PLTR", "SNOW", "HOOD", "NVDA", "BIIB"]
    ticker_label = {
        "PLTR": "PLTR (data analytics)",
        "SNOW": "SNOW (cloud data)",
        "HOOD": "HOOD (fintech)",
        "NVDA": "NVDA (AI semis)",
        "BIIB": "BIIB (biotech)",
    }

    fig, axes = plt.subplots(1, len(spec), figsize=(10.5, 3.5),
                             sharey=True)

    for ax, (batch, atk, label, color) in zip(axes, spec):
        # Per-ticker rows
        rows_t = [r for r in rows
                  if r["batch"] == batch
                  and r["attack"] == atk
                  and r["level"] == "ticker"]
        cross = next((r for r in rows
                      if r["batch"] == batch
                      and r["attack"] == atk
                      and r["level"] == "cross"), None)

        y_positions = []
        deltas = []
        labels = []
        for i, t in enumerate(ticker_order):
            for r in rows_t:
                if r["ticker"] == t:
                    y_positions.append(len(ticker_order) - i)
                    deltas.append(float(r["delta"]))
                    labels.append(ticker_label[t])
                    break

        ax.scatter(deltas, y_positions, s=70, c=color,
                   edgecolor="black", linewidth=0.5, zorder=3)

        # Cross-ticker mean diamond
        if cross:
            d = float(cross["delta"])
            lo = float(cross["ci_lo"])
            hi = float(cross["ci_hi"])
            cross_y = 0.5
            ax.errorbar(d, cross_y, xerr=[[d - lo], [hi - d]],
                        fmt="D", color=color, ecolor=color,
                        elinewidth=1.5, capsize=4, markersize=8,
                        markeredgecolor="black", markeredgewidth=0.6,
                        zorder=4)
            ax.text(hi + 0.05, cross_y, f"$\\Delta={d:+.2f}$",
                    va="center", fontsize=7.5)

        ax.axvline(0, color="black", linewidth=0.6, linestyle="--")
        ax.set_yticks([0.5] + list(range(1, len(ticker_order) + 1)))
        ax.set_yticklabels(["Cross-ticker"] + labels[::-1], fontsize=8.5)
        ax.set_xlim(-1.0, 1.5)
        ax.set_xlabel(r"$\Delta$ vs.\ clean")
        ax.set_title(label, fontsize=10)
        ax.grid(axis="x", linestyle=":", alpha=0.5, linewidth=0.5)

    fig.suptitle("Per-ticker attack effects (bullish): sector-narrative coupling",
                 fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(FIG_DIR / "fig6_perticker_forest.pdf")
    fig.savefig(FIG_DIR / "fig6_perticker_forest.png", dpi=300)
    plt.close(fig)
    print(f"  Wrote fig6_perticker_forest.pdf + .png")


# =====================================================================
# Main
# =====================================================================

if __name__ == "__main__":
    print(f"Output dir: {FIG_DIR.relative_to(ROOT)}/")
    make_fig3_arch_ablation()
    make_fig4_defense_forest()
    make_fig5_stealth_scatter()
    make_fig6_perticker_forest()
    print()
    print("Done. Figures in:", FIG_DIR.relative_to(ROOT))
