"""Colab cells for Group 3 stenosis testing on existing TotalSpineSeg output.

This notebook-style script assumes you already have TotalSpineSeg outputs for a
case, especially:
  - `step1_levels.nii.gz`
  - `input_iso.nii.gz` (preferred) or the exact MRI volume TSS used
  - optionally `step2_output.nii.gz` and `segmentation_run_manifest.json`

The implemented mapping is:
  3.1 Functional canal / dural sac AP  -> SCT `canal`
  3.2 Spinal cord AP                   -> SCT `spinalcord`
  3.3 SAC                              -> same-slice subtraction
  3.4 Most stenotic level              -> min dural-sac AP (plus min SAC)
"""


# =============================================================================
# Colab cell 1/3 - install dependencies (Python + SCT)
# =============================================================================

from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import median


try:
    from google.colab import drive  # type: ignore
except ImportError:
    drive = None


# -------- Edit these before running --------
MOUNT_DRIVE = True
SCT_DIR = Path("/content/sct")
SCT_GIT_REF = "master"   # Optional: set to a release tag/branch if you want to pin it
PIP_PACKAGES = [
    "nibabel>=5.0",
    "numpy>=1.24",
    "pandas>=2.0",
    "matplotlib>=3.8",
]
# ------------------------------------------


def _run(cmd: list[str], *, cwd: Path | None = None, clean_ld_library_path: bool = False) -> None:
    print("$", " ".join(cmd))
    env = os.environ.copy()
    if clean_ld_library_path:
        env.pop("LD_LIBRARY_PATH", None)
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        env=env,
    )
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout tail:\n{result.stdout[-4000:]}\n"
            f"stderr tail:\n{result.stderr[-4000:]}"
        )


def _mount_drive_if_requested() -> None:
    if MOUNT_DRIVE and drive is not None:
        drive.mount("/content/drive", force_remount=False)


def _install_python_packages() -> None:
    _run([sys.executable, "-m", "pip", "install", "-q", *PIP_PACKAGES])


def _install_sct() -> None:
    if shutil.which("sct_deepseg") and shutil.which("sct_process_segmentation"):
        print("SCT commands already available on PATH; skipping installation.")
        return

    _run(["apt-get", "update", "-qq"])
    _run(["apt-get", "install", "-y", "-qq", "gcc", "git", "curl", "bzip2", "unzip", "libglib2.0-0"])

    if not SCT_DIR.exists():
        _run(["git", "clone", "https://github.com/spinalcordtoolbox/spinalcordtoolbox.git", str(SCT_DIR)])
    if SCT_GIT_REF and SCT_GIT_REF != "master":
        _run(["git", "checkout", SCT_GIT_REF], cwd=SCT_DIR)

    install_script = SCT_DIR / "install_sct"
    if not install_script.exists():
        raise FileNotFoundError(f"Could not find SCT install script at {install_script}")
    _run(["bash", str(install_script), "-y"], cwd=SCT_DIR)

    os.environ["PATH"] = f"{SCT_DIR / 'bin'}:{os.environ['PATH']}"
    if not shutil.which("sct_deepseg") or not shutil.which("sct_process_segmentation"):
        raise RuntimeError("SCT installation finished but SCT commands were not found on PATH.")


def _install_sct_model(task: str) -> None:
    """Install an SCT deepseg model if needed.

    SCT ships the framework, but task-specific models may need a separate
    install the first time they are used.
    """
    _run(["sct_deepseg", task, "-install"], clean_ld_library_path=True)


_mount_drive_if_requested()
_install_python_packages()
_install_sct()

print("Environment ready.")
print("  sct_deepseg =", shutil.which("sct_deepseg"))
print("  sct_process_segmentation =", shutil.which("sct_process_segmentation"))


# =============================================================================
# Colab cell 2/3 - configure paths + helper functions
# =============================================================================

import pandas as pd


# -------- Edit these before running --------
CASE_OUTPUT_DIR = Path("/content/drive/MyDrive/mri_report_generator_runs/case_001")

# Optional overrides. Leave as None to auto-resolve from CASE_OUTPUT_DIR and/or
# segmentation_run_manifest.json.
STEP1_LEVELS_PATH = None        # e.g. "/content/.../step1_levels.nii.gz"
RAW_MRI_OR_ISO_PATH = None      # Prefer TotalSpineSeg's input_iso.nii.gz
SEG_STEP2_PATH = None           # Optional; not required for the SCT metrics

