"""
Embedding Service for SAKSHI Investigation Platform.
Phase 3 — Evidence Text Extraction, Chunking, and Embedding.

Model Selection & Forensic Grounding Rationale:
- Primary Selected Model: 'sentence-transformers/all-MiniLM-L6-v2'
- Verified Vector Dimension: 384
- Architecture: 6-layer MiniLM transformer with mean pooling and L2 normalization
- Hardware & Resource Footprint: ~80MB parameter size; runs efficiently on standard CPU (<200MB RAM)
- Offline & Privacy Compliance: Self-contained weights, zero external cloud network egress, air-gapped compliant
- Licensing: Apache 2.0 (open-source, auditable, fully reproducible)

Provider Abstraction:
- SentenceTransformerEmbeddingProvider: Production inference using local PyTorch / sentence-transformers
- DeterministicMockEmbeddingProvider: Deterministic, unit-normalized 384-d float vector generator for
  fast, offline automated testing and CI/CD without heavy GPU/CUDA binaries.
"""
import math
import struct
import hashlib
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from app.core.config import settings
from app.core.errors import (
    EmbeddingGenerationException,
    EmbeddingModelLoadException,
    EmbeddingDimensionMismatchException,
)
from app.schemas.rag import DocumentChunk, EmbeddedChunk

logger = logging.getLogger("sakshi.rag.embedding")


class IEmbeddingProvider(ABC):
    """Abstract interface for dense text embedding models."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Canonical model identifier."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Expected output vector dimension."""
        pass

    @abstractmethod
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Compute normalized vector embeddings for a batch of strings."""
        pass


class DeterministicMockEmbeddingProvider(IEmbeddingProvider):
    """
    High-fidelity deterministic embedding provider for testing and offline environments.
    Generates unit-normalized (L2 norm = 1.0) float vectors with the exact target dimension (384)
    derived deterministically from cryptographic hashes of the input text.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        dimension: Optional[int] = None,
    ):
        self._model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._dimension = dimension or settings.EMBEDDING_DIMENSION

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        results: List[List[float]] = []
        for text in texts:
            results.append(self._generate_single(text))
        return results

    def _generate_single(self, text: str) -> List[float]:
        """
        Produces a deterministic, unit-normalized float vector of length `self.dimension`.
        """
        # Normalized text representation
        norm_text = text.strip().lower()
        base_hash = hashlib.sha256(norm_text.encode("utf-8")).digest()

        raw_components: List[float] = []
        # Expand 32-byte SHA-256 digest into 384 distinct float components
        for i in range(self.dimension):
            # Deterministic pseudo-random seed per dimension index
            h = hashlib.sha256(base_hash + struct.pack(">I", i)).digest()
            val = struct.unpack(">f", h[:4])[0]
            if math.isnan(val) or math.isinf(val):
                val = 0.5
            raw_components.append(val)

        # Apply L2 unit normalization (standard for cosine similarity)
        norm = math.sqrt(sum(x * x for x in raw_components)) or 1.0
        normalized_vector = [round(x / norm, 6) for x in raw_components]

        return normalized_vector


class SentenceTransformerEmbeddingProvider(IEmbeddingProvider):
    """
    Production embedding provider using local sentence-transformers model weights.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        dimension: Optional[int] = None,
    ):
        self._model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self._dimension = dimension or settings.EMBEDDING_DIMENSION
        self._model = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info("Loading SentenceTransformer model '%s'...", self._model_name)
                # Case evidence must never trigger a model download or external request.
                # Production deployers provision weights locally before enabling this provider.
                self._model = SentenceTransformer(self._model_name, local_files_only=True)
            except ImportError as ie:
                raise EmbeddingModelLoadException(
                    f"sentence-transformers package is not installed: {ie}. "
                    "Install sentence-transformers or configure EMBEDDING_PROVIDER='deterministic_mock'."
                )
            except Exception as e:
                raise EmbeddingModelLoadException(
                    f"Failed to load embedding model weights for '{self._model_name}': {type(e).__name__}: {e}"
                )

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        self._load_model()
        try:
            # Generate L2-normalized embeddings
            embeddings = self._model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            # Convert numpy array or tensor to standard Python float lists
            return [[float(x) for x in vec] for vec in embeddings]
        except Exception as e:
            raise EmbeddingGenerationException(
                f"SentenceTransformer inference failed: {type(e).__name__}: {e}"
            )


class EmbeddingService:
    """
    Orchestration service for generating and validating vector embeddings for evidence chunks.
    """

    def __init__(self, provider: Optional[IEmbeddingProvider] = None):
        if provider is not None:
            self.provider = provider
        else:
            # Select provider based on application configuration
            if settings.EMBEDDING_PROVIDER == "sentence_transformer":
                self.provider = SentenceTransformerEmbeddingProvider()
            elif settings.EMBEDDING_PROVIDER == "deterministic_mock":
                if settings.ENVIRONMENT.lower() == "production":
                    raise EmbeddingModelLoadException(
                        "Deterministic mock embeddings are disabled in production. "
                        "Configure a locally provisioned sentence_transformer provider."
                    )
                self.provider = DeterministicMockEmbeddingProvider()
            else:
                raise EmbeddingModelLoadException(
                    "Unsupported EMBEDDING_PROVIDER configuration. "
                    "Use 'sentence_transformer' with local weights or 'deterministic_mock' only outside production."
                )

    @property
    def model_name(self) -> str:
        return self.provider.model_name

    @property
    def dimension(self) -> int:
        return self.provider.dimension

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding vector for a single string query or passage."""
        cleaned = text.strip()
        if not cleaned:
            raise EmbeddingGenerationException("Cannot generate embedding for empty text string.")

        results = self.provider.generate_embeddings([cleaned])
        if not results or len(results) != 1:
            raise EmbeddingGenerationException("Provider failed to return expected embedding vector.")

        vector = results[0]
        self._validate_vector(vector)
        return vector

    def embed_chunks(self, chunks: List[DocumentChunk]) -> List[EmbeddedChunk]:
        """
        Generate and validate vector embeddings for a list of document chunks.
        """
        if not chunks:
            return []

        # Extract text contents
        texts = [c.content for c in chunks]

        try:
            raw_vectors = self.provider.generate_embeddings(texts)
        except Exception as e:
            logger.error("Embedding generation failed for %d chunks: %s", len(chunks), e)
            if isinstance(e, (EmbeddingGenerationException, EmbeddingModelLoadException)):
                raise
            raise EmbeddingGenerationException(f"Failed to compute embeddings: {e}")

        if len(raw_vectors) != len(chunks):
            raise EmbeddingGenerationException(
                f"Vector count mismatch: generated {len(raw_vectors)} vectors for {len(chunks)} chunks."
            )

        embedded_chunks: List[EmbeddedChunk] = []
        for chunk, vector in zip(chunks, raw_vectors):
            self._validate_vector(vector)
            embedded_chunks.append(
                EmbeddedChunk(
                    chunk=chunk,
                    embedding=vector,
                    embedding_model=self.model_name,
                )
            )

        logger.info(
            "Computed %d embeddings with model '%s' (dim=%d)",
            len(embedded_chunks),
            self.model_name,
            self.dimension,
        )
        return embedded_chunks

    def _validate_vector(self, vector: List[float]) -> None:
        """Validates length and values of vector embedding."""
        if len(vector) != self.dimension:
            raise EmbeddingDimensionMismatchException(
                f"Vector dimension mismatch: expected {self.dimension}, got {len(vector)}."
            )

        for val in vector:
            if math.isnan(val) or math.isinf(val):
                raise EmbeddingGenerationException("Generated embedding contains NaN or Inf components.")
