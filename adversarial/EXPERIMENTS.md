# Reproducing the experiments

This document lists every experiment in the paper, the exact command
that produced it, and where its output lives. The full numerical
results — including locked Findings F1–F5 with cluster-bootstrap CIs
and BH-corrected p-values — are reported in the paper itself
([`paper/5293report.pdf`](../paper/5293report.pdf), §6).

> **Cost note.** Re-running the entire 1,210-trial campaign costs
> roughly USD $20–30 in OpenAI API charges (gpt-4o-mini × 1,210 ×
> ~5–6 LLM calls / trial). Every payload and per-trial JSON is
> already cached in `data/` and `results/` respectively, so by
> default re-running an experiment hits the cache and incurs no
> API cost.

---

## 1. Environment

| | Value |
|---|---|
| Agent LLM | `gpt-4o-mini` |
| Generator T (A1) | 0.7 |
| Generator T (A2) | 0.85 |
| Judge / Skeptic T | 0.0 |
| Bootstrap iterations | B = 10,000 |
| FDR correction | Benjamini-Hochberg |
| Random seeds | `seed_idx` 0–9 (per-condition) |
| Python | ≥ 3.10 |

All prompt-level parameters are constants in their respective module
files; see e.g. `attacks/news_rewriter.py:REWRITE_PROMPT`,
`attacks/coordinated_disinfo.py:COORD_PROMPT`,
`defenses/skeptic_agent.py:SKEPTIC_PROMPT`. Changing them invalidates
the on-disk cache for the affected payloads.

---

## 2. Tickers and trade dates

The five (ticker, date) pairs studied in the paper. Each pair was
chosen so that real news exists for that date (so the clean baseline
is meaningful) and so the ticker has a yfinance feed (used for the
real-news baseline corpus in the stealth metric).

| Ticker | Trade date | Sector hook |
|---|---|---|
| PLTR | 2025-12-09 | data analytics + federal contracts (primary case study) |
| SNOW | 2025-12-16 | data warehousing |
| HOOD | 2026-01-13 | retail brokerage |
| NVDA | 2026-01-20 | AI infrastructure |
| BIIB | 2025-12-02 | biotech (out-of-domain control) |

---

## 3. Reproducing each batch

Each command below is **idempotent**: re-running it reads existing
cached payloads and per-trial outputs from disk and produces the
same CSV/JSON it did originally. Add `--force-regenerate` flags
(see `--help`) only if you have changed an attack prompt and want a
fresh generation.

### 3.1 Bullish v1 baseline (5 tickers × 4 conditions × 10 seeds = 200 trials)

```bash
for TICKER_DATE in "PLTR 2025-12-09" "SNOW 2025-12-16" \
                   "HOOD 2026-01-13" "NVDA 2026-01-20" \
                   "BIIB 2025-12-02"; do
    read -r T D <<< "$TICKER_DATE"
    python -m adversarial.run_campaign \
        --ticker "$T" --date "$D" \
        --conditions clean,a1,a2,a5 \
        --n-seeds 10
done
```

**Output:** `results/campaign/{TICKER}_{DATE}/`

### 3.2 Bullish v2 + Mixed (5 × 4 × 10 = 200 trials)

```bash
# As 3.1 but with --conditions clean,a2v2,a5v2,a2v2_a5v2 and
# --out-suffix _v2.
```

**Output:** `results/campaign/{TICKER}_{DATE}_v2/`

### 3.3 Bearish (5 × 4 × 10 = 200 trials)

```bash
# As 3.1 but with --conditions clean,a1,a2v2,a5v2,
# --a1-direction bearish --a2-direction bearish --a5-direction bearish,
# --out-suffix _bearish, and --a1-case craig_twitter_2015 (the only
# bearish-direction seed in our SEC corpus).
```

**Output:** `results/campaign/{TICKER}_{DATE}_bearish/`

### 3.4 K-variant ablation (PLTR only)

Tests payload-side stochasticity: K = 3 independent A2v2 payloads
× N = 15 seeds each, holding the (case, ticker, date) fixed.

