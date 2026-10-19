"""Phase 4 unit tests for secure, case-scoped RAG retrieval."""
import pytest

from app.core.errors import EmbeddingGenerationException
from app.core.security import AuthenticatedInvestigator
from app.models.case import Case
from app.models.evidence import Evidence
from app.models.rag_chunk import RAGChunk
from app.models.rag_document import RAGDocument
from app.models.rag_index_job import RAGIndexJob
from app.services.embedding_service import EmbeddingService, IEmbeddingProvider
from app.services.rag_retrieval_service import RAGRetrievalService
from app.services.audit_integration import AuditIntegrationService


class MappingEmbeddingProvider(IEmbeddingProvider):
    def __init__(self, values):
        self.values = values

    @property
    def model_name(self):
        return "test-local-model"

    @property
    def dimension(self):
        return 384

    def generate_embeddings(self, texts):
        return [self.values[text] for text in texts]


def vector(first, second=0.0):
    return [first, second] + [0.0] * 382


def add_indexed_evidence(db, *, case_id, evidence_id, document_id, chunks, job_status="COMPLETED", eligible=True):
    digest = (evidence_id.lower().replace("-", "") + "x" * 64)[:64]
    sha3_digest = (evidence_id.lower().replace("-", "") + "y" * 128)[:128]
    evidence = Evidence(
        evidence_id=evidence_id,
        case_id=case_id,
        original_file_name="original-report.pdf",
        stored_file_name=f"{evidence_id}.pdf",
        evidence_category="DOCUMENT_PDF",
        declared_mime_type="application/pdf",
        file_size_bytes=100,
        submitting_investigator_id="IO-1",
        status="COMMITTED" if eligible else "VALIDATED",
        antivirus_status="CLEAN" if eligible else "PENDING",
        worm_status="COMMITTED" if eligible else "PENDING",
        checksum_sha256=digest,
        checksum_sha3_512=sha3_digest,
        integrity_status="VERIFIED" if eligible else "UNVERIFIED",
        lock_status="LOCKED" if eligible else "UNLOCKED",
        encryption_status="UNENCRYPTED",
        raw_storage_path="/not-used-by-retrieval",
    )
    document = RAGDocument(
        document_id=document_id,
        case_id=case_id,
        evidence_id=evidence_id,
        source_sha256=digest,
        source_sha3_512=sha3_digest,
        indexing_status="INDEXED",
        processing_version="v1.0",
        total_chunks=len(chunks),
    )
    db.add_all([evidence, document])
    for index, (chunk_id, text, embedding) in enumerate(chunks):
        db.add(RAGChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            case_id=case_id,
            evidence_id=evidence_id,
            chunk_index=index,
            content=text,
            page_number=index + 1,
            char_start=index * 100,
            char_end=index * 100 + len(text),
            source_sha256=digest,
            source_sha3_512=sha3_digest,
            embedding_model="test-local-model",
            processing_version="v1.0",
            embedding=embedding,
        ))
    db.add(RAGIndexJob(
        job_id=f"JOB-{document_id}",
        document_id=document_id,
        case_id=case_id,
        evidence_id=evidence_id,
        status=job_status,
    ))
    db.commit()


@pytest.fixture
def retrieval_context(db_session):
    case_one = Case(
        case_id="CASE-ONE", title="One", fir_metadata={"jurisdiction_code": "J1"},
        assigned_io_id="IO-1", lifecycle_stage="EVIDENCE_PROCESSING", status="ACTIVE",
        case_workspace_path="/case-one", created_by="IO-1",
    )
    case_two = Case(
        case_id="CASE-TWO", title="Two", fir_metadata={"jurisdiction_code": "J2"},
        assigned_io_id="IO-2", lifecycle_stage="EVIDENCE_PROCESSING", status="ACTIVE",
        case_workspace_path="/case-two", created_by="IO-2",
    )
    db_session.add_all([case_one, case_two])
    db_session.commit()
    investigator = AuthenticatedInvestigator(
        subject_id="IO-1", role="INVESTIGATING_OFFICER", station_jurisdiction="J1", is_authenticated=True,
    )
    provider = MappingEmbeddingProvider({"needle": vector(1.0)})
    return db_session, investigator, EmbeddingService(provider)


