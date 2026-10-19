"""Create RAG persistence tables (rag_documents, rag_chunks, rag_index_jobs).

Integrates pgvector on PostgreSQL (enabling vector extension and vector column)
while preserving JSON-compatible representation for SQLite testing.
Defers HNSW/IVFFlat vector index creation until embedding dimension and metric
are finalized in Phase 3.

Revision ID: 002_create_rag_tables
Revises: 001_baseline
Create Date: 2026-10-13 14:50:00 UTC

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
import sys
from pathlib import Path
from pgvector.sqlalchemy import Vector

try:
    from app.core.config import settings
except ImportError:
    _backend_dir = str(Path(__file__).resolve().parents[2])
    if _backend_dir not in sys.path:
        sys.path.insert(0, _backend_dir)
    from app.core.config import settings

revision: str = "002_create_rag_tables"
down_revision: Union[str, None] = "001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect_name = bind.dialect.name
    is_postgres = (dialect_name == "postgresql")
    try:
        inspector = sa.inspect(bind)
        existing_tables = inspector.get_table_names()
    except Exception:
        existing_tables = []

    # 1. Enable pgvector extension on PostgreSQL
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Configure dialect-appropriate vector column type
    if is_postgres:
        # Use explicit dimension if verified and configured, else unconstrained Vector()
        if settings.EMBEDDING_DIMENSION is not None:
            embedding_column_type = Vector(settings.EMBEDDING_DIMENSION)
        else:
            embedding_column_type = Vector()
    else:
        # SQLite / in-memory testing dialect: stores vector as JSON array of floats
        embedding_column_type = sa.JSON()

    # 3. Create rag_documents table
    if "rag_documents" not in existing_tables:
        op.create_table(
            "rag_documents",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("document_id", sa.String(length=64), unique=True, nullable=False),
            sa.Column("case_id", sa.String(length=64), sa.ForeignKey("cases.case_id"), nullable=False),
            sa.Column("evidence_id", sa.String(length=64), sa.ForeignKey("evidence.evidence_id"), nullable=False),
            sa.Column("source_sha256", sa.String(length=64), nullable=False),
            sa.Column("source_sha3_512", sa.String(length=128), nullable=True),
            sa.Column("processing_version", sa.String(length=32), nullable=False, server_default="v1.0"),
            sa.Column("indexing_status", sa.String(length=32), nullable=False, server_default="PENDING"),
            sa.Column("mime_type", sa.String(length=128), nullable=True),
            sa.Column("total_chunks", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_characters", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("evidence_id", "processing_version", name="uq_rag_document_evidence_version"),
        )
        op.create_index("ix_rag_documents_id", "rag_documents", ["id"])
        op.create_index("ix_rag_documents_document_id", "rag_documents", ["document_id"], unique=True)
        op.create_index("ix_rag_documents_case_id", "rag_documents", ["case_id"])
        op.create_index("ix_rag_documents_evidence_id", "rag_documents", ["evidence_id"])
        op.create_index("ix_rag_documents_source_sha256", "rag_documents", ["source_sha256"])
        op.create_index("ix_rag_documents_indexing_status", "rag_documents", ["indexing_status"])
        op.create_index("ix_rag_documents_case_status", "rag_documents", ["case_id", "indexing_status"])

    # 4. Create rag_chunks table
    if "rag_chunks" not in existing_tables:
        op.create_table(
            "rag_chunks",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("chunk_id", sa.String(length=64), unique=True, nullable=False),
            sa.Column("document_id", sa.String(length=64), sa.ForeignKey("rag_documents.document_id"), nullable=False),
            sa.Column("case_id", sa.String(length=64), sa.ForeignKey("cases.case_id"), nullable=False),
            sa.Column("evidence_id", sa.String(length=64), sa.ForeignKey("evidence.evidence_id"), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("page_number", sa.Integer(), nullable=True),
            sa.Column("char_start", sa.Integer(), nullable=True),
            sa.Column("char_end", sa.Integer(), nullable=True),
            sa.Column("source_sha256", sa.String(length=64), nullable=False),
            sa.Column("source_sha3_512", sa.String(length=128), nullable=True),
            sa.Column("embedding_model", sa.String(length=128), nullable=True),
            sa.Column("processing_version", sa.String(length=32), nullable=False, server_default="v1.0"),
            sa.Column("embedding", embedding_column_type, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("document_id", "chunk_index", "processing_version", name="uq_rag_chunk_doc_index_version"),
        )
        op.create_index("ix_rag_chunks_id", "rag_chunks", ["id"])
        op.create_index("ix_rag_chunks_chunk_id", "rag_chunks", ["chunk_id"], unique=True)
        op.create_index("ix_rag_chunks_document_id", "rag_chunks", ["document_id"])
        op.create_index("ix_rag_chunks_case_id", "rag_chunks", ["case_id"])
        op.create_index("ix_rag_chunks_evidence_id", "rag_chunks", ["evidence_id"])
        op.create_index("ix_rag_chunks_case_evidence", "rag_chunks", ["case_id", "evidence_id"])

        # Vector Index: Only created when running on PostgreSQL AND when the vector dimension is verified
        if is_postgres and settings.EMBEDDING_DIMENSION is not None:
            op.execute(
                "CREATE INDEX IF NOT EXISTS ix_rag_chunks_embedding "
                "ON rag_chunks USING hnsw (embedding vector_cosine_ops);"
            )

    # 5. Create rag_index_jobs table
    if "rag_index_jobs" not in existing_tables:
        op.create_table(
            "rag_index_jobs",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("job_id", sa.String(length=64), unique=True, nullable=False),
            sa.Column("document_id", sa.String(length=64), sa.ForeignKey("rag_documents.document_id"), nullable=False),
            sa.Column("case_id", sa.String(length=64), sa.ForeignKey("cases.case_id"), nullable=False),
            sa.Column("evidence_id", sa.String(length=64), sa.ForeignKey("evidence.evidence_id"), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("failure_error_code", sa.String(length=64), nullable=True),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("last_error_details", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_rag_index_jobs_id", "rag_index_jobs", ["id"])
        op.create_index("ix_rag_index_jobs_job_id", "rag_index_jobs", ["job_id"], unique=True)
        op.create_index("ix_rag_index_jobs_document_id", "rag_index_jobs", ["document_id"])
        op.create_index("ix_rag_index_jobs_case_id", "rag_index_jobs", ["case_id"])
        op.create_index("ix_rag_index_jobs_evidence_id", "rag_index_jobs", ["evidence_id"])
        op.create_index("ix_rag_index_jobs_status", "rag_index_jobs", ["status"])
        op.create_index("ix_rag_jobs_case_status", "rag_index_jobs", ["case_id", "status"])


def downgrade() -> None:
    op.drop_table("rag_index_jobs")
    op.drop_table("rag_chunks")
    op.drop_table("rag_documents")
