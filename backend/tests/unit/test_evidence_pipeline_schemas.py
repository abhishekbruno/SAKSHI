"""
Unit tests for MOD-05 to MOD-08 Evidence Pipeline Orchestration Schemas.

Validates PipelineStage, PipelineExecutionStatus, and PipelineExecutionResult
contracts, timezone enforcement, and validation rules.
"""
from datetime import datetime, timezone, timedelta, timezone as dt_timezone
import pytest
from pydantic import ValidationError

from app.schemas.evidence import (
    PipelineStage,
    PipelineExecutionStatus,
    PipelineExecutionResult,
    EvidenceIntakeStatus,
)


class TestPipelineStageEnum:
    """Test suite for PipelineStage enum members and values."""

    def test_pipeline_stage_values(self):
        expected_stages = {
            "INTAKE",
            "MIME_VALIDATION",
            "ANTIVIRUS_SCAN",
            "WORM_COMMIT",
            "DUAL_HASHING",
            "OBJECT_LOCK",
        }
        actual_stages = {stage.value for stage in PipelineStage}
        assert actual_stages == expected_stages

    def test_pipeline_stage_is_str_enum(self):
        assert PipelineStage.INTAKE == "INTAKE"
        assert isinstance(PipelineStage.INTAKE, str)


class TestPipelineExecutionStatusEnum:
    """Test suite for PipelineExecutionStatus enum members and values."""

    def test_pipeline_execution_status_values(self):
        expected_statuses = {
            "SUCCESS",
            "INTAKE_FAILED",
            "MIME_VALIDATION_FAILED",
            "ANTIVIRUS_QUARANTINED",
            "WORM_COMMIT_FAILED",
            "INTEGRITY_FAILED",
            "OBJECT_LOCK_FAILED",
            "RETRYABLE_ERROR",
        }
        actual_statuses = {status.value for status in PipelineExecutionStatus}
        assert actual_statuses == expected_statuses

    def test_pipeline_execution_status_is_str_enum(self):
        assert PipelineExecutionStatus.SUCCESS == "SUCCESS"
        assert isinstance(PipelineExecutionStatus.SUCCESS, str)


