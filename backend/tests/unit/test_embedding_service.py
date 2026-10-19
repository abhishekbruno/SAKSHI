"""
Unit tests for EmbeddingService (SAKSHI RAG Phase 3).
Validates model configuration, 384-dimensional vector validation, unit normalization,
deterministic mock provider, and error handling.
"""
import math
import pytest
from app.core.config import settings
from app.core.errors import (
    EmbeddingGenerationException,
    EmbeddingModelLoadException,
    EmbeddingDimensionMismatchException,
)
from app.schemas.rag import DocumentChunk
from app.services.embedding_service import (
    EmbeddingService,
    DeterministicMockEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    IEmbeddingProvider,
)


def test_selected_model_and_dimension_configuration():
    """Verify that settings explicitly configure all-MiniLM-L6-v2 with 384 dimensions."""
    assert settings.EMBEDDING_MODEL_NAME == "sentence-transformers/all-MiniLM-L6-v2"
    assert settings.EMBEDDING_DIMENSION == 384

    service = EmbeddingService()
    assert service.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert service.dimension == 384


def test_deterministic_mock_provider_dimension_and_normalization():
    """Verify mock provider returns exactly 384 dimensions with unit L2 norm."""
    provider = DeterministicMockEmbeddingProvider()
    assert provider.dimension == 384

    texts = [
        "Inquest report of deceased found at crime scene.",
        "Forensic autopsy report establishing cause of death.",
    ]
    vectors = provider.generate_embeddings(texts)

    assert len(vectors) == 2
    for vec in vectors:
        assert len(vec) == 384
        # Verify L2 unit norm (sum of squares is ~ 1.0)
        norm_sq = sum(x * x for x in vec)
        assert math.isclose(norm_sq, 1.0, rel_tol=1e-3)


def test_deterministic_consistency_and_entropy():
    """Verify identical text produces identical embeddings, while different texts differ."""
    service = EmbeddingService(DeterministicMockEmbeddingProvider())

    vec_a1 = service.embed_text("Ligature mark on neck consistent with hanging.")
    vec_a2 = service.embed_text("Ligature mark on neck consistent with hanging.")
    vec_b = service.embed_text("Toxicology report shows lethal dose of organophosphate.")

    assert vec_a1 == vec_a2
    assert vec_a1 != vec_b

    # Cosine similarity between differing texts is bounded between -1.0 and 1.0
    dot_product = sum(a * b for a, b in zip(vec_a1, vec_b))
    assert -1.0 <= dot_product <= 1.0


def test_empty_text_raises_exception():
    """Verify passing empty or whitespace text raises EmbeddingGenerationException."""
    service = EmbeddingService(DeterministicMockEmbeddingProvider())
    with pytest.raises(EmbeddingGenerationException):
        service.embed_text("   ")


def test_dimension_mismatch_validation():
    """Verify EmbeddingService catches dimension mismatches and raises explicit exception."""
    class BrokenDimensionProvider(IEmbeddingProvider):
        @property
        def model_name(self) -> str:
            return "broken-provider"

        @property
        def dimension(self) -> int:
            return 384  # claims 384

        def generate_embeddings(self, texts):
            # returns 128 dimensions instead
            return [[0.1] * 128 for _ in texts]

    service = EmbeddingService(BrokenDimensionProvider())
    with pytest.raises(EmbeddingDimensionMismatchException) as exc:
        service.embed_text("Test sentence.")
    assert "expected 384, got 128" in str(exc.value)


def test_nan_vector_component_rejection():
    """Verify EmbeddingService catches NaN or Inf components."""
    class NanProvider(IEmbeddingProvider):
        @property
        def model_name(self) -> str:
            return "nan-provider"

        @property
        def dimension(self) -> int:
            return 384

        def generate_embeddings(self, texts):
            vec = [0.1] * 384
            vec[0] = float("nan")
            return [vec]

    service = EmbeddingService(NanProvider())
    with pytest.raises(EmbeddingGenerationException) as exc:
        service.embed_text("Test sentence.")
    assert "NaN or Inf" in str(exc.value)


def test_embed_chunks_preserves_provenance():
    """Verify embed_chunks attaches embeddings and preserves chunk metadata."""
    service = EmbeddingService(DeterministicMockEmbeddingProvider())

    chunks = [
        DocumentChunk(
            chunk_id="SAKSHI-CHK-TEST-0001",
            document_id="SAKSHI-DOC-TEST",
            case_id="SAKSHI-CASE-01",
            evidence_id="SAKSHI-EVID-01",
            chunk_index=0,
            content="Sample forensic inquest evidence passage.",
            page_number=1,
            char_start=0,
            char_end=41,
            source_sha256="a" * 64,
            processing_version="v1.0",
        )
    ]

    embedded = service.embed_chunks(chunks)
    assert len(embedded) == 1
    assert embedded[0].chunk.chunk_id == "SAKSHI-CHK-TEST-0001"
    assert embedded[0].embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
    assert len(embedded[0].embedding) == 384


def test_sentence_transformer_error_handling_when_uninstalled():
    """Verify SentenceTransformerEmbeddingProvider raises EmbeddingModelLoadException when missing."""
    provider = SentenceTransformerEmbeddingProvider(model_name="non-existent-local-model")
    # If sentence_transformers is not installed or fails loading
    with pytest.raises(EmbeddingModelLoadException):
        provider.generate_embeddings(["Test query."])


def test_production_never_silently_uses_mock_embeddings(monkeypatch):
    """A missing local production model must not downgrade retrieval to hash vectors."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "deterministic_mock")
    with pytest.raises(EmbeddingModelLoadException, match="disabled in production"):
        EmbeddingService()


def test_production_sentence_transformer_missing_locally_fails_without_mock(monkeypatch):
    """Selecting production inference preserves the model-load error rather than downgrading providers."""
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "sentence_transformer")
    service = EmbeddingService()
    assert isinstance(service.provider, SentenceTransformerEmbeddingProvider)
    with pytest.raises(EmbeddingModelLoadException):
        service.embed_text("test query")
