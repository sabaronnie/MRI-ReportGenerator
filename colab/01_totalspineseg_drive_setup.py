"""Colab cell 1/3 — install TotalSpineSeg and cache its model weights on Drive.

Run this as the FIRST cell in a fresh Colab runtime.

The ONLY thing this writes to Drive is the model weights. Dependencies are
installed into the (ephemeral) runtime, and the downloaded weight ZIPs are
discarded after extraction — they are not kept on Drive.

What it does:
  1. Mounts Google Drive.
  2. Installs the pinned dependency stack into the runtime (NOT cached on Drive
     — pip handles these every fresh runtime; they are fast vs. the weights).
  3. Points TOTALSPINESEG_DATA at a Drive folder so the model weights live there.
  4. Downloads the weights into that Drive folder via `totalspineseg_init`.
     If the weights are already on Drive from a previous run, the download is
     skipped — nothing is re-downloaded.

After this cell finishes: Runtime > Restart session, then run cell 2.
(The restart is needed because numpy/torch were reinstalled into a kernel that
had already imported the old versions. Pip-installed packages survive the
restart — only the Python kernel is recycled.)
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


# -------- Edit these only if you want different Drive locations --------
DRIVE_CACHE_ROOT = Path("/content/drive/MyDrive/mri_report_generator_cache")
# TotalSpineSeg stores its weights under TOTALSPINESEG_DATA/nnUNet/results/...
TOTALSPINESEG_DATA = DRIVE_CACHE_ROOT / "totalspineseg"
# ----------------------------------------------------------------------

# Pinned "proper" versions. TotalSpineSeg recommends torch<2.6 and tests against
# nnunetv2==2.6.2; kornia==0.7.2 keeps `kornia.core.Tensor` available for the
# nnU-Net import chain. numpy must stay <2 for this stack.
PINNED_TORCH = "2.5.1"
PINNED_TORCHVISION = "0.20.1"
PINNED_TORCHAUDIO = "2.5.1"
PINNED_NUMPY = "1.26.4"
PINNED_SCIPY = "1.12.0"
PINNED_NNUNETV2 = "2.6.2"
PINNED_KORNIA = "0.7.2"
PINNED_TOTALSPINESEG = "20260429"  # latest release; bump if upstream moves

# Internal nnU-Net dataset folders that signal the weights are fully installed.
WEIGHT_DATASET_DIRS = (
    "Dataset101_TotalSpineSeg_step1",
    "Dataset102_TotalSpineSeg_step2",
)


def _run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def _pip_install(args: list[str]) -> None:
    _run([sys.executable, "-m", "pip", "install", "-q", *args])


def _mount_drive() -> None:
    if "google.colab" not in sys.modules:
        print("Not running inside Colab; skipping Google Drive mount.")
        return
    from google.colab import drive  # type: ignore

    drive.mount("/content/drive", force_remount=False)


def _make_cache_dirs() -> None:
    TOTALSPINESEG_DATA.mkdir(parents=True, exist_ok=True)
    print(f"TotalSpineSeg weight cache (on Drive): {TOTALSPINESEG_DATA}")


def _install_dependencies() -> None:
    # Toolchain first so the pinned wheels resolve cleanly.
    _pip_install(["--upgrade", "pip", "setuptools", "wheel"])

    # dcm2niix is only needed if you feed a DICOM folder in cell 2. apt package,
    # not cached — reinstalled each fresh runtime.
    if shutil.which("dcm2niix") is None:
        _run(["apt-get", "update", "-qq"])
        _run(["apt-get", "install", "-y", "-qq", "dcm2niix"])
    else:
        print("dcm2niix already on PATH.")

    # GPU torch stack from the CUDA 12.1 wheel index. force-reinstall because
    # Colab ships a newer (>=2.6) torch that TotalSpineSeg does not support.
    _pip_install(
        [
            "--force-reinstall",
            "--no-cache-dir",
            f"torch=={PINNED_TORCH}",
            f"torchvision=={PINNED_TORCHVISION}",
            f"torchaudio=={PINNED_TORCHAUDIO}",
            "--index-url",
            "https://download.pytorch.org/whl/cu121",
        ]
    )

    # Scientific + segmentation stack in ONE resolver pass so every pin is
    # honoured together. If totalspineseg were installed in a separate call it
    # could pull a newer kornia and silently override the 0.7.2 pin that cell 2
    # hard-checks. numpy/scipy are force-reinstalled because Colab ships numpy>=2,
    # which breaks this nnU-Net era.
    _pip_install(
        [
            "--force-reinstall",
            "--no-cache-dir",
            f"numpy=={PINNED_NUMPY}",
            f"scipy=={PINNED_SCIPY}",
            "nibabel>=5.0,<6",
            f"kornia=={PINNED_KORNIA}",
            f"nnunetv2=={PINNED_NNUNETV2}",
            f"totalspineseg=={PINNED_TOTALSPINESEG}",
        ]
    )


def _weights_present() -> bool:
    if not TOTALSPINESEG_DATA.exists():
        return False
    # rglob tolerates the optional release subfolder TotalSpineSeg sometimes
    # nests weights under (e.g. nnUNet/results/<release>/Dataset10x_...).
    return all(any(TOTALSPINESEG_DATA.rglob(name)) for name in WEIGHT_DATASET_DIRS)


def _init_command() -> list[str]:
    # --store-export sets store_export=False, so the downloaded weight ZIPs are
    # NOT kept on Drive — only the extracted model weights remain there.
    args = ["-d", str(TOTALSPINESEG_DATA), "--store-export"]
    if shutil.which("totalspineseg_init") is not None:
        return ["totalspineseg_init", *args]
    # Console script not yet on PATH in this kernel — call the module directly.
    return [sys.executable, "-m", "totalspineseg.init_inference", *args]


def _ensure_weights_cached() -> None:
    if _weights_present():
        print(f"Cached model weights found on Drive at: {TOTALSPINESEG_DATA}")
        print("Skipping download — nothing will be re-installed.")
        return

    print("No cached weights on Drive yet — downloading via totalspineseg_init.")
    print("This is the slow one-time step; future runs reuse these Drive weights.")
    _run(_init_command())

    if not _weights_present():
        raise RuntimeError(
            "totalspineseg_init finished but the expected dataset folders "
            f"{WEIGHT_DATASET_DIRS} were not found under {TOTALSPINESEG_DATA}. "
            "Check the download logs above."
        )
    print(f"Weights downloaded and cached on Drive at: {TOTALSPINESEG_DATA}")


def _report_versions() -> None:
    # Run in a subprocess so it reads the freshly installed packages rather than
    # whatever this (pre-restart) kernel already imported.
    code = (
        "import importlib.metadata as md;"
        "import torch;"
        "print('  torch    =', torch.__version__);"
        "print('  numpy    =', md.version('numpy'));"
        "print('  scipy    =', md.version('scipy'));"
        "print('  nibabel  =', md.version('nibabel'));"
        "print('  kornia   =', md.version('kornia'));"
        "print('  nnunetv2 =', md.version('nnunetv2'));"
        "print('  totalspineseg =', md.version('totalspineseg'));"
        "print('  cuda available =', torch.cuda.is_available())"
    )
    print("Installed versions:")
    subprocess.run([sys.executable, "-c", code], check=False)


def main() -> None:
    _mount_drive()
    _make_cache_dirs()
    _install_dependencies()
    _report_versions()
    _ensure_weights_cached()

    print("\nSetup complete.")
    print("Next: Runtime > Restart session, then run cell 2 "
          "(02_run_totalspineseg_colab.py).")


main()
