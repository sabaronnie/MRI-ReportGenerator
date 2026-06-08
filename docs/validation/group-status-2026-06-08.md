# Per-Group Validation Status (living) — 2026-06-08

Single source of truth for where each measurement group stands. Bar for "validated":
healthy reads the normal range **and** pathology crosses into abnormal (threshold-crossing /
distribution-separation; no per-case radiologist GT exists). Cohort: 12 healthy Spine-Generic vs
10 (now scaling to 50) MMCSD symptomatic spondylosis. Detail: `results-full-2026-06-08.md`, journal J1–J17.

## Summary table
| Group | Component | Healthy side | Pathology side | Verdict |
|---|---|---|---|---|
| **G3** | canal AP / SAC / cord (SCT) | normal-side, 0% over-flag | crosses: canal **p=0.0001**, SAC **p=0.0001**, cord p=0.009 | ✅ **VALIDATED (strong)** |
| **G4** | Cobb **C1** (SPINEPS endplate) | +15.2° lordotic = literature | 11 healthy vs **41** unhealthy: 15.2° vs 8.3°, d=0.76, AUC 0.68; **two-sided p=0.070 / one-sided p=0.035** | ⚠️ **directional/borderline — NOT validated 2-sided; bottleneck = healthy n=11, needs ~10-18 more healthy controls** |
| **G1** | Ha/Hp compression screen (our 5.2) | 0% FP on 12 healthy | correctly NULL on spondylosis (true neg) | ✅ **validated as screen**; compression-fracture arm UNTESTED (no dataset) |
| **G5.1** | myelomalacia (SCIseg) | ~91% healthy specificity | sensitivity from SCIseg paper; MMCSD arm not run | ✅ **healthy-validated**; unhealthy arm pending |
| **G5.2** | fracture/compression | = G1 (17%→0% FP) | RSNA negative (non-compression); same gap as G1 | ✅ **validated as screen** |
| **G2** | disc DHI / bulge / signal | over-flag fixed (J22) | within-MMCSD: signal DEAD; **disc/VB AP ratio + AP width discriminate** (AUC ~0.62, level-controlled) | ⚠️ **partial — geometric disc-spread validated; signal/bulge negative** |
| **G4** | Cobb canal-cut; segmental; post-tangent | sign fixed | noisy / no norm | ⚠️ superseded by C1 / not validated |
| **G1** | morphometry heights + slip (SERVICE) | Ha/Hp backwards (corner method) | — | ❌ **service port not done** (our endplate method works; not ported) |
| **G6** | interpretation catalog | thresholds cited | n/a | 🔧 **built + unit-tested, NOT end-to-end run** |

## Per-group detail

### G3 — VALIDATED (the headline)
Canal AP min 11.7→8.6 mm and SAC min 4.7→2.3 mm both separate at p=0.0001; cord thinner (p=0.009).
Open: validate on a *random* MMCSD draw (current 10 lesion-selected); older clinical "normal" may sit tighter.

### G4 — directional/borderline (scaled to 41 unhealthy; J24)
SPINEPS endplate-voxel C1 reads correct lordosis (healthy +15.2°, matches F1000 15.4°). At scale (11
healthy vs 41 unhealthy): healthy 15.2° vs unhealthy 8.3°, **d=0.76, AUC 0.68**, **two-sided p=0.070**
(not significant), one-sided p=0.035 (significant under the pre-specified directional hypothesis). The
pilot d=0.91 (n=10) was optimistic; the real bottleneck is the **healthy** arm (n=11, SD ±10°) — adding
to the 41-case unhealthy arm barely moved p. Production path verified: `c3c7_cobb_angle` uses the C1
method and matches the direct computation (5/5 spot check). **To cross 2-sided p<0.05: segment ~10-18
more healthy Spine-Generic controls with SPINEPS** (≈30 available); C3-C7 stays the metric. Alignment is
biologically a weaker/less-specific CSM marker than canal stenosis — expect AUC ~0.68 even fully powered.

