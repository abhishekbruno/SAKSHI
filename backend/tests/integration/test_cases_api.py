"""
Integration tests for Case Management REST API endpoints.
Tests HTTP contracts, security boundaries, status codes, and error payloads.
"""
from fastapi import status


def test_create_case_api(client, auth_headers_io1):
    payload = {
        "title": "Unnatural Death Inquiry - Apartment 4B",
        "fir_metadata": {
            "fir_number": "FIR-API-2026-001",
            "police_station": "South District Police Station",
            "incident_date": "2026-09-30T01:15:00Z",
            "report_date": "2026-09-30T03:00:00Z",
            "jurisdiction_code": "JUR-DEL-04",
            "incident_location": "Apartment 4B, Sunrise Enclave"
        }
    }
    response = client.post("/api/v1/cases", json=payload, headers=auth_headers_io1)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["case_id"].startswith("SAKSHI-CASE-")
    assert data["title"] == payload["title"]
    assert data["assigned_io_id"] == auth_headers_io1["X-Investigator-Id"]
    assert data["lifecycle_stage"] == "INITIALIZED"
    assert data["case_workspace"]["ready_for_ingestion"] is True


def test_unauthenticated_request_rejected(client):
    payload = {
        "title": "No Auth Case",
        "fir_metadata": {"fir_number": "FIR-000", "police_station": "HQ"}
    }
    response = client.post("/api/v1/cases", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    error_payload = response.json()
    assert error_payload["error_code"] == "AUTHENTICATION_REQUIRED"


def test_get_case_api(client, auth_headers_io1):
    # 1. Create a case
    create_payload = {
        "title": "Retrieval Case Test",
        "fir_metadata": {"fir_number": "FIR-GET-101", "police_station": "East Division"}
    }
    created = client.post("/api/v1/cases", json=create_payload, headers=auth_headers_io1).json()
    case_id = created["case_id"]

    # 2. Retrieve by Case ID
    res = client.get(f"/api/v1/cases/{case_id}", headers=auth_headers_io1)
    assert res.status_code == status.HTTP_200_OK
    retrieved = res.json()
    assert retrieved["case_id"] == case_id
    assert retrieved["title"] == create_payload["title"]


def test_get_nonexistent_case_returns_404(client, auth_headers_io1):
    res = client.get("/api/v1/cases/SAKSHI-CASE-UNKNOWN-9999", headers=auth_headers_io1)
    assert res.status_code == status.HTTP_404_NOT_FOUND
    error = res.json()
    assert error["error_code"] == "CASE_NOT_FOUND"


def test_cross_case_authorization_boundary(client, auth_headers_io1, auth_headers_io2, auth_headers_supervisor):
    # IO1 creates a case
    created = client.post("/api/v1/cases", json={
        "title": "Confidential Investigation",
        "fir_metadata": {"fir_number": "FIR-CONF-01", "police_station": "Sector 9"}
    }, headers=auth_headers_io1).json()
    case_id = created["case_id"]

    # IO2 attempts to view IO1's case -> Must be rejected with 403 Forbidden
    res_forbidden = client.get(f"/api/v1/cases/{case_id}", headers=auth_headers_io2)
    assert res_forbidden.status_code == status.HTTP_403_FORBIDDEN
    assert res_forbidden.json()["error_code"] == "FORBIDDEN"

    # Supervisor attempts to view IO1's case -> Permitted by policy
    res_supervisor = client.get(f"/api/v1/cases/{case_id}", headers=auth_headers_supervisor)
    assert res_supervisor.status_code == status.HTTP_200_OK


def test_list_cases_respects_investigator_filter(client, auth_headers_io1, auth_headers_io2):
    # IO1 creates a case
    client.post("/api/v1/cases", json={
        "title": "Case of IO1",
        "fir_metadata": {"fir_number": "FIR-L1-01", "police_station": "Station A"}
    }, headers=auth_headers_io1)

    # IO2 creates a case
    client.post("/api/v1/cases", json={
        "title": "Case of IO2",
        "fir_metadata": {"fir_number": "FIR-L2-02", "police_station": "Station B"}
    }, headers=auth_headers_io2)

    # IO1 lists cases -> only sees their own case
    res1 = client.get("/api/v1/cases", headers=auth_headers_io1)
    assert res1.status_code == status.HTTP_200_OK
    data1 = res1.json()
    assert all(c["assigned_io_id"] == auth_headers_io1["X-Investigator-Id"] for c in data1["cases"])


def test_patch_metadata_update(client, auth_headers_io1):
    created = client.post("/api/v1/cases", json={
        "title": "Preliminary Death Report",
        "fir_metadata": {"fir_number": "FIR-UP-01", "police_station": "North Division"}
    }, headers=auth_headers_io1).json()
    case_id = created["case_id"]

    # Update title
    update_res = client.patch(f"/api/v1/cases/{case_id}", json={
        "title": "Conclusive Post-Mortem Report Pending"
    }, headers=auth_headers_io1)
    assert update_res.status_code == status.HTTP_200_OK
    assert update_res.json()["title"] == "Conclusive Post-Mortem Report Pending"
    assert update_res.json()["case_id"] == case_id


def test_phase2_integration_contract_endpoint(client, auth_headers_io1):
    created = client.post("/api/v1/cases", json={
        "title": "Phase 2 Contract Endpoint Test",
        "fir_metadata": {"fir_number": "FIR-P2-EP", "police_station": "Central Station"}
    }, headers=auth_headers_io1).json()
    case_id = created["case_id"]

    res = client.get(f"/api/v1/cases/{case_id}/phase2-contract", headers=auth_headers_io1)
    assert res.status_code == status.HTTP_200_OK
    contract = res.json()
    assert contract["case_id"] == case_id
    assert contract["authorized_io_id"] == auth_headers_io1["X-Investigator-Id"]
    assert contract["lifecycle_stage"] == "INITIALIZED"
    assert contract["case_workspace_boundary"]["ingestion_gate_open"] is True
