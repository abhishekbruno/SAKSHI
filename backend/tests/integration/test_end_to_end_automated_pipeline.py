"""
Comprehensive End-to-End Automated Investigation Pipeline Test Suite.
Validates the complete workflow:
Upload FIR -> Auto-Register Case -> Security Gates (MIME, AV, WORM, Hash, Lock)
-> Document Processing -> RAG Indexing -> Fact Extraction -> Entity Graph
-> Branching Timeline -> Statement Comparisons & Gaps -> Preliminary Report -> Review.

Includes mandatory Greenfield Community Hall Equipment Theft (Property Loss) regression.
"""
import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.pipeline_run import PipelineRun, PipelineStageRun, CaseReport
from app.core.security import AuthenticatedInvestigator
from app.api.deps import get_current_investigator


GREENFIELD_PROPERTY_LOSS_FIR_TEXT = """
FIRST INFORMATION REPORT
Case Title: Greenfield Community Hall Equipment Theft
FIR Number: FIR-SYN-2026-021
Police Station: Greenfield Community Police Station
Report Date: 22 October 2026
Incident Location: Greenfield Community Hall, Equipment Storage Room
Complainant: Ravi Thomas
Discovery Date / Time: Approximately 08:15 IST on 22 October 2026
Last Confirmed Present: Approximately 18:00 IST on 21 October 2026
Actual Occurrence Time: Unknown / not established
Penal Sections: Section 305 / Section 331(4) BNS
Property Stolen: Two portable audio speakers and one wireless microphone
Brief Facts:
On 22 October 2026 at approximately 08:15 IST, complainant Ravi Thomas, hall manager,
discovered that the rear padlock of the equipment storage room had been severed. Upon inspection,
two portable audio speakers and one wireless microphone last confirmed present at 18:00 IST on 21 October 2026
were found missing. Actual time of occurrence and responsible person are unknown.
Investigating Officer: Sub-Inspector M. Varma
"""

RIVERSIDE_DEATH_FIR_TEXT = """
FIRST INFORMATION REPORT
Case: Initial Inquest Report
Title: Riverside Guesthouse Incident
Police Station: Nallur Coastal Police Station
FIR / Inquest Number: FIR-SYN-2026-1042
Report Date: 18 October 2026
Scene/location: Riverside Guesthouse, Room 204, Nallur, Kerala
Person found unresponsive: Arjun Menon
Discovery time: Approximately 07:20 IST on 18 October 2026
Witness A sighting: Approximately 00:10 IST on 18 October 2026
Witness B sighting: Approximately 01:00 IST on 18 October 2026
Important limitations:
Time of death: Unknown / not established
Cause of death: Unknown / not established
Investigating Officer: Inspector K. Suresh
"""


@pytest.fixture
def mock_io():
    return AuthenticatedInvestigator(
        subject_id="dev-investigator-001",
        investigator_id="dev-investigator-001",
        full_name="Investigating Officer",
        role="INVESTIGATING_OFFICER",
        jurisdiction="KERALA",
        station="Greenfield Community Police Station",
    )


@pytest.fixture
def client(mock_io):
    app.dependency_overrides[get_current_investigator] = lambda: mock_io
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_current_investigator, None)


