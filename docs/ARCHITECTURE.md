# Architecture

The framework targets **three independent supply-chain entry points** of
the upstream TradingAgents pipeline (5 analysts → Bull/Bear debate →
Risk Team → Portfolio Manager). Each defense sits at a different
architectural layer.

## Three attacks

| Attack | Entry point | Key technique |
|---|---|---|
| **Fake News Injection** | `route_to_vendor("get_news", …)` | LLM rewrites real SEC enforcement cases (Avon tender, Craig fake research, …) → 4-criterion LLM-Judge QC with up to 3 retry attempts → runtime monkey-patch appends fake article to vendor output. |
| **Cross-Channel Coordinated Disinformation** | same chokepoint, two-section payload | A *single* LLM call returns 1 Bloomberg-style article **plus** 5 social posts that explicitly cite the article; nested headers (`--- LATEST BREAKING UPDATES ---` / `--- RECENT SOCIAL MEDIA POSTS ---`) cause the News Analyst and Social Analyst to each extract their own segment, fabricating cross-source corroboration. |
| **Pattern-Matched Memory Poisoning** | per-trial isolated memory log file | 5 same-ticker + 3 cross-ticker fabricated `LESSON LEARNED` entries with directive reflection ("this is now a hard rule in my playbook") fully utilise the PM's memory budget; written before the trial begins, bypassing all upstream analysts. |

## Three defenses

| Defense | Architectural layer | Mechanism |
|---|---|---|
| **Provenance-Aware Portfolio Manager** | decision layer | Augments the PM's system prompt with a strength-tuneable provenance checklist. Three variants: `citation-only` (named-source check), `full` (+ corroboration + scale plausibility), `independent-source` (+ cross-channel-type check + circular-provenance detection). |
| **Anomaly Filter** | input layer | Hooks the same `route_to_vendor` chokepoint that the news / cross-channel attacks use. Splits each tool output into segments and assigns a stealth score; segments below a threshold are dropped. Two backends: `lexical` (9 hand-engineered features + bigram JS divergence vs a real-news baseline) and `finbert` (FinBERT [CLS] embedding cosine similarity vs baseline centroid). |
| **Skeptic Agent** | review layer | Inserts an independent gpt-4o-mini @ T = 0 between the Risk Team debate and the PM's decision. Runs a 7-item checklist (single-source, retail tone, self-undermining language, internal inconsistency, numeric implausibility, price-reaction self-narration, past-context pattern mismatch) and emits a 3-level caution verdict (`none / moderate / high`); the PM prompt is augmented with a hard rule that `high` requires a one-tier conviction downgrade.

All attacks and defenses are **runtime overlays** — no source files in
`tradingagents/` are modified — which makes the attack × defense matrix
cheap to enumerate (we run 1,210 trials across one process without
rebuilding the framework).

## Key technical details

- **Determinism.** Every random source is seed-controlled. Memory
  poisoning uses `random.Random(seed)`; LLM payloads are SHA1-keyed
  and persisted under `adversarial/data/`. Re-running an experiment
  hits the cache by default (`use_cache=True`).
- **Caching across layers.** Fake-news samples and cross-channel bundles
  are persisted as JSON under `adversarial/data/`; per-trial outputs
  under `adversarial/results/campaign/` and `…/defense_matrix/`. The
  demo reads cached payloads on demand, keeping deployment startup
  near-instant.
- **Refusal handling.** The fake-news generator detects model refusals
  at load and generate time and quarantines them rather than
  persisting refusal text into the cache.
- **Statistical methodology.** Cross-ticker effects are reported as
  cluster-bootstrap 95 % CIs (B = 10,000) with Benjamini-Hochberg FDR
  correction. Code: `adversarial/stats.py`, `adversarial/stats_hierarchical.py`.
- **No live trading.** All experiments are offline. LLM-generated content
  is tagged `[SYNTH-RED-TEAM]` for audit before that tag is stripped at
  injection time.
