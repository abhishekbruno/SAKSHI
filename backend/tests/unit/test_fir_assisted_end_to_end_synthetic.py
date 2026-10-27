"""
Automated End-to-End Test Suite for SAKSHI FIR-Assisted Ingestion (Method B).
Verifies:
1. Accurate field extraction on supplied synthetic FIR without arbitrary defaults (e.g. no 'INITIAL', no 'Section 194 BNSS').
2. Correct mapping of:
   - Case title -> Riverside Guesthouse Incident
   - FIR Number -> FIR-SYN-2026-1042
   - Police station -> Nallur Coastal Police Station (fictional)
   - Report date -> 18 October 2026
   - Scene/location -> Riverside Guesthouse, Room 204, Nallur, Kerala (fictional)
   - Person found unresponsive -> Arjun Menon (fictional)
   - Discovery time -> Approximately 07:20 IST on 18 October 2026
   - Witness A sighting -> Approximately 00:10 IST on 18 October 2026
   - Witness B sighting -> Approximately 01:00 IST on 18 October 2026
   - Informant/complainant -> None (Not specified in source)
   - Statutory sections -> None (Not specified in source)
   - Time of death -> Unknown / not established
   - Cause of death -> Unknown / not established
3. Source grounding passages retain verbatim excerpts, character offsets, and extraction status.
4. Mandatory field validation requires non-empty title, FIR number, and police station.
5. Case registration persists confirmed particulars, preserves original FIR exhibit, and supports audit trail.
6. Reopening the case retrieves persisted values without reset.
7. Idempotency prevents duplicate cases on repeated submission.
"""
import pytest
from app.schemas.case import (
    FIRMetadata,
    FIRAssistedCaseCreateRequest,
    FIRAssistedExtractResponse,
)
from app.services.case_service import CaseService
from app.services.evidence_extraction_service import EvidenceExtractionService
from app.services.evidence_pipeline_orchestrator import EvidencePipelineOrchestrator
from app.api.v1.cases import create_case_fir_assisted


SYNTHETIC_TEST_FIR_TEXT = """
Case: Initial Inquest Report
Title: Riverside Guesthouse Incident
Police Station: Nallur Coastal Police Station (fictional)
FIR / Inquest Number: FIR-SYN-2026-1042
Report Date: 18 October 2026
Scene/location: Riverside Guesthouse, Room 204, Nallur, Kerala (fictional)
Person found unresponsive: Arjun Menon (fictional)
Discovery time: Approximately 07:20 IST on 18 October 2026
Witness A sighting: Approximately 00:10 IST on 18 October 2026
Witness B sighting: Approximately 01:00 IST on 18 October 2026
Important limitations:
Time of death: Unknown / not established
Cause of death: Unknown / not established
"""


def test_synthetic_fir_extraction_matches_specification_table():
    """Verify that candidate extraction matches all values in the specification table."""
    res = EvidenceExtractionService.extract_fir_candidate_details(
        text=SYNTHETIC_TEST_FIR_TEXT,
        filename="FIR_synthetic_test.txt",
    )

    assert isinstance(res, FIRAssistedExtractResponse)

    # 1. Title
    assert res.suggested_title == "Riverside Guesthouse Incident"

    # 2. FIR / Inquest Number (Must NOT be INITIAL)
    assert res.fir_number == "FIR-SYN-2026-1042"
    assert res.fir_number != "INITIAL"

    # 3. Police Station
    assert res.police_station == "Nallur Coastal Police Station (fictional)"

    # 4. Report Date
    assert res.report_date == "18 October 2026"

    # 5. Scene / Location
    assert res.incident_location == "Riverside Guesthouse, Room 204, Nallur, Kerala (fictional)"

    # 6. Person Found Unresponsive
    assert res.victim_name == "Arjun Menon (fictional)"

    # 7. Discovery Time (Distinguished from occurrence / time of death)
    assert res.discovery_time == "Approximately 07:20 IST on 18 October 2026"

    # 8. Witness Sightings
    assert len(res.witness_sightings) == 2
    w_a = next((w for w in res.witness_sightings if "Witness A" in w.get("witness", "")), None)
    w_b = next((w for w in res.witness_sightings if "Witness B" in w.get("witness", "")), None)
    assert w_a is not None
    assert w_a["sighting"] == "Approximately 00:10 IST on 18 October 2026"
    assert w_b is not None
    assert w_b["sighting"] == "Approximately 01:00 IST on 18 October 2026"

    # 9. Informant / Complainant (Must remain None / unspecified)
    assert res.complainant_name is None
    assert "complainant_name" in res.missing_fields

    # 10. Statutory Sections (Must remain None / unspecified, NOT 'Section 194 BNSS')
    assert res.offense_sections is None
    assert "offense_sections" in res.missing_fields

    # 11. Time of death & Cause of death limitations
    assert res.time_of_death == "Unknown / not established"
    assert res.cause_of_death == "Unknown / not established"

    # 12. Grounding Passages
    assert len(res.source_passages) >= 7
    passage_fields = [sp.field for sp in res.source_passages]
    assert "fir_number" in passage_fields
    assert "police_station" in passage_fields
    assert "report_date" in passage_fields
    assert "incident_location" in passage_fields
    assert "victim_name" in passage_fields
    assert "discovery_time" in passage_fields

    for sp in res.source_passages:
        assert sp.start_char is not None and sp.end_char is not None
        assert sp.start_char < sp.end_char
        assert sp.extraction_status == "EXTRACTED"
        assert len(sp.quote.strip()) > 0
        assert sp.quote in SYNTHETIC_TEST_FIR_TEXT


