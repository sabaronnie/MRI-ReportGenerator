"""Scorecard: compare group2_summary.csv against cervical normal/plausibility thresholds.

Used as the objective function for the calibration loop. Each check is a PASS/FAIL
against a reference range drawn from cervical-spine MRI literature (see CLAUDE.md
medical-AI rule 1) and anatomical plausibility ceilings. Geometry checks use the
RELIABLE cervical discs (C2-C3 excluded — dens; FOV-edge discs excluded by their flags).

Exit code = number of failing checks (0 == all pass).

    py -3.12 colab/evaluate_calibration.py
    py -3.12 colab/evaluate_calibration.py --csv group2_summary.csv
"""
from __future__ import annotations

import argparse
import csv
import statistics as st
import sys
from pathlib import Path

CERV = ["C2-C3", "C3-C4", "C4-C5", "C5-C6", "C6-C7", "C7-T1"]
HEALTHY_ANCHOR = "593973-000001"   # youngest/most-hydrated scan in this batch


def f(v):
    return None if v in ("", "None", None) else float(v)


def col(rows, key):
    return [f(r[key]) for r in rows if f(r[key]) is not None]


def load(csv_path: Path):
    rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
    reliable_cerv = [r for r in rows if r["reliable"] == "True" and r["disc_level"] in CERV]
    return rows, reliable_cerv


def run_checks(csv_path: Path) -> list[tuple[str, bool, str, str]]:
    """Return [(name, ok, detail, category)]. category is one of:
        'pfirrmann' - auto-calibratable (intensity-scale dependent),
        'geometry'  - millimetre measurement; never auto-shifted (would hide pathology),
        'anchor'    - healthy-reference sanity check.
    """
    rows, rc = load(csv_path)
    checks: list[tuple[str, bool, str, str]] = []

    def rng(name, key, lo, hi, cat, src=None, agg=st.median, aggname="median"):
        vals = col(src if src is not None else rc, key)
        if not vals:
            checks.append((name, False, "no data", cat)); return
        v = agg(vals)
        checks.append((name, lo <= v <= hi, f"{aggname}={v:.3f}  target[{lo},{hi}]", cat))

    def ceil(name, key, hi, cat):
        vals = col(rc, key)
        if not vals:
            checks.append((name, False, "no data", cat)); return
        v = max(vals)
        checks.append((name, v <= hi, f"max={v:.2f}  ceiling<={hi}", cat))

    def frac(name, predicate, limit, cat, src=None):
        s = src if src is not None else rc
        n = len(s)
        if n == 0:
            checks.append((name, False, "no data", cat)); return
        k = sum(1 for r in s if predicate(r))
        checks.append((name, (k / n) <= limit, f"{k}/{n}={k/n:.0%}  limit<={limit:.0%}", cat))

    # ---- disc height (disc_si_height.py) ----
    rng("H_anterior median (mm)", "H_anterior_mm", 3.0, 6.5, "geometry")
    rng("H_posterior median (mm)", "H_posterior_mm", 2.5, 6.0, "geometry")
    rng("H_middle median (mm)", "H_middle_mm", 3.0, 6.0, "geometry")
    ceil("H_anterior plausibility", "H_anterior_mm", 8.0, "geometry")
    ceil("H_posterior plausibility", "H_posterior_mm", 8.0, "geometry")
    frac("wedge: H_post>H_ant minority", lambda r: f(r["H_posterior_mm"]) > f(r["H_anterior_mm"]), 0.45, "geometry")

    # ---- disc AP width (disc_si_height.py / cervical_body_morphometry.py) ----
    rng("AP_width median (mm)", "AP_width_mm", 13.0, 20.0, "geometry")
    ceil("AP_width plausibility", "AP_width_mm", 25.0, "geometry")

    # ---- DHI (disc_height_index.py) ----
    rng("DHI median", "DHI", 0.30, 0.45, "geometry")

    # ---- disc/VB AP ratio (disc_ap_bulge.py) ----
    rng("disc/VB AP ratio median", "disc_vb_ap_ratio", 0.85, 1.10, "geometry")
    ceil("disc/VB AP ratio plausibility", "disc_vb_ap_ratio", 1.30, "geometry")

    # ---- posterior bulge (disc_ap_bulge.py) ----
    rng("posterior_bulge median (mm)", "posterior_bulge_mm", 0.0, 1.2, "geometry")
    ceil("posterior_bulge plausibility", "posterior_bulge_mm", 6.0, "geometry")
    frac("bulge>=2mm minority", lambda r: f(r["posterior_bulge_mm"]) >= 2.0, 0.30, "geometry")

    # ---- systematic-degradation monitor ----
    # The per-disc plausibility guards (vb_ap_implausible, ap_width_implausible, FOV edges)
    # flag individual bad measurements. If they fire on a LARGE share of discs, that signals a
    # systematic measurement breakdown (e.g. a new scan type), not isolated outliers -> review.
    all_cerv = [r for r in rows if r["disc_level"] in CERV]
    if all_cerv:
        frac_ok = sum(1 for r in all_cerv if r["reliable"] == "True") / len(all_cerv)
        checks.append(("reliable-disc fraction", frac_ok >= 0.60,
                       f"{frac_ok:.0%} of cervical discs reliable  floor>=60%", "geometry"))

    # ---- Pfirrmann grade (pfirrmann_grade.py) — intensity-scale dependent ----
    grades = [int(r["pfirrmann_grade"]) for r in rc if r["pfirrmann_grade"] not in ("", "None")]
    if grades:
        med = st.median(grades)
        checks.append(("Pfirrmann median grade", 2 <= med <= 3, f"median={med}  target[2,3]", "pfirrmann"))
        g4 = sum(1 for g in grades if g >= 4)
        checks.append(("Pfirrmann grade>=IV minority", (g4 / len(grades)) <= 0.35,
                       f"{g4}/{len(grades)}={g4/len(grades):.0%}  limit<=35%", "pfirrmann"))
    anchor = [int(r["pfirrmann_grade"]) for r in rows
              if r["patient_id"] == HEALTHY_ANCHOR and r["disc_level"] in CERV
              and r["pfirrmann_grade"] not in ("", "None")]
    if anchor:
        am = st.median(anchor)
        checks.append((f"healthy anchor {HEALTHY_ANCHOR} median grade<=2", am <= 2,
                       f"median={am}  grades={sorted(anchor)}", "anchor"))
    return checks


def evaluate(csv_path: Path) -> int:
    checks = run_checks(csv_path)
    _, rc = load(csv_path)
    n_fail = sum(1 for _, ok, _, _ in checks if not ok)
    print(f"\n{'CALIBRATION SCORECARD':<42}  ({csv_path.name}, n reliable cervical={len(rc)})")
    print("=" * 78)
    for name, ok, detail, _ in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}]  {name:<34} {detail}")
    print("=" * 78)
    print(f"  {len(checks)-n_fail}/{len(checks)} checks pass"
          + (f"   ({n_fail} FAILING)" if n_fail else "   <-- ALL PASS"))
    return n_fail


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, default=Path(__file__).resolve().parents[1] / "group2_summary.csv")
    args = p.parse_args(argv)
    if not args.csv.is_file():
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        return 99
    return evaluate(args.csv)


if __name__ == "__main__":
    raise SystemExit(main())
