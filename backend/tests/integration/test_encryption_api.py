"""
Integration tests for MOD-11 AES-256-GCM Encryption REST API.

Tests HTTP endpoints:
    - POST /api/v1/cases/{case_id}/evidence/{evidence_id}/encrypt
    - GET  /api/v1/cases/{case_id}/evidence/{evidence_id}/encryption-contract
    - POST /api/v1/cases/{case_id}/evidence/{evidence_id}/verify-encryption
    - GET  /health (MOD-11 registration & version 0.5.0)

Coverage:
    1. Full pipeline success: MOD-05 → MOD-06 → MOD-07 → MOD-08 → MOD-09 → MOD-10 → MOD-11.
    2. EncryptionResult schema validation.
    3. EncryptedEvidenceObject contract retrieval for MOD-12.
    4. Contract before encryption rejected (400 EVIDENCE_NOT_ENCRYPTED).
    5. Gate enforcement: Unlocked evidence rejected (400 OBJECT_NOT_LOCKED_FOR_ENCRYPTION).
    6. Idempotency: Second POST /encrypt returns already_encrypted=True with identical references.
    7. POST /verify-encryption returns 200 VERIFIED with tag_valid=True and dual_hash_matched=True.
    8. Tamper detection: File corruption triggers 422 ENCRYPTION_TAMPER_DETECTED.
    9. RBAC: Unauthorized investigator rejected with 403 Forbidden.
    10. RBAC: Supervisor authorized with 200 OK.
    11. 404 Not Found on invalid case or evidence ID.
    12. Health check endpoint reports MOD-11 active.
"""
import io
import os
import stat
import hashlib
from fastapi import status


CLEAN_PDF_BYTES = b"%PDF-1.5 forensic encryption integration test\n%%EOF"


def _full_pipeline_to_object_lock(
    client,
    auth_headers,
    file_bytes: bytes = CLEAN_PDF_BYTES,
    filename: str = "enc_sample.pdf",
    mime: str = "application/pdf",
    category: str = "DOCUMENT_PDF",
    run_lock: bool = True,
):
    """Helper: creates case, advances to EVIDENCE_INGESTION, runs MOD-05 → MOD-10."""
    case_resp = client.post(
        "/api/v1/cases",
        json={
            "title": "AES Encryption Integration Test Case",
            "fir_metadata": {
                "fir_number": f"FIR-ENC-{filename[:18]}",
                "police_station": "Special Cyber Cell",
                "jurisdiction_code": "JUR-DEL-04",
            },
        },
        headers=auth_headers,
    ).json()
    case_id = case_resp["case_id"]

    # Stage Engine: Advance to EVIDENCE_INGESTION
    client.post(
        f"/api/v1/cases/{case_id}/stage",
        json={"lifecycle_stage": "EVIDENCE_INGESTION"},
        headers=auth_headers,
    )

    # MOD-05: Register
    files = {"file": (filename, io.BytesIO(file_bytes), mime)}
    data = {"evidence_category": category, "declared_mime_type": mime}
    ev_resp = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files=files, data=data, headers=auth_headers,
    ).json()
    evidence_id = ev_resp["evidence_id"]

    # MOD-06: MIME Validation
    r = client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/validate", headers=auth_headers)
    assert r.status_code == status.HTTP_200_OK

    # MOD-07: AV Scan
    r = client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scan", headers=auth_headers)
    assert r.status_code == status.HTTP_200_OK

    # MOD-08: WORM Commit
    r = client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/worm-commit", headers=auth_headers)
    assert r.status_code == status.HTTP_200_OK

    # MOD-09: Dual Hash Integrity
    r = client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/integrity", headers=auth_headers)
    assert r.status_code == status.HTTP_200_OK

    if run_lock:
        # MOD-10: WORM Object Lock
        r = client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock",
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_200_OK

    return case_id, evidence_id


# ═══════════════════════════════════════════════════════════════════════════
# Test 1: Full Pipeline Encryption Success (POST /encrypt)
# ═══════════════════════════════════════════════════════════════════════════

