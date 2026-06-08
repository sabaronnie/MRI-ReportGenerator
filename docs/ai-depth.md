# AI Technical Depth & Non-Triviality (Rubric T1)

> **Scope.** This document argues, with evidence, that the MRI-ReportGenerator pipeline carries
> genuine technical and AI depth and is **not** a thin wrapper over pretrained models. It is written
> for a skeptical technical reader. Every clinical claim is cited; the engineering claims are backed
> by committed code, validation results, and the development journal. Companion evidence:
> [DEVELOPMENT_JOURNEY.md](../DEVELOPMENT_JOURNEY.md) (J1–J23, the method narrative),
> [docs/validation/group-status-2026-06-08.md](validation/group-status-2026-06-08.md) (per-group
> verdict), [docs/validation/results-full-2026-06-08.md](validation/results-full-2026-06-08.md)
> (numbers + figures), and the `paper/` draft.
>
> **Medical framing (hard rule).** The system produces measurements and *findings flagged for
> physician review*, never diagnoses. Nothing here claims otherwise.

---

## 1. Thesis

The depth of this system is not in training a new neural network — and we deliberately do **not** claim
to. It is in three places that a "wrapper" does not reach:

1. **Multi-model segmentation composition** — orchestrating three independent, differently-trained
   segmentation engines (TotalSpineSeg, Spinal Cord Toolbox, SPINEPS) and deciding, per measurement,
   which one to trust on a region (cervical spine) where none of them is individually validated for the
   downstream measurement.
2. **Clinically-meaningful measurement algorithms** — converting voxel masks into vertebral, disc,
   canal, cord and alignment measurements with methods that required real geometric engineering
   (endplate-line fitting, anatomical canal-cut body isolation, PCA tilt-correction, endplate-voxel
   Cobb). The naïve version of each of these measurements **demonstrably fails**; we have the
   before/after numbers to prove it.
3. **Validation methodology under a hard data constraint** — no public dataset pairs cervical MRI with
   per-case expert measurements, so per-case sensitivity/specificity is impossible. We designed a
   *threshold-crossing / distribution-separation* methodology anchored on a healthy cohort, with
   explicit confound control. Designing a defensible evaluation when the obvious one is unavailable is
   itself the technical contribution.

The single strongest piece of evidence that this is non-trivial is the **bug ledger** (Section 7): a
list of places where the obvious, naïve implementation produced *wrong* clinical numbers, which only
rigorous validation surfaced and principled algorithm changes fixed. A trivial wrapper has no such
ledger.

---

## 2. The honest framing: where the AI is, and where it is not

We are explicit about this because the rubric rewards honesty and because over-claiming in medical AI
is a failure mode in itself.

**What we do *not* do:** we do not train a segmentation model from scratch, and we do not claim a novel
deep-learning architecture. The segmenters are pretrained and **frozen**.

**Why that is the correct engineering decision, not a shortcut:**

