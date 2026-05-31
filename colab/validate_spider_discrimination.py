"""SPIDER discrimination harness — can the pipeline identify out-of-range discs?

Runs the calibrated geometric helpers + Pfirrmann signal grading on SPIDER's expert lumbar
masks (and the matching raw T2 images) and compares the measurements to the per-disc
radiologist labels (narrowing, bulging, herniation, Pfirrmann grade 1-5):

    * narrowing (= disc smaller than normal) <- low DHI, low H_center, low H_middle
    * bulging / herniation (= disc protrudes further than normal) <- high disc/VB ratio,
      high posterior_bulge_mm
    * Pfirrmann grade  <- agreement with predicted grade (exact, within-1, Spearman)

Reports ROC AUC for each binary label and Pfirrmann agreement statistics. Writes a per-disc
CSV (measurements + labels) to spider_data/discrimination_results.csv (gitignored).

    py -3.12 colab/validate_spider_discrimination.py
    py -3.12 colab/validate_spider_discrimination.py --limit 10        # quick smoke test
"""
from __future__ import annotations

import argparse
import csv
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

import nibabel as nib
import numpy as np
import SimpleITK as sitk
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.measurements.geometric.disc_si_height import measure_disc_slice  # noqa: E402
from services.measurements.geometric.cervical_body_morphometry import (  # noqa: E402
    _largest_connected_component,
    _measure_body_slice,
    AP_AXIS,
    DISC_AP_MARGIN_MM,
    SI_AXIS,
)
from services.measurements.geometric.disc_ap_bulge import _posterior_bulge  # noqa: E402
from services.measurements.signal.pfirrmann_grade import _disc_signal_features, _grade_disc  # noqa: E402

MASKS_DIR = ROOT / "spider_data" / "masks" / "masks"
IMAGES_DIR = ROOT / "spider_data" / "images_unz" / "images"
GRADINGS_CSV = ROOT / "spider_data" / "radiological_gradings.csv"
OUT_CSV = ROOT / "spider_data" / "discrimination_results.csv"

CANAL_LABEL = 100             # SPIDER canal label (TSS uses 2; the components hard-code 2,
                              # but we work with the raw geometry helpers here.)
DISC_BASE = 200               # SPIDER per-patient disc labels are 200 + IVD index
CANAL_BAND_FRACTION = 0.70
MIN_DISC_PIXELS_2D = 9


def load_canonical(mha_path: Path):
    """SITK .mha -> canonical-RAS array + (LR, AP, SI) spacing in mm.

    SimpleITK -> NIfTI on disk -> nibabel reorient. This is the same reorientation the
    production pipeline uses (nib.as_closest_canonical), so axes match what the helpers
    expect (axis 0 = L-R, axis 1 = P-A, axis 2 = I-S).
    """
    img = sitk.ReadImage(str(mha_path))
    with tempfile.NamedTemporaryFile(suffix=".nii.gz", delete=False) as f:
        tmp = f.name
    sitk.WriteImage(img, tmp)
    try:
        nii = nib.as_closest_canonical(nib.load(tmp))
        data = np.asarray(nii.dataobj)
        spacing = tuple(float(z) for z in nii.header.get_zooms()[:3])
    finally:
        Path(tmp).unlink(missing_ok=True)
    return data, spacing


def extract_body_2d(seg_2d: np.ndarray, label: int, disc_ap_bounds, spacing_pa: float):
    """Body-isolation: trim a vertebra mask to the disc's AP region + margin (matches
    services.measurements.geometric.disc_si_height.extract_vertebral_body_slice, but takes
    an integer label rather than a cervical level name)."""
    full = (seg_2d == label)
    if not full.any():
        return None
    margin_vox = int(np.ceil(DISC_AP_MARGIN_MM / spacing_pa))
    lo = max(0, int(disc_ap_bounds[0]) - margin_vox)
    hi = min(full.shape[0] - 1, int(disc_ap_bounds[1]) + margin_vox)
    trimmed = full.copy()
    trimmed[:lo] = False
    trimmed[hi + 1:] = False
    if trimmed.any():
        return _largest_connected_component(trimmed)
    return _largest_connected_component(full)


