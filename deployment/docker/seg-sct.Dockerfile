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

# Pre-fetch the exact v7 deepseg tasks the wrapper invokes (sct_segmenter.py): cord + canal (G3) and
# the SCIseg cord-lesion (G5.1). Names must match `sct_deepseg <task>` in the wrapper. Best-effort
# (|| true): if a name/flag differs by patch release, the model just downloads on the first request.
RUN for t in spinalcord canal lesion_sci_t2; do \
      sct_deepseg "$t" -install 2>/dev/null || sct_deepseg -install-task "$t" 2>/dev/null || true; \
    done

# scipy: input_handler uses nibabel.processing (resample_to_output). dcm2niix: accept zipped DICOM too.
RUN pip install --no-cache-dir gunicorn flask nibabel numpy scipy dcm2niix

COPY services/segmentation /app/services/segmentation

EXPOSE 8084
CMD ["gunicorn", "-b", "0.0.0.0:8084", "-w", "1", "--timeout", "1800", "services.segmentation.sct_app:app"]