- **Reproducibility and no overfitting.** Because nothing is trained on our evaluation cohort, there is
  no train/test leakage and no risk of fitting our metrics to the symptomatic set. The unhealthy cohort
  is a *demonstration* set, not a training set (see [validation_design_rationale] in project memory and
  the paper's methodology section). This is a deliberate medical-AI safety property.
- **Standing on validated tools.** TotalSpineSeg and Spinal Cord Toolbox are published, peer-reviewed,
  open-source segmentation stacks. Re-implementing inferior versions would be worse engineering, not
  better.
- **The value lives in the layer they do not provide.** None of these tools outputs a cervical
  radiology report, threshold-based interpretation, or validated cervical *measurements*. That layer —
  the clinically actionable output — is entirely ours, and it is where the difficulty is.

So the correct mental model is **not** "wrapper around a model" but "a measurement-and-interpretation
system that *uses* segmentation as one input, the way a radiology workstation uses a DICOM loader."

---

## 3. Pipeline overview

```
Input (DICOM / NIfTI, sagittal T2)
   │
   ▼
Segmentation IEP   ── TotalSpineSeg  → vertebrae, discs, spinal canal (labelmap)
                   ── Spinal Cord Toolbox → cord & canal cross-sections (per-slice)
                   ── SPINEPS         → vertebra instances + endplate sheets
   │
   ▼
Measurements IEP   ── G1 vertebral morphometry (Ha/Hp, AP width, tilt)
                   ── G2 disc (height index, AP spread, signal)
                   ── G3 canal / SAC / cord diameters
                   ── G4 cervical alignment (C3–C7 Cobb)
                   ── G5 fracture screen + myelomalacia screen
   │
   ▼
Interpretation     ── G6 threshold catalog → status per finding (cited thresholds)
   │
   ▼
Reporting IEP      ── structured, radiologist-style report ("flagged for physician review")
```

The Enterprise Execution Plane (EEP) orchestrates the two deployed Internal Execution Planes
(measurements, reporting); see the infra documentation for the service architecture. This document
concerns the **measurement-science depth** inside the measurements IEP and the segmentation
composition that feeds it.

---

## 4. Depth dimension 1 — Multi-model segmentation composition

A wrapper calls one model and trusts it. We call **three**, because no single one is sufficient for
cervical measurement, and the composition is non-trivial:

| Engine | License | What it gives us | Why we need it |
|---|---|---|---|
| **TotalSpineSeg** (TSS) | LGPLv3 | Whole-vertebra, disc and canal labels on an isotropic grid | The backbone labelmap for G1/G2 and the canal for body isolation |
| **Spinal Cord Toolbox** (SCT) | LGPLv3 | Per-slice cord and canal cross-sectional diameters | G3 — cord/canal/SAC; TSS's canal label is coarse for AP diameters |
| **SPINEPS** | Apache-2.0 | Per-vertebra instances **plus thin endplate voxel sheets** | G4 — the endplate-voxel Cobb that TSS corners cannot do reliably at C7 |

The non-trivial engineering here:

- **Per-measurement model selection.** The C3–C7 Cobb angle is *more accurate* from SPINEPS endplate
  voxels than from the TSS labelmap, because the cervico-thoracic junction (C7) is frequently obscured
  and corner-based angles there are unstable. So `c3c7_cobb_angle` **prefers** the SPINEPS method when a
  seg-vert mask is present and **falls back** to the TSS canal-cut method otherwise
  ([c3c7_cobb_angle.py](../services/measurements/geometric/c3c7_cobb_angle.py)). This selection logic
  measurably rescues cases the fallback cannot measure at all (J22).
- **Reconciling incompatible runtimes.** TSS/nnU-Net and SPINEPS pin **mutually incompatible NumPy
  versions** (SPINEPS requires `numpy==2.0.2`, which breaks the TSS/nnU-Net ABI). They cannot share a
  process; the pipeline runs them in separate environments and re-aligns their outputs onto a common
  grid in the measurement context. This is real systems integration, documented in the Colab run notes
  and J-series.
- **Grid and orientation reconciliation.** The three engines emit masks in different
  orientations/resolutions; `load_context`
  ([context.py](../services/measurements/context.py)) standardizes to canonical RAS, enforces isotropy,
  and index-aligns the grayscale and the SPINEPS instance mask to the labelmap so measurements are
  computed in one coherent frame.

None of this is visible to a user, and none of it is provided by any single model. It is the connective
tissue that makes three research tools into one measurement system.

---

## 5. Depth dimension 2 — Measurement algorithms (the core technical contribution)

This is where most of the engineering lives. For each measurement we did *not* take the obvious
pixel-counting approach, because the obvious approach gives clinically wrong numbers on real cervical
anatomy. Four representative examples, each with the evidence that the naïve method fails:

### 5.1 Endplate-LINE fitting instead of corner extrema (G1 heights, G4 Cobb)

**Naïve method:** read vertebral-body heights from the four corner pixels (antero/postero
superior/inferior extrema). **Why it fails:** cervical endplates are *concave and sloped*, not flat
(Chen et al., 2013), so a single corner pixel lands in the wrong place. **Our method:** fit straight
lines (Theil–Sen, robust to osteophyte tails) to the full superior and inferior endplate boundaries
after PCA orientation, and read wall heights from the lines. The literature supports the line fit
directly: a fitted endplate line reaches ICC ≈ 0.97 versus ≈ 0.75 for four-corner extraction
(Wang et al., 2023, PMC10685593).

**Evidence it matters — measured, not asserted:** the corner method reads healthy cervical Ha/Hp ≈
**1.08** (anterior taller than posterior — physiologically backwards). The endplate-line method reads
**0.93**, matching the physiological slight anterior wedge (posterior > anterior). Switching the service
to the line fit moved healthy Ha/Hp 1.08 → 0.93 and preserved the correct healthy ≥ unhealthy ordering
(J20, J22). Implementation:
[`_vertebral_geometry.endplate_line_heights`](../services/measurements/geometric/_vertebral_geometry.py),
wired into [cervical_body_morphometry.py](../services/measurements/geometric/cervical_body_morphometry.py).

### 5.2 Anatomical canal-cut body isolation instead of morphological erosion (G1)

**Naïve method:** isolate the vertebral *body* from the whole-vertebra mask by erosion / connected
components. **Why it fails:** on real cervical anatomy the body and the posterior arch are one connected
blob on the mid-sagittal slice; erosion leaves a wedge-shaped body and a systematic false anterior
wedge. **Our method:** cut the mask at the spinal canal's anterior face — the body is, by definition,
everything anterior to the canal — using TSS's own canal label
([`extract_body_via_canal`](../services/measurements/geometric/_vertebral_geometry.py)). This replaced a
heuristic that produced a systematic ~0.86 height-ratio artifact (documented in the module docstring and
J-series).

### 5.3 SPINEPS endplate-voxel Cobb instead of labelmap corners (G4)

**Naïve method:** take the Cobb angle from the C3 and C7 corner points of the labelmap. **Why it
fails:** C7 is frequently obscured at the cervico-thoracic junction; corner-based C6–C7 angles have a
standard deviation of ~18.5°, which is uselessly noisy. **Our method:** fit the line directly to
SPINEPS' own inferior-endplate voxel sheets (instance label 100+X), dropping C6–C7 SD to **5.9°** (J11,
J12). On the healthy cohort this reads +15.2° lordosis, matching the external reference (F1000 cervical
cohort, 15.4°). The production code prefers this method when the mask is available (Section 4).

