"""Public case endpoints (the system boundary the frontend talks to)."""

from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from .. import config, store
from ..models import CaseSummary, SignOffRequest, UploadAccepted
from ..orchestration import process_upload, render_case_report

router = APIRouter(prefix="/cases", tags=["cases"])


def _err(status: int, code: str, message: str, **extra):
    raise HTTPException(status_code=status, detail={"code": code, "message": message, **extra})


@router.get("", response_model=list[CaseSummary])
def list_cases():
    return store.list_cases()


@router.post("", response_model=UploadAccepted, status_code=202)
async def upload_case(file: UploadFile = File(...), uploader: str = Form("demo")):
    name = file.filename or "uploaded-study.nii.gz"
    if not name.lower().endswith(config.ACCEPTED_SUFFIXES):
        _err(415, "unsupported_type", "expected a DICOM .zip or NIfTI .nii/.nii.gz", failed_stage="upload", retryable=False)
    # stream-read to enforce the size limit without buffering the whole file
    size = 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > config.MAX_UPLOAD_BYTES:
            _err(413, "too_large", "file exceeds the upload limit", failed_stage="upload", retryable=False)
    return process_upload(name, uploader)


@router.get("/{case_id}")
def get_case(case_id: str):
    case = store.get_case(case_id)
    if case is None:
        _err(404, "not_found", "case not found")
    return case


@router.get("/{case_id}/job")
def get_job(case_id: str):
    job = store.get_job(case_id)
    if job is None:
        _err(404, "not_found", "case not found")
    return job


@router.post("/{case_id}/sign-off")
def sign_off(case_id: str, body: SignOffRequest | None = None):
    signed_by = (body.signed_by if body else None) or "Radiologist"
    case = store.sign_off(case_id, signed_by)
    if case is None:
        _err(404, "not_found", "case not found")
    return case


def _serve(filename: str, media_type: str):
    path = config.SAMPLE_DATA_DIR / filename
    if not path.exists():
        _err(404, "artifact_unavailable", f"{filename} not available in this deployment")
    return FileResponse(path, media_type=media_type)


@router.get("/{case_id}/report.html", response_class=HTMLResponse)
def report_html(case_id: str):
    """Render this case's clinical report by orchestrating the reporting IEP (measurements -> reporting)."""
    case = store.get_case(case_id)
    if case is None:
        _err(404, "not_found", "case not found")
    html = render_case_report(case)
    if html is None:
        _err(503, "reporting_unavailable", "the reporting service is not reachable", failed_stage="reporting", retryable=True)
    return HTMLResponse(content=html)


@router.get("/{case_id}/volume")
def volume(case_id: str):
    return _serve("sample_volume_T2.nii.gz", "application/gzip")


@router.get("/{case_id}/mask")
def mask(case_id: str, type: str = "tss"):
    return _serve("sample_mask_tss.nii.gz", "application/gzip")
