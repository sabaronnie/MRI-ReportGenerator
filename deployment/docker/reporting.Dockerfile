# Reporting IEP — Flask service that turns the assessement handoff into a clinical report.
# Build context = repo root (imports `services.reporting.*` and `services.assessement.*`).
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

RUN pip install --no-cache-dir gunicorn
COPY services/reporting/requirements.txt /app/services/reporting/requirements.txt
RUN pip install --no-cache-dir -r services/reporting/requirements.txt

COPY services/reporting /app/services/reporting
COPY services/assessement /app/services/assessement

EXPOSE 8082
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8082/healthz').status==200 else 1)"

# Rendering is pure-Python + fast; 2 workers is plenty.
CMD ["gunicorn", "-b", "0.0.0.0:8082", "-w", "2", "--timeout", "60", "services.reporting.app:app"]
