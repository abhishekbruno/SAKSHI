"""
Integration tests for MOD-10 WORM Object Lock / Dual Storage REST API.

Tests HTTP endpoints:
    - POST /api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock
    - GET  /api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock-contract
    - GET  /health  (MOD-10 registration)

Tests:
    - Full pipeline POST success (MOD-05 → ... → MOD-09 → MOD-10)
    - ObjectLockResult response schema validation
    - ObjectLockedEvidenceObject contract retrieval
    - Unverified evidence rejected (400 INTEGRITY_NOT_VERIFIED_FOR_LOCK)
    - Contract before lock rejected (400 OBJECT_NOT_LOCKED)
    - Idempotency: second POST returns already_locked=True
    - GOVERNANCE vs COMPLIANCE lock_mode query parameter
    - Unauthorized access (403 Forbidden)
    - Unauthenticated access (401 Unauthorized)
    - objlock:// reference format validation
    - Integrity binding format validation
    - Health endpoint includes MOD-10
"""
import io
import hashlib
from fastapi import status


CLEAN_PDF_BYTES = b"%PDF-1.5 forensic object lock integration test\n%%EOF"


def _full_pipeline(
    client,
    auth_headers,
    file_bytes: bytes = CLEAN_PDF_BYTES,
    filename: str = "objlock_sample.pdf",
    mime: str = "application/pdf",
    category: str = "DOCUMENT_PDF",
    run_integrity: bool = True,
):
    """Helper: creates case, advances to EVIDENCE_INGESTION, runs MOD-05 → MOD-09."""
    case_resp = client.post(
        "/api/v1/cases",
        json={
            "title": "Object Lock Integration Test Case",
            "fir_metadata": {
                "fir_number": f"FIR-OL-{filename[:20]}",
                "police_station": "Forensic Bureau",
                "jurisdiction_code": "JUR-DEL-04",
            },
        },
        headers=auth_headers,
    ).json()
    case_id = case_resp["case_id"]

    # Advance to EVIDENCE_INGESTION
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

    # MOD-06: Validate
    r = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/validate",
        headers=auth_headers,
    )
    assert r.status_code == status.HTTP_200_OK

    # MOD-07: AV Scan
    r = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scan",
        headers=auth_headers,
    )
    assert r.status_code == status.HTTP_200_OK

    # MOD-08: WORM Commit
    r = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/worm-commit",
        headers=auth_headers,
    )
    assert r.status_code == status.HTTP_200_OK

    if run_integrity:
        # MOD-09: Dual Hash Integrity
        r = client.post(
            f"/api/v1/cases/{case_id}/evidence/{evidence_id}/integrity",
            headers=auth_headers,
        )
        assert r.status_code == status.HTTP_200_OK

    return case_id, evidence_id


# ─── Success Path ────────────────────────────────────────────────────────

def test_apply_object_lock_api_success(client, auth_headers_io1):
    """POST /object-lock succeeds after full MOD-05..MOD-09 pipeline."""
    case_id, evidence_id = _full_pipeline(client, auth_headers_io1, filename="api_lock_success.pdf")

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock",
        headers=auth_headers_io1,
    )
    assert res.status_code == status.HTTP_200_OK, res.text
    data = res.json()

    assert data["evidence_id"] == evidence_id
    assert data["case_id"] == case_id
    assert data["lock_status"] == "LOCKED"
    assert data["lock_mode"] == "GOVERNANCE"
    assert data["lock_storage_reference"].startswith("objlock://")
    assert data["lock_overwrite_protected"] is True
    assert data["lock_delete_protected"] is True
    assert data["lock_backend"] == "LOCAL_FILESYSTEM"
    assert data["already_locked"] is False
    assert data["lock_applied_at"] is not None
    assert data["lock_retention_until"] is not None


