"""
SQLAlchemy ORM model for RAGChunk entity in SAKSHI.
Stores discrete bounded text chunks extracted from verified evidence documents,
anchored to their source exhibit hashes and mapped to vector embeddings.

EC-MORE Explainability Guarantee:
Every chunk retains its exact byte/character range (`char_start`, `char_end`)
and source hashes (`source_sha256`, `source_sha3_512`) to provide 100% verifiable
exhibit citations for all analytical conclusions.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, UniqueConstraint, Index
from app.db.base import Base
from app.core.config import settings
from app.models.vector_type import CompatibleVector


def get_utc_now():
    return datetime.now(timezone.utc)


class RAGChunk(Base):
    __tablename__ = "rag_chunks"

    # Internal database primary key (UUID)
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)

    # Canonical public Chunk ID (e.g. SAKSHI-CHK-2026-XXXXXXXX)
    chunk_id = Column(String(64), unique=True, nullable=False, index=True)

    # Relational hierarchy references
    document_id = Column(String(64), ForeignKey("rag_documents.document_id"), nullable=False, index=True)
    case_id = Column(String(64), ForeignKey("cases.case_id"), nullable=False, index=True)
    evidence_id = Column(String(64), ForeignKey("evidence.evidence_id"), nullable=False, index=True)

    # Sequence position within parent document
    chunk_index = Column(Integer, nullable=False)

    # Text content of the forensic evidence chunk
    content = Column(Text, nullable=False)

    # Exact citation range in source exhibit
    page_number = Column(Integer, nullable=True)
    char_start = Column(Integer, nullable=True)
    char_end = Column(Integer, nullable=True)

    # Cryptographic binding to source exhibit
    source_sha256 = Column(String(64), nullable=False)
    source_sha3_512 = Column(String(128), nullable=True)

    # Embedding metadata
    embedding_model = Column(String(128), nullable=True)
    processing_version = Column(String(32), nullable=False, default="v1.0")

    # Vector embedding column (dialect-aware: pgvector VECTOR in PG, JSON list in SQLite)
    # Dimension is unconstrained (None) until the embedding model is finalized in Phase 3
    embedding = Column(CompatibleVector(settings.EMBEDDING_DIMENSION), nullable=True)

    # Audit timestamp
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)

    __table_args__ = (
        # Prevent duplicate chunks for the same index in the same document version
        UniqueConstraint("document_id", "chunk_index", "processing_version", name="uq_rag_chunk_doc_index_version"),
        # Composite index for filtering within case boundaries
        Index("ix_rag_chunks_case_evidence", "case_id", "evidence_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<RAGChunk(chunk_id='{self.chunk_id}', doc='{self.document_id}', "
            f"case='{self.case_id}', index={self.chunk_index})>"
        )