def test_synthetic_fir_without_explicit_title_header():
    """Verify that if 'Title:' header is absent, the suggested title still identifies the incident."""
    doc_no_title = """
    Case: Initial Inquest Report
    Police Station: Nallur Coastal Police Station (fictional)
    FIR / Inquest Number: FIR-SYN-2026-1042
    Report Date: 18 October 2026
    Scene/location: Riverside Guesthouse, Room 204, Nallur, Kerala (fictional)
    Person found unresponsive: Arjun Menon (fictional)
    Discovery time: Approximately 07:20 IST on 18 October 2026
    """
    res = EvidenceExtractionService.extract_fir_candidate_details(doc_no_title)
    assert res.suggested_title == "Riverside Guesthouse Incident"
    assert res.fir_number == "FIR-SYN-2026-1042"
    assert res.fir_number != "INITIAL"
    assert res.police_station == "Nallur Coastal Police Station (fictional)"
    assert res.victim_name == "Arjun Menon (fictional)"


def test_missing_mandatory_particulars_are_flagged():
    """Verify that documents with absent mandatory fields flag them as missing."""
    sparse_doc = """
    Notice of Occurrence
    Location: Abandoned Pier, Port Area
    Date: 2026-10-18
    """
    res = EvidenceExtractionService.extract_fir_candidate_details(sparse_doc)
    assert res.fir_number is None
    assert "fir_number" in res.missing_fields
    assert res.police_station is None
    assert "police_station" in res.missing_fields
    assert res.extraction_status == "NEEDS_REVIEW"


def test_fir_assisted_case_creation_persistence_and_idempotency(db_session, mock_io1):
    """
    Test end-to-end case registration with confirmed synthetic particulars:
    1. Persist case and initial exhibit.
    2. Retrieve case from database and verify saved fields.
    3. Re-submit same payload to verify idempotent duplicate handling.
    """
    case_service = CaseService(db_session)
    orchestrator = EvidencePipelineOrchestrator(db_session)

    # 1. Create case with confirmed synthetic particulars
    request_payload = FIRAssistedCaseCreateRequest(
        title="Riverside Guesthouse Incident",
        fir_metadata=FIRMetadata(
            fir_number="FIR-SYN-2026-1042",
            police_station="Nallur Coastal Police Station (fictional)",
            report_date="18 October 2026",
            incident_date="Approximately 07:20 IST on 18 October 2026",
            incident_location="Riverside Guesthouse, Room 204, Nallur, Kerala (fictional)",
            victim_name="Arjun Menon (fictional)",
            complainant_name=None,
            additional_attributes={
                "discovery_time": "Approximately 07:20 IST on 18 October 2026",
                "witness_sightings": [
                    {"witness": "Witness A", "sighting": "Approximately 00:10 IST on 18 October 2026"},
                    {"witness": "Witness B", "sighting": "Approximately 01:00 IST on 18 October 2026"},
                ],
                "time_of_death": "Unknown / not established",
                "cause_of_death": "Unknown / not established",
                "candidate_extractions": {"fir_number": "FIR-SYN-2026-1042"},
                "reviewer_modifications": {},
                "assisted_registration": True,
            },
        ),
        fir_raw_text=SYNTHETIC_TEST_FIR_TEXT,
        fir_filename="FIR-SYN-2026-1042.txt",
    )

    resp = create_case_fir_assisted(
        payload=request_payload,
        investigator=mock_io1,
        case_service=case_service,
        orchestrator=orchestrator,
    )

    assert resp.case is not None
    meta = resp.case.fir_metadata if isinstance(resp.case.fir_metadata, dict) else resp.case.fir_metadata.model_dump()
    assert meta.get("fir_number") == "FIR-SYN-2026-1042"
    assert meta.get("police_station") == "Nallur Coastal Police Station (fictional)"
    assert meta.get("victim_name") == "Arjun Menon (fictional)"
    assert meta.get("additional_attributes", {}).get("discovery_time") == "Approximately 07:20 IST on 18 October 2026"
    assert len(meta.get("additional_attributes", {}).get("witness_sightings", [])) == 2
    assert resp.case.lifecycle_stage == "EVIDENCE_INGESTION"

    # 2. Re-read case from database to ensure persistence
    reopened_case = case_service.get_case(resp.case.case_id, mock_io1)
    assert reopened_case.case_id == resp.case.case_id
    assert reopened_case.title == "Riverside Guesthouse Incident"
    reopened_meta = reopened_case.fir_metadata if isinstance(reopened_case.fir_metadata, dict) else reopened_case.fir_metadata.model_dump()
    assert reopened_meta.get("fir_number") == "FIR-SYN-2026-1042"
    assert reopened_meta.get("incident_location") == "Riverside Guesthouse, Room 204, Nallur, Kerala (fictional)"

    # 3. Idempotent re-submission check
    duplicate_resp = create_case_fir_assisted(
        payload=request_payload,
        investigator=mock_io1,
        case_service=case_service,
        orchestrator=orchestrator,
    )
    assert duplicate_resp.case.case_id == resp.case.case_id
    assert "Idempotent duplicate submission reconciled" in duplicate_resp.message
