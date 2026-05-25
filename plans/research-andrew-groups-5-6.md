# Research Notes — Andrew — Groups 5 + 6

**Owner:** Andrew (`@andrew2119`)
**Scope:** Group 5 (signal-based abnormal finding detection) + Group 6 (clinical interpretation & report integration)
**Status:** in progress — week 1 research
**Source of truth for measurement definitions:** `plans/measurement_components.pdf` (AUBMC radiologist spec)

This file is for parallel research notes. It will be consolidated later into `phase-3c-signal-based.md`, `phase-4-interpretation.md`, and `phase-6-report-generation.md`.

---

## Conceptual Context (built through Q&A — append insights as they come)

> Captures the mental model behind what we're researching and why. Not a literature summary — that lives in the per-task sections below. This section is for the *frame* of the work.

### What the measurement stage is

A radiologist reading a cervical spine MRI does two things: (a) identifies anatomy, (b) quantifies it (mm, degrees, ratios) and interprets against medical thresholds. **Segmentation does (a). The measurement stage does (b).** Without measurements, segmentation gives you colored regions with no clinical meaning. Without interpretation, measurements give you numbers no one can act on.

### What prior stages give us as inputs

- **From Phase 1 (Input)**: a clean NIfTI in known orientation (sagittal), voxel spacing in mm, mid-sagittal slice index.
- **From Phase 2 (Segmentation, TotalSpineSeg + SCT)**: a label map where every voxel is tagged — label `1` = cord, label `2` = canal (CSF), labels `41+` per individual vertebra (C1–C7 etc.), labels `63+` per disc.

So the measurement stage's input is: one labeled 3D image + voxel spacing + mid-sagittal slice. From that, everything is computed.

### Why measurements split into 4 technical categories (not just "spine measurements")

| Type | Example | Used by |
|---|---|---|
| Direct geometric | VB AP width = front-to-back distance across the contour | Groups 1, 2, 3, 4 |
| Derived | Torg-Pavlov = canal AP ÷ VB AP; SAC = canal AP − cord AP | Groups 3, derived in 4 |
| **Signal-based** | Myelomalacia = abnormally bright signal *inside* the cord mask | **Group 5 (mine)** |
| Tool-wrapped | Cord measurements via Spinal Cord Toolbox; cord percentiles via SCT `-normalize-hc` | Groups 3 (cord), 6 (percentiles) |

### Why the 6 groups exist (one per clinical question a radiologist asks)

| Group | Clinical question | Owner |
|---|---|---|
| 1 — VB | "Is the bone shape normal? Is one vertebra slipping?" | Ronnie |
| 2 — Disc | "Is the disc collapsing or bulging?" | Mohammad |
| 3 — Canal/Cord | "Is the cord being squeezed (stenosis)?" | Ronnie |
| 4 — Alignment | "Is the spine curved correctly (lordosis/kyphosis)?" | Mohammad |
| 5 — Signal anomalies | "Are there abnormal-looking spots? (cord damage, fracture, tumor)" | **Andrew** |
| 6 — Interpretation | "What does it all clinically mean?" | **Andrew** |

A radiology report needs all six to be complete.

### What makes Group 5 fundamentally different from Groups 1–4

|  | Groups 1–4 | **Group 5 (mine)** |
|---|---|---|
| Input needed | Just the mask (binary "this voxel is bone") | Mask **+ raw MRI intensity values** inside the mask |
| Measurement type | Distances, ratios, angles | Signal intensity statistics + thresholding |
| Output | Numbers (mm, degrees, ratios) | Flags ("abnormal signal at C5 cord — possible myelomalacia, physician review") |
| Reference for "normal" | Literature-derived population averages | Often the patient's own unaffected levels (within-subject normalization) |

**Mental model:** Groups 1–4 use masks as *shapes*. Group 5 uses masks as *regions to look inside*. Same source data, different operations on it.

### Why my slot (Groups 5 + 6) is internally coherent even though 5 is signal and 6 is rules

- **5 produces anomaly flags** (e.g., 5.1 myelomalacia detected → flag).
- **6 consumes those flags** as inputs to syndrome rules (e.g., 6.2 myelopathy combines canal stenosis from Ronnie + reduced SAC + 5.1 cord signal flag).
- So 5 + 6 = the "detect abnormal stuff and figure out what it clinically means" role. Coupled by purpose, not by technique.

The other slots are coherent by different logics:
- **Ronnie (1 + 3)**: coupled by *data* — VB AP width feeds Torg-Pavlov. Self-contained bucket.
- **Mohammad (2 + 4)**: coupled by *technique* — both are geometric extractions from masks.

### Spine anatomy primer (CS-friendly)

**Spine = stack of Oreos.** Cookie = vertebra (bone). Cream filling between cookies = disc (gel cushion / shock absorber).

**Spine regions, top to bottom:**
| Region | Vertebrae | Location |
|---|---|---|
| **Cervical** | **C1–C7** (7) | **Neck — our project** |
| Thoracic | T1–T12 (12) | Mid-back, where ribs attach |
| Lumbar | L1–L5 (5) | Lower back |
| Sacrum / Coccyx | fused | Pelvis / tailbone |

**C1–C7 numbered top to bottom.** C1 = directly under skull. C7 = right above T1.

**Why C1 is omitted in our measurements:**
- C1 (the **atlas**) is anatomically unique — ring-shaped, no normal vertebral body. Lets you nod yes.
- C2 (the **axis**) has a peg-like bone (the "dens"). Lets you shake no.
- **No standard disc between C1 and C2** — different anatomy.
- C1's shape doesn't fit our measurement assumptions, so the pipeline focuses on **C2–C7**.

**Disc levels in our scope** (5 total): C2–C3, C3–C4, C4–C5, C5–C6, C6–C7. The "per-level structured report" (Group 6.3) produces one row per disc level → 5 rows.

### What we're actually measuring (reframing)

We are **NOT measuring conditions** like myelomalacia or fracture. We are measuring:
1. **Dimensions** in mm, degrees, ratios (Groups 1–4)
2. **Signal intensity statistics** within masks (Group 5)

**Conditions are INTERPRETATIONS of those measurements**, applied via threshold tables in Group 6.

Analogy: a doctor's checkup measures your blood pressure (a number); compares to thresholds (>130/80 = high); flags possible conditions (hypertension). They don't measure "hypertension" directly. **We don't measure "myelopathy" or "fracture" directly either.** We measure dimensions + signals, then map them to possible conditions.

