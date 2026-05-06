"""
Combine ordinal decisions + LLM-judge absorption into a paper-ready table
for a finished campaign directory.

Run:
    python -m adversarial.analyze --dir adversarial/results/campaign/PLTR_2025-09-23
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def _safe_median(xs: list[int | float]) -> float | None:
    return float(statistics.median(xs)) if xs else None


def _safe_mean(xs: list[int | float]) -> float | None:
    return float(statistics.mean(xs)) if xs else None


def _safe_stdev(xs: list[int | float]) -> float:
    return float(statistics.stdev(xs)) if len(xs) > 1 else 0.0


def analyze(campaign_dir: Path) -> dict:
    full = campaign_dir / "results_full.json"
    aug = campaign_dir / "results_full_with_absorption.json"
    src = aug if aug.exists() else full
    rows = json.loads(src.read_text())

    by_cond: dict[str, list[dict]] = {}
    for r in rows:
        by_cond.setdefault(r["condition"], []).append(r)

    clean_median = None
    if "clean" in by_cond:
        ords = [r["ordinal"] for r in by_cond["clean"]
                if r.get("ordinal") is not None]
        if ords:
            clean_median = statistics.median(ords)

    table: dict[str, dict] = {}
    for cond, items in by_cond.items():
        ords = [r["ordinal"] for r in items if r.get("ordinal") is not None]
        decisions = [r["decision"] for r in items]
        abs_vals = [
            (r.get("absorption") or {}).get("absorption_level")
            for r in items
        ]
        abs_vals = [v for v in abs_vals if v is not None]

        # flip relative to clean median (only if clean known and condition is attacked)
        flip_count = None
        if clean_median is not None and cond != "clean" and ords:
            flip_count = sum(1 for o in ords if o != clean_median)

        table[cond] = {
            "n": len(items),
            "decisions": decisions,
            "median_ordinal": _safe_median(ords),
            "mean_ordinal": _safe_mean(ords),
            "std_ordinal": _safe_stdev(ords),
            "absorption_mean": _safe_mean(abs_vals) if abs_vals else None,
            "absorption_dist": {
                lvl: sum(1 for v in abs_vals if v == lvl) for lvl in (0, 1, 2)
            } if abs_vals else None,
            "flip_count_vs_clean_median": flip_count,
            "delta_mean_vs_clean": (
                _safe_mean(ords) - _safe_mean([
                    r["ordinal"] for r in by_cond["clean"]
                    if r.get("ordinal") is not None
                ])
                if "clean" in by_cond and cond != "clean" and ords else None
            ),
        }

    return {"clean_median": clean_median, "by_condition": table}


def render(report: dict) -> str:
    lines = []
    lines.append(f"clean median ordinal = {report['clean_median']}")
    lines.append("")
    header = (
        f"{'cond':>6}  {'n':>2}  {'med':>4}  {'mean':>5}  {'std':>5}  "
        f"{'absMean':>7}  {'absDist':>14}  {'flip':>5}  {'Δmean':>6}  decisions"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for cond, s in report["by_condition"].items():
        med = s["median_ordinal"]
        mn = s["mean_ordinal"]
        sd = s["std_ordinal"]
        am = s["absorption_mean"]
        ad = s["absorption_dist"]
        ad_s = (f"{{0:{ad[0]},1:{ad[1]},2:{ad[2]}}}" if ad else "—")
        flip = s["flip_count_vs_clean_median"]
        delta = s["delta_mean_vs_clean"]
        lines.append(
            f"{cond:>6}  {s['n']:>2}  "
            f"{('%.1f' % med) if med is not None else '—':>4}  "
            f"{('%.2f' % mn) if mn is not None else '—':>5}  "
            f"{sd:>5.2f}  "
            f"{('%.2f' % am) if am is not None else '—':>7}  "
            f"{ad_s:>14}  "
            f"{('%d/%d' % (flip, s['n'])) if flip is not None else '—':>5}  "
            f"{('%+.2f' % delta) if delta is not None else '—':>6}  "
            f"{s['decisions']}"
        )
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dir", required=True,
                   help="campaign output directory")
    args = p.parse_args()

    report = analyze(Path(args.dir))
    print(render(report))

    out = Path(args.dir) / "analysis_table.txt"
    out.write_text(render(report) + "\n")
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
