"""
SAKSHI Investigation Pipeline Orchestrator.
Orchestrates the complete end-to-end automated investigation pipeline:
Phase 1: Case Creation & FIR Classification
Phase 2: Evidence Intake & Security (MIME, AV, WORM, Dual Hash, Object Lock)
Phase 3: Document Processing & Normalization
Phase 4: Chunking, Embeddings, Indexing & RAG
Phase 5: Structured Fact, Entity, Event & Statement Extraction
Phase 6A: Evidence-Backed Entity Relationship Graph
Phase 6B: Branching Timeline Construction
Phase 7: Statement Comparison & Gap Analysis
Phase 8: Preliminary Investigation Report Generation
Phase 9: Exception-Based Investigator Review Queue
"""
from __future__ import annotations

import base64
import io
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pypdf
from sqlalchemy.orm import Session

from app.core.errors import (
    CaseNotFoundException,
    ForbiddenException,
    InvalidCaseDataException,
    InvalidEvidenceDataException,
    SakshiException,
)
from app.core.logging import log_event, logger
from app.core.security import AuthenticatedInvestigator
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.pipeline_run import (
    CaseReport,
    PipelineRun,
    PipelineRunStatus,
    PipelineStageName,
    PipelineStageRun,
    get_utc_now,
)
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.pipeline_repository import PipelineRepository
from app.schemas.case import (
    CaseCreateRequest,
    CaseResponse,
    FIRMetadata,
)
from app.schemas.evidence import (
    EvidenceCategory,
    EvidenceIntakeMetadata,
    PipelineExecutionResult,
    PipelineExecutionStatus,
)
from app.schemas.pipeline import (
    AutoRegisterCaseResponse,
    CaseReportResponse,
    CaseReportSection,
    PipelineRunResponse,
    PipelineStageRunResponse,
)
from app.services.case_service import CaseService
from app.services.evidence_extraction_service import EvidenceExtractionService
from app.services.evidence_intelligence_service import EvidenceIntelligenceService
from app.services.evidence_pipeline_orchestrator import EvidencePipelineOrchestrator


