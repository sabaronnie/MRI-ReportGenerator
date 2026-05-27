"""Automated group-2 pipeline.

    Duke C-spine MRI  ->  TotalSpineSeg  ->  4 disc-measurement components  ->  group2_summary.csv

For each of the first N scans in the Duke annotation folder this script:
  1. ensures a TotalSpineSeg `step2_output` segmentation exists
     (reuses a cached seg if present, otherwise batch-runs TSS),
  2. loads the segmentation + raw T2 into a MeasurementContext,
  3. runs disc_si_height -> disc_height_index -> disc_ap_bulge -> pfirrmann_grade,
  4. emits ONE CSV row per disc level with every measurement + reliability flags.

The output (`group2_summary.csv`, one row per disc) is the calibration table:
raw measured values per level/patient that get shifted to match normal thresholds.

Run with the Python that has totalspineseg + nibabel installed:
    py -3.12 colab/run_group2_pipeline.py
    py -3.12 colab/run_group2_pipeline.py --n 10 --device cuda
"""
from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
import time
from pathlib import Path

import nibabel as nib
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.measurements.context import load_context, MeasurementError  # noqa: E402
from services.measurements.geometric import (  # noqa: E402
    disc_si_height,
    disc_height_index,
    disc_ap_bulge,
)
from services.measurements.signal import pfirrmann_grade  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration (defaults; override on the CLI)
# ---------------------------------------------------------------------------
SCANS_DIR = Path(r"C:\Users\Moka\Desktop\Share\DukeCSpineSeg_annotation")
PIPE_DIR = ROOT / "tss_runs" / "group2_pipeline"        # this pipeline's own TSS work area
SEG_PER_SCAN_BASE = ROOT / "tss_runs" / "segmentations"  # per-scan folders from segment_batch.py
CACHE_SEG_DIRS = [                                       # searched (in order) for an existing seg
    PIPE_DIR / "out" / "step2_output",
    ROOT / "tss_runs" / "batch_out" / "step2_output",
]
OUTPUT_CSV = ROOT / "group2_summary.csv"

# Disc levels in cranio-caudal order, so the CSV reads top-to-bottom per patient.
LEVEL_ORDER = [
    "C2-C3", "C3-C4", "C4-C5", "C5-C6", "C6-C7",
    "C7-T1", "T1-T2", "T2-T3", "T3-T4",
]

CSV_FIELDS = [
    "patient_id", "source_file", "disc_level", "disc_label", "region", "slice_index",
    "vx_lr_mm", "vx_pa_mm", "vx_si_mm",
    # disc_si_height (2.1)
    "H_anterior_mm", "H_middle_mm", "H_posterior_mm", "H_mean_mm", "H_center_mm", "AP_width_mm",
    # disc_height_index (2.3)
    "DHI", "DHI_anterior", "DHI_posterior", "h_upperVB_middle_mm", "h_lowerVB_middle_mm",
    # disc_ap_bulge (2.2)
    "disc_vb_ap_ratio", "vb_ap_width_ref_mm", "posterior_bulge_mm",
    # pfirrmann_grade (2.4)
    "pfirrmann_grade", "pfirrmann_label", "nucleus_csf_ratio", "nucleus_norm",
    "heterogeneity", "na_contrast_norm", "height_ratio",
    # quality
    "reliable", "flags",
]


def _round(v, nd=4):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    if not np.isfinite(f):
        return None
    return round(f, nd)


# ---------------------------------------------------------------------------
# Segmentation (TotalSpineSeg)
# ---------------------------------------------------------------------------
def find_cached_seg(raw_name: str) -> Path | None:
    """Return a cached step2 segmentation matching the raw scan's filename, if any.

    Checks the per-scan layout written by segment_batch.py
    (tss_runs/segmentations/<scan_stem>/step2_output/<raw_name>) first, then the
    older shared-folder caches.
    """
    stem = raw_name[:-7] if raw_name.endswith(".nii.gz") else Path(raw_name).stem
    per_scan = SEG_PER_SCAN_BASE / stem / "step2_output" / raw_name
    if per_scan.is_file():
        return per_scan
    for d in CACHE_SEG_DIRS:
        cand = d / raw_name
        if cand.is_file():
            return cand
    return None


def run_tss(raw_paths: list[Path], device: str) -> Path:
    """Batch-run TotalSpineSeg on `raw_paths`; return the step2_output folder."""
    in_dir = PIPE_DIR / "input"
    out_dir = PIPE_DIR / "out"
    in_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    for p in raw_paths:
        dst = in_dir / p.name
        if not dst.exists():
            shutil.copy2(p, dst)

    cmd = [
        sys.executable, "-m", "totalspineseg.inference",
        str(in_dir), str(out_dir), "--device", device,
    ]
    print(f"[tss] segmenting {len(raw_paths)} scan(s): {' '.join(p.name for p in raw_paths)}")
    print(f"[tss] $ {' '.join(cmd)}")
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(ROOT))
    if proc.returncode != 0:
        raise RuntimeError(f"TotalSpineSeg failed (exit {proc.returncode})")
    print(f"[tss] done in {time.perf_counter() - t0:.0f}s")
    return out_dir / "step2_output"


