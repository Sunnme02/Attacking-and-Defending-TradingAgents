# Paper Writing Companion

> Single-stop reference for writing the final report. Every number,
> figure, citation, and prose snippet you'll need is pointed to here.
> Maintained alongside `PROJECT.md` (task tracker) and `RESULTS.md`
> (raw numerical data).

Last updated: 2026-05-04 — 6 batches still running (~1.5 hr remaining).
This doc is **complete enough to write everything except §5.3 cross-
ticker arch ablation tail and §5.5 defense cross-ticker / bearish
defense subsections**, which depend on the running batches.

---

## 0. Quick paper-writing index

| If you want to write… | Open this file/section |
|---|---|
| Method / experimental setup | `main.tex` §3–§4 (already drafted) |
| Specific numbers in Results §5.x | `RESULTS.md` Finding 1–6 (locked) |
| Citation BibTeX entry | `paper/refs.bib` (verified) |
| What figure goes where | §3 of THIS file (figures inventory) |
| Pre-written prose for §5 subsections | §4 of THIS file (snippets) |
| What's missing for paper | §5 of THIS file (gap checklist) |

---

## 1. Data Status Dashboard (as of last update)

### ✅ Locked — ready to use in paper

| Data | Path | N trials |
|---|---|---|
| v1 bullish baseline | `results/campaign/{TICKER}_{DATE}/` | 5 ticker × 4 cond × N=10 = 200 |
| v2 bullish | `results/campaign/{TICKER}_{DATE}_v2/` | 5 ticker × 4 cond × N=10 = 200 |
| Bearish | `results/campaign/{TICKER}_{DATE}_bearish/` | 5 ticker × 4 cond × N=10 = 200 |
| K-variant ablation | `results/campaign/PLTR_2025-12-09_kvariant/` | 45 |
| Architecture ablation PLTR | `results/campaign/PLTR_2025-12-09_arch_*/` | 4 variants × 3 cond × N=5 = 60 |
| Defense matrix bullish | `results/defense_matrix/{TICKER}_{DATE}_v2attacks_bullish/` | 3 ticker × 3 def × 4 atk × N=5 = 180 |
| D3 variants PLTR | `results/defense_matrix/PLTR_2025-12-09_d3_variants/` | 40 |
| D4 lex / FinBERT PLTR | `results/defense_matrix/PLTR_2025-12-09_d4_eval/` + `_d4_finbert/` | 80 |
| Absorption judge (5 ticker × N=10) | `results/campaign/{TICKER}_{DATE}_v2/results_full_with_absorption.json` | 150 |
| Stealth metric (all cached payloads) | `data/stealth_report.json` | 32 |

### 🔄 Currently running (~1.5 hr remaining)

| Batch | Path on completion | Trials |
|---|---|---|
| D3 variants SNOW | `results/defense_matrix/SNOW_2025-12-16_d3_variants/` | 40 |
| D3 variants HOOD | `results/defense_matrix/HOOD_2026-01-13_d3_variants/` | 40 |
| Architecture ablation SNOW | `results/campaign/SNOW_2025-12-16_arch_*/` | 60 |
| Bearish defense matrix PLTR (none + d3) | `results/defense_matrix/PLTR_2025-12-09_bearish_d3/` | 40 |
| Bearish defense matrix PLTR (none + d5) | `results/defense_matrix/PLTR_2025-12-09_bearish_d5/` | 40 |

### ❌ Not in scope for course report (Tier 3, see `PROJECT.md`)

- Cross-LLM gpt-4o
- Sector-matched A1 (Theranos seed)
- D3+D5 combined defense
- Real backtest with portfolio P&L
- Adaptive attacker

These are all flagged in `PROJECT.md` Tier 3 with full execution
commands for future use.

### Aggregated paper-ready data files (regenerate after pending batches)

```
results/secondary_metrics.csv         per-ticker × cond × def: flip / distortion / unsafe
results/stats_hierarchical.csv        cluster bootstrap effects + 95% CI + BH p-values
results/architecture_ablation.csv     PLTR arch variants
results/paper_attack_effects.csv      Findings 2/4/6 main table
results/paper_defense_effects.csv     Finding 3 main table
results/paper_stealth_summary.csv     Finding 5 main table
results/paper_arch_ablation.csv       Finding 1 main table
data/stealth_report.json              Finding 5 raw data
```

To regenerate after pending batches finish:
```bash
cd ~/Projects/TradingAgents
python -m adversarial.analyze_secondary
python -m adversarial.stats_hierarchical
python -m adversarial.aggregate_paper
```

