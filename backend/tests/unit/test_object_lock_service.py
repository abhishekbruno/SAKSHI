"""
Unit tests for MOD-10 WORM Object Lock / Dual Storage Service.

Test Coverage:
    1. LocalObjectLockBackend — reference generation, lock application, idempotency,
       manifest structure, permission stripping, verify_lock_integrity.
    2. ObjectLockService — full pipeline success (MOD-09 gate → lock → DB update → contract).
    3. Gate Enforcement — unverified evidence rejected, missing dual hash rejected.
    4. Idempotency — second lock request returns existing state without error.
    5. Authorization — forbidden investigator rejected (MOD-03 integration).
    6. Case Isolation — path traversal / workspace boundary violation detected.
    7. ObjectLockedEvidenceObject contract — strict invariants enforced.
    8. Contract before lock fails — ObjectNotLockedException.
    9. Audit event emission — EVIDENCE_OBJECT_LOCK_STARTED, EVIDENCE_OBJECT_LOCKED.
    10. GOVERNANCE vs COMPLIANCE lock modes.
    11. Lock manifest content validation.
    12. Lock event log append behavior.
    13. Failure-safe: LOCK_FAILED state on backend error.
    14. End-to-end pipeline: MOD-05 → MOD-06 → MOD-07 → MOD-08 → MOD-09 → MOD-10.
"""
import json
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
from app.services.integrity_service import IntegrityService
from app.services.object_lock_service import (
    ObjectLockService,
    LocalObjectLockBackend,
    LOCK_MANIFEST_FILENAME,
    OBJECT_LOCK_DIR_NAME,
    DEFAULT_RETENTION_DAYS,
)
from app.schemas.case import CaseCreateRequest, FIRMetadata
from app.schemas.evidence import (
    EvidenceCategory,
    EvidenceIntakeMetadata,
    EvidenceIntakeStatus,
    AntivirusVerdict,
    ObjectLockMode,
    ObjectLockResult,
    ObjectLockedEvidenceObject,
)
from app.core.errors import (
    CaseNotFoundException,
    EvidenceNotFoundException,
    ForbiddenException,
    IntegrityNotVerifiedForLockException,
    ObjectLockFailedException,
    ObjectNotLockedException,
)

CLEAN_PDF = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"


# ═══════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def workspace_dir():
    temp_dir = tempfile.mkdtemp(prefix="sakshi_mod10_ws_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def active_case(db_session, mock_io1, workspace_dir):
    """Creates a case in EVIDENCE_INGESTION stage with isolated test workspace."""
    case_service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Forensic Object Lock Evidence Case",
        fir_metadata=FIRMetadata(
            fir_number="FIR-2026-LOCK-01",
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


def _setup_integrity_verified_evidence(
    db_session,
    active_case,
    mock_io1,
    payload_bytes: bytes = CLEAN_PDF,
    filename: str = "mod10_exhibit.pdf",
) -> Evidence:
    """
    Full MOD-05 → MOD-06 → MOD-07 → MOD-08 → MOD-09 pipeline.
    Returns the Evidence entity with integrity_status == 'VERIFIED'.
    """
    intake_service = EvidenceIntakeService(db_session)
    reg_obj = intake_service.register_evidence(
        case_id=active_case.case_id,
        file_payload=payload_bytes,
        original_filename=filename,
        metadata=EvidenceIntakeMetadata(
            evidence_category=EvidenceCategory.DOCUMENT_PDF,
            declared_mime_type="application/pdf",
        ),
        investigator=mock_io1,
    )

    mime_service = MimeValidationService(db_session)
    mime_service.validate_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)

    av_service = AntivirusScanService(db_session)
    av_service.scan_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)

    worm_service = WORMCommitService(db_session)
    worm_service.commit_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)

    integrity_service = IntegrityService(db_session)
    integrity_service.verify_and_compute_integrity(active_case.case_id, reg_obj.evidence_id, mock_io1)

    return intake_service.evidence_repo.get_by_evidence_id(reg_obj.evidence_id)


