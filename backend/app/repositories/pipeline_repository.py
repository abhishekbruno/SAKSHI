"""
Repository for SAKSHI Pipeline Runs, Stages, and Case Reports.
"""
from __future__ import annotations

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.pipeline_run import PipelineRun, PipelineStageRun, CaseReport


class PipelineRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_pipeline_run(self, run: PipelineRun) -> PipelineRun:
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_pipeline_run(self, run_id: str) -> Optional[PipelineRun]:
        return self.db.query(PipelineRun).filter(PipelineRun.run_id == run_id).first()

    def get_latest_run_for_case(self, case_id: str) -> Optional[PipelineRun]:
        return (
            self.db.query(PipelineRun)
            .filter(PipelineRun.case_id == case_id)
            .order_by(desc(PipelineRun.created_at))
            .first()
        )

    def list_runs_for_case(self, case_id: str) -> List[PipelineRun]:
        return (
            self.db.query(PipelineRun)
            .filter(PipelineRun.case_id == case_id)
            .order_by(desc(PipelineRun.created_at))
            .all()
        )

    def update_pipeline_run(self, run: PipelineRun) -> PipelineRun:
        self.db.commit()
        self.db.refresh(run)
        return run

    def create_stage_run(self, stage_run: PipelineStageRun) -> PipelineStageRun:
        self.db.add(stage_run)
        self.db.commit()
        self.db.refresh(stage_run)
        return stage_run

    def get_stage_runs(self, run_id: str) -> List[PipelineStageRun]:
        return (
            self.db.query(PipelineStageRun)
            .filter(PipelineStageRun.run_id == run_id)
            .order_by(PipelineStageRun.started_at)
            .all()
        )

    def update_stage_run(self, stage_run: PipelineStageRun) -> PipelineStageRun:
        self.db.commit()
        self.db.refresh(stage_run)
        return stage_run

    def create_case_report(self, report: CaseReport) -> CaseReport:
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report

    def get_latest_case_report(self, case_id: str) -> Optional[CaseReport]:
        return (
            self.db.query(CaseReport)
            .filter(CaseReport.case_id == case_id)
            .order_by(desc(CaseReport.created_at))
            .first()
        )

    def get_case_report_by_id(self, report_id: str) -> Optional[CaseReport]:
        return self.db.query(CaseReport).filter(CaseReport.report_id == report_id).first()

    def list_case_reports(self, case_id: str) -> List[CaseReport]:
        return (
            self.db.query(CaseReport)
            .filter(CaseReport.case_id == case_id)
            .order_by(desc(CaseReport.created_at))
            .all()
        )

    def update_case_report(self, report: CaseReport) -> CaseReport:
        self.db.commit()
        self.db.refresh(report)
        return report
