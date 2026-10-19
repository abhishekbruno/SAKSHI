# SAKSHI — Comprehensive RAG Implementation Audit, Verification & Gap Analysis

**Date:** October 20, 2026  
**Auditor:** Antigravity AI  
**Scope:** RAG Phases 0–4 (Architecture, Database, Migrations, Indexing, Retrieval, Security Gates, HTTP API, Frontend, and Phase 5 Readiness)  
**Methodology:** Read-only code inspection, static analysis, live automated test execution, and connection diagnostics.

---

## Executive Summary

A comprehensive, evidence-based audit of the Retrieval-Augmented Generation (RAG) subsystem in the SAKSHI repository was conducted. 

### Key Audit Findings:
1. **RAG Core Implementation (Phases 0–4):** Fully implemented in Python/FastAPI and SQLAlchemy. All core services (`TextExtractionService`, `ChunkingService`, `EmbeddingService`, `RAGIndexingService`, `RAGRetrievalService`, `RAGRepository`) and API endpoints (`POST /api/v1/cases/{case_id}/rag/search`) are present and operational under SQLite.
2. **Resolution of Previous Test Blocker:** The historical report (`RAG_PHASE_4_IMPLEMENTATION_REPORT.md`) claimed that the 6 HTTP API integration tests were unexecuted due to Windows asynchronous socket initialization failures. In this audit, **all 6 HTTP API tests executed and passed cleanly in 0.54s**, and the full repository test suite (**406 tests**) passed without a single failure or skipped test.
3. **Dual-Hash Provenance Hardening:** Verified that `backend/app/repositories/rag_repository.py` strictly enforces matching SHA-256 and SHA3-512 hashes across `RAGChunk`, `RAGDocument`, and `Evidence`.
4. **PostgreSQL + pgvector Reality:** Fully coded in Alembic migration `002_create_rag_tables.py`, `backend/app/models/vector_type.py` (`CompatibleVector`), and `RAGRepository.search_eligible_chunks_postgres`. However, **live execution is UNVERIFIED and BLOCKED** due to the absence of a running PostgreSQL daemon, `psql`, or Docker on this Windows host.
5. **Phase 5 (RAG-to-LLM Boundary):** **COMPLETELY MISSING**. No LLM providers (Gemini, OpenAI, Anthropic, Ollama), prompt construction, answer generation, claim-to-source mapping, or citation validators exist in the codebase.
6. **Frontend Integration:** **COMPLETELY MISSING / PLACEHOLDER**. The frontend (`frontend/app.js`) contains zero references or API calls to `/rag`. Existing analysis screens render mock data.

---

## 1. Repository Inspection & Working Tree State

Inspection confirmed the following file paths and working tree states:

### 1.1 Uncommitted Working Tree State (Preserved Intact)
The working tree contains ongoing uncommitted modifications from the IAM & Firebase authentication module:
- Modified: `backend/app/api/deps.py`, `backend/app/api/v1/auth.py`, `backend/app/main.py`, `backend/app/models/__init__.py`, `backend/app/services/auth_service.py`, `backend/app/services/authorization_service.py`, `backend/requirements.txt`, `backend/tests/conftest.py`, `frontend/app.js`, `frontend/index.html`, `frontend/style.css`.
- New Untracked/Staged: `backend/app/api/v1/iam.py`, `backend/app/models/officer.py`, `backend/app/models/organization.py`, `backend/app/models/case_assignment.py`, `backend/app/repositories/iam_repository.py`, `backend/app/schemas/iam.py`, `backend/app/services/firebase_auth_service.py`, `backend/app/services/iam_service.py`, `backend/migrations/versions/003_iam_officers_and_assignments.py`, `backend/tests/unit/test_firebase_auth_service.py`, `backend/tests/unit/test_username_generation.py`, `backend/tests/integration/test_iam_api.py`.
- **Database Preservation:** Both SQLite databases (`sakshi_cases.db` at workspace root and `backend/sakshi_cases.db`) were preserved with zero destructive operations, resets, or migrations.

