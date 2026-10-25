"""Unit tests for the MOD-05 through MOD-08 composite orchestrator."""
import shutil
import tempfile

import pytest

from app.core.errors import (
    ForbiddenException,
    ObjectLockFailedException,
    SHA256IntegrityMismatchException,
    WORMCommitFailedException,
)
from app.schemas.case import CaseCreateRequest, FIRMetadata
from app.schemas.evidence import EvidenceCategory, EvidenceIntakeMetadata, PipelineExecutionStatus, PipelineStage
from app.services.antivirus_scan_service import AntivirusScanService, EicarHeuristicScanner, EICAR_SIGNATURE
from app.services.case_service import CaseService
from app.services.evidence_intake_service import EvidenceIntakeService
from app.services.evidence_pipeline_orchestrator import (
    EvidencePipelineOrchestrator,
    _CasePipelineLockRegistry,
)
from app.services.integrity_service import IntegrityService
from app.services.object_lock_service import ObjectLockService
from app.services.worm_commit_service import IWORMStorage, WORMCommitService


CLEAN_PDF = b"%PDF-1.5\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


@pytest.fixture
def workspace_dir():
    path = tempfile.mkdtemp(prefix="sakshi_pipeline_ws_")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def active_case(db_session, mock_io1, workspace_dir):
    case_service = CaseService(db_session)
    case = case_service.create_case(
        CaseCreateRequest(
            title="Pipeline orchestration case",
            fir_metadata=FIRMetadata(
                fir_number="FIR-2026-PIPELINE-01",
                police_station="Central Police Station",
                jurisdiction_code="JUR-DEL-04",
            ),
        ),
        mock_io1,
    )
    entity = case_service.repo.get_by_case_id(case.case_id)
    entity.case_workspace_path = workspace_dir
    case_service.repo.update(entity)
    case_service.update_stage(case.case_id, "EVIDENCE_INGESTION", mock_io1)
    return case_service.repo.get_by_case_id(case.case_id)


class FailingWORMStorage(IWORMStorage):
    def put_immutable(self, case_id, sha256_digest, source_file_path, case_workspace_path=None):
        raise WORMCommitFailedException("simulated WORM storage failure")

    def get_reference(self, case_id, sha256_digest):
        return f"worm://{case_id}/{sha256_digest}"

    def exists(self, case_id, sha256_digest, case_workspace_path=None):
        return False

    def verify_immutable(self, storage_reference, expected_sha256, case_workspace_path=None):
        return False


class UnexpectedFailureIntakeService:
    def register_evidence(self, **kwargs):
        raise RuntimeError("filesystem path C:\\private\\evidence should not be exposed")


def _metadata():
    return EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.DOCUMENT_PDF,
        declared_mime_type="application/pdf",
        description="Pipeline unit-test evidence",
    )


def _orchestrator(
    db_session,
    scanner=None,
    worm_service=None,
    intake_service=None,
    integrity_service=None,
    object_lock_service=None,
    rag_indexing_service=None,
    auto_index=True,
):
    return EvidencePipelineOrchestrator(
        db_session,
        intake_service=intake_service,
        antivirus_service=AntivirusScanService(
            db_session,
            scanner=scanner or EicarHeuristicScanner(),
        ),
        worm_service=worm_service or WORMCommitService(db_session),
        integrity_service=integrity_service,
        object_lock_service=object_lock_service,
        rag_indexing_service=rag_indexing_service,
        auto_index=auto_index,
    )


def test_new_evidence_pipeline_completes_all_six_stages(db_session, active_case, mock_io1):
    result = _orchestrator(db_session).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="report.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )

    assert result.overall_status == PipelineExecutionStatus.SUCCESS
    assert [stage.value for stage in result.completed_stages] == [
        "INTAKE",
        "MIME_VALIDATION",
        "ANTIVIRUS_SCAN",
        "WORM_COMMIT",
        "DUAL_HASHING",
        "OBJECT_LOCK",
    ]
    assert result.current_stage == PipelineStage.OBJECT_LOCK
    assert result.evidence_id
    assert result.intake_status.value == "COMMITTED"
    assert result.worm_storage_reference.startswith(f"worm://{active_case.case_id}/")
    assert result.checksum_sha256
    assert result.checksum_sha3_512
    assert result.lock_storage_reference.startswith(f"objlock://{active_case.case_id}/")
    assert result.integrity_status == "VERIFIED"
    assert result.lock_status == "LOCKED"
    assert result.is_retryable is False


def test_intake_failure_has_no_evidence_id(db_session, active_case, mock_io1):
    result = _orchestrator(db_session).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=b"",
        original_filename="empty.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )

    assert result.overall_status == PipelineExecutionStatus.INTAKE_FAILED
    assert result.evidence_id is None
    assert result.completed_stages == []


