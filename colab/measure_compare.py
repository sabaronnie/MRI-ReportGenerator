"""
End-to-end check of the standardization layer.

For each patient, measure the disc components on:
  (A) the BASELINE segmentation (raw MRI -> TSS, from the earlier batch run), and
  (B) the STANDARDIZED segmentation (raw MRI -> standardize_mri -> TSS).
Then compare. If (B) is sensible (cervical literature ranges) and consistent
with (A), the standardization layer works end-to-end and preserves the true
measurements while making the input uniform.

Runs the geometry chain disc_si_height -> {disc_height_index, disc_ap_bulge}
(via load_context + the repo component pattern), and Pfirrmann if a
shape-matching intensity image is available.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import nibabel as nib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.measurements.context import load_context, MeasurementError  # noqa: E402
from services.measurements.geometric import (  # noqa: E402
    disc_si_height, disc_height_index, disc_ap_bulge)
try:
    from services.measurements.signal import pfirrmann_grade
except Exception:                       # pragma: no cover
    pfirrmann_grade = None

CERVICAL = ["C2-C3", "C3-C4", "C4-C5", "C5-C6", "C6-C7", "C7-T1"]
# cervical reference ranges (mid-sagittal MRI literature)
REF = {"H_center": (2.5, 7.0), "DHI": (0.25, 0.50), "AP_width": (12.0, 19.0),
       "ratio": (0.80, 1.15)}


def measure_seg(seg_path: Path, raw_path: Path | None = None) -> dict:
    ctx = load_context(str(seg_path), str(raw_path) if raw_path else None)
    si = disc_si_height.compute(ctx)
    prior = {"disc_si_height": si}
    dhi = disc_height_index.compute(ctx, prior); prior["disc_height_index"] = dhi
    ap = disc_ap_bulge.compute(ctx, prior); prior["disc_ap_bulge"] = ap

    pf_grade = {}
    if pfirrmann_grade is not None and getattr(ctx, "raw_data", None) is not None:
        try:
            pf = pfirrmann_grade.compute(ctx, prior)
            # grab whichever measurement key holds the grade
            for k, v in pf.measurements.items():
                if "grade" in k.lower() or "pfirr" in k.lower():
                    pf_grade = v
                    break
        except Exception as e:
            pf_grade = {"_error": str(e)[:80]}

    out = {}
    for d in si.measurements["disc_H_center"]:
        out[d] = {
            "H_center": si.measurements["disc_H_center"].get(d),
            "H_middle": si.measurements["disc_H_middle"].get(d),
            "AP_width": si.measurements["disc_AP_width"].get(d),
            "DHI": dhi.measurements["DHI"].get(d),
            "ratio": ap.measurements["disc_vb_ap_ratio"].get(d),
            "reliable": not si.flags["disc_measurement_unreliable"].get(d, False),
            "grade": pf_grade.get(d) if isinstance(pf_grade, dict) else None,
        }
    return out


def _fmt(v, nd=2):
    return f"{v:.{nd}f}" if isinstance(v, (int, float)) else " . "


def compare_patient(pid: str, base_seg, base_raw, std_seg, std_raw):
    print("\n" + "=" * 78)
    print(f"PATIENT {pid}")
    print("=" * 78)
    try:
        base = measure_seg(base_seg, base_raw)
    except MeasurementError as e:
        print(f"  baseline measure failed: {e}"); base = {}
    std = measure_seg(std_seg, std_raw)

    print(f"  {'disc':<7} | {'H_center(mm)':>14} | {'DHI':>12} | {'AP_width(mm)':>14} | {'disc/VB':>11} | grade")
    print(f"  {'':<7} | {'base / std':>14} | {'base / std':>12} | {'base / std':>14} | {'base/std':>11} | b/s")
    for d in [x for x in CERVICAL if x in std]:
        b = base.get(d, {}); s = std[d]
        print(f"  {d:<7} | {_fmt(b.get('H_center')):>6} /{_fmt(s['H_center']):>6} "
              f"| {_fmt(b.get('DHI'),3):>5} /{_fmt(s['DHI'],3):>5} "
              f"| {_fmt(b.get('AP_width')):>6} /{_fmt(s['AP_width']):>6} "
              f"| {_fmt(b.get('ratio')):>4} /{_fmt(s['ratio']):>4} "
              f"| {b.get('grade')}/{s.get('grade')}"
              + ("" if s['reliable'] else "  [unreliable]"))

    # sanity vs literature (standardized, reliable cervical discs)
    print("  -- standardized reliable-disc sanity vs cervical literature --")
    import statistics as st
    for key, (lo, hi) in REF.items():
        vals = [std[d][key] for d in CERVICAL if d in std and std[d]["reliable"]
                and isinstance(std[d][key], (int, float))]
        if vals:
            med = st.median(vals)
            print(f"     {key:9} median={med:6.2f}  ref[{lo},{hi}]  "
                  f"{'OK' if lo <= med <= hi else 'CHECK'}")


def main():
    base_seg_dir = ROOT / "tss_runs" / "batch_out" / "step2_output"
    base_raw_dir = ROOT / "tss_runs" / "batch_in"
    std_seg_dir = ROOT / "tss_runs" / "std_out" / "step2_output"
    std_raw_dir = ROOT / "tss_runs" / "std_in"
    if not std_seg_dir.exists():
        print("standardized segmentations not found yet:", std_seg_dir); return 1

    for std_seg in sorted(std_seg_dir.glob("*.nii.gz")):
        pid = std_seg.name.split("_")[0]
        std_raw = next(std_raw_dir.glob(f"{pid}_*.nii.gz"), None)
        base_seg = next(base_seg_dir.glob(f"{pid}_*.nii.gz"), None)
        base_raw = next(base_raw_dir.glob(f"{pid}_*.nii.gz"), None)
        if base_seg is None:
            print(f"[skip] no baseline seg for {pid}"); continue
        compare_patient(pid, base_seg, base_raw, std_seg, std_raw)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
