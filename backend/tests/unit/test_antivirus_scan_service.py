"""
Unit tests for MOD-07 Antivirus Scan Service.
Tests passive byte scanning, clean files (PDF, JPEG, PNG, WAV, CSV), EICAR detection,
quarantine enforcement, fail-closed handling (offline, timeout, error),
authorization, case isolation, audit logging, and downstream ScannedEvidenceObject handoff.
"""
import os
import shutil
import tempfile
import pytest

from app.services.case_service import CaseService
from app.services.evidence_intake_service import EvidenceIntakeService
from app.services.mime_validation_service import MimeValidationService
from app.services.antivirus_scan_service import (
    AntivirusScanService,
    EicarHeuristicScanner,
    ClamAVScanner,
    get_configured_scanner,
    EICAR_SIGNATURE,
)
from app.schemas.case import CaseCreateRequest, FIRMetadata
from app.schemas.evidence import (
    EvidenceCategory,
    EvidenceIntakeMetadata,
    EvidenceIntakeStatus,
    AntivirusVerdict,
    ScannedEvidenceObject,
)
from app.core.errors import (
    CaseNotFoundException,
    EvidenceNotFoundException,
    EvidenceFileNotFoundException,
    EvidenceValidationFailedException,
    AntivirusThreatDetectedException,
    AntivirusUnavailableException,
    AntivirusTimeoutException,
    AntivirusScanFailedException,
    ForbiddenException,
)
from app.models.evidence import Evidence


# Clean binary test payloads
CLEAN_PDF = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
CLEAN_JPEG = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00TestJpegData\xFF\xD9"
CLEAN_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
CLEAN_WAV = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
CLEAN_CSV = b"timestamp,caller_msisdn,receiver_msisdn,duration_sec\n2026-03-01T10:00:00Z,919876543210,919123456789,120\n"


@pytest.fixture
def workspace_dir():
    temp_dir = tempfile.mkdtemp(prefix="sakshi_mod07_ws_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def active_case(db_session, mock_io1, workspace_dir):
    """Creates a case in EVIDENCE_INGESTION stage with an isolated test workspace."""
    case_service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Cyber Forensic Malware Investigation",
        fir_metadata=FIRMetadata(
            fir_number="FIR-2026-AV-01",
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


def _setup_validated_evidence(
    db_session,
    active_case,
    mock_io1,
    payload_bytes: bytes,
    filename: str,
    declared_mime: str,
    category: EvidenceCategory = EvidenceCategory.DOCUMENT_PDF,
) -> Evidence:
    """Helper that registers evidence (MOD-05) and validates it (MOD-06)."""
    intake_service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=category,
        declared_mime_type=declared_mime,
        description="Test evidence object for MOD-07 scan"
    )
    reg_obj = intake_service.register_evidence(
        case_id=active_case.case_id,
        file_payload=payload_bytes,
        original_filename=filename,
        metadata=metadata,
        investigator=mock_io1,
    )

    mime_service = MimeValidationService(db_session)
    val_res = mime_service.validate_evidence(
        case_id=active_case.case_id,
        evidence_id=reg_obj.evidence_id,
        investigator=mock_io1,
    )
    assert val_res.valid is True, f"Validation failed: {val_res.validation_reason}"

    return intake_service.evidence_repo.get_by_evidence_id(reg_obj.evidence_id)


# ═══════════════════════════════════════════════════════════════════════════
# 1. Clean File Scan Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_scan_clean_pdf(db_session, active_case, mock_io1):
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "clean_doc.pdf", "application/pdf"
    )

    av_service = AntivirusScanService(db_session)
    result = av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    assert result.verdict == AntivirusVerdict.CLEAN
    assert result.status == EvidenceIntakeStatus.CLEAN.value
    assert result.threat_name is None
    assert result.scanner_name == "EicarHeuristicScanner"
    assert result.duration_ms is not None

    # Verify database persistence
    refreshed = av_service.evidence_repo.get_by_evidence_id(evidence.evidence_id)
    assert refreshed.status == EvidenceIntakeStatus.CLEAN.value
    assert refreshed.antivirus_status == "CLEAN"
    assert refreshed.antivirus_scanned_at is not None

    # Verify downstream handoff contract to MOD-08
    contract = av_service.get_scanned_evidence_object(active_case.case_id, evidence.evidence_id, mock_io1)
    assert isinstance(contract, ScannedEvidenceObject)
    assert contract.evidence_id == evidence.evidence_id
    assert contract.antivirus_verdict == "CLEAN"


