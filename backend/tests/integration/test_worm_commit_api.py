"""
Integration tests for MOD-08 WORM Commit + Checksum REST API.
Tests HTTP endpoints:
- POST /api/v1/cases/{case_id}/evidence/{evidence_id}/worm-commit
- GET /api/v1/cases/{case_id}/evidence/{evidence_id}/worm-contract
- /health endpoint verification for MOD-08 inclusion
Tests clean commits, idempotent repeat commits, unscanned/quarantined rejections,
unauthorized / unauthenticated access, and Phase 3 downstream contract generation.
"""
import io
import hashlib
from fastapi import status
from app.services.antivirus_scan_service import EICAR_SIGNATURE

CLEAN_PDF_BYTES = b"%PDF-1.5 forensic report sample\n%%EOF"
CLEAN_CSV_BYTES = b"timestamp,caller,receiver\n2026-03-01,911,999\n"
EICAR_CSV_BYTES = CLEAN_CSV_BYTES + b"\n# TEST_PAYLOAD: " + EICAR_SIGNATURE + b"\n"


def _create_open_case_and_scan_evidence(
    client,
    auth_headers,
    file_bytes: bytes,
    filename: str,
    mime: str,
    category: str,
    perform_scan: bool = True
):
    """Helper that creates a case, advances to EVIDENCE_INGESTION, registers evidence, runs MOD-06 validation, and optionally MOD-07 scan."""
    create_payload = {
        "title": "Forensic WORM Commit Ingestion Case",
        "fir_metadata": {
            "fir_number": f"FIR-WORM-API-{filename}",
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

    # Antivirus scan (MOD-07)
    if perform_scan:
        scan_resp = client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scan", headers=auth_headers)
        assert scan_resp.status_code == status.HTTP_200_OK

    return case_id, evidence_id


def test_worm_commit_clean_evidence_api_success(client, auth_headers_io1):
    """Test successful WORM commitment and SHA-256 pre-hashing of clean scanned evidence."""
    case_id, evidence_id = _create_open_case_and_scan_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "forensic_exhibit.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    expected_sha256 = hashlib.sha256(CLEAN_PDF_BYTES).hexdigest().lower()

    # Invoke MOD-08 WORM commit
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/worm-commit",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    assert data["evidence_id"] == evidence_id
    assert data["case_id"] == case_id
    assert data["status"] == "COMMITTED"
    assert data["worm_status"] == "COMMITTED"
    assert data["checksum_algorithm"] == "SHA-256"
    assert data["checksum_sha256"] == expected_sha256
    assert data["worm_storage_reference"] == f"worm://{case_id}/{expected_sha256}"
    assert data["worm_committed_at"] is not None
    assert "committed" in data["message"].lower()


def test_get_worm_contract_api_success(client, auth_headers_io1):
    """Test exporting the WORMCommittedEvidenceObject downstream contract for Phase 3."""
    case_id, evidence_id = _create_open_case_and_scan_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "downstream_contract.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    expected_sha256 = hashlib.sha256(CLEAN_PDF_BYTES).hexdigest().lower()

    # Commit to WORM
    client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/worm-commit",
        headers=auth_headers_io1
    )

    # Fetch downstream Phase 3 contract
    res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/worm-contract",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_200_OK
    contract = res.json()

    assert contract["evidence_id"] == evidence_id
    assert contract["case_id"] == case_id
    assert contract["checksum_algorithm"] == "SHA-256"
    assert contract["checksum_sha256"] == expected_sha256
    assert contract["worm_storage_reference"] == f"worm://{case_id}/{expected_sha256}"
    assert contract["worm_status"] == "COMMITTED"
    assert contract["antivirus_verdict"] == "CLEAN"
    assert contract["antivirus_scanner"] == "EicarHeuristicScanner"
    assert contract["mime_status"] == "VALIDATED"


def test_get_worm_contract_before_commit_fails(client, auth_headers_io1):
    """Attempting to retrieve the WORM contract before WORM commitment must fail."""
    case_id, evidence_id = _create_open_case_and_scan_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "not_yet_committed.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/worm-contract",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    err = res.json()
    assert err["error_code"] == "EVIDENCE_NOT_COMMITTED"


def test_worm_commit_idempotent_api(client, auth_headers_io1):
    """Calling WORM commit a second time on committed evidence returns the existing commitment without error."""
    case_id, evidence_id = _create_open_case_and_scan_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "idempotent_sample.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    # First commit
    res1 = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/worm-commit",
        headers=auth_headers_io1
    )
    assert res1.status_code == status.HTTP_200_OK

    # Second commit (idempotent)
    res2 = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/worm-commit",
        headers=auth_headers_io1
    )
    assert res2.status_code == status.HTTP_200_OK
    assert res2.json()["checksum_sha256"] == res1.json()["checksum_sha256"]
    assert res2.json()["worm_storage_reference"] == res1.json()["worm_storage_reference"]
    assert res2.json()["already_committed"] is True


def test_worm_commit_unscanned_evidence_rejected_api(client, auth_headers_io1):
    """Evidence validated by MOD-06 but NOT scanned by MOD-07 must be rejected by MOD-08."""
    case_id, evidence_id = _create_open_case_and_scan_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "unscanned.pdf", "application/pdf", "DOCUMENT_PDF",
        perform_scan=False
    )

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/worm-commit",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    err = res.json()
    assert err["error_code"] == "EVIDENCE_NOT_SCANNED"


def test_worm_commit_quarantined_evidence_rejected_api(client, auth_headers_io1):
    """Evidence containing malware flagged as QUARANTINED by MOD-07 must be rejected by MOD-08."""
    case_id, evidence_id = _create_open_case_and_scan_evidence(
        client, auth_headers_io1, EICAR_CSV_BYTES, "eicar_infected.csv", "text/csv", "CDR_SPREADSHEET",
        perform_scan=True
    )

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/worm-commit",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY or res.status_code == 422
    err = res.json()
    assert err["error_code"] == "ANTIVIRUS_THREAT_DETECTED"


def test_worm_commit_unauthorized_investigator_forbidden(client, auth_headers_io1, auth_headers_io2):
    """An investigator not assigned to the case cannot commit evidence to WORM."""
    case_id, evidence_id = _create_open_case_and_scan_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "auth_check.pdf", "application/pdf", "DOCUMENT_PDF"
    )

    # Attempt commit by io2 (different jurisdiction and unassigned)
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/worm-commit",
        headers=auth_headers_io2
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_worm_commit_unauthenticated_rejected(client):
    """Commit without credentials must return 401 Unauthorized."""
    res = client.post("/api/v1/cases/any-case/evidence/any-ev/worm-commit")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_health_check_includes_mod08(client):
    """Verify system health check endpoint reports MOD-08 WORM Commit + Checksum."""
    res = client.get("/health")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "MOD-08 WORM Commit + Checksum" in data["modules"]
