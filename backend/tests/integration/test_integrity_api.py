"""
Integration tests for MOD-09 Dual Hashing (SHA-256 + SHA3-512) & Integrity Verification REST API.
Tests HTTP endpoints:
- POST /api/v1/cases/{case_id}/evidence/{evidence_id}/integrity
- GET /api/v1/cases/{case_id}/evidence/{evidence_id}/integrity-contract
- /health endpoint verification for MOD-09 and Phase 3 inclusion
Tests end-to-end progression from MOD-05 -> MOD-06 -> MOD-07 -> MOD-08 -> MOD-09,
tampering detection, uncommitted rejection, downstream contract export, idempotency,
unauthorized/unauthenticated access, and error cases.
"""
import io
import os
import hashlib
from fastapi import status

CLEAN_PDF_BYTES = b"%PDF-1.5 forensic dual hash sample\n%%EOF"


def _create_open_case_and_commit_evidence(
    client,
    auth_headers,
    file_bytes: bytes = CLEAN_PDF_BYTES,
    filename: str = "integrity_sample.pdf",
    mime: str = "application/pdf",
    category: str = "DOCUMENT_PDF",
    commit_to_worm: bool = True
):
    """Helper that creates a case, advances to EVIDENCE_INGESTION, registers evidence, validates MIME, scans AV, and optionally commits to WORM."""
    create_payload = {
        "title": "Forensic Dual Hashing Ingestion Case",
        "fir_metadata": {
            "fir_number": f"FIR-INT-API-{filename}",
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

    # Scan evidence (MOD-07)
    scan_resp = client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scan", headers=auth_headers)
    assert scan_resp.status_code == status.HTTP_200_OK

    # Commit to WORM (MOD-08)
    if commit_to_worm:
        worm_resp = client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/worm-commit", headers=auth_headers)
        assert worm_resp.status_code == status.HTTP_200_OK

    return case_id, evidence_id


def test_dual_hash_integrity_verification_api_success(client, auth_headers_io1):
    """Full MOD-08 -> MOD-09 pipeline verification over clean WORM-committed evidence."""
    case_id, evidence_id = _create_open_case_and_commit_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "test_dual_hash.pdf"
    )

    expected_sha256 = hashlib.sha256(CLEAN_PDF_BYTES).hexdigest().lower()
    expected_sha3_512 = hashlib.sha3_512(CLEAN_PDF_BYTES).hexdigest().lower()

    # Invoke MOD-09 Dual Hashing & Integrity Verification
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/integrity",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    assert data["evidence_id"] == evidence_id
    assert data["case_id"] == case_id
    assert data["integrity_status"] == "VERIFIED"
    assert data["checksum_sha256"] == expected_sha256
    assert data["checksum_sha3_512"] == expected_sha3_512
    assert len(data["checksum_sha3_512"]) == 128
    assert data["sha256_matched"] is True
    assert data["already_verified"] is False
    assert data["worm_storage_reference"] == f"worm://{case_id}/{expected_sha256}"


def test_get_integrity_contract_api_success(client, auth_headers_io1):
    """Exporting the formal IntegrityProtectedEvidenceObject handoff contract."""
    case_id, evidence_id = _create_open_case_and_commit_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "contract_export.pdf"
    )

    expected_sha256 = hashlib.sha256(CLEAN_PDF_BYTES).hexdigest().lower()
    expected_sha3_512 = hashlib.sha3_512(CLEAN_PDF_BYTES).hexdigest().lower()

    # First verify integrity
    client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/integrity",
        headers=auth_headers_io1
    )

    # Fetch downstream contract
    res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/integrity-contract",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_200_OK
    contract = res.json()

    assert contract["evidence_id"] == evidence_id
    assert contract["case_id"] == case_id
    assert contract["integrity_status"] == "VERIFIED"
    assert contract["checksum_sha256"] == expected_sha256
    assert contract["checksum_sha3_512"] == expected_sha3_512
    assert contract["source"] == "MOD-09"
    assert contract["worm_storage_reference"] == f"worm://{case_id}/{expected_sha256}"


def test_get_integrity_contract_before_verification_fails(client, auth_headers_io1):
    """Attempting to retrieve the integrity contract before verification fails with 400 Bad Request."""
    case_id, evidence_id = _create_open_case_and_commit_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "unverified_contract.pdf"
    )

    res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/integrity-contract",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    err = res.json()
    assert err["error_code"] == "INTEGRITY_NOT_VERIFIED"


def test_dual_hash_integrity_tampering_detection_api(client, auth_headers_io1, db_session):
    """If payload is altered after WORM commitment, MOD-09 rejects with 422 SHA256_INTEGRITY_MISMATCH."""
    case_id, evidence_id = _create_open_case_and_commit_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "tampered_api.pdf"
    )

    # Retrieve physical file path from DB and tamper with it
    from app.repositories.evidence_repository import EvidenceRepository
    repo = EvidenceRepository(db_session)
    ev = repo.get_by_evidence_id(evidence_id)
    with open(ev.raw_storage_path, "wb") as f:
        f.write(b"%PDF-1.5 TAMPERED PAYLOAD CORRUPTED FOR FORENSIC TEST")

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/integrity",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY or res.status_code == 422
    err = res.json()
    assert err["error_code"] == "SHA256_INTEGRITY_MISMATCH"


def test_dual_hash_uncommitted_evidence_rejected_api(client, auth_headers_io1):
    """Calling integrity verification on evidence that has NOT been WORM committed fails with 400."""
    case_id, evidence_id = _create_open_case_and_commit_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "not_worm_committed.pdf",
        commit_to_worm=False
    )

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/integrity",
        headers=auth_headers_io1
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    err = res.json()
    assert err["error_code"] == "EVIDENCE_NOT_WORM_COMMITTED"


def test_dual_hash_idempotent_repeated_api(client, auth_headers_io1):
    """Calling integrity endpoint a second time returns existing verified status."""
    case_id, evidence_id = _create_open_case_and_commit_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "idempotent_api.pdf"
    )

    res1 = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/integrity",
        headers=auth_headers_io1
    )
    assert res1.status_code == status.HTTP_200_OK
    assert res1.json()["already_verified"] is False

    res2 = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/integrity",
        headers=auth_headers_io1
    )
    assert res2.status_code == status.HTTP_200_OK
    assert res2.json()["already_verified"] is True
    assert res2.json()["checksum_sha3_512"] == res1.json()["checksum_sha3_512"]


def test_dual_hash_unauthorized_investigator_forbidden(client, auth_headers_io1, auth_headers_io2):
    """Unassigned investigator in differing jurisdiction is denied with 403 Forbidden."""
    case_id, evidence_id = _create_open_case_and_commit_evidence(
        client, auth_headers_io1, CLEAN_PDF_BYTES, "unauth_api.pdf"
    )

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/integrity",
        headers=auth_headers_io2
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_dual_hash_unauthenticated_rejected(client):
    """Calling integrity verification without credentials returns 401 Unauthorized."""
    res = client.post("/api/v1/cases/any-case/evidence/any-ev/integrity")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_system_health_endpoint_includes_mod09_and_phase3(client):
    """Verify health check reports Phase 3 and MOD-09 Dual Hashing."""
    res = client.get("/health")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["phase"] in {"03 - Security & Integrity", "04 - Secure RAG Retrieval"}
    assert "MOD-09 Dual Hashing (SHA-256 + SHA3-512)" in data["modules"]
