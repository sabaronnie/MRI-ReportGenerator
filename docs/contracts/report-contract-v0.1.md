# Report Contract v0.1 — reporting ⇄ EEP/frontend boundary  **[FROZEN]**

> Companion to [`data-contract-v0.1.md`](data-contract-v0.1.md). That contract froze the **science core**
> (`measurements`/`flags`/`components`/`interpretations`). This one defines the **report surface** between
> **Ronnie's reporting service** (`services/reporting/`) and the **frontend/EEP track**.
>
> **Status: FROZEN v0.1** — ratified by Ronnie (reporting) 2026-06-07. Co-owned: Ronnie (producer) +
> frontend/EEP (consumer). Breaking changes bump `report.schema_version` and need both sides' sign-off.
>
> **Ratification adjustments folded in:** (1) `figure` is nullable; (2) reporting emits **artifact refs**,
> the **EEP serves** the public `/cases/{id}/...` URLs; (3) `/render` returns `{report, artifact_refs}`,
> not inline bytes.

## Boundary in one sentence
**Ronnie's `services/reporting/` _produces_ the `report` object + artifact refs (PDF/DOCX/figure) → the EEP _stores + serves_ them at public URLs → the frontend _renders_ them.** The frozen science core flows into reporting unchanged.

```
segmentation → measurements → interpretation → REPORTING (Ronnie) ──┐
                                   (frozen core)                     ▼
                                              report object + artifact_refs (keys)
                                                                    │
                                  EEP (stores artifacts, serves public URLs) ──┤
                                                                    ▼
                                                       frontend (renders)
```
Reporting is its own service ⇒ a **3rd IEP** (EEP + segmentation + measurements + reporting) → strengthens rubric **GT3**.

## Status legend
🟢 FROZEN · 🟡 LIKELY-TO-CHANGE · ⚪ OPEN

---

## 1. The `report` object (reporting emits; EEP fills public URLs; frontend renders)
A real instance ships in [`docs/contracts/samples/case-healthy.json`](samples/case-healthy.json) under `report`.

```json
{
  "schema_version": "report-0.1",
  "impression": [
    { "text": "Vertebral-body heights within the cohort reference range.",
      "traceable_to": ["vb_hahp_ratio"], "status": "within_reference", "severity": "normal" }
  ],
  "disclaimers": [ "All outputs are screens flagged for physician review, never a diagnosis.", "..." ],
  "findings_by_level": { "source": "interpretations.measurements", "order": ["C3","C4","C5","C6","C7"] },
  "figure": null,
  "exports": { "pdf_url": "/cases/{id}/report.pdf", "docx_url": "/cases/{id}/report.docx", "generated_at": "ISO-8601" },
  "metadata": { "generated_at": "ISO-8601", "schema_version": "report-0.1", "reporting_version": "x.y.z",
                "status": "final", "signed_by": null, "signed_at": null }
}
```

| field | status | who fills | notes |
|---|---|---|---|
| `impression[]` | 🟢 | reporting | `{text, traceable_to[], status, severity?}`. `status` = frozen 4-value enum. `traceable_to` = measurement_keys behind the line (UI links impression → measurement → citation). |
| `disclaimers[]` | 🟢 | reporting | Mandatory medical-AI disclaimers (§5). Always present + rendered. |
| `findings_by_level` | 🟢 | — | **NOT duplicated** — both report + UI read the frozen `interpretations.measurements[]`. `report` carries only display `order` (+ optional `highlight[]`). |
| `figure` | 🟢 | reporting | **Nullable.** `null` unless `/render` is given image artifacts (Q2). When present: `{kind:"png", annotated_png_url, caption}` where `annotated_png_url` is an **EEP-served** URL. |
| `exports` | 🟢 | reporting→**EEP** | Reporting returns artifact **refs**; the **EEP rewrites them into public URLs** (`/cases/{id}/report.pdf` etc.) in the object it serves the frontend. |
| `metadata` | 🟡 | reporting + EEP | `status` ∈ `draft`/`final`/`signed`. Sign-off fields filled by EEP (§6). |

---

## 2. Endpoints

