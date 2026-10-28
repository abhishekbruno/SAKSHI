"""
Unit tests for SAKSHI RAG persistence models, schema constraints, vector types, and migration infrastructure.
Validates Phase 2: Database Schema, ORM Models, and Migration Infrastructure.
"""
import os
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.rag_document import RAGDocument
from app.models.rag_chunk import RAGChunk
from app.models.rag_index_job import RAGIndexJob
from app.models.vector_type import CompatibleVector
from app.db.verify_connection import verify_database_connection


@pytest.fixture
def rag_test_db():
    """Isolated in-memory SQLite database session for RAG schema tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed parent case and evidence records to test relational hierarchy
    case = Case(
        case_id="SAKSHI-CASE-2026-TEST01",
        title="Unnatural Death Investigation - Room 402",
        fir_metadata={"fir_number": "FIR-2026-0042", "police_station": "Station A"},
        assigned_io_id="IO-7842-SHARMA",
        lifecycle_stage="EVIDENCE_PROCESSING",
        status="ACTIVE",
        case_workspace_path="/sakshi/workspaces/SAKSHI-CASE-2026-TEST01",
        created_by="IO-7842-SHARMA",
    )
    session.add(case)
    session.commit()

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-DOC001",
        case_id=case.case_id,
        original_file_name="inquest_report.pdf",
        stored_file_name="inquest_report_sanitized.pdf",
        evidence_category="DOCUMENT_PDF",
        declared_mime_type="application/pdf",
        file_size_bytes=1048576,
        submitting_investigator_id="IO-7842-SHARMA",
        status="COMMITTED",
        checksum_sha256="a" * 64,
        checksum_sha3_512="b" * 128,
        integrity_status="VERIFIED",
        lock_status="LOCKED",
        encryption_status="ENCRYPTED",
        raw_storage_path="/sakshi/workspaces/SAKSHI-CASE-2026-TEST01/evidence/raw/inquest.pdf",
    )
    session.add(evidence)
    session.commit()

    yield session, engine

    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


# ═══════════════════════════════════════════════════════════════════════════
# 1. ORM Model Registration & Metadata Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_rag_models_registered_in_base_metadata():
    """Verify that all RAG models are properly attached to Base.metadata."""
    table_names = set(Base.metadata.tables.keys())
    assert "cases" in table_names
    assert "evidence" in table_names
    assert "rag_documents" in table_names
    assert "rag_chunks" in table_names
    assert "rag_index_jobs" in table_names


def test_rag_document_foreign_keys():
    """Verify foreign-key constraints on rag_documents reference cases and evidence."""
    doc_table = Base.metadata.tables["rag_documents"]
    fk_targets = {fk.target_fullname for fk in doc_table.foreign_keys}
    assert "cases.case_id" in fk_targets
    assert "evidence.evidence_id" in fk_targets


def test_rag_chunk_foreign_keys():
    """Verify foreign-key constraints on rag_chunks reference rag_documents, cases, and evidence."""
    chunk_table = Base.metadata.tables["rag_chunks"]
    fk_targets = {fk.target_fullname for fk in chunk_table.foreign_keys}
    assert "rag_documents.document_id" in fk_targets
    assert "cases.case_id" in fk_targets
    assert "evidence.evidence_id" in fk_targets


def test_rag_index_job_foreign_keys():
    """Verify foreign-key constraints on rag_index_jobs reference rag_documents, cases, and evidence."""
    job_table = Base.metadata.tables["rag_index_jobs"]
    fk_targets = {fk.target_fullname for fk in job_table.foreign_keys}
    assert "rag_documents.document_id" in fk_targets
    assert "cases.case_id" in fk_targets
    assert "evidence.evidence_id" in fk_targets


# ═══════════════════════════════════════════════════════════════════════════
# 2. SQLite Compatibility & Record Creation Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_rag_document_creation_and_preservation(rag_test_db):
    """Verify creating a RAG document preserves existing Case and Evidence entities."""
    session, _ = rag_test_db

    doc = RAGDocument(
        document_id="SAKSHI-DOC-2026-AA11BB22",
        case_id="SAKSHI-CASE-2026-TEST01",
        evidence_id="SAKSHI-EVID-2026-DOC001",
        source_sha256="a" * 64,
        source_sha3_512="b" * 128,
        processing_version="v1.0",
        indexing_status="INDEXED",
        mime_type="application/pdf",
        total_chunks=3,
        total_characters=4500,
    )
    session.add(doc)
    session.commit()

    # Query back
    retrieved = session.query(RAGDocument).filter_by(document_id="SAKSHI-DOC-2026-AA11BB22").one()
    assert retrieved.case_id == "SAKSHI-CASE-2026-TEST01"
    assert retrieved.evidence_id == "SAKSHI-EVID-2026-DOC001"
    assert retrieved.indexing_status == "INDEXED"

    # Verify existing parent records remain completely intact
    parent_case = session.query(Case).filter_by(case_id="SAKSHI-CASE-2026-TEST01").one()
    assert parent_case.title == "Unnatural Death Investigation - Room 402"
    parent_evid = session.query(Evidence).filter_by(evidence_id="SAKSHI-EVID-2026-DOC001").one()
    assert parent_evid.lock_status == "LOCKED"


def test_rag_chunk_creation_with_compatible_vector(rag_test_db):
    """Verify RAG chunk insertion with vector embedding operates cleanly on SQLite."""
    session, _ = rag_test_db

    doc = RAGDocument(
        document_id="SAKSHI-DOC-2026-AA11BB22",
        case_id="SAKSHI-CASE-2026-TEST01",
        evidence_id="SAKSHI-EVID-2026-DOC001",
        source_sha256="a" * 64,
        processing_version="v1.0",
        indexing_status="INDEXED",
    )
    session.add(doc)
    session.commit()

    # Insert chunk with sample vector
    mock_vector = [0.1234, -0.5678, 0.9012, 0.3456]
    chunk = RAGChunk(
        chunk_id="SAKSHI-CHK-2026-0001",
        document_id=doc.document_id,
        case_id="SAKSHI-CASE-2026-TEST01",
        evidence_id="SAKSHI-EVID-2026-DOC001",
        chunk_index=0,
        content="Rigors observed in upper extremities consistent with post-mortem interval.",
        page_number=1,
        char_start=0,
        char_end=74,
        source_sha256="a" * 64,
        embedding_model="mock-embedding-v1",
        processing_version="v1.0",
        embedding=mock_vector,
    )
    session.add(chunk)
    session.commit()

    retrieved = session.query(RAGChunk).filter_by(chunk_id="SAKSHI-CHK-2026-0001").one()
    assert retrieved.chunk_index == 0
    assert retrieved.content.startswith("Rigors observed")
    assert retrieved.char_end == 74
    # Embedding is parsed back as a list of floats
    assert isinstance(retrieved.embedding, list)
    assert len(retrieved.embedding) == 4
    assert pytest.approx(retrieved.embedding[0]) == 0.1234


def test_rag_index_job_lifecycle(rag_test_db):
    """Verify RAGIndexJob status transitions and error handling."""
    session, _ = rag_test_db

    doc = RAGDocument(
        document_id="SAKSHI-DOC-2026-JOBDOC",
        case_id="SAKSHI-CASE-2026-TEST01",
        evidence_id="SAKSHI-EVID-2026-DOC001",
        source_sha256="a" * 64,
        processing_version="v1.0",
    )
    session.add(doc)
    session.commit()

    job = RAGIndexJob(
        job_id="SAKSHI-JOB-2026-9901",
        document_id=doc.document_id,
        case_id="SAKSHI-CASE-2026-TEST01",
        evidence_id="SAKSHI-EVID-2026-DOC001",
        status="RUNNING",
        attempt_count=1,
        max_attempts=3,
    )
    session.add(job)
    session.commit()

    # Simulate job failure with safe diagnostics
    job.status = "FAILED"
    job.failure_error_code = "EXTRACTION_PARSER_ERROR"
    job.failure_reason = "Corrupted PDF stream encountered at page 3"
    job.last_error_details = {"corrupted_page": 3, "recoverable": False}
    session.commit()

    retrieved_job = session.query(RAGIndexJob).filter_by(job_id="SAKSHI-JOB-2026-9901").one()
    assert retrieved_job.status == "FAILED"
    assert retrieved_job.failure_error_code == "EXTRACTION_PARSER_ERROR"
    assert retrieved_job.last_error_details["corrupted_page"] == 3


# ═══════════════════════════════════════════════════════════════════════════
# 3. Uniqueness and Integrity Constraint Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_rag_document_uniqueness_constraint(rag_test_db):
    """Verify UniqueConstraint on (evidence_id, processing_version) prevents duplicate documents."""
    session, _ = rag_test_db

    doc1 = RAGDocument(
        document_id="SAKSHI-DOC-2026-D1",
        case_id="SAKSHI-CASE-2026-TEST01",
        evidence_id="SAKSHI-EVID-2026-DOC001",
        source_sha256="a" * 64,
        processing_version="v1.0",
    )
    session.add(doc1)
    session.commit()

    # Attempting to add second document for same exhibit and version must fail
    doc2 = RAGDocument(
        document_id="SAKSHI-DOC-2026-D2",
        case_id="SAKSHI-CASE-2026-TEST01",
        evidence_id="SAKSHI-EVID-2026-DOC001",
        source_sha256="a" * 64,
        processing_version="v1.0",
    )
    session.add(doc2)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_rag_chunk_uniqueness_constraint(rag_test_db):
    """Verify UniqueConstraint on (document_id, chunk_index, processing_version) prevents duplicates."""
    session, _ = rag_test_db

    doc = RAGDocument(
        document_id="SAKSHI-DOC-2026-CHUNKTEST",
        case_id="SAKSHI-CASE-2026-TEST01",
        evidence_id="SAKSHI-EVID-2026-DOC001",
        source_sha256="a" * 64,
        processing_version="v1.0",
    )
    session.add(doc)
    session.commit()

    c1 = RAGChunk(
        chunk_id="SAKSHI-CHK-2026-C1",
        document_id=doc.document_id,
        case_id="SAKSHI-CASE-2026-TEST01",
        evidence_id="SAKSHI-EVID-2026-DOC001",
        chunk_index=0,
        content="First paragraph.",
        source_sha256="a" * 64,
        processing_version="v1.0",
    )
    session.add(c1)
    session.commit()

    # Attempting to insert duplicate chunk index for same document and version must fail
    c2 = RAGChunk(
        chunk_id="SAKSHI-CHK-2026-C2",
        document_id=doc.document_id,
        case_id="SAKSHI-CASE-2026-TEST01",
        evidence_id="SAKSHI-EVID-2026-DOC001",
        chunk_index=0,
        content="Conflicting content with duplicate index.",
        source_sha256="a" * 64,
        processing_version="v1.0",
    )
    session.add(c2)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


# ═══════════════════════════════════════════════════════════════════════════
# 4. Migration Infrastructure & Configuration Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_alembic_configuration_and_revisions():
    """Verify Alembic configuration, script directory, and revision chaining."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
    assert os.path.exists(alembic_ini_path), "alembic.ini must exist"

    cfg = Config(alembic_ini_path)
    script = ScriptDirectory.from_config(cfg)

    # Check heads
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] in {"002_create_rag_tables", "003_iam_officers", "004_pipeline_runs_and_reports"}

    # Check revision sequence
    rev2 = script.get_revision("002_create_rag_tables")
    assert rev2.down_revision == "001_baseline"

    rev1 = script.get_revision("001_baseline")
    assert rev1.down_revision is None


