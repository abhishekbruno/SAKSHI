"""
Integration tests for Evidence Pipeline REST API (/api/v1/cases/{case_id}/evidence/pipeline).
Validates end-to-end execution through MOD-05 to MOD-08, error handling,
authentication, authorization, retry/resume safety, and backward compatibility.
"""
import io
import json
import logging
from unittest.mock import patch
from fastapi import status

from app.core.logging import StructuredJsonFormatter
from app.services.antivirus_scan_service import EICAR_SIGNATURE, EicarHeuristicScanner


CLEAN_PDF = b"%PDF-1.4 simulated clean autopsy report\n%%EOF"


def _create_and_open_case(client, auth_headers):
    """Helper to create a case and advance it to EVIDENCE_INGESTION stage."""
    create_payload = {
        "title": "Forensic Evidence Pipeline Case",
        "fir_metadata": {
            "fir_number": "FIR-PIPELINE-TEST-01",
            "police_station": "Central Cyber Crime Cell",
            "jurisdiction_code": "JUR-DEL-04",
        },
    }
    case_resp = client.post("/api/v1/cases", json=create_payload, headers=auth_headers).json()
    case_id = case_resp["case_id"]

    stage_resp = client.post(
        f"/api/v1/cases/{case_id}/stage",
        json={"lifecycle_stage": "EVIDENCE_INGESTION"},
        headers=auth_headers,
    )
    assert stage_resp.status_code == status.HTTP_200_OK
    return case_id


def test_pipeline_api_full_execution_success(client, auth_headers_io1):
    case_id = _create_and_open_case(client, auth_headers_io1)

    files = {
        "file": ("autopsy_report.pdf", io.BytesIO(CLEAN_PDF), "application/pdf"),
    }
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
        "collection_location": "District Hospital Mortuary",
        "source_device_or_person": "Dr. R. K. Sen",
        "description": "Post-mortem forensic report",
    }

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/pipeline",
        files=files,
        data=data,
        headers=auth_headers_io1,
    )

    assert res.status_code == status.HTTP_201_CREATED
    payload = res.json()
    assert payload["case_id"] == case_id
    assert payload["evidence_id"].startswith("SAKSHI-EVID-")
    assert payload["overall_status"] == "SUCCESS"
    assert payload["current_stage"] == "OBJECT_LOCK"
    assert payload["completed_stages"] == [
        "INTAKE",
        "MIME_VALIDATION",
        "ANTIVIRUS_SCAN",
        "WORM_COMMIT",
        "DUAL_HASHING",
        "OBJECT_LOCK",
    ]
    assert payload["intake_status"] == "COMMITTED"
    assert payload["worm_storage_reference"].startswith(f"worm://{case_id}/")
    assert payload["checksum_sha256"] is not None
    assert payload["checksum_sha3_512"] is not None
    assert payload["lock_storage_reference"].startswith(f"objlock://{case_id}/")
    assert payload["integrity_status"] == "VERIFIED"
    assert payload["lock_status"] == "LOCKED"
    assert payload["is_retryable"] is False
    assert payload["already_committed"] is False

    # Verify evidence item is cataloged and retrievable via GET
    get_res = client.get(
        f"/api/v1/cases/{case_id}/evidence/{payload['evidence_id']}",
        headers=auth_headers_io1,
    )
    assert get_res.status_code == status.HTTP_200_OK
    ev = get_res.json()
    assert ev["status"] == "COMMITTED"
    assert ev["worm_status"] == "COMMITTED"


def test_pipeline_api_unauthenticated_rejected(client, auth_headers_io1):
    case_id = _create_and_open_case(client, auth_headers_io1)

    files = {
        "file": ("evidence.pdf", io.BytesIO(CLEAN_PDF), "application/pdf"),
    }
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
    }

    # No auth headers
    res = client.post(f"/api/v1/cases/{case_id}/evidence/pipeline", files=files, data=data)
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_pipeline_api_unauthorized_investigator_forbidden(client, auth_headers_io1, auth_headers_io2):
    case_id = _create_and_open_case(client, auth_headers_io1)

    files = {
        "file": ("evidence.pdf", io.BytesIO(CLEAN_PDF), "application/pdf"),
    }
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
    }

    # IO2 calling IO1's case
    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/pipeline",
        files=files,
        data=data,
        headers=auth_headers_io2,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_pipeline_api_mime_rejection(client, auth_headers_io1):
    case_id = _create_and_open_case(client, auth_headers_io1)

    files = {
        "file": ("fake.pdf", io.BytesIO(b"Plain text masquerading as PDF"), "application/pdf"),
    }
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
    }

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/pipeline",
        files=files,
        data=data,
        headers=auth_headers_io1,
    )

    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    payload = res.json()
    assert payload["overall_status"] == "MIME_VALIDATION_FAILED"
    assert payload["current_stage"] == "MIME_VALIDATION"
    assert payload["completed_stages"] == ["INTAKE"]
    assert payload["intake_status"] == "REJECTED"


