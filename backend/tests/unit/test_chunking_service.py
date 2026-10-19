"""
Unit tests for ChunkingService (SAKSHI RAG Phase 3).
Validates passage splitting, natural boundary preservation, page attribution,
source offset precision, and stable chunk identifiers.
"""
import pytest
from app.schemas.rag import ExtractedDocument, ExtractedPage
from app.services.chunking_service import ChunkingService


def test_chunking_single_short_page():
    """Verify that a page shorter than chunk_size emits a single chunk with exact offsets."""
    text = "Short inquest report statement regarding forensic scene observation."
    doc = ExtractedDocument(
        case_id="SAKSHI-CASE-2026-CHK01",
        evidence_id="SAKSHI-EVID-2026-DOC001",
        source_sha256="a" * 64,
        mime_type="application/pdf",
        extraction_method="PDF_NATIVE_TEXT",
        processing_version="v1.0",
        pages=[ExtractedPage(page_number=1, text=text, char_count=len(text))],
        total_pages=1,
        total_characters=len(text),
    )

    service = ChunkingService(chunk_size=500, chunk_overlap=100)
    chunks = service.chunk_document(doc)

    assert len(chunks) == 1
    c = chunks[0]
    assert c.chunk_index == 0
    assert c.page_number == 1
    assert c.char_start == 0
    assert c.char_end == len(text)
    assert c.content == text
    assert c.source_sha256 == "a" * 64
    assert c.chunk_id == "SAKSHI-CHK-DOC001-0000"


def test_chunking_multipage_page_attribution_and_offsets():
    """Verify chunks accurately retain their respective page numbers and exact character slices."""
    p1 = "Paragraph 1 on Page 1.\n\nParagraph 2 on Page 1 has more details about the decedent."
    p2 = "Page 2 describes the toxicological report findings.\n\nNegative for alcohol and narcotics."
    doc = ExtractedDocument(
        case_id="SAKSHI-CASE-2026-CHK01",
        evidence_id="SAKSHI-EVID-2026-DOC002",
        source_sha256="b" * 64,
        source_sha3_512="c" * 128,
        mime_type="application/pdf",
        extraction_method="PDF_NATIVE_TEXT",
        pages=[
            ExtractedPage(page_number=1, text=p1, char_count=len(p1)),
            ExtractedPage(page_number=2, text=p2, char_count=len(p2)),
        ],
        total_pages=2,
        total_characters=len(p1) + len(p2),
    )

    service = ChunkingService(chunk_size=100, chunk_overlap=20, min_chunk_length=15)
    chunks = service.chunk_document(doc)

    assert len(chunks) >= 2
    for chunk in chunks:
        # Verify page attribution
        assert chunk.page_number in (1, 2)
        # Verify source offset matches actual substring on that page
        page_text = p1 if chunk.page_number == 1 else p2
        extracted_slice = page_text[chunk.char_start:chunk.char_end]
        assert extracted_slice == chunk.content
        assert chunk.source_sha3_512 == "c" * 128


def test_chunking_natural_boundary_preservation():
    """Verify chunking splits on paragraph and sentence breaks rather than hard-chopping words."""
    sentence1 = "The first full sentence describes the initial inspection of the scene."
    sentence2 = "The second sentence documents external injuries noted on the decedent."
    full_text = f"{sentence1} {sentence2}"

    doc = ExtractedDocument(
        case_id="SAKSHI-CASE-2026-CHK01",
        evidence_id="SAKSHI-EVID-2026-DOC003",
        source_sha256="d" * 64,
        mime_type="text/plain",
        extraction_method="PLAINTEXT_DIRECT",
        pages=[ExtractedPage(page_number=1, text=full_text, char_count=len(full_text))],
        total_pages=1,
        total_characters=len(full_text),
    )

    # Size chosen so sentence1 fits in chunk 1, but sentence1+sentence2 exceeds chunk_size
    service = ChunkingService(chunk_size=80, chunk_overlap=20, min_chunk_length=15)
    chunks = service.chunk_document(doc)

    assert len(chunks) >= 2
    # First chunk should end neatly at sentence boundary without chopped words
    assert chunks[0].content.endswith(".") or chunks[0].content.endswith("scene.")
    assert not chunks[0].content.endswith("dece")


def test_chunking_skips_empty_pages():
    """Verify empty or whitespace-only pages are cleanly skipped without generating blank chunks."""
    doc = ExtractedDocument(
        case_id="SAKSHI-CASE-2026-CHK01",
        evidence_id="SAKSHI-EVID-2026-DOC004",
        source_sha256="e" * 64,
        mime_type="application/pdf",
        extraction_method="PDF_NATIVE_TEXT",
        pages=[
            ExtractedPage(page_number=1, text="   \n\n   ", char_count=0),
            ExtractedPage(page_number=2, text="Valid content on page 2 of autopsy report.", char_count=42),
            ExtractedPage(page_number=3, text="", char_count=0),
        ],
        total_pages=3,
        total_characters=42,
    )

    service = ChunkingService(chunk_size=200, chunk_overlap=40)
    chunks = service.chunk_document(doc)

    assert len(chunks) == 1
    assert chunks[0].page_number == 2
    assert "Valid content" in chunks[0].content


def test_stable_chunk_identifiers_are_deterministic():
    """Verify chunk identifiers remain completely deterministic across invocations."""
    doc = ExtractedDocument(
        case_id="SAKSHI-CASE-2026-CHK01",
        evidence_id="SAKSHI-EVID-2026-EXHIBIT8",
        source_sha256="f" * 64,
        mime_type="application/pdf",
        extraction_method="PDF_NATIVE_TEXT",
        pages=[ExtractedPage(page_number=1, text="Forensic statement regarding scene inspection details.", char_count=55)],
        total_pages=1,
        total_characters=55,
    )

    service = ChunkingService(chunk_size=200, chunk_overlap=40)
    run1 = service.chunk_document(doc)
    run2 = service.chunk_document(doc)

    assert run1[0].chunk_id == run2[0].chunk_id
    assert run1[0].chunk_id == "SAKSHI-CHK-EXHIBIT8-0000"
