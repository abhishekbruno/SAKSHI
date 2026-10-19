"""
Integration tests for IAM, Officer Registry, Jurisdiction, and Case Assignment REST API endpoints.
"""
from unittest.mock import MagicMock, patch
from fastapi import status
from app.models.organization import Organization, Jurisdiction, PoliceStation


def seed_iam_scope(db):
    org = Organization(organization_id="ORG-KL-POLICE", name="Kerala Police Department", code="KLP", created_by="ADMIN-0001")
    jur1 = Jurisdiction(jurisdiction_id="JUR-KL-TVM-01", organization_id="ORG-KL-POLICE", name="Thiruvananthapuram City", code="TVM", created_by="ADMIN-0001")
    jur2 = Jurisdiction(jurisdiction_id="JUR-KL-EKM-01", organization_id="ORG-KL-POLICE", name="Ernakulam City", code="EKM", created_by="ADMIN-0001")
    stn1 = PoliceStation(station_id="STN-KL-TVM-001", organization_id="ORG-KL-POLICE", jurisdiction_id="JUR-KL-TVM-01", name="Museum Police Station", code="MSM", created_by="ADMIN-0001")
    stn2 = PoliceStation(station_id="STN-KL-EKM-001", organization_id="ORG-KL-POLICE", jurisdiction_id="JUR-KL-EKM-01", name="Central Police Station", code="CTL", created_by="ADMIN-0001")
    db.add_all([org, jur1, jur2, stn1, stn2])
    db.commit()


def test_list_organizations_jurisdictions_stations(client, db_session, auth_headers_admin):
    seed_iam_scope(db_session)

    res_orgs = client.get("/api/v1/organizations", headers=auth_headers_admin)
    assert res_orgs.status_code == status.HTTP_200_OK
    orgs = res_orgs.json()
    assert len(orgs) >= 1
    assert any(o["organization_id"] == "ORG-KL-POLICE" for o in orgs)

    res_jur = client.get("/api/v1/jurisdictions", headers=auth_headers_admin)
    assert res_jur.status_code == status.HTTP_200_OK
    jurs = res_jur.json()
    assert len(jurs) >= 2

    res_stn = client.get("/api/v1/stations", headers=auth_headers_admin)
    assert res_stn.status_code == status.HTTP_200_OK
    stns = res_stn.json()
    assert len(stns) >= 2


def test_admin_onboard_officer_api(client, db_session, auth_headers_admin):
    seed_iam_scope(db_session)

    payload = {
        "full_name": "Inspector Manoj Varma",
        "mobile_number": "+919876500001",
        "role": "INVESTIGATING_OFFICER",
        "organization_id": "ORG-KL-POLICE",
        "jurisdiction_id": "JUR-KL-TVM-01",
        "station_id": "STN-KL-TVM-001",
        "initial_password": "SecurePassword123!",
        "service_identifier": "PEN-10029",
        "mobile_verified": True
    }

    with patch("app.api.v1.iam.FirebaseAdminProvisioner") as mock_prov_cls:
        mock_prov = MagicMock()
        mock_prov.create_user.return_value = "fb-mock-uid-001"
        mock_prov_cls.return_value = mock_prov

        res = client.post("/api/v1/officers", json=payload, headers=auth_headers_admin)

    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["full_name"] == payload["full_name"]
    assert data["mobile_e164"] == payload["mobile_number"]
    assert data["role"] == "INVESTIGATING_OFFICER"
    assert data["username"].startswith("SAK-IO-")
    assert data["status"] == "ACTIVE"
    officer_id = data["officer_id"]

    # Retrieve officer details
    res_get = client.get(f"/api/v1/officers/{officer_id}", headers=auth_headers_admin)
    assert res_get.status_code == status.HTTP_200_OK
    assert res_get.json()["officer_id"] == officer_id

    # List officers
    res_list = client.get("/api/v1/officers", headers=auth_headers_admin)
    assert res_list.status_code == status.HTTP_200_OK
    assert any(o["officer_id"] == officer_id for o in res_list.json())


