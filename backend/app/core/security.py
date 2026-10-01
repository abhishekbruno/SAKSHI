"""
Identity and security models for SAKSHI Investigation Platform.
MOD-02: Identity / OIDC — Canonical Authenticated Investigator representation.

Enforces the Zero-Password Principle: No authentication passwords/secrets stored in domain models.
The external identity provider remains the authority for authentication.
SAKSHI maintains only the validated identity claims required for downstream processing.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class AuthenticatedInvestigator(BaseModel):
    """
    Canonical representation of an authenticated investigator, extracted from
    the Identity/OIDC validation boundary.

    This model is consumed by all downstream modules (Case Management, RBAC/ABAC,
    Stage Engine). It never contains raw credentials, passwords, or signing keys.

    Fields:
        subject_id:            Stable unique identifier from the IdP (OIDC 'sub' claim).
                               This is the authoritative identity reference across SAKSHI.
        username:              Preferred username / login handle (OIDC 'preferred_username').
        display_name:          Human-readable name for audit trails and UI display.
        email:                 Contact email from identity claims.
        roles:                 List of role claims (for downstream MOD-03 RBAC/ABAC).
        claims:                Sanitized subset of identity claims (no secrets).
        issuer:                Token issuer URL — identifies which IdP authenticated this user.
        authentication_method: How this identity was established ('oidc', 'development').

    Legacy compatibility:
        investigator_id:       Alias for subject_id — preserved for MOD-01 backward compatibility.
        role:                  Primary role string — preserved for MOD-01 backward compatibility.
        station_jurisdiction:  Jurisdiction code — preserved for MOD-01 backward compatibility.
        scopes:                Granted token scopes.
        is_authenticated:      Confirmation flag.
        raw_claims:            Alias for claims — preserved for MOD-01 backward compatibility.
    """
    # ─── MOD-02 Canonical Fields ─────────────────────────────────────────
    subject_id: str = Field(
        ...,
        description="Unique subject identifier from OIDC 'sub' claim or internal identity system"
    )
    username: Optional[str] = Field(
        default=None,
        description="Preferred username (OIDC 'preferred_username' claim)"
    )
    display_name: str = Field(
        default="Investigating Officer",
        description="Full name or designated title for display and audit"
    )
    email: Optional[str] = Field(
        default=None,
        description="Contact email from identity claims"
    )
    roles: List[str] = Field(
        default_factory=list,
        description="Role claims for downstream RBAC/ABAC (MOD-03)"
    )
    claims: Dict[str, Any] = Field(
        default_factory=dict,
        description="Sanitized identity claims — never contains secrets"
    )
    issuer: Optional[str] = Field(
        default=None,
        description="Token issuer URL identifying the authenticating IdP"
    )
    authentication_method: str = Field(
        default="development",
        description="How this identity was established: 'oidc' or 'development'"
    )

    # ─── MOD-01 Backward Compatibility ───────────────────────────────────
    # These fields preserve the interface consumed by CaseService and existing tests.
    # They are derived from the canonical fields above.

    @property
    def investigator_id(self) -> str:
        """Backward-compatible alias: subject_id is the authoritative identity."""
        return self.subject_id

    name: str = Field(
        default="Investigating Officer",
        description="Full name or designated title (legacy, same as display_name)"
    )
    role: str = Field(
        default="INVESTIGATING_OFFICER",
        description="Primary role string for MOD-01 backward compatibility"
    )
    station_jurisdiction: Optional[str] = Field(
        default=None,
        description="Station or territorial jurisdiction code"
    )
    scopes: List[str] = Field(
        default_factory=list,
        description="Granted OIDC token scopes"
    )
    is_authenticated: bool = Field(
        default=True,
        description="Authentication confirmation status"
    )
    raw_claims: Dict[str, Any] = Field(
        default_factory=dict,
        description="Raw claims from Identity Token (legacy alias for claims)"
    )
