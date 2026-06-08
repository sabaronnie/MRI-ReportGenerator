"""Pydantic request/response models for the EEP public API.

Full case envelopes are served as dicts (they conform to docs/contracts/data-contract-v0.1.md +
report-contract-v0.1.md). These models cover the lightweight request/summary/error shapes.
"""

from __future__ import annotations

from pydantic import BaseModel


class CaseSummary(BaseModel):
    case_id: str
    status: str
    triage_badge: str
    modality: str
    uploader: str
    created_at: str
    updated_at: str


class UploadAccepted(BaseModel):
    case_id: str
    status: str


class SignOffRequest(BaseModel):
    signed_by: str = "Radiologist"


class ApiError(BaseModel):
    code: str
    message: str
    failed_stage: str | None = None
    retryable: bool = False
