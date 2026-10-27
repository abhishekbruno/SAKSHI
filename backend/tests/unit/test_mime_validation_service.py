"""
Unit tests for MOD-06 MIME & File Signature Validation Service.
Tests magic-byte verification, declared vs detected MIME comparison,
allowlist enforcement, disguised executables, extension checks, case isolation,
state transitions, and downstream handoff contract creation.
"""
import os
import shutil
import tempfile
import pytest

from app.services.case_service import CaseService
from app.services.evidence_intake_service import EvidenceIntakeService
from app.services.mime_validation_service import MimeValidationService
from app.schemas.case import CaseCreateRequest, FIRMetadata
from app.schemas.evidence import (
    EvidenceCategory,
    EvidenceIntakeMetadata,
    EvidenceIntakeStatus,
    ValidatedEvidenceObject,
)
from app.core.errors import (
    CaseNotFoundException,
    EvidenceNotFoundException,
    EvidenceFileNotFoundException,
    EvidenceValidationFailedException,
    ForbiddenException,
)


@pytest.fixture
def workspace_dir():
    temp_dir = tempfile.mkdtemp(prefix="sakshi_mod06_ws_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def active_case(db_session, mock_io1, workspace_dir):
    """Creates a case in EVIDENCE_INGESTION stage with an isolated test workspace."""
    case_service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Unnatural Death Investigation - Forensic Ballistics Case",
        fir_metadata=FIRMetadata(
            fir_number="FIR-2026-VAL-01",
            police_station="Central Police Station",
            jurisdiction_code="JUR-DEL-04"
        )
    )
    case_resp = case_service.create_case(payload, mock_io1)

    case_entity = case_service.repo.get_by_case_id(case_resp.case_id)
    case_entity.case_workspace_path = workspace_dir
    case_service.repo.update(case_entity)

    case_service.update_stage(case_resp.case_id, "EVIDENCE_INGESTION", mock_io1)
    return case_service.repo.get_by_case_id(case_resp.case_id)


def _register_test_evidence(
    db_session,
    active_case,
    mock_io1,
    payload_bytes: bytes,
    filename: str,
    declared_mime: str,
    category: EvidenceCategory = EvidenceCategory.DOCUMENT_PDF,
):
    intake_service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=category,
        declared_mime_type=declared_mime,
        description="Test evidence object for MOD-06 validation"
    )
    return intake_service.register_evidence(
        case_id=active_case.case_id,
        file_payload=payload_bytes,
        original_filename=filename,
        metadata=metadata,
        investigator=mock_io1,
    )


# ─── BASIC VALID TYPES ──────────────────────────────────────────────────

def test_valid_pdf_signature(db_session, active_case, mock_io1):
    pdf_content = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
    ev = _register_test_evidence(db_session, active_case, mock_io1, pdf_content, "autopsy.pdf", "application/pdf")

    service = MimeValidationService(db_session)
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)

    assert result.valid is True
    assert result.status == "VALIDATED"
    assert result.detected_mime == "application/pdf"
    assert result.detected_format == "PDF"
    assert "matches" in result.validation_reason.lower()


def test_valid_jpeg_signature(db_session, active_case, mock_io1):
    jpeg_content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C"
    ev = _register_test_evidence(
        db_session, active_case, mock_io1, jpeg_content, "scene.jpg", "image/jpeg", EvidenceCategory.SCENE_PHOTO
    )

    service = MimeValidationService(db_session)
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)

    assert result.valid is True
    assert result.status == "VALIDATED"
    assert result.detected_mime == "image/jpeg"
    assert result.detected_format == "JPEG"


def test_valid_png_signature(db_session, active_case, mock_io1):
    png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    ev = _register_test_evidence(
        db_session, active_case, mock_io1, png_content, "injury_diagram.png", "image/png", EvidenceCategory.AUTOPSY_PHOTO
    )

    service = MimeValidationService(db_session)
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)

    assert result.valid is True
    assert result.status == "VALIDATED"
    assert result.detected_mime == "image/png"
    assert result.detected_format == "PNG"


def test_valid_audio_wav_signature(db_session, active_case, mock_io1):
    wav_content = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00data\x00\x00\x00\x00"
    ev = _register_test_evidence(
        db_session, active_case, mock_io1, wav_content, "control_room_112.wav", "audio/wav", EvidenceCategory.AUDIO_RECORDING
    )

    service = MimeValidationService(db_session)
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)

    assert result.valid is True
    assert result.status == "VALIDATED"
    assert result.detected_mime == "audio/wav"
    assert result.detected_format == "WAV"


