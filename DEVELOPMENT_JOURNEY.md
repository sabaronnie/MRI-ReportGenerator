# Development Journey — how we made the measurements accurate

The methodology narrative for the report + papers: each substantive **mistake → how we found it →
the fix → how we validated it**. This is the science. Append a new entry for every correction;
keep it honest and specific (numbers, dates, evidence, citations). Chronological detail lives in
`SESSION_LOG.md`; this file is the curated "how we reached accuracy" story.

> Validation philosophy used throughout: with **no public dataset pairing cervical MRI to expert
> measurements** (confirmed across repeated hunts → that's the AUBMC gap), "accurate" means
> **"healthy lands in the published normal range + discriminates pathology, with documented limits,"**
> not gold-standard clinical proof. Where a norm/method was uncertain we launched an adversarial
> research workflow to ground it in primary sources (Perplexity banned — it confabulates).

---

## J1 — Vertebral-body fracture norm: a phantom 0.97±0.02 → cohort-derived 0.94±0.13 (Group 5.2)
- **What we had:** an in-code "healthy" anterior/posterior height ratio Ha/Hp = **0.97 ± 0.02** with a
  0.80 wedge cutoff.
- **What was wrong:** unsourced. A 75-agent literature search traced 0.97±0.02 to **Sorci 2024**
  (PMC11718528) — a 62%-osteoporotic, all-female, mean-age-67.6 cohort (NOT healthy), and the ±0.02
  was a spread-of-level-means, not a within-population SD.
- **How we found it:** measured Ha/Hp on 12 healthy Spine-Generic necks (n=60 C3–C7) = **0.94 ± 0.13**;
  it sat in the true healthy range **0.88–0.95** (Tan 2004 PMC3476578, Lee 2012, Kaur 2025 — cadaver,
  posterior > anterior) but well off the phantom. The old cutoff over-flagged **17%** of healthy.
- **The fix:** recalibrated to the measured cohort norm; added a data-driven `cervical_deformity_flag`
  (flag Ha/Hp < mean − z·SD, z=2 → ~0.68), separate from the medical Genant grade. **z=2.0 confirmed**
  by a 62-agent search (no cervical compression-fracture Ha/Hp data exists; the wide SD is the real
  lever).
- **Validated:** healthy false-positive rate **17% → 0%** (0/60); discriminates DCM (0.85) from healthy
  (0.92); resolution-controlled (0.8 mm ≈ 4 mm). Cite Tan 2004 / Lee 2012 / Kaur 2025 + Chen 2013 / Nell 2019.

## J2 — Body isolation: erosion/connected-component heuristics → the canal-cut (Group 5.2)
- **What we tried:** isolate the vertebral body from the posterior arch by connected components, then
  erosion-at-the-pedicle-neck.
- **What was wrong:** on real cervical masks the body and arch are one fused blob on the mid-sagittal
  slice; the heuristics left a wedge-shaped body → a stuck healthy ratio ~0.86 and false wedges.
- **How we found it:** the ratio wouldn't move across 5 measurement methods; root-caused to the *input*
  (body isolation), not the math (unit tests on clean rectangles gave Ha=Hp).
- **The fix:** **canal-cut** — the body is everything anterior to the spinal canal (TSS gives canal=2),
  a principled anatomical boundary. `extract_body_via_canal`.
- **Validated:** synthetic healthy 0.86 → 1.00, no false wedges, real wedge still caught; then the real
  Duke + healthy validation in J1/J3.

## J3 — Height measurement: image-axis edge fractions → PCA + endplate-LINE fitting (Group 5.2)
- **What we had:** per-column SI-extent heights along the image axes.
- **What was wrong:** cervical TILT + posterior taper made it garbage on real Duke T2 (per-vertebra
  Ha/Hp ranged [0.64, 4.60]).
- **The fix:** **PCA tilt-orient** (measure on the body's own axes) + fit **straight LINES to the
  superior/inferior endplates** and read the gap at the margins (a thin-bin filter drops tails/rounded
  tips). Robust to tilt and taper.
- **Validated:** spread collapsed to [0.77, 1.01]; locked behind 30 TDD tests (tilt-invariance,
  taper-robustness, orientation-invariance). **This endplate-LINE idea is the candidate fix for the
  teammates' corner-instability problem — see J6.**

## J4 — Fracture scope: "any fracture detector" → vertebral-body COMPRESSION screen (Group 5.2)
- **What we attempted:** detect "any cervical fracture" via the wedge metric, validated vs RSNA-2022.
- **What was wrong:** RSNA cervical fractures are predominantly non-compression (odontoid/facet/arch);
  healthy 0.86 vs fractured 0.88 — the geometric wedge metric has **~zero** power there.
- **The fix / honesty:** scoped 5.2 to a **vertebral-body compression/deformity screen — flag for
  physician review**, NOT a general fracture detector; banked the RSNA negative result; documented the
  per-vertebra SD (±0.13 → coarse) and the no-MRI-comparator (triangulation) caveat.

## J5 — Myelomalacia: hand-rolled intensity thresholds → adopt SCIseg (Group 5.1)
- **What we tried:** flag cord T2-hyperintensity by intensity thresholds (Weber CSF-ratio + local window).
- **What was wrong:** simple thresholds can't separate lesion from normal cord variation (validated vs
  SCIseg on 10 Duke cases: ~0% sensitivity, or ~97 false positives/healthy case at a bright-tail cutoff).
- **The fix:** adopt **SCIseg** (`sct_deepseg lesion_sci_t2`, published/validated) as the engine; keep the
  hand-rolled version as an interpretable baseline. Our job became the **specificity** check ("on healthy,
  flags nothing") — pending a Colab run on the 12 healthy cords.

## J6 — Validating the teammates' code: an over-claim, corrected — and the keystone (Groups 1/3/4)
- **What we did:** ran the teammates' measurement code on the 12 healthy necks and reported the flag rates.
- **The mistake (ours, important to document):** we first concluded "their measurements are inaccurate."
  That was an **over-reach** — we treated *every* flag as a clinical false-positive, when some
  (e.g. `tilt_outlier`) are **measurement-quality/caution** flags, not "this patient is abnormal." We were
  also judging from the outside without confirming intended flag semantics or running their canonical version.
- **How we corrected:** (a) separated **clinical** flags (wedge, spondylolisthesis, SAC) from **quality**
  flags (tilt_outlier, *_approximate, *_unreliable); (b) asked the owners for ground truth; (c) **pulled
  Ronnie's canonical branch** and re-ran via his own orchestrator; (d) ruled out the input type — the
  over-flagging persists at both 0.8 mm and 4 mm, and **our** 5.2 method reads the *same* masks correctly,
  so the input is valid (the Spine-Generic necks are genuine cervical T2, SPACE/3D-iso).
- **The real finding (the keystone):** on Ronnie's canonical code, the **6-corner landmark extraction**
  (disc-anchored body crop → PCA → edge-strip corner extrema) is **unstable on real lordotic necks**, and
  it cascades into three downstream measurements:
  - anterior > posterior heights (Ha/Hp ≈ **1.08**, backwards from the verified ~0.90), persists on his
    sub-voxel version;
  - Cobb C3–C7 = **−21° ± 27°** (healthy reads *kyphotic*; should be lordotic ~+10–35°); segmental angles
    range ±90°;
  - spondylolisthesis flags **62%** of healthy adjacent pairs.
  The vertebra *sizes* (AP width ~18 mm, heights ~11–12 mm) survive — only the corner-dependent
  (directional/angular) outputs are corrupted. So it is **one keystone**, not five separate bugs: fix the
  corner/body-isolation geometry and heights + Cobb + spondylolisthesis improve together.
- **The fix (in progress):** ground a robust cervical endplate/corner-landmark method in the literature
  (research workflow launched), then reverse-engineer it — our J2 canal-cut + J3 endplate-LINE method is the
  starting candidate (it reads the same healthy necks correctly). G3 (canal/cord) couldn't be validated
  locally — it's SCT-backed and needs a Colab run.

## J7 — The corner fix, validated by the literature: endplate-LINE fitting beats corner extrema
- **The question (from J6):** is our candidate fix (canal-cut body isolation + fit lines to the full
  endplate boundary, drop tails) actually the right method, or just our preference?
- **How we answered it:** an adversarial method-research workflow (2026-06-06; 108 agents, primary sources
  only) — **cross-validated by a second blind 238-agent run, same verdict** → high confidence.
- **The verdict — our direction is the validated state of the art:** the one head-to-head cervical study,
  Wang 2023 (cervical CT, PMC10685593), shows **line-fitting beats four-corner extrema: ICC 0.97 vs 0.75,
  MAE 3.23° vs 5.42°.** Mechanism (why extrema fail): cervical endplates are **concave + sloped** (Chen 2013,
  PMC3698350) so the most-posterior voxel in a flat band lands on the concave interior = a mislocated corner
  — the literal cause of the backwards Ha/Hp and kyphotic Cobb in J6. Corroborated by Zhong 2024 (cervical
  T2 MRI centroid-line Cobb, ICC 97.9%) and de Dios 2023 (cervical-MRI slip from a posterior-surface line,
  MDC 1.5 mm — our broken slip SD 3.7 mm was ~7× the SEM).
- **The recipe (now implementing on our TSS masks):** fit lines (robust Theil-Sen) to the full sup/inf
  endplate boundary → derive corners, heights, Cobb (C2-inf→C7-inf, lordosis-positive, supine offset), and
  slip (posterior-surface line) from the lines. Targets: corner <2.5 mm, Cobb MAE <5°/+9–11° healthy supine,
  Ha/Hp <1.0, slip SD <1.5 mm. Tooling upgrade to pilot later: SPINEPS + TPTBox (Apache-2.0).
- **Process lesson worth recording:** the workflow **survived a laptop death mid-run via resume** (108 agents
  completed after the machine came back) — multi-agent research is crash-resilient, which let a long
  verification run finish despite hardware failure. The adversarial layer also **caught fabricated author
  names** on real PMIDs (Pan→Wang, Brynolf→de Dios, Kang→Marques) — cite only the corrected identifiers.

---
*Open methodology gaps tracked elsewhere:* teammate threshold/citation fixes (disc DHI<0.30, bulge flat-wall,
Pfirrmann cut-points) — see `group5/AUDIT_groups1-4_measurements.md`; the corner-geometry fix — see the
research handoff under `../handoffs/`.
