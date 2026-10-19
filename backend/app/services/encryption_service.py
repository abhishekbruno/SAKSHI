"""
MOD-11: AES-256-GCM Encryption Service for SAKSHI Investigation Platform.
Phase 3 — Security & Integrity.

Consumes:
    ObjectLockedEvidenceObject (from MOD-10 WORM Object Lock — lock_status == 'LOCKED')
Produces:
    EncryptedEvidenceObject (downstream handoff contract for MOD-12 TLS 1.3 / mTLS)

Core Responsibilities:
    1. Strict MOD-10 Gate: Evidence must have lock_status == 'LOCKED' and
       integrity_status == 'VERIFIED' (MOD-09) with dual hashes present.
    2. AES-256-GCM Authenticated Encryption: Symmetric encryption providing both
       confidentiality and cryptographic tamper-detection.
    3. Secure Nonce Generation: 96-bit (12 bytes) cryptographically secure random
       nonce generated per encryption via os.urandom.
    4. Authenticated Associated Data (AAD): Cryptographically binds ciphertext to
       case_id, evidence_id, and dual hashes (SHA-256 + SHA3-512).
    5. Authentication Tag Verification: 128-bit (16 bytes) GCM authentication tag
       verified during decryption/audit. Any modification raises EncryptionTamperException.
    6. Case-Scoped Key Isolation: Keys are strictly isolated per case via pluggable
       IKeyProvider (LocalKeyProvider for dev/test; ProductionHSMKMSProvider for cloud).
       Cross-case key access fails-closed with CaseKeyIsolationException.
    7. Decryption & Round-Trip Integrity: Trial decryption confirms decrypted bytes
       match established MOD-08/MOD-09 dual hashes.
    8. Deterministic Idempotency: Repeated encryption requests return existing
       encrypted state safely.
    9. Fail-Closed Behaviour: Any corruption, tag mismatch, key mismatch, or boundary
       violation immediately halts processing and logs security audit alerts.
    10. Downstream Contract: Produces EncryptedEvidenceObject for MOD-12.
"""
import os
import stat
import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

from app.models.case import Case
from app.models.evidence import Evidence
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.core.security import AuthenticatedInvestigator
from app.core.errors import (
    CaseNotFoundException,
    EvidenceNotFoundException,
    EvidenceFileNotFoundException,
    ForbiddenException,
    ObjectNotLockedForEncryptionException,
    EvidenceNotEncryptedException,
    EncryptionFailedException,
    DecryptionFailedException,
    EncryptionTamperException,
    CaseKeyIsolationException,
    KeyProviderException,
)
from app.core.logging import log_event
from app.services.auth_service import IAuthorizationService, authorization_service
from app.services.audit_integration import AuditIntegrationService
from app.services.key_provider import IKeyProvider, LocalKeyProvider
from app.schemas.evidence import (
    EncryptionResult,
    EncryptedEvidenceObject,
    EncryptionVerificationResult,
)

logger = logging.getLogger("sakshi.mod11.encryption")

ENCRYPTED_DIR_NAME = ".encrypted"
AES_ALGORITHM_NAME = "AES-256-GCM"
NONCE_LENGTH_BYTES = 12  # 96 bits standard for AES-GCM
AUTH_TAG_LENGTH_BYTES = 16  # 128 bits standard for AES-GCM


