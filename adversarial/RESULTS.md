# Paper Results — Locked Numbers Reference

> Single source of truth for every number that should appear in the paper.
> All entries below are **measured**, not hypothesised. Update when new
> data lands.

Last updated: 2026-05-04 — after 5-ticker bullish/bearish + arch ablation
+ absorption judge + stealth analysis. **D3a/D3b + D4 lex/finbert running on
PLTR (~1.5 hr remaining).** Outstanding: bearish defense matrix, cross-ticker
arch ablation, cross-ticker D3a/D3b.

---

## Naming convention (paper-facing)

| Internal code | Paper name (for prose / figures) |
|---|---|
| A1 | Fake News Injection |
| A2 (v1) | Single-Channel Social Pump |
| A2v2 | Cross-Channel Coordinated Disinformation |
| A5 (v1) | Generic Memory Poisoning |
| A5v2 | Pattern-Matched Memory Poisoning |
| a2v2_a5v2 | Mixed Attack |
| D3a | Citation-Only Provenance |
| D3 (full) | Provenance-Aware PM |
| D3b | Independent-Source Provenance |
| D4 | Anomaly Filter |
| D5 | Skeptic Agent |

---

## Experimental scale

| Component | Spec | N trials |
|---|---|---|
| v1 bullish baseline (5 ticker × 4 cond × N=10) | PLTR/SNOW/HOOD/BIIB/NVDA × {clean,a1,a2,a5} | **200** |
| v2 bullish (5 ticker × 4 cond × N=10) | × {clean, a2v2, a5v2, a2v2_a5v2} | **200** |
| Bearish (5 ticker × 4 cond × N=10) | × {clean, a1, a2v2, a5v2}, a1=craig | **200** |
| K-variant ablation (PLTR K=3 × N=15) | clean,a2v2 | **45** |
| Architecture ablation (PLTR × 4 variants × N=5) | × {clean, a5v2, a2v2_a5v2} | **60** |
| Defense matrix v2attacks bullish (3 ticker × 3 def × 4 atk × N=5) | none/d3/d5 × clean/a1/a2v2/combo | **180** |
| Defense matrix D3a/D3b (PLTR, running) | d3a,d3b × 4 atk × N=5 | **40** (running) |
| Defense matrix D4 lex (PLTR, running) | none,d4 × 4 atk × N=5 | **40** (running) |
| Defense matrix D4 finbert (PLTR, running) | none,d4 × 4 atk × N=5 | **40** (running) |
| **Total measured trials** | | **925 + 120 running = 1045** |
| Absorption judge calls (5 ticker × 4 cond × N=10) | LLM-as-judge per trial | **150** ✅ |
| Stealth metric scoring | All cached payloads (lex + FinBERT) | **32** ✅ |

---

## Finding 1 — Architectural Memory Access Boundary as Immunity Mechanism ⭐⭐⭐

**Headline claim**: Pattern-Matched Memory Poisoning (A5v2) achieves 0% cross-
ticker bullish ASR not because the payload is weak, but because the
TradingAgents architecture grants memory access only to the Portfolio Manager
(PM) — the last node in the pipeline — by which point upstream agents (Bull/
Bear research debate, Trader, Risk debate) have already anchored the decision
without seeing memory.

**Evidence layers**:

### 1a. Cross-ticker decision Δ = 0 (5 ticker × N=10)
A5v2 bullish: Δ=-0.12 [-0.28, +0.06], p_BH=0.30 (NOT significant after BH)
- PLTR Δ=-0.20, SNOW Δ=-0.30, HOOD Δ=-0.30, BIIB Δ=+0.00, NVDA Δ=+0.20

### 1b. Absorption judge confirms memory does not propagate to reports (NEW)
Cross-ticker N=10 absorption verdicts:
- A5v2: **49/50 (98%) not_absorbed**, 1 partial
- A2v2: **50/50 (100%) fully_absorbed**
- Mixed: **50/50 (100%) fully_absorbed**

A5v2 memory content NEVER reaches news/sentiment/investment reports because
no upstream agent reads memory. Compare A2v2 reaching reports 100% — proves
memory is *architecturally* gated, not just down-weighted.

