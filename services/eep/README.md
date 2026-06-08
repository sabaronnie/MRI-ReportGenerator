# EEP — External Endpoint (FastAPI)

The public system boundary (rubric §4.3). Orchestrates the internal IEPs
(segmentation → measurements → interpretation → reporting) and exposes the API the frontend consumes
(see `docs/contracts/report-contract-v0.1.md` §2).

## Run
```bash
pip install -r services/eep/requirements.txt
PYTHONPATH=. uvicorn services.eep.app:app --host 0.0.0.0 --port 8080
```
Interactive docs at `/docs`. Health `/healthz` `/readyz`. Prometheus `/metrics`.

## Endpoints
`GET /cases` · `POST /cases` (upload DICOM `.zip` / NIfTI) · `GET /cases/{id}` · `GET /cases/{id}/job` ·
`POST /cases/{id}/sign-off` · `GET /cases/{id}/volume|/mask` (NiiVue).

## Modes
- **Fixture mode** (default): serves 3 bundled sample cases; uploads run a simulated queued→…→ready pipeline.
- **Live orchestration**: set `MEASUREMENTS_URL` (+ provide a stand-in `segmentation.zip`) and uploads call the
  measurements IEP for real. See `deployment/compose/`.

## Config (env — see `config.py`)
`MEASUREMENTS_URL` · `EEP_SAMPLE_DIR` · `EEP_ALLOWED_ORIGINS` · `MAX_UPLOAD_BYTES` ·
`EEP_RATE_LIMIT_MAX` / `EEP_RATE_LIMIT_WINDOW_S` · `EEP_SIM_TOTAL_S`.

## Architecture notes
- Cross-cutting: CORS (frontend origin), per-IP fixed-window rate limit, request metrics, upload validation
  (type + size), structured error shape `{code,message,failed_stage,retryable}`.
- In-memory case store (`store.py`) — a real datastore (Postgres) replaces it in the deployment track.
- Segmentation (TotalSpineSeg/SCT, GPU/Colab) runs upstream — the EEP consumes a mask, it doesn't run deepseg.
