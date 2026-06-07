# Post-Interpretation Handoff Contract

This document defines the JSON payload passed from the end of the interpretation
stage into the reporting stage.

Purpose:

- keep the interpretation-to-reporting boundary stable
- ensure reporting has the full structured evidence it needs
- avoid coupling reporting to measurement-component internals

This is the contract the EEP should assemble once segmentation, measurements, and
interpretation have completed for one case.

## Design rules

- Reporting must receive both interpreted rows and the underlying structured data.
- Reporting must not depend on ad hoc prose generated upstream.
- Citations remain centralized in `thresholds.py`; the handoff carries measurement
  keys so reporting can resolve provenance by key.
- The contract should support both current behavior and near-term additions such as
  syndrome summaries and rendered artifacts.

## Required top-level shape

```json
{
  "contract_version": "1.0",
  "case": {},
  "manifest": {},
  "components": {},
  "measurements": {},
  "flags": {},
  "interpretations": {
    "measurements": [],
    "syndromes": []
  },
  "report_context": {}
}
```

## Field definitions

### `contract_version`

String version for the interpretation-to-reporting contract.

Current value:

```json
"1.0"
```

### `case`

Case and patient-context metadata required for report headers, demographic-aware
display, and job traceability.

Required fields:

```json
{
  "job_id": "scan_8f3a2c1d",
  "case_id": "scan_8f3a2c1d",
  "submitted_at": "2026-06-07T14:10:00Z",
  "patient_context": {
    "sex": "male",
    "age_years": 42,
    "height_cm": 178
  },
  "source_file": {
    "filename": "scan.nii.gz"
  }
}
```

Notes:

- `job_id` and `case_id` may be the same in v1.
- `patient_context` should be preserved even if some interpretation rules do not
  yet use demographics.

### `manifest`

Case-level technical metadata for appendices, QA, and reproducibility.

Recommended fields:

```json
{
  "seg_shape": [25, 60, 50],
  "voxel_spacing_mm": [1.0, 1.0, 1.0],
  "labels_present": [13, 14, 15, 16, 17, 63, 64, 65, 66, 67]
}
```

This should be the same manifest already returned by the measurements service.

### `components`

Per-component execution metadata from the measurement pipeline.

Shape:

```json
{
  "cervical_body_morphometry": {
    "status": "ok",
    "duration_s": 0.012,
    "metadata": {
      "levels": ["C3", "C4", "C5", "C6", "C7"]
    }
  }
}
```

Why reporting needs it:

- method caveats
- derived labels that currently live in metadata
- QA / appendix detail

Important current example:

- `lordosis_classification` is currently emitted via component metadata, not as a
  standalone interpretation row.

### `measurements`

Raw structured measurement outputs grouped by measurement key.

Shape:

```json
{
  "AP_width": {"C3": 19.0, "C4": 19.5},
  "dural_sac_AP_min": {"C5": 9.8},
  "SAC": {"C5": 2.7},
  "Cobb_C3_C7": {"C3-C7": -2.0}
}
```

Why reporting needs it:

- findings tables
- appendix values
- figure annotation labels
- explicit traceability from prose back to source values

### `flags`

Raw pathology and quality flags emitted by the measurement components.

Shape:

```json
{
  "sac_high_risk": {"C5": true},
  "sac_slice_misaligned": {"C5": true},
  "tilt_outlier": {"C4": true}
}
```

Why reporting needs it:

- QC callouts
- caution sections
- preserving non-interpreted but still important technical warnings

### `interpretations`

Normalized interpretation-stage output.

Required shape:

```json
{
  "measurements": [],
  "syndromes": []
}
```

#### `interpretations.measurements`

This is the main evidence layer from `InterpretedMeasurement`.

Row shape:

```json
{
  "measurement": "SAC",
  "level": "C5",
  "value": 2.7,
  "unit": "mm",
  "status": "outside_reference",
  "severity": "high_risk",
  "flag": true,
  "demographics_used": {},
  "quality_flags": ["sac_slice_misaligned"],
  "caveat": "Derived metric; confirm with segmentation QC."
}
```

Reporting uses these rows to:

- decide what should surface in findings
- build severity tags
- attach method caveats
- decide which values are normal, borderline, review-only, or not interpretable

#### `interpretations.syndromes`

Advisory higher-level patterns derived from interpreted rows.

Shape:

