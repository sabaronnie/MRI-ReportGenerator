# Phase 3A — Geometric Measurements

**Owner:** TBD
**Reviewer:** TBD
**Status:** v1 content imported — under team review; 3A.1 and 3A.2 method finalized 2026-04-28 by Roni
**Last updated:** 2026-04-28 by Roni (3A.1 / 3A.2: disc-anchored 6-point Genant method refined with AP-width centerline slice selection; exploratory shared-single-slice variant added in Colab only)

---

## What a reviewer should check

- Does the method chosen actually work on Duke's segmentation masks?
- Are the alternatives rejected for the right reasons?
- Is any repo/reference missing? Add it if so.
- Does anything here conflict with another phase? Flag it.
- Is anything unclear? Mark it as an open question at the bottom.

---

The Measurements phase has three sub-engines that run in parallel on the same segmentation output:

- **3A — Geometric engine** on TotalSpineSeg vertebra/disc/canal masks
- **3B — Cord/compression engine** on SCT cord segmentation
- **3C — Signal-based engine** (experimental) on raw T2 intensities within masks

Each sub-engine outputs a flat dict `{ measurement_name: { level: value_in_physical_units, ... } }`. These are merged before Phase 4.

---
### 3A — Geometric engine

Most 3A measurements operate on one chosen mid-sagittal 2D slice per level unless otherwise noted. All outputs are in mm or degrees.

#### 3A.1 Vertebral body AP width  &  3A.2 Vertebral body SI heights — joint method

> **Note:** 3A.1 (AP width) and 3A.2 (anterior / middle / posterior SI heights) share a single 6-point extraction pipeline based on the Genant 1993 morphometric method, adapted for mask-based MRI input. The pipeline produces all four measurements per vertebra in one pass. This section documents the joint method; 3A.2 below references it.

**Input (per vertebra):** TotalSpineSeg `step2_output/scan.nii.gz` 3D segmentation containing:
- Cervical vertebra labels: C3=13, C4=14, C5=15, C6=16, C7=17
- Adjacent disc labels: 63=C2-C3, 64=C3-C4, 65=C4-C5, 66=C5-C6, 67=C6-C7, 71=C7-T1
- Canal labels: 1=spinal cord, 2=CSF

The MRI used for display is loaded from `input_raw/scan_0000.nii.gz` and resampled onto the segmentation grid via `nibabel.processing.resample_from_to`.

**Method:** Five stages.

**1. 3D disc-anchored body isolation.** The body's anteroposterior range is defined by the union of voxels in its adjacent discs (above and below) across the entire 3D volume:

```
ap_lo = min(disc_voxels along AP axis) − 2 mm margin
ap_hi = max(disc_voxels along AP axis) + 2 mm margin
body_3d = vertebra_mask  AND  (ap_lo ≤ AP coordinate ≤ ap_hi)
```

Discs share AP depth with the bodies (both anterior of the canal); arch + spinous process are posterior of the canal and so fall outside the disc AP range. Using all disc voxels in 3D — not per-slice — makes the AP filter robust to per-slice TSS noise. This replaces a previous SI-extent-threshold approach which failed on C7 (large spinous process) and on slices with thin body cross-sections.

**2. Slice selection — canal-visible (midline) band.** Per-slice canal voxel count peaks at the true midline and falls off laterally. Slices where canal voxels reach ≥ 70% of the per-slice peak define the *midline band* — anatomically the slices nearest the patient's true sagittal midline. Within this band, each vertebra's geometric reference slice is the slice with the most body-mask voxels for that level. Measurements are then attempted on that best slice and its neighbors (`best ± 1`) when valid. Heights and tilt are averaged across valid slices, but AP width is taken from the valid slice whose width endpoints have the **smallest SI mismatch** (the cleanest craniocaudal centerline crossing). Edge slices (where TSS produces sliver-shaped artefacts) are excluded by construction without measurement-value filtering, so pathological measurements are still surfaced as flags.

**3. PCA in physical (mm) space.** On the chosen 2D body mask, compute pixel coordinates in mm by multiplying voxel positions by the affine spacings, then run PCA on the centred coordinates. The two principal eigenvectors are the body's intrinsic SI and AP axes — robust to anisotropic voxel spacing and to lordotic vertebra tilt. SI is identified as the eigenvector more aligned with the global SI direction; AP is the perpendicular one. Signs are made deterministic (SI points inferior, AP sign consistent across vertebrae).

