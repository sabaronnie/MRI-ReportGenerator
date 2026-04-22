# Phase 7 — Deferred / future work

**Owner:** TBD
**Reviewer:** TBD
**Status:** v1 content imported — under team review
**Last updated:** 2026-04-22 by Andrew (initial import from master_plan_v1.md)

---

## What a reviewer should check

- Does the method chosen actually work on Duke's segmentation masks?
- Are the alternatives rejected for the right reasons?
- Is any repo/reference missing? Add it if so.
- Does anything here conflict with another phase? Flag it.
- Is anything unclear? Mark it as an open question at the bottom.

---

Explicit list of things explicitly out of scope, with why:

| Item | Why deferred | What it would take |
|---|---|---|
| Axial MRI input + canal transverse width | Second input file + cross-orientation level matching | 2–4 weeks |
| Facet joint segmentation and analysis | Needs new segmentation model (not in TotalSpineSeg) + axial input | 1–3 months |
| Fracture detection (geometric + marrow edema) | T1/STIR input + fracture classifier | Own research project |
| Tumor detection | Own annotated dataset + classifier | Own research project |
| Post-surgical scar detection | Contrast-enhanced sequences not in input spec | Extend input pipeline |
| Full 5-grade cervical Pfirrmann classifier | No open-source cervical model; would need to train | 2–3 months with annotated data |
| Modic change detection | Trainable (SpineNet does it for lumbar) | 1–2 months to adapt |
| Osteoporosis proxy from MRI | MRI is not gold standard; poor evidence base for cervical | Not recommended at all |
| Foraminal stenosis | Requires oblique views | Requires protocol change |

---
## Open questions specific to this phase

(Append questions here as they come up during research. One per bullet.)

- _(none yet)_

## Session notes

(Append brief notes by date/author as research progresses. Don't delete old notes.)

- _(none yet)_
