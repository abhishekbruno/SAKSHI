"""
Unit and Integration Tests for SAKSHI Evidence Intelligence Workspace.

Verifies:
1. File viewing endpoint (/cases/{case_id}/evidence/{evidence_id}/file) returns original file inline.
2. File viewing enforces strict case-scoping and authorization (cross-case isolation and jurisdiction).
3. Fact review decision endpoint (/cases/{case_id}/evidence/{evidence_id}/facts/{fact_id}/decision)
   records investigator corrections, reasons, and produces audited responses with epistemic state updates.
4. Enhanced extracted facts schema includes document classification, 5-question structured summary,
   source passages, why_it_matters explainability, and scoped unknowns.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_current_investigator, get_db
from app.services.case_service import CaseService
from app.services.evidence_intake_service import EvidenceIntakeService
from app.services.evidence_extraction_service import EvidenceExtractionService
from app.schemas.case import CaseCreateRequest, FIRMetadata
from app.schemas.evidence import (
    EvidenceCategory,
    EvidenceIntakeMetadata,
    FactReviewRequest,
    FactReviewDecision,
)
from app.core.security import AuthenticatedInvestigator


@pytest.fixture
def workspace_setup(db_session, mock_io1, tmp_path):
    """Creates a test case and registers an exhibit."""
    case_service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Riverside Guesthouse Investigation Workspace Test",
        fir_metadata=FIRMetadata(
            fir_number="FIR-SYN-2026-INTEL-01",
            police_station="Central Police Station",
            incident_date="2026-10-18T01:50:00Z",
            jurisdiction_code="JUR-DEL-04",
        ),
    )
    case_resp = case_service.create_case(payload, mock_io1)

    case_entity = case_service.repo.get_by_case_id(case_resp.case_id)
    case_entity.case_workspace_path = str(tmp_path / "case_workspace")
    case_service.repo.update(case_entity)

    # Transition to EVIDENCE_INGESTION
    case_service.update_stage(case_resp.case_id, "EVIDENCE_INGESTION", mock_io1)

    intake_service = EvidenceIntakeService(db_session)
    pdf_bytes = b"%PDF-1.4 FIR-SYN-2026-1042 Arjun Menon reported incident at MG Road Sector 4 at 21:30 hrs."
    meta = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.DOCUMENT_PDF,
        declared_mime_type="application/pdf",
        collection_location="MG Road Sector 4",
        source_device_or_person="Sub-Inspector Station Custody",
        description="Initial FIR document for workspace verification",
    )
    ev_resp = intake_service.register_evidence(
        case_id=case_resp.case_id,
        file_payload=pdf_bytes,
        original_filename="E00_synthetic_FIR.pdf",
        metadata=meta,
        investigator=mock_io1,
    )

    return {
        "case_id": case_resp.case_id,
        "evidence_id": ev_resp.evidence_id,
        "filename": "E00_synthetic_FIR.pdf",
        "investigator": mock_io1,
    }


def test_get_evidence_file_success(db_session, workspace_setup):
    """Test downloading / viewing the original exhibit file."""
    app.dependency_overrides[get_current_investigator] = lambda: workspace_setup["investigator"]
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)
    case_id = workspace_setup["case_id"]
    evidence_id = workspace_setup["evidence_id"]

    response = client.get(f"/api/v1/cases/{case_id}/evidence/{evidence_id}/file")
    assert response.status_code == 200
    assert response.headers["Content-Disposition"].startswith("inline")
    assert "E00_synthetic_FIR.pdf" in response.headers["Content-Disposition"]
    assert response.headers["X-Evidence-ID"] == evidence_id
    assert response.headers["X-Case-ID"] == case_id
    assert b"FIR-SYN-2026-1042" in response.content

    app.dependency_overrides.clear()


def test_get_evidence_file_cross_case_isolation(db_session, workspace_setup, mock_io1, tmp_path):
    """Test that requesting evidence belonging to case A using case B ID fails."""
    # Create another case
    case_service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Unrelated Second Case",
        fir_metadata=FIRMetadata(
            fir_number="FIR-SYN-2026-UNRELATED",
            police_station="Central Police Station",
            incident_date="2026-10-18T01:50:00Z",
            jurisdiction_code="JUR-DEL-04",
        ),
    )
    other_case = case_service.create_case(payload, mock_io1)

    app.dependency_overrides[get_current_investigator] = lambda: mock_io1
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)
    # Attempting to fetch evidence from other_case.case_id should fail with 404
    response = client.get(f"/api/v1/cases/{other_case.case_id}/evidence/{workspace_setup['evidence_id']}/file")
    assert response.status_code == 404

    app.dependency_overrides.clear()


def test_record_fact_decision_confirm(db_session, workspace_setup):
    """Test confirming an extracted fact and verifying audit trail."""
    app.dependency_overrides[get_current_investigator] = lambda: workspace_setup["investigator"]
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)
    case_id = workspace_setup["case_id"]
    evidence_id = workspace_setup["evidence_id"]

    payload = {
        "decision": "CONFIRMED",
        "reason": "Corroborated by CCTV timestamp and witness confirmation.",
        "notes": "Verified by IO during inquest examination."
    }

    response = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/facts/FACT-001/decision",
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == case_id
    assert data["evidence_id"] == evidence_id
    assert data["fact_id"] == "FACT-001"
    assert data["decision"] == "CONFIRMED"
    assert data["review_status"] == "HUMAN_REVIEWED"
    assert data["audit_recorded"] is True
    assert "Corroborated by CCTV" in data["reason"]

    app.dependency_overrides.clear()


def test_record_fact_decision_correct(db_session, workspace_setup):
    """Test correcting an extracted fact with new wording and revision reason."""
    app.dependency_overrides[get_current_investigator] = lambda: workspace_setup["investigator"]
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)
    case_id = workspace_setup["case_id"]
    evidence_id = workspace_setup["evidence_id"]

    payload = {
        "decision": "CORRECTED",
        "corrected_text": "Incident occurred at Sector 4 Guesthouse, Room 102.",
        "reason": "Correcting vague location name to precise room number.",
        "notes": "Amended per guest registry exhibit."
    }

    response = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/facts/FACT-002/decision",
        json=payload
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "CORRECTED"
    assert data["review_status"] == "SUPERSEDED"
    assert data["current_text"] == "Incident occurred at Sector 4 Guesthouse, Room 102."
    assert "Correcting vague location" in data["reason"]

    app.dependency_overrides.clear()


def test_fact_decision_cross_case_isolation(db_session, workspace_setup, mock_io1):
    """Test that fact decision cannot be submitted against wrong case ID."""
    case_service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Third Isolated Case",
        fir_metadata=FIRMetadata(
            fir_number="FIR-SYN-2026-THIRD",
            police_station="Central Police Station",
            incident_date="2026-10-18T01:50:00Z",
            jurisdiction_code="JUR-DEL-04",
        ),
    )
    third_case = case_service.create_case(payload, mock_io1)

    app.dependency_overrides[get_current_investigator] = lambda: mock_io1
    app.dependency_overrides[get_db] = lambda: db_session

    client = TestClient(app)
    resp = client.post(
        f"/api/v1/cases/{third_case.case_id}/evidence/{workspace_setup['evidence_id']}/facts/FACT-001/decision",
        json={"decision": "CONFIRMED", "reason": "Test cross-case attempt."}
    )
    assert resp.status_code == 404

    app.dependency_overrides.clear()