def test_pipeline_api_malware_quarantined(client, auth_headers_io1):
    case_id = _create_and_open_case(client, auth_headers_io1)

    files = {
        "file": ("infected.pdf", io.BytesIO(CLEAN_PDF + EICAR_SIGNATURE), "application/pdf"),
    }
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
    }

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/pipeline",
        files=files,
        data=data,
        headers=auth_headers_io1,
    )

    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    payload = res.json()
    assert payload["overall_status"] == "ANTIVIRUS_QUARANTINED"
    assert payload["current_stage"] == "ANTIVIRUS_SCAN"
    assert payload["completed_stages"] == ["INTAKE", "MIME_VALIDATION"]
    assert payload["intake_status"] == "QUARANTINED"
    assert payload["worm_storage_reference"] is None


def test_pipeline_api_resume_completed_evidence(client, auth_headers_io1):
    case_id = _create_and_open_case(client, auth_headers_io1)

    files = {
        "file": ("report.pdf", io.BytesIO(CLEAN_PDF), "application/pdf"),
    }
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
    }

    first_run = client.post(
        f"/api/v1/cases/{case_id}/evidence/pipeline",
        files=files,
        data=data,
        headers=auth_headers_io1,
    ).json()
    evidence_id = first_run["evidence_id"]

    # Safe resume call specifying evidence_id only
    resume_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/pipeline",
        data={"evidence_id": evidence_id},
        headers=auth_headers_io1,
    )

    assert resume_res.status_code == status.HTTP_200_OK
    resumed_payload = resume_res.json()
    assert resumed_payload["overall_status"] == "SUCCESS"
    assert resumed_payload["current_stage"] == "OBJECT_LOCK"
    assert resumed_payload["evidence_id"] == evidence_id
    assert resumed_payload["already_committed"] is True
    assert resumed_payload["completed_stages"] == [
        "INTAKE",
        "MIME_VALIDATION",
        "ANTIVIRUS_SCAN",
        "WORM_COMMIT",
        "DUAL_HASHING",
        "OBJECT_LOCK",
    ]


def test_pipeline_api_resume_rejects_second_payload(client, auth_headers_io1):
    case_id = _create_and_open_case(client, auth_headers_io1)

    # Calling resume with both evidence_id and a new file must be rejected
    files = {
        "file": ("second_file.pdf", io.BytesIO(CLEAN_PDF), "application/pdf"),
    }
    data = {
        "evidence_id": "SAKSHI-EVID-EXISTING",
    }

    res = client.post(
        f"/api/v1/cases/{case_id}/evidence/pipeline",
        files=files,
        data=data,
        headers=auth_headers_io1,
    )

    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_pipeline_api_retryable_operational_failure(client, auth_headers_io1):
    case_id = _create_and_open_case(client, auth_headers_io1)

    files = {
        "file": ("report.pdf", io.BytesIO(CLEAN_PDF), "application/pdf"),
    }
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
    }

    # Simulate antivirus timeout
    with patch(
        "app.services.antivirus_scan_service.get_configured_scanner",
        return_value=EicarHeuristicScanner(simulate_timeout=True),
    ):
        res = client.post(
            f"/api/v1/cases/{case_id}/evidence/pipeline",
            files=files,
            data=data,
            headers=auth_headers_io1,
        )

    assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    payload = res.json()
    assert payload["overall_status"] == "RETRYABLE_ERROR"
    assert payload["is_retryable"] is True
    assert payload["current_stage"] == "ANTIVIRUS_SCAN"
    assert payload["evidence_id"] is not None


def test_backward_compatibility_individual_evidence_endpoints(client, auth_headers_io1):
    """Ensure the existing individual MOD-05 through MOD-08 endpoints still function."""
    case_id = _create_and_open_case(client, auth_headers_io1)

    # 1. Individual intake (MOD-05)
    files = {
        "file": ("exhibit.pdf", io.BytesIO(CLEAN_PDF), "application/pdf"),
    }
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
        "description": "Individual step test",
    }
    intake_res = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        files=files,
        data=data,
        headers=auth_headers_io1,
    )
    assert intake_res.status_code == status.HTTP_201_CREATED
    evidence_id = intake_res.json()["evidence_id"]

    # 2. Individual MIME validation (MOD-06)
    mime_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/validate",
        headers=auth_headers_io1,
    )
    assert mime_res.status_code == status.HTTP_200_OK
    assert mime_res.json()["valid"] is True

    # 3. Individual Antivirus scan (MOD-07)
    av_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/scan",
        headers=auth_headers_io1,
    )
    assert av_res.status_code == status.HTTP_200_OK
    assert av_res.json()["verdict"] == "CLEAN"

    # 4. Individual WORM commit (MOD-08)
    worm_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/worm-commit",
        headers=auth_headers_io1,
    )
    assert worm_res.status_code == status.HTTP_200_OK
    assert worm_res.json()["worm_status"] == "COMMITTED"

    # 5. Individual Dual Hashing (MOD-09)
    integrity_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/integrity",
        headers=auth_headers_io1,
    )
    assert integrity_res.status_code == status.HTTP_200_OK
    assert integrity_res.json()["integrity_status"] == "VERIFIED"
    assert integrity_res.json()["checksum_sha3_512"] is not None

    # 6. Individual Object Lock (MOD-10)
    lock_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/object-lock",
        headers=auth_headers_io1,
    )
    assert lock_res.status_code == status.HTTP_200_OK
    assert lock_res.json()["lock_status"] == "LOCKED"
    assert lock_res.json()["lock_storage_reference"].startswith(f"objlock://{case_id}/")