The full set of ~15 measurements feeds Group 6's interpretation rules. No measurement is condition-specific — many measurements together inform many possible findings.

### MRI sequences (T1 / T2 / STIR)

Different "MRI sequences" = different magnet pulse settings → different tissues highlighted. Same patient, same scanner, different sequence → different image.

| Sequence | Bright | Dark | Best for |
|---|---|---|---|
| T1-weighted | Fat, marrow | Water / CSF | Anatomy detail |
| **T2-weighted** ← we use | **Water / CSF (very bright)**, edema | Cortical bone | Fluid, cord damage, edema, disc water |
| STIR | Edema (very bright) | Fat (suppressed) | Marrow edema, hidden fractures |

**We have ONLY T2.** Scope constraint. Picked because T2 alone shows the bulk of cervical spine pathology (compression, cord signal change, disc water content). Adding more sequences = scope expansion = team decision.

#### Why T2 specifically (and not T1 or STIR)?

In MRI physics, every tissue has its own "T2 relaxation time" — basically, how long the tissue holds onto its signal after being magnetically excited. Tissues with lots of free water (CSF, edema, fluid-rich tissue) have long T2 relaxation times; bone, fat, and dense tissue have short T2. When you tune the scanner to "T2-weighted" settings, the magnet's timing is set so that only the long-T2 (water-rich) tissues still have signal when the image is captured. The result: water-rich tissues come out brilliantly bright; everything else fades to grayscale or dark. That's what "water-bright settings" means in practice.

This matters for our project because **the cervical spine pathology we care about is fundamentally about water content**:

- **Spinal cord vs CSF contrast.** We need to see exactly where the cord ends and the cushioning CSF begins. CSF is pure fluid → T2 makes it brilliantly bright. The cord is medium gray. The boundary is sharp and easy for segmentation models to identify. On T1, CSF is dark and that boundary is muddy.
- **Cord damage (myelomalacia)** accumulates water through gliosis and edema. On T2, this shows up as **bright spots inside an otherwise gray cord** — you can literally see the damage. On T1, the same damage is mostly invisible.
- **Cord compression** is visible because you can see the bright CSF being "squeezed out" from around the cord as the canal narrows.
- **Disc water content** is what Pfirrmann grading (Group 2.4) measures. Healthy young discs have a water-rich gel center that's bright on T2. As they degenerate, water content drops and they get darker. T2 makes this directly visible.
- **Edema anywhere** — inflammation, injury, swelling — is bright on T2. So abnormal-finding flagging in Group 5 hinges on T2's water-sensitivity.

If we picked T1 instead, CSF would be dark, the cord-vs-CSF boundary would be unclear, and cord lesions would be nearly invisible. T1's strength is anatomical detail (subtle bone/fat structures), which isn't what we need. STIR (essentially T2 with fat suppression) is excellent for marrow edema and hidden fractures, but it's less universally acquired — every cervical MRI session includes T2; STIR sometimes isn't acquired at all. So T2 is the natural single-sequence choice: every clinically meaningful question we ask the pipeline depends on water-content contrast.

### File formats — NIfTI vs DICOM

The pipeline accepts EITHER format as input:

**DICOM** (`.dcm`):
- Hospital scanner output. Clinical standard.
- A **folder** of many `.dcm` files (one per slice) + heavy metadata (patient ID, scanner, voxel spacing, sequence, etc.)
- Read with Python `pydicom`.

**NIfTI** (`.nii` / `.nii.gz`):
- Research-friendly. Single file = entire 3D image + minimal metadata.
- `.nii` = uncompressed; `.nii.gz` = gzip-compressed (smaller).
- Read with Python `nibabel`.

Phase 1 (input handling) converts DICOM → NIfTI internally so downstream code only deals with one format.

### Decoding "sagittal T2-weighted cervical spine MRI"

| Word | Means |
|---|---|
| **Cervical spine** | Neck portion of spine (C1–C7) |
| **MRI** | Magnetic Resonance Imaging |
| **T2-weighted** | Sequence (water-bright settings) |
| **Sagittal** | Slice orientation (side profile view) |

Full phrase = a **side-view scan of the neck, taken with T2-weighted MRI**. "One sequence, one orientation, one file" = exactly that one thing, not a multi-sequence MRI session.

### What "T2 values" / intensity values actually are

When MRI scans tissue, each voxel emits a signal recorded as a **single number** — the intensity. **No real-world unit** (no mm, no Pa). It's an arbitrary scale.

- Higher number = brighter
- Range depends on bit depth (often 0–4095 for 12-bit, 0–65535 for 16-bit)
- Exact values vary per scanner / per scan

**You cannot say "T2 value of 180 = abnormal" universally.** You say "cord at C5 is 30% brighter than cord at C3 in this same scan → abnormal." This is why Group 5 uses **within-patient normalization** (compare suspected level vs unaffected levels in the same scan) rather than absolute thresholds.

### MRI signal primer (since Group 5 lives here)

On T2-weighted MRI:
- Water / CSF → very bright (hyperintense)
- Healthy cord → medium gray
- Healthy bone marrow → medium-bright
- Fat → bright
- Air, cortical bone → very dark (hypointense)

**When tissue is damaged/diseased, its signal changes from this baseline.** Damaged cord becomes brighter (more water from gliosis/edema). Bone marrow with edema becomes brighter on STIR. Detection = look at intensity values *inside* a mask region and check if they deviate from expected.

### Plain-English glossary (CS-translated)

**Anatomy:**
- **Spinal cord** — bundle of nerves from brain down through the spinal canal. Sends signals brain ↔ body.
- **Spinal canal** — the bony tube formed by stacked vertebrae. The cord lives inside it.
- **Vertebra** — one spine bone. Cervical = the 7 in the neck (C1–C7).
- **Vertebral body (VB)** — the thick drum-shaped front part of a vertebra (load-bearing).
- **Disc / IVD** — gel-filled cushion between two vertebrae. Shock absorber.
- **Endplate** — flat top/bottom of a vertebral body where the disc sits.
- **CSF** (cerebrospinal fluid) — clear liquid surrounding the cord inside the canal. **Brightest thing on T2.**
- **Bone marrow** — soft tissue inside bones, makes blood cells. In vertebrae, fills the VB.
- **Cortical bone** — hard outer shell of bone, low water → very dark on T2.
- **Fat** — adipose tissue, bright on T2.
- **Edema** — tissue swelling with fluid (extra water from injury / inflammation). Bright on T2 because of water content.

