"""
Repository layer for SAKSHI RAG entities.
Encapsulates database persistence and query logic for RAGDocument, RAGChunk, and RAGIndexJob.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, select

from app.models.rag_document import RAGDocument
from app.models.rag_chunk import RAGChunk
from app.models.rag_index_job import RAGIndexJob
from app.models.evidence import Evidence
from app.core.config import settings


@dataclass(frozen=True)
class RetrievalCandidate:
    """Database-backed RAG records that have passed relational eligibility checks."""
    chunk: RAGChunk
    document: RAGDocument
    evidence: Evidence
    distance: Optional[float] = None


class RAGRepository:
    def __init__(self, db: Session):
        self.db = db

    # ─── RAG Document Operations ─────────────────────────────────────────────

    def get_document_by_id(self, document_id: str) -> Optional[RAGDocument]:
        """Fetch a RAG document by its canonical document_id."""
        return self.db.query(RAGDocument).filter(RAGDocument.document_id == document_id).first()

    def get_document_by_evidence_and_version(
        self,
        evidence_id: str,
        processing_version: str = "v1.0"
    ) -> Optional[RAGDocument]:
        """Fetch a RAG document by exhibit reference and processing pipeline version."""
        return (
            self.db.query(RAGDocument)
            .filter(
                RAGDocument.evidence_id == evidence_id,
                RAGDocument.processing_version == processing_version,
            )
            .first()
        )

    def list_documents_by_case(self, case_id: str) -> List[RAGDocument]:
        """Fetch all RAG documents associated with a case."""
        return (
            self.db.query(RAGDocument)
            .filter(RAGDocument.case_id == case_id)
            .order_by(RAGDocument.created_at.desc())
            .all()
        )

    def create_document(self, document: RAGDocument) -> RAGDocument:
        """Persist a new RAG document record."""
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def update_document(self, document: RAGDocument) -> RAGDocument:
        """Persist updates to a RAG document."""
        self.db.commit()
        self.db.refresh(document)
        return document

    # ─── RAG Chunk Operations ────────────────────────────────────────────────

    def create_chunks(self, chunks: List[RAGChunk]) -> List[RAGChunk]:
        """Batch persist evidence text chunks."""
        self.db.add_all(chunks)
        self.db.commit()
        for chunk in chunks:
            self.db.refresh(chunk)
        return chunks

    def get_chunks_by_document(self, document_id: str) -> List[RAGChunk]:
        """Retrieve all ordered chunks belonging to a document."""
        return (
            self.db.query(RAGChunk)
            .filter(RAGChunk.document_id == document_id)
            .order_by(RAGChunk.chunk_index.asc())
            .all()
        )

    def count_chunks_by_document(self, document_id: str) -> int:
        """Count chunks for a document."""
        return (
            self.db.query(func.count(RAGChunk.id))
            .filter(RAGChunk.document_id == document_id)
            .scalar() or 0
        )

    def delete_chunks_by_document(self, document_id: str) -> int:
        """Purge chunks for a document (e.g. prior to re-indexing)."""
        deleted = (
            self.db.query(RAGChunk)
            .filter(RAGChunk.document_id == document_id)
            .delete(synchronize_session="fetch")
        )
        self.db.commit()
        return deleted

    # ─── Secure Retrieval Operations ───────────────────────────────────────

    @staticmethod
    def _eligible_chunk_query(case_id: str):
        """
        Build the common, case-restricted retrieval query.

        All joins redundantly bind case/evidence/document identifiers so a malformed
        RAG row can never cross the requested case boundary.  A completed *latest*
        index job is required; stale, failed, pending, or orphaned records are not
        eligible for retrieval.
        """
        latest_job_id = (
            select(RAGIndexJob.id)
            .where(
                RAGIndexJob.document_id == RAGDocument.document_id,
                RAGIndexJob.case_id == case_id,
                RAGIndexJob.evidence_id == RAGDocument.evidence_id,
            )
            .order_by(RAGIndexJob.created_at.desc(), RAGIndexJob.id.desc())
            .limit(1)
            .correlate(RAGDocument)
            .scalar_subquery()
        )

        return (
            and_(
                RAGChunk.case_id == case_id,
                RAGDocument.case_id == case_id,
                Evidence.case_id == case_id,
                RAGChunk.document_id == RAGDocument.document_id,
                RAGChunk.evidence_id == RAGDocument.evidence_id,
                RAGChunk.case_id == RAGDocument.case_id,
                RAGChunk.evidence_id == Evidence.evidence_id,
                RAGChunk.case_id == Evidence.case_id,
                RAGDocument.evidence_id == Evidence.evidence_id,
                RAGDocument.case_id == Evidence.case_id,
                RAGChunk.source_sha256 == RAGDocument.source_sha256,
                RAGDocument.source_sha256 == Evidence.checksum_sha256,
                RAGChunk.source_sha3_512.is_not(None),
                RAGDocument.source_sha3_512.is_not(None),
                Evidence.checksum_sha3_512.is_not(None),
                RAGChunk.source_sha3_512 == RAGDocument.source_sha3_512,
                RAGDocument.source_sha3_512 == Evidence.checksum_sha3_512,
                RAGDocument.indexing_status == "INDEXED",
                RAGChunk.embedding.is_not(None),
                RAGIndexJob.status == "COMPLETED",
                RAGIndexJob.case_id == case_id,
                RAGIndexJob.evidence_id == RAGDocument.evidence_id,
                RAGIndexJob.id == latest_job_id,
                Evidence.antivirus_status == "CLEAN",
                Evidence.status == "COMMITTED",
                Evidence.worm_status == "COMMITTED",
                Evidence.integrity_status == "VERIFIED",
                Evidence.lock_status == "LOCKED",
                Evidence.checksum_sha256.is_not(None),
                Evidence.encryption_status.in_(("UNENCRYPTED", "ENCRYPTED")),
            )
        )

    def search_eligible_chunks_postgres(
        self,
        case_id: str,
        query_embedding: List[float],
        limit: int,
    ) -> List[RetrievalCandidate]:
        """Use pgvector cosine distance; the case predicate remains in the SQL query."""
        cosine_distance = RAGChunk.embedding.cosine_distance(query_embedding).label("cosine_distance")
        rows = (
            self.db.query(RAGChunk, RAGDocument, Evidence, cosine_distance)
            .join(RAGDocument, RAGChunk.document_id == RAGDocument.document_id)
            .join(Evidence, RAGChunk.evidence_id == Evidence.evidence_id)
            .join(
                RAGIndexJob,
                and_(
                    RAGIndexJob.document_id == RAGDocument.document_id,
                    RAGIndexJob.evidence_id == RAGDocument.evidence_id,
                ),
            )
            .filter(self._eligible_chunk_query(case_id))
            .order_by(cosine_distance.asc(), RAGChunk.chunk_id.asc())
            .limit(limit)
            .all()
        )
        return [
            RetrievalCandidate(chunk=chunk, document=document, evidence=evidence, distance=float(distance))
            for chunk, document, evidence, distance in rows
        ]

    def search_eligible_chunks_sqlite_candidates(self, case_id: str) -> List[RetrievalCandidate]:
        """
        Return a deliberately bounded, deterministic candidate set for SQLite only.

        SQLite JSON vectors have no native vector operator. This is not a full-corpus
        vector search and must not be represented as PostgreSQL/pgvector behavior.
        """
        candidate_limit = settings.RAG_SQLITE_RETRIEVAL_CANDIDATE_LIMIT
        rows = (
            self.db.query(RAGChunk, RAGDocument, Evidence)
            .join(RAGDocument, RAGChunk.document_id == RAGDocument.document_id)
            .join(Evidence, RAGChunk.evidence_id == Evidence.evidence_id)
            .join(
                RAGIndexJob,
                and_(
                    RAGIndexJob.document_id == RAGDocument.document_id,
                    RAGIndexJob.evidence_id == RAGDocument.evidence_id,
                ),
            )
            .filter(self._eligible_chunk_query(case_id))
            .order_by(RAGChunk.created_at.desc(), RAGChunk.chunk_id.asc())
            .limit(candidate_limit)
            .all()
        )
        return [RetrievalCandidate(chunk=chunk, document=document, evidence=evidence) for chunk, document, evidence in rows]

    # ─── RAG Index Job Operations ────────────────────────────────────────────

    def create_index_job(self, job: RAGIndexJob) -> RAGIndexJob:
        """Persist a new asynchronous indexing job record."""
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def update_index_job(self, job: RAGIndexJob) -> RAGIndexJob:
        """Persist job state transitions."""
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_index_job(self, job_id: str) -> Optional[RAGIndexJob]:
        """Fetch an indexing job by canonical job_id."""
        return self.db.query(RAGIndexJob).filter(RAGIndexJob.job_id == job_id).first()

    def list_jobs_by_case(self, case_id: str) -> List[RAGIndexJob]:
        """List indexing jobs within a case boundary."""
        return (
            self.db.query(RAGIndexJob)
            .filter(RAGIndexJob.case_id == case_id)
            .order_by(RAGIndexJob.created_at.desc())
            .all()
        )
