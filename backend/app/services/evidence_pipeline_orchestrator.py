"""MOD-05 through MOD-10 evidence-pipeline orchestration.

The orchestrator composes the existing authoritative domain services.  It does
not reproduce their authorization, validation, antivirus, WORM, dual hashing,
or object lock logic.
"""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.errors import (
    AntivirusThreatDetectedException,
    AntivirusTimeoutException,
    AntivirusUnavailableException,
    ForbiddenException,
    IntegrityNotVerifiedForLockException,
    ObjectLockFailedException,
    SakshiException,
    SHA256IntegrityMismatchException,
)
from app.core.logging import log_event
from app.core.security import AuthenticatedInvestigator
from app.models.evidence import Evidence
from app.repositories.evidence_repository import EvidenceRepository
from app.schemas.evidence import (
    EvidenceIntakeMetadata,
    EvidenceIntakeStatus,
    PipelineExecutionResult,
    PipelineExecutionStatus,
    PipelineStage,
)
from app.services.antivirus_scan_service import AntivirusScanService
from app.services.evidence_intake_service import EvidenceIntakeService
from app.services.integrity_service import IntegrityService
from app.services.mime_validation_service import MimeValidationService
from app.services.object_lock_service import ObjectLockService
from app.services.rag_indexing_service import RAGIndexingService
from app.services.worm_commit_service import WORMCommitService


class _CasePipelineLockRegistry:
    """Best-effort in-process serialization for composite evidence runs.

    The current repository has no workflow-run table or database locking API.
    This registry prevents two pipeline endpoint calls in this application
    process from advancing the same case simultaneously.  It deliberately
    does not claim a cross-process or cross-endpoint concurrency guarantee.
    """

    _registry_lock = Lock()
    _case_locks: dict[str, Lock] = {}

    @classmethod
    def try_acquire(cls, case_id: str) -> Optional[Lock]:
        with cls._registry_lock:
            case_lock = cls._case_locks.setdefault(case_id, Lock())

        if case_lock.acquire(blocking=False):
            return case_lock
        return None

    @classmethod
    def release(cls, case_id: str, case_lock: Lock) -> None:
        case_lock.release()
        with cls._registry_lock:
            if not case_lock.locked():
                cls._case_locks.pop(case_id, None)


