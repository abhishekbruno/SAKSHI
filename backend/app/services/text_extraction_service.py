"""
Text Extraction Service for SAKSHI Investigation Platform.
Phase 3 — Evidence Text Extraction, Chunking, and Embedding.

Extracts text content from verified, committed, object-locked forensic exhibits
(such as inquest reports, autopsy reports, FIRs, and witness statements).

Security Invariants:
1. Strict Security Gate:
   - MOD-08 WORM commit: evidence.status == 'COMMITTED'
   - MOD-09 Dual-hashing: evidence.integrity_status == 'VERIFIED'
   - MOD-10 WORM Object Lock: evidence.lock_status == 'LOCKED'
   - MOD-07 Antivirus: evidence is not INFECTED or QUARANTINED.
2. MOD-03 Authorization:
   - Validates investigator case access permissions via PolicyEngine.
3. MOD-11 Authorized Decryption:
   - Decrypts encrypted exhibits in-memory via EncryptionService.decrypt_evidence_bytes.
   - Decrypted plaintext is NEVER written to temporary files or persisted unencrypted.
4. Untrusted Input Handling:
   - Extracted document text is forensic input, treated as untrusted text without asserting veracity.
5. Immutability:
   - Authoritative evidence files on disk are strictly opened read-only and never modified.
"""
import io
import os
import hashlib
import logging
from typing import Optional, List
from sqlalchemy.orm import Session
import pypdf

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
    IneligibleEvidenceException,
    UnsupportedDocumentFormatException,
    TextExtractionException,
)
from app.services.auth_service import IAuthorizationService, authorization_service
from app.services.encryption_service import EncryptionService
from app.services.audit_integration import AuditIntegrationService
from app.schemas.rag import ExtractedDocument, ExtractedPage

logger = logging.getLogger("sakshi.rag.extraction")

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
}

SUPPORTED_CATEGORIES = {
    "DOCUMENT_PDF",
    "CDR_SPREADSHEET",
    "OTHER",
}


