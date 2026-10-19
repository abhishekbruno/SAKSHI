"""
Standardized error codes and exception handlers for SAKSHI Case Management Service.
Ensures internal DB errors and stack traces are never leaked to external clients.
"""
from typing import Any, Optional
from fastapi import HTTPException, status


class SakshiException(HTTPException):
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        details: Optional[Any] = None
    ):
        super().__init__(
            status_code=status_code,
            detail={
                "error_code": error_code,
                "message": message,
                "details": details
            }
        )


class CaseNotFoundException(SakshiException):
    def __init__(self, case_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="CASE_NOT_FOUND",
            message=f"Investigation case with ID '{case_id}' was not found.",
            details={"case_id": case_id}
        )


class UnauthorizedException(SakshiException):
    def __init__(self, message: str = "Authentication required or credentials invalid."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="UNAUTHORIZED",
            message=message
        )


class ForbiddenException(SakshiException):
    def __init__(self, message: str = "Investigator is not authorized to perform this operation."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="FORBIDDEN",
            message=message
        )


class InvalidCaseDataException(SakshiException):
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            error_code="INVALID_CASE_DATA",
            message=message,
            details=details
        )


class InvalidInvestigatorException(SakshiException):
    def __init__(self, message: str = "Invalid or unverified investigator reference."):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INVALID_INVESTIGATOR",
            message=message
        )


class CaseCreationFailedException(SakshiException):
    def __init__(self, message: str = "Failed to establish case record or workspace."):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="CASE_CREATION_FAILED",
            message=message
        )


class InvalidStageException(SakshiException):
    def __init__(self, message: str = "Invalid case lifecycle stage transition."):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INVALID_STAGE",
            message=message
        )


# ─── MOD-02: Authentication Error Types ─────────────────────────────────

class AuthenticationRequiredException(SakshiException):
    """No authentication credentials were provided."""
    def __init__(self, message: str = "Authentication required. Provide a valid Bearer token."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="AUTHENTICATION_REQUIRED",
            message=message
        )


class InvalidTokenException(SakshiException):
    """Token is malformed, undecodable, or structurally invalid."""
    def __init__(self, message: str = "The provided authentication token is invalid."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="INVALID_TOKEN",
            message=message
        )


class TokenExpiredException(SakshiException):
    """Token has passed its expiration time."""
    def __init__(self, message: str = "The authentication token has expired."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="TOKEN_EXPIRED",
            message=message
        )


class TokenIssuerInvalidException(SakshiException):
    """Token issuer does not match the trusted OIDC provider."""
    def __init__(self, message: str = "Token issuer is not trusted."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="TOKEN_ISSUER_INVALID",
            message=message
        )


class TokenAudienceInvalidException(SakshiException):
    """Token audience does not match the expected SAKSHI audience."""
    def __init__(self, message: str = "Token audience is invalid."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="TOKEN_AUDIENCE_INVALID",
            message=message
        )


class IdentityClaimMissingException(SakshiException):
    """Required identity claim (e.g. 'sub') is missing from the token."""
    def __init__(self, claim: str = "sub", message: Optional[str] = None):
        msg = message or f"Required identity claim '{claim}' is missing from the token."
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            error_code="IDENTITY_CLAIM_MISSING",
            message=msg,
            details={"missing_claim": claim}
        )


class OIDCConfigurationException(SakshiException):
    """OIDC is enabled but required configuration is missing or invalid."""
    def __init__(self, message: str = "OIDC authentication is misconfigured."):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="OIDC_CONFIGURATION_ERROR",
            message=message
        )


# ─── MOD-05: Evidence Intake Error Types ────────────────────────────────

class EvidenceNotFoundException(SakshiException):
    """Evidence entity not found in case repository."""
    def __init__(self, evidence_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="EVIDENCE_NOT_FOUND",
            message=f"Evidence item with ID '{evidence_id}' was not found.",
            details={"evidence_id": evidence_id}
        )


class IngestionGateClosedException(SakshiException):
    """Case lifecycle stage does not permit evidence ingestion."""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INGESTION_GATE_CLOSED",
            message=message,
            details=details
        )


class InvalidEvidenceDataException(SakshiException):
    """Evidence upload payload or metadata is invalid."""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            error_code="INVALID_EVIDENCE_DATA",
            message=message,
            details=details
        )