```json
[
  {
    "syndrome": "possible_myelopathy",
    "level": "C5",
    "status": "review_only",
    "advisory": "pattern consistent with possible cervical myelopathy; clinical correlation required",
    "contributing": ["dural_sac_AP_min", "SAC", "myelomalacia"],
    "provisional": true,
    "caveat": "Provisional combination rule; advisory only, never diagnostic."
  }
]
```

Notes:

- `syndromes` should be present even if empty.
- Reporting should treat these as advisory summary candidates, not diagnoses.

### `report_context`

Rendering and policy context for the reporting layer.

Required fields:

```json
{
  "modality": "cervical_sagittal_mri",
  "report_language": "en",
  "disclaimers": [
    "This is a research tool, not a medical device. Not for clinical diagnosis.",
    "Measurements acquired on supine MRI; functional radiographs may differ."
  ],
  "include_appendix": true
}
```

Why this belongs here:

- keeps reporting deterministic
- avoids hard-coding policy text in the renderer

## Full example

```json
{
  "contract_version": "1.0",
  "case": {
    "job_id": "scan_8f3a2c1d",
    "case_id": "scan_8f3a2c1d",
    "submitted_at": "2026-06-07T14:10:00Z",
    "patient_context": {
      "sex": "male",
      "age_years": 42,
      "height_cm": 178
    },
    "source_file": {
      "filename": "scan.nii.gz"
    }
  },
  "manifest": {
    "seg_shape": [25, 60, 50],
    "voxel_spacing_mm": [1.0, 1.0, 1.0],
    "labels_present": [13, 14, 15, 16, 17, 63, 64, 65, 66, 67]
  },
  "components": {
    "cervical_body_morphometry": {
      "status": "ok",
      "duration_s": 0.012,
      "metadata": {
        "levels": ["C3", "C4", "C5", "C6", "C7"]
      }
    },
    "lordosis_classification": {
      "status": "ok",
      "duration_s": 0.002,
      "metadata": {
        "lordosis_classification": {
          "C3-C7": "straightened / low lordosis"
        }
      }
    }
  },
  "measurements": {
    "AP_width": {
      "C3": 19.0,
      "C4": 19.5
    },
    "dural_sac_AP_min": {
      "C5": 9.8
    },
    "cord_AP": {
      "C5": 7.1
    },
    "SAC": {
      "C5": 2.7
    },
    "Cobb_C3_C7": {
      "C3-C7": -2.0
    }
  },
  "flags": {
    "sac_high_risk": {
      "C5": true
    },
    "sac_slice_misaligned": {
      "C5": true
    }
  },
  "interpretations": {
    "measurements": [
      {
        "measurement": "dural_sac_AP_min",
        "level": "C5",
        "value": 9.8,
        "unit": "mm",
        "status": "outside_reference",
        "severity": "stenosis_provisional",
        "flag": true,
        "demographics_used": {},
        "quality_flags": [],
        "caveat": "Measures SOFT-TISSUE dural-sac AP via SCT, NOT the osseous canal."
      },
      {
        "measurement": "SAC",
        "level": "C5",
        "value": 2.7,
        "unit": "mm",
        "status": "outside_reference",
        "severity": "high_risk",
        "flag": true,
        "demographics_used": {},
        "quality_flags": ["sac_slice_misaligned"],
        "caveat": "Derived metric; confirm with segmentation QC."
      }
    ],
    "syndromes": [
      {
        "syndrome": "possible_myelopathy",
        "level": "C5",
        "status": "review_only",
        "advisory": "pattern consistent with possible cervical myelopathy; clinical correlation required",
        "contributing": ["dural_sac_AP_min", "SAC", "myelomalacia"],
        "provisional": true,
        "caveat": "Provisional combination rule; advisory only, never diagnostic."
      }
    ]
  },
  "report_context": {
    "modality": "cervical_sagittal_mri",
    "report_language": "en",
    "disclaimers": [
      "This is a research tool, not a medical device. Not for clinical diagnosis.",
      "Measurements acquired on supine MRI; functional radiographs may differ."
    ],
    "include_appendix": true
  }
}
```

## Minimum implementation changes implied by this contract

- Keep returning `components`, `measurements`, `flags`, and `manifest`.
- Ensure `interpretations.syndromes` is present, even when empty.
- Add `case` and `report_context` in the EEP before calling reporting.
- Keep report generation downstream of this contract rather than re-deriving from raw
  component internals.

## What reporting should derive from this payload

Reporting should derive, not require as input:

- per-level findings table
- overall impression bullets
- appendix sections
- report-ready HTML / PDF / DOCX

That keeps the boundary clean:

- interpretation decides what the values mean
- reporting decides how to present that meaning