### Public — frontend ↔ EEP (frontend/EEP track owns)
| method | path | role | returns |
|---|---|---|---|
| `POST` | `/auth/login` (+ Auth.js session routes) | everyone | session/JWT; role drives access |
| `POST` | `/cases` | Radiologist·Tech·Admin | upload DICOM `.zip` / NIfTI `.nii.gz` → `{case_id, status:"queued"}` |
| `GET` | `/cases` | all (role-filtered; Viewer=finalized only) | worklist: case summaries |
| `GET` | `/cases/{id}` | all | full case `{schema_version, case, job, measurements, flags, components, interpretations, report}` |
| `GET` | `/cases/{id}/job` | all | `job` (poll while processing) |
| `GET` | `/cases/{id}/report.pdf` · `/report.docx` | all | rendered document (EEP streams from artifact store) |
| `GET` | `/cases/{id}/figure.png` | all | annotated figure (if any) |
| `GET` | `/cases/{id}/volume` · `/mask` | all | NiiVue inputs (see `segmentation-viewer-v0.1.md`) |
| `POST` | `/cases/{id}/sign-off` | **Radiologist only** | marks report `signed` (§6) |

### Internal — EEP → reporting (Ronnie owns)
| method | path | input | output |
|---|---|---|---|
| `POST` | `/render` | `{case, measurements, flags, components, interpretations, image_artifacts?}` | `{report, artifact_refs}` |
| `GET` | `/healthz` `/readyz` `/metrics` | — | k8s probes + Prometheus |

- `image_artifacts?` (optional) 🟢: `{midsag_source_ref, seg_overlay_refs?}`. **If absent, text/table render fine and `report.figure = null`** (Q2).
- `artifact_refs` 🟢: `{pdf, docx, figure_png?}` — **local object names in dev, S3 keys in deploy** (Q1). Reporting never returns bytes in JSON.

---

## 3. Artifact serving flow (resolves adjustment 3 + Q1)
1. EEP calls `POST /render` with the frozen core (+ image artifacts if available).
2. Reporting renders, writes PDF/DOCX/PNG to the shared artifact store, returns `{report, artifact_refs:{pdf,docx,figure_png?}}`.
3. **EEP** records the refs, **rewrites** `report.exports.*` and `report.figure.annotated_png_url` into public `/cases/{id}/...` routes, and serves those routes by streaming bytes from the store.
4. Frontend only ever sees/uses the public EEP URLs.

---

## 4. Two image surfaces (no overlap)
- **Interactive NiiVue viewer** in the web UI → **frontend**, from `/volume`+`/mask` (live scroll/zoom/overlay).
- **Static annotated figure** in the PDF/DOCX (+ optional UI thumbnail) → **reporting** (matplotlib), exposed via `report.figure` + `GET /figure.png`.

---

## 5. Mandatory disclaimers (always in `disclaimers[]`)
- "This is a research tool, not a medical device. Not for clinical diagnosis."
- "All outputs are screens flagged for physician review, never a diagnosis."
- "Measurements acquired on supine MRI; functional radiographs may differ."
- "Demographic percentiles are relative to a clinical cohort (Duke CSpineSeg), not healthy volunteers."
- Where signal anomalies apply: "Signal-based anomalies flagged for physician review only; not a diagnosis."

---

## 6. Sign-off flow
1. Report generated → `report.metadata.status="final"`, `case.status="ready"`.
2. A **Radiologist** calls `POST /cases/{id}/sign-off`.
3. EEP sets `report.metadata.status="signed"`, `signed_by`, `signed_at`, `case.status="reviewed"`.
4. Signed reports immutable; a re-run creates a new version (versioning post-v0.1).

---

## 7. Resolved questions + reporting stack (ratified 2026-06-07)
- **Q1 exports:** `/render` returns `{report, artifact_refs}` — refs are local object names (dev) / **S3 keys** (deploy). No inline bytes. ✅
- **Q2 figure:** needs a mid-sagittal source + segmentation/overlay refs via `image_artifacts`; if absent, text still renders and `figure=null`. ✅
- **Q3 timing:** `/render` is **fast + synchronous**, called inline at job end. ✅
- **Q4 stack:** **Jinja2 + WeasyPrint** (PDF), **python-docx** (DOCX), **matplotlib** (annotated PNG). → infra containerizes these in the reporting image. ✅
- **Q5 impression:** **rule-based templating only, no LLM** (no LLMOps surface from reporting). ✅

---

## 8. Mock-first guidance (both sides)
- Frontend builds the report view against [`docs/contracts/samples/case-healthy.json`](samples/case-healthy.json)'s `report` block + this schema; reads cut values/citations/disclaimers **from the response**, never hardcoded; treats `figure` as possibly `null`.
- Reporting builds `/render` to emit exactly this `report` object + `artifact_refs`; validates against the same sample.
- Treat every measurement/flag key as optional (a component can error — data contract §3).
