"""
SQLAlchemy ORM model for RAGIndexJob entity in SAKSHI.
Tracks asynchronous text extraction, chunking, and embedding generation jobs.

Provides resilient job state management, retry tracking, and safe error diagnostics
without leaking database internals or security credentials.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, ForeignKey, Index
from app.db.base import Base


def get_utc_now():
    return datetime.now(timezone.utc)


class RAGIndexJob(Base):
    __tablename__ = "rag_index_jobs"

    # Internal database primary key (UUID)
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)

    # Canonical public Job ID (e.g. SAKSHI-JOB-2026-XXXXXXXX)
    job_id = Column(String(64), unique=True, nullable=False, index=True)

    # Target document and forensic exhibit references
    document_id = Column(String(64), ForeignKey("rag_documents.document_id"), nullable=False, index=True)
    case_id = Column(String(64), ForeignKey("cases.case_id"), nullable=False, index=True)
    evidence_id = Column(String(64), ForeignKey("evidence.evidence_id"), nullable=False, index=True)

    # Job lifecycle status: PENDING | RUNNING | COMPLETED | FAILED | CANCELLED
    status = Column(String(32), nullable=False, default="PENDING", index=True)

    # Retry and attempt tracking
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)

    # Safe failure diagnostics (no credentials or raw dumps)
    failure_error_code = Column(String(64), nullable=True)
    failure_reason = Column(Text, nullable=True)
    last_error_details = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    __table_args__ = (
        # Composite index for querying active jobs within a case boundary
        Index("ix_rag_jobs_case_status", "case_id", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<RAGIndexJob(job_id='{self.job_id}', doc='{self.document_id}', "
            f"status='{self.status}', attempts={self.attempt_count}/{self.max_attempts})>"
        )
