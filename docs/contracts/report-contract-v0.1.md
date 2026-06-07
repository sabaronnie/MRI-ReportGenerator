# Report Contract v0.1 — reporting ⇄ EEP/frontend boundary

> Companion to [`data-contract-v0.1.md`](data-contract-v0.1.md). That contract froze the **science core**
> (`measurements`/`flags`/`components`/`interpretations`). This one defines the **one surface still open**
> between **Ronnie's reporting service** (`services/reporting/`) and the **frontend/EEP track**: the
> `report` object and the report-related endpoints.
>
> **Status:** DRAFT proposal by the frontend/EEP track (the *consumer*) — **for Ronnie to ratify.**
> **Co-owned** once ratified: Ronnie (producer) + frontend/EEP (consumer). Versioned here.

## Boundary in one sentence
**Ronnie's `services/reporting/` _produces_ the `report` object + the PDF/DOCX documents → the EEP _serves_ them → the frontend _renders_ them.** The frozen science core flows into both sides unchanged.

```
segmentation → measurements → interpretation → REPORTING (Ronnie) ──┐
                                   (frozen core)                     ▼
                                                        report object + PDF/DOCX
                                                                    │
                                            EEP (serves) ───────────┤
                                                                    ▼
                                                       frontend (renders)
```
Reporting is its own service ⇒ it counts as a **3rd IEP** (EEP + segmentation + measurements + reporting), which strengthens rubric **GT3**.

## Status legend
🟢 FROZEN (proposed-frozen on ratification) · 🟡 LIKELY-TO-CHANGE · ⚪ OPEN (Ronnie decides / answer below)

---

## 1. The `report` object (Ronnie emits, frontend renders)
Extends the rough §10 in the data contract. A real instance already ships inside
[`samples/case-healthy.json`](samples/case-healthy.json) under `report` — this formalizes + extends it.

```json
{
  "schema_version": "report-0.1",
  "impression": [
    { "text": "Vertebral-body heights within the cohort reference range.",
      "traceable_to": ["vb_hahp_ratio"],
      "status": "within_reference",
      "severity": "normal" }
  ],
  "disclaimers": [ "All outputs are screens flagged for physician review, never a diagnosis.", "..." ],
  "findings_by_level": { "source": "interpretations.measurements", "order": ["C3","C4","C5","C6","C7"] },
  "figure": { "kind": "png", "annotated_png_url": "/cases/{id}/figure.png", "caption": "Mid-sagittal, level overlays" },
  "exports": { "pdf_url": "/cases/{id}/report.pdf", "docx_url": "/cases/{id}/report.docx", "generated_at": "ISO-8601" },
  "metadata": { "generated_at": "ISO-8601", "schema_version": "report-0.1",
                "reporting_version": "x.y.z", "status": "final",
                "signed_by": null, "signed_at": null }
}
```

| field | status | who fills | notes |
|---|---|---|---|
| `impression[]` | 🟢 | reporting | `{text, traceable_to[], status, severity?}`. `status` reuses the **frozen 4-value enum** (`within_reference`/`outside_reference`/`review_only`/`not_interpretable`). `traceable_to` = the `measurement_key`s behind the line so the UI can link impression → measurement → citation. |
| `disclaimers[]` | 🟢 | reporting | The mandatory medical-AI disclaimers (see §4). Always present, always rendered. |
| `findings_by_level` | 🟢 | — | **NOT duplicated.** The per-level table is read from the frozen `interpretations.measurements[]` by BOTH the report and the UI. `report` only carries display `order` (+ optional `highlight[]`). This is what prevents drift. |
| `figure` | 🟡 | reporting | The **static annotated image** embedded in the PDF/DOCX (and usable as a UI thumbnail). Distinct from the interactive NiiVue viewer — see §3. |
| `exports` | 🟡 | reporting→EEP | The download links. The real producer/consumer handoff. URLs served by the EEP (§2); how the bytes are stored is ⚪ (see Q1). |
| `metadata` | 🟡 | reporting + EEP | `status` ∈ `draft`/`final`/`signed`. Sign-off fields filled by the EEP on sign-off (§5). |

---

## 2. Endpoints