**MRI image:**
- **Voxel** — 3D pixel (cube). MRI is 3D so it's voxels, not pixels.
- **Voxel spacing** — the real-world size of each voxel in mm (e.g., `0.5×0.5×3 mm`). Every mm-measurement multiplies voxel counts by this.
- **Hyperintense / hypointense** — bright / dark on the image.
- **Sagittal / axial / coronal** — orthogonal views. **Sagittal** = side-on profile view (what we use).
- **T1 / T2 / STIR** — different MRI sequences (magnet settings). **T2** = water bright (what we use). **T1** = fat bright. **STIR** = T2 with fat suppressed (best for marrow edema).

**Conditions Group 5 detects:**
- **Myelomalacia** — *"cord softening."* Permanent damage to cord tissue from long-term compression / injury. Damaged tissue holds water → bright on T2.
- **Fracture** — broken vertebra. Compression / burst / wedge types. From trauma or osteoporosis.
- **Tumor / mass** — abnormal growth (benign or malignant; possibly metastasis from elsewhere). We flag, never classify.
- **Post-surgical scar** — fibrous scar tissue from prior spine surgery. Reported because it can mimic / hide other findings.

### Pipeline input — what we have (and what we don't)

**Input to the pipeline:** ONE file.
- **Sagittal T2-weighted cervical spine MRI**
- In **NIfTI** (`.nii` / `.nii.gz`) **or DICOM** (folder of `.dcm`) format

**We explicitly do NOT receive:**
- T1-weighted images
- STIR (fat-suppressed T2)
- Axial views
- Gadolinium-enhanced (contrast) sequences
- Other sequences (DTI, DWI, etc.)

Documented in `plans/phase-1-input-handling.md`. **Anyone wanting to expand this = team scope decision.**

### Implication for Group 5: signal analysis on T2 alone

Signal analysis ≠ STIR-only. T2 itself shows lots of useful signal info. Per-task viability:

| Sub-task | Ideal sequence | Have on T2? | Verdict |
|---|---|---|---|
| 5.1 Myelomalacia | T2 (cord damage = bright on T2) | ✅ | **Doable** — Weber 2023 T2-MI works on T2 |
| 5.2 Fracture | STIR for marrow edema | ❌ | **Geometric path only** (shape vs neighbors); skip signal path |
| 5.3 Tumor | Multi-sequence ideal, T2 partial | ✅ partial | **Flag abnormal regions only**, no classification |
| 5.4 Post-surgical scar | Gadolinium-enhanced T1 | ❌ | **Defer entirely** — out of scope |

### Mask vs raw MRI — what they are and how they combine

**The MRI** = a 3D NumPy-style array, shape e.g. `(384, 384, 20)`, each voxel holds an intensity value. Higher = brighter on T2.

```python
mri[100, 200, 11] = 90   # medium-dark voxel (could be cord)
mri[100, 200, 10] = 245  # very bright voxel (could be CSF)
```

**The segmentation mask** = a second 3D array, same shape, each voxel holds an integer label saying what tissue it is:

```python
mask[100, 200, 11] = 1   # this voxel is SPINAL CORD
mask[100, 200, 10] = 2   # this voxel is CANAL (CSF)
mask[100, 200, 12] = 45  # this voxel is VERTEBRA C5
```

**Mask = WHERE anatomy is. MRI = WHAT it looks like.**

**Groups 1–4 (geometric) use just the mask:**
```python
canal_voxels = np.where(mask[100, :, 10] == 2)[0]
canal_width_mm = len(canal_voxels) * voxel_spacing[1]
```
Notice: never reads `mri`, only `mask`.

**Group 5 (signal) uses BOTH:**
```python
cord_locations = np.where(mask == 1)        # mask: locate cord
cord_signal_values = mri[cord_locations]    # mri:  read intensity at those locations
mean_cord_signal = np.mean(cord_signal_values)
# compare against expected → flag if abnormal
```

### How Group 6 puts everything together

Each measurement from Groups 1–5 has an associated **threshold table** that maps a number to a severity tier. Examples:

- **Canal AP diameter** (Group 3): `>13 mm` normal, `10–13 mm` relatively narrow, `<10 mm` critically narrow
- **Meyerding** (Group 1.3): % slippage → Grade I (0–25%) / II / III / IV
- **Pfirrmann** (Group 2.4): T2 signal pattern → Grade I–V disc degeneration
- **Cobb angle thresholds** (Group 4.2): defines normal lordosis vs straightened vs kyphotic

**Group 6's job:**
1. Apply threshold tables → produce severity tags per measurement
2. **6.1 Radiculopathy rules** — combine disc + canal data → flag nerve-root compression patterns
3. **6.2 Myelopathy rules** — combine canal stenosis + SAC + cord signal flags from 5.1 → flag cord compression syndrome
4. **6.3 Per-level structured report** — compile every measurement + flag for each spine level into the radiology-style output
5. **6.4 Demographic percentile** — where does this patient sit vs population (Duke quantile regression + SCT `-normalize-hc` for cord)

So my role = **detect abnormalities (5) + apply thresholds + combine into clinical findings + assemble the report (6)**. Detection + interpretation + integration. The other slots produce raw measurements; my slot turns them into a usable report.

---

## Group 5 — Research Approach: Survey First, Deep-Dive Second

Before committing to any specific algorithm or paper for the four sub-tasks of Group 5, the research approach is to **first survey the landscape of existing solutions**, and only then pick what to wrap, what to implement, and what to defer. This is the academic-paper literature-review approach, and it is more rigorous than picking one paper (e.g., Weber 2023) and committing to implement it without seeing what else exists.

