"""
Cross-ticker paper-figure aggregator.

Produces paper-ready master tables (CSV) and an ASCII forest plot for
quick visual inspection. Reads from every results directory we generated
(campaign + defense_matrix + stealth + absorption-augmented) and
synthesises four output files:

  1. paper_attack_effects.csv
       Per-ticker × per-attack effect sizes (mean, CI) + cross-ticker
       random-effects-style summary, for both bullish and bearish runs.
       This drives the forest plot in §Results.

  2. paper_defense_effects.csv
       Per-ticker × per-defense × per-attack effect sizes (defense
       reduction Δ vs none) with bootstrap CI; this drives the
       defense-effectiveness table.

  3. paper_stealth_summary.csv
       Cross-attack stealth comparison (lexical / FinBERT means + per-
       ticker breakdown). Cross-references the stealth_report.json.

  4. paper_arch_ablation.csv
       Architecture ablation summary (4 variants × {a5v2, a2v2_a5v2}
       on PLTR), the mechanism evidence for §Finding 1.

In addition prints an ASCII forest plot to stdout — quick check whether
defense effects are tight CI exclude-zero across tickers.

Bootstrap: cluster-resample by ticker for cross-ticker effects (matches
``stats_hierarchical.py``). B = 5000 iterations (less than stats's 10000
to keep aggregation fast; statistically still tight on these sample
sizes).

No LLM compute. Pure data aggregation.
"""

from __future__ import annotations

import csv
import json
import random
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_DIR = ROOT / "adversarial" / "results" / "campaign"
DEFMAT_DIR = ROOT / "adversarial" / "results" / "defense_matrix"
RESULTS_DIR = ROOT / "adversarial" / "results"
STEALTH_REPORT = ROOT / "adversarial" / "data" / "stealth_report.json"

B_BOOT = 5000
SEED = 1337


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────

def _load(path: Path) -> list[dict]:
    full = path / "results_full.json"
    if not full.exists():
        return []
    return json.loads(full.read_text())


def _bootstrap_cluster(
    paired: list[tuple[float, float]],
    rng: random.Random,
    B: int = B_BOOT,
) -> tuple[float, float, float]:
    """Cluster-bootstrap the mean (a-b) where each cluster is one ticker.
    Returns (delta, ci_lo, ci_hi)."""
    n = len(paired)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    delta = sum(a - b for a, b in paired) / n
    if n == 1:
        return delta, delta, delta
    boots = []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        diff = sum(paired[i][0] - paired[i][1] for i in idx) / n
        boots.append(diff)
    boots.sort()
    lo = boots[int(0.025 * len(boots))]
    hi = boots[int(0.975 * len(boots)) - 1]
    return delta, lo, hi


