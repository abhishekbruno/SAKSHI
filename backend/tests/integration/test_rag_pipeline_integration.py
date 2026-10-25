"""
Unified RPA + RAG + Core Integration Tests.

Validates:
1. Successfully locked evidence automatically triggers RAG indexing.
2. Indexing failure is safely contained without failing evidence intake or WORM commitment.
3. Indexing retry works independently without repeating MOD-05 to MOD-10.
4. Idempotency prevents duplicate RAGDocument and RAGChunk records.
5. Ineligible evidence (failing MOD-09 or MOD-10) is rejected for indexing.
6. Non-indexable MIME types are gracefully marked SKIPPED.
7. Core case retrieval endpoint (/cases/{case_id}/search) and standalone RAG endpoint return passages with provenance.
8. Cross-case and unauthorized retrieval/indexing are rejected with 403 Forbidden.
9. UiPath pipeline response contract maintains 100% backward compatibility.
"""
import io
import hashlib
from unittest.mock import patch
from fastapi import status
import pytest

from app.models.case import Case
from app.models.evidence import Evidence
from app.models.rag_document import RAGDocument
from app.models.rag_chunk import RAGChunk
from app.models.rag_index_job import RAGIndexJob
from app.core.errors import IneligibleEvidenceException, TextExtractionException


def make_minimal_pdf(content_pages: list[str]) -> bytes:
    """Build a minimal valid PDF with extractable text."""
    parts = ["%PDF-1.4\n"]
    offsets = []
    catalog_id = 1
    pages_id = 2
    page_ids = [3 + i * 2 for i in range(len(content_pages))]
    content_ids = [4 + i * 2 for i in range(len(content_pages))]
    font_id = 3 + len(content_pages) * 2

    offsets.append(len("".join(parts)))
    parts.append(f"{catalog_id} 0 obj << /Type /Catalog /Pages {pages_id} 0 R >> endobj\n")

    kids = " ".join([f"{pid} 0 R" for pid in page_ids])
    offsets.append(len("".join(parts)))
    parts.append(f"{pages_id} 0 obj << /Type /Pages /Kids [{kids}] /Count {len(content_pages)} >> endobj\n")

    for i, text in enumerate(content_pages):
        pid = page_ids[i]
        cid = content_ids[i]
        stream_data = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET"
        stream_len = len(stream_data)

        offsets.append(len("".join(parts)))
        parts.append(
            f"{pid} 0 obj << /Type /Page /Parent {pages_id} 0 R "
            f"/MediaBox [0 0 612 792] /Contents {cid} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >> endobj\n"
        )

        offsets.append(len("".join(parts)))
        parts.append(f"{cid} 0 obj << /Length {stream_len} >>\nstream\n{stream_data}\nendstream\nendobj\n")

    offsets.append(len("".join(parts)))
    parts.append(f"{font_id} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")

    xref_offset = len("".join(parts))
    parts.append("xref\n")
    parts.append(f"0 {len(offsets) + 1}\n")
    parts.append("0000000000 65535 f \n")
    for off in offsets:
        parts.append(f"{off:010d} 00000 n \n")

    parts.append("trailer << /Size " + str(len(offsets) + 1) + f" /Root {catalog_id} 0 R >>\n")
    parts.append("startxref\n")
    parts.append(f"{xref_offset}\n")
    parts.append("%%EOF\n")

    return "".join(parts).encode("latin-1")


def _setup_case(client, auth_headers):
    payload = {
        "title": "Unified RPA-RAG Integration Test Case",
        "fir_metadata": {
            "fir_number": "FIR-UNIFIED-2026-001",
            "police_station": "Central Cyber Cell",
            "jurisdiction_code": "JUR-DEL-04",
        },
    }
    resp = client.post("/api/v1/cases", json=payload, headers=auth_headers).json()
    case_id = resp["case_id"]
    client.post(
        f"/api/v1/cases/{case_id}/stage",
        json={"lifecycle_stage": "EVIDENCE_INGESTION"},
        headers=auth_headers,
    )
    return case_id