---

## 2. Naming Convention (paper-facing)

For consistency across `main.tex`, figures, and tables. **Use these
names everywhere reviewers can see**, NOT the internal codes
(A1/A2v2/D3 etc.) which are implementation labels.

| Internal code | Paper name |
|---|---|
| A1 | **Fake News Injection** |
| A2 (v1) | Single-Channel Social Pump |
| A2v2 | **Cross-Channel Coordinated Disinformation** |
| A5 (v1) | Generic Memory Poisoning |
| A5v2 | **Pattern-Matched Memory Poisoning** |
| a2v2_a5v2 | **Mixed Attack** |
| D3a | Citation-Only Provenance |
| D3 (full) | **Provenance-Aware PM** |
| D3b | Independent-Source Provenance |
| D4 | **Anomaly Filter** |
| D5 | **Skeptic Agent** |

Latex macros already defined in `main.tex`: `\attack{...}`, `\defense{...}`.

---

## 3. Figure Inventory and Production Status

### Figures the paper needs

| # | Title | Status | Data Source | Production tool |
|---|---|---|---|---|
| **Fig 1** | Threat surfaces and defense overlays on TradingAgents pipeline | ✅ Designed (hand-drawn done; 待用 GPT/draw.io 重绘) | — (conceptual) | draw.io / Excalidraw / DALL-E |
| **Fig 2** | Attack mechanisms vs defense countermeasures (4-row pairs) | ❌ Not started | — (conceptual) | draw.io |
| **Fig 3** | Architecture ablation bar chart | ❌ Not started | `paper_arch_ablation.csv` | matplotlib (need to install) or Excel |
| **Fig 4** | Defense effect forest plot | ❌ Not started | `paper_defense_effects.csv` (level=cross) | matplotlib or Excel |
| **Fig 5** | Stealth × defense pairing scatter | ❌ Not started | `paper_stealth_summary.csv` + `paper_defense_effects.csv` | matplotlib |
| **Fig 6** | Per-ticker attack effect (forest plot) | ❌ Not started | `paper_attack_effects.csv` (level=ticker) | matplotlib |

### What's missing to produce figures

- **matplotlib not installed.** Either:
  ```bash
  pip install matplotlib pandas
  ```
  or use Excel / Google Sheets to plot the CSV files directly.

- **Figure 1/2 are not data-driven.** Hand-draw or use draw.io / DALL-E.

### Recommendation

For course report, **3 figures are usually sufficient**:
1. Fig 1 (overview) — already started, finalize after running batches done
2. Fig 3 (architecture ablation) — strongest result, 4 bars
3. Fig 4 (defense forest plot) — 6 cells, shows main defense table

The other 3 figures (Fig 2 mechanism details, Fig 5 stealth scatter,
Fig 6 per-ticker forest plot) are **paper polish**, not strict course
requirements.

---

## 4. Pre-written Prose Snippets for Results Section

Each subsection of §5 in `main.tex` has a placeholder. Below are
detailed paragraphs you can adapt directly. **All numbers cited
below are locked; do not edit unless re-running stats.**

---

### §5.1 Sector-narrative coupling of fake-news attack effectiveness

We instantiate the Fake News Injection attack (A1) using the
SEC-enforcement-action seed `avon_fake_tender_2015` (a tech/M&A
narrative) and inject into the news vendor channel of all five tickers.
Per-ticker effects span a striking range: PLTR $\Delta=+0.64$
(data analytics) and SNOW $\Delta=+0.33$ (cloud data) and HOOD
$\Delta=+0.30$ (fintech) all show the expected attacker-aligned shift,
BIIB $\Delta=+0.00$ (biotech) is unaffected, and NVDA $\Delta=-0.70$
(AI semis) shifts in the \emph{opposite} direction --- a backfire of
$0.70$ ordinal tiers. Cross-ticker mean $\Delta=+0.114$ with
$95\%$ cluster-bootstrap CI $[-0.300,+0.449]$ ($p_{BH}=0.59$, n.s.).

