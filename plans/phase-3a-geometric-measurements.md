# Phase 3A — Geometric Measurements

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

The Measurements phase has three sub-engines that run in parallel on the same segmentation output:

- **3A — Geometric engine** on TotalSpineSeg vertebra/disc/canal masks
- **3B — Cord/compression engine** on SCT cord segmentation
- **3C — Signal-based engine** (experimental) on raw T2 intensities within masks

Each sub-engine outputs a flat dict `{ measurement_name: { level: value_in_physical_units, ... } }`. These are merged before Phase 4.

---
### 3A — Geometric engine

All 3A measurements operate on a single chosen mid-sagittal 2D slice unless otherwise noted. All outputs are in mm or degrees.

#### 3A.1 Vertebral body AP width

**Input:** 2D binary mask per vertebra (C2–C7).

**Method:** For each vertebra:
1. Extract its 2D binary mask on the mid-sagittal slice.
2. Fit a **minimum-area rotated rectangle** via `cv2.minAreaRect`. This returns a center, (width, height), and rotation angle.
3. Identify which side of the rectangle is AP vs SI based on rotation angle (SI side is the longer one in a vertebral body; AP is shorter). Sanity-check by comparing ratio to population norms (SI/AP typically 0.7–1.1).
4. Report shorter side × pixel spacing = AP width in mm.

**Why rotated rectangle over axis-aligned bounding box:** vertebrae tilt with lordosis (especially C2 and C7); axis-aligned box overestimates AP width by including empty space when the vertebra is rotated.

**Why not "measure at mid-height":** the rotated rectangle already integrates over the whole vertebra. Measuring at a single mid-height horizontal line is noisier and sensitive to exact choice of horizontal coordinate. The rotated-rectangle approach is more robust and is the de-facto standard in [Spine Explorer (Huang 2020)](https://www.sciencedirect.com/science/article/abs/pii/S1529943019311241) for lumbar.

**Known limitation:** Osteophytes anterior to the vertebral body inflate AP width. For cases where osteophyte detection becomes relevant, a future refinement is to erode the mask by 1–2 mm before fitting the rectangle. Not implemented in v1.

**Reference values (for Phase 4 thresholds):**
- Yukawa et al. 2018 — 1,200 asymptomatic Japanese adults, C2–C7 VB dimensions stratified by age/sex
- Thelen et al. 2019 (SHIP, [PLOS One](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0222682)) — 2,453 Caucasian adults, cervical VB width reference

**Code asset:** Custom, ~30 lines. No standalone repo for this on cervical MRI.

#### 3A.2 Vertebral body SI height (anterior + middle + posterior)

**Input:** same as 3A.1.

**Method:**
1. Get the 4 corners of the rotated rectangle (from 3A.1).
2. Identify the 4 corners as: anterior-superior (AS), anterior-inferior (AI), posterior-superior (PS), posterior-inferior (PI).
   - Identification: sort corners by the AP axis (shorter principal axis of rectangle) to get anterior vs posterior pair, then by SI axis to get superior vs inferior within each pair.
3. Compute:
   - **Anterior height** = distance(AS, AI)
   - **Posterior height** = distance(PS, PI)
   - **Middle height** = distance between midpoints of the two SI edges (average of the two)
4. All three values per vertebra.

**Why all three rather than just one:** Free extra signal. The ratio of anterior/posterior height is the standard [Genant 1993 classification](https://pubmed.ncbi.nlm.nih.gov/8237484/) metric for vertebral wedge fractures. Storing all three now unlocks future fracture-detection work without rerunning segmentation.

**Reference values:**
- Same Yukawa 2018 / SHIP 2019 as 3A.1.

**Code asset:** Custom, ~20 lines atop 3A.1.

**Downstream consumer:** 3A.6 Disc Height Index uses `middle height`.

#### 3A.3 Spondylolisthesis + Meyerding grading

**Input:** rotated-rectangle corners for every adjacent vertebra pair (from 3A.1 / 3A.2).

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

**Method:** Hard thresholds on C2–C7 Cobb angle. Defined in Phase 4 (Interpretation), not here — this subtask just provides the raw angle.

---
## Open questions specific to this phase

(Append questions here as they come up during research. One per bullet.)

- _(none yet)_

## Session notes

(Append brief notes by date/author as research progresses. Don't delete old notes.)

- _(none yet)_
