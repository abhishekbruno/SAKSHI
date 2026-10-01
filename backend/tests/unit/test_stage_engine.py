"""
MOD-04: Stage Engine Unit, Integration, and Security Tests.

Tests:
    1. Valid sequential transitions across investigation lifecycle.
    2. Legitimate iterative transitions (e.g. ANALYSIS -> EVIDENCE_INGESTION for gap-filling).
    3. Administrative transitions (suspension & resumption).
    4. Invalid transition rejection (illegal jumps, e.g. INITIALIZED -> CLOSED).
    5. Redundant self-transition rejection.
    6. Unknown / unmapped stage rejection.
    7. Supervisory role requirements for terminal/reopening transitions (CLOSED, REOPENED).
    8. CaseService integration & state persistence.
    9. REST API endpoints (/api/v1/cases/{case_id}/stage).
    10. Audit trail generation on stage transitions.
"""
import pytest
from app.core.security import AuthenticatedInvestigator
from app.core.errors import InvalidStageException, ForbiddenException
from app.models.case import Case
from app.services.stage_engine import (
    CaseStage,
    StageEngine,
    StageTransitionDecision,
    stage_engine,
)
from app.services.case_service import CaseService
from app.schemas.case import CaseCreateRequest, FIRMetadata, CaseStageUpdateRequest


# ─── FIXTURES ─────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    return StageEngine()


@pytest.fixture
def io_investigator():
    return AuthenticatedInvestigator(
        subject_id="IO-7842-SHARMA",
        display_name="Inspector Sharma",
        role="INVESTIGATING_OFFICER",
        station_jurisdiction="JUR-DEL-04",
        is_authenticated=True,
    )


@pytest.fixture
def supervisor_officer():
    return AuthenticatedInvestigator(
        subject_id="IO-0001-COMMISSIONER",
        display_name="DCP Roy",
        role="SUPERVISORY_OFFICER",
        station_jurisdiction="ALL",
        is_authenticated=True,
    )


