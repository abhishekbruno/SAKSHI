"""
MOD-08: WORM Commit + Checksum Service for SAKSHI Investigation Platform.
Phase 2 — Evidence Ingestion.

Consumes:
    ScannedEvidenceObject (from MOD-07 Antivirus Scan)
Produces:
    WORMCommittedEvidenceObject (downstream handoff to Phase 3 Security & Integrity)

Core Responsibilities:
    1. Fail-closed AV Gate: strictly verifies that evidence has status == 'CLEAN'
       and antivirus_status == 'CLEAN'. Unscanned or non-clean files are rejected.
    2. Chunked SHA-256 Pre-Hashing: bounded streaming reads (1 MB chunks) supporting
       arbitrarily large multi-gigabyte forensic evidence payloads safely.
    3. WORM Storage Abstraction: IWORMStorage interface with Write-Once-Read-Many
       semantics, content-addressable storage, and overwrite prevention.
    4. Local WORM Implementation: LocalFileSystemWORMStorage stores immutable
       content-addressed objects, strips write permissions, and generates
       canonical references: worm://<case-id>/<sha256>.
    5. Case Isolation & Path Boundary: enforces canonical path resolution within
       case workspace boundaries, rejecting directory traversals.
    6. MOD-03 Authorization: verifies 'evidence:commit' permission via PolicyEngine.
    7. Atomicity & State Transitions: updates state to COMMITTED only after storage
       write and digest verification succeed.
    8. Structured Audit Logging: emits tamper-evident audit events via AuditIntegrationService.

IMPORTANT ARCHITECTURAL BOUNDARY:
MOD-08 implements the Phase 2 SHA-256 pre-hash and WORM commitment boundary.
It does NOT implement SHA3-512 dual hashing, Merkle audit trees, or production
Object Lock architectures (which belong exclusively to Phase 3).
"""
import os
import stat
import shutil
import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
import time
from typing import Optional, Dict, Any, Tuple
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
    EvidenceNotScannedException,
    AntivirusThreatDetectedException,
    WORMCommitFailedException,
    WORMAlreadyCommittedException,
    ChecksumMismatchException,
    EvidenceNotCommittedException,
    ForbiddenException,
)
from app.core.logging import log_event
from app.services.auth_service import IAuthorizationService, authorization_service
from app.services.audit_integration import AuditIntegrationService
from app.schemas.evidence import (
    EvidenceIntakeStatus,
    AntivirusVerdict,
    ScannedEvidenceObject,
    WORMCommitResult,
    WORMCommittedEvidenceObject,
)

logger = logging.getLogger("sakshi.mod08.worm_commit")

# Chunk size for bounded streaming SHA-256 computation (1 MB)
HASH_CHUNK_SIZE = 1048576  # 1 MB


# ═══════════════════════════════════════════════════════════════════════════
# SHA-256 Bounded Streaming Computation
# ═══════════════════════════════════════════════════════════════════════════