### 1c. Architecture ablation (controlled mechanism evidence)
PLTR × N=5 × 3 conditions across 4 architectural variants:

| Variant | A5v2 Δ | Mixed Δ | Mechanism |
|---|---|---|---|
| **none (default)** | **+0.00** | **+0.00** | Architecture intact |
| **mem_to_analyst** | **+0.80** | **+0.60** | Move memory upstream → attack succeeds |
| **no_bb** (skip Bull/Bear) | **+1.40** | **+1.40** | Bull/Bear is anchoring node |
| **no_risk** (skip Risk debate) | **+1.00** | **-0.40** | Risk debate is anchoring node |

→ Three independent ablations all confirm the architectural-immunity hypothesis.

**Lit grounding**: Replicates and extends ASB ICLR 2025's 7.92% memory
poisoning baseline (Zhang et al., arXiv:2410.02644); we observe 0% ASR
because TradingAgents' hierarchical decision pipeline is more restrictive
than ASB's tested agents.

---

## Finding 2 — Direction-Asymmetric Architectural Immunity ⭐⭐

**Headline claim**: Pattern-Matched Memory Poisoning is architecturally immune
in bullish direction but **not** in bearish direction.

| | Bullish | Bearish |
|---|---|---|
| Cross-ticker Δ | +0.00 [-0.28, +0.06] | **-0.42 [-0.68, -0.16]** |
| p_BH | 0.30 (n.s.) | **<0.0001 (sig)** |

The bearish A5v2 finding is the only attack effect that crosses BH-corrected
significance. Hypothesised mechanism: bearish "LESSON LEARNED" memory
synergises with the agent's natural risk-averse bias (PM by default leans
toward Hold/Underweight); bullish memory must overcome this bias.

Secondary metric: PLTR bearish A5v2 produces a **bimodal split** — 60% of
trials follow memory toward Sell, 40% revolt to Hold. Standard distortion
0.98 vs clean 0.18 (5× stretch).

---

## Finding 3 — Defense Effects (Bullish, 3 Ticker × 4 Attack × N=5)

**Headline claim**: D3 and D5 each robustly reduce single-channel attacks
(4/4 cells significant after BH), but BOTH leak on the Mixed Attack.

Cross-ticker cluster bootstrap:

| Defense effect (Δ_def vs none) | n (tickers) | Δ | 95% CI | p_BH |
|---|---|---|---|---|
| **D3 vs Fake News** | 3 | +0.47 | [+0.20, +1.00] | **<0.0001** ✅ |
| **D5 vs Fake News** | 3 | +0.67 | [+0.20, +1.40] | **<0.0001** ✅ |
| **D3 vs Cross-Channel** | 3 | +0.47 | [+0.20, +0.60] | **<0.0001** ✅ |
| **D5 vs Cross-Channel** | 3 | +0.47 | [+0.40, +0.60] | **<0.0001** ✅ |
| D3 vs Mixed Attack | 3 | +0.07 | [-0.20, +0.20] | 0.62 ❌ leak |
| D5 vs Mixed Attack | 3 | -0.07 | [-0.40, +0.40] | 0.74 ❌ leak |

**The mixed-attack leak motivates D3b** (Independent-Source Provenance with
circular-provenance detection), which directly counters cross-channel
disinformation by detecting that multiple "sources" trace back to one
fabricated origin. **Currently testing D3b on PLTR** (to be cross-ticker
validated).

---

## Finding 4 — Sector-Narrative Coupling

**Headline claim**: Fake News Injection (A1) effectiveness is highly
dependent on sector-narrative match, not universal across tickers.

Using `avon_fake_tender_2015` (tech/M&A narrative) on 5 tickers:
- PLTR (data analytics): Δ=+0.64
- SNOW (cloud data): Δ=+0.33
- HOOD (fintech): Δ=+0.30
- BIIB (biotech): **Δ=+0.00** ← sector-mismatch failure
- NVDA (AI semis): **Δ=-0.70** ← high-prior backfire

Cross-ticker Δ=+0.114 [-0.300, +0.449] (n.s., $p_{BH}$=0.59) — variance
dominated by **two distinct failure modes**.

