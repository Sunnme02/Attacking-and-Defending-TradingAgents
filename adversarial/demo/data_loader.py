"""Aggregate per-trial JSONs into a queryable in-memory store for the demo."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"

ATTACK_LABEL = {
    "clean": "None (clean)",
    "a1": "Fake News",
    "a2": "Cross-Channel",
    "a2v2": "Cross-Channel",
    "a5": "Memory Poisoning",
    "a5v2": "Memory Poisoning",
    "a2v2_a5v2": "Mixed (Cross-Channel + Memory)",
}

DEFENSE_LABEL = {
    "none": "None",
    "d3": "Provenance-Aware PM",
    "d3a": "Provenance-Aware PM (strict)",
    "d3b": "Provenance-Aware PM (lenient)",
    "d4": "Anomaly Filter",
    "d5": "Skeptic Agent",
}

DECISION_TIERS = ["StrongSell", "Underweight", "Hold", "Overweight", "StrongBuy"]
ORDINAL_TO_EXPOSURE = {1: -1.0, 2: -0.5, 3: 0.0, 4: 0.5, 5: 1.0}


@dataclass
class Trial:
    ticker: str
    date: str
    direction: str  # "bullish" | "bearish"
    attack: str  # canonical key (clean/a1/a2/a2v2/a5/a5v2/a2v2_a5v2)
    defense: str  # canonical key (none/d3/d3a/d3b/d4/d5)
    architecture: str  # "full" | "no_bb" | "no_risk" | "mem_to_analyst"
    seed_idx: int
    decision: str
    ordinal: int
    news_report: str = ""
    sentiment_report: str = ""
    investment_plan: str = ""
    final_trade_decision: str = ""
    source: str = ""  # subdir name for traceability


def _parse_dirname(name: str) -> dict[str, str]:
    """Parse a results subdir name into ticker/date/direction/architecture flags."""
    m = re.match(r"^([A-Z]+)_(\d{4}-\d{2}-\d{2})(.*)$", name)
    if not m:
        return {}
    ticker, date, suffix = m.groups()
    suffix = suffix.lstrip("_")

    direction = "bullish"
    architecture = "full"

    if suffix.startswith("bearish") or "_bearish" in name:
        direction = "bearish"
    if "arch_no_bb" in name:
        architecture = "no_bb"
    elif "arch_no_risk" in name:
        architecture = "no_risk"
    elif "arch_mem_to_analyst" in name:
        architecture = "mem_to_analyst"
    elif "arch_none" in name:
        architecture = "full"  # arch_none = baseline arch

    return {
        "ticker": ticker,
        "date": date,
        "direction": direction,
        "architecture": architecture,
        "suffix": suffix,
    }


def _is_excluded(name: str) -> bool:
    """Skip pilots, smoke tests, broken runs, k-variant."""
    excluded = ["smoke", "pilot", "broken", "qc-", "kvariant"]
    return any(x in name for x in excluded)


def _load_trials_from_file(path: Path, src_name: str, kind: str) -> list[Trial]:
    """Load all trials from a results_full.json file."""
    info = _parse_dirname(src_name)
    if not info:
        return []

    with open(path) as f:
        data = json.load(f)

    trials: list[Trial] = []
    for t in data:
        cond = t.get("condition", "clean")
        # campaign trials don't have explicit defense field; defaults to none
        defense = t.get("defense", "none")
        attack = t.get("attack", cond if cond != "clean" else "clean")
        # Defense matrix uses cond=clean for the no-attack baseline within a defense run
        if cond == "clean":
            attack = "clean"
        else:
            # In defense matrix, the 'attack' key is more authoritative
            attack = t.get("attack", cond)

        arch_raw = t.get("architecture_variant", info["architecture"])
        # "none" in arch_variant means "no ablation = baseline architecture"
        arch = "full" if arch_raw in (None, "none", "") else arch_raw
        trials.append(
            Trial(
                ticker=info["ticker"],
                date=info["date"],
                direction=info["direction"],
                attack=attack,
                defense=defense,
                architecture=arch,
                seed_idx=int(t.get("seed_idx", 0)),
                decision=t.get("decision", "Hold"),
                ordinal=int(t.get("ordinal", 3)),
                news_report=t.get("news_report", "") or "",
                sentiment_report=t.get("sentiment_report", "") or "",
                investment_plan=t.get("investment_plan", "") or "",
                final_trade_decision=t.get("final_trade_decision", "") or "",
                source=src_name,
            )
        )
    return trials


@lru_cache(maxsize=1)
def load_all_trials() -> list[Trial]:
    """Load every trial from campaign/ + defense_matrix/."""
    trials: list[Trial] = []

    for kind in ["campaign", "defense_matrix"]:
        root = RESULTS_ROOT / kind
        if not root.exists():
            continue
        for sub in sorted(os.listdir(root)):
            if _is_excluded(sub):
                continue
            f = root / sub / "results_full.json"
            if not f.exists():
                continue
            trials.extend(_load_trials_from_file(f, sub, kind))

    return trials


def get_tickers(direction: str = "bullish") -> list[str]:
    """Tickers with sufficient data for a given direction."""
    if direction == "bearish":
        return ["BIIB", "HOOD", "NVDA", "PLTR", "SNOW"]
    return ["BIIB", "HOOD", "NVDA", "PLTR", "SNOW"]


def get_available_attacks(ticker: str, direction: str) -> list[str]:
    """Attacks with data for this ticker+direction."""
    trials = load_all_trials()
    seen = {
        t.attack
        for t in trials
        if t.ticker == ticker and t.direction == direction and t.architecture == "full"
    }
    # Order: clean → a1 → a2/a2v2 → a5/a5v2 → mixed
    order = ["clean", "a1", "a2", "a2v2", "a5", "a5v2", "a2v2_a5v2"]
    return [a for a in order if a in seen]


def get_available_defenses(
    ticker: str, direction: str, attack: str
) -> list[str]:
    """Defenses with data for this ticker+direction+attack."""
    trials = load_all_trials()
    seen = {
        t.defense
        for t in trials
        if t.ticker == ticker
        and t.direction == direction
        and t.attack == attack
        and t.architecture == "full"
    }
    order = ["none", "d3", "d3a", "d3b", "d4", "d5"]
    return [d for d in order if d in seen]


def find_trials(
    ticker: str,
    direction: str,
    attack: str,
    defense: str = "none",
    architecture: str = "full",
) -> list[Trial]:
    """Return all matching trials, sorted by seed_idx."""
    trials = load_all_trials()
    matches = [
        t
        for t in trials
        if t.ticker == ticker
        and t.direction == direction
        and t.attack == attack
        and t.defense == defense
        and t.architecture == architecture
    ]
    return sorted(matches, key=lambda x: x.seed_idx)


def get_clean_baseline(ticker: str, direction: str) -> list[Trial]:
    """Clean baseline trials for diff comparison."""
    return find_trials(ticker, direction, "clean", "none")


def aggregate_ordinal(trials: list[Trial]) -> dict[str, Any]:
    """Compute mean/n/decision-distribution across a list of trials."""
    if not trials:
        return {"n": 0, "mean": None, "distribution": {}}
    ordinals = [t.ordinal for t in trials]
    mean = sum(ordinals) / len(ordinals)
    dist: dict[str, int] = {}
    for t in trials:
        dist[t.decision] = dist.get(t.decision, 0) + 1
    return {
        "n": len(trials),
        "mean": mean,
        "distribution": dist,
        "ordinals": ordinals,
    }


if __name__ == "__main__":
    # Quick smoke test
    trials = load_all_trials()
    print(f"Loaded {len(trials)} trials total.")
    print(f"Tickers: {sorted({t.ticker for t in trials})}")
    print(f"Directions: {sorted({t.direction for t in trials})}")
    print(f"Attacks: {sorted({t.attack for t in trials})}")
    print(f"Defenses: {sorted({t.defense for t in trials})}")
    print(f"Architectures: {sorted({t.architecture for t in trials})}")

    # Sanity: PLTR bullish defense lookup
    for combo in [
        ("PLTR", "bullish", "clean", "none"),
        ("PLTR", "bullish", "a2v2", "none"),
        ("PLTR", "bullish", "a2v2", "d3"),
        ("PLTR", "bullish", "a2v2", "d5"),
        ("PLTR", "bullish", "a5v2", "none"),
        ("PLTR", "bullish", "a2v2_a5v2", "d5"),
        ("PLTR", "bearish", "a5v2", "d3"),
        ("HOOD", "bullish", "a2v2", "d3"),
        ("SNOW", "bullish", "a2v2_a5v2", "d3"),
    ]:
        sample = find_trials(*combo)
        agg = aggregate_ordinal(sample)
        ticker, dir_, atk, dfn = combo
        mean_str = f"{agg['mean']:.2f}" if agg["mean"] is not None else "n/a"
        print(f"  {ticker:5s} {dir_:8s} {atk:11s} {dfn:5s}: n={agg['n']}, mean={mean_str}")