The motivation is simple: for a course project we want to **minimize what we write from scratch**. If a tool already exists that does 80% of what we need (e.g., the Spinal Cord Toolbox's compression-detection module), wrapping it is far better than reinventing it. The survey identifies these opportunities.

For each sub-task in Group 5, the survey will answer five questions:

1. **What published methods exist?** (Papers, with citation and year.)
2. **What open-source code is available?** (Repos, libraries, command-line tools.)
3. **What is the state-of-the-art accuracy / validation status?** (Tested on what dataset, with what metric.)
4. **Implementation cost: wrap-existing vs implement-from-paper vs build-from-scratch?**
5. **What datasets validate the approach?** (Is Duke usable, or do we need other data?)

The output of this survey is a "landscape map" for Group 5 — a structured summary that, for each sub-task, tells us what we'd wrap, what we'd implement, and where there's no good existing solution we'd have to acknowledge as a gap.

### Why split into 5.1–5.4 instead of a single unified signal-detection function?

The clearest way to see why is to walk through what each sub-task actually does, in plain terms — input, operation, output. Once the four are concrete, the differences are obvious.

**5.1 Myelomalacia — looking for damage inside the cord.** Take the MRI and the cord mask. Isolate the cord (the gray nerve bundle running through the canal). Walk along its length slice by slice and look at brightness. A healthy cord has roughly uniform medium-gray brightness from C2 down to C7. Damage shows up as a noticeably bright spot because damaged cord tissue accumulates water, and water is bright on T2. The operation: find spots where brightness is unusually high compared to the same patient's cord at adjacent unaffected levels. Output: `"Cord lesion at C5-C6, T2-MI score 1.4 (moderate)"`. This is a clean problem — the cord is one continuous structure, the patient's own healthy levels give a clear reference, and damage has a specific bright-on-T2 signature. Weber 2023's T2-MI works because of these favorable properties.

**5.2 Fracture — actually geometric, not signal-based.** Despite living in Group 5, fracture detection in our pipeline doesn't use signal at all, because the signal-based path requires STIR and we only have T2. Instead it uses shape. The operation: for each vertebra (C2 through C7), measure its height at the front, middle, and back. Compare those heights to the vertebrae directly above and below. A normal vertebra has heights similar to its neighbors. A fractured one is shorter or has uneven heights — wedge fractures have a much shorter front than back, compression fractures are shorter overall, burst fractures expand outward. Output: `"Wedge deformity at C6, anterior height loss 25% vs adjacent levels"`. **This is fundamentally different from 5.1 — it never reads the intensity values inside the vertebra. It uses the mask's shape only.** In technique it's more similar to Groups 1–4's geometric work than to 5.1's signal work.

**5.3 Tumor / mass — looking for anything weird, anywhere.** Tumors don't live in a fixed anatomical region — they can appear inside cord, inside vertebra, in surrounding soft tissue. Tumor signal patterns vary widely; some are bright, some dark, some mixed. There is no clean "expected normal" reference because you don't know in advance where the tumor is or what it looks like. The operation here is necessarily vaguer: scan the image for regions that stand out from their immediate surroundings (sharp signal discontinuity, region size beyond expected anatomical structures). Output: `"Abnormal signal region at C4 vertebral body level, physician review recommended"` — no specific diagnosis claim. This is much harder than 5.1 because the "what does normal look like?" question has no clean answer when you don't know what you're looking for.

**5.4 Post-surgical scar — out of scope without contrast imaging.** Scar tissue has characteristic signal patterns, but reliably detecting it requires gadolinium-enhanced sequences (an injected contrast agent that lights up scar tissue). We don't take contrast-enhanced sequences as input, so this sub-task is **deferred entirely** — not because it's impossible in principle, but because we'd need different input data that the team's scope doesn't include.

#### The differences are now obvious

- 5.1 looks at *intensity inside one specific organ* (cord) with a clean within-patient reference.
- 5.2 actually doesn't use intensity at all — it uses the *geometric shape* of vertebra masks. Shares technique with Groups 1–4 more than with 5.1.
- 5.3 has *no fixed location and no clean reference* — a different and harder problem class.
- 5.4 is *out of scope* because we lack the necessary input sequence.

So "Group 5 — signal-based detection" is really an organizational bucket that holds the four kinds of abnormal-finding tasks the AUBMC radiologist asked us to consider. The implementations, validation strategies, and feasibility differ significantly across them. Lumping them into one universal function would force ugly compromises on every one.

### Feasibility analysis given the Duke dataset and AUBMC validation

Before researching methods or code in depth, the right question is what can we actually deliver given the data we have? Here is the honest assessment.

**What Duke (the Nature dataset) provides** (from `cervical-spine-master-plan.md`):
- 1,255 sagittal T2 cervical MRI exams
- 481 patients with expert-verified segmentation masks — but **only of vertebral bodies and discs**, not cord, not canal, not pathology
- Demographics (age, sex, race, ethnicity)
- Imaging metadata

**What Duke does NOT provide:**
- Pathology labels (no "this patient has myelomalacia at C5")
- Cord or canal segmentation (those come from TotalSpineSeg, automated, not Duke-validated)
- Radiologist measurements (no ground truth for any specific measurement)
- Per-level vertebra classification within the masks

**What AUBMC will provide (per the master plan):** a separate ~20–30 case subset where a radiologist measures each case manually. This is the **only** place ground-truth pathology labels will exist for our project — used for clinical validation via ICC and Bland-Altman.

#### Per-sub-task feasibility

**5.1 Myelomalacia** is **feasible with caveats**. We can implement Weber 2023's T2-MI on Duke because the T2 images are present and TotalSpineSeg gives us cord segmentation. We cannot validate quantitatively against Duke because there are no pathology labels. The validation strategy is: run on the 481 expert-validated Duke cases to check the score distribution looks clinically sensible, then have the AUBMC radiologist confirm a sample of flagged cases. Realistic deliverable for the course: working pipeline + sanity-checked output distribution + small AUBMC validation set.

**5.2 Fracture (geometric path)** is **feasible**. We have vertebra masks expert-validated on 481 Duke cases, so the underlying segmentation is reliable. Computing shape deviations vs neighboring vertebrae is straightforward. Validation: run on Duke and manually inspect flagged cases to confirm they look like real fractures. Caveat: fractures are likely rare in Duke since it is a general MRI dataset, not a trauma cohort — so the AUBMC validation set will be the main place we actually see fracture cases.

**5.3 Tumor / mass** has **questionable feasibility**. Tumors are rare in any general MRI dataset, and Duke has no labeled tumor examples. Without labeled cases or a clinical population biased toward oncology, there is essentially no way to do meaningful validation. The honest deliverable is a **"flag abnormal signal region" function with no specific diagnosis claim**, demonstrated on whatever tumor case AUBMC happens to include in the validation set, or on synthetic test cases. I would recommend scoping this very narrowly — present it as "if there is an abnormal-looking region in any anatomical structure, the system flags it for physician review," not as a tumor detector.

**5.4 Post-surgical scar** is **confirmed deferred**. The required gadolinium-enhanced sequences are out of the pipeline's input scope. Document the limitation clearly in the final report and the writeup, frame it as a future-work item.

#### Recommended scoping for Group 5

Based on the feasibility analysis, the suggested scope:

1. **5.1 Myelomalacia detection** — full implementation, primary Group 5 deliverable.
2. **5.2 Fracture detection (geometric)** — full implementation, secondary deliverable.
3. **5.3 Tumor / mass detection** — narrow scope as a generic "abnormal-region flagger," with no tumor-specific claims.
4. **5.4 Post-surgical scar** — explicitly deferred and documented.

This is being honest about what the data supports and prevents the survey work from chasing tools we cannot validate. The survey can now focus tightly on (a) cord-signal analysis tools for 5.1 and (b) vertebral fracture detection tools for 5.2.

#### What Group 5 actually outputs

The split also reflects Group 5's output structure. Group 5 does not produce a single "anomaly score per voxel." It produces **structured, per-condition flags** that Group 6 consumes for clinical interpretation. A representative output sketch:

```python
group_5_output = {
    "myelomalacia_flags": [
        {"level": "C5-C6", "severity": "moderate", "t2_mi_score": 1.4}
    ],
    "fracture_flags": [
        {"level": "C6", "type": "wedge", "anterior_height_loss_pct": 25}
    ],
    "abnormal_signal_flags": [
        {"location": "C4 vertebral body", "note": "abnormal signal region; physician review recommended"}
    ],
    "scar_flags": []  # deferred — gadolinium required
}
```

The reason for this structure is that Group 6 needs to know *what kind* of finding came from Group 5 to apply the right interpretation rule. Myelopathy interpretation depends on the cord-lesion flag specifically. The fracture finding stands alone in the report. The catch-all "abnormal signal" flag triggers a generic review-recommended line. A radiologist reading the final report needs **named findings, not a generic score** — and the medical AI hard rules in CLAUDE.md require this. We never say "abnormal" without saying *what kind* of abnormal we're flagging.

#### On the universal anomaly-detection idea

There is a research direction in medical imaging called *anomaly detection* or *out-of-distribution detection* that tries to flag anything unusual without knowing what it is — using techniques like variational autoencoder reconstruction error or normalizing flows. It's interesting but immature for spinal MRI specifically, hard to validate clinically (a model that says "this looks weird" doesn't tell a doctor anything actionable), and produces outputs radiologists don't find directly useful. It could potentially serve as a *safety net* on top of the per-condition approach to catch things the four templates miss, but not as a *replacement* for the per-condition work.