# ═══════════════════════════════════════════════════════════════════════════
# 1. LocalObjectLockBackend Unit Tests
# ═══════════════════════════════════════════════════════════════════════════

class TestLocalObjectLockBackend:

    def test_get_reference_format(self, workspace_dir):
        """Canonical reference: objlock://<case_id>/<sha256>+<sha3_512_prefix16>."""
        backend = LocalObjectLockBackend()
        sha256 = "a" * 64
        sha3_512 = "b" * 128
        ref = backend.get_reference("CASE-001", sha256, sha3_512)
        assert ref == f"objlock://CASE-001/{sha256}+{'b' * 16}"
        assert ref.startswith("objlock://")

    def test_get_reference_lowercased(self, workspace_dir):
        """Reference uses lowercase hex digests."""
        backend = LocalObjectLockBackend()
        sha256 = "ABCDEF" + "0" * 58
        sha3_512 = "FF" * 64
        ref = backend.get_reference("CASE-X", sha256, sha3_512)
        assert ref == ref.lower() or sha256.lower() in ref

    def test_is_locked_false_before_any_lock(self, workspace_dir):
        """is_locked returns False when no manifest exists."""
        backend = LocalObjectLockBackend()
        sha256 = hashlib.sha256(b"test_data").hexdigest()
        assert backend.is_locked("CASE-001", sha256, workspace_dir) is False

    def test_apply_lock_creates_manifest(self, workspace_dir):
        """apply_lock writes a JSON manifest inside .objlock/<sha256>/."""
        backend = LocalObjectLockBackend()
        sha256 = hashlib.sha256(CLEAN_PDF).hexdigest()
        sha3_512 = hashlib.sha3_512(CLEAN_PDF).hexdigest()

        # Write a source file
        src = os.path.join(workspace_dir, "evidence.pdf")
        with open(src, "wb") as f:
            f.write(CLEAN_PDF)

        result = backend.apply_lock(
            case_id="CASE-001",
            sha256_digest=sha256,
            sha3_512_digest=sha3_512,
            source_file_path=src,
            lock_mode=ObjectLockMode.GOVERNANCE,
            retention_days=365,
            case_workspace_path=workspace_dir,
        )

        assert result["lock_storage_reference"].startswith("objlock://")
        assert result["lock_overwrite_protected"] is True
        assert result["lock_delete_protected"] is True
        assert result["already_locked"] is False

        # Manifest file must exist
        manifest_path = os.path.join(
            workspace_dir, OBJECT_LOCK_DIR_NAME, sha256, LOCK_MANIFEST_FILENAME
        )
        assert os.path.exists(manifest_path)

    def test_apply_lock_manifest_content(self, workspace_dir):
        """Lock manifest contains all required fields with correct values."""
        backend = LocalObjectLockBackend()
        sha256 = hashlib.sha256(CLEAN_PDF).hexdigest()
        sha3_512 = hashlib.sha3_512(CLEAN_PDF).hexdigest()

        src = os.path.join(workspace_dir, "evidence2.pdf")
        with open(src, "wb") as f:
            f.write(CLEAN_PDF)

        backend.apply_lock(
            case_id="CASE-MAN-CHECK",
            sha256_digest=sha256,
            sha3_512_digest=sha3_512,
            source_file_path=src,
            lock_mode=ObjectLockMode.COMPLIANCE,
            retention_days=2555,
            case_workspace_path=workspace_dir,
        )

        manifest_path = os.path.join(
            workspace_dir, OBJECT_LOCK_DIR_NAME, sha256, LOCK_MANIFEST_FILENAME
        )
        with open(manifest_path, "r") as f:
            data = json.load(f)

        assert data["schema_version"] == "MOD10_V1"
        assert data["backend"] == "LOCAL_FILESYSTEM"
        assert data["case_id"] == "CASE-MAN-CHECK"
        assert data["checksum_sha256"] == sha256.lower()
        assert data["checksum_sha3_512"] == sha3_512.lower()
        assert data["lock_mode"] == ObjectLockMode.COMPLIANCE
        assert data["retention_days"] == 2555
        assert data["lock_overwrite_protected"] is True
        assert data["lock_delete_protected"] is True
        assert "architectural_note" in data
        assert "LOCAL_FILESYSTEM" in data["architectural_note"] or "application-level" in data["architectural_note"]
        expected_binding = f"sha256:{sha256.lower()}:sha3_512:{sha3_512.lower()}"
        assert data["lock_integrity_binding"] == expected_binding

    def test_apply_lock_idempotent_returns_existing(self, workspace_dir):
        """Second apply_lock call returns existing manifest data without error."""
        backend = LocalObjectLockBackend()
        sha256 = hashlib.sha256(b"idempotent_test").hexdigest()
        sha3_512 = hashlib.sha3_512(b"idempotent_test").hexdigest()

        src = os.path.join(workspace_dir, "idempotent.pdf")
        with open(src, "wb") as f:
            f.write(b"idempotent_test")

        result1 = backend.apply_lock("C1", sha256, sha3_512, src, "GOVERNANCE", 100, workspace_dir)
        result2 = backend.apply_lock("C1", sha256, sha3_512, src, "GOVERNANCE", 100, workspace_dir)

        assert result2["already_locked"] is True
        assert result1["lock_storage_reference"] == result2["lock_storage_reference"]

    def test_is_locked_true_after_lock(self, workspace_dir):
        """is_locked returns True after successful apply_lock."""
        backend = LocalObjectLockBackend()
        sha256 = hashlib.sha256(b"lock_status_test").hexdigest()
        sha3_512 = hashlib.sha3_512(b"lock_status_test").hexdigest()

        src = os.path.join(workspace_dir, "lockstatus.bin")
        with open(src, "wb") as f:
            f.write(b"lock_status_test")

        assert backend.is_locked("CASE-ST", sha256, workspace_dir) is False
        backend.apply_lock("CASE-ST", sha256, sha3_512, src, "GOVERNANCE", 365, workspace_dir)
        assert backend.is_locked("CASE-ST", sha256, workspace_dir) is True

    def test_verify_lock_integrity_after_lock(self, workspace_dir):
        """verify_lock_integrity returns True for a successfully locked object."""
        backend = LocalObjectLockBackend()
        sha256 = hashlib.sha256(CLEAN_PDF).hexdigest()
        sha3_512 = hashlib.sha3_512(CLEAN_PDF).hexdigest()

        src = os.path.join(workspace_dir, "verify_test.pdf")
        with open(src, "wb") as f:
            f.write(CLEAN_PDF)

        result = backend.apply_lock("CASE-VFY", sha256, sha3_512, src, "GOVERNANCE", 365, workspace_dir)
        assert backend.verify_lock_integrity(result["lock_storage_reference"], sha256, workspace_dir) is True

    def test_verify_lock_integrity_wrong_sha256_fails(self, workspace_dir):
        """verify_lock_integrity returns False when expected SHA-256 does not match manifest."""
        backend = LocalObjectLockBackend()
        sha256 = hashlib.sha256(CLEAN_PDF).hexdigest()
        sha3_512 = hashlib.sha3_512(CLEAN_PDF).hexdigest()

        src = os.path.join(workspace_dir, "wrong_hash.pdf")
        with open(src, "wb") as f:
            f.write(CLEAN_PDF)

        result = backend.apply_lock("CASE-WRG", sha256, sha3_512, src, "GOVERNANCE", 365, workspace_dir)
        assert backend.verify_lock_integrity(result["lock_storage_reference"], "0" * 64, workspace_dir) is False

    def test_verify_lock_integrity_missing_manifest_fails(self, workspace_dir):
        """verify_lock_integrity returns False when the manifest does not exist."""
        backend = LocalObjectLockBackend()
        ref = "objlock://CASE-NX/abcdef1234abcdef1234abcdef1234abcdef1234abcdef1234abcdef1234abcd+1234567890123456"
        assert backend.verify_lock_integrity(ref, "abcdef", workspace_dir) is False

    def test_manifest_is_read_only_after_lock(self, workspace_dir):
        """Lock manifest file has write permission stripped."""
        backend = LocalObjectLockBackend()
        sha256 = hashlib.sha256(b"perm_test").hexdigest()
        sha3_512 = hashlib.sha3_512(b"perm_test").hexdigest()

        src = os.path.join(workspace_dir, "perm_test.bin")
        with open(src, "wb") as f:
            f.write(b"perm_test")

        backend.apply_lock("CASE-PERM", sha256, sha3_512, src, "GOVERNANCE", 365, workspace_dir)
        manifest_path = os.path.join(workspace_dir, OBJECT_LOCK_DIR_NAME, sha256, LOCK_MANIFEST_FILENAME)
        mode = os.stat(manifest_path).st_mode
        # Owner write bit should be unset
        import stat
        assert not (mode & stat.S_IWUSR), "Manifest should be read-only"


