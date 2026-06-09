from __future__ import annotations

import pytest

from services.reporting import build_report_document


def test_build_report_document_consumes_reporting_contract():
    payload = {
        "contract_version": "1.0",
        "case": {
            "job_id": "scan_123",
            "case_id": "scan_123",
            "submitted_at": "2026-06-07T14:10:00Z",
            "patient_context": {"sex": "male", "age_years": 42, "height_cm": 178},
            "source_file": {"filename": "scan.nii.gz"},
        },
        "manifest": {"seg_shape": [25, 60, 50]},
        "components": {
            "lordosis_classification": {
                "status": "ok",
                "duration_s": 0.001,
                "metadata": {
                    "lordosis_classification": {"C3-C7": "straightened / low lordosis"},
                },
            }
        },
        "measurements": {
            "SAC": {"C5": 2.7},
            "Cobb_C3_C7": {"C3-C7": -2.0},
        },
        "flags": {
            "sac_high_risk": {"C5": True},
            "sac_slice_misaligned": {"C5": True},
        },
        "assessements": {
            "measurements": [
                {
                    "measurement": "SAC",
                    "level": "C5",
                    "value": 2.7,
                    "unit": "mm",
                    "status": "outside_reference",
                    "severity": "high_risk",
                    "flag": True,
                    "demographics_used": {},
                    "quality_flags": ["sac_slice_misaligned"],
                    "caveat": "Derived metric; confirm with segmentation QC.",
                }
            ],
            "syndromes": [
                {
                    "syndrome": "possible_myelopathy",
                    "level": "C5",
                    "status": "review_only",
                    "advisory": "pattern consistent with possible cervical myelopathy; clinical correlation required",
                    "contributing": ["dural_sac_AP_min", "SAC", "myelomalacia"],
                    "provisional": True,
                    "caveat": "Provisional combination rule; advisory only, never diagnostic.",
                }
            ],
        },
        "report_context": {
            "modality": "cervical_sagittal_mri",
            "report_language": "en",
            "disclaimers": ["This is a research tool, not a medical device. Not for clinical diagnosis."],
            "include_appendix": True,
        },
    }

    document = build_report_document(payload)

    assert document["report_version"] == "1.0"
    assert document["source_contract_version"] == "1.0"
    assert document["case"]["job_id"] == "scan_123"
    assert document["case_header"]["source_filename"] == "scan.nii.gz"
    assert document["case_header"]["patient_summary"] == "Male, 42 years, 178 cm"
    assert document["clinical_report"]["exam"] == "MRI cervical spine"
    assert document["clinical_report"]["findings_sections"][0]["heading"] == "Alignment"
    assert "straightened / low lordosis" in document["clinical_report"]["findings_sections"][0]["body"]
    assert document["clinical_report"]["findings_sections"][1]["heading"] == "Level-Specific Findings"
    assert "At C5" in document["clinical_report"]["findings_sections"][1]["body"]
    assert document["summary"]["measurement_row_count"] == 1
    assert document["summary"]["flagged_measurement_count"] == 1
    assert document["summary"]["syndrome_count"] == 1
    assert document["findings"]["table_rows"][0]["display_name"] == "space available for the cord (canal AP - cord AP)"
    assert document["findings"]["highlighted_measurements"][0]["measurement"] == "SAC"
    assert document["impression"][0] == (
        "C5: pattern consistent with possible cervical myelopathy; clinical correlation required"
    )
    assert document["impression"][1] == "C5: space available for the cord (canal AP - cord AP) 2.7 mm (high_risk)."
    assert document["impression"][2] == "Alignment: straightened / low lordosis; C3-C7 Cobb angle -2.0 deg."
    assert document["quality_notes"][0]["type"] == "measurement_quality"
    assert document["quality_caveats"]["measurement_notes"][0]["measurement"] == "SAC"
    assert document["quality_caveats"]["general_caveats"][0] == "Derived metric; confirm with segmentation QC."
    assert document["disclaimers"] == payload["report_context"]["disclaimers"]
    assert document["appendix"]["raw_data"]["measurements"] == payload["measurements"]
    assert document["appendix"]["provenance"][0]["measurement"] == "SAC"
    assert "Fehlings" in document["appendix"]["provenance"][0]["citation"]


def test_build_report_document_requires_contract_keys():
    with pytest.raises(ValueError, match="missing required top-level keys"):
        build_report_document({"contract_version": "1.0"})