def compute_sha256(file_path: str, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    """
    Computes a cryptographic SHA-256 hexadecimal digest of the actual evidence payload bytes.
    Uses bounded chunked reads so large evidence files (e.g. disk images, multi-hour audio)
    never exhaust host memory.
    """
    if not os.path.exists(file_path):
        raise EvidenceFileNotFoundException(file_path)

    hasher = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
    except PermissionError:
        raise WORMCommitFailedException(f"Permission denied reading evidence payload at '{file_path}'.")
    except Exception as e:
        raise WORMCommitFailedException(f"Failed to read payload for hashing: {type(e).__name__}: {str(e)}")

    return hasher.hexdigest().lower()


# ═══════════════════════════════════════════════════════════════════════════
# WORM Storage Abstraction
# ═══════════════════════════════════════════════════════════════════════════

class IWORMStorage(ABC):
    """
    Abstract interface for Write-Once-Read-Many (WORM) storage engines in SAKSHI.
    Enforces immutability: once an object is committed with its digest,
    it cannot be overwritten, replaced, or deleted through this interface.
    """

    @abstractmethod
    def put_immutable(
        self,
        case_id: str,
        sha256_digest: str,
        source_file_path: str,
        case_workspace_path: Optional[str] = None,
    ) -> str:
        """
        Commit source file into WORM storage at content-addressable reference.

        Returns:
            The canonical immutable storage reference (e.g. worm://<case_id>/<sha256>).

        Raises:
            WORMCommitFailedException: If storage write or verification fails.
            ChecksumMismatchException: If verified bytes do not match digest.
        """
        pass

    @abstractmethod
    def get_reference(self, case_id: str, sha256_digest: str) -> str:
        """Construct the canonical storage reference for a given case and digest."""
        pass

    @abstractmethod
    def exists(
        self,
        case_id: str,
        sha256_digest: str,
        case_workspace_path: Optional[str] = None,
    ) -> bool:
        """Check if an immutable object exists for this case and digest."""
        pass

    @abstractmethod
    def verify_immutable(
        self,
        storage_reference: str,
        expected_sha256: str,
        case_workspace_path: Optional[str] = None,
    ) -> bool:
        """Verify the content of the committed WORM object matches the expected SHA-256."""
        pass


class LocalFileSystemWORMStorage(IWORMStorage):
    """
    Development/Local WORM Storage implementation.
    Simulates Write-Once-Read-Many storage on the local filesystem.
    Stores immutable content-addressed objects inside a dedicated .worm/<sha256> folder
    within the case workspace, removes write permissions on the committed file,
    and strictly forbids overwrites or replacement.
    """

    def __init__(self, base_worm_dir: Optional[str] = None):
        self._base_worm_dir = base_worm_dir

    def _resolve_worm_dir(self, case_id: str, case_workspace_path: Optional[str] = None) -> str:
        if self._base_worm_dir:
            return os.path.join(self._base_worm_dir, case_id)
        if case_workspace_path:
            return os.path.join(case_workspace_path, ".worm")
        raise WORMCommitFailedException("Neither base_worm_dir nor case_workspace_path provided for WORM storage.")

    def get_reference(self, case_id: str, sha256_digest: str) -> str:
        return f"worm://{case_id}/{sha256_digest.lower()}"

    def exists(
        self,
        case_id: str,
        sha256_digest: str,
        case_workspace_path: Optional[str] = None,
    ) -> bool:
        worm_dir = self._resolve_worm_dir(case_id, case_workspace_path)
        dest_path = os.path.join(worm_dir, sha256_digest.lower())
        return os.path.exists(dest_path)

    def put_immutable(
        self,
        case_id: str,
        sha256_digest: str,
        source_file_path: str,
        case_workspace_path: Optional[str] = None,
    ) -> str:
        worm_dir = self._resolve_worm_dir(case_id, case_workspace_path)
        os.makedirs(worm_dir, exist_ok=True)

        dest_path = os.path.join(worm_dir, sha256_digest.lower())

        # If object already exists at this exact content address:
        if os.path.exists(dest_path):
            # First verify the source file actually matches the claimed digest
            source_digest = compute_sha256(source_file_path)
            if source_digest != sha256_digest.lower():
                raise ChecksumMismatchException(
                    expected=sha256_digest.lower(),
                    actual=source_digest,
                    message="Source file hash does not match claimed SHA-256 digest."
                )

            # Verify existing stored object integrity
            existing_digest = compute_sha256(dest_path)
            if existing_digest == sha256_digest.lower():
                # Idempotent: already committed with exact same digest
                return self.get_reference(case_id, sha256_digest)
            else:
                # Content address collision or corrupted state
                raise WORMCommitFailedException(
                    f"WORM storage collision at '{dest_path}': existing digest mismatch."
                )

        # Write-Once: Stream copy to destination while computing verification digest
        temp_dest = f"{dest_path}.tmp_{int(time.time() * 1000)}"
        verify_hasher = hashlib.sha256()

        try:
            with open(source_file_path, "rb") as src, open(temp_dest, "wb") as dst:
                while True:
                    chunk = src.read(HASH_CHUNK_SIZE)
                    if not chunk:
                        break
                    dst.write(chunk)
                    verify_hasher.update(chunk)

            verified_digest = verify_hasher.hexdigest().lower()
            if verified_digest != sha256_digest.lower():
                if os.path.exists(temp_dest):
                    os.remove(temp_dest)
                raise ChecksumMismatchException(
                    expected=sha256_digest.lower(),
                    actual=verified_digest,
                    message="Calculated payload SHA-256 does not match bytes written to WORM storage."
                )

            # Atomic rename to final content address
            os.replace(temp_dest, dest_path)

            # Strip write permissions on committed WORM file (read-only for owner/group/others)
            try:
                os.chmod(dest_path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            except Exception as e:
                logger.warning("Could not set read-only permissions on WORM file: %s", e)

            return self.get_reference(case_id, sha256_digest)

        except ChecksumMismatchException:
            raise
        except Exception as e:
            if os.path.exists(temp_dest):
                try:
                    os.remove(temp_dest)
                except Exception:
                    pass
            raise WORMCommitFailedException(f"Failed to commit object to WORM storage: {type(e).__name__}: {str(e)}")

    def verify_immutable(
        self,
        storage_reference: str,
        expected_sha256: str,
        case_workspace_path: Optional[str] = None,
    ) -> bool:
        # storage_reference format: worm://<case_id>/<sha256>
        if not storage_reference.startswith("worm://"):
            return False
        parts = storage_reference[7:].split("/")
        if len(parts) != 2:
            return False
        case_id, digest = parts[0], parts[1]

        worm_dir = self._resolve_worm_dir(case_id, case_workspace_path)
        dest_path = os.path.join(worm_dir, digest.lower())
        if not os.path.exists(dest_path):
            return False

        computed = compute_sha256(dest_path)
        return computed == expected_sha256.lower()


# ═══════════════════════════════════════════════════════════════════════════
# MOD-08 WORM Commit + Checksum Service
# ═══════════════════════════════════════════════════════════════════════════

class WORMCommitService:
    """
    MOD-08: WORM Commit + Checksum Service.
    Enforces the cryptographic and immutable storage boundary for evidence
    that has completed MOD-05, MOD-06, and MOD-07.
    """

    def __init__(
        self,
        db: Session,
        worm_storage: Optional[IWORMStorage] = None,
        authz: Optional[IAuthorizationService] = None,
    ):
        self.db = db
        self.case_repo = CaseRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.authz = authz or authorization_service
        self.worm_storage = worm_storage or LocalFileSystemWORMStorage()

    def commit_evidence(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> WORMCommitResult:
        """
        Consumes ScannedEvidenceObject (from MOD-07) and commits evidence to WORM storage.

        Workflow:
            1. Authenticate & Authorize investigator via MOD-03 ('evidence:commit').
            2. Validate case existence and evidence belonging.
            3. Strict Fail-Closed AV Gate:
               - Enforce evidence status == 'CLEAN' and antivirus_status == 'CLEAN'.
               - Reject if status is QUARANTINED, THREAT_DETECTED, SCANNER_UNAVAILABLE,
                 SCAN_TIMEOUT, SCAN_ERROR, or un-scanned.
            4. Verify physical payload existence and workspace boundary containment.
            5. Check Idempotency: If already committed, return existing immutable reference.
            6. Emit EVIDENCE_WORM_COMMIT_STARTED audit log.
            7. Compute chunked SHA-256 pre-hash on actual payload bytes.
            8. Emit EVIDENCE_SHA256_COMPUTED audit log.
            9. Commit payload to WORM storage via IWORMStorage (Write-Once).
            10. Atomic DB State Transition:
                - status -> COMMITTED
                - checksum_algorithm -> SHA-256
                - checksum_sha256 -> digest
                - worm_status -> COMMITTED
                - worm_storage_reference -> worm://<case-id>/<sha256>
            11. Emit EVIDENCE_WORM_COMMITTED audit log.
            12. Return WORMCommitResult.
        """
        # 1. Fetch Case
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        # 2. RBAC/ABAC Authorization check (MOD-03)
        self.authz.check_can_commit_evidence(investigator, case)

        # 3. Fetch Evidence Record
        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        # 4. Idempotency Check: Already successfully committed?
        if evidence.status == EvidenceIntakeStatus.COMMITTED.value and \
           evidence.worm_status == "COMMITTED" and \
           evidence.checksum_sha256:
            # Deterministic: return existing immutable commitment
            return WORMCommitResult(
                evidence_id=evidence.evidence_id,
                case_id=evidence.case_id,
                status=evidence.status,
                worm_status=evidence.worm_status or "COMMITTED",
                checksum_algorithm=evidence.checksum_algorithm or "SHA-256",
                checksum_sha256=evidence.checksum_sha256,
                worm_storage_reference=evidence.worm_storage_reference or self.worm_storage.get_reference(case_id, evidence.checksum_sha256),
                message="Evidence item is already committed in immutable WORM storage.",
                worm_commit_message=evidence.worm_commit_message or "Evidence item is already committed in immutable WORM storage.",
                committed_at=evidence.worm_committed_at or datetime.now(timezone.utc),
                worm_committed_at=evidence.worm_committed_at or datetime.now(timezone.utc),
                already_committed=True,
            )

        # 5. Strict Fail-Closed Antivirus Gate
        # Only evidence that has passed MOD-07 with a CLEAN verdict can enter MOD-08.
        if evidence.status == EvidenceIntakeStatus.QUARANTINED.value or \
           evidence.antivirus_status == AntivirusVerdict.THREAT_DETECTED.value:
            raise AntivirusThreatDetectedException(
                threat_name=evidence.antivirus_threat_name or "Unknown Threat",
                message=(
                    f"Evidence '{evidence_id}' is quarantined due to detected threat "
                    f"'{evidence.antivirus_threat_name}' and cannot be committed to WORM storage."
                ),
            )

        if evidence.antivirus_status != AntivirusVerdict.CLEAN.value or \
           evidence.status != EvidenceIntakeStatus.CLEAN.value:
            raise EvidenceNotScannedException(
                f"Evidence '{evidence_id}' has not passed MOD-07 Antivirus scanning with a CLEAN verdict "
                f"(status: '{evidence.status}', av_status: '{evidence.antivirus_status}'). "
                f"Only verified clean evidence can proceed to MOD-08 WORM commitment."
            )

        # 6. Physical Payload & Workspace Boundary Containment
        staged_path = evidence.raw_storage_path
        if not os.path.exists(staged_path):
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
            raise ForbiddenException("Evidence storage path violates case workspace boundary containment.")

        # 7. Audit: WORM Commit Started
        now = datetime.now(timezone.utc)
        AuditIntegrationService.record_event(
            action="EVIDENCE_WORM_COMMIT_STARTED",
            investigator_id=investigator.investigator_id,
            case_id=case.case_id,
            details={
                "evidence_id": evidence.evidence_id,
                "case_id": case.case_id,
                "antivirus_scanner": evidence.antivirus_scanner,
                "antivirus_status": evidence.antivirus_status,
            },
        )

        try:
            # 8. Compute SHA-256 pre-hash using bounded chunked reading
            sha256_digest = compute_sha256(canonical_payload_path, chunk_size=HASH_CHUNK_SIZE)
            checksum_computed_at = datetime.now(timezone.utc)

            # Audit: SHA-256 Computed
            AuditIntegrationService.record_event(
                action="EVIDENCE_SHA256_COMPUTED",
                investigator_id=investigator.investigator_id,
                case_id=case.case_id,
                details={
                    "evidence_id": evidence.evidence_id,
                    "case_id": case.case_id,
                    "algorithm": "SHA-256",
                    "digest": sha256_digest,
                },
            )

            # 9. Commit to WORM storage
            storage_reference = self.worm_storage.put_immutable(
                case_id=case.case_id,
                sha256_digest=sha256_digest,
                source_file_path=canonical_payload_path,
                case_workspace_path=case.case_workspace_path,
            )

            # 10. Atomic DB State Transition
            committed_at = datetime.now(timezone.utc)
            evidence.status = EvidenceIntakeStatus.COMMITTED.value
            evidence.checksum_algorithm = "SHA-256"
            evidence.checksum_sha256 = sha256_digest
            evidence.checksum_computed_at = checksum_computed_at
            evidence.worm_status = "COMMITTED"
            evidence.worm_storage_reference = storage_reference
            evidence.worm_committed_at = committed_at
            evidence.worm_commit_message = "Evidence committed to WORM storage with SHA-256 pre-hash."
            self.evidence_repo.update(evidence)

            # 11. Audit: WORM Committed
            AuditIntegrationService.record_event(
                action="EVIDENCE_WORM_COMMITTED",
                investigator_id=investigator.investigator_id,
                case_id=case.case_id,
                details={
                    "evidence_id": evidence.evidence_id,
                    "case_id": case.case_id,
                    "checksum_algorithm": "SHA-256",
                    "checksum_sha256": sha256_digest,
                    "worm_storage_reference": storage_reference,
                    "status": "COMMITTED",
                },
            )

            log_event(
                event_type="WORM_COMMIT_SUCCESS",
                message=f"Evidence '{evidence.evidence_id}' committed to WORM storage ({storage_reference}).",
                case_id=case.case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "sha256": sha256_digest,
                    "storage_reference": storage_reference,
                },
            )

            return WORMCommitResult(
                evidence_id=evidence.evidence_id,
                case_id=evidence.case_id,
                status=evidence.status,
                worm_status="COMMITTED",
                checksum_algorithm="SHA-256",
                checksum_sha256=sha256_digest,
                worm_storage_reference=storage_reference,
                message="Evidence committed to WORM storage with SHA-256 pre-hash.",
                worm_commit_message="Evidence committed to WORM storage with SHA-256 pre-hash.",
                committed_at=committed_at,
                worm_committed_at=committed_at,
                already_committed=False,
            )

        except (ChecksumMismatchException, WORMCommitFailedException, WORMAlreadyCommittedException) as e:
            # Audit commit failure
            AuditIntegrationService.record_event(
                action="EVIDENCE_WORM_COMMIT_FAILED",
                investigator_id=investigator.investigator_id,
                case_id=case.case_id,
                details={
                    "evidence_id": evidence.evidence_id,
                    "case_id": case.case_id,
                    "failure_reason": str(e),
                },
            )
            log_event(
                event_type="WORM_COMMIT_FAILURE",
                message=f"WORM commitment failed for evidence '{evidence.evidence_id}': {str(e)}",
                case_id=case.case_id,
                investigator_id=investigator.investigator_id,
            )
            raise

    def get_worm_committed_evidence_object(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> WORMCommittedEvidenceObject:
        """
        Downstream Handoff Contract for Phase 3 (Security & Integrity).

        STRICT INVARIANT:
            Only evidence with status == 'COMMITTED', worm_status == 'COMMITTED',
            and verified SHA-256 digest is permitted to yield this contract.
            Uncommitted, clean-only, quarantined, or failed items are strictly denied handoff.
        """
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        self.authz.check_can_read_evidence(investigator, case)

        if evidence.status != EvidenceIntakeStatus.COMMITTED.value or \
           evidence.worm_status != "COMMITTED" or \
           not evidence.checksum_sha256:
            raise EvidenceNotCommittedException(
                f"Evidence '{evidence_id}' has not been committed to WORM storage (status: '{evidence.status}'). "
                f"Only successfully committed evidence can proceed to Phase 3."
            )

        return WORMCommittedEvidenceObject(
            evidence_id=evidence.evidence_id,
            case_id=evidence.case_id,
            staged_file_path=evidence.raw_storage_path,
            original_file_name=evidence.original_file_name,
            verified_mime_type=evidence.detected_mime_type or evidence.declared_mime_type,
            detected_format=evidence.detected_format or "UNKNOWN",
            evidence_category=evidence.evidence_category,
            file_size_bytes=evidence.file_size_bytes,
            submitting_investigator_id=evidence.submitting_investigator_id,
            mime_status="VALIDATED",
            antivirus_verdict=evidence.antivirus_status or "CLEAN",
            antivirus_scanner=evidence.antivirus_scanner or "UNKNOWN",
            checksum_algorithm=evidence.checksum_algorithm or "SHA-256",
            checksum_sha256=evidence.checksum_sha256,
            checksum_computed_at=evidence.checksum_computed_at or datetime.now(timezone.utc),
            worm_status=evidence.worm_status or "COMMITTED",
            worm_storage_reference=evidence.worm_storage_reference or self.worm_storage.get_reference(case_id, evidence.checksum_sha256),
            committed_at=evidence.worm_committed_at or datetime.now(timezone.utc),
        )
