"""CLI runner for the SCT segmentation IEP.

Usage:
    python -m services.segmentation.sct_cli <input_iso.nii.gz> <output_dir>

Exit code 0 on success, 1 on any SCT error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .sct_segmenter import SCTSegmentationError, run_sct_segmentations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run SCT canal + cord segmentation on one case.")
    parser.add_argument("input_iso", help="Path to the 1 mm isotropic MRI volume (e.g. TSS input_iso)")
    parser.add_argument("output_dir", help="Working/output directory (created if missing)")
    args = parser.parse_args(argv)

    try:
        result = run_sct_segmentations(Path(args.input_iso), Path(args.output_dir))
    except SCTSegmentationError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print("SCT segmentation OK:")
    print(f"  canal: {result.canal_seg}")
    print(f"  cord:  {result.cord_seg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