Per-ticker analysis reveals two distinct failure modes hidden by the
cross-ticker average. First, a \emph{sector-narrative mismatch}
(BIIB): the tech/M\&A narrative carries no semantic relevance to
biotech and the agent treats it as noise. This replicates the
Universal-Triggers-Not-Universal finding of
\citet{meade2024universalnotuniversal} in the multi-agent financial
domain. Second, a \emph{high-prior backfire} (NVDA): NVDA's clean
baseline ordinal is $3.30$ (Hold/Overweight-leaning), substantially
above the other tickers' $\sim 2.30$ baseline; under the same fake-news
payload, the agent's risk-aversion machinery interprets the unverified
bullish claim as a "too good to be true" signal and swings the
decision \emph{downward} to $\bar{\text{ord}}=2.60$. This is, to our
knowledge, the first documented case of an adversarial fake-news
attack \emph{backfiring} on an LLM trading agent because the target's
own priors were already aligned with the attack direction --- a finding
with practical implications for adversarial threat modeling on
strong-prior assets.

[Insert Figure 6 here: per-ticker forest plot of A1 cross-ticker
effects.]

---

### §5.2 Cross-channel mixed attack partially overcomes sector mismatch

We test whether cross-channel coordinated disinformation can recover
the BIIB outlier from §5.1. The Cross-Channel Coordinated
Disinformation attack (A2v2) injects one Bloomberg-style fabricated
article plus five trader-tone social posts that explicitly cite the
article, simulating multi-channel adversarial corroboration. On BIIB
(biotech), A2v2 reaches $\Delta=+0.30$ and the Mixed Attack reaches
$\Delta=+0.40$ — comparing to A1's $\Delta=+0.00$ on the same ticker.
Cross-ticker, A2v2 yields $\Delta=+0.04$ and the Mixed Attack
$\Delta=+0.10$ (both n.s.; CIs include zero). The interpretation is
that cross-source corroboration partially substitutes for narrative-
sector fit — when the news article alone is insufficient to convince
the agent, social-media corroboration provides a second independent
signal that the agent's downstream synthesis treats as cross-validating
evidence. This mirrors the mixed-attack mechanism formalized by
\citet{zhang2025asb} in their Agent Security Bench (their reported
mixed-attack ASR of 84.30\% benchmarks this attack class as the SOTA-
effective configuration).

---

### §5.3 Architectural memory access boundary as immunity mechanism

We then test whether memory poisoning can move the agent's decision.
The Pattern-Matched Memory Poisoning attack (A5v2) pre-populates the
agent's long-term memory log with eight directive "lesson learned"
entries. Despite its design — semantic imitation
heuristic~\citep{srivastava2025memorygraft}, vocabulary overlapping
real analyst reports (13F filings, operating leverage, options flow),
and full utilization of the PM's memory reader cap — the cross-ticker
bullish effect is $\Delta=-0.12~[-0.28,+0.06]$ ($p_{BH}=0.30$, n.s.).
Notably, this is consistent with ASB's reported memory-poisoning-
alone ASR of $7.92\%$~\citep{zhang2025asb}; we measure $0\%$ because
\TA's hierarchical pipeline appears more restrictive.

\paragraph{Absorption-judge data isolates the failure mode.}
We use a separate LLM-as-judge (\texttt{gpt-4o-mini}, temperature$=0$)
to assess whether the injected payload reaches the analyst-stage
reports (news, sentiment, fundamentals) at all. Across $5$ tickers
$\times$ $N=10$ trials, A2v2 absorbs as `fully\_absorbed' in $50/50$
trials ($100\%$); A5v2 is `not\_absorbed' in $49/50$ trials ($98\%$).
The asymmetry is mechanistic: \TA{} grants memory access only to
the Portfolio Manager, the last node in the pipeline, by which point
upstream agents have already anchored the decision without seeing
memory.

\paragraph{Architectural ablation confirms the mechanism causally.}
On PLTR ($N=5$ each variant, $3$ conditions):

\begin{tabular}{lcc}
\toprule
Variant & $\Delta_{\text{A5v2}}$ & $\Delta_{\text{Mixed}}$ \\
\midrule
None (full pipeline)   & $+0.00$ & $+0.00$ \\
\texttt{mem\_to\_analyst} & $+0.80$ & $+0.60$ \\
\texttt{no\_bb} (skip Bull/Bear) & $+1.40$ & $+1.40$ \\
\texttt{no\_risk} (skip Risk debate) & $+1.00$ & $-0.40$ \\
\bottomrule
\end{tabular}

Moving memory access into the Fundamentals Analyst recovers an
$0.80$-tier decision shift; removing the Bull/Bear research debate
recovers $1.40$ tiers; removing the risk debate recovers $1.00$ tiers.
All three independent ablations confirm that A5v2's failure is
architecture-induced, not payload-weakness-induced.
[NOTE: cross-ticker validation on SNOW currently running.]

[Insert Figure 3 here: architecture ablation bar chart.]

