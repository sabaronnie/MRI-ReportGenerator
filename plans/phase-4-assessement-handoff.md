# Phase 4 Assessement Stage Handoff

**Created:** 2026-06-06  
**Purpose:** teammate handoff for the new pipeline stage that sits after raw measurement extraction and before final report generation.

---

## 1. What This Stage Is

This is the new **Assessement** stage of the pipeline.

Pipeline position:

`Input -> Segmentation -> Measurements -> Assessement -> Report`

What it does:
- takes the raw numeric outputs produced by the measurement pipeline
- wraps them in a standard assessement container
- prepares the system for later threshold/range logic, severity labels, and report generation

What it does **not** do yet:
- it does not contain the final literature-derived threshold engine
- it does not yet assign measurement-specific severity bands
- it does not yet generate final radiology prose

Right now, this stage is a **scaffold** whose main job is to stabilize the output schema before the full clinical rules are added.

---

## 2. Why We Added It

Before this stage, the pipeline only had:
- raw measurements
- raw flags from individual components

That was not enough for a clean report pipeline, because we need a place where the system can consistently answer:
- what was measured?
- where was it measured?
- what is the assessement status?
- should it be surfaced in findings?
- are there quality warnings?
- are there methodological caveats?

This stage gives us that layer.

The key design decision was:

- **raw measurement code stays in Phase 3**
- **clinical judgment / thresholding / labeling belongs in Phase 4**

---

## 3. Current Implementation

### Main code file

- [services/measurements/assessement.py](/Users/ronniesaba/Documents/EECE503N_Project/MRI-ReportGenerator/services/measurements/assessement.py:1)

### Where it is wired in

- [services/measurements/orchestrator.py](/Users/ronniesaba/Documents/EECE503N_Project/MRI-ReportGenerator/services/measurements/orchestrator.py:59)

The measurement service now returns a new section:

```json
"assessements": {
  "measurements": [...]
}
```

This list is built after all selected measurement components run.

### Current behavior

For every numeric measurement already present in `report["measurements"]`, the assessement layer creates a standard result record.

Current status logic is intentionally simple:

- if the measurement has a **non-quality flag** raised by its source component, it becomes:
  - `status = "outside_reference"`
  - `flag = true`

- otherwise it becomes:
  - `status = "review_only"`
  - `flag = false`

Quality-style flags are separated into `quality_flags`.

This is only a temporary Phase 4 scaffold. It is **not** the final literature-threshold logic.

---

## 4. Standard Assessement Container

The current standard record for one assessed measurement is:

```json
{
  "measurement": "SAC",
  "level": "C5",
  "value": 2.7,
  "unit": "mm",
  "status": "outside_reference",
  "severity": null,
  "flag": true,
  "demographics_used": {},
  "quality_flags": ["sac_slice_misaligned"],
  "caveat": "Derived metric; confirm with segmentation QC."
}
```

### Field meanings

`measurement`
- internal name of the measurement
- examples: `SAC`, `dural_sac_AP_min`, `Cobb_C3_C7`

`level`
- anatomical scope of the record
- examples: `C5`, `C5-C6`, `C3-C7`

`value`
- raw numeric output from the measurement stage

`unit`
- physical unit or ratio type
- examples: `mm`, `deg`, `%`, `ratio`

`status`
- the broad assessement state
- currently agreed allowed values:
  - `within_reference`
  - `outside_reference`
  - `review_only`
  - `not_assessable`

`severity`
- intentionally **not standardized yet**
- left flexible because different measurements may need different severity vocabularies later

`flag`
- boolean for whether this result should be surfaced as noteworthy in findings

`demographics_used`
- which patient demographics were actually used by the assessement rule
- currently empty because full demographic-aware rules are not implemented yet

`quality_flags`
- technical / confidence warnings
- examples: low confidence, slice mismatch, approximation, resolution issue

`caveat`
- human-readable methodology or assessement warning carried from component metadata when available

### Explicitly removed fields

We intentionally removed:
- `reference_id`
- `reference_label`

Reason:
- literature provenance will be maintained centrally in rule/threshold definitions and documentation
- we do not want every output row to duplicate citation metadata

---

## 5. Current Policy Decisions

These decisions were made during the design of this stage.

### `flag`

Policy:
- `flag = true` means the result should be surfaced as noteworthy in findings
- `flag = false` means it does not need highlighting

This is a reporting/usefulness flag, not a diagnosis.

### `status`

Policy:
- restricted to:
  - `within_reference`
  - `outside_reference`
  - `review_only`
  - `not_assessable`

Current implementation does not use all four yet, but the vocabulary is now decided.

### `severity`

Policy:
- not restricted yet
- to be revisited after measurement-specific literature review

