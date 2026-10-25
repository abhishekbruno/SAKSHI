"""
Pydantic schemas for SAKSHI Case Management Service.
Defines strict input validation, response serialization, and the Phase 2 Integration Contract.
"""
import secrets
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class FIRMetadata(BaseModel):
    """Initial case information / FIR metadata contract."""
    fir_number: str = Field(..., min_length=2, max_length=64, description="Official First Information Report identifier")
    police_station: str = Field(..., min_length=2, max_length=128, description="Originating police station / jurisdiction")
    incident_date: Optional[str] = Field(None, description="ISO-8601 formatted date/time of incident occurrence")
    report_date: Optional[str] = Field(None, description="ISO-8601 formatted date/time of FIR registration")
    jurisdiction_code: Optional[str] = Field(None, description="Territorial or district jurisdiction code")
    incident_location: Optional[str] = Field(None, description="Reported location of incident or discovery of body")
    additional_attributes: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Flexible legal/procedural metadata")

    @field_validator("fir_number")
    @classmethod
    def validate_fir_number(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("FIR number must not be empty or blank whitespace.")
        return clean


class CaseCreateRequest(BaseModel):
    """Payload to initiate a new death investigation case."""
    title: str = Field(..., min_length=3, max_length=255, description="Brief descriptive title or legal reference")
    fir_metadata: Optional[FIRMetadata] = Field(default=None, description="Structured initial FIR metadata")
    assigned_io_id: Optional[str] = Field(
        default=None,
        description="Designated Investigating Officer ID. If omitted, assigned to the authenticated requester."
    )
    case_id: Optional[str] = Field(default=None, description="Optional custom or explicit Case ID")
    fir_number: Optional[str] = None
    police_station: Optional[str] = None
    incident_date: Optional[str] = None
    incident_location: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def assemble_fir_metadata(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("fir_metadata"):
                fir_num = data.get("fir_number") or f"FIR-{secrets.token_hex(3).upper()}/2026"
                ps = data.get("police_station") or "Connaught Place, New Delhi"
                data["fir_metadata"] = {
                    "fir_number": fir_num,
                    "police_station": ps,
                    "incident_date": data.get("incident_date"),
                    "incident_location": data.get("incident_location"),
                    "jurisdiction_code": data.get("jurisdiction_code") or "STATION_CENTRAL",
                }
        return data


class CaseUpdateRequest(BaseModel):
    """Permitted fields for case metadata updates."""
    title: Optional[str] = Field(None, min_length=3, max_length=255)
    fir_metadata: Optional[FIRMetadata] = None
    status: Optional[str] = Field(None, description="Operational status: ACTIVE, SUSPENDED, CLOSED")


class CaseAssignIORequest(BaseModel):
    """Payload to associate / reassign an Investigating Officer."""
    assigned_io_id: str = Field(..., min_length=2, max_length=128, description="Target Investigating Officer identifier")


class CaseStageUpdateRequest(BaseModel):
    """Payload for Stage Engine lifecycle updates."""
    lifecycle_stage: str = Field(..., min_length=2, max_length=64, description="New lifecycle state")


class CaseWorkspaceRepresentation(BaseModel):
    """Represents the isolated workspace boundary produced in Phase 1."""
    workspace_id: str
    case_id: str
    workspace_path: str
    ready_for_ingestion: bool = True


class CaseResponse(BaseModel):
    """
    Standard public Case API response.
    Isolates internal DB primary keys from public client view.
    """
    case_id: str = Field(..., description="Authoritative unique Case ID")
    title: str
    fir_metadata: Dict[str, Any]
    assigned_io_id: str
    lifecycle_stage: str
    status: str
    case_workspace: CaseWorkspaceRepresentation
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class CaseListResponse(BaseModel):
    """Paginated or filtered list of cases accessible to the authorized investigator."""
    total: int
    cases: List[CaseResponse]


class Phase2IntegrationContract(BaseModel):
    """
    Formal integration contract exported from Phase 1 to Phase 2 (Evidence Ingestion).
    Phase 2 requires this exact contract before ingesting multi-modal evidence objects.
    """
    case_id: str
    case_workspace_boundary: Dict[str, Any]
    authorized_io_id: str
    lifecycle_stage: str
    provenance: Dict[str, Any]


class FIRSourcePassage(BaseModel):
    """Traceable passage extracted from submitted FIR."""
    field: str = Field(..., description="Field name this passage grounds (e.g. fir_number, police_station)")
    quote: str = Field(..., description="Exact textual excerpt from the source document")
    char_offset: Optional[int] = Field(None, description="Starting character offset in source text")
    start_char: Optional[int] = Field(None, description="Exact start character index")
    end_char: Optional[int] = Field(None, description="Exact end character index")


class FIRAssistedExtractResponse(BaseModel):
    """
    Extracted candidate metadata from an FIR document.
    Presented for human investigator review and correction before authoritative case creation.
    """
    fir_number: str = Field(..., description="Extracted FIR number")
    police_station: str = Field(..., description="Extracted police station or jurisdiction")
    incident_date: Optional[str] = Field(None, description="Extracted date/time of occurrence")
    report_date: Optional[str] = Field(None, description="Extracted date of registration")
    incident_location: Optional[str] = Field(None, description="Extracted location")
    complainant_name: Optional[str] = Field(None, description="Extracted complainant or informant name")
    victim_name: Optional[str] = Field(None, description="Extracted deceased or victim name")
    offense_sections: Optional[str] = Field(None, description="Extracted statutory penal sections")
    reported_narrative: Optional[str] = Field(None, description="Concise candidate occurrence narrative")
    source_passages: List[FIRSourcePassage] = Field(default_factory=list, description="Exact source quotes grounding extracted fields")
    extraction_confidence: str = Field("CANDIDATE_EXTRACTION", description="Extraction certainty rating")
    disclaimer: str = Field(
        "Candidate extraction from submitted FIR document. "
        "All extracted fields require review and confirmation by the Investigating Officer prior to authoritative case registration.",
        description="Legal and procedural disclaimer"
    )


class FIRAssistedCaseCreateRequest(BaseModel):
    """
    Payload for Method B: FIR-Assisted Registration.
    Contains confirmed case metadata and initial FIR payload to be preserved into chain of custody.
    """
    title: str = Field(..., min_length=3, max_length=255)
    fir_metadata: Optional[FIRMetadata] = None
    assigned_io_id: Optional[str] = None
    case_id: Optional[str] = None
    fir_raw_text: Optional[str] = None
    fir_text: Optional[str] = None
    fir_filename: Optional[str] = Field("FIR_initial_record.pdf", description="Original filename of FIR document")
    fir_file_b64: Optional[str] = Field(None, description="Base64-encoded binary payload of FIR file if provided")
    fir_number: Optional[str] = None
    police_station: Optional[str] = None
    incident_date: Optional[str] = None
    incident_location: Optional[str] = None
    deceased_name: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def assemble_fir_payload(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if data.get("fir_text") and not data.get("fir_raw_text"):
                data["fir_raw_text"] = data["fir_text"]
            if not data.get("fir_metadata"):
                fir_num = data.get("fir_number") or f"FIR-{secrets.token_hex(3).upper()}/2026"
                ps = data.get("police_station") or "Connaught Place, New Delhi"
                data["fir_metadata"] = {
                    "fir_number": fir_num,
                    "police_station": ps,
                    "incident_date": data.get("incident_date"),
                    "incident_location": data.get("incident_location"),
                    "jurisdiction_code": data.get("jurisdiction_code") or "STATION_CENTRAL",
                }
        return data


class FIRAssistedCaseCreateResponse(BaseModel):
    """Response returned upon successful FIR-assisted case creation and evidence ingestion."""
    case: CaseResponse
    fir_evidence_id: Optional[str] = None
    evidence_id: Optional[str] = None
    chain_of_custody_logged: bool = True
    fir_pipeline_status: Optional[str] = None
    fir_indexing_status: Optional[str] = None
    message: str = "Case registered and initial FIR exhibit preserved into chain of custody."

