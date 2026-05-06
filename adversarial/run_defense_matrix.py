"""
Defense × Attack matrix experiment.

For one (ticker, date), runs every (defense, attack) cell:
  defenses ∈ {none, d3, d5}   (3)
  attacks  ∈ {clean, a1, a2, a5}   (4)
  × N seeds = 12N trials per (ticker, date).

Each trial enables the appropriate defense BEFORE TradingAgentsGraph is
instantiated, then disables it cleanly in a finally block. Defenses are
mutually exclusive in this matrix (d3+d5 composition is excluded — those
two prompts replace each other under the current monkey-patch design).

Reuses the well-tested ``run_single`` from ``run_campaign``: same memory
isolation, same news-injection plumbing, same per-trial save protocol.
The only difference is enable_defense() / disable_defense() bracketing
each call.

Outputs:
    adversarial/results/defense_matrix/{TICKER}_{DATE}/
        results.csv                # appended after each trial
        results_full.json          # rolling, includes agent reports
        failures.json              # if any trial errored
"""

from __future__ import annotations

import argparse
import csv
import functools
import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Force unbuffered stdout (matches run_campaign behavior so progress is
# visible from a tee'd log without manual flush calls).
os.environ.setdefault("PYTHONUNBUFFERED", "1")
sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
print = functools.partial(print, flush=True)  # noqa: A001

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

from adversarial.run_campaign import (  # noqa: E402
    prepare_attack, run_single, to_ordinal,
)
from adversarial.defenses import skeptic_agent, provenance_pm, anomaly_filter  # noqa: E402


MATRIX_DIR = ROOT / "adversarial" / "results" / "defense_matrix"

DEFENSE_NAMES = ["none", "d3", "d3a", "d3b", "d4", "d5"]
ATTACK_NAMES = ["clean", "a1", "a2", "a5"]


def _setup_defense(
    name: str,
    skeptic_llm,
    *,
    d4_threshold: float = 0.10,
    d4_backend: str = "lexical",
) -> None:
    if name == "none":
        return
    if name == "d3":
        provenance_pm.enable(variant="full")
    elif name == "d3a":
        provenance_pm.enable(variant="a")
    elif name == "d3b":
        provenance_pm.enable(variant="b")
    elif name == "d4":
        anomaly_filter.enable(threshold=d4_threshold, backend=d4_backend)
    elif name == "d5":
        skeptic_agent.enable(skeptic_llm=skeptic_llm)
    else:
        raise ValueError(f"unknown defense {name}")


def _teardown_defense(name: str) -> None:
    if name == "none":
        return
    if name in ("d3", "d3a", "d3b"):
        provenance_pm.disable()
    elif name == "d4":
        anomaly_filter.disable()
    elif name == "d5":
        skeptic_agent.disable()
    else:
        raise ValueError(f"unknown defense {name}")


def _build_skeptic_llm(model: str):
    """The Skeptic uses temperature=0 for reproducible verdicts and a
    separate ChatOpenAI instance from the agent so we don't mutate the
    agent's LLM config when D5 is enabled."""
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, temperature=0.0, max_tokens=600)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ticker", required=True)
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.add_argument("--n-seeds", type=int, default=5)
    p.add_argument("--defenses", default="none,d3,d5")
    p.add_argument("--attacks", default="clean,a1,a2,a5")
    p.add_argument("--agent-llm", default="gpt-4o-mini")
    p.add_argument("--payload-model", default="gpt-4o-mini")
    p.add_argument("--skeptic-llm", default="gpt-4o-mini",
                   help="LLM the D5 Skeptic uses (independent instance)")
    p.add_argument("--a1-case", default="avon_fake_tender_2015")
    p.add_argument("--a1-direction", default=None)
    p.add_argument("--a2-direction", default="bullish")
    p.add_argument("--a2-n-posts", type=int, default=5)
    p.add_argument("--a5-direction", default="bullish")
    p.add_argument("--a5-n-same", type=int, default=3)
    p.add_argument("--a5-n-cross", type=int, default=2)
    p.add_argument("--n-payload-variants", type=int, default=1)
    p.add_argument("--d4-threshold", type=float, default=0.10,
                   help="Stealth threshold below which D4 drops a segment")
    p.add_argument("--d4-backend", default="lexical",
                   choices=["lexical", "finbert", "hybrid"],
                   help="D4 stealth-scoring backend")
    p.add_argument("--out-suffix", default="",
                   help="Optional suffix appended to output dir name; lets "
                        "defense matrices for different attack sets / "
                        "directions coexist (e.g. --out-suffix=_v2attacks).")
    args = p.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY missing — check .env")

    defenses = [d.strip() for d in args.defenses.split(",") if d.strip()]
    attacks = [a.strip() for a in args.attacks.split(",") if a.strip()]
    suffix = args.out_suffix or ""
    out_dir = MATRIX_DIR / f"{args.ticker}_{args.date}{suffix}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Pre-build payloads (or attack specs) once. Same caching applies.
    payloads: dict[str, dict] = {}
    for atk in attacks:
        sub = argparse.Namespace(
            attack=atk,
            ticker=args.ticker, date=args.date,
            payload_model=args.payload_model,
            a1_case=args.a1_case, a1_direction=args.a1_direction,
            a2_n_posts=args.a2_n_posts, a2_direction=args.a2_direction,
            a5_direction=args.a5_direction,
            a5_n_same=args.a5_n_same, a5_n_cross=args.a5_n_cross,
            n_payload_variants=args.n_payload_variants,
        )
        label, spec = prepare_attack(sub)
        payloads[atk] = spec
        if spec.get("kind") == "news":
            k = len(spec["variants"])
            sizes = [len(v) for v in spec["variants"]]
            print(f"  payload[{atk}] -> {label}  ({k} variant(s), sizes={sizes})")
        elif spec.get("kind") == "memory":
            print(f"  payload[{atk}] -> {label}  (memory-poisoning, "
                  f"{spec['n_same']}+{spec['n_cross']} {spec['direction']} entries)")

    skeptic_llm = _build_skeptic_llm(args.skeptic_llm)

    csv_path = out_dir / "results.csv"
    full_path = out_dir / "results_full.json"
    fields = ["defense", "attack", "seed_idx", "decision", "ordinal"]
    with csv_path.open("w", newline="") as f:
        csv.DictWriter(f, fieldnames=fields).writeheader()

    rows: list[dict] = []
    failures: list[dict] = []
    total = len(defenses) * len(attacks) * args.n_seeds
    counter = 0

    print(f"\nMatrix: {args.ticker} / {args.date}")
    print(f"  defenses = {defenses}  attacks = {attacks}  N seeds = {args.n_seeds}")
    print(f"  total trials = {total}")
    print(f"  out_dir = {out_dir.relative_to(ROOT)}\n")

    for defense in defenses:
        for attack in attacks:
            for seed_idx in range(args.n_seeds):
                counter += 1
                print(f"[{counter}/{total}] defense={defense:5s}  "
                      f"attack={attack:5s}  seed={seed_idx} ...")
                try:
                    _setup_defense(
                        defense, skeptic_llm,
                        d4_threshold=args.d4_threshold,
                        d4_backend=args.d4_backend,
                    )
                    try:
                        res = run_single(
                            args.ticker, args.date,
                            attack, seed_idx,
                            payloads[attack],
                            args.agent_llm,
                            out_dir,
                        )
                        # Tag the row with defense for matrix indexing
                        res["defense"] = defense
                        res["attack"] = attack
                    finally:
                        _teardown_defense(defense)
                except Exception as e:
                    err = {
                        "defense": defense, "attack": attack,
                        "seed_idx": seed_idx,
                        "error_type": type(e).__name__,
                        "error_msg": str(e)[:500],
                        "traceback": traceback.format_exc()[-2000:],
                    }
                    failures.append(err)
                    (out_dir / "failures.json").write_text(
                        json.dumps(failures, indent=2, ensure_ascii=False)
                    )
                    print(f"           FAILED: {err['error_type']}: "
                          f"{err['error_msg'][:120]}")
                    continue

                print(f"           decision = {res['decision']!r}  "
                      f"ordinal = {res['ordinal']}")
                rows.append(res)
                with csv_path.open("a", newline="") as f:
                    csv.DictWriter(f, fieldnames=fields).writerow({
                        "defense": defense, "attack": attack,
                        "seed_idx": seed_idx,
                        "decision": res["decision"],
                        "ordinal": res["ordinal"],
                    })
                full_path.write_text(
                    json.dumps(rows, indent=2, ensure_ascii=False)
                )

    print("\n" + "=" * 64)
    print("MATRIX DONE")
    print("=" * 64)
    print(f"  trials run: {counter}    failures: {len(failures)}")
    print(f"  csv      : {csv_path.relative_to(ROOT)}")
    print(f"  full     : {full_path.relative_to(ROOT)}")
    if failures:
        print(f"  failures : {(out_dir/'failures.json').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
