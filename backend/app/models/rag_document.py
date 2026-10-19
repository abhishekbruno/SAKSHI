"""
SQLAlchemy ORM model for RAGDocument entity in SAKSHI.
Governs extracted, normalized, and indexed text artifacts derived from verified evidence exhibits.

Evidence Gate Invariant:
Documents are only established from exhibits that have attained VERIFIED dual-hash integrity
and LOCKED WORM object status (MOD-09 through MOD-11).
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, UniqueConstraint, Index
from app.db.base import Base


def get_utc_now():
    return datetime.now(timezone.utc)


class RAGDocument(Base):
    __tablename__ = "rag_documents"

    # Internal database primary key (UUID)
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)

    # Canonical public Document ID (e.g. SAKSHI-DOC-2026-XXXXXXXX)
    document_id = Column(String(64), unique=True, nullable=False, index=True)

    # Foreign key references to authoritative Case and Evidence entities
    case_id = Column(String(64), ForeignKey("cases.case_id"), nullable=False, index=True)
    evidence_id = Column(String(64), ForeignKey("evidence.evidence_id"), nullable=False, index=True)

    # Source cryptographic hashes binding the document to the immutable exhibit
    source_sha256 = Column(String(64), nullable=False, index=True)
    source_sha3_512 = Column(String(128), nullable=True)

    # Processing and chunking pipeline version (e.g. "v1.0")
    processing_version = Column(String(32), nullable=False, default="v1.0")

    # Indexing Lifecycle Status: PENDING | PROCESSING | INDEXED | FAILED | OUTDATED
    indexing_status = Column(String(32), nullable=False, default="PENDING", index=True)

    # Source document format and size metrics
    mime_type = Column(String(128), nullable=True)
    total_chunks = Column(Integer, nullable=False, default=0)
    total_characters = Column(Integer, nullable=False, default=0)

    # Error diagnostics (safe failure information, no secrets)
    failure_reason = Column(Text, nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)
    indexed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # Prevent duplicate document records for the same exhibit under the same processing version
        UniqueConstraint("evidence_id", "processing_version", name="uq_rag_document_evidence_version"),
        # Composite index for fast case-level document status queries
        Index("ix_rag_documents_case_status", "case_id", "indexing_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<RAGDocument(document_id='{self.document_id}', case_id='{self.case_id}', "
            f"evidence_id='{self.evidence_id}', status='{self.indexing_status}')>"
        )
