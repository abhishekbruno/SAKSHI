"""
Pydantic schemas for SAKSHI Evidence Intake Service (MOD-05).
Defines intake metadata validation, response contracts, and the downstream
handoff contract (RegisteredEvidenceObject) to MOD-06.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class EvidenceCategory(str, Enum):
    """Forensic evidence classification categories."""
    DOCUMENT_PDF = "DOCUMENT_PDF"
    DOCUMENT = "DOCUMENT_PDF"
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

    # MOD-10: WORM Object Lock Fields
    lock_status: Optional[str] = None
    lock_mode: Optional[str] = None
    lock_storage_reference: Optional[str] = None
    lock_applied_at: Optional[datetime] = None
    lock_retention_until: Optional[datetime] = None
    lock_backend: Optional[str] = None
    lock_overwrite_protected: Optional[bool] = None
    lock_delete_protected: Optional[bool] = None
    lock_integrity_binding: Optional[str] = None

    # MOD-11: AES-256-GCM Encryption Fields
    encryption_status: Optional[str] = None
    encryption_algorithm: Optional[str] = None
    encryption_key_reference: Optional[str] = None
    encryption_key_provider: Optional[str] = None
    encryption_storage_reference: Optional[str] = None
    ciphertext_sha256: Optional[str] = None
    encrypted_file_size_bytes: Optional[int] = None
    encrypted_at: Optional[datetime] = None

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


# ─── MOD-05 to MOD-10: Pipeline Orchestration Result Schemas ─────────────

class PipelineStage(str, Enum):
    """The stages executed by the MOD-05 through MOD-10 evidence pipeline."""
    INTAKE = "INTAKE"
    MIME_VALIDATION = "MIME_VALIDATION"
    ANTIVIRUS_SCAN = "ANTIVIRUS_SCAN"
    WORM_COMMIT = "WORM_COMMIT"
    DUAL_HASHING = "DUAL_HASHING"
    OBJECT_LOCK = "OBJECT_LOCK"


class PipelineExecutionStatus(str, Enum):
    """Terminal outcome of one MOD-05 through MOD-10 pipeline execution."""
    SUCCESS = "SUCCESS"
    INTAKE_FAILED = "INTAKE_FAILED"
    MIME_VALIDATION_FAILED = "MIME_VALIDATION_FAILED"
    ANTIVIRUS_QUARANTINED = "ANTIVIRUS_QUARANTINED"
    WORM_COMMIT_FAILED = "WORM_COMMIT_FAILED"
    INTEGRITY_FAILED = "INTEGRITY_FAILED"
    OBJECT_LOCK_FAILED = "OBJECT_LOCK_FAILED"
    RETRYABLE_ERROR = "RETRYABLE_ERROR"


class PipelineExecutionResult(BaseModel):
    """
    Summary contract for a single MOD-05 through MOD-10 pipeline execution.

    This schema reports an orchestration outcome; it does not execute pipeline work.
    `evidence_id` remains optional because intake can fail before an evidence record exists.
    """
    case_id: str
    evidence_id: Optional[str] = None
    overall_status: PipelineExecutionStatus
    current_stage: Optional[PipelineStage] = None
    intake_status: Optional[EvidenceIntakeStatus] = None
    message: str
    is_retryable: bool = False
    started_at: datetime
    completed_at: datetime
    completed_stages: List[PipelineStage] = Field(default_factory=list)
    worm_storage_reference: Optional[str] = None
    checksum_sha256: Optional[str] = None
    already_committed: bool = False
    lock_storage_reference: Optional[str] = None
    checksum_sha3_512: Optional[str] = None
    integrity_status: Optional[str] = None
    lock_status: Optional[str] = None
    document_id: Optional[str] = None
    indexing_status: Optional[str] = None

    @property
    def evidence_status(self) -> Optional[EvidenceIntakeStatus]:
        """Backward-compatible accessor for intake_status."""
        return self.intake_status

    @property
    def terminal_reason(self) -> str:
        """Backward-compatible accessor for message."""
        return self.message

    @property
    def rag_indexing_status(self) -> Optional[str]:
        """Backward-compatible accessor for indexing_status."""
        return self.indexing_status

    @field_validator("started_at", "completed_at")
    @classmethod
    def require_aware_utc_timestamp(cls, value: datetime) -> datetime:
        """Reject naive datetimes and normalize aware values to UTC."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_retryable_status(self) -> "PipelineExecutionResult":
        """A retryable result must be represented by RETRYABLE_ERROR."""
        if (
            self.is_retryable
            and self.overall_status != PipelineExecutionStatus.RETRYABLE_ERROR
        ):
            raise ValueError(
                "is_retryable may be True only when "
                "overall_status is RETRYABLE_ERROR"
            )
        return self


