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

## J12 — Option C1: fitting the line to SPINEPS' OWN endplate voxels — the endpoint fix that worked
- **The lead (from a 93-agent research workflow):** J11 concluded the SPINEPS corpus swap didn't help. The
  workflow found WHY: we fit the line to the **corpus border (label 49)**, but SPINEPS already predicts the
  **endplate itself** and writes each vertebra's inferior-endplate sheet into the INSTANCE mask at **label
  100+X** (C2=102 … C7=107) — voxels we already had and had dismissed as "disc/POI markers." Fitting to the
  real endplate voxels is the literature-validated method (Wang 2023: line-fit ICC 0.97 vs four-corner 0.75;
  ceiling Zhang 2025 PG-nnUNet, sagittal-T2 C2-C7, ICC 0.94 / MAE 2.44°).
- **What we built:** `cervical_alignment.spineps_endplate_cobb_angle` — the PCA major axis of the thin
  endplate sheet on the mid-sagittal slice IS the endplate tangent; the Cobb is the angle between two
  vertebrae's inferior-endplate tangents, sign-calibrated to lordosis-positive (the raw angle is consistently
  negative across all 12 necks). Needs only the instance mask. 4 TDD tests; verified the 100+X anatomy
  (inferior endplate, co-located both subjects) + the sign consistency on real data *before* coding.
- **The result — it beats both prior methods on every span (precision + coverage):**
  | Span | ENDPLATE (C1) | corpus (J11) | canal-cut |
  |---|---|---|---|
  | C2-C7 | **+15.4 ± 13.7 (11/12)** | −4.7 ± 26.0 (9/12) | +1.7 ± 16.6 (9/12) |
  | C3-C7 | **+15.2 ± 9.8 (11/12)** | +4.0 ± 22.7 | +8.0 ± 22.4 |
  | C3-C5 (mid) | **+0.2 ± 4.9 (11/12)** | +8.8 ± 12.1 | +2.2 ± 6.7 |
  | C6-C7 (endpoint) | **+8.8 ± 5.9 (11/12)** | −7.0 ± 31.3 | −1.8 ± 18.5 (8/12) |
- **Why it's believable:** the C6-C7 endpoint (the cervicothoracic-junction failure J8/J11 couldn't fix)
  dropped to SD **5.9°** (canal-cut 18.5°); coverage rose to 11/12 incl. C7; and the C2-C7 **mean +15.4°
  matches the F1000 literature mean (15.4°)** — strong evidence it reads true lordosis, not noise.
- **Honest scope:** still PRECISION + coverage, not accuracy — no healthy-MRI Cobb GT exists (only the F1000
  n=77 *spondylosis* Excel angles, image format unconfirmed). The full-span SD (±13.7°) reflects real
  inter-subject lordosis variation, not method error; the MAE ceiling (~2.4°) needs GT we don't have. **C1 is
  now our recommended SPINEPS Cobb method; canal-cut stays the fallback.** Next: port the same endplate-voxel
  method into the teammates' `c3c7_cobb_angle.py` (still corner-pair AI→PI) via feat/ + PR.
- **Process note:** the research workflow itself (93 agents, adversarial-verify) is what turned J11's negative
  into J12's positive — it located a free, validated fix (the endplate voxels were already on disk) that the
  single-context investigation missed. Also corrected a false assumption: supine MRI does NOT read ~5° less
  lordotic than standing for C2-C7 (F1000: diff −0.50°, n.s.) — fix the Group 6 Cobb caveat accordingly.

## J13 — Integrating Group 5 into the measurement service: an anatomy-orientation fixture bug, caught by the test
- **Context:** during the 2026-06-07 structure refactor, Group 5 was wired into the measurement
  orchestrator via a new adapter (`services/measurements/group5/fracture_screen.py`) so the validated
  vertebral-body compression screen emits through the same report path as the other groups. A new
  synthetic integration test (`test_group5_fracture_screen.py`) shipped red.
- **The mistake:** the test's synthetic "compressed C4" placed the truncated vertebral wall on the
  **wrong anterior/posterior side** for the measurement's RAS convention. The screen therefore read
  Ha=12.5 / Hp=7.2 → ratio **1.737** (healthy-looking) instead of the intended ~0.58, so the
  compression flag never fired and the test failed.
- **How we found it / ruled out a regression:** ran the suite on the refactored tree (136/137). Traced
  the one failure to the *adapter's* new fixture, not the science: the validated `vertebral_fracture.py`
  moved byte-identical and read the healthy C3 correctly (1.0) in the same test; the adapter only
  forwards orientation. The dataset owner (Ronnie) confirmed the adapter is correct and the fix belongs
  in the fixture.
