from types import SimpleNamespace
import pytest
from app.models.organization import Organization, Jurisdiction, PoliceStation
from app.models.case import Case
from app.models.officer import Officer
from app.models.case_assignment import CaseAssignment
from app.core.security import AuthenticatedInvestigator
from app.core.errors import ForbiddenException, InvalidInvestigatorException
from app.services.iam_service import OfficerService, CaseAssignmentService, normalize_mobile


def admin(scope="ALL"):
    return AuthenticatedInvestigator(subject_id="ADMIN-1", display_name="Admin", role="ADMIN", roles=["ADMIN"], station_jurisdiction=scope, authentication_method="development")

def seed_scope(db):
    db.add_all([
        Organization(organization_id="ORG-1", name="Police", code="POL", created_by="ADMIN-1"),
        Jurisdiction(jurisdiction_id="JUR-1", organization_id="ORG-1", name="District", code="D1", created_by="ADMIN-1"),
        PoliceStation(station_id="STN-1", organization_id="ORG-1", jurisdiction_id="JUR-1", name="Central", code="C1", created_by="ADMIN-1"),
    ]); db.commit()

class Provisioner:
    def __init__(self): self.disabled = []; self.enabled = []; self.count = 0
    def create_user(self, identifier, password, disabled=False):
        self.count += 1
        return f"firebase-uid-{self.count}"
    def disable_user(self, uid): self.disabled.append(uid)
    def enable_user(self, uid): self.enabled.append(uid)

def payload(mobile="+919876543210"):
    return SimpleNamespace(full_name="Officer A", mobile_number=mobile, role="INVESTIGATING_OFFICER", organization_id="ORG-1", station_id="STN-1", jurisdiction_id="JUR-1", service_identifier=None, initial_password="a-very-long-password", mobile_verified=True)

def test_mobile_normalization_and_validation():
    assert normalize_mobile("+91 98765-43210") == "+919876543210"
    with pytest.raises(InvalidInvestigatorException): normalize_mobile("not-a-number")

def test_officer_onboarding_is_scoped_and_generates_private_identity(db_session):
    seed_scope(db_session)
    officer = OfficerService(db_session).create(payload(), admin(), Provisioner())
    assert officer.status == "ACTIVE"
    assert officer.username.startswith("SAK-IO-")
    assert officer.firebase_uid == "firebase-uid-1"
    assert officer.firebase_login_identifier.endswith("@firebase.sakshi.invalid")
    assert officer.mobile_e164 == "+919876543210"

def test_duplicate_mobile_is_rejected(db_session):
    seed_scope(db_session); service = OfficerService(db_session)
    service.create(payload(), admin(), Provisioner())
    with pytest.raises(InvalidInvestigatorException): service.create(payload(), admin(), Provisioner())

def test_non_admin_cannot_onboard(db_session):
    seed_scope(db_session)
    actor = AuthenticatedInvestigator(subject_id="IO", display_name="IO", role="INVESTIGATING_OFFICER", roles=["INVESTIGATING_OFFICER"], station_jurisdiction="JUR-1")
    with pytest.raises(ForbiddenException): OfficerService(db_session).create(payload(), actor, Provisioner())

def test_assignment_reassignment_keeps_history_and_denies_cross_jurisdiction(db_session):
    seed_scope(db_session)
    svc = OfficerService(db_session); provisioner = Provisioner()
    first = svc.create(payload(), admin(), provisioner)
    second = svc.create(payload("+919876543211"), admin(), provisioner)
    case = Case(case_id="CASE-IAM-1", title="Scope case", fir_metadata={"jurisdiction_code":"JUR-1", "fir_number":"F1", "police_station":"Central"}, assigned_io_id="legacy", case_workspace_path="/safe", created_by="ADMIN-1")
    db_session.add(case); db_session.commit()
    assignments = CaseAssignmentService(db_session)
    assignments.assign(case.case_id, first.officer_id, "Initial allocation", admin())
    assignments.assign(case.case_id, second.officer_id, "Operational reassignment", admin())
    history = db_session.query(CaseAssignment).filter_by(case_id=case.case_id).all()
    assert len(history) == 2 and sorted(x.status for x in history) == ["ACTIVE", "REASSIGNED"]
    assert db_session.query(Case).filter_by(case_id=case.case_id).one().assigned_io_id == second.officer_id
    with pytest.raises(ForbiddenException): assignments.assign(case.case_id, second.officer_id, "Wrong scope", admin("JUR-OTHER"))


