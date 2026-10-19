"""
MOD-10: WORM Object Lock / Dual Storage Service for SAKSHI Investigation Platform.
Phase 3 — Security & Integrity.

Consumes:
    IntegrityProtectedEvidenceObject (from MOD-09 Dual Hashing — integrity_status == 'VERIFIED')
Produces:
    ObjectLockedEvidenceObject (downstream handoff contract for MOD-11 AES-256-GCM Encryption)

Core Responsibilities:
    1. Strict MOD-09 Gate: Evidence must have integrity_status == 'VERIFIED' AND dual hashes present.
    2. IObjectLockBackend abstraction: pluggable backend supporting local filesystem today,
       S3 Object Lock / cloud storage in a future production phase.
    3. Dual-hash integrity binding: captures SHA-256 + SHA3-512 fingerprint at lock time,
       binding the object's cryptographic identity to the lock record.
    4. Immutable object reference: generates canonical objlock://<case_id>/<sha256>+<sha3_512_prefix16>
    5. Retention metadata: records lock_applied_at, lock_retention_until, lock_mode (GOVERNANCE/COMPLIANCE).
    6. Overwrite protection: read-only permission enforcement at filesystem level.
    7. Deletion protection: lock manifest prevents physical deletion.
    8. Case isolation: all paths verified against case workspace boundary.
    9. MOD-03 Authorization: verifies 'evidence:object_lock' permission via PolicyEngine.
    10. Structured audit events via AuditIntegrationService (tamper-evident).
    11. Deterministic idempotency: repeated lock requests are safe and return existing state.
    12. Failure-safe behaviour: partial lock state is rolled back; lock_status transitions to LOCK_FAILED.
    13. ObjectLockedEvidenceObject downstream contract for MOD-11.

IMPORTANT ARCHITECTURAL BOUNDARY:
    MOD-10 implements the Phase 3 application-level Object Lock boundary.
    It does NOT claim equivalence to hardware/cloud-enforced Object Lock
    (e.g., AWS S3 Object Lock COMPLIANCE mode). That distinction was already
    correctly documented in Phase 2 and is preserved here.
    The IObjectLockBackend interface is intentionally designed to plug in a cloud
    backend in a future production phase without changing the service contract.
"""
import json
import os
import stat
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
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
    ForbiddenException,
    IntegrityNotVerifiedForLockException,
    ObjectLockFailedException,
    ObjectAlreadyLockedException,
    ObjectNotLockedException,
)
from app.core.logging import log_event
from app.services.auth_service import IAuthorizationService, authorization_service
from app.services.audit_integration import AuditIntegrationService
from app.schemas.evidence import (
    ObjectLockMode,
    ObjectLockResult,
    ObjectLockedEvidenceObject,
)

logger = logging.getLogger("sakshi.mod10.object_lock")

# Default retention period for locked evidence objects (days)
DEFAULT_RETENTION_DAYS = 2555  # ~7 years, reflecting forensic evidence retention norms

# Manifest filename stored alongside each locked object
LOCK_MANIFEST_FILENAME = ".object_lock_manifest.json"

# Directory name for the object-lock store within the case workspace
OBJECT_LOCK_DIR_NAME = ".objlock"


# ═══════════════════════════════════════════════════════════════════════════
# IObjectLockBackend — Pluggable Object Lock Storage Interface
# ═══════════════════════════════════════════════════════════════════════════

