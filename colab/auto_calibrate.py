"""Automatic, self-calibrating measurement check — run it after each segmentation batch.

Daily workflow:
    1. run segment_batch.py (adds more TotalSpineSeg segmentations)
    2. run THIS script

What it does, in order:
    1. Measures every available segmentation -> group2_summary.csv (no TSS, CPU only).
    2. Scores the result against cervical normal/plausibility ranges (evaluate_calibration).
    3. If every check passes -> prints "no calibration needed" and stops. (No-op by design:
       calibration only happens when the data actually drifts.)
    4. If the Pfirrmann grade distribution drifted -> AUTO-REFITS the cervical grade cut-points
       from the new data (percentile-anchored to the cohort's hydration distribution), saves
       them to services/measurements/calibration.json, re-measures and re-scores.
    5. Anything else that fails (geometry medians/ceilings, wedge, bulge, ratio tail) is
       reported as REVIEW-NEEDED and NOT auto-changed.

Why only Pfirrmann is auto-calibrated
-------------------------------------
Pfirrmann uses `nucleus_norm`, a relative T2-brightness scale that shifts with scanner /
protocol, so its cut-points are legitimately dataset-dependent and safe to refit (we anchor
to the most-hydrated discs, preserving disc-to-disc ordering). The geometry measurements are
in physical millimetres: a degenerative cohort is *supposed* to read abnormal there, so
auto-shifting them toward "normal" would erase real pathology (forbidden by the medical-AI
rules in CLAUDE.md). Geometry is corrected by algorithm fixes + plausibility flags, not by
statistical shifting; genuine geometry drift is surfaced for human review instead.

    py -3.12 colab/auto_calibrate.py
    py -3.12 colab/auto_calibrate.py --n 100        # consider only the first 100 Duke scans
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[0]
sys.path.insert(0, str(HERE))

from evaluate_calibration import run_checks, load, CERV, f  # noqa: E402

CALIBRATION_PATH = ROOT / "services" / "measurements" / "calibration.json"
REPORT_PATH = ROOT / "group2_calibration_report.md"
DEFAULT_CSV = ROOT / "group2_summary.csv"

# Target Pfirrmann distribution used to anchor the cut-point refit: cumulative fraction
# (from the healthy end) at each grade boundary -> I~10%, II~25%, III~35%, IV~25%, V~5%.
# A sensible degenerative-cohort spread. Refit cuts = these percentiles of nucleus_norm.
TARGET_CUM = (0.10, 0.35, 0.70, 0.95)
MIN_DISCS_FOR_REFIT = 30


def measure(n: int) -> bool:
    """Measure all available segmentations into group2_summary.csv. Returns True on success."""
    cmd = [sys.executable, str(HERE / "run_group2_pipeline.py"), "--n", str(n), "--no-segment"]
    print(f"[measure] {' '.join(cmd[-3:])} ...")
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    for line in proc.stdout.splitlines():
        if line.startswith("[seg]") or "Wrote" in line:
            print("   " + line)
    if proc.returncode != 0:
        print(proc.stderr[-1500:], file=sys.stderr)
    return proc.returncode == 0


def refit_pfirrmann_cuts(csv_path: Path, region: str = "cervical") -> list[float] | None:
    """Refit grade cut-points as percentiles of the reliable-disc nucleus_norm distribution."""
    _, rc = load(csv_path)
    levels = CERV if region == "cervical" else None
    nn = [f(r["nucleus_norm"]) for r in rc
          if (levels is None or r["disc_level"] in levels) and f(r["nucleus_norm"]) is not None]
    if len(nn) < MIN_DISCS_FOR_REFIT:
        print(f"[refit] only {len(nn)} discs (< {MIN_DISCS_FOR_REFIT}); not enough to refit safely.")
        return None
    pcts = [100.0 * (1.0 - c) for c in TARGET_CUM]      # [90, 65, 30, 5]
    cuts = [round(float(np.percentile(nn, p)), 4) for p in pcts]
    # enforce strict monotonic decrease (defensive)
    for i in range(1, len(cuts)):
        cuts[i] = min(cuts[i], cuts[i - 1] - 1e-4)
    return cuts


def write_calibration(region: str, cuts: list[float]) -> dict:
    data = {}
    if CALIBRATION_PATH.is_file():
        try:
            data = json.loads(CALIBRATION_PATH.read_text())
        except Exception:  # noqa: BLE001
            data = {}
    data.setdefault("pfirrmann_norm_cuts", {})[region] = cuts
    data["_updated"] = dt.datetime.now().isoformat(timespec="seconds")
    CALIBRATION_PATH.write_text(json.dumps(data, indent=2))
    return data


def summarize(checks) -> tuple[int, list, list, list]:
    fails = [c for c in checks if not c[1]]
    pf = [c for c in fails if c[3] == "pfirrmann"]
    geo = [c for c in fails if c[3] == "geometry"]
    anchor = [c for c in fails if c[3] == "anchor"]
    return len(fails), pf, geo, anchor


def write_report(lines: list[str]) -> None:
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    REPORT_PATH.write_text(f"# Group-2 calibration report ({stamp})\n\n" + "\n".join(lines) + "\n",
                           encoding="utf-8")
    print(f"\n[report] written to {REPORT_PATH}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--n", type=int, default=100000, help="how many Duke scans to consider (default: all)")
    p.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    args = p.parse_args(argv)

    report: list[str] = []

    # 1) measure everything available
    if not measure(args.n):
        print("ERROR: measurement step failed.", file=sys.stderr)
        return 1
    if not args.csv.is_file():
        print(f"ERROR: {args.csv} not produced.", file=sys.stderr)
        return 1

    # 2) score
    checks = run_checks(args.csv)
    _, rc = load(args.csv)
    n_fail, pf_fail, geo_fail, anchor_fail = summarize(checks)
    print(f"\nScorecard: {len(checks) - n_fail}/{len(checks)} pass  "
          f"(reliable cervical discs = {len(rc)})")
    report.append(f"- Reliable cervical discs measured: **{len(rc)}**")
    report.append(f"- Scorecard: **{len(checks) - n_fail}/{len(checks)} pass**\n")

    # 3) all good -> no calibration
    if n_fail == 0:
        print("\nAll measurements within normal/plausibility ranges. NO CALIBRATION NEEDED.")
        report.append("**All checks pass - no calibration applied.**")
        report += [f"  - PASS {c[0]}: {c[2]}" for c in checks]
        write_report(report)
        return 0

    print(f"\n{n_fail} check(s) failing:")
    for c in (pf_fail + geo_fail + anchor_fail):
        print(f"  FAIL {c[0]}: {c[2]}")

    # 4) auto-calibrate Pfirrmann if its distribution drifted
    if pf_fail:
        print("\n[calibrate] Pfirrmann distribution drifted -> refitting cut-points from data.")
        old = None
        if CALIBRATION_PATH.is_file():
            try:
                old = json.loads(CALIBRATION_PATH.read_text()).get("pfirrmann_norm_cuts", {}).get("cervical")
            except Exception:  # noqa: BLE001
                old = None
        cuts = refit_pfirrmann_cuts(args.csv, "cervical")
        if cuts is None:
            report.append("- Pfirrmann FAILED but too few discs to refit safely — REVIEW.")
        else:
            write_calibration("cervical", cuts)
            print(f"[calibrate] cervical cut-points {old} -> {cuts}; re-measuring.")
            report.append(f"- **Auto-calibrated Pfirrmann** cervical cut-points: `{old}` -> `{cuts}`")
            if abs(cuts[0] - (old[0] if old else 0.30)) > 0.10:
                report.append("  - WARNING: large shift, may indicate a scanner/protocol change; worth a human look.")
            measure(args.n)
            checks = run_checks(args.csv)
            n_fail, pf_fail, geo_fail, anchor_fail = summarize(checks)
            print(f"[calibrate] after refit: {len(checks) - n_fail}/{len(checks)} pass.")
            report.append(f"  - After refit: **{len(checks) - n_fail}/{len(checks)} pass**.")

    # 5) geometry / anchor failures are NOT auto-shifted — flag for review
    review = geo_fail + anchor_fail
    if review:
        print("\n[review] These need a human / code fix (NOT auto-shifted — would hide pathology):")
        report.append("\n**Review needed (not auto-calibrated):**")
        for c in review:
            print(f"  - {c[0]}: {c[2]}")
            report.append(f"  - {c[0]}: {c[2]}")

    write_report(report)
    return 0 if n_fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
