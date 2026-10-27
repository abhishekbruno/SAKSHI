"""
Pydantic Schemas for Phase F.1 — Evidence Intelligence, Entity Registry and Investigative Dossiers.
Strictly forensic, case-scoped, and provenance-grounded.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.evidence import RAGExcerptCitation


class SearchFilterType(str, Enum):
    """Supported search filters in the unified investigative search interface."""
    ALL = "ALL"
    EVIDENCE = "EVIDENCE"
    PERSON = "PERSON"
    OBJECT = "OBJECT"
    LOCATION = "LOCATION"
    EVENT = "EVENT"
    SOURCE_PASSAGE = "SOURCE_PASSAGE"


class SearchResultMatchType(str, Enum):
    """Categorization of match confidence and criteria."""
    EXACT_IDENTIFIER = "EXACT_IDENTIFIER"
    EXACT_NAME = "EXACT_NAME"
    PARTIAL_MATCH = "PARTIAL_MATCH"
    SEMANTIC_PASSAGE = "SEMANTIC_PASSAGE"
    RELATIONSHIP_MATCH = "RELATIONSHIP_MATCH"


class UnifiedSearchResultItem(BaseModel):
    """Individual result item in unified investigative search."""
    id: str
    type: str  # "EXHIBIT", "PERSON", "OBJECT", "LOCATION", "EVENT", "PASSAGE"
    name: str
    category: str
    identifier: Optional[str] = None  # Assigned exhibit number, person ID, or serial number
    subtitle: Optional[str] = None
    description: Optional[str] = None
    match_type: SearchResultMatchType
    match_reason: str
    source_evidence_id: Optional[str] = None
    source_filename: Optional[str] = None
    page_number: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    similarity_score: Optional[float] = None
    review_status: Optional[str] = None
    status: Optional[str] = None
    dossier_type: Optional[str] = None  # "person", "object", "exhibit"
    dossier_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class UnifiedSearchResponse(BaseModel):
    """Unified search payload containing categorized and ranked results."""
    case_id: str
    query: str
    filter_type: SearchFilterType
    total_results: int
    results: List[UnifiedSearchResultItem] = Field(default_factory=list)
    exact_match_found: bool = True
    disambiguation_required: bool = False
    disambiguation_candidates: List[Dict[str, Any]] = Field(default_factory=list)
    notice: Optional[str] = None


# ─── Person Dossier Schemas ──────────────────────────────────────────────────

class PersonIdentityField(BaseModel):
    """Documented or investigator-entered identifying attribute with provenance."""
    field_name: str
    value: Optional[str] = None
    source_type: str = "SOURCE_REPORTED"  # SOURCE_REPORTED, INVESTIGATOR_ENTERED, NOT_DOCUMENTED
    source_label: str
    evidence_id: Optional[str] = None
    source_filename: Optional[str] = None
    supporting_passage: Optional[str] = None


class PersonRelationshipItem(BaseModel):
    """Grounded relationship between the subject and other case entities."""
    edge_id: str
    target_id: str
    target_name: str
    target_category: str
    relationship_type: str
    label: str
    source_evidence_id: str
    source_filename: str
    supporting_passage: str
    status: str  # SOURCE_REPORTED, CORROBORATED, DISPUTED, INVESTIGATOR_CONFIRMED, REJECTED, UNRESOLVED
    decision_history: List[Dict[str, Any]] = Field(default_factory=list)


class PersonInteractionItem(BaseModel):
    """Reported or corroborated interaction involving the subject."""
    interaction_id: str
    participants: List[str]
    description: str
    reported_time: Optional[str] = None
    time_uncertainty: str = "EXACT"  # EXACT, APPROXIMATE, UNKNOWN
    location: Optional[str] = None
    source_evidence_id: str
    source_filename: str
    supporting_passage: str
    interaction_type: str = "REPORTED_BY_ANOTHER"  # DIRECTLY_OBSERVED, REPORTED_BY_ANOTHER, INVESTIGATOR_ENTERED
    review_status: str = "REPORTED"
    contradictions: List[str] = Field(default_factory=list)


class PersonAssociatedEvidenceItem(BaseModel):
    """Exhibit or source document referencing the person."""
    evidence_id: str
    original_file_name: str
    category: str
    mention_type: str
    page_or_offset: Optional[str] = None
    excerpt: Optional[str] = None


class PersonTimelineItem(BaseModel):
    """Chronological event referencing or involving the person."""
    event_id: str
    title: str
    timestamp_str: Optional[str] = None
    certainty: str = "EXACT"  # EXACT, APPROXIMATE, UNKNOWN
    description: str
    location: Optional[str] = None
    source_filename: str
    source_evidence_id: str
    supporting_passage: str


class PersonConflictItem(BaseModel):
    """Conflicting claims or inconsistencies regarding this person."""
    conflict_id: str
    conflict_type: str  # NAME_ALIAS, AGE_DOB, ROLE, STATEMENT, IDENTITY_MATCH
    claim_a: str
    source_a: str
    claim_b: str
    source_b: str
    status: str = "UNRESOLVED"


class PersonDossierResponse(BaseModel):
    """Complete source-grounded investigative dossier for a person."""
    person_id: str
    case_id: str
    canonical_name: str
    aliases: List[str] = Field(default_factory=list)
    identifying_info: Dict[str, PersonIdentityField] = Field(default_factory=dict)
    relationships: List[PersonRelationshipItem] = Field(default_factory=list)
    interactions: List[PersonInteractionItem] = Field(default_factory=list)
    associated_evidence: List[PersonAssociatedEvidenceItem] = Field(default_factory=list)
    timeline: List[PersonTimelineItem] = Field(default_factory=list)
    conflicts: List[PersonConflictItem] = Field(default_factory=list)
    investigator_review_status: str = "PENDING_REVIEW"
    provenance_records: List[Dict[str, Any]] = Field(default_factory=list)
    legal_safeguard: str = (
        "Judicial Caution: Role statements and presence in timeline do not infer guilt, "
        "culpability, motive, or criminal liability. Allegations remain subject to formal proof."
    )


# ─── Object and Physical Exhibit Dossier Schemas ─────────────────────────────

class ObjectCharacteristicItem(BaseModel):
    """Specific physical attribute or measurement with units, method, and source."""
    attribute_name: str
    value: str  # If missing, "Not documented in available evidence"
    unit: Optional[str] = None  # e.g. "cm", "mm", "g"
    source_type: str  # REPORTED_IN_SOURCE, MEASURED_DURING_EXAMINATION, INVESTIGATOR_ENTERED, NOT_DOCUMENTED
    source_evidence_id: Optional[str] = None
    source_filename: Optional[str] = None
    measurement_method: Optional[str] = None
    supporting_passage: Optional[str] = None
    review_status: str = "REPORTED"


class ObjectDossierResponse(BaseModel):
    """Complete source-grounded investigative dossier for a physical object or exhibit."""
    object_id: str
    case_id: str
    exhibit_number: str
    internal_record_id: str
    object_type: str
    description: str
    original_filename: Optional[str] = None
    evidence_category: Optional[str] = None
    recovery_location: Optional[str] = None
    recovery_details: Optional[str] = None
    collection_datetime: Optional[datetime] = None
    custody_status: str
    integrity_status: str
    checksum_sha256: Optional[str] = None
    characteristics_register: List[ObjectCharacteristicItem] = Field(default_factory=list)
    forensic_limitations_notice: str = (
        "Forensic Safeguard: Sharpness, cutting capability, penetration depth, or likely injury causation "
        "must not be inferred from the item name or unexamined photographs alone. Such conclusions require "
        "a documented forensic examination by an accredited laboratory."
    )
    examination_findings: List[Dict[str, Any]] = Field(default_factory=list)
    associated_persons: List[Dict[str, Any]] = Field(default_factory=list)
    associated_locations_events: List[Dict[str, Any]] = Field(default_factory=list)
    source_passages: List[Dict[str, Any]] = Field(default_factory=list)
    missing_characteristics: List[str] = Field(default_factory=list)
    media_links: List[Dict[str, Any]] = Field(default_factory=list)


# ─── Source Comparison and Contradiction Review Schemas ──────────────────────

class SourceComparisonItem(BaseModel):
    """Side-by-side comparison of conflicting or divergent evidence claims."""
    comparison_id: str
    topic: str
    claim_a: Dict[str, Any]
    claim_b: Dict[str, Any]
    discrepancy_type: str  # TEMPORAL_CONFLICT, MEASUREMENT_DISCREPANCY, IDENTITY_DISCREPANCY, STATEMENT_CONFLICT
    status: str = "UNRESOLVED"  # UNRESOLVED, POTENTIAL_DISCREPANCY, INVESTIGATOR_RESOLVED
    resolution_history: List[Dict[str, Any]] = Field(default_factory=list)


class SourceComparisonResponse(BaseModel):
    """Case-scoped source comparison dataset."""
    case_id: str
    total_comparisons: int
    comparisons: List[SourceComparisonItem] = Field(default_factory=list)


# ─── Missing Information and Follow-up Suggestions Schemas ───────────────────

class InvestigationFollowupItem(BaseModel):
    """Identified investigation gap or procedural follow-up action."""
    id: str
    category: str  # MISSING_IDENTIFYING_DETAIL, UNDOCUMENTED_CHARACTERISTIC, UNRESOLVED_RELATIONSHIP, UNCERTAIN_TIMESTAMP, PENDING_LAB_REPORT
    title: str
    what_is_unknown: str
    why_it_matters: str
    prompted_by_source: str
    recommended_action: str
    procedural_requirement: bool = False
    status: str = "PENDING"  # PENDING, ADDRESSED, NOT_APPLICABLE, UNRESOLVED


class InvestigationFollowupResponse(BaseModel):
    """List of identified follow-up opportunities for an authorized case."""
    case_id: str
    total_followups: int
    followups: List[InvestigationFollowupItem] = Field(default_factory=list)


# ─── Entity Registry Schemas ─────────────────────────────────────────────────

class RegistryEntitySummary(BaseModel):
    """Compact summary of a case entity for the stable registry."""
    id: str
    name: str
    category: str
    identifier: Optional[str] = None
    subtitle: Optional[str] = None
    associated_evidence_count: int = 0
    review_status: str = "REPORTED"
    dossier_type: str  # "person", "object", "exhibit"


class EntityRegistryResponse(BaseModel):
    """Case-wide catalog of all discovered, extracted, and cataloged entities."""
    case_id: str
    total_entities: int
    entities: List[RegistryEntitySummary] = Field(default_factory=list)


# ─── 6-Section Evidence-Backed Answer Schema ──────────────────────────────────

class EvidenceBackedStructuredAnswerResponse(BaseModel):
    """
    Evidence-grounded answer synthesized according to Phase F.1 Section 7:
    1. Directly documented information
    2. Supporting source references
    3. Conflicting or inconsistent information
    4. Missing or undocumented information
    5. Possible interpretations (labeled hypotheses)
    6. Suggested follow-up questions
    """
    case_id: str
    question: str
    documented_information: List[str] = Field(default_factory=list)
    supporting_source_references: List[RAGExcerptCitation] = Field(default_factory=list)
    conflicting_information: List[str] = Field(default_factory=list)
    missing_or_undocumented_information: List[str] = Field(default_factory=list)
    possible_interpretations: List[str] = Field(default_factory=list)
    suggested_followups: List[str] = Field(default_factory=list)
    answer_text: str
    is_grounded: bool = True
