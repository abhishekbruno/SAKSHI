"""
Verification Test Suite for Phases C, D, and E:
- Phase C: Reasoning Engine, Dual-Brain, Statutory Procedural Rules, Abstention, Threshold Evaluation.
- Phase D: Entity Knowledge Graph, Fresh-Case Isolation, Relationship Provenance & Decision Lifecycle.
- Phase E: Timeline & Scenario Verification, Evidence-Driven Events, Operational Audit Separation.
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone

from app.core.security import AuthenticatedInvestigator
from app.core.errors import CaseNotFoundException, ForbiddenException
from app.models.case import Case
from app.models.evidence import Evidence
from app.schemas.evidence import (
    EntityNodeType,
    EntityEdgeType,
    RelationshipReviewStatus,
    EdgeDecisionRequest,
    TimelineCertainty,
)
from app.services.evidence_extraction_service import EvidenceExtractionService


@pytest.fixture
def mock_investigator():
    return AuthenticatedInvestigator(
        subject_id="IO-VERIFY-001",
        email="io.verify@police.gov.in",
        role="INVESTIGATING_OFFICER",
        roles=["INVESTIGATING_OFFICER"],
        station_jurisdiction="KERALA",
        is_authenticated=True,
    )


class TestPhaseCReasoningEngine:
    """Phase C: Actual Reasoning Engine Behavior Verification."""

    def test_empty_case_dual_brain_abstains_without_hallucination(self, mock_investigator):
        db = MagicMock()
        svc = EvidenceExtractionService(db)
        svc.case_repo = MagicMock()
        svc.evidence_repo = MagicMock()
        svc.authz = MagicMock()

        case = Case(
            case_id="CASE-SYNTH-EMPTY-01",
            title="Synthetic Empty Case",
            assigned_io_id="IO-VERIFY-001",
            fir_metadata={"jurisdiction_code": "KERALA"},
        )
        svc.case_repo.get_by_case_id.return_value = case
        svc.evidence_repo.list_by_case_id.return_value = []

        reasoning = svc.get_dual_brain_reasoning("CASE-SYNTH-EMPTY-01", mock_investigator)
        assert reasoning.case_id == "CASE-SYNTH-EMPTY-01"
        assert reasoning.evidence_count == 0
        assert len(reasoning.proposals) == 0
        assert len(reasoning.challenges) == 0
        assert reasoning.firewall_status == "ACTIVE_ENFORCED"
        assert reasoning.evidence_gate_status == "ENFORCING_MINIMUM_CREDIBILITY"

    def test_dual_brain_preserves_multiple_scenarios_and_statutory_bars(self, mock_investigator):
        db = MagicMock()
        svc = EvidenceExtractionService(db)
        svc.case_repo = MagicMock()
        svc.evidence_repo = MagicMock()
        svc.authz = MagicMock()

        case = Case(
            case_id="CASE-SYNTH-DUAL-02",
            title="Synthetic Inquest",
            assigned_io_id="IO-VERIFY-001",
            fir_metadata={"jurisdiction_code": "KERALA"},
        )
        ev1 = Evidence(
            evidence_id="EVID-SYNTH-01",
            case_id="CASE-SYNTH-DUAL-02",
            original_file_name="CCTV_Corridor_Cam02.mp4",
            evidence_category="VIDEO",
            integrity_status="VERIFIED",
            worm_status="COMMITTED",
        )
        ev2 = Evidence(
            evidence_id="EVID-SYNTH-02",
            case_id="CASE-SYNTH-DUAL-02",
            original_file_name="Witness_Statement_Neighbor.pdf",
            evidence_category="DOCUMENT_PDF",
            integrity_status="VERIFIED",
            worm_status="COMMITTED",
        )

        svc.case_repo.get_by_case_id.return_value = case
        svc.evidence_repo.list_by_case_id.return_value = [ev1, ev2]

        reasoning = svc.get_dual_brain_reasoning("CASE-SYNTH-DUAL-02", mock_investigator)
        # Verify candidate explanations are preserved (Physical vs Witness statement)
        assert len(reasoning.proposals) == 2
        prop_types = [p.scenario_type for p in reasoning.proposals]
        assert "FORENSIC_TIMELINE_RECONSTRUCTION" in prop_types
        assert "ORAL_TESTIMONY_SEQUENCE" in prop_types

        # Verify Discipline challenges evaluate statutory procedural bars
        assert len(reasoning.challenges) == 2
        chal1 = reasoning.challenges[0]
        chal2 = reasoning.challenges[1]
        assert "Section 63 BSA" in str(chal1.statutory_procedural_rules) or "Section 63 BSA" in chal1.statutory_rule_citation
        assert "Section 23 BSA" in str(chal2.statutory_procedural_rules) or "Section 23 BSA" in chal2.statutory_rule_citation

        # Verify evidence gate statuses
        assert chal1.evidence_gate_status == "BLOCKED_PENDING_LAB_REPORT"
        assert chal2.evidence_gate_status == "REQUIRES_INDEPENDENT_CORROBORATION"

    def test_rag_abstention_below_threshold(self, mock_investigator):
        """Verify that similarity below 0.35 results in refusal/abstention."""
        db = MagicMock()
        svc = EvidenceExtractionService(db)
        svc.case_repo = MagicMock()
        svc.authz = MagicMock()

        case = Case(
            case_id="CASE-SYNTH-03",
            title="Synthetic Case 03",
            assigned_io_id="IO-VERIFY-001",
            fir_metadata={"jurisdiction_code": "KERALA"},
        )
        svc.case_repo.get_by_case_id.return_value = case

        mock_rag_item = MagicMock()
        mock_rag_item.similarity_score = 0.22  # Below 0.35 cutoff
        mock_rag_item.text_content = "Irrelevant passage about weather in a different district."
        mock_rag_item.evidence_id = "EVID-IRRELEVANT"
        mock_rag_item.original_file_name = "weather.pdf"
        mock_rag_item.chunk_index = 0

        mock_rag_resp = MagicMock()
        mock_rag_resp.results = [mock_rag_item]

        with MagicMock() as mock_rag_svc:
            mock_rag_svc.search.return_value = mock_rag_resp
            import app.services.evidence_extraction_service as ees_mod
            orig_cls = ees_mod.RAGRetrievalService
            ees_mod.RAGRetrievalService = MagicMock(return_value=mock_rag_svc)
            try:
                resp = svc.ask_case_question(
                    case_id="CASE-SYNTH-03",
                    question="Who is the suspect responsible for this crime?",
                    limit=5,
                    investigator=mock_investigator,
                )
            finally:
                ees_mod.RAGRetrievalService = orig_cls

        assert resp.is_grounded is False
        assert len(resp.citations) == 0
        assert "no direct passage was retrieved" in resp.answer.lower()


class TestPhaseDEntityGraph:
    """Phase D: Entity Knowledge Graph & Provenance Verification."""

    def test_fresh_case_contains_no_spurious_nodes(self, mock_investigator):
        db = MagicMock()
        svc = EvidenceExtractionService(db)
        svc.case_repo = MagicMock()
        svc.evidence_repo = MagicMock()
        svc.authz = MagicMock()

        case = Case(
            case_id="CASE-FRESH-999",
            title="Fresh Inquest Case",
            assigned_io_id="IO-VERIFY-001",
            fir_metadata={},
        )
        svc.case_repo.get_by_case_id.return_value = case
        svc.evidence_repo.list_by_case_id.return_value = []

        graph = svc.get_case_knowledge_graph("CASE-FRESH-999", mock_investigator)
        assert graph.total_nodes == 0
        assert graph.total_edges == 0
        assert graph.case_isolated is True

    def test_graph_edges_record_exact_citation_and_provenance(self, mock_investigator):
        db = MagicMock()
        svc = EvidenceExtractionService(db)
        svc.case_repo = MagicMock()
        svc.evidence_repo = MagicMock()
        svc.authz = MagicMock()

        case = Case(
            case_id="CASE-GROUNDED-01",
            title="Grounded Case",
            assigned_io_id="IO-VERIFY-001",
            fir_metadata={
                "complainant_name": "Ramesh Kumar",
                "deceased_name": "Suresh Nair",
                "incident_location": "Apartment 101, Marine Drive",
                "police_station": "Marine Drive PS",
            },
        )
        ev1 = Evidence(
            evidence_id="EVID-PRIMARY-FIR",
            case_id="CASE-GROUNDED-01",
            original_file_name="Primary_Inquest_FIR.pdf",
            evidence_category="DOCUMENT_PDF",
            integrity_status="VERIFIED",
            worm_status="COMMITTED",
        )
        ev2 = Evidence(
            evidence_id="EVID-RECOVERED-KEY",
            case_id="CASE-GROUNDED-01",
            original_file_name="Recovered_Brass_Key.jpg",
            evidence_category="SCENE_PHOTO",
            integrity_status="VERIFIED",
            worm_status="COMMITTED",
        )
        svc.case_repo.get_by_case_id.return_value = case
        svc.evidence_repo.list_by_case_id.return_value = [ev1, ev2]

        graph = svc.get_case_knowledge_graph("CASE-GROUNDED-01", mock_investigator)
        assert graph.total_nodes > 0
        assert graph.total_edges > 0

        # Verify edge provenance
        seized_edge = next((e for e in graph.edges if e.relation_type == EntityEdgeType.SEIZED_FROM), None)
        assert seized_edge is not None
        assert seized_edge.evidence_id == "EVID-RECOVERED-KEY"
        assert seized_edge.source_filename == "Recovered_Brass_Key.jpg"
        assert seized_edge.citation is not None
        assert seized_edge.citation["exhibit_id"] == "EVID-RECOVERED-KEY"

    def test_edge_decision_audit_lifecycle(self, mock_investigator):
        db = MagicMock()
        svc = EvidenceExtractionService(db)
        svc.case_repo = MagicMock()
        svc.authz = MagicMock()

        case = Case(
            case_id="CASE-DECISION-01",
            title="Decision Case",
            assigned_io_id="IO-VERIFY-001",
            fir_metadata={"jurisdiction_code": "KERALA"},
        )
        svc.case_repo.get_by_case_id.return_value = case

        req = EdgeDecisionRequest(
            decision=RelationshipReviewStatus.REJECTED,
            notes="Seizure memo indicates this key belonged to security guard, not victim.",
        )
        resp = svc.record_edge_decision(
            case_id="CASE-DECISION-01",
            edge_id="EDGE-01-002",
            request=req,
            investigator=mock_investigator,
        )
        assert resp.edge_id == "EDGE-01-002"
        assert resp.new_status == RelationshipReviewStatus.REJECTED
        assert resp.audit_recorded is True


class TestPhaseETimelineAndScenarios:
    """Phase E: Timeline & Scenario Verification."""

    def test_evidence_driven_timeline_events(self, mock_investigator):
        db = MagicMock()
        svc = EvidenceExtractionService(db)
        svc.case_repo = MagicMock()
        svc.evidence_repo = MagicMock()
        svc.authz = MagicMock()

        case = Case(
            case_id="CASE-TIME-01",
            title="Timeline Case",
            assigned_io_id="IO-VERIFY-001",
            fir_metadata={"jurisdiction_code": "KERALA"},
        )
        now = datetime.now(timezone.utc)
        ev1 = Evidence(
            evidence_id="EVID-AUDIO-01",
            case_id="CASE-TIME-01",
            original_file_name="Emergency_Call_Recording.wav",
            evidence_category="AUDIO",
            collection_datetime=now,
            integrity_status="VERIFIED",
            worm_status="COMMITTED",
        )
        svc.case_repo.get_by_case_id.return_value = case
        svc.evidence_repo.list_by_case_id.return_value = [ev1]

        timeline = svc.get_case_timeline_events("CASE-TIME-01", mock_investigator)
        assert timeline.total_events == 1
        event = timeline.events[0]
        assert event.evidence_id == "EVID-AUDIO-01"
        assert event.source_name == "Emergency_Call_Recording.wav"
        assert event.time_certainty == TimelineCertainty.EXACT
        assert event.confidence_level == "HIGH"

    def test_case_isolation_on_timeline(self, mock_investigator):
        db = MagicMock()
        svc = EvidenceExtractionService(db)
        svc.case_repo = MagicMock()
        svc.evidence_repo = MagicMock()
        svc.authz = MagicMock()

        case = Case(
            case_id="CASE-TIME-EMPTY",
            title="Empty Case",
            assigned_io_id="IO-VERIFY-001",
            fir_metadata={"jurisdiction_code": "KERALA"},
        )
        svc.case_repo.get_by_case_id.return_value = case
        svc.evidence_repo.list_by_case_id.return_value = []

        timeline = svc.get_case_timeline_events("CASE-TIME-EMPTY", mock_investigator)
        assert timeline.total_events == 0
        assert len(timeline.events) == 0