# ─── MOD-06: MIME / Signature Validation Error Types ───────────────────

class EvidenceFileNotFoundException(SakshiException):
    """Staged raw evidence physical file not found on disk."""
    def __init__(self, file_path: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            error_code="EVIDENCE_FILE_NOT_FOUND",
            message=f"Staged evidence file was not found at path '{file_path}'.",
            details={"file_path": file_path}
        )


class MimeTypeNotAllowedException(SakshiException):
    """Evidence MIME type is not permitted under investigation allowlist."""
    def __init__(self, mime_type: str, reason: Optional[str] = None):
        msg = reason or f"MIME type '{mime_type}' is not permitted by evidence policy."
        super().__init__(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            error_code="MIME_TYPE_NOT_ALLOWED",
            message=msg,
            details={"mime_type": mime_type}
        )


class MimeSignatureMismatchException(SakshiException):
    """Actual binary magic bytes do not match the declared MIME type."""
    def __init__(self, declared_mime: str, detected_mime: Optional[str] = None, reason: Optional[str] = None):
        msg = reason or (
            f"File binary signature mismatch: declared as '{declared_mime}' "
            f"but detected as '{detected_mime or 'unknown'}'."
        )
        super().__init__(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            error_code="MIME_SIGNATURE_MISMATCH",
            message=msg,
            details={"declared_mime": declared_mime, "detected_mime": detected_mime}
        )


class UnknownFileSignatureException(SakshiException):
    """File binary signature / magic bytes could not be recognized."""
    def __init__(self, message: str = "Unrecognized binary header or magic bytes.", details: Optional[Any] = None):
        super().__init__(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            error_code="UNKNOWN_FILE_SIGNATURE",
            message=message,
            details=details
        )


class AmbiguousFileSignatureException(SakshiException):
    """File matches multiple conflicting formats (potential polyglot payload)."""
    def __init__(self, message: str = "Ambiguous file format detected; potential polyglot file rejected.", details: Optional[Any] = None):
        super().__init__(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            error_code="AMBIGUOUS_FILE_SIGNATURE",
            message=message,
            details=details
        )


class EvidenceValidationFailedException(SakshiException):
    """Evidence failed MOD-06 validation and cannot proceed downstream."""
    def __init__(self, message: str = "Evidence failed MIME/signature validation.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="EVIDENCE_VALIDATION_FAILED",
            message=message,
            details=details
        )


# ─── MOD-07: Antivirus Scan Error Types ─────────────────────────────────

class AntivirusThreatDetectedException(SakshiException):
    """Malware, virus, or hostile payload detected in evidence."""
    def __init__(self, threat_name: str, message: Optional[str] = None, details: Optional[Any] = None):
        msg = message or f"Hostile payload detected: '{threat_name}'. Evidence rejected and quarantined."
        super().__init__(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            error_code="ANTIVIRUS_THREAT_DETECTED",
            message=msg,
            details={"threat_name": threat_name, **(details or {})}
        )


class AntivirusUnavailableException(SakshiException):
    """Antivirus scanning engine is offline, unreachable, or uninitialized."""
    def __init__(self, message: str = "Antivirus scanning engine is unavailable. Evidence scan aborted (Fail-Closed).", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="ANTIVIRUS_UNAVAILABLE",
            message=message,
            details=details
        )


class AntivirusTimeoutException(SakshiException):
    """Antivirus scan exceeded time limit."""
    def __init__(self, message: str = "Antivirus scanning engine timed out. Evidence scan aborted (Fail-Closed).", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            error_code="ANTIVIRUS_TIMEOUT",
            message=message,
            details=details
        )


class AntivirusScanFailedException(SakshiException):
    """General scan failure or attempt to bypass MOD-06 validation."""
    def __init__(self, message: str = "Antivirus scan operation failed.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="ANTIVIRUS_SCAN_FAILED",
            message=message,
            details=details
        )


# ─── MOD-08: WORM Commit + Checksum Error Types ─────────────────────────

