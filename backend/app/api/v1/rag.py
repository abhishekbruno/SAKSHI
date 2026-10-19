"""Authenticated, case-scoped evidence retrieval API (RAG Phase 4)."""
from fastapi import APIRouter, Depends

from app.api.deps import get_current_investigator, get_rag_retrieval_service
from app.core.security import AuthenticatedInvestigator
from app.schemas.rag import RAGSearchRequest, RAGSearchResponse
from app.services.rag_retrieval_service import RAGRetrievalService

router = APIRouter(prefix="/cases/{case_id}/rag", tags=["RAG Retrieval"])


@router.post("/search", response_model=RAGSearchResponse, summary="Retrieve eligible indexed evidence passages")
def search_case_evidence(
    case_id: str,
    payload: RAGSearchRequest,
    investigator: AuthenticatedInvestigator = Depends(get_current_investigator),
    service: RAGRetrievalService = Depends(get_rag_retrieval_service),
) -> RAGSearchResponse:
    """Returns citations and original passages only; it does not generate an answer or conclusion."""
    return service.search(
        case_id=case_id,
        query=payload.query,
        limit=payload.limit,
        investigator=investigator,
    )