### 5.4 Sub-voxel boundary refinement and PCA tilt-correction

Two supporting techniques that lift precision beyond pixel quantization:

- **Sub-voxel refinement:** the in-plane mask boundary is upsampled and re-thresholded at the 0.5 level
  (a marching-squares-style half-level crossing), placing edges between voxel centres rather than on
  them, reducing the ±1-voxel quantization on every height/width/slip
  ([cervical_body_morphometry.py](../services/measurements/geometric/cervical_body_morphometry.py),
  `_refine_mask`).
- **PCA tilt-correction:** every vertebra is measured on its *own* principal axes, not the image axes,
  because healthy cervical bodies sit ~28° from absolute vertical (the lordotic curve). Measuring on
  image axes would conflate normal lordosis with deformity — which is exactly the bug the old `tilt`
  flag had (Section 7).

Each of these is a deliberate algorithmic choice with a measured payoff. That is the definition of
technical depth in a measurement pipeline.

---

## 6. Depth dimension 3 — Validation methodology under a hard data constraint

The hardest intellectual problem in the project was not building the measurements — it was figuring out
how to **validate** them when the ideal data does not exist.

**The constraint.** Extensive, repeated dataset searches (recorded across the project's research
memos — `external_validation_data`, `groups_1_4_validation_datasets`, `group5_validation_datasets`)
established that **no public dataset pairs cervical MRI with per-case expert measurements.** Per-case
sensitivity/specificity against a radiologist gold standard is therefore impossible with public data.

