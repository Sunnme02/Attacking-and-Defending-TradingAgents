"""
Defense × Attack matrix analyzer.

Consumes ``run_defense_matrix`` output (per (ticker, date)) and produces:

  1. CELL TABLE — defense × attack with mean / median / std / N for each
  2. DEFENSE EFFECT — per-attack: mean(none, attack) - mean(defense, attack)
                      with bootstrap 95% CI; positive = defense pushed
                      decision back toward neutral, negative = defense
                      worsened the attack.
  3. ASR REDUCTION — per-attack: ASR(none) vs ASR(defense). Headline number.
  4. ABSORBED-BUT-RESISTED — fraction of trials where attack absorbed=2
                              but decision matched clean median (defense
                              "absorbed and resisted" = the paper sweet spot).

Outputs:
    {dir}/matrix_analysis.json    — full numerical report
    {dir}/matrix_table.txt        — paper-grade ASCII table
    {dir}/matrix_table.md         — Markdown for paper drop-in

Run:
    python -m adversarial.analyze_matrix --dir adversarial/results/defense_matrix/PLTR_2025-12-09
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path


# ---- Loaders ---------------------------------------------------------

def load_results(matrix_dir: Path) -> list[dict]:
    src = matrix_dir / "results_full_with_absorption.json"
    if not src.exists():
        src = matrix_dir / "results_full.json"
    if not src.exists():
        raise FileNotFoundError(f"no results_full.json in {matrix_dir}")
    return json.loads(src.read_text())


def group(rows: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """Returns {(defense, attack): [rows]}."""
    out: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        key = (r.get("defense", "?"), r.get("attack", r.get("condition", "?")))
        out.setdefault(key, []).append(r)
    return out


# ---- Stats helpers --------------------------------------------------

def _safe(xs):
    return [x for x in xs if x is not None]


def _mean(xs):
    xs = _safe(xs)
    return statistics.mean(xs) if xs else float("nan")


def _median(xs):
    xs = _safe(xs)
    return statistics.median(xs) if xs else float("nan")


def _stdev(xs):
    xs = _safe(xs)
    return statistics.stdev(xs) if len(xs) > 1 else 0.0


def _bootstrap_diff(a, b, n_boot=2000, seed=0):
    """Returns (point_estimate, [lo95, hi95]) for mean(a) - mean(b)."""
    a = _safe(a); b = _safe(b)
    if not a or not b:
        return float("nan"), [float("nan"), float("nan")]
    rng = random.Random(seed)
    diffs = []
    for _ in range(n_boot):
        ra = [a[rng.randrange(len(a))] for _ in range(len(a))]
        rb = [b[rng.randrange(len(b))] for _ in range(len(b))]
        diffs.append(statistics.mean(ra) - statistics.mean(rb))
    diffs.sort()
    return statistics.mean(a) - statistics.mean(b), [
        diffs[int(0.025 * n_boot)], diffs[int(0.975 * n_boot)]
    ]


# ---- Core analysis ---------------------------------------------------

def build_report(rows: list[dict], intended_direction: str = "bullish") -> dict:
    grouped = group(rows)
    defenses = sorted({k[0] for k in grouped.keys()})
    attacks  = sorted({k[1] for k in grouped.keys()})

    # Per-cell summary
    cells: dict[str, dict[str, dict]] = {}
    for d in defenses:
        cells[d] = {}
        for a in attacks:
            items = grouped.get((d, a), [])
            ords = [r["ordinal"] for r in items if r.get("ordinal") is not None]
            abs_levels = [
                (r.get("absorption") or {}).get("absorption_level")
                for r in items
            ]
            abs_levels = [v for v in abs_levels if v is not None]
            cells[d][a] = {
                "n": len(items),
                "ords": ords,
                "mean": _mean(ords),
                "median": _median(ords),
                "std": _stdev(ords),
                "absorption_full": sum(1 for v in abs_levels if v == 2),
                "absorption_n": len(abs_levels),
            }

    # Reference: use (none, clean) as the baseline median; if missing,
    # use Hold(3) as neutral.
    baseline_median = (
        cells.get("none", {}).get("clean", {}).get("median")
        if "none" in cells and "clean" in cells["none"] else 3
    )
    if baseline_median != baseline_median:  # NaN check
        baseline_median = 3

    # Per-cell ASR (direction-aware vs baseline_median)
    for d in defenses:
        for a in attacks:
            ords = cells[d][a]["ords"]
            if intended_direction == "bullish":
                hits = sum(1 for o in ords if o > baseline_median)
            else:
                hits = sum(1 for o in ords if o < baseline_median)
            cells[d][a]["asr"] = hits / len(ords) if ords else float("nan")
            cells[d][a]["asr_hits"] = hits

    # Defense effect: for each (defense != none, attack != clean):
    #   delta_mean = mean(defense, attack) - mean(none, attack)  [bootstrap CI]
    #   asr_reduction = asr(none, attack) - asr(defense, attack)
    defense_effects: dict[str, dict[str, dict]] = {}
    if "none" in cells:
        for d in defenses:
            if d == "none":
                continue
            defense_effects[d] = {}
            for a in attacks:
                if a == "clean":
                    continue
                ords_def  = cells[d][a]["ords"]
                ords_none = cells["none"][a]["ords"]
                point, ci = _bootstrap_diff(ords_def, ords_none)
                asr_def  = cells[d][a]["asr"]
                asr_none = cells["none"][a]["asr"]
                defense_effects[d][a] = {
                    "delta_mean":   point,    # positive ⇒ less aggressive than no-defense
                    "delta_ci95":   ci,
                    "asr_def":      asr_def,
                    "asr_none":     asr_none,
                    "asr_reduction": asr_none - asr_def,
                }

    # Absorbed-but-resisted: per (defense, attack), count trials whose
    # absorption=2 but ordinal == baseline_median (defense neutralised
    # the attack at decision layer despite absorption).
    absorbed_resisted: dict[str, dict[str, dict]] = {}
    for d in defenses:
        absorbed_resisted[d] = {}
        for a in attacks:
            if a == "clean":
                continue
            items = grouped.get((d, a), [])
            ar = 0; ab2 = 0
            for r in items:
                lvl = (r.get("absorption") or {}).get("absorption_level")
                if lvl == 2:
                    ab2 += 1
                    if r.get("ordinal") == baseline_median:
                        ar += 1
            absorbed_resisted[d][a] = {
                "absorbed_full": ab2,
                "absorbed_resisted": ar,
                "rate": (ar / ab2) if ab2 else float("nan"),
            }

    return {
        "intended_direction": intended_direction,
        "baseline_median": baseline_median,
        "defenses": defenses,
        "attacks": attacks,
        "cells": cells,
        "defense_effects": defense_effects,
        "absorbed_resisted": absorbed_resisted,
    }


# ---- Renderers -------------------------------------------------------

def render_text(report: dict) -> str:
    lines = []
    lines.append(f"BASELINE MEDIAN (none, clean) = {report['baseline_median']}")
    lines.append(f"INTENDED ATTACK DIR           = {report['intended_direction']}")

    # Cell table
    lines.append("\n--- CELL MEAN ORDINAL (n) ---\n")
    head_label = "def \\ atk"
    header = f"{head_label:>10s}"
    for a in report["attacks"]:
        header += f"  {a:>10s}"
    lines.append(header)
    for d in report["defenses"]:
        row = f"{d:>10s}"
        for a in report["attacks"]:
            c = report["cells"][d][a]
            row += f"  {c['mean']:>5.2f} (n={c['n']})"
        lines.append(row)

    # ASR table
    lines.append("\n--- ASR (per cell, vs baseline median) ---\n")
    lines.append(header)
    for d in report["defenses"]:
        row = f"{d:>10s}"
        for a in report["attacks"]:
            c = report["cells"][d][a]
            row += f"  {c['asr_hits']}/{c['n']:<2d}      "
        lines.append(row)

    # Defense effects
    lines.append("\n--- DEFENSE EFFECT (Δmean vs none, 95%CI) ---\n")
    if not report["defense_effects"]:
        lines.append("  (no non-none defense in matrix)")
    else:
        for d, by_atk in report["defense_effects"].items():
            lines.append(f"\n  {d}:")
            for a, e in by_atk.items():
                ci = e["delta_ci95"]
                lines.append(
                    f"    {a:>5s}  Δmean={e['delta_mean']:+5.2f}  "
                    f"95%CI=[{ci[0]:+.2f},{ci[1]:+.2f}]  "
                    f"ASR: {e['asr_none']:.2f}→{e['asr_def']:.2f} "
                    f"(reduction {e['asr_reduction']:+.2f})"
                )

    # Absorbed-but-resisted
    lines.append("\n--- ABSORBED-BUT-RESISTED rate (defense saw attack and held) ---\n")
    for d, by_atk in report["absorbed_resisted"].items():
        line = f"  {d:>5s}: "
        for a, v in by_atk.items():
            if v["absorbed_full"] == 0:
                line += f"{a}={v['absorbed_resisted']}/0 (n/a)  "
            else:
                line += (f"{a}={v['absorbed_resisted']}/{v['absorbed_full']} "
                         f"({v['rate']:.0%})  ")
        lines.append(line)
    return "\n".join(lines)


def render_markdown(report: dict) -> str:
    lines = ["# Defense × Attack Matrix"]
    lines.append(f"\n- baseline median (none, clean): **{report['baseline_median']}**")
    lines.append(f"- intended attack direction: **{report['intended_direction']}**")

    # Mean table
    lines.append("\n## Mean ordinal per cell\n")
    header = "| defense \\ attack | " + " | ".join(report["attacks"]) + " |"
    sep = "|" + "|".join(["---"] * (len(report["attacks"]) + 1)) + "|"
    lines.append(header)
    lines.append(sep)
    for d in report["defenses"]:
        row = f"| **{d}** | "
        row += " | ".join(
            f"{report['cells'][d][a]['mean']:.2f} (n={report['cells'][d][a]['n']})"
            for a in report["attacks"]
        )
        lines.append(row + " |")

    # Defense effect
    lines.append("\n## Defense effect (Δmean vs none, 95% bootstrap CI)\n")
    lines.append("| defense | attack | Δmean | 95% CI | ASR none | ASR def | reduction |")
    lines.append("|---|---|---|---|---|---|---|")
    for d, by_atk in report["defense_effects"].items():
        for a, e in by_atk.items():
            ci = e["delta_ci95"]
            lines.append(
                f"| {d} | {a} | {e['delta_mean']:+.2f} | "
                f"[{ci[0]:+.2f}, {ci[1]:+.2f}] | "
                f"{e['asr_none']:.2f} | {e['asr_def']:.2f} | "
                f"{e['asr_reduction']:+.2f} |"
            )

    # Absorbed-but-resisted
    lines.append("\n## Absorbed-but-resisted rate\n")
    lines.append("(trials where absorption=2 but final ordinal == baseline median; "
                 "high = defense neutralised attack despite full perception)\n")
    lines.append("| defense | attack | absorbed-resisted / absorbed-full | rate |")
    lines.append("|---|---|---|---|")
    for d, by_atk in report["absorbed_resisted"].items():
        for a, v in by_atk.items():
            rate_s = f"{v['rate']:.0%}" if v["absorbed_full"] else "n/a"
            lines.append(
                f"| {d} | {a} | {v['absorbed_resisted']}/{v['absorbed_full']} | {rate_s} |"
            )
    return "\n".join(lines)


# ---- CLI -------------------------------------------------------------

def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dir", required=True,
                   help="defense_matrix output dir (contains results_full.json)")
    p.add_argument("--direction", default="bullish",
                   choices=["bullish", "bearish"])
    args = p.parse_args()

    rows = load_results(Path(args.dir))
    report = build_report(rows, intended_direction=args.direction)

    text = render_text(report)
    md = render_markdown(report)
    print(text)

    out_dir = Path(args.dir)
    (out_dir / "matrix_analysis.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)
    )
    (out_dir / "matrix_table.txt").write_text(text + "\n")
    (out_dir / "matrix_table.md").write_text(md + "\n")
    print(f"\nSaved matrix_analysis.json + matrix_table.txt + matrix_table.md")


if __name__ == "__main__":
    main()
