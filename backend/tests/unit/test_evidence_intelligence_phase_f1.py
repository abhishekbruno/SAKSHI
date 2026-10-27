"""
Comprehensive Unit Tests for Phase F.1 — Evidence Intelligence, Entity Registry and Investigative Dossiers.
Verifies all 20 requirements from Phase F.1 prompt.
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock
import pytest

from app.core.security import AuthenticatedInvestigator
from app.core.errors import CaseNotFoundException, ForbiddenException, EvidenceNotFoundException
from app.models.case import Case
from app.models.evidence import Evidence
from app.schemas.evidence import (
    EntityNodeType,
    EntityEdgeType,
    RelationshipReviewStatus,
    EntityNode,
    EntityEdge,
    CaseKnowledgeGraphResponse,
    TimelineEventItem,
    TimelineCertainty,
    BranchingTimelineResponse,
)
from app.schemas.intelligence import (
    SearchFilterType,
    SearchResultMatchType,
)
from app.services.evidence_intelligence_service import EvidenceIntelligenceService


@pytest.fixture
def mock_investigator():
    return AuthenticatedInvestigator(
        subject_id="test-io-001",
        email="io.sharma@police.gov.in",
        role="INVESTIGATING_OFFICER",
        roles=["INVESTIGATING_OFFICER"],
        station_jurisdiction="KERALA",
    )


@pytest.fixture
def mock_unauthorized_investigator():
    return AuthenticatedInvestigator(
        subject_id="external-user-999",
        email="external@other.gov.in",
        role="GUEST",
        roles=["GUEST"],
        station_jurisdiction="OTHER_STATE",
    )


def build_synthetic_case_and_exhibits():
    case = Case(
        case_id="SAKSHI-CASE-2026-F101",
        title="Unnatural Death Investigation - Royal Palms",
        assigned_io_id="test-io-001",
        fir_metadata={
            "fir_number": "101/2026",
            "police_station": "Koramangala Police Station",
            "incident_date": "2026-10-24 21:30:00",
            "incident_location": "Flat 402, Royal Palms, Koramangala",
            "complainant_name": "Ramesh Nair",
            "victim_name": "Arjun Menon",
        },
        lifecycle_stage="INVESTIGATION_ACTIVE",
        status="ACTIVE",
        case_workspace_path="/cases/SAKSHI-CASE-2026-F101",
        created_by="test-io-001",
    )

    ev1 = Evidence(
        id="internal-ev-001",
        evidence_id="SAKSHI-EVID-2026-00042",
        case_id="SAKSHI-CASE-2026-F101",
        original_file_name="Seized_Kitchen_Knife_Scene.jpg",
        stored_file_name="stored_knife_001.jpg",
        evidence_category="PHYSICAL_EXHIBIT",
        declared_mime_type="image/jpeg",
        file_size_bytes=1048576,
        submitting_investigator_id="test-io-001",
        status="COMMITTED",
        collection_datetime=datetime(2026, 10, 24, 22, 15, tzinfo=timezone.utc),
        collection_location="Kitchen counter, Flat 402",
        checksum_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        worm_status="COMMITTED_WORM",
        integrity_status="VERIFIED",
    )

    ev2 = Evidence(
        id="internal-ev-002",
        evidence_id="SAKSHI-EVID-2026-00043",
        case_id="SAKSHI-CASE-2026-F101",
        original_file_name="Post_Mortem_Inquest_Report.pdf",
        stored_file_name="stored_pm_002.pdf",
        evidence_category="DOCUMENT_PDF",
        declared_mime_type="application/pdf",
        file_size_bytes=2097152,
        submitting_investigator_id="test-io-001",
        status="COMMITTED",
        collection_datetime=datetime(2026, 10, 25, 9, 30, tzinfo=timezone.utc),
        collection_location="District Government Hospital Mortuary",
        checksum_sha256="c4ca4238a0b923820dcc509a6f75849bca40c4ca4238a0b923820dcc509a6f75",
        worm_status="COMMITTED_WORM",
        integrity_status="VERIFIED",
    )

    return case, [ev1, ev2]


def setup_mock_service(case, exhibits, investigator):
    db = MagicMock()
    svc = EvidenceIntelligenceService(db)

    svc.case_repo = MagicMock()
    svc.case_repo.get_by_case_id.side_effect = lambda cid: case if cid == case.case_id else None

    svc.evidence_repo = MagicMock()
    svc.evidence_repo.list_by_case_id.side_effect = lambda cid: exhibits if cid == case.case_id else []
    svc.evidence_repo.get_by_evidence_id.side_effect = lambda eid: next((e for e in exhibits if e.evidence_id == eid), None)

    # Authz mock
    svc.authz = MagicMock()
    def check_auth(inv, c):
        if getattr(inv, "station_jurisdiction", None) != "KERALA" and inv.role == "GUEST":
            raise ForbiddenException("Access denied: investigator not authorized for this jurisdiction.")
        return True
    svc.authz.check_can_read_evidence.side_effect = check_auth

    # Mock knowledge graph
    kg_nodes = [
        EntityNode(
            id="node-doc-ev1",
            name="Seized_Kitchen_Knife_Scene.jpg",
            category=EntityNodeType.DOCUMENT,
            subtitle="PHYSICAL_EXHIBIT",
            details={"evidence_id": "SAKSHI-EVID-2026-00042"},
            evidence_id="SAKSHI-EVID-2026-00042",
            source_filename="Seized_Kitchen_Knife_Scene.jpg",
        ),
        EntityNode(
            id="node-person-victim",
            name="Arjun Menon",
            category=EntityNodeType.PERSON,
            subtitle="Deceased / Subject of Inquest",
            details={"case_role": "Subject of Inquiry"},
            evidence_id="SAKSHI-EVID-2026-00042",
            source_filename="Post_Mortem_Inquest_Report.pdf",
        ),
        EntityNode(
            id="node-person-complainant",
            name="Ramesh Nair",
            category=EntityNodeType.PERSON,
            subtitle="Reporting Complainant",
            details={"case_role": "Informant"},
            evidence_id="SAKSHI-EVID-2026-00042",
            source_filename="Post_Mortem_Inquest_Report.pdf",
        ),
        EntityNode(
            id="node-obj-knife",
            name="Kitchen Knife with Wooden Handle",
            category=EntityNodeType.OBJECT,
            subtitle="Physical Cutting Instrument",
            details={"evidence_id": "SAKSHI-EVID-2026-00042", "description": "Kitchen knife recovered near scene"},
            evidence_id="SAKSHI-EVID-2026-00042",
            source_filename="Seized_Kitchen_Knife_Scene.jpg",
        ),
        EntityNode(
            id="node-loc-scene",
            name="Flat 402, Royal Palms, Koramangala",
            category=EntityNodeType.LOCATION,
            subtitle="Crime Scene",
            details={"type": "Place of Occurrence"},
            evidence_id="SAKSHI-EVID-2026-00042",
            source_filename="Seized_Kitchen_Knife_Scene.jpg",
        ),
    ]

    kg_edges = [
        EntityEdge(
            id="EDGE-F101-001",
            source_node_id="node-person-victim",
            target_node_id="node-loc-scene",
            relation_type=EntityEdgeType.LOCATED_AT,
            label="Discovered at Scene",
            evidence_id="SAKSHI-EVID-2026-00042",
            source_filename="Post_Mortem_Inquest_Report.pdf",
            page_number=1,
            char_offset=120,
            source_passage="The deceased Arjun Menon was discovered inside Flat 402, Royal Palms.",
            review_status=RelationshipReviewStatus.REPORTED,
        ),
        EntityEdge(
            id="EDGE-F101-002",
            source_node_id="node-obj-knife",
            target_node_id="node-loc-scene",
            relation_type=EntityEdgeType.SEIZED_FROM,
            label="Seized from Scene",
            evidence_id="SAKSHI-EVID-2026-00042",
            source_filename="Seized_Kitchen_Knife_Scene.jpg",
            page_number=1,
            char_offset=45,
            source_passage="Kitchen knife item recovered from kitchen counter of Flat 402.",
            review_status=RelationshipReviewStatus.CONFIRMED,
        ),
        EntityEdge(
            id="EDGE-F101-003",
            source_node_id="node-person-complainant",
            target_node_id="node-person-victim",
            relation_type=EntityEdgeType.ASSOCIATED_WITH,
            label="Colleague / Associate",
            evidence_id="SAKSHI-EVID-2026-00043",
            source_filename="Post_Mortem_Inquest_Report.pdf",
            page_number=1,
            char_offset=210,
            source_passage="Ramesh Nair stated he had been an associate of the deceased Arjun Menon.",
            review_status=RelationshipReviewStatus.REPORTED,
        ),
    ]

    svc.extraction_service = MagicMock()
    svc.extraction_service.get_case_knowledge_graph.return_value = CaseKnowledgeGraphResponse(
        case_id=case.case_id,
        total_nodes=len(kg_nodes),
        total_edges=len(kg_edges),
        nodes=kg_nodes,
        edges=kg_edges,
    )

    # Mock timeline
    timeline_events = [
        TimelineEventItem(
            event_id="EVT-001",
            date="2026-10-24",
            time="21:30",
            title="Discovery of Victim at Incident Scene",
            raw_timestamp="2026-10-24 21:30:00",
            time_certainty=TimelineCertainty.EXACT,
            description="Discovery of Arjun Menon inside Flat 402, Royal Palms.",
            evidence_id="SAKSHI-EVID-2026-00042",
            source_name="Post_Mortem_Inquest_Report.pdf",
            source_page=1,
            is_contradiction=False,
        ),
        TimelineEventItem(
            event_id="EVT-002",
            date="2026-10-24",
            time="22:15",
            title="Seizure of Physical Weapon",
            raw_timestamp="2026-10-24 22:15:00",
            time_certainty=TimelineCertainty.EXACT,
            description="Seizure and sealing of kitchen knife item.",
            evidence_id="SAKSHI-EVID-2026-00042",
            source_name="Seized_Kitchen_Knife_Scene.jpg",
            source_page=1,
            is_contradiction=False,
        ),
    ]
    svc.extraction_service.get_case_timeline_events.return_value = BranchingTimelineResponse(
        case_id=case.case_id,
        total_events=len(timeline_events),
        events=timeline_events,
    )

    # Mock RAG retrieval
    mock_rag_item = MagicMock()
    mock_rag_item.chunk_id = "chunk-test-001"
    mock_rag_item.evidence_id = "SAKSHI-EVID-2026-00043"
    mock_rag_item.source_name = "Post_Mortem_Inquest_Report.pdf"
    mock_rag_item.page_number = 2
    mock_rag_item.char_start = 500
    mock_rag_item.char_end = 650
    mock_rag_item.similarity_score = 0.88
    mock_rag_item.passage = "External examination indicates single incised wound on left antecubital fossa."

    mock_rag_response = MagicMock()
    mock_rag_response.results = [mock_rag_item]

    svc.rag_retrieval_service = MagicMock()
    svc.rag_retrieval_service.search.return_value = mock_rag_response

    return svc


# ─── 1. Exact Exhibit Lookup ──────────────────────────────────────────────────

def test_exact_exhibit_number_lookup(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    res = svc.unified_search(
        case_id=case.case_id,
        query="SAKSHI-EVID-2026-00042",
        filter_type=SearchFilterType.ALL,
        investigator=mock_investigator,
    )

    assert res.case_id == case.case_id
    assert res.total_results >= 1
    assert res.exact_match_found is True
    first = res.results[0]
    assert first.type == "EXHIBIT"
    assert first.identifier == "SAKSHI-EVID-2026-00042"
    assert first.match_type == SearchResultMatchType.EXACT_IDENTIFIER
    assert "Exact match on assigned exhibit identifier" in first.match_reason


# ─── 2. Unknown Exhibit Number Lookup ─────────────────────────────────────────

def test_unknown_exhibit_number_behavior(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    res = svc.unified_search(
        case_id=case.case_id,
        query="SAKSHI-EVID-2026-99999",
        filter_type=SearchFilterType.ALL,
        investigator=mock_investigator,
    )

    assert res.exact_match_found is False
    assert res.notice is not None
    assert "No matching evidence record found for identifier" in res.notice
    # Crucial safeguard: Must NOT return a similar exhibit as though it were the exact match
    assert not any(r.identifier == "SAKSHI-EVID-2026-99999" for r in res.results)


# ─── 3. Person Lookup by Exact Name ───────────────────────────────────────────

def test_person_lookup_exact_name(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    res = svc.unified_search(
        case_id=case.case_id,
        query="Arjun Menon",
        filter_type=SearchFilterType.PERSON,
        investigator=mock_investigator,
    )

    assert res.total_results >= 1
    person_res = next(r for r in res.results if r.type == "PERSON")
    assert person_res.name == "Arjun Menon"
    assert person_res.match_type == SearchResultMatchType.EXACT_NAME
    assert person_res.dossier_type == "person"


# ─── 4. Ambiguous Names and Disambiguation ───────────────────────────────────

def test_ambiguous_names_disambiguation(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    # Inject two entities with matching names into the knowledge graph
    kg = svc.extraction_service.get_case_knowledge_graph.return_value
    kg.nodes.append(EntityNode(
        id="node-person-witness-arjun",
        name="Arjun Menon",
        category=EntityNodeType.PERSON,
        subtitle="Independent Eyewitness",
        details={"case_role": "Witness"},
        evidence_id="SAKSHI-EVID-2026-00043",
        source_filename="Post_Mortem_Inquest_Report.pdf",
    ))

    res = svc.unified_search(
        case_id=case.case_id,
        query="Arjun Menon",
        filter_type=SearchFilterType.PERSON,
        investigator=mock_investigator,
    )

    assert res.disambiguation_required is True
    assert len(res.disambiguation_candidates) >= 2
    # Verify records are kept distinct, not silently merged
    ids = [c["id"] for c in res.disambiguation_candidates]
    assert "node-person-victim" in ids
    assert "node-person-witness-arjun" in ids


# ─── 5. Object Lookup by Type & Characteristics ───────────────────────────────

def test_object_lookup_by_type(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    res = svc.unified_search(
        case_id=case.case_id,
        query="knife",
        filter_type=SearchFilterType.OBJECT,
        investigator=mock_investigator,
    )

    assert res.total_results >= 1
    obj_res = next(r for r in res.results if r.type == "OBJECT")
    assert "Knife" in obj_res.name or "knife" in obj_res.description.lower()
    assert obj_res.dossier_type == "object"


# ─── 6. Attribute Lookup (Knife Length) ────────────────────────────────────────

def test_attribute_lookup_knife_length(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    res = svc.unified_search(
        case_id=case.case_id,
        query="knife length",
        filter_type=SearchFilterType.ALL,
        investigator=mock_investigator,
    )

    assert res.total_results >= 1
    matched = [r for r in res.results if r.type == "OBJECT"]
    assert len(matched) >= 1
    assert "Attribute inquiry" in matched[0].match_reason


# ─── 7. Handling Undocumented Measurement in Object Dossier ───────────────────

def test_object_dossier_missing_measurement_marked_undocumented(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    dossier = svc.get_object_dossier(
        case_id=case.case_id,
        object_id="SAKSHI-EVID-2026-00042",
        investigator=mock_investigator,
    )

    assert dossier.object_id == "SAKSHI-EVID-2026-00042"
    assert dossier.exhibit_number == "SAKSHI-EVID-2026-00042"

    # Verify characteristics register
    reg = {item.attribute_name: item for item in dossier.characteristics_register}
    assert "Total Length / Dimensions" in reg
    assert reg["Total Length / Dimensions"].value == "Not documented in available evidence"
    assert reg["Total Length / Dimensions"].source_type == "NOT_DOCUMENTED"

    assert "Blade / Cutting Edge Length" in reg
    assert reg["Blade / Cutting Edge Length"].value == "Not documented in available evidence"

    # Forensic Limitations Safeguard
    assert "Sharpness, Penetration & Cutting Capability" in reg
    sharpness_val = reg["Sharpness, Penetration & Cutting Capability"].value
    assert "Not established" in sharpness_val
    assert "Section 45 IEA" in sharpness_val or "Section 39 BSA" in sharpness_val

    # Forensic limitations notice is prominently present
    assert "Sharpness, cutting capability, penetration depth" in dossier.forensic_limitations_notice


# ─── 8. Person Dossier Provenance Links ─────────────────────────────────────────

def test_person_dossier_provenance_and_sections(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    dossier = svc.get_person_dossier(
        case_id=case.case_id,
        person_id="node-person-victim",
        investigator=mock_investigator,
    )

    assert dossier.canonical_name == "Arjun Menon"
    assert "name" in dossier.identifying_info
    assert dossier.identifying_info["name"].value == "Arjun Menon"
    assert dossier.identifying_info["name"].source_type == "SOURCE_REPORTED"

    # Distinct source-reported age vs calculated age
    assert "age_source_reported" in dossier.identifying_info
    assert "calculated_age" in dossier.identifying_info
    assert dossier.identifying_info["calculated_age"].value == "Not documented in available evidence"

    # Relationships linked
    assert len(dossier.relationships) >= 1
    rel = dossier.relationships[0]
    assert rel.source_evidence_id is not None
    assert rel.supporting_passage is not None

    # Interactions and timeline
    assert len(dossier.timeline) >= 1
    assert len(dossier.associated_evidence) >= 1
    assert len(dossier.provenance_records) >= 1

    # Legal safeguard
    assert "Judicial Caution" in dossier.legal_safeguard


# ─── 9. Relationship Provenance & Review Status ────────────────────────────────

def test_relationship_provenance_and_review(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    dossier = svc.get_person_dossier(
        case_id=case.case_id,
        person_id="node-person-victim",
        investigator=mock_investigator,
    )

    for rel in dossier.relationships:
        assert rel.edge_id.startswith("EDGE-")
        assert rel.status in {"REPORTED", "CONFIRMED", "CORRECTED", "REJECTED", "UNRESOLVED"}
        assert len(rel.supporting_passage) > 0
        assert rel.source_filename.endswith((".pdf", ".jpg"))


# ─── 10. Reported Interactions with Uncertain Timestamps ──────────────────────

def test_reported_interactions_timestamp_uncertainty(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    dossier = svc.get_person_dossier(
        case_id=case.case_id,
        person_id="node-person-victim",
        investigator=mock_investigator,
    )

    assert len(dossier.interactions) >= 1
    inter = dossier.interactions[0]
    assert inter.time_uncertainty in {"EXACT", "APPROXIMATE", "UNKNOWN"}
    assert inter.interaction_type in {"DIRECTLY_OBSERVED", "REPORTED_BY_ANOTHER", "INVESTIGATOR_ENTERED"}


# ─── 11. Contradictions & Source Comparisons ──────────────────────────────────

def test_source_comparisons_and_contradictions(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    comps = svc.get_source_comparisons(
        case_id=case.case_id,
        investigator=mock_investigator,
    )

    assert comps.case_id == case.case_id
    assert comps.total_comparisons >= 1
    first_comp = comps.comparisons[0]
    assert first_comp.discrepancy_type == "TEMPORAL_CONFLICT"
    assert "source" in first_comp.claim_a
    assert "source" in first_comp.claim_b
    assert first_comp.status in {"UNRESOLVED", "POTENTIAL_DISCREPANCY", "INVESTIGATOR_RESOLVED"}


# ─── 12. Missing Information and Follow-up Suggestions ────────────────────────

def test_missing_information_followup_suggestions(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    followups = svc.get_investigation_followups(
        case_id=case.case_id,
        investigator=mock_investigator,
    )

    assert followups.total_followups >= 2
    cats = [f.category for f in followups.followups]
    assert "PENDING_LAB_REPORT" in cats
    assert "UNDOCUMENTED_CHARACTERISTIC" in cats

    for f in followups.followups:
        assert len(f.what_is_unknown) > 0
        assert len(f.why_it_matters) > 0
        assert len(f.recommended_action) > 0


# ─── 13. Entity Registry ───────────────────────────────────────────────────────

def test_entity_registry_completeness(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    reg = svc.get_entity_registry(
        case_id=case.case_id,
        investigator=mock_investigator,
    )

    assert reg.total_entities >= 4
    categories = {e.category for e in reg.entities}
    assert "EXHIBIT" in categories
    assert "PERSON" in categories
    assert "OBJECT" in categories


# ─── 14. Case and Jurisdiction Isolation ──────────────────────────────────────

def test_case_and_jurisdiction_isolation(mock_unauthorized_investigator, mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    # 1. Non-existent case
    with pytest.raises(CaseNotFoundException):
        svc.unified_search(
            case_id="NON-EXISTENT-CASE",
            query="knife",
            investigator=mock_investigator,
        )

    # 2. Unauthorized investigator
    with pytest.raises(ForbiddenException):
        svc.unified_search(
            case_id=case.case_id,
            query="knife",
            investigator=mock_unauthorized_investigator,
        )


# ─── 15. No Cross-Case Leakage ────────────────────────────────────────────────

def test_no_cross_case_leakage(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    # Query Case B (different case ID)
    case_b = Case(
        case_id="SAKSHI-CASE-2026-OTHER",
        title="Other Case",
        assigned_io_id="test-io-001",
        fir_metadata={"victim_name": "Separate Individual"},
        lifecycle_stage="INVESTIGATION_ACTIVE",
        status="ACTIVE",
        case_workspace_path="/cases/SAKSHI-CASE-2026-OTHER",
        created_by="test-io-001",
    )
    svc.case_repo.get_by_case_id.side_effect = lambda cid: case_b if cid == "SAKSHI-CASE-2026-OTHER" else None
    svc.evidence_repo.list_by_case_id.side_effect = lambda cid: [] if cid == "SAKSHI-CASE-2026-OTHER" else exhibits

    empty_kg = CaseKnowledgeGraphResponse(
        case_id="SAKSHI-CASE-2026-OTHER",
        total_nodes=0,
        total_edges=0,
        nodes=[],
        edges=[],
    )
    svc.extraction_service.get_case_knowledge_graph.return_value = empty_kg

    res = svc.unified_search(
        case_id="SAKSHI-CASE-2026-OTHER",
        query="Arjun Menon",
        filter_type=SearchFilterType.ALL,
        investigator=mock_investigator,
    )

    # Must return 0 results — Case A entities MUST NOT leak into Case B!
    assert res.total_results == 0


# ─── 16. Evidence-Backed 6-Section Structured Answer ──────────────────────────

def test_evidence_backed_6_section_structured_answer(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    # Query about knife length
    ans = svc.synthesize_structured_answer(
        case_id=case.case_id,
        question="How long is the knife?",
        investigator=mock_investigator,
    )

    assert ans.case_id == case.case_id
    assert ans.is_grounded is True

    # 1. Directly Documented Information
    assert len(ans.documented_information) >= 1
    # 4. Missing or Undocumented Information: length is explicitly not documented!
    assert any("NOT documented" in m for m in ans.missing_or_undocumented_information)
    # 5. Possible Interpretations labeled as hypotheses
    assert any("Hypothesis:" in h for h in ans.possible_interpretations)
    # 6. Suggested follow-up questions
    assert len(ans.suggested_followups) >= 1

    # Full text verification of the 6 headers
    assert "1. DIRECTLY DOCUMENTED INFORMATION:" in ans.answer_text
    assert "2. SUPPORTING SOURCE REFERENCES:" in ans.answer_text
    assert "3. CONFLICTING OR INCONSISTENT INFORMATION:" in ans.answer_text
    assert "4. MISSING OR UNDOCUMENTED INFORMATION:" in ans.answer_text
    assert "5. POSSIBLE INTERPRETATIONS (HYPOTHESES ONLY):" in ans.answer_text
    assert "6. SUGGESTED FOLLOW-UP QUESTIONS:" in ans.answer_text


# ─── 17. Relationship Query Structured Answer ─────────────────────────────────

def test_relationship_query_structured_answer(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    ans = svc.synthesize_structured_answer(
        case_id=case.case_id,
        question="What is Arjun Menon's relationship with the victim?",
        investigator=mock_investigator,
    )

    assert ans.case_id == case.case_id
    assert len(ans.documented_information) >= 1
    assert len(ans.conflicting_information) >= 1
    assert len(ans.missing_or_undocumented_information) >= 1


# ─── 18. Graph & Dossier Consistency with Shared Persisted Entities ────────────

def test_graph_and_dossier_consistency(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    # Fetch knowledge graph and person dossier
    kg = svc.extraction_service.get_case_knowledge_graph(case.case_id, mock_investigator)
    dossier = svc.get_person_dossier(case.case_id, "node-person-victim", mock_investigator)

    victim_node = next(n for n in kg.nodes if n.id == "node-person-victim")
    assert dossier.canonical_name == victim_node.name
    # Consistency check: relationship entities match dossier relationships
    kg_connected_entities = {
        e.target_node_id if e.source_node_id == "node-person-victim" else e.source_node_id
        for e in kg.edges
        if e.source_node_id == "node-person-victim" or e.target_node_id == "node-person-victim"
    }
    dossier_targets = {r.target_id for r in dossier.relationships}
    assert kg_connected_entities == dossier_targets


# ─── 19. Search Persistence Across Refresh ────────────────────────────────────

def test_search_results_persistence_across_refresh(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    # Initial search
    res1 = svc.unified_search(case.case_id, "knife", SearchFilterType.ALL, investigator=mock_investigator)
    # Simulated refresh / case reopening
    res2 = svc.unified_search(case.case_id, "knife", SearchFilterType.ALL, investigator=mock_investigator)

    assert res1.total_results == res2.total_results
    assert [r.id for r in res1.results] == [r.id for r in res2.results]


# ─── 20. Safe Behavior with Empty Query or Service Error ──────────────────────

def test_safe_behavior_on_whitespace_query(mock_investigator):
    case, exhibits = build_synthetic_case_and_exhibits()
    svc = setup_mock_service(case, exhibits, mock_investigator)

    res = svc.unified_search(case.case_id, "   ", SearchFilterType.ALL, investigator=mock_investigator)
    assert res.total_results == 0
    assert res.results == []

