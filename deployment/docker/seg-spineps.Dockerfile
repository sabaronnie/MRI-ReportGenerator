# Segmentation engine 3 — SPINEPS (per-vertebra instances + endplate-voxel sheets, for the G4 Cobb).
# SEPARATE image from TSS on purpose: SPINEPS pins numpy==2.0.2, which breaks the nnU-Net ABI that
# TotalSpineSeg needs. Apache-2.0 (verify the TPTBox `spinestats` submodule isn't AGPL before bundling).
#
# NOTE: the Flask service wrapper (`services/segmentation/spineps_app.py`) is owned by the science
# chat — it does not exist yet (SPINEPS currently lives only in colab/ + research/group5/
# run_spineps_alignment.py). This Dockerfile is the deployment shell; build it from the science
# branch once that wrapper lands (see the seg-services handoff + .github/workflows/build-seg-images.yml).
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir gunicorn flask nibabel "numpy==2.0.2"
# SPINEPS + TPTBox (device-agnostic torch; pins resolved by the science chat's pinned requirements).
RUN pip install --no-cache-dir spineps

COPY services/segmentation /app/services/segmentation

EXPOSE 8085
# spineps_app:app is the wrapper the science chat must provide (POST /segment -> instance/endplate masks).
CMD ["gunicorn", "-b", "0.0.0.0:8085", "-w", "1", "--timeout", "1800", "services.segmentation.spineps_app:app"]
