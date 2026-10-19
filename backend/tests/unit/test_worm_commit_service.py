"""
Unit tests for MOD-08 WORM Commit + Checksum Service.
Tests chunked SHA-256 computation, strict fail-closed AV gate, WORM storage abstraction,
overwrite prevention, case isolation, path traversal, idempotency, audit trail,
and downstream handoff contract creation (WORMCommittedEvidenceObject).
"""
import os
import shutil
import tempfile
import hashlib
import pytest

from app.services.case_service import CaseService
from app.services.evidence_intake_service import EvidenceIntakeService
from app.services.mime_validation_service import MimeValidationService
from app.services.antivirus_scan_service import AntivirusScanService, EicarHeuristicScanner, EICAR_SIGNATURE
from app.services.worm_commit_service import (
    WORMCommitService,
    LocalFileSystemWORMStorage,
    compute_sha256,
)
from app.schemas.case import CaseCreateRequest, FIRMetadata
from app.schemas.evidence import (
    EvidenceCategory,
    EvidenceIntakeMetadata,
    EvidenceIntakeStatus,
    AntivirusVerdict,
    WORMCommittedEvidenceObject,
)
from app.core.errors import (
    CaseNotFoundException,
    EvidenceNotFoundException,
    EvidenceFileNotFoundException,
    EvidenceNotScannedException,
    AntivirusThreatDetectedException,
    WORMCommitFailedException,
    ChecksumMismatchException,
    EvidenceNotCommittedException,
    ForbiddenException,
)
from app.models.evidence import Evidence


CLEAN_PDF = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
CLEAN_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"


@pytest.fixture
def workspace_dir():
    temp_dir = tempfile.mkdtemp(prefix="sakshi_mod08_ws_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def active_case(db_session, mock_io1, workspace_dir):
    """Creates a case in EVIDENCE_INGESTION stage with an isolated test workspace."""
    case_service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Forensic Ballistics & WORM Evidence Case",
        fir_metadata=FIRMetadata(
            fir_number="FIR-2026-WORM-01",
            police_station="Central Police Station",
            jurisdiction_code="JUR-DEL-04"
        )
    )
    case_resp = case_service.create_case(payload, mock_io1)

    case_entity = case_service.repo.get_by_case_id(case_resp.case_id)
    case_entity.case_workspace_path = workspace_dir
    case_service.repo.update(case_entity)

    case_service.update_stage(case_resp.case_id, "EVIDENCE_INGESTION", mock_io1)
    return case_service.repo.get_by_case_id(case_resp.case_id)


def _setup_clean_scanned_evidence(
    db_session,
    active_case,
    mock_io1,
    payload_bytes: bytes,
    filename: str,
    declared_mime: str,
    category: EvidenceCategory = EvidenceCategory.DOCUMENT_PDF,
) -> Evidence:
    """Helper that executes MOD-05 (Intake) -> MOD-06 (Validation) -> MOD-07 (AV Scan)."""
    intake_service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=category,
        declared_mime_type=declared_mime,
        description="Clean evidence for MOD-08 WORM commitment"
    )
    reg_obj = intake_service.register_evidence(
        case_id=active_case.case_id,
        file_payload=payload_bytes,
        original_filename=filename,
        metadata=metadata,
        investigator=mock_io1,
    )

    mime_service = MimeValidationService(db_session)
    mime_res = mime_service.validate_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)
    assert mime_res.valid is True

    av_service = AntivirusScanService(db_session)
    av_res = av_service.scan_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)
    assert av_res.verdict == AntivirusVerdict.CLEAN

    return intake_service.evidence_repo.get_by_evidence_id(reg_obj.evidence_id)


# ═══════════════════════════════════════════════════════════════════════════
# 1. SHA-256 Pre-Hashing Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_compute_sha256_known_payload(workspace_dir):
    test_path = os.path.join(workspace_dir, "sample.bin")
    content = b"SAKSHI FORENSIC EVIDENCE PAYLOAD 2026"
    expected = hashlib.sha256(content).hexdigest().lower()

    with open(test_path, "wb") as f:
        f.write(content)

    actual = compute_sha256(test_path)
    assert actual == expected


