"""
Unit tests for MOD-09 Dual Hashing (SHA-256 + SHA3-512) and Integrity Verification Service.
Tests:
- SHA3-512 and SHA-256 computation over known payloads, empty files, and large streamed files
- 128-hex-character length and format invariant for SHA3-512
- MOD-08 pre-hash verification and mismatch detection (fail-closed)
- WORM commitment prerequisite enforcement
- Idempotent repeated verification
- Database persistence of integrity metadata
- Case isolation and path traversal prevention
- Downstream IntegrityProtectedEvidenceObject contract generation
- Audit event generation
"""
import os
import shutil
import hashlib
import tempfile
import pytest

from app.models.case import Case
from app.models.evidence import Evidence
from app.services.case_service import CaseService
from app.services.evidence_intake_service import EvidenceIntakeService
from app.services.mime_validation_service import MimeValidationService
from app.services.antivirus_scan_service import AntivirusScanService
from app.services.worm_commit_service import WORMCommitService
from app.services.integrity_service import IntegrityService, compute_dual_hashes
from app.schemas.case import CaseCreateRequest, FIRMetadata
from app.schemas.evidence import (
    EvidenceCategory,
    EvidenceIntakeMetadata,
    EvidenceIntakeStatus,
    AntivirusVerdict,
    IntegrityProtectedEvidenceObject,
)
from app.core.errors import (
    CaseNotFoundException,
    EvidenceNotFoundException,
    EvidenceFileNotFoundException,
    EvidenceNotWORMCommittedException,
    SHA256IntegrityMismatchException,
    IntegrityNotVerifiedException,
    ForbiddenException,
)

CLEAN_PDF = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"


@pytest.fixture
def workspace_dir():
    temp_dir = tempfile.mkdtemp(prefix="sakshi_mod09_ws_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def active_case(db_session, mock_io1, workspace_dir):
    """Creates a case in EVIDENCE_INGESTION stage with an isolated test workspace."""
    case_service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Forensic Dual Hashing Evidence Case",
        fir_metadata=FIRMetadata(
            fir_number="FIR-2026-HASH-01",
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


def _setup_committed_evidence(
    db_session,
    active_case,
    mock_io1,
    payload_bytes: bytes,
    filename: str,
    declared_mime: str = "application/pdf",
    category: EvidenceCategory = EvidenceCategory.DOCUMENT_PDF,
) -> Evidence:
    """Helper that executes MOD-05 -> MOD-06 -> MOD-07 -> MOD-08 (WORM Commit)."""
    intake_service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=category,
        declared_mime_type=declared_mime,
        description="Clean evidence for MOD-09 Dual Hashing"
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

    worm_service = WORMCommitService(db_session)
    worm_res = worm_service.commit_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)
    assert worm_res.status == "COMMITTED"
    assert worm_res.checksum_sha256 is not None

    return intake_service.evidence_repo.get_by_evidence_id(reg_obj.evidence_id)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Standalone Dual Hashing Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_compute_dual_hashes_known_payload(workspace_dir):
    """Verify compute_dual_hashes calculates exact SHA-256 and SHA3-512 digests."""
    test_path = os.path.join(workspace_dir, "sample.bin")
    content = b"SAKSHI FORENSIC EVIDENCE PAYLOAD FOR DUAL HASHING 2026"
    expected_sha256 = hashlib.sha256(content).hexdigest().lower()
    expected_sha3_512 = hashlib.sha3_512(content).hexdigest().lower()

    with open(test_path, "wb") as f:
        f.write(content)

    sha256_out, sha3_512_out = compute_dual_hashes(test_path)
    assert sha256_out == expected_sha256
    assert sha3_512_out == expected_sha3_512


def test_sha3_512_digest_format_and_length(workspace_dir):
    """Verify SHA3-512 digest produces exactly 128 lowercase hexadecimal characters."""
    test_path = os.path.join(workspace_dir, "length_check.bin")
    with open(test_path, "wb") as f:
        f.write(b"arbitrary forensic data block")

    _, sha3_512_out = compute_dual_hashes(test_path)
    assert len(sha3_512_out) == 128
    assert sha3_512_out == sha3_512_out.lower()
    assert all(c in "0123456789abcdef" for c in sha3_512_out)


def test_compute_dual_hashes_empty_file(workspace_dir):
    """Verify dual hashing handles empty files without error."""
    test_path = os.path.join(workspace_dir, "empty.bin")
    with open(test_path, "wb") as f:
        pass

    expected_sha256 = hashlib.sha256(b"").hexdigest().lower()
    expected_sha3_512 = hashlib.sha3_512(b"").hexdigest().lower()

    sha256_out, sha3_512_out = compute_dual_hashes(test_path)
    assert sha256_out == expected_sha256
    assert sha3_512_out == expected_sha3_512


def test_compute_dual_hashes_chunked_streaming_large_payload(workspace_dir):
    """Verify bounded streaming chunked I/O handles multi-megabyte payloads correctly."""
    test_path = os.path.join(workspace_dir, "large_evidence.bin")
    chunk_pattern = b"FORENSIC_CHUNK_DATA_BLOCK_1234567890_" * 256  # ~9.7 KB
    num_chunks = 250  # ~2.4 MB

    hasher_256 = hashlib.sha256()
    hasher_3_512 = hashlib.sha3_512()

    with open(test_path, "wb") as f:
        for _ in range(num_chunks):
            f.write(chunk_pattern)
            hasher_256.update(chunk_pattern)
            hasher_3_512.update(chunk_pattern)

    expected_sha256 = hasher_256.hexdigest().lower()
    expected_sha3_512 = hasher_3_512.hexdigest().lower()

    sha256_out, sha3_512_out = compute_dual_hashes(test_path, chunk_size=65536)  # 64 KB chunks
    assert sha256_out == expected_sha256
    assert sha3_512_out == expected_sha3_512


# ═══════════════════════════════════════════════════════════════════════════
# 2. Service Verification & Pipeline Integration Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_verify_and_compute_integrity_clean_worm_committed_success(db_session, active_case, mock_io1):
    """Successful dual hash integrity verification of WORM-committed evidence."""
    evidence = _setup_committed_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "clean_exhibit.pdf"
    )

    expected_sha256 = hashlib.sha256(CLEAN_PDF).hexdigest().lower()
    expected_sha3_512 = hashlib.sha3_512(CLEAN_PDF).hexdigest().lower()

    integrity_service = IntegrityService(db_session)
    result = integrity_service.verify_and_compute_integrity(
        active_case.case_id, evidence.evidence_id, mock_io1
    )

    assert result.evidence_id == evidence.evidence_id
    assert result.case_id == active_case.case_id
    assert result.checksum_sha256 == expected_sha256
    assert result.checksum_sha3_512 == expected_sha3_512
    assert result.integrity_status == "VERIFIED"
    assert result.sha256_matched is True
    assert result.already_verified is False

    # Verify DB persistence
    updated = integrity_service.evidence_repo.get_by_evidence_id(evidence.evidence_id)
    assert updated.integrity_status == "VERIFIED"
    assert updated.checksum_sha3_512 == expected_sha3_512
    assert updated.sha3_512_computed_at is not None
    assert updated.integrity_verified_at is not None
    assert "Dual hash integrity verified" in updated.integrity_verification_message