def test_retrieval_ranks_relevant_case_chunks_and_preserves_provenance(retrieval_context):
    db, investigator, embeddings = retrieval_context
    add_indexed_evidence(db, case_id="CASE-ONE", evidence_id="EVID-ONE", document_id="DOC-ONE", chunks=[
        ("CHUNK-RELEVANT", "needle passage", vector(1.0)),
        ("CHUNK-LESS", "other passage", vector(0.0, 1.0)),
    ])
    service = RAGRetrievalService(db, embedding_service=embeddings)

    response = service.search(case_id="CASE-ONE", query="needle", investigator=investigator, limit=10)

    assert response.query_metadata.retrieval_mode == "sqlite_bounded_development_fallback"
    assert [result.chunk_id for result in response.results] == ["CHUNK-RELEVANT", "CHUNK-LESS"]
    first = response.results[0]
    assert first.case_id == "CASE-ONE"
    assert first.evidence_id == "EVID-ONE"
    assert first.document_id == "DOC-ONE"
    assert first.page_number == 1
    assert first.char_start == 0
    assert first.char_end == len("needle passage")
    assert first.source_name == "EVID-ONE.pdf"
    assert first.similarity_score == 1.0
    assert "untrusted source material" in response.score_semantics


def test_matching_cross_case_chunk_never_appears(retrieval_context):
    db, investigator, embeddings = retrieval_context
    add_indexed_evidence(db, case_id="CASE-ONE", evidence_id="EVID-ONE", document_id="DOC-ONE", chunks=[
        ("CHUNK-ONE", "case one", vector(0.0, 1.0)),
    ])
    add_indexed_evidence(db, case_id="CASE-TWO", evidence_id="EVID-TWO", document_id="DOC-TWO", chunks=[
        ("CHUNK-SECRET", "needle", vector(1.0)),
    ])
    service = RAGRetrievalService(db, embedding_service=embeddings)

    response = service.search(case_id="CASE-ONE", query="needle", investigator=investigator, limit=10)

    assert [result.chunk_id for result in response.results] == ["CHUNK-ONE"]
    assert all(result.case_id == "CASE-ONE" for result in response.results)
    assert "CHUNK-SECRET" not in {result.chunk_id for result in response.results}


def test_failed_or_ineligible_index_records_are_excluded(retrieval_context):
    db, investigator, embeddings = retrieval_context
    add_indexed_evidence(db, case_id="CASE-ONE", evidence_id="EVID-FAILED", document_id="DOC-FAILED", chunks=[
        ("CHUNK-FAILED", "needle", vector(1.0)),
    ], job_status="FAILED")
    add_indexed_evidence(db, case_id="CASE-ONE", evidence_id="EVID-INELIGIBLE", document_id="DOC-INELIGIBLE", chunks=[
        ("CHUNK-INELIGIBLE", "needle", vector(1.0)),
    ], eligible=False)
    service = RAGRetrievalService(db, embedding_service=embeddings)

    response = service.search(case_id="CASE-ONE", query="needle", investigator=investigator, limit=10)

    assert response.results == []
    assert response.empty_result_notice


def test_nonfinite_query_embedding_fails_safely(retrieval_context):
    db, investigator, _ = retrieval_context
    service = RAGRetrievalService(
        db,
        embedding_service=EmbeddingService(MappingEmbeddingProvider({"needle": [float("nan")] * 384})),
    )
    with pytest.raises(EmbeddingGenerationException):
        service.search(case_id="CASE-ONE", query="needle", investigator=investigator, limit=1)