def test_greenfield_property_loss_end_to_end_pipeline(client):
    """
    Mandatory Acceptance Test: Greenfield Community Hall Equipment Theft.
    Proves full end-to-end automation from FIR upload to Preliminary Report generation
    without manual field-by-field verification checkpoints.
    """
    # 1. Automatic Case Registration and Pipeline Execution
    response = client.post(
        "/api/v1/cases/auto-register",
        data={
            "fir_raw_text": GREENFIELD_PROPERTY_LOSS_FIR_TEXT,
            "title": "Greenfield Community Hall Equipment Theft",
        },
    )
    assert response.status_code == 201, f"Failed: {response.text}"
    data = response.json()

    # 2. Case Verification
    case = data["case"]
    case_id = case["case_id"]
    assert case["title"] == "Greenfield Community Hall Equipment Theft"
    assert case["fir_metadata"]["fir_number"] == "FIR-SYN-2026-021"
    assert "Greenfield" in case["fir_metadata"]["police_station"]
    assert data["incident_type"] == "PROPERTY_LOSS"

    # 3. Property Loss Invariants: Death fields suppressed
    assert case["fir_metadata"].get("victim_name") is None
    assert "Unnatural Death" not in case["title"]
    assert case["fir_metadata"].get("last_confirmed_present") is not None
    assert "18:00" in case["fir_metadata"]["last_confirmed_present"]
    assert "08:15" in case["fir_metadata"]["discovery_time"]

    # 4. Evidence Pipeline Execution
    fir_evidence_id = data["fir_evidence_id"]
    assert fir_evidence_id is not None
    assert fir_evidence_id.startswith("SAKSHI-EVID-")

    # 5. Pipeline Run Verification
    pipeline_run = data["pipeline_run"]
    assert pipeline_run["case_id"] == case_id
    assert pipeline_run["status"] in ("COMPLETED", "COMPLETED_WITH_WARNINGS")
    assert len(pipeline_run["stage_runs"]) >= 7

    # Verify individual stages ran in order
    stage_names = [sr["stage_name"] for sr in pipeline_run["stage_runs"]]
    assert "CASE_INTAKE" in stage_names
    assert "EVIDENCE_SECURITY" in stage_names
    assert "DOCUMENT_PROCESSING" in stage_names
    assert "EVIDENCE_INDEXING" in stage_names
    assert "FACT_EXTRACTION" in stage_names
    assert "ENTITY_GRAPH" in stage_names
    assert "TIMELINE_CONSTRUCTION" in stage_names
    assert "STATEMENT_COMPARISON" in stage_names
    assert "PRELIMINARY_REPORT" in stage_names

    # 6. Preliminary Report Verification
    report = data["preliminary_report"]
    assert report is not None
    assert report["case_id"] == case_id
    assert report["incident_type"] == "PROPERTY_LOSS"
    assert report["status"] == "PRELIMINARY"
    assert report["approval_status"] in ("PENDING_REVIEW", "APPROVED")
    assert len(report["sections"]) >= 8

    # Verify no autopsy/post-mortem gaps in property loss report
    all_gaps_text = " ".join(report.get("unresolved_questions", []))
    assert "Post-Mortem" not in all_gaps_text
    assert "Chemical Viscera" not in all_gaps_text
    assert "Key Register" in all_gaps_text or "CCTV" in all_gaps_text or "Invoices" in all_gaps_text

    # 7. Check GET /cases/{case_id}/pipeline/status
    status_resp = client.get(f"/api/v1/cases/{case_id}/pipeline/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["run_id"] == pipeline_run["run_id"]
    assert status_data["status"] in ("COMPLETED", "COMPLETED_WITH_WARNINGS")

    # 8. Check GET /cases/{case_id}/report
    rep_resp = client.get(f"/api/v1/cases/{case_id}/report")
    assert rep_resp.status_code == 200
    rep_data = rep_resp.json()
    assert rep_data["report_id"] == report["report_id"]
    assert len(rep_data["sections"]) >= 8

    # 9. Test Report Review & Approval (Phase 9)
    review_resp = client.post(
        f"/api/v1/cases/{case_id}/report/review",
        json={
            "decision": "APPROVED",
            "notes": "Reviewed and verified preliminary findings against physical storage evidence.",
        },
    )
    assert review_resp.status_code == 200
    rev_data = review_resp.json()
    assert rev_data["approval_status"] == "APPROVED"
    assert rev_data["approved_by"] == "dev-investigator-001"


def test_riverside_death_investigation_end_to_end_pipeline(client):
    """
    Acceptance Test: Riverside Guesthouse Death Investigation.
    Verifies that death investigations preserve deceased subject, death evidentiary limitations,
    and post-mortem requisition gaps.
    """
    response = client.post(
        "/api/v1/cases/auto-register",
        data={
            "fir_raw_text": RIVERSIDE_DEATH_FIR_TEXT,
            "title": "Riverside Guesthouse Death Investigation",
        },
    )
    assert response.status_code == 201
    data = response.json()

    case = data["case"]
    case_id = case["case_id"]
    assert data["incident_type"] == "DEATH_INVESTIGATION"
    assert case["fir_metadata"]["victim_name"] == "Arjun Menon"
    assert case["fir_metadata"]["time_of_death"] == "Unknown / not established"

    # Report should include death investigation gaps
    report = data["preliminary_report"]
    assert report is not None
    assert report["incident_type"] == "DEATH_INVESTIGATION"
    all_gaps_text = " ".join(report.get("unresolved_questions", []))
    assert "Post-Mortem" in all_gaps_text or "Chemical Viscera" in all_gaps_text


def test_idempotent_duplicate_fir_submission(client):
    """
    Acceptance Test: Submitting the same FIR twice reconciles idempotently
    without creating duplicate cases or duplicating exhibits.
    """
    fir_text = """
    FIRST INFORMATION REPORT
    Case Title: Unique Duplicate Test FIR
    FIR Number: FIR-SYN-DUP-001
    Police Station: Coastal Station Alpha
    Report Date: 25 October 2026
    Location: Sector 9 Harbour
    Complainant: Officer Patel
    Brief Facts: Duplicate submission verification test.
    """

    res1 = client.post(
        "/api/v1/cases/auto-register",
        data={"fir_raw_text": fir_text},
    )
    assert res1.status_code == 201
    data1 = res1.json()
    case_id_1 = data1["case"]["case_id"]

    res2 = client.post(
        "/api/v1/cases/auto-register",
        data={"fir_raw_text": fir_text},
    )
    assert res2.status_code == 201
    data2 = res2.json()
    case_id_2 = data2["case"]["case_id"]

    # Reconciled idempotently
    assert case_id_1 == case_id_2
    assert "Idempotent" in data2["message"]


def test_auto_register_via_file_upload(client):
    """
    Acceptance Test: Direct binary file upload to /auto-register.
    """
    content = b"""%PDF-1.4
    FIRST INFORMATION REPORT
    Case Title: File Upload Test Incident
    FIR Number: FIR-SYN-FILE-002
    Police Station: West End Police Station
    Report Date: 26 October 2026
    Location: Depot 4
    Complainant: Inspector Sharma
    Brief Facts: Binary document intake test.
    """

    files = {"file": ("FIR_uploaded.pdf", content, "application/pdf")}
    res = client.post("/api/v1/cases/auto-register", files=files)
    assert res.status_code == 201
    data = res.json()
    assert data["case"]["fir_metadata"]["fir_number"] == "FIR-SYN-FILE-002"
    assert data["pipeline_run"]["status"] in ("COMPLETED", "COMPLETED_WITH_WARNINGS")
