"""
FastAPI dependency injection utilities for SAKSHI Investigation Platform.
MOD-02: Extracts authenticated investigator context via the Identity/OIDC boundary.

Authentication flow:
    HTTP Request → Authorization: Bearer <token> → Authentication dependency
    → Token validation → Identity extraction → AuthenticatedInvestigator → Route handler

CRITICAL:
    - Authentication is centralized here — do NOT put auth logic in individual routes.
    - Client-supplied X-Investigator-Id is ONLY accepted in development mode.
    - In OIDC mode, identity comes exclusively from the validated JWT token.
"""
from typing import Optional
from fastapi import Depends, Header
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import AuthenticatedInvestigator
from app.services.auth_service import auth_service, IAuthenticationService
from app.services.case_service import CaseService


def get_current_investigator(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_investigator_id: Optional[str] = Header(None, alias="X-Investigator-Id"),
    x_investigator_role: Optional[str] = Header(None, alias="X-Investigator-Role"),
    x_investigator_jurisdiction: Optional[str] = Header(None, alias="X-Investigator-Jurisdiction"),
) -> AuthenticatedInvestigator:
    """
    Central authentication dependency.

    Delegates to the configured IAuthenticationService implementation:
        - In OIDC mode: validates the Bearer JWT token, ignores X-Investigator-* headers.
        - In development mode: accepts Bearer token or X-Investigator-* headers for mock identity.

    Returns an AuthenticatedInvestigator whose subject_id (aliased as investigator_id)
    is the authoritative identity for all downstream operations.
    """
    return auth_service.authenticate_request(
        auth_header=authorization,
        dev_investigator_id=x_investigator_id,
        dev_role=x_investigator_role,
        dev_jurisdiction=x_investigator_jurisdiction
    )


def get_case_service(db: Session = Depends(get_db)) -> CaseService:
    """Dependency injecting a CaseService instance wired with the current DB session."""
    return CaseService(db)


def get_authorization_engine():
    """Dependency injecting the centralized MOD-03 PolicyEngine."""
    from app.services.authorization_service import policy_engine
    return policy_engine


def require_permission(required_permission: str):
    """
    FastAPI dependency factory enforcing RBAC permission for the authenticated investigator.

    Usage:
        @router.get("", dependencies=[Depends(require_permission(Permission.CASE_READ))])
    """
    def _dependency(
        investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    ) -> AuthenticatedInvestigator:
        from app.services.authorization_service import policy_engine
        from app.core.errors import ForbiddenException

        roles = investigator.roles if investigator.roles else [investigator.role]
        effective_perms = set()
        for r in roles:
            effective_perms.update(policy_engine.get_permissions_for_role(r))

        if required_permission not in effective_perms:
            raise ForbiddenException(f"Access denied: missing required permission '{required_permission}'.")
        return investigator

    return _dependency