### G1 — compression screen validated; service heights/slip NOT
Our Ha/Hp screen (canal-cut + endplate-line): 0% healthy FP, correctly silent on the non-compression
spondylosis cohort. The **compression-fracture abnormal arm is untested** — spondylosis doesn't exercise
it and no labeled cervical compression-fracture MRI exists (documented gap). The **service** morphometry
still uses the old corner method (Ha/Hp backwards); porting our endplate-line method in is open. Slip is
experimental (no supine-MRI threshold). AP width/tilt are quality metrics (tilt over-flags at 20°).

### G5 — screens healthy-validated
5.2 compression (17%→0% FP) and 5.1 myelomalacia (~91% healthy specificity) validated on healthy. 5.1 was
NOT run on the MMCSD unhealthy cohort this pass (open). 5.3 tumor scoped out, 5.4 scar deferred (needs gadolinium).

### G2 — PARTIAL: geometric disc-spread validated; signal/bulge are negatives (J23, 49-case within-MMCSD)
Within-MMCSD lesion vs non-lesion (46/49 cases, 276 discs, 87 lesion / 189 non-lesion), **level-stratified**
to remove the confound that lesions cluster at wide mid-cervical levels:
- **Signal (nucleus/CSF, Miyazaki): DEAD** — AUC 0.50, p=0.93. Even with the correct native `tss/input`
  grayscale, disc signal does not discriminate. Clean negative; signal axis abandoned for this cohort.
- **Posterior bulge (fixed): flat** — AUC 0.50. TSS masks don't capture protrusion (segments to anatomical
  borders). Documented limitation.
- **Disc/VB AP ratio: ✅ discriminates** — AUC 0.62, p=0.0018, consistent per-level. Best G2 metric (disc
  spreads toward VB width with degeneration; normalizes for body size).
- **Disc AP width: discriminates but mostly level-confound** — raw AUC 0.79 → 0.61 stratified (p=0.0022);
  genuine ~1.5 mm within-level residual.
- **DHI: weak/correct** — AUC 0.59, p=0.015 (raw read backwards purely from the level confound).
No validated cutoff (no per-case GT) → reported as continuous separation. J22 fixes removed the
backwards/over-flag artifacts (bulge 60%→8% healthy, DHI relative flag); this run says what carries signal.

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

## Service-code fixes applied (2026-06-08, journal J22; Andrew now owns all group code)
Each run through the real 12 healthy + 10 unhealthy service contexts, kept only on evidence; all 137
service tests green. Harness: `research/group5/test_service_g1_g2.py`.

- **G1 tilt cut 20→45°** (`cervical_body_morphometry.py`) — healthy tilt-flag 88% → 0%. ✅ committed.
- **G1 heights → endplate-line fit** (`cervical_body_morphometry.py`) — healthy Ha/Hp 1.08 → 0.93
  (was backwards: anterior read taller); direction preserved (H 0.93 ≥ U 0.89). ✅ committed.
- **G2 bulge reference → endplate corners** (`disc_ap_bulge.py`) — healthy bulge 2.93 → 0.00 mm,
  over-flag 60% → 8%; no cross-dataset discrimination yet (within-MMCSD pending). ✅ committed.
- **G4 SPINEPS C1 Cobb plumbed** (`context.py` + `c3c7_cobb_angle.py`) — context carries seg-vert,
  c3c7 prefers C1 (healthy 15.2°), falls back to canal-cut; rescues C7-obscured necks. ✅ committed.

Confirmed at scale on the 49-case unhealthy batch (245 levels, 0 errors): tilt @45° **0% over-flag**,
Ha/Hp median **0.91** (physiological), compression screen **0%** — correctly null on spondylosis. The
G1 fixes generalize from n=10 to n=49.

## One-line state
G3 validated; G4 directional/borderline (2-sided p=0.070 at 11 healthy vs 41 unhealthy, healthy n is the
bottleneck); G1+G5 screens healthy-validated (compression arm gap);
G2 partial (signal/bulge negative, disc/VB AP ratio + AP width discriminate AUC ~0.62 level-controlled,
49-case within-MMCSD J23); G6 built, pending. Local: G1 tilt cut
recalibrate 20°→~45° (over-flagged 83% healthy); AP depth + Ha/Hp precision confirmed; mm metrics
resolution-robust, canal-cut Cobb is not.