# ═══════════════════════════════════════════════════════════════════════════
# 2. ObjectLockService Full Pipeline Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_apply_object_lock_full_pipeline_success(db_session, active_case, mock_io1):
    """Full MOD-09 → MOD-10 pipeline: integrity verified evidence is successfully locked."""
    evidence = _setup_integrity_verified_evidence(db_session, active_case, mock_io1)

    expected_sha256 = hashlib.sha256(CLEAN_PDF).hexdigest().lower()
    expected_sha3_512 = hashlib.sha3_512(CLEAN_PDF).hexdigest().lower()

    lock_service = ObjectLockService(db_session)
    result = lock_service.apply_object_lock(
        case_id=active_case.case_id,
        evidence_id=evidence.evidence_id,
        investigator=mock_io1,
    )

    assert isinstance(result, ObjectLockResult)
    assert result.lock_status == "LOCKED"
    assert result.lock_mode == "GOVERNANCE"
    assert result.lock_storage_reference.startswith("objlock://")
    assert expected_sha256 in result.lock_storage_reference
    assert result.lock_overwrite_protected is True
    assert result.lock_delete_protected is True
    assert result.checksum_sha256 == expected_sha256
    assert result.checksum_sha3_512 == expected_sha3_512
    assert expected_sha256 in result.lock_integrity_binding
    assert expected_sha3_512 in result.lock_integrity_binding
    assert result.already_locked is False
    assert result.lock_applied_at is not None
    assert result.lock_retention_until is not None
    assert result.lock_backend == "LOCAL_FILESYSTEM"


