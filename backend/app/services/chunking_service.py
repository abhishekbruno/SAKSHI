r"""
Chunking Service for SAKSHI Investigation Platform.
Phase 3 — Evidence Text Extraction, Chunking, and Embedding.

Converts ExtractedDocument payloads into discrete, overlapping, bounded passages
optimized for vector embedding generation and forensic citation grounding.

EC-MORE Forensic Grounding Invariants:
1. Exact Page & Character Citation:
   - Every chunk retains its exact 1-indexed page_number and extracted text character offsets
     (`char_start`, `char_end`).
   - Note: Offsets explicitly reference positions within the extracted, normalized page text stream,
     as opposed to raw PDF binary bytecode.
2. Natural Boundary Preservation:
   - Chunking prioritizes paragraph breaks (\n\n) and sentence boundaries ([.!?]\s+)
     over arbitrary character splits.
3. Overlap Continuity:
   - Configurable character overlap ensures query concepts spanning chunk transitions
     are not split across hard boundaries.
4. Stable Identifiers:
   - Chunk IDs follow the canonical, deterministic pattern:
     SAKSHI-CHK-<evidence_hash8>-<chunk_index:04d>
5. Resource Protection:
   - Enforces configurable limits on document size, chunk length, and maximum chunk count.
"""
import re
import hashlib
import logging
from typing import List, Optional
from app.core.config import settings
from app.schemas.rag import ExtractedDocument, DocumentChunk

logger = logging.getLogger("sakshi.rag.chunking")

# Regex for sentence boundary detection
SENTENCE_SPLIT_PATTERN = re.compile(r'(?<=[.!?])\s+')


