"""
MOD-06: MIME / File Signature Validation Service for SAKSHI Investigation Platform.
Phase 2 — Evidence Ingestion.

Answers the question: "Does the actual binary content of this registered evidence match its claimed type?"

Responsibilities:
    - Bounded streaming inspection of file magic bytes / signatures.
    - Comparison of declared MIME against detected binary signature.
    - Detection of disguised executables, scripts, and unknown binaries.
    - Enforcement of centralized configurable evidence allowlist.
    - Extension consistency and polyglot / ambiguous format handling.
    - Case workspace boundary containment and isolation checks.
    - State transition: REGISTERED_INTAKE -> VALIDATED or REJECTED.
    - Export of ValidatedEvidenceObject contract for downstream MOD-07 (Antivirus Scan).
"""
import os
import re
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
import puremagic

from app.models.case import Case
from app.models.evidence import Evidence
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.core.security import AuthenticatedInvestigator
from app.core.errors import (
    CaseNotFoundException,
    EvidenceNotFoundException,
    EvidenceFileNotFoundException,
    MimeTypeNotAllowedException,
    MimeSignatureMismatchException,
    UnknownFileSignatureException,
    AmbiguousFileSignatureException,
    EvidenceValidationFailedException,
    ForbiddenException,
)
from app.core.logging import log_event
from app.services.auth_service import IAuthorizationService, authorization_service
from app.services.audit_integration import AuditIntegrationService
from app.schemas.evidence import (
    EvidenceIntakeStatus,
    RegisteredEvidenceObject,
    MIMEValidationResult,
    ValidatedEvidenceObject,
)

logger = logging.getLogger("sakshi.mod06.mime_validation")

VALIDATOR_VERSION = "SAKSHI-MIME-V1.0"
READ_BUFFER_SIZE = 8192  # 8 KB bounded read for header magic bytes


# ═══════════════════════════════════════════════════════════════════════════
# Centralized Configurable Evidence MIME Allowlist
# ═══════════════════════════════════════════════════════════════════════════

ALLOWED_MIME_TYPES: Dict[str, Dict[str, Any]] = {
    # Documents
    "application/pdf": {
        "format": "PDF",
        "extensions": [".pdf"],
        "equivalent_mimes": ["application/pdf", "application/vnd.fdf"],
    },
    # Images
    "image/jpeg": {
        "format": "JPEG",
        "extensions": [".jpg", ".jpeg", ".jfif", ".jpe"],
        "equivalent_mimes": ["image/jpeg"],
    },
    "image/png": {
        "format": "PNG",
        "extensions": [".png"],
        "equivalent_mimes": ["image/png"],
    },
    "image/tiff": {
        "format": "TIFF",
        "extensions": [".tif", ".tiff"],
        "equivalent_mimes": ["image/tiff"],
    },
    "image/webp": {
        "format": "WEBP",
        "extensions": [".webp"],
        "equivalent_mimes": ["image/webp"],
    },
    # Audio
    "audio/wav": {
        "format": "WAV",
        "extensions": [".wav"],
        "equivalent_mimes": ["audio/wav", "audio/x-wav"],
    },
    "audio/x-wav": {
        "format": "WAV",
        "extensions": [".wav"],
        "equivalent_mimes": ["audio/wav", "audio/x-wav"],
    },
    "audio/mpeg": {
        "format": "MP3",
        "extensions": [".mp3"],
        "equivalent_mimes": ["audio/mpeg", "audio/mp3"],
    },
    "audio/mp3": {
        "format": "MP3",
        "extensions": [".mp3"],
        "equivalent_mimes": ["audio/mpeg", "audio/mp3"],
    },
    "audio/ogg": {
        "format": "OGG",
        "extensions": [".ogg"],
        "equivalent_mimes": ["audio/ogg", "application/ogg"],
    },
    "audio/flac": {
        "format": "FLAC",
        "extensions": [".flac"],
        "equivalent_mimes": ["audio/flac", "audio/x-flac"],
    },
    # CDR Spreadsheets & Tabular Text
    "text/csv": {
        "format": "CSV",
        "extensions": [".csv"],
        "equivalent_mimes": ["text/csv", "text/plain"],
        "is_text": True,
    },
    "text/plain": {
        "format": "TEXT",
        "extensions": [".txt", ".csv", ".tsv", ".log"],
        "equivalent_mimes": ["text/plain", "text/csv"],
        "is_text": True,
    },
    "application/vnd.ms-excel": {
        "format": "XLS",
        "extensions": [".xls"],
        "equivalent_mimes": ["application/vnd.ms-excel"],
    },
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
        "format": "XLSX",
        "extensions": [".xlsx"],
        "equivalent_mimes": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/zip"],
    },
    # Digital Device Extractions & Archives
    "application/zip": {
        "format": "ZIP",
        "extensions": [".zip"],
        "equivalent_mimes": ["application/zip"],
    },
    "application/gzip": {
        "format": "GZIP",
        "extensions": [".gz", ".tar.gz"],
        "equivalent_mimes": ["application/gzip", "application/x-gzip"],
    },
    "application/json": {
        "format": "JSON",
        "extensions": [".json"],
        "equivalent_mimes": ["application/json", "text/plain"],
        "is_text": True,
    },
}

