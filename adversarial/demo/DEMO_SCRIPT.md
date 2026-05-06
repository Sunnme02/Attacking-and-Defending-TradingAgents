# Demo Script — 8 minutes

> Project: *Attacking and Defending Multi-Agent LLM Trading Systems*
> Course: Columbia STAT GR5293 GenAI · Final demo
> Total: **8 min** (5 min Plan A + 2 min Plan B + 1 min buffer)

---

## Pre-flight (do *before* walking on stage)

- [ ] `export OPENAI_API_KEY=sk-...` in the shell you'll run from
- [ ] `./adversarial/demo/run_demo.sh` → opens browser to localhost:8765
- [ ] Open the **Skeptic — live** tab, click *📰 Clean PLTR baseline* → *Run Skeptic* with live mode → confirm it returns in ~5s
- [ ] Toggle *Use cached example* on; click each of the 3 sample buttons → confirm cache works
- [ ] Switch back to live mode; clear chat; have **two terminal tabs** ready (one for the app, one for `tail -f` logs in case)
- [ ] Have backup: a screen-recording video of the full demo, in case projector / WiFi dies

---

## Act 1 — Decision overview (2 min)

Open on **default config**: `bullish · PLTR · None (clean) · None`.

> "This is the TradingAgents pipeline running with no attack and no defense.
> Five agents reach a modal decision of **Underweight** — that maps to a
> short-side portfolio exposure of −0.5. This baseline is averaged over
> 41 independent runs with different random seeds."

**Click**: Sidebar → Attack → **Memory Poisoning**.

> "Now I inject 8 directive entries into the persistent memory. Note the
> mean ordinal jumps from 2.20 to about 2.27 — small, suggestive of a shift,
> but the cluster-bootstrap CI in the next tab shows this isn't statistically
> robust. **Architectural absorption is doing some of the defending for free.**"

**Click**: Sidebar → Attack → **Mixed (Cross-Channel + Memory)**.

> "Combined attack — same story for PLTR. The architecture absorbs both."

**Click**: Sidebar → Direction → **bearish**, Attack → **Memory Poisoning**.

> "Now flip direction. Bearish memory poisoning **does** shift PLTR's mean
> ordinal down — the Δ in the next tab will show this is the one
> direction-attack pair where the architecture leaks."

---

## Act 2 — Reports (1.5 min)

**Click**: Tab → *📰 Agent reports*.

> "This is one trial under attack. The red highlights are pattern-matched
> phrases from our adversarial seeds — a fabricated 188% acquisition
> premium, the made-up filing, the price-reaction self-narration. Notice
> the **Investment Plan** on the right does cite this — the agents read
> the poisoned content. But the **Final Decision** still says Underweight.
> That's the gap between *perception-level absorption* and *decision-level
> resistance* — the two-tier framing in the paper."

(Move slider to seed 5, point at how decision is stable across seeds.)

---

## Act 3 — Defenses & CIs (1.5 min)

**Back to Overview.** Sidebar → Defense → **Skeptic Agent**.

> "Now turn on the Skeptic. Mean ordinal moves toward the clean baseline,
> red bars in the next tab become smaller."

**Click**: Tab → *📈 Effect CIs*.

> "These are cluster-bootstrap 95% confidence intervals across all five
> tickers. With Skeptic on, the bearish memory-poisoning effect drops from
> Δ = −0.42, CI excluding zero, down to a CI that crosses zero. That's a
> meaningful neutralization."

> "The headline finding is in the paper Section 6: **defense composition
> is the more informative unit of analysis** — D3+D5 stacked is what
> actually works, neither alone closes the gap."

---

## Act 4 — Skeptic LIVE (2 min)

**Click**: Tab → *🛡️ Skeptic — live*.

> "The cached results are great, but the question is — does the Skeptic
> *actually catch* novel adversarial content it has never seen? Let's
> ask the audience to pick."

**Audience prompt**: *"Someone — give me an example of a fake news headline
about NVDA you'd worry would fool a trading agent."*

If audience freezes, click **🚨 Fake tender offer (Avon-style)** sample.

**Press ▶ Run Skeptic** (live mode, ~3-5s).

> "Watch it now — in real-time it's running the 7-item provenance
> checklist: single-source blockbuster check, retail-tone language, self-
> undermining caveats, internal inconsistency, numeric implausibility,
> price-reaction self-narration, past-context pattern mismatch."

When verdict appears: read out the flagged concerns.

> "Four concerns flagged. Confidence: low. Recommended caution: high.
> When this output is fed into the Portfolio Manager prompt, the PM
> downgrades its rating — that's the mechanism behind the CI shrinkage
> we just saw."

---

## Closing (30s)

> "To summarize: 1,210 trials show that perception-level absorption is
> nearly universal but decision-level resistance is configuration-
> dependent. The right unit of analysis is the **defense stack**, not
> any single component. Code, data, and this demo are all reproducible
> from the GitHub repo. Happy to take questions."

---

## Q&A — likely questions & 1-line answers

| Q | A |
|---|---|
| "Why gpt-4o-mini and not GPT-4?" | Cost per trial × 1,210 trials. Architectural conclusions should generalize to bigger models — that's a *prior-driven* finding in the paper's Scope of Generalization paragraph. |
| "What if Skeptic itself gets adversarially attacked?" | That's the adaptive-attacker section (§6.3). Carlini-style: redesign the news to dodge the 7-item checklist. We don't claim robustness against that. |
| "Why ordinal and not P&L?" | Two-tier framing: ordinal is decision-level proxy. Real P&L would require a market simulator + execution model — out of scope, flagged as future work. |
| "How do you know the defenses don't just hurt clean performance?" | Clean-baseline trials are run *with* each defense too. The Δ vs clean accounts for that — see paper Table 4. |
| "What's the most surprising finding?" | The bearish/bullish asymmetry — same architecture, same attacks, but only bearish memory poisoning leaks. We hypothesize it's because the bull/bear debate's prior on "verify suspicious bullish news" is weaker on the bear side. |

---

## Failure modes & recovery

| Symptom | Recovery |
|---------|----------|
| Skeptic spinner > 10s | Toggle *Use cached example* → re-run. Say "WiFi is being slow, here's the cached one." |
| API returns rate-limit error | Same fix. Don't show the error to the audience. |
| Streamlit crashes mid-demo | Already have screen-recording fallback; switch to it. |
| Audience asks for ticker we don't have | "We have full data for these 5 tickers. The framework generalizes — you'd just rerun the campaign with a new ticker." |