def test_scan_clean_jpeg(db_session, active_case, mock_io1):
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_JPEG, "crime_scene.jpg", "image/jpeg",
        category=EvidenceCategory.SCENE_PHOTO
    )

    av_service = AntivirusScanService(db_session)
    result = av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    assert result.verdict == AntivirusVerdict.CLEAN
    assert result.status == EvidenceIntakeStatus.CLEAN.value


def test_scan_clean_png(db_session, active_case, mock_io1):
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PNG, "evidence_scan.png", "image/png",
        category=EvidenceCategory.SCENE_PHOTO
    )

    av_service = AntivirusScanService(db_session)
    result = av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    assert result.verdict == AntivirusVerdict.CLEAN
    assert result.status == EvidenceIntakeStatus.CLEAN.value


def test_scan_clean_wav(db_session, active_case, mock_io1):
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_WAV, "wiretap_recording.wav", "audio/wav",
        category=EvidenceCategory.AUDIO_RECORDING
    )

    av_service = AntivirusScanService(db_session)
    result = av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    assert result.verdict == AntivirusVerdict.CLEAN
    assert result.status == EvidenceIntakeStatus.CLEAN.value


def test_scan_clean_csv(db_session, active_case, mock_io1):
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_CSV, "call_detail_record.csv", "text/csv",
        category=EvidenceCategory.CDR_SPREADSHEET
    )

    av_service = AntivirusScanService(db_session)
    result = av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    assert result.verdict == AntivirusVerdict.CLEAN
    assert result.status == EvidenceIntakeStatus.CLEAN.value


# ═══════════════════════════════════════════════════════════════════════════
# 2. Malware & EICAR Detection Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_scan_eicar_test_signature_detected(db_session, active_case, mock_io1):
    """
    Standard EICAR test string embedded in a valid text/csv format.
    Must be detected as THREAT_DETECTED, quarantined, and blocked from MOD-08.
    """
    eicar_csv_payload = CLEAN_CSV + b"\n# MALWARE_SAMPLE_ATTACHED:\n" + EICAR_SIGNATURE + b"\n"
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, eicar_csv_payload, "suspicious_cdr.csv", "text/csv",
        category=EvidenceCategory.CDR_SPREADSHEET
    )

    av_service = AntivirusScanService(db_session)
    result = av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    assert result.verdict == AntivirusVerdict.THREAT_DETECTED
    assert result.status == EvidenceIntakeStatus.QUARANTINED.value
    assert "EICAR" in (result.threat_name or "")

    # Check database persistence
    refreshed = av_service.evidence_repo.get_by_evidence_id(evidence.evidence_id)
    assert refreshed.status == EvidenceIntakeStatus.QUARANTINED.value
    assert refreshed.antivirus_status == AntivirusVerdict.THREAT_DETECTED.value
    assert "EICAR" in (refreshed.antivirus_threat_name or "")

    # Invariant: Evidence is quarantined and cannot proceed to MOD-08
    with pytest.raises(AntivirusThreatDetectedException) as exc_info:
        av_service.get_scanned_evidence_object(active_case.case_id, evidence.evidence_id, mock_io1)
    assert "quarantined" in str(exc_info.value).lower()


