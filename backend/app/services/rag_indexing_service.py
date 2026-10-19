"""
RAG Indexing Service for SAKSHI Investigation Platform.
Phase 3 — Evidence Text Extraction, Chunking, and Embedding Services.

Orchestrates the complete evidence text processing pipeline:
1. Security gate verification and authorized plaintext extraction (MOD-05 through MOD-11)
2. Passage chunking with exact page attribution and character offsets (EC-MORE)
3. 384-dimensional dense vector embedding generation (all-MiniLM-L6-v2)
4. Safe, transactional persistence into RAG ORM models (rag_documents, rag_chunks, rag_index_jobs)

Invariants:
- Safe Job State: Tracks progress via RAGIndexJob; failures never falsely mark document as INDEXED.
- Atomic Chunk Persistence: Document is only marked INDEXED if all chunks and embeddings persist successfully.
- Cryptographic Provenance: Every chunk and document is bound to authoritative exhibit dual hashes.
- No HTTP API is exposed in this phase.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.evidence import Evidence
from app.models.rag_document import RAGDocument
from app.models.rag_chunk import RAGChunk
from app.models.rag_index_job import RAGIndexJob
from app.repositories.case_repository import CaseRepository
from app.repositories.evidence_repository import EvidenceRepository
from app.repositories.rag_repository import RAGRepository
from app.core.security import AuthenticatedInvestigator
from app.core.errors import (
    CaseNotFoundException,
    EvidenceNotFoundException,
    IneligibleEvidenceException,
    TextExtractionException,
    EmbeddingGenerationException,
)
from app.services.text_extraction_service import TextExtractionService
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.audit_integration import AuditIntegrationService

logger = logging.getLogger("sakshi.rag.indexing")


def get_utc_now():
    return datetime.now(timezone.utc)


class RAGIndexingService:
    """
    Core pipeline orchestrator for indexing verified forensic evidence exhibits.
    """

    def __init__(
        self,
        db: Session,
        extraction_service: Optional[TextExtractionService] = None,
        chunking_service: Optional[ChunkingService] = None,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        self.db = db
        self.rag_repo = RAGRepository(db)
        self.case_repo = CaseRepository(db)
        self.evidence_repo = EvidenceRepository(db)
        self.extraction_service = extraction_service or TextExtractionService(db)
        self.chunking_service = chunking_service or ChunkingService()
        self.embedding_service = embedding_service or EmbeddingService()

    def index_evidence(
        self,
        case_id: str,
        evidence_id: str,
        investigator: AuthenticatedInvestigator,
        processing_version: str = "v1.0",
        force_reindex: bool = False,
    ) -> RAGDocument:
        """
        Executes end-to-end evidence indexing:
        Extraction -> Chunking -> Embedding -> Persistence.
        """
        # 1. Verify existence
        case = self.case_repo.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        evidence = self.evidence_repo.get_by_evidence_id(evidence_id)
        if not evidence or evidence.case_id != case_id:
            raise EvidenceNotFoundException(evidence_id)

        # 2. Check for existing document
        existing_doc = self.rag_repo.get_document_by_evidence_and_version(
            evidence_id=evidence_id,
            processing_version=processing_version,
        )

        if existing_doc and existing_doc.indexing_status == "INDEXED" and not force_reindex:
            logger.info("Evidence %s already indexed under version %s. Returning existing record.", evidence_id, processing_version)
            return existing_doc

        now = get_utc_now()

        # 3. Initialize or retrieve RAGDocument
        if existing_doc:
            doc = existing_doc
            doc.indexing_status = "PROCESSING"
            doc.updated_at = now
            self.rag_repo.update_document(doc)
            # If re-indexing, clean previous chunks
            if force_reindex:
                self.rag_repo.delete_chunks_by_document(doc.document_id)
        else:
            doc_id = f"SAKSHI-DOC-{evidence.evidence_id.split('-')[-1]}"
            doc = RAGDocument(
                document_id=doc_id,
                case_id=case.case_id,
                evidence_id=evidence.evidence_id,
                source_sha256=evidence.checksum_sha256 or "PENDING",
                source_sha3_512=evidence.checksum_sha3_512,
                processing_version=processing_version,
                indexing_status="PROCESSING",
                mime_type=evidence.declared_mime_type,
                created_at=now,
                updated_at=now,
            )
            doc = self.rag_repo.create_document(doc)

        # 4. Initialize RAGIndexJob
        job_token = uuid.uuid4().hex[:8].upper()
        job = RAGIndexJob(
            job_id=f"SAKSHI-JOB-{job_token}",
            document_id=doc.document_id,
            case_id=case.case_id,
            evidence_id=evidence.evidence_id,
            status="RUNNING",
            attempt_count=1,
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        job = self.rag_repo.create_index_job(job)

        # 5. Pipeline Execution with Safe Failure Handling
        try:
            # Step A: Text Extraction (Enforces MOD-05 through MOD-11 gates)
            extracted_doc = self.extraction_service.extract_text(
                case_id=case.case_id,
                evidence_id=evidence.evidence_id,
                investigator=investigator,
            )

            # Update document with extracted provenance metadata
            doc.source_sha256 = extracted_doc.source_sha256
            doc.source_sha3_512 = extracted_doc.source_sha3_512
            doc.mime_type = extracted_doc.mime_type
            doc.total_characters = extracted_doc.total_characters

            # Step B: Passage Chunking
            chunks = self.chunking_service.chunk_document(
                extracted_doc=extracted_doc,
                document_id=doc.document_id,
            )

            # Step C: Dense Vector Embedding Generation (all-MiniLM-L6-v2)
            embedded_chunks = self.embedding_service.embed_chunks(chunks)

            # Step D: Transactional Persistence
            orm_chunks: List[RAGChunk] = []
            for item in embedded_chunks:
                c = item.chunk
                orm_chunks.append(
                    RAGChunk(
                        chunk_id=c.chunk_id,
                        document_id=c.document_id,
                        case_id=c.case_id,
                        evidence_id=c.evidence_id,
                        chunk_index=c.chunk_index,
                        content=c.content,
                        page_number=c.page_number,
                        char_start=c.char_start,
                        char_end=c.char_end,
                        source_sha256=c.source_sha256,
                        source_sha3_512=c.source_sha3_512,
                        embedding_model=item.embedding_model,
                        processing_version=c.processing_version,
                        embedding=item.embedding,
                        created_at=now,
                    )
                )

            if orm_chunks:
                self.rag_repo.create_chunks(orm_chunks)

            # Step E: Complete Pipeline State
            complete_now = get_utc_now()
            doc.indexing_status = "INDEXED"
            doc.total_chunks = len(orm_chunks)
            doc.indexed_at = complete_now
            doc.updated_at = complete_now
            doc.failure_reason = None
            self.rag_repo.update_document(doc)

            job.status = "COMPLETED"
            job.completed_at = complete_now
            job.updated_at = complete_now
            job.failure_reason = None
            self.rag_repo.update_index_job(job)

            AuditIntegrationService.record_event(
                action="EVIDENCE_RAG_INDEXED",
                investigator_id=investigator.investigator_id,
                case_id=case.case_id,
                details={
                    "evidence_id": evidence.evidence_id,
                    "document_id": doc.document_id,
                    "total_chunks": len(orm_chunks),
                    "total_characters": doc.total_characters,
                    "embedding_model": self.embedding_service.model_name,
                    "dimension": self.embedding_service.dimension,
                },
            )

            logger.info(
                "Successfully indexed evidence %s into document %s (%d chunks)",
                evidence.evidence_id,
                doc.document_id,
                len(orm_chunks),
            )
            return doc

        except Exception as e:
            # Safe Failure Handling: NEVER mark as INDEXED
            fail_now = get_utc_now()
            error_code = type(e).__name__
            error_reason = str(e)

            logger.error("RAG indexing failed for evidence %s: %s: %s", evidence.evidence_id, error_code, error_reason)

            doc.indexing_status = "FAILED"
            doc.failure_reason = f"{error_code}: {error_reason}"
            doc.failed_at = fail_now
            doc.updated_at = fail_now
            self.rag_repo.update_document(doc)

            job.status = "FAILED"
            job.failure_error_code = error_code
            job.failure_reason = error_reason
            job.last_error_details = {"error_type": error_code, "message": error_reason}
            job.updated_at = fail_now
            self.rag_repo.update_index_job(job)

            AuditIntegrationService.record_event(
                action="EVIDENCE_RAG_INDEXING_FAILED",
                investigator_id=investigator.investigator_id,
                case_id=case.case_id,
                details={
                    "evidence_id": evidence.evidence_id,
                    "document_id": doc.document_id,
                    "error_type": error_code,
                    "message": error_reason,
                },
            )
            raise
