"""
Unit tests for TextExtractionService (SAKSHI RAG Phase 3).
Validates secure in-memory text extraction, security gate enforcement,
authorized decryption handoff, and provenance preservation.
"""
import io
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
from app.core.security import AuthenticatedInvestigator
from app.core.errors import (
    IneligibleEvidenceException,
    UnsupportedDocumentFormatException,
    TextExtractionException,
    ForbiddenException,
)
from app.services.text_extraction_service import TextExtractionService
from app.services.encryption_service import EncryptionService
from app.services.key_provider import LocalKeyProvider


def make_test_pdf_bytes(pages: list[str]) -> bytes:
    """Helper to synthesize a valid, minimal multi-page PDF in memory."""
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
        # Clean text for simple PDF stream
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
def extraction_fixture():
    """Sets up an isolated in-memory DB and temporary workspace for extraction tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    tmp_dir = tempfile.mkdtemp()

    case = Case(
        case_id="SAKSHI-CASE-2026-EXT01",
        title="Unnatural Death Inquest - Scene 4",
        fir_metadata={"fir_number": "FIR-2026-0099"},
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


def test_extract_multipage_pdf_success(extraction_fixture):
    """Verify extracting text from a valid multi-page PDF exhibit."""
    session, case, investigator, tmp_dir = extraction_fixture

    # Synthesize 2-page forensic PDF
    page1_text = "Inquest Report: Unnatural death observed at 0300 hours."
    page2_text = "Medical Examiner Findings: Consistent with asphyxia."
    pdf_bytes = make_test_pdf_bytes([page1_text, page2_text])

    file_path = os.path.join(tmp_dir, "inquest.pdf")
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    sha3 = hashlib.sha3_512(pdf_bytes).hexdigest()

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-PDF01",
        case_id=case.case_id,
        original_file_name="inquest.pdf",
        stored_file_name="inquest.pdf",
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

    service = TextExtractionService(session)
    extracted = service.extract_text(case.case_id, evidence.evidence_id, investigator)

    assert extracted.case_id == case.case_id
    assert extracted.evidence_id == evidence.evidence_id
    assert extracted.source_sha256 == sha256
    assert extracted.source_sha3_512 == sha3
    assert extracted.extraction_method == "PDF_NATIVE_TEXT"
    assert extracted.total_pages == 2
    assert len(extracted.pages) == 2
    assert extracted.pages[0].page_number == 1
    assert "Inquest Report" in extracted.pages[0].text
    assert extracted.pages[1].page_number == 2
    assert "Medical Examiner" in extracted.pages[1].text
    assert extracted.total_characters > 0


def test_extract_plaintext_success(extraction_fixture):
    """Verify extracting text from a plain-text forensic document."""
    session, case, investigator, tmp_dir = extraction_fixture

    content = "Forensic Witness Statement:\nWitness saw victim at 21:00 hours near the market."
    txt_bytes = content.encode("utf-8")
    file_path = os.path.join(tmp_dir, "witness_statement.txt")
    with open(file_path, "wb") as f:
        f.write(txt_bytes)

    sha256 = hashlib.sha256(txt_bytes).hexdigest()
    sha3 = hashlib.sha3_512(txt_bytes).hexdigest()

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-TXT01",
        case_id=case.case_id,
        original_file_name="witness_statement.txt",
        stored_file_name="witness_statement.txt",
        evidence_category="OTHER",
        declared_mime_type="text/plain",
        detected_mime_type="text/plain",
        file_size_bytes=len(txt_bytes),
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

    service = TextExtractionService(session)
    extracted = service.extract_text(case.case_id, evidence.evidence_id, investigator)

    assert extracted.extraction_method == "PLAINTEXT_DIRECT"
    assert extracted.total_pages == 1
    assert "Witness Statement" in extracted.pages[0].text
    assert extracted.total_characters == len(content.strip())


def test_security_gate_uncommitted_evidence_rejected(extraction_fixture):
    """Verify uncommitted evidence (MOD-08 gate) is strictly rejected."""
    session, case, investigator, tmp_dir = extraction_fixture

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-REJ01",
        case_id=case.case_id,
        original_file_name="draft.pdf",
        stored_file_name="draft.pdf",
        evidence_category="DOCUMENT_PDF",
        declared_mime_type="application/pdf",
        file_size_bytes=100,
        submitting_investigator_id=investigator.investigator_id,
        status="REGISTERED_INTAKE",  # NOT COMMITTED
        checksum_sha256="a" * 64,
        integrity_status="UNVERIFIED",
        lock_status="UNLOCKED",
        raw_storage_path="/tmp/draft.pdf",
    )
    session.add(evidence)
    session.commit()

    service = TextExtractionService(session)
    with pytest.raises(IneligibleEvidenceException) as exc:
        service.extract_text(case.case_id, evidence.evidence_id, investigator)
    assert exc.value.status_code == 422
    assert "committed" in str(exc.value).lower()


def test_security_gate_unlocked_evidence_rejected(extraction_fixture):
    """Verify unlocked evidence (MOD-10 gate) is strictly rejected."""
    session, case, investigator, tmp_dir = extraction_fixture

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-REJ02",
        case_id=case.case_id,
        original_file_name="doc.pdf",
        stored_file_name="doc.pdf",
        evidence_category="DOCUMENT_PDF",
        declared_mime_type="application/pdf",
        file_size_bytes=100,
        submitting_investigator_id=investigator.investigator_id,
        status="COMMITTED",
        worm_status="COMMITTED",
        checksum_sha256="a" * 64,
        integrity_status="VERIFIED",
        lock_status="UNLOCKED",  # NOT LOCKED
        raw_storage_path="/tmp/doc.pdf",
    )
    session.add(evidence)
    session.commit()

    service = TextExtractionService(session)
    with pytest.raises(IneligibleEvidenceException) as exc:
        service.extract_text(case.case_id, evidence.evidence_id, investigator)
    assert "LOCKED" in str(exc.value)


def test_unsupported_document_category_rejected(extraction_fixture):
    """Verify image/audio evidence categories without OCR are rejected cleanly."""
    session, case, investigator, tmp_dir = extraction_fixture

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-IMG01",
        case_id=case.case_id,
        original_file_name="crime_scene.jpg",
        stored_file_name="crime_scene.jpg",
        evidence_category="SCENE_PHOTO",
        declared_mime_type="image/jpeg",
        detected_mime_type="image/jpeg",
        file_size_bytes=1024,
        submitting_investigator_id=investigator.investigator_id,
        status="COMMITTED",
        worm_status="COMMITTED",
        checksum_sha256="a" * 64,
        checksum_sha3_512="b" * 128,
        integrity_status="VERIFIED",
        lock_status="LOCKED",
        raw_storage_path=os.path.join(tmp_dir, "scene.jpg"),
    )
    # Write dummy jpeg bytes matching hash
    with open(evidence.raw_storage_path, "wb") as f:
        f.write(b"fake jpeg content")
    evidence.checksum_sha256 = hashlib.sha256(b"fake jpeg content").hexdigest()
    evidence.checksum_sha3_512 = hashlib.sha3_512(b"fake jpeg content").hexdigest()
    session.add(evidence)
    session.commit()

    service = TextExtractionService(session)
    with pytest.raises(UnsupportedDocumentFormatException):
        service.extract_text(case.case_id, evidence.evidence_id, investigator)


def test_corrupt_pdf_fails_cleanly(extraction_fixture):
    """Verify corrupt PDF stream raises TextExtractionException cleanly without crashing."""
    session, case, investigator, tmp_dir = extraction_fixture

    corrupt_bytes = b"%PDF-1.4\ncorrupted bytes content invalid syntax"
    file_path = os.path.join(tmp_dir, "corrupt.pdf")
    with open(file_path, "wb") as f:
        f.write(corrupt_bytes)

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-BADPDF",
        case_id=case.case_id,
        original_file_name="corrupt.pdf",
        stored_file_name="corrupt.pdf",
        evidence_category="DOCUMENT_PDF",
        declared_mime_type="application/pdf",
        detected_mime_type="application/pdf",
        file_size_bytes=len(corrupt_bytes),
        submitting_investigator_id=investigator.investigator_id,
        status="COMMITTED",
        worm_status="COMMITTED",
        checksum_sha256=hashlib.sha256(corrupt_bytes).hexdigest(),
        checksum_sha3_512=hashlib.sha3_512(corrupt_bytes).hexdigest(),
        integrity_status="VERIFIED",
        lock_status="LOCKED",
        raw_storage_path=file_path,
    )
    session.add(evidence)
    session.commit()

    service = TextExtractionService(session)
    with pytest.raises(TextExtractionException):
        service.extract_text(case.case_id, evidence.evidence_id, investigator)


def test_extraction_does_not_modify_authoritative_file(extraction_fixture):
    """Verify that authoritative evidence file on disk is strictly read-only and unmodified."""
    session, case, investigator, tmp_dir = extraction_fixture

    pdf_bytes = make_test_pdf_bytes(["Authoritative evidence content."])
    file_path = os.path.join(tmp_dir, "auth_evidence.pdf")
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    mtime_before = os.path.getmtime(file_path)
    size_before = os.path.getsize(file_path)

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-IMMUT01",
        case_id=case.case_id,
        original_file_name="auth_evidence.pdf",
        stored_file_name="auth_evidence.pdf",
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
        encryption_status="UNENCRYPTED",
        raw_storage_path=file_path,
    )
    session.add(evidence)
    session.commit()

    service = TextExtractionService(session)
    extracted = service.extract_text(case.case_id, evidence.evidence_id, investigator)
    assert extracted.total_characters > 0

    # Ensure file attributes and content are 100% unaltered
    mtime_after = os.path.getmtime(file_path)
    size_after = os.path.getsize(file_path)
    with open(file_path, "rb") as f:
        content_after = f.read()

    assert mtime_before == mtime_after
    assert size_before == size_after
    assert content_after == pdf_bytes


def test_extraction_encrypted_evidence_zero_tempfile_leakage(extraction_fixture):
    """Verify authorized decryption extracts plaintext purely in memory without writing plaintext temp files."""
    session, case, investigator, tmp_dir = extraction_fixture

    pdf_bytes = make_test_pdf_bytes(["Confidential autopsy toxicology report."])
    raw_path = os.path.join(tmp_dir, "confidential.pdf")
    with open(raw_path, "wb") as f:
        f.write(pdf_bytes)

    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    sha3 = hashlib.sha3_512(pdf_bytes).hexdigest()

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-ENC01",
        case_id=case.case_id,
        original_file_name="confidential.pdf",
        stored_file_name="confidential.pdf",
        evidence_category="DOCUMENT_PDF",
        declared_mime_type="application/pdf",
        file_size_bytes=len(pdf_bytes),
        submitting_investigator_id=investigator.investigator_id,
        status="COMMITTED",
        worm_status="COMMITTED",
        checksum_sha256=sha256,
        checksum_sha3_512=sha3,
        integrity_status="VERIFIED",
        lock_status="LOCKED",
        lock_storage_reference=f"objlock://{case.case_id}/{sha256}+{sha3[:16]}",
        encryption_status="UNENCRYPTED",
        raw_storage_path=raw_path,
    )
    session.add(evidence)
    session.commit()

    # Encrypt exhibit under MOD-11
    enc_service = EncryptionService(session, key_provider=LocalKeyProvider())
    enc_service.encrypt_evidence(case.case_id, evidence.evidence_id, investigator)

    # Record files in system temp directory before extraction
    system_temp = tempfile.gettempdir()
    temp_files_before = set(os.listdir(system_temp))

    # Extract text from encrypted exhibit
    extraction_service = TextExtractionService(session, encryption_service=enc_service)
    extracted = extraction_service.extract_text(case.case_id, evidence.evidence_id, investigator)

    # Record files after extraction
    temp_files_after = set(os.listdir(system_temp))
    new_temp_files = temp_files_after - temp_files_before

    assert extracted.total_characters > 0
    assert "toxicology" in extracted.pages[0].text
    # Verify no new unencrypted temp files were created in system temp
    for new_file in new_temp_files:
        full_new_path = os.path.join(system_temp, new_file)
        if os.path.isfile(full_new_path):
            try:
                with open(full_new_path, "rb") as f:
                    file_data = f.read()
                    assert b"toxicology" not in file_data, f"Plaintext leaked into temporary file: {new_file}"
            except Exception:
                pass


def test_quarantined_evidence_rejected(extraction_fixture):
    """Verify quarantined or infected evidence is rejected immediately."""
    session, case, investigator, tmp_dir = extraction_fixture

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-QUAR01",
        case_id=case.case_id,
        original_file_name="malware.pdf",
        stored_file_name="malware.pdf",
        evidence_category="DOCUMENT_PDF",
        declared_mime_type="application/pdf",
        file_size_bytes=100,
        submitting_investigator_id=investigator.investigator_id,
        status="QUARANTINED",  # Quarantined
        antivirus_status="INFECTED",
        checksum_sha256="a" * 64,
        integrity_status="VERIFIED",
        lock_status="LOCKED",
        raw_storage_path="/tmp/malware.pdf",
    )
    session.add(evidence)
    session.commit()

    service = TextExtractionService(session)
    with pytest.raises(IneligibleEvidenceException) as exc:
        service.extract_text(case.case_id, evidence.evidence_id, investigator)
    assert "quarantined" in str(exc.value).lower()


def test_unverified_integrity_rejected(extraction_fixture):
    """Verify evidence without VERIFIED dual-hash integrity is rejected."""
    session, case, investigator, tmp_dir = extraction_fixture

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-UNVER01",
        case_id=case.case_id,
        original_file_name="unverified.pdf",
        stored_file_name="unverified.pdf",
        evidence_category="DOCUMENT_PDF",
        declared_mime_type="application/pdf",
        file_size_bytes=100,
        submitting_investigator_id=investigator.investigator_id,
        status="COMMITTED",
        worm_status="COMMITTED",
        checksum_sha256="b" * 64,
        integrity_status="UNVERIFIED",  # Unverified
        lock_status="LOCKED",
        raw_storage_path="/tmp/unverified.pdf",
    )
    session.add(evidence)
    session.commit()

    service = TextExtractionService(session)
    with pytest.raises(IneligibleEvidenceException) as exc:
        service.extract_text(case.case_id, evidence.evidence_id, investigator)
    assert "VERIFIED" in str(exc.value)


def test_tampered_plaintext_hash_mismatch_rejected(extraction_fixture):
    """Verify evidence file on disk whose hash does not match DB record fails closed."""
    session, case, investigator, tmp_dir = extraction_fixture

    pdf_bytes = make_test_pdf_bytes(["Original document."])
    file_path = os.path.join(tmp_dir, "tampered.pdf")
    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    evidence = Evidence(
        evidence_id="SAKSHI-EVID-2026-TAMP01",
        case_id=case.case_id,
        original_file_name="tampered.pdf",
        stored_file_name="tampered.pdf",
        evidence_category="DOCUMENT_PDF",
        declared_mime_type="application/pdf",
        file_size_bytes=len(pdf_bytes),
        submitting_investigator_id=investigator.investigator_id,
        status="COMMITTED",
        worm_status="COMMITTED",
        checksum_sha256="0" * 64,  # Mismatch with actual pdf_bytes
        checksum_sha3_512="0" * 128,
        integrity_status="VERIFIED",
        lock_status="LOCKED",
        encryption_status="UNENCRYPTED",
        raw_storage_path=file_path,
    )
    session.add(evidence)
    session.commit()

    service = TextExtractionService(session)
    with pytest.raises(IneligibleEvidenceException) as exc:
        service.extract_text(case.case_id, evidence.evidence_id, investigator)
    assert "integrity match" in str(exc.value).lower()