class InvestigationPipelineOrchestrator:
    """End-to-End Automated Investigation Pipeline Orchestrator for SAKSHI."""

    def __init__(
        self,
        db: Session,
        case_service: Optional[CaseService] = None,
        evidence_orchestrator: Optional[EvidencePipelineOrchestrator] = None,
        extraction_service: Optional[EvidenceExtractionService] = None,
        intelligence_service: Optional[EvidenceIntelligenceService] = None,
        pipeline_repo: Optional[PipelineRepository] = None,
    ):
        self.db = db
        self.case_service = case_service or CaseService(db)
        self.evidence_orchestrator = evidence_orchestrator or EvidencePipelineOrchestrator(db)
        self.extraction_service = extraction_service or EvidenceExtractionService(db)
        self.intelligence_service = intelligence_service or EvidenceIntelligenceService(db)
        self.pipeline_repo = pipeline_repo or PipelineRepository(db)
        self.case_repo = CaseRepository(db)
        self.evidence_repo = EvidenceRepository(db)

    def auto_register_and_process(
        self,
        investigator: AuthenticatedInvestigator,
        file_payload: Optional[bytes] = None,
        original_filename: Optional[str] = None,
        fir_text: Optional[str] = None,
        title_override: Optional[str] = None,
        assigned_io_override: Optional[str] = None,
    ) -> AutoRegisterCaseResponse:
        """
        Target User Workflow:
        1. Ingest FIR (file or text) without requiring field-by-field approval.
        2. Automatically classify case (e.g. PROPERTY_LOSS vs DEATH_INVESTIGATION).
        3. Authoritatively register and persist Case record.
        4. Ingest and preserve FIR exhibit through security pipeline (MIME, AV, WORM, Hash, Lock, RAG).
        5. Extract structured facts, entities, events, statements.
        6. Construct entity knowledge graph and timeline.
        7. Execute statement comparisons and evidence gap analysis.
        8. Generate and persist comprehensive preliminary investigation report.
        9. Return registered case, pipeline run status, and report.
        """
        started_at = get_utc_now()

        # Step 0: Extract text from file or raw text input
        raw_text, filename = self._resolve_raw_text(file_payload, original_filename, fir_text)
        if not raw_text or len(raw_text.strip()) < 5:
            raise InvalidCaseDataException("FIR document content is required for automatic registration.")

        # Step 1: Automated extraction of candidate case particulars
        candidate = self.extraction_service.extract_fir_candidate_details(raw_text, filename=filename)

        incident_type = candidate.incident_type or "NEEDS_REVIEW"
        fir_number = candidate.fir_number or f"FIR-AUTO-{datetime.now().year}-{uuid.uuid4().hex[:6].upper()}"
        police_station = candidate.police_station or "Jurisdiction Police Station"

        # Prepare FIR Metadata based on incident classification
        fir_metadata_dict = {
            "fir_number": fir_number,
            "police_station": police_station,
            "report_date": candidate.report_date,
            "incident_date": candidate.incident_date or "Unknown / not established",
            "incident_location": candidate.incident_location or "Unknown / not established",
            "incident_type": incident_type,
            "complainant_name": candidate.complainant_name or "Not recorded",
            "jurisdiction_code": getattr(investigator, "jurisdiction", None) or "DEFAULT",
        }

        # Keep property loss distinct from death investigations
        if incident_type == "PROPERTY_LOSS":
            fir_metadata_dict["property_items"] = candidate.property_items or "Not recorded"
            fir_metadata_dict["last_confirmed_present"] = candidate.last_confirmed_present
            fir_metadata_dict["discovery_time"] = candidate.discovery_time
            fir_metadata_dict["victim_name"] = None
        else:
            fir_metadata_dict["victim_name"] = candidate.victim_name
            fir_metadata_dict["discovery_time"] = candidate.discovery_time
            fir_metadata_dict["time_of_death"] = candidate.time_of_death or "Unknown / not established"
            fir_metadata_dict["cause_of_death"] = candidate.cause_of_death or "Unknown / pending post-mortem"

        # Check for existing duplicate case for idempotency
        existing = self.case_repo.find_existing_by_fir(fir_number=fir_number, police_station=police_station)
        if existing:
            meta = dict(existing.fir_metadata or {})
            updated_meta = False
            for k, v in fir_metadata_dict.items():
                if v is not None and (k not in meta or meta[k] is None):
                    meta[k] = v
                    updated_meta = True
            if updated_meta:
                existing.fir_metadata = meta
                self.case_repo.update(existing)

            latest_run = self.pipeline_repo.get_latest_run_for_case(existing.case_id)
            latest_report = self.pipeline_repo.get_latest_case_report(existing.case_id)
            if not latest_report:
                self.run_case_investigation_pipeline(existing.case_id, investigator)
                latest_run = self.pipeline_repo.get_latest_run_for_case(existing.case_id)
                latest_report = self.pipeline_repo.get_latest_case_report(existing.case_id)

            exhibits = self.evidence_repo.list_by_case_id(existing.case_id)
            fir_ev = exhibits[0] if exhibits else None
            fir_id = fir_ev.evidence_id if fir_ev else f"EV-{existing.case_id[:8]}-FIR"

            case_resp = self.case_service.to_case_response(existing)
            run_resp = self._to_pipeline_run_response(latest_run) if latest_run else PipelineRunResponse(
                run_id=f"RUN-IDEMP-{existing.case_id[:8]}",
                case_id=existing.case_id,
                status="COMPLETED",
                requested_by=investigator.investigator_id,
                current_stage="PRELIMINARY_REPORT",
                started_at=existing.created_at,
                completed_at=existing.updated_at,
            )
            report_resp = self._to_case_report_response(latest_report) if latest_report else None

            return AutoRegisterCaseResponse(
                case=case_resp,
                fir_evidence_id=fir_id,
                pipeline_run=run_resp,
                preliminary_report=report_resp,
                incident_type=incident_type,
                message="Idempotent registration: returned existing case and latest investigation dossier.",
            )

        # Title derivation: use provided override or candidate suggested title
        final_title = title_override or candidate.suggested_title or f"{incident_type.replace('_', ' ').title()}: {fir_number}"

        # Step 2: Authoritative Case Registration
        assigned_io = assigned_io_override or investigator.investigator_id
        case_resp = self.case_service.create_case(
            payload=CaseCreateRequest(
                title=final_title,
                fir_metadata=FIRMetadata(**fir_metadata_dict),
                assigned_io_id=assigned_io,
            ),
            investigator=investigator,
        )

        case_id = case_resp.case_id

        # Step 3: Initialize Pipeline Run Tracking
        run_id = f"RUN-{case_id.split('-')[-1]}-{uuid.uuid4().hex[:6].upper()}"
        pipeline_run = PipelineRun(
            run_id=run_id,
            case_id=case_id,
            status=PipelineRunStatus.RUNNING.value,
            requested_by=investigator.investigator_id,
            current_stage=PipelineStageName.CASE_INTAKE.value,
            started_at=started_at,
        )
        self.pipeline_repo.create_pipeline_run(pipeline_run)

        # Stage 1 Record: Case Intake
        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.CASE_INTAKE.value,
            status="COMPLETED",
            started_at=started_at,
            output_ref={
                "case_id": case_id,
                "fir_number": fir_number,
                "incident_type": incident_type,
                "title": final_title,
            },
        )

        # Prepare FIR bytes for evidence ingestion
        fir_bytes = file_payload
        if not fir_bytes:
            fir_bytes = raw_text.encode("utf-8")

        # Step 4: Advance Case to EVIDENCE_INGESTION and run Security Pipeline
        self.case_service.update_stage(case_id, "EVIDENCE_INGESTION", investigator)
        sec_stage_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.EVIDENCE_SECURITY.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)

        if fir_bytes.startswith(b"%PDF-"):
            mime_type = "application/pdf"
            cat = EvidenceCategory.DOCUMENT_PDF
            if not filename.lower().endswith(".pdf"):
                filename += ".pdf"
        else:
            mime_type = "text/plain"
            cat = EvidenceCategory.OTHER
            if filename.lower().endswith(".pdf"):
                filename = filename[:-4] + ".txt"

        evidence_meta = EvidenceIntakeMetadata(
            evidence_category=cat,
            declared_mime_type=mime_type,
            description="Preserved First Information Report (FIR) ingested during automatic registration",
        )

        sec_result = self.evidence_orchestrator.execute_new_evidence(
            case_id=case_id,
            file_payload=fir_bytes,
            original_filename=filename,
            metadata=evidence_meta,
            investigator=investigator,
        )

        # Check for security failures
        sec_status = "COMPLETED"
        is_blocked = False
        error_details = None
        if sec_result.overall_status != PipelineExecutionStatus.SUCCESS:
            sec_status = "BLOCKED" if sec_result.overall_status == PipelineExecutionStatus.ANTIVIRUS_QUARANTINED else "FAILED"
            is_blocked = True
            error_details = {"reason": sec_result.message, "status": sec_result.overall_status.value}

        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.EVIDENCE_SECURITY.value,
            status=sec_status,
            started_at=sec_stage_start,
            output_ref={
                "evidence_id": sec_result.evidence_id,
                "overall_status": sec_result.overall_status.value,
                "worm_reference": sec_result.worm_storage_reference,
                "lock_reference": sec_result.lock_storage_reference,
            },
            error_details=error_details,
        )

        if is_blocked:
            pipeline_run.status = PipelineRunStatus.BLOCKED.value
            pipeline_run.error_summary = f"Security gate blocked pipeline: {sec_result.message}"
            pipeline_run.completed_at = get_utc_now()
            self.pipeline_repo.update_pipeline_run(pipeline_run)
            return AutoRegisterCaseResponse(
                case=case_resp,
                fir_evidence_id=sec_result.evidence_id or "PENDING",
                pipeline_run=self._to_pipeline_run_response(pipeline_run),
                preliminary_report=None,
                incident_type=incident_type,
                message=f"Case registered, but evidence processing was blocked by security policy: {sec_result.message}",
            )

        fir_evidence_id = sec_result.evidence_id

        # Step 5: Advance Case to EVIDENCE_PROCESSING and run Document Processing + Indexing
        self.case_service.update_stage(case_id, "EVIDENCE_PROCESSING", investigator)
        doc_stage_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.DOCUMENT_PROCESSING.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)

        # Document Processing stage
        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.DOCUMENT_PROCESSING.value,
            status="COMPLETED",
            started_at=doc_stage_start,
            output_ref={
                "evidence_id": fir_evidence_id,
                "document_id": sec_result.document_id,
                "text_length": len(raw_text),
            },
        )

        # Evidence Indexing stage (Phase 4 RAG)
        idx_stage_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.EVIDENCE_INDEXING.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)
        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.EVIDENCE_INDEXING.value,
            status="COMPLETED",
            started_at=idx_stage_start,
            output_ref={
                "indexing_status": sec_result.rag_indexing_status or "INDEXED",
                "document_id": sec_result.document_id,
            },
        )

        # Step 6: Fact and Entity Extraction (Phase 5)
        fact_stage_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.FACT_EXTRACTION.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)
        facts_resp = self.extraction_service.extract_facts_from_evidence(
            case_id=case_id,
            evidence_id=fir_evidence_id,
            investigator=investigator,
        )
        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.FACT_EXTRACTION.value,
            status="COMPLETED",
            started_at=fact_stage_start,
            output_ref={
                "total_facts": getattr(facts_resp, "total_facts", 0),
                "review_required": len(getattr(facts_resp, "missing_fields", [])) > 0,
            },
        )

        # Step 7: Advance Case to ANALYSIS and build Graph, Timeline, Comparisons
        self.case_service.update_stage(case_id, "ANALYSIS", investigator)

        # 7A: Entity Graph
        graph_stage_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.ENTITY_GRAPH.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)
        graph = self.extraction_service.get_case_knowledge_graph(case_id, investigator)
        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.ENTITY_GRAPH.value,
            status="COMPLETED",
            started_at=graph_stage_start,
            output_ref={"node_count": len(graph.nodes), "edge_count": len(graph.edges)},
        )

        # 7B: Timeline Construction
        tl_stage_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.TIMELINE_CONSTRUCTION.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)
        timeline = self.extraction_service.get_case_timeline_events(case_id, investigator)
        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.TIMELINE_CONSTRUCTION.value,
            status="COMPLETED",
            started_at=tl_stage_start,
            output_ref={"event_count": len(timeline.events)},
        )

        # 7C: Statement Comparison & Gap Analysis
        cmp_stage_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.STATEMENT_COMPARISON.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)
        comparisons = self.intelligence_service.get_source_comparisons(case_id, investigator)
        followups = self.intelligence_service.get_investigation_followups(case_id, investigator)
        analysis_summary = self.extraction_service.get_case_analysis_summary(case_id, investigator)
        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.STATEMENT_COMPARISON.value,
            status="COMPLETED",
            started_at=cmp_stage_start,
            output_ref={
                "contradictions_count": len(analysis_summary.contradictions),
                "investigation_gaps_count": len(analysis_summary.investigation_gaps),
            },
        )

        # Step 8: Preliminary Investigation Report Generation (Phase 8)
        rep_stage_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.PRELIMINARY_REPORT.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)

        case_entity = self.case_repo.get_by_case_id(case_id)
        preliminary_report = self._generate_and_persist_report(
            case=case_entity,
            pipeline_run_id=run_id,
            incident_type=incident_type,
            facts_resp=facts_resp,
            timeline=timeline,
            graph=graph,
            analysis_summary=analysis_summary,
            candidate=candidate,
            investigator=investigator,
        )
        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.PRELIMINARY_REPORT.value,
            status="COMPLETED",
            started_at=rep_stage_start,
            output_ref={"report_id": preliminary_report.report_id, "version": preliminary_report.version},
        )

        # Step 9: Investigator Review Queue (Phase 9 - Exception Based)
        rev_stage_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.INVESTIGATOR_REVIEW.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)

        # Check for meaningful ambiguities or gaps
        has_warnings = False
        warning_notes = []
        if candidate.missing_fields:
            has_warnings = True
            warning_notes.append(f"Missing FIR fields: {', '.join(candidate.missing_fields)}")
        if incident_type == "NEEDS_REVIEW":
            has_warnings = True
            warning_notes.append("Incident classification requires review.")

        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.INVESTIGATOR_REVIEW.value,
            status="NEEDS_REVIEW" if has_warnings else "COMPLETED",
            started_at=rev_stage_start,
            output_ref={"warning_notes": warning_notes},
        )

        # Finalize Pipeline Run
        pipeline_run.status = (
            PipelineRunStatus.COMPLETED_WITH_WARNINGS.value if has_warnings else PipelineRunStatus.COMPLETED.value
        )
        pipeline_run.completed_at = get_utc_now()
        pipeline_run.stage_summary = {
            "fir_number": fir_number,
            "incident_type": incident_type,
            "fir_evidence_id": fir_evidence_id,
            "report_id": preliminary_report.report_id,
            "timeline_events_count": len(timeline.events),
            "graph_nodes_count": len(graph.nodes),
            "warnings": warning_notes,
        }
        self.pipeline_repo.update_pipeline_run(pipeline_run)

        # Refresh case response
        refreshed_case = self.case_service.to_case_response(case_entity)

        return AutoRegisterCaseResponse(
            case=refreshed_case,
            fir_evidence_id=fir_evidence_id,
            pipeline_run=self._to_pipeline_run_response(pipeline_run),
            preliminary_report=self._to_case_report_response(preliminary_report),
            incident_type=incident_type,
            message="Case registered and automated investigation pipeline completed successfully.",
        )

    def run_case_investigation_pipeline(
        self,
        case_id: str,
        investigator: AuthenticatedInvestigator,
    ) -> PipelineRunResponse:
        """Execute or refresh the investigation pipeline for all exhibits in an existing case."""
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)
        self.case_service.authz.check_can_modify_case(investigator, case)

        started_at = get_utc_now()
        run_id = f"RUN-{case_id.split('-')[-1]}-{uuid.uuid4().hex[:6].upper()}"
        pipeline_run = PipelineRun(
            run_id=run_id,
            case_id=case_id,
            status=PipelineRunStatus.RUNNING.value,
            requested_by=investigator.investigator_id,
            current_stage=PipelineStageName.EVIDENCE_SECURITY.value,
            started_at=started_at,
        )
        self.pipeline_repo.create_pipeline_run(pipeline_run)

        exhibits = self.evidence_repo.list_by_case_id(case_id)
        fir_meta = case.fir_metadata if isinstance(case.fir_metadata, dict) else {}
        incident_type = fir_meta.get("incident_type") or "DEATH_INVESTIGATION"

        # Step 1: Ensure all exhibits have completed security and indexing
        sec_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.EVIDENCE_SECURITY.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)
        for ev in exhibits:
            if ev.status != "COMMITTED" or ev.lock_status != "LOCKED":
                try:
                    self.evidence_orchestrator.resume_existing_evidence(case_id, ev.evidence_id, investigator)
                except Exception as e:
                    logger.warning("Could not auto-resume evidence %s: %s", ev.evidence_id, e)
        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.EVIDENCE_SECURITY.value,
            status="COMPLETED",
            started_at=sec_start,
            output_ref={"exhibits_verified": len(exhibits)},
        )

        # Step 2: Extract facts from all exhibits
        fact_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.FACT_EXTRACTION.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)
        for ev in exhibits:
            try:
                self.extraction_service.extract_facts_from_evidence(case_id, ev.evidence_id, investigator)
            except Exception as e:
                logger.warning("Fact extraction skipped for %s: %s", ev.evidence_id, e)
        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.FACT_EXTRACTION.value,
            status="COMPLETED",
            started_at=fact_start,
            output_ref={"exhibits_processed": len(exhibits)},
        )

        # Step 3: Refresh graph, timeline, comparisons
        graph_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.ENTITY_GRAPH.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)
        graph = self.extraction_service.get_case_knowledge_graph(case_id, investigator)
        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.ENTITY_GRAPH.value,
            status="COMPLETED",
            started_at=graph_start,
            output_ref={"nodes": len(graph.nodes), "edges": len(graph.edges)},
        )

        tl_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.TIMELINE_CONSTRUCTION.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)
        timeline = self.extraction_service.get_case_timeline_events(case_id, investigator)
        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.TIMELINE_CONSTRUCTION.value,
            status="COMPLETED",
            started_at=tl_start,
            output_ref={"events": len(timeline.events)},
        )

        cmp_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.STATEMENT_COMPARISON.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)
        analysis_summary = self.extraction_service.get_case_analysis_summary(case_id, investigator)
        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.STATEMENT_COMPARISON.value,
            status="COMPLETED",
            started_at=cmp_start,
            output_ref={"contradictions": len(analysis_summary.contradictions), "gaps": len(analysis_summary.investigation_gaps)},
        )

        # Step 4: Generate new version of Case Report
        rep_start = get_utc_now()
        pipeline_run.current_stage = PipelineStageName.PRELIMINARY_REPORT.value
        self.pipeline_repo.update_pipeline_run(pipeline_run)
        report = self._generate_and_persist_report(
            case=case,
            pipeline_run_id=run_id,
            incident_type=incident_type,
            facts_resp=None,
            timeline=timeline,
            graph=graph,
            analysis_summary=analysis_summary,
            candidate=None,
            investigator=investigator,
        )
        self._record_stage_run(
            run_id=run_id,
            case_id=case_id,
            stage_name=PipelineStageName.PRELIMINARY_REPORT.value,
            status="COMPLETED",
            started_at=rep_start,
            output_ref={"report_id": report.report_id},
        )

        pipeline_run.status = PipelineRunStatus.COMPLETED.value
        pipeline_run.current_stage = PipelineStageName.PRELIMINARY_REPORT.value
        pipeline_run.completed_at = get_utc_now()
        self.pipeline_repo.update_pipeline_run(pipeline_run)

        return self._to_pipeline_run_response(pipeline_run)

    def get_latest_pipeline_status(self, case_id: str, investigator: AuthenticatedInvestigator) -> Optional[PipelineRunResponse]:
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)
        self.case_service.authz.check_can_read_case(investigator, case)

        latest_run = self.pipeline_repo.get_latest_run_for_case(case_id)
        if not latest_run:
            return None
        return self._to_pipeline_run_response(latest_run)

    def get_case_report(self, case_id: str, investigator: AuthenticatedInvestigator) -> Optional[CaseReportResponse]:
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)
        self.case_service.authz.check_can_read_case(investigator, case)

        latest_report = self.pipeline_repo.get_latest_case_report(case_id)
        if not latest_report:
            # Dynamically synthesize if no report has been persisted yet
            fir_meta = case.fir_metadata if isinstance(case.fir_metadata, dict) else {}
            incident_type = fir_meta.get("incident_type") or "DEATH_INVESTIGATION"
            graph = self.extraction_service.get_case_knowledge_graph(case_id, investigator)
            timeline = self.extraction_service.get_case_timeline_events(case_id, investigator)
            analysis_summary = self.extraction_service.get_case_analysis_summary(case_id, investigator)

            latest_report = self._generate_and_persist_report(
                case=case,
                pipeline_run_id=None,
                incident_type=incident_type,
                facts_resp=None,
                timeline=timeline,
                graph=graph,
                analysis_summary=analysis_summary,
                candidate=None,
                investigator=investigator,
            )

        return self._to_case_report_response(latest_report)

    # ─────────────────────────────────────────────────────────────────────────
    # Private Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _resolve_raw_text(
        self,
        file_payload: Optional[bytes],
        original_filename: Optional[str],
        fir_text: Optional[str],
    ) -> tuple[str, str]:
        if file_payload:
            fn = original_filename or "FIR_document.pdf"
            if fn.lower().endswith(".pdf") or file_payload.startswith(b"%PDF-"):
                try:
                    reader = pypdf.PdfReader(io.BytesIO(file_payload))
                    pages_text = [page.extract_text() or "" for page in reader.pages]
                    return "\n".join(pages_text).strip(), fn
                except Exception:
                    return file_payload.decode("utf-8", errors="replace"), fn
            return file_payload.decode("utf-8", errors="replace"), fn
        elif fir_text:
            return fir_text.strip(), original_filename or "FIR_pasted_text.txt"
        return "", "unknown.txt"

    def _record_stage_run(
        self,
        run_id: str,
        case_id: str,
        stage_name: str,
        status: str,
        started_at: datetime,
        output_ref: Optional[Dict[str, Any]] = None,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> PipelineStageRun:
        stage_run = PipelineStageRun(
            stage_run_id=f"STG-{uuid.uuid4().hex[:8].upper()}",
            run_id=run_id,
            case_id=case_id,
            stage_name=stage_name,
            status=status,
            output_ref=output_ref,
            error_details=error_details,
            started_at=started_at,
            completed_at=get_utc_now(),
        )
        return self.pipeline_repo.create_stage_run(stage_run)

    def _generate_and_persist_report(
        self,
        case: Case,
        pipeline_run_id: Optional[str],
        incident_type: str,
        facts_resp: Any,
        timeline: Any,
        graph: Any,
        analysis_summary: Any,
        candidate: Any,
        investigator: AuthenticatedInvestigator,
    ) -> CaseReport:
        """Synthesize and persist a traceable preliminary investigation report."""
        fir_meta = case.fir_metadata if isinstance(case.fir_metadata, dict) else {}
        exhibits = self.evidence_repo.list_by_case_id(case.case_id)

        # Determine version
        existing_reports = self.pipeline_repo.list_case_reports(case.case_id)
        version_num = len(existing_reports) + 1
        version_str = f"v{version_num}.0"

        # Build Structured Sections
        sections: List[Dict[str, Any]] = []

        # Section 1: Case Particulars & Classification
        particulars_items = [
            {"label": "Case Identifier", "value": case.case_id},
            {"label": "Incident Title", "value": case.title},
            {"label": "FIR / Reference Number", "value": fir_meta.get("fir_number", "Not recorded")},
            {"label": "Police Station / Jurisdiction", "value": fir_meta.get("police_station", "Not recorded")},
            {"label": "Incident Category", "value": incident_type.replace("_", " ").title()},
            {"label": "Report Registration Date", "value": fir_meta.get("report_date", "Not recorded")},
            {"label": "Scene / Incident Location", "value": fir_meta.get("incident_location", "Not recorded")},
            {"label": "Reporting Complainant / Informant", "value": fir_meta.get("complainant_name", "Not recorded")},
            {"label": "Assigned Investigating Officer", "value": case.assigned_io_id},
        ]
        if incident_type == "PROPERTY_LOSS":
            particulars_items.append({"label": "Stolen / Affected Property", "value": fir_meta.get("property_items", "Not recorded")})
            particulars_items.append({"label": "Last Confirmed Present", "value": fir_meta.get("last_confirmed_present", "Not recorded")})
            particulars_items.append({"label": "Discovery Observation Time", "value": fir_meta.get("discovery_time", "Not recorded")})
        else:
            particulars_items.append({"label": "Victim / Deceased Subject", "value": fir_meta.get("victim_name", "Not recorded")})
            particulars_items.append({"label": "Discovery Time", "value": fir_meta.get("discovery_time", "Not recorded")})

        sections.append({
            "section_number": 1,
            "title": "Case Particulars & Classification Context",
            "content_text": (
                f"Official preliminary investigation dossier established under Case ID {case.case_id}. "
                f"Incident classified as {incident_type.replace('_', ' ').title()} pursuant to primary FIR filing."
            ),
            "items": particulars_items,
            "citations": [{"source": fir_meta.get("fir_number", "FIR"), "type": "FIR_METADATA"}],
        })

        # Section 2: Executive Case Summary
        exec_summary = (
            f"Preliminary automated investigation dossier for {case.title}. "
            f"Official inquiry instituted at {fir_meta.get('police_station', 'Jurisdiction Station')} on "
            f"{fir_meta.get('report_date', 'Report Date')}. "
            f"Total evidence exhibits catalogued in custody: {len(exhibits)}."
        )
        sections.append({
            "section_number": 2,
            "title": "Executive Case Summary",
            "content_text": exec_summary,
            "items": [],
            "citations": [],
        })

        # Section 3: Evidence Register & Custody Integrity
        ev_items = [
            {
                "evidence_id": ev.evidence_id,
                "filename": ev.original_file_name,
                "category": ev.evidence_category,
                "source": ev.source_device_or_person or ev.collection_location or "Station Custody",
                "sha256": ev.checksum_sha256 or "PENDING",
                "sha3_512": ev.checksum_sha3_512 or "PENDING",
                "integrity": ev.integrity_status or "UNVERIFIED",
                "lock_status": ev.lock_status or "UNLOCKED",
            }
            for ev in exhibits
        ]
        sections.append({
            "section_number": 3,
            "title": "Evidence Register & Cryptographic Integrity",
            "content_text": (
                f"All {len(exhibits)} exhibits registered under WORM object lock and dual-hashing "
                f"(SHA-256 + SHA3-512) to ensure tamper-evident chain of custody."
            ),
            "items": ev_items,
            "citations": [{"evidence_id": ev.evidence_id, "source": ev.original_file_name} for ev in exhibits],
        })

        # Section 4: Chronological Event Reconstruction
        timeline_events = getattr(timeline, "events", []) if timeline else []
        tl_items = [
            {
                "event_id": getattr(e, "event_id", f"EVT-{idx:02d}"),
                "datetime": f"{getattr(e, 'date', '')} {getattr(e, 'time', '')}".strip(),
                "title": getattr(e, "title", "Event"),
                "certainty": getattr(e, "time_certainty", "Reported Estimate"),
                "source": getattr(e, "source_name", "FIR"),
            }
            for idx, e in enumerate(timeline_events, 1)
        ]
        sections.append({
            "section_number": 4,
            "title": "Chronological Event Reconstruction",
            "content_text": (
                "Chronological reconstruction separates exact timestamped records from human witness estimates. "
                "No temporal certainty is fabricated."
            ),
            "items": tl_items,
            "citations": [{"event": item["title"], "source": item["source"]} for item in tl_items],
        })

        # Section 5: Established Entity Relationships & Graph
        edges = getattr(graph, "edges", []) if graph else []
        edge_items = [
            {
                "edge_id": getattr(ed, "id", f"EDG-{idx:02d}"),
                "source": getattr(ed, "source_node_id", "A"),
                "target": getattr(ed, "target_node_id", "B"),
                "relation": getattr(ed, "label", getattr(ed, "relation_type", "Associated")),
                "source_file": getattr(ed, "source_filename", "Evidence"),
                "review_status": getattr(ed, "review_status", "SOURCE_SUPPORTED"),
            }
            for idx, ed in enumerate(edges, 1)
        ]
        sections.append({
            "section_number": 5,
            "title": "Entity Knowledge Graph & Procedural Associations",
            "content_text": "Entity associations are derived strictly from documented exhibit passages. Associations do not imply culpability.",
            "items": edge_items,
            "citations": [{"relation": ed["relation"], "source": ed["source_file"]} for ed in edge_items],
        })

        # Section 6: Candidate Alternative Scenarios (Hypotheses)
        scenarios = getattr(analysis_summary, "candidate_scenarios", []) if analysis_summary else []
        scenario_items = [
            {
                "scenario_id": getattr(sc, "scenario_id", f"SCN-{idx:02d}"),
                "title": getattr(sc, "title", "Hypothesis"),
                "description": getattr(sc, "plain_language_description", ""),
                "disclaimer": getattr(sc, "hypothesis_disclaimer", "Candidate Investigative Hypothesis — Not Established Fact"),
                "distinguishing_evidence_needed": getattr(sc, "distinguishing_evidence_needed", "Pending laboratory/technical records"),
            }
            for idx, sc in enumerate(scenarios, 1)
        ]
        sections.append({
            "section_number": 6,
            "title": "Candidate Alternative Scenarios (Investigative Hypotheses)",
            "content_text": "Hypotheses are presented without bias or ranking to guide balanced inquiry. They are not conclusions of guilt.",
            "items": scenario_items,
            "citations": [],
        })

        # Section 7: Statement Comparisons & Contradictions
        contradictions = getattr(analysis_summary, "contradictions", []) if analysis_summary else []
        contra_items = [
            {
                "title": getattr(c, "title", "Observation Difference"),
                "summary": getattr(c, "difference_summary", ""),
                "source_a": getattr(c, "source_a_filename", "Source A"),
                "source_b": getattr(c, "source_b_filename", "Source B"),
            }
            for c in contradictions
        ]
        sections.append({
            "section_number": 7,
            "title": "Cross-Source Statement Comparisons & Contradictions",
            "content_text": (
                f"{len(contra_items)} potential contradiction(s) identified across multi-exhibit testimony. "
                "Different perspectives are not presumed dishonest without corroborating physical telemetry."
            ),
            "items": contra_items,
            "citations": [{"source_a": ci["source_a"], "source_b": ci["source_b"]} for ci in contra_items],
        })

        # Section 8: Investigation Gaps & Unanswered Questions
        gaps = getattr(analysis_summary, "investigation_gaps", []) if analysis_summary else []
        gap_items = [
            {
                "gap_id": g.get("gap_id", f"GAP-{idx:02d}"),
                "priority": g.get("priority", "MEDIUM"),
                "missing": g.get("missing", g.get("title", "Missing item")),
                "why_it_matters": g.get("why_it_matters", ""),
                "potential_custodian": g.get("potential_custodian", "Investigating Agency"),
                "recommended_action": g.get("recommended_action", "Requisition record"),
            }
            for idx, g in enumerate(gaps, 1)
        ]
        sections.append({
            "section_number": 8,
            "title": "Investigation Gaps & Recommended Follow-up Requisitions",
            "content_text": "Identified procedural and evidentiary gaps required to complete comprehensive inquiry.",
            "items": gap_items,
            "citations": [],
        })

        # Section 9: Limitations & Provenance Appendix
        limitations = [
            "This preliminary report is generated automatically from initial FIR intake and recorded exhibits.",
            "Unverified witness statements are treated as reported allegations, not judicial proof.",
            "Time estimates are bounded by recorded observer variance.",
        ]
        if incident_type == "PROPERTY_LOSS":
            limitations.append("Death investigation medical protocols are excluded as inapplicable to property loss.")
        else:
            limitations.append("Definitive cause and physiological time of death remain subject to final forensic medical examination.")

        sections.append({
            "section_number": 9,
            "title": "Evidentiary Limitations & Provenance Appendix",
            "content_text": "Notice of evidentiary boundaries and analytical scope.",
            "items": [{"limitation": lim} for lim in limitations],
            "citations": [],
        })

        # Build and persist report
        report_id = f"REP-{case.case_id.split('-')[-1]}-{uuid.uuid4().hex[:6].upper()}"
        report = CaseReport(
            report_id=report_id,
            case_id=case.case_id,
            pipeline_run_id=pipeline_run_id,
            version=version_str,
            status="PRELIMINARY",
            title=f"Preliminary Investigation Dossier: {case.title}",
            incident_type=incident_type,
            executive_summary=exec_summary,
            content={"sections": sections},
            citation_mappings=[{"section": s["title"], "citations": s["citations"]} for s in sections if s["citations"]],
            limitations=limitations,
            unresolved_questions=[g["missing"] for g in gap_items],
            approval_status="PENDING_REVIEW",
        )
        return self.pipeline_repo.create_case_report(report)

    def _to_pipeline_run_response(self, run: PipelineRun) -> PipelineRunResponse:
        stage_runs = self.pipeline_repo.get_stage_runs(run.run_id)
        return PipelineRunResponse(
            run_id=run.run_id,
            case_id=run.case_id,
            status=run.status,
            requested_by=run.requested_by,
            current_stage=run.current_stage,
            started_at=run.started_at,
            completed_at=run.completed_at,
            stage_runs=[
                PipelineStageRunResponse(
                    stage_run_id=sr.stage_run_id,
                    run_id=sr.run_id,
                    stage_name=sr.stage_name,
                    status=sr.status,
                    attempt_count=sr.attempt_count,
                    started_at=sr.started_at,
                    completed_at=sr.completed_at,
                    error_code=sr.error_code,
                    error_details=sr.error_details,
                    output_ref=sr.output_ref,
                )
                for sr in stage_runs
            ],
            error_summary=run.error_summary,
            stage_summary=run.stage_summary,
        )

    def _to_case_report_response(self, report: CaseReport) -> CaseReportResponse:
        content_dict = report.content if isinstance(report.content, dict) else {}
        raw_sections = content_dict.get("sections", [])
        sections = [
            CaseReportSection(
                section_number=s.get("section_number", idx),
                title=s.get("title", f"Section {idx}"),
                content_text=s.get("content_text", ""),
                items=s.get("items", []),
                citations=s.get("citations", []),
            )
            for idx, s in enumerate(raw_sections, 1)
        ]
        return CaseReportResponse(
            report_id=report.report_id,
            case_id=report.case_id,
            pipeline_run_id=report.pipeline_run_id,
            version=report.version,
            status=report.status,
            title=report.title,
            incident_type=report.incident_type,
            executive_summary=report.executive_summary,
            sections=sections,
            citation_mappings=report.citation_mappings or [],
            limitations=report.limitations or [],
            unresolved_questions=report.unresolved_questions or [],
            approval_status=report.approval_status,
            approved_by=report.approved_by,
            approved_at=report.approved_at,
            review_notes=report.review_notes,
            generated_at=report.generated_at,
        )