def test_offline_postgres_failure_handling():
    """Verify connection verifier handles unreachable PostgreSQL without crashing or leaking secrets."""
    unreachable_url = "postgresql+psycopg://test_user:confidential_pw@127.0.0.1:5432/sakshi_nonexistent"
    result = verify_database_connection(unreachable_url, timeout_seconds=2)
    assert result["status"] == "connection_failed"
    assert result["dialect"] == "postgresql"
    assert "confidential_pw" not in result["database_url"]
    assert "********" in result["database_url"]
    assert result["pgvector_ready"] is False
    assert "Ensure PostgreSQL service is active" in result["recommendation"]


def test_rag_models_required_field_constraints(rag_test_db):
    """Verify required non-nullable fields on RAG models reject None/missing values."""
    session, _ = rag_test_db

    # RAGDocument missing source_sha256
    doc_invalid = RAGDocument(
        document_id="SAKSHI-DOC-REQ-01",
        case_id="SAKSHI-CASE-2026-TEST01",
        evidence_id="SAKSHI-EVID-2026-DOC001",
        source_sha256=None,  # Nullable=False
    )
    session.add(doc_invalid)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    # RAGChunk missing content
    doc = RAGDocument(
        document_id="SAKSHI-DOC-REQ-PARENT",
        case_id="SAKSHI-CASE-2026-TEST01",
        evidence_id="SAKSHI-EVID-2026-DOC001",
        source_sha256="a" * 64,
    )
    session.add(doc)
    session.commit()

    chunk_invalid = RAGChunk(
        chunk_id="SAKSHI-CHK-REQ-01",
        document_id=doc.document_id,
        case_id="SAKSHI-CASE-2026-TEST01",
        evidence_id="SAKSHI-EVID-2026-DOC001",
        chunk_index=0,
        content=None,  # Nullable=False
        source_sha256="a" * 64,
    )
    session.add(chunk_invalid)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_compatible_vector_dialect_handling():
    """Verify CompatibleVector compiles to JSON on SQLite and Vector on PostgreSQL dialect."""
    from sqlalchemy.dialects import sqlite, postgresql
    from sqlalchemy.types import JSON
    from pgvector.sqlalchemy import Vector

    vec_type_unconstrained = CompatibleVector()
    vec_type_dim = CompatibleVector(dim=384)

    # SQLite dialect descriptor
    sqlite_dialect = sqlite.dialect()
    assert isinstance(vec_type_unconstrained.load_dialect_impl(sqlite_dialect), JSON)
    assert isinstance(vec_type_dim.load_dialect_impl(sqlite_dialect), JSON)

    # PostgreSQL dialect descriptor
    pg_dialect = postgresql.dialect()
    pg_impl_unconstrained = vec_type_unconstrained.load_dialect_impl(pg_dialect)
    assert isinstance(pg_impl_unconstrained, Vector)
    assert pg_impl_unconstrained.dim is None

    pg_impl_dim = vec_type_dim.load_dialect_impl(pg_dialect)
    assert isinstance(pg_impl_dim, Vector)
    assert pg_impl_dim.dim == 384

    # Serialization on SQLite
    raw_vector = [0.1, 0.2, 0.3]
    processed = vec_type_unconstrained.process_bind_param(raw_vector, sqlite_dialect)
    assert processed == [0.1, 0.2, 0.3]
    assert vec_type_unconstrained.process_result_value(processed, sqlite_dialect) == [0.1, 0.2, 0.3]