class EvidenceNotScannedException(SakshiException):
    """Evidence payload has not passed MOD-07 Antivirus scan with CLEAN verdict."""
    def __init__(self, message: str = "Evidence has not passed MOD-07 Antivirus scan. WORM commit rejected.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="EVIDENCE_NOT_SCANNED",
            message=message,
            details=details
        )


class WORMCommitFailedException(SakshiException):
    """WORM storage commit operation failed or verification failed."""
    def __init__(self, message: str = "WORM storage commit failed.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="WORM_COMMIT_FAILED",
            message=message,
            details=details
        )


class WORMAlreadyCommittedException(SakshiException):
    """Evidence item is already committed in WORM storage; overwrite rejected."""
    def __init__(self, message: str = "Evidence item is already committed in immutable WORM storage.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code="WORM_ALREADY_COMMITTED",
            message=message,
            details=details
        )


class ChecksumMismatchException(SakshiException):
    """Calculated checksum does not match payload verification during WORM commit."""
    def __init__(self, expected: str, actual: str, message: Optional[str] = None):
        msg = message or f"Checksum mismatch: expected '{expected}', computed '{actual}'."
        super().__init__(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            error_code="CHECKSUM_MISMATCH",
            message=msg,
            details={"expected_checksum": expected, "actual_checksum": actual}
        )


class EvidenceNotCommittedException(SakshiException):
    """Evidence item has not yet been committed to WORM storage."""
    def __init__(self, message: str = "Evidence has not been committed to WORM storage.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="EVIDENCE_NOT_COMMITTED",
            message=message,
            details=details
        )


# ─── MOD-09: Dual Hashing (SHA-256 + SHA3-512) Error Types ──────────────

class EvidenceNotWORMCommittedException(SakshiException):
    """Evidence payload has not been committed to immutable WORM storage."""
    def __init__(self, message: str = "Evidence must be committed to WORM storage before integrity verification.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="EVIDENCE_NOT_WORM_COMMITTED",
            message=message,
            details=details
        )


class SHA256IntegrityMismatchException(SakshiException):
    """Recomputed SHA-256 digest does not match the established MOD-08 pre-hash."""
    def __init__(self, expected: str, actual: str, message: Optional[str] = None):
        msg = message or f"SHA-256 integrity mismatch: expected '{expected}', computed '{actual}'."
        super().__init__(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            error_code="SHA256_INTEGRITY_MISMATCH",
            message=msg,
            details={"expected_sha256": expected, "computed_sha256": actual}
        )


class IntegrityVerificationFailedException(SakshiException):
    """Integrity verification or dual hashing calculation failed."""
    def __init__(self, message: str = "Dual hash integrity verification failed.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INTEGRITY_VERIFICATION_FAILED",
            message=message,
            details=details
        )


class IntegrityNotVerifiedException(SakshiException):
    """Evidence item has not successfully passed MOD-09 dual hashing integrity verification."""
    def __init__(self, message: str = "Evidence integrity has not been verified.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INTEGRITY_NOT_VERIFIED",
            message=message,
            details=details
        )


# ─── MOD-10: WORM Object Lock Error Types ───────────────────────────────

class IntegrityNotVerifiedForLockException(SakshiException):
    """MOD-09 dual hash integrity must be VERIFIED before MOD-10 Object Lock can be applied."""
    def __init__(self, message: str = "Evidence integrity must be verified (MOD-09) before applying Object Lock.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INTEGRITY_NOT_VERIFIED_FOR_LOCK",
            message=message,
            details=details
        )


class ObjectLockFailedException(SakshiException):
    """Object Lock storage enforcement operation failed."""
    def __init__(self, message: str = "Object Lock enforcement failed.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="OBJECT_LOCK_FAILED",
            message=message,
            details=details
        )


class ObjectAlreadyLockedException(SakshiException):
    """Evidence item is already under Object Lock; re-lock rejected to prevent state ambiguity."""
    def __init__(self, message: str = "Evidence item is already under Object Lock.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code="OBJECT_ALREADY_LOCKED",
            message=message,
            details=details
        )


class ObjectNotLockedException(SakshiException):
    """Evidence item has not been placed under Object Lock; downstream contract cannot be issued."""
    def __init__(self, message: str = "Evidence has not been placed under Object Lock (MOD-10).", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="OBJECT_NOT_LOCKED",
            message=message,
            details=details
        )