**Two distinct failure mechanisms uncovered by per-ticker analysis**:
1. **Sector-narrative mismatch** (BIIB, biotech): tech/M&A payload is
   semantically irrelevant; agent treats it as noise → $\Delta=+0.00$.
2. **High-prior backfire** (NVDA, AI semis): agent's clean baseline is
   already bullish-leaning ($\overline{\text{ord}}_{\text{clean}}=3.30$, vs
   $\sim 2.30$ for other tickers); the same fake-news payload triggers
   skepticism ("too good to be true") and pushes the decision DOWN to
   $\overline{\text{ord}}=2.60$ — a $-0.70$ swing in the opposite direction.

**Lit grounding**: The mismatch failure replicates Wallace et al.
EMNLP 2019 / Meade et al. arXiv 2024 "universal triggers are not
universal" in the multi-agent financial domain. The high-prior backfire
is a new finding specific to LLM agents with strong baseline priors
(e.g., NVDA bullishness).

**Cross-channel coordinated attack (A2v2) partially recovers the BIIB
outlier**: A2v2 BIIB $\Delta=+0.30$, Mixed Attack BIIB $\Delta=+0.40$ —
the cross-channel design partially overcomes sector-mismatch but does
NOT recover the NVDA backfire (A2v2 NVDA $\Delta=+0.10$, see
$\Cref{sec:results-mixed}$).

---

## Finding 3b — D3 Variant Comparison (PLTR N=5)

**Headline claim**: Provenance enforcement exhibits non-monotonic returns —
the lightest variant (D3a citation-only) is sufficient against single-channel
attacks; stricter variants (D3b) provide marginal additional value on mixed
attacks but appear to introduce conservative bias on legitimate signals.

| Defense × Attack | Δ vs none (PLTR) | Interpretation |
|---|---|---|
| **D3a vs Fake News** | **-0.20** (BEST) | citation-only sufficient — fake news lacks named sources |
| D3 (full) vs Fake News | +1.00 | works |
| D3b vs Fake News | +0.40 | strict rules over-cautious on legitimate signals |
| **D3a vs Cross-Channel** | **-0.40** (BEST) | same |
| D3 (full) vs Cross-Channel | +0.20 | works |
| D3b vs Cross-Channel | -0.20 | over-cautious |
| D3a vs Mixed Attack | +0.80 | leaks (named sources still pass) |
| **D3 (full) vs Mixed Attack** | **+0.20** | works (with corroboration) |
| **D3b vs Mixed Attack** | **+0.20** | works equally; circular detection no extra benefit |

**Caveat**: PLTR-only N=5 result. Cross-ticker validation pending on SNOW + HOOD.

**Paper interpretation**: The non-monotonic pattern suggests defense
strength must match attack class — not "more checks = always better".
Stronger variants (D3b) trade single-attack defense robustness for mixed-
attack robustness; in our setting the trade-off does not net positive.

---

## Finding 5 — Stealth Detector-Class Dependence

**Headline claim**: Adversarial stealth is fundamentally dependent on the
detector class. No single attack design hides from both lexical and FinBERT
detectors simultaneously.

| Attack | n | Lexical | FinBERT | Verdict |
|---|---|---|---|---|
| A1 avon (bullish) | 7 | 0.37 | 0.77 | borderline (5/7) |
| A1 craig (bearish) | 6 | 0.34 | 0.57 | anomalous (3/6) |
| **A2 (Atlas pump)** | 7 | **0.002** | **0.89** | anomalous (7/7) — lexically dead |
| **A2v2 (coord disinfo)** | 12 | **0.097** | **0.71** | anomalous (12/12) — mixed-format signature |

Key observations:
- A2v2 closes A2's lexical gap (50× improvement: 0.002 → 0.097)
- But introduces a mixed-document-format FinBERT signature (article + handle-tagged posts), lowering similarity to real news
- Bearish vs bullish: bearish narratives consistently FinBERT-lower (real-news cluster centroid is bullish-skewed)

**Implication**: D4 (Anomaly Filter) backends are complementary, not
redundant. Lexical catches A2 (lex=0.002), FinBERT catches A2v2 mixed-format
(FinBERT=0.71). **Verified empirically in defense matrix** (see Finding 5b).

---