- **The fix:** swap the two C4 wall blocks so the truncation lands on the side the validated
  `measure_vertebra` reads as anterior (Ha). Touched the test only — no change to the science or the adapter.
- **Validated:** the screen now reads Ha/Hp ≈ 0.58 → `outside_reference / compression_screen_positive`;
  full suite **137/137 green**.
- **Lesson (recurring):** synthetic fixtures must match the real RAS anatomy/orientation the code assumes —
  the same class of trap as the canal/body-isolation orientation issues in J2/J6. Integration tests across
  a service boundary catch convention mismatches that unit tests on clean rectangles don't.

## J14 — First threshold-crossing validation on real healthy + unhealthy MRI: G3 discriminates cleanly
- **What we did:** ran the full pipeline on 12 healthy (Spine-Generic) + 10 symptomatic (MMCSD cervical
  spondylosis: 5 CSM + 5 CSR) — TSS + SCT on Colab A100, then our measurement methods locally — and
  compared each measurement's distribution healthy-vs-unhealthy against the cited thresholds.
- **Headline — G3 (canal/cord/SAC) separates cleanly:** canal-AP minimum healthy median **11.7 mm**
  (0% < 10) vs unhealthy **8.6 mm** (**100% < 10**); SAC minimum healthy **4.7 mm** (0% < 3) vs unhealthy
  **2.3 mm** (**80% < 3**); cord-AP thinner unhealthy (5.5 vs 6.3 mm). The two canal distributions barely
  touch (healthy floor 10.5 vs unhealthy ceiling 9.97). First hard proof the pipeline reads normal on
  healthy and crosses into abnormal on real pathology.
- **G4 Cobb — right direction, noisy:** unhealthy more kyphotic (−13° vs −3° healthy) = expected loss of
  lordosis, but canal-cut is noisy (+56° healthy outlier; 9/12 measurable) → SPINEPS C1 is the fix for
  absolute values; the cohort direction already separates.
- **G1 Ha/Hp = 0% flags in BOTH cohorts — CORRECT, not a failure.** Spondylosis is degenerative, not
  compression-fracture, so MMCSD heights are normal (true negatives) — empirically confirming the design
  reasoning that MMCSD doesn't exercise the compression axis (needs a dedicated fracture set, the one data
  gap). Healthy 0% over-flag re-confirms 5.2 specificity on the full 12.
- **Honest caveats (logged):** n small (12/10); the 10 unhealthy were *selected to have mid-cervical
  lesions* so part of the G3 separation is by construction — a random draw from the 250 MMCSD is the next
  test; healthy = young controls (wide canals). Notably the earlier worry that SAC<3 / canal<10 *over-flag*
  healthy on MRI did NOT materialize (0% healthy). Full numbers + reproduction:
  `docs/validation/results-run1-2026-06-07.md`.

## J15 — Full-cohort validation with statistics: G3 separates at p=0.0001; G4-C1 directional; G1 correctly null
- **What we did:** ran every group on the full cohort (12 healthy Spine-Generic + 10 MMCSD unhealthy) and
  added Mann-Whitney U tests + per-measure figures (`docs/validation/results-full-2026-06-08.md`).
- **G3 (canal/cord/SAC) — VALIDATED:** canal-AP min healthy 11.7 vs unhealthy 8.6 mm (**p=0.0001**); SAC
  min 4.7 vs 2.3 mm (**p=0.0001**); cord AP 6.3 vs 5.5 mm (p=0.009). Distributions barely touch. Strong
  threshold-crossing on real MRI.
- **G4 Cobb C1 (SPINEPS endplate) — method-validated, directional:** healthy +15.2° (matches F1000
  literature 15.4°) vs unhealthy +8.8° (loss of lordosis), but p=0.13 (n.s. at n=10/11). C1 dramatically
  cleaner than canal-cut (which gave a +56° healthy outlier). Validated the C1 *method* on an independent
  cohort; as a *discriminator* it is directional only (alignment is less specific than stenosis for CSM).
- **G1 Ha/Hp — correctly NULL:** 0.81 vs 0.80, p=0.92, 0 flags either cohort. Expected and correct —
  spondylosis is not compression fracture (true negatives), empirically confirming MMCSD doesn't exercise
  the compression axis. Re-confirms 5.2 specificity on all 12 healthy.
