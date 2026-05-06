"""
Hierarchical bootstrap + multiple-comparison correction — addresses
reviewer concern that 5 ticker × 10 seeds = 50 trials is NOT 50
independent samples (seeds within a ticker share the same payload, news
context, and market window).

Design:
  - Independence unit: ticker (the cluster). Within a cluster, seeds are
    correlated; across clusters they are not.
  - For payload-variance ablation runs (K>1) the cluster is
    (ticker, payload_variant); we treat variant as a sub-cluster but
    bootstrap at the outer ticker level (more conservative).
  - Effect size: cross-ticker mean difference, reported with bootstrap
    95 % CI from B = 10000 cluster-level resamples.
  - Multiple comparisons: Benjamini-Hochberg adjustment on the
    bootstrap-derived two-sided p-values across the test family
    (3 attack effects + 6 defense effects = 9 tests).

This script does NOT need any LLM compute — it reads existing
``results_full.json`` files and produces:

  results/stats_hierarchical.csv          — flat table for paper
  printed paper-ready summary
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_DIR = ROOT / "adversarial" / "results" / "campaign"
DEFMAT_DIR = ROOT / "adversarial" / "results" / "defense_matrix"

B_BOOT = 10000        # bootstrap iterations
SEED = 1337


def _load_results(path: Path) -> list[dict]:
    full = path / "results_full.json"
    if not full.exists():
        return []
    return json.loads(full.read_text())


def _ticker_date(name: str, suffix: str) -> tuple[str, str]:
    base = name[:-len(suffix)] if suffix and name.endswith(suffix) else name
    parts = base.split("_", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def _gather_campaign(suffix: str, direction: str) -> dict[str, dict[str, list[int]]]:
    """For each ticker, return {condition: list_of_ordinals} from the
    campaign directory matching ``suffix``."""
    out: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for d in sorted(d for d in CAMPAIGN_DIR.iterdir() if d.is_dir()):
        if "_smoke" in d.name or "__" in d.name:
            continue
        # Match exactly the suffix (e.g. "_v2", "_bearish", "" for v1)
        if suffix:
            if not d.name.endswith(suffix):
                continue
        else:
            # v1 = no special suffix at all
            EXCLUDED_SUFFIXES = (
                "_v2", "_bearish", "_kvariant",
                "_v2_smoke", "_v2_combo_smoke",
                "_arch_none", "_arch_no_bb", "_arch_no_risk", "_arch_mem_to_analyst",
                "_arch_smoke",
            )
            if any(d.name.endswith(s) for s in EXCLUDED_SUFFIXES):
                continue

        ticker, date = _ticker_date(d.name, suffix)
        rows = _load_results(d)
        for r in rows:
            ord_ = r.get("ordinal")
            if ord_ is None:
                continue
            out[ticker][r["condition"]].append(int(ord_))
    return out


def _gather_defmat() -> dict[str, dict[tuple[str, str], list[int]]]:
    """For each ticker, return {(defense, attack): list_of_ordinals}."""
    out: dict[str, dict[tuple[str, str], list[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    if not DEFMAT_DIR.exists():
        return out
    for d in sorted(d for d in DEFMAT_DIR.iterdir() if d.is_dir()):
        suf = "_v2attacks_bullish"
        if not d.name.endswith(suf):
            continue
        ticker, _ = _ticker_date(d.name, suf)
        rows = _load_results(d)
        for r in rows:
            ord_ = r.get("ordinal")
            if ord_ is None:
                continue
            out[ticker][(r["defense"], r["attack"])].append(int(ord_))
    return out


def _bootstrap_cluster(
    paired_means: list[tuple[float, float]],
    rng: random.Random,
    B: int = B_BOOT,
) -> list[float]:
    """Cluster bootstrap of (mean_A - mean_B) deltas.

    ``paired_means`` is one (mean_A, mean_B) tuple per cluster. Each
    bootstrap iteration resamples clusters with replacement, then takes
    the mean of (A_i - B_i) across resampled clusters.
    """
    n = len(paired_means)
    if n == 0:
        return []
    deltas = []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        diff = sum(paired_means[i][0] - paired_means[i][1] for i in idx) / n
        deltas.append(diff)
    return deltas


def _ci(boots: list[float], alpha: float = 0.05) -> tuple[float, float]:
    if not boots:
        return float("nan"), float("nan")
    s = sorted(boots)
    lo = s[int(alpha / 2 * len(s))]
    hi = s[int((1 - alpha / 2) * len(s)) - 1]
    return lo, hi


def _two_sided_p(boots: list[float], null: float = 0.0) -> float:
    """Two-sided bootstrap p-value testing H0: effect = null."""
    if not boots:
        return float("nan")
    n = len(boots)
    p_left = sum(1 for b in boots if b <= null) / n
    p_right = sum(1 for b in boots if b >= null) / n
    return 2 * min(p_left, p_right)


def _bh_correct(pvals: list[float]) -> list[float]:
    """Benjamini-Hochberg adjusted p-values."""
    n = len(pvals)
    order = sorted(range(n), key=lambda i: pvals[i])
    adj = [0.0] * n
    prev = 1.0
    for rank_i, idx in enumerate(reversed(order)):
        rank = n - rank_i
        raw = pvals[idx] * n / rank
        adj_val = min(raw, prev)
        adj[idx] = adj_val
        prev = adj_val
    return adj


def _mean(xs: Iterable[int | float]) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def report_cross_ticker_attack(
    bullish_v2: dict[str, dict[str, list[int]]],
    rng: random.Random,
) -> list[dict]:
    """For each non-clean condition, compute cross-ticker mean Δ vs clean
    with cluster-bootstrap CI and BH-corrected p-value."""
    rows: list[dict] = []
    conditions = sorted({
        c for ticker_data in bullish_v2.values() for c in ticker_data
        if c != "clean"
    })
    pvals: list[float] = []
    for cond in conditions:
        paired = []
        for ticker, by_cond in sorted(bullish_v2.items()):
            if cond not in by_cond or "clean" not in by_cond:
                continue
            paired.append((_mean(by_cond[cond]), _mean(by_cond["clean"])))
        if not paired:
            continue
        boots = _bootstrap_cluster(paired, rng)
        delta = sum(a - b for a, b in paired) / len(paired)
        lo, hi = _ci(boots)
        p = _two_sided_p(boots)
        pvals.append(p)
        rows.append({
            "test_family": "attack_effect",
            "comparison": f"{cond} vs clean",
            "n_clusters": len(paired),
            "delta": delta,
            "ci_lo": lo,
            "ci_hi": hi,
            "p_raw": p,
        })

    # BH correction
    if pvals:
        adj = _bh_correct(pvals)
        for r, p_a in zip(rows, adj):
            r["p_bh"] = p_a
    return rows


def report_defense_effects(
    defmat: dict[str, dict[tuple[str, str], list[int]]],
    rng: random.Random,
) -> list[dict]:
    """For each (defense != none, attack != clean), compute
    cross-ticker effect size mean(none, attack) - mean(defense, attack)
    (positive ⇒ defense reduces attack-aligned ordinal)."""
    rows: list[dict] = []
    pvals: list[float] = []
    attacks = sorted({a for v in defmat.values() for (_, a) in v if a != "clean"})
    defenses = sorted({d for v in defmat.values() for (d, _) in v if d != "none"})

    for atk in attacks:
        for de in defenses:
            paired = []
            for ticker, cells in sorted(defmat.items()):
                none_vals = cells.get(("none", atk), [])
                def_vals = cells.get((de, atk), [])
                if not none_vals or not def_vals:
                    continue
                # Effect size from the perspective of the defender:
                # positive = defense reduced ordinal (assuming bullish atk)
                paired.append((_mean(none_vals), _mean(def_vals)))
            if not paired:
                continue
            boots = _bootstrap_cluster(paired, rng)
            delta = sum(a - b for a, b in paired) / len(paired)
            lo, hi = _ci(boots)
            p = _two_sided_p(boots)
            pvals.append(p)
            rows.append({
                "test_family": "defense_effect",
                "comparison": f"none-{de} | attack={atk}",
                "n_clusters": len(paired),
                "delta": delta,
                "ci_lo": lo,
                "ci_hi": hi,
                "p_raw": p,
            })

    if pvals:
        adj = _bh_correct(pvals)
        for r, p_a in zip(rows, adj):
            r["p_bh"] = p_a
    return rows


def main() -> None:
    rng = random.Random(SEED)

    # Gather data
    bullish_v1 = _gather_campaign("", "bullish")
    bullish_v2 = _gather_campaign("_v2", "bullish")
    bearish    = _gather_campaign("_bearish", "bearish")
    defmat     = _gather_defmat()

    print(f"Loaded:")
    print(f"  v1 bullish: {len(bullish_v1)} tickers")
    print(f"  v2 bullish: {len(bullish_v2)} tickers")
    print(f"  bearish:    {len(bearish)} tickers")
    print(f"  defmat:     {len(defmat)} tickers")
    print()

    # Cross-ticker attack effect (bullish v1)
    v1_rows = report_cross_ticker_attack(bullish_v1, rng)
    for r in v1_rows:
        r["test_family"] = "attack_effect_v1"
    # Cross-ticker attack effect (bullish v2)
    attack_rows = report_cross_ticker_attack(bullish_v2, rng)
    # Cross-ticker bearish attack effect
    bearish_rows = []
    for r in report_cross_ticker_attack(bearish, rng):
        r["test_family"] = "attack_effect_bearish"
        # In bearish runs we measure the attacker pushing ordinal DOWN, so
        # a "successful" attack is delta < 0. Keep raw delta but document.
        bearish_rows.append(r)
    # Defense effects
    defense_rows = report_defense_effects(defmat, rng)

    all_rows = v1_rows + attack_rows + bearish_rows + defense_rows

    # Write CSV
    out_path = ROOT / "adversarial" / "results" / "stats_hierarchical.csv"
    fieldnames = [
        "test_family", "comparison", "n_clusters",
        "delta", "ci_lo", "ci_hi", "p_raw", "p_bh",
    ]
    with out_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in all_rows:
            for k in ("delta", "ci_lo", "ci_hi", "p_raw", "p_bh"):
                if k in r and isinstance(r[k], float):
                    r[k] = round(r[k], 4)
            w.writerow({k: r.get(k, "") for k in fieldnames})

    print(f"Wrote {out_path.relative_to(ROOT)}  ({len(all_rows)} rows)")
    print()

    # Print paper-ready tables
    print("=" * 90)
    print("Table A0 — Cross-ticker attack effect (bullish V1 batch, B=10000 cluster bootstrap)")
    print("=" * 90)
    print(f"  {'comparison':25s}  {'n':>3s}  {'Δ':>7s}  "
          f"{'95% CI':>17s}  {'p_raw':>8s}  {'p_BH':>8s}  sig?")
    print("  " + "-" * 80)
    for r in v1_rows:
        sig = "*" if r["p_bh"] < 0.05 else (".") if r["p_bh"] < 0.10 else ""
        print(f"  {r['comparison']:25s}  {r['n_clusters']:>3d}  "
              f"{r['delta']:>+7.3f}  [{r['ci_lo']:>+6.3f},{r['ci_hi']:>+6.3f}]  "
              f"{r['p_raw']:>8.4f}  {r['p_bh']:>8.4f}  {sig}")

    print()
    print("=" * 90)
    print("Table A — Cross-ticker attack effect (bullish V2 batch, B=10000 cluster bootstrap)")
    print("=" * 90)
    print(f"  {'comparison':25s}  {'n':>3s}  {'Δ':>7s}  "
          f"{'95% CI':>17s}  {'p_raw':>8s}  {'p_BH':>8s}  sig?")
    print("  " + "-" * 80)
    for r in attack_rows:
        sig = "*" if r["p_bh"] < 0.05 else (".") if r["p_bh"] < 0.10 else ""
        print(f"  {r['comparison']:25s}  {r['n_clusters']:>3d}  "
              f"{r['delta']:>+7.3f}  [{r['ci_lo']:>+6.3f},{r['ci_hi']:>+6.3f}]  "
              f"{r['p_raw']:>8.4f}  {r['p_bh']:>8.4f}  {sig}")

    print()
    print("=" * 90)
    print("Table B — Cross-ticker BEARISH attack effect (negative Δ = attack worked)")
    print("=" * 90)
    print(f"  {'comparison':25s}  {'n':>3s}  {'Δ':>7s}  "
          f"{'95% CI':>17s}  {'p_raw':>8s}  {'p_BH':>8s}  sig?")
    print("  " + "-" * 80)
    for r in bearish_rows:
        sig = "*" if r["p_bh"] < 0.05 else (".") if r["p_bh"] < 0.10 else ""
        print(f"  {r['comparison']:25s}  {r['n_clusters']:>3d}  "
              f"{r['delta']:>+7.3f}  [{r['ci_lo']:>+6.3f},{r['ci_hi']:>+6.3f}]  "
              f"{r['p_raw']:>8.4f}  {r['p_bh']:>8.4f}  {sig}")

    print()
    print("=" * 90)
    print("Table C — Defense effect (positive Δ = defense reduced attack-aligned ordinal)")
    print("=" * 90)
    print(f"  {'comparison':30s}  {'n':>3s}  {'Δ':>7s}  "
          f"{'95% CI':>17s}  {'p_raw':>8s}  {'p_BH':>8s}  sig?")
    print("  " + "-" * 80)
    for r in defense_rows:
        sig = "*" if r["p_bh"] < 0.05 else (".") if r["p_bh"] < 0.10 else ""
        print(f"  {r['comparison']:30s}  {r['n_clusters']:>3d}  "
              f"{r['delta']:>+7.3f}  [{r['ci_lo']:>+6.3f},{r['ci_hi']:>+6.3f}]  "
              f"{r['p_raw']:>8.4f}  {r['p_bh']:>8.4f}  {sig}")

    print()
    print("Significance: * = p_BH < 0.05,  . = p_BH < 0.10")
    print(f"BH correction applied within each test family.")
    print(f"n_clusters = number of tickers used in the cross-ticker effect.")


if __name__ == "__main__":
    main()