### Survey targets

The four sub-tasks anchor the survey, but the search casts a wider net than "exact match on each task name":

- **5.1 Myelomalacia / cord signal abnormality.** Core search: T2 Myelopathy Index methods (Weber et al. 2023). Adjacent literature: Spinal Cord Toolbox compression detection (`sct_detect_compression`, Horáková et al. 2022); MS lesion detection in cord (deep-learning models like nnUNet-trained classifiers); cord lesion segmentation generally. Useful tools to evaluate: SCT itself, any nnUNet-based cord-lesion model.
- **5.2 Fracture detection (geometric path).** Core search: vertebral compression-fracture detection from sagittal MRI; deep-learning fracture detectors (nnDetect, vertebral-shape models). Adjacent: osteoporotic fracture detection on CT (different modality but same problem class — sometimes the methods translate).
- **5.3 Tumor / mass anomaly flagging.** Core search: spinal tumor / metastasis MRI detection. Realistic expectation: classification is too hard for course scope; the survey is to confirm that and identify the simplest "abnormal-region flagger" we can adopt.
- **5.4 Post-surgical scar.** Survey is brief and exists only to confirm our defer decision: scar detection requires gadolinium-enhanced sequences which are out of input scope.

Once the survey is complete (the next research session), each sub-task gets its own deeper section below with the chosen approach + implementation notes.

---

## Group 5 — Abnormal Finding Detection (Signal-Based)

### 5.1 Myelomalacia Detection (T2-MI / Weber 2023)

**Goal:** detect abnormally high T2 signal within the spinal cord mask → flag as "possible cord injury / gliosis, physician review."

**Approach options to research:**
- Threshold-based: signal intensity within cord mask vs. CSF reference at the same level (Weber et al. 2023 method).
- Within-patient normalization: compare cord signal at suspected level vs. cord signal at unaffected adjacent levels.

**Key references to read:**
- Weber et al. 2023 — T2 Myelopathy Index (primary method)
- Horáková et al. 2022 — SCT compression detection (related approach)

**Open questions:**
- _(append as research progresses)_

---

### 5.2 Fracture Detection

**Goal:** flag vertebral body shape deformity (compression, burst, wedge).

**Approach options:**
- Geometric: compare actual VB shape to expected shape from neighboring levels.
- Signal-based: bone marrow edema on T2/STIR.