class TestPipelineExecutionResult:
    """Test suite for PipelineExecutionResult contract and validation rules."""

    @pytest.fixture
    def valid_timestamps(self):
        start = datetime(2026, 10, 21, 10, 0, 0, tzinfo=timezone.utc)
        completed = datetime(2026, 10, 21, 10, 0, 5, tzinfo=timezone.utc)
        return start, completed

    def test_valid_minimal_result(self, valid_timestamps):
        start, completed = valid_timestamps
        result = PipelineExecutionResult(
            case_id="CASE-2026-001",
            overall_status=PipelineExecutionStatus.SUCCESS,
            message="Pipeline completed successfully",
            started_at=start,
            completed_at=completed,
        )

        assert result.case_id == "CASE-2026-001"
        assert result.evidence_id is None
        assert result.overall_status == PipelineExecutionStatus.SUCCESS
        assert result.current_stage is None
        assert result.intake_status is None
        assert result.message == "Pipeline completed successfully"
        assert result.is_retryable is False
        assert result.started_at == start
        assert result.completed_at == completed

    def test_valid_full_result(self, valid_timestamps):
        start, completed = valid_timestamps
        result = PipelineExecutionResult(
            case_id="CASE-2026-001",
            evidence_id="EVID-2026-001",
            overall_status=PipelineExecutionStatus.SUCCESS,
            current_stage=PipelineStage.WORM_COMMIT,
            intake_status=EvidenceIntakeStatus.COMMITTED,
            message="Evidence committed to WORM storage",
            is_retryable=False,
            started_at=start,
            completed_at=completed,
        )

        assert result.evidence_id == "EVID-2026-001"
        assert result.current_stage == PipelineStage.WORM_COMMIT
        assert result.intake_status == EvidenceIntakeStatus.COMMITTED

    def test_reject_naive_started_at(self, valid_timestamps):
        _, completed = valid_timestamps
        naive_start = datetime(2026, 10, 21, 10, 0, 0)  # No tzinfo

        with pytest.raises(ValidationError) as exc_info:
            PipelineExecutionResult(
                case_id="CASE-2026-001",
                overall_status=PipelineExecutionStatus.SUCCESS,
                message="Naive start test",
                started_at=naive_start,
                completed_at=completed,
            )
        assert "timestamp must be timezone-aware" in str(exc_info.value)

    def test_reject_naive_completed_at(self, valid_timestamps):
        start, _ = valid_timestamps
        naive_completed = datetime(2026, 10, 21, 10, 0, 5)  # No tzinfo

        with pytest.raises(ValidationError) as exc_info:
            PipelineExecutionResult(
                case_id="CASE-2026-001",
                overall_status=PipelineExecutionStatus.SUCCESS,
                message="Naive completed test",
                started_at=start,
                completed_at=naive_completed,
            )
        assert "timestamp must be timezone-aware" in str(exc_info.value)

    def test_normalize_aware_non_utc_timestamp(self):
        offset_tz = dt_timezone(timedelta(hours=5, minutes=30))
        start_offset = datetime(2026, 10, 21, 15, 30, 0, tzinfo=offset_tz)
        completed_offset = datetime(2026, 10, 21, 15, 30, 5, tzinfo=offset_tz)

        result = PipelineExecutionResult(
            case_id="CASE-2026-001",
            overall_status=PipelineExecutionStatus.SUCCESS,
            message="Normalized offset test",
            started_at=start_offset,
            completed_at=completed_offset,
        )

        assert result.started_at.tzinfo == timezone.utc
        assert result.started_at == datetime(2026, 10, 21, 10, 0, 0, tzinfo=timezone.utc)
        assert result.completed_at.tzinfo == timezone.utc
        assert result.completed_at == datetime(2026, 10, 21, 10, 0, 5, tzinfo=timezone.utc)

    def test_retryable_true_with_retryable_error_status_allowed(self, valid_timestamps):
        start, completed = valid_timestamps
        result = PipelineExecutionResult(
            case_id="CASE-2026-001",
            overall_status=PipelineExecutionStatus.RETRYABLE_ERROR,
            current_stage=PipelineStage.ANTIVIRUS_SCAN,
            message="Antivirus scan timed out, retry scheduled",
            is_retryable=True,
            started_at=start,
            completed_at=completed,
        )
        assert result.is_retryable is True
        assert result.overall_status == PipelineExecutionStatus.RETRYABLE_ERROR

    def test_retryable_true_with_non_retryable_status_rejected(self, valid_timestamps):
        start, completed = valid_timestamps
        invalid_statuses = [
            PipelineExecutionStatus.SUCCESS,
            PipelineExecutionStatus.INTAKE_FAILED,
            PipelineExecutionStatus.MIME_VALIDATION_FAILED,
            PipelineExecutionStatus.ANTIVIRUS_QUARANTINED,
            PipelineExecutionStatus.WORM_COMMIT_FAILED,
            PipelineExecutionStatus.INTEGRITY_FAILED,
            PipelineExecutionStatus.OBJECT_LOCK_FAILED,
        ]

        for status in invalid_statuses:
            with pytest.raises(ValidationError) as exc_info:
                PipelineExecutionResult(
                    case_id="CASE-2026-001",
                    overall_status=status,
                    message=f"Invalid retryable combination for {status}",
                    is_retryable=True,
                    started_at=start,
                    completed_at=completed,
                )
            assert "is_retryable may be True only when overall_status is RETRYABLE_ERROR" in str(exc_info.value)

    def test_retryable_false_with_retryable_error_allowed(self, valid_timestamps):
        start, completed = valid_timestamps
        result = PipelineExecutionResult(
            case_id="CASE-2026-001",
            overall_status=PipelineExecutionStatus.RETRYABLE_ERROR,
            message="Retry budget exhausted",
            is_retryable=False,
            started_at=start,
            completed_at=completed,
        )
        assert result.is_retryable is False
        assert result.overall_status == PipelineExecutionStatus.RETRYABLE_ERROR

    def test_serialization_round_trip(self, valid_timestamps):
        start, completed = valid_timestamps
        original = PipelineExecutionResult(
            case_id="CASE-2026-001",
            evidence_id="EVID-2026-001",
            overall_status=PipelineExecutionStatus.SUCCESS,
            current_stage=PipelineStage.WORM_COMMIT,
            intake_status=EvidenceIntakeStatus.COMMITTED,
            message="Pipeline run complete",
            is_retryable=False,
            started_at=start,
            completed_at=completed,
        )

        data = original.model_dump()
        restored = PipelineExecutionResult.model_validate(data)
        assert original == restored
