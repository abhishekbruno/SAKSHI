"""
Unit tests for MOD-05 Evidence Intake Service domain logic.
Tests raw evidence intake, canonical Evidence ID generation, filename sanitization,
Stage Engine gate enforcement, authorization policies, and downstream handoff contracts.
"""
import io
import os
import shutil
import tempfile
import pytest

from app.services.case_service import CaseService
from app.services.evidence_intake_service import EvidenceIntakeService
from app.schemas.case import CaseCreateRequest, FIRMetadata
from app.schemas.evidence import (
    EvidenceCategory,
    EvidenceIntakeMetadata,
    EvidenceIntakeStatus,
    RegisteredEvidenceObject,
)
from app.core.errors import (
    CaseNotFoundException,
    EvidenceNotFoundException,
    IngestionGateClosedException,
    InvalidEvidenceDataException,
    ForbiddenException,
)
from app.core.security import AuthenticatedInvestigator


@pytest.fixture
def workspace_dir():
    temp_dir = tempfile.mkdtemp(prefix="sakshi_test_ws_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def active_case(db_session, mock_io1, workspace_dir):
    """Creates a case and advances its stage to EVIDENCE_INGESTION."""
    case_service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Unnatural Death Investigation - Room 101",
        fir_metadata=FIRMetadata(
            fir_number="FIR-2026-INTAKE-01",
            police_station="Central Police Station",
            incident_date="2026-10-01T20:00:00Z",
            jurisdiction_code="JUR-DEL-04"
        )
    )
    case_resp = case_service.create_case(payload, mock_io1)

    # Use the test workspace directory
    case_entity = case_service.repo.get_by_case_id(case_resp.case_id)
    case_entity.case_workspace_path = workspace_dir
    case_service.repo.update(case_entity)

    # Advance stage from INITIALIZED to EVIDENCE_INGESTION
    case_service.update_stage(case_resp.case_id, "EVIDENCE_INGESTION", mock_io1)
    return case_service.repo.get_by_case_id(case_resp.case_id)


def test_evidence_id_generation():
    id1 = EvidenceIntakeService.generate_evidence_id()
    id2 = EvidenceIntakeService.generate_evidence_id()

    assert id1.startswith("SAKSHI-EVID-")
    assert id2.startswith("SAKSHI-EVID-")
    assert id1 != id2


def test_filename_sanitization():
    # Path traversal attack
    traversal = "../../../etc/shadow"
    assert EvidenceIntakeService.sanitize_filename(traversal) == "shadow"

    # Windows-style path traversal
    win_traversal = "..\\..\\windows\\system32\\calc.exe"
    assert EvidenceIntakeService.sanitize_filename(win_traversal) == "calc.exe"

    # Illegal chars and control characters
    illegal = "test<file>:*?.pdf"
    assert EvidenceIntakeService.sanitize_filename(illegal) == "test_file____.pdf"

    # Empty or blank filename
    empty = ""
    sanitized_empty = EvidenceIntakeService.sanitize_filename(empty)
    assert sanitized_empty.startswith("evidence_")
    assert sanitized_empty.endswith(".bin")


def test_evidence_intake_success(db_session, active_case, mock_io1):
    service = EvidenceIntakeService(db_session)
    sample_content = b"%PDF-1.4 simulated inquest report content"

    metadata = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.DOCUMENT_PDF,
        declared_mime_type="application/pdf",
        collection_location="Civil Hospital Mortuary",
        source_device_or_person="Dr. A. Verma, Medical Examiner",
        description="Signed preliminary post-mortem inquest report"
    )

    evidence = service.register_evidence(
        case_id=active_case.case_id,
        file_payload=sample_content,
        original_filename="inquest_report.pdf",
        metadata=metadata,
        investigator=mock_io1,
    )

    assert evidence.evidence_id.startswith("SAKSHI-EVID-")
    assert evidence.case_id == active_case.case_id
    assert evidence.original_file_name == "inquest_report.pdf"
    assert evidence.stored_file_name == "inquest_report.pdf"
    assert evidence.evidence_category == EvidenceCategory.DOCUMENT_PDF.value
    assert evidence.declared_mime_type == "application/pdf"
    assert evidence.file_size_bytes == len(sample_content)
    assert evidence.submitting_investigator_id == mock_io1.investigator_id
    assert evidence.status == EvidenceIntakeStatus.REGISTERED_INTAKE.value
    assert os.path.exists(evidence.raw_storage_path)

    with open(evidence.raw_storage_path, "rb") as f:
        assert f.read() == sample_content