def test_verify_integrity_sha256_mismatch_fails_closed(db_session, active_case, mock_io1):
    """If evidence payload is tampered/corrupted after WORM commit, verification must fail closed."""
    evidence = _setup_committed_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "tamper_target.pdf"
    )

    # Tamper with the raw payload bytes
    with open(evidence.raw_storage_path, "wb") as f:
        f.write(b"%PDF-1.5 TAMPERED FORENSIC PAYLOAD")

    integrity_service = IntegrityService(db_session)
    with pytest.raises(SHA256IntegrityMismatchException) as exc_info:
        integrity_service.verify_and_compute_integrity(
            active_case.case_id, evidence.evidence_id, mock_io1
        )

    assert "mismatch" in str(exc_info.value).lower()

    # Verify failure state persisted in DB
    updated = integrity_service.evidence_repo.get_by_evidence_id(evidence.evidence_id)
    assert updated.integrity_status == "FAILED"
    assert updated.checksum_sha3_512 is None
    assert "does not match" in updated.integrity_verification_message.lower() or "mismatch" in updated.integrity_verification_message.lower()


def test_verify_integrity_uncommitted_evidence_rejected(db_session, active_case, mock_io1):
    """Evidence that is only registered/scanned but NOT WORM-committed must be rejected."""
    intake_service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.DOCUMENT_PDF,
        declared_mime_type="application/pdf",
        description="Uncommitted evidence"
    )
    reg_obj = intake_service.register_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="uncommitted.pdf",
        metadata=metadata,
        investigator=mock_io1,
    )

    integrity_service = IntegrityService(db_session)
    with pytest.raises(EvidenceNotWORMCommittedException) as exc_info:
        integrity_service.verify_and_compute_integrity(
            active_case.case_id, reg_obj.evidence_id, mock_io1
        )
    assert "WORM storage" in str(exc_info.value)


def test_verify_integrity_idempotent_repeated_call(db_session, active_case, mock_io1):
    """Calling integrity verification multiple times is idempotent and returns existing verified state."""
    evidence = _setup_committed_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "idempotent.pdf"
    )

    integrity_service = IntegrityService(db_session)
    res1 = integrity_service.verify_and_compute_integrity(
        active_case.case_id, evidence.evidence_id, mock_io1
    )
    assert res1.integrity_status == "VERIFIED"
    assert res1.already_verified is False

    res2 = integrity_service.verify_and_compute_integrity(
        active_case.case_id, evidence.evidence_id, mock_io1
    )
    assert res2.integrity_status == "VERIFIED"
    assert res2.already_verified is True
    assert res2.checksum_sha3_512 == res1.checksum_sha3_512


