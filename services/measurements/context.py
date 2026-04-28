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


class MeasurementError(RuntimeError):
    """Raised by a measurement component when its inputs are unusable."""


@dataclass
class MeasurementContext:
    seg_path: Path | None
    seg_data: np.ndarray            # int label volume in canonical RAS
    seg_affine: np.ndarray          # 4x4 affine of the canonical-RAS volume
    voxel_spacing_mm: tuple[float, float, float]   # (LR, PA, IS) in mm
    raw_path: Path | None = None
    raw_data: np.ndarray | None = None
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


def load_context(seg_path: Path | str, raw_path: Path | str | None = None) -> MeasurementContext:
    """Load a TotalSpineSeg step2_output (and optionally the raw MRI) into a measurement context."""
    seg_path = Path(seg_path).resolve()
    seg_img = nib.as_closest_canonical(nib.load(str(seg_path)))
    seg_data = np.asarray(seg_img.dataobj).astype(np.int32)

    spacing = tuple(float(x) for x in seg_img.header.get_zooms()[:3])
    if any(s <= 0 or not np.isfinite(s) for s in spacing):
        raise MeasurementError(f"{seg_path.name}: non-finite spacing {spacing}")

    raw_data = None
    raw_path_resolved = None
    if raw_path is not None:
        raw_path_resolved = Path(raw_path).resolve()
        raw_img = nib.as_closest_canonical(nib.load(str(raw_path_resolved)))
        raw_data = np.asarray(raw_img.dataobj).astype(np.float32)

    return MeasurementContext(
        seg_path=seg_path,
        seg_data=seg_data,
        seg_affine=seg_img.affine,
        voxel_spacing_mm=spacing,
        raw_path=raw_path_resolved,
        raw_data=raw_data,
        manifest={
            "seg_shape": list(seg_data.shape),
            "voxel_spacing_mm": list(spacing),
            "labels_present": sorted(int(x) for x in np.unique(seg_data) if x != 0),
        },
    )
