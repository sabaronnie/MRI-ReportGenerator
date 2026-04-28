"""Tests for the spondylolisthesis component.

Unit tests use hand-built fake body-morphometry outputs so the spondy logic is
exercised in isolation. One integration test builds a synthetic two-vertebra
segmentation and runs the body-morphometry -> spondy chain end-to-end.
"""

from __future__ import annotations

import nibabel as nib
import numpy as np
import pytest

from services.measurements.context import (
    ComponentResult,
    MeasurementContext,
    MeasurementError,
    load_context,
)
from services.measurements.geometric import cervical_body_morphometry, spondylolisthesis


# ---------------------------------------------------------------- helpers ----


def _fake_body_morphometry(corner_voxels: dict, ap_widths: dict) -> ComponentResult:
    return ComponentResult(
        measurements={"AP_width": ap_widths},
        intermediate={"corners_voxel": corner_voxels},
        flags={},
        metadata={},
    )


def _stub_ctx(spacing=(1.0, 1.0, 1.0)) -> MeasurementContext:
    return MeasurementContext(
        seg_path=None,
        seg_data=np.zeros((1, 1, 1), dtype=np.int32),
        seg_affine=np.eye(4),
        voxel_spacing_mm=spacing,
    )


# Fixed corner positions: both bodies AP=20 mm wide, IS=18 mm tall, IS-stacked.
# C4 baseline: PA range [20, 40), IS range [-1, 17). PS_lower at min PA, max IS.
# C3 stacked above with optional AP shift.
def _corners_for_pair(c3_pa_offset: int) -> dict:
    c4 = {
        "PI":    (12, 20, -1),
        "PS":    (12, 20, 17),
        "AS":    (12, 40, 17),
        "AI":    (12, 40, -1),
        "M_sup": (12, 30, 17),
        "M_inf": (12, 30, -1),
    }
    c3 = {
        "PI":    (12, 20 + c3_pa_offset, 17),
        "PS":    (12, 20 + c3_pa_offset, 35),
        "AS":    (12, 40 + c3_pa_offset, 35),
        "AI":    (12, 40 + c3_pa_offset, 17),
        "M_sup": (12, 30 + c3_pa_offset, 35),
        "M_inf": (12, 30 + c3_pa_offset, 17),
    }
    return {"C3": c3, "C4": c4}


# ------------------------------------------------------------- unit tests ----


def test_anterolisthesis_3mm_grade_I():
    fake = _fake_body_morphometry(_corners_for_pair(c3_pa_offset=3), {"C3": 20.0, "C4": 20.0})
    r = spondylolisthesis.compute(_stub_ctx(), {"cervical_body_morphometry": fake})
    assert r.measurements["spondy_slip_mm"]["C3-C4"] == pytest.approx(3.0)
    assert r.measurements["spondy_pct_of_lower_AP"]["C3-C4"] == pytest.approx(15.0)
    assert r.metadata["spondy_direction"]["C3-C4"] == "anterolisthesis"
    assert r.metadata["spondy_meyerding_grade"]["C3-C4"] == "I"
    assert r.flags["spondylolisthesis_present"]["C3-C4"] is True


def test_retrolisthesis_signed_negative():
    fake = _fake_body_morphometry(_corners_for_pair(c3_pa_offset=-3), {"C3": 20.0, "C4": 20.0})
    r = spondylolisthesis.compute(_stub_ctx(), {"cervical_body_morphometry": fake})
    assert r.measurements["spondy_slip_mm"]["C3-C4"] == pytest.approx(-3.0)
    assert r.metadata["spondy_direction"]["C3-C4"] == "retrolisthesis"


def test_neutral_below_1mm_threshold():
    fake = _fake_body_morphometry(_corners_for_pair(c3_pa_offset=0), {"C3": 20.0, "C4": 20.0})
    r = spondylolisthesis.compute(_stub_ctx(), {"cervical_body_morphometry": fake})
    assert r.measurements["spondy_slip_mm"]["C3-C4"] == pytest.approx(0.0)
    assert r.metadata["spondy_direction"]["C3-C4"] == "neutral"
    assert r.flags["spondylolisthesis_present"]["C3-C4"] is False


def test_voxel_spacing_scales_slip():
    fake = _fake_body_morphometry(_corners_for_pair(c3_pa_offset=2), {"C3": 20.0, "C4": 20.0})
    r = spondylolisthesis.compute(_stub_ctx(spacing=(1.0, 0.7, 0.7)), {"cervical_body_morphometry": fake})
    assert r.measurements["spondy_slip_mm"]["C3-C4"] == pytest.approx(1.4)


def test_meyerding_grade_thresholds():
    g = spondylolisthesis._meyerding_grade
    assert g(0.0) == "I"
    assert g(24.99) == "I"
    assert g(25.0) == "II"
    assert g(49.99) == "II"
    assert g(50.0) == "III"
    assert g(74.99) == "III"
    assert g(75.0) == "IV"
    assert g(99.99) == "IV"
    assert g(100.0) == "V"
    assert g(150.0) == "V"