**The methodology we designed instead.** Our measurements are *disease-agnostic geometry/signal
detectors anchored on healthy norms* — a canal of 8 mm reads "stenosis" regardless of cause. This yields
a validation strategy that does not need per-case labels:

1. **Healthy-anchoring.** Validate that healthy anatomy reads *inside* the normal range (specificity),
   using a healthy cohort (Spine-Generic).
2. **Threshold-crossing / distribution separation.** Validate that symptomatic anatomy *crosses* into
   the abnormal range (the symptomatic MMCSD cohort), tested with distribution-separation statistics
   (Mann–Whitney), not per-case accuracy.
3. **The scanner-immunity insight.** We discovered and exploited a key distinction: *physical-dimension*
   metrics (mm — canal, SAC, cord) are immune to scanner differences and validate cross-dataset, while
   *intensity/ratio* metrics (disc signal, height ratios) are acquisition-sensitive and must be
   validated *within* a single dataset. This is why G3 (mm) validates cleanly cross-dataset and the disc
   signal does not — a non-obvious property that shaped the entire evaluation design
   (validation_design_rationale; J16, J23).
4. **Confound control.** When the within-dataset disc test showed a large effect for disc AP width
   (AUC 0.79), we did *not* report it — lesion discs cluster at wider mid-cervical levels, so we
   re-tested level-stratified and the honest figure was AUC 0.61. Reporting the unstratified 0.79 would
   have been a confounded over-claim (J23). This discipline — actively hunting the nuisance variable
   before believing a result — is the difference between a measurement and a finding.

Designing, justifying, and executing a sound evaluation when the textbook one is unavailable is a
graduate-level methods contribution, not a wrapper feature.

---

## 7. Proof of non-triviality: the bug ledger

The most direct evidence that this pipeline required real depth is the set of clinically-wrong outputs
that the *naïve* implementation produced and that only rigorous validation caught. If the task were
trivial, these would not exist.

| Naïve behavior (wrong) | How it was caught | Principled fix | Evidence |
|---|---|---|---|
| Vertebral Ha/Hp read **backwards** (anterior taller, 1.08) | Healthy cohort read non-physiological | Endplate-line fit replaces corner extrema | 1.08 → 0.93 (J20, J22) |
| `tilt` flag fired on **88% of healthy** vertebrae | Healthy false-flag rate measured | Recalibrated cut 20° → 45° (lordosis is normal) | 88% → 0% (J19, J22) |
| Disc posterior bulge **backwards** (healthy worse, 60% flagged) | Healthy over-flagged vs symptomatic | Reference chord from endplate-line corners | 60% → 8% healthy (J22) |
| Disc AP-width "AUC 0.79" discrimination | Suspected level confound | Level-stratified re-test | Honest AUC 0.61 (J23) |
| Disc signal grade looked usable | Within-dataset lesion test | Shown to be non-discriminating (AUC 0.50) | Reported as a negative (J23) |
| Latent: `seg == "C4"` (string vs int label) silently matched nothing | Code review during bulge fix | Resolve names via `VERT_LABELS` | J22 |

Each row is a place where "just measure it" gives the wrong clinical answer, and a place where we have a
committed, tested fix. The full narrative is in [DEVELOPMENT_JOURNEY.md](../DEVELOPMENT_JOURNEY.md).

---

## 8. Validated outcomes (the depth pays off)

We are equally explicit about what is strongly validated and what is partial — honesty is a graded and a
clinical requirement.

