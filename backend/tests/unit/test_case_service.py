"""
Unit tests for CaseService domain logic.
Tests source-defined functions (Create Case, Assign IO) and architectural invariants.
"""
import pytest
from app.services.case_service import CaseService
from app.schemas.case import CaseCreateRequest, FIRMetadata, CaseUpdateRequest
from app.core.errors import (
    CaseNotFoundException,
    InvalidCaseDataException,
    ForbiddenException
)
from app.core.security import AuthenticatedInvestigator


def test_create_case_success(db_session, mock_io1):
    service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Unnatural Death Investigation - Hotel Room 304",
        fir_metadata=FIRMetadata(
            fir_number="FIR-2026-0042",
            police_station="Central City Police Station",
            incident_date="2026-09-30T02:00:00Z",
            report_date="2026-09-30T04:30:00Z",
            jurisdiction_code="JUR-DEL-04"
        )
    )

    case = service.create_case(payload, mock_io1)

    assert case.case_id.startswith("SAKSHI-CASE-")
    assert case.title == "Unnatural Death Investigation - Hotel Room 304"
    assert case.assigned_io_id == mock_io1.investigator_id
    assert case.lifecycle_stage == "INITIALIZED"
    assert case.status == "ACTIVE"
    assert case.case_workspace.ready_for_ingestion is True
    assert case.case_workspace.case_id == case.case_id


def test_case_id_uniqueness(db_session, mock_io1):
    service = CaseService(db_session)
    id1, ws1 = service.generate_case_id()
    id2, ws2 = service.generate_case_id()

    assert id1 != id2
    assert ws1 != ws2
    assert id1.startswith("SAKSHI-CASE-")
    assert id2.startswith("SAKSHI-CASE-")


def test_duplicate_fir_rejection(db_session, mock_io1):
    service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="First Report",
        fir_metadata=FIRMetadata(
            fir_number="FIR-DUPLICATE-99",
            police_station="North Station"
        )
    )
    service.create_case(payload, mock_io1)

    # Attempting to create duplicate FIR at same station must be rejected
    with pytest.raises(InvalidCaseDataException) as exc:
        service.create_case(payload, mock_io1)
    assert "already been initiated" in str(exc.value.detail)


def test_unauthorized_creator_role_rejected(db_session):
    service = CaseService(db_session)
    unauthorized_user = AuthenticatedInvestigator(
        subject_id="CIVILIAN-001",
        role="CIVILIAN_OBSERVER",
        is_authenticated=True
    )
    payload = CaseCreateRequest(
        title="Unauthorized Case",
        fir_metadata=FIRMetadata(fir_number="FIR-001", police_station="HQ")
    )
    with pytest.raises(ForbiddenException):
        service.create_case(payload, unauthorized_user)


def test_case_id_stability_after_updates(db_session, mock_io1):
    service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Original Title",
        fir_metadata=FIRMetadata(fir_number="FIR-STABILITY-1", police_station="Central")
    )
    case = service.create_case(payload, mock_io1)
    original_case_id = case.case_id

    # Perform metadata update
    updated = service.update_case(
        original_case_id,
        CaseUpdateRequest(title="Updated Title After Scene Inspection"),
        mock_io1
    )

    # Invariant: Case ID must remain stable and identical
    assert updated.case_id == original_case_id
    assert updated.title == "Updated Title After Scene Inspection"


def test_assign_io_function(db_session, mock_io1, mock_supervisor):
    service = CaseService(db_session)
    case = service.create_case(
        CaseCreateRequest(
            title="Initial Matter",
            fir_metadata=FIRMetadata(fir_number="FIR-ASSIGN-01", police_station="Central")
        ),
        mock_io1
    )
    assert case.assigned_io_id == mock_io1.investigator_id

    # Reassigning to another officer by supervisor
    reassigned = service.assign_investigator(
        case.case_id,
        "IO-9912-VERMA",
        mock_supervisor
    )
    assert reassigned.assigned_io_id == "IO-9912-VERMA"


def test_lifecycle_stage_transition(db_session, mock_io1):
    service = CaseService(db_session)
    case = service.create_case(
        CaseCreateRequest(
            title="Lifecycle Test",
            fir_metadata=FIRMetadata(fir_number="FIR-STAGE-01", police_station="Central")
        ),
        mock_io1
    )
    assert case.lifecycle_stage == "INITIALIZED"

    # Stage Engine updates stage
    updated = service.update_stage(case.case_id, "EVIDENCE_INGESTION", mock_io1)
    assert updated.lifecycle_stage == "EVIDENCE_INGESTION"


def test_phase2_integration_contract(db_session, mock_io1):
    service = CaseService(db_session)
    case = service.create_case(
        CaseCreateRequest(
            title="Phase 2 Handoff Test",
            fir_metadata=FIRMetadata(fir_number="FIR-P2-01", police_station="Central")
        ),
        mock_io1
    )
    contract = service.get_phase2_contract(case.case_id, mock_io1)

    assert contract.case_id == case.case_id
    assert contract.authorized_io_id == mock_io1.investigator_id
    assert contract.lifecycle_stage == "INITIALIZED"
    assert contract.case_workspace_boundary["ingestion_gate_open"] is True