def test_scan_heuristic_nop_sled_detected(db_session, active_case, mock_io1):
    """
    Heuristic exploit detection: Suspicious NOP sled shellcode embedded in file.
    """
    exploit_csv = CLEAN_CSV + (b"\x90" * 150)
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, exploit_csv, "exploit_data.csv", "text/csv",
        category=EvidenceCategory.CDR_SPREADSHEET
    )

    av_service = AntivirusScanService(db_session)
    result = av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    assert result.verdict == AntivirusVerdict.THREAT_DETECTED
    assert result.status == EvidenceIntakeStatus.QUARANTINED.value
    assert "Shellcode" in (result.threat_name or "")

    # Blocked from MOD-08 handoff
    with pytest.raises(AntivirusThreatDetectedException):
        av_service.get_scanned_evidence_object(active_case.case_id, evidence.evidence_id, mock_io1)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Pipeline Ordering & Invalid State Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_scan_unvalidated_evidence_rejected(db_session, active_case, mock_io1):
    """
    Evidence in REGISTERED_INTAKE (has not passed MOD-06) cannot enter MOD-07.
    """
    intake_service = EvidenceIntakeService(db_session)
    metadata = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.DOCUMENT_PDF,
        declared_mime_type="application/pdf",
    )
    reg_obj = intake_service.register_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="unvalidated.pdf",
        metadata=metadata,
        investigator=mock_io1,
    )

    av_service = AntivirusScanService(db_session)
    with pytest.raises(EvidenceValidationFailedException) as exc_info:
        av_service.scan_evidence(active_case.case_id, reg_obj.evidence_id, mock_io1)
    assert "cannot enter MOD-07" in str(exc_info.value)


def test_scan_rejected_evidence_cannot_be_scanned(db_session, active_case, mock_io1):
    """
    Evidence that failed MOD-06 validation (status REJECTED) cannot be scanned.
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "doc.pdf", "application/pdf"
    )
    # Manually transition to REJECTED (simulating MOD-06 failure)
    evidence.status = EvidenceIntakeStatus.REJECTED.value
    db_session.commit()

    av_service = AntivirusScanService(db_session)
    with pytest.raises(EvidenceValidationFailedException):
        av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)


def test_scan_nonexistent_evidence(db_session, active_case, mock_io1):
    av_service = AntivirusScanService(db_session)
    with pytest.raises(EvidenceNotFoundException):
        av_service.scan_evidence(active_case.case_id, "NON-EXISTENT-EVID-ID", mock_io1)


def test_scan_nonexistent_case(db_session, mock_io1):
    av_service = AntivirusScanService(db_session)
    with pytest.raises(CaseNotFoundException):
        av_service.scan_evidence("NON-EXISTENT-CASE-ID", "EVID-01", mock_io1)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Fail-Closed Security Model Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_scan_engine_offline_fails_closed(db_session, active_case, mock_io1):
    """
    If scanner daemon is offline/unavailable, fail closed:
    Raise AntivirusUnavailableException, do NOT mark clean, do NOT allow MOD-08 handoff.
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "doc.pdf", "application/pdf"
    )

    offline_scanner = EicarHeuristicScanner(simulate_unavailable=True)
    av_service = AntivirusScanService(db_session, scanner=offline_scanner)

    with pytest.raises(AntivirusUnavailableException) as exc_info:
        av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)
    assert "offline" in str(exc_info.value).lower() or "unavailable" in str(exc_info.value).lower()

    # Verify status is NOT clean
    refreshed = av_service.evidence_repo.get_by_evidence_id(evidence.evidence_id)
    assert refreshed.status != EvidenceIntakeStatus.CLEAN.value
    assert refreshed.antivirus_status == AntivirusVerdict.SCANNER_UNAVAILABLE.value

    # Downstream contract denied
    with pytest.raises(AntivirusScanFailedException):
        av_service.get_scanned_evidence_object(active_case.case_id, evidence.evidence_id, mock_io1)


def test_scan_engine_timeout_fails_closed(db_session, active_case, mock_io1):
    """
    If scanner times out, fail closed:
    Raise AntivirusTimeoutException, do NOT mark clean.
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "timeout_doc.pdf", "application/pdf"
    )

    timeout_scanner = EicarHeuristicScanner(simulate_timeout=True)
    av_service = AntivirusScanService(db_session, scanner=timeout_scanner)

    with pytest.raises(AntivirusTimeoutException):
        av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    refreshed = av_service.evidence_repo.get_by_evidence_id(evidence.evidence_id)
    assert refreshed.status != EvidenceIntakeStatus.CLEAN.value
    assert refreshed.antivirus_status == AntivirusVerdict.SCAN_TIMEOUT.value


def test_scan_engine_internal_error_fails_closed(db_session, active_case, mock_io1):
    """
    If scanner encounters an internal error, fail closed:
    Raise AntivirusScanFailedException, do NOT mark clean.
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "error_doc.pdf", "application/pdf"
    )

    error_scanner = EicarHeuristicScanner(simulate_error=True)
    av_service = AntivirusScanService(db_session, scanner=error_scanner)

    with pytest.raises(AntivirusScanFailedException):
        av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    refreshed = av_service.evidence_repo.get_by_evidence_id(evidence.evidence_id)
    assert refreshed.status != EvidenceIntakeStatus.CLEAN.value
    assert refreshed.antivirus_status == AntivirusVerdict.SCAN_ERROR.value


