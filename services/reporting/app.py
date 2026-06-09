"""Flask service exposing the reporting IEP.

Endpoints:
- GET  /healthz : liveness probe
- GET  /readyz  : readiness probe (verifies the builder + renderers import)
- GET  /metrics : Prometheus metrics scrape endpoint
- POST /render  : consume the post-interpretation handoff contract (the same JSON the
                  measurements IEP emits) and return the normalized report document plus
                  rendered HTML artifacts.

This is the second internal endpoint: it has its own responsibility (turn interpreted
findings into a clinician-facing report) and is architecturally independent from the
measurements IEP — the EEP orchestrates measurements -> reporting.
"""

from __future__ import annotations

import os
import time

from flask import Flask, Response, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from .builder import build_report_document
from .render_html import render_clinical_report_html, render_technical_report_html
from .render_pdf import render_clinical_report_pdf

app = Flask(__name__)

RENDERS = Counter("reporting_render_total", "Reports rendered", ["status"])
RENDER_LATENCY = Histogram("reporting_render_duration_seconds", "Report render latency (s)")


@app.get("/healthz")
def healthz():
    return jsonify(status="ok")


@app.get("/readyz")
def readyz():
    # Importable callables == ready to render.
    ready = callable(build_report_document) and callable(render_clinical_report_html)
    return (jsonify(status="ready"), 200) if ready else (jsonify(status="not-ready"), 503)


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


@app.post("/render")
def render():
    """Body = the post-interpretation handoff contract. Returns {report, artifacts}."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        RENDERS.labels("bad_request").inc()
        return jsonify(error="request body must be the JSON handoff contract"), 400

    start = time.perf_counter()
    try:
        document = build_report_document(payload)
        clinical_html = render_clinical_report_html(document)
        technical_html = render_technical_report_html(document)
    except (ValueError, KeyError, TypeError) as e:
        RENDERS.labels("error").inc()
        return jsonify(error=f"reporting failed: {e}"), 422
    finally:
        RENDER_LATENCY.observe(time.perf_counter() - start)

    RENDERS.labels("ok").inc()
    return jsonify(
        report=document,
        artifacts={"clinical_html": clinical_html, "technical_html": technical_html},
    )


@app.post("/render.pdf")
def render_pdf_route():
    """Body = the handoff contract. Returns the branded clinical report as a real PDF."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        RENDERS.labels("bad_request").inc()
        return jsonify(error="request body must be the JSON handoff contract"), 400
    start = time.perf_counter()
    try:
        document = build_report_document(payload)
        pdf = render_clinical_report_pdf(document)
    except (ValueError, KeyError, TypeError) as e:
        RENDERS.labels("error").inc()
        return jsonify(error=f"reporting failed: {e}"), 422
    finally:
        RENDER_LATENCY.observe(time.perf_counter() - start)
    RENDERS.labels("ok").inc()
    return Response(bytes(pdf), mimetype="application/pdf")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8082))
    app.run(host="0.0.0.0", port=port, debug=False)
