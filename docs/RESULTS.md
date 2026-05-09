# Headline results

Quick visibility into the numbers behind the paper. All effects are
cross-ticker cluster-bootstrap means with 95 % CIs (B = 10,000), BH
FDR-corrected. The full per-ticker breakdown lives in
[`adversarial/results/paper_*.csv`](../adversarial/results/) — these
tables are pulled from those CSVs.

## Attack effects (cross-ticker Δ vs clean baseline)

Negative Δ = attack pushes decision more bearish. **Bold** = CI
excludes 0 (significant at α = 0.05 after BH).

| Direction | Attack | n_tickers | Δ ordinal | 95 % CI | Significant? |
|---|---|---:|---:|---|:---:|
| bullish (v1) | Fake News | 5 | +0.11 | [−0.29, +0.45] | n.s. |
| bullish (v1) | Cross-Channel (Atlas-style social pump) | 5 | −0.25 | [−0.54, +0.03] | n.s. |
| bullish (v1) | Memory Poisoning (v1) | 5 | +0.06 | [−0.07, +0.20] | n.s. |
| bullish (v2) | Cross-Channel | 5 | +0.04 | [−0.12, +0.18] | n.s. |
| bullish (v2) | Memory Poisoning (v2) | 5 | −0.12 | [−0.28, +0.06] | n.s. |
| bullish (v2) | Mixed (Cross-Channel + Memory) | 5 | +0.10 | [−0.06, +0.26] | n.s. |
| bearish | Fake News | 5 | −0.02 | [−0.22, +0.12] | n.s. |
| bearish | Cross-Channel | 5 | −0.02 | [−0.18, +0.12] | n.s. |
| **bearish** | **Memory Poisoning (v2)** | **5** | **−0.42** | **[−0.68, −0.16]** | ✅ **yes** |

**Reading:** Of the 9 attack × direction cells measured, only one
(bearish memory poisoning) significantly shifts the decision. Bullish
attacks are absorbed by the architecture; bearish attacks mostly are
too — *except* memory poisoning, where the architectural attenuation
breaks down.

## Defense effects (cross-ticker Δ recovered toward baseline)

Positive Δ = defense moves the attacked decision back toward clean.
Computed within the v2 attack matrix on bullish PLTR / HOOD / SNOW
(3 tickers × 4 attacks × {none, defense} × N = 5).

| Defense | Attack | Δ recovered | 95 % CI |
|---|---|---:|---|
| Provenance-Aware PM (`d3`) | Fake News | +0.47 | [+0.20, +1.00] |
| Skeptic Agent (`d5`) | Fake News | +0.67 | [+0.20, +1.40] |
| Provenance-Aware PM (`d3`) | Cross-Channel | +0.47 | [+0.20, +0.60] |
| Skeptic Agent (`d5`) | Cross-Channel | +0.47 | [+0.40, +0.60] |
| Provenance-Aware PM (`d3`) | Mixed | +0.07 | [−0.20, +0.20] |
| Skeptic Agent (`d5`) | Mixed | −0.07 | [−0.40, +0.40] |

### Provenance variants (citation-only / full / independent-source)

Three strength variants of the Provenance-Aware PM:

| Variant | Attack | Δ recovered | 95 % CI |
|---|---|---:|---|
| `d3a` (citation-only) | Fake News | +0.73 | [+0.20, +1.20] |
| `d3a` (citation-only) | Cross-Channel | +0.67 | [+0.60, +0.80] |
| `d3a` (citation-only) | Mixed | −0.07 | [−0.60, +0.20] |
| `d3b` (independent-source + circular) | Fake News | +0.20 | [0.0, +0.40] |
| `d3b` (independent-source + circular) | Cross-Channel | +0.20 | [0.0, +0.40] |
| `d3b` (independent-source + circular) | Mixed | +0.27 | [−0.20, +1.00] |

**Reading:** Single-channel attacks (Fake News, Cross-Channel) are
recoverable by either Provenance PM or Skeptic. Mixed attacks
(Cross-Channel + Memory simultaneously) fall outside any single
defense's reach — confirming the paper's headline claim that
**defense composition is the unit of analysis**.

## Architecture ablation (PLTR + SNOW pooled)

Effect of disabling individual upstream architectural pieces (Bull/Bear
debate, Risk Team, etc.) under v2 attacks.

| Architecture variant | Attack | Δ vs clean (averaged across PLTR/SNOW seeds) |
|---|---|---:|
| Full pipeline | Cross-Channel | 0.0 |
| Full pipeline | Mixed (Cross-Channel + Memory) | 0.0 |
| No Bull/Bear debate | Cross-Channel | +1.4 |
| No Bull/Bear debate | Mixed | +1.4 |
| No Risk Team | Cross-Channel | +1.0 |
| No Risk Team | Mixed | −0.4 |
| Memory exposed to analysts | Cross-Channel | +0.4 |
| Memory exposed to analysts | Mixed | +0.6 |

**Reading:** Removing the Bull/Bear debate degrades robustness the
most (Δ jumps to +1.4 — i.e. the agent flips strongly toward the
attack's intended direction). Confirms that multi-agent deliberation
is the load-bearing structural component.

## Paper figures referenced

The figures below are inside the paper PDF and are also available as
PNG in `paper/figures/`:

- **Figure 1** — System overview: 3 attacks × 3 defenses × 3 layers
  ([`overview.png`](../paper/figures/overview.png))
- **Figure 3** — Architecture ablation forest plot
  ([`fig3_arch_ablation.png`](../paper/figures/fig3_arch_ablation.png))
- **Figure 4** — Per-defense forest plot
  ([`fig4_defense_forest.png`](../paper/figures/fig4_defense_forest.png))
- **Figure 5** — Stealth-score scatter
  ([`fig5_stealth_scatter.png`](../paper/figures/fig5_stealth_scatter.png))
- **Figure 6** — Per-ticker forest plot
  ([`fig6_perticker_forest.png`](../paper/figures/fig6_perticker_forest.png))

All figures regenerable from CSV via `python -m adversarial.make_figures`.

## How to regenerate these tables

```bash
python -m adversarial.aggregate_paper        # produces paper_*.csv
python -m adversarial.stats_hierarchical     # produces stats_hierarchical.csv with CIs
```

Or re-run the full minimal-repro check (no LLM cost):

```bash
python -m adversarial.reproduce_minimal
```