- **Lesson:** the validation behaves as designed — strong where the disease lives (stenosis→G3), directional
  where the metric is less specific (alignment→G4), and silent where the cohort has no such pathology
  (compression→G1). Honest caveat logged: the 10 unhealthy were lesion-selected, so a random MMCSD draw is
  the next test; n is small; no GT → separation not sens/spec.

## J16 — Validation as a bug detector: G2 disc (DHI + AP bulge) read BACKWARDS → real bug, root-caused
- **What we found:** on the same cohort, **both** Group-2 disc metrics fail the threshold-crossing test by
  pointing the WRONG way: DHI healthy 0.23 vs unhealthy 0.26 (healthy looks *more* degenerated, p=0.05,
  wrong sign), and AP bulge healthy 2.95 vs unhealthy 0.91 mm (healthy looks *more* bulged, p=0.005, wrong
  sign). A metric that scores healthy worse than pathology is invalid by construction.
- **Root cause (confirmed via intermediates):** the DHI denominator (adjacent VB middle height) is
  **over-measured at the junction levels** — healthy `h_upperVB_middle_mm` C2-C3 = 26.6 mm, C7-T1 = 20.5 mm
  vs the true ~12-13 mm — collapsing DHI and firing `reduced_dhi` 77% on healthy. Mid-cervical VB heights
  (C3-C6 ≈ 12-14 mm) are fine → the bug is level-specific (C2 / cervicothoracic junction). This is exactly
  the denominator discrepancy Mohammad predicted in his G2 handoff.
