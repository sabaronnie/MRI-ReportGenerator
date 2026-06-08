"""External Endpoint (EEP) — the public FastAPI boundary that orchestrates the internal IEPs.

Responsibilities: input validation + upload limits, request rate-limiting, CORS for the frontend,
Prometheus metrics, health/readiness, and orchestration of the measurements IEP (see orchestration.py).
Run: uvicorn services.eep.app:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from . import config, store
from .orchestration import measurements_ready
from .routers import cases

app = FastAPI(title="MRI-ReportGenerator EEP", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REQUESTS = Counter("eep_requests_total", "EEP requests", ["method", "path", "status"])
LATENCY = Histogram("eep_request_duration_seconds", "EEP request latency (s)", ["method", "path"])

# Fixed-window per-IP rate limit (per worker; a shared store replaces this in deploy).
_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def observe_and_limit(request: Request, call_next):
    ip = request.client.host if request.client else "?"
    now = time.monotonic()
    window = _hits[ip]
    while window and window[0] < now - config.RATE_LIMIT_WINDOW_S:
        window.popleft()
    if request.url.path.startswith("/cases") and len(window) >= config.RATE_LIMIT_MAX:
        return JSONResponse(
            status_code=429,
            content={"code": "rate_limited", "message": "too many requests", "retryable": True},
        )
    window.append(now)

    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start
    route = request.scope.get("route")
    path_tmpl = getattr(route, "path", request.url.path) if route else request.url.path
    LATENCY.labels(request.method, path_tmpl).observe(duration)
    REQUESTS.labels(request.method, path_tmpl, str(response.status_code)).inc()
    return response


@app.get("/healthz")
def healthz():
    return {"service": "eep", "status": "ok"}


@app.get("/readyz")
def readyz():
    return {"status": "ready", "cases": len(store.list_cases()), "measurements_ready": measurements_ready()}


@app.get("/metrics")
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(cases.router)