def test_mime_rejection_stops_before_antivirus(db_session, active_case, mock_io1):
    result = _orchestrator(db_session).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=b"not a PDF document",
        original_filename="report.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )

    assert result.overall_status == PipelineExecutionStatus.MIME_VALIDATION_FAILED
    assert [stage.value for stage in result.completed_stages] == ["INTAKE"]
    assert result.intake_status.value == "REJECTED"


def test_malware_detection_stops_before_worm_commit(db_session, active_case, mock_io1):
    result = _orchestrator(db_session).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF + EICAR_SIGNATURE,
        original_filename="infected.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )

    assert result.overall_status == PipelineExecutionStatus.ANTIVIRUS_QUARANTINED
    assert [stage.value for stage in result.completed_stages] == ["INTAKE", "MIME_VALIDATION"]
    assert result.intake_status.value == "QUARANTINED"
    assert result.worm_storage_reference is None


@pytest.mark.parametrize("scanner", [
    EicarHeuristicScanner(simulate_unavailable=True),
    EicarHeuristicScanner(simulate_timeout=True),
])
def test_antivirus_operational_failures_are_retryable(db_session, active_case, mock_io1, scanner):
    result = _orchestrator(db_session, scanner=scanner).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="report.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )

    assert result.overall_status == PipelineExecutionStatus.RETRYABLE_ERROR
    assert result.is_retryable is True
    assert [stage.value for stage in result.completed_stages] == ["INTAKE", "MIME_VALIDATION"]
    assert result.intake_status.value == "VALIDATED"


def test_worm_commit_failure_is_reported_without_claiming_completion(db_session, active_case, mock_io1):
    worm_service = WORMCommitService(db_session, worm_storage=FailingWORMStorage())
    result = _orchestrator(db_session, worm_service=worm_service).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="report.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )

    assert result.overall_status == PipelineExecutionStatus.WORM_COMMIT_FAILED
    assert [stage.value for stage in result.completed_stages] == [
        "INTAKE", "MIME_VALIDATION", "ANTIVIRUS_SCAN"
    ]
    assert result.intake_status.value == "CLEAN"


def test_authorization_denial_raises_forbidden(db_session, active_case, mock_io2):
    with pytest.raises(ForbiddenException):
        _orchestrator(db_session).execute_new_evidence(
            case_id=active_case.case_id,
            file_payload=CLEAN_PDF,
            original_filename="report.pdf",
            metadata=_metadata(),
            investigator=mock_io2,
        )


def test_resume_uses_verified_persisted_state_without_repeating_intake(db_session, active_case, mock_io1):
    stalled = _orchestrator(
        db_session,
        scanner=EicarHeuristicScanner(simulate_unavailable=True),
    ).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="report.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )
    assert stalled.overall_status == PipelineExecutionStatus.RETRYABLE_ERROR

    resumed = _orchestrator(db_session).resume_existing_evidence(
        case_id=active_case.case_id,
        evidence_id=stalled.evidence_id,
        investigator=mock_io1,
    )
    assert resumed.overall_status == PipelineExecutionStatus.SUCCESS
    assert resumed.evidence_id == stalled.evidence_id
    assert [stage.value for stage in resumed.completed_stages] == [
        "INTAKE", "MIME_VALIDATION", "ANTIVIRUS_SCAN", "WORM_COMMIT", "DUAL_HASHING", "OBJECT_LOCK"
    ]

    repeated_resume = _orchestrator(db_session).resume_existing_evidence(
        case_id=active_case.case_id,
        evidence_id=stalled.evidence_id,
        investigator=mock_io1,
    )
    assert repeated_resume.overall_status == PipelineExecutionStatus.SUCCESS
    assert repeated_resume.already_committed is True
    assert [stage.value for stage in repeated_resume.completed_stages] == [
        "INTAKE", "MIME_VALIDATION", "ANTIVIRUS_SCAN", "WORM_COMMIT", "DUAL_HASHING", "OBJECT_LOCK"
    ]