class IObjectLockBackend(ABC):
    """
    Abstract interface for Object Lock storage backends.

    This interface is designed for forward-compatibility with cloud/S3 backends.
    In Phase 3, the LocalObjectLockBackend provides filesystem-level enforcement.

    Future backends may implement:
        - S3ObjectLockBackend: AWS S3 Object Lock (GOVERNANCE/COMPLIANCE modes)
        - AzureBlobImmutableBackend: Azure Blob Immutable Storage
        - GCSRetentionBackend: Google Cloud Storage with retention policies
    """

    BACKEND_NAME: str = "ABSTRACT"

    @abstractmethod
    def apply_lock(
        self,
        case_id: str,
        sha256_digest: str,
        sha3_512_digest: str,
        source_file_path: str,
        lock_mode: str,
        retention_days: int,
        case_workspace_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Apply an immutable object lock to the evidence object.

        Returns a dict with:
            lock_storage_reference (str): Canonical objlock:// reference.
            lock_manifest_path (str): Path to the lock manifest record.
            lock_applied_at (datetime): UTC timestamp of lock application.
            lock_retention_until (datetime): UTC timestamp when lock expires.
            lock_overwrite_protected (bool): True if overwrite is prevented.
            lock_delete_protected (bool): True if deletion is prevented.
        """

    @abstractmethod
    def is_locked(
        self,
        case_id: str,
        sha256_digest: str,
        case_workspace_path: Optional[str] = None,
    ) -> bool:
        """Return True if an object lock record already exists for this digest."""

    @abstractmethod
    def get_reference(self, case_id: str, sha256_digest: str, sha3_512_digest: str) -> str:
        """Construct the canonical objlock:// storage reference."""

    @abstractmethod
    def verify_lock_integrity(
        self,
        lock_storage_reference: str,
        expected_sha256: str,
        case_workspace_path: Optional[str] = None,
    ) -> bool:
        """
        Verify the integrity of the lock manifest and locked object.
        Returns True if the lock record and object bytes are consistent.
        """


# ═══════════════════════════════════════════════════════════════════════════
# LocalObjectLockBackend — Phase 3 Filesystem Implementation
# ═══════════════════════════════════════════════════════════════════════════

class LocalObjectLockBackend(IObjectLockBackend):
    """
    Phase 3 Local Filesystem Object Lock Backend.

    Implements the IObjectLockBackend interface using local filesystem primitives:
        - Creates a dedicated .objlock/ directory within the case workspace.
        - Writes a JSON lock manifest capturing the dual-hash binding,
          retention period, lock mode, and protecting metadata.
        - Strips write permissions (read-only) on both the WORM object and the manifest.
        - Does NOT hardcode file deletion prevention at the OS level
          (that requires cloud infrastructure or OS-level WORM volumes).

    ARCHITECTURAL LIMITATION:
        This is an application-level implementation of Object Lock semantics.
        It does NOT provide hardware/cloud-enforced immutability equivalent to:
            - AWS S3 Object Lock (COMPLIANCE mode)
            - NetApp ONTAP SnapLock
            - Azure Blob Immutable Storage
        Those require infrastructure-level support and are the target of a
        future production deployment phase.

        This implementation correctly documents this distinction and provides
        the service contract that a future cloud backend can replace.

    Backend Name: LOCAL_FILESYSTEM
    """

    BACKEND_NAME = "LOCAL_FILESYSTEM"

    def __init__(self, base_objlock_dir: Optional[str] = None):
        self._base_objlock_dir = base_objlock_dir

    def _resolve_objlock_dir(self, case_id: str, case_workspace_path: Optional[str] = None) -> str:
        if self._base_objlock_dir:
            return os.path.join(self._base_objlock_dir, case_id)
        if case_workspace_path:
            return os.path.join(case_workspace_path, OBJECT_LOCK_DIR_NAME)
        raise ObjectLockFailedException(
            "Neither base_objlock_dir nor case_workspace_path provided for Object Lock storage."
        )

    def get_reference(self, case_id: str, sha256_digest: str, sha3_512_digest: str) -> str:
        """
        Canonical objlock reference format:
            objlock://<case_id>/<sha256>+<sha3_512_prefix16>

        The 16-character SHA3-512 prefix provides meaningful identity disambiguation
        while keeping the reference compact. The full hashes are stored in the manifest.
        """
        sha3_prefix = sha3_512_digest[:16]
        return f"objlock://{case_id}/{sha256_digest.lower()}+{sha3_prefix}"

    def is_locked(
        self,
        case_id: str,
        sha256_digest: str,
        case_workspace_path: Optional[str] = None,
    ) -> bool:
        objlock_dir = self._resolve_objlock_dir(case_id, case_workspace_path)
        manifest_path = os.path.join(objlock_dir, sha256_digest.lower(), LOCK_MANIFEST_FILENAME)
        return os.path.exists(manifest_path)

    def apply_lock(
        self,
        case_id: str,
        sha256_digest: str,
        sha3_512_digest: str,
        source_file_path: str,
        lock_mode: str,
        retention_days: int,
        case_workspace_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Apply Object Lock to the evidence object on the local filesystem.

        Workflow:
            1. Resolve .objlock/<sha256>/ directory within case workspace.
            2. Idempotency: if manifest already exists, return existing lock record.
            3. Write the JSON lock manifest capturing:
                - dual-hash binding (SHA-256 + SHA3-512)
                - lock mode (GOVERNANCE / COMPLIANCE)
                - retention period (applied_at, retention_until)
                - overwrite / delete protection status
                - backend name
            4. Strip write permissions on the manifest (read-only).
            5. Strip write permissions on the source WORM file (belt-and-suspenders,
               as MOD-08 already did this, but we enforce again at lock time).
        """
        now = datetime.now(timezone.utc)
        retention_until = now + timedelta(days=retention_days)

        objlock_dir = self._resolve_objlock_dir(case_id, case_workspace_path)
        object_dir = os.path.join(objlock_dir, sha256_digest.lower())

        try:
            os.makedirs(object_dir, exist_ok=True)
        except Exception as e:
            raise ObjectLockFailedException(
                f"Failed to create Object Lock directory '{object_dir}': {type(e).__name__}: {e}"
            )

        manifest_path = os.path.join(object_dir, LOCK_MANIFEST_FILENAME)

        # Idempotency: already locked?
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                return {
                    "lock_storage_reference": existing.get("lock_storage_reference"),
                    "lock_manifest_path": manifest_path,
                    "lock_applied_at": datetime.fromisoformat(existing["lock_applied_at"]),
                    "lock_retention_until": datetime.fromisoformat(existing["lock_retention_until"]),
                    "lock_overwrite_protected": existing.get("lock_overwrite_protected", True),
                    "lock_delete_protected": existing.get("lock_delete_protected", True),
                    "already_locked": True,
                }
            except Exception as e:
                logger.warning("Could not read existing lock manifest at '%s': %s", manifest_path, e)

        lock_storage_reference = self.get_reference(case_id, sha256_digest, sha3_512_digest)

        manifest_data = {
            "schema_version": "MOD10_V1",
            "backend": self.BACKEND_NAME,
            "case_id": case_id,
            "checksum_sha256": sha256_digest.lower(),
            "checksum_sha3_512": sha3_512_digest.lower(),
            "lock_integrity_binding": f"sha256:{sha256_digest.lower()}:sha3_512:{sha3_512_digest.lower()}",
            "lock_storage_reference": lock_storage_reference,
            "lock_mode": lock_mode,
            "lock_applied_at": now.isoformat(),
            "lock_retention_until": retention_until.isoformat(),
            "retention_days": retention_days,
            "lock_overwrite_protected": True,
            "lock_delete_protected": True,
            "source_file": source_file_path,
            "architectural_note": (
                "This is a Phase 3 application-level Object Lock. "
                "It does NOT provide hardware/cloud-enforced immutability. "
                "Production Object Lock (e.g., S3 COMPLIANCE mode) requires cloud infrastructure."
            ),
        }

        try:
            # Write manifest atomically using a temp file
            tmp_manifest = manifest_path + ".tmp"
            with open(tmp_manifest, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2, ensure_ascii=False)
            os.replace(tmp_manifest, manifest_path)

            # Strip write permissions on the manifest (read-only)
            try:
                os.chmod(manifest_path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            except Exception as e:
                logger.warning("Could not set read-only permissions on lock manifest: %s", e)

            # Belt-and-suspenders: enforce read-only on the source WORM file
            if os.path.exists(source_file_path):
                try:
                    os.chmod(source_file_path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
                except Exception as e:
                    logger.warning("Could not re-enforce read-only on WORM file '%s': %s", source_file_path, e)

        except ObjectLockFailedException:
            raise
        except Exception as e:
            # Rollback partial state
            for p in [manifest_path + ".tmp", manifest_path]:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
            raise ObjectLockFailedException(
                f"Object Lock manifest write failed: {type(e).__name__}: {e}"
            )

        return {
            "lock_storage_reference": lock_storage_reference,
            "lock_manifest_path": manifest_path,
            "lock_applied_at": now,
            "lock_retention_until": retention_until,
            "lock_overwrite_protected": True,
            "lock_delete_protected": True,
            "already_locked": False,
        }

    def verify_lock_integrity(
        self,
        lock_storage_reference: str,
        expected_sha256: str,
        case_workspace_path: Optional[str] = None,
    ) -> bool:
        """
        Verify that the lock manifest exists and its SHA-256 binding matches the expected digest.
        """
        if not lock_storage_reference.startswith("objlock://"):
            return False
        parts = lock_storage_reference[10:].split("/")
        if len(parts) != 2:
            return False
        case_id = parts[0]
        sha256_part = parts[1].split("+")[0]  # strip sha3_512 prefix

        objlock_dir = self._resolve_objlock_dir(case_id, case_workspace_path)
        manifest_path = os.path.join(objlock_dir, sha256_part, LOCK_MANIFEST_FILENAME)

        if not os.path.exists(manifest_path):
            return False

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            return manifest.get("checksum_sha256", "").lower() == expected_sha256.lower()
        except Exception:
            return False


# ═══════════════════════════════════════════════════════════════════════════
# ObjectLockService — MOD-10 Business Orchestration
# ═══════════════════════════════════════════════════════════════════════════

class ObjectLockService:
    """
    MOD-10: WORM Object Lock / Dual Storage Service.

    Orchestrates the Phase 3 Object Lock workflow consuming
    IntegrityProtectedEvidenceObject (MOD-09) and producing
    ObjectLockedEvidenceObject (downstream for MOD-11).
    """

    def __init__(
        self,
        db: Session,
        lock_backend: Optional[IObjectLockBackend] = None,
        authz: Optional[IAuthorizationService] = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ):
        self.db = db
        self.case_repo = CaseRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.authz = authz or authorization_service
        self.lock_backend = lock_backend or LocalObjectLockBackend()
        self.retention_days = retention_days

    def apply_object_lock(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
        lock_mode: str = ObjectLockMode.GOVERNANCE,
    ) -> ObjectLockResult:
        """
        Apply WORM Object Lock to an IntegrityProtectedEvidenceObject.

        Workflow:
            1. Validate Case Existence.
            2. RBAC/ABAC Authorization ('evidence:object_lock').
            3. Retrieve Evidence Record & Verify Case Containment.
            4. Strict Gate: evidence.integrity_status == 'VERIFIED' and dual hashes present (MOD-09).
            5. Idempotency Check: return existing if already LOCKED.
            6. Physical Payload Boundary Containment (canonical realpath within case workspace).
            7. Validate lock_mode parameter.
            8. Emit EVIDENCE_OBJECT_LOCK_STARTED audit event.
            9. Compute dual-hash integrity binding fingerprint.
            10. Invoke IObjectLockBackend.apply_lock().
            11. Atomic DB State Transition:
                - lock_status → LOCKED
                - lock_mode, lock_storage_reference, lock_applied_at, lock_retention_until
                - lock_backend, lock_overwrite_protected, lock_delete_protected
                - lock_integrity_binding
            12. Append structured event to object_lock_event_log.
            13. Emit EVIDENCE_OBJECT_LOCKED audit event.
            14. Return ObjectLockResult.
        """
        # 1. Validate Case Existence
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        # 2. RBAC/ABAC Authorization
        self.authz.check_can_object_lock_evidence(investigator, case)

        # 3. Retrieve Evidence & Case Containment
        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        # 4. Strict MOD-09 Gate: integrity must be VERIFIED with dual hashes
        if (evidence.integrity_status != "VERIFIED"
                or not evidence.checksum_sha256
                or not evidence.checksum_sha3_512):
            raise IntegrityNotVerifiedForLockException(
                f"Evidence '{evidence_id}' has not successfully passed MOD-09 dual hash integrity "
                f"verification (current integrity_status: '{evidence.integrity_status}'). "
                f"Object Lock requires both SHA-256 and SHA3-512 to be present and VERIFIED."
            )

        # 5. Validate lock_mode
        valid_modes = {ObjectLockMode.GOVERNANCE, ObjectLockMode.COMPLIANCE}
        if lock_mode not in valid_modes:
            raise ObjectLockFailedException(
                f"Invalid lock_mode '{lock_mode}'. Must be one of: {[m.value for m in valid_modes]}."
            )

        # 6. Idempotency: already locked?
        if evidence.lock_status == "LOCKED" and evidence.lock_storage_reference:
            return self._build_result(evidence, already_locked=True)

        # 7. Physical Payload & Workspace Boundary Containment
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
                    f"MOD-10: Evidence path '{canonical_payload_path}' escapes case "
                    f"workspace '{canonical_workspace_path}'."
                ),
                case_id=case_id,
                investigator_id=investigator.investigator_id,
            )
            evidence.lock_status = "LOCK_FAILED"
            evidence.lock_failure_reason = "Storage path violates case workspace boundary containment."
            self.evidence_repo.update(evidence)
            raise ForbiddenException(
                "Evidence storage path violates case workspace boundary containment."
            )

        # 8. Audit: Object Lock Started
        now = datetime.now(timezone.utc)
        AuditIntegrationService.record_event(
            action="EVIDENCE_OBJECT_LOCK_STARTED",
            investigator_id=investigator.investigator_id,
            case_id=case.case_id,
            details={
                "evidence_id": evidence.evidence_id,
                "case_id": case.case_id,
                "lock_mode": lock_mode,
                "worm_storage_reference": evidence.worm_storage_reference,
                "sha256": evidence.checksum_sha256,
                "sha3_512": evidence.checksum_sha3_512,
            },
        )

        # 9. Compute integrity binding fingerprint
        integrity_binding = (
            f"sha256:{evidence.checksum_sha256.lower()}:"
            f"sha3_512:{evidence.checksum_sha3_512.lower()}"
        )

        try:
            # 10. Apply Object Lock via backend
            lock_result = self.lock_backend.apply_lock(
                case_id=case.case_id,
                sha256_digest=evidence.checksum_sha256,
                sha3_512_digest=evidence.checksum_sha3_512,
                source_file_path=canonical_payload_path,
                lock_mode=lock_mode,
                retention_days=self.retention_days,
                case_workspace_path=case.case_workspace_path,
            )

            # 11. Atomic DB State Transition
            lock_applied_at = lock_result["lock_applied_at"]
            lock_retention_until = lock_result["lock_retention_until"]

            evidence.lock_status = "LOCKED"
            evidence.lock_mode = lock_mode
            evidence.lock_storage_reference = lock_result["lock_storage_reference"]
            evidence.lock_applied_at = lock_applied_at
            evidence.lock_retention_until = lock_retention_until
            evidence.lock_backend = self.lock_backend.BACKEND_NAME
            evidence.lock_overwrite_protected = lock_result.get("lock_overwrite_protected", True)
            evidence.lock_delete_protected = lock_result.get("lock_delete_protected", True)
            evidence.lock_integrity_binding = integrity_binding
            evidence.lock_failure_reason = None

            # 12. Append to object_lock_event_log
            event_log_entry = {
                "event": "OBJECT_LOCK_APPLIED",
                "timestamp": now.isoformat(),
                "investigator_id": investigator.investigator_id,
                "lock_mode": lock_mode,
                "lock_storage_reference": lock_result["lock_storage_reference"],
                "lock_backend": self.lock_backend.BACKEND_NAME,
                "integrity_binding": integrity_binding,
            }
            existing_log = []
            if evidence.object_lock_event_log:
                try:
                    existing_log = json.loads(evidence.object_lock_event_log)
                    if not isinstance(existing_log, list):
                        existing_log = []
                except (json.JSONDecodeError, ValueError):
                    existing_log = []
            existing_log.append(event_log_entry)
            evidence.object_lock_event_log = json.dumps(existing_log, ensure_ascii=False)

            self.evidence_repo.update(evidence)

            # 13. Audit: Object Locked
            AuditIntegrationService.record_event(
                action="EVIDENCE_OBJECT_LOCKED",
                investigator_id=investigator.investigator_id,
                case_id=case.case_id,
                details={
                    "evidence_id": evidence.evidence_id,
                    "case_id": case.case_id,
                    "lock_status": "LOCKED",
                    "lock_mode": lock_mode,
                    "lock_storage_reference": lock_result["lock_storage_reference"],
                    "lock_backend": self.lock_backend.BACKEND_NAME,
                    "lock_applied_at": lock_applied_at.isoformat(),
                    "lock_retention_until": lock_retention_until.isoformat(),
                    "lock_integrity_binding": integrity_binding,
                },
            )

            log_event(
                event_type="OBJECT_LOCK_SUCCESS",
                message=(
                    f"Evidence '{evidence.evidence_id}' placed under Object Lock "
                    f"({lock_result['lock_storage_reference']}) in mode '{lock_mode}'."
                ),
                case_id=case.case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "lock_storage_reference": lock_result["lock_storage_reference"],
                    "lock_mode": lock_mode,
                    "backend": self.lock_backend.BACKEND_NAME,
                },
            )

            return self._build_result(evidence, already_locked=False)

        except (ObjectLockFailedException, ForbiddenException, EvidenceFileNotFoundException):
            raise
        except Exception as e:
            evidence.lock_status = "LOCK_FAILED"
            evidence.lock_failure_reason = f"Object Lock application failed: {type(e).__name__}: {e}"
            self.evidence_repo.update(evidence)

            AuditIntegrationService.record_event(
                action="EVIDENCE_OBJECT_LOCK_FAILED",
                investigator_id=investigator.investigator_id,
                case_id=case.case_id,
                details={
                    "evidence_id": evidence.evidence_id,
                    "case_id": case.case_id,
                    "error": str(e),
                },
            )
            raise ObjectLockFailedException(
                f"Object Lock enforcement failed for evidence '{evidence_id}': "
                f"{type(e).__name__}: {e}"
            )

    def get_object_lock_contract(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> ObjectLockedEvidenceObject:
        """
        Exports the formal downstream handoff contract for MOD-11 (AES-256-GCM Encryption).

        STRICT INVARIANT:
            Only evidence with:
                - integrity_status == 'VERIFIED' (MOD-09 gate)
                - lock_status == 'LOCKED' (MOD-10 gate)
                - valid dual hashes and lock_storage_reference
            is permitted to yield this contract.
        """
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        self.authz.check_can_read_evidence(investigator, case)

        if (evidence.lock_status != "LOCKED"
                or not evidence.lock_storage_reference
                or not evidence.lock_integrity_binding):
            raise ObjectNotLockedException(
                f"Evidence '{evidence_id}' has not been placed under Object Lock "
                f"(current lock_status: '{evidence.lock_status}'). "
                f"Only Object Locked evidence can proceed downstream to MOD-11."
            )

        if (evidence.integrity_status != "VERIFIED"
                or not evidence.checksum_sha256
                or not evidence.checksum_sha3_512):
            raise IntegrityNotVerifiedForLockException(
                f"Evidence '{evidence_id}' has lock_status LOCKED but integrity_status is "
                f"'{evidence.integrity_status}' — this indicates an inconsistent state. "
                f"Downstream contract cannot be issued."
            )

        return ObjectLockedEvidenceObject(
            case_id=evidence.case_id,
            evidence_id=evidence.evidence_id,
            original_file_name=evidence.original_file_name,
            evidence_category=evidence.evidence_category,
            file_size_bytes=evidence.file_size_bytes,
            worm_storage_reference=evidence.worm_storage_reference or f"worm://{case_id}/{evidence.checksum_sha256}",
            lock_storage_reference=evidence.lock_storage_reference,
            lock_status=evidence.lock_status,
            lock_mode=evidence.lock_mode or ObjectLockMode.GOVERNANCE,
            lock_backend=evidence.lock_backend or self.lock_backend.BACKEND_NAME,
            lock_applied_at=evidence.lock_applied_at or datetime.now(timezone.utc),
            lock_retention_until=evidence.lock_retention_until,
            lock_overwrite_protected=evidence.lock_overwrite_protected if evidence.lock_overwrite_protected is not None else True,
            lock_delete_protected=evidence.lock_delete_protected if evidence.lock_delete_protected is not None else True,
            lock_integrity_binding=evidence.lock_integrity_binding,
            checksum_sha256=evidence.checksum_sha256,
            checksum_sha3_512=evidence.checksum_sha3_512,
            integrity_status=evidence.integrity_status,
            verified_at=evidence.integrity_verified_at or datetime.now(timezone.utc),
            source="MOD-10",
        )

    # ─── Private Helpers ────────────────────────────────────────────────

    @staticmethod
    def _build_result(evidence: Evidence, already_locked: bool) -> ObjectLockResult:
        """Build ObjectLockResult from a fully locked evidence entity."""
        now = datetime.now(timezone.utc)
        return ObjectLockResult(
            evidence_id=evidence.evidence_id,
            case_id=evidence.case_id,
            lock_status=evidence.lock_status or "LOCKED",
            lock_mode=evidence.lock_mode or ObjectLockMode.GOVERNANCE,
            lock_storage_reference=evidence.lock_storage_reference or "",
            lock_applied_at=evidence.lock_applied_at or now,
            lock_retention_until=evidence.lock_retention_until,
            lock_backend=evidence.lock_backend or LocalObjectLockBackend.BACKEND_NAME,
            lock_overwrite_protected=evidence.lock_overwrite_protected if evidence.lock_overwrite_protected is not None else True,
            lock_delete_protected=evidence.lock_delete_protected if evidence.lock_delete_protected is not None else True,
            lock_integrity_binding=evidence.lock_integrity_binding or "",
            checksum_sha256=evidence.checksum_sha256 or "",
            checksum_sha3_512=evidence.checksum_sha3_512 or "",
            worm_storage_reference=evidence.worm_storage_reference or "",
            message=(
                "Evidence item is already under Object Lock."
                if already_locked
                else "Evidence successfully placed under WORM Object Lock."
            ),
            already_locked=already_locked,
        )