def test_valid_audio_mp3_signature(db_session, active_case, mock_io1):
    mp3_content = b"ID3\x03\x00\x00\x00\x00\x00#TSSE\x00\x00\x00\x0f\x00\x00\x03Lavf58.29.100\x00"
    ev = _register_test_evidence(
        db_session, active_case, mock_io1, mp3_content, "witness_interview.mp3", "audio/mpeg", EvidenceCategory.AUDIO_RECORDING
    )

    service = MimeValidationService(db_session)
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)

    assert result.valid is True
    assert result.status == "VALIDATED"
    assert result.detected_mime in ["audio/mpeg", "audio/mp3"]


def test_valid_csv_spreadsheet(db_session, active_case, mock_io1):
    csv_content = b"call_datetime,tower_id,caller_msisdn,duration\n2026-10-01 10:00:00,TWR-04,+919876543210,45\n"
    ev = _register_test_evidence(
        db_session, active_case, mock_io1, csv_content, "tower_dump.csv", "text/csv", EvidenceCategory.CDR_SPREADSHEET
    )

    service = MimeValidationService(db_session)
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)

    assert result.valid is True
    assert result.status == "VALIDATED"
    assert result.detected_mime in ["text/csv", "text/plain"]


# ─── SIGNATURE MISMATCHES ───────────────────────────────────────────────

def test_jpeg_declared_as_pdf_rejected(db_session, active_case, mock_io1):
    jpeg_content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
    ev = _register_test_evidence(
        db_session, active_case, mock_io1, jpeg_content, "fake_doc.pdf", "application/pdf", EvidenceCategory.DOCUMENT_PDF
    )

    service = MimeValidationService(db_session)
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)

    assert result.valid is False
    assert result.status == "REJECTED"
    assert "mismatch" in result.validation_reason.lower()
    assert result.detected_mime == "image/jpeg"


def test_pdf_declared_as_jpeg_rejected(db_session, active_case, mock_io1):
    pdf_content = b"%PDF-1.4 sample pdf content"
    ev = _register_test_evidence(
        db_session, active_case, mock_io1, pdf_content, "disguised_photo.jpg", "image/jpeg", EvidenceCategory.SCENE_PHOTO
    )

    service = MimeValidationService(db_session)
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)

    assert result.valid is False
    assert result.status == "REJECTED"
    assert "mismatch" in result.validation_reason.lower()
    assert result.detected_mime == "application/pdf"


def test_windows_executable_declared_as_pdf_rejected(db_session, active_case, mock_io1):
    exe_content = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00This program cannot be run in DOS mode."
    ev = _register_test_evidence(
        db_session, active_case, mock_io1, exe_content, "malicious_report.pdf", "application/pdf", EvidenceCategory.DOCUMENT_PDF
    )

    service = MimeValidationService(db_session)
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)

    assert result.valid is False
    assert result.status == "REJECTED"
    assert "executable" in result.validation_reason.lower()


def test_linux_elf_executable_declared_as_csv_rejected(db_session, active_case, mock_io1):
    elf_content = b"\x7fELF\x02\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x02\x00>\x00"
    ev = _register_test_evidence(
        db_session, active_case, mock_io1, elf_content, "cdr_dump.csv", "text/csv", EvidenceCategory.CDR_SPREADSHEET
    )

    service = MimeValidationService(db_session)
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)

    assert result.valid is False
    assert result.status == "REJECTED"
    assert "executable" in result.validation_reason.lower()


# ─── UNKNOWN / DANGEROUS EXTENSION / ALLOWLIST ─────────────────────────

def test_unknown_binary_signature_rejected(db_session, active_case, mock_io1):
    # Random binary noise that matches no known format
    random_binary = b"\x01\x02\x03\x04\x05\x06\x07\x08\xaa\xbb\xcc\xdd\xee\xff"
    ev = _register_test_evidence(
        db_session, active_case, mock_io1, random_binary, "corrupt_data.pdf", "application/pdf", EvidenceCategory.DOCUMENT_PDF
    )

    service = MimeValidationService(db_session)
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)

    assert result.valid is False
    assert result.status == "REJECTED"
    assert "failed" in result.validation_reason.lower() or "unrecognized" in result.validation_reason.lower()


def test_disallowed_mime_type_rejected(db_session, active_case, mock_io1):
    # Register with a MIME not in allowlist (e.g. application/x-msdos-program)
    # Using raw DB injection to simulate a bypassed or unknown declared type
    intake_service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.OTHER,
        declared_mime_type="application/x-msdos-program",  # not in ALLOWED_MIME_TYPES
    )
    ev = intake_service.register_evidence(
        case_id=active_case.case_id,
        file_payload=b"RIFF\x00\x00\x00\x00AVI ",
        original_filename="sample.avi",
        metadata=metadata,
        investigator=mock_io1,
    )

    service = MimeValidationService(db_session)
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)

    assert result.valid is False
    assert result.status == "REJECTED"
    assert "not permitted" in result.validation_reason.lower()