def ensure_segmentations(raw_paths: list[Path], device: str, no_segment: bool = False) -> dict[str, Path]:
    """Map raw filename -> step2 seg path.

    With `no_segment=True` (default for measuring an in-progress batch) only
    already-segmented scans are returned; missing ones are skipped, not sent to TSS.
    """
    seg_for: dict[str, Path] = {}
    to_segment: list[Path] = []
    for raw in raw_paths:
        cached = find_cached_seg(raw.name)
        if cached is not None:
            seg_for[raw.name] = cached
        else:
            to_segment.append(raw)

    print(f"[seg] {len(seg_for)} already segmented, {len(to_segment)} missing.")
    if to_segment and no_segment:
        print(f"[seg] --no-segment: skipping the {len(to_segment)} unsegmented scan(s).")
    elif to_segment:
        step2 = run_tss(to_segment, device)
        for raw in to_segment:
            seg = step2 / raw.name
            if seg.is_file():
                seg_for[raw.name] = seg
            else:
                print(f"[seg] WARNING: TSS produced no segmentation for {raw.name}")
    return seg_for


# ---------------------------------------------------------------------------
# Measurements
# ---------------------------------------------------------------------------
def measure_case(seg_path: Path, raw_path: Path) -> list[dict]:
    """Run the 4 disc components on one case; return one dict per disc level."""
    ctx = load_context(str(seg_path), str(raw_path))

    # Pfirrmann needs the raw T2 in the SAME voxel grid as the seg. TSS step2 (no --iso)
    # follows the input, so shapes match; guard anyway and skip signal grading on mismatch.
    raw_ok = ctx.raw_data is not None and ctx.raw_data.shape == ctx.seg_data.shape
    if ctx.raw_data is not None and not raw_ok:
        print(f"      [warn] raw/seg shape mismatch "
              f"({ctx.raw_data.shape} vs {ctx.seg_data.shape}); skipping Pfirrmann")
        ctx.raw_data = None

    si = disc_si_height.compute(ctx)
    prior = {"disc_si_height": si}
    try:
        dhi = disc_height_index.compute(ctx, prior)
        prior["disc_height_index"] = dhi
    except MeasurementError:
        dhi = None
    try:
        ap = disc_ap_bulge.compute(ctx, prior)
        prior["disc_ap_bulge"] = ap
    except MeasurementError:
        ap = None

    pf = None
    if ctx.raw_data is not None:
        try:
            pf = pfirrmann_grade.compute(ctx, prior)
        except MeasurementError as e:
            print(f"      [warn] pfirrmann skipped: {e}")

    def m(result, key, level):
        if result is None:
            return None
        return result.measurements.get(key, {}).get(level)

    # Per-level flag strings from the AP component (carries vb_ap_implausible etc.).
    ap_flags_by_level = {r["disc_name"]: r.get("flags", "") for r in (ap.metadata.get("rows", []) if ap else [])}

    rows = []
    for level in si.metadata.get("levels", []):
        flags = set()
        for s in (si.intermediate["flags"].get(level, ""), ap_flags_by_level.get(level, "")):
            flags.update(x for x in s.split(";") if x)
        # A disc is reliable only if BOTH the base geometry and the AP/ratio measurement
        # are trustworthy (the latter flags under-measured vertebral bodies).
        reliable = bool(si.intermediate["reliable"].get(level, False))
        if ap is not None and ap.flags.get("disc_ap_unreliable", {}).get(level, False):
            reliable = False

        pf_label = None
        if pf is not None:
            pf_label = pf.metadata.get("pfirrmann_label", {}).get(level)

        rows.append({
            "disc_level": level,
            "disc_label": disc_si_height.DISC_LABELS.get(level),
            "region": "cervical" if level.startswith("C") else "thoracic",
            "slice_index": si.intermediate["slice_index"].get(level),
            "H_anterior_mm": _round(m(si, "disc_H_anterior", level)),
            "H_middle_mm": _round(m(si, "disc_H_middle", level)),
            "H_posterior_mm": _round(m(si, "disc_H_posterior", level)),
            "H_mean_mm": _round(m(si, "disc_H_mean", level)),
            "H_center_mm": _round(m(si, "disc_H_center", level)),
            "AP_width_mm": _round(m(si, "disc_AP_width", level)),
            "DHI": _round(m(dhi, "DHI", level)),
            "DHI_anterior": _round(m(dhi, "DHI_anterior", level)),
            "DHI_posterior": _round(m(dhi, "DHI_posterior", level)),
            "h_upperVB_middle_mm": _round(
                (dhi.intermediate["h_upperVB_middle_mm"].get(level) if dhi else None)),
            "h_lowerVB_middle_mm": _round(
                (dhi.intermediate["h_lowerVB_middle_mm"].get(level) if dhi else None)),
            "disc_vb_ap_ratio": _round(m(ap, "disc_vb_ap_ratio", level)),
            "vb_ap_width_ref_mm": _round(m(ap, "vb_ap_width_ref", level)),
            "posterior_bulge_mm": _round(m(ap, "posterior_bulge_mm", level)),
            "pfirrmann_grade": (int(m(pf, "pfirrmann_grade", level))
                                if m(pf, "pfirrmann_grade", level) is not None else None),
            "pfirrmann_label": pf_label,
            "nucleus_csf_ratio": _round(m(pf, "nucleus_csf_ratio", level)),
            "nucleus_norm": _round(m(pf, "nucleus_norm", level)),
            "heterogeneity": _round(m(pf, "heterogeneity", level)),
            "na_contrast_norm": _round(m(pf, "na_contrast_norm", level)),
            "height_ratio": _round(m(dhi, "DHI", level)),  # pfirrmann's height_ratio == DHI
            "reliable": reliable,
            "flags": ";".join(sorted(flags)),
            "vx_lr_mm": _round(ctx.voxel_spacing_mm[0], 3),
            "vx_pa_mm": _round(ctx.voxel_spacing_mm[1], 3),
            "vx_si_mm": _round(ctx.voxel_spacing_mm[2], 3),
        })
    return rows