def test_pipeline_audit_logging_no_raw_payload_leak(client, auth_headers_io1, caplog):
    case_id = _create_and_open_case(client, auth_headers_io1)

    secret_marker = b"VERY_SECRET_FORENSIC_EVIDENCE_PAYLOAD_CONTENT"
    file_content = CLEAN_PDF + secret_marker
    files = {
        "file": ("secret_report.pdf", io.BytesIO(file_content), "application/pdf"),
    }
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
    }

    with caplog.at_level(logging.INFO):
        res = client.post(
            f"/api/v1/cases/{case_id}/evidence/pipeline",
            files=files,
            data=data,
            headers=auth_headers_io1,
        )

    assert res.status_code == status.HTTP_201_CREATED
    # Verify no log record leaked the raw binary or secret marker
    for record in caplog.records:
        message = record.getMessage()
        assert "VERY_SECRET_FORENSIC_EVIDENCE_PAYLOAD_CONTENT" not in message
        if hasattr(record, "extra_data") and record.extra_data:
            assert "VERY_SECRET_FORENSIC_EVIDENCE_PAYLOAD_CONTENT" not in str(record.extra_data)


def test_pipeline_api_sha256_mismatch_fails_closed(client, auth_headers_io1):
    case_id = _create_and_open_case(client, auth_headers_io1)

    files = {
        "file": ("evidence.pdf", io.BytesIO(CLEAN_PDF), "application/pdf"),
    }
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
    }

    from app.core.errors import SHA256IntegrityMismatchException
    with patch(
        "app.services.integrity_service.compute_dual_hashes",
        return_value=("mismatched_sha256_hash", "computed_sha3_512_hash"),
    ):
        res = client.post(
            f"/api/v1/cases/{case_id}/evidence/pipeline",
            files=files,
            data=data,
            headers=auth_headers_io1,
        )

    assert res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    payload = res.json()
    assert payload["overall_status"] == "INTEGRITY_FAILED"
    assert payload["current_stage"] == "DUAL_HASHING"
    assert payload["is_retryable"] is False
    assert "OBJECT_LOCK" not in payload["completed_stages"]
    evidence_id = payload["evidence_id"]

    # Resume must also return 422 INTEGRITY_FAILED and not proceed
    resume_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/pipeline",
        data={"evidence_id": evidence_id},
        headers=auth_headers_io1,
    )
    assert resume_res.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    resumed_payload = resume_res.json()
    assert resumed_payload["overall_status"] == "INTEGRITY_FAILED"
    assert resumed_payload["current_stage"] == "DUAL_HASHING"


def test_pipeline_api_transient_mod09_and_mod10_recovery(client, auth_headers_io1):
    case_id = _create_and_open_case(client, auth_headers_io1)

    files = {
        "file": ("retry_report.pdf", io.BytesIO(CLEAN_PDF), "application/pdf"),
    }
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
    }

    # Simulate transient MOD-09 I/O failure
    with patch(
        "app.services.integrity_service.IntegrityService.verify_and_compute_integrity",
        side_effect=IOError("Transient storage bus busy"),
    ):
        res = client.post(
            f"/api/v1/cases/{case_id}/evidence/pipeline",
            files=files,
            data=data,
            headers=auth_headers_io1,
        )

    assert res.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    payload = res.json()
    assert payload["overall_status"] == "RETRYABLE_ERROR"
    assert payload["current_stage"] == "DUAL_HASHING"
    assert payload["is_retryable"] is True
    evidence_id = payload["evidence_id"]

    # Now resume with working service: should succeed through MOD-10
    resume_res = client.post(
        f"/api/v1/cases/{case_id}/evidence/pipeline",
        data={"evidence_id": evidence_id},
        headers=auth_headers_io1,
    )
    assert resume_res.status_code == status.HTTP_200_OK
    resumed_payload = resume_res.json()
    assert resumed_payload["overall_status"] == "SUCCESS"
    assert resumed_payload["current_stage"] == "OBJECT_LOCK"
    assert resumed_payload["completed_stages"] == [
        "INTAKE",
        "MIME_VALIDATION",
        "ANTIVIRUS_SCAN",
        "WORM_COMMIT",
        "DUAL_HASHING",
        "OBJECT_LOCK",
    ]
    assert resumed_payload["integrity_status"] == "VERIFIED"
    assert resumed_payload["lock_status"] == "LOCKED"
