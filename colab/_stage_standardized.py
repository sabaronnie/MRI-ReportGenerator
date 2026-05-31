"""One-off: standardize a few raw MRIs and stage them for a TSS batch run."""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "segmentation"))
from standardize import standardize_mri  # noqa: E402

RAWS = [
    ROOT / "tss_runs" / "batch_in" / "593973-000002_Study-MR-2_Series-3.nii.gz",
    ROOT / "tss_runs" / "batch_in" / "593973-000005_Study-MR-5_Series-11.nii.gz",
]
stage = ROOT / "tss_runs" / "std_stage"
inp = ROOT / "tss_runs" / "std_in"
inp.mkdir(parents=True, exist_ok=True)

for r in RAWS:
    res = standardize_mri(str(r), stage, iso_mm=1.0)
    shutil.copy(res.standardized_path, inp / res.standardized_path.name)
    print(f"{r.name}: spacing {tuple(round(x,3) for x in res.orig_spacing_mm)} -> "
          f"{res.new_spacing_mm}, shape {res.orig_shape} -> {res.new_shape}, "
          f"axes {res.orig_axcodes}->RAS, flags={res.flags}")
print("staged:", [p.name for p in sorted(inp.glob('*.nii.gz'))])