def test_verify_integrity_missing_file_rejected(db_session, active_case, mock_io1):
    """Missing physical file during integrity verification fails closed."""
    evidence = _setup_committed_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "missing_payload.pdf"
    )
    if os.path.exists(evidence.raw_storage_path):
        os.remove(evidence.raw_storage_path)

    integrity_service = IntegrityService(db_session)
    with pytest.raises(EvidenceFileNotFoundException):
        integrity_service.verify_and_compute_integrity(
            active_case.case_id, evidence.evidence_id, mock_io1
        )

    updated = integrity_service.evidence_repo.get_by_evidence_id(evidence.evidence_id)
    assert updated.integrity_status == "FAILED"


def test_verify_integrity_workspace_boundary_traversal_rejected(db_session, active_case, mock_io1):
    """Evidence path attempting to escape case workspace is rejected with ForbiddenException."""
    evidence = _setup_committed_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "boundary_test.pdf"
    )

    outside_dir = tempfile.mkdtemp(prefix="sakshi_outside_")
    outside_file = os.path.join(outside_dir, "traversal.pdf")
    with open(outside_file, "wb") as f:
        f.write(CLEAN_PDF)

    evidence.raw_storage_path = outside_file
    db_session.commit()

    integrity_service = IntegrityService(db_session)
    try:
        with pytest.raises(ForbiddenException) as exc_info:
            integrity_service.verify_and_compute_integrity(
                active_case.case_id, evidence.evidence_id, mock_io1
            )
        assert "workspace boundary" in str(exc_info.value).lower()
    finally:
        shutil.rmtree(outside_dir, ignore_errors=True)


def test_verify_integrity_cross_case_denied(db_session, active_case, mock_io1):
    """Verifying evidence against a mismatched case_id is rejected."""
    evidence = _setup_committed_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "cross_case.pdf"
    )

    # Create a second real case
    case_service = CaseService(db_session)
    case2_resp = case_service.create_case(
        CaseCreateRequest(
            title="Second Distinct Investigation Case",
            fir_metadata=FIRMetadata(
                fir_number="FIR-2026-SECOND-01",
                police_station="Second Station",
                jurisdiction_code="JUR-DEL-04"
            )
        ),
        mock_io1
    )

    integrity_service = IntegrityService(db_session)
    with pytest.raises(EvidenceNotFoundException):
        integrity_service.verify_and_compute_integrity(
            case2_resp.case_id, evidence.evidence_id, mock_io1
        )


def test_verify_integrity_unauthorized_investigator_denied(db_session, active_case, mock_io1, mock_io2):
    """Unassigned investigator in different jurisdiction cannot verify evidence integrity."""
    evidence = _setup_committed_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "auth_test.pdf"
    )

    integrity_service = IntegrityService(db_session)
    with pytest.raises(ForbiddenException):
        integrity_service.verify_and_compute_integrity(
            active_case.case_id, evidence.evidence_id, mock_io2
        )


def test_verify_integrity_supervisory_officer_allowed(db_session, active_case, mock_io1, mock_supervisor):
    """Supervisory officers have authorization to execute integrity verification."""
    evidence = _setup_committed_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "supervisor_test.pdf"
    )

    integrity_service = IntegrityService(db_session)
    res = integrity_service.verify_and_compute_integrity(
        active_case.case_id, evidence.evidence_id, mock_supervisor
    )
    assert res.integrity_status == "VERIFIED"


# ═══════════════════════════════════════════════════════════════════════════
# 3. Downstream Handoff Contract Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_get_integrity_contract_success(db_session, active_case, mock_io1):
    """Successfully export IntegrityProtectedEvidenceObject contract after verification."""
    evidence = _setup_committed_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "contract_test.pdf"
    )

    integrity_service = IntegrityService(db_session)
    integrity_service.verify_and_compute_integrity(
        active_case.case_id, evidence.evidence_id, mock_io1
    )

    contract = integrity_service.get_integrity_contract(
        active_case.case_id, evidence.evidence_id, mock_io1
    )

    assert isinstance(contract, IntegrityProtectedEvidenceObject)
    assert contract.evidence_id == evidence.evidence_id
    assert contract.case_id == active_case.case_id
    assert contract.integrity_status == "VERIFIED"
    assert contract.checksum_sha256 == evidence.checksum_sha256
    assert len(contract.checksum_sha3_512) == 128
    assert contract.source == "MOD-09"
    assert contract.worm_storage_reference.startswith("worm://")


def test_get_integrity_contract_unverified_rejected(db_session, active_case, mock_io1):
    """Attempting to export IntegrityProtectedEvidenceObject before verification is rejected."""
    evidence = _setup_committed_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "unverified_contract.pdf"
    )

    integrity_service = IntegrityService(db_session)
    with pytest.raises(IntegrityNotVerifiedException) as exc_info:
        integrity_service.get_integrity_contract(
            active_case.case_id, evidence.evidence_id, mock_io1
        )
    assert "not successfully passed dual hash integrity verification" in str(exc_info.value)
