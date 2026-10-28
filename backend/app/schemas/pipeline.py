"""
Pydantic schemas for SAKSHI End-to-End Automated Investigation Pipeline.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.case import CaseResponse


class PipelineStageRunResponse(BaseModel):
    stage_run_id: str
    run_id: str
    stage_name: str
    status: str
    attempt_count: int = 1
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    output_ref: Optional[Dict[str, Any]] = None


class PipelineRunResponse(BaseModel):
    run_id: str
    case_id: str
    status: str
    requested_by: str
    current_stage: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    stage_runs: List[PipelineStageRunResponse] = Field(default_factory=list)
    error_summary: Optional[str] = None
    stage_summary: Optional[Dict[str, Any]] = None


class CaseReportSection(BaseModel):
    section_number: int
    title: str
    content_text: str
    items: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    citations: List[Dict[str, Any]] = Field(default_factory=list)


class CaseReportResponse(BaseModel):
    report_id: str
    case_id: str
    pipeline_run_id: Optional[str] = None
    version: str = "v1.0"
    status: str = "PRELIMINARY"
    title: str
    incident_type: str = "NEEDS_REVIEW"
    executive_summary: Optional[str] = None
    sections: List[CaseReportSection] = Field(default_factory=list)
    citation_mappings: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    limitations: Optional[List[str]] = Field(default_factory=list)
    unresolved_questions: Optional[List[str]] = Field(default_factory=list)
    approval_status: str = "PENDING_REVIEW"
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    generated_at: datetime


class CaseReportReviewRequest(BaseModel):
    decision: str = Field(..., description="Review outcome: APPROVED, REJECTED, REVISION_REQUESTED")
    notes: Optional[str] = Field(None, max_length=1000, description="Investigator review rationale")


class CaseReportReviewResponse(BaseModel):
    report_id: str
    case_id: str
    approval_status: str
    approved_by: str
    approved_at: datetime
    message: str


class AutoRegisterCaseRequest(BaseModel):
    fir_file_b64: Optional[str] = Field(None, description="Base64-encoded FIR document payload")
    fir_filename: Optional[str] = Field(None, description="Original filename of the FIR document")
    fir_raw_text: Optional[str] = Field(None, description="Plaintext FIR content if submitted without a file")
    title: Optional[str] = Field(None, description="Optional manual case title override")
    assigned_io_id: Optional[str] = Field(None, description="Assigned Investigating Officer ID")


class AutoRegisterCaseResponse(BaseModel):
    case: CaseResponse
    fir_evidence_id: str
    pipeline_run: PipelineRunResponse
    preliminary_report: Optional[CaseReportResponse] = None
    incident_type: str
    message: str