**4. Six-point extraction.** All six points are real body pixels in the PCA-projected (SI, AP) frame. Corners use **edge-strip extrema**:

- **Top edge strip** = body pixels in the top 15% of SI range (the superior endplate region).
- **Bottom edge strip** = bottom 15% of SI range (the inferior endplate region).
- **AS** = pixel in top strip with smallest AP projection (anterior-superior corner).
- **PS** = pixel in top strip with largest AP projection (posterior-superior corner).
- **AI** = pixel in bottom strip with smallest AP projection.
- **PI** = pixel in bottom strip with largest AP projection.
- **M_sup, M_inf** = topmost / bottommost pixels in a thin AP slab (~1.5 mm wide) around the AP midpoint of the body. These follow the actual endplate surface, capturing inward dip in biconcave fractures (Genant 1993).
- **A_mid, P_mid** = anterior-most / posterior-most pixels inside a thin SI slab (~1.5 mm wide) around the SI midpoint of the body. If multiple pixels tie, choose the ones closest to the true SI centerline. This makes AP width less sensitive to off-center slices.

**5. Measurements.**

| Measurement | Formula | Goes to |
|---|---|---|
| `AP_width`    | \|AP(`A_mid`) − AP(`P_mid`)\| on the valid slice with minimum `SI_mismatch(A_mid, P_mid)` | **3A.1 output** |
| `H_anterior`  | ‖AS − AI‖ | **3A.2 output** |
| `H_middle`    | ‖M_sup − M_inf‖ | **3A.2 output** |
| `H_posterior` | ‖PS − PI‖ | **3A.2 output** |

For 3A.2, `H_anterior`, `H_middle`, `H_posterior`, and `tilt` are averaged across valid `best ± 1` slices. For 3A.1, AP width is **not averaged**; it is taken from the cleanest centerline slice among those same candidates.

**Pathology flags (post-measurement, never used to reject):**
- `AP_width` < 12 mm or > 22 mm → outside typical cervical normative range.
- |tilt| > 20° → unusual axis orientation; likely segmentation issue.
- `H_anterior` < 70% × `H_posterior` → possible wedge fracture.
- `H_middle` < 70% × max(`H_anterior`, `H_posterior`) → possible biconcave fracture.

Flags are surfaced for radiologist review. Measurements are always reported regardless of their values, so genuine pathology remains visible in the output.

**Why edge-strip corners over rotated bounding-box vertices:** Rotated-bbox vertices (e.g. `cv2.minAreaRect` corners) sit at the body's outermost extent in PCA space — *not on the body itself* — so AP_width is overestimated for non-rectangular bodies. Edge-strip extrema return real body pixels along the actual endplates, giving accurate AP and SI dimensions for any body shape.

**Why edge-strip corners over closest-pixel-to-bbox-vertex search:** A nearest-neighbour search for each bbox vertex can land on interior pixels when the body is irregular (a more "central" pixel can win the Euclidean-distance race against an actual corner pixel). It also caused symmetric-collapse failures (e.g. AS = PS at C7) when the body was small. Edge-strip extrema put each corner in a distinct strip and at the strip's actual edge.

**Why disc-anchored body isolation over an SI-extent threshold:** A 50%-of-max-SI-extent threshold on AP bins fails on vertebrae where the spinous process has comparable SI extent to the body (notably C7). Discs provide an anatomical AP anchor that doesn't require a tunable threshold and gives consistent results across all cervical levels.

**Why canal-visibility for slice selection:** The canal is a midline structure visible only at slices near the true midline. Restricting slice selection to slices where the canal reaches ≥ 70% of its peak voxel count selects an anatomically meaningful band — the same band where the body cross-section is well-formed. Edge slices producing sliver-shaped TSS artefacts are excluded without filtering on measurement values.

**Why AP width now uses centerline-constrained slice choice:** Duke-case debugging showed that the main AP-width error source was not Euclidean-vs-AP distance, but choosing a slice where `A_mid` and `P_mid` sat at different SI levels. A candidate slice with near-zero SI mismatch produced the expected C3 width, while adjacent slices overestimated it by ~0.9 mm. The current rule therefore keeps the per-vertebra midline band, but chooses AP width from the valid slice with the smallest `A_mid`/`P_mid` SI mismatch.