### 1.2 Actual RAG File Locations
| Subsystem Component | Actual File Path | Lines |
|---|---|---|
| Database Configuration | `backend/app/core/config.py` | 136 |
| Database Engine & Session | `backend/app/db/session.py` | 46 |
| Connection Diagnostics | `backend/app/db/verify_connection.py` | 89 |
| Setup Documentation | `backend/docs/POSTGRESQL_SETUP.md` | 165 |
| Baseline Migration | `backend/migrations/versions/001_baseline_schema.py` | 132 |
| RAG Tables Migration | `backend/migrations/versions/002_create_rag_tables.py` | 158 |
| Dual-Dialect Vector Type | `backend/app/models/vector_type.py` | 57 |
| RAGDocument Model | `backend/app/models/rag_document.py` | 65 |
| RAGChunk Model | `backend/app/models/rag_chunk.py` | 75 |
| RAGIndexJob Model | `backend/app/models/rag_index_job.py` | 68 |
| RAG Pydantic Schemas | `backend/app/schemas/rag.py` | 147 |
| RAG Persistence Repository | `backend/app/repositories/rag_repository.py` | 252 |
| Text Extraction Service | `backend/app/services/text_extraction_service.py` | 345 |
| Chunking Service | `backend/app/services/chunking_service.py` | 163 |
| Embedding Service | `backend/app/services/embedding_service.py` | 267 |
| RAG Indexing Service | `backend/app/services/rag_indexing_service.py` | 194 |
| RAG Retrieval Service | `backend/app/services/rag_retrieval_service.py` | 215 |
| RAG Search API Route | `backend/app/api/v1/rag.py` | 26 |
| FastAPI Application Wiring | `backend/app/main.py` | 113 |
| RAG Unit Tests | `backend/tests/unit/test_rag_*.py` | 6 files |
| RAG API Integration Tests | `backend/tests/integration/test_rag_search_api.py` | 128 |

---

## 2. Audit of RAG Phase 0 — Repository & Database Readiness

- **Database URL Configuration:** `settings.DATABASE_URL` defaults to `sqlite:///./sakshi_cases.db`. For PostgreSQL, it dynamically builds `postgresql+psycopg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}`.
- **Engine Configuration & Connection Pooling:**
  - SQLite: Configured with `StaticPool` and `check_same_thread=False` for in-memory and file-based testing.
  - PostgreSQL: Configured with production pooling parameters: `pool_size=5` (configurable via `DB_POOL_SIZE`), `max_overflow=10`, `pool_timeout=30`, `pool_recycle=1800`, and `pool_pre_ping=True` (liveness probing).
- **Startup Schema Safety:** `app/main.py` lifespan explicitly restricts `Base.metadata.create_all()` to non-production SQLite environments. When running against PostgreSQL or in production (`settings.ENVIRONMENT == "production"`), automatic schema creation is bypassed; schemas must be managed exclusively via Alembic migrations.
- **Dual Database Files:**
  - `C:\main project\sakshi_cases.db`: 208,896 bytes (Last modified: 2026-10-17 21:20:24)
  - `C:\main project\backend\sakshi_cases.db`: 217,088 bytes (Last modified: 2026-10-13 15:54:17)
  Both databases contain pre-existing case and evidence records and were left untouched.
- **Native Database Verification Status:** Running `python app/db/verify_connection.py` reports:
  - Database dialect: `sqlite` (v3.49.1)
  - pgvector Ready: `False`
  - Cause: Host lacks PostgreSQL server, `psql`, and Docker runtime. Native PostgreSQL verification is **BLOCKED BY ENVIRONMENT**.

---

## 3. Audit of RAG Phase 1 — PostgreSQL and pgvector Configuration

- **Driver Dependencies:** `psycopg` (v3.3.6) and `pgvector` (v0.5.1) are installed in `.venv`. The connection string format correctly utilizes the modern `postgresql+psycopg://` dialect identifier.
- **Vector-Type Compatibility (`CompatibleVector`):** Defined in `backend/app/models/vector_type.py` as a SQLAlchemy `TypeDecorator`:
  - When dialect is `postgresql`: Delegates directly to `pgvector.sqlalchemy.Vector(dim)`.
  - When dialect is `sqlite`: Compiles to SQLAlchemy `JSON()` and serializes float vectors into JSON lists.
- **SQLite Fallback Transparency:** The system explicitly guards against mistaking JSON lists for native vector operations. `RAGRetrievalService._retrieve_candidates` checks `db.get_bind().dialect.name`. When `sqlite` is detected, it labels `retrieval_mode` as `"sqlite_bounded_development_fallback"`, fetches a bounded candidate set (`RAG_SQLITE_RETRIEVAL_CANDIDATE_LIMIT=200`), and computes cosine similarity in Python. On `postgresql`, it routes to `search_eligible_chunks_postgres` with native `<->` / cosine distance.
- **Embedding Dimensions:** Centrally pinned to `settings.EMBEDDING_DIMENSION = 384` matching `sentence-transformers/all-MiniLM-L6-v2`.

