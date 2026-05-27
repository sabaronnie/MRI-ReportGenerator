"""Segmentation-only batch runner: first N Duke C-spine scans -> TotalSpineSeg.

Each scan gets ITS OWN output folder containing the TSS `step2_output` segmentation:

    tss_runs/segmentations/<scan_stem>/step2_output/<scan_stem>.nii.gz

Behaviour:
  * Processes the first N scans (sorted by filename) in the Duke folder.
  * SKIPS any scan already segmented:
      - if its per-scan folder already has a step2 segmentation -> skip outright;
      - else if a segmentation exists in a legacy cache (the earlier batch runs) ->
        copy it into the per-scan folder and skip TSS (no re-segmenting).
  * Segments the rest with TotalSpineSeg (no --iso, so step2 follows the input grid,
    matching the already-done scans and keeping the raw usable for downstream Pfirrmann).
  * Runs one scan at a time and is fully RESUMABLE: re-running continues where it stopped.
  * No measurements are computed (segmentation outputs only).

Run it independently of any chat session, with the Python that has totalspineseg:

    py -3.12 colab/segment_batch.py                 # first 100, GPU
    py -3.12 colab/segment_batch.py --n 100 --device cuda
    py -3.12 colab/segment_batch.py --dry-run       # just print the skip/segment plan

Outputs land in:  tss_runs/segmentations/   (one folder per scan)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --- configuration (override on the CLI) -----------------------------------
SCANS_DIR = Path(r"C:\Users\Moka\Desktop\Share\DukeCSpineSeg_annotation")
OUT_BASE = ROOT / "tss_runs" / "segmentations"          # one folder per scan, created here
LEGACY_SEG_DIRS = [                                      # reuse already-done segmentations
    ROOT / "tss_runs" / "group2_pipeline" / "out" / "step2_output",
    ROOT / "tss_runs" / "batch_out" / "step2_output",
]
KEEP_ONLY = "step2_output"                               # keep only the labelled segmentation


def scan_stem(raw_name: str) -> str:
    """`593973-000001_Study-MR-1_Series-22.nii.gz` -> `593973-...-Series-22`."""
    return raw_name[:-7] if raw_name.endswith(".nii.gz") else Path(raw_name).stem


def per_scan_step2(out_base: Path, raw_name: str) -> Path:
    return out_base / scan_stem(raw_name) / "step2_output"


def existing_step2(folder: Path, raw_name: str) -> Path | None:
    """Return a step2 .nii.gz in `folder` matching this scan, if present."""
    if not folder.is_dir():
        return None
    cand = folder / raw_name
    if cand.is_file():
        return cand
    # fall back to any single nii.gz (per-scan folders only ever hold one)
    hits = sorted(folder.glob("*.nii.gz"))
    return hits[0] if hits else None


def find_legacy(raw_name: str) -> Path | None:
    for d in LEGACY_SEG_DIRS:
        cand = d / raw_name
        if cand.is_file():
            return cand
    return None


def run_tss(raw_path: Path, out_dir: Path, device: str) -> bool:
    """Segment one scan into `out_dir`; return True on success."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "totalspineseg.inference",
        str(raw_path), str(out_dir),
        "--device", device,
        "--keep-only", KEEP_ONLY,
    ]
    print(f"    $ {' '.join(cmd)}")
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(ROOT))
    ok = proc.returncode == 0 and existing_step2(out_dir / "step2_output", raw_path.name) is not None
    print(f"    {'done' if ok else 'FAILED'} in {time.perf_counter() - t0:.0f}s")
    return ok


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scans-dir", type=Path, default=SCANS_DIR)
    p.add_argument("--out-base", type=Path, default=OUT_BASE)
    p.add_argument("--n", type=int, default=100, help="number of scans to process (default 100)")
    p.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    p.add_argument("--dry-run", action="store_true",
                   help="print the skip/segment plan and exit (no TSS)")
    args = p.parse_args(argv)

    if not args.scans_dir.is_dir():
        print(f"ERROR: scans dir not found: {args.scans_dir}", file=sys.stderr)
        return 1

    all_scans = sorted(args.scans_dir.glob("*.nii.gz"))
    scans = all_scans[: args.n]
    if not scans:
        print(f"ERROR: no .nii.gz scans in {args.scans_dir}", file=sys.stderr)
        return 1

    args.out_base.mkdir(parents=True, exist_ok=True)
    print(f"Scans dir : {args.scans_dir}")
    print(f"Output to : {args.out_base}\\<scan>\\step2_output\\")
    print(f"Selected  : first {len(scans)} of {len(all_scans)} scans\n")

    done_already, reused, to_seg = [], [], []
    for raw in scans:
        if existing_step2(per_scan_step2(args.out_base, raw.name), raw.name):
            done_already.append(raw)
        elif find_legacy(raw.name):
            reused.append(raw)
        else:
            to_seg.append(raw)

    print(f"Plan: {len(done_already)} already in output folders, "
          f"{len(reused)} reused from legacy cache, {len(to_seg)} to segment with TSS.\n")

    if args.dry_run:
        for raw in reused:
            print(f"  [reuse] {raw.name}  (copy legacy seg -> per-scan folder)")
        for raw in to_seg:
            print(f"  [TSS]   {raw.name}")
        return 0

    # 1) copy reused legacy segmentations into the per-scan folder layout (cheap, instant)
    for raw in reused:
        dst_dir = per_scan_step2(args.out_base, raw.name)
        dst_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(find_legacy(raw.name), dst_dir / raw.name)
        print(f"[reuse] {raw.name}")

    # 2) segment the rest, one scan at a time (resumable)
    segmented, failed = [], []
    for i, raw in enumerate(to_seg, 1):
        out_dir = args.out_base / scan_stem(raw.name)
        print(f"\n[{i}/{len(to_seg)}] segmenting {raw.name}")
        try:
            if run_tss(raw, out_dir, args.device):
                segmented.append(raw)
            else:
                failed.append(raw)
        except Exception as e:  # noqa: BLE001 - keep the batch going
            print(f"    ERROR: {type(e).__name__}: {e}")
            failed.append(raw)

    print("\n" + "=" * 70)
    print(f"DONE. output base: {args.out_base}")
    print(f"  already present : {len(done_already)}")
    print(f"  reused (copied) : {len(reused)}")
    print(f"  newly segmented : {len(segmented)}")
    print(f"  failed          : {len(failed)}")
    if failed:
        print("  failed scans (re-run to retry — completed ones are skipped):")
        for raw in failed:
            print(f"    {raw.name}")
    total_ok = len(done_already) + len(reused) + len(segmented)
    print(f"  segmentations available: {total_ok}/{len(scans)}")
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