VERT_RANGE = "2:7"             # cervical C2..C7
LEVEL_NAME_MAP = {
    2: "C2",
    3: "C3",
    4: "C4",
    5: "C5",
    6: "C6",
    7: "C7",
}
LOW_CONFIDENCE_SLICE_COUNT = 3
# ------------------------------------------


@dataclass(frozen=True)
class ShapeMetricRow:
    slice_index: int | None
    vertebral_level: int | None
    metrics: dict[str, float]
    raw: dict[str, str]


def read_manifest(case_dir: Path) -> dict:
    json_manifest = case_dir / "segmentation_run_manifest.json"
    if json_manifest.exists():
        try:
            return json.loads(json_manifest.read_text())
        except (OSError, ValueError):
            pass
    return {}


def resolve_levels_path(case_dir: Path) -> Path:
    if STEP1_LEVELS_PATH:
        path = Path(STEP1_LEVELS_PATH)
        if not path.exists():
            raise FileNotFoundError(f"STEP1_LEVELS_PATH does not exist: {path}")
        return path

    manifest = read_manifest(case_dir)
    candidate = manifest.get("step1_levels")
    if candidate:
        path = Path(candidate)
        if path.exists():
            return path

    for path in [
        case_dir / "step1_levels.nii.gz",
        case_dir / "tss_output" / "step1_levels" / "step1_levels.nii.gz",
    ]:
        if path.exists():
            return path
    found = sorted(case_dir.rglob("step1_levels*.nii.gz"))
    if found:
        return found[0]
    raise FileNotFoundError("Could not resolve step1_levels.nii.gz")


def resolve_raw_iso_path(case_dir: Path) -> Path:
    if RAW_MRI_OR_ISO_PATH:
        path = Path(RAW_MRI_OR_ISO_PATH)
        if not path.exists():
            raise FileNotFoundError(f"RAW_MRI_OR_ISO_PATH does not exist: {path}")
        return path

    manifest = read_manifest(case_dir)
    for key in ("iso_input", "prepared_nifti_path", "input_path"):
        candidate = manifest.get(key)
        if not candidate:
            continue
        path = Path(candidate)
        if path.exists():
            return path

    for path in [
        case_dir / "input_iso.nii.gz",
        case_dir / "tss_output" / "input_iso" / "input_iso.nii.gz",
    ]:
        if path.exists():
            return path
    found = sorted(case_dir.rglob("input_iso*.nii.gz"))
    if found:
        return found[0]
    raise FileNotFoundError(
        "Could not resolve the MRI volume for SCT. Prefer providing TotalSpineSeg's input_iso.nii.gz."
    )


def resolve_step2_path(case_dir: Path) -> Path | None:
    if SEG_STEP2_PATH:
        path = Path(SEG_STEP2_PATH)
        if not path.exists():
            raise FileNotFoundError(f"SEG_STEP2_PATH does not exist: {path}")
        return path
    manifest = read_manifest(case_dir)
    candidate = manifest.get("step2_output")
    if candidate:
        path = Path(candidate)
        if path.exists():
            return path
    found = sorted(case_dir.rglob("step2_output*.nii.gz"))
    return found[0] if found else None


def run_deepseg(task: str, input_path: Path, output_dir: Path, *, keep_largest: bool = True) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    _install_sct_model(task)
    out_path = output_dir / "prediction.nii.gz"
    cmd = [
        "sct_deepseg",
        task,
        "-i",
        str(input_path),
        "-o",
        str(out_path),
        "-r",
        "0",
    ]
    if keep_largest:
        cmd.extend(["-largest", "1"])
    _run(cmd, clean_ld_library_path=True)

    if out_path.exists():
        return out_path

    nifti_files = sorted(output_dir.glob("*.nii.gz"))
    if len(nifti_files) == 1:
        return nifti_files[0]
    if not nifti_files:
        raise FileNotFoundError(f"sct_deepseg {task} produced no NIfTI output in {output_dir}")
    raise RuntimeError(f"Ambiguous SCT output in {output_dir}: {[p.name for p in nifti_files]}")


