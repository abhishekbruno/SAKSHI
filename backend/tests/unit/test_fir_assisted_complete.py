"""
Unit and regression test suite for FIR-Assisted Case Creation & Evidence Capability Audit.
Tests:
- Phase 2: FIR preview, structured extraction, grounding source passages, suggested title,
  investigating officer extraction, missing/ambiguous fields, scanned PDF without OCR disclosure.
- Phase 2.D & 2.E: Investigator review, case initialization, original FIR preservation in WORM,
  idempotent reconciliation of duplicate submissions.
- Phase 3: Evidence category validation (DOCUMENT_PDF, MEDICAL_REPORT, SCENE_PHOTO, etc.)
  and strict rejection of category-to-format mismatches.
"""
import io
import base64
import pytest
from pypdf import PdfWriter

from app.schemas.case import (
    FIRMetadata,
    CaseCreateRequest,
    FIRAssistedCaseCreateRequest,
    FIRAssistedExtractResponse,
)
from app.schemas.evidence import EvidenceCategory, EvidenceIntakeMetadata
from app.services.case_service import CaseService
from app.services.evidence_extraction_service import EvidenceExtractionService
from app.services.evidence_intake_service import EvidenceIntakeService
from app.services.mime_validation_service import MimeValidationService
from app.services.evidence_pipeline_orchestrator import EvidencePipelineOrchestrator
from app.repositories.evidence_repository import EvidenceRepository


def _create_synthetic_fir_pdf(text_content: str) -> bytes:
    """Helper: builds a minimal synthetic PDF document containing the provided text."""
    pdf_buffer = io.BytesIO()
    # Write a simple valid PDF structure with the text in a stream
    raw_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<<>>>>endobj\n"
        b"4 0 obj<</Length " + str(len(text_content) + 50).encode("ascii") + b">>\nstream\n"
        b"BT /F1 12 Tf 72 712 Td (" + text_content.encode("latin-1", errors="replace") + b") Tj ET\n"
        b"endstream\nendobj\n"
        b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000216 00000 n \n"
        b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n350\n%%EOF\n"
    )
    return raw_pdf


# ─── 1. STRUCTURED FIR CANDIDATE EXTRACTION & PASSAGE GROUNDING ──────────────

def test_fir_candidate_extraction_with_source_grounding():
    fir_text = """
    FIRST INFORMATION REPORT
    (Under Section 154 Cr.P.C. / BNSS)
    1. District: South Delhi, Police Station: Hauz Khas Police Station
    2. FIR Number: FIR-2026-HK-0891
    3. Date of Report: 2026-10-18 09:30 AM
    4. Date and Time of Occurrence: 2026-10-18 01:15 AM
    5. Place of Occurrence: Room 204, Riverside Guesthouse, Hauz Khas Village
    6. Complainant / Informant: Rajesh Verma (Night Duty Manager)
    7. Victim / Deceased: Ananya Sharma
    8. Acts and Sections: Section 194 BNSS (Unnatural Death)
    9. Investigating Officer: Inspector K. S. Rathore
    10. Brief Facts: Information received regarding an unresponsive female guest found in Room 204.
    """
    res = EvidenceExtractionService.extract_fir_candidate_details(fir_text, filename="FIR_0891.txt")

    assert isinstance(res, FIRAssistedExtractResponse)
    assert res.fir_number == "FIR-2026-HK-0891"
    assert "Hauz Khas" in res.police_station
    assert res.incident_date == "2026-10-18 01:15 AM"
    assert "Riverside Guesthouse" in (res.incident_location or "")
    assert res.victim_name == "Ananya Sharma"
    assert "Rajesh Verma" in (res.complainant_name or "")
    assert "194" in (res.offense_sections or "")
    assert "Rathore" in (res.investigating_officer or "")

    # Suggested Title check
    assert res.suggested_title is not None
    assert "Ananya Sharma" in res.suggested_title
    assert "Riverside Guesthouse" in res.suggested_title or "Hauz Khas" in res.suggested_title

    # Source Passages check
    assert len(res.source_passages) >= 5
    fields = [sp.field for sp in res.source_passages]
    assert "fir_number" in fields
    assert "police_station" in fields
    assert "incident_date" in fields
    assert "incident_location" in fields
    assert "victim_name" in fields

    # Character offsets validation
    for sp in res.source_passages:
        assert sp.char_offset >= 0
        assert sp.start_char is not None
        assert sp.end_char is not None
        assert fir_text[sp.start_char:sp.end_char].strip() != ""


