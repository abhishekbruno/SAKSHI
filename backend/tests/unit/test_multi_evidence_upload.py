"""
SAKSHI Unit and Integration Tests: Multi-File Evidence Upload Pipeline.

Verifies:
1. Intake of multiple evidence files (Witness A and Witness B statements).
2. Each uploaded exhibit is assigned a distinct canonical evidence identifier.
3. Exhibits are persistently stored and linked to the correct case ID.
4. List query returns all distinct exhibits without dropping or replacing earlier items.
5. Ingestion gate permits transition to EVIDENCE_INGESTION from INITIALIZED or EVIDENCE_PROCESSING.
6. Empty payload (0 bytes) raises InvalidEvidenceDataException.
7. REST API endpoint /cases/{case_id}/evidence successfully handles sequential and batch intake.
"""
import pytest
import tempfile
import shutil
from fastapi.testclient import TestClient

from app.main import app
from app.services.case_service import CaseService
from app.services.evidence_intake_service import EvidenceIntakeService
from app.services.stage_engine import stage_engine
from app.schemas.case import CaseCreateRequest, FIRMetadata
from app.schemas.evidence import (
    EvidenceCategory,
    EvidenceIntakeMetadata,
    EvidenceIntakeStatus,
)
from app.core.errors import InvalidEvidenceDataException, IngestionGateClosedException


@pytest.fixture
def workspace_dir():
    temp_dir = tempfile.mkdtemp(prefix="sakshi_multi_upload_ws_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def multi_test_case(db_session, mock_io1, workspace_dir):
    """Creates a case and advances its stage to EVIDENCE_INGESTION."""
    case_service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Riverside Guesthouse Incident - Test Multi-Upload",
        fir_metadata=FIRMetadata(
            fir_number="FIR-SYN-2026-MULTI",
            police_station="Nallur Coastal Police Station",
            incident_date="2026-10-18T00:00:00Z",
            jurisdiction_code="JUR-DEL-04"
        )
    )
    case_resp = case_service.create_case(payload, mock_io1)

    case_entity = case_service.repo.get_by_case_id(case_resp.case_id)
    case_entity.case_workspace_path = workspace_dir
    case_service.repo.update(case_entity)

    case_service.update_stage(case_resp.case_id, "EVIDENCE_INGESTION", mock_io1)
    return case_service.repo.get_by_case_id(case_resp.case_id)


def test_multi_evidence_upload_sequential_persistence(db_session, multi_test_case, mock_io1):
    """
    Verifies that uploading Witness A and Witness B statements alongside initial FIR
    creates distinct exhibits, all persisted and associated with the case.
    """
    service = EvidenceIntakeService(db_session)
    case_id = multi_test_case.case_id

    # 1. Intake Exhibit 1: FIR intake
    fir_content = b"FIRST INFORMATION REPORT - FIR-SYN-2026-MULTI"
    meta_fir = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.DOCUMENT_PDF,
        declared_mime_type="text/plain",
        source_device_or_person="Station House Officer",
        description="Initial FIR Intake Document",
    )
    exhibit1 = service.register_evidence(
        case_id=case_id,
        file_payload=fir_content,
        original_filename="01_SYNTHETIC_FIR_INTAKE.txt",
        metadata=meta_fir,
        investigator=mock_io1,
    )

    # 2. Intake Exhibit 2: Witness A Statement
    witness_a_content = (
        b"STATEMENT OF WITNESS A (Sunil Kumar)\n"
        b"Recorded on 18 October 2026 at 11:30 IST.\n"
        b"Observed Arjun Menon entering Room 204 at approximately 00:10 IST on 18 October 2026."
    )
    meta_a = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.DOCUMENT_PDF,
        declared_mime_type="text/plain",
        source_device_or_person="Sunil Kumar (Receptionist)",
        description="Witness A Signed Statement",
    )
    exhibit2 = service.register_evidence(
        case_id=case_id,
        file_payload=witness_a_content,
        original_filename="02_WITNESS_A_STATEMENT.txt",
        metadata=meta_a,
        investigator=mock_io1,
    )

    # 3. Intake Exhibit 3: Witness B Statement
    witness_b_content = (
        b"STATEMENT OF WITNESS B (Deepa Pillai)\n"
        b"Recorded on 18 October 2026 at 12:15 IST.\n"
        b"Saw Arjun Menon in corridor talking on mobile phone at approximately 01:00 IST on 18 October 2026."
    )
    meta_b = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.DOCUMENT_PDF,
        declared_mime_type="text/plain",
        source_device_or_person="Deepa Pillai (Housekeeping Staff)",
        description="Witness B Signed Statement",
    )
    exhibit3 = service.register_evidence(
        case_id=case_id,
        file_payload=witness_b_content,
        original_filename="03_WITNESS_B_STATEMENT.txt",
        metadata=meta_b,
        investigator=mock_io1,
    )

    # Invariants:
    # 1. Distinct evidence identifiers
    evidence_ids = {exhibit1.evidence_id, exhibit2.evidence_id, exhibit3.evidence_id}
    assert len(evidence_ids) == 3, "All exhibits must receive distinct evidence identifiers"

    # 2. Correct case association
    assert exhibit1.case_id == case_id
    assert exhibit2.case_id == case_id
    assert exhibit3.case_id == case_id

    # 3. Correct filenames and sizes
    assert exhibit1.original_file_name == "01_SYNTHETIC_FIR_INTAKE.txt"
    assert exhibit2.original_file_name == "02_WITNESS_A_STATEMENT.txt"
    assert exhibit3.original_file_name == "03_WITNESS_B_STATEMENT.txt"
    assert exhibit2.file_size_bytes == len(witness_a_content)
    assert exhibit3.file_size_bytes == len(witness_b_content)

    # 4. Query register: all exhibits are returned
    listed = service.list_evidence(case_id=case_id, investigator=mock_io1)
    assert listed.total == 3
    filenames = {e.original_file_name for e in listed.items}
    assert "01_SYNTHETIC_FIR_INTAKE.txt" in filenames
    assert "02_WITNESS_A_STATEMENT.txt" in filenames
    assert "03_WITNESS_B_STATEMENT.txt" in filenames


