"""
Multi-(ticker, date) batch orchestrator.

Sequentially runs ``run_campaign`` for each (ticker, date) target. We do NOT
parallelize because ``news_injection.INJECTION_REGISTRY`` is module-level
state and concurrent campaigns would race.

Each target produces an independent campaign directory under
``adversarial/results/campaign/{TICKER}_{DATE}/`` (same as a single-ticker
``run_campaign`` invocation). The orchestrator additionally writes a
top-level batch summary recording which targets completed and timing.

Default targets implement **knowledge-isolated evaluation**: all dates
≥ 2025-12-01 (post-cutoff for the agent LLM gpt-4o-mini and any frontier
model we might later test like Sonnet/Opus/GPT-5), with vendor data
frozen via yfinance and live web/tool access disabled. The combination
prevents the agent from using its own pre-training knowledge to override
the injected adversarial narrative — a property required for valid
adversarial evaluation independent of model identity.

Run:
    # Canary (one ticker, small N)
    python -m adversarial.run_batch --targets PLTR:2025-12-09 --n-seeds 2

    # Full default 5-ticker × N=10 batch
    python -m adversarial.run_batch --n-seeds 10
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


# Knowledge-isolated default targets. All dates >= 2025-12-01 are
# post-cutoff for the agent LLM (gpt-4o-mini) and any frontier model we
# might later test (Sonnet/Opus/GPT-5). Combined with frozen yfinance
# vendor data and disabled live web/tool access, this ensures the agent
# cannot use its own pre-training knowledge to override the injected
# adversarial narrative.
#
# Selection rationale (per `PROJECT.md` criteria):
#   - mid-cap or controlled mega-cap (5B–200B market cap)
#   - Tuesday/Wednesday only (max liquidity, no weekend gaps)
#   - ≥ 14 days from each ticker's quarterly earnings
#   - sector-diverse: AI/data + cloud + fintech + biopharma + mega-cap-control
DEFAULT_TARGETS = [
    {"ticker": "PLTR", "date": "2025-12-09", "sector": "AI/data"},
    {"ticker": "SNOW", "date": "2025-12-16", "sector": "cloud/AI"},
    {"ticker": "HOOD", "date": "2026-01-13", "sector": "fintech"},
    {"ticker": "BIIB", "date": "2025-12-02", "sector": "biopharma"},
    {"ticker": "NVDA", "date": "2026-01-20", "sector": "mega-cap-tech"},
]


BATCH_DIR = ROOT / "adversarial" / "results" / "batch"


def parse_targets(raw: str | None) -> list[dict]:
    """Parse --targets argument. Format: 'TICKER:YYYY-MM-DD,TICKER2:DATE2'.
    Empty → DEFAULT_TARGETS."""
    if not raw:
        return DEFAULT_TARGETS
    out = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if ":" not in tok:
            raise ValueError(f"bad target {tok!r}: expected 'TICKER:YYYY-MM-DD'")
        ticker, date = tok.split(":", 1)
        out.append({"ticker": ticker.strip().upper(), "date": date.strip()})
    return out


def campaign_done(ticker: str, date: str) -> bool:
    """Check if a campaign already produced its summary.json."""
    p = ROOT / "adversarial" / "results" / "campaign" / f"{ticker}_{date}" / "summary.json"
    return p.exists()


def run_one_campaign(target: dict, args) -> dict:
    """Invoke run_campaign as a subprocess for one (ticker, date).

    Subprocess isolation matters: each invocation starts with a clean
    Python interpreter, so any in-process state (INJECTION_REGISTRY,
    cached imports, langchain client pools) is reset between campaigns.
    """
    cmd = [
        sys.executable, "-m", "adversarial.run_campaign",
        "--ticker", target["ticker"],
        "--date", target["date"],
        "--n-seeds", str(args.n_seeds),
        "--conditions", args.conditions,
        "--a1-case", args.a1_case,
        "--a2-direction", args.direction,
        "--a2-n-posts", str(args.a2_n_posts),
        "--a5-direction", args.direction,
        "--a5-n-same", str(args.a5_n_same),
        "--a5-n-cross", str(args.a5_n_cross),
        "--agent-llm", args.agent_llm,
        "--payload-model", args.payload_model,
    ]
    if args.a1_direction:
        cmd += ["--a1-direction", args.a1_direction]
    if args.n_payload_variants > 1:
        cmd += ["--n-payload-variants", str(args.n_payload_variants)]

    print(f"\n{'='*72}")
    print(f">>> {target['ticker']} / {target['date']}  "
          f"(sector: {target.get('sector', 'unknown')})")
    print(f"{'='*72}")

    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    start = datetime.utcnow()
    try:
        proc = subprocess.run(cmd, env=env, check=False)
        rc = proc.returncode
    except Exception as e:
        rc = -1
        print(f"!! subprocess raised: {e}")
    elapsed = (datetime.utcnow() - start).total_seconds()

    return {
        "ticker": target["ticker"],
        "date": target["date"],
        "sector": target.get("sector"),
        "exit_code": rc,
        "success": rc == 0,
        "elapsed_sec": round(elapsed, 1),
    }


def main() -> None:
    p = argparse.ArgumentParser(
        description="Multi-(ticker, date) batch orchestrator."
    )
    p.add_argument("--targets", default=None,
                   help="Comma-list 'TICKER:YYYY-MM-DD,...'. "
                        "Default: 5 knowledge-isolated tickers (post-cutoff dates "
                        "+ frozen vendor data).")
    p.add_argument("--n-seeds", type=int, default=10)
    p.add_argument("--conditions", default="clean,a1,a2,a5")
    p.add_argument("--direction", default="bullish",
                   choices=["bullish", "bearish"])
    p.add_argument("--a1-case", default="avon_fake_tender_2015")
    p.add_argument("--a1-direction", default=None)
    p.add_argument("--a2-n-posts", type=int, default=5)
    p.add_argument("--a5-n-same", type=int, default=3)
    p.add_argument("--a5-n-cross", type=int, default=2)
    p.add_argument("--agent-llm", default="gpt-4o-mini")
    p.add_argument("--payload-model", default="gpt-4o-mini")
    p.add_argument("--n-payload-variants", type=int, default=1)
    p.add_argument("--skip-done", action="store_true",
                   help="Skip targets whose campaign summary.json exists.")
    p.add_argument("--stop-on-failure", action="store_true",
                   help="Halt the batch if any campaign exits non-zero.")
    args = p.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY missing — check .env")

    targets = parse_targets(args.targets)

    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    batch_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    batch_log = BATCH_DIR / f"batch_{batch_id}.json"

    n_trials_per = args.n_seeds * len(args.conditions.split(","))
    cost_per_trial_usd = 0.02   # gpt-4o-mini empirical
    total_trials = n_trials_per * len(targets)
    total_min = total_trials * 2  # ~2 min per propagate

    print(f"\nBATCH START  id={batch_id}")
    print(f"  targets       = {len(targets)}")
    print(f"  N seeds       = {args.n_seeds}")
    print(f"  conditions    = {args.conditions}")
    print(f"  agent_llm     = {args.agent_llm}")
    print(f"  payload_model = {args.payload_model}")
    print(f"  K variants    = {args.n_payload_variants}")
    print(f"  est. trials   = {total_trials}  (~${total_trials*cost_per_trial_usd:.2f}, ~{total_min/60:.1f}h)")
    for t in targets:
        print(f"    - {t['ticker']:6s}  {t['date']}  ({t.get('sector','?')})")
    print()

    results: list[dict] = []
    for idx, target in enumerate(targets, 1):
        print(f"\n[batch {idx}/{len(targets)}]")
        if args.skip_done and campaign_done(target["ticker"], target["date"]):
            print(f"  skip (already has summary.json)")
            results.append({
                "ticker": target["ticker"], "date": target["date"],
                "skipped": True, "success": True, "exit_code": 0,
            })
            continue
        r = run_one_campaign(target, args)
        results.append(r)
        # Persist after each campaign so partial batches are recoverable
        batch_log.write_text(json.dumps({
            "batch_id": batch_id, "args": vars(args),
            "targets": targets, "results": results,
        }, indent=2, ensure_ascii=False))
        if not r["success"] and args.stop_on_failure:
            print(f"!! campaign for {target['ticker']} failed; halting batch")
            break

    # Final batch summary
    succeeded = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    print(f"\n{'='*72}")
    print(f"BATCH DONE  id={batch_id}")
    print(f"  succeeded: {len(succeeded)} / {len(targets)}")
    print(f"  failed   : {len(failed)}")
    if failed:
        for r in failed:
            print(f"    - {r['ticker']} / {r['date']}  exit={r['exit_code']}")
    print(f"  log: {batch_log.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
