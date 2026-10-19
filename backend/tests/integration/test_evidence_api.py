"""
Integration tests for Evidence Intake REST API (MOD-05).
Tests multipart upload, authentication & authorization boundaries,
Stage Engine gate enforcement, list/get retrieval, and downstream contract export.
"""
import io
from fastapi import status


def _create_and_open_case(client, auth_headers):
    """Helper to create a case and advance it to EVIDENCE_INGESTION."""
    create_payload = {
        "title": "Unnatural Death Investigation - Forensic Evidence Intake",
        "fir_metadata": {
            "fir_number": "FIR-INTAKE-TEST-01",
            "police_station": "Central Forensic Police Station",
            "jurisdiction_code": "JUR-DEL-04"
        }
    }
    case_resp = client.post("/api/v1/cases", json=create_payload, headers=auth_headers).json()
    case_id = case_resp["case_id"]

    # Transition to EVIDENCE_INGESTION stage
    stage_resp = client.post(
        f"/api/v1/cases/{case_id}/stage",
        json={"lifecycle_stage": "EVIDENCE_INGESTION"},
        headers=auth_headers
    )
    assert stage_resp.status_code == status.HTTP_200_OK
    return case_id


def test_evidence_upload_api_success(client, auth_headers_io1):
    case_id = _create_and_open_case(client, auth_headers_io1)

    file_content = b"%PDF-1.4 simulated autopsy report"
    files = {
        "file": ("autopsy_report.pdf", io.BytesIO(file_content), "application/pdf")
    }
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
        "collection_location": "District Hospital Mortuary",
        "source_device_or_person": "Dr. R. K. Sen",
        "description": "Post-mortem examination report with external injury chart"
    }

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files=files,
        data=data,
        headers=auth_headers_io1
    )

    assert res.status_code == status.HTTP_201_CREATED
    ev = res.json()
    assert ev["evidence_id"].startswith("SAKSHI-EVID-")
    assert ev["case_id"] == case_id
    assert ev["original_file_name"] == "autopsy_report.pdf"
    assert ev["evidence_category"] == "DOCUMENT_PDF"
    assert ev["declared_mime_type"] == "application/pdf"
    assert ev["file_size_bytes"] == len(file_content)
    assert ev["submitting_investigator_id"] == auth_headers_io1["X-Investigator-Id"]
    assert ev["status"] == "REGISTERED_INTAKE"


def test_evidence_upload_unauthenticated_rejected(client, auth_headers_io1):
    case_id = _create_and_open_case(client, auth_headers_io1)

    files = {
        "file": ("document.pdf", io.BytesIO(b"data"), "application/pdf")
    }
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
    }

    res = client.post(f"/api/v1/cases/{case_id}/evidence", files=files, data=data)
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_evidence_upload_gate_closed_in_initialized_stage(client, auth_headers_io1):
    """Case is in INITIALIZED stage (not advanced to EVIDENCE_INGESTION). Upload must be rejected."""
    create_payload = {
        "title": "Fresh Unopened Case",
        "fir_metadata": {
            "fir_number": "FIR-GATE-CLOSED-01",
            "police_station": "Station A"
        }
    }
    case_resp = client.post("/api/v1/cases", json=create_payload, headers=auth_headers_io1).json()
    case_id = case_resp["case_id"]

    files = {
        "file": ("scene_photo.jpg", io.BytesIO(b"\xFF\xD8\xFF image data"), "image/jpeg")
    }
    data = {
        "evidence_category": "SCENE_PHOTO",
        "declared_mime_type": "image/jpeg",
    }

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files=files,
        data=data,
        headers=auth_headers_io1
    )

    assert res.status_code == status.HTTP_400_BAD_REQUEST
    err = res.json()
    assert err["error_code"] == "INGESTION_GATE_CLOSED"


def test_evidence_list_and_get_api(client, auth_headers_io1):
    case_id = _create_and_open_case(client, auth_headers_io1)

    # Upload item 1
    client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("file1.pdf", io.BytesIO(b"content 1"), "application/pdf")},
        data={"evidence_category": "DOCUMENT_PDF", "declared_mime_type": "application/pdf"},
        headers=auth_headers_io1
    )

    # Upload item 2
    upload2 = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("scene.jpg", io.BytesIO(b"photo bytes"), "image/jpeg")},
        data={"evidence_category": "SCENE_PHOTO", "declared_mime_type": "image/jpeg"},
        headers=auth_headers_io1
    ).json()

    evidence_id2 = upload2["evidence_id"]

    # List evidence
    list_res = client.get(f"/api/v1/cases/{case_id}/evidence", headers=auth_headers_io1)
    assert list_res.status_code == status.HTTP_200_OK
    list_data = list_res.json()
    assert list_data["total"] == 2
    assert len(list_data["items"]) == 2

    # Get single item
    get_res = client.get(f"/api/v1/cases/{case_id}/evidence/{evidence_id2}", headers=auth_headers_io1)
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()["evidence_id"] == evidence_id2

    # Get downstream contract for MOD-06
    contract_res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id2}/contract",
        headers=auth_headers_io1
    )
    assert contract_res.status_code == status.HTTP_200_OK
    contract_data = contract_res.json()
    assert contract_data["evidence_id"] == evidence_id2
    assert contract_data["case_id"] == case_id
    assert contract_data["intake_status"] == "REGISTERED_INTAKE"
    assert contract_data["declared_mime_type"] == "image/jpeg"


def test_cross_investigator_evidence_intake_forbidden(client, auth_headers_io1, auth_headers_io2):
    """IO2 cannot upload evidence to IO1's case."""
    case_id = _create_and_open_case(client, auth_headers_io1)

    files = {
        "file": ("unauthorized.csv", io.BytesIO(b"cdr data"), "text/csv")
    }
    data = {
        "evidence_category": "CDR_SPREADSHEET",
        "declared_mime_type": "text/csv",
    }

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files=files,
        data=data,
        headers=auth_headers_io2
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_supervisor_can_access_case_evidence(client, auth_headers_io1, auth_headers_supervisor):
    """Supervisory officer has access across assigned boundaries."""
    case_id = _create_and_open_case(client, auth_headers_io1)

    # IO1 uploads evidence
    upload_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files={"file": ("inquest.pdf", io.BytesIO(b"inquest data"), "application/pdf")},
        data={"evidence_category": "DOCUMENT_PDF", "declared_mime_type": "application/pdf"},
        headers=auth_headers_io1
    ).json()

    evidence_id = upload_res["evidence_id"]

    # Supervisor retrieves evidence list and detail
    list_res = client.get(f"/api/v1/cases/{case_id}/evidence", headers=auth_headers_supervisor)
    assert list_res.status_code == status.HTTP_200_OK
    assert list_res.json()["total"] == 1

    get_res = client.get(f"/api/v1/cases/{case_id}/evidence/{evidence_id}", headers=auth_headers_supervisor)
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()["evidence_id"] == evidence_id