class TextExtractionService:
    """
    Forensic text extraction service enforcing MOD-05 through MOD-11 security gates.
    """

    def __init__(
        self,
        db: Session,
        encryption_service: Optional[EncryptionService] = None,
        authz: Optional[IAuthorizationService] = None,
    ):
        self.db = db
        self.case_repo = CaseRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.authz = authz or authorization_service
        self.encryption_service = encryption_service or EncryptionService(db, authz=self.authz)

    def extract_text(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> ExtractedDocument:
        """
        Validates security gates, retrieves exhibit payload safely into memory,
        and extracts normalized text with page citations and hash bindings.
        """
        # 1. Verify Case Existence and Authorization
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        self.authz.check_can_read_evidence(investigator, case)

        # Verify Case Stage is not closed
        if case.lifecycle_stage in ("SUSPENDED", "CLOSED"):
            raise IneligibleEvidenceException(
                f"Case '{case_id}' is in lifecycle stage '{case.lifecycle_stage}'. Evidence processing is suspended."
            )

        # 2. Verify Evidence Existence and Case Isolation
        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        # 3. Enforce Evidence Security Gates (MOD-05 through MOD-10)
        self._enforce_security_gates(evidence)

        # 4. Secure Payload Ingestion (In-Memory, Zero Disk Plaintext Leakage)
        raw_bytes = self._obtain_plaintext_bytes(case, evidence, investigator)

        # 5. Extract Text based on Document Format
        extracted_doc = self._perform_extraction(case, evidence, raw_bytes)

        # 6. Audit Trail
        AuditIntegrationService.record_event(
            action="EVIDENCE_TEXT_EXTRACTED",
            investigator_id=investigator.investigator_id,
            case_id=case.case_id,
            details={
                "evidence_id": evidence.evidence_id,
                "mime_type": extracted_doc.mime_type,
                "extraction_method": extracted_doc.extraction_method,
                "total_pages": extracted_doc.total_pages,
                "total_characters": extracted_doc.total_characters,
                "source_sha256": extracted_doc.source_sha256,
            },
        )

        return extracted_doc

    def _enforce_security_gates(self, evidence: Evidence) -> None:
        """
        Enforces MOD-07, MOD-08, MOD-09, and MOD-10 gates.
        Fails-closed on any gate violation.
        """
        # MOD-07: Antivirus
        if evidence.antivirus_status in ("INFECTED", "QUARANTINED") or evidence.status == "QUARANTINED":
            raise IneligibleEvidenceException(
                f"Evidence '{evidence.evidence_id}' is quarantined or failed antivirus scanning (status: {evidence.antivirus_status})."
            )

        # MOD-08: WORM Commit
        is_committed = (evidence.status == "COMMITTED" or evidence.worm_status == "COMMITTED")
        if not is_committed:
            raise IneligibleEvidenceException(
                f"Evidence '{evidence.evidence_id}' has not achieved MOD-08 WORM committed status (status: '{evidence.status}', worm_status: '{evidence.worm_status}')."
            )

        # MOD-09: Dual Hashing Integrity
        if evidence.integrity_status != "VERIFIED" or not evidence.checksum_sha256:
            raise IneligibleEvidenceException(
                f"Evidence '{evidence.evidence_id}' dual-hash integrity is '{evidence.integrity_status}'. Must be 'VERIFIED' under MOD-09."
            )

        # MOD-10: WORM Object Lock
        if evidence.lock_status != "LOCKED":
            raise IneligibleEvidenceException(
                f"Evidence '{evidence.evidence_id}' is not in 'LOCKED' state under MOD-10 WORM Object Lock (current: '{evidence.lock_status}')."
            )

    def _obtain_plaintext_bytes(
        self,
        case: Case,
        evidence: Evidence,
        investigator: AuthenticatedInvestigator,
    ) -> bytes:
        """
        Retrieves plaintext bytes directly in memory.
        If encrypted under MOD-11, uses authorized decryption with GCM tag verification.
        If unencrypted, reads raw storage path and verifies dual-hash integrity.
        """
        if evidence.encryption_status == "ENCRYPTED":
            # MOD-11 Authorized Decryption
            return self.encryption_service.decrypt_evidence_bytes(
                case_id=case.case_id,
                evidence_id=evidence.evidence_id,
                investigator=investigator,
            )

        # Direct read from immutable WORM storage path
        file_path = evidence.raw_storage_path
        if not file_path or not os.path.exists(file_path):
            raise EvidenceFileNotFoundException(file_path or "UNSET")

        try:
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
        except Exception as e:
            raise TextExtractionException(f"Failed to read evidence file: {e}")

        # Verify dual-hash integrity before processing
        sha256_digest = hashlib.sha256(raw_bytes).hexdigest()
        if sha256_digest.lower() != (evidence.checksum_sha256 or "").lower():
            raise IneligibleEvidenceException(
                f"Evidence file on disk failed SHA-256 integrity match against authoritative record."
            )

        if evidence.checksum_sha3_512:
            sha3_digest = hashlib.sha3_512(raw_bytes).hexdigest()
            if sha3_digest.lower() != evidence.checksum_sha3_512.lower():
                raise IneligibleEvidenceException(
                    f"Evidence file on disk failed SHA3-512 integrity match against authoritative record."
                )

        return raw_bytes

    def _perform_extraction(
        self,
        case: Case,
        evidence: Evidence,
        raw_bytes: bytes,
    ) -> ExtractedDocument:
        """
        Performs in-memory extraction based on MIME type or category.
        """
        effective_mime = (
            evidence.detected_mime_type
            or evidence.declared_mime_type
            or "application/octet-stream"
        ).lower()

        is_pdf = (
            effective_mime == "application/pdf"
            or evidence.evidence_category == "DOCUMENT_PDF"
            or evidence.original_file_name.lower().endswith(".pdf")
        )

        is_plaintext = (
            effective_mime in ("text/plain", "text/markdown", "text/csv")
            or evidence.evidence_category == "CDR_SPREADSHEET"
            or evidence.original_file_name.lower().endswith((".txt", ".md", ".csv"))
        )

        if is_pdf:
            return self._extract_pdf_text(case, evidence, raw_bytes, effective_mime)
        elif is_plaintext:
            return self._extract_plaintext(case, evidence, raw_bytes, effective_mime)
        else:
            raise UnsupportedDocumentFormatException(
                f"Unsupported document format for text extraction: category='{evidence.evidence_category}', MIME='{effective_mime}'. "
                f"Supported formats: PDF and plain-text/tabular documents."
            )

    def _extract_pdf_text(
        self,
        case: Case,
        evidence: Evidence,
        raw_bytes: bytes,
        mime_type: str,
    ) -> ExtractedDocument:
        """Extracts text from PDF bytes using pypdf in memory."""
        try:
            stream = io.BytesIO(raw_bytes)
            reader = pypdf.PdfReader(stream)
            num_pages = len(reader.pages)
            pages: List[ExtractedPage] = []
            total_chars = 0

            for page_idx, page in enumerate(reader.pages):
                page_num = page_idx + 1
                try:
                    text = page.extract_text() or ""
                except Exception as page_err:
                    logger.warning("Error extracting text on page %d of evidence %s: %s", page_num, evidence.evidence_id, page_err)
                    text = ""

                cleaned_text = text.strip()
                char_count = len(cleaned_text)
                total_chars += char_count

                pages.append(
                    ExtractedPage(
                        page_number=page_num,
                        text=cleaned_text,
                        char_count=char_count,
                    )
                )

            return ExtractedDocument(
                case_id=case.case_id,
                evidence_id=evidence.evidence_id,
                source_sha256=evidence.checksum_sha256,
                source_sha3_512=evidence.checksum_sha3_512,
                mime_type=mime_type if "pdf" in mime_type else "application/pdf",
                extraction_method="PDF_NATIVE_TEXT",
                processing_version="v1.0",
                pages=pages,
                total_pages=num_pages,
                total_characters=total_chars,
            )

        except Exception as e:
            logger.error("PDF text extraction failed for evidence %s: %s", evidence.evidence_id, e)
            raise TextExtractionException(f"Failed to parse PDF document: {type(e).__name__}: {str(e)}")

    def _extract_plaintext(
        self,
        case: Case,
        evidence: Evidence,
        raw_bytes: bytes,
        mime_type: str,
    ) -> ExtractedDocument:
        """Extracts text from plain text or tabular byte streams."""
        try:
            # Attempt UTF-8 decoding with fallback to Latin-1
            try:
                decoded_text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                decoded_text = raw_bytes.decode("latin-1")

            cleaned_text = decoded_text.strip()
            total_chars = len(cleaned_text)

            pages = [
                ExtractedPage(
                    page_number=1,
                    text=cleaned_text,
                    char_count=total_chars,
                )
            ]

            return ExtractedDocument(
                case_id=case.case_id,
                evidence_id=evidence.evidence_id,
                source_sha256=evidence.checksum_sha256,
                source_sha3_512=evidence.checksum_sha3_512,
                mime_type=mime_type,
                extraction_method="PLAINTEXT_DIRECT",
                processing_version="v1.0",
                pages=pages,
                total_pages=1,
                total_characters=total_chars,
            )

        except Exception as e:
            logger.error("Plaintext extraction failed for evidence %s: %s", evidence.evidence_id, e)
            raise TextExtractionException(f"Failed to decode text document: {str(e)}")
