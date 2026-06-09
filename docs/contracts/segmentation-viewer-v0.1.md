# Segmentation Viewer Contract v0.1 — NiiVue (frontend #2)

> What the science track hands the browser so the NiiVue WebGL viewer can overlay the
> segmentation on the MRI. Companion to [`data-contract-v0.1.md`](data-contract-v0.1.md).
> Status legend identical (🟢 FROZEN / 🟡 LIKELY / ⚪ PROPOSED).

## 1. 🟢 Files & formats
All volumes are **NIfTI `.nii.gz`** (NiiVue loads these natively). Per case there are up to three masks
plus the base image, each on a known grid:

| artifact | producer | content | NiiVue role |
|---|---|---|---|
| base T2 volume | input / `input_iso` | grayscale MRI (sagittal T2) | background layer |
| **TSS step2 mask** | TotalSpineSeg (`--iso`) | multi-label: vertebrae + discs (+ canal/cord region) | primary colored overlay |
| SCT canal mask | Spinal Cord Toolbox `sc_canal_t2` | **binary** dural-sac/canal | optional G3 overlay |
| SCT cord mask | Spinal Cord Toolbox `spinalcord` | **binary** spinal cord | optional G3 overlay |

- The measurement service forces a **1 mm isotropic** grid; the base + TSS mask are index-aligned on
  that grid (canonical **RAS**). The SCT masks are produced from the raw/iso image and share its grid.
- `affine` / voxel spacing 🟢 travel inside each `.nii.gz` header — NiiVue reads them; the frontend does
  not need a side-channel affine. (If a `/meta` endpoint wants them, expose `header.get_zooms()` and the
  4×4 affine as JSON 🟡.)

## 2. 🟢 TSS step2 label → name map (primary overlay)
Cervical labels we use (full TSS atlas is larger; these are the cervical subset):

```json
{
  "11": "C1", "12": "C2", "13": "C3", "14": "C4", "15": "C5", "16": "C6", "17": "C7", "21": "T1",
  "63": "C2-C3", "64": "C3-C4", "65": "C4-C5", "66": "C5-C6", "67": "C6-C7", "71": "C7-T1"
}
```
- Vertebra (11–21) and disc (63–71) labels are **unambiguous** 🟢. Note `C7-T1` disc = **71** (verified;
  NOT 68). We report/measure **C3–C7** (C1/C2 excluded); the viewer may still display C1/C2/T1 for context.

### ⚠️ The canal/cord (label 1 vs 2) ambiguity — read this
Inside the TSS step2 mask there are also labels **1** and **2** for the canal/cord region. There is a
**known 1↔2 naming discrepancy**: our validated measurement code treats **label 2 = canal**
(`fracture_screen._CANAL_LABEL = 2`, the canal-cut body isolation), while an older colab overlay map
(`colab/02_run_totalspineseg_colab.py` `LABEL_NAMES`) lists `1:"Canal", 2:"Cord"` — i.e. **swapped**.
**Recommendation:** do NOT drive the canal/cord overlay from TSS labels 1/2. Render the cord and canal
from the **dedicated SCT binary masks** (unambiguous, and they're what G3 actually measures). If you must
color 1/2 from the TSS mask, treat **2 as canal** (matches the measurements) and confirm visually. 🟡 until
we reconcile the overlay map in code.

## 3. 🟡 Suggested colors (frontend may override)
NiiVue takes a label→RGBA colormap. Proposal (vertebrae warm, discs cool, cord/canal distinct):
```json
{
  "vertebrae_C3_C7": "#E8A33D (amber)", "vertebrae_other": "#C7C7C7 (grey, context)",
  "discs": "#4F9DDE (blue)", "cord": "#E5484D (red)", "canal": "#30A46C (green, ~40% alpha)"
}
```
Per-label RGBA table can be generated on request; colors are a UI choice, not science. 🟡

## 4. ⚪ How it's served (PROPOSED — EEP owns the endpoints)
The science side produces the `.nii.gz` files; the EEP decides delivery. Proposal:
- `GET /cases/{id}/volume` → the base T2 `.nii.gz` (bytes, `application/gzip`) or a signed URL.
- `GET /cases/{id}/mask?type=tss|sct_canal|sct_cord` → the requested mask `.nii.gz`.
- `GET /cases/{id}/labels` → the label→name (+ optional color) map JSON from §2/§3.
- Large volumes → prefer a **signed URL** (S3) over streaming through the API. 🟡
- Auth/expiry on signed URLs per the infra track.

## 5. Notes
- No PHI: masks/volumes are de-identified; filenames use opaque case ids, not patient identifiers.
- For mock fixtures, the science track can provide one de-identified Spine-Generic healthy volume + its
  TSS mask on request (open CC dataset; numbers-only JSON already in `samples/`). Flag if/when you want the
  binary NIfTI pair committed (it's gitignored data — likely delivered via Drive/S3, not git).