# ═══════════════════════════════════════════════════════════════════════════
# 5. Security, Case Isolation & Path Boundary Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_unauthorized_investigator_denied_scan(db_session, active_case, mock_io1, mock_io2):
    """
    Investigator 2 (unassigned regular IO without supervisory role) is denied scan operation.
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "doc.pdf", "application/pdf"
    )

    av_service = AntivirusScanService(db_session)
    with pytest.raises(ForbiddenException):
        av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io2)


def test_supervisory_officer_allowed_scan(db_session, active_case, mock_io1, mock_supervisor):
    """
    Supervisory officer has cross-investigation oversight and can initiate scanning.
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "doc.pdf", "application/pdf"
    )

    av_service = AntivirusScanService(db_session)
    result = av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_supervisor)
    assert result.verdict == AntivirusVerdict.CLEAN


def test_cross_case_evidence_access_denied(db_session, active_case, mock_io1, workspace_dir):
    """
    Evidence belonging to Case A cannot be scanned under Case B.
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "case_a_doc.pdf", "application/pdf"
    )

    # Create Case B
    case_service = CaseService(db_session)
    case_b_resp = case_service.create_case(
        CaseCreateRequest(
            title="Unrelated Case B",
            fir_metadata=FIRMetadata(
                fir_number="FIR-2026-CASE-B",
                police_station="South Station",
                jurisdiction_code="JUR-DEL-04"
            )
        ),
        mock_io1
    )

    av_service = AntivirusScanService(db_session)
    with pytest.raises(EvidenceNotFoundException):
        av_service.scan_evidence(case_b_resp.case_id, evidence.evidence_id, mock_io1)


def test_workspace_boundary_path_traversal_denied(db_session, active_case, mock_io1):
    """
    If raw_storage_path points outside the case workspace, scan is rejected with ForbiddenException.
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "doc.pdf", "application/pdf"
    )

    # Alter storage path to point to a system folder outside the case workspace
    evidence.raw_storage_path = os.path.abspath(os.path.join(active_case.case_workspace_path, "..", "external_secret.txt"))
    with open(evidence.raw_storage_path, "wb") as f:
        f.write(CLEAN_PDF)
    db_session.commit()

    av_service = AntivirusScanService(db_session)
    try:
        with pytest.raises(ForbiddenException) as exc_info:
            av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)
        assert "workspace boundary" in str(exc_info.value).lower()
    finally:
        if os.path.exists(evidence.raw_storage_path):
            os.remove(evidence.raw_storage_path)


def test_missing_physical_file_raises_error(db_session, active_case, mock_io1):
    """
    If physical file has been deleted from disk, raises EvidenceFileNotFoundException.
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "temp.pdf", "application/pdf"
    )
    if os.path.exists(evidence.raw_storage_path):
        os.remove(evidence.raw_storage_path)

    av_service = AntivirusScanService(db_session)
    with pytest.raises(EvidenceFileNotFoundException):
        av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)


# ═══════════════════════════════════════════════════════════════════════════
# 6. Idempotency & Rescan Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_rescan_idempotency(db_session, active_case, mock_io1):
    """
    Evidence in CLEAN status can be re-scanned (e.g. after signature update).
    Verdict and timestamp are refreshed deterministically.
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "rescan_doc.pdf", "application/pdf"
    )

    av_service = AntivirusScanService(db_session)
    res1 = av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)
    assert res1.verdict == AntivirusVerdict.CLEAN

    # Rescan again
    res2 = av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)
    assert res2.verdict == AntivirusVerdict.CLEAN
    assert res2.status == EvidenceIntakeStatus.CLEAN.value


# ═══════════════════════════════════════════════════════════════════════════
# 7. Semantic Hardening & Fail-Closed / No-Fallback Tests (Corrections 1 & 2)
# ═══════════════════════════════════════════════════════════════════════════