def test_compute_sha256_empty_file(workspace_dir):
    test_path = os.path.join(workspace_dir, "empty.bin")
    with open(test_path, "wb") as f:
        pass

    # Standard empty string SHA-256
    expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    actual = compute_sha256(test_path)
    assert actual == expected


def test_compute_sha256_chunked_streaming_large_payload(workspace_dir):
    """
    Test streaming chunked hashing for larger files (> 2 MB with 64 KB chunks).
    """
    test_path = os.path.join(workspace_dir, "large.bin")
    content = b"ForensicChunkData" * 150000  # ~2.55 MB
    expected = hashlib.sha256(content).hexdigest().lower()

    with open(test_path, "wb") as f:
        f.write(content)

    # Use small 64 KB chunk size to ensure multiple loop iterations
    actual = compute_sha256(test_path, chunk_size=65536)
    assert actual == expected


def test_compute_sha256_deterministic(workspace_dir):
    test_path = os.path.join(workspace_dir, "determ.bin")
    with open(test_path, "wb") as f:
        f.write(CLEAN_PDF)

    h1 = compute_sha256(test_path)
    h2 = compute_sha256(test_path)
    assert h1 == h2


# ═══════════════════════════════════════════════════════════════════════════
# 2. Strict Fail-Closed Antivirus Gate Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_worm_commit_clean_evidence_allowed(db_session, active_case, mock_io1):
    evidence = _setup_clean_scanned_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "doc.pdf", "application/pdf"
    )

    worm_service = WORMCommitService(db_session)
    result = worm_service.commit_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    assert result.status == EvidenceIntakeStatus.COMMITTED.value
    assert result.checksum_algorithm == "SHA-256"
    assert result.checksum_sha256 == hashlib.sha256(CLEAN_PDF).hexdigest().lower()
    assert result.worm_storage_reference.startswith(f"worm://{active_case.case_id}/")
    assert result.already_committed is False

    # Check DB persistence
    refreshed = worm_service.evidence_repo.get_by_evidence_id(evidence.evidence_id)
    assert refreshed.status == EvidenceIntakeStatus.COMMITTED.value
    assert refreshed.worm_status == "COMMITTED"
    assert refreshed.checksum_sha256 == result.checksum_sha256
    assert refreshed.worm_storage_reference == result.worm_storage_reference

    # Verify downstream contract to Phase 3
    contract = worm_service.get_worm_committed_evidence_object(active_case.case_id, evidence.evidence_id, mock_io1)
    assert isinstance(contract, WORMCommittedEvidenceObject)
    assert contract.evidence_id == evidence.evidence_id
    assert contract.checksum_sha256 == result.checksum_sha256
    assert contract.worm_status == "COMMITTED"


def test_worm_commit_unscanned_evidence_rejected(db_session, active_case, mock_io1):
    """
    Evidence in VALIDATED status (passed MOD-06, but not yet scanned in MOD-07)
    must be strictly rejected by the AV gate.
    """
    intake_service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.DOCUMENT_PDF,
        declared_mime_type="application/pdf",
    )
    reg_obj = intake_service.register_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="unscanned.pdf",
        metadata=metadata,
        investigator=mock_io1,
    )

    mime_service = MimeValidationService(db_session)
    mime_service.validate_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)

    worm_service = WORMCommitService(db_session)
    with pytest.raises(EvidenceNotScannedException) as exc_info:
        worm_service.commit_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)
    assert "not passed MOD-07" in str(exc_info.value)