def test_non_admin_cannot_onboard_officer(client, db_session, auth_headers_io1):
    seed_iam_scope(db_session)
    payload = {
        "full_name": "Unauthorized Officer",
        "mobile_number": "+919876500099",
        "role": "INVESTIGATING_OFFICER",
        "organization_id": "ORG-KL-POLICE",
        "jurisdiction_id": "JUR-KL-TVM-01",
        "station_id": "STN-KL-TVM-001",
        "initial_password": "SecurePassword123!"
    }
    res = client.post("/api/v1/officers", json=payload, headers=auth_headers_io1)
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_officer_lifecycle_deactivate_reactivate_transfer(client, db_session, auth_headers_admin):
    seed_iam_scope(db_session)

    payload = {
        "full_name": "Inspector Rajesh Kumar",
        "mobile_number": "+919876500002",
        "role": "INVESTIGATING_OFFICER",
        "organization_id": "ORG-KL-POLICE",
        "jurisdiction_id": "JUR-KL-TVM-01",
        "station_id": "STN-KL-TVM-001",
        "initial_password": "SecurePassword123!",
        "mobile_verified": True
    }

    with patch("app.api.v1.iam.FirebaseAdminProvisioner") as mock_prov_cls:
        mock_prov = MagicMock()
        mock_prov.create_user.return_value = "fb-mock-uid-002"
        mock_prov_cls.return_value = mock_prov
        res = client.post("/api/v1/officers", json=payload, headers=auth_headers_admin)

    officer_id = res.json()["officer_id"]

    # 1. Deactivate
    with patch("app.api.v1.iam.FirebaseAdminProvisioner") as mock_prov_cls:
        mock_prov = MagicMock()
        mock_prov_cls.return_value = mock_prov
        res_deact = client.post(f"/api/v1/officers/{officer_id}/deactivate", headers=auth_headers_admin)
    assert res_deact.status_code == status.HTTP_200_OK
    assert res_deact.json()["status"] == "DEACTIVATED"

    # 2. Reactivate
    with patch("app.api.v1.iam.FirebaseAdminProvisioner") as mock_prov_cls:
        mock_prov = MagicMock()
        mock_prov_cls.return_value = mock_prov
        res_react = client.post(f"/api/v1/officers/{officer_id}/reactivate", headers=auth_headers_admin)
    assert res_react.status_code == status.HTTP_200_OK
    assert res_react.json()["status"] == "ACTIVE"

    # 3. Transfer to Ernakulam
    transfer_payload = {
        "target_jurisdiction_id": "JUR-KL-EKM-01",
        "target_station_id": "STN-KL-EKM-001",
        "reason": "Administrative transfer order PHQ/TR/2026/102"
    }
    res_tr = client.post(f"/api/v1/officers/{officer_id}/transfer", json=transfer_payload, headers=auth_headers_admin)
    assert res_tr.status_code == status.HTTP_200_OK
    assert res_tr.json()["station_id"] == "STN-KL-EKM-001"
    assert res_tr.json()["jurisdiction_id"] == "JUR-KL-EKM-01"

    # 4. Reset Password
    with patch("app.api.v1.iam.FirebaseAdminProvisioner") as mock_prov_cls:
        mock_prov = MagicMock()
        mock_prov_cls.return_value = mock_prov
        res_pw = client.post(
            f"/api/v1/officers/{officer_id}/reset-password",
            json={"new_password": "NewSuperPassword999!"},
            headers=auth_headers_admin
        )
    assert res_pw.status_code == status.HTTP_200_OK


def test_case_assignment_api(client, db_session, auth_headers_admin):
    seed_iam_scope(db_session)

    # 1. Onboard an IO in TVM
    payload = {
        "full_name": "Inspector Anand Sharma",
        "mobile_number": "+919876500003",
        "role": "INVESTIGATING_OFFICER",
        "organization_id": "ORG-KL-POLICE",
        "jurisdiction_id": "JUR-KL-TVM-01",
        "station_id": "STN-KL-TVM-001",
        "initial_password": "SecurePassword123!",
        "mobile_verified": True
    }
    with patch("app.api.v1.iam.FirebaseAdminProvisioner") as mock_prov_cls:
        mock_prov = MagicMock()
        mock_prov.create_user.return_value = "fb-mock-uid-003"
        mock_prov_cls.return_value = mock_prov
        officer = client.post("/api/v1/officers", json=payload, headers=auth_headers_admin).json()
    officer_id = officer["officer_id"]

    # 2. Create a case in TVM
    case_payload = {
        "title": "Unnatural Death - Kowdiar Palace Road",
        "fir_metadata": {
            "fir_number": "FIR-TVM-2026-088",
            "police_station": "Museum Police Station",
            "jurisdiction_code": "JUR-KL-TVM-01"
        }
    }
    case = client.post("/api/v1/cases", json=case_payload, headers=auth_headers_admin).json()
    case_id = case["case_id"]

    # 3. Check eligible officers
    res_elig = client.get(f"/api/v1/cases/{case_id}/eligible-officers", headers=auth_headers_admin)
    assert res_elig.status_code == status.HTTP_200_OK
    assert any(o["officer_id"] == officer_id for o in res_elig.json())

    # 4. Assign case
    assign_payload = {
        "officer_id": officer_id,
        "reason": "Initial formal allotment of unnatural death inquiry"
    }
    res_assign = client.post(f"/api/v1/cases/{case_id}/assignments", json=assign_payload, headers=auth_headers_admin)
    assert res_assign.status_code == status.HTTP_201_CREATED
    assert res_assign.json()["officer_id"] == officer_id

    # 5. Check assignments history
    res_hist = client.get(f"/api/v1/cases/{case_id}/assignments", headers=auth_headers_admin)
    assert res_hist.status_code == status.HTTP_200_OK
    history = res_hist.json()
    assert len(history) >= 1
    assert history[0]["status"] == "ACTIVE"


def test_auth_logout_api(client, auth_headers_admin):
    res = client.post("/api/v1/auth/logout", headers=auth_headers_admin)
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "logged_out"
