# Segmentation model 1 — TotalSpineSeg (nnUNetv2). Device-agnostic: torch uses the GPU if the
# runtime provides one (nvidia device plugin), else CPU (slower). Build context = repo root.
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    # nnUNet + TotalSpineSeg weights cache (baked at build so cold-start is fast + offline).
    TOTALSPINESEG_DATA=/opt/tss-data

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir gunicorn flask nibabel numpy scipy
# Pulls nnUNetv2 + torch (CUDA build runs on CPU too — one image for both node types).
RUN pip install --no-cache-dir "totalspineseg[nnunetv2]"

# Pre-download the model weights at build time so the first request doesn't (and the node can be
# offline). `totalspineseg_init` fetches the release weights into TOTALSPINESEG_DATA.
RUN mkdir -p "$TOTALSPINESEG_DATA" && (totalspineseg_init || echo "weights will download on first run")

COPY services/segmentation /app/services/segmentation

EXPOSE 8083
# Long timeout: a CPU TotalSpineSeg run is minutes.
CMD ["gunicorn", "-b", "0.0.0.0:8083", "-w", "1", "--timeout", "1800", "services.segmentation.app:app"]
