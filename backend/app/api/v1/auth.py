"""
MOD-02: Identity / OIDC — Authentication API Endpoints.
Version: v1 (/api/v1/auth)

Provides:
    GET /api/v1/auth/me — Returns the authenticated investigator's identity context.
    GET /api/v1/auth/status — Returns authentication configuration status (non-sensitive).

SECURITY:
    - Does NOT return raw tokens, signing keys, or client secrets.
    - Does NOT expose internal cryptographic details.
    - Returns only sanitized identity information suitable for the frontend.
"""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_investigator
from app.core.security import AuthenticatedInvestigator
from app.core.config import settings
from app.schemas.auth import AuthMeResponse, AuthStatusResponse

router = APIRouter(prefix="/auth", tags=["Identity / Authentication (MOD-02)"])


@router.get(
    "/me",
    response_model=AuthMeResponse,
    summary="Get authenticated investigator identity"
)
def get_auth_me(
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator)
) -> AuthMeResponse:
    """
    Returns the identity context of the currently authenticated investigator.

    Behavior:
        No token       → 401 Unauthorized (AUTHENTICATION_REQUIRED)
        Invalid token   → 401 Unauthorized (INVALID_TOKEN)
        Expired token   → 401 Unauthorized (TOKEN_EXPIRED)
        Valid token     → Authenticated investigator identity

    This endpoint does NOT return sensitive token information, signing keys,
    or raw authentication credentials.
    """
    return AuthMeResponse(
        authenticated=True,
        subject_id=investigator.subject_id,
        username=investigator.username,
        display_name=investigator.display_name,
        email=investigator.email,
        roles=investigator.roles,
        issuer=investigator.issuer,
        authentication_method=investigator.authentication_method,
        # Legacy fields for MOD-01 compatibility
        investigator_id=investigator.investigator_id,
        role=investigator.role,
        station_jurisdiction=investigator.station_jurisdiction,
    )


@router.get(
    "/status",
    response_model=AuthStatusResponse,
    summary="Get authentication configuration status"
)
def get_auth_status() -> AuthStatusResponse:
    """
    Returns non-sensitive authentication configuration status.
    Does NOT require authentication.

    Useful for frontend to determine whether to show OIDC login or dev-mode login.
    """
    return AuthStatusResponse(
        auth_mode=settings.AUTH_MODE,
        oidc_configured=settings.is_oidc_auth and settings.OIDC_ISSUER_URL is not None,
        issuer_url=settings.OIDC_ISSUER_URL if settings.is_oidc_auth else None,
        client_id=settings.OIDC_CLIENT_ID if settings.is_oidc_auth else None,
        development_mode=settings.is_development_auth,
    )