def test_clean_verdict_semantics_no_threat_detected(db_session, active_case, mock_io1):
    """
    TEST 1: CLEAN SEMANTICS
    Verify that a clean scan result explicitly states:
    "No threat detected by the configured antivirus scanner"
    and does NOT claim "certified benign", "proven harmless", or "proven malware-free".
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "semantics_doc.pdf", "application/pdf"
    )

    av_service = AntivirusScanService(db_session)
    result = av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    assert result.verdict == AntivirusVerdict.CLEAN
    assert "No threat detected by the configured antivirus scanner" in result.message
    # Must NOT claim absolute proof
    assert "certified benign" not in result.message.lower()
    assert "proven harmless" not in result.message.lower()
    assert "proven malware-free" not in result.message.lower()


def test_clamav_unavailable_fails_closed(db_session, active_case, mock_io1):
    """
    TEST 2: CLAMAV UNAVAILABLE
    Configure ClamAV as the active scanner. Simulate ClamAV unavailable.
    Expected:
    - verdict = SCANNER_UNAVAILABLE
    - evidence status remains VALIDATED (not CLEAN)
    - no ScannedEvidenceObject can be produced
    - MOD-08 handoff strictly rejected
    - CRITICAL: Never returns CLEAN!
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "clamav_unavail.pdf", "application/pdf"
    )

    clamav_scanner = ClamAVScanner(simulate_unavailable=True)
    av_service = AntivirusScanService(db_session, scanner=clamav_scanner)

    with pytest.raises(AntivirusUnavailableException):
        av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    refreshed = av_service.evidence_repo.get_by_evidence_id(evidence.evidence_id)
    assert refreshed.status == EvidenceIntakeStatus.VALIDATED.value
    assert refreshed.antivirus_status == AntivirusVerdict.SCANNER_UNAVAILABLE.value

    # Downstream MOD-08 handoff must be rejected
    with pytest.raises(AntivirusScanFailedException):
        av_service.get_scanned_evidence_object(active_case.case_id, evidence.evidence_id, mock_io1)


def test_no_unsafe_fallback_when_clamav_unavailable(db_session, active_case, mock_io1):
    """
    TEST 3: NO UNSAFE FALLBACK
    Configure ClamAV as active scanner, but ClamAV is offline.
    Use an arbitrary clean-looking file.
    CRITICAL: EicarHeuristicScanner must NOT be silently invoked to return CLEAN.
    Expected: SCANNER_UNAVAILABLE, not CLEAN.
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_JPEG, "photo.jpg", "image/jpeg",
        category=EvidenceCategory.SCENE_PHOTO
    )

    clamav_scanner = ClamAVScanner(simulate_unavailable=True)
    av_service = AntivirusScanService(db_session, scanner=clamav_scanner)

    with pytest.raises(AntivirusUnavailableException):
        av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    refreshed = av_service.evidence_repo.get_by_evidence_id(evidence.evidence_id)
    # Must NOT have fallen back to heuristic scanner or marked CLEAN
    assert refreshed.status != EvidenceIntakeStatus.CLEAN.value
    assert refreshed.antivirus_status != AntivirusVerdict.CLEAN.value
    assert refreshed.antivirus_scanner == "ClamAVScanner"


def test_explicit_eicar_heuristic_mode_detects_eicar(db_session, active_case, mock_io1):
    """
    TEST 4: EXPLICIT EICAR HEURISTIC MODE
    Explicitly configure EICAR_HEURISTIC scanner. Scan EICAR payload.
    Expected:
    - THREAT_DETECTED
    - scanner_name == 'EicarHeuristicScanner'
    - evidence status == QUARANTINED
    - MOD-08 handoff rejected
    """
    eicar_csv = CLEAN_CSV + b"\n# MALWARE_SAMPLE:\n" + EICAR_SIGNATURE + b"\n"
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, eicar_csv, "explicit_eicar.csv", "text/csv",
        category=EvidenceCategory.CDR_SPREADSHEET
    )

    heuristic_scanner = EicarHeuristicScanner()
    av_service = AntivirusScanService(db_session, scanner=heuristic_scanner)

    result = av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)
    assert result.verdict == AntivirusVerdict.THREAT_DETECTED
    assert result.scanner_name == "EicarHeuristicScanner"
    assert result.status == EvidenceIntakeStatus.QUARANTINED.value

    # Downstream MOD-08 handoff must be blocked
    with pytest.raises(AntivirusThreatDetectedException):
        av_service.get_scanned_evidence_object(active_case.case_id, evidence.evidence_id, mock_io1)


def test_explicit_eicar_clean_file_semantics(db_session, active_case, mock_io1):
    """
    TEST 5: EXPLICIT EICAR CLEAN FILE
    Explicitly configure EicarHeuristicScanner. Scan normal clean file.
    Expected:
    - CLEAN
    - Semantic meaning: no threat detected by this configured scanner
    - NOT proven malware-free
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PNG, "clean_icon.png", "image/png",
        category=EvidenceCategory.SCENE_PHOTO
    )

    heuristic_scanner = EicarHeuristicScanner()
    av_service = AntivirusScanService(db_session, scanner=heuristic_scanner)

    result = av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)
    assert result.verdict == AntivirusVerdict.CLEAN
    assert result.scanner_name == "EicarHeuristicScanner"
    assert "No threat detected by the configured antivirus scanner (EicarHeuristicScanner)" in result.message
    assert "proven malware-free" not in result.message.lower()


