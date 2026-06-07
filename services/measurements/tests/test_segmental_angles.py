"""Tests for segmental angles from endplate-LINE fits on the segmentation.

Per adjacent pair, the angle between the upper vertebra's inferior endplate and the lower vertebra's
superior endplate (line fit, canal-cut), replacing the 2-corner AI->PI / AS->PS method.
"""

from __future__ import annotations

import numpy as np
import pytest

from services.measurements.context import MeasurementContext, MeasurementError
from services.measurements.geometric import segmental_angles


def _ctx(seg, spacing=(1.0, 1.0, 1.0)) -> MeasurementContext:
    return MeasurementContext(
        seg_path=None,
        seg_data=seg.astype(np.int32),
        seg_affine=np.eye(4),               # canonical RAS
        voxel_spacing_mm=spacing,
    )


def _five_levels() -> np.ndarray:
    # canonical RAS (LR, PA, IS): C3..C7 bodies stacked anterior, spinal canal posterior.
    seg = np.zeros((6, 34, 70), dtype=np.int32)
    for label, is0 in [(17, 4), (16, 17), (15, 30), (14, 43), (13, 56)]:   # C7 bottom .. C3 top
        seg[1:5, 18:30, is0:is0 + 11] = label
    seg[1:5, 8:14, 4:68] = 2                 # spinal canal (TSS label 2)
    return seg


def test_four_segmental_pairs_near_zero_for_parallel_bodies():
    result = segmental_angles.compute(_ctx(_five_levels()), {})
    seg_ang = result.measurements["segmental_angle"]
    assert set(seg_ang) == {"C3-C4", "C4-C5", "C5-C6", "C6-C7"}
    assert all(abs(v) < 5.0 for v in seg_ang.values())


def test_raises_when_no_pair_measurable():
    seg = np.zeros((6, 34, 70), dtype=np.int32)
    seg[1:5, 8:14, 4:68] = 2                 # canal only, no vertebrae
    with pytest.raises(MeasurementError):
        segmental_angles.compute(_ctx(seg), {})
