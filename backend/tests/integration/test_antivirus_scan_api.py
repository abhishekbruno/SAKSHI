"""
Integration tests for MOD-07 Antivirus Scan REST API.
Tests HTTP endpoints:
- POST /api/v1/cases/{case_id}/evidence/{evidence_id}/scan
- GET /api/v1/cases/{case_id}/evidence/{evidence_id}/scanned-contract
- /health endpoint verification
Tests clean scans, EICAR detection, quarantine blocking, pipeline ordering,
unauthorized / unauthenticated access, and error cases.
"""
import io
from fastapi import status
from app.services.antivirus_scan_service import EICAR_SIGNATURE

CLEAN_PDF_BYTES = b"%PDF-1.5 forensic report sample\n%%EOF"
CLEAN_CSV_BYTES = b"timestamp,caller,receiver\n2026-03-01,911,999\n"
EICAR_CSV_BYTES = CLEAN_CSV_BYTES + b"\n# TEST_PAYLOAD: " + EICAR_SIGNATURE + b"\n"


def _create_open_case_and_validate_evidence(
    client,
    auth_headers,
    file_bytes: bytes,
    filename: str,
    mime: str,
    category: str
):
    """Helper that creates a case, advances to EVIDENCE_INGESTION, registers evidence, and runs MOD-06 validation."""
    create_payload = {
        "title": "Forensic Malware Ingestion Case",
        "fir_metadata": {
            "fir_number": f"FIR-AV-API-{filename}",
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

    # Validate evidence (MOD-06)
    val_resp = client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/validate", headers=auth_headers)
    assert val_resp.status_code == status.HTTP_200_OK

    return case_id, evidence_id


def test_scan_clean_evidence_api(client, auth_headers_io1):
    case_id, evidence_id = _create_open_case_and_validate_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "case_report.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    # Invoke MOD-07 Antivirus scan
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scan",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["verdict"] == "CLEAN"
    assert data["status"] == "CLEAN"
    assert data["threat_name"] is None
    assert data["scanner_name"] == "EicarHeuristicScanner"
    assert data["evidence_id"] == evidence_id
    assert data["case_id"] == case_id


def test_get_scanned_contract_api_clean(client, auth_headers_io1):
    case_id, evidence_id = _create_open_case_and_validate_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "clean_handover.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    # Scan clean evidence
    client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scan", headers=auth_headers_io1)

    # Export ScannedEvidenceObject for MOD-08
    res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scanned-contract",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_200_OK
    contract = res.json()
    assert contract["evidence_id"] == evidence_id
    assert contract["case_id"] == case_id
    assert contract["antivirus_verdict"] == "CLEAN"
    assert contract["mime_status"] == "VALIDATED"
    assert contract["antivirus_scanner"] == "EicarHeuristicScanner"


def test_scan_eicar_threat_api(client, auth_headers_io1):
    case_id, evidence_id = _create_open_case_and_validate_evidence(
        client, auth_headers_io1, EICAR_CSV_BYTES, "cdr_malware.csv", "text/csv", "CDR_SPREADSHEET"
    )

    # Invoke MOD-07 scan on EICAR payload
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scan",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["verdict"] == "THREAT_DETECTED"
    assert data["status"] == "QUARANTINED"
    assert "EICAR" in (data["threat_name"] or "")


def test_get_scanned_contract_api_threat_quarantined_rejected(client, auth_headers_io1):
    case_id, evidence_id = _create_open_case_and_validate_evidence(
        client, auth_headers_io1, EICAR_CSV_BYTES, "blocked_malware.csv", "text/csv", "CDR_SPREADSHEET"
    )

    # Scan evidence -> Quarantined
    client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scan", headers=auth_headers_io1)

    # Downstream MOD-08 handoff contract MUST be rejected
    res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scanned-contract",
        headers=auth_headers_io1
    )
    assert res.status_code == 422
    err = res.json()
    assert err["error_code"] == "ANTIVIRUS_THREAT_DETECTED"


def test_scan_unvalidated_evidence_rejected_api(client, auth_headers_io1):
    """
    Cannot scan an evidence item that is still in REGISTERED_INTAKE (skipping MOD-06).
    """
    create_payload = {
        "title": "Unvalidated Evidence Case",
        "fir_metadata": {
            "fir_number": "FIR-AV-UNVAL-01",
            "police_station": "Central Crime Branch",
            "jurisdiction_code": "JUR-DEL-04"
        }
    }
    case_resp = client.post("/api/v1/cases", json=create_payload, headers=auth_headers_io1).json()
    case_id = case_resp["case_id"]

    client.post(f"/api/v1/cases/{case_id}/stage", json={"lifecycle_stage": "EVIDENCE_INGESTION"}, headers=auth_headers_io1)

    # Register only (no MOD-06 validation)
    files = {"file": ("unval.pdf", io.BytesIO(CLEAN_PDF_BYTES), "application/pdf")}
    data = {"evidence_category": "DOCUMENT_PDF", "declared_mime_type": "application/pdf"}
    ev_resp = client.post(f"/api/v1/cases/{case_id}/evidence", files=files, data=data, headers=auth_headers_io1).json()
    evidence_id = ev_resp["evidence_id"]

    # Attempting to scan before validation fails
    res = client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scan", headers=auth_headers_io1)
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.json()["error_code"] == "EVIDENCE_VALIDATION_FAILED"


def test_get_scanned_contract_before_scan_api(client, auth_headers_io1):
    """
    Cannot obtain ScannedEvidenceObject before running antivirus scan.
    """
    case_id, evidence_id = _create_open_case_and_validate_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "doc.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scanned-contract",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert res.json()["error_code"] == "ANTIVIRUS_SCAN_FAILED"


def test_scan_evidence_unauthorized_investigator(client, auth_headers_io1, auth_headers_io2):
    """
    IO2 cannot scan evidence on IO1's case.
    """
    case_id, evidence_id = _create_open_case_and_validate_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "private_doc.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scan",
        headers=auth_headers_io2
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_scan_evidence_unauthenticated(client, auth_headers_io1):
    case_id, evidence_id = _create_open_case_and_validate_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "doc.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    res = client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scan")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_scan_nonexistent_evidence_api(client, auth_headers_io1):
    create_payload = {
        "title": "Nonexistent Evidence Test",
        "fir_metadata": {
            "fir_number": "FIR-AV-NONE-01",
            "police_station": "Central Crime Branch",
            "jurisdiction_code": "JUR-DEL-04"
        }
    }
    case_resp = client.post("/api/v1/cases", json=create_payload, headers=auth_headers_io1).json()
    case_id = case_resp["case_id"]

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/NON-EXISTENT-EVID/scan",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND


def test_system_health_endpoint_includes_mod07(client):
    res = client.get("/health")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "MOD-07 Antivirus Scan" in data["modules"]
