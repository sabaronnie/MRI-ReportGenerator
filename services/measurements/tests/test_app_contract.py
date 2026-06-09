from __future__ import annotations

import io
import zipfile
from types import SimpleNamespace

from services.measurements.app import app


def _segmentation_zip_bytes() -> io.BytesIO:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("step2_output.nii.gz", b"fake")
        zf.writestr("segmentation_run_manifest.json", '{"input_metadata":{"voxel_spacing_mm":[1.0,1.0,1.0]}}')
    payload.seek(0)
    return payload


def test_measure_endpoint_returns_reporting_handoff_contract(monkeypatch):
    dummy_ctx = SimpleNamespace(manifest={"seg_shape": [25, 60, 50], "voxel_spacing_mm": [1.0, 1.0, 1.0]})
    dummy_report = {
        "components": {
            "sac": {
                "status": "ok",
                "duration_s": 0.01,
                "metadata": {"sac_caveat": "Derived metric; confirm with segmentation QC."},
            }
        },
        "measurements": {"SAC": {"C5": 2.7}},
        "flags": {"sac_high_risk": {"C5": True}},
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
                    "quality_flags": [],
                    "caveat": "Derived metric; confirm with segmentation QC.",
                }
            ],
            "syndromes": [],
        },
    }

    monkeypatch.setattr("services.measurements.app.load_context", lambda *args, **kwargs: dummy_ctx)
    monkeypatch.setattr("services.measurements.app.run_all", lambda ctx, enabled: dummy_report)

    client = app.test_client()
    response = client.post(
        "/measure",
        data={
            "file": (_segmentation_zip_bytes(), "segmentation.zip"),
            "job_id": "scan_test_1",
            "sex": "female",
            "age_years": "37",
            "height_cm": "165",
            "report_language": "en",
            "include_appendix": "false",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["contract_version"] == "1.0"
    assert payload["case"]["job_id"] == "scan_test_1"
    assert payload["case"]["patient_context"] == {
        "sex": "female",
        "age_years": 37,
        "height_cm": 165.0,
    }
    assert payload["manifest"] == dummy_ctx.manifest
    assert payload["measurements"] == dummy_report["measurements"]
    assert payload["flags"] == dummy_report["flags"]
    assert payload["assessements"] == dummy_report["assessements"]
    assert payload["report_context"]["modality"] == "cervical_sagittal_mri"
    assert payload["report_context"]["report_language"] == "en"
    assert payload["report_context"]["include_appendix"] is False