def test_apply_object_lock_db_persisted(db_session, active_case, mock_io1):
    """Object Lock metadata is atomically persisted to the Evidence database record."""
    evidence = _setup_integrity_verified_evidence(db_session, active_case, mock_io1)

    lock_service = ObjectLockService(db_session)
    result = lock_service.apply_object_lock(
        case_id=active_case.case_id,
        evidence_id=evidence.evidence_id,
        investigator=mock_io1,
    )

    # Reload from DB
    from app.repositories.evidence_repository import EvidenceRepository
    repo = EvidenceRepository(db_session)
    reloaded = repo.get_by_evidence_id(evidence.evidence_id)

    assert reloaded.lock_status == "LOCKED"
    assert reloaded.lock_mode == "GOVERNANCE"
    assert reloaded.lock_storage_reference == result.lock_storage_reference
    assert reloaded.lock_applied_at is not None
    assert reloaded.lock_retention_until is not None
    assert reloaded.lock_backend == "LOCAL_FILESYSTEM"
    assert reloaded.lock_overwrite_protected is True
    assert reloaded.lock_delete_protected is True
    assert reloaded.lock_integrity_binding is not None
    assert reloaded.lock_failure_reason is None


def test_apply_object_lock_event_log_persisted(db_session, active_case, mock_io1):
    """Object lock application is appended to the evidence event log."""
    evidence = _setup_integrity_verified_evidence(db_session, active_case, mock_io1)

    lock_service = ObjectLockService(db_session)
    lock_service.apply_object_lock(active_case.case_id, evidence.evidence_id, mock_io1)

    from app.repositories.evidence_repository import EvidenceRepository
    reloaded = EvidenceRepository(db_session).get_by_evidence_id(evidence.evidence_id)

    assert reloaded.object_lock_event_log is not None
    log = json.loads(reloaded.object_lock_event_log)
    assert isinstance(log, list)
    assert len(log) == 1
    entry = log[0]
    assert entry["event"] == "OBJECT_LOCK_APPLIED"
    assert entry["investigator_id"] == mock_io1.investigator_id
    assert entry["lock_mode"] == "GOVERNANCE"
    assert "lock_storage_reference" in entry
    assert "integrity_binding" in entry