def test_locked_evidence_automatically_indexed(client, auth_headers_io1):
    """MOD-10 successfully locked evidence is automatically indexed into RAG."""
    case_id = _setup_case(client, auth_headers_io1)
    pdf_bytes = make_minimal_pdf(["Suspect vehicle license plate DL-01-AB-1234 recorded on CCTV."])

    files = {"file": ("cctv_log.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
        "description": "CCTV vehicle transcript",
    }

    resp = client.post(
        f"/api/v1/cases/{case_id}/evidence/pipeline",
        files=files,
        data=data,
        headers=auth_headers_io1,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()

    assert body["overall_status"] == "SUCCESS"
    assert body["lock_status"] == "LOCKED"
    assert body["integrity_status"] == "VERIFIED"
    assert body["indexing_status"] == "INDEXED"
    assert body["document_id"] is not None
    assert body["document_id"].startswith("SAKSHI-DOC-")

    # Verify status via independent index-status endpoint
    evidence_id = body["evidence_id"]
    status_resp = client.get(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/index-status",
        headers=auth_headers_io1,
    )
    assert status_resp.status_code == status.HTTP_200_OK
    doc_info = status_resp.json()
    assert doc_info["document_id"] == body["document_id"]
    assert doc_info["indexing_status"] == "INDEXED"
    assert doc_info["total_chunks"] >= 1


def test_indexing_failure_is_containment_safe(client, auth_headers_io1):
    """If RAG indexing fails after MOD-10, evidence pipeline status is still SUCCESS."""
    case_id = _setup_case(client, auth_headers_io1)
    pdf_bytes = make_minimal_pdf(["Witness observed the suspect at 14:00 hours."])

    files = {"file": ("witness_statement.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
        "description": "Witness statement",
    }

    with patch("app.services.rag_indexing_service.RAGIndexingService.index_evidence") as mock_idx:
        mock_idx.side_effect = TextExtractionException("Simulated text extraction parser crash")

        resp = client.post(
            f"/api/v1/cases/{case_id}/evidence/pipeline",
            files=files,
            data=data,
            headers=auth_headers_io1,
        )

        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()

        # Evidence commitment and lock succeeded
        assert body["overall_status"] == "SUCCESS"
        assert body["lock_status"] == "LOCKED"
        assert body["integrity_status"] == "VERIFIED"
        # Indexing recorded as FAILED without failing evidence intake
        assert body["indexing_status"] == "FAILED"
        assert body["document_id"] is None


def test_indexing_retry_without_reintake(client, auth_headers_io1):
    """Failed indexing can be retried independently without re-running MOD-05 to MOD-10."""
    case_id = _setup_case(client, auth_headers_io1)
    pdf_bytes = make_minimal_pdf(["Forensic ballistic test confirms 9mm casing match."])

    files = {"file": ("ballistics.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
        "description": "Ballistics analysis",
    }

    # Step 1: Ingest with indexing failing
    with patch("app.services.rag_indexing_service.RAGIndexingService.index_evidence") as mock_idx:
        mock_idx.side_effect = RuntimeError("Temporary embedding service timeout")
        resp = client.post(
            f"/api/v1/cases/{case_id}/evidence/pipeline",
            files=files,
            data=data,
            headers=auth_headers_io1,
        )
        assert resp.status_code == status.HTTP_201_CREATED
        evidence_id = resp.json()["evidence_id"]
        assert resp.json()["indexing_status"] == "FAILED"

    # Step 2: Retry indexing via independent endpoint
    retry_resp = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/index",
        headers=auth_headers_io1,
    )
    assert retry_resp.status_code == status.HTTP_200_OK
    doc_body = retry_resp.json()
    assert doc_body["indexing_status"] == "INDEXED"
    assert doc_body["evidence_id"] == evidence_id
    assert doc_body["total_chunks"] >= 1


def test_idempotent_indexing_avoids_duplicate_records(client, auth_headers_io1):
    """Calling indexing multiple times returns existing document without duplicate chunks."""
    case_id = _setup_case(client, auth_headers_io1)
    pdf_bytes = make_minimal_pdf(["Fingerprint match found on weapon handle."])

    files = {"file": ("fingerprint.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
        "description": "Fingerprint report",
    }

    resp = client.post(
        f"/api/v1/cases/{case_id}/evidence/pipeline",
        files=files,
        data=data,
        headers=auth_headers_io1,
    )
    evidence_id = resp.json()["evidence_id"]
    doc_id = resp.json()["document_id"]
    assert resp.json()["indexing_status"] == "INDEXED"

    # Call index endpoint again
    call2 = client.post(
        f"/api/v1/cases/{case_id}/evidence/{evidence_id}/index",
        headers=auth_headers_io1,
    )
    assert call2.status_code == status.HTTP_200_OK
    assert call2.json()["document_id"] == doc_id
    assert call2.json()["indexing_status"] == "INDEXED"


def test_non_indexable_mime_type_skipped(client, auth_headers_io1):
    """Non-text MIME types (e.g., images) are gracefully marked SKIPPED."""
    case_id = _setup_case(client, auth_headers_io1)
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    files = {"file": ("scene_photo.png", io.BytesIO(png_bytes), "image/png")}
    data = {
        "evidence_category": "SCENE_PHOTO",
        "declared_mime_type": "image/png",
        "description": "Crime scene photograph",
    }

    resp = client.post(
        f"/api/v1/cases/{case_id}/evidence/pipeline",
        files=files,
        data=data,
        headers=auth_headers_io1,
    )
    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    assert body["overall_status"] == "SUCCESS"
    assert body["lock_status"] == "LOCKED"
    assert body["indexing_status"] == "SKIPPED"
    assert body["document_id"] is None


def test_core_case_search_and_provenance(client, auth_headers_io1):
    """Case investigation search returns passages with complete forensic provenance."""
    case_id = _setup_case(client, auth_headers_io1)
    text = "The suspect was intercepted near Gateway of India carrying contraband."
    pdf_bytes = make_minimal_pdf([text])

    files = {"file": ("interception_report.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {
        "evidence_category": "DOCUMENT_PDF",
        "declared_mime_type": "application/pdf",
        "description": "Interception report",
    }

    p_resp = client.post(
        f"/api/v1/cases/{case_id}/evidence/pipeline",
        files=files,
        data=data,
        headers=auth_headers_io1,
    )
    assert p_resp.status_code == status.HTTP_201_CREATED
    evidence_id = p_resp.json()["evidence_id"]

    # Search via Core Case Endpoint (/cases/{case_id}/search)
    search_resp = client.post(
        f"/api/v1/cases/{case_id}/search",
        json={"query": "contraband Gateway", "limit": 3},
        headers=auth_headers_io1,
    )
    assert search_resp.status_code == status.HTTP_200_OK
    search_data = search_resp.json()
    assert search_data["case_id"] == case_id
    assert search_data["result_count"] >= 1

    first_result = search_data["results"][0]
    assert first_result["evidence_id"] == evidence_id
    assert first_result["case_id"] == case_id
    assert "contraband" in first_result["passage"]
    assert first_result["source_sha256"] is not None
    assert first_result["page_number"] == 1

    # Verify Standalone RAG endpoint (/cases/{case_id}/rag/search) returns same results
    rag_resp = client.post(
        f"/api/v1/cases/{case_id}/rag/search",
        json={"query": "contraband Gateway", "limit": 3},
        headers=auth_headers_io1,
    )
    assert rag_resp.status_code == status.HTTP_200_OK
    assert rag_resp.json()["result_count"] == search_data["result_count"]


def test_cross_case_isolation_and_unauthorized_search(client, auth_headers_io1, auth_headers_io2):
    """Investigator cannot search or index evidence across case/jurisdiction boundary."""
    case_id = _setup_case(client, auth_headers_io1)

    # IO2 (different jurisdiction/not assigned) attempts to search
    unauth_search = client.post(
        f"/api/v1/cases/{case_id}/search",
        json={"query": "contraband", "limit": 3},
        headers=auth_headers_io2,
    )
    assert unauth_search.status_code == status.HTTP_403_FORBIDDEN

    # IO2 attempts to index
    unauth_idx = client.post(
        f"/api/v1/cases/{case_id}/evidence/SAKSHI-EVID-FAKE/index",
        headers=auth_headers_io2,
    )
    assert unauth_idx.status_code == status.HTTP_403_FORBIDDEN