# ─── Extracted Facts, Branching Timeline & Analysis Schemas ───────────────

class FactAttributionType(str, Enum):
    """Forensic classification for fact attribution and verification standard."""
    QUOTED_FROM_SOURCE = "QUOTED_FROM_SOURCE"
    EXTRACTED_BY_SOFTWARE = "EXTRACTED_BY_SOFTWARE"
    AI_INTERPRETATION = "AI_INTERPRETATION"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"


class ExtractedFactItem(BaseModel):
    """Individual extracted forensic fact with provenance and attribution metadata."""
    fact_id: str
    category: str = Field(..., description="Fact category: DATE_TIME, LOCATION, PERSON_ENTITY, STATEMENT, IDENTIFIER, OBSERVATION, UNCERTAINTY")
    title: str
    fact_text: str
    attribution_type: FactAttributionType
    attribution_note: str = Field(..., description="Plain-language explanation of source grounding")
    evidence_id: str
    source_filename: str
    page_number: Optional[int] = None
    char_offset_start: Optional[int] = None
    char_offset_end: Optional[int] = None
    source_passage: Optional[str] = None
    verified_by_investigator: bool = False


class EvidenceExtractedFactsResponse(BaseModel):
    """Structured response for document content extraction and forensic fact review."""
    evidence_id: str
    case_id: str
    original_filename: str
    is_supported: bool
    detected_format: Optional[str] = None
    indexing_status: str
    document_summary: Optional[str] = None
    summary_label: str = "AI-Generated Summary — Grounded in Document Text (Requires Investigator Corroboration)"
    total_facts: int = Field(0, description="Total count of extracted facts")
    facts: List[ExtractedFactItem] = Field(default_factory=list)
    important_passages: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    message: Optional[str] = None


class TimelineCertainty(str, Enum):
    """Certainty level for chronological timeline events."""
    EXACT = "EXACT"
    ESTIMATED = "ESTIMATED"
    REPORTED = "REPORTED"
    UNKNOWN = "UNKNOWN"


class TimelineEventItem(BaseModel):
    """Evidence-grounded chronological event with branching support."""
    event_id: str
    time: str = Field(..., description="Time string (HH:MM) or ISO-8601")
    date: str = Field(..., description="Date string (YYYY-MM-DD)")
    raw_timestamp: Optional[str] = None
    title: str
    description: str
    evidence_id: str
    source_name: str
    source_page: Optional[int] = None
    time_certainty: TimelineCertainty = TimelineCertainty.EXACT
    confidence_level: str = "HIGH"
    branch_id: str = Field("MAIN", description="Branch identifier: MAIN, BRANCH_A, BRANCH_B")
    branch_label: Optional[str] = None
    is_contradiction: bool = False
    contradiction_detail: Optional[str] = None


class BranchingTimelineResponse(BaseModel):
    """Branching timeline dataset with active branches and unresolved timing conflicts."""
    case_id: str
    total_events: int
    branches: List[str] = Field(default_factory=lambda: ["MAIN"])
    branch_labels: dict[str, str] = Field(default_factory=lambda: {"MAIN": "Common Chronological Sequence"})
    events: List[TimelineEventItem] = Field(default_factory=list)
    temporal_conflicts: List[dict] = Field(default_factory=list)


