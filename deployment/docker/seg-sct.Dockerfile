# Segmentation models 2 & 3 — SCT deepseg (spinal cord + canal). Built on the Spinal Cord Toolbox
# (LGPLv3) installed via its official installer. Device-agnostic (GPU if present, else CPU).
# Build context = repo root.
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive \
    SCT_DIR=/opt/sct

# SCT install prerequisites.
RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl bzip2 ca-certificates libglib2.0-0 libgl1 gcc \
    && rm -rf /var/lib/apt/lists/*

# Install SCT (non-interactive). Pin a known release for reproducibility.
RUN git clone --depth 1 --branch 7.0 https://github.com/spinalcordtoolbox/spinalcordtoolbox.git "$SCT_DIR" \
    && cd "$SCT_DIR" && yes | ./install_sct -iy
ENV PATH="/opt/sct/bin:${PATH}"

# Pre-fetch the deepseg models used (canal + spinalcord) so the first request is offline/fast.
RUN sct_deepseg -install-task seg_sc_contrast 2>/dev/null || true; \
    sct_deepseg -install-task canal_t2w 2>/dev/null || true

RUN pip install --no-cache-dir gunicorn flask nibabel numpy

COPY services/segmentation /app/services/segmentation

EXPOSE 8084
CMD ["gunicorn", "-b", "0.0.0.0:8084", "-w", "1", "--timeout", "1800", "services.segmentation.sct_app:app"]
