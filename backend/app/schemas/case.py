"""
Pydantic schemas for SAKSHI Case Management Service.
Defines strict input validation, response serialization, and the Phase 2 Integration Contract.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator


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
    fir_metadata: FIRMetadata = Field(..., description="Structured initial FIR metadata")
    assigned_io_id: Optional[str] = Field(
        default=None,
        description="Designated Investigating Officer ID. If omitted, assigned to the authenticated requester."
    )


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