def test_sha256_mismatch_stops_before_object_lock_and_fails_closed(db_session, active_case, mock_io1):
    from unittest.mock import MagicMock

    mock_integrity = MagicMock(spec=IntegrityService)
    def _raise_mismatch(case_id, evidence_id, investigator):
        from app.repositories.evidence_repository import EvidenceRepository
        repo = EvidenceRepository(db_session)
        ev = repo.get_by_evidence_id(evidence_id)
        ev.integrity_status = "FAILED"
        ev.integrity_verification_message = "Cryptographic integrity violation: SHA-256 mismatch"
        repo.update(ev)
        raise SHA256IntegrityMismatchException(
            expected="expected_sha256",
            actual="actual_sha256",
            message="Cryptographic integrity violation: SHA-256 mismatch",
        )
    mock_integrity.verify_and_compute_integrity.side_effect = _raise_mismatch

    mock_lock = MagicMock(spec=ObjectLockService)

    result = _orchestrator(
        db_session,
        integrity_service=mock_integrity,
        object_lock_service=mock_lock,
    ).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="tampered.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )

    assert result.overall_status == PipelineExecutionStatus.INTEGRITY_FAILED
    assert result.current_stage == PipelineStage.DUAL_HASHING
    assert "OBJECT_LOCK" not in [s.value for s in result.completed_stages]
    assert result.is_retryable is False
    assert mock_lock.apply_object_lock.call_count == 0

    # Resume must fail closed and never run object lock
    resumed = _orchestrator(
        db_session,
        object_lock_service=mock_lock,
    ).resume_existing_evidence(
        case_id=active_case.case_id,
        evidence_id=result.evidence_id,
        investigator=mock_io1,
    )
    assert resumed.overall_status == PipelineExecutionStatus.INTEGRITY_FAILED
    assert resumed.current_stage == PipelineStage.DUAL_HASHING
    assert mock_lock.apply_object_lock.call_count == 0


def test_transient_mod09_failure_can_resume_at_mod09(db_session, active_case, mock_io1):
    from unittest.mock import MagicMock

    transient_integrity = MagicMock(spec=IntegrityService)
    transient_integrity.verify_and_compute_integrity.side_effect = IOError("Transient disk I/O error")

    result = _orchestrator(
        db_session,
        integrity_service=transient_integrity,
    ).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="transient_test.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )

    assert result.overall_status == PipelineExecutionStatus.RETRYABLE_ERROR
    assert result.current_stage == PipelineStage.DUAL_HASHING
    assert result.is_retryable is True
    assert result.evidence_id is not None

    # Resume with working IntegrityService
    resumed = _orchestrator(db_session).resume_existing_evidence(
        case_id=active_case.case_id,
        evidence_id=result.evidence_id,
        investigator=mock_io1,
    )
    assert resumed.overall_status == PipelineExecutionStatus.SUCCESS
    assert resumed.current_stage == PipelineStage.OBJECT_LOCK
    assert [s.value for s in resumed.completed_stages] == [
        "INTAKE", "MIME_VALIDATION", "ANTIVIRUS_SCAN", "WORM_COMMIT", "DUAL_HASHING", "OBJECT_LOCK"
    ]
    assert resumed.integrity_status == "VERIFIED"
    assert resumed.lock_status == "LOCKED"


def test_mod10_failure_can_resume_at_mod10(db_session, active_case, mock_io1):
    from unittest.mock import MagicMock

    failing_lock = MagicMock(spec=ObjectLockService)
    def _raise_lock_fail(case_id, evidence_id, investigator):
        from app.repositories.evidence_repository import EvidenceRepository
        repo = EvidenceRepository(db_session)
        ev = repo.get_by_evidence_id(evidence_id)
        ev.lock_status = "LOCK_FAILED"
        repo.update(ev)
        raise ObjectLockFailedException("Simulated lock storage failure")
    failing_lock.apply_object_lock.side_effect = _raise_lock_fail

    result = _orchestrator(
        db_session,
        object_lock_service=failing_lock,
    ).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="lock_fail_test.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )

    assert result.overall_status == PipelineExecutionStatus.OBJECT_LOCK_FAILED
    assert result.current_stage == PipelineStage.OBJECT_LOCK
    assert "DUAL_HASHING" in [s.value for s in result.completed_stages]
    assert result.evidence_id is not None

    # Resume with real ObjectLockService
    resumed = _orchestrator(db_session).resume_existing_evidence(
        case_id=active_case.case_id,
        evidence_id=result.evidence_id,
        investigator=mock_io1,
    )
    assert resumed.overall_status == PipelineExecutionStatus.SUCCESS
    assert resumed.current_stage == PipelineStage.OBJECT_LOCK
    assert resumed.lock_status == "LOCKED"
    assert resumed.lock_storage_reference.startswith(f"objlock://{active_case.case_id}/")


def test_resumed_request_does_not_repeat_intake_or_worm_commit(db_session, active_case, mock_io1):
    from unittest.mock import MagicMock

    # Create evidence that stalls at MOD-09
    transient_integrity = MagicMock(spec=IntegrityService)
    transient_integrity.verify_and_compute_integrity.side_effect = IOError("Transient error")

    stalled = _orchestrator(
        db_session,
        integrity_service=transient_integrity,
    ).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="no_repeat_test.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )
    assert stalled.overall_status == PipelineExecutionStatus.RETRYABLE_ERROR

    # Setup spy mocks for intake and WORM commit
    spy_intake = MagicMock(wraps=EvidenceIntakeService(db_session))
    spy_worm = MagicMock(wraps=WORMCommitService(db_session))

    resumed = _orchestrator(
        db_session,
        intake_service=spy_intake,
        worm_service=spy_worm,
    ).resume_existing_evidence(
        case_id=active_case.case_id,
        evidence_id=stalled.evidence_id,
        investigator=mock_io1,
    )

    assert resumed.overall_status == PipelineExecutionStatus.SUCCESS
    assert spy_intake.register_evidence.call_count == 0
    assert spy_worm.commit_evidence.call_count == 0


