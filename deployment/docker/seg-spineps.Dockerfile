# Segmentation engine 3 — SPINEPS (per-vertebra instances + endplate-voxel sheets, for the G4 Cobb).
# SEPARATE image from TSS on purpose: SPINEPS pins numpy==2.0.2, which breaks the nnU-Net ABI that
# TotalSpineSeg needs. Apache-2.0 (verify the TPTBox `spinestats` submodule isn't AGPL before bundling).
#
# The Flask wrapper (services/segmentation/spineps_app.py) + spineps_segmenter.py are finalized on the
# integration branch (merged from research/andrew/writeups). It runs `spineps sample ... -model_semantic
# t2w -model_instance instance` and returns spineps_seg-vert_msk.nii.gz (endplate voxels 102-107).
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

# scipy: input_handler uses nibabel.processing. dcm2niix: accept zipped DICOM too.
RUN pip install --no-cache-dir gunicorn flask nibabel scipy dcm2niix "numpy==2.0.2"
# SPINEPS + TPTBox (device-agnostic torch). It may pull a newer numpy transitively, so RE-PIN
# numpy==2.0.2 immediately after — a newer numpy breaks the SPINEPS/numba ABI
# (_blas_supports_fpe crash). HARD requirement, see spineps_requirements.txt.
RUN pip install --no-cache-dir spineps \
    && pip install --no-cache-dir --force-reinstall "numpy==2.0.2" \
    && python -c "import numpy; assert numpy.__version__ == '2.0.2', numpy.__version__"

# Pre-download the SPINEPS model weights (semantic t2w + instance) at build so the first request is
# offline/fast. The v1.0.9 release ships checkpoint_final.pth but the loader asks for checkpoint_best.pth
# -> copy final->best in each fold.
RUN python -c "import shutil; from pathlib import Path; from spineps.utils import auto_download as ad; from spineps.utils.filepaths import get_mri_segmentor_models_dir as gd; m=gd(); [ad.download_weights(u, Path(m, ad.download_names[k]+'_'+v)) for k,u,v in [('t2w',ad.semantic['t2w'],ad.current_highest_version),('instance',ad.instances['instance'],ad.current_instance_highest_version),('t2w_labeling',ad.labeling['t2w_labeling'],ad.current_labeling_highest_version)] if not (Path(m, ad.download_names[k]+'_'+v).exists())]; [shutil.copy(str(f), str(f.with_name('checkpoint_best.pth'))) for f in Path(m).rglob('checkpoint_final.pth') if not f.with_name('checkpoint_best.pth').exists()]; print('spineps weights ready')"

COPY services/segmentation /app/services/segmentation

EXPOSE 8085
# spineps_app:app is the wrapper the science chat must provide (POST /segment -> instance/endplate masks).
CMD ["gunicorn", "-b", "0.0.0.0:8085", "-w", "1", "--timeout", "1800", "services.segmentation.spineps_app:app"]