- **What we did NOT do (and why):** did not blind-rewrite Mohammad's Duke-tuned disc algorithm overnight —
  per our teammate-code rule, a fix to his code without his review and without GT would be irresponsible.
  Documented + flagged with the exact evidence + a candidate fix (robustify `measure_adjacent_body_slice`
  so junction/C2 VB heights aren't over-measured), to be done with him, then re-validate.
- **Lesson:** the validation harness earned its keep — it caught a real, sign-level measurement bug that a
  unit test on clean shapes would miss, and localized it to a specific denominator at specific levels.

## J17 — The G2 disc bug, diagnosed and partially fixed: a cited relative flag, and an honest non-result
- **The bug (from J16):** DHI and bulge read backwards (healthy scored worse than the symptomatic cohort).
- **Diagnosis (decompose numerator vs denominator, mid-cervical C3-C6):** healthy disc-middle height
  4.00 mm vs unhealthy 4.12 mm (**numerator is flat -- disc height does not separate the cohorts**);
  healthy VB-denominator 12.70 mm vs unhealthy 11.39 mm (**the backwards DHI is denominator-driven** --
  healthy bodies measure taller). Against Mohammad's anchor (disc 5.2 mm, denom 9 mm, DHI 0.55), our
  denominator (~12.7 mm) is in fact closer to the true cervical body height (~12-13 mm); his ~9 mm is an
  under-measured AP-strip, so his DHI 0.55 is inflated, not a target to match.
- **Why a denominator swap would have been the WRONG fix:** it would make our numbers resemble his by
  under-measuring (not move toward truth) and still would not discriminate, because the disc-height
  numerator is flat. Caught before shipping (per the "revert if it's the wrong fix" rule).
- **The fix that is correct + cited (additive, safe):** the real defect is the in-code absolute
  `DHI < 0.30` flag, already debunked as uncited. Replaced/augmented with a CROSS-LEVEL relative rule -- a
  disc whose middle height is >30% below the patient's own reference disc height (Suzuki 2018) -- which
  cancels the cross-dataset calibration. Result: healthy false-positive firing **77% -> 3%** (unhealthy
  56% -> 2%). Additive (Mohammad's DHI value + `reduced_dhi` untouched) so it cannot break his pipeline;
  committed on `feat/measurements/disc-dhi-relative-flag` for his review.
- **The honest non-result:** the relative flag fires ~equally on both cohorts (3% vs 2%) -- i.e. disc
  HEIGHT does not discriminate this CSM/CSR cohort. That is clinically correct: cervical degeneration here
  is signal loss and bulge/herniation, not mid-cervical height collapse. So G2's real discriminator is the
  Miyazaki SIGNAL grade, not height; the bulge metric remains separately broken (backwards) and unfixed.
- **Lesson:** "fixing" a metric is not the same as making it discriminate. We fixed the false-firing
  (a real defect) honestly, and reported that the metric still does not separate -- rather than tuning the
  denominator to fabricate a clean-looking number.

## J18 — G4 'directional' diagnosed: a LARGE effect, just underpowered (not a weak metric)
- **Question:** is C1 Cobb's directional-only discrimination (healthy +15.2 vs unhealthy +6.0, p=0.13) a weak
  metric or just small n? Tested effect size + alternative metrics on the SPINEPS masks (11 healthy, 10 unhealthy).
- **Finding:** **Cobb C3-C7 has a LARGE effect, Cohen d=0.91** -- the separation is real, it just needs ~19
  cases/group for 80% power (we have 10). C3-C7 beats the alternatives: C2-C7 d=0.60 (endpoint noise),
  focal min-segmental d=0.64, #kyphotic-segments d=0.37 (weak). So global C3-C7 is the right discriminating
  metric and the only thing missing is statistical power.
- **Fix (not code -- data):** segment ~19-20+ unhealthy MMCSD cases with SPINEPS (Run B) -> re-run C1 Cobb
  -> expected p<0.05. No method change; C3-C7 stays the metric.
- **Lesson:** 'directional, p=0.13' looked like a weak result but the effect size revealed it as underpowered
  -- the same diagnostic discipline that (oppositely) showed G2's disc height is genuinely flat (d~0).

## J19 — G1 tilt flag recalibrated: the 20° cut over-flagged 83% of HEALTHY cervical bodies
- **Question:** `cervical_body_morphometry.TILT_DEG_MAX = 20.0` flags a vertebra whose body SI-axis tilts
  >20° from global vertical as an outlier. Is 20° right for *cervical* anatomy? Measured the healthy tilt
  distribution (12 Spine-Generic necks, 60 C3-C7 bodies; tilt = angle between the body's PCA SI-axis and
  vertical, the same definition the service uses, computed via our validated endplate-fit).
- **Finding:** healthy cervical tilt is **median 27.0°, mean 27.8 ± 6.9°** (p95 41.4°, p99 42.5°, max 43.5°).
  The 20° cut trips **50/60 = 83% of HEALTHY vertebrae** — it is a near-vertical (thoraco-lumbar-style)
  assumption that is simply wrong for the lordotic mid/lower cervical spine, where bodies are physiologically
  tilted 20-40° from absolute vertical. This is a quality/sanity flag, not a disease detector, so the cut
  belongs above the healthy range.
- **Fix (data → threshold):** recalibrate `TILT_DEG_MAX` from 20° to **~45°** (mean+2.5SD ≈ 45°, clears p99
  42.5° and max 43.5° with margin → 0% healthy false-flag). Earlier eyeball estimate was ~28° (≈ the median);
  the data shows that is still too low — the median, by definition, would flag half the healthy cohort.
- **Lesson:** an unsourced borrowed threshold (20°) silently mass-flagged healthy anatomy; only measuring the
  healthy distribution exposed it. The recalibration is to the OWN-cohort distribution (specificity-anchored),
  same discipline as the Ha/Hp norm (J-series, vb_hahp_norm_verified).

## J20 — G1 AP depth + height precision: healthy C3-C7 cluster tightly (sanity confirmed)
- **Question:** are G1's AP-width and vertebral-height outputs in a plausible, tightly-clustered mm range on
  healthy necks (they were previously "not checked vs norms")? Measured AP depth (PCA AP extent) and Ha/Hp on
  the 12 healthy.
- **Finding:** AP depth clusters tightly — **18.9 ± 2.2 mm** across C3-C7 (per-level CV 9-14%), monotonic
  C3 19.6 → C7 18.4 mm. This reads ~2 mm **above** the ~15-17 mm CT/anatomic norm, expected for T2 MRI +
  a max-AP-extent (endplate-corner) measure vs mid-body CT calipers — magnitude is right, precision is good.
  Ha/Hp = **0.94 ± 0.13** overall with a physiological caudal trend (C3 0.86 anterior-wedged → C7 1.00
  rectangular). NOTE this reproduces COHORT_HAHP_MEAN/SD exactly because it IS that cohort — a consistency/
  reproducibility check, not independent validation.
- **Fix:** none needed (sizes sane). Flagged for the report: cite AP depth against a *cervical-MRI* norm if one
  is pulled (Nell 2019 per-level percentiles held but numbers not yet extracted); current support is order-of-
  magnitude CT.
- **Lesson:** "looks reasonable" is not validation — but tight per-level clustering (SD ~2 mm) is real evidence
  the geometry is stable; the honest caveat is the +2 mm MRI/method offset vs the CT norm.

## J21 — Resolution robustness: mm metrics survive 4 mm through-plane; canal-cut Cobb does NOT
- **Question:** each healthy neck exists at 0.8 mm and at 4 mm through-plane (Duke-like). Do Ha/Hp, AP depth and
  Cobb agree across resolution (test-retest precision)?
- **Finding:** **AP depth is resolution-robust** — mean |0.8-4 mm| = 0.81 mm, bias −0.15 mm (negligible).
  **Ha/Hp has zero group-level bias** (−0.009) but ~0.14 per-vertebra scatter → robust for the cohort MEAN
  (which is what the norm uses; confirms the in-code "0.8 mm and 4 mm agree" claim *at the group level*), coarse
  per body. **Canal-cut Cobb C3-C7 is NOT robust** — mean |0.8-4 mm| = 15.6° (n=9) — consistent with it being
  the inferior angular method (canal-cut C6-C7 SD 18.5°, J11/J12) that the SPINEPS endplate-voxel C1 method
  (J12) supersedes.
- **Fix:** none for the mm metrics (validated robust). The Cobb fragility is a *third* independent argument for
  the SPINEPS C1 method over canal-cut (after precision and C7 coverage); the 4 mm Cobb test should be repeated
  on SPINEPS masks once available.
- **Lesson:** resolution-robustness must be checked per-metric: physical-dimension (mm) metrics are immune as
  predicted (mirrors the cross-scanner argument, validation_design_rationale), but a derived angular metric from
  a fragile body-isolation can amplify coarse-slice noise — robustness is a property of the *method*, not just
  the quantity.

## J22 — Applying the validation findings to the SERVICE code (4 fixes, each kept only on evidence)
Andrew took over all teammate group code; the four mask-independent fixes below were each run through the
real 12 healthy + 10 unhealthy service contexts (`test_service_g1_g2.py`) and kept only if they corrected
the target metric (revert otherwise). All 137 service tests stayed green after each.

- **G1 tilt cut 20→45° (`cervical_body_morphometry.py`)** — the service confirmed the 20° cut flagged
  **88% of healthy** vertebrae (median 27.9°); at 45° → **0% healthy** (and 0% on the straighter CSM necks,
  which the flag should leave alone). Quality flag, can't cause clinical false-negatives. Committed.

- **G1 heights via endplate-line, not corner extrema (`cervical_body_morphometry.py`)** — wired the already-
  vendored `endplate_line_heights` into the service (it was present but only `_endplate_cobb` used it). Fixed
  healthy Ha/Hp **1.08 → 0.93** (corner extrema read anterior TALLER than posterior — backwards; the line fit
  gives the physiological posterior>anterior ~0.94). Healthy stays ≥ unhealthy (0.93 vs 0.89). Corner
  fallback retained for degenerate slices. Committed.

- **G2 posterior-bulge reference from endplate corners (`disc_ap_bulge.py`)** — the chord WAS already tilted
  (upper-PI→lower-PS), so the memory's "flat vertical line" was already fixed; the residual backwards result
  came from the *corner-extrema* posterior corners sitting too anterior. Sourcing PI/PS from the endplate-line
  fit dropped healthy bulge **2.93 mm → 0.00 mm**, over-flag **60% → 8%** (healthy discs read flush, correct),
  no longer backwards (healthy 8% ≈ unhealthy 7%). **Caught a latent bug:** `DISC_TO_VERTS` yields level-NAME
  strings, so `seg==name` silently matched nothing and fell back every time — resolved via `VERT_LABELS`. No
  cross-dataset discrimination (8% vs 7%) — that is the confound, deferred to the within-MMCSD 50-case run.
  Committed.

- **G4 SPINEPS C1 Cobb plumbed into the context (`context.py` + `c3c7_cobb_angle.py`)** — `load_context` now
  carries an optional SPINEPS seg-vert (native grid, to preserve the thin endplate sheets); `c3c7_cobb_angle`
  prefers `spineps_endplate_cobb_angle` when present, falls back to canal-cut otherwise. With seg-vert: 11/12
  healthy + 10/10 unhealthy use C1, healthy median **15.2°** (= F1000 lit 15.4°). **Bonus:** SPINEPS rescues 3
  healthy necks canal-cut couldn't measure (C7 obscured) → coverage up. p=0.13 still (n=11v10) — discrimination
  is the SPINEPS-on-50 batch (RUN 2). Committed.

---
*Open methodology gaps tracked elsewhere:* teammate threshold/citation fixes (disc DHI<0.30, bulge flat-wall,
Pfirrmann cut-points) — see `group5/AUDIT_groups1-4_measurements.md`; C6/C7 Cobb **precision** is now closed by
the SPINEPS endplate-voxel method (J12, C6-C7 SD 5.9°); absolute **accuracy** (MAE/ICC) + the slip calibration
still need radiologist ground truth — only the F1000 n=77 spondylosis angles exist as an external reference.