def test_encrypt_evidence_endpoint_success(client, auth_headers_io1):
    case_id, evidence_id = _full_pipeline_to_object_lock(client, auth_headers_io1)

    r = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/encrypt",
        headers=auth_headers_io1,
    )

    assert r.status_code == status.HTTP_200_OK
    data = r.json()

    assert data["evidence_id"] == evidence_id
    assert data["case_id"] == case_id
    assert data["encryption_status"] == "ENCRYPTED"
    assert data["encryption_algorithm"] == "AES-256-GCM"
    assert data["already_encrypted"] is False
    assert data["encryption_storage_reference"].startswith(f"enc://{case_id}/")
    assert data["key_reference"] == f"localkms://cases/{case_id}/keys/aes-256-v1"
    assert data["key_provider"] == "LOCAL_DEV_KEY_PROVIDER"
    assert len(data["nonce_hex"]) == 24
    assert len(data["auth_tag_hex"]) == 32
    assert len(data["ciphertext_sha256"]) == 64
    assert data["file_size_bytes"] == len(CLEAN_PDF_BYTES)
    assert data["encrypted_file_size_bytes"] == len(CLEAN_PDF_BYTES) + 16
    assert data["lock_storage_reference"].startswith("objlock://")
    assert "sha256=" in data["aad_binding"]


# ═══════════════════════════════════════════════════════════════════════════
# Test 2: Idempotency (Second POST /encrypt)
# ═══════════════════════════════════════════════════════════════════════════

def test_encrypt_evidence_endpoint_idempotency(client, auth_headers_io1):
    case_id, evidence_id = _full_pipeline_to_object_lock(client, auth_headers_io1)

    r1 = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/encrypt",
        headers=auth_headers_io1,
    )
    assert r1.status_code == status.HTTP_200_OK
    data1 = r1.json()

    r2 = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/encrypt",
        headers=auth_headers_io1,
    )
    assert r2.status_code == status.HTTP_200_OK
    data2 = r2.json()

    assert data2["already_encrypted"] is True
    assert data2["encryption_storage_reference"] == data1["encryption_storage_reference"]
    assert data2["nonce_hex"] == data1["nonce_hex"]
    assert data2["auth_tag_hex"] == data1["auth_tag_hex"]
    assert data2["ciphertext_sha256"] == data1["ciphertext_sha256"]


# ═══════════════════════════════════════════════════════════════════════════
# Test 3: Downstream Contract Retrieval (GET /encryption-contract)
# ═══════════════════════════════════════════════════════════════════════════

def test_get_encryption_contract_endpoint(client, auth_headers_io1):
    case_id, evidence_id = _full_pipeline_to_object_lock(client, auth_headers_io1)

    # Encrypt
    client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/encrypt", headers=auth_headers_io1)

    # Retrieve Contract
    r = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/encryption-contract",
        headers=auth_headers_io1,
    )

    assert r.status_code == status.HTTP_200_OK
    contract = r.json()

    assert contract["source"] == "MOD-11"
    assert contract["case_id"] == case_id
    assert contract["evidence_id"] == evidence_id
    assert contract["encryption_status"] == "ENCRYPTED"
    assert contract["encryption_algorithm"] == "AES-256-GCM"
    assert contract["lock_storage_reference"].startswith("objlock://")
    assert contract["worm_storage_reference"].startswith("worm://")
    assert contract["encryption_storage_reference"].startswith(f"enc://{case_id}/")
    assert len(contract["nonce_hex"]) == 24
    assert len(contract["auth_tag_hex"]) == 32
    assert len(contract["ciphertext_sha256"]) == 64


# ═══════════════════════════════════════════════════════════════════════════
# Test 4: Gate Enforcement (Unlocked Evidence Rejected)
# ═══════════════════════════════════════════════════════════════════════════

def test_encrypt_unlocked_evidence_rejected(client, auth_headers_io1):
    # Pipeline without MOD-10
    case_id, evidence_id = _full_pipeline_to_object_lock(
        client, auth_headers_io1, run_lock=False
    )

    r = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/encrypt",
        headers=auth_headers_io1,
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    err = r.json()
    assert err["error_code"] == "OBJECT_NOT_LOCKED_FOR_ENCRYPTION"


# ═══════════════════════════════════════════════════════════════════════════
# Test 5: Contract Before Encryption Rejected (400)
# ═══════════════════════════════════════════════════════════════════════════

