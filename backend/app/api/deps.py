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
    db: Session = Depends(get_db),
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
        dev_jurisdiction=x_investigator_jurisdiction,
        db=db,
    )


def get_case_service(db: Session = Depends(get_db)) -> CaseService:
    """Dependency injecting a CaseService instance wired with the current DB session."""
    return CaseService(db)


def get_evidence_intake_service(db: Session = Depends(get_db)):
    """Dependency injecting an EvidenceIntakeService instance wired with current DB session."""
    from app.services.evidence_intake_service import EvidenceIntakeService
    return EvidenceIntakeService(db)


def get_mime_validation_service(db: Session = Depends(get_db)):
    """Dependency injecting a MimeValidationService instance wired with current DB session."""
    from app.services.mime_validation_service import MimeValidationService
    return MimeValidationService(db)


def get_antivirus_scan_service(db: Session = Depends(get_db)):
    """Dependency injecting an AntivirusScanService instance wired with current DB session."""
    from app.services.antivirus_scan_service import AntivirusScanService
    return AntivirusScanService(db)


def get_worm_commit_service(db: Session = Depends(get_db)):
    """Dependency injecting a WORMCommitService instance wired with current DB session."""
    from app.services.worm_commit_service import WORMCommitService
    return WORMCommitService(db)


def get_evidence_pipeline_orchestrator(db: Session = Depends(get_db)):
    """Dependency injecting the MOD-05 through MOD-08 composite orchestrator."""
    from app.services.evidence_pipeline_orchestrator import EvidencePipelineOrchestrator
    return EvidencePipelineOrchestrator(db)


def get_integrity_service(db: Session = Depends(get_db)):
    """Dependency injecting an IntegrityService instance wired with current DB session (MOD-09)."""
    from app.services.integrity_service import IntegrityService
    return IntegrityService(db)


def get_object_lock_service(db: Session = Depends(get_db)):
    """Dependency injecting an ObjectLockService instance wired with the current DB session (MOD-10)."""
    from app.services.object_lock_service import ObjectLockService
    return ObjectLockService(db)


def get_encryption_service(db: Session = Depends(get_db)):
    """Dependency injecting an EncryptionService instance wired with the current DB session (MOD-11)."""
    from app.services.encryption_service import EncryptionService
    return EncryptionService(db)


def get_authorization_engine():
    """Dependency injecting the centralized MOD-03 PolicyEngine."""
    from app.services.authorization_service import policy_engine
    return policy_engine


def get_rag_indexing_service(db: Session = Depends(get_db)):
    """Dependency injecting RAGIndexingService wired with the current DB session."""
    from app.services.rag_indexing_service import RAGIndexingService
    return RAGIndexingService(db)


def get_rag_retrieval_service(db: Session = Depends(get_db)):
    """Dependency injecting the Phase 4 retrieval service with the request DB session."""
    from app.services.rag_retrieval_service import RAGRetrievalService
    return RAGRetrievalService(db)


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
    return _dependency


def get_evidence_extraction_service(db: Session = Depends(get_db)):
    """Dependency injecting EvidenceExtractionService wired with current DB session."""
    from app.services.evidence_extraction_service import EvidenceExtractionService
    return EvidenceExtractionService(db)


def get_evidence_intelligence_service(db: Session = Depends(get_db)):
    """Dependency injecting EvidenceIntelligenceService wired with current DB session (Phase F.1)."""
    from app.services.evidence_intelligence_service import EvidenceIntelligenceService
    return EvidenceIntelligenceService(db)