def test_busy_case_returns_retryable_result_without_intake(db_session, mock_io1):
    case_id = "SAKSHI-CASE-LOCKED"
    held_lock = _CasePipelineLockRegistry.try_acquire(case_id)
    assert held_lock is not None
    try:
        result = _orchestrator(db_session).execute_new_evidence(
            case_id=case_id,
            file_payload=CLEAN_PDF,
            original_filename="report.pdf",
            metadata=_metadata(),
            investigator=mock_io1,
        )
    finally:
        _CasePipelineLockRegistry.release(case_id, held_lock)

    assert result.overall_status == PipelineExecutionStatus.RETRYABLE_ERROR
    assert result.evidence_id is None


def test_unexpected_errors_are_sanitized(db_session, active_case, mock_io1):
    result = _orchestrator(
        db_session,
        intake_service=UnexpectedFailureIntakeService(),
    ).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="report.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )

    assert result.overall_status == PipelineExecutionStatus.INTAKE_FAILED
    assert "private" not in result.message
    assert "filesystem" not in result.message


def test_orchestrator_triggers_indexing_when_locked(db_session, active_case, mock_io1):
    from unittest.mock import MagicMock
    from app.models.rag_document import RAGDocument

    mock_doc = MagicMock(spec=RAGDocument)
    mock_doc.document_id = "SAKSHI-DOC-TEST1"
    mock_doc.indexing_status = "INDEXED"

    mock_indexer = MagicMock()
    mock_indexer.index_evidence.return_value = mock_doc

    result = _orchestrator(
        db_session,
        rag_indexing_service=mock_indexer,
    ).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="cctv_report.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )

    assert result.overall_status == PipelineExecutionStatus.SUCCESS
    assert result.lock_status == "LOCKED"
    assert result.integrity_status == "VERIFIED"
    assert result.document_id == "SAKSHI-DOC-TEST1"
    assert result.indexing_status == "INDEXED"
    assert mock_indexer.index_evidence.call_count == 1


def test_orchestrator_skips_indexing_for_non_text_mime(db_session, active_case, mock_io1):
    from unittest.mock import MagicMock
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    meta = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.SCENE_PHOTO,
        declared_mime_type="image/png",
        description="Scene photo",
    )

    mock_indexer = MagicMock()

    result = _orchestrator(
        db_session,
        rag_indexing_service=mock_indexer,
    ).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=png_bytes,
        original_filename="scene.png",
        metadata=meta,
        investigator=mock_io1,
    )

    assert result.overall_status == PipelineExecutionStatus.SUCCESS
    assert result.lock_status == "LOCKED"
    assert result.indexing_status == "SKIPPED"
    assert result.document_id is None
    assert mock_indexer.index_evidence.call_count == 0


def test_orchestrator_contains_indexing_error_and_returns_success(db_session, active_case, mock_io1):
    from unittest.mock import MagicMock

    mock_indexer = MagicMock()
    mock_indexer.index_evidence.side_effect = RuntimeError("Embedding service network partition")

    result = _orchestrator(
        db_session,
        rag_indexing_service=mock_indexer,
    ).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="report.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )

    # Invariant: Evidence is securely committed and locked, overall_status is SUCCESS
    assert result.overall_status == PipelineExecutionStatus.SUCCESS
    assert result.lock_status == "LOCKED"
    assert result.integrity_status == "VERIFIED"
    # Indexing status is FAILED and recoverable
    assert result.indexing_status == "FAILED"
    assert result.document_id is None
    assert mock_indexer.index_evidence.call_count == 1


def test_orchestrator_never_indexes_if_integrity_fails(db_session, active_case, mock_io1):
    from unittest.mock import MagicMock

    class FailingIntegrityService:
        def verify_and_compute_integrity(self, **kwargs):
            raise SHA256IntegrityMismatchException("recorded_sha256", "recomputed_sha256")

    mock_indexer = MagicMock()

    result = _orchestrator(
        db_session,
        integrity_service=FailingIntegrityService(),
        rag_indexing_service=mock_indexer,
    ).execute_new_evidence(
        case_id=active_case.case_id,
        file_payload=CLEAN_PDF,
        original_filename="tampered.pdf",
        metadata=_metadata(),
        investigator=mock_io1,
    )

    assert result.overall_status == PipelineExecutionStatus.INTEGRITY_FAILED
    # Indexing was never triggered
    assert mock_indexer.index_evidence.call_count == 0
    assert result.document_id is None
    assert result.indexing_status is None