def test_migration_execution_and_downgrade_on_sqlite():
    """Verify end-to-end Alembic migration upgrade and downgrade on temporary SQLite database."""
    import tempfile
    import sqlite3
    from alembic.config import Config
    from alembic import command

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        db_url = f"sqlite:///{tmp_path.replace(os.sep, '/')}"
        alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
        cfg = Config(alembic_ini_path)
        cfg.set_main_option("sqlalchemy.url", db_url)

        # 1. Upgrade to head (001_baseline + 002_create_rag_tables)
        command.upgrade(cfg, "head")

        conn = sqlite3.connect(tmp_path)
        cur = conn.cursor()
        tables = set(r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall())
        expected_tables = {"alembic_version", "cases", "evidence", "rag_documents", "rag_chunks", "rag_index_jobs"}
        assert expected_tables.issubset(tables)

        # 2. Downgrade to 001_baseline (should drop rag_* tables while keeping baseline cases & evidence)
        command.downgrade(cfg, "001_baseline")
        tables_after_downgrade = set(r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall())
        assert "cases" in tables_after_downgrade
        assert "evidence" in tables_after_downgrade
        assert "rag_documents" not in tables_after_downgrade
        assert "rag_chunks" not in tables_after_downgrade
        assert "rag_index_jobs" not in tables_after_downgrade
        conn.close()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_migration_preserves_preexisting_data():
    """Verify running migrations on a database with pre-existing case records does not drop or overwrite data."""
    import tempfile
    import sqlite3
    from alembic.config import Config
    from alembic import command

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Pre-seed a cases table before running migrations
        conn = sqlite3.connect(tmp_path)
        cur = conn.cursor()
        cur.execute(
            "CREATE TABLE cases ("
            "  id VARCHAR(36) PRIMARY KEY, "
            "  case_id VARCHAR(64) UNIQUE, "
            "  title VARCHAR(255), "
            "  fir_metadata JSON, "
            "  assigned_io_id VARCHAR(128), "
            "  lifecycle_stage VARCHAR(64), "
            "  status VARCHAR(32), "
            "  case_workspace_path VARCHAR(512), "
            "  created_by VARCHAR(128), "
            "  created_at TIMESTAMP, "
            "  updated_at TIMESTAMP"
            ");"
        )
        cur.execute(
            "INSERT INTO cases (id, case_id, title, fir_metadata, assigned_io_id, lifecycle_stage, status, case_workspace_path, created_by, created_at, updated_at) "
            "VALUES ('uid-1', 'PRE-EXISTING-001', 'Active Inquest', '{}', 'IO-1', 'INITIALIZED', 'ACTIVE', '/ws/1', 'IO-1', '2026-10-10', '2026-10-10');"
        )
        conn.commit()
        conn.close()

        # Run Alembic upgrade head
        db_url = f"sqlite:///{tmp_path.replace(os.sep, '/')}"
        alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "alembic.ini"))
        cfg = Config(alembic_ini_path)
        cfg.set_main_option("sqlalchemy.url", db_url)

        command.upgrade(cfg, "head")

        # Verify pre-existing case record is preserved untouched
        conn = sqlite3.connect(tmp_path)
        cur = conn.cursor()
        cases = cur.execute("SELECT case_id, title FROM cases WHERE case_id = 'PRE-EXISTING-001';").fetchall()
        assert len(cases) == 1
        assert cases[0][0] == "PRE-EXISTING-001"
        assert cases[0][1] == "Active Inquest"

        # Verify new RAG tables were also added successfully
        tables = set(r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall())
        assert {"rag_documents", "rag_chunks", "rag_index_jobs"}.issubset(tables)
        conn.close()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def test_verify_database_connection_sqlite_diagnostics():
    """Verify database connection probe correctly reports SQLite environment."""
    result = verify_database_connection("sqlite:///:memory:")
    assert result["status"] == "connected"
    assert result["dialect"] == "sqlite"
    assert "sqlite" in result["database_url"].lower()
    assert result["pgvector_ready"] is False
    assert "SQLite" in result["server_version"]
    assert "development" in result["recommendation"].lower()