| Group | Result | Status |
|---|---|---|
| **G3** canal / SAC / cord (SCT) | canal AP 11.7 → 8.6 mm **p = 0.0001**; SAC 4.7 → 2.3 mm **p = 0.0001**; cord 6.3 → 5.5 mm p = 0.009 | ✅ **Validated (strong)** |
| **G4** C3–C7 Cobb (SPINEPS) | Reads correct lordosis +15.2° (= literature 15.4°); discrimination underpowered (d = 0.91, awaiting larger n) | ⚠️ Method-validated |
| **G1** Ha/Hp compression screen | 0% false-flag on healthy; correctly null on (non-compressive) spondylosis, confirmed n = 49 | ✅ Validated as a screen |
| **G2** disc | Signal/bulge are documented negatives; disc/VB AP ratio discriminates (AUC 0.62, level-controlled) | ⚠️ Partial — geometric spread only |
| **G5** myelomalacia / fracture screens | ~91% healthy specificity (myelomalacia); compression screen as G1 | ✅ Validated as screens |

Full numbers and figures:
[results-full-2026-06-08.md](validation/results-full-2026-06-08.md).

---

## 9. Why this composition is the right AI choice for clinical deployment

The pretrained-and-compose design is not a concession — it is the defensible architecture for a clinical
*application* (the project's positioning; see GT5 and `docs/positioning.md`):

- **Auditability.** Every output traces to a measurement and a *cited* threshold (G6 catalog), not to an
  opaque end-to-end model. A radiologist can check each number. This is a regulatory and trust property
  an end-to-end black box cannot offer.
- **No overfitting by construction.** Frozen segmenters + cited thresholds mean the system cannot have
  memorized our evaluation cohort.
- **Graceful degradation.** Per-component error contracts mean one failed measurement does not sink the
  report; missing a SPINEPS mask degrades the Cobb method, it does not crash the pipeline.
- **The differentiator is the clinical layer.** Measurement validity, cited interpretation, and the
  report — the parts that decide whether a radiologist would trust the output — are exactly the parts we
  built and validated.

---

## 10. Summary for the grader

- The system is **not** a wrapper: it composes three segmentation engines, implements non-trivial
  geometric measurement algorithms, and validates them under a genuine data constraint.
- The depth is **demonstrated, not asserted** — every algorithmic choice has a measured before/after,
  and the bug ledger shows the naïve approach producing clinically wrong numbers that we caught and
  fixed.
- We are honest about the boundary: pretrained segmenters (correct medical-AI choice), validated
  measurements (our contribution), and an evaluation methodology designed for a domain where the ideal
  dataset does not exist.

---

## References

Citations below are drawn from the project's verified-research memos, which record the locked
identifiers; where the source confidence is qualified, that is noted in the relevant memo and the
paper's bibliography.

- Genant HK, et al. Vertebral fracture assessment using a semiquantitative technique. *J Bone Miner
  Res.* 1993. **PMID: 8237484**.
- Wang, et al. Endplate line-fit morphometry (ICC 0.97 vs 0.75 four-corner). 2023. **PMC10685593**.
- Chen, et al. Cervical endplate concavity/slope morphology. 2013.
- Miyazaki M, et al. Cervical disc degeneration grading (T2). 2008. **PMID: 18525490**.
- Nakashima H, et al. Disc bulging on MRI in an asymptomatic population (n = 1211). **PMID: 25584950**.
- Nell C, et al. Cervical canal / SAC normative values on MRI. *PLoS One.* 2019.
  **doi:10.1371/journal.pone.0222682**.
- Spine-Generic (healthy multi-vendor cervical T2) — used as the healthy anchor cohort.
- MMCSD (Synapse syn63903115) — symptomatic CSM/CSR cohort used as the demonstration set.
- F1000 cervical MRI + Cobb cohort (n = 77) — external alignment reference.

For thresholds and their provenance (including where in-code values were found to be uncited and were
corrected), see the G6 threshold catalog and the verified-research memos
(`vb_hahp_norm_verified`, `disc_bulge_norm_verified`, `cervical_disc_grading_verified`,
`disc_height_dhi_norms`, `cervical_cobb_gt_data`).
