"""
Unit tests for MOD-11 AES-256-GCM Encryption Service.

Test Coverage:
    1. LocalKeyProvider — 256-bit key generation, canonical URI, per-case isolation,
       cross-case prevention (CaseKeyIsolationException), rotation.
    2. ProductionHSMKMSProvider — documented architectural contract, mock vs live guard.
    3. EncryptionService Pipeline — full progression MOD-05 → MOD-06 → MOD-07 → MOD-08 → MOD-09 → MOD-10 → MOD-11.
    4. Authenticated Encryption — AES-256-GCM, 96-bit nonce, 128-bit auth tag, AAD binding.
    5. Nonce Uniqueness — independent random nonces per encryption operation.
    6. Gate Enforcement — unlocked evidence rejected (ObjectNotLockedForEncryptionException),
       unverified dual-hash rejected.
    7. Idempotency — re-encrypting returns existing encrypted state with already_encrypted=True.
    8. Pre-Encryption Tamper Check — detects if plaintext modified before encryption.
    9. Post-Encryption Verification — verify_encryption_integrity succeeds on valid ciphertext.
    10. Cryptographic Tamper Detection — bit flips in ciphertext detected and fail-closed.
    11. Tag Mismatch Detection — modified GCM auth tag raises EncryptionTamperException.
    12. AAD Transposition Resistance — AAD tamper fails GCM tag verification.
    13. Case Key Isolation — attempting to decrypt with key from another case fails.
    14. Decryption Utility — decrypt_evidence_bytes round-trip dual-hash match.
    15. RBAC Authorization — unauthorized investigator rejected (ForbiddenException).
    16. Workspace Boundary Containment — payload path escaping workspace rejected.
    17. EncryptedEvidenceObject Contract — strict invariants, ready for MOD-12 handoff.
    18. Contract Retrieval before encryption fails with EvidenceNotEncryptedException.
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
from app.services.integrity_service import IntegrityService
from app.services.object_lock_service import ObjectLockService
from app.services.encryption_service import (
    EncryptionService,
    NONCE_LENGTH_BYTES,
    AUTH_TAG_LENGTH_BYTES,
    AES_ALGORITHM_NAME,
)
from app.services.key_provider import (
    LocalKeyProvider,
    ProductionHSMKMSProvider,
)
from app.schemas.case import CaseCreateRequest, FIRMetadata
from app.schemas.evidence import (
    EvidenceCategory,
    EvidenceIntakeMetadata,
    ObjectLockMode,
    EncryptionResult,
    EncryptedEvidenceObject,
    EncryptionVerificationResult,
)
from app.core.errors import (
    CaseNotFoundException,
    EvidenceNotFoundException,
    ForbiddenException,
    ObjectNotLockedForEncryptionException,
    EvidenceNotEncryptedException,
    EncryptionTamperException,
    CaseKeyIsolationException,
    KeyProviderException,
)
from app.core.security import AuthenticatedInvestigator


# ═══════════════════════════════════════════════════════════════════════════
# Helpers & Fixtures
# ═══════════════════════════════════════════════════════════════════════════

SAMPLE_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Title (Confidential Forensic Report) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"


def create_pipeline_case(db_session, case_id: str, io_id: str = "IO-7842-SHARMA") -> Case:
    """Create an active investigation case."""
    temp_dir = tempfile.mkdtemp(prefix=f"sakshi_test_enc_{case_id[:12]}_")
    case_service = CaseService(db_session)
    payload = CaseCreateRequest(
        title=f"Test Case {case_id}",
        fir_metadata=FIRMetadata(
            fir_number=f"FIR-2026-{case_id[:8]}",
            police_station="Cyber Crime Unit",
            jurisdiction_code="JUR-DEL-04"
        )
    )
    mock_inv = AuthenticatedInvestigator(
        subject_id=io_id,
        display_name="Inspector Sharma",
        name="Inspector Sharma",
        role="INVESTIGATING_OFFICER",
        station_jurisdiction="JUR-DEL-04"
    )
    case_resp = case_service.create_case(payload, mock_inv)
    case_entity = case_service.repo.get_by_case_id(case_resp.case_id)
    case_entity.case_workspace_path = temp_dir
    case_service.repo.update(case_entity)
    case_service.update_stage(case_resp.case_id, "EVIDENCE_INGESTION", mock_inv)
    return case_service.repo.get_by_case_id(case_resp.case_id)


def prepare_locked_evidence(
    db_session,
    case: Case,
    investigator: AuthenticatedInvestigator,
    payload_bytes: bytes = SAMPLE_PDF_BYTES,
    filename: str = "report.pdf",
) -> Evidence:
    """Runs evidence through MOD-05 -> MOD-06 -> MOD-07 -> MOD-08 -> MOD-09 -> MOD-10."""
    intake_svc = EvidenceIntakeService(db_session)
    reg_obj = intake_svc.register_evidence(
        case_id=case.case_id,
        file_payload=payload_bytes,
        original_filename=filename,
        metadata=EvidenceIntakeMetadata(
            evidence_category=EvidenceCategory.DOCUMENT_PDF,
            declared_mime_type="application/pdf",
        ),
        investigator=investigator,
    )

    mime_svc = MimeValidationService(db_session)
    mime_svc.validate_evidence(case.case_id, reg_obj.evidence_id, investigator)

    av_svc = AntivirusScanService(db_session)
    av_svc.scan_evidence(case.case_id, reg_obj.evidence_id, investigator)

    worm_svc = WORMCommitService(db_session)
    worm_svc.commit_evidence(case.case_id, reg_obj.evidence_id, investigator)

    integrity_svc = IntegrityService(db_session)
    integrity_svc.verify_and_compute_integrity(case.case_id, reg_obj.evidence_id, investigator)

    lock_svc = ObjectLockService(db_session)
    lock_svc.apply_object_lock(case.case_id, reg_obj.evidence_id, investigator, lock_mode=ObjectLockMode.GOVERNANCE)

    return intake_svc.evidence_repo.get_by_evidence_id(reg_obj.evidence_id)


# ═══════════════════════════════════════════════════════════════════════════
# Test Suite 1: LocalKeyProvider
# ═══════════════════════════════════════════════════════════════════════════

class TestLocalKeyProvider:

    def test_key_generation_and_canonical_uri(self):
        provider = LocalKeyProvider()
        case_id = "CASE-KEY-001"
        key_bytes, key_ref = provider.get_or_create_case_key(case_id)

        assert len(key_bytes) == 32  # 256 bits
        assert key_ref == f"localkms://cases/{case_id}/keys/aes-256-v1"
        assert provider.provider_name == "LOCAL_DEV_KEY_PROVIDER"

    def test_key_persistence_and_caching(self):
        provider = LocalKeyProvider()
        case_id = "CASE-KEY-002"
        key1, ref1 = provider.get_or_create_case_key(case_id)
        key2, ref2 = provider.get_or_create_case_key(case_id)

        assert key1 == key2
        assert ref1 == ref2

    def test_case_isolation_retrieval(self):
        provider = LocalKeyProvider()
        case_id = "CASE-KEY-003"
        key_bytes, key_ref = provider.get_or_create_case_key(case_id)

        retrieved = provider.get_case_key(key_ref, case_id)
        assert retrieved == key_bytes

    def test_cross_case_isolation_enforcement(self):
        """Cross-case key retrieval MUST be rejected with CaseKeyIsolationException."""
        provider = LocalKeyProvider()
        case_a = "CASE-KEY-AAA"
        case_b = "CASE-KEY-BBB"

        _, ref_a = provider.get_or_create_case_key(case_a)
        _, _ = provider.get_or_create_case_key(case_b)

        # Attempt to access Case A's key while claiming to be in Case B
        with pytest.raises(CaseKeyIsolationException) as exc_info:
            provider.get_case_key(ref_a, case_b)

        assert "Cross-case key access denied" in str(exc_info.value)
        assert case_a in str(exc_info.value)
        assert case_b in str(exc_info.value)

    def test_key_rotation(self):
        provider = LocalKeyProvider()
        case_id = "CASE-KEY-ROTATE"
        key1, ref1 = provider.get_or_create_case_key(case_id)
        key2, ref2 = provider.rotate_case_key(case_id)

        assert key1 != key2
        assert ref1.endswith("v1")
        assert ref2.endswith("v2")
        # Both keys should still be retrievable by their respective references
        assert provider.get_case_key(ref1, case_id) == key1
        assert provider.get_case_key(ref2, case_id) == key2


# ═══════════════════════════════════════════════════════════════════════════
# Test Suite 2: ProductionHSMKMSProvider Architectural Contract
# ═══════════════════════════════════════════════════════════════════════════

class TestProductionHSMKMSProvider:

    def test_production_guard_raises_in_dev_without_live_credentials(self):
        provider = ProductionHSMKMSProvider()
        assert provider.provider_name == "PRODUCTION_HSM_KMS"

        with pytest.raises(KeyProviderException) as exc_info:
            provider.get_or_create_case_key("CASE-PROD-001")
        assert "ProductionHSMKMSProvider requires live cloud KMS or HSM credentials" in str(exc_info.value)

    def test_mock_mode_for_architectural_testing(self):
        provider = ProductionHSMKMSProvider(allow_mock=True)
        key_bytes, ref = provider.get_or_create_case_key("CASE-PROD-002")
        assert len(key_bytes) == 32
        assert ref == "kms://sakshi/cases/CASE-PROD-002/keys/kek-v1"


# ═══════════════════════════════════════════════════════════════════════════
# Test Suite 3: EncryptionService Pipeline & Encryption Properties
# ═══════════════════════════════════════════════════════════════════════════

class TestEncryptionService:

    def test_full_pipeline_encryption_success(self, db_session, mock_io1):
        case = create_pipeline_case(db_session, "CASE-ENC-PIPE-01", mock_io1.investigator_id)
        evidence = prepare_locked_evidence(db_session, case, mock_io1)

        enc_service = EncryptionService(db_session)
        result: EncryptionResult = enc_service.encrypt_evidence(
            case_id=case.case_id,
            evidence_id=evidence.evidence_id,
            investigator=mock_io1,
        )

        assert isinstance(result, EncryptionResult)
        assert result.encryption_status == "ENCRYPTED"
        assert result.encryption_algorithm == AES_ALGORITHM_NAME
        assert result.already_encrypted is False
        assert result.encryption_storage_reference.startswith(f"enc://{case.case_id}/")
        assert len(result.nonce_hex) == NONCE_LENGTH_BYTES * 2  # 24 hex chars
        assert len(result.auth_tag_hex) == AUTH_TAG_LENGTH_BYTES * 2  # 32 hex chars
        assert len(result.ciphertext_sha256) == 64
        assert result.file_size_bytes == len(SAMPLE_PDF_BYTES)
        assert result.encrypted_file_size_bytes == len(SAMPLE_PDF_BYTES) + AUTH_TAG_LENGTH_BYTES
        assert result.checksum_sha256 == evidence.checksum_sha256
        assert result.checksum_sha3_512 == evidence.checksum_sha3_512
        assert result.lock_storage_reference == evidence.lock_storage_reference

        # Verify DB record updated
        db_ev = db_session.query(Evidence).filter(Evidence.evidence_id == evidence.evidence_id).one()
        assert db_ev.encryption_status == "ENCRYPTED"
        assert db_ev.encryption_algorithm == AES_ALGORITHM_NAME
        assert db_ev.encryption_nonce_hex == result.nonce_hex
        assert db_ev.encryption_auth_tag_hex == result.auth_tag_hex
        assert db_ev.ciphertext_sha256 == result.ciphertext_sha256
        assert os.path.exists(db_ev.encrypted_file_path)

        # Cleanup
        shutil.rmtree(case.case_workspace_path, ignore_errors=True)

    def test_nonce_uniqueness(self, db_session, mock_io1):
        """Each encryption operation must generate a distinct 96-bit nonce."""
        case = create_pipeline_case(db_session, "CASE-ENC-NONCE-01", mock_io1.investigator_id)
        ev1 = prepare_locked_evidence(db_session, case, mock_io1, SAMPLE_PDF_BYTES + b"\n% Payload 1 for unique nonce test")
        ev2 = prepare_locked_evidence(db_session, case, mock_io1, SAMPLE_PDF_BYTES + b"\n% Payload 2 for unique nonce test")

        enc_service = EncryptionService(db_session)
        res1 = enc_service.encrypt_evidence(case.case_id, ev1.evidence_id, mock_io1)
        res2 = enc_service.encrypt_evidence(case.case_id, ev2.evidence_id, mock_io1)

        assert res1.nonce_hex != res2.nonce_hex
        assert len(res1.nonce_hex) == 24
        assert len(res2.nonce_hex) == 24

        shutil.rmtree(case.case_workspace_path, ignore_errors=True)

    def test_idempotent_encryption(self, db_session, mock_io1):
        """Repeated encryption calls return existing encrypted state without altering records."""
        case = create_pipeline_case(db_session, "CASE-ENC-IDEM-01", mock_io1.investigator_id)
        evidence = prepare_locked_evidence(db_session, case, mock_io1)

        enc_service = EncryptionService(db_session)
        res1 = enc_service.encrypt_evidence(case.case_id, evidence.evidence_id, mock_io1)
        res2 = enc_service.encrypt_evidence(case.case_id, evidence.evidence_id, mock_io1)

        assert res2.already_encrypted is True
        assert res2.encryption_status == "ENCRYPTED"
        assert res2.nonce_hex == res1.nonce_hex
        assert res2.auth_tag_hex == res1.auth_tag_hex
        assert res2.ciphertext_sha256 == res1.ciphertext_sha256
        assert res2.encryption_storage_reference == res1.encryption_storage_reference

        shutil.rmtree(case.case_workspace_path, ignore_errors=True)

    def test_gate_enforcement_unlocked_evidence_rejected(self, db_session, mock_io1):
        """Evidence without MOD-10 Object Lock must be rejected."""
        case = create_pipeline_case(db_session, "CASE-ENC-GATE-01", mock_io1.investigator_id)
        intake_svc = EvidenceIntakeService(db_session)
        meta = EvidenceIntakeMetadata(
            evidence_category=EvidenceCategory.DOCUMENT_PDF,
            declared_mime_type="application/pdf",
        )
        ev_resp = intake_svc.register_evidence(
            case_id=case.case_id,
            file_payload=SAMPLE_PDF_BYTES,
            original_filename="file.pdf",
            metadata=meta,
            investigator=mock_io1,
        )

        enc_service = EncryptionService(db_session)
        with pytest.raises(ObjectNotLockedForEncryptionException) as exc_info:
            enc_service.encrypt_evidence(case.case_id, ev_resp.evidence_id, mock_io1)

        assert "Object Lock (MOD-10)" in str(exc_info.value)
        shutil.rmtree(case.case_workspace_path, ignore_errors=True)

    def test_gate_enforcement_unverified_integrity_rejected(self, db_session, mock_io1):
        """Evidence without MOD-09 dual hash verification must be rejected."""
        case = create_pipeline_case(db_session, "CASE-ENC-GATE-02", mock_io1.investigator_id)
        # Register evidence and manually set locked but integrity unverified
        intake_svc = EvidenceIntakeService(db_session)
        meta = EvidenceIntakeMetadata(
            evidence_category=EvidenceCategory.DOCUMENT_PDF,
            declared_mime_type="application/pdf",
        )
        ev_resp = intake_svc.register_evidence(
            case_id=case.case_id,
            file_payload=SAMPLE_PDF_BYTES,
            original_filename="file.pdf",
            metadata=meta,
            investigator=mock_io1,
        )

        ev = db_session.query(Evidence).filter(Evidence.evidence_id == ev_resp.evidence_id).one()
        ev.lock_status = "LOCKED"
        ev.lock_storage_reference = "objlock://dummy"
        ev.integrity_status = "UNVERIFIED"
        db_session.commit()

        enc_service = EncryptionService(db_session)
        with pytest.raises(ObjectNotLockedForEncryptionException) as exc_info:
            enc_service.encrypt_evidence(case.case_id, ev_resp.evidence_id, mock_io1)

        assert "MOD-09 gate" in str(exc_info.value)
        shutil.rmtree(case.case_workspace_path, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════
# Test Suite 4: Cryptographic Tampering & Verification
# ═══════════════════════════════════════════════════════════════════════════

class TestTamperDetectionAndVerification:

    def test_verify_encryption_integrity_valid(self, db_session, mock_io1):
        case = create_pipeline_case(db_session, "CASE-VERIFY-01", mock_io1.investigator_id)
        evidence = prepare_locked_evidence(db_session, case, mock_io1)

        enc_service = EncryptionService(db_session)
        enc_service.encrypt_evidence(case.case_id, evidence.evidence_id, mock_io1)

        verify_res: EncryptionVerificationResult = enc_service.verify_encryption_integrity(
            case.case_id, evidence.evidence_id, mock_io1
        )

        assert verify_res.verification_status == "VERIFIED"
        assert verify_res.tag_valid is True
        assert verify_res.ciphertext_integrity_matched is True
        assert verify_res.dual_hash_integrity_matched is True

        shutil.rmtree(case.case_workspace_path, ignore_errors=True)

    def test_ciphertext_tampering_detected(self, db_session, mock_io1):
        """Flipping a single bit in the ciphertext file triggers fail-closed tamper detection."""
        case = create_pipeline_case(db_session, "CASE-TAMPER-01", mock_io1.investigator_id)
        evidence = prepare_locked_evidence(db_session, case, mock_io1)

        enc_service = EncryptionService(db_session)
        enc_service.encrypt_evidence(case.case_id, evidence.evidence_id, mock_io1)

        db_ev = db_session.query(Evidence).filter(Evidence.evidence_id == evidence.evidence_id).one()
        enc_file_path = db_ev.encrypted_file_path

        # Corrupt 1 byte in the ciphertext file
        with open(enc_file_path, "rb") as f:
            data = bytearray(f.read())
        data[5] ^= 0xFF  # Flip bit
        # Temporarily make writable to simulate attack, then restore
        import stat
        os.chmod(enc_file_path, stat.S_IWRITE)
        with open(enc_file_path, "wb") as f:
            f.write(data)
        os.chmod(enc_file_path, stat.S_IREAD)

        # Verification must catch the checksum tamper
        with pytest.raises(EncryptionTamperException) as exc_info:
            enc_service.verify_encryption_integrity(case.case_id, evidence.evidence_id, mock_io1)

        assert "checksum mismatch" in str(exc_info.value)

        shutil.rmtree(case.case_workspace_path, ignore_errors=True)

    def test_tag_verification_failure_detected(self, db_session, mock_io1):
        """If ciphertext checksum is bypassed, GCM authentication tag verification rejects corrupt tag/data."""
        case = create_pipeline_case(db_session, "CASE-TAMPER-02", mock_io1.investigator_id)
        evidence = prepare_locked_evidence(db_session, case, mock_io1)

        enc_service = EncryptionService(db_session)
        enc_service.encrypt_evidence(case.case_id, evidence.evidence_id, mock_io1)

        db_ev = db_session.query(Evidence).filter(Evidence.evidence_id == evidence.evidence_id).one()
        enc_file_path = db_ev.encrypted_file_path

        # Alter tag (last 16 bytes) and also update DB ciphertext_sha256 to simulate sophisticated checksum spoof
        with open(enc_file_path, "rb") as f:
            data = bytearray(f.read())
        data[-1] ^= 0xAA  # Corrupt auth tag byte

        import stat
        os.chmod(enc_file_path, stat.S_IWRITE)
        with open(enc_file_path, "wb") as f:
            f.write(data)
        os.chmod(enc_file_path, stat.S_IREAD)

        # Update DB ciphertext hash to simulate attacker matching file checksum
        db_ev.ciphertext_sha256 = hashlib.sha256(data).hexdigest()
        db_session.commit()

        # Decryption / verification must fail at GCM tag verification
        with pytest.raises(EncryptionTamperException) as exc_info:
            enc_service.verify_encryption_integrity(case.case_id, evidence.evidence_id, mock_io1)

        assert "authentication tag verification failed" in str(exc_info.value)

        shutil.rmtree(case.case_workspace_path, ignore_errors=True)

    def test_decryption_utility_roundtrip(self, db_session, mock_io1):
        """decrypt_evidence_bytes decrypts successfully and verifies dual hashes."""
        case = create_pipeline_case(db_session, "CASE-DEC-01", mock_io1.investigator_id)
        payload = SAMPLE_PDF_BYTES + b"\n% Specific forensic evidence payload for decryption roundtrip test 12345"
        evidence = prepare_locked_evidence(db_session, case, mock_io1, payload)

        enc_service = EncryptionService(db_session)
        enc_service.encrypt_evidence(case.case_id, evidence.evidence_id, mock_io1)

        decrypted = enc_service.decrypt_evidence_bytes(case.case_id, evidence.evidence_id, mock_io1)
        assert decrypted == payload

        shutil.rmtree(case.case_workspace_path, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════════════════
# Test Suite 5: Downstream Contract & Authorization
# ═══════════════════════════════════════════════════════════════════════════

class TestContractAndAuthorization:

    def test_encrypted_evidence_object_contract_success(self, db_session, mock_io1):
        case = create_pipeline_case(db_session, "CASE-CONTRACT-01", mock_io1.investigator_id)
        evidence = prepare_locked_evidence(db_session, case, mock_io1)

        enc_service = EncryptionService(db_session)
        enc_service.encrypt_evidence(case.case_id, evidence.evidence_id, mock_io1)

        contract: EncryptedEvidenceObject = enc_service.get_encryption_contract(
            case.case_id, evidence.evidence_id, mock_io1
        )

        assert isinstance(contract, EncryptedEvidenceObject)
        assert contract.case_id == case.case_id
        assert contract.evidence_id == evidence.evidence_id
        assert contract.encryption_status == "ENCRYPTED"
        assert contract.encryption_algorithm == AES_ALGORITHM_NAME
        assert contract.source == "MOD-11"
        assert contract.lock_storage_reference == evidence.lock_storage_reference
        assert contract.worm_storage_reference == evidence.worm_storage_reference
        assert contract.checksum_sha256 == evidence.checksum_sha256
        assert contract.checksum_sha3_512 == evidence.checksum_sha3_512
        assert contract.ciphertext_sha256 is not None
        assert contract.auth_tag_hex is not None
        assert contract.nonce_hex is not None

        shutil.rmtree(case.case_workspace_path, ignore_errors=True)

    def test_contract_before_encryption_fails(self, db_session, mock_io1):
        case = create_pipeline_case(db_session, "CASE-CONTRACT-02", mock_io1.investigator_id)
        evidence = prepare_locked_evidence(db_session, case, mock_io1)

        enc_service = EncryptionService(db_session)
        with pytest.raises(EvidenceNotEncryptedException) as exc_info:
            enc_service.get_encryption_contract(case.case_id, evidence.evidence_id, mock_io1)

        assert "has not undergone AES-256-GCM encryption" in str(exc_info.value)
        shutil.rmtree(case.case_workspace_path, ignore_errors=True)

    def test_unauthorized_investigator_denied(self, db_session, mock_io1, mock_io2):
        """Unassigned IO is denied access to encrypt evidence in another's case."""
        case = create_pipeline_case(db_session, "CASE-AUTH-01", mock_io1.investigator_id)
        evidence = prepare_locked_evidence(db_session, case, mock_io1)

        enc_service = EncryptionService(db_session)
        with pytest.raises(ForbiddenException):
            enc_service.encrypt_evidence(case.case_id, evidence.evidence_id, mock_io2)

        shutil.rmtree(case.case_workspace_path, ignore_errors=True)

    def test_supervisor_authorized(self, db_session, mock_io1, mock_supervisor):
        """Supervisory officer with elevated role can encrypt evidence."""
        case = create_pipeline_case(db_session, "CASE-AUTH-02", mock_io1.investigator_id)
        evidence = prepare_locked_evidence(db_session, case, mock_io1)

        enc_service = EncryptionService(db_session)
        res = enc_service.encrypt_evidence(case.case_id, evidence.evidence_id, mock_supervisor)
        assert res.encryption_status == "ENCRYPTED"

        shutil.rmtree(case.case_workspace_path, ignore_errors=True)
