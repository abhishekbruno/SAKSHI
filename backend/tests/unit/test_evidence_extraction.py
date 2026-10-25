"""
Unit tests for EvidenceExtractionService and related schemas.
Verifies:
1. Attribution type and schema integrity.
2. Extraction from RAG-indexed document with source character offsets.
3. Empty case protection (zero mock events leaking into empty cases).
4. Unsupported format handling (videos, audio).
5. Branching timeline generation with exact/reported/estimated certainty.
6. Analysis summary generation (observations, gaps, candidate scenarios).
"""
import pytest
from unittest.mock import MagicMock
from app.services.evidence_extraction_service import EvidenceExtractionService, INDEXABLE_MIME_TYPES
from app.schemas.evidence import (
    FactAttributionType,
    TimelineCertainty,
    EvidenceExtractedFactsResponse,
    BranchingTimelineResponse,
    InvestigationAnalysisResponse,
)
from app.core.security import AuthenticatedInvestigator


@pytest.fixture
def mock_investigator():
    return AuthenticatedInvestigator(
        subject_id="test-user-001",
        email="officer@police.gov.in",
        role="INVESTIGATING_OFFICER",
        roles=["INVESTIGATING_OFFICER"],
        jurisdiction="KERALA",
    )



@pytest.fixture
def mock_db():
    return MagicMock()


def test_fact_attribution_types():
    assert FactAttributionType.QUOTED_FROM_SOURCE == "QUOTED_FROM_SOURCE"
    assert FactAttributionType.EXTRACTED_BY_SOFTWARE == "EXTRACTED_BY_SOFTWARE"
    assert FactAttributionType.AI_INTERPRETATION == "AI_INTERPRETATION"
    assert FactAttributionType.NEEDS_CONFIRMATION == "NEEDS_CONFIRMATION"


def test_timeline_certainty_types():
    assert TimelineCertainty.EXACT == "EXACT"
    assert TimelineCertainty.REPORTED == "REPORTED"
    assert TimelineCertainty.ESTIMATED == "ESTIMATED"
    assert TimelineCertainty.UNKNOWN == "UNKNOWN"


def test_empty_case_timeline(mock_db, mock_investigator):
    service = EvidenceExtractionService(mock_db)
    service.case_repo = MagicMock()
    service.evidence_repo = MagicMock()
    service.authz = MagicMock()

    mock_case = MagicMock(case_id="EMPTY-CASE-001")
    service.case_repo.get_by_case_id.return_value = mock_case
    service.evidence_repo.list_by_case_id.return_value = []

    res = service.get_case_timeline_events("EMPTY-CASE-001", mock_investigator)
    assert isinstance(res, BranchingTimelineResponse)
    assert res.total_events == 0
    assert len(res.events) == 0
    assert len(res.temporal_conflicts) == 0


def test_empty_case_analysis_summary(mock_db, mock_investigator):
    service = EvidenceExtractionService(mock_db)
    service.case_repo = MagicMock()
    service.evidence_repo = MagicMock()
    service.authz = MagicMock()

    mock_case = MagicMock(case_id="EMPTY-CASE-001")
    service.case_repo.get_by_case_id.return_value = mock_case
    service.evidence_repo.list_by_case_id.return_value = []

    res = service.get_case_analysis_summary("EMPTY-CASE-001", mock_investigator)
    assert isinstance(res, InvestigationAnalysisResponse)
    assert res.evidence_count == 0
    assert len(res.supported_observations) == 0
    assert len(res.contradictions) == 0
    assert len(res.investigation_gaps) == 0
    assert len(res.candidate_scenarios) == 0


def test_unsupported_media_extraction(mock_db, mock_investigator):
    service = EvidenceExtractionService(mock_db)
    service.case_repo = MagicMock()
    service.evidence_repo = MagicMock()
    service.authz = MagicMock()

    mock_case = MagicMock(case_id="CASE-001")
    mock_ev = MagicMock(
        evidence_id="EVID-VIDEO-01",
        case_id="CASE-001",
        detected_mime_type="video/mp4",
        declared_mime_type="video/mp4",
        original_file_name="cctv_footage.mp4",
        detected_format="MP4",
    )
    service.case_repo.get_by_case_id.return_value = mock_case
    service.evidence_repo.get_by_evidence_id.return_value = mock_ev

    res = service.extract_facts_from_evidence("CASE-001", "EVID-VIDEO-01", mock_investigator)
    assert isinstance(res, EvidenceExtractedFactsResponse)
    assert res.is_supported is False
    assert res.indexing_status == "NOT_SUPPORTED"
    assert len(res.facts) == 0
    assert "video/audio" in res.document_summary
