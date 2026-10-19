"""Secure, case-scoped retrieval of already indexed evidence passages (RAG Phase 4)."""
import math
from typing import List, Tuple

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import (
    ForbiddenException,
    RAGRetrievalFailedException,
    SakshiException,
    UnauthorizedException,
)
from app.core.security import AuthenticatedInvestigator
from app.repositories.case_repository import CaseRepository
from app.repositories.rag_repository import RAGRepository, RetrievalCandidate
from app.schemas.rag import (
    RAGSearchQueryMetadata,
    RAGSearchResponse,
    RAGSearchResult,
)
from app.services.audit_integration import AuditIntegrationService
from app.services.auth_service import IAuthorizationService, authorization_service
from app.services.embedding_service import EmbeddingService


class RAGRetrievalService:
    """
    Retrieves traceable passages only after case-level MOD-03 authorization.

    This service never generates an answer, conclusion, or factual assertion. It
    returns the original indexed passage and stable citation metadata only.
    """

    def __init__(
        self,
        db: Session,
        embedding_service: EmbeddingService = None,
        authz_service: IAuthorizationService = authorization_service,
    ):
        self.db = db
        self.case_repo = CaseRepository(db)
        self.rag_repo = RAGRepository(db)
        self.embedding_service = embedding_service or EmbeddingService()
        self.authz = authz_service

    def search(
        self,
        *,
        case_id: str,
        query: str,
        investigator: AuthenticatedInvestigator,
        limit: int,
    ) -> RAGSearchResponse:
        """Authorize and run a bounded search against exactly one requested case."""
        if not investigator or not investigator.is_authenticated:
            raise UnauthorizedException("Authentication is required for evidence retrieval.")

        normalized_query = query.strip()
        if not normalized_query:
            # This is normally enforced by the request schema, but retains a safe
            # service-level boundary for direct callers.
            raise ValueError("query must contain non-whitespace characters")

        # Avoid a case-existence oracle: RAG search uses the same generic denial
        # response for absent and inaccessible cases.
        case = self.case_repo.get_by_case_id(case_id)
        if case is None:
            self._audit("DENIED", investigator, case_id, reason="CASE_ACCESS_DENIED")
            raise ForbiddenException()

        try:
            # Reuse the established MOD-03 evidence-read policy (assignment,
            # jurisdiction, supervisory role, and RBAC checks).
            self.authz.check_can_read_evidence(investigator, case)
        except ForbiddenException:
            self._audit("DENIED", investigator, case_id, reason="CASE_ACCESS_DENIED")
            raise

        try:
            query_embedding = self.embedding_service.embed_text(normalized_query)
            self._validate_query_vector(query_embedding)
            candidates, retrieval_mode = self._retrieve_candidates(case_id, query_embedding, limit)
            results, excluded_invalid_vectors = self._to_results(candidates, query_embedding, limit)
        except SakshiException:
            self._audit("FAILED", investigator, case_id, reason="RETRIEVAL_DEPENDENCY_FAILURE")
            raise
        except (SQLAlchemyError, TypeError, ValueError, ArithmeticError):
            self._audit("FAILED", investigator, case_id, reason="RETRIEVAL_FAILURE")
            raise RAGRetrievalFailedException()

        self._audit(
            "SUCCESS",
            investigator,
            case_id,
            result_count=len(results),
            invalid_candidates_excluded=excluded_invalid_vectors,
            retrieval_mode=retrieval_mode,
        )
        return RAGSearchResponse(
            case_id=case_id,
            query_metadata=RAGSearchQueryMetadata(
                query_length=len(normalized_query),
                embedding_model=self.embedding_service.model_name,
                embedding_dimension=self.embedding_service.dimension,
                retrieval_mode=retrieval_mode,
            ),
            result_count=len(results),
            results=results,
            empty_result_notice=(
                "No eligible indexed passage was returned. This does not establish that no relevant evidence exists."
                if not results else None
            ),
        )

    def _retrieve_candidates(
        self, case_id: str, query_embedding: List[float], limit: int
    ) -> Tuple[List[RetrievalCandidate], str]:
        dialect = self.db.get_bind().dialect.name
        if dialect == "postgresql":
            return (
                self.rag_repo.search_eligible_chunks_postgres(case_id, query_embedding, limit),
                "postgresql_native_cosine",
            )
        if dialect == "sqlite":
            return (
                self.rag_repo.search_eligible_chunks_sqlite_candidates(case_id),
                "sqlite_bounded_development_fallback",
            )
        raise RAGRetrievalFailedException("Evidence retrieval is unavailable for this database dialect.")

    def _to_results(
        self,
        candidates: List[RetrievalCandidate],
        query_embedding: List[float],
        limit: int,
    ) -> Tuple[List[RAGSearchResult], int]:
        scored: List[Tuple[float, RetrievalCandidate]] = []
        invalid_candidates_excluded = 0
        for candidate in candidates:
            if candidate.distance is not None:
                similarity = max(-1.0, min(1.0, 1.0 - candidate.distance))
            else:
                try:
                    similarity = self._cosine_similarity(query_embedding, candidate.chunk.embedding)
                except (TypeError, ValueError, ArithmeticError):
                    # A malformed stored JSON vector is not eligible; it must not
                    # weaken or broaden the case-scoped retrieval query.
                    invalid_candidates_excluded += 1
                    continue
            scored.append((similarity, candidate))

        scored.sort(key=lambda item: (-item[0], item[1].chunk.chunk_id))
        results = [
            RAGSearchResult(
                case_id=candidate.chunk.case_id,
                evidence_id=candidate.chunk.evidence_id,
                document_id=candidate.chunk.document_id,
                chunk_id=candidate.chunk.chunk_id,
                source_name=candidate.evidence.stored_file_name,
                page_number=candidate.chunk.page_number,
                char_start=candidate.chunk.char_start,
                char_end=candidate.chunk.char_end,
                passage=candidate.chunk.content,
                similarity_score=round(similarity, 8),
                source_sha256=candidate.chunk.source_sha256,
                source_sha3_512=candidate.chunk.source_sha3_512,
                processing_version=candidate.chunk.processing_version,
                embedding_model=candidate.chunk.embedding_model,
            )
            for similarity, candidate in scored[:limit]
        ]
        return results, invalid_candidates_excluded

    def _validate_query_vector(self, vector: List[float]) -> None:
        if len(vector) != self.embedding_service.dimension:
            raise ValueError("query embedding dimension does not match the configured model")
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in vector):
            raise ValueError("query embedding contains non-finite values")

    @staticmethod
    def _cosine_similarity(left: List[float], right: List[float]) -> float:
        if not isinstance(right, (list, tuple)) or len(left) != len(right):
            raise ValueError("stored embedding is malformed")
        if not all(isinstance(value, (int, float)) and math.isfinite(value) for value in right):
            raise ValueError("stored embedding contains non-finite values")
        left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
        right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
        if left_norm == 0 or right_norm == 0:
            raise ValueError("zero-norm embedding is not eligible")
        score = sum(float(a) * float(b) for a, b in zip(left, right)) / (left_norm * right_norm)
        if not math.isfinite(score):
            raise ValueError("cosine score is non-finite")
        return max(-1.0, min(1.0, score))

    @staticmethod
    def _audit(
        outcome: str,
        investigator: AuthenticatedInvestigator,
        case_id: str,
        result_count: int = 0,
        reason: str = None,
        **safe_details,
    ) -> None:
        """Audit safe metadata only; never log the query, passages, or embeddings."""
        details = {"outcome": outcome, "result_count": result_count, **safe_details}
        if reason:
            details["error_category"] = reason
        AuditIntegrationService.record_event(
            action="RAG_RETRIEVAL",
            investigator_id=investigator.investigator_id,
            case_id=case_id,
            details=details,
        )