---

## 4. Audit of RAG Phase 2 — Schema & Migrations

### 4.1 Schema Definitions (`rag_documents`, `rag_chunks`, `rag_index_jobs`)
- **Foreign Keys & Referential Integrity:**
  - `rag_documents`: `case_id -> cases.case_id`, `evidence_id -> evidence.evidence_id`.
  - `rag_chunks`: `document_id -> rag_documents.document_id`, `case_id -> cases.case_id`, `evidence_id -> evidence.evidence_id`.
  - `rag_index_jobs`: `document_id -> rag_documents.document_id`, `case_id -> cases.case_id`, `evidence_id -> evidence.evidence_id`.
- **Uniqueness Constraints:**
  - `uq_rag_document_evidence_version`: Ensures only one active document record exists per evidence exhibit per processing version (prevents re-indexing collisions).
  - `uq_rag_chunk_doc_index_version`: Ensures chunk index sequence uniqueness per document version.
- **Indexes:**
  - Relational indexes on all foreign keys and status columns.
  - Composite indexes: `ix_rag_chunks_case_evidence` (`case_id`, `evidence_id`), `ix_rag_documents_case_status` (`case_id`, `indexing_status`), `ix_rag_jobs_case_status` (`case_id`, `status`).
  - HNSW Index: In `002_create_rag_tables.py`, PostgreSQL creates:
    `CREATE INDEX IF NOT EXISTS ix_rag_chunks_embedding ON rag_chunks USING hnsw (embedding vector_cosine_ops);`
- **Migration Verification:** Tested on SQLite via `tests/unit/test_rag_schema.py::test_migration_execution_and_downgrade_on_sqlite` and `test_migration_preserves_preexisting_data`. Both passed. PostgreSQL execution remains unverified due to environment constraints.

---

## 5. Audit of RAG Phase 3 — Extraction, Chunking, Embeddings & Indexing

### 5.1 Text Extraction (`TextExtractionService`)
- **Supported Formats:** PDF (native text extracted via `pypdf.PdfReader`) and plain text/tabular (`.txt`, `.md`, `.csv` with UTF-8/Latin-1 decoding).
- **Unsupported Formats (Explicitly Identified):**
  - **Scanned / Image-Only PDFs:** No OCR engine (e.g. Tesseract) is integrated. Text extraction returns empty strings.
  - **Images:** `.png`, `.jpg`, `.tiff` are rejected with `UnsupportedDocumentFormatException`.
  - **Audio/Video:** Forensics audio/video files are rejected.
- **Security Gates (MOD-07 through MOD-11):** Fail-closed enforcement:
  - MOD-07: Antivirus status must not be `INFECTED` or `QUARANTINED`.
  - MOD-08: Evidence status must be `COMMITTED` (WORM state).
  - MOD-09: Integrity status must be `VERIFIED` with valid SHA-256 and SHA3-512 digests matching authoritative records.
  - MOD-10: Lock status must be `LOCKED`.
  - MOD-11: Encrypted exhibits are decrypted entirely in-memory via `EncryptionService.decrypt_evidence_bytes`. Zero plaintext is written to temporary files.
- **Provenance Preservation:** Tracks page numbers and character counts for every extracted page. Authoritative disk files are opened read-only and never modified.

### 5.2 Chunking (`ChunkingService`)
- **Parameters:** Target chunk size = 500 characters, overlap = 100 characters, minimum chunk size = 30 characters.
- **Provenance Offsets:** Preserves exact `page_number`, `char_start`, and `char_end` relative to the extracted text.
- **Stable Identifiers:** Generates deterministic chunk identifiers: `SAKSHI-CHK-{doc_id_hash}-{chunk_idx:04d}`.