def measure_one(seg: np.ndarray, raw: np.ndarray | None, spacing, patient_id: str, gradings):
    """Yield one row per IVD listed in `gradings` for this patient."""
    spacing_pa = float(spacing[AP_AXIS])
    spacing_si = float(spacing[SI_AXIS])

    canal3 = (seg == CANAL_LABEL)
    cps = canal3.sum(axis=(AP_AXIS, SI_AXIS))
    if cps.max() <= 0:
        return
    midband = cps >= CANAL_BAND_FRACTION * cps.max()

    # Pfirrmann normalisation (cohort intensity refs) — needs raw image with matching shape.
    csf_ref = dark_ref = None
    if raw is not None and canal3.any():
        csf_ref = float(np.percentile(raw[canal3], 95))
        dark_ref = float(np.percentile(raw[raw > 0], 5)) if np.any(raw > 0) else float(np.percentile(raw, 5))

    for g in gradings:
        k = int(g["IVD label"])
        disc_label = DISC_BASE + k
        disc3 = (seg == disc_label)
        if not disc3.any():
            continue
        areas = disc3.sum(axis=(AP_AXIS, SI_AXIS))
        masked = np.where(midband, areas, -1)
        slice_idx = int(np.argmax(masked)) if masked.max() > 0 else int(np.argmax(areas))
        disc2 = _largest_connected_component(disc3[slice_idx, :, :])
        if int(disc2.sum()) < MIN_DISC_PIXELS_2D:
            continue
        m = measure_disc_slice(disc2, slice_idx, spacing_pa, spacing_si)
        if m is None:
            continue
        ap_bounds = m["ap_bounds_voxel"]

        # adjacent vertebrae: upper = k, lower = k+1 (lower may not exist for the last disc)
        upper_body = extract_body_2d(seg[slice_idx, :, :], k, ap_bounds, spacing_pa)
        lower_body = extract_body_2d(seg[slice_idx, :, :], k + 1, ap_bounds, spacing_pa)
        ups = _measure_body_slice(f"V{k}", upper_body, slice_idx, spacing_pa, spacing_si) if upper_body is not None else None
        los = _measure_body_slice(f"V{k+1}", lower_body, slice_idx, spacing_pa, spacing_si) if lower_body is not None else None

        vb_widths = [x.AP_width for x in (ups, los) if x is not None]
        vb_heights = [x.H_middle for x in (ups, los) if x is not None]
        vb_ref = float(np.mean(vb_widths)) if vb_widths else float("nan")
        vb_h_mean = float(np.mean(vb_heights)) if vb_heights else float("nan")

        ratio = m["ap_width_mm"] / vb_ref if vb_ref and vb_ref > 0 else float("nan")
        dhi = m["h_middle_mm"] / vb_h_mean if vb_h_mean and not np.isnan(vb_h_mean) else float("nan")
        bulge, _ = _posterior_bulge(disc2, upper_body, lower_body, spacing_pa, spacing_si)

        # Pfirrmann (signal) via the calibrated lumbar cut-points.
        pf_grade = None
        if raw is not None and csf_ref is not None:
            try:
                feats = _disc_signal_features(raw[slice_idx, :, :], disc2, csf_ref, dark_ref)
                pf_grade, _ = _grade_disc(
                    nucleus_norm=feats["nucleus_norm"],
                    na_contrast_norm=feats["na_contrast_norm"],
                    heterogeneity=feats["heterogeneity"],
                    height_ratio=dhi if np.isfinite(dhi) else float("nan"),
                    region="lumbar",
                )
            except Exception:  # noqa: BLE001
                pf_grade = None

        yield {
            "patient": patient_id, "ivd": k,
            "H_center_mm": round(float(m["h_center_mm"]), 3),
            "H_middle_mm": round(float(m["h_middle_mm"]), 3),
            "AP_width_mm": round(float(m["ap_width_mm"]), 3),
            "DHI": round(dhi, 4) if np.isfinite(dhi) else None,
            "disc_vb_ratio": round(ratio, 3) if np.isfinite(ratio) else None,
            "posterior_bulge_mm": round(float(bulge), 3),
            "pfirrmann_pred": pf_grade,
            "gt_narrowing": int(g["Disc narrowing"]),
            "gt_bulging": int(g["Disc bulging"]),
            "gt_herniation": int(g["Disc herniation"]),
            "gt_pfirrmann": int(g["Pfirrman grade"]),
        }


