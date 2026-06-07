# Frontend Design — MRI-ReportGenerator web app

**Owner:** Andrew (frontend/infra track) · **Status:** v0.1, building · **Date:** 2026-06-07

## Purpose
A polished web app for cervical-spine MRI **triage + reporting**. A scan is uploaded → auto-analyzed by the
pipeline → a radiologist reviews a structured report and signs off. Target deployer: radiology departments /
research-hospital workflows. (Non-AI baseline: manual radiologist measurement — slow, high inter-observer variance.)

## Users & roles (RBAC)
| Role | Who | Can |
|---|---|---|
| **Admin** | us / IT | manage users + settings, see all cases. **Cannot sign** (not a clinician). |
| **Radiologist** | interpreting physician | work the worklist, review/adjust, **only role that signs off**. |
| **Technologist** | MRI tech | upload/register scans, monitor processing, view results. Cannot sign. |
| **Viewer** | nurse / referring doctor | **read-only** access to finalized reports. |

## Screens (Next.js App Router routes)
- `/login` — Auth.js sign-in
- `/worklist` — landing: case queue, role-filtered, per-case status + triage badge
- `/cases/[id]` — report view: findings table + impressions + disclaimers + **interactive NiiVue viewer** + sign-off
- `/upload` — drag-drop DICOM `.zip` / NIfTI `.nii.gz`
- `/admin` — user management (Admin only)
- per-case **PDF/DOCX** export (EEP-served)

## Architecture
- **Next.js (App Router, TypeScript).** The same components run against a **mock API** now and the **real EEP**
  later — flip with `NEXT_PUBLIC_API_MODE=mock|live`. The frontend talks **only to the EEP**.
- **Boundaries** (each small + testable): `app/` routes · `components/` shadcn UI (`components/viewer/` = NiiVue) ·
  `lib/api/` typed client + contract types (single source of truth) · `mocks/` MSW handlers + fixtures ·
  `lib/auth/` Auth.js + role guards.

## MRI viewer
Full interactive **NiiVue** (WebGL): scroll slices, zoom/pan, toggle the segmentation overlay. Inputs from the EEP
`/cases/{id}/volume` + `/mask` (see `docs/contracts/segmentation-viewer-v0.1.md`). The static figure embedded in the
PDF is **reporting's** job, not ours.

## Stack
Next.js · TypeScript · Tailwind · **shadcn/ui** · TanStack Query · **MSW** (mock) · Auth.js · **NiiVue**.

## Contract it builds against (frozen)
- `docs/contracts/data-contract-v0.1.md` — frozen core (`measurements`/`flags`/`components`/`interpretations`).
- `docs/contracts/report-contract-v0.1.md` — `report` object + the EEP endpoints + request workflow.
- Render the findings table from `interpretations.measurements[]`; impressions/disclaimers from `report`.
- **Read thresholds/citations from the response, never hardcode. Treat every measurement/flag key as optional.**

## Endpoints consumed (EEP public API)
`POST /auth/login` · `POST /cases` · `GET /cases` · `GET /cases/{id}` · `GET /cases/{id}/job` ·
`GET /cases/{id}/report.pdf|.docx` · `GET /cases/{id}/figure.png` · `GET /cases/{id}/volume|/mask` ·
`POST /cases/{id}/sign-off`.

## Mock-first
Vendor the 3 sample fixtures (`case-healthy`, `case-stenosis`, `case-fracture`) from `docs/contracts/samples/`.
MSW intercepts API calls and serves them; flip to the live EEP later with no code change. Build + demo never
blocked on the backend.

## Milestones
0. **Foundation** — worktree · scaffold · shadcn · contract types · mock layer ← *current*
1. **Worklist** — the case queue rendering mock cases (status, triage badges)
2. **Case detail** — findings table + impressions + disclaimers
3. **NiiVue viewer**
4. **Auth + roles**
5. **Upload + processing** — upload + job-status polling
6. **Polish** — loading/error/empty states, responsive, dark mode
7. **Containerize** — Dockerfile (→ infra track)

## Not ours (other chats own these)
- Reporting service (`/render`, PDF/DOCX/figure) → **Ronnie**.
- Science internals (segmentation, measurements, interpretation) → **science/executor chat**.
- We build the EEP, wiring its IEP orchestration as those services firm up.

## Discipline
Granular commits at each logical stage · plain imperative messages, **no signatures** · `feat/frontend/*` branches ·
stage by name · never secrets/patient data.