def test_apply_object_lock_api_reference_format(client, auth_headers_io1):
    """Lock reference has format: objlock://<case_id>/<sha256_64chars>+<sha3_prefix_16chars>."""
    expected_sha256 = hashlib.sha256(CLEAN_PDF_BYTES).hexdigest().lower()
    expected_sha3_prefix = hashlib.sha3_512(CLEAN_PDF_BYTES).hexdigest()[:16].lower()

    case_id, evidence_id = _full_pipeline(client, auth_headers_io1, filename="ref_format.pdf")
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock",
        headers=auth_headers_io1,
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    ref = data["lock_storage_reference"]
    # Should be objlock://<case_id>/<sha256>+<sha3_prefix16>
    assert ref.startswith(f"objlock://{case_id}/")
    digest_part = ref.split("/")[-1]
    assert "+" in digest_part
    sha256_part, sha3_part = digest_part.split("+")
    assert sha256_part == expected_sha256
    assert sha3_part == expected_sha3_prefix


def test_apply_object_lock_api_integrity_binding_format(client, auth_headers_io1):
    """Integrity binding: sha256:<val>:sha3_512:<val> — correct format and hash lengths."""
    case_id, evidence_id = _full_pipeline(client, auth_headers_io1, filename="binding_api.pdf")
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock",
        headers=auth_headers_io1,
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    binding = data["lock_integrity_binding"]
    assert binding.startswith("sha256:")
    parts = binding.split(":")
    assert len(parts) == 4
    assert len(parts[1]) == 64
    assert parts[2] == "sha3_512"
    assert len(parts[3]) == 128


def test_apply_object_lock_api_dual_hashes_correct(client, auth_headers_io1):
    """Lock result carries correct SHA-256 and SHA3-512 digests."""
    expected_sha256 = hashlib.sha256(CLEAN_PDF_BYTES).hexdigest().lower()
    expected_sha3_512 = hashlib.sha3_512(CLEAN_PDF_BYTES).hexdigest().lower()

    case_id, evidence_id = _full_pipeline(client, auth_headers_io1, filename="dual_hash_api.pdf")
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock",
        headers=auth_headers_io1,
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()

    assert data["checksum_sha256"] == expected_sha256
    assert data["checksum_sha3_512"] == expected_sha3_512


def test_apply_object_lock_governance_mode(client, auth_headers_io1):
    """Default lock_mode is GOVERNANCE."""
    case_id, evidence_id = _full_pipeline(client, auth_headers_io1, filename="governance_mode.pdf")
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock",
        params={"lock_mode": "GOVERNANCE"},
        headers=auth_headers_io1,
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["lock_mode"] == "GOVERNANCE"


def test_apply_object_lock_compliance_mode(client, auth_headers_io1):
    """COMPLIANCE lock mode is accepted and recorded correctly."""
    case_id, evidence_id = _full_pipeline(client, auth_headers_io1, filename="compliance_mode.pdf")
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock",
        params={"lock_mode": "COMPLIANCE"},
        headers=auth_headers_io1,
    )
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["lock_mode"] == "COMPLIANCE"


# ─── Object Lock Contract ────────────────────────────────────────────────

def test_get_object_lock_contract_api_success(client, auth_headers_io1):
    """GET /object-lock-contract returns full ObjectLockedEvidenceObject after lock."""
    expected_sha256 = hashlib.sha256(CLEAN_PDF_BYTES).hexdigest().lower()
    expected_sha3_512 = hashlib.sha3_512(CLEAN_PDF_BYTES).hexdigest().lower()

    case_id, evidence_id = _full_pipeline(client, auth_headers_io1, filename="contract_api.pdf")

    # First apply the lock
    lock_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock",
        headers=auth_headers_io1,
    )
    assert lock_res.status_code == status.HTTP_200_OK

    # Retrieve contract
    res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock-contract",
        headers=auth_headers_io1,
    )
    assert res.status_code == status.HTTP_200_OK, res.text
    contract = res.json()

    assert contract["evidence_id"] == evidence_id
    assert contract["case_id"] == case_id
    assert contract["lock_status"] == "LOCKED"
    assert contract["integrity_status"] == "VERIFIED"
    assert contract["source"] == "MOD-10"
    assert contract["lock_storage_reference"].startswith("objlock://")
    assert contract["worm_storage_reference"].startswith("worm://")
    assert contract["checksum_sha256"] == expected_sha256
    assert contract["checksum_sha3_512"] == expected_sha3_512
    assert contract["lock_overwrite_protected"] is True
    assert contract["lock_delete_protected"] is True
    assert "sha256:" in contract["lock_integrity_binding"]
    assert ":sha3_512:" in contract["lock_integrity_binding"]
    assert contract["lock_applied_at"] is not None
    assert contract["verified_at"] is not None


