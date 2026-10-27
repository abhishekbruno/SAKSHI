"""
Evidence Intake REST API Endpoints (MOD-05).
Version: v1 (/api/v1/cases/{case_id}/evidence)
Phase 2: Evidence Ingestion.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import (
    get_db,
    get_current_investigator,
    get_evidence_intake_service,
    get_mime_validation_service,
    get_antivirus_scan_service,
    get_worm_commit_service,
    get_evidence_pipeline_orchestrator,
    get_integrity_service,
    get_object_lock_service,
    get_encryption_service,
    get_rag_indexing_service,
    get_evidence_extraction_service,
)
from app.core.security import AuthenticatedInvestigator
from app.core.errors import InvalidEvidenceDataException
from app.services.evidence_intake_service import EvidenceIntakeService
from app.services.mime_validation_service import MimeValidationService
from app.services.antivirus_scan_service import AntivirusScanService
from app.services.worm_commit_service import WORMCommitService
from app.services.evidence_pipeline_orchestrator import EvidencePipelineOrchestrator
from app.services.integrity_service import IntegrityService
from app.services.object_lock_service import ObjectLockService
from app.services.encryption_service import EncryptionService
from app.services.rag_indexing_service import RAGIndexingService
from app.services.evidence_extraction_service import EvidenceExtractionService
from app.schemas.rag import RAGDocumentSummary
import os
from fastapi.responses import FileResponse
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.rag_repository import RAGRepository
from app.services.auth_service import authorization_service
from app.core.errors import (
    InvalidEvidenceDataException,
    CaseNotFoundException,
    EvidenceNotFoundException,
    EvidenceFileNotFoundException,
)
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
    PipelineExecutionResult,
    PipelineExecutionStatus,
    EvidenceExtractedFactsResponse,
    FactReviewRequest,
    FactReviewResponse,
)

router = APIRouter(prefix="/cases/{case_id}/evidence", tags=["Evidence Ingestion (MOD-05)"])



def _pipeline_response_status(
    result: PipelineExecutionResult,
    is_resume: bool,
) -> int:
    """Map a safe, structured workflow result to an HTTP response status."""
    if result.overall_status == PipelineExecutionStatus.SUCCESS:
        return status.HTTP_200_OK if is_resume else status.HTTP_201_CREATED
    if result.overall_status in {
        PipelineExecutionStatus.MIME_VALIDATION_FAILED,
        PipelineExecutionStatus.ANTIVIRUS_QUARANTINED,
        PipelineExecutionStatus.INTEGRITY_FAILED,
    }:
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    if result.overall_status == PipelineExecutionStatus.RETRYABLE_ERROR:
        return status.HTTP_503_SERVICE_UNAVAILABLE
    return status.HTTP_500_INTERNAL_SERVER_ERROR



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


@router.post(
    "/pipeline",
    response_model=PipelineExecutionResult,
    responses={
        403: {"model": PipelineExecutionResult, "description": "Authorization denied"},
        422: {"model": PipelineExecutionResult, "description": "MIME rejection or malware quarantine"},
        503: {"model": PipelineExecutionResult, "description": "Retryable operational failure"},
        500: {"model": PipelineExecutionResult, "description": "Permanent pipeline failure"},
    },
    summary="Run the MOD-05 through MOD-08 evidence-ingestion pipeline",
)
async def execute_evidence_pipeline(
    case_id: str,
    response: Response,
    file: Optional[UploadFile] = File(
        None,
        description="Raw evidence payload for a new pipeline execution",
    ),
    evidence_id: Optional[str] = Form(
        None,
        description="Existing evidence ID to resume without repeating intake",
    ),
    evidence_category: Optional[EvidenceCategory] = Form(
        None,
        description="Forensic category, required for a new upload",
    ),
    declared_mime_type: Optional[str] = Form(
        None,
        description="Client-declared MIME type, required for a new upload",
    ),
    collection_datetime: Optional[str] = Form(None, description="Optional ISO-8601 collection timestamp"),
    collection_location: Optional[str] = Form(None, description="Optional physical collection location"),
    source_device_or_person: Optional[str] = Form(None, description="Optional source or custodial reference"),
    description: Optional[str] = Form(None, description="Optional forensic description"),
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    orchestrator: EvidencePipelineOrchestrator = Depends(get_evidence_pipeline_orchestrator),
) -> PipelineExecutionResult:
    """Run a new upload once or safely resume an existing evidence record.

    A resume request accepts only ``evidence_id``.  It never accepts a second
    payload and therefore cannot silently repeat non-idempotent MOD-05 intake.
    """
    is_resume = evidence_id is not None
    if is_resume:
        if file is not None or any(
            value is not None
            for value in (
                evidence_category,
                declared_mime_type,
                collection_datetime,
                collection_location,
                source_device_or_person,
                description,
            )
        ):
            raise InvalidEvidenceDataException(
                "A pipeline resume accepts evidence_id only; do not include a file or intake metadata."
            )
        result = orchestrator.resume_existing_evidence(
            case_id=case_id,
            evidence_id=evidence_id,
            investigator=investigator,
        )
    else:
        if file is None or evidence_category is None or not declared_mime_type:
            raise InvalidEvidenceDataException(
                "A new pipeline execution requires file, evidence_category, and declared_mime_type."
            )

        parsed_datetime = None
        if collection_datetime:
            try:
                parsed_datetime = datetime.fromisoformat(collection_datetime.replace("Z", "+00:00"))
            except ValueError as exc:
                raise InvalidEvidenceDataException(
                    f"Invalid ISO-8601 format for collection_datetime: {exc}"
                )

        metadata = EvidenceIntakeMetadata(
            evidence_category=evidence_category,
            declared_mime_type=declared_mime_type,
            collection_datetime=parsed_datetime,
            collection_location=collection_location,
            source_device_or_person=source_device_or_person,
            description=description,
        )
        result = orchestrator.execute_new_evidence(
            case_id=case_id,
            file_payload=await file.read(),
            original_filename=file.filename or "evidence.bin",
            metadata=metadata,
            investigator=investigator,
        )

    response.status_code = _pipeline_response_status(result, is_resume=is_resume)
    return result


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


@router.post(
    "/{evidence_id}/index",
    response_model=RAGDocumentSummary,
    summary="Index or retry indexing for locked evidence exhibit (RAG Integration)"
)
def index_evidence(
    case_id: str,
    evidence_id: str,
    force_reindex: bool = Query(False, description="Force re-indexing even if already indexed"),
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: RAGIndexingService = Depends(get_rag_indexing_service),
    db: Session = Depends(get_db),
) -> RAGDocumentSummary:
    """
    RAG Integration Endpoint:
    Triggers or retries indexing for an evidence exhibit that has completed MOD-05 through MOD-10.
    Retrying indexing does not repeat evidence intake, antivirus scanning, or WORM commitment.
    Enforces that evidence is locked and verified prior to text extraction and embedding.
    """
    from app.repositories.case_repository import CaseRepository
    from app.services.auth_service import authorization_service
    from app.core.errors import CaseNotFoundException

    case = CaseRepository(db).get_by_case_id(case_id)
    if not case:
        raise CaseNotFoundException(case_id)
    authorization_service.check_can_modify_case(investigator, case)

    doc = service.index_evidence(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
        force_reindex=force_reindex,
    )
    return RAGDocumentSummary.model_validate(doc)


@router.get(
    "/{evidence_id}/index-status",
    response_model=Optional[RAGDocumentSummary],
    summary="Retrieve RAG indexing status for an evidence exhibit"
)
def get_evidence_index_status(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
) -> Optional[RAGDocumentSummary]:
    """
    Returns the current indexing status and document metadata for an evidence exhibit.
    """
    from app.repositories.case_repository import CaseRepository
    from app.repositories.evidence_repository import EvidenceRepository
    from app.services.auth_service import authorization_service
    from app.core.errors import CaseNotFoundException, EvidenceNotFoundException

    case = CaseRepository(db).get_by_case_id(case_id)
    if not case:
        raise CaseNotFoundException(case_id)
    authorization_service.check_can_read_case(investigator, case)

    evidence = EvidenceRepository(db).get_by_evidence_id(evidence_id)
    if not evidence or evidence.case_id != case_id:
        raise EvidenceNotFoundException(evidence_id)

    rag_repo = RAGRepository(db)
    doc = rag_repo.get_document_by_evidence_and_version(evidence_id=evidence_id, processing_version="v1.0")
    if not doc:
        return None
    return RAGDocumentSummary.model_validate(doc)


@router.get(
    "/{evidence_id}/extracted-facts",
    response_model=EvidenceExtractedFactsResponse,
    summary="Retrieve extracted facts, summary, dates, entities, and statements for evidence item"
)
def get_evidence_extracted_facts(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    extraction_service: EvidenceExtractionService = Depends(get_evidence_extraction_service),
) -> EvidenceExtractedFactsResponse:
    """
    Returns authentic extracted facts with strict provenance and attribution:
    - QUOTED_FROM_SOURCE
    - EXTRACTED_BY_SOFTWARE
    - AI_INTERPRETATION
    - NEEDS_CONFIRMATION
    Includes source text offsets, page numbers, and entity classifications.
    Never invents facts or OCR results for unsupported media.
    """
    return extraction_service.extract_facts_from_evidence(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
    )


@router.post(
    "/{evidence_id}/extract-facts",
    response_model=EvidenceExtractedFactsResponse,
    summary="Trigger extraction or re-extraction of facts for evidence item"
)
def trigger_evidence_extracted_facts(
    case_id: str,
    evidence_id: str,
    force_reindex: bool = Query(False, description="Force re-indexing prior to extraction if document not yet indexed"),
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    extraction_service: EvidenceExtractionService = Depends(get_evidence_extraction_service),
) -> EvidenceExtractedFactsResponse:
    """
    Explicitly runs extraction for evidence item.
    Safe and idempotent; does not re-upload or modify raw evidence files.
    """
    return extraction_service.extract_facts_from_evidence(
        case_id=case_id,
        evidence_id=evidence_id,
        investigator=investigator,
        force_reindex=force_reindex,
    )


@router.get(
    "/{evidence_id}/file",
    summary="View or download original preserved evidence file",
)
def get_evidence_file(
    case_id: str,
    evidence_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    """
    Retrieves the authentic, unmodified original evidence file.
    Strictly case-scoped and authorization-checked.
    Never overwrites or modifies evidence; serves with immutable headers.
    """
    case_repo = CaseRepository(db)
    case = case_repo.get_by_case_id(case_id)
    if not case:
        raise CaseNotFoundException(case_id)

    authorization_service.check_can_read_evidence(investigator, case)

    evidence_repo = EvidenceRepository(db)
    evidence = evidence_repo.get_by_evidence_id(evidence_id)
    if not evidence or evidence.case_id != case_id:
        raise EvidenceNotFoundException(evidence_id)

    # Resolve physical file path
    file_path = evidence.raw_storage_path
    if not file_path or not os.path.exists(file_path):
        # Check WORM reference
        if evidence.worm_storage_reference and evidence.worm_storage_reference.startswith("worm://"):
            parts = evidence.worm_storage_reference[7:].split("/")
            if len(parts) == 2:
                digest = parts[1]
                worm_dir = os.path.join(case.case_workspace_path, "evidence", "worm")
                alt_path = os.path.join(worm_dir, digest.lower())
                if os.path.exists(alt_path):
                    file_path = alt_path

    if not file_path or not os.path.exists(file_path):
        raise EvidenceFileNotFoundException(f"Original file for exhibit '{evidence_id}' was not found on storage disk.")

    media_type = evidence.detected_mime_type or evidence.declared_mime_type or "application/octet-stream"
    filename = evidence.original_file_name or f"evidence_{evidence_id}.bin"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename,
        content_disposition_type="inline",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
            "X-Evidence-ID": evidence_id,
            "X-Case-ID": case_id,
        }
    )


@router.post(
    "/{evidence_id}/facts/{fact_id}/decision",
    response_model=FactReviewResponse,
    summary="Record investigator review decision (Confirm, Correct, Flag, Reject) on extracted fact",
)
def record_evidence_fact_decision(
    case_id: str,
    evidence_id: str,
    fact_id: str,
    payload: FactReviewRequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    extraction_service: EvidenceExtractionService = Depends(get_evidence_extraction_service),
) -> FactReviewResponse:
    """
    Records an authoritative investigator review decision on an extracted forensic claim.
    Requires justification reason; logs immutable audit event with revision history.
    """
    return extraction_service.record_fact_decision(
        case_id=case_id,
        evidence_id=evidence_id,
        fact_id=fact_id,
        request=payload,
        investigator=investigator,
    )