---

### §5.4 Direction-asymmetric architectural immunity

The architectural immunity is not symmetric. Reversing the attack
direction to bearish (using the SEC seed `craig\_twitter\_2015` and
A5v2 with `--direction=bearish`), the cross-ticker A5v2 effect becomes
$\Delta=-0.42$ with $95\%$ CI $[-0.68,-0.16]$ ($p_{BH}<0.0001$,
significant). On PLTR specifically, the bearish A5v2 distribution is
\emph{bimodal}: $6/10$ trials follow the poisoned memory toward Sell
(ord$=1$) while $4/10$ revolt to Hold (ord$=3$). The within-batch
position distortion is $0.98$ versus a clean baseline of $0.18$ ($5\times$
stretch).

We hypothesize that bearish poisoned memory synergizes with the agent's
default risk-averse bias (PMs trained on financial data tend toward
Hold/Underweight as the safe baseline action), while bullish memory
must overcome this same bias to move the decision upward. This makes
A5v2 the only attack in our suite to achieve a statistically
significant cross-ticker effect — and it does so only in the bearish
direction. The finding has dual implications: (i) defenders cannot
assume that an attack class which fails in one direction will fail in
both; (ii) the agent's own decision priors are themselves an
adversarial target.

---

### §5.5 Single-channel defense effectiveness and mixed-attack leak

We evaluate D3 (Provenance-Aware PM, three strength levels), D4
(Anomaly Filter, two backends), and D5 (Skeptic Agent) across three
tickers (PLTR / SNOW / HOOD), four attacks, $N=5$ seeds per cell
(180 trials in the bullish v2attacks defense matrix).

\paragraph{Single-channel attacks are robustly defended.} Cross-ticker
defense effects (mean ordinal reduction vs the no-defense baseline,
with cluster-bootstrap 95\% CI):

\begin{tabular}{lccc}
\toprule
Defense & A1 & A2v2 & Mixed Attack \\
\midrule
D3 (full) & $+0.47$ [$+0.20,+1.00$] *** & $+0.47$ [$+0.20,+0.60$] *** & $+0.07$ [$-0.20,+0.20$] \\
D5 (Skeptic) & $+0.67$ [$+0.20,+1.40$] *** & $+0.47$ [$+0.40,+0.60$] *** & $-0.07$ [$-0.40,+0.40$] \\
\bottomrule
\end{tabular}

Asterisks denote $p_{BH}<0.0001$. Both prompt-level (D3) and
agent-level (D5) defenses neutralize single-channel attacks with high
statistical confidence (4/4 cells). Both \emph{leak} on the Mixed
Attack: D3's effect collapses to $+0.07$ (CI includes zero); D5's
effect is $-0.07$ (CI includes zero, sign reverses).

\paragraph{D3 strength variants exhibit non-monotonic returns.} On
PLTR ($N=5$), comparing the three D3 strength levels:

\begin{itemize}
\item D3a (citation-only) is unexpectedly strongest on single attacks
      (Δ vs A1: $-0.20$, A2v2: $-0.40$, both attacks pushed downward),
      because the fake-news payloads contain only fabricated/anonymous
      sources that fail the citation requirement.
\item D3 (full) provides modest additional value on Mixed Attack
      ($\Delta=+0.20$) via the corroboration check.
\item D3b (independent-source + circular-provenance detection) was
      designed to close the Mixed-Attack leak, but on PLTR shows
      $\Delta=+0.20$ — equal to D3 (full), no incremental benefit.
\end{itemize}

The non-monotonicity suggests defense strength must match attack
class — strict cross-channel rules trade single-attack robustness for
mixed-attack robustness, and the trade-off does not net positive in
our setting. [NOTE: cross-ticker validation on SNOW + HOOD currently
running.]

[NOTE: Bearish defense matrix currently running. Once complete, add a
paragraph on whether D3/D5 also defend bearish A5v2 — the only
significant single attack in our suite.]

[Insert Figure 4 here: defense effect forest plot.]

---

### §5.6 Stealth detector-class dependence and stealth–defense pairing

To explain why D4's lexical and FinBERT backends differ, we measure
the stealth profile of each attack payload using two complementary
detectors: lexical (sentence-length statistics, type-token ratio,
hedge-word density, retail-marker frequency, bigram Jensen-Shannon
divergence vs a real-news baseline) and semantic (FinBERT CLS
embedding cosine similarity to the same baseline).

