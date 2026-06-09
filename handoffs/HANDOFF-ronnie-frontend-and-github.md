═══════════════════════════════════════════════════════════════════════════════════════════════════
HANDOFF — Ronnie: finish the project (GitHub merge + final frontend linking) · 2026-06-09
From: Andrew (deployment/infra chat). The whole backend pipeline is DONE, validated, and pushed. AWS is
TORN DOWN — the professor runs everything on HIS OWN machine, locally. Two things remain, both yours:
  A) GitHub: reconcile the two branches + merge to main.
  B) Frontend: link the live UI so a local `docker compose up` runs the full pipeline for the professor.
═══════════════════════════════════════════════════════════════════════════════════════════════════

## 0) STATE OF THE WORLD (so you start warm)
- The real **3-engine DAG works** (TSS ∥ SPINEPS → SCT) and the **live e2e passed** on AWS before teardown:
  upload → DAG → measurements → report `ready`. Then AWS was deleted (cost stopped) — the deliverable is
  the **reproducible repo**, which is complete and correct.
- **Canned demo is gone** (code + deployed). Don't bring it back. Auth seed = `admin@demo` / `demo12345`.
- **Everything is pushed.** Nothing is stranded locally.
- Known deferred gap (NOT blocking): **G5.1 SCIseg lesion reader** is not wired into the measurements
  service (the lesion *mask* IS produced by SCT; only the measurement-component that surfaces it in the
  report is missing — it lives on `research/andrew/groups-5-6-week1` / `group5-proto`). Wire it only if the
  team wants G5.1 findings in the report. Out of scope for "make the demo work."

═══════════════════════════════════════════════════════════════════════════════════════════════════
## PART A — GITHUB: reconcile + merge to main
═══════════════════════════════════════════════════════════════════════════════════════════════════

### The two branches (both pushed, both have OPEN PRs to main)
- **PR #6 — `feat/eep/auth-async-integration`** = the **canonical APP**: EEP real-DAG client + async upload
  (202 + background worker), measurements G3/G4, JWT auth, workflow, PDF, clinical frontend integration,
  and the SCT 7.0 fixes for the app side (`sc_canal_t2`, measurements `sct_process_segmentation -vertfile`,
  measurements Dockerfile installs the SCT CLI).
- **PR #7 — `feat/seg/deploy`** = the **seg/infra/docs**: the 3 engine Dockerfiles (seg-tss/sct/spineps),
  k8s manifests, seg node-group IaC, the RUNBOOK, DEVELOPMENT_JOURNEY (J27–J29), the SCT canal bake fix
  in `seg-sct.Dockerfile`, and these handoffs.

### Why I did NOT auto-merge (don't `git push` to main blindly)
`main` is protected and has moved **+18 commits** since both branches forked. The branches are
**+133 (integration)** and **+67 (seg/deploy)**, and they **diverge from each other** (seg/deploy has 10
unique commits, integration has 76). A dry-run merge shows **real conflicts**. So this is a deliberate
reconciliation, not a one-click merge.

### Recommended reconciliation (do this in a worktree, run the tests)
1. Branch off the canonical app:  `git switch -c chore/reconcile-main origin/feat/eep/auth-async-integration`
2. Merge in the seg/infra branch: `git merge origin/feat/seg/deploy`
   - These two touch **mostly different files** (app code vs seg Dockerfiles/runbook/docs), so most of it is
     additive. **Keep BOTH sets of fixes** when resolving:
     - from `feat/seg/deploy`: `seg-sct.Dockerfile` (canal bake = `sc_canal_t2`), the other seg Dockerfiles,
       k8s/IaC, the runbook + journey.
     - from `feat/eep/auth-async-integration`: the EEP app, `measurements.Dockerfile` (SCT CLI install),
       `services/measurements/sct.py` (`-vertfile`).
     - `sct_segmenter.py` / `functional_canal_ap.py` have the `sc_canal_t2` fix on BOTH — either side is fine.
3. Merge in the moved-on main:    `git merge origin/main`   (resolve the +18 divergence)
4. **Test before the PR:** EEP suite (`services/eep/tests`, ~49 tests) + measurements/segmentation unit tests.
5. Open ONE PR `chore/reconcile-main → main`, get a teammate review, merge. Then PRs #6/#7 close naturally.
   (Alternatively, agree with the team to make `feat/eep/auth-async-integration` the base and cherry-pick the
   seg/deploy-only files — same end state.)