def _ticker_date(name: str, suffix: str) -> tuple[str, str]:
    base = name[:-len(suffix)] if suffix and name.endswith(suffix) else name
    parts = base.split("_", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


# Per-attack mapping to a paper-facing display name
ATTACK_DISPLAY = {
    "clean": "Clean",
    "a1": "Fake News",
    "a2": "Single-Channel Pump (v1)",
    "a5": "Generic Memory (v1)",
    "a2v2": "Cross-Channel Coord.",
    "a5v2": "Pattern-Matched Memory",
    "a2v2_a5v2": "Mixed Attack",
}

DEFENSE_DISPLAY = {
    "none": "None (baseline)",
    "d3": "D3 Provenance (full)",
    "d3a": "D3a Citation-only",
    "d3b": "D3b Indep.-Source",
    "d4": "D4 Anomaly Filter",
    "d5": "D5 Skeptic",
}


# ─────────────────────────────────────────────────────────────────────────
# Section 1 — Per-ticker attack effects (drives forest plot)
# ─────────────────────────────────────────────────────────────────────────

CAMPAIGN_EXCLUDE_SUFFIXES = (
    "_smoke", "_v2_smoke", "_v2_combo_smoke", "_arch_smoke",
    "_arch_none", "_arch_no_bb", "_arch_no_risk", "_arch_mem_to_analyst",
    "_kvariant",
)


def _gather_attack_effects(rng: random.Random) -> list[dict]:
    """For each (batch_type, direction, ticker, attack), compute:
       - per-ticker mean ordinal
       - within-ticker bootstrap CI (resample seeds)
       - then cross-ticker cluster-bootstrap of mean Δ vs clean.

    Output rows are emitted at TWO levels:
       level='ticker'  (one row per ticker × attack)
       level='cross'   (one row per attack, aggregated across tickers)
    """
    rows: list[dict] = []
    # group by (batch_label, direction): collect per-ticker {cond: [ords]}
    batches: dict[tuple, dict[str, dict[str, list[int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )

    for d in sorted(p for p in CAMPAIGN_DIR.iterdir() if p.is_dir()):
        # Skip obvious non-batch dirs
        if any(s in d.name for s in ("__",)):
            continue
        if d.name.endswith(tuple(CAMPAIGN_EXCLUDE_SUFFIXES)):
            continue

        # Identify batch type
        if d.name.endswith("_v2"):
            batch_label, direction = "v2_bullish", "bullish"
            ticker, date = _ticker_date(d.name, "_v2")
        elif d.name.endswith("_bearish"):
            batch_label, direction = "bearish", "bearish"
            ticker, date = _ticker_date(d.name, "_bearish")
        else:
            batch_label, direction = "v1_bullish", "bullish"
            ticker, date = _ticker_date(d.name, "")

        for r in _load(d):
            ord_ = r.get("ordinal")
            if ord_ is None:
                continue
            batches[(batch_label, direction)][ticker][r["condition"]].append(int(ord_))

    # Compute per-ticker × per-attack rows + cross-ticker aggregates
    for (batch_label, direction), per_ticker in batches.items():
        # Per-ticker rows
        per_attack_pairs: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for ticker, cond_map in sorted(per_ticker.items()):
            clean_ords = cond_map.get("clean", [])
            if not clean_ords:
                continue
            clean_mean = statistics.mean(clean_ords)
            for cond, ords in cond_map.items():
                if cond == "clean":
                    continue
                if not ords:
                    continue
                m = statistics.mean(ords)
                rows.append({
                    "level": "ticker",
                    "batch": batch_label,
                    "direction": direction,
                    "ticker": ticker,
                    "attack": cond,
                    "n": len(ords),
                    "mean_attacked": round(m, 3),
                    "mean_clean": round(clean_mean, 3),
                    "delta": round(m - clean_mean, 3),
                    "ci_lo": "",
                    "ci_hi": "",
                })
                per_attack_pairs[cond].append((m, clean_mean))

        # Cross-ticker rows
        for cond, paired in per_attack_pairs.items():
            d_, lo, hi = _bootstrap_cluster(paired, rng)
            rows.append({
                "level": "cross",
                "batch": batch_label,
                "direction": direction,
                "ticker": "ALL",
                "attack": cond,
                "n": len(paired),
                "mean_attacked": "",
                "mean_clean": "",
                "delta": round(d_, 3),
                "ci_lo": round(lo, 3),
                "ci_hi": round(hi, 3),
            })

    return rows


# ─────────────────────────────────────────────────────────────────────────
# Section 2 — Defense effects (per-ticker + cross-ticker)
# ─────────────────────────────────────────────────────────────────────────

def _gather_defense_effects(rng: random.Random) -> list[dict]:
    """For each (matrix-suffix-group, ticker, defense, attack) compute the
    defense effect = mean(none, attack) - mean(defense, attack). Positive
    delta = defense reduced attack-aligned ordinal."""
    rows: list[dict] = []
    if not DEFMAT_DIR.exists():
        return rows

    # group dirs by suffix so v2attacks_bullish and d3_variants and d4_eval
    # each form their own coherent matrix
    by_suffix: dict[str, dict[str, dict[tuple[str, str], list[int]]]] = (
        defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    )
    for d in sorted(p for p in DEFMAT_DIR.iterdir() if p.is_dir()):
        # Identify suffix
        for suf in ("_v2attacks_bullish", "_v2attacks_bearish",
                    "_d3_variants", "_d4_eval", "_d4_finbert",
                    "_bearish_d3", "_bearish_d5",
                    "_v1attacks_bullish"):
            if d.name.endswith(suf):
                ticker, _ = _ticker_date(d.name, suf)
                for r in _load(d):
                    ord_ = r.get("ordinal")
                    if ord_ is None:
                        continue
                    by_suffix[suf][ticker][(r["defense"], r["attack"])].append(int(ord_))
                break

    # ─── Synthetic merged matrix: combine bearish_d3 + bearish_d5 so D3
    # and D5 can be compared against the same `none` baseline for paper.
    if "_bearish_d3" in by_suffix and "_bearish_d5" in by_suffix:
        merged: dict[str, dict[tuple[str, str], list[int]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for src_suf in ("_bearish_d3", "_bearish_d5"):
            for ticker, cells in by_suffix[src_suf].items():
                for (de, atk), ords in cells.items():
                    merged[ticker][(de, atk)].extend(ords)
        by_suffix["_bearish_merged"] = merged

    for suf, by_ticker in by_suffix.items():
        # Per-ticker rows
        all_attacks = sorted({a for tkr in by_ticker.values() for (_, a) in tkr})
        all_defenses = sorted({de for tkr in by_ticker.values() for (de, _) in tkr})
        per_pair: dict[tuple[str, str], list[tuple[float, float]]] = defaultdict(list)
        # _d3_variants lacks an internal `none` baseline. Pull from
        # _v2attacks_bullish per-ticker so we can compute D3a/D3b Δ.
        external_baseline: dict[str, dict[tuple[str, str], list[int]]] | None = None
        if suf == "_d3_variants":
            external_baseline = by_suffix.get("_v2attacks_bullish")
        for ticker, cells in sorted(by_ticker.items()):
            for atk in all_attacks:
                if atk == "clean":
                    continue
                none_ords = cells.get(("none", atk), [])
                if not none_ords and external_baseline is not None:
                    ext_cells = external_baseline.get(ticker, {})
                    none_ords = ext_cells.get(("none", atk), [])
                if not none_ords:
                    continue
                none_mean = statistics.mean(none_ords)
                for de in all_defenses:
                    if de == "none":
                        continue
                    def_ords = cells.get((de, atk), [])
                    if not def_ords:
                        continue
                    def_mean = statistics.mean(def_ords)
                    rows.append({
                        "level": "ticker",
                        "matrix": suf,
                        "ticker": ticker,
                        "defense": de,
                        "attack": atk,
                        "n_def": len(def_ords),
                        "n_none": len(none_ords),
                        "mean_none": round(none_mean, 3),
                        "mean_def": round(def_mean, 3),
                        "delta": round(none_mean - def_mean, 3),
                        "ci_lo": "",
                        "ci_hi": "",
                    })
                    per_pair[(de, atk)].append((none_mean, def_mean))

        for (de, atk), paired in per_pair.items():
            d_, lo, hi = _bootstrap_cluster(paired, rng)
            rows.append({
                "level": "cross",
                "matrix": suf,
                "ticker": "ALL",
                "defense": de,
                "attack": atk,
                "n_def": "",
                "n_none": len(paired),
                "mean_none": "",
                "mean_def": "",
                "delta": round(d_, 3),
                "ci_lo": round(lo, 3),
                "ci_hi": round(hi, 3),
            })

    return rows


# ─────────────────────────────────────────────────────────────────────────
# Section 3 — Stealth summary
# ─────────────────────────────────────────────────────────────────────────

def _gather_stealth() -> list[dict]:
    if not STEALTH_REPORT.exists():
        return []
    report = json.loads(STEALTH_REPORT.read_text())
    rows: list[dict] = []
    for atk, entries in report.items():
        if not entries:
            continue
        for r in entries:
            rows.append({
                "attack": atk,
                "ticker": r.get("ticker"),
                "date": r.get("date"),
                "case_id_or_dir": (
                    r.get("case_id") or r.get("direction") or "atlas"
                ),
                "lexical": r.get("stealth_score_lexical"),
                "js_bigram": r.get("js_bigram"),
                "finbert": r.get("stealth_score_finbert"),
                "verdict": r.get("verdict"),
            })
    return rows


# ─────────────────────────────────────────────────────────────────────────
# Section 4 — Architecture ablation summary
# ─────────────────────────────────────────────────────────────────────────

ARCH_VARIANTS = ["none", "no_bb", "no_risk", "mem_to_analyst"]


def _gather_arch_ablation() -> list[dict]:
    rows: list[dict] = []
    for variant in ARCH_VARIANTS:
        suffix = f"_arch_{variant}"
        for d in sorted(p for p in CAMPAIGN_DIR.iterdir() if p.is_dir()):
            if not d.name.endswith(suffix):
                continue
            ticker, date = _ticker_date(d.name, suffix)
            data = _load(d)
            if not data:
                continue
            by_cond: dict[str, list[int]] = defaultdict(list)
            for r in data:
                ord_ = r.get("ordinal")
                if ord_ is None:
                    continue
                by_cond[r["condition"]].append(int(ord_))
            clean = by_cond.get("clean", [])
            clean_mean = statistics.mean(clean) if clean else None
            for cond, ords in by_cond.items():
                m = statistics.mean(ords)
                row = {
                    "variant": variant,
                    "ticker": ticker,
                    "date": date,
                    "condition": cond,
                    "n": len(ords),
                    "mean": round(m, 3),
                    "delta_vs_clean": (
                        round(m - clean_mean, 3) if clean_mean is not None else ""
                    ),
                }
                rows.append(row)
    return rows


# ─────────────────────────────────────────────────────────────────────────
# ASCII forest plot
# ─────────────────────────────────────────────────────────────────────────

def _ascii_forest(
    rows: list[dict], *, level: str, batch: str | None = None,
    width: int = 50, x_lo: float = -1.0, x_hi: float = 1.0,
) -> None:
    """Print a single ASCII forest plot for the cross-ticker rows of a
    given batch (e.g. v2_bullish, bearish)."""
    selected = [
        r for r in rows
        if r["level"] == level and (batch is None or r.get("batch") == batch)
    ]
    if not selected:
        print("  (no data)")
        return

    def map_x(x: float) -> int:
        x = max(x_lo, min(x_hi, x))
        return int((x - x_lo) / (x_hi - x_lo) * width)

    zero_col = map_x(0.0)
    print(f"  {'attack':28s} {'Δ':>7s} {'95% CI':>17s}  "
          f"{x_lo:+.1f}{' ' * (width - 8)}{x_hi:+.1f}")
    for r in sorted(selected, key=lambda r: r["attack"]):
        atk = r.get("attack", "?")
        d = r["delta"]
        lo = r.get("ci_lo", "")
        hi = r.get("ci_hi", "")
        line = [" "] * (width + 1)
        line[zero_col] = "|"
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)):
            l_col = map_x(lo)
            h_col = map_x(hi)
            for c in range(min(l_col, h_col), max(l_col, h_col) + 1):
                line[c] = "─"
            line[map_x(d)] = "●"
        else:
            line[map_x(d)] = "●"
        ci_s = (
            f"[{lo:+.2f},{hi:+.2f}]"
            if isinstance(lo, (int, float)) and isinstance(hi, (int, float))
            else ""
        )
        atk_disp = ATTACK_DISPLAY.get(atk, atk)
        print(f"  {atk_disp:28s} {d:>+7.2f} {ci_s:>17s}  {''.join(line)}")


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

def main() -> None:
    rng = random.Random(SEED)

    attack_rows = _gather_attack_effects(rng)
    defense_rows = _gather_defense_effects(rng)
    stealth_rows = _gather_stealth()
    arch_rows = _gather_arch_ablation()

    # Write CSVs
    out_dir = RESULTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Attack effects
    with (out_dir / "paper_attack_effects.csv").open("w", newline="") as f:
        if attack_rows:
            w = csv.DictWriter(f, fieldnames=list(attack_rows[0].keys()))
            w.writeheader()
            w.writerows(attack_rows)

    # 2. Defense effects
    with (out_dir / "paper_defense_effects.csv").open("w", newline="") as f:
        if defense_rows:
            w = csv.DictWriter(f, fieldnames=list(defense_rows[0].keys()))
            w.writeheader()
            w.writerows(defense_rows)

    # 3. Stealth
    with (out_dir / "paper_stealth_summary.csv").open("w", newline="") as f:
        if stealth_rows:
            w = csv.DictWriter(f, fieldnames=list(stealth_rows[0].keys()))
            w.writeheader()
            w.writerows(stealth_rows)

    # 4. Architecture ablation
    with (out_dir / "paper_arch_ablation.csv").open("w", newline="") as f:
        if arch_rows:
            w = csv.DictWriter(f, fieldnames=list(arch_rows[0].keys()))
            w.writeheader()
            w.writerows(arch_rows)

    print(f"Wrote 4 paper-ready CSVs to {out_dir.relative_to(ROOT)}/")
    for name in (
        "paper_attack_effects.csv",
        "paper_defense_effects.csv",
        "paper_stealth_summary.csv",
        "paper_arch_ablation.csv",
    ):
        path = out_dir / name
        n_lines = path.read_text().count("\n") - 1 if path.exists() else 0
        print(f"  {name:35s}  ({n_lines} rows)")
    print()

    # ────────── ASCII forest plots ──────────
    print("=" * 80)
    print("Forest plot — cross-ticker bullish v2 attack effects vs clean")
    print("=" * 80)
    _ascii_forest(attack_rows, level="cross", batch="v2_bullish")

    print()
    print("=" * 80)
    print("Forest plot — cross-ticker bearish attack effects vs clean")
    print("  (negative Δ = attack succeeded in pushing ordinal down)")
    print("=" * 80)
    _ascii_forest(attack_rows, level="cross", batch="bearish")

    print()
    print("=" * 80)
    print("Forest plot — cross-ticker v1 bullish attack effects vs clean")
    print("=" * 80)
    _ascii_forest(attack_rows, level="cross", batch="v1_bullish")

    print()
    print("=" * 80)
    print("Defense effects (cross-ticker, V2attacks bullish defense matrix)")
    print("  Positive Δ = defense reduced attacker-aligned ordinal")
    print("=" * 80)
    selected = [
        r for r in defense_rows
        if r["level"] == "cross" and r.get("matrix") == "_v2attacks_bullish"
    ]
    if not selected:
        print("  (no data)")
    else:
        print(f"  {'defense × attack':38s} {'Δ':>7s} {'95% CI':>17s}  -1.0{' '*42}+1.0")
        zero_col = 25
        width = 50
        for r in sorted(selected, key=lambda r: (r["defense"], r["attack"])):
            de = DEFENSE_DISPLAY.get(r["defense"], r["defense"])
            atk = ATTACK_DISPLAY.get(r["attack"], r["attack"])
            label = f"{de} | {atk}"[:38]
            d = r["delta"]
            lo = r["ci_lo"]
            hi = r["ci_hi"]

            def map_x(x: float) -> int:
                x = max(-1.0, min(1.0, x))
                return int((x + 1.0) / 2.0 * width)

            line = [" "] * (width + 1)
            line[map_x(0.0)] = "|"
            if isinstance(lo, (int, float)):
                l_col = map_x(lo)
                h_col = map_x(hi)
                for c in range(min(l_col, h_col), max(l_col, h_col) + 1):
                    line[c] = "─"
                line[map_x(d)] = "●"
            ci_s = f"[{lo:+.2f},{hi:+.2f}]" if isinstance(lo, (int, float)) else ""
            print(f"  {label:38s} {d:>+7.2f} {ci_s:>17s}  {''.join(line)}")

    print()
    print("=" * 80)
    print("Architecture ablation — A5v2 / mixed Δ under each variant (PLTR N=5)")
    print("=" * 80)
    by_variant: dict[str, dict[str, float]] = defaultdict(dict)
    for r in arch_rows:
        if r["ticker"] != "PLTR":
            continue
        if r["delta_vs_clean"] != "":
            by_variant[r["variant"]][r["condition"]] = r["delta_vs_clean"]
    print(f"  {'variant':18s} {'a5v2 Δ':>9s} {'a2v2_a5v2 Δ':>13s}")
    for v in ARCH_VARIANTS:
        cells = by_variant.get(v, {})
        a5v2 = cells.get("a5v2", "—")
        combo = cells.get("a2v2_a5v2", "—")
        a5v2_s = f"{a5v2:+.2f}" if isinstance(a5v2, (int, float)) else str(a5v2)
        combo_s = f"{combo:+.2f}" if isinstance(combo, (int, float)) else str(combo)
        print(f"  {v:18s} {a5v2_s:>9s} {combo_s:>13s}")

    print()
    print("=" * 80)
    print("Stealth — cross-attack mean comparison")
    print("=" * 80)
    by_atk: dict[str, list[dict]] = defaultdict(list)
    for r in stealth_rows:
        by_atk[r["attack"]].append(r)
    print(f"  {'attack':10s} {'n':>3s}  {'lex':>7s}  {'finbert':>8s}  {'verdict mix':30s}")
    for atk in ("a1", "a2", "a2v2"):
        rows = by_atk.get(atk, [])
        if not rows:
            continue
        lex = [r["lexical"] for r in rows if r["lexical"] is not None]
        fb = [r["finbert"] for r in rows if r["finbert"] is not None]
        verdicts = sorted(set(r["verdict"] for r in rows if r.get("verdict")))
        lex_m = f"{statistics.mean(lex):.3f}" if lex else "—"
        fb_m = f"{statistics.mean(fb):.3f}" if fb else "—"
        v_str = "/".join(verdicts)[:30]
        print(f"  {atk:10s} {len(rows):>3d}  {lex_m:>7s}  {fb_m:>8s}  {v_str:30s}")


if __name__ == "__main__":
    main()