def test_evidence_intake_gate_closed_in_initialized_stage(db_session, mock_io1, workspace_dir):
    """Case is in INITIALIZED stage — intake gate must be closed."""
    case_service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Unnatural Death Investigation - Room 102",
        fir_metadata=FIRMetadata(
            fir_number="FIR-2026-INTAKE-02",
            police_station="Central Police Station"
        )
    )
    case_resp = case_service.create_case(payload, mock_io1)
    case_entity = case_service.repo.get_by_case_id(case_resp.case_id)
    case_entity.case_workspace_path = workspace_dir
    case_service.repo.update(case_entity)

    service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.SCENE_PHOTO,
        declared_mime_type="image/jpeg",
    )

    with pytest.raises(IngestionGateClosedException) as exc_info:
        service.register_evidence(
            case_id=case_resp.case_id,
            file_payload=b"\xFF\xD8\xFF image data",
            original_filename="crime_scene_01.jpg",
            metadata=metadata,
            investigator=mock_io1,
        )
    assert "INITIALIZED" in str(exc_info.value)
    assert "EVIDENCE_INGESTION" in str(exc_info.value)


def test_evidence_intake_empty_payload_rejected(db_session, active_case, mock_io1):
    service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.AUDIO_RECORDING,
        declared_mime_type="audio/wav",
    )

    with pytest.raises(InvalidEvidenceDataException) as exc_info:
        service.register_evidence(
            case_id=active_case.case_id,
            file_payload=b"",
            original_filename="empty_recording.wav",
            metadata=metadata,
            investigator=mock_io1,
        )
    assert "0 bytes" in str(exc_info.value)


def test_evidence_intake_case_not_found(db_session, mock_io1):
    service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.CDR_SPREADSHEET,
        declared_mime_type="text/csv",
    )

    with pytest.raises(CaseNotFoundException):
        service.register_evidence(
            case_id="SAKSHI-CASE-NONEXISTENT",
            file_payload=b"timestamp,caller,receiver\n",
            original_filename="cdr.csv",
            metadata=metadata,
            investigator=mock_io1,
        )


def test_evidence_intake_authorization_enforcement(db_session, active_case, mock_io2):
    """IO2 is not assigned to this case and does not share jurisdiction."""
    service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.DIGITAL_DEVICE_EXTRACTION,
        declared_mime_type="application/octet-stream",
    )

    with pytest.raises(ForbiddenException):
        service.register_evidence(
            case_id=active_case.case_id,
            file_payload=b"device extraction bits",
            original_filename="phone_dump.bin",
            metadata=metadata,
            investigator=mock_io2,
        )


def test_evidence_list_and_get(db_session, active_case, mock_io1):
    service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.CDR_SPREADSHEET,
        declared_mime_type="text/csv",
    )

    ev1 = service.register_evidence(
        case_id=active_case.case_id,
        file_payload=b"cell tower dump 1",
        original_filename="dump1.csv",
        metadata=metadata,
        investigator=mock_io1,
    )
    ev2 = service.register_evidence(
        case_id=active_case.case_id,
        file_payload=b"cell tower dump 2",
        original_filename="dump2.csv",
        metadata=metadata,
        investigator=mock_io1,
    )

    listed = service.list_evidence(active_case.case_id, mock_io1)
    assert listed.total == 2
    assert len(listed.items) == 2

    retrieved = service.get_evidence(active_case.case_id, ev1.evidence_id, mock_io1)
    assert retrieved.evidence_id == ev1.evidence_id
    assert retrieved.stored_file_name == "dump1.csv"

    # Non-existent evidence ID raises EvidenceNotFoundException
    with pytest.raises(EvidenceNotFoundException):
        service.get_evidence(active_case.case_id, "SAKSHI-EVID-FAKE-0000", mock_io1)


def test_registered_evidence_object_contract(db_session, active_case, mock_io1):
    service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.AUTOPSY_PHOTO,
        declared_mime_type="image/jpeg",
        description="External trauma photograph"
    )

    ev = service.register_evidence(
        case_id=active_case.case_id,
        file_payload=b"\xFF\xD8\xFF\xE0 post mortem photo",
        original_filename="autopsy_01.jpg",
        metadata=metadata,
        investigator=mock_io1,
    )

    db_entity = service.evidence_repo.get_by_evidence_id(ev.evidence_id)
    contract = service.to_registered_evidence_object(db_entity)

    assert isinstance(contract, RegisteredEvidenceObject)
    assert contract.evidence_id == ev.evidence_id
    assert contract.case_id == active_case.case_id
    assert contract.staged_file_path == ev.raw_storage_path
    assert contract.original_file_name == "autopsy_01.jpg"
    assert contract.declared_mime_type == "image/jpeg"
    assert contract.evidence_category == EvidenceCategory.AUTOPSY_PHOTO.value
    assert contract.file_size_bytes == len(b"\xFF\xD8\xFF\xE0 post mortem photo")
    assert contract.submitting_investigator_id == mock_io1.investigator_id
    assert contract.intake_status == EvidenceIntakeStatus.REGISTERED_INTAKE.value