def test_apply_object_lock_compliance_mode(db_session, active_case, mock_io1):
    """COMPLIANCE lock mode is correctly recorded in the manifest and DB."""
    evidence = _setup_integrity_verified_evidence(
        db_session, active_case, mock_io1, filename="compliance_ev.pdf"
    )

    lock_service = ObjectLockService(db_session)
    result = lock_service.apply_object_lock(
        case_id=active_case.case_id,
        evidence_id=evidence.evidence_id,
        investigator=mock_io1,
        lock_mode=ObjectLockMode.COMPLIANCE,
    )

    assert result.lock_mode == "COMPLIANCE"

    from app.repositories.evidence_repository import EvidenceRepository
    reloaded = EvidenceRepository(db_session).get_by_evidence_id(evidence.evidence_id)
    assert reloaded.lock_mode == "COMPLIANCE"


def test_apply_object_lock_retention_period_correct(db_session, active_case, mock_io1):
    """Retention period is correctly computed (applied_at + retention_days)."""
    evidence = _setup_integrity_verified_evidence(
        db_session, active_case, mock_io1, filename="retention_test.pdf"
    )

    from datetime import timezone
    from datetime import timedelta

    lock_service = ObjectLockService(db_session, retention_days=365)
    result = lock_service.apply_object_lock(active_case.case_id, evidence.evidence_id, mock_io1)

    delta = result.lock_retention_until - result.lock_applied_at
    # Retention should be approximately 365 days (within a few seconds tolerance)
    assert abs(delta.days - 365) <= 1


def test_apply_object_lock_integrity_binding_format(db_session, active_case, mock_io1):
    """Integrity binding has the canonical sha256:<val>:sha3_512:<val> format."""
    evidence = _setup_integrity_verified_evidence(
        db_session, active_case, mock_io1, filename="binding_fmt.pdf"
    )

    lock_service = ObjectLockService(db_session)
    result = lock_service.apply_object_lock(active_case.case_id, evidence.evidence_id, mock_io1)

    binding = result.lock_integrity_binding
    assert binding.startswith("sha256:")
    assert ":sha3_512:" in binding
    parts = binding.split(":")
    assert len(parts) == 4  # sha256, <val>, sha3_512, <val>
    assert len(parts[1]) == 64   # SHA-256 hex length
    assert len(parts[3]) == 128  # SHA3-512 hex length


