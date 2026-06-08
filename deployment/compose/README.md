# Local stack (Docker Compose)

## Run the backend (EEP + measurements IEP)
```bash
cd deployment/compose
docker compose up --build
```
- **EEP** (FastAPI) → http://localhost:8080 — `/docs`, `/healthz`, `/readyz`, `/metrics`
- **measurements IEP** (Flask) → http://localhost:8081 — `/healthz`, `/readyz`, `/metrics`
- The EEP reaches the measurements IEP via `MEASUREMENTS_URL=http://measurements:8081` (real EEP→IEP orchestration).

## Sample data (viewer + real orchestration)
Drop these into `deployment/compose/sample_data/` (gitignored — never committed):
- `sample_volume_T2.nii.gz`, `sample_mask_tss.nii.gz` — served by `GET /cases/{id}/volume|/mask` for NiiVue.
- `segmentation.zip` (containing `step2_output.nii.gz`) — lets the EEP call the measurements IEP for **real**
  on upload; without it the EEP returns the cloned-fixture core.

## Add the frontend (after feat/frontend merges to main)
Once `frontend/` exists at the repo root:
```bash
docker compose --profile fullstack up --build   # frontend on :3000, built NEXT_PUBLIC_API_MODE=live
```
Until then run it from its worktree: `npm run dev` in `frontend-worktree/frontend`.

## Notes
- **Segmentation (TotalSpineSeg/SCT) is intentionally not containerized** — it's GPU/Colab; the EEP uses a
  stand-in mask. Reporting (Ronnie) is pending.
- Three images (EEP, measurements, frontend) satisfy the rubric's containerization minimum.