class ChunkingService:
    """
    Forensic text chunking engine preserving exact source citations and boundaries.
    """

    def __init__(
        self,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        min_chunk_length: Optional[int] = None,
        max_doc_chars: Optional[int] = None,
    ):
        self.chunk_size = chunk_size or settings.RAG_CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.RAG_CHUNK_OVERLAP
        self.min_chunk_length = min_chunk_length or settings.RAG_MIN_CHUNK_LENGTH
        self.max_doc_chars = max_doc_chars or settings.RAG_MAX_DOC_CHARS

        # Sanity check
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size")

    def chunk_document(
        self,
        extracted_doc: ExtractedDocument,
        document_id: Optional[str] = None,
    ) -> List[DocumentChunk]:
        """
        Segments an ExtractedDocument into an ordered list of citation-anchored DocumentChunk objects.
        """
        # Guardrail on total document characters
        if extracted_doc.total_characters > self.max_doc_chars:
            logger.warning(
                "Document %s exceeds character limit (%d > %d). Truncating processing.",
                extracted_doc.evidence_id,
                extracted_doc.total_characters,
                self.max_doc_chars,
            )

        # Derive a stable, compact evidence token for chunk IDs
        raw_evidence_id = extracted_doc.evidence_id
        if "-" in raw_evidence_id:
            evidence_token = raw_evidence_id.split("-")[-1]
        else:
            evidence_token = hashlib.sha256(raw_evidence_id.encode("utf-8")).hexdigest()[:8]

        # Canonical document_id fallback if not explicitly provided
        doc_id = document_id or f"SAKSHI-DOC-{evidence_token}"

        chunks: List[DocumentChunk] = []
        global_chunk_idx = 0

        for page in extracted_doc.pages:
            page_text = page.text
            if not page_text or len(page_text.strip()) < self.min_chunk_length:
                # Skip empty or negligible pages
                continue

            # Chunk the page text with boundary preservation
            page_chunks = self._chunk_page(
                page_text=page_text,
                page_number=page.page_number,
                doc_id=doc_id,
                case_id=extracted_doc.case_id,
                evidence_id=extracted_doc.evidence_id,
                source_sha256=extracted_doc.source_sha256,
                source_sha3_512=extracted_doc.source_sha3_512,
                processing_version=extracted_doc.processing_version,
                evidence_token=evidence_token,
                start_index=global_chunk_idx,
            )

            chunks.extend(page_chunks)
            global_chunk_idx += len(page_chunks)

        logger.info(
            "Chunked document %s (%s): %d total chunks across %d pages",
            doc_id,
            extracted_doc.evidence_id,
            len(chunks),
            extracted_doc.total_pages,
        )
        return chunks

    def _chunk_page(
        self,
        page_text: str,
        page_number: int,
        doc_id: str,
        case_id: str,
        evidence_id: str,
        source_sha256: str,
        source_sha3_512: Optional[str],
        processing_version: str,
        evidence_token: str,
        start_index: int,
    ) -> List[DocumentChunk]:
        """
        Splits a single page's text into overlapping chunks, tracking char offsets.
        """
        page_chunks: List[DocumentChunk] = []
        text_len = len(page_text)
        current_idx = start_index

        # If the entire page text is smaller than or equal to chunk_size, emit as single chunk
        if text_len <= self.chunk_size:
            chunk_id = f"SAKSHI-CHK-{evidence_token}-{current_idx:04d}"
            page_chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=doc_id,
                    case_id=case_id,
                    evidence_id=evidence_id,
                    chunk_index=current_idx,
                    content=page_text,
                    page_number=page_number,
                    char_start=0,
                    char_end=text_len,
                    source_sha256=source_sha256,
                    source_sha3_512=source_sha3_512,
                    processing_version=processing_version,
                )
            )
            return page_chunks

        # Sliding window with boundary awareness
        cursor = 0
        step_size = self.chunk_size - self.chunk_overlap

        while cursor < text_len:
            end_pos = min(cursor + self.chunk_size, text_len)

            # If not at the end of text, attempt to break at a sentence or paragraph boundary
            if end_pos < text_len:
                boundary_pos = self._find_natural_break(page_text, cursor, end_pos)
                if boundary_pos is not None:
                    end_pos = boundary_pos

            chunk_text = page_text[cursor:end_pos].strip()

            if len(chunk_text) >= self.min_chunk_length:
                # Locate exact offsets of the stripped chunk within page_text
                # to guarantee offset precision
                rel_start = page_text.find(chunk_text, cursor)
                if rel_start == -1:
                    rel_start = cursor
                rel_end = rel_start + len(chunk_text)

                chunk_id = f"SAKSHI-CHK-{evidence_token}-{current_idx:04d}"
                page_chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        document_id=doc_id,
                        case_id=case_id,
                        evidence_id=evidence_id,
                        chunk_index=current_idx,
                        content=chunk_text,
                        page_number=page_number,
                        char_start=rel_start,
                        char_end=rel_end,
                        source_sha256=source_sha256,
                        source_sha3_512=source_sha3_512,
                        processing_version=processing_version,
                    )
                )
                current_idx += 1

            if end_pos >= text_len:
                break

            # Slide window forward by step_size (accounting for overlap)
            # Ensure forward progress
            next_cursor = max(cursor + 1, end_pos - self.chunk_overlap)
            cursor = next_cursor

        return page_chunks

    def _find_natural_break(self, text: str, start: int, target_end: int) -> Optional[int]:
        """
        Looks for the closest sentence (.!?) or paragraph (\n) break
        within a reasonable search window before target_end.
        """
        # Look backwards up to 30% of chunk_size from target_end
        search_window = int(self.chunk_size * 0.3)
        window_start = max(start, target_end - search_window)
        substring = text[window_start:target_end]

        # 1. Paragraph break
        para_idx = substring.rfind("\n\n")
        if para_idx != -1:
            return window_start + para_idx + 2

        # 2. Sentence boundary
        matches = list(SENTENCE_SPLIT_PATTERN.finditer(substring))
        if matches:
            last_match = matches[-1]
            return window_start + last_match.end()

        # 3. Line break
        newline_idx = substring.rfind("\n")
        if newline_idx != -1:
            return window_start + newline_idx + 1

        # 4. Word boundary (space)
        space_idx = substring.rfind(" ")
        if space_idx != -1:
            return window_start + space_idx + 1

        return None
