"""Per-case context loaded once and passed to every measurement component.

Reorients the segmentation to canonical RAS so downstream code can rely on:
    axis 0 = L→R   (sagittal slice index, increasing rightward)
    axis 1 = P→A   (anterior-posterior, increasing anteriorly)
    axis 2 = I→S   (superior-inferior, increasing superiorly)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
from nibabel.affines import obliquity
from nibabel.processing import resample_from_to, resample_to_output


# The geometry components (slice ±1 neighbourhoods, per-slice voxel bands, 15%
# edge strips, ~1.5 mm slabs) were developed against TotalSpineSeg `--iso`
# output, i.e. 1 mm isotropic. This is the input contract for the measurement IEP.
TARGET_ISO_MM = 1.0
ISO_TOL_MM = 0.05  # spacing within this of TARGET on every axis counts as isotropic
OBLIQUE_DEG_TOL = 5.0
GRID_ALIGN_TOL = 0.02

# Acquisition slice thickness (coarsest voxel axis) above which the 1 mm
# isotropic measurement grid is interpolated through-plane rather than real
# resolution — typical of sagittal cervical T2 (~3-4 mm slices). Cases above this
# are flagged so downstream readers don't over-trust through-plane detail. This is
# an engineering quality-gate threshold, NOT a clinical cutoff.
SLICE_THICKNESS_WARN_MM = 2.0


class MeasurementError(RuntimeError):
    """Raised by a measurement component when its inputs are unusable."""


@dataclass
class MeasurementContext:
    seg_path: Path | None
    seg_data: np.ndarray            # int label volume in canonical RAS
    seg_affine: np.ndarray          # 4x4 affine of the canonical-RAS volume
    voxel_spacing_mm: tuple[float, float, float]   # (LR, PA, IS) in mm
    levels_path: Path | None = None
    raw_path: Path | None = None
    sct_canal_seg_path: Path | None = None
    sct_cord_seg_path: Path | None = None
    raw_data: np.ndarray | None = None
    # SPINEPS vertebra-instance mask (its OWN grid, not resampled): carries the thin
    # inferior-endplate sheets (instance label offset + N) the C1 Cobb fits to. Kept in
    # native orientation because the Cobb is an angle in that frame; resampling would
    # destroy the 1-voxel sheets. Absent (None) when no SPINEPS pass was run -> Cobb
    # falls back to the canal-cut endplate-line method.
    spineps_seg_path: Path | None = None
    seg_vert_data: np.ndarray | None = None
    seg_vert_axcodes: tuple | None = None
    seg_vert_zooms: tuple | None = None
    # Patient demographics captured at input (alongside the MRI). age + sex feed the
    # age/sex-dependent interpretation norms (Nell 2019 canal/SAC, PAM50 cord); height is
    # captured for the record but no cervical threshold normalizes by it (no cited norm yet).
    age: float | None = None
    sex: str | None = None
    height_cm: float | None = None
    manifest: dict = field(default_factory=dict)


@dataclass
class ComponentResult:
    """Standard output shape for every measurement component.

    measurements : numeric outputs, keyed `{measurement_name: {level_or_pair: float}}`
    intermediate : per-component state for downstream consumers (corners, axes, etc.)
    flags        : boolean flags, keyed `{flag_name: {level_or_pair: bool}}`
    metadata     : non-numeric outputs (grade strings, report lines, level lists)
    """

    measurements: dict[str, dict[str, float]]
    intermediate: dict[str, Any]
    flags: dict[str, dict[str, bool]]
    metadata: dict[str, Any] = field(default_factory=dict)


def _ensure_isotropic(seg_img: nib.Nifti1Image) -> tuple[nib.Nifti1Image, dict | None]:
    """Guarantee a ~TARGET_ISO_MM isotropic grid for the measurement geometry.

    Normal path: TotalSpineSeg ran with `--iso`, so the segmentation is already
    1 mm isotropic and this is a no-op. Guard path: a non-isotropic mask (`--iso`
    skipped, or an externally produced mask) is resampled to TARGET_ISO_MM with
    nearest-neighbour interpolation (order=0) so integer labels are preserved
    rather than blended. Returns the (possibly resampled) image and a record of
    what was done (None when no resampling was needed).
    """
    spacing = tuple(float(x) for x in seg_img.header.get_zooms()[:3])
    if all(abs(s - TARGET_ISO_MM) <= ISO_TOL_MM for s in spacing):
        return seg_img, None
    resampled = resample_to_output(seg_img, voxel_sizes=TARGET_ISO_MM, order=0)
    return resampled, {
        "from_spacing_mm": [round(s, 4) for s in spacing],
        "to_spacing_mm": [TARGET_ISO_MM] * 3,
    }


def _standardize_grid(
    img: nib.Nifti1Image,
    *,
    order: int,
) -> tuple[nib.Nifti1Image, dict | None]:
    """Resample oblique/sheared voxel grids onto an orthogonal canonical grid."""
    canonical = nib.as_closest_canonical(img)
    max_oblique_deg, max_alignment_error = _geometry_metrics(canonical.affine)
    if max_oblique_deg <= OBLIQUE_DEG_TOL and max_alignment_error <= GRID_ALIGN_TOL:
        return canonical, None

    spacing = tuple(float(x) for x in canonical.header.get_zooms()[:3])
    standardized = resample_to_output(canonical, voxel_sizes=spacing, order=order)
    standardized = nib.as_closest_canonical(standardized)
    return standardized, {
        "from_spacing_mm": [round(float(s), 4) for s in img.header.get_zooms()[:3]],
        "to_spacing_mm": [round(float(s), 4) for s in standardized.header.get_zooms()[:3]],
        "max_oblique_deg": round(max_oblique_deg, 3),
        "max_alignment_error": round(max_alignment_error, 5),
    }


def _geometry_metrics(affine: np.ndarray) -> tuple[float, float]:
    linear = np.asarray(affine[:3, :3], dtype=np.float64)
    norms = np.linalg.norm(linear, axis=0)
    if np.any(norms <= 0) or not np.all(np.isfinite(norms)):
        return float("inf"), float("inf")

    unit = linear / norms
    alignment_error = float(np.max(np.abs(unit - np.eye(3))))
    max_oblique_deg = float(np.degrees(np.max(obliquity(affine))))
    return max_oblique_deg, alignment_error


def _coerce_spacing(spacing: Any) -> tuple[float, float, float] | None:
    """Validate an externally supplied voxel spacing; return None if unusable."""
    if spacing is None:
        return None
    try:
        vals = tuple(float(x) for x in spacing)[:3]
    except (TypeError, ValueError):
        return None
    if len(vals) != 3 or any(s <= 0 or not np.isfinite(s) for s in vals):
        return None
    return vals


def _resolution_quality(
    source_spacing_mm: tuple[float, float, float] | None,
    seg_file_spacing_mm: tuple[float, float, float],
    measurement_spacing_mm: tuple[float, float, float],
) -> dict:
    """Record how trustworthy the through-plane resolution is.

    The measurement grid is forced to 1 mm isotropic, but if the *acquisition*
    slice thickness was coarse (typical sagittal cervical T2 is ~3-4 mm
    through-plane), that 1 mm grid is interpolated, not real detail. We surface
    the coarsest acquisition axis so a case can be quality-gated rather than
    silently trusted.

    source_spacing_mm   : original MRI voxel spacing (from the segmentation
                          manifest) — the authoritative slice-thickness source.
    seg_file_spacing_mm : spacing of the segmentation file as received (already
                          ~1 mm when TotalSpineSeg ran with --iso, so only a
                          best-effort fallback when the source spacing is absent).
    """
    if source_spacing_mm is not None:
        thickness = max(source_spacing_mm)
        basis = "source_mri"
    else:
        thickness = max(seg_file_spacing_mm)
        basis = "segmentation_file"
    return {
        "source_spacing_mm": [round(float(s), 4) for s in source_spacing_mm]
        if source_spacing_mm is not None
        else None,
        "segmentation_file_spacing_mm": [round(float(s), 4) for s in seg_file_spacing_mm],
        "measurement_grid_mm": [round(float(s), 4) for s in measurement_spacing_mm],
        "slice_thickness_mm": round(float(thickness), 4),
        "slice_thickness_basis": basis,
        "low_through_plane_resolution": bool(thickness > SLICE_THICKNESS_WARN_MM),
    }


def load_context(
    seg_path: Path | str,
    raw_path: Path | str | None = None,
    levels_path: Path | str | None = None,
    sct_canal_seg_path: Path | str | None = None,
    sct_cord_seg_path: Path | str | None = None,
    spineps_seg_path: Path | str | None = None,
    age: float | None = None,
    sex: str | None = None,
    height_cm: float | None = None,
    source_spacing_mm: Any = None,
) -> MeasurementContext:
    """Load a TotalSpineSeg step2_output (and optionally the raw MRI) into a measurement context.

    source_spacing_mm: the original MRI voxel spacing (e.g. from the segmentation
        manifest's input_metadata.voxel_spacing_mm). The segmentation file is
        usually already 1 mm isotropic, so this is the only way to recover the
        true acquisition slice thickness for the resolution-quality flag.
    """
    seg_path = Path(seg_path).resolve()
    source_spacing = _coerce_spacing(source_spacing_mm)

    raw_seg_img = nib.load(str(seg_path))
    seg_file_spacing_mm = tuple(float(x) for x in raw_seg_img.header.get_zooms()[:3])
    seg_img, geometry_record = _standardize_grid(raw_seg_img, order=0)

    spacing = tuple(float(x) for x in seg_img.header.get_zooms()[:3])
    if any(s <= 0 or not np.isfinite(s) for s in spacing):
        raise MeasurementError(f"{seg_path.name}: non-finite spacing {spacing}")

    seg_img, resample_record = _ensure_isotropic(seg_img)
    seg_data = np.asarray(seg_img.dataobj).astype(np.int32)
    spacing = tuple(float(x) for x in seg_img.header.get_zooms()[:3])

    raw_data = None
    raw_path_resolved = None
    if raw_path is not None:
        raw_path_resolved = Path(raw_path).resolve()
        raw_img, _ = _standardize_grid(nib.load(str(raw_path_resolved)), order=1)
        # Put the raw MRI on the (possibly resampled) segmentation grid so raw_data
        # is index-aligned with seg_data for overlays/signal work (linear interp).
        raw_img = resample_from_to(raw_img, (seg_img.shape, seg_img.affine), order=1)
        raw_data = np.asarray(raw_img.dataobj).astype(np.float32)

    levels_path_resolved = None if levels_path is None else Path(levels_path).resolve()
    sct_canal_seg_resolved = None if sct_canal_seg_path is None else Path(sct_canal_seg_path).resolve()
    sct_cord_seg_resolved = None if sct_cord_seg_path is None else Path(sct_cord_seg_path).resolve()

    # SPINEPS vertebra-instance mask (optional). Loaded in its NATIVE grid/orientation so the
    # thin endplate sheets survive; the C1 Cobb works in that frame from its own axcodes/zooms.
    spineps_seg_resolved = None
    seg_vert_data = seg_vert_axcodes = seg_vert_zooms = None
    if spineps_seg_path is not None:
        spineps_seg_resolved = Path(spineps_seg_path).resolve()
        sv_img = nib.load(str(spineps_seg_resolved))
        seg_vert_data = np.rint(np.asarray(sv_img.dataobj)).astype(np.int32)
        seg_vert_axcodes = tuple(nib.aff2axcodes(sv_img.affine))
        seg_vert_zooms = tuple(float(z) for z in sv_img.header.get_zooms()[:3])

    return MeasurementContext(
        seg_path=seg_path,
        seg_data=seg_data,
        seg_affine=seg_img.affine,
        voxel_spacing_mm=spacing,
        levels_path=levels_path_resolved,
        raw_path=raw_path_resolved,
        sct_canal_seg_path=sct_canal_seg_resolved,
        sct_cord_seg_path=sct_cord_seg_resolved,
        raw_data=raw_data,
        spineps_seg_path=spineps_seg_resolved,
        seg_vert_data=seg_vert_data,
        seg_vert_axcodes=seg_vert_axcodes,
        seg_vert_zooms=seg_vert_zooms,
        age=age,
        sex=sex,
        height_cm=height_cm,
        manifest={
            "seg_shape": list(seg_data.shape),
            "voxel_spacing_mm": list(spacing),
            "levels_path": str(levels_path_resolved) if levels_path_resolved is not None else None,
            "sct_canal_seg_path": (
                str(sct_canal_seg_resolved) if sct_canal_seg_resolved is not None else None
            ),
            "sct_cord_seg_path": (
                str(sct_cord_seg_resolved) if sct_cord_seg_resolved is not None else None
            ),
            "resolution_quality": _resolution_quality(
                source_spacing, seg_file_spacing_mm, spacing
            ),
            "geometry_standardized": geometry_record,
            "resampled_to_isotropic": resample_record,
            "labels_present": sorted(int(x) for x in np.unique(seg_data) if x != 0),
        },
    )