class InvestigationContradictionItem(BaseModel):
    """Specific discrepancy between two verified sources."""
    contradiction_id: str
    title: str
    source_a_filename: str
    source_a_passage: str
    source_b_filename: str
    source_b_passage: str
    difference_summary: str
    is_timing_uncertain: bool = False
    investigator_status: str = "UNRESOLVED"  # UNRESOLVED, CONFIRMED, DISMISSED, INVESTIGATING


class CandidateScenarioItem(BaseModel):
    """Candidate investigative explanation, strictly labeled as hypothesis."""
    scenario_id: str
    title: str
    hypothesis_disclaimer: str = "Candidate Investigative Hypothesis — Not Established Fact"
    plain_language_description: str
    supporting_evidence: List[str] = Field(default_factory=list)
    conflicting_evidence: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)
    confidence_limitations: str
    distinguishing_evidence_needed: str
    investigator_review_decision: Optional[str] = None


class InvestigationAnalysisResponse(BaseModel):
    """Structured guided analysis workspace model."""
    case_id: str
    evidence_count: int
    supported_observations: List[dict] = Field(default_factory=list)
    contradictions: List[InvestigationContradictionItem] = Field(default_factory=list)
    investigation_gaps: List[dict] = Field(default_factory=list)
    candidate_scenarios: List[CandidateScenarioItem] = Field(default_factory=list)


# ─── Knowledge Graph Schemas ──────────────────────────────────────────────────

class EntityNodeType(str, Enum):
    """Entity categories grounded in police evidence."""
    PERSON = "PERSON"
    OBJECT = "OBJECT"
    LOCATION = "LOCATION"
    DOCUMENT = "DOCUMENT"
    EVENT = "EVENT"


class EntityEdgeType(str, Enum):
    """Relationship categories between entities."""
    REPORTED_BY = "REPORTED_BY"
    WITNESSED_BY = "WITNESSED_BY"
    SEIZED_FROM = "SEIZED_FROM"
    LOCATED_AT = "LOCATED_AT"
    FAMILY_RELATION_TO = "FAMILY_RELATION_TO"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    MENTIONED_IN = "MENTIONED_IN"
    DISPUTES = "DISPUTES"
    FORENSIC_MATCH_TO = "FORENSIC_MATCH_TO"


class RelationshipReviewStatus(str, Enum):
    """Investigator review state for an entity relationship."""
    REPORTED = "REPORTED"
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    REJECTED = "REJECTED"
    UNRESOLVED = "UNRESOLVED"


class EntityNode(BaseModel):
    """Grounded entity node in the investigation knowledge graph."""
    id: str
    name: str
    category: EntityNodeType
    subtitle: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    evidence_id: Optional[str] = None
    source_filename: Optional[str] = None
    timeline_event_ids: List[str] = Field(default_factory=list)


class EntityEdge(BaseModel):
    """Evidence-grounded edge connecting two entities with provenance."""
    id: str
    source_node_id: str
    target_node_id: str
    relation_type: EntityEdgeType
    label: str
    evidence_id: str
    source_filename: str
    page_number: Optional[int] = None
    char_offset: Optional[int] = None
    source_passage: str
    review_status: RelationshipReviewStatus = RelationshipReviewStatus.REPORTED
    investigator_notes: Optional[str] = None
    citation: Optional[Dict[str, Any]] = None


class CaseKnowledgeGraphResponse(BaseModel):
    """Knowledge graph payload for an authorized case."""
    case_id: str
    total_nodes: int
    total_edges: int
    nodes: List[EntityNode] = Field(default_factory=list)
    edges: List[EntityEdge] = Field(default_factory=list)
    case_isolated: bool = True
    message: Optional[str] = None