def test_contract_before_encryption_rejected(client, auth_headers_io1):
    case_id, evidence_id = _full_pipeline_to_object_lock(client, auth_headers_io1)

    r = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/encryption-contract",
        headers=auth_headers_io1,
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    err = r.json()
    assert err["error_code"] == "EVIDENCE_NOT_ENCRYPTED"


# ═══════════════════════════════════════════════════════════════════════════
# Test 6: POST /verify-encryption Success
# ═══════════════════════════════════════════════════════════════════════════

def test_verify_encryption_endpoint_success(client, auth_headers_io1):
    case_id, evidence_id = _full_pipeline_to_object_lock(client, auth_headers_io1)
    client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/encrypt", headers=auth_headers_io1)

    r = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/verify-encryption",
        headers=auth_headers_io1,
    )
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["verification_status"] == "VERIFIED"
    assert data["tag_valid"] is True
    assert data["ciphertext_integrity_matched"] is True
    assert data["dual_hash_integrity_matched"] is True


# ═══════════════════════════════════════════════════════════════════════════
# Test 7: Tamper Detection via API (422)
# ═══════════════════════════════════════════════════════════════════════════

def test_verify_encryption_tamper_detected(client, auth_headers_io1, db_session):
    from app.models.evidence import Evidence

    case_id, evidence_id = _full_pipeline_to_object_lock(client, auth_headers_io1)
    client.post(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/encrypt", headers=auth_headers_io1)

    # Locate encrypted file from DB and tamper with it
    ev = db_session.query(Evidence).filter(Evidence.evidence_id == evidence_id).one()
    enc_path = ev.encrypted_file_path

    with open(enc_path, "rb") as f:
        data = bytearray(f.read())
    data[10] ^= 0xEE  # Flip bit

    os.chmod(enc_path, stat.S_IWRITE)
    with open(enc_path, "wb") as f:
        f.write(data)
    os.chmod(enc_path, stat.S_IREAD)

    r = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/verify-encryption",
        headers=auth_headers_io1,
    )
    assert r.status_code == getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
    err = r.json()
    assert err["error_code"] == "ENCRYPTION_TAMPER_DETECTED"


# ═══════════════════════════════════════════════════════════════════════════
# Test 8: RBAC Authorization (Unauthorized IO Rejected)
# ═══════════════════════════════════════════════════════════════════════════

def test_encrypt_unauthorized_investigator_rejected(client, auth_headers_io1, auth_headers_io2):
    case_id, evidence_id = _full_pipeline_to_object_lock(client, auth_headers_io1)

    # IO2 attempts to encrypt IO1's case evidence
    r = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/encrypt",
        headers=auth_headers_io2,
    )
    assert r.status_code == status.HTTP_403_FORBIDDEN


# ═══════════════════════════════════════════════════════════════════════════
# Test 9: RBAC Supervisor Authorized
# ═══════════════════════════════════════════════════════════════════════════

def test_encrypt_supervisor_authorized(client, auth_headers_io1, auth_headers_supervisor):
    case_id, evidence_id = _full_pipeline_to_object_lock(client, auth_headers_io1)

    # Supervisor can encrypt evidence across jurisdictions
    r = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/encrypt",
        headers=auth_headers_supervisor,
    )
    assert r.status_code == status.HTTP_200_OK
    assert r.json()["encryption_status"] == "ENCRYPTED"


# ═══════════════════════════════════════════════════════════════════════════
# Test 10: 404 for Non-Existent Case / Evidence
# ═══════════════════════════════════════════════════════════════════════════

def test_encrypt_not_found(client, auth_headers_io1):
    r = client.post(
        "/api/v1/cases/NON-EXISTENT-CASE/evidence/NON-EXISTENT-EVID/encrypt",
        headers=auth_headers_io1,
    )
    assert r.status_code == status.HTTP_404_NOT_FOUND


# ═══════════════════════════════════════════════════════════════════════════
# Test 11: Health Check Endpoint Reports MOD-11
# ═══════════════════════════════════════════════════════════════════════════

def test_health_check_includes_mod11(client):
    r = client.get("/health")
    assert r.status_code == status.HTTP_200_OK
    data = r.json()
    assert data["version"] in {"0.5.0", "0.6.0"}
    assert "MOD-11 AES-256-GCM Encryption" in data["modules"]
