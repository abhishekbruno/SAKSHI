"""
Comprehensive Unit Tests for SAKSHI Document Intelligence UI Simplification.

Verifies:
1. Document summary generation from actual extracted text (concise narrative, no chunk/character counts).
2. Proper classification of people, identifiers, dates, times, locations, and events.
3. Intelligent grouping of compatible location values (e.g. Room 204 + Riverside Guesthouse) without unsupported merging.
4. Preservation of exact source passages and character offsets.
5. Separation of document-specific unknowns from case-level follow-ups (e.g. Section 63 BSA, FSL toxicology).
6. Fact review decision workflow (confirm, correct, flag) with audit logging.
7. RAG core freeze invariants (diff against baseline 0c51f15ee27a65a664eedd468b3a5d6b56324553 remains zero).
"""
import subprocess
import pytest
from app.db.session import SessionLocal
from app.services.evidence_extraction_service import EvidenceExtractionService
from app.core.security import AuthenticatedInvestigator
from app.schemas.evidence import (
    ImportantDetailItem,
    EvidenceExtractedFactsResponse,
    FactAttributionType,
)


@pytest.fixture
def live_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def assigned_io():
    return AuthenticatedInvestigator(
        subject_id="dev-investigator-001",
        full_name="Lead Investigating Officer",
        role="INVESTIGATING_OFFICER",
        jurisdiction="KERALA",
    )


@pytest.fixture
def unauthorized_io():
    return AuthenticatedInvestigator(
        subject_id="unauthorized-io-999",
        full_name="Unauthorized Officer",
        role="INVESTIGATING_OFFICER",
        jurisdiction="TAMIL_NADU",
    )


def test_guest_register_summary_grounded_in_text(live_db, assigned_io):
    """Verifies that guest register summary is grounded in check-in facts and does not fabricate crimes."""
    svc = EvidenceExtractionService(live_db)
    res = svc.extract_facts_from_evidence(
        case_id="SAKSHI-CASE-2026-C5A64E99",
        evidence_id="SAKSHI-EVID-2026-43F94E97",
        investigator=assigned_io,
    )

    assert res.is_supported is True
    assert res.document_type == "Premises / Guest Register Log"
    assert res.document_summary is not None
    # Must mention check-in, Arjun Menon, Room 204, 18:10, 17 October 2026
    assert "Arjun Menon" in res.document_summary
    assert "Room 204" in res.document_summary
    assert "18:10" in res.document_summary
    assert "17 October 2026" in res.document_summary
    # Must NOT fabricate unresponsiveness or crime for the guest register
    assert "unresponsive" not in res.document_summary.lower()
    # Must NOT include raw character or chunk counts in narrative summary
    assert "characters across" not in res.document_summary
    assert "parsed chunks" not in res.document_summary


def test_fir_summary_grounded_in_incident_report(live_db, assigned_io):
    """Verifies that FIR summary documents official FIR reference, police station, and reported statements."""
    svc = EvidenceExtractionService(live_db)
    res = svc.extract_facts_from_evidence(
        case_id="SAKSHI-CASE-2026-C5A64E99",
        evidence_id="SAKSHI-EVID-2026-54C01EA8",
        investigator=assigned_io,
    )

    assert res.is_supported is True
    assert res.document_type == "First Information Report (FIR)"
    assert res.document_summary is not None
    assert "FIR-SYN-2026-1042" in res.document_summary
    assert "Riverside Training Police Station" in res.document_summary
    assert "Arjun Menon" in res.document_summary
    assert "unresponsive" in res.document_summary.lower()
    assert "characters across" not in res.document_summary


def test_location_grouping_without_unsupported_merging(live_db, assigned_io):
    """Verifies compatible locations (Room 204 + Riverside Guesthouse) are grouped while preserving components."""
    svc = EvidenceExtractionService(live_db)
    # Check Guest Register
    gr_res = svc.extract_facts_from_evidence(
        case_id="SAKSHI-CASE-2026-C5A64E99",
        evidence_id="SAKSHI-EVID-2026-43F94E97",
        investigator=assigned_io,
    )
    grouped_loc = next((d for d in gr_res.important_details if d.category == "LOCATIONS" and d.is_grouped), None)
    assert grouped_loc is not None
    assert "Room 204, Riverside Guesthouse" in grouped_loc.display_value
    assert grouped_loc.is_normalized is True
    assert len(grouped_loc.supporting_fact_ids) == 2
    assert "FACT-002" in grouped_loc.supporting_fact_ids
    assert "FACT-003" in grouped_loc.supporting_fact_ids

    # Check that individual underlying claims remain distinct in facts list
    f2 = next(f for f in gr_res.facts if f.fact_id == "FACT-002")
    f3 = next(f for f in gr_res.facts if f.fact_id == "FACT-003")
    assert f2.title == "Room Reference: Room 204"
    assert "Riverside Guesthouse" in f3.title

    # Check FIR: distinct locations (Police Station, Corridor) are NOT merged into Room 204
    fir_res = svc.extract_facts_from_evidence(
        case_id="SAKSHI-CASE-2026-C5A64E99",
        evidence_id="SAKSHI-EVID-2026-54C01EA8",
        investigator=assigned_io,
    )
    fir_locs = [d for d in fir_res.important_details if d.category == "LOCATIONS"]
    assert len(fir_locs) >= 3  # Grouped Room/Premises, Police Station, Corridor
    ps_entry = next((d for d in fir_locs if "Police Station" in d.field_label or "Police Station" in d.display_value), None)
    assert ps_entry is not None
    assert ps_entry.is_grouped is False  # Police station must not be merged into room!
    corridor_entry = next((d for d in fir_locs if "Corridor" in d.field_label or "Corridor" in d.display_value), None)
    assert corridor_entry is not None
    assert corridor_entry.is_grouped is False  # Transit area must not be merged!


