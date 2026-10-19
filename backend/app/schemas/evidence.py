"""
Pydantic schemas for SAKSHI Evidence Intake Service (MOD-05).
Defines intake metadata validation, response contracts, and the downstream
handoff contract (RegisteredEvidenceObject) to MOD-06.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class EvidenceCategory(str, Enum):
    """Forensic evidence classification categories."""
    DOCUMENT_PDF = "DOCUMENT_PDF"
    SCENE_PHOTO = "SCENE_PHOTO"
    AUTOPSY_PHOTO = "AUTOPSY_PHOTO"
    AUDIO_RECORDING = "AUDIO_RECORDING"
    CDR_SPREADSHEET = "CDR_SPREADSHEET"
    DIGITAL_DEVICE_EXTRACTION = "DIGITAL_DEVICE_EXTRACTION"
    OTHER = "OTHER"


class EvidenceIntakeStatus(str, Enum):
    """Lifecycle / pipeline status within Evidence Ingestion."""
    REGISTERED_INTAKE = "REGISTERED_INTAKE"
    PENDING_MIME_VALIDATION = "PENDING_MIME_VALIDATION"
    VALIDATED = "VALIDATED"
    AV_SCANNING = "AV_SCANNING"
    CLEAN = "CLEAN"
    QUARANTINED = "QUARANTINED"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"


class AntivirusVerdict(str, Enum):
    """
    Forensic Antivirus scan outcomes.

    IMPORTANT SEMANTIC DEFINITION:
    CLEAN = No threat was detected by the configured antivirus scanner.
    A CLEAN verdict represents the finding of the configured antivirus scanner
    and is not an absolute guarantee that the payload contains no malware.
    """
    CLEAN = "CLEAN"
    THREAT_DETECTED = "THREAT_DETECTED"
    SCAN_ERROR = "SCAN_ERROR"
    SCANNER_UNAVAILABLE = "SCANNER_UNAVAILABLE"
    SCAN_TIMEOUT = "SCAN_TIMEOUT"


class EvidenceIntakeMetadata(BaseModel):
    """Metadata provided alongside the raw file payload during intake."""
    evidence_category: EvidenceCategory = Field(
        ...,
        description="Forensic category of the uploaded evidence item"
    )
    declared_mime_type: str = Field(
        ...,
        min_length=3,
        max_length=128,
        description="Client-declared MIME type (e.g. application/pdf, image/jpeg, audio/wav, text/csv)"
    )
    collection_datetime: Optional[datetime] = Field(
        default=None,
        description="Timestamp when evidence was recovered or seized"
    )
    collection_location: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Physical location or recovery scene description"
    )
    source_device_or_person: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Source witness, custodian, or device serial number"
    )
    description: Optional[str] = Field(
        default=None,
        description="Brief forensic description of the evidence artifact"
    )

    @field_validator("declared_mime_type")
    @classmethod
    def validate_mime(cls, v: str) -> str:
        clean = v.strip().lower()
        if not clean or "/" not in clean:
            raise ValueError("declared_mime_type must be in standard type/subtype format (e.g. application/pdf).")
        return clean


class EvidenceResponse(BaseModel):
    """Public API response representing a registered evidence object."""
    evidence_id: str = Field(..., description="Canonical unique Evidence ID")
    case_id: str = Field(..., description="Associated Case ID")
    original_file_name: str
    stored_file_name: str
    evidence_category: str
    declared_mime_type: str
    file_size_bytes: int
    collection_datetime: Optional[datetime] = None
    collection_location: Optional[str] = None
    source_device_or_person: Optional[str] = None
    description: Optional[str] = None
    submitting_investigator_id: str
    status: str
    raw_storage_path: str
    detected_mime_type: Optional[str] = None
    detected_format: Optional[str] = None
    validation_reason: Optional[str] = None
    validated_at: Optional[datetime] = None
    antivirus_status: Optional[str] = None
    antivirus_scanner: Optional[str] = None
    antivirus_threat_name: Optional[str] = None
    antivirus_message: Optional[str] = None
    antivirus_scanned_at: Optional[datetime] = None
    checksum_algorithm: Optional[str] = None
    checksum_sha256: Optional[str] = None
    checksum_computed_at: Optional[datetime] = None
    worm_status: Optional[str] = None
    worm_storage_reference: Optional[str] = None
    worm_committed_at: Optional[datetime] = None
    checksum_sha3_512: Optional[str] = None
    sha3_512_computed_at: Optional[datetime] = None
    integrity_status: Optional[str] = None
    integrity_verified_at: Optional[datetime] = None
    integrity_verification_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class EvidenceListResponse(BaseModel):
    """List response of registered evidence objects for an investigation."""
    case_id: str
    total: int
    items: List[EvidenceResponse]


class RegisteredEvidenceObject(BaseModel):
    """
    Downstream Handoff Contract:
    Produced by MOD-05 (Evidence Intake) and consumed by MOD-06 (MIME / Signature Validation).
    """
    evidence_id: str
    case_id: str
    staged_file_path: str
    original_file_name: str
    declared_mime_type: str
    evidence_category: str
    file_size_bytes: int
    submitting_investigator_id: str
    intake_status: str
    registered_at: datetime


class MIMEValidationResult(BaseModel):
    """
    Internal and API result for MOD-06 MIME & Signature Validation.
    """
    evidence_id: str
    case_id: str
    valid: bool
    status: str  # "VALIDATED" or "REJECTED"
    declared_mime: str
    detected_mime: Optional[str] = None
    detected_format: Optional[str] = None
    declared_extension: Optional[str] = None
    validation_reason: str
    validator_version: str = "SAKSHI-MIME-V1.0"
    validated_at: datetime


class ValidatedEvidenceObject(BaseModel):
    """
    Downstream Handoff Contract:
    Produced by MOD-06 (MIME / Signature Validation) and consumed by MOD-07 (Antivirus Scan).
    Strict Invariant: Only files with status == 'VALIDATED' can yield this contract.
    """
    evidence_id: str
    case_id: str
    staged_file_path: str
    original_file_name: str
    verified_mime_type: str
    detected_format: str
    evidence_category: str
    file_size_bytes: int
    submitting_investigator_id: str
    validation_status: str
    validated_at: datetime


class AntivirusScanResult(BaseModel):
    """
    Internal and API result for MOD-07 Antivirus Scan.
    """
    evidence_id: str
    case_id: str
    verdict: AntivirusVerdict
    status: str  # "CLEAN", "QUARANTINED", "ERROR"
    scanner_name: str
    scanner_version: str
    threat_name: Optional[str] = None
    message: str
    duration_ms: Optional[float] = None
    scanned_at: datetime


class ScannedEvidenceObject(BaseModel):
    """
    Downstream Handoff Contract:
    Produced by MOD-07 (Antivirus Scan) when no threat is detected by the configured scanner,
    and consumed by MOD-08 (WORM Commit + Checksum).

    Strict Invariant:
    Only evidence with verdict == 'CLEAN' and status == 'CLEAN' can yield this contract.
    A CLEAN verdict means no threat was detected by the configured antivirus scanner.
    """
    evidence_id: str
    case_id: str
    staged_file_path: str
    original_file_name: str
    verified_mime_type: str
    detected_format: str
    evidence_category: str
    file_size_bytes: int
    submitting_investigator_id: str
    mime_status: str
    antivirus_verdict: str
    antivirus_scanner: str
    antivirus_scanned_at: datetime


class WORMCommitResult(BaseModel):
    """
    Internal and API result for MOD-08 WORM Commit + Checksum operation.
    """
    evidence_id: str
    case_id: str
    status: str = "COMMITTED"
    worm_status: str = "COMMITTED"
    checksum_algorithm: str = "SHA-256"
    checksum_sha256: str
    worm_storage_reference: str
    message: str
    worm_commit_message: Optional[str] = None
    committed_at: datetime
    worm_committed_at: Optional[datetime] = None
    already_committed: bool = False


class WORMCommittedEvidenceObject(BaseModel):
    """
    Downstream Handoff Contract:
    Produced by MOD-08 (WORM Commit + Checksum) and consumed by Phase 3 (Security & Integrity).
    Strict Invariant: Only evidence with status == 'COMMITTED' and worm_status == 'COMMITTED'
    and verified SHA-256 digest can yield this contract.
    """
    evidence_id: str
    case_id: str
    staged_file_path: str
    original_file_name: str
    verified_mime_type: str
    detected_format: str
    evidence_category: str
    file_size_bytes: int
    submitting_investigator_id: str
    mime_status: Optional[str] = None
    antivirus_verdict: str
    antivirus_scanner: str
    checksum_algorithm: str = "SHA-256"
    checksum_sha256: str
    checksum_computed_at: datetime
    worm_status: str = "COMMITTED"
    worm_storage_reference: str
    committed_at: datetime


class IntegrityVerificationResult(BaseModel):
    """
    Internal and API result for MOD-09 Dual Hashing (SHA-256 + SHA3-512) and Integrity Verification.
    """
    evidence_id: str
    case_id: str
    worm_storage_reference: str
    checksum_sha256: str
    checksum_sha3_512: str
    integrity_status: str  # "VERIFIED"
    message: str
    verified_at: datetime
    sha256_matched: bool = True
    already_verified: bool = False


class IntegrityProtectedEvidenceObject(BaseModel):
    """
    Downstream Handoff Contract:
    Produced by MOD-09 (Dual Hashing) and consumed by subsequent Phase 3 / Phase 4 modules.
    Strict Invariant: Evidence must be WORM-committed and verified with dual hashes (SHA-256 + SHA3-512).
    """
    case_id: str
    evidence_id: str
    original_file_name: str
    evidence_category: str
    file_size_bytes: int
    worm_storage_reference: str
    checksum_sha256: str
    checksum_sha3_512: str
    integrity_status: str = "VERIFIED"
    verified_at: datetime
    source: str = "MOD-09"


# ─── MOD-10: WORM Object Lock / Dual Storage ────────────────────────────

class ObjectLockMode(str, Enum):
    """
    Object Lock mode — mirrors S3 Object Lock semantics for forward-compatibility.

    GOVERNANCE:
        Retention policy is enforced by application-layer controls.
        Authorized administrators can override with explicit reason.
        Suitable for development, QA, and non-production forensic workflows.

    COMPLIANCE:
        Retention policy is absolute and cannot be reduced or deleted
        by ANY principal, including root/admin, until the retention period expires.
        Suitable for production, regulatory, and evidentiary production workflows.

    NOTE (Phase 3 — Local Implementation):
        Both modes are enforced by the application-level LocalObjectLockBackend
        in the current local-filesystem implementation. TRUE hardware/cloud Object Lock
        (e.g., S3 Object Lock COMPLIANCE mode) is out of scope for Phase 3 and
        requires cloud infrastructure integration in a future production phase.
    """
    GOVERNANCE = "GOVERNANCE"
    COMPLIANCE = "COMPLIANCE"


class ObjectLockResult(BaseModel):
    """
    Internal and API result for MOD-10 WORM Object Lock operation.
    Returned by POST /evidence/{id}/object-lock.
    """
    evidence_id: str
    case_id: str
    lock_status: str = "LOCKED"           # LOCKED | LOCK_FAILED
    lock_mode: str = "GOVERNANCE"          # GOVERNANCE | COMPLIANCE
    lock_storage_reference: str            # objlock://<case_id>/<sha256>+<sha3_512_prefix16>
    lock_applied_at: datetime
    lock_retention_until: Optional[datetime] = None
    lock_backend: str                      # LOCAL_FILESYSTEM | S3_OBJECT_LOCK | ...
    lock_overwrite_protected: bool = True
    lock_delete_protected: bool = True
    lock_integrity_binding: str            # sha256:<val>:sha3_512:<val>
    checksum_sha256: str
    checksum_sha3_512: str
    worm_storage_reference: str            # Inherited from MOD-08
    message: str
    already_locked: bool = False


class ObjectLockedEvidenceObject(BaseModel):
    """
    Downstream Handoff Contract:
    Produced by MOD-10 (WORM Object Lock) and consumed by MOD-11 (AES-256-GCM Encryption).

    Strict Invariant:
        Evidence must have integrity_status == 'VERIFIED' (MOD-09 gate)
        AND lock_status == 'LOCKED' (MOD-10 gate)
        before this contract can be yielded.

    Architectural Clarification:
        This contract formalises the object-lock boundary.
        In this Phase 3 implementation, enforcement is application-level
        (local filesystem + read-only permission stripping). True hardware/cloud-enforced
        Object Lock (e.g., AWS S3 Object Lock) requires cloud infrastructure
        and is the target of a future production phase.
    """
    case_id: str
    evidence_id: str
    original_file_name: str
    evidence_category: str
    file_size_bytes: int
    # MOD-08 WORM reference
    worm_storage_reference: str
    # MOD-10 Object Lock reference
    lock_storage_reference: str
    lock_status: str = "LOCKED"
    lock_mode: str = "GOVERNANCE"
    lock_backend: str
    lock_applied_at: datetime
    lock_retention_until: Optional[datetime] = None
    lock_overwrite_protected: bool = True
    lock_delete_protected: bool = True
    # Dual-hash integrity binding (SHA-256 + SHA3-512 fingerprint captured at lock time)
    lock_integrity_binding: str
    checksum_sha256: str
    checksum_sha3_512: str
    integrity_status: str = "VERIFIED"
    verified_at: datetime
    source: str = "MOD-10"


# ─── MOD-11: AES-256-GCM Encryption Schemas & Downstream Contract ────────

class EncryptionResult(BaseModel):
    """
    Internal and API result for MOD-11 AES-256-GCM encryption operation.
    Returned by POST /evidence/{id}/encrypt.
    """
    evidence_id: str
    case_id: str
    encryption_status: str = "ENCRYPTED"       # ENCRYPTED | ENCRYPTION_FAILED
    encryption_algorithm: str = "AES-256-GCM"  # Authenticated symmetric cipher
    encryption_storage_reference: str          # enc://<case_id>/<sha256_prefix>+<nonce_prefix>
    key_reference: str                         # Case-scoped key reference URI
    key_provider: str                          # LOCAL_DEV_KEY_PROVIDER | AWS_KMS | PKCS11_HSM
    nonce_hex: str                             # 96-bit (12 bytes) IV/nonce in hex
    auth_tag_hex: str                          # 128-bit (16 bytes) GCM auth tag in hex
    aad_binding: str                           # Associated Authenticated Data
    ciphertext_sha256: str                     # SHA-256 checksum of ciphertext
    file_size_bytes: int                       # Original unencrypted payload bytes
    encrypted_file_size_bytes: int             # Encrypted payload bytes
    encrypted_at: datetime
    checksum_sha256: str                       # Original SHA-256 pre-hash
    checksum_sha3_512: str                     # Original SHA3-512 pre-hash
    lock_storage_reference: str                # MOD-10 WORM Object Lock reference
    message: str
    already_encrypted: bool = False


class EncryptedEvidenceObject(BaseModel):
    """
    Downstream Handoff Contract:
    Produced by MOD-11 (AES-256-GCM Encryption) and consumed by MOD-12 (TLS 1.3 / mTLS).

    Strict Invariants:
        Evidence must have:
            - integrity_status == 'VERIFIED' (MOD-09 dual-hash gate)
            - lock_status == 'LOCKED' (MOD-10 object-lock gate)
            - encryption_status == 'ENCRYPTED' (MOD-11 encryption gate)
        Authenticated encryption tag and AAD binding must be valid.
    """
    case_id: str
    evidence_id: str
    original_file_name: str
    evidence_category: str
    file_size_bytes: int
    encrypted_file_size_bytes: int
    worm_storage_reference: str
    lock_storage_reference: str
    encryption_storage_reference: str
    encryption_status: str = "ENCRYPTED"
    encryption_algorithm: str = "AES-256-GCM"
    key_reference: str
    key_provider: str
    nonce_hex: str
    auth_tag_hex: str
    aad_binding: str
    checksum_sha256: str
    checksum_sha3_512: str
    ciphertext_sha256: str
    encrypted_at: datetime
    source: str = "MOD-11"


class EncryptionVerificationResult(BaseModel):
    """
    Internal and API result for MOD-11 Encryption Verification operation.
    Validates ciphertext integrity, tag authenticity, and trial decryption dual-hash match.
    Returned by POST /evidence/{id}/verify-encryption.
    """
    evidence_id: str
    case_id: str
    encryption_status: str
    verification_status: str               # VERIFIED | TAMPER_DETECTED
    tag_valid: bool
    ciphertext_integrity_matched: bool
    dual_hash_integrity_matched: bool
    key_reference: str
    verified_at: datetime
    message: str