```bash
python -m adversarial.run_campaign \
    --ticker PLTR --date 2025-12-09 \
    --conditions clean,a2v2 \
    --n-seeds 15 \
    --n-payload-variants 3 \
    --out-suffix _kvariant
```

**Output:** `results/campaign/PLTR_2025-12-09_kvariant/` (45 trials)

### 3.5 Architectural ablation (PLTR + SNOW)

Tests how four upstream architectural choices contribute to robustness:
the full pipeline, no Bull/Bear debate, no Risk Team, and a variant
that exposes long-term memory to the analysts as well as the PM.
Three conditions × N = 5 seeds × 4 variants × 2 tickers = 120 trials.

```bash
for VARIANT in none no_bb no_risk mem_to_analyst; do
    python -m adversarial.run_campaign \
        --ticker PLTR --date 2025-12-09 \
        --conditions clean,a5v2,a2v2_a5v2 \
        --n-seeds 5 \
        --architecture-variant $VARIANT \
        --out-suffix _arch_$VARIANT
done
# Repeat for SNOW 2025-12-16.
```

**Output:** `results/campaign/{PLTR,SNOW}_{DATE}_arch_{VARIANT}/`

### 3.6 Defense × attack matrix

Three sub-batches give the headline defense-effectiveness numbers.

**3.6.a Bullish v2 attacks × {none, D3, D5}** — 3 tickers × 3 defenses × 4 attacks × N=5 = 180 trials

```bash
for TICKER_DATE in "PLTR 2025-12-09" "HOOD 2026-01-13" "SNOW 2025-12-16"; do
    read -r T D <<< "$TICKER_DATE"
    python -m adversarial.run_defense_matrix \
        --ticker "$T" --date "$D" \
        --defenses none,d3,d5 \
        --attacks clean,a1,a2v2,a2v2_a5v2 \
        --n-seeds 5 \
        --out-suffix _v2attacks_bullish
done
```

**Output:** `results/defense_matrix/{TICKER}_{DATE}_v2attacks_bullish/`

**3.6.b D3 strength variants** — citation-only / full / independent-source

```bash
for TICKER_DATE in "PLTR 2025-12-09" "HOOD 2026-01-13" "SNOW 2025-12-16"; do
    read -r T D <<< "$TICKER_DATE"
    python -m adversarial.run_defense_matrix \
        --ticker "$T" --date "$D" \
        --defenses d3a,d3b \
        --attacks clean,a1,a2v2,a2v2_a5v2 \
        --n-seeds 5 \
        --out-suffix _d3_variants
done
```

**Output:** `results/defense_matrix/{TICKER}_{DATE}_d3_variants/`

**3.6.c D4 anomaly filter (PLTR only — single-ticker ablation)**

```bash
# Lexical backend
python -m adversarial.run_defense_matrix \
    --ticker PLTR --date 2025-12-09 \
    --defenses none,d4 \
    --attacks clean,a1,a2v2,a2v2_a5v2 \
    --n-seeds 5 \
    --d4-backend lexical \
    --out-suffix _d4_eval

# FinBERT backend (requires torch + transformers)
python -m adversarial.run_defense_matrix \
    --ticker PLTR --date 2025-12-09 \
    --defenses none,d4 \
    --attacks clean,a1,a2v2,a2v2_a5v2 \
    --n-seeds 5 \
    --d4-backend finbert \
    --out-suffix _d4_finbert
```

**Output:** `results/defense_matrix/PLTR_2025-12-09_d4_{eval,finbert}/`

**3.6.d Bearish defense (PLTR only)**

```bash
for DEFENSE in d3 d5; do
    python -m adversarial.run_defense_matrix \
        --ticker PLTR --date 2025-12-09 \
        --defenses none,$DEFENSE \
        --attacks clean,a1,a2v2,a5v2 \
        --a1-direction bearish --a2-direction bearish --a5-direction bearish \
        --n-seeds 5 \
        --out-suffix _bearish_$DEFENSE
done
```

**Output:** `results/defense_matrix/PLTR_2025-12-09_bearish_{d3,d5}/`

---

## 4. Aggregating + analyzing

