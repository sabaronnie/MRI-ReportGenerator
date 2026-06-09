# Local stack (Docker Compose)

## Run the professor-ready full stack
```bash
cd deployment/compose
docker compose up --build
```
- **Frontend** (Next.js, live mode) → http://localhost:3000
- **EEP** (FastAPI) → http://localhost:8080 — `/docs`, `/healthz`, `/readyz`, `/metrics`
- **measurements IEP** (Flask) → http://localhost:8081 — `/healthz`, `/readyz`, `/metrics`
- **reporting IEP** (Flask) → http://localhost:8082 — `/healthz`
- **seg-tss** → http://localhost:8083 — `POST /segment`
- **seg-sct** → http://localhost:8084 — `POST /segment-sct`
- **seg-spineps** → http://localhost:8085 — `POST /segment`

The EEP now reaches the internal services through:
- `MEASUREMENTS_URL=http://measurements:8081`
- `REPORTING_URL=http://reporting:8082`
- `SEG_TSS_URL=http://seg-tss:8083`
- `SEG_SCT_URL=http://seg-sct:8084`
- `SEG_SPINEPS_URL=http://seg-spineps:8085`

## Sample data
Drop these into `deployment/compose/sample_data/` (gitignored — never committed):
- `sample_volume_T2.nii.gz`, `sample_mask_tss.nii.gz` — served by `GET /cases/{id}/volume|/mask` for NiiVue.
- `segmentation.zip` — optional fallback artifact for the sample viewer data.

## Notes
- This stack is heavy. The real 3-engine DAG is CPU-capable, but expect roughly 13 minutes per case.
- `seg-spineps` needs a real shared-memory segment and about 40 GB RAM on CPU; the compose file sets
  `shm_size` and `mem_limit` accordingly.
- The frontend is built in `NEXT_PUBLIC_API_MODE=live` and points to `http://localhost:8080`.
- Login seed: `admin@demo` / `demo12345`.

## Goal check
After the stack is up:
1. Open `http://localhost:3000`
2. Log in with `admin@demo` / `demo12345`
3. Upload `deployment/compose/sample_data/sample_volume_T2.nii.gz`
4. Wait for `queued -> segmenting -> measuring -> interpreting -> ready`
5. Confirm the report and NiiVue viewer render
