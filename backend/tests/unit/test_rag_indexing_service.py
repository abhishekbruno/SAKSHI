"""
Unit tests for RAGIndexingService (SAKSHI RAG Phase 3).
Validates end-to-end extraction -> chunking -> embedding -> ORM persistence,
job state management, failure containment, and idempotency.
"""
import os
import hashlib
import tempfile
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.rag_document import RAGDocument
from app.models.rag_chunk import RAGChunk
from app.models.rag_index_job import RAGIndexJob
from app.core.security import AuthenticatedInvestigator
from app.core.errors import IneligibleEvidenceException
from app.services.rag_indexing_service import RAGIndexingService
from app.services.text_extraction_service import TextExtractionService
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService, DeterministicMockEmbeddingProvider


def make_test_pdf_bytes(pages: list[str]) -> bytes:
    """Helper to synthesize valid minimal multi-page PDF in memory."""
    parts = ['%PDF-1.4\n']
    offsets = []
    catalog_id = 1
    pages_id = 2
    page_ids = [3 + i * 2 for i in range(len(pages))]
    content_ids = [4 + i * 2 for i in range(len(pages))]
    font_id = 3 + len(pages) * 2

    offsets.append(len(''.join(parts)))
    parts.append(f'{catalog_id} 0 obj << /Type /Catalog /Pages {pages_id} 0 R >> endobj\n')

    offsets.append(len(''.join(parts)))
    kids = ' '.join(f'{pid} 0 R' for pid in page_ids)
    parts.append(f'{pages_id} 0 obj << /Type /Pages /Kids [{kids}] /Count {len(pages)} >> endobj\n')

    for i, text in enumerate(pages):
        pid = page_ids[i]
        cid = content_ids[i]
        safe_text = text.replace('(', '\\(').replace(')', '\\)')
        stream_content = f'BT /F1 12 Tf 72 712 Td ({safe_text}) Tj ET\n'

        offsets.append(len(''.join(parts)))
        parts.append(f'{pid} 0 obj << /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 792] /Contents {cid} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >> endobj\n')

        offsets.append(len(''.join(parts)))
        parts.append(f'{cid} 0 obj << /Length {len(stream_content)} >> stream\n{stream_content}endstream endobj\n')

    offsets.append(len(''.join(parts)))
    parts.append(f'{font_id} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n')

    startxref = len(''.join(parts))
    total_objs = font_id + 1
    parts.append(f'xref\n0 {total_objs}\n0000000000 65535 f \n')
    for off in offsets:
        parts.append(f'{off:010d} 00000 n \n')
    parts.append(f'trailer << /Size {total_objs} /Root {catalog_id} 0 R >>\nstartxref\n{startxref}\n%%EOF\n')

    return ''.join(parts).encode('latin-1')


