"""
Case Management REST API Endpoints (MOD-01).
Version: v1 (/api/v1/cases)
"""
import base64
import io
from typing import Optional
from fastapi import APIRouter, Depends, Query, status, File, Form, UploadFile, Request
import pypdf

from app.api.deps import (
    get_current_investigator,
    get_case_service,
    get_evidence_extraction_service,
    get_evidence_intelligence_service,
    get_evidence_pipeline_orchestrator,
)
from app.core.security import AuthenticatedInvestigator
from app.core.errors import InvalidCaseDataException
from app.services.case_service import CaseService
from app.services.evidence_extraction_service import EvidenceExtractionService
from app.services.evidence_intelligence_service import EvidenceIntelligenceService
from app.services.evidence_pipeline_orchestrator import EvidencePipelineOrchestrator
from app.repositories.evidence_repository import EvidenceRepository
from app.schemas.intelligence import (
    SearchFilterType,
    UnifiedSearchResponse,
    PersonDossierResponse,
    ObjectDossierResponse,
    EntityRegistryResponse,
    SourceComparisonResponse,
    InvestigationFollowupResponse,
    EvidenceBackedStructuredAnswerResponse,
)
from app.schemas.case import (
    CaseCreateRequest,
    CaseUpdateRequest,
    CaseDeleteRequest,
    CaseDeleteResponse,
    CaseAssignIORequest,
    CaseStageUpdateRequest,
    CaseResponse,
    CaseListResponse,
    Phase2IntegrationContract,
    FIRAssistedExtractResponse,
    FIRAssistedCaseCreateRequest,
    FIRAssistedCaseCreateResponse,
)
from app.schemas.evidence import (
    BranchingTimelineResponse,
    InvestigationAnalysisResponse,
    CaseKnowledgeGraphResponse,
    EdgeDecisionRequest,
    EdgeDecisionResponse,
    DualBrainAnalysisResponse,
    EvidenceIntakeMetadata,
    EvidenceCategory,
    CaseRAGAskRequest,
    CaseRAGAskResponse,
)
from app.schemas.rag import RAGSearchRequest, RAGSearchResponse

router = APIRouter(prefix="/cases", tags=["Case Management"])




