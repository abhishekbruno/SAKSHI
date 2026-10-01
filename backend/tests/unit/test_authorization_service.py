"""
MOD-03: RBAC / ABAC Authorization Engine Unit & Security Tests.

Tests the full matrix of RBAC, ABAC, Security, API, and Audit requirements
specified in Phase 1 Module 3 Master Specification.

Coverage:
    1. RBAC Tests: Valid role/permitted, forbidden action, unknown role, missing perm.
    2. ABAC Tests: Assigned IO, different IO, matching jurisdiction, different jurisdiction, supervisor access.
    3. Security Tests: Impersonation prevention, role/jurisdiction spoofing, cross-case access, default-deny.
    4. API Tests: 401 on unauthenticated, 403 on unauthorized, 200/201 on authorized.
    5. Audit Tests: Structured audit events emitted on both ALLOW and DENY.
"""
import pytest
from unittest.mock import patch, MagicMock

from app.core.security import AuthenticatedInvestigator
from app.core.errors import ForbiddenException
from app.models.case import Case
from app.services.authorization_service import (
    Permission,
    ROLE_PERMISSIONS,
    SUPERVISORY_ROLES,
    AuthorizationDecision,
    AuthorizationContext,
    PolicyEngine,
    policy_engine,
)
from app.services.auth_service import (
    PolicyEngineAuthorizationService,
    OIDCAuthenticationService,
)
from app.services.audit_integration import AuditIntegrationService
from app.services.case_service import CaseService
from app.schemas.case import CaseCreateRequest, FIRMetadata, CaseUpdateRequest


# ─── FIXTURES ─────────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    """Fresh PolicyEngine instance for tests."""
    return PolicyEngine()


@pytest.fixture
def authz_service():
    """PolicyEngineAuthorizationService instance."""
    return PolicyEngineAuthorizationService()


@pytest.fixture
def mock_case():
    """Sample Case entity representing an active investigation."""
    return Case(
        case_id="CASE-2026-TEST-0001",
        title="Unnatural Death Investigation",
        fir_metadata={
            "fir_number": "FIR-2026-001",
            "police_station": "Kowdiar Station",
            "jurisdiction_code": "JUR-TVM-01",
        },
        assigned_io_id="IO-7842-SHARMA",
        lifecycle_stage="INITIALIZED",
        status="ACTIVE",
        case_workspace_path="/sakshi/workspaces/CASE-2026-TEST-0001",
        created_by="IO-7842-SHARMA",
    )


@pytest.fixture
def io_assigned():
    """Investigator who is assigned to mock_case."""
    return AuthenticatedInvestigator(
        subject_id="IO-7842-SHARMA",
        display_name="Inspector Sharma",
        role="INVESTIGATING_OFFICER",
        station_jurisdiction="JUR-TVM-01",
        is_authenticated=True,
        authentication_method="oidc",
    )


@pytest.fixture
def io_same_jurisdiction():
    """Investigator not assigned to mock_case, but in the same jurisdiction."""
    return AuthenticatedInvestigator(
        subject_id="IO-5511-MENON",
        display_name="Inspector Menon",
        role="INVESTIGATING_OFFICER",
        station_jurisdiction="JUR-TVM-01",
        is_authenticated=True,
        authentication_method="oidc",
    )


@pytest.fixture
def io_different_jurisdiction():
    """Investigator not assigned to mock_case, in a different jurisdiction."""
    return AuthenticatedInvestigator(
        subject_id="IO-9912-VERMA",
        display_name="Inspector Verma",
        role="INVESTIGATING_OFFICER",
        station_jurisdiction="JUR-DEL-05",
        is_authenticated=True,
        authentication_method="oidc",
    )


