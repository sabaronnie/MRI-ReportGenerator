"""Tests for the integrated Group 5 vertebral-body compression screen component."""

from __future__ import annotations

import numpy as np

from services.measurements.context import MeasurementContext
from services.measurements.group5 import fracture_screen


def _ctx(seg: np.ndarray) -> MeasurementContext:
    return MeasurementContext(
        seg_path=None,
        seg_data=seg.astype(np.int32),
        seg_affine=np.eye(4),
        voxel_spacing_mm=(1.0, 1.0, 1.0),
    )


def _synthetic_seg() -> np.ndarray:
    """Simple RAS synthetic seg with one healthy and one compressed cervical body."""
    seg = np.zeros((7, 40, 40), dtype=np.int32)  # LR, AP, IS under canonical RAS

    # Posterior canal (label 2), spanning both vertebrae.
    seg[2:5, 10:15, 6:34] = 2

    # Healthy C3 body: rectangular.
    seg[2:5, 20:30, 22:34] = 13

    # Compressed C4 body: truncate the wall the screen reads as anterior (Ha) so Ha/Hp
    # drops below the compression-screen cut. Blocks swapped to match the validated
    # measure_vertebra anterior/posterior convention (Ronnie's adapter forwards orientation
    # correctly; the prior coordinates put the truncation on the posterior side -> ratio 1.74).
    seg[2:5, 20:25, 6:13] = 14
    seg[2:5, 25:30, 6:18] = 14

    return seg


def test_group5_fracture_screen_emits_ratio_and_contract():
    result = fracture_screen.compute(_ctx(_synthetic_seg()))

    assert set(result.measurements["vb_hahp_ratio"]) == {"C3", "C4"}
    assert result.measurements["vb_hahp_ratio"]["C3"] > 0.9
    assert "group5_contract" in result.metadata
    assert result.metadata["group5_contract"]["levels"][0]["fracture"]["note"]


def test_group5_fracture_screen_flags_compressed_level():
    result = fracture_screen.compute(_ctx(_synthetic_seg()))

    assert result.flags["vb_compression_screen_positive"]["C3"] is False
    assert result.flags["vb_compression_screen_positive"]["C4"] is True
