"""Public IAM contracts. Passwords are write-only and never echoed."""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class MobilePasswordLoginRequest(BaseModel):
    mobile_number: str = Field(..., min_length=8, max_length=32)
    password: str = Field(..., min_length=8, max_length=256)

class FirebaseLoginResponse(BaseModel):
    id_token: str
    expires_in: int
    token_type: str = "Bearer"

class OfficerCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    mobile_number: str = Field(..., min_length=8, max_length=32)
    role: str = Field(..., min_length=2, max_length=64)
    organization_id: str = Field(..., min_length=2, max_length=64)
    station_id: str = Field(..., min_length=2, max_length=64)
    jurisdiction_id: str = Field(..., min_length=2, max_length=64)
    service_identifier: Optional[str] = Field(None, max_length=128)
    initial_password: str = Field(..., min_length=12, max_length=256, repr=False)
    mobile_verified: bool = False

class OfficerUpdateRequest(BaseModel):
    role: Optional[str] = Field(None, min_length=2, max_length=64)
    station_id: Optional[str] = Field(None, min_length=2, max_length=64)
    jurisdiction_id: Optional[str] = Field(None, min_length=2, max_length=64)
    mobile_verified: Optional[bool] = None

class OfficerResponse(BaseModel):
    officer_id: str; username: str; full_name: str; mobile_e164: str; role: str
    organization_id: str; station_id: str; jurisdiction_id: str; status: str; mobile_verified: bool
    service_identifier: Optional[str] = None
    created_at: datetime; updated_at: datetime
    model_config = {"from_attributes": True}

class AssignmentCreateRequest(BaseModel):
    officer_id: str = Field(..., min_length=2, max_length=64)
    reason: str = Field(..., min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def non_blank_reason(cls, value):
        value = value.strip()
        if not value: raise ValueError("Assignment reason must not be blank.")
        return value

class AssignmentResponse(BaseModel):
    assignment_id: str; case_id: str; officer_id: str; previous_officer_id: Optional[str]
    assigned_by: str; reason: str; status: str; assigned_at: datetime; ended_at: Optional[datetime]
    model_config = {"from_attributes": True}

class ScopeCreateRequest(BaseModel):
    identifier: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=2, max_length=255)
    code: str = Field(..., min_length=2, max_length=64)
    organization_id: Optional[str] = Field(None, max_length=64)
    jurisdiction_id: Optional[str] = Field(None, max_length=64)

class OfficerTransferRequest(BaseModel):
    target_station_id: str = Field(..., min_length=2, max_length=64)
    target_jurisdiction_id: str = Field(..., min_length=2, max_length=64)
    reason: str = Field(..., min_length=3, max_length=1000)

    @field_validator("reason")
    @classmethod
    def non_blank_reason(cls, value):
        value = value.strip()
        if not value: raise ValueError("Transfer reason must not be blank.")
        return value

class OfficerResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=12, max_length=256, repr=False)

class OrganizationResponse(BaseModel):
    organization_id: str; name: str; code: str; status: str
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class JurisdictionResponse(BaseModel):
    jurisdiction_id: str; organization_id: str; name: str; code: str; status: str
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class StationResponse(BaseModel):
    station_id: str; organization_id: str; jurisdiction_id: str; name: str; code: str; status: str
    created_at: Optional[datetime] = None
    model_config = {"from_attributes": True}

class EligibleOfficerResponse(BaseModel):
    officer_id: str; username: str; full_name: str; role: str
    station_id: str; jurisdiction_id: str; status: str; mobile_verified: bool
    model_config = {"from_attributes": True}
