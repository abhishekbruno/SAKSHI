"""
MOD-09: Dual Hashing (SHA-256 + SHA3-512) & Integrity Verification Service.
Phase 3 — Security & Integrity.

Consumes:
    WORMCommittedEvidenceObject (from MOD-08 WORM Commit + Checksum)
Produces:
    IntegrityProtectedEvidenceObject (downstream handoff for subsequent Phase 3/4 modules)

Core Responsibilities:
    1. Consumes WORM-committed evidence from MOD-08 (requires worm_status == 'COMMITTED').
    2. Enforces case workspace path containment and canonicalization (rejects directory traversal).
    3. Executes streaming dual hashing in bounded 1 MB chunks without buffering entire files into RAM.
    4. Verifies recomputed SHA-256 digest against the established MOD-08 pre-hash (Fail-Closed).
    5. Computes authoritative 512-bit SHA3-512 digest (128 lowercase hexadecimal characters).
    6. Atomically updates evidence integrity status to 'VERIFIED' (or 'FAILED' on mismatch).
    7. Emits structured tamper-evident audit logs via AuditIntegrationService.
    8. Provides deterministic idempotency for repeated integrity verification requests.
    9. Exports the formal IntegrityProtectedEvidenceObject downstream handoff contract.
"""
import os
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.evidence import Evidence
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.core.security import AuthenticatedInvestigator
from app.core.errors import (
    CaseNotFoundException,
    EvidenceNotFoundException,
    EvidenceFileNotFoundException,
    EvidenceNotWORMCommittedException,
    SHA256IntegrityMismatchException,
    IntegrityVerificationFailedException,
    IntegrityNotVerifiedException,
    ForbiddenException,
)
from app.core.logging import log_event
from app.services.auth_service import IAuthorizationService, authorization_service
from app.services.audit_integration import AuditIntegrationService
from app.schemas.evidence import (
    EvidenceIntakeStatus,
    IntegrityVerificationResult,
    IntegrityProtectedEvidenceObject,
)

logger = logging.getLogger("sakshi.mod09.dual_hashing")

# Chunk size for bounded streaming dual hash computation (1 MB)
HASH_CHUNK_SIZE = 1048576  # 1 MB


def compute_dual_hashes(file_path: str, chunk_size: int = HASH_CHUNK_SIZE) -> Tuple[str, str]:
    """
    Computes both SHA-256 and SHA3-512 digests over an immutable evidence file
    in a single streaming pass using bounded memory buffers.

    Returns:
        (sha256_hex, sha3_512_hex) as lowercase hexadecimal strings.
    """
    if not os.path.exists(file_path):
        raise EvidenceFileNotFoundException(file_path)

    sha256_hasher = hashlib.sha256()
    sha3_512_hasher = hashlib.sha3_512()

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256_hasher.update(chunk)
            sha3_512_hasher.update(chunk)

    return sha256_hasher.hexdigest().lower(), sha3_512_hasher.hexdigest().lower()