\begin{tabular}{lccc}
\toprule
Attack & $n$ payloads & Lexical (mean) & FinBERT (mean) \\
\midrule
A1 (Fake News, avon bullish) & 7 & $0.379$ & $0.768$ \\
A1 (Fake News, craig bearish) & 6 & $0.344$ & $0.572$ \\
A2 (Atlas pump, retail) & 7 & $\mathbf{0.002}$ & $\mathbf{0.890}$ \\
A2v2 (Cross-Channel) & 12 & $0.097$ & $0.713$ \\
\bottomrule
\end{tabular}

A2 exhibits a striking lexical-vs-FinBERT divergence: lexically dead
($0.002$, far below the $0.10$ threshold) yet semantically real-like
($0.890$). A2v2 closes the lexical gap by $50\times$ ($0.097$, near the
threshold) but introduces a new mixed-document-format signature that
lowers FinBERT similarity to $0.713$. A1 sits at the borderline of
both detectors.

\paragraph{D4 backend defense effects empirically validate this.}
On PLTR ($N=5$):

\begin{tabular}{lccc}
\toprule
Defense & A1 & A2v2 & Mixed Attack \\
\midrule
D4 (Lexical) & $+0.40$ & $-0.40$ & $+0.00$ \\
D4 (FinBERT) & $+0.80$ & $+0.20$ & $+0.80$ \\
\bottomrule
\end{tabular}

D4 with the lexical backend leaks A2v2 (negative $\Delta$) and is
ineffective on the Mixed Attack ($\Delta=0.00$). D4 with the FinBERT
backend catches A2v2 (positive $\Delta$) and is the strongest single
defense against the Mixed Attack ($\Delta=+0.80$), which neither D3
(full) nor D5 achieves on a single-ticker N=5 measurement. The result
is the empirical confirmation of detector-class dependence: stealth-
metric data directly predicts which defense backend is appropriate for
which attack class.

[Insert Figure 5 here: stealth × defense scatter, axes
lexical-stealth vs FinBERT-stealth, points colored by attack, marker
size proportional to D4-FinBERT $\Delta$.]

---

### §5.7 Payload variance dominates seed variance

Cross-ticker measurements suffer from payload-side stochasticity:
when each ticker × condition cell uses a single LLM-generated payload
(K=1) shared across $N$ seeds, the seed-level standard deviation
underestimates the true effect distribution. We test this on PLTR by
generating $K=3$ independent A2v2 payload variants and running
$N=15$ seeds (each variant gets 5 seeds via deterministic cycling).

\begin{itemize}
\item PLTR $K=1, N=10$: A2v2 $\Delta=-0.10$, std $=0.48$
\item PLTR $K=3, N=15$: A2v2 $\Delta=+0.53$, std $=1.22$
\end{itemize}

The $K=3$ measurement reveals 1 Buy, 1 Overweight, and 2 Sell among
the 15 trials — extreme decisions that the $K=1$ measurement averages
away as null effect. Payload-side variance ($0.74$-tier shift in
mean estimate) dominates agent-side seed variance (which on this
ticker is $\sim 0.5$ ordinal-tier).

The implication is methodological: claims of attack effectiveness
should report payload variance explicitly, ideally via $K\geq 3$
ablation. Single-payload measurements may dramatically under- or
over-estimate true attack potential.

---

## 5. Gap Checklist (what's still missing for a complete report)

### ❌ Data still pending (will be locked when current batches finish, ~1.5 hr)

- [ ] §5.3 cross-ticker arch ablation tail — needs SNOW arch ablation data (T3+T4)
- [ ] §5.5 D3 variants cross-ticker — needs SNOW + HOOD D3 variants data (T1+T2)
- [ ] §5.5 bearish defense matrix paragraph — needs T5+T6 data

### ❌ Prose / Sections to write

- [ ] §1 Introduction — DONE (in main.tex)
- [ ] §2 Related Work — outline only; needs filling (~1 hr; see citations in `refs.bib`)
- [ ] §3 Threat Model — outline only; copy from PROJECT.md "Threat Model" section (~30 min)
- [ ] §4 Methodology — DRAFT in main.tex, very detailed; ready as-is
- [ ] §5 Results — 5 of 7 subsections lockable now from §4 of THIS file
- [ ] §6 Discussion — needs prose; key points: two-tier defense, defense composition, limitations
- [ ] §7 Conclusion — short summary

### ❌ Figures to create