### 5.3 Embeddings (`EmbeddingService`)
- **Configured Model:** `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions).
- **Providers:**
  - `DeterministicMockEmbeddingProvider`: Unit-normalized (L2 norm = 1.0) 384-dimensional vectors derived deterministically from SHA-256 hash expansions.
  - `SentenceTransformerEmbeddingProvider`: Loads local weights with `local_files_only=True` (zero cloud egress).
- **Production Fail-Safe:** If `EMBEDDING_PROVIDER == "deterministic_mock"` while `ENVIRONMENT == "production"`, `EmbeddingService` raises `EmbeddingModelLoadException`. Mock embeddings can **never** silently run in production.
- **Environment Status:** Neither `torch` nor `sentence-transformers` is installed in the current `.venv`. Production embeddings are **BLOCKED BY DEPENDENCY**.

### 5.4 Indexing Pipeline (`RAGIndexingService`)
- **Lifecycle:** Manages `RAGIndexJob` through `PENDING -> RUNNING -> COMPLETED` (or `FAILED` with error code and traceback).
- **Idempotency:** Re-indexing an already `INDEXED` document returns the existing record immediately without re-processing.
- **Persistence:** Chunks and documents are persisted atomically in SQLAlchemy sessions.

---

## 6. Audit of RAG Phase 4 — Retrieval, Search API & Case Isolation

### 6.1 Search API Endpoint
`POST /api/v1/cases/{case_id}/rag/search`
- **Authentication:** Enforced via FastAPI dependency `Depends(get_current_investigator)`. Unauthenticated requests yield `401 Unauthorized`.
- **MOD-03 Authorization:** Enforces investigator case assignment, station, and jurisdiction permissions before embedding generation or database querying.
- **Anti-Oracle Response Uniformity:** Querying an unauthorized case or a non-existent case yields an identical `403 Forbidden` response (`error_code: FORBIDDEN`), preventing case-existence enumeration.
- **Query Validation:** Enforces non-blank strings, max length 2,000 characters, and limit range `[1, 20]`. Non-compliant inputs yield `422 Unprocessable Content`.

### 6.2 SQL Defense-in-Depth & Case Isolation
In `backend/app/repositories/rag_repository.py` (`_eligible_chunk_query`), retrieval executes under redundant SQL predicates:
- `RAGChunk.case_id == case_id`, `RAGDocument.case_id == case_id`, `Evidence.case_id == case_id`.
- Re-binds `RAGChunk.case_id == RAGDocument.case_id` and `RAGChunk.case_id == Evidence.case_id`.
- Enforces MOD-09 Dual-Hash Provenance:
  ```python
  RAGChunk.source_sha256 == RAGDocument.source_sha256,
  RAGDocument.source_sha256 == Evidence.checksum_sha256,
  RAGChunk.source_sha3_512.is_not(None),
  RAGDocument.source_sha3_512.is_not(None),
  Evidence.checksum_sha3_512.is_not(None),
  RAGChunk.source_sha3_512 == RAGDocument.source_sha3_512,
  RAGDocument.source_sha3_512 == Evidence.checksum_sha3_512,
  ```
- Excludes stale or failed indexing jobs via correlated subquery selecting `latest_job_id` with `status == 'COMPLETED'`.
- Enforces active evidence security gates (`antivirus_status == 'CLEAN'`, `worm_status == 'COMMITTED'`, `integrity_status == 'VERIFIED'`, `lock_status == 'LOCKED'`).

### 6.3 Audit Privacy Hygiene
`AuditIntegrationService.record_event` logs: `investigator_id`, `case_id`, `action='RAG_RETRIEVAL'`, `outcome`, `result_count`, and `retrieval_mode`.
**Verified:** Raw query strings, evidence passages, embeddings, and decrypted byte counts are strictly omitted from audit logs. Note: Audit logging is a structured database logger, not an append-only cryptographic ledger.

---

## 7. Verification of All Outstanding Test Claims

### 7.1 Re-Verification of Historical Claims
The previous report (`RAG_PHASE_4_IMPLEMENTATION_REPORT.md`) recorded:
- 28 focused RAG tests passed.
- 6 RAG API tests collected but unexecuted due to Windows async socket errors.
- Full suite blocked by timeout.
- 375 total tests collected.

### 7.2 Current Live Test Execution Results
All test suites were executed live using `.venv\Scripts\pytest.exe`:

| Test Suite / Command | Scope | Result | Execution Time |
|---|---|---|---|
| `pytest tests/integration/test_rag_search_api.py -v` | RAG HTTP Search API | **6 PASSED**, 0 failed | 0.54s |
| `pytest tests/unit/test_rag_retrieval_service.py tests/unit/test_embedding_service.py -v` | Retrieval & Embeddings | **28 PASSED**, 0 failed | 0.94s |
| `pytest tests/unit/test_rag_*.py tests/unit/test_embedding_service.py tests/unit/test_chunking_service.py tests/unit/test_text_extraction_service.py tests/integration/test_rag_search_api.py -v` | All RAG Components (7 files) | **69 PASSED**, 0 failed | 4.59s |
| `pytest` | Full Repository Test Suite | **406 PASSED**, 0 failed, 0 skipped | 26.65s |

### 7.3 Breakthrough Finding: Socket Blocker Disproven
The previously reported Windows async socket initialization hang **does not reproduce**. All 6 HTTP integration tests (`test_rag_search_api.py`) executed synchronously against FastAPI's `TestClient` and passed without issues.

---

## 8. Audit of RAG-to-LLM Boundary (Phase 5)

**Status: COMPLETELY MISSING.**
- **LLM Providers:** No SDKs or HTTP clients for OpenAI, Anthropic, Google Gemini, Ollama, or vLLM exist in `requirements.txt` or `app/services/`.
- **Context Assembly & Prompt Construction:** No prompt templates or context assembly services exist.
- **Citation Validation & Claim Verification:** No algorithms exist to map generated answer sentences to chunk IDs or verify that claims are supported by retrieved text.
- **Refusal Guardrails:** No mechanisms exist to detect insufficient evidence or refuse ungrounded queries.
- **Contract Adequacy:** The existing `RAGSearchResponse` schema provides an ideal contract (`chunk_id`, `passage`, `page_number`, `char_start`, `char_end`, `source_sha256`, `source_sha3_512`, `similarity_score`). Phase 5 can be implemented directly on top of this output without modifying Phase 0–4 schemas.

---

## 9. Integration with SAKSHI's 17-Phase Architecture

| Architecture Layer | SAKSHI Phase | Current Integration Status | Integration Interface & Details |
|---|---|---|---|
| Case Management | Phase 1 (MOD-01) | **Integrated** | Relational foreign keys to `cases.case_id`; case lifecycle stage checks. |
| Identity & Auth | Phase 2 (MOD-02) | **Integrated** | `AuthenticatedInvestigator` required on all extraction and retrieval paths. |
| Access Control | Phase 3 (MOD-03) | **Integrated** | `authorization_service.check_can_read_evidence` enforced before retrieval. |
| Stage Engine | Phase 4 (MOD-04) | **Integrated** | Verifies case is in active stage (`EVIDENCE_PROCESSING`). |
| Evidence Security | Phases 5–11 (MOD-05–11) | **Integrated** | Antivirus, WORM, Dual-Hashing, Object Lock, AES-256-GCM enforced as SQL eligibility filters. |
| RAG Retrieval | Phase 12 | **Implemented (SQLite)** | Provenance-traceable passage retrieval. PostgreSQL unverified. |
| Grounded Generation | Phase 13 | **Missing** | No LLM answer generation or citation validation. |
| Structured Memory | Phase 14 | **Missing** | No bridge between retrieved chunks and structured case entity memory. |
| Knowledge Graph | Phase 15 | **Missing** | No entity/relation extraction from RAG chunks into graph structures. |
| Timeline Reconstruction | Phase 16 | **Missing** | No temporal extraction from RAG chunks into forensic timelines. |
| Investigative Gap Engine | Phase 17 | **Missing** | No discrepancy detection between retrieved evidence and case claims. |

---

## 10. Audit of Frontend Integration

**Status: MISSING / PLACEHOLDER.**
- An exhaustive scan of `frontend/app.js` and `frontend/index.html` confirmed **zero calls** to `/api/v1/cases/{case_id}/rag/search`.
- Analysis views in `app.js` (`ScreenAnalysis`, `ScreenGaps`, `ScreenTimeline`) render static mock cards and hardcoded metrics.
- The UI currently provides no interface for investigators to input search queries, view retrieved evidence passages, inspect citation offsets, or review similarity scores.

---

## 11. Comprehensive Implementation Status Matrix

| # | Component | Required Behavior | Actual Implementation | Status | Verification Evidence | Remaining Work |
|---|---|---|---|---|---|---|
| 1 | PostgreSQL Configuration | Configurable pool, dialect check, fallback handling | `app/core/config.py`, `app/db/session.py` | `COMPLETE AND VERIFIED` | `test_db_config.py`, `test_rag_schema.py` | None for config; runtime verification pending live DB. |
| 2 | pgvector Extension & Native Search | Native `vector(384)`, `<->` cosine distance, HNSW index | `002_create_rag_tables.py`, `rag_repository.py` | `IMPLEMENTED BUT UNVERIFIED` | Code inspection; `verify_connection.py` | Run migrations & queries on live PostgreSQL. |
| 3 | Database Migrations | Idempotent schema upgrades & downgrades | `001_baseline_schema.py`, `002_create_rag_tables.py` | `COMPLETE AND VERIFIED` (SQLite) / `UNVERIFIED` (PG) | `test_migration_execution_and_downgrade_on_sqlite` passed | Execute `alembic upgrade head` on PostgreSQL. |
| 4 | RAG Schema & Constraints | Document, chunk, job schemas, FKs, unique constraints | `rag_document.py`, `rag_chunk.py`, `rag_index_job.py` | `COMPLETE AND VERIFIED` | 16 tests in `test_rag_schema.py` passed | None. |
| 5 | Text Extraction | Extract text from PDF & text files, preserve pages | `text_extraction_service.py` (PyPDF, direct text) | `COMPLETE AND VERIFIED` | 11 tests in `test_text_extraction_service.py` passed | OCR integration for scanned PDFs/images (future). |
| 6 | Chunking & Provenance | Bounded chunks (500 chars), offsets, page tracking | `chunking_service.py` | `COMPLETE AND VERIFIED` | 5 tests in `test_chunking_service.py` passed | None. |
| 7 | Production Embeddings | `all-MiniLM-L6-v2` local weights, 384 dims, no egress | `SentenceTransformerEmbeddingProvider` | `BLOCKED` | Code inspection | Install `sentence-transformers` & download weights. |
| 8 | Mock Embeddings & Safeguards | Deterministic 384-d L2 vectors; fail-safe in prod | `DeterministicMockEmbeddingProvider` | `COMPLETE AND VERIFIED` | 10 tests in `test_embedding_service.py` passed | None. |
| 9 | Indexing Service | Job state transitions, idempotency, persistence | `rag_indexing_service.py` | `COMPLETE AND VERIFIED` (SQLite) | 3 tests in `test_rag_indexing_service.py` passed | Execute indexing against live PostgreSQL. |
| 10 | Evidence-Security Gates | Enforce AV, WORM, Dual-Hash, Lock, Decryption | Gates in `TextExtractionService` and `RAGRepository` | `COMPLETE AND VERIFIED` | Unit & API tests verify rejection on gate failure | None. |
| 11 | Retrieval Service | Case-scoped candidate filtering & score calculation | `rag_retrieval_service.py` | `COMPLETE AND VERIFIED` (SQLite) | 18 tests in `test_rag_retrieval_service.py` passed | Execute on live pgvector. |
| 12 | Case Isolation | Strict SQL filtering preventing cross-case leakage | Redundant SQL predicates in `rag_repository.py` | `COMPLETE AND VERIFIED` | `test_cross_case_search_is_denied` passed | None. |
| 13 | Authorization | MOD-03 check before embedding & retrieval; anti-oracle | `check_can_read_evidence`, uniform 403 on absent/denied | `COMPLETE AND VERIFIED` | `test_unknown_case_uses_the_same_safe_denial_shape` passed | None. |
| 14 | Citation/Provenance Output | Output chunk ID, page, offsets, source hashes | `RAGSearchResult` schema | `COMPLETE AND VERIFIED` | `test_authenticated_search_returns_traceable_schema` passed | None. |
| 15 | HTTP Search API | `POST /api/v1/cases/{case_id}/rag/search` | `app/api/v1/rag.py` mounted in `main.py` | `COMPLETE AND VERIFIED` | 6 tests in `test_rag_search_api.py` passed | None. |
| 16 | API Integration Tests | Real HTTP request/response validation | `test_rag_search_api.py` | `COMPLETE AND VERIFIED` | 6 of 6 tests executed & passed in 0.54s | None. |
| 17 | Full Regression Tests | Ensure no regressions across case, evidence, IAM | Pytest full suite | `COMPLETE AND VERIFIED` | 406 of 406 tests passed in 26.65s | None. |
| 18 | Frontend Integration | UI query input, passage & citation display | None | `MISSING` | `grep` confirmed zero calls to `/rag` | Implement RAG Search screen in `frontend/app.js`. |
| 19 | LLM Answer Generation | Evidence-constrained generation, prompt construction | None | `MISSING` | Code inspection | Build Phase 5 LLM service & prompt engine. |
| 20 | Citation Validation | Automated claim-to-source citation verification | None | `MISSING` | Code inspection | Build citation validator & hallucination refusal. |
| 21 | Reasoning-Layer Integration | Connect RAG to Memory, KG, Timeline, Gap Engine | None | `MISSING` | Code inspection | Build reasoning bridges for Phases 14–17. |
| 22 | Audit & Security Verification | Safe structured audit logging; zero secret leakage | `AuditIntegrationService` in retrieval flow | `COMPLETE AND VERIFIED` | `test_search_audit_does_not_record_query_or_passage` passed | Immutable append-only ledger (future). |
| 23 | Deployment Readiness | Production DB, packages, local weights, runner | Configured in code; runtime missing | `BLOCKED` | Environment diagnostics (`verify_connection.py`) | Provision PostgreSQL container and model weights. |

---

## 12. Transparent Completion Calculations

Completion is calculated across 7 explicit dimensions, distinguishing implementation progress from verification progress.

| Dimension | Implementation | Verification | Weighted Formula | Dimension Score |
|---|---|---|---|---|
| **1. RAG Database Readiness** | 100% (PostgreSQL + SQLite code complete) | 50% (SQLite verified; PostgreSQL unverified) | `0.5 * Impl + 0.5 * Verif` | **75.0%** |
| **2. Indexing Pipeline** | 90% (Extraction, chunking, mock done; ST uninstalled) | 75% (Tested on SQLite with mock; ST/PG unverified) | `0.5 * Impl + 0.5 * Verif` | **82.5%** |
| **3. Retrieval Implementation** | 100% (Full logic, gates, dual-hash, SQL predicates) | 100% (Architecture complete) | `1.0 * Impl` | **100.0%** |
| **4. Retrieval Verification** | 100% (All test suites written) | 75% (SQLite unit & API passed; PG unexecuted) | `1.0 * Verif` | **75.0%** |
| **5. Frontend Integration** | 0% (No UI components or API calls) | 0% (Unverified) | `0.5 * Impl + 0.5 * Verif` | **0.0%** |
| **6. LLM Generation & Citation (Phase 5)** | 0% (No LLM or citation validation code) | 0% (Unverified) | `0.5 * Impl + 0.5 * Verif` | **0.0%** |

### Overall Readiness Calculations:
1. **RAG Phases 0–4 Scope (Retrieval Engine Readiness):**  
   Weights: Database Readiness (25%), Indexing Pipeline (25%), Retrieval Implementation (25%), Retrieval Verification (25%):  
   $$\text{Score} = (0.25 \times 75.0\%) + (0.25 \times 82.5\%) + (0.25 \times 100.0\%) + (0.25 \times 75.0\%) = \mathbf{83.1\%}$$

2. **Full End-to-End System Scope (Phases 0–5 + Frontend Integration):**  
   Weights: Database (15%), Indexing (20%), Retrieval Impl (20%), Retrieval Verif (15%), Frontend (10%), LLM/Citation (20%):  
   $$\text{Score} = (0.15 \times 75.0) + (0.20 \times 82.5) + (0.20 \times 100.0) + (0.15 \times 75.0) + (0.10 \times 0.0) + (0.20 \times 0.0) = \mathbf{59.0\%}$$

---

## 13. Prioritized Gap-Closure Plan

### Phase 4 Hardening & Environment Verification (Pre-requisite to Production)
- **GAP-1: Live PostgreSQL + pgvector Verification**
  - **Priority:** P1
  - **Files:** `backend/app/db/verify_connection.py`, `backend/migrations/versions/002_create_rag_tables.py`
  - **Action:** Provision disposable PostgreSQL 16 container with `pgvector/pgvector:pg16`. Execute `alembic upgrade head`. Test HNSW index creation, cosine ordering, and `EXPLAIN (ANALYZE, BUFFERS)` with synthetic 384-d vectors.
  - **Acceptance Criteria:** `verify_connection.py` reports `pgvector Ready: True`.
- **GAP-2: Production Embedding Model Provisioning**
  - **Priority:** P2
  - **Files:** `backend/requirements.txt`, `backend/app/services/embedding_service.py`
  - **Action:** Install `sentence-transformers` in virtual environment. Pre-download weights for `sentence-transformers/all-MiniLM-L6-v2` into a local model cache directory. Verify `SentenceTransformerEmbeddingProvider` runs inference with `local_files_only=True`.
  - **Acceptance Criteria:** Unit tests run successfully with `EMBEDDING_PROVIDER="sentence_transformer"`.

### Phase 5 Implementation (Grounded Generation & Citation Validation)
- **GAP-3: Citation-Constrained Answer Generation Service**
  - **Priority:** P3
  - **Files:** `backend/app/services/rag_generation_service.py`, `backend/app/schemas/rag.py`
  - **Action:** Implement answer generation service consuming `RAGSearchResponse`. Formulate strict prompts forbidding ungrounded claims. Every assertion must cite a valid `[chunk_id]`.
  - **Acceptance Criteria:** Generates structured answers with inline citations.
- **GAP-4: Automated Citation Validator & Hallucination Guardrail**
  - **Priority:** P4
  - **Files:** `backend/app/services/citation_validator_service.py`
  - **Action:** Implement post-generation validator that maps each generated claim against cited chunk passages. If a claim lacks lexical/semantic grounding, reject or flag the answer with `INSUFFICIENT_EVIDENCE`.
  - **Acceptance Criteria:** 100% of claims are anchored to verified exhibit text.

### Frontend Integration
- **GAP-5: Evidence Retrieval & Citation Inspector UI**
  - **Priority:** P5
  - **Files:** `frontend/app.js`, `frontend/index.html`, `frontend/style.css`
  - **Action:** Add a "Forensic Evidence Search" tab in the Case Workspace. Wire `POST /api/v1/cases/{case_id}/rag/search` to an interactive search input. Render retrieved passages with source exhibit name, page number, character offsets, similarity score badge, and dual-hash verification status.
  - **Acceptance Criteria:** Investigators can perform searches and inspect citations directly in the browser.

---

## 14. Explicit Direct Answers to the 9 Mandatory Questions

1. **Is RAG currently functional?**  
   **Yes, within the SQLite development environment.** Evidence exhibits meeting security gates MOD-07 through MOD-11 can be indexed and searched via `RAGRetrievalService` and the HTTP API (`POST /api/v1/cases/{case_id}/rag/search`). It is **not** yet functional in production due to unprovisioned PostgreSQL/pgvector and missing local model weights.
2. **Which parts have been verified through actual execution?**  
   - SQLite migrations and schemas (16 tests passed).
   - Text extraction (PDF native + plaintext) with zero disk leakage under MOD-11 (11 tests passed).
   - Chunking with sliding window and character offsets (5 tests passed).
   - Mock embeddings, L2 normalization, dimension validation, and production safeguards (10 tests passed).
   - RAG indexing lifecycle and idempotency on SQLite (3 tests passed).
   - RAG retrieval service, security gates, dual-hash (SHA-256 + SHA3-512) provenance, and case isolation (18 tests passed).
   - HTTP API integration tests (6 tests passed).
   - Full repository regression suite (406 tests passed).
3. **Can PostgreSQL/pgvector retrieval be considered verified?**  
   **No.** The code is fully written, but execution on live PostgreSQL with pgvector is UNVERIFIED and BLOCKED because no PostgreSQL instance or Docker container is available on this host.
4. **Has the actual HTTP API been tested?**  
   **Yes.** All 6 integration tests in `backend/tests/integration/test_rag_search_api.py` were executed against FastAPI's `TestClient` and passed in 0.54s. The previous async socket hang did not reproduce.
5. **Is RAG integrated with an LLM?**  
   **No.** There are zero LLM client libraries, prompt templates, or generation services in the repository.
6. **Is citation validation implemented?**  
   **No.** Citation metadata (page numbers, character offsets, chunk IDs, source hashes) is faithfully captured and returned by retrieval, but automated claim-to-source validation algorithms do not yet exist.
7. **Is the frontend connected to real RAG retrieval?**  
   **No.** `frontend/app.js` contains zero references or API calls to `/rag`. Existing analysis views render mock data.
8. **Is the system ready for Phase 5?**  
   **Yes for development on SQLite, but Pending Verification for production.** The retrieval service and HTTP API provide a comprehensive, provenance-rich schema contract (`RAGSearchResponse`) suitable for Phase 5 generation. However, PostgreSQL and local model weights must be provisioned before production deployment.
9. **What is the single best next step?**  
   **Provision a disposable PostgreSQL 16 + pgvector instance to execute migrations and verify the native vector retrieval path against real PostgreSQL.**