class EdgeDecisionRequest(BaseModel):
    """Investigator decision on an entity edge."""
    decision: RelationshipReviewStatus
    corrected_relation: Optional[EntityEdgeType] = None
    notes: Optional[str] = None
    investigator_notes: Optional[str] = None


class EdgeDecisionResponse(BaseModel):
    """Outcome of an investigator relationship review."""
    edge_id: str
    new_status: RelationshipReviewStatus
    updated_at: datetime
    message: str
    edge: Optional[Dict[str, Any]] = None
    audit_recorded: bool = True


# ─── Dual-Brain Reasoning Schemas ─────────────────────────────────────────────

class IntuitionProposal(BaseModel):
    """Candidate investigative explanation proposed by Intuition Brain."""
    proposal_id: str
    title: str
    scenario_type: str
    hypothesis_statement: str
    proposed_sequence: List[str] = Field(default_factory=list)
    underlying_assumptions: List[str] = Field(default_factory=list)
    core_assumptions: List[str] = Field(default_factory=list)
    investigative_questions: List[str] = Field(default_factory=list)
    neutral_investigative_questions: List[str] = Field(default_factory=list)
    required_evidence_to_verify: List[str] = Field(default_factory=list)
    confidence_warning: str = (
        "Intuition proposal is an investigative hypothesis only. "
        "It carries ZERO legal or probative weight until verified against hard evidence."
    )


class DisciplineChallenge(BaseModel):
    """Rigorous evidentiary and procedural challenge produced by Discipline Brain."""
    challenge_id: str
    target_proposal_id: str
    evidentiary_objections: List[str] = Field(default_factory=list)
    evidentiary_objection: Optional[str] = None
    temporal_conflicts: List[str] = Field(default_factory=list)
    missing_mandatory_certificates: List[str] = Field(default_factory=list)
    statutory_procedural_rules: List[str] = Field(default_factory=list)
    statutory_rule_citation: Optional[str] = None
    evidence_gate_status: str
    unresolved_issues: List[str] = Field(default_factory=list)


class DualBrainAnalysisResponse(BaseModel):
    """Controlled comparison workspace separating Intuition Brain and Discipline Brain."""
    case_id: str
    evidence_count: int
    firewall_status: str = "ACTIVE_ENFORCED"
    evidence_gate_status: str = "ENFORCING_MINIMUM_CREDIBILITY"
    proposals: List[IntuitionProposal] = Field(default_factory=list)
    challenges: List[DisciplineChallenge] = Field(default_factory=list)
    intuition_proposals: List[IntuitionProposal] = Field(default_factory=list)
    discipline_challenges: List[DisciplineChallenge] = Field(default_factory=list)
    controlled_comparisons: List[Dict[str, Any]] = Field(default_factory=list)


# ─── Conversational Evidence RAG ("Ask About This Case") Schemas ──────────────

class CaseRAGAskRequest(BaseModel):
    """Officer natural-language question bounded to case evidence."""
    question: str = Field(..., min_length=2, max_length=1000)
    limit: int = Field(5, ge=1, le=10)


class RAGExcerptCitation(BaseModel):
    """Verbatim quoted passage from an evidence exhibit."""
    evidence_id: str
    exhibit_id: Optional[str] = None
    source_filename: str
    page_number: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    quoted_passage: str
    verbatim_quote: Optional[str] = None
    similarity_score: Optional[float] = None
    legal_caution: str = "Subject to Section 63 BSA / Section 65B IEA certificate of electronic authenticity."


class CaseRAGAskResponse(BaseModel):
    """Direct, evidence-grounded answer citing exact source passages."""
    case_id: str
    question: str
    answer: str
    citations: List[RAGExcerptCitation] = Field(default_factory=list)
    is_grounded: bool
    insufficient_evidence: bool = False
    disclaimer: str = (
        "Response synthesized strictly from verified, case-scoped evidence chunks. "
        "SAKSHI never invents facts or infers guilt."
    )