After all batches finish, build the paper-facing CSVs and figures:

```bash
# Build paper_attack_effects.csv, paper_defense_effects.csv, etc.
python -m adversarial.aggregate_paper

# Per-finding statistical tables
python -m adversarial.stats_hierarchical

# Generate paper figures
python -m adversarial.make_figures

# Quick attack-effects table for a single batch (sanity-check)
python -m adversarial.analyze --batch results/campaign/PLTR_2025-12-09_v2

# Defense matrix analysis (ordinal × absorption × recovery)
python -m adversarial.analyze_matrix --batch results/defense_matrix/PLTR_2025-12-09_v2attacks_bullish
```

---

## 5. Output schema

Every campaign / defense-matrix batch directory contains:

| File | Content |
|---|---|
| `results.csv` | One-row-per-trial summary (condition, seed_idx, decision, ordinal) |
| `results_full.json` | Full per-trial state including all analyst reports, investment plan, and final decision text |
| `results_full_with_absorption.json` | (when absorption judge has run) `results_full.json` + `absorption_label` per trial |
| `summary.json` | Aggregate stats per condition (mean ordinal, distribution) |
| `analysis_table.txt` | Human-readable table |
| `stats_report.{txt,json}` | Statistical tests (MW-U, bootstrap CI) |
| `memory/` | Per-trial isolated memory log (used by A5 attacks) |

The aggregated, paper-facing CSVs at the top of `results/` are:

| File | Content |
|---|---|
| `paper_attack_effects.csv` | Per-ticker + cross-ticker Δ for each (direction, attack) cell |
| `paper_defense_effects.csv` | Per-ticker + cross-ticker Δ for each (defense, attack) cell |
| `paper_arch_ablation.csv` | Architecture ablation results (none / no_bb / no_risk / mem_to_analyst) |
| `paper_stealth_summary.csv` | Stealth-metric summary for cached A1/A2 payloads |
| `architecture_ablation.csv` | Lower-level architecture ablation table |
| `secondary_metrics.csv` | Secondary metrics (decision dispersion, agreement, etc.) |
| `stats_hierarchical.csv` | Per-finding cluster-bootstrap CIs + BH-corrected p-values |

---

## 6. Statistical methodology

- **Primary metric.** 5-tier ordinal decision (StrongSell = 1, …,
  StrongBuy = 5). The "delta vs clean baseline" is the difference of
  per-condition mean ordinals.
- **Cross-ticker effects.** Cluster-bootstrap CIs with B = 10,000
  iterations, clusters = (ticker, date). The cluster level matters:
  per-ticker variance dominates per-trial variance, so a naive
  bootstrap over trials would over-state precision.
- **Multiple-comparisons control.** Benjamini-Hochberg FDR at α = 0.05
  applied across all locked Findings.
- **Per-trial test.** Mann-Whitney U used on per-trial ordinals to
  complement the cross-ticker bootstrap.

The CI in
[`paper/5293report.pdf`](../paper/5293report.pdf) Figures 3 / 4 is
the cluster-bootstrap one. The right-hand panel of Figure 4 is
single-ticker (PLTR-only) and labelled as exploratory.

---

## 7. Common-issue cheat sheet

| Issue | Fix |
|---|---|
| `vendor lookup failed` for ticker | Stick to PLTR / SNOW / HOOD / NVDA / BIIB; other tickers may not have yfinance feeds for the studied dates |
| Cache miss on a payload that should be cached | Verify the cache key components match (case_id, ticker, date, direction, model, variant). Cache files are SHA1-keyed under `data/fake_news/` and `data/coord_disinfo/`. |
| `KeyError` from absorption judge | The judge needs `OPENAI_API_KEY`. Set it before calling `judges/injection_landed.py`. |
| FinBERT backend slow on first run | First call downloads `ProsusAI/finbert` weights to `~/.cache/huggingface/`. Subsequent runs are fast. |
| Random batches diverging from paper numbers | A campaign run might have a different software version or subtly different prompt. The paper numbers correspond to the batches that were merged at v0.2.4 (commit `7c37249`). |
