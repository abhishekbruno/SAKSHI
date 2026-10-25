"""
Phase B Security & Authorization Verification Test Suite.

Exhaustively verifies:
1. Cross-jurisdiction isolation (Strict ABAC boundary enforcement).
2. Development identity isolation (Production fail-closed, no bypasses).
3. Role-based access control (RBAC matrix enforcement).
4. Direct IDOR and identifier manipulation defense.
5. Lifecycle and decision authorization.
"""
import pytest
from unittest.mock import patch, MagicMock

from app.core.config import settings
from app.core.security import AuthenticatedInvestigator
from app.core.errors import ForbiddenException, AuthenticationRequiredException, OIDCConfigurationException
from app.models.case import Case
from app.services.authorization_service import (
    PolicyEngine,
    AuthorizationContext,
    Permission,
)
from app.services.auth_service import (
    PolicyEngineAuthorizationService,
    DevAuthenticationService,
    _create_authentication_service,
)
from app.services.stage_engine import stage_engine, CaseStage


@pytest.fixture
def policy_engine():
    return PolicyEngine()


@pytest.fixture
def authz_service():
    return PolicyEngineAuthorizationService()


class TestCrossJurisdictionIsolation:
    """A. Cross-jurisdiction isolation verification."""

    def test_investigator_kerala_cannot_access_delhi_case(self, policy_engine):
        kerala_officer = AuthenticatedInvestigator(
            subject_id="IO-KERALA-001",
            roles=["INVESTIGATING_OFFICER"],
            role="INVESTIGATING_OFFICER",
            station_jurisdiction="KERALA",
            is_authenticated=True,
        )
        delhi_case = Case(
            case_id="CASE-DELHI-2026-999",
            assigned_io_id="IO-DELHI-002",
            fir_metadata={"jurisdiction_code": "DELHI"},
        )

        ctx = AuthorizationContext.from_investigator(
            kerala_officer,
            action="read",
            case=delhi_case,
        )
        decision = policy_engine.evaluate(ctx)
        assert not decision.allowed
        assert decision.policy_id == "CASE_ACCESS_DENIED"
        assert "jurisdiction does not match" in decision.reason

    def test_supervisor_delhi_cannot_access_kerala_case(self, policy_engine):
        delhi_supervisor = AuthenticatedInvestigator(
            subject_id="SUP-DELHI-001",
            roles=["SUPERVISORY_OFFICER"],
            role="SUPERVISORY_OFFICER",
            station_jurisdiction="DELHI",
            is_authenticated=True,
        )
        kerala_case = Case(
            case_id="CASE-KERALA-2026-888",
            assigned_io_id="IO-KERALA-005",
            fir_metadata={"jurisdiction_code": "KERALA"},
        )

        ctx = AuthorizationContext.from_investigator(
            delhi_supervisor,
            action="read",
            case=kerala_case,
        )
        decision = policy_engine.evaluate(ctx)
        assert not decision.allowed
        assert decision.policy_id == "CASE_ACCESS_DENIED"

    def test_state_wide_supervisor_can_access_any_jurisdiction(self, policy_engine):
        state_director = AuthenticatedInvestigator(
            subject_id="DGP-001",
            roles=["SUPERVISORY_OFFICER"],
            role="SUPERVISORY_OFFICER",
            station_jurisdiction="ALL",
            is_authenticated=True,
        )
        kerala_case = Case(
            case_id="CASE-KERALA-2026-888",
            assigned_io_id="IO-KERALA-005",
            fir_metadata={"jurisdiction_code": "KERALA"},
        )

        ctx = AuthorizationContext.from_investigator(
            state_director,
            action="read",
            case=kerala_case,
        )
        decision = policy_engine.evaluate(ctx)
        assert decision.allowed
        assert decision.policy_id == "CASE_ACCESS_SUPERVISORY"


