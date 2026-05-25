"""CLI runner for the segmentation IEP — used to prove the pipeline on one case.

Usage:
    python -m services.segmentation.cli <input> <output_dir> [--no-iso]

Exit code 0 on success, 1 on any input or segmentation error.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .input_handler import InputError, prepare_nifti
from .segmenter import SegmentationError, run_totalspineseg
from .standardize import StandardizationError, standardize_mri


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run input handling + TotalSpineSeg on one case.")
    parser.add_argument("input", help="Path to NIfTI file (.nii/.nii.gz) or DICOM folder")
    parser.add_argument("output_dir", help="Working/output directory (created if missing)")
    parser.add_argument(
        "--no-iso",
        action="store_true",
        help="Disable TotalSpineSeg --iso (1mm-isotropic resampling). Default: --iso enabled.",
    )
    parser.add_argument(
        "--no-standardize",
        action="store_true",
        help="Skip the Phase 1.5 standardization layer (reorient + iso resample + "
             "intensity normalize) and feed the raw NIfTI to TotalSpineSeg.",
    )
    parser.add_argument(
        "--iso-mm", type=float, default=1.0,
        help="Target isotropic voxel spacing (mm) for standardization. Default 1.0.",
    )
    args = parser.parse_args(argv)

    try:
        metadata = prepare_nifti(Path(args.input), Path(args.output_dir))
        print(
            f"Input OK: {metadata.nifti_path.name} "
            f"shape={metadata.shape} spacing_mm={metadata.voxel_spacing_mm} "
            f"axes={metadata.canonical_axes}"
        )
        seg_input = metadata.nifti_path
        if not args.no_standardize:
            std = standardize_mri(metadata.nifti_path, Path(args.output_dir),
                                  iso_mm=args.iso_mm)
            seg_input = std.standardized_path
            print(
                f"Standardized: {seg_input.name} "
                f"spacing_mm={std.orig_spacing_mm}->{std.new_spacing_mm} "
                f"shape={std.orig_shape}->{std.new_shape} axes={std.orig_axcodes}->RAS"
                + (f"  FLAGS={std.flags}" if std.flags else "")
            )
        result = run_totalspineseg(
            seg_input, Path(args.output_dir), iso=not args.no_iso
        )
    except (InputError, StandardizationError, SegmentationError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print("Segmentation OK:")
    print(f"  step2_output: {result.step2_output}")
    print(f"  step1_levels: {result.step1_levels}")
    if result.iso_input:
        print(f"  iso_input:    {result.iso_input}")
    print(f"  cervical labels present: {result.cervical_labels_present}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