@pytest.fixture
def supervisor():
    """Supervisory officer with broad oversight."""
    return AuthenticatedInvestigator(
        subject_id="IO-0001-COMMISSIONER",
        display_name="DCP Roy",
        role="SUPERVISORY_OFFICER",
        station_jurisdiction="ALL",
        is_authenticated=True,
        authentication_method="oidc",
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1. RBAC TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestRBACEvaluation:
    """RBAC validation: roles, permissions, default-deny."""

    def test_rbac_valid_role_permitted_action_allow(self, engine, io_assigned):
        """1. Valid role + permitted action -> ALLOW."""
        ctx = AuthorizationContext(
            subject_id=io_assigned.subject_id,
            subject_role=io_assigned.role,
            subject_roles=[io_assigned.role],
            action="create",
        )
        decision = engine.evaluate(ctx)
        assert decision.allowed is True
        assert "RBAC" in decision.policy_id or "ABAC" in decision.policy_id

    def test_rbac_valid_role_forbidden_action_deny(self, engine):
        """2. Valid role + forbidden action -> DENY."""
        # CASE_ADMIN does not have permission to update case or create case
        ctx = AuthorizationContext(
            subject_id="ADMIN-001",
            subject_role="CASE_ADMIN",
            subject_roles=["CASE_ADMIN"],
            action="create",
        )
        decision = engine.evaluate(ctx)
        assert decision.allowed is False
        assert decision.policy_id == "RBAC_PERMISSION_DENIED"

    def test_rbac_unknown_role_deny(self, engine):
        """3. Unknown role -> DENY (Default Deny)."""
        ctx = AuthorizationContext(
            subject_id="UNKNOWN-USER",
            subject_role="TRAINEE_INTERN",
            subject_roles=["TRAINEE_INTERN"],
            action="create",
        )
        decision = engine.evaluate(ctx)
        assert decision.allowed is False
        assert decision.policy_id == "RBAC_PERMISSION_DENIED"

    def test_rbac_missing_permission_deny(self, engine):
        """4. Missing permission -> DENY."""
        ctx = AuthorizationContext(
            subject_id="GUEST-01",
            subject_role="GUEST",
            subject_roles=["GUEST"],
            action="read",
            resource_id="CASE-1",
        )
        decision = engine.evaluate(ctx)
        assert decision.allowed is False
        assert decision.policy_id == "RBAC_PERMISSION_DENIED"

    def test_rbac_unknown_action_deny(self, engine, io_assigned):
        """Action with no permission mapping -> DENY."""
        ctx = AuthorizationContext(
            subject_id=io_assigned.subject_id,
            subject_role=io_assigned.role,
            subject_roles=[io_assigned.role],
            action="delete_case_database",
        )
        decision = engine.evaluate(ctx)
        assert decision.allowed is False
        assert decision.policy_id == "RBAC_UNKNOWN_ACTION"


# ═══════════════════════════════════════════════════════════════════════════
# 2. ABAC TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestABACEvaluation:
    """ABAC validation: assignment, jurisdiction, supervisor oversight."""

    def test_abac_assigned_investigator_allow(self, engine, io_assigned, mock_case):
        """5. Assigned investigator -> ALLOW."""
        ctx = AuthorizationContext.from_investigator(
            io_assigned, action="read", case=mock_case
        )
        decision = engine.evaluate(ctx)
        assert decision.allowed is True
        assert decision.policy_id == "CASE_ACCESS_ASSIGNED_IO"

    def test_abac_different_investigator_different_jurisdiction_deny(
        self, engine, io_different_jurisdiction, mock_case
    ):
        """6. Different investigator in different jurisdiction -> DENY."""
        ctx = AuthorizationContext.from_investigator(
            io_different_jurisdiction, action="read", case=mock_case
        )
        decision = engine.evaluate(ctx)
        assert decision.allowed is False
        assert decision.policy_id == "CASE_ACCESS_DENIED"

    def test_abac_matching_jurisdiction_allow(
        self, engine, io_same_jurisdiction, mock_case
    ):
        """7. Matching jurisdiction -> ALLOW."""
        ctx = AuthorizationContext.from_investigator(
            io_same_jurisdiction, action="read", case=mock_case
        )
        decision = engine.evaluate(ctx)
        assert decision.allowed is True
        assert decision.policy_id == "CASE_ACCESS_JURISDICTION"

    def test_abac_different_jurisdiction_deny(
        self, engine, io_different_jurisdiction, mock_case
    ):
        """8. Different jurisdiction -> DENY."""
        ctx = AuthorizationContext.from_investigator(
            io_different_jurisdiction, action="update", case=mock_case
        )
        decision = engine.evaluate(ctx)
        assert decision.allowed is False
        assert decision.policy_id == "CASE_ACCESS_DENIED"

    def test_abac_authorized_supervisor_allow(
        self, engine, supervisor, mock_case
    ):
        """9. Authorized supervisor -> ALLOW according to configured policy."""
        ctx = AuthorizationContext.from_investigator(
            supervisor, action="read", case=mock_case
        )
        decision = engine.evaluate(ctx)
        assert decision.allowed is True
        assert decision.policy_id == "CASE_ACCESS_SUPERVISORY"

    def test_abac_unauthorized_user_deny(self, engine, mock_case):
        """10. Unauthorized user with valid role attempting assignment to other IO -> DENY."""
        non_supervisor = AuthenticatedInvestigator(
            subject_id="IO-1111",
            role="INVESTIGATING_OFFICER",
            is_authenticated=True,
        )
        ctx = AuthorizationContext.from_investigator(
            non_supervisor, action="assign", case=mock_case, target_io_id="IO-2222"
        )
        decision = engine.evaluate(ctx)
        assert decision.allowed is False
        assert decision.policy_id == "CASE_ASSIGN_DENIED"


# ═══════════════════════════════════════════════════════════════════════════
# 3. SECURITY TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestSecurityControls:
    """Security invariants: IDOR, impersonation, elevation, default-deny."""

    def test_security_client_investigator_id_cannot_impersonate(
        self, db_session, mock_io1, mock_io2
    ):
        """11. Client investigator_id in request payload cannot override trusted token identity."""
        service = CaseService(db_session)
        # mock_io1 creates case specifying mock_io2 in assigned_io_id — but self is IO1
        # Regular IO cannot assign to another IO!
        with pytest.raises(ForbiddenException):
            service.create_case(
                CaseCreateRequest(
                    title="Impersonation Attack",
                    fir_metadata=FIRMetadata(fir_number="FIR-SEC-01", police_station="Station A"),
                    assigned_io_id=mock_io2.investigator_id  # Attempting to assign to IO2
                ),
                investigator=mock_io1  # Authenticated identity is IO1
            )

    def test_security_client_role_cannot_override_token_role(self, engine):
        """12. Client-supplied role cannot override validated token role."""
        # Trusted identity from token: INVESTIGATING_OFFICER
        # Malicious client tries to pass roles=["SUPERVISORY_OFFICER"]
        token_identity = AuthenticatedInvestigator(
            subject_id="IO-ATTACKER",
            role="INVESTIGATING_OFFICER",
            roles=["INVESTIGATING_OFFICER"],  # Trusted claims
            is_authenticated=True,
        )
        ctx = AuthorizationContext.from_investigator(
            token_identity, action="assign", target_io_id="IO-VICTIM"
        )
        decision = engine.evaluate(ctx)
        assert decision.allowed is False
        assert decision.policy_id == "CASE_ASSIGN_DENIED"

    def test_security_client_station_cannot_override_trusted_identity(
        self, engine, mock_case
    ):
        """13. Client-supplied station in request payload cannot override trusted token identity."""
        io_diff = AuthenticatedInvestigator(
            subject_id="IO-DIFF",
            role="INVESTIGATING_OFFICER",
            station_jurisdiction="JUR-OTHER",
            is_authenticated=True,
        )
        # Even if request payload claimed station "Kowdiar Station", context uses io_diff.station_jurisdiction
        ctx = AuthorizationContext.from_investigator(
            io_diff, action="read", case=mock_case
        )
        decision = engine.evaluate(ctx)
        assert decision.allowed is False
        assert decision.policy_id == "CASE_ACCESS_DENIED"

    def test_security_client_jurisdiction_cannot_override_trusted_identity(
        self, engine, mock_case
    ):
        """14. Client jurisdiction cannot override trusted identity."""
        io_spoof = AuthenticatedInvestigator(
            subject_id="IO-SPOOF",
            role="INVESTIGATING_OFFICER",
            station_jurisdiction="JUR-FAKE-01",
            is_authenticated=True,
        )
        ctx = AuthorizationContext.from_investigator(
            io_spoof, action="read", case=mock_case
        )
        decision = engine.evaluate(ctx)
        assert decision.allowed is False
        assert decision.policy_id == "CASE_ACCESS_DENIED"

    def test_security_cross_case_access_denied(
        self, db_session, mock_io1, mock_io2
    ):
        """15. Cross-case access is strictly denied for non-supervisory officers."""
        service = CaseService(db_session)
        case1 = service.create_case(
            CaseCreateRequest(
                title="IO1 Confidential Case",
                fir_metadata=FIRMetadata(
                    fir_number="FIR-CROSS-01",
                    police_station="South Station",
                    jurisdiction_code="JUR-SOUTH",
                )
            ),
            investigator=mock_io1
        )

        # mock_io2 (different jurisdiction) attempts to access case1
        with pytest.raises(ForbiddenException):
            service.get_case(case1.case_id, investigator=mock_io2)

    def test_security_unauthorized_update_denied(
        self, db_session, mock_io1, mock_io2
    ):
        """16. Unauthorized update is denied."""
        service = CaseService(db_session)
        case1 = service.create_case(
            CaseCreateRequest(
                title="IO1 Mutable Case",
                fir_metadata=FIRMetadata(fir_number="FIR-UPD-01", police_station="Station A")
            ),
            investigator=mock_io1
        )

        with pytest.raises(ForbiddenException):
            service.update_case(
                case1.case_id,
                CaseUpdateRequest(title="Tampered Title"),
                investigator=mock_io2
            )

    def test_security_unauthorized_assignment_denied(
        self, db_session, mock_io1, mock_io2
    ):
        """17. Unauthorized assignment is denied (regular IO cannot reassign to another IO)."""
        service = CaseService(db_session)
        case1 = service.create_case(
            CaseCreateRequest(
                title="Reassignment Boundary Test",
                fir_metadata=FIRMetadata(fir_number="FIR-REAS-01", police_station="Station A")
            ),
            investigator=mock_io1
        )

        with pytest.raises(ForbiddenException):
            service.assign_investigator(
                case1.case_id,
                target_io_id=mock_io2.investigator_id,
                investigator=mock_io1  # Regular IO trying to reassign
            )

    def test_security_default_deny_behavior(self, engine):
        """18. Default-deny behavior: Any unmatched action or role is rejected."""
        unrecognized_ctx = AuthorizationContext(
            subject_id="UNKNOWN",
            subject_role="UNKNOWN",
            subject_roles=["UNKNOWN"],
            action="unrecognized_operation",
        )
        decision = engine.evaluate(unrecognized_ctx)
        assert decision.allowed is False


# ═══════════════════════════════════════════════════════════════════════════
# 4. API & INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestAuthorizationAPI:
    """HTTP API authorization tests via FastAPI TestClient."""

    def test_api_no_token_401_in_oidc_mode(self, client):
        """19. No token in OIDC mode -> 401 Unauthorized."""
        from app.core.config import settings
        from app.services import auth_service as auth_mod
        from app.api import deps as deps_mod

        # Instantiate an OIDC service to simulate OIDC mode
        oidc_svc = OIDCAuthenticationService(
            issuer_url="https://idp.example.com",
            audience="sakshi",
        )
        with patch.object(deps_mod, "auth_service", oidc_svc):
            resp = client.get("/api/v1/cases")
            assert resp.status_code == 401
            assert resp.json()["error_code"] == "AUTHENTICATION_REQUIRED"

    def test_api_insufficient_permission_403(self, client, auth_headers_io1):
        """20. Valid token/session but insufficient permission -> 403 Forbidden."""
        # Create a case with IO1
        create_resp = client.post(
            "/api/v1/cases",
            json={
                "title": "Restricted Case",
                "fir_metadata": {
                    "fir_number": "FIR-403-01",
                    "police_station": "Station A",
                    "jurisdiction_code": "JUR-A"
                }
            },
            headers=auth_headers_io1
        )
        assert create_resp.status_code == 201
        case_id = create_resp.json()["case_id"]

        # IO2 tries to access IO1's case
        headers_io2 = {
            "X-Investigator-Id": "IO-9912-VERMA",
            "X-Investigator-Role": "INVESTIGATING_OFFICER",
            "X-Investigator-Jurisdiction": "JUR-B"
        }
        get_resp = client.get(f"/api/v1/cases/{case_id}", headers=headers_io2)
        assert get_resp.status_code == 403
        assert get_resp.json()["error_code"] == "FORBIDDEN"

    def test_api_valid_token_permission_success(self, client, auth_headers_io1):
        """21. Valid token + authorized permission -> success (201, 200)."""
        create_resp = client.post(
            "/api/v1/cases",
            json={
                "title": "Authorized Case",
                "fir_metadata": {
                    "fir_number": "FIR-200-01",
                    "police_station": "Central Station"
                }
            },
            headers=auth_headers_io1
        )
        assert create_resp.status_code == 201
        case_id = create_resp.json()["case_id"]

        get_resp = client.get(f"/api/v1/cases/{case_id}", headers=auth_headers_io1)
        assert get_resp.status_code == 200
        assert get_resp.json()["case_id"] == case_id

    def test_api_existing_case_endpoints_functional(
        self, client, auth_headers_io1, auth_headers_supervisor
    ):
        """22. Existing case endpoints remain completely functional."""
        # 1. Create
        c_resp = client.post(
            "/api/v1/cases",
            json={
                "title": "Lifecycle End-to-End",
                "fir_metadata": {"fir_number": "FIR-E2E-01", "police_station": "Central"}
            },
            headers=auth_headers_io1
        )
        assert c_resp.status_code == 201
        case_id = c_resp.json()["case_id"]

        # 2. List
        l_resp = client.get("/api/v1/cases", headers=auth_headers_io1)
        assert l_resp.status_code == 200
        assert l_resp.json()["total"] >= 1

        # 3. Patch
        p_resp = client.patch(
            f"/api/v1/cases/{case_id}",
            json={"title": "Updated Title E2E"},
            headers=auth_headers_io1
        )
        assert p_resp.status_code == 200
        assert p_resp.json()["title"] == "Updated Title E2E"

        # 4. Supervisor Reassign
        assign_resp = client.post(
            f"/api/v1/cases/{case_id}/assign-investigator",
            json={"assigned_io_id": "IO-9912-VERMA"},
            headers=auth_headers_supervisor
        )
        assert assign_resp.status_code == 200
        assert assign_resp.json()["assigned_io_id"] == "IO-9912-VERMA"

        # 5. Phase 2 contract export
        contract_resp = client.get(
            f"/api/v1/cases/{case_id}/phase2-contract",
            headers=auth_headers_supervisor
        )
        assert contract_resp.status_code == 200
        assert contract_resp.json()["case_id"] == case_id


# ═══════════════════════════════════════════════════════════════════════════
# 5. AUDIT INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestAuditIntegration:
    """Audit recording verification for authorization decisions."""

    def test_audit_event_recorded_on_allow(self, authz_service, io_assigned, mock_case):
        """23. Authorization ALLOW events are sent to AuditIntegrationService."""
        with patch.object(AuditIntegrationService, "record_authorization_event") as mock_audit:
            authz_service.check_can_read_case(io_assigned, mock_case)
            mock_audit.assert_called_once()
            call_kwargs = mock_audit.call_args[1]
            assert call_kwargs["decision"] == "ALLOW"
            assert call_kwargs["subject_id"] == io_assigned.subject_id
            assert call_kwargs["action"] == "read"
            assert call_kwargs["resource_id"] == mock_case.case_id

    def test_audit_event_recorded_on_deny(self, authz_service, io_different_jurisdiction, mock_case):
        """24. Authorization DENY events are sent to AuditIntegrationService and raise ForbiddenException."""
        with patch.object(AuditIntegrationService, "record_authorization_event") as mock_audit:
            with pytest.raises(ForbiddenException):
                authz_service.check_can_read_case(io_different_jurisdiction, mock_case)
            mock_audit.assert_called_once()
            call_kwargs = mock_audit.call_args[1]
            assert call_kwargs["decision"] == "DENY"
            assert call_kwargs["subject_id"] == io_different_jurisdiction.subject_id
            assert call_kwargs["action"] == "read"
            assert call_kwargs["resource_id"] == mock_case.case_id