def test_dangerous_extension_rejected(db_session, active_case, mock_io1):
    # Valid PDF magic bytes, but extension is .exe
    pdf_content = b"%PDF-1.4 valid pdf content"
    ev = _register_test_evidence(
        db_session, active_case, mock_io1, pdf_content, "malicious.exe", "application/pdf", EvidenceCategory.DOCUMENT_PDF
    )

    service = MimeValidationService(db_session)
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)

    assert result.valid is False
    assert result.status == "REJECTED"
    assert "suspicious extension" in result.validation_reason.lower()


# ─── SECURITY & BOUNDARIES ──────────────────────────────────────────────

def test_missing_file_raises_error(db_session, active_case, mock_io1):
    pdf_content = b"%PDF-1.4 valid pdf"
    ev = _register_test_evidence(db_session, active_case, mock_io1, pdf_content, "test.pdf", "application/pdf")

    # Delete the physical staged file
    os.remove(ev.raw_storage_path)

    service = MimeValidationService(db_session)
    with pytest.raises(EvidenceFileNotFoundException):
        service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)


def test_cross_case_isolation_enforced(db_session, active_case, mock_io1, workspace_dir):
    # Create Case B
    case_service = CaseService(db_session)
    case_b_resp = case_service.create_case(
        CaseCreateRequest(
            title="Case B",
            fir_metadata=FIRMetadata(fir_number="FIR-CASE-B", police_station="Central Police Station")
        ),
        mock_io1
    )
    case_b = case_service.repo.get_by_case_id(case_b_resp.case_id)
    case_b.case_workspace_path = workspace_dir
    case_service.repo.update(case_b)

    # Register evidence under Case A
    ev_a = _register_test_evidence(db_session, active_case, mock_io1, b"%PDF-1.4", "doc.pdf", "application/pdf")

    # Attempt to validate Case A's evidence under Case B's ID -> EvidenceNotFoundException
    service = MimeValidationService(db_session)
    with pytest.raises(EvidenceNotFoundException):
        service.validate_evidence(case_b.case_id, ev_a.evidence_id, mock_io1)


def test_unauthorized_investigator_forbidden(db_session, active_case, mock_io1, mock_io2):
    pdf_content = b"%PDF-1.4 valid pdf"
    ev = _register_test_evidence(db_session, active_case, mock_io1, pdf_content, "doc.pdf", "application/pdf")

    service = MimeValidationService(db_session)
    # mock_io2 has different jurisdiction and is not assigned to this case
    with pytest.raises(ForbiddenException):
        service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io2)


# ─── STATE & MOD-07 HANDOFF CONTRACT ────────────────────────────────────

def test_validated_evidence_state_and_handoff(db_session, active_case, mock_io1):
    pdf_content = b"%PDF-1.4 valid pdf content for handoff"
    ev = _register_test_evidence(db_session, active_case, mock_io1, pdf_content, "handoff.pdf", "application/pdf")

    service = MimeValidationService(db_session)
    # 1. Unvalidated evidence cannot produce ValidatedEvidenceObject
    with pytest.raises(EvidenceValidationFailedException):
        service.get_validated_evidence_object(active_case.case_id, ev.evidence_id, mock_io1)

    # 2. Validate
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)
    assert result.status == "VALIDATED"

    # 3. Check DB persistence (original metadata preserved + validation attributes set)
    updated_ev = service.evidence_repo.get_by_evidence_id(ev.evidence_id)
    assert updated_ev.status == EvidenceIntakeStatus.VALIDATED.value
    assert updated_ev.detected_mime_type == "application/pdf"
    assert updated_ev.detected_format == "PDF"
    assert updated_ev.original_file_name == "handoff.pdf"  # preserved!
    assert updated_ev.declared_mime_type == "application/pdf"  # preserved!

    # 4. Successfully produce ValidatedEvidenceObject for MOD-07
    handoff = service.get_validated_evidence_object(active_case.case_id, ev.evidence_id, mock_io1)
    assert isinstance(handoff, ValidatedEvidenceObject)
    assert handoff.evidence_id == ev.evidence_id
    assert handoff.case_id == active_case.case_id
    assert handoff.verified_mime_type == "application/pdf"
    assert handoff.detected_format == "PDF"
    assert handoff.validation_status == "VALIDATED"


def test_rejected_evidence_cannot_proceed_to_mod07(db_session, active_case, mock_io1):
    # Rejectable mismatch
    jpeg_content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00"
    ev = _register_test_evidence(db_session, active_case, mock_io1, jpeg_content, "doc.pdf", "application/pdf")

    service = MimeValidationService(db_session)
    result = service.validate_evidence(active_case.case_id, ev.evidence_id, mock_io1)
    assert result.status == "REJECTED"

    # Attempt to retrieve handoff contract -> rejected!
    with pytest.raises(EvidenceValidationFailedException) as exc_info:
        service.get_validated_evidence_object(active_case.case_id, ev.evidence_id, mock_io1)
    assert "REJECTED" in str(exc_info.value)
    assert "cannot proceed to MOD-07" in str(exc_info.value)
