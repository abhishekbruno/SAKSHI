"""
Regression tests for Case Directory visibility, development identity alignment,
and RBAC/ABAC authorization boundaries.
Ensures SAKSHI-TEST-2026-002 and development cases are visible to assigned IOs
and supervisory officers while preserving strict authorization isolation.
"""
import pytest
from fastapi import status
from app.main import app
from app.core.config import settings
from app.models.case import Case
from app.models.evidence import Evidence


@pytest.fixture(autouse=True)
def seed_dev_test_case(db_session):
    """Seed SAKSHI-TEST-2026-002 and its synthetic exhibit into the test database session."""
    existing_case = db_session.query(Case).filter(Case.case_id == "SAKSHI-TEST-2026-002").first()
    if not existing_case:
        test_case = Case(
            case_id="SAKSHI-TEST-2026-002",
            title="Unnatural Death Investigation - Case 002",
            fir_metadata={
                "fir_number": "FIR-TEST-2026-002",
                "police_station": "Fort Police Station",
                "incident_date": "2026-10-01T10:00:00Z",
                "report_date": "2026-10-01T11:30:00Z",
                "jurisdiction_code": "KERALA",
            },
            assigned_io_id="dev-investigator-001",
            lifecycle_stage="EVIDENCE_INGESTION",
            status="ACTIVE",
            case_workspace_path="/cases/SAKSHI-TEST-2026-002",
            created_by="dev-investigator-001",
        )
        db_session.add(test_case)
        db_session.commit()

    existing_ev = db_session.query(Evidence).filter(Evidence.evidence_id == "SAKSHI-EVID-2026-E51D496A").first()
    if not existing_ev:
        test_ev = Evidence(
            evidence_id="SAKSHI-EVID-2026-E51D496A",
            case_id="SAKSHI-TEST-2026-002",
            original_file_name="SAKSHI_Synthetic_Evidence_RAG_Test.pdf",
            stored_file_name="SAKSHI-EVID-2026-E51D496A.pdf",
            evidence_category="DOCUMENT_PDF",
            declared_mime_type="application/pdf",
            detected_mime_type="application/pdf",
            file_size_bytes=42000,
            submitting_investigator_id="dev-investigator-001",
            status="COMMITTED",
            worm_status="COMMITTED",
            integrity_status="VERIFIED",
            raw_storage_path="/storage/SAKSHI-EVID-2026-E51D496A.pdf",
        )
        db_session.add(test_ev)
        db_session.commit()


def test_auth_status_returns_dev_identity_defaults(client):
    """Verify /auth/status exposes development identity configuration."""
    response = client.get("/api/v1/auth/status")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["auth_mode"] == "development"
    assert data["development_mode"] is True
    assert data["default_investigator_id"] == "dev-investigator-001"
    assert data["default_investigator_name"] == settings.DEV_INVESTIGATOR_NAME
    assert data["default_jurisdiction"] == "KERALA"


def test_case_list_assigned_io_sees_dev_test_case(client):
    """Verify assigned IO (dev-investigator-001) sees SAKSHI-TEST-2026-002."""
    headers = {
        "X-Investigator-Id": "dev-investigator-001",
        "X-Investigator-Role": "INVESTIGATING_OFFICER",
        "X-Investigator-Jurisdiction": "KERALA"
    }
    response = client.get("/api/v1/cases", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] >= 1
    case_ids = [c["case_id"] for c in data["cases"]]
    assert "SAKSHI-TEST-2026-002" in case_ids

    # Find the specific test case and assert fields
    test_case = next(c for c in data["cases"] if c["case_id"] == "SAKSHI-TEST-2026-002")
    assert test_case["assigned_io_id"] == "dev-investigator-001"
    assert test_case["lifecycle_stage"] == "EVIDENCE_INGESTION"
    assert test_case["status"] == "ACTIVE"
    assert test_case["fir_metadata"]["jurisdiction_code"] == "KERALA"


def test_case_list_supervisory_officer_sees_all_cases(client):
    """Verify supervisory role sees all cases across the jurisdiction."""
    headers = {
        "X-Investigator-Id": "SUPERVISOR-KL-01",
        "X-Investigator-Role": "SUPERVISORY_OFFICER",
        "X-Investigator-Jurisdiction": "KERALA"
    }
    response = client.get("/api/v1/cases", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total"] >= 1
    case_ids = [c["case_id"] for c in data["cases"]]
    assert "SAKSHI-TEST-2026-002" in case_ids


def test_case_list_unassigned_io_isolated_by_abac(client):
    """Verify unassigned IO (e.g. IO-7842-SHARMA) cannot see cases of other IOs."""
    headers = {
        "X-Investigator-Id": "IO-7842-SHARMA",
        "X-Investigator-Role": "INVESTIGATING_OFFICER",
        "X-Investigator-Jurisdiction": "KL-TVM-001"
    }
    response = client.get("/api/v1/cases", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    case_ids = [c["case_id"] for c in data["cases"]]
    assert "SAKSHI-TEST-2026-002" not in case_ids


def test_case_workspace_access_jurisdiction_enforcement(client):
    """Verify jurisdiction constraint is enforced on case workspace retrieval."""
    # Matching jurisdiction -> Allowed
    allowed_headers = {
        "X-Investigator-Id": "dev-investigator-001",
        "X-Investigator-Role": "INVESTIGATING_OFFICER",
        "X-Investigator-Jurisdiction": "KERALA"
    }
    res_allow = client.get("/api/v1/cases/SAKSHI-TEST-2026-002", headers=allowed_headers)
    assert res_allow.status_code == status.HTTP_200_OK

    # Mismatched jurisdiction -> Forbidden
    denied_headers = {
        "X-Investigator-Id": "dev-investigator-001",
        "X-Investigator-Role": "INVESTIGATING_OFFICER",
        "X-Investigator-Jurisdiction": "KL-TVM-001"
    }
    res_deny = client.get("/api/v1/cases/SAKSHI-TEST-2026-002", headers=denied_headers)
    assert res_deny.status_code == status.HTTP_403_FORBIDDEN


def test_evidence_record_preserved(client):
    """Verify existing UiPath synthetic evidence is intact and COMMITTED."""
    headers = {
        "X-Investigator-Id": "dev-investigator-001",
        "X-Investigator-Role": "INVESTIGATING_OFFICER",
        "X-Investigator-Jurisdiction": "KERALA"
    }
    res = client.get("/api/v1/cases/SAKSHI-TEST-2026-002/evidence", headers=headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["total"] >= 1
    evidence_ids = [e["evidence_id"] for e in data["items"]]
    assert "SAKSHI-EVID-2026-E51D496A" in evidence_ids

    ev = next(e for e in data["items"] if e["evidence_id"] == "SAKSHI-EVID-2026-E51D496A")
    assert ev["status"] == "COMMITTED"
    assert ev["worm_status"] == "COMMITTED"
    assert ev["declared_mime_type"] == "application/pdf"
    assert ev["original_file_name"] == "SAKSHI_Synthetic_Evidence_RAG_Test.pdf"