def test_fir_candidate_extraction_missing_and_ambiguous_fields():
    # Incomplete FIR text with approximate date
    incomplete_fir = """
    FIRST INFORMATION REPORT
    Police Station: Metro Sector 9
    FIR No: FIR-2026-INC-99
    Date of Occurrence: around midnight intervening night of 17-18 Oct 2026
    Place of Discovery: Highway Overpass
    """
    res = EvidenceExtractionService.extract_fir_candidate_details(incomplete_fir)

    # Ambiguous date detection
    assert "incident_date" in res.ambiguous_fields
    # Missing fields detection
    assert "victim_name" in res.missing_fields
    assert "complainant_name" in res.missing_fields
    assert "investigating_officer" in res.missing_fields
    assert "offense_sections" in res.missing_fields

    # Fallback neutral title without victim name
    assert "Unknown Subject" in (res.suggested_title or "")


def test_scanned_pdf_without_ocr_disclosure():
    # Scanned PDF with minimal/empty extractable text
    minimal_text = "   \n\n  "
    res = EvidenceExtractionService.extract_fir_candidate_details(minimal_text, filename="scanned_fir.pdf")

    assert res.is_ocr_applied is False
    assert res.ocr_limitation_notice is not None
    assert "OCR is not configured" in res.ocr_limitation_notice or "Limited text" in res.ocr_limitation_notice


# ─── 2. FIR-ASSISTED CASE INITIALIZATION & ORIGINAL PRESERVATION ─────────────

def test_fir_assisted_case_creation_and_preservation(db_session, mock_io1):
    case_service = CaseService(db_session)
    orchestrator = EvidencePipelineOrchestrator(db_session)

    fir_content = (
        b"%PDF-1.4\n"
        b"FIRST INFORMATION REPORT FIR-2026-EXP-777\n"
        b"Police Station: Central Police Station\n"
        b"Victim: Vikram Malhotra\n"
        b"Incident Location: Room 101 Lakeview Hotel\n"
        b"%%EOF"
    )

    req = FIRAssistedCaseCreateRequest(
        title="Unnatural Death Inquiry — Vikram Malhotra — Lakeview Hotel",
        fir_metadata=FIRMetadata(
            fir_number="FIR-2026-EXP-777",
            police_station="Central Police Station",
            jurisdiction_code="JUR-DEL-04",
            incident_date="2026-10-18T02:00:00Z",
            incident_location="Room 101 Lakeview Hotel",
        ),
        fir_file_b64=base64.b64encode(fir_content).decode("ascii"),
        fir_filename="FIR_777_original.pdf",
    )

    # 1. Create case via FIR-assisted workflow
    from app.api.v1.cases import create_case_fir_assisted
    resp = create_case_fir_assisted(
        payload=req,
        investigator=mock_io1,
        case_service=case_service,
        orchestrator=orchestrator,
    )

    assert resp.case.case_id is not None
    assert resp.case.title == "Unnatural Death Inquiry — Vikram Malhotra — Lakeview Hotel"
    assert resp.case.lifecycle_stage == "EVIDENCE_INGESTION"
    assert resp.fir_evidence_id is not None
    assert resp.fir_pipeline_status == "SUCCESS"

    # 2. Verify evidence record in repository
    ev_repo = EvidenceRepository(db_session)
    ev_list = ev_repo.list_by_case_id(resp.case.case_id)
    assert len(ev_list) == 1

    fir_ev = ev_list[0]
    assert fir_ev.evidence_id == resp.fir_evidence_id
    assert fir_ev.original_file_name == "FIR_777_original.pdf"
    assert fir_ev.evidence_category in ("DOCUMENT_PDF", "DOCUMENT")
    assert fir_ev.checksum_sha256 is not None
    assert fir_ev.worm_status == "COMMITTED"
    assert fir_ev.integrity_status == "VERIFIED"