def test_get_object_lock_contract_before_lock_fails(client, auth_headers_io1):
    """GET /object-lock-contract before lock raises 400 OBJECT_NOT_LOCKED."""
    case_id, evidence_id = _full_pipeline(client, auth_headers_io1, filename="contract_before_lock.pdf")

    res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock-contract",
        headers=auth_headers_io1,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    err = res.json()
    assert err["error_code"] == "OBJECT_NOT_LOCKED"


# ─── Gate Enforcement ───────────────────────────────────────────────────

def test_object_lock_rejects_unverified_evidence_api(client, auth_headers_io1):
    """POST /object-lock without prior MOD-09 returns 400 INTEGRITY_NOT_VERIFIED_FOR_LOCK."""
    case_id, evidence_id = _full_pipeline(
        client, auth_headers_io1,
        filename="unverified_lock_api.pdf",
        run_integrity=False,  # Skip MOD-09
    )

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock",
        headers=auth_headers_io1,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    err = res.json()
    assert err["error_code"] == "INTEGRITY_NOT_VERIFIED_FOR_LOCK"


# ─── Idempotency ────────────────────────────────────────────────────────

def test_object_lock_idempotent_api(client, auth_headers_io1):
    """Second POST /object-lock returns already_locked=True and the same reference."""
    case_id, evidence_id = _full_pipeline(client, auth_headers_io1, filename="idem_api.pdf")

    res1 = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock",
        headers=auth_headers_io1,
    )
    assert res1.status_code == status.HTTP_200_OK
    assert res1.json()["already_locked"] is False

    res2 = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock",
        headers=auth_headers_io1,
    )
    assert res2.status_code == status.HTTP_200_OK
    assert res2.json()["already_locked"] is True
    assert res2.json()["lock_storage_reference"] == res1.json()["lock_storage_reference"]
    assert res2.json()["lock_integrity_binding"] == res1.json()["lock_integrity_binding"]


# ─── Authorization ───────────────────────────────────────────────────────

def test_object_lock_forbidden_for_unassigned_investigator(client, auth_headers_io1, auth_headers_io2):
    """Investigator not assigned to case gets 403 Forbidden."""
    case_id, evidence_id = _full_pipeline(client, auth_headers_io1, filename="forbidden_lock.pdf")

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock",
        headers=auth_headers_io2,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_object_lock_unauthenticated_rejected(client):
    """Unauthenticated request to /object-lock gets 401 Unauthorized."""
    res = client.post("/api/v1/cases/any-case/evidence/any-ev/object-lock")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_object_lock_contract_unauthenticated_rejected(client):
    """Unauthenticated request to /object-lock-contract gets 401 Unauthorized."""
    res = client.get("/api/v1/cases/any-case/evidence/any-ev/object-lock-contract")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_object_lock_contract_forbidden_for_unassigned_investigator(client, auth_headers_io1, auth_headers_io2):
    """GET /object-lock-contract returns 403 for unassigned investigator."""
    case_id, evidence_id = _full_pipeline(client, auth_headers_io1, filename="contract_403.pdf")
    client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock",
        headers=auth_headers_io1,
    )

    res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock-contract",
        headers=auth_headers_io2,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


# ─── Health Check ───────────────────────────────────────────────────────

def test_health_check_includes_mod10_api(client):
    """Health endpoint reports MOD-10 WORM Object Lock and version 0.4.0."""
    res = client.get("/health")
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert "MOD-10 WORM Object Lock / Dual Storage" in data["modules"]
    assert data["phase"] in {"03 - Security & Integrity", "04 - Secure RAG Retrieval"}
    assert data["version"] >= "0.4.0"