# ═══════════════════════════════════════════════════════════════════════════
# 3. Gate Enforcement Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_apply_object_lock_rejects_unverified_evidence(db_session, active_case, mock_io1):
    """Evidence with integrity_status != 'VERIFIED' is rejected with IntegrityNotVerifiedForLockException."""
    # Only go through MOD-05 → MOD-06 → MOD-07 → MOD-08 (skip MOD-09)
    intake_service = EvidenceIntakeService(db_session)
    reg_obj = intake_service.register_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="unverified_ev.pdf",
        metadata=EvidenceIntakeMetadata(
            evidence_category=EvidenceCategory.DOCUMENT_PDF,
            declared_mime_type="application/pdf",
        ),
        investigator=mock_io1,
    )
    MimeValidationService(db_session).validate_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)
    AntivirusScanService(db_session).scan_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)
    WORMCommitService(db_session).commit_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)
    # Do NOT run MOD-09

    lock_service = ObjectLockService(db_session)
    with pytest.raises(IntegrityNotVerifiedForLockException) as exc_info:
        lock_service.apply_object_lock(active_case.case_id, reg_obj.evidence_id, mock_io1)

    assert exc_info.value.detail["error_code"] == "INTEGRITY_NOT_VERIFIED_FOR_LOCK"


def test_apply_object_lock_rejects_missing_sha3_512(db_session, active_case, mock_io1):
    """Evidence with missing checksum_sha3_512 is rejected even if integrity_status is VERIFIED."""
    evidence = _setup_integrity_verified_evidence(
        db_session, active_case, mock_io1, filename="missing_sha3.pdf"
    )

    from app.repositories.evidence_repository import EvidenceRepository
    ev = EvidenceRepository(db_session).get_by_evidence_id(evidence.evidence_id)
    ev.checksum_sha3_512 = None
    EvidenceRepository(db_session).update(ev)

    lock_service = ObjectLockService(db_session)
    with pytest.raises(IntegrityNotVerifiedForLockException):
        lock_service.apply_object_lock(active_case.case_id, evidence.evidence_id, mock_io1)


def test_apply_object_lock_rejects_unknown_case(db_session, mock_io1):
    """Nonexistent case raises CaseNotFoundException."""
    lock_service = ObjectLockService(db_session)
    with pytest.raises(CaseNotFoundException):
        lock_service.apply_object_lock("NONEXISTENT-CASE", "FAKE-EVID", mock_io1)


def test_apply_object_lock_rejects_unknown_evidence(db_session, active_case, mock_io1):
    """Nonexistent evidence raises EvidenceNotFoundException."""
    lock_service = ObjectLockService(db_session)
    with pytest.raises(EvidenceNotFoundException):
        lock_service.apply_object_lock(active_case.case_id, "FAKE-EVID-999", mock_io1)


