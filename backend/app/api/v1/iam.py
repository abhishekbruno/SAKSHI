"""Protected IAM and case-assignment API. No public officer registration exists."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_investigator
from app.db.session import get_db
from app.core.security import AuthenticatedInvestigator
from app.core.errors import ForbiddenException
from app.repositories.iam_repository import IAMRepository
from app.services.iam_service import OfficerService, CaseAssignmentService, is_admin_or_manager
from app.services.firebase_auth_service import FirebaseAdminProvisioner
from app.schemas.iam import (
    OfficerCreateRequest,
    OfficerResponse,
    OfficerUpdateRequest,
    OfficerTransferRequest,
    OfficerResetPasswordRequest,
    AssignmentCreateRequest,
    AssignmentResponse,
    EligibleOfficerResponse,
    ScopeCreateRequest,
    OrganizationResponse,
    JurisdictionResponse,
    StationResponse,
)
from app.models.organization import Organization, Jurisdiction, PoliceStation

router = APIRouter(tags=["Identity and Access Management"])


def _check_admin_or_manager(actor: AuthenticatedInvestigator):
    if not is_admin_or_manager(actor):
        raise ForbiddenException("Access denied: administrative or managerial authority required.")


def _check_system_admin(actor: AuthenticatedInvestigator):
    actor_roles = set(actor.roles or [actor.role])
    if not (actor_roles & {"ADMIN", "SYSTEM_ADMIN"}):
        raise ForbiddenException("Access denied: system administrator privileges required.")


# ═══════════════════════════════════════════════════════════════════════════
# Organization, Jurisdiction & Station Management
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/organizations", response_model=List[OrganizationResponse])
def list_organizations(
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    return IAMRepository(db).list_organizations()


@router.post("/organizations", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: ScopeCreateRequest,
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    _check_system_admin(actor)
    record = Organization(
        organization_id=payload.identifier,
        name=payload.name.strip(),
        code=payload.code.strip(),
        created_by=actor.subject_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/jurisdictions", response_model=List[JurisdictionResponse])
def list_jurisdictions(
    organization_id: Optional[str] = Query(None),
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    return IAMRepository(db).list_jurisdictions(organization_id=organization_id)


@router.post("/jurisdictions", response_model=JurisdictionResponse, status_code=status.HTTP_201_CREATED)
def create_jurisdiction(
    payload: ScopeCreateRequest,
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    _check_system_admin(actor)
    if not payload.organization_id or not IAMRepository(db).organization(payload.organization_id):
        raise ForbiddenException("Organization does not exist or was not specified.")
    record = Jurisdiction(
        jurisdiction_id=payload.identifier,
        organization_id=payload.organization_id,
        name=payload.name.strip(),
        code=payload.code.strip(),
        created_by=actor.subject_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/stations", response_model=List[StationResponse])
def list_stations(
    jurisdiction_id: Optional[str] = Query(None),
    organization_id: Optional[str] = Query(None),
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    return IAMRepository(db).list_stations(jurisdiction_id=jurisdiction_id, organization_id=organization_id)


@router.post("/stations", response_model=StationResponse, status_code=status.HTTP_201_CREATED)
def create_station(
    payload: ScopeCreateRequest,
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    _check_admin_or_manager(actor)
    repo = IAMRepository(db)
    if (
        not payload.organization_id
        or not payload.jurisdiction_id
        or not repo.organization(payload.organization_id)
        or not repo.jurisdiction(payload.jurisdiction_id)
    ):
        raise ForbiddenException("Invalid organization or jurisdiction specified.")

    actor_roles = set(actor.roles or [actor.role])
    if actor.station_jurisdiction not in {"ALL", payload.jurisdiction_id} and not (actor_roles & {"ADMIN", "SYSTEM_ADMIN"}):
        raise ForbiddenException("Cannot create station outside your authorized jurisdiction.")

    record = PoliceStation(
        station_id=payload.identifier,
        organization_id=payload.organization_id,
        jurisdiction_id=payload.jurisdiction_id,
        name=payload.name.strip(),
        code=payload.code.strip(),
        created_by=actor.subject_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


# ═══════════════════════════════════════════════════════════════════════════
# Officer Registry & Lifecycle
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/officers", response_model=OfficerResponse, status_code=status.HTTP_201_CREATED)
def create_officer(
    payload: OfficerCreateRequest,
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    _check_admin_or_manager(actor)
    return OfficerService(db).create(payload, actor, provisioner=FirebaseAdminProvisioner())


@router.get("/officers", response_model=List[OfficerResponse])
def list_officers(
    jurisdiction_id: Optional[str] = Query(None),
    station_id: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    active_only: bool = Query(False),
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    _check_admin_or_manager(actor)
    return OfficerService(db).list_officers(
        actor=actor,
        jurisdiction_id=jurisdiction_id,
        station_id=station_id,
        role=role,
        status=status_filter,
        active_only=active_only,
    )


@router.get("/officers/{officer_id}", response_model=OfficerResponse)
def get_officer(
    officer_id: str,
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    _check_admin_or_manager(actor)
    return OfficerService(db).get(officer_id, actor)


@router.patch("/officers/{officer_id}", response_model=OfficerResponse)
def update_officer(
    officer_id: str,
    payload: OfficerUpdateRequest,
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    _check_admin_or_manager(actor)
    return OfficerService(db).update(officer_id, payload, actor)


@router.post("/officers/{officer_id}/deactivate", response_model=OfficerResponse)
def deactivate_officer(
    officer_id: str,
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    return OfficerService(db).change_status(
        officer_id,
        "DEACTIVATED",
        actor,
        provisioner=FirebaseAdminProvisioner(),
    )


@router.post("/officers/{officer_id}/reactivate", response_model=OfficerResponse)
def reactivate_officer(
    officer_id: str,
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    return OfficerService(db).change_status(
        officer_id,
        "ACTIVE",
        actor,
        provisioner=FirebaseAdminProvisioner(),
    )


@router.post("/officers/{officer_id}/transfer", response_model=OfficerResponse)
def transfer_officer(
    officer_id: str,
    payload: OfficerTransferRequest,
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    return OfficerService(db).transfer(
        officer_id=officer_id,
        target_station_id=payload.target_station_id,
        target_jurisdiction_id=payload.target_jurisdiction_id,
        reason=payload.reason,
        actor=actor,
    )


@router.post("/officers/{officer_id}/reset-password", status_code=status.HTTP_200_OK)
def reset_officer_password(
    officer_id: str,
    payload: OfficerResetPasswordRequest,
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    OfficerService(db).reset_password(
        officer_id=officer_id,
        new_password=payload.new_password,
        actor=actor,
        provisioner=FirebaseAdminProvisioner(),
    )
    return {"message": "Officer credential reset successfully. Active sessions revoked."}


# ═══════════════════════════════════════════════════════════════════════════
# Case Allocation & Reassignment
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/cases/{case_id}/assignments", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
def assign_case(
    case_id: str,
    payload: AssignmentCreateRequest,
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    return CaseAssignmentService(db).assign(case_id, payload.officer_id, payload.reason, actor)


@router.get("/cases/{case_id}/assignments", response_model=List[AssignmentResponse])
def assignment_history(
    case_id: str,
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    # Existing policy governs visibility of the case before its history is exposed
    from app.services.case_service import CaseService
    CaseService(db).get_case(case_id, actor)
    return CaseAssignmentService(db).assignments(case_id)


@router.get("/cases/{case_id}/eligible-officers", response_model=List[EligibleOfficerResponse])
def eligible_officers_for_case(
    case_id: str,
    actor: AuthenticatedInvestigator = Depends(get_current_investigator),
    db: Session = Depends(get_db),
):
    from app.services.case_service import CaseService
    CaseService(db).get_case(case_id, actor)
    return CaseAssignmentService(db).eligible_officers(case_id, actor)
