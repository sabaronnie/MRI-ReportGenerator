# External Endpoint (EEP) — FastAPI public boundary.
# Build context = repo root (so `services.eep.app` is importable).
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY services/eep/requirements.txt /app/services/eep/requirements.txt
RUN pip install --no-cache-dir -r services/eep/requirements.txt

COPY services/eep /app/services/eep

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz').status==200 else 1)"

CMD ["uvicorn", "services.eep.app:app", "--host", "0.0.0.0", "--port", "8080"]