def test_grade_5_spondyloptosis():
    # 25 mm slip on a 20 mm lower body → 125% → Grade V
    fake = _fake_body_morphometry(_corners_for_pair(c3_pa_offset=25), {"C3": 20.0, "C4": 20.0})
    r = spondylolisthesis.compute(_stub_ctx(), {"cervical_body_morphometry": fake})
    assert r.measurements["spondy_slip_mm"]["C3-C4"] == pytest.approx(25.0)
    assert r.metadata["spondy_meyerding_grade"]["C3-C4"] == "V"


def test_missing_body_morphometry_raises():
    with pytest.raises(MeasurementError, match="cervical_body_morphometry"):
        spondylolisthesis.compute(_stub_ctx(), {})


def test_skips_pair_with_missing_corners():
    fake = _fake_body_morphometry(
        corner_voxels={
            "C3": {},  # corner extraction failed for C3
            "C4": _corners_for_pair(0)["C4"],
            "C5": {  # placed below C4, IS-shifted
                "PI": (12, 20, -19), "PS": (12, 20, -1),
                "AS": (12, 40, -1),  "AI": (12, 40, -19),
                "M_sup": (12, 30, -1), "M_inf": (12, 30, -19),
            },
        },
        ap_widths={"C4": 20.0, "C5": 20.0},
    )
    r = spondylolisthesis.compute(_stub_ctx(), {"cervical_body_morphometry": fake})
    assert "C3-C4" not in r.measurements["spondy_slip_mm"]
    assert "C4-C5" in r.measurements["spondy_slip_mm"]


def test_unknown_grade_when_ap_width_missing():
    fake = _fake_body_morphometry(
        _corners_for_pair(c3_pa_offset=3),
        {"C3": 20.0},  # C4 AP_width absent
    )
    r = spondylolisthesis.compute(_stub_ctx(), {"cervical_body_morphometry": fake})
    assert r.metadata["spondy_meyerding_grade"]["C3-C4"] == "?"


def test_caveat_is_in_every_report_line():
    fake = _fake_body_morphometry(_corners_for_pair(c3_pa_offset=3), {"C3": 20.0, "C4": 20.0})
    r = spondylolisthesis.compute(_stub_ctx(), {"cervical_body_morphometry": fake})
    line = r.metadata["spondy_report_lines"]["C3-C4"]
    assert "supine MRI" in line
    assert "Lattig" in line


# ---------------------------------------------------- integration test --


def _build_two_vertebra_seg(tmp_path, ap_offset_voxels=0):
    """Synthetic seg: rectangular C3 stacked above C4 with optional AP offset."""
    LR, PA, IS = 25, 80, 80
    seg = np.zeros((LR, PA, IS), dtype=np.int16)
    lr_c, pa_c, is_c = LR // 2, PA // 2, IS // 2
    body_lr = slice(lr_c - 5, lr_c + 6)

    c4_pa = slice(pa_c - 10, pa_c + 10)
    c4_is = slice(is_c - 22, is_c - 4)
    seg[body_lr, c4_pa, c4_is] = 14

    c3_pa = slice(pa_c - 10 + ap_offset_voxels, pa_c + 10 + ap_offset_voxels)
    c3_is = slice(is_c + 4, is_c + 22)
    seg[body_lr, c3_pa, c3_is] = 13

    disc_pa = slice(min(c3_pa.start, c4_pa.start), max(c3_pa.stop, c4_pa.stop))
    seg[body_lr, disc_pa, is_c - 4:is_c + 4] = 64

    seg[body_lr, c3_pa, c3_is.stop:c3_is.stop + 4] = 63
    seg[body_lr, c4_pa, c4_is.start - 4:c4_is.start] = 65

    canal_pa_stop = max(0, min(c3_pa.start, c4_pa.start) - 6)
    if canal_pa_stop > 0:
        canal_pa = slice(0, canal_pa_stop)
        for s in (lr_c - 1, lr_c, lr_c + 1):
            seg[s, canal_pa, :] = 2

    nib.save(nib.Nifti1Image(seg, np.eye(4)), str(tmp_path / "step2_output.nii.gz"))
    return tmp_path / "step2_output.nii.gz"


def test_integration_3mm_anterolisthesis(tmp_path):
    seg_path = _build_two_vertebra_seg(tmp_path, ap_offset_voxels=3)
    ctx = load_context(seg_path)

    morphometry_result = cervical_body_morphometry.compute(ctx)
    assert {"C3", "C4"}.issubset(set(morphometry_result.metadata["levels"]))

    spondy = spondylolisthesis.compute(ctx, {"cervical_body_morphometry": morphometry_result})
    slip = spondy.measurements["spondy_slip_mm"]["C3-C4"]
    assert slip == pytest.approx(3.0, abs=1.0)
    assert spondy.metadata["spondy_direction"]["C3-C4"] == "anterolisthesis"
    assert spondy.metadata["spondy_meyerding_grade"]["C3-C4"] in ("I", "II")