# Explicitly forbidden executable and dangerous script signatures
DANGEROUS_SIGNATURES: List[Tuple[bytes, str]] = [
    (b"MZ", "Windows Portable Executable (EXE/DLL)"),
    (b"\x7fELF", "Linux Executable and Linkable Format (ELF)"),
    (b"\xca\xfe\xba\xbe", "Mach-O Fat Binary / Java Class"),
    (b"\xfe\xed\xfa\xce", "Mach-O 32-bit Binary"),
    (b"\xfe\xed\xfa\xcf", "Mach-O 64-bit Binary"),
    (b"\xce\xfa\xed\xfe", "Mach-O 32-bit Reverse Binary"),
    (b"\xcf\xfa\xed\xfe", "Mach-O 64-bit Reverse Binary"),
    (b"#!/bin/sh", "Unix Shell Script"),
    (b"#!/bin/bash", "Unix Bash Script"),
    (b"#!/usr/bin/", "Unix Executable Script"),
    (b"<?php", "PHP Server Script"),
]


class MimeValidationService:
    def __init__(
        self,
        db: Session,
        authz_service: IAuthorizationService = authorization_service,
        allowlist: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        self.db = db
        self.case_repo = CaseRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.authz = authz_service
        self.allowlist = allowlist or ALLOWED_MIME_TYPES

    def _read_header_bytes(self, file_path: str, max_bytes: int = READ_BUFFER_SIZE) -> bytes:
        """Reads initial bounded bytes for magic byte detection without loading entire file."""
        if not os.path.exists(file_path):
            raise EvidenceFileNotFoundException(file_path)
        with open(file_path, "rb") as f:
            return f.read(max_bytes)

    def _check_dangerous_signatures(self, header: bytes) -> Optional[str]:
        """Inspects binary header against disallowed executable and dangerous payload headers."""
        for sig, description in DANGEROUS_SIGNATURES:
            if header.startswith(sig):
                return description
        return None

    def _is_valid_text_stream(self, header: bytes) -> bool:
        """
        Validates whether bytes represent pure printable text (ASCII / UTF-8 / UTF-16).
        Rejects payloads containing binary null bytes or non-printable control codes.
        """
        if not header:
            return False
        # Null bytes indicate binary data, never valid plain text or CSV
        if b"\x00" in header:
            return False

        # Attempt UTF-8 decode
        try:
            text = header.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = header.decode("utf-16")
            except UnicodeDecodeError:
                return False

        # Verify printable characters (allow whitespace \r, \n, \t)
        printable_ratio = sum(1 for c in text if c.isprintable() or c in "\r\n\t") / len(text)
        return printable_ratio >= 0.95

    def detect_file_type(self, header: bytes, filename: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Detects actual file signature from bounded header bytes.
        Returns: (detected_mime, detected_format, error_or_warning)
        """
        if not header or len(header) == 0:
            return None, None, "Empty file (0 bytes)"

        # 1. Dangerous signature check
        dangerous_desc = self._check_dangerous_signatures(header)
        if dangerous_desc:
            return "application/x-executable", "EXECUTABLE", f"Dangerous signature: {dangerous_desc}"

        # 2. Check for manual high-confidence signatures
        if header.startswith(b"%PDF"):
            return "application/pdf", "PDF", None
        if header.startswith(b"\xFF\xD8\xFF"):
            return "image/jpeg", "JPEG", None
        if header.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png", "PNG", None
        if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WAVE":
            return "audio/wav", "WAV", None
        if header.startswith(b"RIFF") and len(header) >= 12 and header[8:12] == b"WEBP":
            return "image/webp", "WEBP", None
        if header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0):
            return "audio/mpeg", "MP3", None
        if header.startswith(b"OggS"):
            return "audio/ogg", "OGG", None
        if header.startswith(b"fLaC"):
            return "audio/flac", "FLAC", None
        if header.startswith(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"):
            return "application/vnd.ms-excel", "XLS", None

        # 3. ZIP-based formats (.xlsx vs standard .zip)
        if header.startswith(b"PK\x03\x04"):
            # Check if this might be an Office Open XML spreadsheet
            ext = os.path.splitext(filename)[1].lower()
            if ext == ".xlsx":
                return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "XLSX", None
            return "application/zip", "ZIP", None

        # 4. Use puremagic for other formats
        try:
            matches = puremagic.magic_string(header)
            if matches:
                # Check for ambiguity
                top_match = matches[0]
                if top_match.mime_type:
                    return top_match.mime_type, top_match.extension.replace(".", "").upper(), None
        except Exception as e:
            logger.debug(f"puremagic inspection error: {e}")

        # 5. Check if it is valid plain text / CSV
        if self._is_valid_text_stream(header):
            ext = os.path.splitext(filename)[1].lower()
            if ext == ".csv":
                return "text/csv", "CSV", None
            if ext == ".json":
                return "application/json", "JSON", None
            return "text/plain", "TEXT", None

        return None, None, "Unrecognized binary header"

    def validate_evidence(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> MIMEValidationResult:
        """
        Executes MOD-06 MIME & Signature Validation on a registered evidence object.
        Verifies:
            1. Case existence & workspace containment
            2. Authorization (investigator access to case)
            3. Declared MIME against configurable allowlist
            4. Actual binary magic bytes against declared MIME
            5. File extension consistency
            6. Rejection of executables, scripts, and unknown/ambiguous binaries
        """
        # 1. Look up Case and Evidence
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        # 2. Authorization Check (MOD-03)
        self.authz.check_can_validate_evidence(investigator, case)

        # 3. Case Workspace Isolation Check
        staged_path = os.path.abspath(evidence.raw_storage_path)
        workspace_boundary = os.path.abspath(case.case_workspace_path)
        if not staged_path.startswith(workspace_boundary):
            raise ForbiddenException("Path security violation: Evidence staging path is outside case workspace boundary.")

        # 4. Check File Existence & Read Header
        if not os.path.exists(staged_path):
            raise EvidenceFileNotFoundException(staged_path)

        header = self._read_header_bytes(staged_path)
        declared_mime = evidence.declared_mime_type.strip().lower()
        original_ext = os.path.splitext(evidence.original_file_name)[1].lower()

        # 5. Check against Allowed Evidence MIME Types
        if declared_mime not in self.allowlist:
            reason = f"Declared MIME type '{declared_mime}' is not permitted by investigation evidence policy."
            return self._record_and_persist_decision(
                evidence=evidence,
                case=case,
                investigator=investigator,
                valid=False,
                detected_mime=None,
                detected_format=None,
                declared_extension=original_ext,
                reason=reason,
            )

        # 6. Check for empty file
        if len(header) == 0:
            reason = "Uploaded evidence payload is empty (0 bytes)."
            return self._record_and_persist_decision(
                evidence=evidence,
                case=case,
                investigator=investigator,
                valid=False,
                detected_mime=None,
                detected_format=None,
                declared_extension=original_ext,
                reason=reason,
            )

        # 7. Check for Disguised Executable or Dangerous Payloads
        dangerous = self._check_dangerous_signatures(header)
        if dangerous:
            reason = f"Executable binary signature detected: {dangerous}. Evidence rejected."
            return self._record_and_persist_decision(
                evidence=evidence,
                case=case,
                investigator=investigator,
                valid=False,
                detected_mime="application/x-executable",
                detected_format="EXECUTABLE",
                declared_extension=original_ext,
                reason=reason,
            )

        # 8. Detect Actual File Type
        detected_mime, detected_format, err = self.detect_file_type(header, evidence.stored_file_name)
        if not detected_mime:
            reason = f"Binary signature validation failed: {err or 'Unrecognized binary format'}."
            return self._record_and_persist_decision(
                evidence=evidence,
                case=case,
                investigator=investigator,
                valid=False,
                detected_mime=None,
                detected_format=None,
                declared_extension=original_ext,
                reason=reason,
            )

        # 9. Compare Declared MIME against Detected MIME
        allowlist_entry = self.allowlist[declared_mime]
        equivalent_mimes = [m.lower() for m in allowlist_entry.get("equivalent_mimes", [declared_mime])]

        if detected_mime.lower() not in equivalent_mimes:
            reason = (
                f"Binary signature mismatch: declared MIME is '{declared_mime}', "
                f"but actual binary signature corresponds to '{detected_mime}' ({detected_format})."
            )
            return self._record_and_persist_decision(
                evidence=evidence,
                case=case,
                investigator=investigator,
                valid=False,
                detected_mime=detected_mime,
                detected_format=detected_format,
                declared_extension=original_ext,
                reason=reason,
            )

        # 10. Extension Consistency Check
        # If extension contradicts detected type (e.g. .exe with a PDF MIME), reject
        if original_ext in [".exe", ".bat", ".cmd", ".sh", ".dll", ".so", ".bin", ".vbs"]:
            reason = f"Suspicious extension '{original_ext}' contradicts declared evidence type."
            return self._record_and_persist_decision(
                evidence=evidence,
                case=case,
                investigator=investigator,
                valid=False,
                detected_mime=detected_mime,
                detected_format=detected_format,
                declared_extension=original_ext,
                reason=reason,
            )

        # 11. PASS: Valid MIME and binary signature match
        reason = f"Binary signature matches declared MIME '{declared_mime}' ({detected_format})."
        return self._record_and_persist_decision(
            evidence=evidence,
            case=case,
            investigator=investigator,
            valid=True,
            detected_mime=detected_mime,
            detected_format=detected_format,
            declared_extension=original_ext,
            reason=reason,
        )

    def _record_and_persist_decision(
        self,
        evidence: Evidence,
        case: Case,
        investigator: AuthenticatedInvestigator,
        valid: bool,
        detected_mime: Optional[str],
        detected_format: Optional[str],
        declared_extension: Optional[str],
        reason: str,
    ) -> MIMEValidationResult:
        """Persists validation outcome to database, records audit log, and returns result schema."""
        now = datetime.now(timezone.utc)
        target_status = EvidenceIntakeStatus.VALIDATED.value if valid else EvidenceIntakeStatus.REJECTED.value

        evidence.status = target_status
        evidence.detected_mime_type = detected_mime
        evidence.detected_format = detected_format
        evidence.validation_reason = reason
        evidence.validated_at = now
        self.evidence_repo.update(evidence)

        action = "EVIDENCE_MIME_VALIDATED" if valid else "EVIDENCE_MIME_REJECTED"
        audit_details = {
            "evidence_id": evidence.evidence_id,
            "case_id": case.case_id,
            "status": target_status,
            "declared_mime": evidence.declared_mime_type,
            "detected_mime": detected_mime,
            "detected_format": detected_format,
            "reason": reason,
            "validator_version": VALIDATOR_VERSION,
        }

        AuditIntegrationService.record_event(
            action=action,
            investigator_id=investigator.investigator_id,
            case_id=case.case_id,
            details=audit_details,
        )

        log_event(
            event_type=f"MIME_VALIDATION_{'PASS' if valid else 'FAIL'}",
            message=f"Evidence '{evidence.evidence_id}' {target_status}: {reason}",
            case_id=case.case_id,
            investigator_id=investigator.investigator_id,
            extra_data=audit_details,
        )

        return MIMEValidationResult(
            evidence_id=evidence.evidence_id,
            case_id=case.case_id,
            valid=valid,
            status=target_status,
            declared_mime=evidence.declared_mime_type,
            detected_mime=detected_mime,
            detected_format=detected_format,
            declared_extension=declared_extension,
            validation_reason=reason,
            validator_version=VALIDATOR_VERSION,
            validated_at=now,
        )

    def get_validated_evidence_object(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> ValidatedEvidenceObject:
        """
        Downstream Handoff Contract for MOD-07 (Antivirus Scan).
        STRICT INVARIANT: Only evidence items with status == 'VALIDATED' can yield this contract.
        Rejected or unvalidated items are strictly denied handoff.
        """
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        self.authz.check_can_read_evidence(investigator, case)

        if evidence.status != EvidenceIntakeStatus.VALIDATED.value:
            raise EvidenceValidationFailedException(
                f"Evidence '{evidence_id}' has status '{evidence.status}' and cannot proceed to MOD-07. "
                f"Only files with status '{EvidenceIntakeStatus.VALIDATED.value}' can proceed."
            )

        return ValidatedEvidenceObject(
            evidence_id=evidence.evidence_id,
            case_id=evidence.case_id,
            staged_file_path=evidence.raw_storage_path,
            original_file_name=evidence.original_file_name,
            verified_mime_type=evidence.detected_mime_type or evidence.declared_mime_type,
            detected_format=evidence.detected_format or "UNKNOWN",
            evidence_category=evidence.evidence_category,
            file_size_bytes=evidence.file_size_bytes,
            submitting_investigator_id=evidence.submitting_investigator_id,
            validation_status=evidence.status,
            validated_at=evidence.validated_at or datetime.now(timezone.utc),
        )
