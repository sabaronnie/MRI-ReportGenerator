"""Tests for the Phase 1.5 standardization layer.

Key property under test: standardization makes inputs *look* uniform
(orientation, voxel spacing, intensity scale) while **preserving true physical
size** — a box of known mm dimensions measures the same mm after
standardization. That is exactly what lets us standardize "zoom" without
corrupting the real spine measurements.

Run:  py -3.12 services/segmentation/tests/test_standardize.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import nibabel as nib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from standardize import standardize_mri  # noqa: E402

FAILURES: list[str] = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  -- {detail}" if detail and not cond else ""))
    if not cond:
        FAILURES.append(name)


def _save(data, affine) -> str:
    p = Path(tempfile.mkdtemp()) / "in.nii.gz"
    nib.save(nib.Nifti1Image(data, affine), str(p))
    return str(p)


def test_fine_input_preserved_and_normalized():
    print("\n[1] fine input: native res preserved (no downsample) + mm size kept")
    # RAS-diagonal affine, in-plane 0.5mm (finer than 1.0 target) x 3.0mm slice.
    data = np.zeros((40, 60, 16), dtype=np.float32)
    data[10:30, 20:50, 4:12] = 600.0          # box: 20*.5=10mm, 30*.5=15mm, 8*3=24mm
    affine = np.diag([0.5, 0.5, 3.0, 1.0])
    res = standardize_mri(_save(data, affine), Path(tempfile.mkdtemp()), iso_mm=1.0)

    out = nib.load(str(res.standardized_path))
    sp = [round(z, 3) for z in out.header.get_zooms()[:3]]
    check("fine input NOT downsampled (0.5mm kept)", sp[0] <= 0.5 + 1e-6, str(sp))
    check("native_resolution_preserved flagged",
          "native_resolution_preserved" in res.flags, str(res.flags))
    check("output is RAS", "".join(nib.aff2axcodes(out.affine)) == "RAS",
          "".join(nib.aff2axcodes(out.affine)))
    od = np.asarray(out.dataobj)
    check("intensity within target range", od.min() >= -1e-3 and od.max() <= 1000.5,
          f"[{od.min():.1f},{od.max():.1f}]")
    coords = np.argwhere(od > 500)
    ext = (coords.max(0) - coords.min(0) + 1).astype(float) * np.array(sp)   # mm
    check("R extent ~10 mm preserved", abs(ext[0] - 10) <= 2, f"{ext[0]:.1f}")
    check("A extent ~15 mm preserved", abs(ext[1] - 15) <= 2, f"{ext[1]:.1f}")
    check("S extent ~24 mm preserved", abs(ext[2] - 24) <= 3, f"{ext[2]:.1f}")


def test_coarse_input_upsampled():
    print("\n[1b] coarse input IS upsampled to iso (1.5mm in-plane -> 1.0mm)")
    data = np.zeros((20, 40, 40), dtype=np.float32)
    data[5:15, 10:30, 10:30] = 500.0
    affine = np.diag([1.5, 1.5, 3.0, 1.0])     # coarser than target -> upsample
    res = standardize_mri(_save(data, affine), Path(tempfile.mkdtemp()), iso_mm=1.0)
    out = nib.load(str(res.standardized_path))
    sp = tuple(round(z, 3) for z in out.header.get_zooms()[:3])
    check("coarse input upsampled to 1mm iso", sp == (1.0, 1.0, 1.0), str(sp))
    check("not native-preserved", "native_resolution_preserved" not in res.flags, str(res.flags))


def test_reorients_nonras_to_ras():
    print("\n[2] reorients a non-RAS input to RAS")
    data = np.zeros((30, 40, 20), dtype=np.float32)
    data[5:25, 10:30, 5:15] = 400.0
    # non-RAS affine (columns -> A, S, R): axcodes ~ ('A','S','R')
    affine = np.array([[0, 0, 0.6, 0],
                       [0.5, 0, 0, 0],
                       [0, 1.0, 0, 0],
                       [0, 0, 0, 1.0]], dtype=float)
    src_ax = "".join(nib.aff2axcodes(affine))
    res = standardize_mri(_save(data, affine), Path(tempfile.mkdtemp()), iso_mm=1.0)
    out = nib.load(str(res.standardized_path))
    check(f"non-RAS input ({src_ax}) -> RAS output",
          "".join(nib.aff2axcodes(out.affine)) == "RAS", res.orig_axcodes)


def test_flags_implausible_spacing():
    print("\n[3] flags implausible input spacing")
    data = np.zeros((20, 40, 40), dtype=np.float32)
    data[5:15, 10:30, 10:30] = 300.0
    affine = np.diag([0.05, 0.05, 4.0, 1.0])   # 0.05mm in-plane = physically implausible
    res = standardize_mri(_save(data, affine), Path(tempfile.mkdtemp()), iso_mm=1.0)
    check("implausible_input_spacing flagged",
          "implausible_input_spacing" in res.flags, str(res.flags))


def test_conform_fixed_shape():
    print("\n[4] conform to a fixed matrix shape (same dimensions for all)")
    data = np.zeros((40, 50, 18), dtype=np.float32)
    data[10:30, 15:35, 4:12] = 500.0
    res = standardize_mri(_save(data, np.diag([0.6, 0.6, 3.0, 1.0])),
                          Path(tempfile.mkdtemp()), iso_mm=1.0,
                          target_shape=(64, 256, 256))
    out = nib.load(str(res.standardized_path))
    check("output matches target shape", tuple(out.shape) == (64, 256, 256), str(out.shape))


if __name__ == "__main__":
    test_fine_input_preserved_and_normalized()
    test_coarse_input_upsampled()
    test_reorients_nonras_to_ras()
    test_flags_implausible_spacing()
    test_conform_fixed_shape()
    print("\n" + "=" * 56)
    if FAILURES:
        print(f"FAILED {len(FAILURES)}: {FAILURES}")
        raise SystemExit(1)
    print("ALL CHECKS PASSED")
