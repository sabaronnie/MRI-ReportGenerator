# Per-Group Validation Status (living) — 2026-06-08

Single source of truth for where each measurement group stands. Bar for "validated":
healthy reads the normal range **and** pathology crosses into abnormal (threshold-crossing /
distribution-separation; no per-case radiologist GT exists). Cohort: 12 healthy Spine-Generic vs
10 (now scaling to 50) MMCSD symptomatic spondylosis. Detail: `results-full-2026-06-08.md`, journal J1–J17.

## Summary table
| Group | Component | Healthy side | Pathology side | Verdict |
|---|---|---|---|---|
| **G3** | canal AP / SAC / cord (SCT) | normal-side, 0% over-flag | crosses: canal **p=0.0001**, SAC **p=0.0001**, cord p=0.009 | ✅ **VALIDATED (strong)** |
| **G4** | Cobb **C1** (SPINEPS endplate) | +15.2° lordotic = literature | directional now (p=0.13) but **d=0.91 LARGE** -> underpowered | ⚠️ **method-validated; needs ~19/group (SPINEPS on more MMCSD) -> expected p<0.05** |
| **G1** | Ha/Hp compression screen (our 5.2) | 0% FP on 12 healthy | correctly NULL on spondylosis (true neg) | ✅ **validated as screen**; compression-fracture arm UNTESTED (no dataset) |
| **G5.1** | myelomalacia (SCIseg) | ~91% healthy specificity | sensitivity from SCIseg paper; MMCSD arm not run | ✅ **healthy-validated**; unhealthy arm pending |
| **G5.2** | fracture/compression | = G1 (17%→0% FP) | RSNA negative (non-compression); same gap as G1 | ✅ **validated as screen** |
| **G2** | disc DHI / bulge / signal | over-flagged (now fixed for DHI) | does NOT discriminate | ❌ **NOT validated — in active remediation** |
| **G4** | Cobb canal-cut; segmental; post-tangent | sign fixed | noisy / no norm | ⚠️ superseded by C1 / not validated |
| **G1** | morphometry heights + slip (SERVICE) | Ha/Hp backwards (corner method) | — | ❌ **service port not done** (our endplate method works; not ported) |
| **G6** | interpretation catalog | thresholds cited | n/a | 🔧 **built + unit-tested, NOT end-to-end run** |

## Per-group detail

### G3 — VALIDATED (the headline)
Canal AP min 11.7→8.6 mm and SAC min 4.7→2.3 mm both separate at p=0.0001; cord thinner (p=0.009).
Open: validate on a *random* MMCSD draw (current 10 lesion-selected); older clinical "normal" may sit tighter.

### G4 — method-validated, discrimination directional
SPINEPS endplate-voxel C1 reads correct lordosis (healthy +15.2°, matches F1000 15.4°) and is far cleaner
than canal-cut. Healthy vs unhealthy is directional (+15 vs +9) but p=0.13 (alignment is less specific for
CSM; small n). Open: plumb SPINEPS into the production context so c3c7 prefers C1.

### G1 — compression screen validated; service heights/slip NOT
Our Ha/Hp screen (canal-cut + endplate-line): 0% healthy FP, correctly silent on the non-compression
spondylosis cohort. The **compression-fracture abnormal arm is untested** — spondylosis doesn't exercise
it and no labeled cervical compression-fracture MRI exists (documented gap). The **service** morphometry
still uses the old corner method (Ha/Hp backwards); porting our endplate-line method in is open. Slip is
experimental (no supine-MRI threshold). AP width/tilt are quality metrics (tilt over-flags at 20°).

### G5 — screens healthy-validated
5.2 compression (17%→0% FP) and 5.1 myelomalacia (~91% healthy specificity) validated on healthy. 5.1 was
NOT run on the MMCSD unhealthy cohort this pass (open). 5.3 tumor scoped out, 5.4 scar deferred (needs gadolinium).

### G2 — NOT validated; in active remediation (current work)
DHI + bulge read backwards (healthy worse than pathology) = real bug. Root cause: cross-dataset
calibration (healthy/unhealthy from different scanners) confounds the height-ratio and signal metrics;
physical dimensions (G3 mm) are immune, which is why G3 validated and G2 doesn't. Done so far: a cited
relative reduced-height flag cut false-firing 77%→3% (additive, safe), but disc height doesn't
discriminate this cohort (3% vs 2%). Signal axis: tried, also flat + a calibration bug (healthy discs
mis-grade 4) traced to resampling the raw onto the mask grid. **In progress:** native-grayscale signal +
**within-MMCSD per-level validation** (lesion vs non-lesion discs, same scanner — confound-free), scaling
to ~50 MMCSD cases for statistical power (pilot d≈0.48 → need ~70 discs/group).

### G6 — built, not end-to-end run
Catalog + classify + interpretation engine unit-tested. Threshold corrections identified (dural-sac/SAC/Torg
over-flag on MRI; 1.35 mm bulge unverified; van Santbrink offset inverted). End-to-end run gated on the
measurement validation above.

## Local validations done while the 50-case batch segments (2026-06-08, journal J19-J21)
All on masks already on disk (12 healthy Spine-Generic, C3-C7, both 0.8 mm and 4 mm). Script:
`research/group5/run_g1_local_validations.py` (proto), results `g1_local_validation_results.json`.

- **G1 tilt recalibration:** healthy tilt = median 27.0°, mean 27.8 ± 6.9° (p99 42.5°, max 43.5°). Current
  `TILT_DEG_MAX = 20°` over-flags **83% of healthy vertebrae** (50/60). **ACTION: raise to ~45°** (mean+2.5SD,
  0% healthy false-flag). Quality/sanity flag, not a disease detector. → `cervical_body_morphometry.py:67`.
- **G1 AP depth + height precision:** AP depth 18.9 ± 2.2 mm (CV 9-14%, tight); ~2 mm above the 15-17 mm CT
  norm (T2-MRI + max-extent offset, expected). Ha/Hp 0.94 ± 0.13, caudal trend C3 0.86 → C7 1.00 (reproduces
  the cohort norm — consistency check, same cohort). Sizes sane; no fix needed.
- **Resolution robustness (0.8 vs 4 mm):** AP depth |Δ| 0.81 mm bias −0.15 mm (**robust**); Ha/Hp bias −0.009
  group-level (**robust for the mean**, ~0.14 per-body scatter); canal-cut Cobb |Δ| 15.6° (**NOT robust** —
  third argument for the SPINEPS C1 method over canal-cut). mm metrics immune as predicted.

## One-line state
G3 validated; G4 method-validated/directional; G1+G5 screens healthy-validated (compression arm gap);
G2 not validated (active remediation, 50-case within-MMCSD run); G6 built, pending. Local: G1 tilt cut
recalibrate 20°→~45° (over-flagged 83% healthy); AP depth + Ha/Hp precision confirmed; mm metrics
resolution-robust, canal-cut Cobb is not.
