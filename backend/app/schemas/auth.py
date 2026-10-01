"""
Pydantic schemas for MOD-02 Identity / OIDC API responses.
Defines the public contract for authentication endpoints.

SECURITY: These schemas expose ONLY sanitized identity information.
They NEVER include tokens, signing keys, passwords, or client secrets.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class AuthMeResponse(BaseModel):
    """
    Response schema for GET /api/v1/auth/me.
    Returns the authenticated investigator's identity context.
    """
    authenticated: bool = Field(
        default=True,
        description="Whether the investigator is authenticated"
    )
    subject_id: str = Field(
        ...,
        description="Unique subject identifier from the identity provider"
    )
    username: Optional[str] = Field(
        default=None,
        description="Preferred username / login handle"
    )
    display_name: str = Field(
        ...,
        description="Human-readable name for UI display and audit"
    )
    email: Optional[str] = Field(
        default=None,
        description="Contact email from identity claims"
    )
    roles: List[str] = Field(
        default_factory=list,
        description="Role claims for authorization (consumed by MOD-03 RBAC/ABAC)"
    )
    issuer: Optional[str] = Field(
        default=None,
        description="Token issuer URL — identifies the authenticating IdP"
    )
    authentication_method: str = Field(
        ...,
        description="How identity was established: 'oidc' or 'development'"
    )

    # Legacy MOD-01 compatibility fields
    investigator_id: str = Field(
        ...,
        description="Backward-compatible alias for subject_id"
    )
    role: str = Field(
        default="INVESTIGATING_OFFICER",
        description="Primary role string (legacy MOD-01 compatibility)"
    )
    station_jurisdiction: Optional[str] = Field(
        default=None,
        description="Station or territorial jurisdiction code"
    )


class AuthStatusResponse(BaseModel):
    """
    Response schema for GET /api/v1/auth/status.
    Returns non-sensitive authentication configuration status.
    """
    auth_mode: str = Field(
        ...,
        description="Current authentication mode: 'development' or 'oidc'"
    )
    oidc_configured: bool = Field(
        ...,
        description="Whether OIDC is fully configured with an issuer"
    )
    issuer_url: Optional[str] = Field(
        default=None,
        description="OIDC issuer URL (only in OIDC mode)"
    )
    client_id: Optional[str] = Field(
        default=None,
        description="OIDC client ID (only in OIDC mode, for frontend login flows)"
    )
    development_mode: bool = Field(
        ...,
        description="Whether the system is in development authentication mode"
    )
