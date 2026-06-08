# Measurements IEP — Flask geometric/cord/group5 measurements + interpretation.
# Build context = repo root (imports `services.measurements.*` and `services.interpretation.*`).
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN pip install --no-cache-dir gunicorn
COPY services/measurements/requirements.txt /app/services/measurements/requirements.txt
RUN pip install --no-cache-dir -r services/measurements/requirements.txt

COPY services/measurements /app/services/measurements
COPY services/interpretation /app/services/interpretation
# cord_ap/functional_canal_ap import services.segmentation.sct_segmenter (a light, stdlib-only
# SCT CLI wrapper — no torch/totalspineseg pulled at import). Needed for the package to load.
COPY services/segmentation /app/services/segmentation

EXPOSE 8081
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8081/healthz').status==200 else 1)"

# 2 workers; measurement requests are CPU-bound and short.
CMD ["gunicorn", "-b", "0.0.0.0:8081", "-w", "2", "--timeout", "120", "services.measurements.app:app"]