class EvidencePipelineOrchestrator:
    """Coordinate the existing MOD-05 through MOD-10 services."""

    def __init__(
        self,
        db: Session,
        intake_service: Optional[EvidenceIntakeService] = None,
        mime_service: Optional[MimeValidationService] = None,
        antivirus_service: Optional[AntivirusScanService] = None,
        worm_service: Optional[WORMCommitService] = None,
        integrity_service: Optional[IntegrityService] = None,
        object_lock_service: Optional[ObjectLockService] = None,
        rag_indexing_service: Optional[RAGIndexingService] = None,
        auto_index: bool = True,
    ):
        self.db = db
        self.evidence_repo = EvidenceRepository(db)
        self.intake_service = intake_service or EvidenceIntakeService(db)
        self.mime_service = mime_service or MimeValidationService(db)
        self.antivirus_service = antivirus_service or AntivirusScanService(db)
        self.worm_service = worm_service or WORMCommitService(db)
        self.integrity_service = integrity_service or IntegrityService(db)
        self.object_lock_service = object_lock_service or ObjectLockService(db)
        self.rag_indexing_service = rag_indexing_service
        self.auto_index = auto_index

    def execute_new_evidence(
        self,
        case_id: str,
        file_payload: bytes,
        original_filename: str,
        metadata: EvidenceIntakeMetadata,
        investigator: AuthenticatedInvestigator,
    ) -> PipelineExecutionResult:
        """Run a new upload through MOD-05 to MOD-08 exactly once.

        Intake is deliberately never retried by this method.  If it creates an
        evidence record and a later stage fails, callers must use
        :meth:`resume_existing_evidence` with that returned evidence ID.
        """
        started_at = datetime.now(timezone.utc)
        case_lock = _CasePipelineLockRegistry.try_acquire(case_id)
        if case_lock is None:
            return self._result(
                case_id=case_id,
                overall_status=PipelineExecutionStatus.RETRYABLE_ERROR,
                current_stage=PipelineStage.INTAKE,
                completed_stages=[],
                message="Another pipeline execution is active for this case on this application instance.",
                started_at=started_at,
            )

        try:
            log_event(
                "PIPELINE_EXECUTION_STARTED",
                f"Evidence pipeline execution started for case '{case_id}'",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "original_filename": original_filename,
                    "stage": PipelineStage.INTAKE.value,
                },
            )

            try:
                intake = self.intake_service.register_evidence(
                    case_id=case_id,
                    file_payload=file_payload,
                    original_filename=original_filename,
                    metadata=metadata,
                    investigator=investigator,
                )
            except ForbiddenException as exc:
                log_event(
                    "PIPELINE_AUTHORIZATION_DENIED",
                    f"Authorization denied for investigator '{investigator.investigator_id}' on case '{case_id}'",
                    case_id=case_id,
                    investigator_id=investigator.investigator_id,
                    extra_data={"stage": PipelineStage.INTAKE.value, "error_code": "FORBIDDEN"},
                )
                raise exc
            except Exception as exc:
                log_event(
                    "PIPELINE_STAGE_FAILED",
                    f"Stage INTAKE failed for case '{case_id}': {self._safe_failure_reason(exc)}",
                    case_id=case_id,
                    investigator_id=investigator.investigator_id,
                    extra_data={"stage": PipelineStage.INTAKE.value, "error_code": "INTAKE_FAILED"},
                )
                return self._failure_result(
                    case_id=case_id,
                    evidence=None,
                    current_stage=PipelineStage.INTAKE,
                    completed_stages=[],
                    exc=exc,
                    started_at=started_at,
                )

            evidence = self.evidence_repo.get_by_evidence_id(intake.evidence_id)
            if not evidence or not self._is_intake_confirmed(evidence):
                return self._permanent_failure(
                    case_id=case_id,
                    evidence=evidence,
                    current_stage=PipelineStage.INTAKE,
                    completed_stages=[],
                    reason="Evidence intake was not confirmed in persistent storage.",
                    started_at=started_at,
                )

            log_event(
                "PIPELINE_STAGE_COMPLETED",
                f"Stage INTAKE completed for evidence '{evidence.evidence_id}'",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "stage": PipelineStage.INTAKE.value,
                },
            )

            return self._continue_from_persisted_evidence(
                case_id=case_id,
                evidence=evidence,
                investigator=investigator,
                started_at=started_at,
                completed_stages=[PipelineStage.INTAKE],
            )
        finally:
            _CasePipelineLockRegistry.release(case_id, case_lock)

    def resume_existing_evidence(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> PipelineExecutionResult:
        """Resume from verified persisted state without repeating MOD-05 intake."""
        started_at = datetime.now(timezone.utc)
        case_lock = _CasePipelineLockRegistry.try_acquire(case_id)
        if case_lock is None:
            return self._result(
                case_id=case_id,
                evidence_id=evidence_id,
                overall_status=PipelineExecutionStatus.RETRYABLE_ERROR,
                current_stage=PipelineStage.INTAKE,
                completed_stages=[],
                message="Another pipeline execution is active for this case on this application instance.",
                started_at=started_at,
            )

        try:
            log_event(
                "PIPELINE_EXECUTION_RESUMED",
                f"Evidence pipeline execution resumed for evidence '{evidence_id}' under case '{case_id}'",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={"evidence_id": evidence_id},
            )

            # Reuse MOD-05's case-isolated read authorization before examining
            # any persisted pipeline state.
            try:
                self.intake_service.get_evidence(
                    case_id=case_id,
                    evidence_id=evidence_id,
                    investigator=investigator,
                )
            except ForbiddenException as exc:
                log_event(
                    "PIPELINE_AUTHORIZATION_DENIED",
                    f"Authorization denied for investigator '{investigator.investigator_id}' on evidence '{evidence_id}'",
                    case_id=case_id,
                    investigator_id=investigator.investigator_id,
                    extra_data={"evidence_id": evidence_id, "error_code": "FORBIDDEN"},
                )
                raise exc
            except Exception as exc:
                return self._failure_result(
                    case_id=case_id,
                    evidence=None,
                    evidence_id=evidence_id,
                    current_stage=PipelineStage.INTAKE,
                    completed_stages=[],
                    exc=exc,
                    started_at=started_at,
                )

            evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
            if not evidence or evidence.case_id != case_id:
                return self._permanent_failure(
                    case_id=case_id,
                    evidence=None,
                    evidence_id=evidence_id,
                    current_stage=PipelineStage.INTAKE,
                    completed_stages=[],
                    reason="The requested evidence could not be loaded for pipeline processing.",
                    started_at=started_at,
                )

            return self._resume_from_persisted_state(
                case_id=case_id,
                evidence=evidence,
                investigator=investigator,
                started_at=started_at,
            )
        finally:
            _CasePipelineLockRegistry.release(case_id, case_lock)

    def _resume_from_persisted_state(
        self,
        case_id: str,
        evidence: Evidence,
        investigator: AuthenticatedInvestigator,
        started_at: datetime,
    ) -> PipelineExecutionResult:
        """Validate the persisted state before deciding which stage may run next."""
        if not self._is_intake_confirmed(evidence):
            return self._permanent_failure(
                case_id=case_id,
                evidence=evidence,
                current_stage=PipelineStage.INTAKE,
                completed_stages=[],
                reason="Persisted evidence metadata does not confirm a completed intake stage.",
                started_at=started_at,
            )

        completed_stages = [PipelineStage.INTAKE]
        persisted_status = evidence.status

        if persisted_status == EvidenceIntakeStatus.REJECTED.value:
            return self._result(
                case_id=case_id,
                evidence=evidence,
                overall_status=PipelineExecutionStatus.MIME_VALIDATION_FAILED,
                current_stage=PipelineStage.MIME_VALIDATION,
                completed_stages=completed_stages,
                message="Evidence MIME/signature validation rejected this evidence.",
                started_at=started_at,
            )

        if persisted_status == EvidenceIntakeStatus.QUARANTINED.value:
            if self._is_mime_confirmed(evidence):
                completed_stages.append(PipelineStage.MIME_VALIDATION)
            return self._result(
                case_id=case_id,
                evidence=evidence,
                overall_status=PipelineExecutionStatus.ANTIVIRUS_QUARANTINED,
                current_stage=PipelineStage.ANTIVIRUS_SCAN,
                completed_stages=completed_stages,
                message="Evidence was quarantined after antivirus detection.",
                started_at=started_at,
            )

        if self._is_worm_commit_confirmed(evidence):
            if not self._is_mime_confirmed(evidence) or not self._has_clean_scan_metadata(evidence):
                return self._permanent_failure(
                    case_id=case_id,
                    evidence=evidence,
                    current_stage=PipelineStage.WORM_COMMIT,
                    completed_stages=completed_stages,
                    reason="Persisted evidence metadata does not confirm all prior pipeline stages.",
                    started_at=started_at,
                )

            # Terminal integrity failure check - fail closed, never retry or lock
            if evidence.integrity_status == "FAILED":
                return self._result(
                    case_id=case_id,
                    evidence=evidence,
                    overall_status=PipelineExecutionStatus.INTEGRITY_FAILED,
                    current_stage=PipelineStage.DUAL_HASHING,
                    completed_stages=[
                        PipelineStage.INTAKE,
                        PipelineStage.MIME_VALIDATION,
                        PipelineStage.ANTIVIRUS_SCAN,
                        PipelineStage.WORM_COMMIT,
                    ],
                    message=evidence.integrity_verification_message or "Evidence failed cryptographic integrity verification.",
                    already_committed=True,
                    started_at=started_at,
                )

            # Fully locked evidence - report success without repeating earlier stages
            if self._is_object_lock_confirmed(evidence):
                doc_id, idx_status = self._trigger_indexing(case_id, evidence, investigator)
                return self._result(
                    case_id=case_id,
                    evidence=evidence,
                    overall_status=PipelineExecutionStatus.SUCCESS,
                    current_stage=PipelineStage.OBJECT_LOCK,
                    completed_stages=[
                        PipelineStage.INTAKE,
                        PipelineStage.MIME_VALIDATION,
                        PipelineStage.ANTIVIRUS_SCAN,
                        PipelineStage.WORM_COMMIT,
                        PipelineStage.DUAL_HASHING,
                        PipelineStage.OBJECT_LOCK,
                    ],
                    message="Evidence is already committed to WORM storage and locked.",
                    already_committed=True,
                    started_at=started_at,
                    document_id=doc_id,
                    indexing_status=idx_status,
                )

            # MOD-09 dual hashing verified, but MOD-10 object lock incomplete
            if self._is_dual_hashing_confirmed(evidence):
                completed_stages.extend([
                    PipelineStage.MIME_VALIDATION,
                    PipelineStage.ANTIVIRUS_SCAN,
                    PipelineStage.WORM_COMMIT,
                    PipelineStage.DUAL_HASHING,
                ])
                return self._run_object_lock(
                    case_id=case_id,
                    evidence=evidence,
                    investigator=investigator,
                    started_at=started_at,
                    completed_stages=completed_stages,
                )

            # MOD-08 committed, but MOD-09 incomplete
            completed_stages.extend([
                PipelineStage.MIME_VALIDATION,
                PipelineStage.ANTIVIRUS_SCAN,
                PipelineStage.WORM_COMMIT,
            ])
            return self._run_dual_hashing(
                case_id=case_id,
                evidence=evidence,
                investigator=investigator,
                started_at=started_at,
                completed_stages=completed_stages,
            )

        if persisted_status == EvidenceIntakeStatus.CLEAN.value:
            if not self._is_mime_confirmed(evidence) or not self._is_clean_scan_confirmed(evidence):
                return self._permanent_failure(
                    case_id=case_id,
                    evidence=evidence,
                    current_stage=PipelineStage.ANTIVIRUS_SCAN,
                    completed_stages=completed_stages,
                    reason="Persisted evidence metadata does not confirm a clean antivirus result.",
                    started_at=started_at,
                )
            completed_stages.extend([
                PipelineStage.MIME_VALIDATION,
                PipelineStage.ANTIVIRUS_SCAN,
            ])
            return self._run_worm_commit(
                case_id=case_id,
                evidence=evidence,
                investigator=investigator,
                started_at=started_at,
                completed_stages=completed_stages,
            )

        if persisted_status == EvidenceIntakeStatus.VALIDATED.value:
            if not self._is_mime_confirmed(evidence):
                return self._permanent_failure(
                    case_id=case_id,
                    evidence=evidence,
                    current_stage=PipelineStage.MIME_VALIDATION,
                    completed_stages=completed_stages,
                    reason="Persisted evidence metadata does not confirm MIME validation.",
                    started_at=started_at,
                )
            completed_stages.append(PipelineStage.MIME_VALIDATION)
            return self._run_antivirus_scan(
                case_id=case_id,
                evidence=evidence,
                investigator=investigator,
                started_at=started_at,
                completed_stages=completed_stages,
            )

        if persisted_status in {
            EvidenceIntakeStatus.REGISTERED_INTAKE.value,
            EvidenceIntakeStatus.PENDING_MIME_VALIDATION.value,
        }:
            return self._run_mime_validation(
                case_id=case_id,
                evidence=evidence,
                investigator=investigator,
                started_at=started_at,
                completed_stages=completed_stages,
            )

        return self._permanent_failure(
            case_id=case_id,
            evidence=evidence,
            current_stage=PipelineStage.INTAKE,
            completed_stages=completed_stages,
            reason="Persisted evidence status is not eligible for pipeline resumption.",
            started_at=started_at,
        )

    def _continue_from_persisted_evidence(
        self,
        case_id: str,
        evidence: Evidence,
        investigator: AuthenticatedInvestigator,
        started_at: datetime,
        completed_stages: List[PipelineStage],
    ) -> PipelineExecutionResult:
        return self._run_mime_validation(
            case_id=case_id,
            evidence=evidence,
            investigator=investigator,
            started_at=started_at,
            completed_stages=completed_stages,
        )

    def _run_mime_validation(
        self,
        case_id: str,
        evidence: Evidence,
        investigator: AuthenticatedInvestigator,
        started_at: datetime,
        completed_stages: List[PipelineStage],
    ) -> PipelineExecutionResult:
        try:
            validation = self.mime_service.validate_evidence(
                case_id=case_id,
                evidence_id=evidence.evidence_id,
                investigator=investigator,
            )
        except ForbiddenException as exc:
            raise exc
        except Exception as exc:
            log_event(
                "PIPELINE_STAGE_FAILED",
                f"Stage MIME_VALIDATION failed for evidence '{evidence.evidence_id}': {self._safe_failure_reason(exc)}",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "stage": PipelineStage.MIME_VALIDATION.value,
                    "error_code": "MIME_VALIDATION_FAILED",
                },
            )
            return self._failure_result(
                case_id=case_id,
                evidence=evidence,
                current_stage=PipelineStage.MIME_VALIDATION,
                completed_stages=completed_stages,
                exc=exc,
                started_at=started_at,
            )

        evidence = self.evidence_repo.get_by_evidence_id(evidence.evidence_id)
        if not validation.valid:
            log_event(
                "PIPELINE_STAGE_FAILED",
                f"MIME validation rejected evidence '{evidence.evidence_id}'",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "stage": PipelineStage.MIME_VALIDATION.value,
                    "error_code": "MIME_VALIDATION_FAILED",
                },
            )
            return self._result(
                case_id=case_id,
                evidence=evidence,
                overall_status=PipelineExecutionStatus.MIME_VALIDATION_FAILED,
                current_stage=PipelineStage.MIME_VALIDATION,
                completed_stages=completed_stages,
                message="Evidence MIME/signature validation rejected this evidence.",
                started_at=started_at,
            )
        if not evidence or not self._is_mime_confirmed(evidence):
            return self._permanent_failure(
                case_id=case_id,
                evidence=evidence,
                current_stage=PipelineStage.MIME_VALIDATION,
                completed_stages=completed_stages,
                reason="MIME validation was not confirmed in persistent storage.",
                started_at=started_at,
            )

        log_event(
            "PIPELINE_STAGE_COMPLETED",
            f"Stage MIME_VALIDATION completed for evidence '{evidence.evidence_id}'",
            case_id=case_id,
            investigator_id=investigator.investigator_id,
            extra_data={
                "evidence_id": evidence.evidence_id,
                "stage": PipelineStage.MIME_VALIDATION.value,
            },
        )

        return self._run_antivirus_scan(
            case_id=case_id,
            evidence=evidence,
            investigator=investigator,
            started_at=started_at,
            completed_stages=[*completed_stages, PipelineStage.MIME_VALIDATION],
        )

    def _run_antivirus_scan(
        self,
        case_id: str,
        evidence: Evidence,
        investigator: AuthenticatedInvestigator,
        started_at: datetime,
        completed_stages: List[PipelineStage],
    ) -> PipelineExecutionResult:
        try:
            scan = self.antivirus_service.scan_evidence(
                case_id=case_id,
                evidence_id=evidence.evidence_id,
                investigator=investigator,
            )
        except ForbiddenException as exc:
            raise exc
        except (AntivirusUnavailableException, AntivirusTimeoutException) as exc:
            log_event(
                "PIPELINE_STAGE_RETRYABLE",
                f"Antivirus service operational issue for evidence '{evidence.evidence_id}': {self._safe_failure_reason(exc)}",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "stage": PipelineStage.ANTIVIRUS_SCAN.value,
                    "error_code": "RETRYABLE_ERROR",
                },
            )
            return self._result(
                case_id=case_id,
                evidence=evidence,
                overall_status=PipelineExecutionStatus.RETRYABLE_ERROR,
                current_stage=PipelineStage.ANTIVIRUS_SCAN,
                completed_stages=completed_stages,
                message=self._safe_failure_reason(exc),
                started_at=started_at,
            )
        except AntivirusThreatDetectedException as exc:
            log_event(
                "PIPELINE_STAGE_FAILED",
                f"Antivirus threat detected for evidence '{evidence.evidence_id}'",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "stage": PipelineStage.ANTIVIRUS_SCAN.value,
                    "error_code": "ANTIVIRUS_QUARANTINED",
                },
            )
            evidence = self.evidence_repo.get_by_evidence_id(evidence.evidence_id)
            return self._result(
                case_id=case_id,
                evidence=evidence,
                overall_status=PipelineExecutionStatus.ANTIVIRUS_QUARANTINED,
                current_stage=PipelineStage.ANTIVIRUS_SCAN,
                completed_stages=completed_stages,
                message="Evidence was quarantined after antivirus detection.",
                started_at=started_at,
            )
        except Exception as exc:
            log_event(
                "PIPELINE_STAGE_FAILED",
                f"Stage ANTIVIRUS_SCAN failed for evidence '{evidence.evidence_id}': {self._safe_failure_reason(exc)}",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "stage": PipelineStage.ANTIVIRUS_SCAN.value,
                    "error_code": "ANTIVIRUS_SCAN_ERROR",
                },
            )
            return self._failure_result(
                case_id=case_id,
                evidence=evidence,
                current_stage=PipelineStage.ANTIVIRUS_SCAN,
                completed_stages=completed_stages,
                exc=exc,
                started_at=started_at,
            )

        evidence = self.evidence_repo.get_by_evidence_id(evidence.evidence_id)
        if scan.status == EvidenceIntakeStatus.QUARANTINED.value:
            log_event(
                "PIPELINE_STAGE_FAILED",
                f"Evidence '{evidence.evidence_id}' quarantined by antivirus scanner",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "stage": PipelineStage.ANTIVIRUS_SCAN.value,
                    "error_code": "ANTIVIRUS_QUARANTINED",
                },
            )
            return self._result(
                case_id=case_id,
                evidence=evidence,
                overall_status=PipelineExecutionStatus.ANTIVIRUS_QUARANTINED,
                current_stage=PipelineStage.ANTIVIRUS_SCAN,
                completed_stages=completed_stages,
                message="Evidence was quarantined after antivirus detection.",
                started_at=started_at,
            )
        if not evidence or not self._is_clean_scan_confirmed(evidence):
            return self._permanent_failure(
                case_id=case_id,
                evidence=evidence,
                current_stage=PipelineStage.ANTIVIRUS_SCAN,
                completed_stages=completed_stages,
                reason="Antivirus scanning was not confirmed as clean in persistent storage.",
                started_at=started_at,
            )

        log_event(
            "PIPELINE_STAGE_COMPLETED",
            f"Stage ANTIVIRUS_SCAN completed clean for evidence '{evidence.evidence_id}'",
            case_id=case_id,
            investigator_id=investigator.investigator_id,
            extra_data={
                "evidence_id": evidence.evidence_id,
                "stage": PipelineStage.ANTIVIRUS_SCAN.value,
            },
        )

        return self._run_worm_commit(
            case_id=case_id,
            evidence=evidence,
            investigator=investigator,
            started_at=started_at,
            completed_stages=[*completed_stages, PipelineStage.ANTIVIRUS_SCAN],
        )

    def _run_worm_commit(
        self,
        case_id: str,
        evidence: Evidence,
        investigator: AuthenticatedInvestigator,
        started_at: datetime,
        completed_stages: List[PipelineStage],
    ) -> PipelineExecutionResult:
        try:
            commit = self.worm_service.commit_evidence(
                case_id=case_id,
                evidence_id=evidence.evidence_id,
                investigator=investigator,
            )
        except ForbiddenException as exc:
            raise exc
        except Exception as exc:
            log_event(
                "PIPELINE_STAGE_FAILED",
                f"Stage WORM_COMMIT failed for evidence '{evidence.evidence_id}': {self._safe_failure_reason(exc)}",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "stage": PipelineStage.WORM_COMMIT.value,
                    "error_code": "WORM_COMMIT_FAILED",
                },
            )
            return self._failure_result(
                case_id=case_id,
                evidence=evidence,
                current_stage=PipelineStage.WORM_COMMIT,
                completed_stages=completed_stages,
                exc=exc,
                started_at=started_at,
            )

        evidence = self.evidence_repo.get_by_evidence_id(evidence.evidence_id)
        if not evidence or not self._is_worm_commit_confirmed(evidence):
            return self._permanent_failure(
                case_id=case_id,
                evidence=evidence,
                current_stage=PipelineStage.WORM_COMMIT,
                completed_stages=completed_stages,
                reason="WORM commitment was not confirmed in persistent storage.",
                started_at=started_at,
            )

        log_event(
            "PIPELINE_STAGE_COMPLETED",
            f"Stage WORM_COMMIT completed for evidence '{evidence.evidence_id}'",
            case_id=case_id,
            investigator_id=investigator.investigator_id,
            extra_data={
                "evidence_id": evidence.evidence_id,
                "stage": PipelineStage.WORM_COMMIT.value,
                "worm_reference": evidence.worm_storage_reference,
            },
        )

        return self._run_dual_hashing(
            case_id=case_id,
            evidence=evidence,
            investigator=investigator,
            started_at=started_at,
            completed_stages=[*completed_stages, PipelineStage.WORM_COMMIT],
        )

    def _run_dual_hashing(
        self,
        case_id: str,
        evidence: Evidence,
        investigator: AuthenticatedInvestigator,
        started_at: datetime,
        completed_stages: List[PipelineStage],
    ) -> PipelineExecutionResult:
        try:
            self.integrity_service.verify_and_compute_integrity(
                case_id=case_id,
                evidence_id=evidence.evidence_id,
                investigator=investigator,
            )
        except ForbiddenException as exc:
            raise exc
        except SHA256IntegrityMismatchException as exc:
            log_event(
                "PIPELINE_STAGE_FAILED",
                f"Stage DUAL_HASHING failed with integrity mismatch for evidence '{evidence.evidence_id}': {self._safe_failure_reason(exc)}",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "stage": PipelineStage.DUAL_HASHING.value,
                    "error_code": "INTEGRITY_FAILED",
                },
            )
            evidence = self.evidence_repo.get_by_evidence_id(evidence.evidence_id)
            return self._result(
                case_id=case_id,
                evidence=evidence,
                overall_status=PipelineExecutionStatus.INTEGRITY_FAILED,
                current_stage=PipelineStage.DUAL_HASHING,
                completed_stages=completed_stages,
                message=self._safe_failure_reason(exc),
                already_committed=True,
                started_at=started_at,
            )
        except (IOError, OSError) as exc:
            log_event(
                "PIPELINE_STAGE_RETRYABLE",
                f"Dual hashing transient I/O issue for evidence '{evidence.evidence_id}': {self._safe_failure_reason(exc)}",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "stage": PipelineStage.DUAL_HASHING.value,
                    "error_code": "RETRYABLE_ERROR",
                },
            )
            evidence = self.evidence_repo.get_by_evidence_id(evidence.evidence_id)
            return self._result(
                case_id=case_id,
                evidence=evidence,
                overall_status=PipelineExecutionStatus.RETRYABLE_ERROR,
                current_stage=PipelineStage.DUAL_HASHING,
                completed_stages=completed_stages,
                message=self._safe_failure_reason(exc),
                already_committed=True,
                started_at=started_at,
            )
        except Exception as exc:
            log_event(
                "PIPELINE_STAGE_FAILED",
                f"Stage DUAL_HASHING failed for evidence '{evidence.evidence_id}': {self._safe_failure_reason(exc)}",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "stage": PipelineStage.DUAL_HASHING.value,
                    "error_code": "DUAL_HASHING_FAILED",
                },
            )
            evidence = self.evidence_repo.get_by_evidence_id(evidence.evidence_id)
            return self._failure_result(
                case_id=case_id,
                evidence=evidence,
                current_stage=PipelineStage.DUAL_HASHING,
                completed_stages=completed_stages,
                exc=exc,
                started_at=started_at,
            )

        evidence = self.evidence_repo.get_by_evidence_id(evidence.evidence_id)
        if not evidence or not self._is_dual_hashing_confirmed(evidence):
            return self._permanent_failure(
                case_id=case_id,
                evidence=evidence,
                current_stage=PipelineStage.DUAL_HASHING,
                completed_stages=completed_stages,
                reason="Dual hashing integrity verification was not confirmed in persistent storage.",
                started_at=started_at,
            )

        log_event(
            "PIPELINE_STAGE_COMPLETED",
            f"Stage DUAL_HASHING completed for evidence '{evidence.evidence_id}'",
            case_id=case_id,
            investigator_id=investigator.investigator_id,
            extra_data={
                "evidence_id": evidence.evidence_id,
                "stage": PipelineStage.DUAL_HASHING.value,
                "checksum_sha256": evidence.checksum_sha256,
                "checksum_sha3_512": evidence.checksum_sha3_512,
            },
        )

        return self._run_object_lock(
            case_id=case_id,
            evidence=evidence,
            investigator=investigator,
            started_at=started_at,
            completed_stages=[*completed_stages, PipelineStage.DUAL_HASHING],
        )

    def _run_object_lock(
        self,
        case_id: str,
        evidence: Evidence,
        investigator: AuthenticatedInvestigator,
        started_at: datetime,
        completed_stages: List[PipelineStage],
    ) -> PipelineExecutionResult:
        try:
            lock_res = self.object_lock_service.apply_object_lock(
                case_id=case_id,
                evidence_id=evidence.evidence_id,
                investigator=investigator,
            )
        except ForbiddenException as exc:
            raise exc
        except (IOError, OSError) as exc:
            log_event(
                "PIPELINE_STAGE_RETRYABLE",
                f"Object lock transient I/O issue for evidence '{evidence.evidence_id}': {self._safe_failure_reason(exc)}",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "stage": PipelineStage.OBJECT_LOCK.value,
                    "error_code": "RETRYABLE_ERROR",
                },
            )
            evidence = self.evidence_repo.get_by_evidence_id(evidence.evidence_id)
            return self._result(
                case_id=case_id,
                evidence=evidence,
                overall_status=PipelineExecutionStatus.RETRYABLE_ERROR,
                current_stage=PipelineStage.OBJECT_LOCK,
                completed_stages=completed_stages,
                message=self._safe_failure_reason(exc),
                already_committed=True,
                started_at=started_at,
            )
        except ObjectLockFailedException as exc:
            log_event(
                "PIPELINE_STAGE_FAILED",
                f"Stage OBJECT_LOCK failed for evidence '{evidence.evidence_id}': {self._safe_failure_reason(exc)}",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "stage": PipelineStage.OBJECT_LOCK.value,
                    "error_code": "OBJECT_LOCK_FAILED",
                },
            )
            evidence = self.evidence_repo.get_by_evidence_id(evidence.evidence_id)
            return self._result(
                case_id=case_id,
                evidence=evidence,
                overall_status=PipelineExecutionStatus.OBJECT_LOCK_FAILED,
                current_stage=PipelineStage.OBJECT_LOCK,
                completed_stages=completed_stages,
                message=self._safe_failure_reason(exc),
                already_committed=True,
                started_at=started_at,
            )
        except Exception as exc:
            log_event(
                "PIPELINE_STAGE_FAILED",
                f"Stage OBJECT_LOCK failed for evidence '{evidence.evidence_id}': {self._safe_failure_reason(exc)}",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "stage": PipelineStage.OBJECT_LOCK.value,
                    "error_code": "OBJECT_LOCK_FAILED",
                },
            )
            evidence = self.evidence_repo.get_by_evidence_id(evidence.evidence_id)
            return self._failure_result(
                case_id=case_id,
                evidence=evidence,
                current_stage=PipelineStage.OBJECT_LOCK,
                completed_stages=completed_stages,
                exc=exc,
                started_at=started_at,
            )

        evidence = self.evidence_repo.get_by_evidence_id(evidence.evidence_id)
        if not evidence or not self._is_object_lock_confirmed(evidence):
            return self._permanent_failure(
                case_id=case_id,
                evidence=evidence,
                current_stage=PipelineStage.OBJECT_LOCK,
                completed_stages=completed_stages,
                reason="Object lock was not confirmed in persistent storage.",
                started_at=started_at,
            )

        doc_id, idx_status = self._trigger_indexing(case_id, evidence, investigator)

        log_event(
            "PIPELINE_EXECUTION_COMPLETED",
            f"Evidence pipeline execution succeeded through MOD-10 for evidence '{evidence.evidence_id}' under case '{case_id}'",
            case_id=case_id,
            investigator_id=investigator.investigator_id,
            extra_data={
                "evidence_id": evidence.evidence_id,
                "overall_status": PipelineExecutionStatus.SUCCESS.value,
                "worm_reference": evidence.worm_storage_reference,
                "lock_storage_reference": evidence.lock_storage_reference,
                "document_id": doc_id,
                "indexing_status": idx_status,
            },
        )

        return self._result(
            case_id=case_id,
            evidence=evidence,
            overall_status=PipelineExecutionStatus.SUCCESS,
            current_stage=PipelineStage.OBJECT_LOCK,
            completed_stages=[*completed_stages, PipelineStage.OBJECT_LOCK],
            message="Evidence completed the MOD-05 through MOD-10 pipeline.",
            already_committed=getattr(lock_res, "already_locked", False),
            started_at=started_at,
            document_id=doc_id,
            indexing_status=idx_status,
        )

    def _trigger_indexing(
        self,
        case_id: str,
        evidence: Evidence,
        investigator: AuthenticatedInvestigator,
    ) -> tuple[Optional[str], Optional[str]]:
        """Trigger RAG indexing for locked evidence if auto_index is enabled.

        Returns (document_id, indexing_status).
        If indexing fails or evidence is not indexable, returns (None, status)
        without raising, so that evidence pipeline overall_status remains SUCCESS.
        """
        if not self.auto_index:
            return None, None

        INDEXABLE_MIME_TYPES = {
            "application/pdf",
            "text/plain",
            "text/markdown",
            "text/csv",
        }
        mime = (evidence.detected_mime_type or evidence.declared_mime_type or "").lower()
        if mime not in INDEXABLE_MIME_TYPES:
            log_event(
                "PIPELINE_INDEXING_SKIPPED",
                f"Evidence '{evidence.evidence_id}' has non-indexable MIME type '{mime}'; indexing skipped.",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "mime_type": mime,
                },
            )
            return None, "SKIPPED"

        try:
            indexer = self.rag_indexing_service or RAGIndexingService(self.db)
            doc = indexer.index_evidence(
                case_id=case_id,
                evidence_id=evidence.evidence_id,
                investigator=investigator,
            )
            log_event(
                "PIPELINE_INDEXING_COMPLETED",
                f"RAG indexing completed for evidence '{evidence.evidence_id}' as document '{doc.document_id}'",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "document_id": doc.document_id,
                    "indexing_status": doc.indexing_status,
                },
            )
            return doc.document_id, doc.indexing_status
        except Exception as exc:
            log_event(
                "PIPELINE_INDEXING_FAILED",
                f"RAG indexing failed for evidence '{evidence.evidence_id}': {self._safe_failure_reason(exc)}",
                case_id=case_id,
                investigator_id=investigator.investigator_id,
                extra_data={
                    "evidence_id": evidence.evidence_id,
                    "error_code": "INDEXING_FAILED",
                    "error_detail": str(exc),
                },
            )
            return None, "FAILED"

    @staticmethod
    def _is_intake_confirmed(evidence: Evidence) -> bool:
        return bool(
            evidence.evidence_id
            and evidence.case_id
            and evidence.raw_storage_path
            and evidence.status
        )

    @staticmethod
    def _is_mime_confirmed(evidence: Evidence) -> bool:
        return bool(evidence.detected_mime_type and evidence.validated_at)

    @staticmethod
    def _is_clean_scan_confirmed(evidence: Evidence) -> bool:
        return bool(
            evidence.status == EvidenceIntakeStatus.CLEAN.value
            and EvidencePipelineOrchestrator._has_clean_scan_metadata(evidence)
        )

    @staticmethod
    def _has_clean_scan_metadata(evidence: Evidence) -> bool:
        return bool(
            evidence.antivirus_status == "CLEAN"
            and evidence.antivirus_scanner
            and evidence.antivirus_scanned_at
        )

    @staticmethod
    def _is_worm_commit_confirmed(evidence: Evidence) -> bool:
        return bool(
            evidence.status == EvidenceIntakeStatus.COMMITTED.value
            and evidence.worm_status == "COMMITTED"
            and evidence.worm_storage_reference
            and evidence.checksum_sha256
        )

    @staticmethod
    def _is_dual_hashing_confirmed(evidence: Evidence) -> bool:
        return bool(
            evidence.integrity_status == "VERIFIED"
            and evidence.checksum_sha256
            and evidence.checksum_sha3_512
        )

    @staticmethod
    def _is_object_lock_confirmed(evidence: Evidence) -> bool:
        return bool(
            evidence.lock_status == "LOCKED"
            and evidence.lock_storage_reference
        )

    def _failure_result(
        self,
        case_id: str,
        evidence: Optional[Evidence],
        current_stage: PipelineStage,
        completed_stages: List[PipelineStage],
        exc: Exception,
        started_at: datetime,
        evidence_id: Optional[str] = None,
    ) -> PipelineExecutionResult:
        if isinstance(exc, ForbiddenException):
            raise exc

        if isinstance(exc, (AntivirusUnavailableException, AntivirusTimeoutException)):
            status = PipelineExecutionStatus.RETRYABLE_ERROR
        elif isinstance(exc, (IOError, OSError)):
            status = PipelineExecutionStatus.RETRYABLE_ERROR
        elif isinstance(exc, AntivirusThreatDetectedException):
            status = PipelineExecutionStatus.ANTIVIRUS_QUARANTINED
        elif isinstance(exc, SHA256IntegrityMismatchException):
            status = PipelineExecutionStatus.INTEGRITY_FAILED
        elif isinstance(exc, ObjectLockFailedException):
            status = PipelineExecutionStatus.OBJECT_LOCK_FAILED
        elif current_stage == PipelineStage.INTAKE:
            status = PipelineExecutionStatus.INTAKE_FAILED
        elif current_stage == PipelineStage.MIME_VALIDATION:
            status = PipelineExecutionStatus.MIME_VALIDATION_FAILED
        elif current_stage == PipelineStage.WORM_COMMIT:
            status = PipelineExecutionStatus.WORM_COMMIT_FAILED
        elif current_stage == PipelineStage.DUAL_HASHING:
            status = PipelineExecutionStatus.INTEGRITY_FAILED
        elif current_stage == PipelineStage.OBJECT_LOCK:
            status = PipelineExecutionStatus.OBJECT_LOCK_FAILED
        else:
            status = PipelineExecutionStatus.INTAKE_FAILED

        return self._result(
            case_id=case_id,
            evidence=evidence,
            evidence_id=evidence_id,
            overall_status=status,
            current_stage=current_stage,
            completed_stages=completed_stages,
            message=self._safe_failure_reason(exc),
            started_at=started_at,
        )

    def _permanent_failure(
        self,
        case_id: str,
        evidence: Optional[Evidence],
        current_stage: PipelineStage,
        completed_stages: List[PipelineStage],
        reason: str,
        started_at: datetime,
        evidence_id: Optional[str] = None,
    ) -> PipelineExecutionResult:
        if current_stage == PipelineStage.INTAKE:
            status = PipelineExecutionStatus.INTAKE_FAILED
        elif current_stage == PipelineStage.MIME_VALIDATION:
            status = PipelineExecutionStatus.MIME_VALIDATION_FAILED
        elif current_stage == PipelineStage.WORM_COMMIT:
            status = PipelineExecutionStatus.WORM_COMMIT_FAILED
        elif current_stage == PipelineStage.ANTIVIRUS_SCAN:
            status = PipelineExecutionStatus.ANTIVIRUS_QUARANTINED
        elif current_stage == PipelineStage.DUAL_HASHING:
            status = PipelineExecutionStatus.INTEGRITY_FAILED
        elif current_stage == PipelineStage.OBJECT_LOCK:
            status = PipelineExecutionStatus.OBJECT_LOCK_FAILED
        else:
            status = PipelineExecutionStatus.INTAKE_FAILED

        return self._result(
            case_id=case_id,
            evidence=evidence,
            evidence_id=evidence_id,
            overall_status=status,
            current_stage=current_stage,
            completed_stages=completed_stages,
            message=reason,
            started_at=started_at,
        )

    @staticmethod
    def _safe_failure_reason(exc: Exception) -> str:
        """Return a client-safe reason without echoing filesystem or scanner internals."""
        if isinstance(exc, ForbiddenException):
            return "Authorization was denied for this evidence pipeline operation."
        if isinstance(exc, AntivirusUnavailableException):
            return "The configured antivirus scanner is unavailable; the pipeline stopped fail-closed."
        if isinstance(exc, AntivirusTimeoutException):
            return "The antivirus scan timed out; the pipeline stopped fail-closed."
        if isinstance(exc, AntivirusThreatDetectedException):
            return "Evidence was quarantined after antivirus detection."
        if isinstance(exc, SHA256IntegrityMismatchException):
            return "Evidence failed cryptographic SHA-256 integrity verification."
        if isinstance(exc, ObjectLockFailedException):
            return "Failed to apply WORM object lock to evidence."
        if isinstance(exc, (IOError, OSError)):
            return "Transient I/O operation error during pipeline processing."
        if isinstance(exc, SakshiException):
            return "The evidence pipeline stage could not be completed. Review the server audit record."
        return "An unexpected pipeline error occurred. Review the server audit record."

    @staticmethod
    def _to_evidence_status(evidence: Optional[Evidence]) -> Optional[EvidenceIntakeStatus]:
        if not evidence or not evidence.status:
            return None
        try:
            return EvidenceIntakeStatus(evidence.status)
        except ValueError:
            return None

    def _result(
        self,
        case_id: str,
        overall_status: PipelineExecutionStatus,
        current_stage: PipelineStage,
        completed_stages: List[PipelineStage],
        message: str,
        started_at: datetime,
        evidence: Optional[Evidence] = None,
        evidence_id: Optional[str] = None,
        already_committed: bool = False,
        document_id: Optional[str] = None,
        indexing_status: Optional[str] = None,
    ) -> PipelineExecutionResult:
        return PipelineExecutionResult(
            case_id=case_id,
            evidence_id=evidence.evidence_id if evidence else evidence_id,
            overall_status=overall_status,
            current_stage=current_stage,
            completed_stages=completed_stages,
            intake_status=self._to_evidence_status(evidence),
            message=message,
            worm_storage_reference=(
                evidence.worm_storage_reference if evidence else None
            ),
            checksum_sha256=evidence.checksum_sha256 if evidence else None,
            checksum_sha3_512=evidence.checksum_sha3_512 if evidence else None,
            lock_storage_reference=evidence.lock_storage_reference if evidence else None,
            integrity_status=evidence.integrity_status if evidence else None,
            lock_status=evidence.lock_status if evidence else None,
            already_committed=already_committed,
            is_retryable=overall_status == PipelineExecutionStatus.RETRYABLE_ERROR,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
            document_id=document_id,
            indexing_status=indexing_status,
        )