**Method references:**
- **Genant HK, Wu CY, van Kuijk C, Nevitt MC.** "Vertebral fracture assessment using a semiquantitative technique." *J Bone Miner Res* 1993; 8(9):1137–1148. PMID: [8237484](https://pubmed.ncbi.nlm.nih.gov/8237484/). Defines the 6-point morphometric method (originally lateral X-ray; the mask-based MRI adaptation here is novel and validated in Phase 5).
- **Huang J, Shen H, Wu J, et al.** "Spine Explorer: a deep learning based fully automated program for efficient and reliable quantifications of the vertebrae and discs on sagittal lumbar spine MR images." *Eur Spine J* 2020; 29:139–149. DOI: [10.1007/s00586-019-06182-z](https://doi.org/10.1007/s00586-019-06182-z). Validates the segmentation → PCA → corner-extraction pipeline (ICC > 0.95 vs manual on lumbar). Cervical adaptation is novel here. ⚠ Verify exact title/DOI before final submission.

**Reference values (Phase 4 thresholds will use these):**
- **Yukawa Y, Nakashima H, Ito K, et al.** "Quantitative analysis of cervical sagittal alignment in 1,200 asymptomatic adults." *Eur Spine J* 2018; 27:426–432. C2–C7 VB AP widths and heights stratified by age/sex. DOI: [10.1007/s00586-016-4807-7](https://doi.org/10.1007/s00586-016-4807-7). ⚠ Verify exact citation before publishing.
- **Thelen K, Jaeger M, Petersohn D, et al. (SHIP).** "Reference values for cervical canal and vertebral dimensions on MRI in 2,453 asymptomatic Caucasian adults." *PLOS ONE* 2019; 14(9):e0222682. DOI: [10.1371/journal.pone.0222682](https://doi.org/10.1371/journal.pone.0222682). Cervical VB and canal MRI normative dimensions.

**Validation status:** End-to-end working on one Duke case (2026-04-28) for C3–C7. Mask-based 6-point Genant on cervical sagittal T2 MRI is **not directly validated** in published literature — Phase 5 (clinical validation against AUBMC manual measurements) is required before clinical use.

**Known limitations:**
- TSS edge under-segmentation: TSS is known to under-cover ~1–2 mm strips at endplates, biasing SI heights low by ~5–15%. Quantified in Phase 5.
- C7 with very large spinous process: if disc 71 (C7-T1) segmentation is poor, body isolation may admit arch + SP pixels at C7. Compensated by the canal-visibility slice filter and by sanity flags.
- Anterior osteophytes: not specifically detected; if present they can extend the body's anterior AP edge and inflate AP_width by 1–2 mm.
- A single shared midsagittal slice for all C3-C7 is useful for visualization, but on the current Duke case it produced worse per-level measurements than the per-vertebra slice strategy. That shared-slice variant remains Colab-only and is not the service default.

**Code asset:** Custom, ~250 lines (helpers + measurement + display). Lives in the Phase 3A measurement service.

#### 3A.2 Vertebral body SI height (anterior + middle + posterior)

**Method:** Computed jointly with 3A.1 — see the 6-point Genant pipeline above. The three heights come out of the same six-point extraction:

- **`H_anterior`** = ‖AS − AI‖ (Euclidean distance in mm between anterior-superior and anterior-inferior corners on the body's edge strips).
- **`H_posterior`** = ‖PS − PI‖.
- **`H_middle`** = ‖M_sup − M_inf‖ (midpoints of the superior and inferior endplate slabs, following the actual endplate surface — captures inward dip in biconcave fractures per Genant 1993).

**Why all three rather than just one:** The anterior/posterior ratio is the standard Genant 1993 classification metric for vertebral wedge fractures, and the middle/corner ratio is the biconcave signature. Reporting all three with the AP measurement preserves diagnostic signal for future fracture-detection work without rerunning segmentation.

**Reference values:** Same Yukawa 2018 / SHIP 2019 normative tables cited in 3A.1.

**Pathology flags:** Same as 3A.1 (`H_ant < 70% × H_post` → wedge; `H_mid < 70% × max(corner)` → biconcave).

**Downstream consumer:** 3A.6 Disc Height Index uses `H_middle`.

#### 3A.3 Spondylolisthesis + Meyerding grading

**Input:** vertebral corners and AP widths from the body-morphometry producer (from 3A.1 / 3A.2).

**Method:** For each pair `(upper, lower)` in `[(C2, C3), (C3, C4), (C4, C5), (C5, C6), (C6, C7)]`:
1. Take posterior-inferior corner of the upper vertebra (PI_upper).
2. Take posterior-superior corner of the lower vertebra (PS_lower).
3. Compute AP-axis offset: `slip = (PI_upper - PS_lower) projected onto AP axis`, in mm.
4. Sign convention: positive = anterior slip (anterolisthesis), negative = posterior slip (retrolisthesis).
5. **Meyerding grade**: `|slip| / AP_width_of_lower × 100%`
   - Grade I: 0–25%
   - Grade II: 25–50%
   - Grade III: 50–75%
   - Grade IV: 75–100%
   - Grade V (spondyloptosis): >100%

**Report format:** `"C4 on C5: 3.2 mm anterolisthesis (Grade I)"`.

**Caveat to surface in the report:** MRI is acquired **supine**. Spondylolisthesis is best detected on **standing lateral / flexion-extension radiographs**; supine imaging often under-detects it because the slip reduces when horizontal. Flag in every spondylolisthesis output: *"Measured on supine MRI — functional radiographs may show greater slip."*

**Code asset:** Custom, ~40 lines. No cervical-specific repo found that outputs graded slip in mm. For comparison: [SpineNet (Windsor)](https://github.com/rwindsor1/SpineNet) does binary spondylolisthesis detection on lumbar but not millimetric slip.

**Literature reference:** Meyerding HW 1932 (original grading); Saravi et al. 2022 for modern deep-learning automation (lumbar, AUC 0.95).

#### 3A.4 Disc SI height

**Input:** per-disc binary mask on mid-sagittal slice (labels 63, 64, 65, 66, 67, 71 for C2/3 through C7/T1).

**Method:** Same rotated-rectangle approach as 3A.1. Discs are elongated in the AP direction (wider than tall), so:
- Longer side = AP width (for 3A.5)
- Shorter side = SI height (this measurement)

**Report per level** in mm.

**Caveat:** Unlike vertebrae, discs vary more in AP width than in SI height. The rotated rectangle is still correct but we should sanity-check that SI height < AP width for every disc — if not, the labels are swapped and something is wrong with segmentation.

**Reference values:** No single definitive table for cervical disc SI height; values cluster around 4–7 mm with wide inter-subject variability. Duke demographic curves (Phase 4.4) will give us our own reference distribution.

**Code asset:** Custom, ~25 lines. Reuses the rotated-rectangle module from 3A.1.

#### 3A.5 Disc AP width

**Method:** As above, longer side of rotated rectangle.

**Use:** Mainly for detecting disc bulge/protrusion by comparing to adjacent vertebral body AP widths. A disc AP width significantly greater than (VB_above AP + VB_below AP)/2 + ~2 mm suggests disc bulge. This comparison logic lives in Phase 4.

#### 3A.6 Disc Height Index (DHI) — derived

**Method:** `DHI[level] = disc_SI_height[level] / middle_height[VB_above_or_below]`.

Convention: use the upper vertebra's middle height (e.g. DHI at C3/4 uses C3 middle height). Alternate convention uses average of upper and lower — we use upper because it matches the most commonly cited Farfan/Frobin definitions and avoids double-counting the upper VB as denominator for two consecutive levels.

**Thresholds:** Reduced DHI (< ~0.3 for cervical) suggests disc space narrowing / degeneration. Exact threshold set in Phase 4.

**Code asset:** ~5 lines of arithmetic once 3A.2 and 3A.4 are done.

#### 3A.7 Canal AP diameter

**Input:** canal mask (TotalSpineSeg label 2) on mid-sagittal slice.

**Method:** Canal AP diameter is conventionally measured **at the mid-vertebral-body level, not at the disc level**, because the canal is narrower at disc levels due to disc bulging. This matches the SHIP study, Griffith 2024, and Ulbrich 2014 conventions.

For each vertebra C2–C7:
1. Identify the canal mask columns (AP-axis extent) that fall within the SI-extent of that vertebral body.
2. For each row within that vertebral body's SI range, measure the AP-axis extent of the canal mask (leftmost-to-rightmost pixel along AP).
3. Take the **median** across rows (robust to noisy segmentation boundaries) → canal AP at that vertebral level, in mm.

**Clinical thresholds (Phase 4 preview):**
- > 13 mm: normal
- 10–13 mm: relatively narrow / borderline
- < 10 mm: critically narrow / absolute stenosis

**Reference:** Ulbrich 2014 (Radiology, N=140) normative values at C1, C3, C6; Thelen 2019 SHIP (N=2,453) for C2–C7.

**Code asset:** Custom, ~30 lines.

#### 3A.8 Torg-Pavlov ratio — derived

**Method:** `Torg_Pavlov[level] = canal_AP[level] / VB_AP_width[level]`.

Per-level. Ratio < 0.8 flags developmental stenosis (Torg 1987).

**Clinical caveat:** The Torg ratio was originally defined on lateral cervical **radiographs**, where magnification affects both canal and VB equally. On MRI, the ratio still works but thresholds may need slight adjustment. Recent work (Griffith 2024) suggests the ratio is most useful at C4–C6 where stenosis risk peaks. We compute it for every level but only flag clinically at C4, C5, C6.

**Code asset:** ~5 lines.

#### 3A.9 Most stenotic level identification

**Method:** `argmin` over canal_AP[level]. Returns the one level with the minimum canal AP diameter, plus its value.

**Rationale:** In stenosis, clinicians care most about *the worst level*. Reporting all six numbers requires the reader to scan and sort; explicitly surfacing the argmin saves a cognitive step.

**Output format:** `"Most stenotic level: C5 (canal AP 9.8 mm, critically narrow)"`.

**Code asset:** ~5 lines.

#### 3A.10 C2–C7 Cobb angle

**Input:** rotated-rectangle corners for C2 and C7.

**Method:** Convention used: **inferior endplate of C2 to inferior endplate of C7** (this is the Martini 2021 convention, the most widely cited in modern cervical alignment literature).

1. Inferior endplate of C2 = line from AI(C2) to PI(C2) where AI/PI are the anterior-inferior and posterior-inferior corners of C2.
2. Inferior endplate of C7 = line from AI(C7) to PI(C7).
3. Cobb angle = angle between these two lines.
4. Sign: positive = lordotic (normal direction for cervical), negative = kyphotic (abnormal).

**Alternative convention considered and rejected:** Superior-endplate-of-C2 to superior-endplate-of-C7. Also in the literature, but less common in recent papers. Stick with inferior-inferior for consistency with Yukawa 2018 reference dataset.

**Normal range (Martini 2021 review, aggregating multiple asymptomatic cohorts):**
- Lordotic: > 10°
- Straight: −10° to 0°
- Kyphotic: < 0°

Yukawa 2018 (N=1,200 asymptomatic): mean 13.9° ± 12.3°. Wide normal range — lots of healthy people are at 0–10°.

**Critical caveat to surface in the report:** MRI is acquired **supine**; radiographs are acquired **standing**. Cervical lordosis is routinely *lower* on supine MRI than on standing radiographs by ~5–10°. Yu 2021 ([PMC8702200](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8702200/)) showed this directly. Thresholds in Phase 4 will be adjusted for the supine context, and the report will flag this explicitly for every Cobb angle output.

**Code asset:** Custom, ~25 lines atop 3A.2.

**Comparable repos for reference only (not directly usable — different modality):**
- [LijunRio/Spine-cobb-angle-measurement](https://github.com/LijunRio/Spine-cobb-angle-measurement) — OpenCV-based, both coronal and sagittal plane, X-ray input. Good reference for the sagittal-plane geometry.
- [mazurowski-lab/Scoliosis_project](https://github.com/mazurowski-lab/Scoliosis_project) — segmentation-based Cobb (Windsor 2024), X-ray coronal. The segmentation-then-centerline approach is methodologically the closest to ours.

#### 3A.11 Segmental angles

**Method:** Same as 3A.10 but applied to each adjacent pair: C2–C3, C3–C4, C4–C5, C5–C6, C6–C7.

**Use:** Identifies focal kyphosis at a single level even when global C2–C7 Cobb looks normal. A segment that contributes anomalously large kyphosis despite normal global lordosis is a common pattern in post-traumatic or post-surgical cervical spines.

**Code asset:** Trivial extension of 3A.10, ~10 extra lines.

#### 3A.12 Lordosis classification

**Method:** Hard thresholds on C2–C7 Cobb angle. Defined in Phase 4 (Assessement), not here — this subtask just provides the raw angle.

---
## Open questions specific to this phase

(Append questions here as they come up during research. One per bullet.)

- _(none yet)_

## Session notes

(Append brief notes by date/author as research progresses. Don't delete old notes.)

- **2026-04-28 — Roni:** Finalized the 3A.1 / 3A.2 method end-to-end on one Duke case. Replaced the v1 `cv2.minAreaRect` rotated-rectangle approach with a disc-anchored, canal-restricted, edge-strip 6-point Genant pipeline. Iteration log:
  - **v1 cv2.minAreaRect on full vertebra mask:** AP_widths came out ~38–58 mm for C3–C7 (2–3× too high). Cause: TSS vertebra label includes the posterior arch + spinous process, which extends the rotated rectangle posteriorly far past the body.
  - **+ 50%-of-max-SI-extent threshold to trim the SP tail:** worked for C5/C6/C7 but C3/C4 corners collapsed (body region too thin) and C7 sometimes selected the back portion (arch had comparable SI extent to body). Tuning the threshold caused regressions elsewhere.
  - **Per-vertebra slice selection (max total vertebra voxels):** fixed C4/C5 picking the back, but the C3 chosen slice was where TSS produced a thin diagonal sliver — wrong AP and 30°+ tilt artefact.
  - **Slice picker by shape quality (solidity, single-CC, not-ribbon-thin):** could land on a small clean blob that wasn't the actual body — segmentation noise wins by being well-shaped.
  - **Disc-anchored body isolation (3D, using union of disc voxels):** anatomically correct AP filter, no tunable threshold, robust to per-slice TSS noise. Solved the SP-inclusion and threshold-tuning problems for all five vertebrae.
  - **Canal-visibility slice band (≥ 70% of peak canal voxels):** restricts to true midline slices where the body cross-section is well-formed. Replaces the value-based "physiological range" filter, which was wrongly hiding pathology.
  - **Corner finding iteration:** rotated-bbox vertices (Spine Explorer convention) overestimated AP because vertices sit outside the body. Closest-pixel-to-vertex landed on interior pixels for irregular bodies. Half-locked closest worked partially but missed body corners on asymmetric bodies. Pure SI extrema in halves underestimated AP. Lexicographic SI-then-AP failed because PCA float projections never tie. **Final method: edge-strip extrema (top/bottom 15% SI bands; min/max AP within each strip)** puts corners on real body pixels at the actual endplates.
  - **AP-width refinement after Duke-case debugging:** the residual C3 width error was not caused by Euclidean-vs-AP distance; it came from using a slice where the `A_mid` and `P_mid` width points sat at different SI levels. The final rule keeps the canal-visible per-vertebra band, computes width on `best ± 1`, and selects the valid slice with the **smallest `A_mid`/`P_mid` SI mismatch**. Width is reported as AP-only distance on that slice.
  - **Shared single-midsagittal prototype:** a Colab-only variant was built to force one slice for all C3-C7 by maximizing total isolated-body area in the canal-visible band. It gave worse measurements on the current Duke case, so it remains exploratory and is not the service default.
  - **Result on the test Duke case (C3–C7):** AP widths in the cervical normative range (15–22 mm), tilts physiological (< 10° max), no degenerate / collapsed measurements. Pathology surfaces as flags rather than getting filtered out.
- **Validation gap:** mask-based 6-point Genant on cervical sagittal MRI is novel — Phase 5 must validate this against AUBMC manual radiologist measurements (ICC, Bland-Altman) before clinical use.
- **Open question for Phase 5:** edge-strip width (`EDGE_FRAC = 0.15`) was set empirically. Phase 5 ICC analysis should compare 0.10 / 0.15 / 0.20 against radiologist measurements to pick the best.