def _level_sort_key(level: str) -> int:
    return LEVEL_ORDER.index(level) if level in LEVEL_ORDER else len(LEVEL_ORDER)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scans-dir", type=Path, default=SCANS_DIR,
                        help=f"Folder of input .nii.gz scans (default: {SCANS_DIR})")
    parser.add_argument("--n", type=int, default=10,
                        help="Number of scans to process (default: 10)")
    parser.add_argument("--out", type=Path, default=OUTPUT_CSV,
                        help=f"Output CSV path (default: {OUTPUT_CSV.name})")
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"],
                        help="Device for TotalSpineSeg (default: cuda)")
    parser.add_argument("--no-segment", action="store_true",
                        help="Measure only scans that are already segmented; do NOT run "
                             "TotalSpineSeg for missing ones (use while segment_batch.py is "
                             "still running).")
    args = parser.parse_args(argv)

    if not args.scans_dir.is_dir():
        print(f"ERROR: scans dir not found: {args.scans_dir}", file=sys.stderr)
        return 1

    all_scans = sorted(args.scans_dir.glob("*.nii.gz"))
    scans = all_scans[: args.n]
    if not scans:
        print(f"ERROR: no .nii.gz scans in {args.scans_dir}", file=sys.stderr)
        return 1
    print(f"Selected first {len(scans)} of {len(all_scans)} scans in {args.scans_dir}\n")

    seg_for = ensure_segmentations(scans, args.device, no_segment=args.no_segment)

    all_rows: list[dict] = []
    n_ok = 0
    for raw in scans:
        pid = raw.name.split("_")[0]
        seg = seg_for.get(raw.name)
        print(f"\n=== {pid} ({raw.name}) ===")
        if seg is None:
            print("  [skip] no segmentation available")
            continue
        try:
            rows = measure_case(seg, raw)
        except MeasurementError as e:
            print(f"  [skip] measurement failed: {e}")
            continue
        except Exception as e:  # noqa: BLE001 - keep batch going, report the failure
            print(f"  [skip] unexpected error: {type(e).__name__}: {e}")
            continue

        rows.sort(key=lambda r: _level_sort_key(r["disc_level"]))
        for r in rows:
            r["patient_id"] = pid
            r["source_file"] = raw.name
            all_rows.append(r)
            grade = r["pfirrmann_grade"]
            print(f"  {r['disc_level']:<6} H_center={r['H_center_mm']!s:>6} "
                  f"DHI={r['DHI']!s:>6} ratio={r['disc_vb_ap_ratio']!s:>5} "
                  f"Pfirr={grade}"
                  + ("" if r["reliable"] else f"  [unreliable: {r['flags']}]"))
        n_ok += 1

    if not all_rows:
        print("\nNo measurements produced; CSV not written.", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for r in all_rows:
            writer.writerow({k: r.get(k) for k in CSV_FIELDS})

    print(f"\nWrote {len(all_rows)} disc rows from {n_ok}/{len(scans)} scans -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