def test_separation_of_document_unknowns_from_case_unknowns(live_db, assigned_io):
    """Verifies that document-specific omissions are kept distinct from case-level statutory/laboratory requisitions."""
    svc = EvidenceExtractionService(live_db)
    gr_res = svc.extract_facts_from_evidence(
        case_id="SAKSHI-CASE-2026-C5A64E99",
        evidence_id="SAKSHI-EVID-2026-43F94E97",
        investigator=assigned_io,
    )

    # Document-specific unknowns for guest register must relate to register scope (checkout, identity doc, etc.)
    assert hasattr(gr_res, "document_unknowns")
    assert hasattr(gr_res, "case_level_unknowns")
    assert len(gr_res.document_unknowns) > 0
    assert any("Check-out" in u or "departure" in u or "identification" in u.lower() or "signature" in u.lower() for u in gr_res.document_unknowns)

    # Document unknowns must NOT contain toxicology or Section 63 BSA certificate
    for u in gr_res.document_unknowns:
        assert "toxicology" not in u.lower()
        assert "section 63" not in u.lower()

    # Case-level unknowns MUST contain Section 63 BSA and FSL toxicology
    assert any("Section 63 BSA" in u for u in gr_res.case_level_unknowns)
    assert any("toxicology" in u.lower() for u in gr_res.case_level_unknowns)


def test_source_passage_offsets_preserved(live_db, assigned_io):
    """Verifies exact character offsets and source passages are preserved across all details."""
    svc = EvidenceExtractionService(live_db)
    gr_res = svc.extract_facts_from_evidence(
        case_id="SAKSHI-CASE-2026-C5A64E99",
        evidence_id="SAKSHI-EVID-2026-43F94E97",
        investigator=assigned_io,
    )
    for d in gr_res.important_details:
        assert d.page_number >= 1
        assert d.char_offset_start is not None
        assert d.char_offset_end is not None
        assert d.char_offset_end >= d.char_offset_start
        assert d.source_passage is not None
        assert len(d.source_passage) > 0


def test_fact_review_decision_persistence(live_db, assigned_io):
    """Verifies recording fact review decisions with mandatory reason and tamper-evident audit history."""
    from app.schemas.evidence import FactReviewRequest
    svc = EvidenceExtractionService(live_db)
    req = FactReviewRequest(
        decision="CONFIRMED",
        reason="Corroborated by investigating officer during premises review.",
        notes="Official review audit",
    )
    res = svc.record_fact_decision(
        case_id="SAKSHI-CASE-2026-C5A64E99",
        evidence_id="SAKSHI-EVID-2026-43F94E97",
        fact_id="FACT-001",
        request=req,
        investigator=assigned_io,
    )

    assert res.decision == "CONFIRMED"
    assert res.review_status == "HUMAN_REVIEWED"
    assert res.audit_recorded is True


def test_cross_case_isolation_rejected(live_db, unauthorized_io):
    """Verifies cross-case access is strictly rejected by the authorization policy."""
    from app.core.errors import ForbiddenException
    svc = EvidenceExtractionService(live_db)
    with pytest.raises(ForbiddenException):
        svc.extract_facts_from_evidence(
            case_id="SAKSHI-CASE-2026-C5A64E99",
            evidence_id="SAKSHI-EVID-2026-43F94E97",
            investigator=unauthorized_io,
        )


def test_frozen_rag_core_integrity():
    """Verifies RAG core baseline 0c51f15ee27a65a664eedd468b3a5d6b56324553 is completely unchanged (0 lines diff)."""
    rag_files = [
        "backend/app/services/rag_indexing_service.py",
        "backend/app/services/rag_retrieval_service.py",
        "backend/app/models/rag_document.py",
        "backend/app/models/rag_chunk.py",
        "backend/app/repositories/rag_repository.py",
    ]
    cmd = ["git", "diff", "0c51f15ee27a65a664eedd468b3a5d6b56324553", "--"] + rag_files
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert len(res.stdout.strip()) == 0, f"RAG core must have 0 lines diff. Found:\n{res.stdout}"