def test_worm_commit_quarantined_evidence_rejected(db_session, active_case, mock_io1):
    """
    Evidence with malware (EICAR) that was QUARANTINED in MOD-07 is strictly blocked.
    """
    eicar_csv = b"col1,col2\n" + EICAR_SIGNATURE + b"\n"
    intake_service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.CDR_SPREADSHEET,
        declared_mime_type="text/csv",
    )
    reg_obj = intake_service.register_evidence(
        case_id=active_case.case_id,
        file_payload=eicar_csv,
        original_filename="eicar.csv",
        metadata=metadata,
        investigator=mock_io1,
    )

    mime_service = MimeValidationService(db_session)
    mime_service.validate_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)

    av_service = AntivirusScanService(db_session)
    av_res = av_service.scan_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)
    assert av_res.verdict == AntivirusVerdict.THREAT_DETECTED

    worm_service = WORMCommitService(db_session)
    with pytest.raises(AntivirusThreatDetectedException) as exc_info:
        worm_service.commit_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)
    assert "quarantined" in str(exc_info.value).lower()


def test_worm_commit_scanner_unavailable_evidence_rejected(db_session, active_case, mock_io1):
    """
    Evidence that failed scanning due to scanner offline cannot enter MOD-08.
    """
    evidence = _setup_clean_scanned_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "doc.pdf", "application/pdf"
    )
    # Simulate scanner unavailable outcome
    evidence.status = EvidenceIntakeStatus.VALIDATED.value
    evidence.antivirus_status = AntivirusVerdict.SCANNER_UNAVAILABLE.value
    db_session.commit()

    worm_service = WORMCommitService(db_session)
    with pytest.raises(EvidenceNotScannedException):
        worm_service.commit_evidence(active_case.case_id, evidence.evidence_id, mock_io1)


# ═══════════════════════════════════════════════════════════════════════════
# 3. WORM Storage Immutability & Overwrite Prevention
# ═══════════════════════════════════════════════════════════════════════════

def test_worm_storage_creates_immutable_object_and_reads(db_session, active_case, mock_io1, workspace_dir):
    evidence = _setup_clean_scanned_evidence(
        db_session, active_case, mock_io1, CLEAN_PNG, "image.png", "image/png",
        category=EvidenceCategory.SCENE_PHOTO
    )

    worm_service = WORMCommitService(db_session)
    res = worm_service.commit_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    expected_digest = hashlib.sha256(CLEAN_PNG).hexdigest().lower()
    worm_file = os.path.join(active_case.case_workspace_path, ".worm", expected_digest)

    assert os.path.exists(worm_file)
    with open(worm_file, "rb") as f:
        stored_bytes = f.read()
    assert stored_bytes == CLEAN_PNG

    # Verify WORM storage reference verification
    is_valid = worm_service.worm_storage.verify_immutable(
        storage_reference=res.worm_storage_reference,
        expected_sha256=expected_digest,
        case_workspace_path=active_case.case_workspace_path,
    )
    assert is_valid is True


def test_worm_storage_refuses_overwrite(workspace_dir):
    """
    Direct IWORMStorage test: committing a differing object to an existing digest is rejected.
    """
    storage = LocalFileSystemWORMStorage()
    src1 = os.path.join(workspace_dir, "src1.bin")
    with open(src1, "wb") as f:
        f.write(b"ORIGINAL OBJECT DATA")

    digest1 = hashlib.sha256(b"ORIGINAL OBJECT DATA").hexdigest().lower()
    ref1 = storage.put_immutable("CASE-01", digest1, src1, case_workspace_path=workspace_dir)
    assert ref1 == f"worm://CASE-01/{digest1}"

    # Try to write differing data using the same digest (simulating collision / tampering)
    src2 = os.path.join(workspace_dir, "src2.bin")
    with open(src2, "wb") as f:
        f.write(b"TAMPERED OBJECT DATA")

    with pytest.raises(ChecksumMismatchException):
        storage.put_immutable("CASE-01", digest1, src2, case_workspace_path=workspace_dir)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Idempotency Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_worm_commit_idempotent_repeated_call(db_session, active_case, mock_io1):
    evidence = _setup_clean_scanned_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "idempotent.pdf", "application/pdf"
    )

    worm_service = WORMCommitService(db_session)
    res1 = worm_service.commit_evidence(active_case.case_id, evidence.evidence_id, mock_io1)
    assert res1.already_committed is False

    # Second commit call
    res2 = worm_service.commit_evidence(active_case.case_id, evidence.evidence_id, mock_io1)
    assert res2.already_committed is True
    assert res2.checksum_sha256 == res1.checksum_sha256
    assert res2.worm_storage_reference == res1.worm_storage_reference


