"""
Core domain service for SAKSHI Case Management Service (MOD-01).
Implements Create Case, Assign IO, Case ID generation, Workspace provisioning, and lifecycle management.
"""
import secrets
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy.orm import Session

from app.models.case import Case
from app.repositories.case_repository import CaseRepository
from app.core.security import AuthenticatedInvestigator
from app.core.errors import (
    CaseNotFoundException,
    InvalidCaseDataException,
    InvalidInvestigatorException,
    InvalidStageException
)
from app.core.logging import log_event
from app.services.auth_service import IAuthorizationService, authorization_service
from app.services.audit_integration import AuditIntegrationService
from app.schemas.case import (
    CaseCreateRequest,
    CaseUpdateRequest,
    CaseResponse,
    CaseWorkspaceRepresentation,
    Phase2IntegrationContract
)


class CaseService:
    def __init__(
        self,
        db: Session,
        authz_service: IAuthorizationService = authorization_service
    ):
        self.repo = CaseRepository(db)
        self.authz = authz_service

    @staticmethod
    def generate_case_id() -> Tuple[str, str]:
        """
        Generates a collision-resistant, canonical Case ID and Workspace ID.
        Strategy: Uses cryptographically secure random entropy (secrets.token_hex).
        Does not encode personal identifiers or sensitive investigative facts into the ID.
        Format: SAKSHI-CASE-{YYYY}-{HEX8}
        """
        year = datetime.now(timezone.utc).year
        suffix = secrets.token_hex(4).upper()
        case_id = f"SAKSHI-CASE-{year}-{suffix}"
        workspace_id = f"WS-{suffix}"
        return case_id, workspace_id

    @staticmethod
    def to_case_response(case: Case) -> CaseResponse:
        """Converts an internal Case ORM entity into a clean public API contract."""
        workspace_id = f"WS-{case.case_id.split('-')[-1]}" if "-" in case.case_id else f"WS-{case.id[:8]}"
        workspace = CaseWorkspaceRepresentation(
            workspace_id=workspace_id,
            case_id=case.case_id,
            workspace_path=case.case_workspace_path,
            ready_for_ingestion=True
        )
        return CaseResponse(
            case_id=case.case_id,
            title=case.title,
            fir_metadata=case.fir_metadata,
            assigned_io_id=case.assigned_io_id,
            lifecycle_stage=case.lifecycle_stage,
            status=case.status,
            case_workspace=workspace,
            created_at=case.created_at,
            updated_at=case.updated_at
        )

    def create_case(
        self,
        payload: CaseCreateRequest,
        investigator: AuthenticatedInvestigator
    ) -> CaseResponse:
        """
        Source-defined function: CREATE CASE / ASSIGN IO.
        Establishes the investigation workspace and anchors the Case ID.
        """
        log_event(
            event_type="CASE_CREATE_REQUEST",
            message=f"Case creation initiated by investigator '{investigator.investigator_id}'",
            investigator_id=investigator.investigator_id
        )

        # 1. Authorization check
        self.authz.check_can_create_case(investigator, payload.fir_metadata.police_station)

        # 2. Duplicate detection
        existing = self.repo.find_existing_by_fir(
            fir_number=payload.fir_metadata.fir_number,
            police_station=payload.fir_metadata.police_station
        )
        if existing:
            raise InvalidCaseDataException(
                f"A case for FIR '{payload.fir_metadata.fir_number}' at station "
                f"'{payload.fir_metadata.police_station}' has already been initiated (Case ID: {existing.case_id})."
            )

        # 3. Determine and authorize assigned IO
        target_io = payload.assigned_io_id or investigator.investigator_id
        self.authz.check_can_assign_io(investigator, target_io)

        # 4. Generate unique Case ID and Workspace locator
        case_id, workspace_id = self.generate_case_id()
        workspace_path = f"/sakshi/workspaces/{case_id}"

        # 5. Build Case entity
        case_entity = Case(
            case_id=case_id,
            title=payload.title,
            fir_metadata=payload.fir_metadata.model_dump(),
            assigned_io_id=target_io,
            lifecycle_stage="INITIALIZED",
            status="ACTIVE",
            case_workspace_path=workspace_path,
            created_by=investigator.investigator_id
        )

        # 6. Persist transactionally
        created_case = self.repo.create(case_entity)

        # 7. Audit and log event
        AuditIntegrationService.record_event(
            action="CASE_CREATED",
            investigator_id=investigator.investigator_id,
            case_id=created_case.case_id,
            details={
                "fir_number": payload.fir_metadata.fir_number,
                "assigned_io_id": target_io,
                "workspace_id": workspace_id
            }
        )

        return self.to_case_response(created_case)

    def get_case(self, case_id: str, investigator: AuthenticatedInvestigator) -> CaseResponse:
        """Retrieve case record by authoritative Case ID with authorization check."""
        case = self.repo.get_by_case_id(case_id)
        if not case:
            log_event(
                event_type="CASE_NOT_FOUND",
                message=f"Case '{case_id}' lookup failed",
                case_id=case_id,
                investigator_id=investigator.investigator_id
            )
            raise CaseNotFoundException(case_id)

        self.authz.check_can_read_case(investigator, case)
        return self.to_case_response(case)

    def list_cases(
        self,
        investigator: AuthenticatedInvestigator,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[CaseResponse], int]:
        """List cases accessible to the authenticated investigator."""
        # MOD-03: Determine case visibility filter from authorization policy engine
        if hasattr(self.authz, "get_case_list_filter"):
            assigned_filter = self.authz.get_case_list_filter(investigator)
        elif investigator.role not in {"SUPERVISORY_OFFICER", "STATION_HEAD", "ADMIN"}:
            assigned_filter = investigator.investigator_id

        cases = self.repo.list_cases(assigned_io_id=assigned_filter, skip=skip, limit=limit)
        total = self.repo.count_cases(assigned_io_id=assigned_filter)
        return [self.to_case_response(c) for c in cases], total

    def update_case(
        self,
        case_id: str,
        payload: CaseUpdateRequest,
        investigator: AuthenticatedInvestigator
    ) -> CaseResponse:
        """Update permitted metadata fields. Ensures Case ID remains immutable."""
        case = self.repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        self.authz.check_can_modify_case(investigator, case)

        if payload.title is not None:
            case.title = payload.title
        if payload.status is not None:
            case.status = payload.status
        if payload.fir_metadata is not None:
            case.fir_metadata = payload.fir_metadata.model_dump()

        updated_case = self.repo.update(case)

        AuditIntegrationService.record_event(
            action="CASE_UPDATED",
            investigator_id=investigator.investigator_id,
            case_id=case_id,
            details={"updated_fields": list(payload.model_dump(exclude_unset=True).keys())}
        )

        return self.to_case_response(updated_case)

    def assign_investigator(
        self,
        case_id: str,
        target_io_id: str,
        investigator: AuthenticatedInvestigator
    ) -> CaseResponse:
        """Source-defined function: ASSIGN IO."""
        if not target_io_id.strip():
            raise InvalidInvestigatorException("Target investigator ID cannot be empty.")

        case = self.repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        self.authz.check_can_assign_io(investigator, target_io_id, case)

        previous_io = case.assigned_io_id
        case.assigned_io_id = target_io_id
        updated_case = self.repo.update(case)

        AuditIntegrationService.record_event(
            action="CASE_ASSIGNMENT",
            investigator_id=investigator.investigator_id,
            case_id=case_id,
            details={"previous_io": previous_io, "new_io": target_io_id}
        )

        return self.to_case_response(updated_case)

    def update_stage(
        self,
        case_id: str,
        new_stage: str,
        investigator: AuthenticatedInvestigator
    ) -> CaseResponse:
        """Integration hook for Stage Engine to govern case lifecycle transitions."""
        if not new_stage.strip():
            raise InvalidStageException("Stage name cannot be empty.")

        case = self.repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        # 1. MOD-03: Authorization check
        self.authz.check_can_modify_case(investigator, case)

        # 2. MOD-04: Stage Engine lifecycle transition validation
        from app.services.stage_engine import stage_engine
        decision = stage_engine.validate_transition(
            current_stage=case.lifecycle_stage,
            target_stage=new_stage,
            investigator=investigator
        )
        if not decision.valid:
            raise InvalidStageException(decision.reason)

        previous_stage = case.lifecycle_stage
        case.lifecycle_stage = decision.target_stage
        updated = self.repo.update(case)

        AuditIntegrationService.record_event(
            action="STAGE_TRANSITION",
            investigator_id=investigator.investigator_id,
            case_id=case_id,
            details={
                "previous_stage": previous_stage,
                "new_stage": decision.target_stage,
                "reason": decision.reason
            }
        )

        return self.to_case_response(updated)

    def get_phase2_contract(
        self,
        case_id: str,
        investigator: AuthenticatedInvestigator
    ) -> Phase2IntegrationContract:
        """Exports the formal Phase 1 Output Contract for Phase 2 Evidence Ingestion."""
        case = self.repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        self.authz.check_can_read_case(investigator, case)

        return Phase2IntegrationContract(
            case_id=case.case_id,
            case_workspace_boundary={
                "workspace_path": case.case_workspace_path,
                "status": case.status,
                "ingestion_gate_open": True
            },
            authorized_io_id=case.assigned_io_id,
            lifecycle_stage=case.lifecycle_stage,
            provenance={
                "fir_number": case.fir_metadata.get("fir_number"),
                "police_station": case.fir_metadata.get("police_station"),
                "created_at": case.created_at.isoformat()
            }
        )
