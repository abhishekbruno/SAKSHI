"""Phase 4 API tests: authentication, case isolation, validation, and safe audit metadata."""
from fastapi import status

from app.models.case import Case
from app.models.evidence import Evidence
from app.models.rag_chunk import RAGChunk
from app.models.rag_document import RAGDocument
from app.models.rag_index_job import RAGIndexJob
from app.services.audit_integration import AuditIntegrationService


def _add_searchable_record(db, *, case_id, evidence_id, document_id, chunk_id, content="needle"):
    digest = (evidence_id.lower().replace("-", "") + "x" * 64)[:64]
    sha3_digest = (evidence_id.lower().replace("-", "") + "y" * 128)[:128]
    db.add(Evidence(
        evidence_id=evidence_id, case_id=case_id, original_file_name="report.pdf",
        stored_file_name="safe-report.pdf", evidence_category="DOCUMENT_PDF",
        declared_mime_type="application/pdf", file_size_bytes=12, submitting_investigator_id="IO-7842-SHARMA",
        status="COMMITTED", antivirus_status="CLEAN", worm_status="COMMITTED",
        checksum_sha256=digest, checksum_sha3_512=sha3_digest, integrity_status="VERIFIED", lock_status="LOCKED",
        encryption_status="UNENCRYPTED", raw_storage_path="/not-exposed",
    ))
    db.add(RAGDocument(
        document_id=document_id, case_id=case_id, evidence_id=evidence_id,
        source_sha256=digest, source_sha3_512=sha3_digest, indexing_status="INDEXED", total_chunks=1,
    ))
    # The deterministic development provider gives an exact query/content match a score of 1.
    from app.services.embedding_service import EmbeddingService
    embedding = EmbeddingService().embed_text(content)
    db.add(RAGChunk(
        chunk_id=chunk_id, document_id=document_id, case_id=case_id, evidence_id=evidence_id,
        chunk_index=0, content=content, page_number=3, char_start=15, char_end=15 + len(content),
        source_sha256=digest, source_sha3_512=sha3_digest, embedding=embedding, embedding_model=EmbeddingService().model_name,
    ))
    db.add(RAGIndexJob(
        job_id=f"JOB-{document_id}", document_id=document_id, case_id=case_id,
        evidence_id=evidence_id, status="COMPLETED",
    ))
    db.commit()


def _add_case(db, case_id, assigned_io, jurisdiction):
    db.add(Case(
        case_id=case_id, title="Synthetic retrieval case", fir_metadata={"jurisdiction_code": jurisdiction},
        assigned_io_id=assigned_io, lifecycle_stage="EVIDENCE_PROCESSING", status="ACTIVE",
        case_workspace_path="/synthetic", created_by=assigned_io,
    ))
    db.commit()


def test_authenticated_search_returns_traceable_schema(client, db_session, auth_headers_io1):
    _add_case(db_session, "CASE-API-ONE", "IO-7842-SHARMA", "JUR-DEL-04")
    _add_searchable_record(
        db_session, case_id="CASE-API-ONE", evidence_id="EVID-API-ONE",
        document_id="DOC-API-ONE", chunk_id="CHUNK-API-ONE",
    )

    response = client.post("/api/v1/cases/CASE-API-ONE/rag/search", json={"query": "needle", "limit": 5}, headers=auth_headers_io1)

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["case_id"] == "CASE-API-ONE"
    assert body["result_count"] == 1
    assert body["query_metadata"]["retrieval_mode"] == "sqlite_bounded_development_fallback"
    result = body["results"][0]
    assert result["chunk_id"] == "CHUNK-API-ONE"
    assert result["source_name"] == "safe-report.pdf"
    assert result["page_number"] == 3
    assert result["char_start"] == 15
    assert "storage_path" not in result


def test_cross_case_search_is_denied_and_matching_chunk_is_not_leaked(client, db_session, auth_headers_io1, auth_headers_io2):
    _add_case(db_session, "CASE-API-PRIVATE", "IO-7842-SHARMA", "JUR-DEL-04")
    _add_searchable_record(
        db_session, case_id="CASE-API-PRIVATE", evidence_id="EVID-API-PRIVATE",
        document_id="DOC-API-PRIVATE", chunk_id="CHUNK-API-SECRET",
    )

    response = client.post(
        "/api/v1/cases/CASE-API-PRIVATE/rag/search", json={"query": "needle"}, headers=auth_headers_io2,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "CHUNK-API-SECRET" not in response.text
    assert "EVID-API-PRIVATE" not in response.text


def test_unknown_case_uses_the_same_safe_denial_shape(client, auth_headers_io1):
    response = client.post(
        "/api/v1/cases/CASE-NOT-DISCLOSED/rag/search", json={"query": "needle"}, headers=auth_headers_io1,
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["error_code"] == "FORBIDDEN"


def test_search_requires_authentication(client):
    response = client.post("/api/v1/cases/CASE-ANY/rag/search", json={"query": "needle"})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_search_validation_rejects_blank_oversized_queries_and_bad_limits(client, auth_headers_io1):
    endpoint = "/api/v1/cases/CASE-ANY/rag/search"
    for payload in (
        {"query": ""}, {"query": "   "}, {"query": "x" * 2001}, {"query": "needle", "limit": 0},
        {"query": "needle", "limit": 21},
    ):
        response = client.post(endpoint, json=payload, headers=auth_headers_io1)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_search_audit_does_not_record_query_or_passage(client, db_session, auth_headers_io1, monkeypatch):
    _add_case(db_session, "CASE-API-AUDIT", "IO-7842-SHARMA", "JUR-DEL-04")
    _add_searchable_record(
        db_session, case_id="CASE-API-AUDIT", evidence_id="EVID-API-AUDIT",
        document_id="DOC-API-AUDIT", chunk_id="CHUNK-API-AUDIT", content="unique sensitive passage",
    )
    events = []
    monkeypatch.setattr(AuditIntegrationService, "record_event", staticmethod(lambda **kwargs: events.append(kwargs)))

    response = client.post(
        "/api/v1/cases/CASE-API-AUDIT/rag/search", json={"query": "unique sensitive passage"}, headers=auth_headers_io1,
    )
    assert response.status_code == status.HTTP_200_OK
    retrieval_event = next(event for event in events if event["action"] == "RAG_RETRIEVAL")
    assert retrieval_event["details"]["outcome"] == "SUCCESS"
    assert "query" not in retrieval_event["details"]
    assert "passage" not in retrieval_event["details"]
