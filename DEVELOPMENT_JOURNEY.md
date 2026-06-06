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

## J8 — Implementing the fix: endplate-line Cobb fixes the sign; endpoints still need SPINEPS
- **What we built:** `vertebral_fracture.endplate_lines` (expose the fitted sup/inf endplate lines + corners
  via robust **Theil-Sen**) and `cervical_alignment.cobb_angle` (Cobb from the inferior-endplate lines,
  lordosis-positive, with a C7-obscured reliability guard). TDD, 62 tests green.
- **Validated on the 12 healthy necks — the headline bug is fixed:** Cobb now reads **lordotic** (positive)
  vs Ronnie's corner method which read **−21° ± 27° (kyphotic garbage)**. Mid-cervical is stable and sensible
  (**C3–C5 +2.2 ± 6.7°**, C3–C6 +1.0 ± 8.9°). So the line-fit direction works.
- **Honest residual (don't overclaim):** the **C6/C7 endpoints** are still noisy (C2–C7 SD ~16°, 9/12
  measurable after the guard). Root cause is **not** the line fit — it's the **canal-cut body isolation
  mis-shaping the C6/C7 body at the cervicothoracic junction**, so PCA orients it wrongly. The reliability
  guard (reject near-vertical endplate tangents) correctly turns those into "C7 not measurable" rather than a
  garbage value (the literature-honest C7-obscured outcome), but it caps coverage.
- **The prescribed upgrade (research-backed):** replace canal-cut body isolation with the **SPINEPS corpus
  label** (learned body/arch split, corpus DSC 0.948) — a Colab/install pilot. That, plus 1–2 radiologist Cobb
  cases for magnitude, is what takes the endpoints from "sign-correct" to "MAE <5°." Same upstream fix also
  benefits spondylolisthesis (shares the endpoint body-isolation).
- **Lesson:** fixing the *measurement method* (corner→line) corrected the **direction** project-wide, but
  *segmentation/body-isolation quality* is the remaining lever for endpoint *precision* — two separable layers.

## J9 — Line-fit pipeline validated on 12 healthy necks vs the research targets (honest scorecard)
| Output | Target | Result on 12 healthy | Verdict |
|---|---|---|---|
| Ha/Hp (heights) | <1.0, ~0.90–0.94 | 0.94, posterior>anterior | ✅ meets target (J1) |
| Cobb sign | lordosis-positive | positive (was −21° kyphotic) | ✅ **sign bug fixed** |
| Cobb precision (mid-cervical) | — | C3–C5 +2.2 ± 6.7° | ✅ stable |
| Cobb precision (C2–C7 incl. endpoints) | MAE <5°, +9–11° | SD ~16°, 9/12 measurable | ⚠️ endpoints need SPINEPS + radiologist GT |
| Spondylolisthesis slip | SD <1.5 mm | SD ~2.9 mm, ~3 mm bias | ⚠️ improved vs 3.7 mm but NOT at target |
- **Net:** corner→line fixed the **gross/directional** failures (Cobb sign, heights) — the headline bugs from
  J6 are gone. The remaining gap is **precision at the C6/C7 endpoints + slip calibration**, and both trace to
  the *same two levers* the research named: (1) better body isolation (SPINEPS corpus, a Colab pilot) and
  (2) 1–2 radiologist-labelled cases to calibrate magnitude/sign. Honestly logged: slip is committed as
  EXPERIMENTAL (not screening-ready) rather than shipped biased.

## J10 — 5.1 myelomalacia closed: SCIseg specificity measured + integrated end-to-end
- **What we did:** ran SCIseg (`sct_deepseg lesion_sci_t2`, Colab GPU) on the healthy Spine-Generic cords
  (11/12 completed before the Colab limit), then scored lesion burden locally.