def test_officer_deactivate_and_reactivate(db_session):
    seed_scope(db_session)
    svc = OfficerService(db_session)
    provisioner = Provisioner()
    officer = svc.create(payload(), admin(), provisioner)
    assert officer.status == "ACTIVE"

    # Deactivate
    deactivated = svc.change_status(officer.officer_id, "INACTIVE", admin(), provisioner)
    assert deactivated.status == "INACTIVE"
    assert officer.firebase_uid in provisioner.disabled

    # Reactivate
    reactivated = svc.change_status(officer.officer_id, "ACTIVE", admin(), provisioner)
    assert reactivated.status == "ACTIVE"


def test_officer_transfer_updates_scope(db_session):
    seed_scope(db_session)
    # Add target jurisdiction and station
    db_session.add_all([
        Jurisdiction(jurisdiction_id="JUR-2", organization_id="ORG-1", name="North District", code="D2", created_by="ADMIN-1"),
        PoliceStation(station_id="STN-2", organization_id="ORG-1", jurisdiction_id="JUR-2", name="North Stn", code="N1", created_by="ADMIN-1"),
    ])
    db_session.commit()

    svc = OfficerService(db_session)
    provisioner = Provisioner()
    officer = svc.create(payload(), admin(), provisioner)
    assert officer.station_id == "STN-1"
    assert officer.jurisdiction_id == "JUR-1"

    # Transfer
    transferred = svc.transfer(
        officer_id=officer.officer_id,
        target_station_id="STN-2",
        target_jurisdiction_id="JUR-2",
        reason="Administrative transfer order PHQ/2026/01",
        actor=admin(),
    )
    assert transferred.station_id == "STN-2"
    assert transferred.jurisdiction_id == "JUR-2"


def test_case_eligible_officers_filtered_by_jurisdiction(db_session):
    seed_scope(db_session)
    # Add second jurisdiction and station
    db_session.add_all([
        Jurisdiction(jurisdiction_id="JUR-2", organization_id="ORG-1", name="West District", code="D2", created_by="ADMIN-1"),
        PoliceStation(station_id="STN-2", organization_id="ORG-1", jurisdiction_id="JUR-2", name="West Stn", code="W1", created_by="ADMIN-1"),
    ])
    db_session.commit()

    svc = OfficerService(db_session)
    provisioner = Provisioner()
    # Officer 1 in JUR-1
    o1 = svc.create(payload("+919876543201"), admin(), provisioner)
    # Officer 2 in JUR-2
    p2 = SimpleNamespace(
        full_name="Officer West",
        mobile_number="+919876543202",
        role="INVESTIGATING_OFFICER",
        organization_id="ORG-1",
        station_id="STN-2",
        jurisdiction_id="JUR-2",
        service_identifier=None,
        initial_password="password12345",
        mobile_verified=True,
    )
    o2 = svc.create(p2, admin(), provisioner)

    # Case in JUR-1
    case = Case(
        case_id="CASE-ELIG-1",
        title="Eligible test case",
        fir_metadata={"jurisdiction_code": "JUR-1", "police_station": "Central"},
        assigned_io_id=o1.officer_id,
        case_workspace_path="/safe",
        created_by="ADMIN-1",
    )
    db_session.add(case)
    db_session.commit()

    assignments = CaseAssignmentService(db_session)
    eligible = assignments.eligible_officers(case.case_id, admin())
    eligible_ids = [e.officer_id for e in eligible]

    # o1 should be eligible because station/jurisdiction matches JUR-1
    assert o1.officer_id in eligible_ids
    # o2 in JUR-2 must NOT be eligible for a JUR-1 case
    assert o2.officer_id not in eligible_ids


