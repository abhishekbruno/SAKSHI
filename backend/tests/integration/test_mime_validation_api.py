"""
Integration tests for MOD-06 MIME & Signature Validation REST API.
Tests HTTP validation endpoints, status transitions, downstream MOD-07 contract exports,
unauthenticated/unauthorized access, and case isolation.
"""
import io
from fastapi import status


def _create_open_case_and_upload(client, auth_headers, file_bytes: bytes, filename: str, mime: str, category: str):
    """Helper to create a case, advance to EVIDENCE_INGESTION, and register an evidence item."""
    create_payload = {
        "title": "Forensic Ballistics & Evidence Validation Case",
        "fir_metadata": {
            "fir_number": f"FIR-VAL-API-{filename}",
            "police_station": "Central Crime Branch",
            "jurisdiction_code": "JUR-DEL-04"
        }
    }
    case_resp = client.post("/api/v1/cases", json=create_payload, headers=auth_headers).json()
    case_id = case_resp["case_id"]

    # Advance stage to EVIDENCE_INGESTION
    client.post(
        f"/api/v1/cases/{case_id}/stage",
        json={"lifecycle_stage": "EVIDENCE_INGESTION"},
        headers=auth_headers
    )

    # Register evidence (MOD-05)
    files = {"file": (filename, io.BytesIO(file_bytes), mime)}
    data = {"evidence_category": category, "declared_mime_type": mime}
    ev_resp = client.post(f"/api/v1/cases/{case_id}/evidence", files=files, data=data, headers=auth_headers).json()
    evidence_id = ev_resp["evidence_id"]

    return case_id, evidence_id


def test_validate_evidence_api_pass(client, auth_headers_io1):
    pdf_bytes = b"%PDF-1.4 simulated autopsy report\n%%EOF"
    case_id, evidence_id = _create_open_case_and_upload(
        client, auth_headers_io1, pdf_bytes, "inquest.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    # Call MOD-06 validation endpoint
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/validate",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["valid"] is True
    assert data["status"] == "VALIDATED"
    assert data["detected_mime"] == "application/pdf"
    assert data["detected_format"] == "PDF"
    assert data["evidence_id"] == evidence_id
    assert data["case_id"] == case_id


def test_validate_evidence_api_mismatch_reject(client, auth_headers_io1):
    # JPEG payload declared as application/pdf
    jpeg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
    case_id, evidence_id = _create_open_case_and_upload(
        client, auth_headers_io1, jpeg_bytes, "disguised.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/validate",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["valid"] is False
    assert data["status"] == "REJECTED"
    assert "mismatch" in data["validation_reason"].lower()
    assert data["detected_mime"] == "image/jpeg"


def test_get_validated_contract_api_success(client, auth_headers_io1):
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    case_id, evidence_id = _create_open_case_and_upload(
        client, auth_headers_io1, png_bytes, "scene_photo.png", "image/png", "SCENE_PHOTO"
    )

    # 1. Validate first
    client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/validate", headers=auth_headers_io1)

    # 2. Retrieve downstream contract for MOD-07
    res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/validated-contract",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["evidence_id"] == evidence_id
    assert data["case_id"] == case_id
    assert data["verified_mime_type"] == "image/png"
    assert data["detected_format"] == "PNG"
    assert data["validation_status"] == "VALIDATED"


def test_get_validated_contract_api_rejected_evidence(client, auth_headers_io1):
    exe_bytes = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
    case_id, evidence_id = _create_open_case_and_upload(
        client, auth_headers_io1, exe_bytes, "trojan.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    # 1. Validate (should reject)
    client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/validate", headers=auth_headers_io1)

    # 2. Attempt to retrieve downstream contract for MOD-07 -> must be blocked!
    res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/validated-contract",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    err = res.json()
    assert err["error_code"] == "EVIDENCE_VALIDATION_FAILED"


def test_validate_evidence_unauthenticated_rejected(client, auth_headers_io1):
    pdf_bytes = b"%PDF-1.4"
    case_id, evidence_id = _create_open_case_and_upload(
        client, auth_headers_io1, pdf_bytes, "doc.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    res = client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/validate")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_cross_investigator_validation_forbidden(client, auth_headers_io1, auth_headers_io2):
    pdf_bytes = b"%PDF-1.4"
    case_id, evidence_id = _create_open_case_and_upload(
        client, auth_headers_io1, pdf_bytes, "doc.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    # IO2 tries to validate IO1's evidence
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/validate",
        headers=auth_headers_io2
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_supervisor_can_validate_case_evidence(client, auth_headers_io1, auth_headers_supervisor):
    pdf_bytes = b"%PDF-1.4 post-mortem toxicology report\n%%EOF"
    case_id, evidence_id = _create_open_case_and_upload(
        client, auth_headers_io1, pdf_bytes, "tox_report.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/validate",
        headers=auth_headers_supervisor
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["status"] == "VALIDATED"