@pytest.fixture
def rag_pipeline_fixture():
    """Sets up an isolated database session and seeded Case record for pipeline testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    tmp_dir = tempfile.mkdtemp()

    case = Case(
        case_id="SAKSHI-CASE-2026-PIPE01",
        title="Forensic Inquest - Unnatural Death Case",
        fir_metadata={"fir_number": "FIR-2026-0812"},
        assigned_io_id="IO-7842-SHARMA",
        lifecycle_stage="EVIDENCE_PROCESSING",
        status="ACTIVE",
        case_workspace_path=tmp_dir,
        created_by="IO-7842-SHARMA",
    )
    session.add(case)
    session.commit()

    investigator = AuthenticatedInvestigator(
        subject_id="IO-7842-SHARMA",
        name="Inspector Sharma",
        role="INVESTIGATING_OFFICER",
        station_jurisdiction="JUR-DEL-04",
        is_authenticated=True,
    )

    yield session, case, investigator, tmp_dir

    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_end_to_end_evidence_indexing_success(rag_pipeline_fixture):
    """Verify complete indexing pipeline creates RAGDocument, RAGChunks with 384-d vectors, and RAGIndexJob."""
    session, case, investigator, tmp_dir = rag_pipeline_fixture

    # 1. Create and write 2-page valid PDF
    p1 = "Forensic Post-Mortem Report. Decedent sustained blunt force head trauma."
    p2 = "Toxicology screening negative. Cause of death craniocerebral damage."
    pdf_bytes = make_test_pdf_bytes([p1, p2])

    file_path = os.path.join(tmp_dir, "autopsy_report.pdf")
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    sha3 = hashlib.sha3_512(pdf_bytes).hexdigest()

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-AUTOPSY01",
        case_id=case.case_id,
        original_file_name="autopsy_report.pdf",
        stored_file_name="autopsy_report.pdf",
        evidence_category="DOCUMENT_PDF",
        declared_mime_type="application/pdf",
        detected_mime_type="application/pdf",
        file_size_bytes=len(pdf_bytes),
        submitting_investigator_id=investigator.investigator_id,
        status="COMMITTED",
        worm_status="COMMITTED",
        checksum_sha256=sha256,
        checksum_sha3_512=sha3,
        integrity_status="VERIFIED",
        lock_status="LOCKED",
        encryption_status="UNENCRYPTED",
        raw_storage_path=file_path,
    )
    session.add(evidence)
    session.commit()

    # 2. Execute RAG indexing
    indexing_service = RAGIndexingService(
        db=session,
        embedding_service=EmbeddingService(DeterministicMockEmbeddingProvider()),
    )
    doc = indexing_service.index_evidence(case.case_id, evidence.evidence_id, investigator)

    # 3. Assert RAGDocument State
    assert doc.indexing_status == "INDEXED"
    assert doc.total_chunks == 2
    assert doc.total_characters > 0
    assert doc.source_sha256 == sha256
    assert doc.source_sha3_512 == sha3
    assert doc.indexed_at is not None

    # 4. Assert RAGChunks State
    chunks = session.query(RAGChunk).filter_by(document_id=doc.document_id).order_by(RAGChunk.chunk_index).all()
    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert "blunt force" in chunks[0].content
    assert chunks[1].page_number == 2
    assert "Cause of death" in chunks[1].content
    # Vector embedding verification (384 dimensions)
    assert isinstance(chunks[0].embedding, list)
    assert len(chunks[0].embedding) == 384
    assert chunks[0].embedding_model == "sentence-transformers/all-MiniLM-L6-v2"

    # 5. Assert RAGIndexJob State
    job = session.query(RAGIndexJob).filter_by(document_id=doc.document_id).one()
    assert job.status == "COMPLETED"
    assert job.completed_at is not None
    assert job.failure_reason is None


def test_indexing_fails_closed_on_ineligible_evidence(rag_pipeline_fixture):
    """Verify ineligible exhibit fails closed, marking job and document FAILED, never INDEXED."""
    session, case, investigator, tmp_dir = rag_pipeline_fixture

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-UNLOCKED01",
        case_id=case.case_id,
        original_file_name="unlocked.pdf",
        stored_file_name="unlocked.pdf",
        evidence_category="DOCUMENT_PDF",
        declared_mime_type="application/pdf",
        file_size_bytes=100,
        submitting_investigator_id=investigator.investigator_id,
        status="COMMITTED",
        worm_status="COMMITTED",
        checksum_sha256="1" * 64,
        integrity_status="VERIFIED",
        lock_status="UNLOCKED",  # VIOLATION: Not locked
        raw_storage_path="/tmp/unlocked.pdf",
    )
    session.add(evidence)
    session.commit()

    indexing_service = RAGIndexingService(
        db=session,
        embedding_service=EmbeddingService(DeterministicMockEmbeddingProvider()),
    )

    with pytest.raises(IneligibleEvidenceException):
        indexing_service.index_evidence(case.case_id, evidence.evidence_id, investigator)

    # Verify RAGDocument is marked FAILED, NOT INDEXED
    doc = session.query(RAGDocument).filter_by(evidence_id=evidence.evidence_id).one()
    assert doc.indexing_status == "FAILED"
    assert "LOCKED" in doc.failure_reason
    assert doc.indexed_at is None

    # Verify RAGIndexJob is marked FAILED
    job = session.query(RAGIndexJob).filter_by(evidence_id=evidence.evidence_id).one()
    assert job.status == "FAILED"
    assert job.failure_error_code == "IneligibleEvidenceException"

    # Verify no chunks were created
    chunk_count = session.query(RAGChunk).filter_by(document_id=doc.document_id).count()
    assert chunk_count == 0


def test_indexing_idempotency_returns_existing_record(rag_pipeline_fixture):
    """Verify calling index_evidence repeatedly returns existing document without duplicate chunks."""
    session, case, investigator, tmp_dir = rag_pipeline_fixture

    text = "Initial statement for idempotency verification."
    pdf_bytes = make_test_pdf_bytes([text])
    file_path = os.path.join(tmp_dir, "statement.pdf")
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-IDEM01",
        case_id=case.case_id,
        original_file_name="statement.pdf",
        stored_file_name="statement.pdf",
        evidence_category="DOCUMENT_PDF",
        declared_mime_type="application/pdf",
        file_size_bytes=len(pdf_bytes),
        submitting_investigator_id=investigator.investigator_id,
        status="COMMITTED",
        worm_status="COMMITTED",
        checksum_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
        checksum_sha3_512=hashlib.sha3_512(pdf_bytes).hexdigest(),
        integrity_status="VERIFIED",
        lock_status="LOCKED",
        raw_storage_path=file_path,
    )
    session.add(evidence)
    session.commit()

    service = RAGIndexingService(db=session, embedding_service=EmbeddingService(DeterministicMockEmbeddingProvider()))
    doc1 = service.index_evidence(case.case_id, evidence.evidence_id, investigator)
    doc2 = service.index_evidence(case.case_id, evidence.evidence_id, investigator)

    assert doc1.document_id == doc2.document_id
    assert doc1.indexing_status == "INDEXED"

    # Exactly 1 chunk created, not duplicated
    chunk_count = session.query(RAGChunk).filter_by(document_id=doc1.document_id).count()
    assert chunk_count == 1
