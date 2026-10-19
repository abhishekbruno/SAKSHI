"""
Evidence Intake REST API Endpoints (MOD-05).
Version: v1 (/api/v1/cases/{case_id}/evidence)
Phase 2: Evidence Ingestion.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, Query, status

from app.api.deps import (
    get_current_investigator,
    get_evidence_intake_service,
    get_mime_validation_service,
    get_antivirus_scan_service,
    get_worm_commit_service,
    get_integrity_service,
    get_object_lock_service,
    get_encryption_service,
)
from app.core.security import AuthenticatedInvestigator
from app.core.errors import InvalidEvidenceDataException
from app.services.evidence_intake_service import EvidenceIntakeService
from app.services.mime_validation_service import MimeValidationService
from app.services.antivirus_scan_service import AntivirusScanService
from app.services.worm_commit_service import WORMCommitService
from app.services.integrity_service import IntegrityService
from app.services.object_lock_service import ObjectLockService
from app.services.encryption_service import EncryptionService
from app.schemas.evidence import (
    EvidenceCategory,
    EvidenceIntakeMetadata,
    EvidenceResponse,
    EvidenceListResponse,
    RegisteredEvidenceObject,
    MIMEValidationResult,
    ValidatedEvidenceObject,
    AntivirusScanResult,
    ScannedEvidenceObject,
    WORMCommitResult,
    WORMCommittedEvidenceObject,
    IntegrityVerificationResult,
    IntegrityProtectedEvidenceObject,
    ObjectLockResult,
    ObjectLockedEvidenceObject,
    EncryptionResult,
    EncryptedEvidenceObject,
    EncryptionVerificationResult,
)

router = APIRouter(prefix="/cases/{case_id}/evidence", tags=["Evidence Ingestion (MOD-05)"])


@router.post(
    "",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register raw evidence item under an investigation case"
)
async def intake_evidence(
    case_id: str,
    file: UploadFile = File(..., description="Raw evidence binary payload (PDF, image, audio, CDR spreadsheet, etc.)"),
    evidence_category: EvidenceCategory = Form(..., description="Forensic evidence category"),
    declared_mime_type: str = Form(..., description="Client-declared MIME type"),
    collection_datetime: Optional[str] = Form(None, description="ISO-8601 formatted collection timestamp"),
    collection_location: Optional[str] = Form(None, description="Physical collection location or scene"),
    source_device_or_person: Optional[str] = Form(None, description="Source device or custodial reference"),
    description: Optional[str] = Form(None, description="Forensic description"),
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: EvidenceIntakeService = Depends(get_evidence_intake_service),
) -> EvidenceResponse:
    """
    Source-defined function: REGISTER RAW EVIDENCE.
    Intakes raw evidence payload, verifies Case ID & Stage Engine gate (EVIDENCE_INGESTION),
    sanitizes filename, stages payload into isolated workspace boundary, and catalogs metadata.
    """
    parsed_dt = None
    if collection_datetime:
        try:
            parsed_dt = datetime.fromisoformat(collection_datetime.replace("Z", "+00:00"))
        except ValueError as e:
            raise InvalidEvidenceDataException(f"Invalid ISO-8601 format for collection_datetime: {str(e)}")

    metadata = EvidenceIntakeMetadata(
        evidence_category=evidence_category,
        declared_mime_type=declared_mime_type,
        collection_datetime=parsed_dt,
        collection_location=collection_location,
        source_device_or_person=source_device_or_person,
        description=description,
    )

    content = await file.read()
    original_filename = file.filename or "evidence.bin"

    return service.register_evidence(
        case_id=case_id,
        file_payload=content,
        original_filename=original_filename,
        metadata=metadata,
        investigator=investigator,
    )


@router.get(
    "",
    response_model=EvidenceListResponse,
    summary="List registered evidence items for a case"
)
def list_evidence(
    case_id: str,
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: EvidenceIntakeService = Depends(get_evidence_intake_service),
) -> EvidenceListResponse:
    """Returns all evidence items registered under the specified case for authorized investigators."""
    return service.list_evidence(
        case_id=case_id,
        investigator=investigator,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{evidence_id}",
    response_model=EvidenceResponse,
    summary="Retrieve details of a registered evidence item"
)
def get_evidence(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: EvidenceIntakeService = Depends(get_evidence_intake_service),
) -> EvidenceResponse:
    """Returns full metadata for an individual registered evidence item."""
    return service.get_evidence(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
    )


@router.get(
    "/{evidence_id}/contract",
    response_model=RegisteredEvidenceObject,
    summary="Export RegisteredEvidenceObject handoff contract for MOD-06"
)
def get_evidence_contract(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: EvidenceIntakeService = Depends(get_evidence_intake_service),
) -> RegisteredEvidenceObject:
    """Exports formal downstream contract for MOD-06 (MIME / Signature Validation)."""
    evidence = service.get_evidence(case_id=case_id, evidence_id=evidence_id, investigator=investigator)
    raw_entity = service.evidence_repo.get_by_evidence_id(evidence_id)
    return service.to_registered_evidence_object(raw_entity)


@router.post(
    "/{evidence_id}/validate",
    response_model=MIMEValidationResult,
    summary="Validate evidence MIME type against actual binary signature (MOD-06)"
)
def validate_evidence_mime(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: MimeValidationService = Depends(get_mime_validation_service),
) -> MIMEValidationResult:
    """
    MOD-06: MIME / File Signature Validation.
    Inspects actual binary magic bytes, enforces allowlist, checks extension consistency,
    rejects disguised executables, and sets status to VALIDATED or REJECTED.
    """
    return service.validate_evidence(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
    )


@router.get(
    "/{evidence_id}/validated-contract",
    response_model=ValidatedEvidenceObject,
    summary="Export ValidatedEvidenceObject handoff contract for MOD-07 (Antivirus Scan)"
)
def get_validated_evidence_contract(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: MimeValidationService = Depends(get_mime_validation_service),
) -> ValidatedEvidenceObject:
    """
    Downstream Handoff Contract for MOD-07 (Antivirus Scan).
    Only returns contract if evidence has status == 'VALIDATED'.
    """
    return service.get_validated_evidence_object(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
    )


@router.post(
    "/{evidence_id}/scan",
    response_model=AntivirusScanResult,
    summary="Scan staged evidence for malware, viruses, and hostile payloads (MOD-07)"
)
def scan_evidence_antivirus(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: AntivirusScanService = Depends(get_antivirus_scan_service),
) -> AntivirusScanResult:
    """
    MOD-07: Antivirus Scan.
    Consumes ValidatedEvidenceObject from MOD-06.
    Performs passive signature scanning on staged payload without executing it.
    Updates status to CLEAN or QUARANTINED, persists scan metadata, and emits audit events.
    """
    return service.scan_evidence(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
    )


@router.get(
    "/{evidence_id}/scanned-contract",
    response_model=ScannedEvidenceObject,
    summary="Export ScannedEvidenceObject handoff contract for MOD-08 (WORM Commit)"
)
def get_scanned_evidence_contract(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: AntivirusScanService = Depends(get_antivirus_scan_service),
) -> ScannedEvidenceObject:
    """
    Downstream Handoff Contract for MOD-08 (WORM Commit + Checksum).
    Strict Invariant: Only evidence verified as CLEAN can yield this contract.
    Quarantined, infected, or unscanned items are strictly denied.
    """
    return service.get_scanned_evidence_object(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
    )


@router.post(
    "/{evidence_id}/worm-commit",
    response_model=WORMCommitResult,
    summary="Commit clean evidence payload to WORM storage with SHA-256 pre-hash (MOD-08)"
)
def commit_evidence_worm(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: WORMCommitService = Depends(get_worm_commit_service),
) -> WORMCommitResult:
    """
    MOD-08: WORM Commit + Checksum.
    Consumes ScannedEvidenceObject from MOD-07 (verifies status == 'CLEAN').
    Computes chunked SHA-256 pre-hash, stages payload to immutable WORM storage,
    generates canonical reference worm://<case-id>/<sha256>, transitions state to COMMITTED,
    and emits structured audit logs.
    """
    return service.commit_evidence(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
    )


@router.get(
    "/{evidence_id}/worm-contract",
    response_model=WORMCommittedEvidenceObject,
    summary="Export WORMCommittedEvidenceObject handoff contract for Phase 3"
)
def get_worm_committed_contract(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: WORMCommitService = Depends(get_worm_commit_service),
) -> WORMCommittedEvidenceObject:
    """
    Downstream Handoff Contract for Phase 3 (Security & Integrity).
    Strict Invariant: Only evidence committed to WORM storage with verified SHA-256 digest
    can yield this contract.
    """
    return service.get_worm_committed_evidence_object(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
    )


@router.post(
    "/{evidence_id}/integrity",
    response_model=IntegrityVerificationResult,
    summary="Execute MOD-09 dual hashing (SHA-256 verification + SHA3-512) and integrity verification"
)
def verify_evidence_integrity(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: IntegrityService = Depends(get_integrity_service),
) -> IntegrityVerificationResult:
    """
    MOD-09: Dual Hashing (SHA-256 + SHA3-512) & Integrity Verification.
    Consumes WORMCommittedEvidenceObject from MOD-08.
    Recomputes SHA-256 and compares against MOD-08 pre-hash (fail-closed on mismatch).
    Computes 128-character lowercase hexadecimal SHA3-512 digest.
    Updates integrity status to 'VERIFIED' and records structured audit logs.
    """
    return service.verify_and_compute_integrity(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
    )


@router.get(
    "/{evidence_id}/integrity-contract",
    response_model=IntegrityProtectedEvidenceObject,
    summary="Export IntegrityProtectedEvidenceObject handoff contract for Phase 3/4"
)
def get_integrity_protected_contract(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: IntegrityService = Depends(get_integrity_service),
) -> IntegrityProtectedEvidenceObject:
    """
    Downstream Handoff Contract for subsequent Phase 3 / Phase 4 modules.
    Strict Invariant: Only evidence that successfully passed dual hash integrity verification
    (integrity_status == 'VERIFIED') can yield this contract.
    """
    return service.get_integrity_contract(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
    )


@router.post(
    "/{evidence_id}/object-lock",
    response_model=ObjectLockResult,
    summary="Apply WORM Object Lock to integrity-verified evidence (MOD-10)"
)
def apply_evidence_object_lock(
    case_id: str,
    evidence_id: str,
    lock_mode: str = "GOVERNANCE",
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: ObjectLockService = Depends(get_object_lock_service),
) -> ObjectLockResult:
    """
    MOD-10: WORM Object Lock / Dual Storage.
    Consumes IntegrityProtectedEvidenceObject from MOD-09 (requires integrity_status == 'VERIFIED').
    Applies an immutable Object Lock record binding SHA-256 + SHA3-512 digests with retention metadata.
    Generates canonical objlock://<case_id>/<sha256>+<sha3_512_prefix16> reference.
    Enforces overwrite and deletion protection at application level.
    Emits structured tamper-evident audit events.
    Produces ObjectLockedEvidenceObject downstream contract for MOD-11 (AES-256-GCM Encryption).
    """
    return service.apply_object_lock(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
        lock_mode=lock_mode,
    )


@router.get(
    "/{evidence_id}/object-lock-contract",
    response_model=ObjectLockedEvidenceObject,
    summary="Export ObjectLockedEvidenceObject handoff contract for MOD-11 (AES-256-GCM Encryption)"
)
def get_object_locked_contract(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: ObjectLockService = Depends(get_object_lock_service),
) -> ObjectLockedEvidenceObject:
    """
    Downstream Handoff Contract for MOD-11 (AES-256-GCM Encryption).
    Strict Invariant:
        Evidence must have integrity_status == 'VERIFIED' (MOD-09 gate)
        AND lock_status == 'LOCKED' (MOD-10 gate) before this contract can be yielded.
    """
    return service.get_object_lock_contract(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
    )


@router.post(
    "/{evidence_id}/encrypt",
    response_model=EncryptionResult,
    summary="Apply AES-256-GCM authenticated encryption to object-locked evidence (MOD-11)"
)
def encrypt_evidence(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: EncryptionService = Depends(get_encryption_service),
) -> EncryptionResult:
    """
    MOD-11: AES-256-GCM Authenticated Encryption.
    Consumes ObjectLockedEvidenceObject from MOD-10 (requires lock_status == 'LOCKED' and integrity_status == 'VERIFIED').
    Applies authenticated symmetric encryption using a 256-bit case-isolated key.
    Generates cryptographically secure 96-bit nonce and binds case/evidence metadata in AAD.
    Produces EncryptedEvidenceObject downstream contract for MOD-12 (TLS 1.3 / mTLS).
    """
    return service.encrypt_evidence(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
    )


@router.get(
    "/{evidence_id}/encryption-contract",
    response_model=EncryptedEvidenceObject,
    summary="Export EncryptedEvidenceObject handoff contract for MOD-12 (TLS 1.3 / mTLS)"
)
def get_encrypted_contract(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: EncryptionService = Depends(get_encryption_service),
) -> EncryptedEvidenceObject:
    """
    Downstream Handoff Contract for MOD-12 (TLS 1.3 / mTLS).
    Strict Invariants:
        Evidence must have:
            - integrity_status == 'VERIFIED' (MOD-09 gate)
            - lock_status == 'LOCKED' (MOD-10 gate)
            - encryption_status == 'ENCRYPTED' (MOD-11 gate)
    """
    return service.get_encryption_contract(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
    )


@router.post(
    "/{evidence_id}/verify-encryption",
    response_model=EncryptionVerificationResult,
    summary="Verify AES-256-GCM authentication tag and ciphertext integrity (MOD-11)"
)
def verify_encryption_integrity(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: EncryptionService = Depends(get_encryption_service),
) -> EncryptionVerificationResult:
    """
    MOD-11: Cryptographic Encryption Verification.
    Validates ciphertext checksum, verifies 128-bit GCM authentication tag,
    and performs trial round-trip dual-hash match without leaking raw plaintext payload.
    """
    return service.verify_encryption_integrity(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
    )