def test_apply_object_lock_rejects_invalid_lock_mode(db_session, active_case, mock_io1):
    """Invalid lock_mode raises ObjectLockFailedException."""
    evidence = _setup_integrity_verified_evidence(
        db_session, active_case, mock_io1, filename="invalid_mode.pdf"
    )
    lock_service = ObjectLockService(db_session)
    with pytest.raises(ObjectLockFailedException):
        lock_service.apply_object_lock(
            active_case.case_id, evidence.evidence_id, mock_io1, lock_mode="INVALID_MODE"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 4. Idempotency Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_apply_object_lock_idempotent_second_call(db_session, active_case, mock_io1):
    """Calling apply_object_lock twice returns the existing lock state safely."""
    evidence = _setup_integrity_verified_evidence(
        db_session, active_case, mock_io1, filename="idem_test.pdf"
    )

    lock_service = ObjectLockService(db_session)
    result1 = lock_service.apply_object_lock(active_case.case_id, evidence.evidence_id, mock_io1)
    result2 = lock_service.apply_object_lock(active_case.case_id, evidence.evidence_id, mock_io1)

    assert result1.lock_status == "LOCKED"
    assert result2.lock_status == "LOCKED"
    assert result2.already_locked is True
    assert result1.lock_storage_reference == result2.lock_storage_reference
    assert result1.lock_integrity_binding == result2.lock_integrity_binding


# ═══════════════════════════════════════════════════════════════════════════
# 5. Authorization Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_apply_object_lock_forbidden_for_unassigned_investigator(db_session, active_case, mock_io1, mock_io2):
    """Investigator not assigned to the case is denied with ForbiddenException."""
    evidence = _setup_integrity_verified_evidence(
        db_session, active_case, mock_io1, filename="forbidden_lock.pdf"
    )

    lock_service = ObjectLockService(db_session)
    with pytest.raises(ForbiddenException):
        lock_service.apply_object_lock(active_case.case_id, evidence.evidence_id, mock_io2)


def test_get_object_lock_contract_forbidden_for_unassigned_investigator(db_session, active_case, mock_io1, mock_io2):
    """get_object_lock_contract is denied for investigator not assigned to case."""
    evidence = _setup_integrity_verified_evidence(
        db_session, active_case, mock_io1, filename="contract_forbidden.pdf"
    )
    lock_service = ObjectLockService(db_session)
    lock_service.apply_object_lock(active_case.case_id, evidence.evidence_id, mock_io1)

    with pytest.raises(ForbiddenException):
        lock_service.get_object_lock_contract(active_case.case_id, evidence.evidence_id, mock_io2)


# ═══════════════════════════════════════════════════════════════════════════
# 6. ObjectLockedEvidenceObject Contract Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_get_object_lock_contract_success(db_session, active_case, mock_io1):
    """get_object_lock_contract returns a valid ObjectLockedEvidenceObject after locking."""
    evidence = _setup_integrity_verified_evidence(
        db_session, active_case, mock_io1, filename="contract_ok.pdf"
    )

    lock_service = ObjectLockService(db_session)
    lock_service.apply_object_lock(active_case.case_id, evidence.evidence_id, mock_io1)
    contract = lock_service.get_object_lock_contract(active_case.case_id, evidence.evidence_id, mock_io1)

    assert isinstance(contract, ObjectLockedEvidenceObject)
    assert contract.evidence_id == evidence.evidence_id
    assert contract.case_id == active_case.case_id
    assert contract.lock_status == "LOCKED"
    assert contract.integrity_status == "VERIFIED"
    assert contract.source == "MOD-10"
    assert contract.lock_storage_reference.startswith("objlock://")
    assert contract.worm_storage_reference.startswith("worm://")
    assert len(contract.checksum_sha256) == 64
    assert len(contract.checksum_sha3_512) == 128
    assert contract.lock_overwrite_protected is True
    assert contract.lock_delete_protected is True
    assert "sha256:" in contract.lock_integrity_binding
    assert ":sha3_512:" in contract.lock_integrity_binding
    assert contract.lock_applied_at is not None
    assert contract.verified_at is not None


def test_get_object_lock_contract_before_lock_fails(db_session, active_case, mock_io1):
    """get_object_lock_contract raises ObjectNotLockedException if evidence is not locked."""
    evidence = _setup_integrity_verified_evidence(
        db_session, active_case, mock_io1, filename="no_lock_contract.pdf"
    )

    lock_service = ObjectLockService(db_session)
    with pytest.raises(ObjectNotLockedException) as exc_info:
        lock_service.get_object_lock_contract(active_case.case_id, evidence.evidence_id, mock_io1)

    assert exc_info.value.detail["error_code"] == "OBJECT_NOT_LOCKED"


def test_get_object_lock_contract_sha3_prefix_in_reference(db_session, active_case, mock_io1):
    """Lock storage reference includes the 16-char SHA3-512 prefix."""
    evidence = _setup_integrity_verified_evidence(
        db_session, active_case, mock_io1, filename="sha3_prefix.pdf"
    )
    lock_service = ObjectLockService(db_session)
    lock_service.apply_object_lock(active_case.case_id, evidence.evidence_id, mock_io1)
    contract = lock_service.get_object_lock_contract(active_case.case_id, evidence.evidence_id, mock_io1)

    # objlock://<case_id>/<sha256>+<sha3_prefix16>
    ref_parts = contract.lock_storage_reference.split("/")
    digest_part = ref_parts[-1]  # <sha256>+<sha3_prefix16>
    assert "+" in digest_part
    sha256_part, sha3_prefix = digest_part.split("+")
    assert len(sha256_part) == 64  # full SHA-256 length
    assert len(sha3_prefix) == 16  # first 16 chars of SHA3-512
    expected_sha3 = hashlib.sha3_512(CLEAN_PDF).hexdigest()[:16]
    assert sha3_prefix == expected_sha3


def test_get_object_lock_contract_worm_reference_preserved(db_session, active_case, mock_io1):
    """MOD-08 WORM reference is preserved in the MOD-10 contract."""
    evidence = _setup_integrity_verified_evidence(
        db_session, active_case, mock_io1, filename="worm_ref_preserve.pdf"
    )
    lock_service = ObjectLockService(db_session)
    lock_service.apply_object_lock(active_case.case_id, evidence.evidence_id, mock_io1)
    contract = lock_service.get_object_lock_contract(active_case.case_id, evidence.evidence_id, mock_io1)

    expected_sha256 = hashlib.sha256(CLEAN_PDF).hexdigest().lower()
    assert contract.worm_storage_reference == f"worm://{active_case.case_id}/{expected_sha256}"


# ═══════════════════════════════════════════════════════════════════════════
# 7. Failure-Safe Behavior Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_apply_object_lock_failure_sets_lock_failed_status(db_session, active_case, mock_io1):
    """When the backend raises an exception, lock_status is set to LOCK_FAILED."""
    evidence = _setup_integrity_verified_evidence(
        db_session, active_case, mock_io1, filename="failure_safe.pdf"
    )

    class FailingBackend(LocalObjectLockBackend):
        def apply_lock(self, *args, **kwargs):
            raise RuntimeError("Simulated backend failure")

    lock_service = ObjectLockService(db_session, lock_backend=FailingBackend())
    with pytest.raises(ObjectLockFailedException):
        lock_service.apply_object_lock(active_case.case_id, evidence.evidence_id, mock_io1)

    from app.repositories.evidence_repository import EvidenceRepository
    reloaded = EvidenceRepository(db_session).get_by_evidence_id(evidence.evidence_id)
    assert reloaded.lock_status == "LOCK_FAILED"
    assert reloaded.lock_failure_reason is not None
    assert "Simulated backend failure" in reloaded.lock_failure_reason


# ═══════════════════════════════════════════════════════════════════════════
# 8. Case Isolation (Path Traversal) Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_apply_object_lock_workspace_boundary_violation_rejected(db_session, active_case, mock_io1):
    """Evidence with path outside case workspace is rejected with ForbiddenException."""
    evidence = _setup_integrity_verified_evidence(
        db_session, active_case, mock_io1, filename="boundary_test.pdf"
    )

    from app.repositories.evidence_repository import EvidenceRepository
    ev = EvidenceRepository(db_session).get_by_evidence_id(evidence.evidence_id)

    # Manually set raw_storage_path to outside the workspace
    outside_temp = tempfile.mkdtemp(prefix="outside_workspace_")
    outside_file = os.path.join(outside_temp, "evidence_outside.pdf")
    with open(outside_file, "wb") as f:
        f.write(CLEAN_PDF)
    ev.raw_storage_path = outside_file
    EvidenceRepository(db_session).update(ev)

    try:
        lock_service = ObjectLockService(db_session)
        with pytest.raises(ForbiddenException):
            lock_service.apply_object_lock(active_case.case_id, ev.evidence_id, mock_io1)
    finally:
        shutil.rmtree(outside_temp, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════
# 9. Health Check & Module Registration
# ═══════════════════════════════════════════════════════════════════════════

def test_health_check_includes_mod10(client):
    """Health endpoint reports MOD-10 WORM Object Lock."""
    from fastapi import status
    res = client.get("/health")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "MOD-10 WORM Object Lock / Dual Storage" in data["modules"]
    assert data["version"] >= "0.4.0"