**Decision:** likely **defer** signal-based (needs T1+STIR which we don't input). Geometric only, as a "shape deviation flag." Confirm scope with team.

---

### 5.3 Tumor / Mass Detection

**Per AUBMC recommendation:** scope as "abnormal signal regions flagged for physician review," not classification. Frame in report as `"region of abnormal signal at C5; clinical correlation required"`.

---

### 5.4 Post-Surgical Scar Detection

**Status:** likely defer entirely — typically requires gadolinium-enhanced sequences which are out of scope (sagittal T2 only).

---

## Group 6 — Clinical Interpretation Layer

### 6.1 Radiculopathy Indicators

**Combines:** disc measurements (2.x) + foraminal proxies → flag pattern, never diagnose.

**Output wording (per CLAUDE.md medical AI rules):**
`"Findings consistent with possible C5–C6 radiculopathy; clinical correlation required."`

---

### 6.2 Myelopathy Indicators

**Combines:** central canal stenosis (3.1) + reduced SAC (3.3) + cord signal changes (5.1).
- Threshold table needs literature review (DCM diagnostic criteria).
- Combine via rule-based scoring (e.g., 2 of 3 thresholds crossed → flag).

---

### 6.3 Per-Level Structured Report

**This defines the report schema that everyone writes to.** Critical cross-slot dependency.

Per level (C2–C3 through C6–C7), the report contains:
- Vertebral body dimensions (from Ronnie — Group 1)
- Disc dimensions (from Mohammad — Group 2)
- Canal AP diameter (from Ronnie — Group 3)
- Cord AP diameter (from Ronnie — Group 3)
- SAC (derived)
- Torg-Pavlov ratio (derived)
- Cobb / segmental angle (from Mohammad — Group 4)
- Any flags (myelomalacia from 5.1, fracture from 5.2, etc.)

**TODO:** publish a JSON schema for the per-level data structure so Ronnie + Mohammad write to it directly.

---

### 6.4 Demographic Percentile Comparison

**Approach:** quantile regression on Duke CSpineSeg (age, sex as inputs). For each measurement, report patient value + percentile.

Example output: `"Canal AP at C5: 11.2mm (12th percentile for 55-year-old male)."`

**Open questions:**
- Train one quantile regression per measurement, or a multi-output model?
- What percentile thresholds trigger a flag (e.g., <10th)?
- Cord percentiles: use SCT's `-normalize-hc` instead of training our own.

---

## Cross-slot dependencies (track here)

| Dependency | I need from | Status |
|---|---|---|
| Vertebra coords (for context in report layout) | Ronnie | not yet defined |
| Disc dimensions (for report 6.3) | Mohammad | not yet defined |
| Canal/cord measurements (for 6.2 myelopathy logic + 6.3 report) | Ronnie | not yet defined |
| Cobb / segmental angles (for 6.3 report) | Mohammad | not yet defined |

---

## Validation Strategy — Accuracy vs Interpretation (2026-04-29)

When we talk about "validating the pipeline," we're really doing two distinct things that are often conflated. Worth separating them explicitly so the team is aligned and so we don't waste effort applying the wrong tool to the wrong question.

### Accuracy validation — are the numbers correct?

This answers: when the pipeline says canal AP is 11.2 mm, is the canal actually 11.2 mm? Validation here means comparing pipeline output to ground-truth measurements taken on the same case.

Concrete steps in priority order:

- **Now (this session's task)**: ITK-Snap / 3D Slicer manual measurement on a Duke case, compare against Roni's pipeline output. Goal: catch algorithmic bugs (>5% errors, axis-flips, off-by-one slice selection).
- **AUBMC validation set (gold standard, scheduled per master plan)**: 20–30 case subset measured by a radiologist. Targets: ICC ≥ 0.75 for canal AP, Cobb angle MAE ≤ 5°.
- **Distribution sanity checks**: once measurements run on all 1,255 Duke cases, aggregate per-level means and SDs and compare to published normative literature (Thelen 2019 SHIP, Ulbrich 2014). Confirms population distribution is in the right ballpark.

This axis is about the algorithm being computationally correct. Done by comparing two sets of *numbers*.

### Interpretation validation — do the flags make clinical sense?

This answers: when the pipeline flags "stenosis" or "myelopathy," is that clinically meaningful? Done by comparing pipeline flags to ground-truth clinical labels.

Duke does not provide pathology labels, so interpretation validation comes entirely from the AUBMC subset where the radiologist provides both measurements AND clinical findings on the same cases.

This is the axis where the **hard-thresholds vs demographic-percentile** decision lives.

### Hard thresholds vs demographic-aware percentiles — both, reported together

Hard thresholds are the textbook clinical approach — canal AP < 10 mm = critically narrow, Torg-Pavlov < 0.8 = stenosis suspected, etc. The AUBMC PDF provides these. They come from decades of clinical consensus, are simple, and serve as first-pass flagging.

But hard thresholds ignore patient context. An 11 mm canal at age 25 is below normal for that age. The same 11 mm at age 80 is near the population average because the cervical canal narrows with aging. A 14 mm canal in a tall man may be small for his body size; the same 14 mm in a small woman is generous. Hard thresholds miss this nuance entirely.

Demographic percentile comparison adds the missing context. Output: *"Canal AP 11.2 mm = 12th percentile for 55-year-old males."*

Best practice and what the pipeline will deliver: report **both**. The radiologist sees:

> *"Canal AP at C5: 11.2 mm — within relatively-narrow hard threshold (10–13 mm); 12th percentile for 55yo M — borderline low."*

This is strictly more informative than either signal alone.

### How demographic percentiles work technically — quantile regression on Duke

For each measurement we want demographic-aware (canal AP, VB AP per level, VB heights per level, possibly disc heights), the workflow:

1. **Training data**: run the pipeline on the 1,255 Duke cases. Each yields measurements + demographics (age, sex, possibly race from `Clinical_manifest_RSNA_20250321.tsv`).
2. **Train one quantile regression model per measurement**, conditional on age + sex. The model returns conditional quantiles `{5%, 10%, 25%, 50%, 75%, 90%, 95%}` of that measurement at any (age, sex) input.
3. **At inference time**, given a new patient (age 55 M, canal AP 11.2 mm), query the trained model with that patient's age and sex, find where 11.2 mm falls in the conditional quantile distribution, output the percentile rank, and flag if extreme (< 10th or > 90th).

Quantile regression is the standard statistical approach for clinical normative curves. Thelen 2019 SHIP uses it for cervical canal/VB across age and sex; pediatric height/weight WHO curves use it; canal-narrowing-with-age studies use it.

Open implementation questions for Group 6.4:

- One quantile regression model per measurement (cleaner, more flexible) vs a multi-output model with shared embedding (simpler training, possibly worse per-measurement) — start with one-per-measurement, optimize later if performance becomes a constraint.
- Library choice: `statsmodels.QuantReg`, `sklearn.linear_model.QuantileRegressor`, or `quantile-forest` — pick once we have an actual Duke run to test on.
- Percentile flag thresholds — start with 10th / 90th cutoffs, refine after seeing the distribution and what AUBMC findings correlate with.

### What we get free (already built) vs what we build

**Cord measurements**: SCT's `sct_normalize_hc` (the `-normalize-hc` flag in the master plan) does demographic percentile comparison **for free**, using Valosek et al.'s PAM50-normalized normative database (203 healthy Spine Generic subjects, filterable by age, sex, vendor). So Group 6.4's cord-percentile branch is essentially "call SCT, get answer." We do not need to train cord-specific quantile regression.

**Vertebra and canal measurements**: we train these ourselves on Duke. Master plan Group 6.4 already specifies this approach: "quantile regression models (trained on Duke CSpineSeg dataset with age and sex as inputs)."

### Where this fits the project timeline

This work is **after** upstream measurement components are stable, **not now**, because we need actual pipeline outputs to train quantile regression on. Sequencing:

1. Measurements stable (Roni's Group 1 vertebra, Mohammad's Groups 2 + 4 disc and alignment) — in progress now
2. Run pipeline on the 1,255 Duke cases — once measurements stable and TSS-end-to-end works
3. Train per-measurement quantile regression on those Duke outputs (Andrew, Group 6.4)
4. Validate the percentile model itself on a held-out Duke test set (the train/val/test split is committed once and never re-shuffled per CLAUDE.md medical AI rule #3)
5. Report **both** hard threshold flag and percentile flag in the final per-level structured report (Group 6.3)

This is NOT the "validation step" of the pipeline. It is part of the interpretation step. The actual accuracy-validation step is the AUBMC subset comparison plus the distribution sanity checks against literature.

### End-to-end validation pipeline by stage

The full pipeline has 5 sequential stages (Input → Segmentation → Measurements → Interpretation → Report) plus a cross-cutting clinical-validation workstream. Each has its own validation question and approach.

| Stage | Question being validated | Reference data | Method | Status |
|---|---|---|---|---|
| 1 — Input handling | Correctly parses NIfTI / DICOM, detects sagittal orientation, fails fast on bad input | Synthetic test cases | pytest unit tests | 6/6 passing (Roni) |
| 2 — Segmentation (TSS) | Vertebra / disc / cord / canal segmentation matches expert | **Duke 481 expert masks** | Dice ≥ 0.85 per master plan | Pending — needs TSS run on 481 cases |
| 3a — Vertebra & disc measurements | Group 1, 2, 4 mm-measurements are accurate | (a) AUBMC manual, (b) literature aggregate distributions | (a) ICC ≥ 0.75, (b) compare population means against Thelen 2019, Ulbrich 2014 | AUBMC pending; literature compare pending |
| 3b — Cord measurements | Group 3 cord measurements are accurate | **Spine Generic + SCT outputs** + AUBMC | Cross-validation against SCT's CSA | Spine Generic ready; AUBMC pending |
| 3c — Signal-based abnormality detection | Group 5 flags right regions (myelomalacia, fracture etc.) | AUBMC pathology cases | Sensitivity / specificity | Pending (needs AUBMC pathology cases) |
| 4a — Hard-threshold flagging | Threshold tables apply correctly to measurements | Synthetic golden cases with known severity | pytest unit tests | Build during interpretation phase |
| 4b — Percentile flagging (Group 6.4) | Demographic percentile model is reasonable | Held-out Duke test set | Quantile regression cross-validation | Pending — needs measurements stable first |
| 5 — Report generation | Report contains required fields with correct medical AI wording | (a) visual review, (b) golden output tests | Visual review on 20 Duke cases + unit tests on wording | Pending |
| Cross-cutting clinical validation | Pipeline's clinical findings match radiologist's findings on real patients | **AUBMC 20–30 case subset** with measurements + clinical labels | ICC for measurements + sensitivity/specificity for flags | Pending — depends on AUBMC delivery |

### Five concrete validation deliverables for the final submission

These are the validation artifacts the project needs to produce to satisfy the rubric (especially Q1 / Q2 testing categories) and the CLAUDE.md medical-AI hard rules.

**Output 1 — Segmentation accuracy report.** Run TSS on the 481 Duke expert-annotated cases, compute Dice per case, report mean / SD / distribution. Bland-Altman-style figure showing TSS vs Duke per-level agreement. Validates that TSS is reliable on our data. Owner: Roni.

**Output 2 — Distribution sanity check.** Run the full measurement pipeline on 1,255 Duke cases, aggregate per-vertebra and per-disc means and SDs, compare to Thelen 2019 SHIP and Ulbrich 2014 normative tables. Report shows our means vs published means per cervical level. Validates that our population-scale measurements are in the right clinical ballpark. Owner: Andrew (this is integration work).

**Output 3 — Cord cross-validation.** Run Roni's cord measurement code on a sample of Spine Generic subjects, compare to SCT's `sct_process_segmentation` cord CSA output on the same subjects. Bland-Altman plot, ICC, mean difference. Validates that cord measurements agree with the established community tool. Owner: Roni.

**Output 4 — Clinical validation report (the hard test).** AUBMC delivers 20–30 cases with both manual measurements and clinical findings. Run our pipeline on those cases. For measurements: ICC ≥ 0.75 for canal AP, Cobb MAE ≤ 5° per master plan targets. For interpretation flags: sensitivity, specificity, agreement matrix versus the radiologist's findings. ICC table + Bland-Altman + flag-agreement matrix. Validates clinical correctness — the actual gold-standard test. Owner: shared (Roni computes, Andrew assembles).

**Output 5 — End-to-end test suite.** Per CLAUDE.md rubric Q1: unit + integration + at least 1 E2E test on the deployed system. Per Q2: golden-dataset regression tests gating merges to main on core measurement code. Owner: shared / CI/CD setup task.

### Validation timeline (rough order of operations)

This is the order things have to happen end-to-end:

1. **Now**: Roni stabilizes Group 1 measurement code on a single Duke case (debugging). Manual ITK-Snap / 3D Slicer measurement is the immediate cross-check, but only for bug-catching, not formal validation.
2. **Once measurements stable**: run pipeline on full 1,255 Duke cases → produces Output 2 (distribution sanity check).
3. **In parallel**: run TSS on 481 Duke expert-annotated cases → produces Output 1 (segmentation accuracy).
4. **In parallel**: run cord measurement code on a Spine Generic subset → produces Output 3 (cord cross-validation).
5. **When AUBMC delivers** the 20–30 case subset: run pipeline on those cases → produces Output 4 (clinical validation report). This is the gold-standard validation.
6. **Throughout**: maintain Output 5 (test suite) as code is added.

---

## External Validation Data — Search Findings (2026-04-29)

This section captures the results of two parallel searches (general web + Perplexity Sonar Deep Research) for external datasets that could serve as ground-truth references when validating measurement code — particularly Ronnie's Group 1 vertebral body morphometry and spondylolisthesis components, but also the cord work in Group 3 and the demographic percentile work in Group 6.4. Both searches reached the same conclusions, so the findings reflect a real gap in the open-access landscape, not a search-strategy artifact.

### Bottom line — no plug-and-play paired dataset exists for cervical spine

There is no public source on the open web that bundles cervical sagittal T2-weighted MRI scans with explicit per-case measurements (vertebra AP width, SI height, spondylolisthesis slip in mm, canal AP, Cobb angle) in a downloadable format. Open-access cervical-spine imaging is biased toward either segmentation masks without measurements (Duke CSpineSeg, others), or population-level normative statistics without per-case images (Thelen 2019 SHIP, Ulbrich 2014, others). Nothing combines both.

This finding is consistent with what the master plan already anticipated — that clinical measurement validation will have to come from the AUBMC radiologist on a 20–30 case subset, not from a pre-existing public dataset.

### Spine Generic Protocol — investigated in depth, partial value

The Spine Generic Protocol is a multi-center, multi-vendor quantitative MRI initiative covering 260 healthy subjects scanned across 42 centers (GE, Philips, Siemens), plus a single-subject sub-dataset of one healthy 38-year-old scanned across 19 centers. Inter-site coefficient of variation under 5% on the metrics they report. Open-access, BIDS-organized, NIfTI format, distributed via git-annex with a permissive license requiring only attribution.

**Documentation:** https://spine-generic.readthedocs.io
**Multi-subject GitHub:** https://github.com/spine-generic/data-multi-subject
**Single-subject GitHub:** https://github.com/spine-generic/data-single-subject
**Zenodo deposit:** https://zenodo.org/records/4299140

#### What Spine Generic does NOT provide for our purposes

The dataset is fundamentally a **raw imaging repository with analysis code**, not a pre-computed measurement database. Concretely:

- **No per-subject vertebral body morphometry** (no AP width, SI height, or vertebra dimension CSV files)
- **No per-subject canal measurements** (no canal AP, dural sac, or canal area files)
- **No per-subject angles** (no Cobb, segmental angles, or lordosis classification)
- **No per-subject spondylolisthesis** measurements

In other words, **Spine Generic does NOT solve Ronnie's Group 1 validation problem.** Downloading Spine Generic does not give you a CSV listing "C5 AP width = 19.0 mm for subject sub-amu01" to compare against the Genant 6-point pipeline output.

#### What Spine Generic DOES provide

The 260 subjects include 3D sagittal T2-weighted MRI sequences usable as raw input to our pipeline (along with T1, T2*, DWI, MT contrasts). The standard SCT analysis pipeline, when run on the dataset, computes spinal-cord-specific outputs:

- Spinal cord cross-sectional area (CSA) from both T1 and T2, averaged C2–C3
- Gray matter CSA at C3–C4 (from T2* multi-echo gradient echo)
- Fractional anisotropy in white matter (DWI, averaged C2–C5)
- Magnetization transfer ratio in white matter (MT, averaged C2–C5)
- MTSat and T1 mapping (advanced microstructural metrics)

These are useful for **Ronnie's Group 3 (cord) work** — particularly when validating cord CSA computations against an external multi-site reference. They are not useful for Group 1 vertebra validation.

#### A free derivative database useful for Group 6.4 (demographic percentiles)

A separate research output by Valosek et al., the **PAM50-normalized normative metrics database** at https://github.com/sct-pipeline/normative-metrics, provides pre-computed morphometric measurements for 203 of the 260 Spine Generic subjects: cross-sectional area, AP diameter, transverse diameter, compression ratio, eccentricity, and solidity — saved as CSV in template space, supporting filtering by sex, age, and MRI vendor. SCT's `sct_normalize_hc` (the `-normalize-hc` flag mentioned in the master plan) is built on top of this database.

This means **for Group 6.4 cord-percentile comparison, we get the percentile distributions for free** — no need to train our own quantile regression on cord measurements. For vertebra and canal percentiles, the Duke-built quantile regression plan in the master plan still stands; this database does not cover those.

### Implications for the team

**For Ronnie (Group 1 vertebra-measurement validation).** Spine Generic does not help. The realistic path remains:
1. Manual measurement on Duke cases using ITK-Snap or 3D Slicer (~30 min per case, free tools, real per-case ground truth)
2. The planned AUBMC radiologist 20–30 case subset (true gold standard, scheduled per master plan)
3. Distribution-level sanity checks against published normative literature (Thelen 2019, Ulbrich 2014)

**For Ronnie (Group 3 cord work).** Spine Generic *is* useful. The 260-subject dataset, processed with SCT, generates cord CSA references that match what Ronnie's cord measurement code should produce. The Valosek normative-metrics derivative provides pre-computed cord morphometry for 203 subjects in template space — directly usable as a reference distribution.

**For Andrew (Group 6.4 demographic percentiles).** SCT's `-normalize-hc` flag (powered by the Valosek database) provides cord percentiles for free. We do not need to build cord-specific quantile regression on Duke. For vertebra and canal percentiles, the original Duke-quantile-regression plan in the master plan stands — this resource does not cover those structures.

### Sources

- [Spine Generic documentation](https://spine-generic.readthedocs.io)
- [Spine Generic multi-subject GitHub](https://github.com/spine-generic/data-multi-subject)
- [Spine Generic single-subject GitHub](https://github.com/spine-generic/data-single-subject)
- [Spine Generic Zenodo deposit](https://zenodo.org/records/4299140)
- [PAM50-normalized normative metrics database (Valosek et al.)](https://github.com/sct-pipeline/normative-metrics)
- [Cohen-Adad 2021 Spine Generic paper, Sci Data](https://www.nature.com/articles/s41597-021-00941-8)
- [Duke CSpineSeg (Zhou 2025, Sci Data)](https://www.nature.com/articles/s41597-025-05975-w)
- [Thelen 2019 SHIP cervical normative reference values, PLOS One](https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0222682)
- [Ulbrich 2014 normative MR cervical canal dimensions, RSNA Radiology](https://pubs.rsna.org/doi/abs/10.1148/radiol.13120370)
- [ITK-Snap (free measurement tool)](http://www.itksnap.org/)
- [3D Slicer (free measurement tool)](https://www.slicer.org/)

---

## Session notes

(Append by date. Don't delete old notes.)

- 2026-04-22 — Andrew: file created. Beginning lit review for 5.1 (Weber 2023) and 6.4 (quantile regression on Duke).
- 2026-04-29 — Andrew: dataset search using WebSearch + Perplexity Sonar Deep Research. Confirmed no public dataset bundles cervical MRI with per-case measurements. Spine Generic Protocol does not solve Group 1 validation but does help Group 3 (cord) and Group 6.4 (cord percentiles via Valosek normative-metrics derivative). Recommendation for Ronnie: manual ITK-Snap measurement on a Duke case as immediate validation step.