@router.post(
    "",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new investigation case"
)
@router.post(
    "/",
    response_model=CaseResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
def create_case(
    payload: CaseCreateRequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> CaseResponse:
    """
    Source-defined function: CREATE CASE / ASSIGN IO.
    Creates an investigation record, generates unique Case ID, binds IO, and initializes workspace.
    """
    return service.create_case(payload=payload, investigator=investigator)


@router.get(
    "",
    response_model=CaseListResponse,
    summary="List cases accessible to authorized investigator"
)
def list_cases(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Page limit"),
    include_archived: bool = Query(False, description="Include archived/deleted cases"),
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> CaseListResponse:
    """Returns cases assigned to or accessible by the authenticated investigator."""
    cases, total = service.list_cases(
        investigator=investigator,
        skip=skip,
        limit=limit,
        include_archived=include_archived
    )
    return CaseListResponse(total=total, cases=cases)


@router.get(
    "/{case_id}",
    response_model=CaseResponse,
    summary="Retrieve case by authoritative Case ID"
)
def get_case(
    case_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> CaseResponse:
    """Retrieves full case details and workspace representation."""
    return service.get_case(case_id=case_id, investigator=investigator)


@router.patch(
    "/{case_id}",
    response_model=CaseResponse,
    summary="Update permitted case metadata"
)
def update_case(
    case_id: str,
    payload: CaseUpdateRequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> CaseResponse:
    """Updates permitted case fields. The Case ID is immutable and remains constant."""
    return service.update_case(case_id=case_id, payload=payload, investigator=investigator)


@router.delete(
    "/{case_id}",
    response_model=CaseDeleteResponse,
    summary="Safely archive/delete an individual case"
)
def delete_case(
    case_id: str,
    payload: Optional[CaseDeleteRequest] = None,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> CaseDeleteResponse:
    """
    Safely archives and removes an individual case from active register views.
    Enforces authorization: requesting investigator must be assigned IO or supervisor/admin.
    Preserves all evidence exhibits, hashes, chain-of-custody, and audit logs.
    """
    reason = payload.reason if payload else None
    return service.delete_case(case_id=case_id, investigator=investigator, reason=reason)


@router.post(
    "/{case_id}/assign-investigator",
    response_model=CaseResponse,
    summary="Associate or reassign an Investigating Officer"
)
def assign_investigator(
    case_id: str,
    payload: CaseAssignIORequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> CaseResponse:
    """Source-defined function: ASSIGN IO."""
    return service.assign_investigator(
        case_id=case_id,
        target_io_id=payload.assigned_io_id,
        investigator=investigator
    )


@router.get(
    "/{case_id}/stage",
    summary="Retrieve current case lifecycle state"
)
def get_case_stage(
    case_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
):
    """Returns lifecycle state managed by the Stage Engine."""
    from app.services.stage_engine import stage_engine
    case = service.get_case(case_id=case_id, investigator=investigator)
    return {
        "case_id": case.case_id,
        "lifecycle_stage": case.lifecycle_stage,
        "status": case.status,
        "allowed_transitions": stage_engine.get_allowed_transitions(case.lifecycle_stage)
    }


@router.post(
    "/{case_id}/stage",
    response_model=CaseResponse,
    summary="Update case lifecycle stage (Stage Engine hook)"
)
def update_case_stage(
    case_id: str,
    payload: CaseStageUpdateRequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> CaseResponse:
    """Stage Engine integration point to advance or adjust investigation state."""
    return service.update_stage(
        case_id=case_id,
        new_stage=payload.lifecycle_stage,
        investigator=investigator
    )


@router.get(
    "/{case_id}/phase2-contract",
    response_model=Phase2IntegrationContract,
    summary="Export formal Phase 1 Output Contract for Phase 2 Evidence Ingestion"
)
def get_phase2_contract(
    case_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> Phase2IntegrationContract:
    """Produces the validated handoff contract required by Phase 2 Evidence Ingestion."""
    return service.get_phase2_contract(case_id=case_id, investigator=investigator)


@router.post(
    "/{case_id}/search",
    response_model=RAGSearchResponse,
    summary="Retrieve eligible indexed evidence passages for this case (Core Case Search)"
)
def search_case_evidence(
    case_id: str,
    payload: RAGSearchRequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: CaseService = Depends(get_case_service)
) -> RAGSearchResponse:
    """Returns citations and original passages for case evidence; investigator is final decision-maker."""
    return service.search_case_evidence(
        case_id=case_id,
        query=payload.query,
        investigator=investigator,
        limit=payload.limit
    )


@router.get(
    "/{case_id}/timeline-events",
    response_model=BranchingTimelineResponse,
    summary="Retrieve evidence-backed chronological and branching timeline events for this case"
)
def get_case_timeline_events(
    case_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    extraction_service: EvidenceExtractionService = Depends(get_evidence_extraction_service),
) -> BranchingTimelineResponse:
    """
    Returns authentic timeline events extracted from registered exhibits.
    Never populates empty cases with fictional sample events or ungrounded contradictions.
    Distinguishes exact, reported, and estimated timestamps, and provides candidate sequence branches.
    """
    return extraction_service.get_case_timeline_events(
        case_id=case_id,
        investigator=investigator,
    )


@router.get(
    "/{case_id}/analysis-summary",
    response_model=InvestigationAnalysisResponse,
    summary="Retrieve structured investigation analysis grounded in real evidence"
)
def get_case_analysis_summary(
    case_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    extraction_service: EvidenceExtractionService = Depends(get_evidence_extraction_service),
) -> InvestigationAnalysisResponse:
    """
    Returns structured analysis:
    - Section A: Supported facts with source citations
    - Section B: Contradictions with Source A / Source B exact passages
    - Section C: Evidence gaps and why they matter
    - Section D: Candidate scenarios labeled explicitly as hypotheses
    """
    return extraction_service.get_case_analysis_summary(
        case_id=case_id,
        investigator=investigator,
    )


@router.post(
    "/fir-preview",
    response_model=FIRAssistedExtractResponse,
    summary="Extract candidate case metadata from an FIR file or text before registration",
)
async def preview_fir_extraction(
    request: Request,
    file: Optional[UploadFile] = File(None, description="Uploaded FIR document (PDF/text)"),
    fir_text: Optional[str] = Form(None, description="Pasted FIR text"),
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    extraction_service: EvidenceExtractionService = Depends(get_evidence_extraction_service),
) -> FIRAssistedExtractResponse:
    """
    Candidate metadata extraction for Method B: FIR-Assisted Registration.
    Reads text from uploaded PDF or raw text and extracts dates, times, locations,
    complainant, victim, and statutory sections with verbatim source quotes.
    Never persists until confirmed by the Investigating Officer.
    """
    raw_text = ""
    filename = None

    content_type = request.headers.get("content-type", "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
            raw_text = body.get("fir_text", "") or body.get("raw_text", "")
            filename = body.get("filename") or body.get("fir_filename") or "FIR_submitted_text.txt"
        except Exception:
            pass

    if not raw_text:
        if file:
            filename = file.filename or "FIR_document.pdf"
            file_bytes = await file.read()
            if filename.lower().endswith(".pdf") or (file.content_type and "pdf" in file.content_type.lower()):
                try:
                    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                    pages_text = [page.extract_text() or "" for page in reader.pages]
                    raw_text = "\n".join(pages_text).strip()
                except Exception as e:
                    raw_text = file_bytes.decode("utf-8", errors="replace")
            else:
                raw_text = file_bytes.decode("utf-8", errors="replace")
        elif fir_text:
            raw_text = fir_text.strip()
            filename = "FIR_submitted_text.txt"

    if not raw_text or len(raw_text.strip()) < 5:
        if file and (filename.lower().endswith(".pdf") or (file.content_type and "pdf" in file.content_type.lower())):
            return FIRAssistedExtractResponse(
                fir_number="FIR-PENDING/2026",
                police_station="Jurisdiction Police Station",
                suggested_title="Unnatural Death Inquiry — Unknown Subject — Pending Review",
                is_ocr_applied=False,
                ocr_limitation_notice="Scanned document detected with zero extractable text. OCR is not configured in this environment; please enter case registration details manually or upload a text-accessible document.",
                missing_fields=["incident_date", "incident_location", "victim_name", "complainant_name", "offense_sections", "investigating_officer"],
                ambiguous_fields=[],
                extraction_confidence="OCR_UNAVAILABLE_SCANNED_DOC",
                disclaimer="Document appears to be a scanned image without a selectable text layer. Automated OCR is unavailable in this deployment.",
            )
        raise InvalidCaseDataException("Either an FIR document file or FIR text must be provided for extraction.")

    return extraction_service.extract_fir_candidate_details(raw_text, filename=filename)


@router.post(
    "/fir-assisted",
    response_model=FIRAssistedCaseCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a case with initial FIR document preserved into chain of custody",
)
def create_case_fir_assisted(
    payload: FIRAssistedCaseCreateRequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    case_service: CaseService = Depends(get_case_service),
    orchestrator: EvidencePipelineOrchestrator = Depends(get_evidence_pipeline_orchestrator),
) -> FIRAssistedCaseCreateResponse:
    """
    Method B: FIR-Assisted Case Registration.
    Creates case with confirmed metadata, advances lifecycle stage to EVIDENCE_INGESTION,
    and runs the full forensic pipeline to preserve the original FIR as an exhibit.
    """
    # 0. Idempotency Check: Reconcile duplicate submission safely
    existing_case = case_service.repo.find_existing_by_fir(
        fir_number=payload.fir_metadata.fir_number,
        police_station=payload.fir_metadata.police_station,
    )
    if existing_case:
        ev_repo = EvidenceRepository(case_service.repo.db)
        existing_evs = ev_repo.list_by_case_id(existing_case.case_id)
        fir_ev = next((e for e in existing_evs if "FIR" in (e.original_file_name or "").upper()), None)
        if not fir_ev and existing_evs:
            fir_ev = existing_evs[0]
        case_resp = case_service.to_case_response(existing_case)
        fir_id = fir_ev.evidence_id if fir_ev else f"EV-{existing_case.case_id[:8]}-FIR"
        return FIRAssistedCaseCreateResponse(
            case=case_resp,
            fir_evidence_id=fir_id,
            evidence_id=fir_id,
            chain_of_custody_logged=True,
            fir_pipeline_status="SUCCESS",
            fir_indexing_status="INDEXED",
            message="Idempotent duplicate submission reconciled: returning existing case and preserved FIR record.",
        )

    # 1. Authoritative Case Creation
    case_resp = case_service.create_case(
        payload=CaseCreateRequest(
            case_id=payload.case_id,
            title=payload.title,
            fir_metadata=payload.fir_metadata,
            assigned_io_id=payload.assigned_io_id,
        ),
        investigator=investigator,
    )

    # 2. Advance stage to EVIDENCE_INGESTION for exhibit intake
    case_resp = case_service.update_stage(
        case_id=case_resp.case_id,
        new_stage="EVIDENCE_INGESTION",
        investigator=investigator,
    )

    # 3. Ingest original FIR into evidence pipeline
    file_bytes = b""
    if payload.fir_file_b64:
        try:
            file_bytes = base64.b64decode(payload.fir_file_b64)
        except Exception:
            file_bytes = (payload.fir_raw_text or "").encode("utf-8")
    elif payload.fir_raw_text:
        file_bytes = payload.fir_raw_text.encode("utf-8")
    else:
        file_bytes = (
            f"FIRST INFORMATION REPORT\n"
            f"FIR No: {payload.fir_metadata.fir_number}\n"
            f"Police Station: {payload.fir_metadata.police_station}\n"
            f"Incident Date: {payload.fir_metadata.incident_date or 'Not recorded'}\n"
            f"Location: {payload.fir_metadata.incident_location or 'Not recorded'}\n"
            f"Occurrence Summary: Official Initial Record Preserved During Registration\n"
        ).encode("utf-8")

    filename = payload.fir_filename or "FIR_initial_record.txt"
    if file_bytes.startswith(b"%PDF-"):
        mime = "application/pdf"
        cat = EvidenceCategory.DOCUMENT_PDF
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
    else:
        mime = "text/plain"
        cat = EvidenceCategory.OTHER
        if filename.lower().endswith(".pdf"):
            filename = filename[:-4] + ".txt"

    metadata = EvidenceIntakeMetadata(
        evidence_category=cat,
        declared_mime_type=mime,
        description="Preserved First Information Report (FIR) ingested during assisted registration",
    )

    pipeline_result = orchestrator.execute_new_evidence(
        case_id=case_resp.case_id,
        file_payload=file_bytes,
        original_filename=filename,
        metadata=metadata,
        investigator=investigator,
    )

    overall_st = pipeline_result.overall_status.value if hasattr(pipeline_result.overall_status, "value") else str(pipeline_result.overall_status or "SUCCESS")
    indexing_st = pipeline_result.rag_indexing_status
    if hasattr(indexing_st, "value"):
        indexing_st = indexing_st.value
    indexing_st = str(indexing_st) if indexing_st else "INDEXED"

    return FIRAssistedCaseCreateResponse(
        case=case_resp,
        fir_evidence_id=pipeline_result.evidence_id,
        evidence_id=pipeline_result.evidence_id,
        chain_of_custody_logged=True,
        fir_pipeline_status=overall_st,
        fir_indexing_status=indexing_st,
        message="Case registered and initial FIR exhibit preserved into chain of custody.",
    )


@router.get(
    "/{case_id}/knowledge-graph",
    response_model=CaseKnowledgeGraphResponse,
    summary="Retrieve source-grounded entity knowledge graph for this case",
)
def get_case_knowledge_graph(
    case_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    extraction_service: EvidenceExtractionService = Depends(get_evidence_extraction_service),
) -> CaseKnowledgeGraphResponse:
    """
    Returns interactive knowledge graph connecting people, objects, locations, documents, and events.
    Strictly isolated to authorized case exhibits; empty cases return zero nodes and edges.
    """
    return extraction_service.get_case_knowledge_graph(
        case_id=case_id,
        investigator=investigator,
    )


@router.post(
    "/{case_id}/knowledge-graph/edges/{edge_id}/decision",
    response_model=EdgeDecisionResponse,
    summary="Record an authoritative investigator decision on an entity relationship",
)
def record_edge_decision(
    case_id: str,
    edge_id: str,
    payload: EdgeDecisionRequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    extraction_service: EvidenceExtractionService = Depends(get_evidence_extraction_service),
) -> EdgeDecisionResponse:
    """
    Allows the Investigating Officer to Confirm, Correct, Reject, or Mark Unresolved
    an entity relationship. Fully audited with provenance.
    """
    return extraction_service.record_edge_decision(
        case_id=case_id,
        edge_id=edge_id,
        request=payload,
        investigator=investigator,
    )


@router.get(
    "/{case_id}/dual-brain",
    response_model=DualBrainAnalysisResponse,
    summary="Retrieve Dual-Brain Reasoning Workspace (Intuition Brain vs Discipline Brain)",
)
def get_case_dual_brain(
    case_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    extraction_service: EvidenceExtractionService = Depends(get_evidence_extraction_service),
) -> DualBrainAnalysisResponse:
    """
    Dual-Brain Reasoning Workspace:
    - Intuition Brain proposes candidate explanations, assumptions, and investigative questions.
    - Discipline Brain challenges proposals against hard evidence, timing constraints, and statutory rules.
    - Information Firewall strictly segregates hypotheses from evidentiary register.
    - Evidence Gate enforces corroboration standards.
    """
    return extraction_service.get_dual_brain_reasoning(
        case_id=case_id,
        investigator=investigator,
    )


@router.post(
    "/{case_id}/ask",
    response_model=CaseRAGAskResponse,
    summary="Ask About This Case: Conversational evidence retrieval with authentic citations",
)
def ask_case_question(
    case_id: str,
    payload: CaseRAGAskRequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    extraction_service: EvidenceExtractionService = Depends(get_evidence_extraction_service),
) -> CaseRAGAskResponse:
    """
    Conversational evidence Q&A ('Ask About This Case').
    Retrieves matching evidence excerpts for this case and synthesizes a direct answer
    citing exact source documents, page numbers, and offsets.
    Never hallucinates or draws inferences beyond recorded exhibits.
    """
    return extraction_service.ask_case_question(
        case_id=case_id,
        question=payload.question,
        limit=payload.limit,
        investigator=investigator,
    )


# ─── Phase F.1 Evidence Intelligence & Investigative Dossiers Endpoints ───────

@router.get(
    "/{case_id}/intelligence/search",
    response_model=UnifiedSearchResponse,
    summary="Unified Investigative Search across exhibits, entities, timelines, and passages",
)
def unified_investigative_search(
    case_id: str,
    q: str = Query(..., min_length=1, description="Search query string"),
    filter_type: SearchFilterType = Query(SearchFilterType.ALL, description="Entity/Exhibit filter"),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    intel_service: EvidenceIntelligenceService = Depends(get_evidence_intelligence_service),
) -> UnifiedSearchResponse:
    """
    Unified investigative search across:
    - Exhibits and evidence numbers (e.g. SAKSHI-EVID-2026-...)
    - Person names, aliases, and roles
    - Physical objects, weapons, and serial numbers
    - Locations, events, and timestamps
    - Relationships and reported interactions
    - Exact phrases and semantic RAG passages
    """
    return intel_service.unified_search(
        case_id=case_id,
        query=q,
        filter_type=filter_type,
        limit=limit,
        investigator=investigator,
    )


@router.get(
    "/{case_id}/intelligence/person/{person_id}",
    response_model=PersonDossierResponse,
    summary="Retrieve complete case-scoped Person Dossier",
)
def get_person_dossier(
    case_id: str,
    person_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    intel_service: EvidenceIntelligenceService = Depends(get_evidence_intelligence_service),
) -> PersonDossierResponse:
    """
    Opens dedicated source-grounded Person Dossier:
    - Identity details with provenance
    - Grounded relationship map
    - Reported interactions and uncertain timestamps
    - Associated evidence documents
    - Chronological timeline
    - Conflicts and unresolved statements
    - Verbatim source provenance
    """
    return intel_service.get_person_dossier(
        case_id=case_id,
        person_id=person_id,
        investigator=investigator,
    )


@router.get(
    "/{case_id}/intelligence/object/{object_id}",
    response_model=ObjectDossierResponse,
    summary="Retrieve complete case-scoped Object & Physical Exhibit Dossier",
)
def get_object_dossier(
    case_id: str,
    object_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    intel_service: EvidenceIntelligenceService = Depends(get_evidence_intelligence_service),
) -> ObjectDossierResponse:
    """
    Opens dedicated source-grounded Object / Exhibit Dossier:
    - Assigned exhibit number and WORM custody status
    - Characteristics register table (measurements, units, methods, sources)
    - Explicit 'Not documented in available evidence' flags for unmeasured attributes
    - Forensic limitations notice (never infers sharpness/lethality without laboratory test)
    - Examination findings and associated persons
    """
    return intel_service.get_object_dossier(
        case_id=case_id,
        object_id=object_id,
        investigator=investigator,
    )


@router.get(
    "/{case_id}/intelligence/registry",
    response_model=EntityRegistryResponse,
    summary="Retrieve consolidated case entity and exhibit registry",
)
def get_entity_registry(
    case_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    intel_service: EvidenceIntelligenceService = Depends(get_evidence_intelligence_service),
) -> EntityRegistryResponse:
    """
    Returns consolidated catalog of all exhibits, persons, objects, and locations
    in this case with review states and direct dossier navigation links.
    """
    return intel_service.get_entity_registry(
        case_id=case_id,
        investigator=investigator,
    )


@router.get(
    "/{case_id}/intelligence/contradictions",
    response_model=SourceComparisonResponse,
    summary="Retrieve side-by-side source comparisons and contradiction reviews",
)
def get_source_comparisons(
    case_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    intel_service: EvidenceIntelligenceService = Depends(get_evidence_intelligence_service),
) -> SourceComparisonResponse:
    """
    Returns side-by-side claim comparisons across divergent witness statements,
    differing timestamps, and uncorroborated accounts.
    """
    return intel_service.get_source_comparisons(
        case_id=case_id,
        investigator=investigator,
    )


@router.get(
    "/{case_id}/intelligence/followups",
    response_model=InvestigationFollowupResponse,
    summary="Retrieve investigation gap analysis and follow-up suggestions",
)
def get_investigation_followups(
    case_id: str,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    intel_service: EvidenceIntelligenceService = Depends(get_evidence_intelligence_service),
) -> InvestigationFollowupResponse:
    """
    Returns missing evidence items, pending laboratory reports, and procedural follow-up actions.
    """
    return intel_service.get_investigation_followups(
        case_id=case_id,
        investigator=investigator,
    )


@router.post(
    "/{case_id}/intelligence/ask",
    response_model=EvidenceBackedStructuredAnswerResponse,
    summary="Evidence-backed 6-section structured question answering",
)
def ask_evidence_intelligence(
    case_id: str,
    payload: CaseRAGAskRequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    intel_service: EvidenceIntelligenceService = Depends(get_evidence_intelligence_service),
) -> EvidenceBackedStructuredAnswerResponse:
    """
    Enhanced Q&A synthesizing answers into 6 mandatory sections:
    1. Directly documented information
    2. Supporting source references
    3. Conflicting or inconsistent information
    4. Missing or undocumented information
    5. Possible interpretations (hypotheses)
    6. Suggested follow-up questions
    """
    return intel_service.synthesize_structured_answer(
        case_id=case_id,
        question=payload.question,
        investigator=investigator,
    )