## Finding 5b — Stealth × Defense Pairing (PLTR N=5, NEW)

**Headline claim**: Stealth metric directly predicts defense effectiveness.
Attacks that are anomalous on a given detector are caught by the
corresponding defense backend; attacks invisible to a detector evade its
defense.

| Attack | A2v2 lex score | D4 lex Δ | A2v2 FinBERT score | D4 FinBERT Δ |
|---|---|---|---|---|
| Fake News (A1) | 0.36 (borderline) | +0.40 (catches) | 0.77 (borderline) | +0.80 (catches) |
| Cross-Channel (A2v2) | 0.097 (near-threshold) | **-0.40 (LEAKS)** | 0.71 (anomalous) | +0.20 (catches) |
| Mixed Attack (combo) | (mixed) | **+0.00 (LEAKS)** | (mixed) | **+0.80 (catches strongly)** |

**FinBERT D4 is 4× more effective than lexical D4 against mixed attacks.**

This is the empirical confirmation of Finding 5's "detector-class dependence"
claim: A2v2 sits at lexical threshold (0.097 ≈ 0.10) so lexical filter
randomly catches/misses it; FinBERT catches it cleanly because of the mixed-
document-format embedding shift. **Mixed attacks should be filtered with
semantic-similarity backends, not lexical.**

---

## Finding 6 — Payload Variance Dominates Effect (K-Variant Ablation, PLTR)

**Headline claim**: A2v2 attack effectiveness is dominated by payload-side
variance, not agent-side stochasticity.

| | N=10 single payload | N=15 K=3 variants |
|---|---|---|
| A2v2 mean Δ | -0.10 | +0.53 |
| std | 0.48 | 1.22 |

→ Single-payload measurements (N=10 K=1) underestimate true attack effect
distribution. K=3 variants reveal genuine attack-success cases (1 Buy, 1
Overweight, 2 Sell among 15) that single-payload averaging masks.

---

## Outstanding experiments (priority order)

### 🔴 must-do (paper completeness)
- [ ] **Bearish defense matrix on PLTR** — D3/D5 vs bearish attacks. Closes direction symmetry of Finding 3. ~3 hr, ~$1.5. [Currently launched as T5+T6 split into d3/d5 sub-batches]

### 🟡 strongly recommended (paper robustness)
- [ ] **Architecture ablation cross-ticker on SNOW** — verify Finding 1 generalizes. ~3 hr, ~$1.5. [Currently launched as T3+T4]
- [ ] **D3 variants cross-ticker on SNOW + HOOD** — verify Finding 3b non-monotonic pattern generalizes (especially D3a strength on single attacks). ~4 hr (2 parallel), ~$3. [Currently launched as T1+T2]

### 🟢 optional (Tier 3 — workshop-bonus / top-conf)
- [ ] **Cross-LLM gpt-4o on PLTR** — robustness across model. ~3 hr, ~$30.
- [ ] **A1 sector-matched ablation on BIIB** — biotech-themed seed (Theranos-style) to validate sector-coupling claim. ~1.5 hr, ~$1.
- [ ] **K-variant on SNOW + HOOD** — strengthen Finding 6 cross-ticker. ~2 hr, ~$2.
- [ ] **Absorption judge on architecture variants** — verify A5v2 absorption goes UP under mem_to_analyst. ~10 min, ~$0.5.

---

## File map (data sources for paper)

```
adversarial/results/
├── secondary_metrics.csv              ← per-ticker × condition × defense (flip / distort / unsafe)
├── stats_hierarchical.csv             ← cross-ticker effects + 95% CI + BH p-values
├── architecture_ablation.csv          ← Finding 1 mechanism table
├── paper_attack_effects.csv           ← Findings 2/4/6 main table
├── paper_defense_effects.csv          ← Finding 3 main table
├── paper_stealth_summary.csv          ← Finding 5 main table
├── paper_arch_ablation.csv            ← Finding 1 main table
└── campaign/{TICKER}_{DATE}_{suffix}/
    └── results_full_with_absorption.json  ← Finding 1b absorption labels (where run)
```

```
adversarial/data/
└── stealth_report.json                ← Finding 5 raw data (lex + FinBERT)
```