def test_intake_rejected_on_empty_payload(db_session, multi_test_case, mock_io1):
    """Verifies that an empty evidence file (0 bytes) is rejected with InvalidEvidenceDataException."""
    service = EvidenceIntakeService(db_session)
    case_id = multi_test_case.case_id

    meta = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.DOCUMENT_PDF,
        declared_mime_type="text/plain",
        source_device_or_person="Test Officer",
    )

    with pytest.raises(InvalidEvidenceDataException, match="cannot be empty"):
        service.register_evidence(
            case_id=case_id,
            file_payload=b"",
            original_filename="empty_file.txt",
            metadata=meta,
            investigator=mock_io1,
        )


def test_stage_engine_transition_permits_multi_file_intake(db_session, multi_test_case, mock_io1):
    """
    Verifies that if a case moves to EVIDENCE_PROCESSING after the first file,
    transitioning back to EVIDENCE_INGESTION is fully valid and allows subsequent uploads.
    """
    case_service = CaseService(db_session)
    service = EvidenceIntakeService(db_session)
    case_id = multi_test_case.case_id

    # Advance to EVIDENCE_PROCESSING (as happens after initial verification)
    case_service.update_stage(case_id, "EVIDENCE_PROCESSING", mock_io1)
    updated_case = case_service.repo.get_by_case_id(case_id)
    assert updated_case.lifecycle_stage == "EVIDENCE_PROCESSING"

    # Ingestion is closed while in EVIDENCE_PROCESSING
    assert not stage_engine.is_ingestion_permitted(updated_case.lifecycle_stage)
    meta = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.DOCUMENT_PDF,
        declared_mime_type="text/plain",
        source_device_or_person="Test Officer",
    )
    with pytest.raises(IngestionGateClosedException):
        service.register_evidence(
            case_id=case_id,
            file_payload=b"test data",
            original_filename="02_WITNESS_A_STATEMENT.txt",
            metadata=meta,
            investigator=mock_io1,
        )

    # Valid transition: EVIDENCE_PROCESSING -> EVIDENCE_INGESTION
    can_trans = stage_engine.can_transition("EVIDENCE_PROCESSING", "EVIDENCE_INGESTION")
    assert can_trans is True

    case_service.update_stage(case_id, "EVIDENCE_INGESTION", mock_io1)
    refreshed_case = case_service.repo.get_by_case_id(case_id)
    assert refreshed_case.lifecycle_stage == "EVIDENCE_INGESTION"

    # Now intake succeeds
    exhibit = service.register_evidence(
        case_id=case_id,
        file_payload=b"Witness A Statement content",
        original_filename="02_WITNESS_A_STATEMENT.txt",
        metadata=meta,
        investigator=mock_io1,
    )
    assert exhibit.evidence_id.startswith("SAKSHI-EVID-")
    assert exhibit.original_file_name == "02_WITNESS_A_STATEMENT.txt"


def test_api_v1_multi_evidence_upload(client, multi_test_case, mock_io1):
    """
    Verifies multi-evidence upload through the FastAPI REST endpoint.
    """
    case_id = multi_test_case.case_id
    headers = {
        "X-Investigator-Id": mock_io1.subject_id,
        "X-Investigator-Role": mock_io1.role,
        "X-Investigator-Jurisdiction": mock_io1.station_jurisdiction,
    }

    # Upload file 1: Witness A
    res_a = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers=headers,
        data={
            "evidence_category": "DOCUMENT_PDF",
            "declared_mime_type": "text/plain",
            "source_device_or_person": "Sunil Kumar",
            "description": "Witness A Statement",
        },
        files={"file": ("02_WITNESS_A_STATEMENT.txt", b"Witness A statement data", "text/plain")}
    )
    assert res_a.status_code == 201, f"Expected 201, got {res_a.status_code}: {res_a.text}"
    data_a = res_a.json()
    assert data_a["original_file_name"] == "02_WITNESS_A_STATEMENT.txt"
    eid_a = data_a["evidence_id"]

    # Upload file 2: Witness B
    res_b = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        headers=headers,
        data={
            "evidence_category": "DOCUMENT_PDF",
            "declared_mime_type": "text/plain",
            "source_device_or_person": "Deepa Pillai",
            "description": "Witness B Statement",
        },
        files={"file": ("03_WITNESS_B_STATEMENT.txt", b"Witness B statement data", "text/plain")}
    )
    assert res_b.status_code == 201, f"Expected 201, got {res_b.status_code}: {res_b.text}"
    data_b = res_b.json()
    assert data_b["original_file_name"] == "03_WITNESS_B_STATEMENT.txt"
    eid_b = data_b["evidence_id"]

    assert eid_a != eid_b, "Evidence IDs must be distinct"

    # List evidence
    res_list = client.get(f"/api/v1/cases/{case_id}/evidence", headers=headers)
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total"] >= 2
    uploaded_names = [e["original_file_name"] for e in list_data["items"]]
    assert "02_WITNESS_A_STATEMENT.txt" in uploaded_names
    assert "03_WITNESS_B_STATEMENT.txt" in uploaded_names