# ─── MOD-11: AES-256-GCM Encryption Error Types ────────────────────────

class ObjectNotLockedForEncryptionException(SakshiException):
    """MOD-10 Object Lock must be LOCKED before MOD-11 AES-256-GCM encryption can be applied."""
    def __init__(self, message: str = "Evidence must be placed under Object Lock (MOD-10) before encryption.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="OBJECT_NOT_LOCKED_FOR_ENCRYPTION",
            message=message,
            details=details
        )


class EvidenceAlreadyEncryptedException(SakshiException):
    """Evidence item is already encrypted; re-encryption rejected."""
    def __init__(self, message: str = "Evidence item is already encrypted under AES-256-GCM.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code="EVIDENCE_ALREADY_ENCRYPTED",
            message=message,
            details=details
        )


class EvidenceNotEncryptedException(SakshiException):
    """Evidence item has not undergone AES-256-GCM encryption; contract or decrypt cannot be issued."""
    def __init__(self, message: str = "Evidence has not undergone AES-256-GCM encryption (MOD-11).", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="EVIDENCE_NOT_ENCRYPTED",
            message=message,
            details=details
        )


class EncryptionFailedException(SakshiException):
    """AES-256-GCM encryption operation failed."""
    def __init__(self, message: str = "AES-256-GCM encryption failed.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="ENCRYPTION_FAILED",
            message=message,
            details=details
        )


class DecryptionFailedException(SakshiException):
    """Decryption failed due to invalid ciphertext, key, or tag."""
    def __init__(self, message: str = "AES-256-GCM decryption failed.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DECRYPTION_FAILED",
            message=message,
            details=details
        )


class EncryptionTamperException(SakshiException):
    """Authenticated encryption tag mismatch or payload tampering detected."""
    def __init__(self, message: str = "Cryptographic tamper detected: AES-256-GCM authentication tag or payload validation failed.", details: Optional[Any] = None):
        super().__init__(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            error_code="ENCRYPTION_TAMPER_DETECTED",
            message=message,
            details=details
        )


class CaseKeyIsolationException(SakshiException):
    """Access to encryption key across case boundaries was attempted."""
    def __init__(self, message: str = "Cross-case key access violation: key does not belong to the requested case.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            error_code="CASE_KEY_ISOLATION_VIOLATION",
            message=message,
            details=details
        )


class KeyProviderException(SakshiException):
    """Key provider error during key retrieval, derivation, or management."""
    def __init__(self, message: str = "Key provider error occurred.", details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="KEY_PROVIDER_ERROR",
            message=message,
            details=details
        )


# ─── RAG Domain Exceptions ───────────────────────────────────────────────

class IneligibleEvidenceException(SakshiException):
    """Evidence does not meet security gate requirements (MOD-08 commit, MOD-09 integrity, MOD-10 object-lock)."""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            error_code="INELIGIBLE_EVIDENCE",
            message=message,
            details=details,
        )


class UnsupportedDocumentFormatException(SakshiException):
    """Document MIME type or evidence category is not supported for text extraction."""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            error_code="UNSUPPORTED_DOCUMENT_FORMAT",
            message=message,
            details=details,
        )


class TextExtractionException(SakshiException):
    """Failure during text extraction from document stream."""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            status_code=getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422),
            error_code="TEXT_EXTRACTION_FAILED",
            message=message,
            details=details,
        )


class EmbeddingModelLoadException(SakshiException):
    """Embedding model could not be loaded."""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="EMBEDDING_MODEL_LOAD_FAILED",
            message=message,
            details=details,
        )


class EmbeddingGenerationException(SakshiException):
    """Failure during vector embedding generation."""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="EMBEDDING_GENERATION_FAILED",
            message=message,
            details=details,
        )


class EmbeddingDimensionMismatchException(SakshiException):
    """Generated vector dimension does not match configured target dimension."""
    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="EMBEDDING_DIMENSION_MISMATCH",
            message=message,
            details=details,
        )


class RAGRetrievalFailedException(SakshiException):
    """Safe failure while retrieving indexed evidence passages."""
    def __init__(self, message: str = "Evidence retrieval is temporarily unavailable."):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="RAG_RETRIEVAL_FAILED",
            message=message,
        )

