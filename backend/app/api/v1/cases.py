"""
Case Management REST API Endpoints (MOD-01).
Version: v1 (/api/v1/cases)
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_current_investigator, get_case_service
from app.core.security import AuthenticatedInvestigator
from app.services.case_service import CaseService
from app.schemas.case import (
    CaseCreateRequest,
    CaseUpdateRequest,
    CaseAssignIORequest,
    CaseStageUpdateRequest,
    CaseResponse,
    CaseListResponse,
    Phase2IntegrationContract
)

router = APIRouter(prefix="/cases", tags=["Case Management"])


@router.post(
    "",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new investigation case"
)
def create_case(
    payload: CaseCreateRequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> CaseResponse:
    """
    Source-defined function: CREATE CASE / ASSIGN IO.
    Creates an investigation record, generates unique Case ID, binds IO, and initializes workspace.
    """
    return service.create_case(payload=payload, investigator=investigator)


@router.get(
    "",
    response_model=CaseListResponse,
    summary="List cases accessible to authorized investigator"
)
def list_cases(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> CaseListResponse:
    """Returns cases assigned to or accessible by the authenticated investigator."""
    cases, total = service.list_cases(investigator=investigator, skip=skip, limit=limit)
    return CaseListResponse(total=total, cases=cases)


@router.get(
    "/{case_id}",
    response_model=CaseResponse,
    summary="Retrieve case by authoritative Case ID"
)
def get_case(
    case_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> CaseResponse:
    """Retrieves full case details and workspace representation."""
    return service.get_case(case_id=case_id, investigator=investigator)


@router.patch(
    "/{case_id}",
    response_model=CaseResponse,
    summary="Update permitted case metadata"
)
def update_case(
    case_id: str,
    payload: CaseUpdateRequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> CaseResponse:
    """Updates permitted case fields. The Case ID is immutable and remains constant."""
    return service.update_case(case_id=case_id, payload=payload, investigator=investigator)


@router.post(
    "/{case_id}/assign-investigator",
    response_model=CaseResponse,
    summary="Associate or reassign an Investigating Officer"
)
def assign_investigator(
    case_id: str,
    payload: CaseAssignIORequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> CaseResponse:
    """Source-defined function: ASSIGN IO."""
    return service.assign_investigator(
        case_id=case_id,
        target_io_id=payload.assigned_io_id,
        investigator=investigator
    )


@router.get(
    "/{case_id}/stage",
    summary="Retrieve current case lifecycle state"
)
def get_case_stage(
    case_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
):
    """Returns lifecycle state managed by the Stage Engine."""
    from app.services.stage_engine import stage_engine
    case = service.get_case(case_id=case_id, investigator=investigator)
    return {
        "case_id": case.case_id,
        "lifecycle_stage": case.lifecycle_stage,
        "status": case.status,
        "allowed_transitions": stage_engine.get_allowed_transitions(case.lifecycle_stage)
    }


@router.post(
    "/{case_id}/stage",
    response_model=CaseResponse,
    summary="Update case lifecycle stage (Stage Engine hook)"
)
def update_case_stage(
    case_id: str,
    payload: CaseStageUpdateRequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> CaseResponse:
    """Stage Engine integration point to advance or adjust investigation state."""
    return service.update_stage(
        case_id=case_id,
        new_stage=payload.lifecycle_stage,
        investigator=investigator
    )


@router.get(
    "/{case_id}/phase2-contract",
    response_model=Phase2IntegrationContract,
    summary="Export formal Phase 1 Output Contract for Phase 2 Evidence Ingestion"
)
def get_phase2_contract(
    case_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> Phase2IntegrationContract:
    """Produces the validated handoff contract required by Phase 2 Evidence Ingestion."""
    return service.get_phase2_contract(case_id=case_id, investigator=investigator)