- [ ] Figure 1: Overview — hand-drawn done; needs draw.io/GPT redraw with labels
- [ ] Figure 3: Architecture ablation bar chart — data in `paper_arch_ablation.csv`
- [ ] Figure 4: Defense effect forest plot — data in `paper_defense_effects.csv`
- [ ] (Optional) Figure 2: Attack/defense pairs (4-row layout)
- [ ] (Optional) Figure 5: Stealth × Defense scatter
- [ ] (Optional) Figure 6: Per-ticker forest plot

### ⚠️ Tools / dependencies

- [ ] `pip install matplotlib pandas` (to render figures from CSV)
  - Alternative: Excel or Google Sheets directly on CSVs

### ✅ Already in good shape

- ✅ Citation list verified (8 entries in `refs.bib`)
- ✅ Naming convention locked (paper-facing names)
- ✅ Threat model framing rewritten (PROJECT.md "Threat Model" section)
- ✅ Lit grounding double-checked (PROJECT.md "已核验的 lit grounding")
- ✅ Numerical results aggregated (4 paper_*.csv files)
- ✅ Statistical methodology ready (cluster bootstrap + BH correction)
- ✅ LaTeX template + macros + sectioning (main.tex)

---

## 6. Quick Reference: where to find every number cited in §5

| Finding | Number | File |
|---|---|---|
| A1 per-ticker (PLTR +0.64, SNOW +0.33, HOOD +0.30, BIIB +0.00, NVDA -0.70) | per-ticker mean diff | `paper_attack_effects.csv` (level=ticker, batch=v1_bullish, attack=a1) |
| A1 BIIB Δ=+0.00 | per-ticker | same file, ticker=BIIB |
| A1 cross-ticker Δ=+0.114 [-0.300, +0.449] p=0.59 | hierarchical bootstrap | `stats_hierarchical.csv` (test_family=attack_effect_v1, comparison='a1 vs clean') |
| A2v2 BIIB Δ=+0.30, Mixed BIIB Δ=+0.40 | per-ticker | `secondary_metrics.csv` (ticker=BIIB, batch_type=v2) |
| A5v2 cross-ticker bullish Δ=-0.12 [-0.28, +0.06] p=0.30 | hierarchical bootstrap | `stats_hierarchical.csv` (a5v2 v2_bullish) |
| A5v2 absorption 49/50 not_absorbed | per-ticker | `results_full_with_absorption.json` files |
| A2v2 absorption 50/50 fully_absorbed | per-ticker | same |
| Architecture ablation 4 variants × 3 conds | PLTR table | `paper_arch_ablation.csv` |
| A5v2 BEARISH Δ=-0.42 [-0.68, -0.16] p<0.0001 | hierarchical bootstrap | `stats_hierarchical.csv` (a5v2 bearish) |
| Defense effects D3/D5 vs A1/A2v2/Mixed | cross-ticker bootstrap | `paper_defense_effects.csv` (level=cross, matrix=_v2attacks_bullish) |
| D3 variants on PLTR | within-batch | `paper_defense_effects.csv` (matrix=_d3_variants) |
| D4 lexical vs FinBERT on PLTR | within-batch | `paper_defense_effects.csv` (matrix=_d4_eval / _d4_finbert) |
| Stealth A1 / A2 / A2v2 means | per-attack means | `paper_stealth_summary.csv` or `data/stealth_report.json` |
| K-variant Δ=+0.53 std=1.22 | aggregate | `results/campaign/PLTR_2025-12-09_kvariant/summary.json` |

---

## 7. Recommended Writing Order

1. **Now (no waiting)**: Flesh out §3 Threat Model and §4 Methodology
   from the existing main.tex outline. ~1.5 hr.
2. **After current batches finish (~1.5 hr from now)**: Re-run
   `aggregate_paper`, then write §5.3 / §5.5 / §5.6 / §5.7 using the
   pre-written prose snippets in §4 of this file. ~3 hr.
3. **Once §5 is done**: Write §6 Discussion (key points: two-tier
   defense, defense composition, limitations) and §7 Conclusion.
   ~1 hr.
4. **Last**: Revise §1 Introduction so it references the actual §
   numbers in the paper. (Already drafted; just needs section-number
   updates.) ~15 min.
5. **Final**: §2 Related Work as the final pass — write last so it
   references the same citations the rest of the paper uses. ~1 hr.
6. **Figures**: After §5 done, install matplotlib, generate Fig 3 and
   Fig 4 from CSVs. Hand-draw / GPT-render Fig 1. ~2 hr.
7. **Polish**: typo / grammar / consistency / format check. ~1 hr.

Total writing time estimate: **~10 hr** for an A+ course report.
