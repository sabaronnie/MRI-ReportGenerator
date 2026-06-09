# Measurements IEP — Flask geometric/cord/group5 measurements + assessement.
# Build context = repo root (imports `services.measurements.*` and `services.assessement.*`).
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive \
    SCT_DIR=/opt/sct

# Spinal Cord Toolbox (LGPLv3) — G3 canal/cord/SAC morphometry shells out to `sct_process_segmentation`
# on the PRE-COMPUTED SCT masks from the seg-sct IEP. Only the CLI is needed here, NOT the deepseg
# models (segmentation already happened upstream), so this install pulls no model weights. Pinned to 7.0
# to match the seg-sct image.
RUN apt-get update && apt-get install -y --no-install-recommends \
      git curl bzip2 ca-certificates libglib2.0-0 libgl1 gcc \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch 7.0 https://github.com/spinalcordtoolbox/spinalcordtoolbox.git "$SCT_DIR" \
    && cd "$SCT_DIR" && yes | ./install_sct -iy
ENV PATH="/opt/sct/bin:${PATH}"

RUN pip install --no-cache-dir gunicorn
COPY services/measurements/requirements.txt /app/services/measurements/requirements.txt
RUN pip install --no-cache-dir -r services/measurements/requirements.txt

COPY services/measurements /app/services/measurements
COPY services/assessement /app/services/assessement
# cord_ap/functional_canal_ap import services.segmentation.sct_segmenter (a light, stdlib-only
# SCT CLI wrapper — no torch/totalspineseg pulled at import). Needed for the package to load.
COPY services/segmentation /app/services/segmentation

EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8081/healthz').status==200 else 1)"

# 2 workers; measurement requests are CPU-bound and short.
CMD ["gunicorn", "-b", "0.0.0.0:8081", "-w", "2", "--timeout", "120", "services.measurements.app:app"]