def test_clamav_timeout_fails_closed(db_session, active_case, mock_io1):
    """
    TEST 6: CLAMAV TIMEOUT
    Simulate ClamAV timeout.
    Expected:
    - SCAN_TIMEOUT
    - No CLEAN
    - No ScannedEvidenceObject
    - MOD-08 handoff rejected
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "clamav_timeout.pdf", "application/pdf"
    )

    clamav_scanner = ClamAVScanner(simulate_timeout=True)
    av_service = AntivirusScanService(db_session, scanner=clamav_scanner)

    with pytest.raises(AntivirusTimeoutException):
        av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    refreshed = av_service.evidence_repo.get_by_evidence_id(evidence.evidence_id)
    assert refreshed.status == EvidenceIntakeStatus.VALIDATED.value
    assert refreshed.antivirus_status == AntivirusVerdict.SCAN_TIMEOUT.value

    with pytest.raises(AntivirusScanFailedException):
        av_service.get_scanned_evidence_object(active_case.case_id, evidence.evidence_id, mock_io1)


def test_clamav_internal_error_fails_closed(db_session, active_case, mock_io1):
    """
    TEST 7: CLAMAV INTERNAL ERROR
    Simulate ClamAV scanner internal error.
    Expected:
    - SCAN_ERROR
    - No CLEAN
    - No ScannedEvidenceObject
    - MOD-08 handoff rejected
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "clamav_err.pdf", "application/pdf"
    )

    clamav_scanner = ClamAVScanner(simulate_error=True)
    av_service = AntivirusScanService(db_session, scanner=clamav_scanner)

    with pytest.raises(AntivirusScanFailedException):
        av_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)

    refreshed = av_service.evidence_repo.get_by_evidence_id(evidence.evidence_id)
    assert refreshed.status == EvidenceIntakeStatus.VALIDATED.value
    assert refreshed.antivirus_status == AntivirusVerdict.SCAN_ERROR.value

    with pytest.raises(AntivirusScanFailedException):
        av_service.get_scanned_evidence_object(active_case.case_id, evidence.evidence_id, mock_io1)


def test_scanner_identity_accuracy_clamav_vs_heuristic(db_session, active_case, mock_io1):
    """
    TEST 8: SCANNER IDENTITY
    Verify the persisted result contains the actual scanner name:
    ClamAVScanner or EicarHeuristicScanner.
    Never allow heuristic results to claim ClamAV.
    """
    evidence = _setup_validated_evidence(
        db_session, active_case, mock_io1, CLEAN_PDF, "identity_doc.pdf", "application/pdf"
    )

    # 1. Scan with EicarHeuristicScanner
    heuristic_service = AntivirusScanService(db_session, scanner=EicarHeuristicScanner())
    h_res = heuristic_service.scan_evidence(active_case.case_id, evidence.evidence_id, mock_io1)
    assert h_res.scanner_name == "EicarHeuristicScanner"
    refreshed_h = heuristic_service.evidence_repo.get_by_evidence_id(evidence.evidence_id)
    assert refreshed_h.antivirus_scanner == "EicarHeuristicScanner"
    assert "ClamAV" not in refreshed_h.antivirus_scanner
