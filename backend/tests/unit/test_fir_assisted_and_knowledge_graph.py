"""
Unit and API integration tests for FIR-Assisted Registration, Knowledge Graph,
Dual-Brain Reasoning, and Conversational Evidence RAG.
"""
import pytest
from app.services.evidence_extraction_service import EvidenceExtractionService
from app.core.security import AuthenticatedInvestigator
from app.schemas.evidence import (
    EntityNodeType,
    EntityEdgeType,
    RelationshipReviewStatus,
    EdgeDecisionRequest,
)


def test_extract_fir_candidate_details():
    fir_text = """
    FIRST INFORMATION REPORT (Under Section 173 BNSS / 154 Cr.P.C.)
    1. District: Bengaluru City, Police Station: Koramangala Police Station, Year: 2026, FIR No: 142/2026
    2. Date and Time of Occurrence: 2026-10-24 21:30:00
    3. Date of Report: 2026-10-24 23:45:00
    4. Place of Occurrence: Flat 402, Royal Palms, Koramangala 4th Block
    5. Complainant / Informant: Rajesh M. Sharma (Resident of Koramangala)
    6. Details of Deceased / Victim: Vikram Singhania, Age 34 Years
    7. Acts and Sections: Section 194 BNSS / Section 302 IPC / Section 103 BNS
    8. Occurrence Details:
    The complainant reported discovery of the body of his colleague Vikram Singhania inside his apartment.
    The apartment door was latched from inside, and signs of disturbance were observed near the balcony door.
    """
    resp = EvidenceExtractionService.extract_fir_candidate_details(fir_text, filename="FIR_142_2026.txt")

    assert resp.fir_number == "142/2026"
    assert "Koramangala" in resp.police_station
    assert "2026-10-24" in (resp.incident_date or "")
    assert "Royal Palms" in (resp.incident_location or "")
    assert "Rajesh" in (resp.complainant_name or "")
    assert "Vikram" in (resp.victim_name or "")
    assert "194 BNSS" in (resp.offense_sections or "")
    assert len(resp.source_passages) >= 4
    for sp in resp.source_passages:
        assert sp.quote in fir_text


from unittest.mock import MagicMock

@pytest.fixture
def mock_investigator():
    return AuthenticatedInvestigator(
        subject_id="test-user-001",
        email="officer@police.gov.in",
        role="INVESTIGATING_OFFICER",
        roles=["INVESTIGATING_OFFICER"],
        jurisdiction="KERALA",
    )


def test_knowledge_graph_empty_case_isolation(mock_investigator):
    db = MagicMock()
    svc = EvidenceExtractionService(db)
    svc.case_repo = MagicMock()
    svc.evidence_repo = MagicMock()
    svc.authz = MagicMock()

    mock_case = MagicMock()
    mock_case.case_id = "CASE-EMPTY-001"
    mock_case.fir_metadata = {}
    svc.case_repo.get_by_case_id.return_value = mock_case
    svc.evidence_repo.list_by_case_id.return_value = []

    kg = svc.get_case_knowledge_graph("CASE-EMPTY-001", mock_investigator)

    assert kg.case_id == "CASE-EMPTY-001"
    assert kg.total_nodes == 0
    assert kg.total_edges == 0
    assert kg.case_isolated is True
    assert "empty" in (kg.message or "").lower()


def test_dual_brain_reasoning_empty_case(mock_investigator):
    db = MagicMock()
    svc = EvidenceExtractionService(db)
    svc.case_repo = MagicMock()
    svc.evidence_repo = MagicMock()
    svc.authz = MagicMock()

    mock_case = MagicMock()
    mock_case.case_id = "CASE-EMPTY-001"
    svc.case_repo.get_by_case_id.return_value = mock_case
    svc.evidence_repo.list_by_case_id.return_value = []

    res = svc.get_dual_brain_reasoning("CASE-EMPTY-001", mock_investigator)

    assert res.case_id == "CASE-EMPTY-001"
    assert res.evidence_count == 0
    assert len(res.proposals) == 0
    assert len(res.challenges) == 0


def test_edge_decision_audit(mock_investigator):
    db = MagicMock()
    svc = EvidenceExtractionService(db)
    svc.case_repo = MagicMock()
    svc.authz = MagicMock()

    mock_case = MagicMock()
    mock_case.case_id = "CASE-TEST-001"
    svc.case_repo.get_by_case_id.return_value = mock_case

    req = EdgeDecisionRequest(
        decision=RelationshipReviewStatus.CONFIRMED,
        notes="Verified against official inquest memo and medical examiner seal.",
    )
    resp = svc.record_edge_decision(
        case_id="CASE-TEST-001",
        edge_id="EDGE-TEST-001",
        request=req,
        investigator=mock_investigator,
    )

    assert resp.edge_id == "EDGE-TEST-001"
    assert resp.new_status == RelationshipReviewStatus.CONFIRMED


def test_ask_case_question_empty(mock_investigator):
    db = MagicMock()
    svc = EvidenceExtractionService(db)
    svc.case_repo = MagicMock()
    svc.authz = MagicMock()

    mock_case = MagicMock()
    mock_case.case_id = "CASE-TEST-001"
    svc.case_repo.get_by_case_id.return_value = mock_case

    # Mock RAGRetrievalService
    mock_rag_resp = MagicMock()
    mock_rag_resp.results = []
    svc.rag_repo = MagicMock()

    with MagicMock() as mock_rag_svc:
        mock_rag_svc.search.return_value = mock_rag_resp
        import app.services.evidence_extraction_service as ees_mod
        orig_cls = ees_mod.RAGRetrievalService
        ees_mod.RAGRetrievalService = MagicMock(return_value=mock_rag_svc)
        try:
            resp = svc.ask_case_question(
                case_id="CASE-TEST-001",
                question="What was the time of death recorded in the autopsy?",
                limit=5,
                investigator=mock_investigator,
            )
        finally:
            ees_mod.RAGRetrievalService = orig_cls

    assert resp.case_id == "CASE-TEST-001"
    assert resp.is_grounded is False
    assert len(resp.citations) == 0
    assert "no direct passage was retrieved" in resp.answer.lower()

