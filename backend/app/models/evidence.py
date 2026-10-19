"""
SQLAlchemy ORM model for Evidence entity in SAKSHI.
Phase 2: Evidence Ingestion (MOD-05 Evidence Intake).
Governs raw multi-modal evidence objects before MIME sniffing, AV scan, and WORM commit.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Boolean
from app.db.base import Base


def get_utc_now():
    return datetime.now(timezone.utc)


class Evidence(Base):
    __tablename__ = "evidence"

    # Internal immutable database primary key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)

    # Authoritative canonical Evidence ID (e.g. SAKSHI-EVID-2026-8F3E9A21)
    evidence_id = Column(String(64), unique=True, nullable=False, index=True)

    # Reference to parent Case
    case_id = Column(String(64), ForeignKey("cases.case_id"), nullable=False, index=True)

    # Original client filename and sanitized storage filename
    original_file_name = Column(String(255), nullable=False)
    stored_file_name = Column(String(255), nullable=False)

    # Forensic evidence category:
    # DOCUMENT_PDF, SCENE_PHOTO, AUTOPSY_PHOTO, AUDIO_RECORDING, CDR_SPREADSHEET, DIGITAL_DEVICE_EXTRACTION, OTHER
    evidence_category = Column(String(64), nullable=False, index=True)

    # Declared MIME type provided during intake (verified in MOD-06)
    declared_mime_type = Column(String(128), nullable=False)

    # Measured file size in bytes
    file_size_bytes = Column(Integer, nullable=False)

    # Forensic intake metadata
    collection_datetime = Column(DateTime(timezone=True), nullable=True)
    collection_location = Column(String(255), nullable=True)
    source_device_or_person = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    # Submitting Investigator Reference
    submitting_investigator_id = Column(String(128), nullable=False, index=True)

    # Lifecycle / Pipeline Intake Status:
    # REGISTERED_INTAKE, PENDING_MIME_VALIDATION, VALIDATED, QUARANTINED, COMMITTED, REJECTED
    status = Column(String(64), nullable=False, default="REGISTERED_INTAKE", index=True)

    # MOD-06: MIME / Signature Validation Outcome Fields
    detected_mime_type = Column(String(128), nullable=True)
    detected_format = Column(String(64), nullable=True)
    validation_reason = Column(Text, nullable=True)
    validated_at = Column(DateTime(timezone=True), nullable=True)

    # MOD-07: Antivirus Scan Outcome Fields
    antivirus_status = Column(String(64), nullable=True)
    antivirus_scanner = Column(String(64), nullable=True)
    antivirus_version = Column(String(64), nullable=True)
    antivirus_threat_name = Column(String(255), nullable=True)
    antivirus_message = Column(Text, nullable=True)
    antivirus_scanned_at = Column(DateTime(timezone=True), nullable=True)

    # MOD-08: WORM Commit + SHA-256 Checksum Fields
    checksum_algorithm = Column(String(32), nullable=True)
    checksum_sha256 = Column(String(64), nullable=True, index=True)
    checksum_computed_at = Column(DateTime(timezone=True), nullable=True)
    worm_status = Column(String(64), nullable=True)
    worm_storage_reference = Column(String(512), nullable=True)
    worm_committed_at = Column(DateTime(timezone=True), nullable=True)
    worm_commit_message = Column(Text, nullable=True)

    # MOD-09: Dual Hashing (SHA-256 + SHA3-512) & Integrity Verification Fields
    checksum_sha3_512 = Column(String(128), nullable=True, index=True)
    sha3_512_computed_at = Column(DateTime(timezone=True), nullable=True)
    integrity_status = Column(String(32), nullable=True, default="UNVERIFIED")
    integrity_verified_at = Column(DateTime(timezone=True), nullable=True)
    integrity_verification_message = Column(Text, nullable=True)

    # MOD-10: WORM Object Lock / Dual Storage Fields
    # lock_status: UNLOCKED | LOCKED | LOCK_FAILED
    lock_status = Column(String(32), nullable=True, default="UNLOCKED", index=True)
    # lock_mode: GOVERNANCE | COMPLIANCE (mirrors S3 Object Lock modes semantically)
    lock_mode = Column(String(32), nullable=True)
    # Canonical immutable object-lock storage reference: objlock://<case_id>/<sha256>+<sha3_512_prefix>
    lock_storage_reference = Column(String(512), nullable=True)
    lock_applied_at = Column(DateTime(timezone=True), nullable=True)
    # Retention period end — evidence MUST NOT be deleted/modified before this timestamp
    lock_retention_until = Column(DateTime(timezone=True), nullable=True)
    # Backend that enforced the lock (e.g. LOCAL_FILESYSTEM, S3_OBJECT_LOCK)
    lock_backend = Column(String(64), nullable=True)
    # Explicit protection flags
    lock_overwrite_protected = Column(Boolean, nullable=True, default=False)
    lock_delete_protected = Column(Boolean, nullable=True, default=False)
    # Cryptographic binding: stores the dual-hash fingerprint at time of lock
    lock_integrity_binding = Column(String(256), nullable=True)
    lock_failure_reason = Column(Text, nullable=True)
    # Append-only structured audit log of object-lock lifecycle events (JSON)
    object_lock_event_log = Column(Text, nullable=True)

    # MOD-11: AES-256-GCM Encryption Fields
    # encryption_status: UNENCRYPTED | ENCRYPTED | ENCRYPTION_FAILED
    encryption_status = Column(String(32), nullable=True, default="UNENCRYPTED", index=True)
    encryption_algorithm = Column(String(32), nullable=True)  # AES-256-GCM
    encryption_key_reference = Column(String(256), nullable=True)  # e.g. localkms://cases/<case_id>/keys/v1
    encryption_key_provider = Column(String(64), nullable=True)   # LOCAL_DEV_KEY_PROVIDER | AWS_KMS | PKCS11_HSM
    encryption_storage_reference = Column(String(512), nullable=True)  # enc://<case_id>/<sha256>+<nonce_prefix>
    encryption_nonce_hex = Column(String(64), nullable=True)      # 96-bit (12 bytes) IV/nonce in hex
    encryption_auth_tag_hex = Column(String(64), nullable=True)   # 128-bit (16 bytes) GCM auth tag in hex
    encryption_aad = Column(Text, nullable=True)                  # Associated Authenticated Data
    ciphertext_sha256 = Column(String(64), nullable=True, index=True)  # SHA-256 of ciphertext
    encrypted_file_size_bytes = Column(Integer, nullable=True)    # Ciphertext file size in bytes
    encrypted_file_path = Column(String(512), nullable=True)      # Physical path to encrypted file
    encrypted_at = Column(DateTime(timezone=True), nullable=True)
    encryption_failure_reason = Column(Text, nullable=True)
    encryption_event_log = Column(Text, nullable=True)             # Append-only structured audit log (JSON)

    # Physical Staging Location relative to or within the isolated Case Workspace boundary
    raw_storage_path = Column(String(512), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    def __repr__(self) -> str:
        return (
            f"<Evidence(evidence_id='{self.evidence_id}', case_id='{self.case_id}', "
            f"category='{self.evidence_category}', status='{self.status}')>"
        )