class IntegrityService:
    """
    Business service orchestrating MOD-09 Dual Hashing (SHA-256 + SHA3-512)
    and cryptographic integrity verification for SAKSHI Phase 3.
    """

    def __init__(
        self,
        db: Session,
        authz: Optional[IAuthorizationService] = None,
    ):
        self.db = db
        self.case_repo = CaseRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.authz = authz or authorization_service

    def verify_and_compute_integrity(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> IntegrityVerificationResult:
        """
        Executes dual hash verification on a WORM-committed evidence item.

        Workflow:
            1. Authenticate & Authorize ('evidence:verify')
            2. Validate Case Existence
            3. Retrieve Evidence Record & Verify Case Containment
            4. Verify WORM Commitment Status (MOD-08 gate)
            5. Idempotency Check (return existing if already VERIFIED)
            6. Physical Payload Boundary Containment (canonical realpath within case workspace)
            7. Emit EVIDENCE_INTEGRITY_VERIFICATION_STARTED audit event
            8. Stream payload, compute SHA-256 and SHA3-512 simultaneously
            9. Compare recomputed SHA-256 against MOD-08 pre-hash:
               - MISMATCH: mark FAILED, emit audit failure, raise SHA256IntegrityMismatchException
               - MATCH: mark VERIFIED, persist SHA3-512 digest, emit audit success
            10. Return IntegrityVerificationResult
        """
        # 1. Validate Case Existence
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        # 2. RBAC/ABAC Authorization check (MOD-03)
        self.authz.check_can_verify_evidence(investigator, case)

        # 3. Retrieve Evidence Record & Check Case Containment
        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        # 4. Strict Gate: Evidence must be committed in WORM storage (MOD-08 output)
        if evidence.status != EvidenceIntakeStatus.COMMITTED.value or \
           evidence.worm_status != "COMMITTED" or \
           not evidence.checksum_sha256:
            raise EvidenceNotWORMCommittedException(
                f"Evidence '{evidence_id}' has not been committed to WORM storage "
                f"(status: '{evidence.status}', worm_status: '{evidence.worm_status}'). "
                f"Only WORM-committed evidence can undergo MOD-09 dual hash verification."
            )

        # 5. Idempotency Check: Already verified?
        if evidence.integrity_status == "VERIFIED" and evidence.checksum_sha3_512:
            return IntegrityVerificationResult(
                evidence_id=evidence.evidence_id,
                case_id=evidence.case_id,
                worm_storage_reference=evidence.worm_storage_reference or f"worm://{case_id}/{evidence.checksum_sha256}",
                checksum_sha256=evidence.checksum_sha256,
                checksum_sha3_512=evidence.checksum_sha3_512,
                integrity_status="VERIFIED",
                message="Evidence dual hash integrity is already verified and consistent.",
                verified_at=evidence.integrity_verified_at or datetime.now(timezone.utc),
                sha256_matched=True,
                already_verified=True,
            )

        # 6. Physical Payload Boundary Containment
        staged_path = evidence.raw_storage_path
        if not os.path.exists(staged_path):
            evidence.integrity_status = "FAILED"
            evidence.integrity_verification_message = f"Physical evidence payload missing at '{staged_path}'."
            self.evidence_repo.update(evidence)
            raise EvidenceFileNotFoundException(staged_path)

        canonical_payload_path = os.path.realpath(staged_path)
        canonical_workspace_path = os.path.realpath(case.case_workspace_path)

        if not canonical_payload_path.startswith(canonical_workspace_path + os.sep) and \
           canonical_payload_path != canonical_workspace_path:
            log_event(
                event_type="WORKSPACE_BOUNDARY_VIOLATION",
                message=f"Evidence path '{canonical_payload_path}' escapes case workspace '{canonical_workspace_path}'.",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
            )
            evidence.integrity_status = "FAILED"
            evidence.integrity_verification_message = "Storage path violates case workspace boundary containment."
            self.evidence_repo.update(evidence)
            raise ForbiddenException("Evidence storage path violates case workspace boundary containment.")

        # 7. Audit: Verification Started
        now = datetime.now(timezone.utc)
        AuditIntegrationService.record_event(
            action="EVIDENCE_INTEGRITY_VERIFICATION_STARTED",
            investigator_id=investigator.investigator_id,
            case_id=case.case_id,
            details={
                "evidence_id": evidence.evidence_id,
                "case_id": case.case_id,
                "worm_storage_reference": evidence.worm_storage_reference,
                "mod08_sha256": evidence.checksum_sha256,
            },
        )

        try:
            # 8. Compute Dual Hashes via streaming
            recomputed_sha256, computed_sha3_512 = compute_dual_hashes(
                canonical_payload_path, chunk_size=HASH_CHUNK_SIZE
            )

            # 9. Verify SHA-256 against MOD-08 pre-hash
            expected_sha256 = evidence.checksum_sha256.lower()
            if recomputed_sha256 != expected_sha256:
                # FAIL-CLOSED on mismatch
                mismatch_msg = (
                    f"Cryptographic integrity violation for evidence '{evidence_id}': "
                    f"MOD-08 pre-hash '{expected_sha256}' does not match recomputed SHA-256 '{recomputed_sha256}'."
                )
                evidence.integrity_status = "FAILED"
                evidence.integrity_verification_message = mismatch_msg
                evidence.integrity_verified_at = datetime.now(timezone.utc)
                self.evidence_repo.update(evidence)

                AuditIntegrationService.record_event(
                    action="EVIDENCE_INTEGRITY_FAILED",
                    investigator_id=investigator.investigator_id,
                    case_id=case.case_id,
                    details={
                        "evidence_id": evidence.evidence_id,
                        "case_id": case.case_id,
                        "reason": "SHA-256 digest mismatch",
                        "expected_sha256": expected_sha256,
                        "recomputed_sha256": recomputed_sha256,
                    },
                )
                log_event(
                    event_type="INTEGRITY_VERIFICATION_FAILURE",
                    message=mismatch_msg,
                    case_id=case.case_id,
                    investigator_id=investigator.investigator_id,
                    extra_data={
                        "evidence_id": evidence.evidence_id,
                        "expected_sha256": expected_sha256,
                        "recomputed_sha256": recomputed_sha256,
                    },
                )
                raise SHA256IntegrityMismatchException(
                    expected=expected_sha256,
                    actual=recomputed_sha256,
                    message=mismatch_msg,
                )

            # SHA-256 MATCH: Audit SHA-256 verified & SHA3-512 computed
            AuditIntegrationService.record_event(
                action="EVIDENCE_SHA256_VERIFIED",
                investigator_id=investigator.investigator_id,
                case_id=case.case_id,
                details={
                    "evidence_id": evidence.evidence_id,
                    "case_id": case.case_id,
                    "sha256": recomputed_sha256,
                },
            )

            AuditIntegrationService.record_event(
                action="EVIDENCE_SHA3_512_COMPUTED",
                investigator_id=investigator.investigator_id,
                case_id=case.case_id,
                details={
                    "evidence_id": evidence.evidence_id,
                    "case_id": case.case_id,
                    "sha3_512": computed_sha3_512,
                },
            )

            # 10. Persist Integrity Status to Database
            verified_at = datetime.now(timezone.utc)
            evidence.checksum_sha3_512 = computed_sha3_512
            evidence.sha3_512_computed_at = verified_at
            evidence.integrity_status = "VERIFIED"
            evidence.integrity_verified_at = verified_at
            evidence.integrity_verification_message = (
                "Dual hash integrity verified: SHA-256 matches MOD-08 pre-hash, SHA3-512 generated."
            )
            self.evidence_repo.update(evidence)

            # Audit: Integrity Verified
            AuditIntegrationService.record_event(
                action="EVIDENCE_INTEGRITY_VERIFIED",
                investigator_id=investigator.investigator_id,
                case_id=case.case_id,
                details={
                    "evidence_id": evidence.evidence_id,
                    "case_id": case.case_id,
                    "checksum_sha256": recomputed_sha256,
                    "checksum_sha3_512": computed_sha3_512,
                    "integrity_status": "VERIFIED",
                },
            )

            log_event(
                event_type="INTEGRITY_VERIFICATION_SUCCESS",
                message=f"Evidence '{evidence.evidence_id}' dual hash integrity verified successfully.",
                case_id=case.case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "sha256": recomputed_sha256,
                    "sha3_512": computed_sha3_512,
                },
            )

            return IntegrityVerificationResult(
                evidence_id=evidence.evidence_id,
                case_id=evidence.case_id,
                worm_storage_reference=evidence.worm_storage_reference or f"worm://{case_id}/{recomputed_sha256}",
                checksum_sha256=recomputed_sha256,
                checksum_sha3_512=computed_sha3_512,
                integrity_status="VERIFIED",
                message="Evidence dual hash integrity successfully verified (SHA-256 match, SHA3-512 generated).",
                verified_at=verified_at,
                sha256_matched=True,
                already_verified=False,
            )

        except (SHA256IntegrityMismatchException, ForbiddenException, EvidenceFileNotFoundException):
            raise
        except Exception as e:
            evidence.integrity_status = "FAILED"
            evidence.integrity_verification_message = f"Integrity verification internal error: {str(e)}"
            self.evidence_repo.update(evidence)

            AuditIntegrationService.record_event(
                action="EVIDENCE_INTEGRITY_FAILED",
                investigator_id=investigator.investigator_id,
                case_id=case.case_id,
                details={
                    "evidence_id": evidence.evidence_id,
                    "case_id": case.case_id,
                    "error": str(e),
                },
            )
            raise IntegrityVerificationFailedException(
                f"Dual hash integrity computation failed: {str(e)}"
            )

    def get_integrity_contract(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> IntegrityProtectedEvidenceObject:
        """
        Exports the formal downstream handoff contract for subsequent Phase 3 / Phase 4 modules.

        STRICT INVARIANT:
            Only evidence with integrity_status == 'VERIFIED' and valid dual hashes
            is permitted to yield this contract.
            Unverified, mismatched, or failed evidence items are strictly denied.
        """
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        self.authz.check_can_read_evidence(investigator, case)

        if evidence.integrity_status != "VERIFIED" or \
           not evidence.checksum_sha256 or \
           not evidence.checksum_sha3_512:
            raise IntegrityNotVerifiedException(
                f"Evidence '{evidence_id}' has not successfully passed dual hash integrity verification "
                f"(current integrity_status: '{evidence.integrity_status}'). "
                f"Only verified evidence can proceed downstream."
            )

        return IntegrityProtectedEvidenceObject(
            case_id=evidence.case_id,
            evidence_id=evidence.evidence_id,
            original_file_name=evidence.original_file_name,
            evidence_category=evidence.evidence_category,
            file_size_bytes=evidence.file_size_bytes,
            worm_storage_reference=evidence.worm_storage_reference or f"worm://{case_id}/{evidence.checksum_sha256}",
            checksum_sha256=evidence.checksum_sha256,
            checksum_sha3_512=evidence.checksum_sha3_512,
            integrity_status="VERIFIED",
            verified_at=evidence.integrity_verified_at or datetime.now(timezone.utc),
            source="MOD-09",
        )
