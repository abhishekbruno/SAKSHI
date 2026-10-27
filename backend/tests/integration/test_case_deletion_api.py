"""
Integration tests for individual case deletion endpoint (DELETE /api/v1/cases/{case_id}).
Verifies:
1. Authorized officer receives 200 OK with CaseDeleteResponse.
2. Case is removed from GET /api/v1/cases active directory.
3. Unauthorized officer receives 403 Forbidden.
4. Non-existent case returns 404 Not Found.
5. Other cases remain untouched.
"""
from fastapi import status


def test_delete_case_api_authorized(client, auth_headers_io1):
    # 1. Create a test case
    res_create = client.post("/api/v1/cases", json={
        "title": "API Deletion Test Inquiry",
        "fir_metadata": {"fir_number": "FIR-API-DEL-01", "police_station": "Station Alpha"}
    }, headers=auth_headers_io1)
    assert res_create.status_code == status.HTTP_201_CREATED
    case_id = res_create.json()["case_id"]

    # 2. Call DELETE endpoint
    res_del = client.delete(f"/api/v1/cases/{case_id}", params={"reason": "Test case completed and archived"}, headers=auth_headers_io1)
    assert res_del.status_code == status.HTTP_200_OK
    data = res_del.json()
    assert data["success"] is True
    assert data["case_id"] == case_id
    assert data["status"] == "ARCHIVED"

    # 3. Verify it is removed from active list
    res_list = client.get("/api/v1/cases", headers=auth_headers_io1)
    assert res_list.status_code == status.HTTP_200_OK
    active_cases = res_list.json()["cases"]
    assert not any(c["case_id"] == case_id for c in active_cases)


def test_delete_case_api_unauthorized(client, auth_headers_io1, auth_headers_io2):
    # IO1 creates case
    res_create = client.post("/api/v1/cases", json={
        "title": "IO1 Case Protected From IO2",
        "fir_metadata": {"fir_number": "FIR-API-DEL-02", "police_station": "Station Alpha"}
    }, headers=auth_headers_io1)
    assert res_create.status_code == status.HTTP_201_CREATED
    case_id = res_create.json()["case_id"]

    # IO2 attempts to delete IO1's case
    res_del = client.delete(f"/api/v1/cases/{case_id}", headers=auth_headers_io2)
    assert res_del.status_code == status.HTTP_403_FORBIDDEN

    # Case must still be present for IO1
    res_get = client.get(f"/api/v1/cases/{case_id}", headers=auth_headers_io1)
    assert res_get.status_code == status.HTTP_200_OK
    assert res_get.json()["status"] == "ACTIVE"


def test_delete_case_api_nonexistent(client, auth_headers_io1):
    res_del = client.delete("/api/v1/cases/SAKSHI-CASE-NONEXISTENT-0000", headers=auth_headers_io1)
    assert res_del.status_code == status.HTTP_404_NOT_FOUND


def test_delete_case_isolation_other_cases_intact(client, auth_headers_io1):
    # Create Case 1
    c1 = client.post("/api/v1/cases", json={
        "title": "Case to be deleted",
        "fir_metadata": {"fir_number": "FIR-ISO-01", "police_station": "Station Alpha"}
    }, headers=auth_headers_io1).json()["case_id"]

    # Create Case 2
    c2 = client.post("/api/v1/cases", json={
        "title": "Case to remain intact",
        "fir_metadata": {"fir_number": "FIR-ISO-02", "police_station": "Station Alpha"}
    }, headers=auth_headers_io1).json()["case_id"]

    # Delete Case 1
    res_del = client.delete(f"/api/v1/cases/{c1}", headers=auth_headers_io1)
    assert res_del.status_code == status.HTTP_200_OK

    # Case 2 must remain ACTIVE and present
    res_get = client.get(f"/api/v1/cases/{c2}", headers=auth_headers_io1)
    assert res_get.status_code == status.HTTP_200_OK
    assert res_get.json()["status"] == "ACTIVE"