def run_process_segmentation(
    seg_path: Path,
    *,
    discfile: Path,
    output_csv: Path,
    vert: str = VERT_RANGE,
) -> list[ShapeMetricRow]:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "sct_process_segmentation",
        "-i",
        str(seg_path),
        "-o",
        str(output_csv),
        "-vert",
        vert,
        "-discfile",
        str(discfile),
        "-angle-corr",
        "1",
        "-perslice",
        "1",
    ]
    _run(cmd, clean_ld_library_path=True)
    if not output_csv.exists():
        raise FileNotFoundError(f"SCT produced no CSV at {output_csv}")

    with output_csv.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise RuntimeError(f"SCT produced an empty CSV at {output_csv}")
    return [_parse_shape_metric_row(row) for row in rows]


def _parse_shape_metric_row(row: dict[str, str]) -> ShapeMetricRow:
    metrics: dict[str, float] = {}
    for key, value in row.items():
        if not key.startswith("MEAN(") or value in ("", None):
            continue
        try:
            metrics[key[5:-1]] = float(value)
        except ValueError:
            continue

    slice_index = _parse_optional_int(row.get("Slice (I->S)") or row.get("Slice") or row.get("SliceI->S"))
    vertebral_level = _parse_optional_int(row.get("VertLevel") or row.get("Vert Level") or row.get("Vertlevel"))
    return ShapeMetricRow(
        slice_index=slice_index,
        vertebral_level=vertebral_level,
        metrics=metrics,
        raw=row,
    )