class EncryptionService:
    """
    MOD-11: AES-256-GCM Encryption Service.

    Consumes ObjectLockedEvidenceObject from MOD-10 and produces
    EncryptedEvidenceObject downstream handoff contract for MOD-12.
    """

    def __init__(
        self,
        db: Session,
        key_provider: Optional[IKeyProvider] = None,
        authz: Optional[IAuthorizationService] = None,
    ):
        self.db = db
        self.case_repo = CaseRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.authz = authz or authorization_service
        self.key_provider = key_provider or LocalKeyProvider()

    def encrypt_evidence(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> EncryptionResult:
        """
        Apply AES-256-GCM authenticated encryption to an ObjectLockedEvidenceObject.

        Pipeline Workflow:
            1. Validate Case Existence.
            2. RBAC/ABAC Authorization ('evidence:encrypt').
            3. Retrieve Evidence Record & Verify Case Containment.
            4. Strict MOD-10 Gate: evidence.lock_status == 'LOCKED' AND
               evidence.integrity_status == 'VERIFIED' with dual hashes present.
            5. Idempotency Check: if already ENCRYPTED, return existing state.
            6. Physical Payload Boundary Containment (canonical realpath within case workspace).
            7. Pre-Encryption Verification: verify source payload bytes match established dual hashes.
            8. Emit EVIDENCE_ENCRYPTION_STARTED audit event.
            9. Key Retrieval: Obtain case-scoped 256-bit AES key via IKeyProvider.
            10. Nonce Generation: Generate 96-bit (12 bytes) cryptographically secure random nonce.
            11. Associated Authenticated Data (AAD): Construct canonical binding string.
            12. Authenticated Encryption: Encrypt plaintext bytes using AESGCM.
            13. Ciphertext Storage: Atomically write ciphertext into `<case_workspace>/.encrypted/`.
            14. Trial Decryption Test: Immediate in-memory round-trip integrity verification.
            15. Atomic DB State Transition:
                - encryption_status → ENCRYPTED
                - algorithm, key_reference, key_provider, storage_ref, nonce, tag, aad, hashes
            16. Append structured event to encryption_event_log.
            17. Emit EVIDENCE_ENCRYPTED audit event.
            18. Return EncryptionResult.
        """
        # 1. Validate Case Existence
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        # 2. RBAC/ABAC Authorization
        self.authz.check_can_encrypt_evidence(investigator, case)

        # 3. Retrieve Evidence Record & Verify Case Containment
        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        # 4. Strict MOD-10 Gate: Evidence must be locked and integrity-verified
        if evidence.lock_status != "LOCKED" or not evidence.lock_storage_reference:
            raise ObjectNotLockedForEncryptionException(
                f"Evidence '{evidence_id}' has not been placed under Object Lock (MOD-10). "
                f"Current lock_status: '{evidence.lock_status}'. "
                f"AES-256-GCM encryption requires evidence to be ObjectLocked first."
            )

        if (evidence.integrity_status != "VERIFIED"
                or not evidence.checksum_sha256
                or not evidence.checksum_sha3_512):
            raise ObjectNotLockedForEncryptionException(
                f"Evidence '{evidence_id}' integrity is not verified (MOD-09 gate). "
                f"Dual hashes (SHA-256 and SHA3-512) must be VERIFIED prior to encryption."
            )

        # 5. Idempotency Check: Already Encrypted?
        if evidence.encryption_status == "ENCRYPTED" and evidence.encryption_storage_reference:
            return self._build_result(evidence, already_encrypted=True)

        # 6. Physical Payload Boundary Containment
        staged_path = evidence.raw_storage_path
        if not os.path.exists(staged_path):
            raise EvidenceFileNotFoundException(staged_path)

        canonical_payload_path = os.path.realpath(staged_path)
        canonical_workspace_path = os.path.realpath(case.case_workspace_path)

        if (not canonical_payload_path.startswith(canonical_workspace_path + os.sep)
                and canonical_payload_path != canonical_workspace_path):
            log_event(
                event_type="WORKSPACE_BOUNDARY_VIOLATION",
                message=(
                    f"MOD-11: Evidence path '{canonical_payload_path}' escapes case "
                    f"workspace '{canonical_workspace_path}'."
                ),
                case_id=case_id,
                investigator_id=investigator.investigator_id,
            )
            evidence.encryption_status = "ENCRYPTION_FAILED"
            evidence.encryption_failure_reason = "Storage path violates case workspace boundary containment."
            self.evidence_repo.update(evidence)
            raise ForbiddenException(
                "Evidence storage path violates case workspace boundary containment."
            )

        # 7. Read source bytes & Pre-Encryption Verification
        try:
            with open(canonical_payload_path, "rb") as f:
                plaintext_bytes = f.read()
        except Exception as e:
            raise EncryptionFailedException(f"Failed to read evidence payload for encryption: {e}")

        recomputed_sha256 = hashlib.sha256(plaintext_bytes).hexdigest()
        recomputed_sha3_512 = hashlib.sha3_512(plaintext_bytes).hexdigest()

        if recomputed_sha256.lower() != evidence.checksum_sha256.lower():
            log_event(
                event_type="INTEGRITY_TAMPER_PRE_ENCRYPTION",
                message=f"Pre-encryption SHA-256 mismatch for evidence {evidence_id}",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
            )
            raise EncryptionTamperException(
                f"Pre-encryption SHA-256 verification failed: expected '{evidence.checksum_sha256}', "
                f"computed '{recomputed_sha256}'."
            )

        if recomputed_sha3_512.lower() != evidence.checksum_sha3_512.lower():
            log_event(
                event_type="INTEGRITY_TAMPER_PRE_ENCRYPTION",
                message=f"Pre-encryption SHA3-512 mismatch for evidence {evidence_id}",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
            )
            raise EncryptionTamperException(
                f"Pre-encryption SHA3-512 verification failed: expected '{evidence.checksum_sha3_512}', "
                f"computed '{recomputed_sha3_512}'."
            )

        # 8. Emit Audit: Encryption Started
        AuditIntegrationService.record_event(
            action="EVIDENCE_ENCRYPTION_STARTED",
            investigator_id=investigator.investigator_id,
            case_id=case.case_id,
            details={
                "evidence_id": evidence.evidence_id,
                "case_id": case.case_id,
                "algorithm": AES_ALGORITHM_NAME,
                "lock_storage_reference": evidence.lock_storage_reference,
                "sha256": evidence.checksum_sha256,
                "sha3_512": evidence.checksum_sha3_512,
            },
        )

        try:
            # 9. Key Retrieval (Case-Scoped Isolation)
            key_bytes, key_reference = self.key_provider.get_or_create_case_key(
                case_id=case.case_id,
                case_workspace_path=case.case_workspace_path,
            )

            # 10. Nonce Generation: 96-bit (12 bytes) secure random
            nonce = os.urandom(NONCE_LENGTH_BYTES)

            # 11. Associated Authenticated Data (AAD): Cryptographically bind case & evidence metadata
            aad_str = (
                f"case_id={case.case_id}|"
                f"evidence_id={evidence.evidence_id}|"
                f"sha256={evidence.checksum_sha256.lower()}|"
                f"sha3_512={evidence.checksum_sha3_512.lower()}"
            )
            aad_bytes = aad_str.encode("utf-8")

            # 12. Authenticated Encryption via AESGCM
            aesgcm = AESGCM(key_bytes)
            # aesgcm.encrypt returns ciphertext + 16-byte authentication tag
            ciphertext_and_tag = aesgcm.encrypt(nonce, plaintext_bytes, aad_bytes)

            auth_tag = ciphertext_and_tag[-AUTH_TAG_LENGTH_BYTES:]
            ciphertext_only = ciphertext_and_tag[:-AUTH_TAG_LENGTH_BYTES]
            ciphertext_sha256 = hashlib.sha256(ciphertext_and_tag).hexdigest()

            # 13. Ciphertext Storage in isolated .encrypted/ directory
            encrypted_dir = os.path.join(canonical_workspace_path, ENCRYPTED_DIR_NAME)
            os.makedirs(encrypted_dir, exist_ok=True)

            enc_filename = f"{evidence.evidence_id}.{ciphertext_sha256[:16]}.enc"
            encrypted_file_path = os.path.join(encrypted_dir, enc_filename)

            # Atomic file write
            tmp_enc_path = encrypted_file_path + ".tmp"
            with open(tmp_enc_path, "wb") as f:
                f.write(ciphertext_and_tag)
            os.replace(tmp_enc_path, encrypted_file_path)

            # Read-only permission stripping
            try:
                os.chmod(encrypted_file_path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            except Exception as e:
                logger.warning("Could not set read-only permissions on encrypted file: %s", e)

            # 14. Trial Decryption Test (In-memory round-trip verification)
            trial_decrypted = aesgcm.decrypt(nonce, ciphertext_and_tag, aad_bytes)
            if trial_decrypted != plaintext_bytes:
                raise EncryptionFailedException("Trial decryption payload mismatch during self-verification.")

            trial_sha256 = hashlib.sha256(trial_decrypted).hexdigest()
            if trial_sha256.lower() != evidence.checksum_sha256.lower():
                raise EncryptionFailedException("Trial decryption SHA-256 mismatch during self-verification.")

            # Construct canonical storage reference
            encryption_storage_reference = (
                f"enc://{case.case_id}/{evidence.checksum_sha256[:16]}+{nonce.hex()[:16]}"
            )
            now = datetime.now(timezone.utc)

            # 15. Atomic DB State Transition
            evidence.encryption_status = "ENCRYPTED"
            evidence.encryption_algorithm = AES_ALGORITHM_NAME
            evidence.encryption_key_reference = key_reference
            evidence.encryption_key_provider = self.key_provider.provider_name
            evidence.encryption_storage_reference = encryption_storage_reference
            evidence.encryption_nonce_hex = nonce.hex()
            evidence.encryption_auth_tag_hex = auth_tag.hex()
            evidence.encryption_aad = aad_str
            evidence.ciphertext_sha256 = ciphertext_sha256
            evidence.encrypted_file_size_bytes = len(ciphertext_and_tag)
            evidence.encrypted_file_path = encrypted_file_path
            evidence.encrypted_at = now
            evidence.encryption_failure_reason = None

            # 16. Append to encryption_event_log
            event_entry = {
                "event": "ENCRYPTION_APPLIED",
                "timestamp": now.isoformat(),
                "investigator_id": investigator.investigator_id,
                "algorithm": AES_ALGORITHM_NAME,
                "key_reference": key_reference,
                "key_provider": self.key_provider.provider_name,
                "encryption_storage_reference": encryption_storage_reference,
                "nonce_hex": nonce.hex(),
                "auth_tag_hex": auth_tag.hex(),
                "ciphertext_sha256": ciphertext_sha256,
                "encrypted_file_size_bytes": len(ciphertext_and_tag),
            }
            existing_log = []
            if evidence.encryption_event_log:
                try:
                    existing_log = json.loads(evidence.encryption_event_log)
                except Exception:
                    existing_log = []
            existing_log.append(event_entry)
            evidence.encryption_event_log = json.dumps(existing_log, ensure_ascii=False)

            self.evidence_repo.update(evidence)

            # 17. Structured Audit Event
            AuditIntegrationService.record_event(
                action="EVIDENCE_ENCRYPTED",
                investigator_id=investigator.investigator_id,
                case_id=case.case_id,
                details={
                    "evidence_id": evidence.evidence_id,
                    "case_id": case.case_id,
                    "algorithm": AES_ALGORITHM_NAME,
                    "key_reference": key_reference,
                    "key_provider": self.key_provider.provider_name,
                    "encryption_storage_reference": encryption_storage_reference,
                    "nonce_hex": nonce.hex(),
                    "auth_tag_hex": auth_tag.hex(),
                    "ciphertext_sha256": ciphertext_sha256,
                    "encrypted_file_size_bytes": len(ciphertext_and_tag),
                },
            )
            log_event(
                event_type="ENCRYPTION_SUCCESS",
                message=f"AES-256-GCM encryption applied to evidence {evidence_id} in case {case_id}",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
            )

            # 18. Return EncryptionResult
            return self._build_result(evidence, already_encrypted=False)

        except (ObjectNotLockedForEncryptionException, ForbiddenException, EncryptionTamperException):
            raise
        except Exception as e:
            logger.error("Encryption operation failed for evidence %s: %s", evidence_id, e, exc_info=True)
            evidence.encryption_status = "ENCRYPTION_FAILED"
            evidence.encryption_failure_reason = f"{type(e).__name__}: {str(e)}"
            self.evidence_repo.update(evidence)

            AuditIntegrationService.record_event(
                action="EVIDENCE_ENCRYPTION_FAILED",
                investigator_id=investigator.investigator_id,
                case_id=case.case_id,
                details={
                    "evidence_id": evidence.evidence_id,
                    "case_id": case.case_id,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise EncryptionFailedException(f"AES-256-GCM encryption failed: {e}")

    def verify_encryption_integrity(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> EncryptionVerificationResult:
        """
        Verify the cryptographic integrity of an encrypted evidence object.

        Checks:
            1. Evidence existence and authorization.
            2. Evidence must have encryption_status == 'ENCRYPTED'.
            3. Encrypted ciphertext file exists on disk.
            4. Ciphertext file SHA-256 matches stored ciphertext_sha256.
            5. Case-scoped key retrieval via IKeyProvider.
            6. AES-256-GCM authentication tag verification via trial decryption.
            7. Decrypted payload matches established dual hashes (SHA-256 and SHA3-512).

        Fail-Closed:
            Any tag mismatch or byte tampering raises EncryptionTamperException
            and emits an audit alert.
        """
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        self.authz.check_can_encrypt_evidence(investigator, case)

        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        if evidence.encryption_status != "ENCRYPTED" or not evidence.encrypted_file_path:
            raise EvidenceNotEncryptedException(
                f"Evidence '{evidence_id}' is not in ENCRYPTED state (current: '{evidence.encryption_status}')."
            )

        enc_path = evidence.encrypted_file_path
        if not os.path.exists(enc_path):
            raise EvidenceFileNotFoundException(enc_path)

        # 1. Read ciphertext bytes
        with open(enc_path, "rb") as f:
            ciphertext_and_tag = f.read()

        # 2. Verify ciphertext file SHA-256
        computed_cipher_sha256 = hashlib.sha256(ciphertext_and_tag).hexdigest()
        ciphertext_integrity_matched = (
            computed_cipher_sha256.lower() == (evidence.ciphertext_sha256 or "").lower()
        )
        if not ciphertext_integrity_matched:
            AuditIntegrationService.record_event(
                action="ENCRYPTION_CIPHERTEXT_TAMPER_DETECTED",
                investigator_id=investigator.investigator_id,
                case_id=case_id,
                details={
                    "evidence_id": evidence_id,
                    "expected_sha256": evidence.ciphertext_sha256,
                    "computed_sha256": computed_cipher_sha256,
                },
            )
            raise EncryptionTamperException(
                f"Encrypted payload ciphertext checksum mismatch for evidence '{evidence_id}'."
            )

        # 3. Retrieve Case Key
        key_bytes = self.key_provider.get_case_key(
            key_reference=evidence.encryption_key_reference,
            case_id=case_id,
            case_workspace_path=case.case_workspace_path,
        )

        # 4. Authenticated Decryption Tag Verification
        nonce = bytes.fromhex(evidence.encryption_nonce_hex)
        aad_bytes = (evidence.encryption_aad or "").encode("utf-8")

        aesgcm = AESGCM(key_bytes)
        try:
            decrypted_bytes = aesgcm.decrypt(nonce, ciphertext_and_tag, aad_bytes)
            tag_valid = True
        except InvalidTag:
            AuditIntegrationService.record_event(
                action="ENCRYPTION_TAG_MISMATCH_TAMPER_DETECTED",
                investigator_id=investigator.investigator_id,
                case_id=case_id,
                details={
                    "evidence_id": evidence_id,
                    "key_reference": evidence.encryption_key_reference,
                    "nonce_hex": evidence.encryption_nonce_hex,
                },
            )
            raise EncryptionTamperException(
                f"AES-256-GCM authentication tag verification failed for evidence '{evidence_id}'. "
                f"Ciphertext, nonce, or AAD has been tampered with."
            )

        # 5. Dual-Hash Plaintext Verification
        dec_sha256 = hashlib.sha256(decrypted_bytes).hexdigest()
        dec_sha3_512 = hashlib.sha3_512(decrypted_bytes).hexdigest()

        dual_hash_matched = (
            dec_sha256.lower() == evidence.checksum_sha256.lower()
            and dec_sha3_512.lower() == evidence.checksum_sha3_512.lower()
        )
        if not dual_hash_matched:
            raise EncryptionTamperException(
                f"Decrypted payload dual-hash mismatch for evidence '{evidence_id}'."
            )

        now = datetime.now(timezone.utc)
        return EncryptionVerificationResult(
            evidence_id=evidence.evidence_id,
            case_id=case.case_id,
            encryption_status=evidence.encryption_status,
            verification_status="VERIFIED",
            tag_valid=tag_valid,
            ciphertext_integrity_matched=ciphertext_integrity_matched,
            dual_hash_integrity_matched=dual_hash_matched,
            key_reference=evidence.encryption_key_reference,
            verified_at=now,
            message="AES-256-GCM encryption verified: authentication tag, ciphertext hash, and dual-hash integrity validated.",
        )

    def decrypt_evidence_bytes(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> bytes:
        """
        Internal authorized decryption helper.
        Enforces case key isolation, verifies GCM authentication tag,
        and confirms dual-hash match before returning raw bytes.
        """
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        self.authz.check_can_decrypt_evidence(investigator, case)

        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        if evidence.encryption_status != "ENCRYPTED" or not evidence.encrypted_file_path:
            raise EvidenceNotEncryptedException(
                f"Evidence '{evidence_id}' has not been encrypted under MOD-11."
            )

        enc_path = evidence.encrypted_file_path
        if not os.path.exists(enc_path):
            raise EvidenceFileNotFoundException(enc_path)

        with open(enc_path, "rb") as f:
            ciphertext_and_tag = f.read()

        # Enforce Case Key Isolation
        key_bytes = self.key_provider.get_case_key(
            key_reference=evidence.encryption_key_reference,
            case_id=case_id,
            case_workspace_path=case.case_workspace_path,
        )

        nonce = bytes.fromhex(evidence.encryption_nonce_hex)
        aad_bytes = (evidence.encryption_aad or "").encode("utf-8")

        aesgcm = AESGCM(key_bytes)
        try:
            plaintext = aesgcm.decrypt(nonce, ciphertext_and_tag, aad_bytes)
        except InvalidTag:
            AuditIntegrationService.record_event(
                action="DECRYPTION_FAILED_INVALID_TAG",
                investigator_id=investigator.investigator_id,
                case_id=case_id,
                details={"evidence_id": evidence_id},
            )
            raise EncryptionTamperException(
                f"Decryption failed: AES-256-GCM authentication tag verification failed for evidence '{evidence_id}'."
            )

        # Verify dual hashes
        if hashlib.sha256(plaintext).hexdigest().lower() != evidence.checksum_sha256.lower():
            raise EncryptionTamperException("Decrypted bytes failed SHA-256 integrity verification.")
        if hashlib.sha3_512(plaintext).hexdigest().lower() != evidence.checksum_sha3_512.lower():
            raise EncryptionTamperException("Decrypted bytes failed SHA3-512 integrity verification.")

        AuditIntegrationService.record_event(
            action="EVIDENCE_DECRYPTED",
            investigator_id=investigator.investigator_id,
            case_id=case_id,
            details={
                "evidence_id": evidence_id,
                "key_reference": evidence.encryption_key_reference,
            },
        )
        return plaintext

    def get_encryption_contract(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> EncryptedEvidenceObject:
        """
        Export the EncryptedEvidenceObject downstream handoff contract for MOD-12 (TLS 1.3 / mTLS).

        Strict Invariants:
            - integrity_status == 'VERIFIED' (MOD-09)
            - lock_status == 'LOCKED' (MOD-10)
            - encryption_status == 'ENCRYPTED' (MOD-11)
        """
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        self.authz.check_can_encrypt_evidence(investigator, case)

        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        if evidence.encryption_status != "ENCRYPTED" or not evidence.encryption_storage_reference:
            raise EvidenceNotEncryptedException(
                f"Evidence '{evidence_id}' has not undergone AES-256-GCM encryption (MOD-11). "
                f"Downstream EncryptedEvidenceObject contract cannot be issued."
            )

        if evidence.lock_status != "LOCKED":
            raise ObjectNotLockedForEncryptionException(
                f"Evidence '{evidence_id}' is missing valid MOD-10 Object Lock."
            )

        return EncryptedEvidenceObject(
            case_id=case.case_id,
            evidence_id=evidence.evidence_id,
            original_file_name=evidence.original_file_name,
            evidence_category=evidence.evidence_category,
            file_size_bytes=evidence.file_size_bytes,
            encrypted_file_size_bytes=evidence.encrypted_file_size_bytes or 0,
            worm_storage_reference=evidence.worm_storage_reference or "",
            lock_storage_reference=evidence.lock_storage_reference or "",
            encryption_storage_reference=evidence.encryption_storage_reference,
            encryption_status=evidence.encryption_status,
            encryption_algorithm=evidence.encryption_algorithm or AES_ALGORITHM_NAME,
            key_reference=evidence.encryption_key_reference or "",
            key_provider=evidence.encryption_key_provider or self.key_provider.provider_name,
            nonce_hex=evidence.encryption_nonce_hex or "",
            auth_tag_hex=evidence.encryption_auth_tag_hex or "",
            aad_binding=evidence.encryption_aad or "",
            checksum_sha256=evidence.checksum_sha256 or "",
            checksum_sha3_512=evidence.checksum_sha3_512 or "",
            ciphertext_sha256=evidence.ciphertext_sha256 or "",
            encrypted_at=evidence.encrypted_at or datetime.now(timezone.utc),
            source="MOD-11",
        )

    def _build_result(self, evidence: Evidence, already_encrypted: bool) -> EncryptionResult:
        msg = (
            f"Evidence '{evidence.evidence_id}' was already encrypted under AES-256-GCM."
            if already_encrypted
            else f"Evidence '{evidence.evidence_id}' successfully encrypted under AES-256-GCM."
        )
        return EncryptionResult(
            evidence_id=evidence.evidence_id,
            case_id=evidence.case_id,
            encryption_status=evidence.encryption_status or "ENCRYPTED",
            encryption_algorithm=evidence.encryption_algorithm or AES_ALGORITHM_NAME,
            encryption_storage_reference=evidence.encryption_storage_reference or "",
            key_reference=evidence.encryption_key_reference or "",
            key_provider=evidence.encryption_key_provider or self.key_provider.provider_name,
            nonce_hex=evidence.encryption_nonce_hex or "",
            auth_tag_hex=evidence.encryption_auth_tag_hex or "",
            aad_binding=evidence.encryption_aad or "",
            ciphertext_sha256=evidence.ciphertext_sha256 or "",
            file_size_bytes=evidence.file_size_bytes,
            encrypted_file_size_bytes=evidence.encrypted_file_size_bytes or 0,
            encrypted_at=evidence.encrypted_at or datetime.now(timezone.utc),
            checksum_sha256=evidence.checksum_sha256 or "",
            checksum_sha3_512=evidence.checksum_sha3_512 or "",
            lock_storage_reference=evidence.lock_storage_reference or "",
            message=msg,
            already_encrypted=already_encrypted,
        )