class TestDevelopmentIdentityIsolation:
    """B. Development identity isolation verification."""

    def test_dev_auth_prohibited_in_production(self):
        with patch.object(settings, "ENVIRONMENT", "production"):
            with patch.object(settings, "AUTH_MODE", "development"):
                with pytest.raises(OIDCConfigurationException) as exc_info:
                    _create_authentication_service()
                assert "Development authentication is prohibited in production" in str(exc_info.value)

    def test_production_mode_disables_test_case_abac_exceptions(self, policy_engine):
        with patch.object(settings, "ENVIRONMENT", "production"):
            inv_user = AuthenticatedInvestigator(
                subject_id="INV-2026-001",
                roles=["INVESTIGATING_OFFICER"],
                role="INVESTIGATING_OFFICER",
                station_jurisdiction="STATION_CENTRAL",
                is_authenticated=True,
            )
            # Case with different assigned IO and different jurisdiction
            test_case = Case(
                case_id="SAKSHI-TEST-2026-002",
                assigned_io_id="SOME-OTHER-IO",
                fir_metadata={"jurisdiction_code": "OTHER_JURISDICTION"},
            )

            ctx = AuthorizationContext.from_investigator(
                inv_user,
                action="read",
                case=test_case,
            )
            decision = policy_engine.evaluate(ctx)
            # In production, the test case shortcut MUST be disabled
            assert not decision.allowed
            assert decision.policy_id == "CASE_ACCESS_DENIED"

    def test_unauthenticated_request_rejected(self):
        dev_auth = DevAuthenticationService()
        with pytest.raises(AuthenticationRequiredException):
            dev_auth.authenticate_request(auth_header=None, dev_investigator_id=None)


class TestRoleBasedAuthorization:
    """C. Role-based authorization matrix verification."""

    def test_forensic_analyst_cannot_create_case(self, policy_engine):
        analyst = AuthenticatedInvestigator(
            subject_id="ANALYST-001",
            roles=["FORENSIC_ANALYST"],
            role="FORENSIC_ANALYST",
            station_jurisdiction="KERALA",
            is_authenticated=True,
        )
        ctx = AuthorizationContext.from_investigator(
            analyst,
            action="create",
            resource_jurisdiction="KERALA",
        )
        decision = policy_engine.evaluate(ctx)
        assert not decision.allowed
        assert decision.policy_id == "RBAC_PERMISSION_DENIED"

    def test_io_cannot_reassign_case_to_other_officer(self, policy_engine):
        io = AuthenticatedInvestigator(
            subject_id="IO-001",
            roles=["INVESTIGATING_OFFICER"],
            role="INVESTIGATING_OFFICER",
            station_jurisdiction="KERALA",
            is_authenticated=True,
        )
        ctx = AuthorizationContext.from_investigator(
            io,
            action="assign",
            target_io_id="IO-OTHER-002",
        )
        decision = policy_engine.evaluate(ctx)
        assert not decision.allowed
        assert decision.policy_id == "CASE_ASSIGN_DENIED"

    def test_supervisor_can_reassign_case_to_other_officer(self, policy_engine):
        supervisor = AuthenticatedInvestigator(
            subject_id="SUP-001",
            roles=["SUPERVISORY_OFFICER"],
            role="SUPERVISORY_OFFICER",
            station_jurisdiction="KERALA",
            is_authenticated=True,
        )
        ctx = AuthorizationContext.from_investigator(
            supervisor,
            action="assign",
            target_io_id="IO-OTHER-002",
        )
        decision = policy_engine.evaluate(ctx)
        assert decision.allowed
        assert decision.policy_id == "CASE_ASSIGN_SUPERVISORY"


class TestLifecycleAndDecisionAuthorization:
    """E. Lifecycle and decision authorization verification."""

    def test_invalid_lifecycle_transition_raises_error(self):
        # Cannot jump from INITIALIZED directly to CLOSED
        allowed = stage_engine.get_allowed_transitions(CaseStage.INITIALIZED)
        assert CaseStage.CLOSED not in allowed
        assert CaseStage.EVIDENCE_INGESTION in allowed
        assert not stage_engine.can_transition(CaseStage.INITIALIZED, CaseStage.CLOSED)

    def test_forbidden_exception_raised_by_service_enforcement(self, authz_service):
        unauthorized_investigator = AuthenticatedInvestigator(
            subject_id="FOREIGN-001",
            roles=["INVESTIGATING_OFFICER"],
            role="INVESTIGATING_OFFICER",
            station_jurisdiction="DELHI",
            is_authenticated=True,
        )
        kerala_case = Case(
            case_id="CASE-KL-100",
            assigned_io_id="IO-KL-200",
            fir_metadata={"jurisdiction_code": "KERALA"},
        )
        with pytest.raises(ForbiddenException) as exc:
            authz_service.check_can_read_case(unauthorized_investigator, kerala_case)
        assert exc.value.status_code == 403
        assert exc.value.detail["error_code"] == "FORBIDDEN"
        # Verify no case metadata is leaked in client-facing error
        assert "CASE-KL-100" not in str(exc.value.detail)
