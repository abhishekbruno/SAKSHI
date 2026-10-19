# SAKSHI — Phase 4 Verification and Hardening Report

## Final status: PARTIALLY VERIFIED

Phase 4 retrieval was inspected, hardened, and tested using the repository virtual environment. The SQLite service path, authorization ordering, case isolation, provenance checks, evidence gates, audit hygiene, configuration, and substantial existing security/evidence test subset pass. Full HTTP integration, full regression, and PostgreSQL/pgvector execution remain unverified because this host cannot initialize the asynchronous socket infrastructure required by TestClient and has neither Docker nor PostgreSQL tooling.

Neither existing SQLite database was deleted, overwritten, migrated, or otherwise modified. Their final sizes/timestamps remained `208,896 bytes / 2026-10-17 21:20:24` (`C:\main project\sakshi_cases.db`) and `217,088 bytes / 2026-10-13 15:54:17` (`backend\sakshi_cases.db`).

## Inspection findings

All requested Phase 4 files exist at their expected paths. The working tree already contained extensive user Phase 2–3 and frontend changes before this verification; they were preserved. Migration `002_create_rag_tables.py` creates `VECTOR(384)` embeddings and an HNSW `vector_cosine_ops` index for PostgreSQL, while SQLite uses JSON vectors. No new migration was needed.

## Defect found and fixed

Retrieval enforced SHA-256 consistency between `RAGChunk`, `RAGDocument`, and `Evidence`, but it did not require SHA3-512 consistency. This left a MOD-09 dual-hash provenance gap for rows with absent or mismatched SHA3 values.

`backend/app/repositories/rag_repository.py` now requires non-null, matching SHA-256 **and** SHA3-512 values across chunk, document, and evidence in the database eligibility query. This is fail-closed. Fixtures and tests now use synthetic SHA3 values and exercise mismatch exclusion.

## Environment and dependencies

- Python `3.12.10` via `backend/.venv/Scripts/python.exe`.
- FastAPI `0.142.1`, Starlette `1.7.0`, HTTPX `0.28.1`, AnyIO `4.15.1`.
- SQLAlchemy `2.1.1`, Alembic `1.20.0`, psycopg `3.3.6`, pgvector Python package `0.5.1`.
- `sentence-transformers` and Torch are not installed; no model weights were downloaded. Production remains configured to fail safely instead of falling back to mock vectors.
- Docker, `psql`, and `pg_isready` are unavailable on `PATH`.

Host Python lacks `pgvector`; the repository virtual environment has it. Tests must use the repository virtual environment.

## Test and static-check results

| Command | Exact result |
| --- | --- |
| `python -m pytest tests/unit/test_rag_retrieval_service.py tests/unit/test_embedding_service.py -q` | **28 passed**, 1 warning, 0.37s. Covers relevance, cross-case exclusion, each evidence gate, dual-hash mismatches, failed/running jobs, absent/wrong/non-finite vectors, provenance, audit hygiene, and authorization-before-embedding. |
| `TEMP=<workspace> TMP=<workspace> python -m pytest tests/unit/test_antivirus_scan_service.py tests/unit/test_integrity_service.py tests/unit/test_worm_commit_service.py tests/unit/test_encryption_service.py tests/unit/test_evidence_intake_service.py tests/unit/test_mime_validation_service.py tests/unit/test_rag_indexing_service.py tests/unit/test_rag_retrieval_service.py tests/unit/test_embedding_service.py -q` | **138 passed**, 1 warning, 3.31s. The workspace-local temporary directory resolved the prior `WinError 5` sandbox failure. |
| `python -m pytest tests/integration/test_rag_search_api.py --collect-only -q` | **6 collected**, not executed. |
| `TEMP=<workspace> TMP=<workspace> python -m pytest tests -x -q` | **Blocked** at the first HTTP test; no test result was produced before host timeout. |
| `python -m compileall -q app tests` | **Passed**. |
| `python -m pytest tests --collect-only -q` | **375 tests collected**, 0.37s. |

No lint/type-check configuration is present (`pyproject.toml`, `setup.cfg`, `tox.ini`, `.flake8`, `ruff.toml`, `mypy.ini`, and `Makefile` are absent). `git diff --check` found no whitespace errors in the hardening changes.

## HTTP test blocker assessment

This is an environment/tooling limitation, not an identified application defect or dependency incompatibility:

- `TestClient` blocks while AnyIO starts its background portal and the Windows Proactor creates an internal socket pair.
- An HTTPX in-process ASGI transport experiment also could not execute because the host blocks the same async runtime initialization.
- The compatible FastAPI/Starlette/HTTPX/AnyIO versions above were inspected; no dependency was changed blindly.
- Tests are intact and are not skipped or weakened. Run the six RAG API tests and full 375-test suite on an unrestricted runner, using a workspace-local `TEMP`/`TMP` where necessary.

## PostgreSQL + pgvector verification

**Not executed.** This host has no Docker engine, PostgreSQL client/server, or pgvector extension runtime. No native retrieval success is claimed.

Complete verification elsewhere with a disposable PostgreSQL+pgvector database: set a disposable `DATABASE_URL`, run `alembic upgrade head`, verify `vector(384)` and `ix_rag_chunks_embedding`/`vector_cosine_ops`, test repeated migrations, 384-dimensional inserts, cosine ordering, malformed vectors, and `EXPLAIN (ANALYZE, BUFFERS)` using synthetic data. Then exercise the actual HTTP route with two cases and separate authorized investigators.

## Security and correctness conclusions

- The registered route is `POST /api/v1/cases/{case_id}/rag/search` and requires the existing authentication dependency.
- MOD-03 `evidence:read` authorization runs before embedding or retrieval, retaining assignment, supervisory, and jurisdiction rules.
- SQL applies case, document, evidence, latest-job, and dual-hash relationship predicates before candidates are returned; matching Case B content was excluded from Case A service results.
- A candidate requires AV `CLEAN`, committed evidence/WORM state, integrity `VERIFIED`, object lock `LOCKED`, known encryption state, `INDEXED` document, latest `COMPLETED` job, valid embedding, and matching SHA-256/SHA3-512 provenance.
- Results preserve source IDs, stored filename, page/character offsets, original passage, metadata, and finite score. SQLite explicitly identifies its bounded development fallback.
- Audit records actor, case, outcome, count, mode, and safe error category; tests confirm it omits query and passage. This is a structured-log facade, **not** a tamper-evident append-only ledger.
- Retrieval does not decrypt, alter, or rewrite authoritative evidence.

## Files changed during hardening

- `backend/app/repositories/rag_repository.py` — dual-hash eligibility enforcement.
- `backend/tests/unit/test_rag_retrieval_service.py` — SHA3 fixtures plus gate/provenance/authorization/audit coverage.
- `backend/tests/integration/test_rag_search_api.py` — SHA3 fixtures for real-route tests.
- `backend/docs/POSTGRESQL_SETUP.md` and this report — actual verification findings.

## Outstanding evidence for VERIFIED

1. Run all six real Phase 4 HTTP tests and the complete 375-test suite on a host that permits AnyIO/asyncio socket initialization.
2. Provision disposable PostgreSQL + pgvector and execute migrations, native vector retrieval, HNSW/index inspection, query-plan, malformed-vector, and repeated-migration checks.
3. Record those exact results. Only then may Phase 4 be marked **VERIFIED**.
