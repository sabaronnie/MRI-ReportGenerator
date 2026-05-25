"""
Colab-ready cervical vertebral body measurements (C3-C7).

Goal:
- Maximize geometric accuracy on sagittal T2 MRI + TotalSpineSeg labels.
- Keep the measurement definitions as close as possible to validated methods.

Primary measurement conventions used here:
- Vertebral heights:
  Genant-style 3-point vertebral morphometry
  (anterior / middle / posterior heights from a 6-point body outline method).
- Vertebral AP width:
  SHIP-style vertebral-body AP width measured through the craniocaudal center
  of the body, implemented as AP span in a thin SI slab around the body center.

Practical robustness additions:
- Canonical-RAS reorientation before any geometry.
- 3D disc-anchored body isolation to exclude posterior arch / spinous process.
- Midline-band candidate slice search using canal visibility.
- Quality-scored reference-slice choice with robust support-slice aggregation.

References:
- Genant HK et al. J Bone Miner Res. 1993. PMID: 8237484
- Nell C et al. PLoS One. 2019. doi:10.1371/journal.pone.0222682
- Huang J et al. Spine J. 2020. doi:10.1016/j.spinee.2019.11.010
"""

import os
import json
from dataclasses import dataclass

import matplotlib.pyplot as plt
import nibabel as nib
import nibabel.processing as nibp
import numpy as np
import pandas as pd
from scipy.ndimage import label as cc_label

try:
    from IPython.display import display
except ImportError:
    display = print


# =========================
# EDIT THESE FOR EACH SCAN
# =========================
# Option A — point at a per-scan TotalSpineSeg output folder on Drive.
# This script now supports both:
# - the new Colab layout with `run_manifest.json` + `segmentation_final.nii.gz`
# - the older TotalSpineSeg layout with `step2_output/`, `step1_output/`, etc.
SCAN_OUTPUT_DIR = "/content/drive/MyDrive/503N-Proj/cspineseg_totalspineseg_outputs/593973-001232_Study-MR-1255_Series-5"

# Option B — explicit overrides. If both are non-empty, they take precedence
# over SCAN_OUTPUT_DIR. Use this when your files live outside a TSS run folder.
MRI_PATH_OVERRIDE = ""
SEG_PATH_OVERRIDE = ""