def test_invalid_stored_vector_is_not_retrieved(retrieval_context):
    db, investigator, embeddings = retrieval_context
    add_indexed_evidence(db, case_id="CASE-ONE", evidence_id="EVID-BAD", document_id="DOC-BAD", chunks=[
        ("CHUNK-BAD", "needle", [float("nan")] + [0.0] * 383),
    ])
    response = RAGRetrievalService(db, embedding_service=embeddings).search(
        case_id="CASE-ONE", query="needle", investigator=investigator, limit=1,
    )
    assert response.results == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("antivirus_status", "PENDING"),
        ("worm_status", "PENDING"),
        ("integrity_status", "UNVERIFIED"),
        ("lock_status", "UNLOCKED"),
        ("encryption_status", "ENCRYPTION_FAILED"),
        ("status", "VALIDATED"),
    ],
)
def test_each_evidence_security_gate_excludes_a_record(retrieval_context, field, value):
    db, investigator, embeddings = retrieval_context
    add_indexed_evidence(db, case_id="CASE-ONE", evidence_id="EVID-GATE", document_id="DOC-GATE", chunks=[
        ("CHUNK-GATE", "needle", vector(1.0)),
    ])
    evidence = db.query(Evidence).filter_by(evidence_id="EVID-GATE").one()
    setattr(evidence, field, value)
    db.commit()

    response = RAGRetrievalService(db, embedding_service=embeddings).search(
        case_id="CASE-ONE", query="needle", investigator=investigator, limit=1,
    )
    assert response.results == []


@pytest.mark.parametrize(
    ("target", "field", "value"),
    [
        ("evidence", "checksum_sha256", "z" * 64),
        ("evidence", "checksum_sha3_512", "z" * 128),
        ("document", "indexing_status", "PROCESSING"),
        ("job", "status", "RUNNING"),
        ("chunk", "embedding", None),
        ("chunk", "embedding", [1.0] * 383),
    ],
)
def test_invalid_provenance_index_or_embedding_state_is_excluded(retrieval_context, target, field, value):
    db, investigator, embeddings = retrieval_context
    add_indexed_evidence(db, case_id="CASE-ONE", evidence_id="EVID-STATE", document_id="DOC-STATE", chunks=[
        ("CHUNK-STATE", "needle", vector(1.0)),
    ])
    model = {"evidence": Evidence, "document": RAGDocument, "job": RAGIndexJob, "chunk": RAGChunk}[target]
    identifier = {
        "evidence": {"evidence_id": "EVID-STATE"},
        "document": {"document_id": "DOC-STATE"},
        "job": {"document_id": "DOC-STATE"},
        "chunk": {"chunk_id": "CHUNK-STATE"},
    }[target]
    record = db.query(model).filter_by(**identifier).one()
    setattr(record, field, value)
    db.commit()

    response = RAGRetrievalService(db, embedding_service=embeddings).search(
        case_id="CASE-ONE", query="needle", investigator=investigator, limit=1,
    )
    assert response.results == []


def test_authorization_precedes_embedding_and_audit_omits_sensitive_content(retrieval_context, monkeypatch):
    db, _, _ = retrieval_context
    add_indexed_evidence(db, case_id="CASE-ONE", evidence_id="EVID-AUTH", document_id="DOC-AUTH", chunks=[
        ("CHUNK-AUTH", "sensitive passage", vector(1.0)),
    ])
    events = []
    monkeypatch.setattr(AuditIntegrationService, "record_event", staticmethod(lambda **event: events.append(event)))
    unauthorized = AuthenticatedInvestigator(
        subject_id="IO-2", role="INVESTIGATING_OFFICER", station_jurisdiction="J2", is_authenticated=True,
    )

    class MustNotEmbedProvider(IEmbeddingProvider):
        model_name = "must-not-run"
        dimension = 384

        def generate_embeddings(self, texts):
            raise AssertionError("embedding must not run before authorization")

    with pytest.raises(Exception) as raised:
        RAGRetrievalService(db, embedding_service=EmbeddingService(MustNotEmbedProvider())).search(
            case_id="CASE-ONE", query="sensitive query", investigator=unauthorized, limit=1,
        )
    assert raised.value.status_code == 403
    retrieval_event = next(event for event in events if event["action"] == "RAG_RETRIEVAL")
    assert retrieval_event["details"]["outcome"] == "DENIED"
    assert "query" not in retrieval_event["details"]
    assert "passage" not in retrieval_event["details"]
