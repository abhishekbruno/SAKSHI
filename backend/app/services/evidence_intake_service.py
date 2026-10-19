"""
Core domain service for SAKSHI Evidence Intake Service (MOD-05).
Implements raw evidence registration, canonical Evidence ID generation,
filename sanitization, Case Workspace staging, and downstream handoff contract creation.
"""
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Optional, List, Tuple, BinaryIO, Union
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.evidence import Evidence
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.core.security import AuthenticatedInvestigator
from app.core.errors import (
    CaseNotFoundException,
    EvidenceNotFoundException,
    IngestionGateClosedException,
    InvalidEvidenceDataException,
)
from app.core.logging import log_event
from app.services.auth_service import IAuthorizationService, authorization_service
from app.services.stage_engine import stage_engine
from app.services.audit_integration import AuditIntegrationService
from app.schemas.evidence import (
    EvidenceIntakeMetadata,
    EvidenceResponse,
    EvidenceListResponse,
    RegisteredEvidenceObject,
    EvidenceIntakeStatus,
)


class EvidenceIntakeService:
    def __init__(
        self,
        db: Session,
        authz_service: IAuthorizationService = authorization_service
    ):
        self.db = db
        self.case_repo = CaseRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.authz = authz_service

    @staticmethod
    def generate_evidence_id() -> str:
        """
        Generates a collision-resistant, canonical Evidence ID.
        Strategy: Year + 8-character cryptographically secure hexadecimal entropy.
        Format: SAKSHI-EVID-{YYYY}-{HEX8}
        """
        year = datetime.now(timezone.utc).year
        suffix = secrets.token_hex(4).upper()
        return f"SAKSHI-EVID-{year}-{suffix}"

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Forensically sanitizes client-provided filenames against directory traversal and control characters.
        Strips path components, null bytes, and non-printable characters.
        """
        if not filename or not filename.strip():
            return f"evidence_{secrets.token_hex(4)}.bin"

        # Extract only the base name (prevents directory traversal e.g. ../../etc/passwd)
        base = os.path.basename(filename.strip().replace("\\", "/"))

        # Remove null bytes and non-printable characters
        cleaned = re.sub(r'[\x00-\x1f\x7f]', '', base)

        # Remove illegal characters for filesystems
        cleaned = re.sub(r'[<>:"/\\|?*]', '_', cleaned)

        # Neutralize leading dots to avoid hidden files
        cleaned = cleaned.lstrip(".")

        if not cleaned:
            return f"evidence_{secrets.token_hex(4)}.bin"

        # Cap length to 255 characters while preserving extension
        if len(cleaned) > 255:
            name, ext = os.path.splitext(cleaned)
            cleaned = name[: 255 - len(ext)] + ext

        return cleaned

    @staticmethod
    def to_evidence_response(evidence: Evidence) -> EvidenceResponse:
        """Serializes an internal Evidence ORM entity into public API response schema."""
        return EvidenceResponse(
            evidence_id=evidence.evidence_id,
            case_id=evidence.case_id,
            original_file_name=evidence.original_file_name,
            stored_file_name=evidence.stored_file_name,
            evidence_category=evidence.evidence_category,
            declared_mime_type=evidence.declared_mime_type,
            file_size_bytes=evidence.file_size_bytes,
            collection_datetime=evidence.collection_datetime,
            collection_location=evidence.collection_location,
            source_device_or_person=evidence.source_device_or_person,
            description=evidence.description,
            submitting_investigator_id=evidence.submitting_investigator_id,
            status=evidence.status,
            raw_storage_path=evidence.raw_storage_path,
            detected_mime_type=getattr(evidence, "detected_mime_type", None),
            detected_format=getattr(evidence, "detected_format", None),
            validation_reason=getattr(evidence, "validation_reason", None),
            validated_at=getattr(evidence, "validated_at", None),
            antivirus_status=getattr(evidence, "antivirus_status", None),
            antivirus_scanner=getattr(evidence, "antivirus_scanner", None),
            antivirus_threat_name=getattr(evidence, "antivirus_threat_name", None),
            antivirus_message=getattr(evidence, "antivirus_message", None),
            antivirus_scanned_at=getattr(evidence, "antivirus_scanned_at", None),
            checksum_algorithm=getattr(evidence, "checksum_algorithm", None),
            checksum_sha256=getattr(evidence, "checksum_sha256", None),
            checksum_computed_at=getattr(evidence, "checksum_computed_at", None),
            worm_status=getattr(evidence, "worm_status", None),
            worm_storage_reference=getattr(evidence, "worm_storage_reference", None),
            worm_committed_at=getattr(evidence, "worm_committed_at", None),
            checksum_sha3_512=getattr(evidence, "checksum_sha3_512", None),
            sha3_512_computed_at=getattr(evidence, "sha3_512_computed_at", None),
            integrity_status=getattr(evidence, "integrity_status", None),
            integrity_verified_at=getattr(evidence, "integrity_verified_at", None),
            integrity_verification_message=getattr(evidence, "integrity_verification_message", None),
            created_at=evidence.created_at,
            updated_at=evidence.updated_at,
        )

    @staticmethod
    def to_registered_evidence_object(evidence: Evidence) -> RegisteredEvidenceObject:
        """Exports the formal downstream contract for MOD-06 (MIME / Signature Validation)."""
        return RegisteredEvidenceObject(
            evidence_id=evidence.evidence_id,
            case_id=evidence.case_id,
            staged_file_path=evidence.raw_storage_path,
            original_file_name=evidence.original_file_name,
            declared_mime_type=evidence.declared_mime_type,
            evidence_category=evidence.evidence_category,
            file_size_bytes=evidence.file_size_bytes,
            submitting_investigator_id=evidence.submitting_investigator_id,
            intake_status=evidence.status,
            registered_at=evidence.created_at,
        )

    def register_evidence(
        self,
        case_id: str,
        file_payload: Union[bytes, BinaryIO],
        original_filename: str,
        metadata: EvidenceIntakeMetadata,
        investigator: AuthenticatedInvestigator,
    ) -> EvidenceResponse:
        """
        Source-defined function: REGISTER RAW EVIDENCE (MOD-05).
        Associates evidence with Case ID, verifies ingestion gate, captures metadata,
        stages raw file into case workspace, and creates Registered Evidence object.
        """
        # 1. Verify Case Existence
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        # 2. MOD-03: Authorization Check
        self.authz.check_can_intake_evidence(investigator, case)

        # 3. MOD-04: Stage Engine Ingestion Gate Verification
        if not stage_engine.is_ingestion_permitted(case.lifecycle_stage):
            raise IngestionGateClosedException(
                f"Evidence intake rejected: Case '{case_id}' is in stage '{case.lifecycle_stage}'. "
                f"Intake requires the lifecycle stage to be 'EVIDENCE_INGESTION'."
            )

        # 4. Extract content and compute size
        if isinstance(file_payload, bytes):
            content_bytes = file_payload
        else:
            content_bytes = file_payload.read()

        file_size = len(content_bytes)
        if file_size == 0:
            raise InvalidEvidenceDataException("Uploaded evidence payload cannot be empty (0 bytes).")

        # 5. Generate canonical Evidence ID and sanitize filename
        evidence_id = self.generate_evidence_id()
        sanitized_filename = self.sanitize_filename(original_filename)

        # 6. Stage physical file in Case Workspace
        # Path: {case_workspace_path}/evidence/raw/{evidence_id}/{sanitized_filename}
        staging_dir = os.path.join(case.case_workspace_path, "evidence", "raw", evidence_id)
        os.makedirs(staging_dir, exist_ok=True)
        staged_file_path = os.path.join(staging_dir, sanitized_filename)

        with open(staged_file_path, "wb") as f:
            f.write(content_bytes)

        # 7. Create Evidence Record in Database
        evidence = Evidence(
            evidence_id=evidence_id,
            case_id=case_id,
            original_file_name=original_filename,
            stored_file_name=sanitized_filename,
            evidence_category=metadata.evidence_category.value,
            declared_mime_type=metadata.declared_mime_type,
            file_size_bytes=file_size,
            collection_datetime=metadata.collection_datetime,
            collection_location=metadata.collection_location,
            source_device_or_person=metadata.source_device_or_person,
            description=metadata.description,
            submitting_investigator_id=investigator.investigator_id,
            status=EvidenceIntakeStatus.REGISTERED_INTAKE.value,
            raw_storage_path=staged_file_path,
        )

        persisted = self.evidence_repo.create(evidence)

        # 8. Record structured audit event
        AuditIntegrationService.record_event(
            action="EVIDENCE_INTAKE",
            investigator_id=investigator.investigator_id,
            case_id=case_id,
            details={
                "evidence_id": evidence_id,
                "file_name": sanitized_filename,
                "original_file_name": original_filename,
                "evidence_category": metadata.evidence_category.value,
                "declared_mime_type": metadata.declared_mime_type,
                "file_size_bytes": file_size,
                "status": EvidenceIntakeStatus.REGISTERED_INTAKE.value,
            }
        )

        log_event(
            event_type="EVIDENCE_INTAKE_SUCCESS",
            message=f"Evidence '{evidence_id}' successfully registered under case '{case_id}'",
            case_id=case_id,
            investigator_id=investigator.investigator_id,
            extra_data={"evidence_id": evidence_id, "size_bytes": file_size}
        )

        return self.to_evidence_response(persisted)

    def list_evidence(
        self,
        case_id: str,
        investigator: AuthenticatedInvestigator,
        skip: int = 0,
        limit: int = 100,
    ) -> EvidenceListResponse:
        """Retrieves registered evidence items for a case, enforcing authorization."""
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        self.authz.check_can_read_evidence(investigator, case)

        items = self.evidence_repo.list_by_case_id(case_id, skip=skip, limit=limit)
        total = self.evidence_repo.count_by_case_id(case_id)

        return EvidenceListResponse(
            case_id=case_id,
            total=total,
            items=[self.to_evidence_response(item) for item in items]
        )

    def get_evidence(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> EvidenceResponse:
        """Retrieves a single registered evidence object, enforcing case isolation."""
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        self.authz.check_can_read_evidence(investigator, case)

        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        return self.to_evidence_response(evidence)