def _auc(rows, label_key, score_fn, invert=False):
    y, s = [], []
    for r in rows:
        yi, si = r[label_key], score_fn(r)
        if yi is None or si is None:
            continue
        y.append(int(yi))
        s.append(-float(si) if invert else float(si))
    if len(set(y)) < 2 or len(y) < 10:
        return None, len(y)
    return float(roc_auc_score(y, s)), len(y)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--limit", type=int, default=0, help="process at most N patients (0=all)")
    p.add_argument("--no-raw", action="store_true", help="skip raw-image load (no Pfirrmann)")
    args = p.parse_args(argv)

    gp = defaultdict(list)
    for r in csv.DictReader(open(GRADINGS_CSV, encoding="utf-8")):
        gp[r["Patient"]].append(r)
    pids = sorted(gp.keys(), key=lambda s: int(s))
    if args.limit:
        pids = pids[: args.limit]
    print(f"SPIDER patients with gradings: {len(gp)}; processing {len(pids)} now.")

    rows, n_ok, n_pf = [], 0, 0
    for i, pid in enumerate(pids, 1):
        seg_path = MASKS_DIR / f"{pid}_t2.mha"
        if not seg_path.is_file():
            continue
        try:
            seg, spacing = load_canonical(seg_path)
            seg = seg.astype(np.int32)
            raw = None
            if not args.no_raw:
                img_path = IMAGES_DIR / f"{pid}_t2.mha"
                if img_path.is_file():
                    raw, _ = load_canonical(img_path)
                    if raw.shape != seg.shape:
                        raw = None
                    else:
                        raw = raw.astype(np.float32)
            before = len(rows)
            for row in measure_one(seg, raw, spacing, pid, gp[pid]):
                rows.append(row)
                if row["pfirrmann_pred"] is not None:
                    n_pf += 1
            if len(rows) > before:
                n_ok += 1
            if i % 25 == 0 or i == len(pids):
                print(f"  processed {i}/{len(pids)} patients, {len(rows)} disc rows so far")
        except Exception as e:  # noqa: BLE001
            print(f"  [skip] patient {pid}: {type(e).__name__}: {e}")

    if not rows:
        print("No measurements produced; nothing to score."); return 1

    keys = list(rows[0].keys())
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(rows)
    print(f"\nWrote {len(rows)} disc rows from {n_ok} patients -> {OUT_CSV}")

    # ---- discrimination scorecard ----
    print("\n" + "=" * 78)
    print("SPIDER DISCRIMINATION (ROC AUC against radiologist per-disc labels)")
    print("=" * 78)

    def show(name, auc, n):
        if auc is None:
            print(f"  {name:<46}  insufficient data (n={n})")
        else:
            print(f"  {name:<46}  AUC = {auc:.3f}   (n={n})")

    # narrowing (smaller-than-normal): low height/DHI should flag it
    show("narrowing  predicted by  -DHI",        *_auc(rows, "gt_narrowing", lambda r: r["DHI"], invert=True))
    show("narrowing  predicted by  -H_center",   *_auc(rows, "gt_narrowing", lambda r: r["H_center_mm"], invert=True))
    show("narrowing  predicted by  -H_middle",   *_auc(rows, "gt_narrowing", lambda r: r["H_middle_mm"], invert=True))
    # bulging (larger-than-normal AP): high ratio / bulge
    show("bulging    predicted by  disc/VB ratio",  *_auc(rows, "gt_bulging", lambda r: r["disc_vb_ratio"]))
    show("bulging    predicted by  posterior_bulge", *_auc(rows, "gt_bulging", lambda r: r["posterior_bulge_mm"]))
    # herniation
    show("herniation predicted by  disc/VB ratio",   *_auc(rows, "gt_herniation", lambda r: r["disc_vb_ratio"]))
    show("herniation predicted by  posterior_bulge", *_auc(rows, "gt_herniation", lambda r: r["posterior_bulge_mm"]))

    # Pfirrmann agreement (predicted vs labelled grade)
    pairs = [(r["gt_pfirrmann"], r["pfirrmann_pred"]) for r in rows if r["pfirrmann_pred"] is not None]
    if pairs:
        from scipy.stats import spearmanr
        exact = sum(1 for g, q in pairs if g == q) / len(pairs)
        within1 = sum(1 for g, q in pairs if abs(g - q) <= 1) / len(pairs)
        rho, _ = spearmanr([p[0] for p in pairs], [p[1] for p in pairs])
        print(f"\n  Pfirrmann (lumbar GT-calibrated)              "
              f"n={len(pairs)}  exact={exact:.0%}  within-1={within1:.0%}  Spearman={rho:.2f}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