### Public — frontend ↔ EEP (frontend/EEP track owns)
| method | path | role | returns |
|---|---|---|---|
| `POST` | `/cases` | Radiologist·Tech·Admin | upload DICOM `.zip` / NIfTI `.nii.gz` → `{case_id, status}` |
| `GET` | `/cases` | all (role-filtered; Viewer=finalized only) | worklist: list of case summaries |
| `GET` | `/cases/{id}` | all | full case `{schema_version, case, job, measurements, flags, components, interpretations, report}` |
| `GET` | `/cases/{id}/job` | all | `job` (poll while processing) |
| `GET` | `/cases/{id}/report.pdf` · `/report.docx` | all | the rendered document (stream) |
| `GET` | `/cases/{id}/figure.png` | all | the annotated figure |
| `GET` | `/cases/{id}/volume` · `/mask` | all | NiiVue inputs (see `segmentation-viewer-v0.1.md`) |
| `POST` | `/cases/{id}/sign-off` | **Radiologist only** | marks report `signed` (§5) |

### Internal — EEP → reporting (Ronnie owns)
| method | path | input | output |
|---|---|---|---|
| `POST` | `/render` | the **frozen case core**: `{case, measurements, flags, components, interpretations}` | `{report, pdf, docx, figure}` (objects or stored refs — see Q1) |
| `GET` | `/healthz` `/readyz` `/metrics` | — | k8s probes + Prometheus (match the measurements service convention) |

Reporting needs only the **frozen core** as input — no raw image required for the text/table. (Figure rendering may need the segmentation overlay — see Q2.)

---

## 3. Two image surfaces (important — avoids overlap)
- **Interactive NiiVue viewer** in the web UI → **frontend** renders it from `/volume` + `/mask` (live scroll/zoom/overlay). Not reporting's concern.
- **Static annotated figure** embedded in the **PDF/DOCX** → **reporting** renders it (a document can't hold an interactive viewer). Exposed as `report.figure` + `GET /figure.png`, and usable as a UI thumbnail/fallback.

So: Ronnie owns the *document figure*; the frontend owns the *interactive viewer*. No duplication of responsibility.

---

## 4. Mandatory disclaimers (medical-AI hard rule — always in `disclaimers[]`)
At minimum (from Phase 6):
- "This is a research tool, not a medical device. Not for clinical diagnosis."
- "All outputs are screens flagged for physician review, never a diagnosis."
- "Measurements acquired on supine MRI; functional radiographs may differ."
- "Demographic percentiles are relative to a clinical cohort (Duke CSpineSeg), not healthy volunteers."
- Where signal anomalies apply: "Signal-based anomalies flagged for physician review only; not a diagnosis."

---

## 5. Sign-off flow
1. Report is generated → `report.metadata.status = "final"`, `case.status = "ready"`.
2. A **Radiologist** calls `POST /cases/{id}/sign-off`.
3. EEP sets `report.metadata.status = "signed"`, `signed_by`, `signed_at`, and `case.status = "reviewed"`.
4. Signed reports are immutable; a re-run creates a new version (versioning ⚪, post-v0.1).

---

## 6. Open questions for Ronnie to ratify
- **Q1 — export storage:** does `/render` return PDF/DOCX **bytes**, or write to **object storage (S3)** and return keys the EEP serves? (Infra leans S3 for k8s statelessness; bytes are simpler for the demo. Your call.)
- **Q2 — figure inputs:** to render the annotated figure, does reporting need the **segmentation masks / mid-sagittal slice** passed in? If so we add `seg_ref`/`slice` to the `/render` input. (Or reporting pulls from the same artifact store.)
- **Q3 — render timing:** confirm `/render` is **fast + synchronous** (seconds, given the core) so the EEP calls it inline at the end of the job — agreed?
- **Q4 — rendering tech:** `reportlab` / `weasyprint` (HTML→PDF) / `python-docx`? (Affects the Docker image; infra will containerize whatever you pick.)
- **Q5 — impression generation:** rule-based templating from the interpreted core (as Phase 6 §6.2), correct? Any LLM involvement (would add an LLMOps surface)?

---

## 7. Mock-first guidance (both sides)
- Frontend builds the report view against `case-healthy.json`'s `report` block + this schema; reads cut values/citations/disclaimers **from the response**, never hardcoded.
- Reporting builds `/render` to emit exactly this `report` object; validate it against the same sample.
- Treat every measurement/flag key as optional (a component can error — data contract §3).

**Versioning:** breaking changes bump `report.schema_version`. Changes ratified by both Ronnie + frontend/EEP track.