- **Specificity result (Andrew's "on healthy, flags nothing" criterion):** **10/11 cords completely clean
  (0 lesion voxels); 1 false positive** (sub-amu02, a 77 mm³ component mapped to C7 — a single SCIseg FP /
  possible edge artifact at the cervicothoracic junction). So healthy specificity ≈ **91% (10/11)** in our
  hands — SCIseg is a good-but-imperfect engine, now MEASURED rather than assumed.
- **Integration verified end-to-end:** `run_group5_pipeline.py --lesion` auto-pairs the SCIseg masks to the
  TSS cases by subject and maps each cord lesion to the cervical level it overlaps (sub-amu02 → myelomalacia
  present at C7 only; clean cases all-negative). The 5→6 flags contract now carries real myelomalacia.
- **5.1 is done:** adopt SCIseg (sensitivity from its publication) + our healthy-specificity check (10/11) +
  wired into the contract. **This closes Group 5's last open sub-part** (5.2 validated, 5.3 scoped out,
  5.4 deferred, 5→6 contract + runner done).

## J11 — The SPINEPS-corpus endpoint-precision pilot: hypothesis tested, NOT supported (Group 4 / teammates' G4)
- **The hypothesis (from J8):** swap canal-cut body isolation for the SPINEPS **corpus** label (learned
  body/arch split, corpus DSC ~0.95) to take the C6/C7 Cobb endpoints from "sign-correct" to "MAE <5°."
- **How we tested it:** ran SPINEPS (Colab T4, model `T2w_semantic_v1.0.9`) on the 12 healthy Spine-Generic
  necks → semantic `seg-spine` + instance `seg-vert`. **Verified the real label IDs before trusting them**
  (corpus = 49; instances follow VerSe numbering C2=2..C7=7 — IDs vary by model version, so this gate
  mattered). Built a TDD'd consumer (`cervical_alignment.spineps_body` / `spineps_cobb_angle`: body =
  corpus ∩ instance, fed through the SAME endplate-line Cobb as the canal-cut path) + a side-by-side runner
  (`run_spineps_alignment.py`). 9 alignment tests; the shared endplate tail was refactored out (`_endplate_from_body`).
- **The result — it did NOT improve precision; it was worse:**
  | Span | SPINEPS SD | canal-cut SD |
  |---|---|---|
  | C2–C7 (endpoints) | ±26.0° | ±16.6° |
  | C3–C5 (mid, the *stable* region) | ±12.1° | ±6.7° |
  | C6–C7 | ±31.3° | ±18.5° |
- **Diagnostic (why):** the corpus bodies are NOT fragmented (healthy 5k–35k voxels); per-vertebra
  inferior-endplate angles mostly AGREE with canal-cut (within a few °), but several individual vertebrae
  diverge 7–13° (e.g. amu03 C5 −4.4° vs −17.7°). Because Cobb **differences** two vertebrae, one bad
  per-vertebra fit blows up the angle → the wider spread + the wild values (amu02 −47°, beijingGE03 +65°).
- **The honest conclusion:** the J8 corpus-swap is **not** the endpoint-precision fix. And — crucially — with
  **no radiologist ground truth** we can only measure PRECISION (spread on healthy), not ACCURACY: canal-cut
  is more *precise*, but "tighter on healthy" ≠ "more correct." So the real unblock stays **radiologist GT**
  (as J7–J9 said), which would adjudicate canal-cut vs SPINEPS per vertebra. We deliberately resisted tuning
  the method to make SPINEPS *look* tighter — without GT that is chasing precision, not truth.
- **Why it's not wasted:** the consumer is built + TDD'd and ready to re-run this comparison the moment 1–2
  labelled cases exist. It doesn't block the product either — Group 6 reports Cobb as a review-only descriptive
  class (lordotic/straightened/kyphotic) with the supine + endpoint caveats, not a hard-flagged magnitude.

---
*Open methodology gaps tracked elsewhere:* teammate threshold/citation fixes (disc DHI<0.30, bulge flat-wall,
Pfirrmann cut-points) — see `group5/AUDIT_groups1-4_measurements.md`; C6/C7 Cobb precision + slip → **radiologist
ground truth** (the SPINEPS-corpus pilot was run and did NOT close the gap — see J11; canal-cut remains our
most-precise method pending GT).