def test_fir_assisted_duplicate_submission_idempotency(db_session, mock_io1):
    case_service = CaseService(db_session)
    orchestrator = EvidencePipelineOrchestrator(db_session)

    fir_content = b"%PDF-1.4\nDuplicate Submission FIR-2026-DUP-01\n%%EOF"
    req = FIRAssistedCaseCreateRequest(
        title="Inquest into Unnatural Death — FIR-2026-DUP-01",
        fir_metadata=FIRMetadata(
            fir_number="FIR-2026-DUP-01",
            police_station="Central Police Station",
            jurisdiction_code="JUR-DEL-04",
        ),
        fir_file_b64=base64.b64encode(fir_content).decode("ascii"),
        fir_filename="FIR_duplicate_test.pdf",
    )

    from app.api.v1.cases import create_case_fir_assisted
    # First submission
    resp1 = create_case_fir_assisted(
        payload=req,
        investigator=mock_io1,
        case_service=case_service,
        orchestrator=orchestrator,
    )
    assert resp1.case.case_id is not None

    # Duplicate re-submission (e.g. browser retry or network double-post)
    resp2 = create_case_fir_assisted(
        payload=req,
        investigator=mock_io1,
        case_service=case_service,
        orchestrator=orchestrator,
    )

    # Must reconcile to the same case ID without crashing or creating duplicate records
    assert resp2.case.case_id == resp1.case.case_id
    assert resp2.fir_evidence_id == resp1.fir_evidence_id
    assert "Idempotent duplicate submission" in (resp2.message or "")

    # Verify no duplicate evidence rows
    ev_repo = EvidenceRepository(db_session)
    ev_items = ev_repo.list_by_case_id(resp1.case.case_id)
    assert len(ev_items) == 1


# ─── 3. EVIDENCE CATEGORY AUDIT & CAPABILITY VALIDATION ──────────────────────

