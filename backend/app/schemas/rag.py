"""
Pydantic schemas and data transfer objects for SAKSHI RAG pipeline.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.core.config import settings


class ExtractedPage(BaseModel):
    """Represents text extracted from a discrete page of a forensic document."""
    page_number: int = Field(..., description="1-indexed page number within document")
    text: str = Field(..., description="Extracted raw text content for the page")
    char_count: int = Field(..., description="Total character count on this page")


class ExtractedDocument(BaseModel):
    """Normalized payload resulting from verified evidence text extraction."""
    case_id: str = Field(..., description="Authoritative parent Case ID")
    evidence_id: str = Field(..., description="Authoritative Evidence exhibit ID")
    source_sha256: str = Field(..., description="Source exhibit SHA-256 digest")
    source_sha3_512: Optional[str] = Field(None, description="Source exhibit SHA3-512 digest")
    mime_type: str = Field(..., description="MIME type of source document")
    extraction_method: str = Field(..., description="Extraction technique: PDF_NATIVE_TEXT | PLAINTEXT_DIRECT")
    processing_version: str = Field(default="v1.0", description="Pipeline processing version")
    pages: List[ExtractedPage] = Field(default_factory=list, description="Extracted pages")
    total_pages: int = Field(default=0, description="Total number of pages extracted")
    total_characters: int = Field(default=0, description="Total extracted text length in characters")


class DocumentChunk(BaseModel):
    """Bounded, citation-traceable text segment extracted from an evidence exhibit."""
    chunk_id: str = Field(..., description="Canonical stable chunk identifier (e.g. SAKSHI-CHK-XXXXXXXX-0000)")
    document_id: str = Field(..., description="Canonical parent RAGDocument ID")
    case_id: str = Field(..., description="Case ID for isolation boundary")
    evidence_id: str = Field(..., description="Source exhibit evidence ID")
    chunk_index: int = Field(..., description="Sequential position index within document (0-indexed)")
    content: str = Field(..., description="Forensic chunk text content")
    page_number: Optional[int] = Field(None, description="Source exhibit page number (1-indexed)")
    char_start: Optional[int] = Field(None, description="Character start offset in extracted page text")
    char_end: Optional[int] = Field(None, description="Character end offset in extracted page text")
    source_sha256: str = Field(..., description="Source exhibit SHA-256 binding")
    source_sha3_512: Optional[str] = Field(None, description="Source exhibit SHA3-512 binding")
    processing_version: str = Field(default="v1.0", description="Processing pipeline version")


class EmbeddedChunk(BaseModel):
    """Evidence chunk mapped to a validated vector embedding."""
    chunk: DocumentChunk
    embedding: List[float] = Field(..., description="Dense float vector embedding")
    embedding_model: str = Field(..., description="Embedding model identifier used for inference")


class RAGDocumentSummary(BaseModel):
    """Public metadata representation of an indexed RAG document."""
    document_id: str
    case_id: str
    evidence_id: str
    source_sha256: str
    source_sha3_512: Optional[str] = None
    processing_version: str
    indexing_status: str
    mime_type: Optional[str] = None
    total_chunks: int
    total_characters: int
    created_at: datetime
    updated_at: datetime
    indexed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None

    model_config = {"from_attributes": True}


class RAGIndexJobSummary(BaseModel):
    """Public status representation of an asynchronous RAG indexing job."""
    job_id: str
    document_id: str
    case_id: str
    evidence_id: str
    status: str
    attempt_count: int
    max_attempts: int
    failure_error_code: Optional[str] = None
    failure_reason: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─── Phase 4: case-scoped retrieval API contracts ──────────────────────────

class RAGSearchRequest(BaseModel):
    """A bounded natural-language query; it is never treated as an investigative conclusion."""
    query: str = Field(..., min_length=1, max_length=settings.RAG_SEARCH_MAX_QUERY_CHARS)
    limit: int = Field(
        default=settings.RAG_SEARCH_DEFAULT_LIMIT,
        ge=1,
        le=settings.RAG_SEARCH_MAX_LIMIT,
    )

    @field_validator("query")
    @classmethod
    def query_must_not_be_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("query must contain non-whitespace characters")
        return trimmed


class RAGSearchResult(BaseModel):
    """A traceable retrieved passage. Content remains untrusted source material."""
    case_id: str
    evidence_id: str
    document_id: str
    chunk_id: str
    source_name: str
    page_number: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    passage: str
    similarity_score: float
    source_sha256: str
    source_sha3_512: Optional[str] = None
    processing_version: str
    embedding_model: Optional[str] = None


class RAGSearchQueryMetadata(BaseModel):
    query_length: int
    embedding_model: str
    embedding_dimension: int
    retrieval_mode: str


class RAGSearchResponse(BaseModel):
    case_id: str
    query_metadata: RAGSearchQueryMetadata
    result_count: int
    results: List[RAGSearchResult] = Field(default_factory=list)
    score_semantics: str = (
        "similarity_score is cosine similarity (1.0 is most similar; -1.0 is least similar). "
        "Retrieved passages are untrusted source material, not verified fact."
    )
    empty_result_notice: Optional[str] = None