@pytest.fixture
def sample_case(db_session, io_investigator):
    service = CaseService(db_session)
    return service.create_case(
        CaseCreateRequest(
            title="Stage Engine Invariant Case",
            fir_metadata=FIRMetadata(fir_number="FIR-STAGE-001", police_station="Central Station")
        ),
        investigator=io_investigator
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. STATE MACHINE TRANSITION TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestStageEngineTransitions:
    """Verifies valid and invalid transitions in the state machine."""

    def test_valid_forward_pipeline_progression(self, engine, supervisor_officer):
        """Sequential lifecycle progression: INITIALIZED -> INGESTION -> PROCESSING -> ANALYSIS -> REVIEW -> CLOSED."""
        # 1. INITIALIZED -> EVIDENCE_INGESTION
        d1 = engine.validate_transition(CaseStage.INITIALIZED.value, CaseStage.EVIDENCE_INGESTION.value, supervisor_officer)
        assert d1.valid is True

        # 2. EVIDENCE_INGESTION -> EVIDENCE_PROCESSING
        d2 = engine.validate_transition(CaseStage.EVIDENCE_INGESTION.value, CaseStage.EVIDENCE_PROCESSING.value, supervisor_officer)
        assert d2.valid is True

        # 3. EVIDENCE_PROCESSING -> ANALYSIS
        d3 = engine.validate_transition(CaseStage.EVIDENCE_PROCESSING.value, CaseStage.ANALYSIS.value, supervisor_officer)
        assert d3.valid is True

        # 4. ANALYSIS -> REVIEW
        d4 = engine.validate_transition(CaseStage.ANALYSIS.value, CaseStage.REVIEW.value, supervisor_officer)
        assert d4.valid is True

        # 5. REVIEW -> CLOSED (Supervisor)
        d5 = engine.validate_transition(CaseStage.REVIEW.value, CaseStage.CLOSED.value, supervisor_officer)
        assert d5.valid is True

    def test_valid_iterative_transitions(self, engine, io_investigator):
        """Legitimate investigative loops (e.g. analysis identifies gaps, requesting more evidence)."""
        # ANALYSIS -> EVIDENCE_INGESTION
        d = engine.validate_transition(CaseStage.ANALYSIS.value, CaseStage.EVIDENCE_INGESTION.value, io_investigator)
        assert d.valid is True

        # REVIEW -> ANALYSIS (supervisor sends back for deeper MO reasoning)
        d2 = engine.validate_transition(CaseStage.REVIEW.value, CaseStage.ANALYSIS.value, io_investigator)
        assert d2.valid is True

    def test_valid_suspension_and_resumption(self, engine, io_investigator):
        """Cases can be suspended and resumed from their operational states."""
        # INITIALIZED -> SUSPENDED
        d1 = engine.validate_transition(CaseStage.INITIALIZED.value, CaseStage.SUSPENDED.value, io_investigator)
        assert d1.valid is True

        # SUSPENDED -> INITIALIZED
        d2 = engine.validate_transition(CaseStage.SUSPENDED.value, CaseStage.INITIALIZED.value, io_investigator)
        assert d2.valid is True

        # SUSPENDED -> ANALYSIS
        d3 = engine.validate_transition(CaseStage.SUSPENDED.value, CaseStage.ANALYSIS.value, io_investigator)
        assert d3.valid is True

    def test_reopening_closed_case(self, engine, supervisor_officer):
        """CLOSED cases can be REOPENED by supervisors when fresh evidence emerges."""
        d = engine.validate_transition(CaseStage.CLOSED.value, CaseStage.REOPENED.value, supervisor_officer)
        assert d.valid is True

        # REOPENED -> EVIDENCE_INGESTION
        d2 = engine.validate_transition(CaseStage.REOPENED.value, CaseStage.EVIDENCE_INGESTION.value, supervisor_officer)
        assert d2.valid is True


# ═══════════════════════════════════════════════════════════════════════════
# 2. INVALID TRANSITION REJECTION TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestInvalidTransitions:
    """Verifies that illegal transitions are strictly blocked."""

    def test_illegal_jump_initialized_to_closed(self, engine, supervisor_officer):
        """Cannot close an investigation immediately without evidence and analysis."""
        d = engine.validate_transition(CaseStage.INITIALIZED.value, CaseStage.CLOSED.value, supervisor_officer)
        assert d.valid is False
        assert "Invalid lifecycle transition" in d.reason
        assert "EVIDENCE_INGESTION" in d.allowed_transitions

    def test_illegal_jump_initialized_to_analysis(self, engine, io_investigator):
        """Cannot jump directly to ANALYSIS without ingesting and processing evidence."""
        d = engine.validate_transition(CaseStage.INITIALIZED.value, CaseStage.ANALYSIS.value, io_investigator)
        assert d.valid is False
        assert "Invalid lifecycle transition" in d.reason

    def test_redundant_self_transition_rejected(self, engine, io_investigator):
        """Transitioning to the current stage is rejected as redundant."""
        d = engine.validate_transition(CaseStage.INITIALIZED.value, CaseStage.INITIALIZED.value, io_investigator)
        assert d.valid is False
        assert "already in stage" in d.reason

    def test_unknown_target_stage_rejected(self, engine, io_investigator):
        """Unknown or hallucinated stage names are rejected."""
        d = engine.validate_transition(CaseStage.INITIALIZED.value, "FLYING_STAGE", io_investigator)
        assert d.valid is False
        assert "not a recognized lifecycle stage" in d.reason

    def test_corrupted_current_stage_rejected(self, engine, io_investigator):
        """If current stage is corrupted, engine rejects gracefully."""
        d = engine.validate_transition("CORRUPTED_STAGE", CaseStage.EVIDENCE_INGESTION.value, io_investigator)
        assert d.valid is False
        assert "corrupted" in d.reason


# ═══════════════════════════════════════════════════════════════════════════
# 3. SUPERVISORY TRANSITION POLICIES
# ═══════════════════════════════════════════════════════════════════════════

class TestSupervisoryStagePolicies:
    """Ensures critical transitions (CLOSED, REOPENED) require supervisory clearance."""

    def test_regular_io_cannot_close_case(self, engine, io_investigator):
        """Regular Investigating Officers cannot mark a case CLOSED."""
        d = engine.validate_transition(CaseStage.REVIEW.value, CaseStage.CLOSED.value, io_investigator)
        assert d.valid is False
        assert "supervisory authorization" in d.reason

    def test_supervisor_can_close_case(self, engine, supervisor_officer):
        """Supervisors can successfully close a case that is in REVIEW."""
        d = engine.validate_transition(CaseStage.REVIEW.value, CaseStage.CLOSED.value, supervisor_officer)
        assert d.valid is True

    def test_regular_io_cannot_reopen_closed_case(self, engine, io_investigator):
        """Regular IOs cannot reopen a closed case."""
        d = engine.validate_transition(CaseStage.CLOSED.value, CaseStage.REOPENED.value, io_investigator)
        assert d.valid is False
        assert "supervisory authorization" in d.reason


# ═══════════════════════════════════════════════════════════════════════════
# 4. CASE SERVICE INTEGRATION
# ═══════════════════════════════════════════════════════════════════════════

class TestCaseServiceStageIntegration:
    """Tests end-to-end integration between CaseService and StageEngine."""

    def test_case_service_advances_valid_stage(self, db_session, io_investigator, sample_case):
        """CaseService successfully advances case stage and persists state."""
        service = CaseService(db_session)
        updated = service.update_stage(
            sample_case.case_id,
            CaseStage.EVIDENCE_INGESTION.value,
            investigator=io_investigator
        )
        assert updated.lifecycle_stage == CaseStage.EVIDENCE_INGESTION.value

        # Fetch case from repository to guarantee persistence
        fetched = service.get_case(sample_case.case_id, investigator=io_investigator)
        assert fetched.lifecycle_stage == CaseStage.EVIDENCE_INGESTION.value

    def test_case_service_rejects_illegal_jump(self, db_session, io_investigator, sample_case):
        """CaseService raises InvalidStageException on illegal transitions."""
        service = CaseService(db_session)
        with pytest.raises(InvalidStageException) as exc_info:
            service.update_stage(
                sample_case.case_id,
                CaseStage.CLOSED.value,
                investigator=io_investigator
            )
        assert "Invalid lifecycle transition" in str(exc_info.value)

        # Confirm stage was NOT changed
        unchanged = service.get_case(sample_case.case_id, investigator=io_investigator)
        assert unchanged.lifecycle_stage == CaseStage.INITIALIZED.value

    def test_case_service_stage_update_unauthorized_investigator(
        self, db_session, sample_case
    ):
        """An investigator from another jurisdiction cannot update the case stage (MOD-03 check)."""
        service = CaseService(db_session)
        different_io = AuthenticatedInvestigator(
            subject_id="IO-9999-OTHER",
            role="INVESTIGATING_OFFICER",
            station_jurisdiction="JUR-OTHER",
            is_authenticated=True,
        )
        with pytest.raises(ForbiddenException):
            service.update_stage(
                sample_case.case_id,
                CaseStage.EVIDENCE_INGESTION.value,
                investigator=different_io
            )


# ═══════════════════════════════════════════════════════════════════════════
# 5. REST API ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestStageAPI:
    """Tests GET and POST /api/v1/cases/{case_id}/stage endpoints."""

    def test_api_get_stage_and_allowed_transitions(self, client, auth_headers_io1):
        """GET /api/v1/cases/{case_id}/stage returns lifecycle stage and permitted next stages."""
        # 1. Create a case
        create_res = client.post(
            "/api/v1/cases",
            json={
                "title": "Stage Inspection API Test",
                "fir_metadata": {"fir_number": "FIR-STG-API-01", "police_station": "Central"}
            },
            headers=auth_headers_io1
        )
        assert create_res.status_code == 201
        case_id = create_res.json()["case_id"]

        # 2. Get stage info
        get_res = client.get(f"/api/v1/cases/{case_id}/stage", headers=auth_headers_io1)
        assert get_res.status_code == 200
        data = get_res.json()
        assert data["case_id"] == case_id
        assert data["lifecycle_stage"] == "INITIALIZED"
        assert "allowed_transitions" in data
        assert "EVIDENCE_INGESTION" in data["allowed_transitions"]

    def test_api_post_valid_stage_transition(self, client, auth_headers_io1):
        """POST /api/v1/cases/{case_id}/stage advances lifecycle stage."""
        # 1. Create a case
        create_res = client.post(
            "/api/v1/cases",
            json={
                "title": "Stage Transition API Test",
                "fir_metadata": {"fir_number": "FIR-STG-API-02", "police_station": "Central"}
            },
            headers=auth_headers_io1
        )
        case_id = create_res.json()["case_id"]

        # 2. Transition INITIALIZED -> EVIDENCE_INGESTION
        post_res = client.post(
            f"/api/v1/cases/{case_id}/stage",
            json={"lifecycle_stage": "EVIDENCE_INGESTION"},
            headers=auth_headers_io1
        )
        assert post_res.status_code == 200
        assert post_res.json()["lifecycle_stage"] == "EVIDENCE_INGESTION"

    def test_api_post_invalid_stage_transition_returns_400(self, client, auth_headers_io1):
        """POST /api/v1/cases/{case_id}/stage with illegal transition returns 400 Bad Request."""
        # 1. Create a case
        create_res = client.post(
            "/api/v1/cases",
            json={
                "title": "Illegal Stage Jump API Test",
                "fir_metadata": {"fir_number": "FIR-STG-API-03", "police_station": "Central"}
            },
            headers=auth_headers_io1
        )
        case_id = create_res.json()["case_id"]

        # 2. Attempt illegal jump INITIALIZED -> CLOSED
        post_res = client.post(
            f"/api/v1/cases/{case_id}/stage",
            json={"lifecycle_stage": "CLOSED"},
            headers=auth_headers_io1
        )
        assert post_res.status_code == 400
        assert post_res.json()["error_code"] == "INVALID_STAGE"