def _parse_optional_int(value: str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def group_ap_by_level(rows: list[ShapeMetricRow]) -> dict[int, list[dict[str, float]]]:
    grouped: dict[int, list[dict[str, float]]] = {}
    for row in rows:
        if row.vertebral_level not in LEVEL_NAME_MAP or row.slice_index is None:
            continue
        ap = row.metrics.get("diameter_AP")
        if ap is None:
            continue
        grouped.setdefault(row.vertebral_level, []).append(
            {
                "slice_index": row.slice_index,
                "raw_ap_mm": float(ap),
            }
        )
    for level_rows in grouped.values():
        level_rows.sort(key=lambda r: r["slice_index"])
    return grouped


def stable_minimum(level_rows: list[dict[str, float]]) -> dict[str, float]:
    if not level_rows:
        raise ValueError("stable_minimum requires at least one slice row")
    raw_values = [row["raw_ap_mm"] for row in level_rows]
    stable_rows = []
    for idx, row in enumerate(level_rows):
        lo = max(0, idx - 1)
        hi = min(len(level_rows), idx + 2)
        stable_rows.append(
            {
                "slice_index": row["slice_index"],
                "raw_ap_mm": row["raw_ap_mm"],
                "stable_ap_mm": float(median(raw_values[lo:hi])),
            }
        )
    return min(stable_rows, key=lambda r: (r["stable_ap_mm"], r["raw_ap_mm"], r["slice_index"]))


def choose_nearest_slice(level_rows: list[dict[str, float]], focal_slice: int) -> dict[str, float]:
    if not level_rows:
        raise ValueError("choose_nearest_slice requires at least one slice row")
    return min(level_rows, key=lambda r: (abs(int(r["slice_index"]) - int(focal_slice)), int(r["slice_index"])))


# =============================================================================
# Colab cell 3/3 - run Group 3 stenosis metrics
# =============================================================================

CASE_OUTPUT_DIR = CASE_OUTPUT_DIR.resolve()
CASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
WORK_DIR = CASE_OUTPUT_DIR / "group3_sct_work"
WORK_DIR.mkdir(parents=True, exist_ok=True)

levels_path = resolve_levels_path(CASE_OUTPUT_DIR)
raw_path = resolve_raw_iso_path(CASE_OUTPUT_DIR)
step2_path = resolve_step2_path(CASE_OUTPUT_DIR)

print("Resolved inputs:")
print("  RAW_MRI_OR_ISO_PATH:", raw_path)
print("  STEP1_LEVELS_PATH:  ", levels_path)
print("  SEG_STEP2_PATH:     ", step2_path if step2_path else "(not used)")


# ---- 3.1 Functional canal / dural sac AP -----------------------------------

canal_seg_path = run_deepseg("canal", raw_path, WORK_DIR / "canal")
canal_rows = run_process_segmentation(
    canal_seg_path,
    discfile=levels_path,
    output_csv=WORK_DIR / "functional_canal_ap.csv",
)
canal_grouped = group_ap_by_level(canal_rows)

dural_sac_ap_min: dict[str, float] = {}
focal_slices: dict[str, int] = {}
canal_low_confidence: dict[str, bool] = {}
for level_num, level_rows in sorted(canal_grouped.items()):
    summary = stable_minimum(level_rows)
    level_name = LEVEL_NAME_MAP[level_num]
    dural_sac_ap_min[level_name] = round(summary["stable_ap_mm"], 3)
    focal_slices[level_name] = int(summary["slice_index"])
    canal_low_confidence[level_name] = len(level_rows) < LOW_CONFIDENCE_SLICE_COUNT


# ---- 3.2 Cord AP aligned to 3.1 focal slices --------------------------------

cord_seg_path = run_deepseg("spinalcord", raw_path, WORK_DIR / "spinalcord")
cord_rows = run_process_segmentation(
    cord_seg_path,
    discfile=levels_path,
    output_csv=WORK_DIR / "cord_ap.csv",
)
cord_grouped = group_ap_by_level(cord_rows)

cord_ap_focal: dict[str, float] = {}
cord_source_slice: dict[str, int] = {}
cord_slice_misaligned: dict[str, bool] = {}
for level_num, level_name in LEVEL_NAME_MAP.items():
    if level_name not in focal_slices:
        continue
    level_rows = cord_grouped.get(level_num)
    if not level_rows:
        continue
    chosen = choose_nearest_slice(level_rows, focal_slices[level_name])
    cord_ap_focal[level_name] = round(chosen["raw_ap_mm"], 3)
    cord_source_slice[level_name] = int(chosen["slice_index"])
    cord_slice_misaligned[level_name] = int(chosen["slice_index"]) != int(focal_slices[level_name])


# ---- 3.3 SAC ----------------------------------------------------------------

sac_mm: dict[str, float] = {}
sac_high_risk: dict[str, bool] = {}
shared_levels = sorted(set(dural_sac_ap_min) & set(cord_ap_focal), key=lambda name: list(LEVEL_NAME_MAP.values()).index(name))
for level_name in shared_levels:
    value = float(dural_sac_ap_min[level_name]) - float(cord_ap_focal[level_name])
    sac_mm[level_name] = round(value, 3)
    sac_high_risk[level_name] = value < 3.0


# ---- 3.4 Most stenotic level ------------------------------------------------

most_stenotic_level = min(dural_sac_ap_min, key=dural_sac_ap_min.get) if dural_sac_ap_min else None
lowest_sac_level = min(sac_mm, key=sac_mm.get) if sac_mm else None


# ---- Display + save ---------------------------------------------------------

rows = []
for level_name in shared_levels:
    rows.append(
        {
            "level": level_name,
            "dural_sac_AP_min_mm": dural_sac_ap_min.get(level_name),
            "focal_slice": focal_slices.get(level_name),
            "cord_AP_focal_mm": cord_ap_focal.get(level_name),
            "cord_source_slice": cord_source_slice.get(level_name),
            "cord_slice_misaligned": cord_slice_misaligned.get(level_name),
            "SAC_mm": sac_mm.get(level_name),
            "SAC_high_risk": sac_high_risk.get(level_name),
            "canal_low_confidence": canal_low_confidence.get(level_name),
        }
    )

results_df = pd.DataFrame(rows)
print("\nGroup 3 results:")
display(results_df if "display" in globals() else results_df)

summary = {
    "resolved_paths": {
        "raw_mri_or_iso": str(raw_path),
        "step1_levels": str(levels_path),
        "step2_output": str(step2_path) if step2_path else None,
    },
    "functional_canal_ap": dural_sac_ap_min,
    "focal_slices": focal_slices,
    "cord_ap_focal": cord_ap_focal,
    "cord_source_slice": cord_source_slice,
    "cord_slice_misaligned": cord_slice_misaligned,
    "sac_mm": sac_mm,
    "sac_high_risk": sac_high_risk,
    "most_stenotic_level_by_dural_sac": most_stenotic_level,
    "lowest_sac_level": lowest_sac_level,
}

out_json = CASE_OUTPUT_DIR / "group3_stenosis_results.json"
out_json.write_text(json.dumps(summary, indent=2))
print("\nSaved summary JSON to:", out_json)
if most_stenotic_level:
    print(
        "Most stenotic level:",
        most_stenotic_level,
        f"(dural sac AP {dural_sac_ap_min[most_stenotic_level]:.3f} mm)",
    )
if lowest_sac_level:
    print(
        "Lowest SAC level:",
        lowest_sac_level,
        f"(SAC {sac_mm[lowest_sac_level]:.3f} mm)",
    )