def test_evidence_category_accepted_types(db_session, mock_io1):
    """Verifies that all supported categories accept their respective valid MIME formats."""
    case_service = CaseService(db_session)
    intake = EvidenceIntakeService(db_session)
    mime_svc = MimeValidationService(db_session)

    c_resp = case_service.create_case(
        CaseCreateRequest(
            title="Evidence Category Verification Case",
            fir_metadata=FIRMetadata(
                fir_number="FIR-2026-CAT-01",
                police_station="Central Police Station",
                jurisdiction_code="JUR-DEL-04",
            ),
        ),
        mock_io1,
    )
    case_service.update_stage(c_resp.case_id, "EVIDENCE_INGESTION", mock_io1)

    # A. General Document PDF
    pdf_bytes = b"%PDF-1.4\nOfficial Correspondence\n%%EOF"
    ev_doc = intake.register_evidence(
        case_id=c_resp.case_id,
        file_payload=pdf_bytes,
        original_filename="inquest_register.pdf",
        metadata=EvidenceIntakeMetadata(
            evidence_category=EvidenceCategory.DOCUMENT_PDF,
            declared_mime_type="application/pdf",
        ),
        investigator=mock_io1,
    )
    res_doc = mime_svc.validate_evidence(c_resp.case_id, ev_doc.evidence_id, mock_io1)
    assert res_doc.valid is True
    assert res_doc.status == "VALIDATED"

    # B. Medical / Autopsy Report
    med_bytes = b"%PDF-1.4\nPost-Mortem Examination Report\n%%EOF"
    ev_med = intake.register_evidence(
        case_id=c_resp.case_id,
        file_payload=med_bytes,
        original_filename="autopsy_examination.pdf",
        metadata=EvidenceIntakeMetadata(
            evidence_category=EvidenceCategory.MEDICAL_REPORT,
            declared_mime_type="application/pdf",
        ),
        investigator=mock_io1,
    )
    res_med = mime_svc.validate_evidence(c_resp.case_id, ev_med.evidence_id, mock_io1)
    assert res_med.valid is True
    assert res_med.status == "VALIDATED"

    # C. Crime Scene Photograph
    jpg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00"
    ev_scene = intake.register_evidence(
        case_id=c_resp.case_id,
        file_payload=jpg_bytes,
        original_filename="corridor_entry.jpg",
        metadata=EvidenceIntakeMetadata(
            evidence_category=EvidenceCategory.SCENE_PHOTO,
            declared_mime_type="image/jpeg",
        ),
        investigator=mock_io1,
    )
    res_scene = mime_svc.validate_evidence(c_resp.case_id, ev_scene.evidence_id, mock_io1)
    assert res_scene.valid is True
    assert res_scene.status == "VALIDATED"

    # D. Audio Recording
    wav_bytes = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00data\x00\x00\x00\x00"
    ev_audio = intake.register_evidence(
        case_id=c_resp.case_id,
        file_payload=wav_bytes,
        original_filename="dispatch_call.wav",
        metadata=EvidenceIntakeMetadata(
            evidence_category=EvidenceCategory.AUDIO_RECORDING,
            declared_mime_type="audio/wav",
        ),
        investigator=mock_io1,
    )
    res_audio = mime_svc.validate_evidence(c_resp.case_id, ev_audio.evidence_id, mock_io1)
    assert res_audio.valid is True
    assert res_audio.status == "VALIDATED"

    # E. Call Detail Record (CDR) Sheet
    csv_bytes = b"timestamp,caller,receiver,duration_sec,cell_id\n2026-10-18 00:15:00,+919999999999,+918888888888,120,CELL-04\n"
    ev_cdr = intake.register_evidence(
        case_id=c_resp.case_id,
        file_payload=csv_bytes,
        original_filename="tower_cdr_dump.csv",
        metadata=EvidenceIntakeMetadata(
            evidence_category=EvidenceCategory.CDR_SPREADSHEET,
            declared_mime_type="text/csv",
        ),
        investigator=mock_io1,
    )
    res_cdr = mime_svc.validate_evidence(c_resp.case_id, ev_cdr.evidence_id, mock_io1)
    assert res_cdr.valid is True
    assert res_cdr.status == "VALIDATED"


def test_evidence_category_mismatch_rejection(db_session, mock_io1):
    """Verifies that submitting an inappropriate format for a specialized category is rejected."""
    case_service = CaseService(db_session)
    intake = EvidenceIntakeService(db_session)
    mime_svc = MimeValidationService(db_session)

    c_resp = case_service.create_case(
        CaseCreateRequest(
            title="Evidence Mismatch Rejection Case",
            fir_metadata=FIRMetadata(
                fir_number="FIR-2026-REJ-01",
                police_station="Central Police Station",
                jurisdiction_code="JUR-DEL-04",
            ),
        ),
        mock_io1,
    )
    case_service.update_stage(c_resp.case_id, "EVIDENCE_INGESTION", mock_io1)

    # Submitting a PDF file classified under SCENE_PHOTO (which requires image)
    pdf_bytes = b"%PDF-1.4\nNot a scene photograph\n%%EOF"
    ev = intake.register_evidence(
        case_id=c_resp.case_id,
        file_payload=pdf_bytes,
        original_filename="supposed_photo.pdf",
        metadata=EvidenceIntakeMetadata(
            evidence_category=EvidenceCategory.SCENE_PHOTO,
            declared_mime_type="application/pdf",
        ),
        investigator=mock_io1,
    )
    res = mime_svc.validate_evidence(c_resp.case_id, ev.evidence_id, mock_io1)

    assert res.valid is False
    assert res.status == "REJECTED"
    assert "category mismatch" in res.validation_reason.lower()