═══════════════════════════════════════════════════════════════════════════════════════════════════
## PART B — FRONTEND: link the live UI for the professor's local run
═══════════════════════════════════════════════════════════════════════════════════════════════════
Full detail is in `handoffs/HANDOFF-frontend-linking-for-ronnie.md`. Summary:

### Already done (don't redo)
- Frontend has a **live mode**: `NEXT_PUBLIC_API_MODE=live` → `NEXT_PUBLIC_EEP_URL` (`frontend/Dockerfile`).
- `deployment/compose/docker-compose.yml` wires `frontend(3000, live→localhost:8080) → eep(8080) →
  measurements(8081)`; EEP CORS allows `http://localhost:3000`.

### The ONE big gap — add the 3 seg engines to the local compose
Compose has eep→measurements but **no seg services**, so an upload won't run the real pipeline locally. Add:
- `seg-tss` (`deployment/docker/seg-tss.Dockerfile`, 8083, `/segment`)
- `seg-sct` (`deployment/docker/seg-sct.Dockerfile`, 8084, `/segment-sct`)
- `seg-spineps` (`deployment/docker/seg-spineps.Dockerfile`, 8085, `/segment`)  ← needs ≥~40 GB RAM + real `/dev/shm`
- on `eep`: `SEG_TSS_URL=http://seg-tss:8083  SEG_SCT_URL=http://seg-sct:8084  SEG_SPINEPS_URL=http://seg-spineps:8085`

### Verify the live client matches the REAL EEP contract (verified live this session)
- `POST /auth/login` `{email,password}` → `{token}` (Bearer on `/cases*`)
- `POST /cases` multipart `file` + `uploader` → **202** `{case_id, status:"queued"}`
- `GET /cases/{id}/job` → `{stage, stages:[queued,segmenting,measuring,assessing,ready], progress, error}`
- `GET /cases/{id}` (measurements/flags/components/assessements/report), `/report.html`, `/report.pdf`,
  `/mask`, `/volume` (NiiVue viewer)

### #1 linking detail — the job is async and MINUTES long
Upload returns 202 instantly; the pipeline runs in the background (**~13 min/case on CPU**). The UI must
**poll `/cases/{id}/job`** and show stage/progress until `ready` (or surface `error`). Make sure the polling
UX and any fetch/proxy timeouts tolerate minutes, not seconds.

### Gotchas
- Measurements MUST be the **SCT-CLI** image (G3 needs `sct_process_segmentation`) — build from
  `feat/eep/auth-async-integration`'s `measurements.Dockerfile`, not an older branch.
- SPINEPS OOMs under ~32–40 GB CPU RAM → if the professor's laptop can't give that, G4 Cobb won't run;
  tell him the RAM requirement.
- C3–C7 global Cobb can no-op when C7 is obscured at the cervicothoracic junction (data, not a bug);
  per-level `segmental_angles` still works.

### Definition of done (frontend)
Clean checkout → `docker compose -f deployment/compose/docker-compose.yml up --build` (with the 3 seg
services added) → open `http://localhost:3000` → log in (`admin@demo`/`demo12345`) → upload
`deployment/compose/sample_data/sample_volume_T2.nii.gz` → job runs to `ready` → report renders with the
NiiVue viewer showing masks. That's the professor-ready linked demo.

═══════════════════════════════════════════════════════════════════════════════════════════════════
## YOUR CHECKLIST
[ ] A. Reconcile `feat/eep/auth-async-integration` + `feat/seg/deploy` + `main` → one PR → review → merge to main
[ ] B. Add the 3 seg services to the local compose + wire SEG_*_URL on the EEP
[ ] B. Verify the live frontend client hits the real EEP contract + handles the async (~13 min) job poll
[ ] B. `docker compose up --build` green-path demo (login → upload sample → ready → report + viewer)
[ ] (optional) Wire G5.1 SCIseg lesion reader into measurements if the team wants G5.1 findings
Reference docs in repo: docs/RUNBOOK-run-the-3-models.md, DEVELOPMENT_JOURNEY.md (J27–J29), SESSION_LOG.md
═══════════════════════════════════════════════════════════════════════════════════════════════════