Reason:
- different measurements may need very different label systems
- examples:
  - mild / moderate / severe
  - Grade I-V
  - binary only
  - experimental / review-only

---

## 6. How Quality Flags Are Handled

The current code auto-recognizes some flag names as quality/caution style using marker substrings:

- `low_confidence`
- `misaligned`
- `approximate`
- `resolution`
- `warning`

If a flag name matches those patterns, it is treated as a `quality_flag`.

Important caveat:
- this is only a naming-based heuristic
- it is not a final ontology
- if a component uses a quality-style flag name that does not include one of those markers, it may currently be misread as a pathology-style flag

Known example:
- `tilt_outlier` is intended by the user to behave more like a geometry / caution flag than a pathology flag, but the current scaffold may not classify it that way automatically

This will need cleanup later.

---

## 7. What Is Done vs Not Done

### Done

- Assessement stage concept established
- Standard per-measurement assessement container implemented
- Assessement output added to measurement service responses
- Reference fields intentionally removed from the container
- `status` vocabulary agreed
- `flag` meaning agreed
- Threshold/range research inventory compiled in:
  - [phase-4-threshold-research-list.txt](/Users/ronniesaba/Documents/EECE503N_Project/MRI-ReportGenerator/plans/phase-4-threshold-research-list.txt:1)

### Not done yet

- final central threshold/rule catalog
- literature-backed per-measurement normal ranges
- literature-backed severity bands
- demographic-aware threshold logic
- `not_assessable` decision rules
- syndrome-level rules
  - myelopathy indicator
  - radiculopathy indicator
- report text templates based on this layer

---

## 8. Research Work Already Prepared

We created a dedicated handoff file for literature-search work:

- [phase-4-threshold-research-list.txt](/Users/ronniesaba/Documents/EECE503N_Project/MRI-ReportGenerator/plans/phase-4-threshold-research-list.txt:1)

That file includes:
- all measurements currently implemented or planned
- which ones are core vs experimental
- exact output names where possible
- caveats that matter for threshold search
- a high-priority search checklist

That file should be used as input to a research-focused model or teammate.

---

## 9. Recommended Next Steps

### Step 1: literature collection

Use the research list to gather:
- normative ranges
- abnormal thresholds
- severity bands
- modality caveats
- demographic modifiers

Priority measurements:
- `AP_width`
- `H_anterior`, `H_middle`, `H_posterior`
- `spondy_slip_mm`
- `spondy_pct_of_lower_AP`
- `disc_AP_width`
- `DHI`
- `dural_sac_AP_min`
- `cord_AP`
- `SAC`
- `Torg-Pavlov ratio`
- `Cobb_C3_C7`
- `segmental_angle`

### Step 2: central threshold/rule catalog

Create a central rule-definition layer, likely something like:

- one registry per measurement
- includes:
  - measurement name
  - rule type
  - units
  - thresholds / label bands
  - demographic modifiers
  - caveats
  - citation provenance

This provenance should live there, not inside each assessed row.

### Step 3: replace scaffold logic

Current scaffold behavior:
- pathology flag -> `outside_reference`
- otherwise -> `review_only`

Replace this with true measurement-specific logic:
- compare value to literature-derived rule
- emit:
  - `within_reference`
  - `outside_reference`
  - `review_only`
  - `not_assessable`

### Step 4: implement `demographics_used`

Once actual rules use age / sex / height, populate:

```json
"demographics_used": {
  "age": ...,
  "sex": ...,
  "height_cm": ...
}
```

Only include fields truly used by the rule.

### Step 5: define syndrome-level rules

After per-measurement assessement is trustworthy:
- define possible myelopathy pattern rule
- define possible radiculopathy pattern rule

These should be second-pass rules over assessed measurements, not raw Phase 3 outputs.

---

## 10. Important Caveats for Anyone Continuing This Work

- Do not mix raw measurement logic into the assessement layer unless absolutely necessary.
- Do not hard-code literature citations into every output row.
- Do not assume radiograph thresholds transfer directly to supine MRI without caveat.
- Do not treat quality/caution flags as clinical pathology flags by default.
- Do not over-standardize `severity` before the literature review is done.

This stage is supposed to create **clarity and traceability**, not to force premature clinical conclusions.

---

## 11. Short Summary for a New Teammate

If you only read one paragraph:

We added a new Phase 4 assessement scaffold that wraps each raw measurement in a standard container with `measurement`, `level`, `value`, `unit`, `status`, `severity`, `flag`, `demographics_used`, `quality_flags`, and `caveat`. Right now it does not contain the real literature threshold engine yet; it mainly stabilizes the API and separates assessement from raw measurement code. The next real job is to research thresholds/ranges for every measurement, define a central rule catalog, and then replace the temporary `outside_reference` / `review_only` scaffold logic with true per-measurement assessement.
