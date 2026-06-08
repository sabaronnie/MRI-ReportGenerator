from __future__ import annotations

from services.reporting import (
    build_report_document,
    render_clinical_report_html,
    render_technical_report_html,
)


def _payload() -> dict:
    return {
        "contract_version": "1.0",
        "case": {
            "job_id": "scan_123",
            "case_id": "scan_123",
            "submitted_at": "2026-06-07T14:10:00Z",
            "patient_context": {"sex": "male", "age_years": 42, "height_cm": 178},
            "source_file": {"filename": "scan.nii.gz"},
        },
        "manifest": {"seg_shape": [25, 60, 50]},
        "components": {},
        "measurements": {"SAC": {"C5": 2.7}},
        "flags": {"sac_high_risk": {"C5": True}},
        "interpretations": {
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
            "syndromes": [],
        },
        "report_context": {
            "modality": "cervical_sagittal_mri",
            "report_language": "en",
            "disclaimers": ["This is a research tool, not a medical device. Not for clinical diagnosis."],
            "include_appendix": True,
        },
    }


def test_clinical_render_excludes_technical_appendix():
    document = build_report_document(_payload())
    clinical_html = render_clinical_report_html(document)
    technical_html = render_technical_report_html(document)

    assert "Explainability Appendix" not in clinical_html
    assert "Threshold Provenance" not in clinical_html
    assert "Raw Structured Data" not in clinical_html

    assert "Explainability Appendix" in technical_html
    assert "Threshold Provenance" in technical_html
    assert "Raw Structured Data" in technical_html
