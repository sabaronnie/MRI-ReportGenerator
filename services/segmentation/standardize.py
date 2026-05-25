"""Phase 1.5 — input standardization layer (runs before TotalSpineSeg).

Why this exists
---------------
Input MRIs arrive at different voxel spacings, orientations, matrix sizes, and
intensity scales. Geometry is computed in millimetres from the affine, so a
correctly-tagged image is already scale-correct — but two real problems remain:

  1. **Bad/implausible spacing metadata** (e.g. corrupt headers) make the mm
     conversion wrong, so measurements come out systematically too big/small.
  2. **Mixed in-plane resolution** biases thin-structure heights via partial
     volume (validated on SPIDER: disc-height vs voxel-size corr -0.23 at native
     resolution, +0.03 after 1 mm resampling).
Plus TotalSpineSeg and the Pfirrmann signal both behave more consistently on a
uniform input.

What it does (and does NOT do)
------------------------------
Standardizes *appearance* while **preserving true physical size**:
  - reorient to canonical RAS+,
  - resample to a fixed isotropic voxel spacing (default 1.0 mm),
  - robust intensity normalization (percentile clip -> fixed range),
  - optional conform to a fixed matrix shape (same image dimensions for all),
  - sanity-flag implausible input spacing.
It deliberately does **not** rescale the spine to a common size — physical mm
are kept, so a genuinely large spine stays large. "All inputs look similar,
except for their actual spine measurements."

This module depends only on numpy + nibabel and can run standalone or be called
between `input_handler.prepare_nifti` and `segmenter.run_totalspineseg`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import nibabel as nib
from nibabel.processing import resample_to_output, conform


# Plausible in-plane voxel spacing for clinical spine MRI (mm).
PLAUSIBLE_SPACING_MM = (0.2, 1.5)
DEFAULT_ISO_MM = 1.0
DEFAULT_INTENSITY_RANGE = (0.0, 1000.0)
DEFAULT_CLIP_PERCENTILES = (0.5, 99.5)


class StandardizationError(RuntimeError):
    """Raised when an input cannot be standardized."""


@dataclass
class StandardizationResult:
    standardized_path: Path
    orig_spacing_mm: tuple[float, float, float]
    orig_shape: tuple[int, int, int]
    orig_axcodes: str
    new_spacing_mm: tuple[float, float, float]
    new_shape: tuple[int, int, int]
    intensity_window: tuple[float, float]   # (p_low, p_high) source intensities
    flags: list[str] = field(default_factory=list)

    def as_manifest(self) -> dict:
        return {
            "standardized_path": str(self.standardized_path),
            "orig_spacing_mm": [round(s, 4) for s in self.orig_spacing_mm],
            "orig_shape": list(self.orig_shape),
            "orig_axcodes": self.orig_axcodes,
            "new_spacing_mm": [round(s, 4) for s in self.new_spacing_mm],
            "new_shape": list(self.new_shape),
            "intensity_window": [round(float(x), 2) for x in self.intensity_window],
            "flags": self.flags,
        }


def _normalize_intensity(data: np.ndarray,
                         clip_pct: tuple[float, float],
                         out_range: tuple[float, float]) -> tuple[np.ndarray, tuple[float, float]]:
    """Robust percentile normalization driven by the image's own foreground.

    Maps [p_low, p_high] of the foreground (finite, >0) intensities onto
    `out_range`. Data-driven from each scan, so different scanners/sequences end
    up on a comparable scale without touching geometry.
    """
    finite = data[np.isfinite(data)]
    fg = finite[finite > 0]
    sample = fg if fg.size > 100 else finite
    lo, hi = np.percentile(sample, clip_pct)
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo, hi = float(np.nanmin(data)), float(np.nanmax(data))
        if hi <= lo:
            return np.zeros_like(data, dtype=np.float32), (lo, hi)
    out_lo, out_hi = out_range
    clipped = np.clip(np.nan_to_num(data, nan=lo), lo, hi)
    scaled = (clipped - lo) / (hi - lo) * (out_hi - out_lo) + out_lo
    return scaled.astype(np.float32), (float(lo), float(hi))


def standardize_mri(
    nifti_path: Path | str,
    work_dir: Path | str,
    *,
    iso_mm: float = DEFAULT_ISO_MM,
    target_shape: tuple[int, int, int] | None = None,
    allow_downsample: bool = False,
    clip_percentiles: tuple[float, float] = DEFAULT_CLIP_PERCENTILES,
    intensity_range: tuple[float, float] = DEFAULT_INTENSITY_RANGE,
) -> StandardizationResult:
    """Standardize one MRI and write `<work_dir>/standardized/<name>_std.nii.gz`.

    `iso_mm`        target isotropic voxel spacing (mm) when resampling.
    `allow_downsample`  default False. When the input is already FINER than
                    `iso_mm` in-plane, resampling to `iso_mm` would throw away
                    real resolution and degrade the segmentation (validated:
                    downsampling a 0.43 mm scan to 1 mm inflated disc/VB AP
                    ratios and broke C7-T1). So by default we never downsample —
                    fine inputs keep their native grid (lossless RAS reorient
                    only), and only genuinely coarse inputs are upsampled to
                    `iso_mm`. mm geometry is affine-correct and TSS resamples to
                    1 mm internally anyway, so preserving native detail is safe.
                    Set True to force `iso_mm` regardless.
    `target_shape`  if given, conform to this exact matrix (fixed dimensions +
                    FOV) — this path always resamples to `iso_mm`.
    """
    nifti_path = Path(nifti_path).resolve()
    work_dir = Path(work_dir).resolve()
    if not nifti_path.exists():
        raise StandardizationError(f"input not found: {nifti_path}")

    img = nib.load(str(nifti_path))
    orig_spacing = tuple(float(z) for z in img.header.get_zooms()[:3])
    orig_shape = tuple(int(s) for s in img.shape[:3])
    orig_axcodes = "".join(nib.aff2axcodes(img.affine))

    flags: list[str] = []
    inplane = sorted(orig_spacing)[:2]   # two smallest = in-plane for a sagittal stack
    if any(not (PLAUSIBLE_SPACING_MM[0] <= s <= PLAUSIBLE_SPACING_MM[1]) for s in inplane):
        flags.append("implausible_input_spacing")   # likely a bad header -> mm may be untrustworthy

    # 1) + 2) reorient to RAS+ and standardize the grid (preserves physical size).
    if target_shape is not None:
        std = conform(img, out_shape=target_shape,
                      voxel_size=(iso_mm, iso_mm, iso_mm),
                      order=1, orientation="RAS")
    else:
        # Lossless reorient (axis permute/flip, no interpolation) keeps native
        # resolution exactly. Only resample if the input is coarser than target.
        canon = nib.as_closest_canonical(img)
        min_inplane = sorted(float(z) for z in canon.header.get_zooms()[:3])[:2][0]
        if allow_downsample or min_inplane >= iso_mm:
            std = resample_to_output(canon, [iso_mm, iso_mm, iso_mm], order=1)
        else:
            std = canon                      # finer than target -> preserve native
            flags.append("native_resolution_preserved")

    # 3) robust intensity normalization (data-driven from this scan)
    norm_data, window = _normalize_intensity(
        np.asarray(std.dataobj, dtype=np.float32), clip_percentiles, intensity_range)
    std = nib.Nifti1Image(norm_data, std.affine, std.header)
    std.header.set_data_dtype(np.float32)

    out_dir = work_dir / "standardized"
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = nifti_path.name
    for ext in (".nii.gz", ".nii"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
            break
    out_path = out_dir / f"{stem}_std.nii.gz"
    nib.save(std, str(out_path))

    return StandardizationResult(
        standardized_path=out_path,
        orig_spacing_mm=orig_spacing,
        orig_shape=orig_shape,
        orig_axcodes=orig_axcodes,
        new_spacing_mm=tuple(float(z) for z in std.header.get_zooms()[:3]),
        new_shape=tuple(int(s) for s in std.shape[:3]),
        intensity_window=window,
        flags=flags,
    )
