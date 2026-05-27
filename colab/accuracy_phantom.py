"""Algorithm-exactness test: measure synthetic segmentations of KNOWN geometry.

This answers "are the measurements exactly correct?" for the MEASUREMENT CODE in isolation
(it removes TotalSpineSeg from the loop). We build segmentation volumes whose disc and
vertebral-body dimensions we set ourselves, run the four group-2 components, and compare the
measured values to the ground truth we baked in. Errors here are pure algorithm error; the
expected residual is voxel quantization (~one voxel = the spacing).

What this DOES prove: the geometry math recovers known sizes (no systematic formula bug).
What this does NOT prove: accuracy on REAL data — real discs are not clean boxes and TSS has
its own segmentation error. For that you need radiologist ground-truth millimetres (see the
notes printed at the end).

    py -3.12 colab/accuracy_phantom.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import nibabel as nib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.measurements.context import load_context  # noqa: E402
from services.measurements.geometric import disc_si_height, disc_height_index, disc_ap_bulge  # noqa: E402

# labels: canal=2, C5=15, C6=16, disc C5-C6=66
LBL_CANAL, LBL_C5, LBL_C6, LBL_DISC = 2, 15, 16, 66


def build_phantom(h_disc, w_disc, h_vb, w_vb, bulge=0, spacing=1.0):
    """Box vertebrae + box disc in canonical RAS (axes: LR, AP-anterior+, SI-superior+).

    Ground-truth dimensions are in mm. With spacing=1 mm, 1 voxel = 1 mm.
    `bulge` extends the disc posteriorly past the vertebral posterior wall by that many mm.
    """
    LR, AP, SI = 21, 96, 96
    seg = np.zeros((LR, AP, SI), dtype=np.int16)
    lr = slice(5, 16)                       # 11 sagittal slices wide, midline at 10

    ap_c = 48
    vb_ap = slice(ap_c - w_vb // 2, ap_c + w_vb - w_vb // 2)          # vertebral body AP span
    disc_ap = slice(ap_c - w_disc // 2 - bulge, ap_c + w_disc - w_disc // 2)  # disc AP span (+bulge posterior)

    si_c = 48
    disc_si = slice(si_c - h_disc // 2, si_c + h_disc - h_disc // 2)
    c5_si = slice(disc_si.stop, disc_si.stop + h_vb)                  # C5 above the disc
    c6_si = slice(disc_si.start - h_vb, disc_si.start)               # C6 below the disc

    seg[lr, vb_ap, c5_si] = LBL_C5
    seg[lr, vb_ap, c6_si] = LBL_C6
    seg[lr, disc_ap, disc_si] = LBL_DISC

    # spinal canal: posterior to the bodies (smaller AP), present on the midline slices
    canal_ap = slice(vb_ap.start - 10, vb_ap.start - 3)
    seg[9:12, canal_ap, :] = LBL_CANAL

    # Ground truth in mm. The posterior `bulge` both widens the disc AP and pushes its
    # posterior margin past the vertebral wall, so account for it explicitly:
    disc_ap_span = w_disc + bulge                       # disc now spans this many voxels in AP
    protrusion_vox = max(0, bulge - (w_vb // 2 - w_disc // 2))  # past the VB posterior wall
    truth = {
        "H_disc": float(h_disc - 1) * spacing,          # SI extent = (n_voxels-1)*spacing
        "AP_disc": float(disc_ap_span - 1) * spacing,
        "DHI": (h_disc - 1) / (h_vb - 1),
        "ratio": (disc_ap_span - 1) / (w_vb - 1),
        "bulge": float(protrusion_vox) * spacing,
    }
    affine = np.diag([spacing, spacing, spacing, 1.0])
    return seg, affine, truth


def measure(seg, affine):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "phantom.nii.gz"
        nib.save(nib.Nifti1Image(seg, affine), str(p))
        ctx = load_context(str(p))
        si = disc_si_height.compute(ctx)
        prior = {"disc_si_height": si}
        dhi = disc_height_index.compute(ctx, prior); prior["disc_height_index"] = dhi
        ap = disc_ap_bulge.compute(ctx, prior)
    lvl = "C5-C6"
    return {
        "H_disc": si.measurements["disc_H_center"][lvl],
        "AP_disc": si.measurements["disc_AP_width"][lvl],
        "DHI": dhi.measurements["DHI"][lvl],
        "ratio": ap.measurements["disc_vb_ap_ratio"][lvl],
        "bulge": ap.measurements["posterior_bulge_mm"][lvl],
    }


def main() -> int:
    cases = [
        ("disc 5mm / AP 16 / VB 14x20",        dict(h_disc=5, w_disc=16, h_vb=14, w_vb=20)),
        ("disc 3mm (narrow) / AP 16",          dict(h_disc=3, w_disc=16, h_vb=14, w_vb=20)),
        ("disc 7mm (tall) / AP 18",            dict(h_disc=7, w_disc=18, h_vb=14, w_vb=20)),
        ("disc AP 20 == VB AP 20 (ratio 1.0)", dict(h_disc=5, w_disc=20, h_vb=14, w_vb=20)),
        ("posterior bulge 4mm",                dict(h_disc=5, w_disc=16, h_vb=14, w_vb=20, bulge=4)),
    ]
    keys = [("H_disc", "mm", 1.5), ("AP_disc", "mm", 1.5), ("DHI", "", 0.06),
            ("ratio", "", 0.08), ("bulge", "mm", 1.5)]

    print(f"\n{'PHANTOM ACCURACY (measured vs known ground truth)':<52}")
    print("=" * 92)
    worst = 0.0
    n_fail = 0
    for name, params in cases:
        seg, affine, truth = build_phantom(**params)
        got = measure(seg, affine)
        print(f"\n{name}")
        print(f"  {'metric':<10} {'truth':>8} {'measured':>10} {'error':>8} {'tol':>6}  ok")
        for k, unit, tol in keys:
            t, g = truth[k], got[k]
            err = abs(g - t)
            ok = err <= tol
            n_fail += (not ok)
            worst = max(worst, err if unit == "mm" else 0)
            print(f"  {k:<10} {t:>8.2f} {g:>10.2f} {err:>8.2f} {tol:>6.2f}  {'OK' if ok else 'FAIL'}")

    print("\n" + "=" * 92)
    print(f"{'ALL PHANTOMS EXACT (within voxel quantization)' if n_fail == 0 else f'{n_fail} metric(s) off'}"
          f"   worst mm error = {worst:.2f} mm")
    print("""
Interpretation:
  * Pass here = the measurement FORMULAS are correct (no systematic bug); residual is
    sub-voxel quantization. This isolates algorithm error from segmentation error.
  * It does NOT validate real-world accuracy. To test that, measure on (a) a few cases where
    a radiologist has marked disc heights/AP widths on the same MRI, then report ICC and a
    Bland-Altman bias +/- limits of agreement; and (b) ground-truth segmentation masks (if
    available) to separate TSS error from measurement error.
""")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