def _resolve_scan_paths(scan_dir, mri_override, seg_override):
    if mri_override and seg_override:
        return mri_override, seg_override

    manifest_path = os.path.join(scan_dir, "run_manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            manifest = json.load(f)

        mri = manifest.get("input_mri")
        seg = manifest.get("final_segmentation") or manifest.get("source_segmentation_file")

        if mri and seg and os.path.exists(mri) and os.path.exists(seg):
            return mri, seg

    seg_candidates = [
        os.path.join(scan_dir, "segmentation_final.nii.gz"),
        os.path.join(scan_dir, "step2_output", "scan.nii.gz"),
        os.path.join(scan_dir, "step1_output", "scan.nii.gz"),
    ]
    seg = next((p for p in seg_candidates if os.path.exists(p)), None)
    if seg is None:
        raise FileNotFoundError(
            f"No segmentation found under {scan_dir}. Tried segmentation_final.nii.gz, "
            f"step2_output/, and step1_output/. Set SEG_PATH_OVERRIDE if your file is elsewhere."
        )

    mri_candidates = [
        os.path.join(scan_dir, "input_raw", "scan_0000.nii.gz"),
        os.path.join(scan_dir, "step2_raw", "scan.nii.gz"),
        os.path.join(scan_dir, "input", "scan_0000.nii.gz"),
    ]
    mri = next((p for p in mri_candidates if os.path.exists(p)), None)
    if mri is None and os.path.exists(manifest_path):
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        mri = manifest.get("input_mri")
        if mri and not os.path.exists(mri):
            mri = None
    if mri is None:
        raise FileNotFoundError(
            f"No MRI found under {scan_dir}. Tried run_manifest.json, input_raw/, step2_raw/, "
            f"and input/. Set MRI_PATH_OVERRIDE if your file is elsewhere."
        )

    return mri, seg


MRI_PATH, SEG_PATH = _resolve_scan_paths(SCAN_OUTPUT_DIR, MRI_PATH_OVERRIDE, SEG_PATH_OVERRIDE)
print(f"MRI: {MRI_PATH}")
print(f"SEG: {SEG_PATH}")


LEVEL_LABELS = {"C3": 13, "C4": 14, "C5": 15, "C6": 16, "C7": 17}
DISC_NEIGHBOURS = {
    "C3": (63, 64),
    "C4": (64, 65),
    "C5": (65, 66),
    "C6": (66, 67),
    "C7": (67, 71),
}
CANAL_LABELS = [1, 2]  # spinal cord + CSF in TSS

DISC_AP_MARGIN_MM = 2.0
CANAL_BAND_FRACTION = 0.70
EDGE_STRIP_FRACTION = 0.15
MID_AP_SLAB_MM = 1.5
MID_SI_SLAB_MM = 1.5
MIN_BODY_PIXELS_2D = 25
SUPPORT_AREA_FRACTION = 0.75
SUPPORT_SCORE_FRACTION = 0.72
MAX_SUPPORT_TILT_DEG = 18.0
MAX_SUPPORT_MISMATCH_MM = 2.5


# =========================
# Load in canonical RAS
# =========================
raw_img = nib.as_closest_canonical(nib.load(MRI_PATH))
seg_img = nib.as_closest_canonical(nib.load(SEG_PATH))

if raw_img.shape != seg_img.shape:
    raw_img = nibp.resample_from_to(raw_img, seg_img, order=1)

MRI_3D = np.asarray(raw_img.dataobj).astype(np.float32)
SEG_3D = np.asarray(seg_img.dataobj).astype(np.int32)

# Canonical RAS guarantees:
# axis 0 = L->R  (sagittal slice index)
# axis 1 = P->A  (AP axis, increasing anteriorly)
# axis 2 = I->S  (SI axis, increasing superiorly)
SAG_AXIS = 0
AP_AXIS = 1
SI_AXIS = 2

SPACING_LR, SPACING_AP, SPACING_SI = [float(x) for x in seg_img.header.get_zooms()[:3]]


# =========================
# Helpers
# =========================
@dataclass
class SliceMeasurement:
    level: str
    slice_idx: int
    AP_width: float
    H_anterior: float
    H_middle: float
    H_posterior: float
    tilt_deg: float
    points_mm: dict
    points_voxel_2d: dict
    body_mask_2d: np.ndarray
    AP_only: float
    AP_si_mismatch: float
    body_area_px: int
    bbox_fill_ratio: float
    ap_range_mm: float
    si_range_mm: float


def largest_connected_component(mask):
    labeled, n = cc_label(mask)
    if n <= 1:
        return mask
    sizes = np.bincount(labeled.ravel())
    sizes[0] = 0
    return labeled == int(np.argmax(sizes))


def normalize_mri(arr):
    lo, hi = np.percentile(arr, [1, 99])
    return np.clip((arr - lo) / max(hi - lo, 1e-6), 0, 1)


def dist_mm(a, b):
    return float(np.hypot(a[0] - b[0], a[1] - b[1]))


def _argbreak(mask, values, mode, tiebreak, tb_mode):
    idx = np.where(mask)[0]
    sub = values[idx]
    target = sub.max() if mode == "max" else sub.min()
    candidates = idx[sub == target]
    tb = tiebreak[candidates]
    return int(candidates[np.argmax(tb) if tb_mode == "max" else np.argmin(tb)])


def take_sagittal_slice(vol, idx):
    return vol[idx, :, :]


# =========================
# 1) Midline-band slice selection
# =========================
canal_3d = np.isin(SEG_3D, CANAL_LABELS)
canal_per_slice = canal_3d.sum(axis=(AP_AXIS, SI_AXIS))
canal_peak = int(canal_per_slice.max())
if canal_peak == 0:
    raise RuntimeError("Canal labels absent; cannot select a reliable midline band.")
MIDLINE_BAND = canal_per_slice >= CANAL_BAND_FRACTION * canal_peak


# =========================
# 2) 3D body isolation
# =========================
def isolate_body_3d(seg_3d, level):
    label = LEVEL_LABELS[level]
    vertebra = seg_3d == label
    if not vertebra.any():
        return None

    disc_ids = [d for d in DISC_NEIGHBOURS[level] if d is not None]
    disc_mask = np.isin(seg_3d, disc_ids)
    if not disc_mask.any():
        return None

    ap_idx = np.where(disc_mask)[AP_AXIS]
    ap_lo = int(ap_idx.min())
    ap_hi = int(ap_idx.max())

    margin_vox = int(np.ceil(DISC_AP_MARGIN_MM / SPACING_AP))
    ap_lo = max(0, ap_lo - margin_vox)
    ap_hi = min(seg_3d.shape[AP_AXIS] - 1, ap_hi + margin_vox)

    ap_filter = np.zeros(seg_3d.shape[AP_AXIS], dtype=bool)
    ap_filter[ap_lo:ap_hi + 1] = True
    body_3d = vertebra & ap_filter[None, :, None]

    return body_3d if body_3d.any() else None


def candidate_slice_indices(body_3d):
    body_per_slice = body_3d.sum(axis=(AP_AXIS, SI_AXIS))
    return [int(s) for s in np.where(MIDLINE_BAND & (body_per_slice > 0))[0]]


def score_slice_quality(m, area_max):
    # Favor large, compact body cross-sections and penalize oblique / off-center
    # width picks that usually come from sliver-like sagittal cuts.
    area_term = m.body_area_px / max(area_max, 1)
    penalty = 1.0 + 0.05 * m.tilt_deg + 0.25 * m.AP_si_mismatch
    return (area_term * m.bbox_fill_ratio) / penalty


def choose_reference_and_support_slices(valid):
    if not valid:
        return None, []

    area_max = max(m.body_area_px for m in valid)
    scored = [(m, score_slice_quality(m, area_max)) for m in valid]
    scored.sort(
        key=lambda item: (
            item[1],
            item[0].body_area_px,
            item[0].bbox_fill_ratio,
            -item[0].tilt_deg,
            -item[0].AP_si_mismatch,
        ),
        reverse=True,
    )
    reference_slice, reference_score = scored[0]

    support = []
    for m, score in scored:
        if abs(m.slice_idx - reference_slice.slice_idx) > 1:
            continue
        if m.body_area_px < SUPPORT_AREA_FRACTION * reference_slice.body_area_px:
            continue
        if score < SUPPORT_SCORE_FRACTION * reference_score:
            continue
        if m.tilt_deg > max(MAX_SUPPORT_TILT_DEG, reference_slice.tilt_deg + 6.0):
            continue
        if m.AP_si_mismatch > max(MAX_SUPPORT_MISMATCH_MM, reference_slice.AP_si_mismatch + 1.0):
            continue
        support.append((m, score))

    if not support:
        support = [(reference_slice, reference_score)]

    support.sort(key=lambda item: item[0].slice_idx)
    support_measurements = [m for m, _ in support]
    return reference_slice, support_measurements


# =========================
# 3) Genant-style heights + SHIP-style AP width
# =========================
def measure_body_slice(level, body_mask_2d, slice_idx):
    body_mask_2d = largest_connected_component(body_mask_2d)
    body_area_px = int(body_mask_2d.sum())
    if body_area_px < MIN_BODY_PIXELS_2D:
        return None

    coords_vox = np.argwhere(body_mask_2d).astype(np.float64)  # (N,2) -> (AP, SI)
    coords_mm = coords_vox * np.array([SPACING_AP, SPACING_SI])
    ap_vox_min, si_vox_min = coords_vox.min(axis=0)
    ap_vox_max, si_vox_max = coords_vox.max(axis=0)
    bbox_area_px = int((ap_vox_max - ap_vox_min + 1) * (si_vox_max - si_vox_min + 1))
    bbox_fill_ratio = body_area_px / max(bbox_area_px, 1)

    center_mm = coords_mm.mean(axis=0)
    centered = coords_mm - center_mm
    cov = np.cov(centered.T)
    eigvals, eigvecs = np.linalg.eigh(cov)
    e0, e1 = eigvecs[:, 0], eigvecs[:, 1]

    global_si = np.array([0.0, 1.0])
    if abs(np.dot(e1, global_si)) >= abs(np.dot(e0, global_si)):
        si_axis = e1
        ap_axis = e0
    else:
        si_axis = e0
        ap_axis = e1
    if si_axis[1] < 0:
        si_axis = -si_axis
    if ap_axis[0] < 0:
        ap_axis = -ap_axis

    si_proj = centered @ si_axis
    ap_proj = centered @ ap_axis
    si_min, si_max = float(si_proj.min()), float(si_proj.max())
    ap_min, ap_max = float(ap_proj.min()), float(ap_proj.max())
    si_range = si_max - si_min
    ap_range = ap_max - ap_min
    if si_range <= 0 or ap_range <= 0:
        return None

    # Genant-style edge strips for anterior/posterior heights.
    top_strip = si_proj >= si_max - EDGE_STRIP_FRACTION * si_range
    bot_strip = si_proj <= si_min + EDGE_STRIP_FRACTION * si_range
    if not top_strip.any() or not bot_strip.any():
        return None

    AS = _argbreak(top_strip, ap_proj, "max", si_proj, "max")
    PS = _argbreak(top_strip, ap_proj, "min", si_proj, "max")
    AI = _argbreak(bot_strip, ap_proj, "max", si_proj, "min")
    PI = _argbreak(bot_strip, ap_proj, "min", si_proj, "min")

    # Genant middle height through a thin AP slab around body-center.
    ap_mid = 0.5 * (ap_min + ap_max)
    half_ap_slab = max(MID_AP_SLAB_MM / 2.0, 0.08 * ap_range)
    in_mid_ap_slab = np.abs(ap_proj - ap_mid) <= half_ap_slab
    if in_mid_ap_slab.sum() < 3:
        in_mid_ap_slab = np.abs(ap_proj - ap_mid) <= 2.0 * half_ap_slab
    if in_mid_ap_slab.sum() < 3:
        return None

    M_sup = _argbreak(in_mid_ap_slab, si_proj, "max", ap_proj, "max")
    M_inf = _argbreak(in_mid_ap_slab, si_proj, "min", ap_proj, "max")

    # SHIP-style AP width through the craniocaudal center of the body.
    # We stay inside a thin SI slab, then prefer points closest to the true
    # SI center so off-center slices don't inflate width.
    si_mid = 0.5 * (si_min + si_max)
    half_si_slab = max(MID_SI_SLAB_MM / 2.0, 0.08 * si_range)
    in_mid_si_slab = np.abs(si_proj - si_mid) <= half_si_slab
    if in_mid_si_slab.sum() < 3:
        in_mid_si_slab = np.abs(si_proj - si_mid) <= 2.0 * half_si_slab
    if in_mid_si_slab.sum() < 3:
        return None

    si_center_closeness = -np.abs(si_proj - si_mid)
    A_mid = _argbreak(in_mid_si_slab, ap_proj, "max", si_center_closeness, "max")
    P_mid = _argbreak(in_mid_si_slab, ap_proj, "min", si_center_closeness, "max")

    point_idx = {
        "AS": AS,
        "PS": PS,
        "AI": AI,
        "PI": PI,
        "M_sup": M_sup,
        "M_inf": M_inf,
        "A_mid": A_mid,
        "P_mid": P_mid,
    }
    points_mm = {k: (float(si_proj[i]), float(ap_proj[i])) for k, i in point_idx.items()}
    points_voxel_2d = {k: tuple(int(v) for v in coords_vox[i]) for k, i in point_idx.items()}

    tilt_deg = float(np.degrees(np.arccos(np.clip(abs(np.dot(si_axis, global_si)), 0.0, 1.0))))
    ap_only = abs(points_mm["A_mid"][1] - points_mm["P_mid"][1])
    ap_si_mismatch = abs(points_mm["A_mid"][0] - points_mm["P_mid"][0])

    return SliceMeasurement(
        level=level,
        slice_idx=int(slice_idx),
        AP_width=ap_only,
        H_anterior=dist_mm(points_mm["AS"], points_mm["AI"]),
        H_middle=dist_mm(points_mm["M_sup"], points_mm["M_inf"]),
        H_posterior=dist_mm(points_mm["PS"], points_mm["PI"]),
        tilt_deg=tilt_deg,
        points_mm=points_mm,
        points_voxel_2d=points_voxel_2d,
        body_mask_2d=body_mask_2d,
        AP_only=ap_only,
        AP_si_mismatch=ap_si_mismatch,
        body_area_px=body_area_px,
        bbox_fill_ratio=float(bbox_fill_ratio),
        ap_range_mm=float(ap_range),
        si_range_mm=float(si_range),
    )


def average_measurements(level, per_slice):
    valid = [m for m in per_slice if m is not None]
    if not valid:
        return None

    reference_slice, support_slices = choose_reference_and_support_slices(valid)
    if reference_slice is None:
        return None

    best_ap = min(
        support_slices,
        key=lambda m: (
            m.AP_si_mismatch,
            -m.body_area_px,
            m.tilt_deg,
        ),
    )

    out = {
        "level": level,
        "slice_idx": reference_slice.slice_idx,
        "AP_width_mm": float(best_ap.AP_width),
        "H_anterior_mm": float(np.median([m.H_anterior for m in support_slices])),
        "H_middle_mm": float(np.median([m.H_middle for m in support_slices])),
        "H_posterior_mm": float(np.median([m.H_posterior for m in support_slices])),
        "tilt_deg": float(np.median([m.tilt_deg for m in support_slices])),
        "n_slices_used": len(support_slices),
        "overlay_source": best_ap,
        "ap_width_slice_idx": best_ap.slice_idx,
        "ap_width_si_mismatch_mm": float(best_ap.AP_si_mismatch),
        "candidate_slices": [m.slice_idx for m in valid],
        "support_slices": [m.slice_idx for m in support_slices],
        "reference_body_area_px": int(reference_slice.body_area_px),
        "reference_fill_ratio": float(reference_slice.bbox_fill_ratio),
    }
    return out


def derive_flags(row):
    flags = []
    if row["AP_width_mm"] < 12.0:
        flags.append("AP width below typical MRI reference range")
    if row["AP_width_mm"] > 22.0:
        flags.append("AP width above typical MRI reference range")
    if row["tilt_deg"] > 20.0:
        flags.append("high tilt; inspect slice/segmentation")
    if row["H_anterior_mm"] < 0.70 * row["H_posterior_mm"]:
        flags.append("possible wedge morphology")
    if row["H_middle_mm"] < 0.70 * max(row["H_anterior_mm"], row["H_posterior_mm"]):
        flags.append("possible biconcave morphology")
    return flags


# =========================
# 4) Run per level
# =========================
results = {}

for level in LEVEL_LABELS:
    body_3d = isolate_body_3d(SEG_3D, level)
    if body_3d is None:
        print(f"{level}: body isolation failed")
        continue

    candidate_slices = candidate_slice_indices(body_3d)
    if not candidate_slices:
        print(f"{level}: no valid slice in midline band")
        continue

    per_slice = []
    for s in candidate_slices:
        body_2d = take_sagittal_slice(body_3d, s)
        per_slice.append(measure_body_slice(level, body_2d, s))

    row = average_measurements(level, per_slice)
    if row is None:
        print(f"{level}: measurement failed")
        continue

    row["flags"] = derive_flags(row)
    results[level] = row

    print(
        f"{level}: slice={row['slice_idx']}  "
        f"AP={row['AP_width_mm']:.2f} mm  "
        f"H_ant={row['H_anterior_mm']:.2f}  "
        f"H_mid={row['H_middle_mm']:.2f}  "
        f"H_post={row['H_posterior_mm']:.2f}  "
        f"tilt={row['tilt_deg']:.1f} deg  "
        f"n={row['n_slices_used']}"
    )


if not results:
    raise RuntimeError("No vertebral body measurements were produced.")


# =========================
# 5) Tabulate
# =========================
rows = []
for level, row in results.items():
    rows.append(
        {
            "level": level,
            "slice_idx": row["slice_idx"],
            "ap_width_slice_idx": row["ap_width_slice_idx"],
            "AP_width_mm": round(row["AP_width_mm"], 2),
            "H_anterior_mm": round(row["H_anterior_mm"], 2),
            "H_middle_mm": round(row["H_middle_mm"], 2),
            "H_posterior_mm": round(row["H_posterior_mm"], 2),
            "tilt_deg": round(row["tilt_deg"], 1),
            "ap_width_si_mismatch_mm": round(row["ap_width_si_mismatch_mm"], 3),
            "n_slices_used": row["n_slices_used"],
            "support_slices": ",".join(str(s) for s in row["support_slices"]),
            "body_area_px": row["reference_body_area_px"],
            "fill_ratio": round(row["reference_fill_ratio"], 3),
            "flags": "; ".join(row["flags"]) if row["flags"] else "",
        }
    )

df = pd.DataFrame(rows).set_index("level").sort_index()
display(df)


# =========================
# 6) Visual sanity-check
# =========================
unique_labels = np.unique(SEG_3D)
unique_labels = unique_labels[unique_labels > 0]
palette = plt.cm.tab20(np.linspace(0, 1, 20))


def build_seg_color(seg_2d):
    img = np.zeros((*seg_2d.shape, 4), dtype=np.float32)
    img[..., 3] = 1.0
    img[seg_2d == 0] = (0.05, 0.05, 0.05, 1.0)
    for i, lbl in enumerate(unique_labels):
        img[seg_2d == int(lbl)] = palette[i % 20]
    return img


def to_display(pt_ap_si, shape_2d):
    ap, si = pt_ap_si
    width = shape_2d[1]
    return ap, width - 1 - si


def zoom_to_mask(ax, mask_2d, margin=25):
    coords = np.argwhere(mask_2d)
    if len(coords) == 0:
        return
    ap_min, si_min = coords.min(axis=0)
    ap_max, si_max = coords.max(axis=0)
    ap_min = max(0, ap_min - margin)
    si_min = max(0, si_min - margin)
    ap_max = min(mask_2d.shape[0], ap_max + margin)
    si_max = min(mask_2d.shape[1], si_max + margin)
    ax.set_xlim(ap_min, ap_max)
    ax.set_ylim(mask_2d.shape[1] - 1 - si_min, mask_2d.shape[1] - 1 - si_max)


edge_specs = [
    ("A_mid", "P_mid", "lime", 2.8),      # AP width
    ("AS", "AI", "yellow", 1.6),          # anterior height
    ("M_sup", "M_inf", "cyan", 2.0),      # middle height
    ("PS", "PI", "orange", 1.6),          # posterior height
]

n = len(results)
fig, axes = plt.subplots(n, 3, figsize=(17, 5.4 * n), gridspec_kw={"width_ratios": [1, 1, 0.8]})
if n == 1:
    axes = axes.reshape(1, 3)

for row_idx, level in enumerate(sorted(results)):
    result = results[level]
    src = result["overlay_source"]
    slice_idx = src.slice_idx

    raw_2d = take_sagittal_slice(MRI_3D, slice_idx)
    seg_2d = take_sagittal_slice(SEG_3D, slice_idx)
    ax_raw, ax_seg, ax_txt = axes[row_idx]

    ax_raw.imshow(np.rot90(normalize_mri(raw_2d)), cmap="gray", interpolation="nearest")
    body_overlay = np.zeros((*seg_2d.shape, 4), dtype=np.float32)
    body_overlay[src.body_mask_2d] = (1.0, 0.25, 0.25, 0.45)
    ax_raw.imshow(np.rot90(body_overlay), interpolation="nearest")
    ax_seg.imshow(np.rot90(build_seg_color(seg_2d)), interpolation="nearest")

    ax_raw.set_title(f"{level} raw MRI @ sagittal slice {slice_idx}", fontsize=12)
    ax_seg.set_title(f"{level} segmentation @ sagittal slice {slice_idx}", fontsize=12)

    for ax in (ax_raw, ax_seg):
        for a, b, color, lw in edge_specs:
            x1, y1 = to_display(src.points_voxel_2d[a], src.body_mask_2d.shape)
            x2, y2 = to_display(src.points_voxel_2d[b], src.body_mask_2d.shape)
            ax.plot([x1, x2], [y1, y2], color=color, linewidth=lw, alpha=0.95, zorder=5)
        for name in ("A_mid", "P_mid"):
            x, y = to_display(src.points_voxel_2d[name], src.body_mask_2d.shape)
            ax.scatter([x], [y], c="lime", s=70, zorder=6, edgecolors="white", linewidths=1.0)
        zoom_to_mask(ax, src.body_mask_2d, margin=30)
        ax.axis("off")

    ax_txt.axis("off")
    flags_text = "none" if not result["flags"] else "\n".join(result["flags"])
    ax_txt.text(
        0.02,
        0.98,
        (
            f"{level}\n"
            f"slice = {result['slice_idx']}\n"
            f"AP slice = {result['ap_width_slice_idx']}\n"
            f"support slices = {result['support_slices']}\n"
            f"slices averaged = {result['n_slices_used']}\n\n"
            f"AP_width   = {result['AP_width_mm']:.2f} mm\n"
            f"H_anterior = {result['H_anterior_mm']:.2f} mm\n"
            f"H_middle   = {result['H_middle_mm']:.2f} mm\n"
            f"H_posterior= {result['H_posterior_mm']:.2f} mm\n"
            f"tilt       = {result['tilt_deg']:.1f} deg\n\n"
            f"AP SI mismatch = {result['ap_width_si_mismatch_mm']:.3f} mm\n\n"
            f"body area = {result['reference_body_area_px']} px\n"
            f"fill ratio = {result['reference_fill_ratio']:.3f}\n\n"
            f"flags:\n{flags_text}"
        ),
        transform=ax_txt.transAxes,
        va="top",
        ha="left",
        fontsize=10,
        family="monospace",
        bbox=dict(facecolor="white", edgecolor="black", linewidth=0.5, pad=8),
    )

plt.suptitle(
    "Validated-style cervical VB measurements: lime=SHIP-style mid-body AP width; "
    "yellow/cyan/orange=Genant-style anterior/middle/posterior heights",
    fontsize=12,
    y=1.002,
)
plt.tight_layout()
plt.show()
