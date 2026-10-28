"""
SQLAlchemy ORM models for SAKSHI End-to-End Automated Investigation Pipeline.
Tracks pipeline runs, stage runs, and persisted preliminary case reports.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db.base import Base


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PipelineRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_WARNINGS = "COMPLETED_WITH_WARNINGS"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class PipelineStageName(str, Enum):
    CASE_INTAKE = "CASE_INTAKE"
    EVIDENCE_SECURITY = "EVIDENCE_SECURITY"
    DOCUMENT_PROCESSING = "DOCUMENT_PROCESSING"
    EVIDENCE_INDEXING = "EVIDENCE_INDEXING"
    FACT_EXTRACTION = "FACT_EXTRACTION"
    ENTITY_GRAPH = "ENTITY_GRAPH"
    TIMELINE_CONSTRUCTION = "TIMELINE_CONSTRUCTION"
    STATEMENT_COMPARISON = "STATEMENT_COMPARISON"
    PRELIMINARY_REPORT = "PRELIMINARY_REPORT"
    INVESTIGATOR_REVIEW = "INVESTIGATOR_REVIEW"


class PipelineRun(Base):
    """Authoritative execution record for an end-to-end investigation pipeline run."""
    __tablename__ = "pipeline_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    run_id = Column(String(64), unique=True, nullable=False, index=True)
    case_id = Column(String(64), ForeignKey("cases.case_id"), nullable=False, index=True)

    status = Column(String(32), nullable=False, default=PipelineRunStatus.PENDING.value, index=True)
    requested_by = Column(String(128), nullable=False, index=True)
    current_stage = Column(String(64), nullable=False, default=PipelineStageName.CASE_INTAKE.value)

    # Detailed stage outputs and status dictionary
    stage_summary = Column(JSON, nullable=True)
    error_summary = Column(Text, nullable=True)
    retry_metadata = Column(JSON, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    __table_args__ = (
        Index("ix_pipeline_runs_case_status", "case_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<PipelineRun(run_id='{self.run_id}', case_id='{self.case_id}', status='{self.status}')>"


class PipelineStageRun(Base):
    """Detailed execution record for an individual stage within a pipeline run."""
    __tablename__ = "pipeline_stage_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    stage_run_id = Column(String(64), unique=True, nullable=False, index=True)
    run_id = Column(String(64), ForeignKey("pipeline_runs.run_id"), nullable=False, index=True)
    case_id = Column(String(64), ForeignKey("cases.case_id"), nullable=False, index=True)

    stage_name = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="PENDING", index=True)

    input_ref = Column(JSON, nullable=True)
    output_ref = Column(JSON, nullable=True)
    attempt_count = Column(Integer, nullable=False, default=1)

    error_code = Column(String(64), nullable=True)
    error_details = Column(JSON, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_stage_runs_run_stage", "run_id", "stage_name"),
    )

    def __repr__(self) -> str:
        return f"<PipelineStageRun(stage='{self.stage_name}', status='{self.status}', run_id='{self.run_id}')>"


class CaseReport(Base):
    """Persisted, traceable preliminary and final investigation case report."""
    __tablename__ = "case_reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    report_id = Column(String(64), unique=True, nullable=False, index=True)
    case_id = Column(String(64), ForeignKey("cases.case_id"), nullable=False, index=True)
    pipeline_run_id = Column(String(64), nullable=True, index=True)

    version = Column(String(32), nullable=False, default="v1.0")
    status = Column(String(32), nullable=False, default="PRELIMINARY", index=True)  # PRELIMINARY | APPROVED | SUPERSEDED

    title = Column(String(255), nullable=False)
    incident_type = Column(String(64), nullable=False, default="NEEDS_REVIEW")
    executive_summary = Column(Text, nullable=True)

    # Structured report content with source citations and section mappings
    content = Column(JSON, nullable=False)
    citation_mappings = Column(JSON, nullable=True)
    limitations = Column(JSON, nullable=True)
    unresolved_questions = Column(JSON, nullable=True)

    # Review and approval metadata
    approval_status = Column(String(32), nullable=False, default="PENDING_REVIEW")
    approved_by = Column(String(128), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)

    generated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    __table_args__ = (
        Index("ix_case_reports_case_version", "case_id", "version"),
    )

    def __repr__(self) -> str:
        return f"<CaseReport(report_id='{self.report_id}', case_id='{self.case_id}', status='{self.status}')>"