# ═══════════════════════════════════════════════════════════════════════════
# 5. Security, Case Isolation & Boundary Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_unauthorized_investigator_denied_commit(db_session, active_case, mock_io1, mock_io2):
    evidence = _setup_clean_scanned_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "doc.pdf", "application/pdf"
    )

    worm_service = WORMCommitService(db_session)
    with pytest.raises(ForbiddenException):
        worm_service.commit_evidence(active_case.case_id, evidence.evidence_id, mock_io2)


def test_supervisory_officer_allowed_commit(db_session, active_case, mock_io1, mock_supervisor):
    evidence = _setup_clean_scanned_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "supervisor_doc.pdf", "application/pdf"
    )

    worm_service = WORMCommitService(db_session)
    res = worm_service.commit_evidence(active_case.case_id, evidence.evidence_id, mock_supervisor)
    assert res.status == EvidenceIntakeStatus.COMMITTED.value


def test_cross_case_commit_denied(db_session, active_case, mock_io1):
    evidence = _setup_clean_scanned_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "case_a_doc.pdf", "application/pdf"
    )

    # Create Case B
    case_service = CaseService(db_session)
    case_b_resp = case_service.create_case(
        CaseCreateRequest(
            title="Unrelated Case B",
            fir_metadata=FIRMetadata(
                fir_number="FIR-2026-WORM-B",
                police_station="South Station",
                jurisdiction_code="JUR-DEL-04"
            )
        ),
        mock_io1
    )

    worm_service = WORMCommitService(db_session)
    with pytest.raises(EvidenceNotFoundException):
        worm_service.commit_evidence(case_b_resp.case_id, evidence.evidence_id, mock_io1)


def test_workspace_boundary_path_traversal_rejected(db_session, active_case, mock_io1):
    evidence = _setup_clean_scanned_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "traversal.pdf", "application/pdf"
    )

    # Point storage path outside case workspace
    evidence.raw_storage_path = os.path.abspath(os.path.join(active_case.case_workspace_path, "..", "external_secret.txt"))
    with open(evidence.raw_storage_path, "wb") as f:
        f.write(CLEAN_PDF)
    db_session.commit()

    worm_service = WORMCommitService(db_session)
    try:
        with pytest.raises(ForbiddenException) as exc_info:
            worm_service.commit_evidence(active_case.case_id, evidence.evidence_id, mock_io1)
        assert "workspace boundary" in str(exc_info.value).lower()
    finally:
        if os.path.exists(evidence.raw_storage_path):
            os.remove(evidence.raw_storage_path)


def test_missing_physical_file_rejected(db_session, active_case, mock_io1):
    evidence = _setup_clean_scanned_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "missing.pdf", "application/pdf"
    )
    if os.path.exists(evidence.raw_storage_path):
        os.remove(evidence.raw_storage_path)

    worm_service = WORMCommitService(db_session)
    with pytest.raises(EvidenceFileNotFoundException):
        worm_service.commit_evidence(active_case.case_id, evidence.evidence_id, mock_io1)


# ═══════════════════════════════════════════════════════════════════════════
# 6. Downstream Handoff Contract to Phase 3
# ═══════════════════════════════════════════════════════════════════════════

def test_worm_committed_evidence_contract_uncommitted_rejected(db_session, active_case, mock_io1):
    evidence = _setup_clean_scanned_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "clean_uncommitted.pdf", "application/pdf"
    )

    worm_service = WORMCommitService(db_session)
    with pytest.raises(EvidenceNotCommittedException) as exc_info:
        worm_service.get_worm_committed_evidence_object(active_case.case_id, evidence.evidence_id, mock_io1)
    assert "not been committed to WORM storage" in str(exc_info.value)
