# SAKSHI — PostgreSQL & pgvector Setup Guide
**Phase 1: Environment & Engine Preparation**  
**Paradigm: Evidence-Constrained Modus Operandi Reconstruction (EC-MORE)**

---

## 1. Overview

SAKSHI requires **PostgreSQL (v15+)** with the **pgvector** extension for Retrieval-Augmented Generation (RAG) and Structured Case Memory.

Co-locating relational forensic data (`Case`, `Evidence`, `ExhibitMetadata`) and vector embeddings (`EvidenceChunk`, `Vector`) within PostgreSQL ensures:
1. **Strict Evidentiary Grounding:** Every retrieved chunk is tied via foreign key to an exhibit with verified WORM SHA-256 and SHA3-512 hashes.
2. **ACID Transaction Boundaries:** Invalidation, locking, or updates to evidence items immediately cascade to vector chunks within the same database transaction.
3. **Multi-Tenant Case Boundary Isolation:** Vector searches strictly enforce relational case boundaries (`WHERE case_id = :case_id`), preventing cross-case information leakage.

---

## 2. Choosing an Installation Option

### Option A: Docker (Recommended for Rapid Setup & Testing)
Run an official PostgreSQL container with `pgvector` pre-installed:

```bash
docker run -d \
  --name sakshi-postgres \
  -e POSTGRES_DB=sakshi_cases \
  -e POSTGRES_USER=sakshi_user \
  -e POSTGRES_PASSWORD=your_secure_password \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

### Option B: Ubuntu / Debian Linux Server

1. **Install PostgreSQL 16 and pgvector:**
   ```bash
   sudo apt-get update
   sudo apt-get install -y postgresql-16 postgresql-contrib postgresql-server-dev-16

   # Install pgvector from official PostgreSQL repository
   sudo apt-get install -y postgresql-16-pgvector
   ```

2. **Initialize Database and Dedicated User:**
   ```bash
   sudo -u postgres psql
   ```
   ```sql
   CREATE DATABASE sakshi_cases;
   CREATE USER sakshi_user WITH ENCRYPTED PASSWORD 'your_secure_password';
   GRANT ALL PRIVILEGES ON DATABASE sakshi_cases TO sakshi_user;
   ALTER DATABASE sakshi_cases OWNER TO sakshi_user;
   \c sakshi_cases
   CREATE EXTENSION IF NOT EXISTS vector;
   GRANT ALL ON SCHEMA public TO sakshi_user;
   \q
   ```

### Option C: Windows Native (Local Workstation)

1. Download and run the **PostgreSQL 16 Windows Installer** from [EnterpriseDB](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads).
2. Install **pgvector** binary on Windows:
   - Download the precompiled Windows release matching your PostgreSQL version from [pgvector Releases](https://github.com/pgvector/pgvector/releases).
   - Copy `vector.dll` to `C:\Program Files\PostgreSQL\16\lib\`.
   - Copy `vector.control` and `vector--*.sql` to `C:\Program Files\PostgreSQL\16\share\extension\`.
3. Open `psql` or pgAdmin, connect as `postgres`, and execute:
   ```sql
   CREATE DATABASE sakshi_cases;
   CREATE USER sakshi_user WITH ENCRYPTED PASSWORD 'your_secure_password';
   GRANT ALL PRIVILEGES ON DATABASE sakshi_cases TO sakshi_user;
   ALTER DATABASE sakshi_cases OWNER TO sakshi_user;
   \c sakshi_cases
   CREATE EXTENSION IF NOT EXISTS vector;
   GRANT ALL ON SCHEMA public TO sakshi_user;
   ```

---

## 3. Configuring SAKSHI Backend

1. In the `backend/` directory, create or edit `.env` (refer to `.env.example`):
   ```ini
   DATABASE_URL="postgresql+psycopg://sakshi_user:your_secure_password@localhost:5432/sakshi_cases"
   DB_POOL_SIZE=5
   DB_MAX_OVERFLOW=10
   DB_POOL_TIMEOUT=30
   DB_CONNECT_TIMEOUT=10
   DB_POOL_PRE_PING=true
   ```

2. Drivers supported:
   - Modern `psycopg` (v3): `postgresql+psycopg://...` *(recommended)*
   - Legacy `psycopg2`: `postgresql+psycopg2://...` or `postgresql://...`

---

## 4. Verifying Connection & pgvector Availability

SAKSHI provides an automated verification tool:

```powershell
# In backend/ with active virtual environment:
python -m app.db.verify_connection
```

Or specify a connection string to test a target database without changing `.env`:

```powershell
python -m app.db.verify_connection postgresql+psycopg://sakshi_user:your_secure_password@localhost:5432/sakshi_cases
```

### Expected Successful Output:
```
======================================================================
SAKSHI — Database & pgvector Diagnostic Verifier
======================================================================
Status:        CONNECTED
Dialect:       postgresql
Target URL:    postgresql+psycopg://sakshi_user:********@localhost:5432/sakshi_cases
Server Ver:    PostgreSQL 16.2 ...
pgvector Ready:True
pgvector Ext:  True (v0.6.0)
Vector Math:   True
----------------------------------------------------------------------
Guidance:
PostgreSQL and pgvector are fully operational for SAKSHI RAG.
======================================================================
```

---

## 5. SQLite Coexistence & Safety Invariants

- **SQLite Preservation:** When `DATABASE_URL` is unset or points to `sqlite:///...`, SAKSHI seamlessly runs on SQLite.
- **Zero Data Deletion:** Existing `sakshi_cases.db` files are never deleted or modified.
- **Testing Integrity:** Automated test suites (`pytest`) run against an isolated in-memory SQLite database (`sqlite:///:memory:`), keeping local developer cycles fast and fully self-contained.

---

## 6. Phase 4 Retrieval Verification

The Phase 4 endpoint is `POST /api/v1/cases/{case_id}/rag/search`. It is available only to an authenticated investigator and performs the existing MOD-03 `evidence:read` case authorization check before querying vectors.

On PostgreSQL, retrieval uses pgvector cosine distance (`embedding <=> :query_embedding`) and orders ascending by distance. The migration creates an HNSW index using `vector_cosine_ops`; the embedding column is `VECTOR(384)`. The query also applies the requested `case_id`, indexed-document, completed-index-job, evidence linkage, matching SHA-256 and SHA3-512 provenance, antivirus, WORM commit, integrity, and object-lock predicates in SQL. Run `EXPLAIN (ANALYZE, BUFFERS)` with representative data before claiming that the planner selects the HNSW index—small tables or highly selective relational filters may appropriately select another plan.

SQLite stores embeddings as JSON for local development and tests only. It has no native vector operator. The application therefore uses the explicitly named `sqlite_bounded_development_fallback`: it loads at most `RAG_SQLITE_RETRIEVAL_CANDIDATE_LIMIT` eligible chunks from the requested case, then calculates cosine similarity in process. This is deliberately not a full-corpus or production-equivalent vector search.

Production configuration must use `EMBEDDING_PROVIDER=sentence_transformer` with the configured model weights already present locally. The provider uses local-files-only loading and refuses the deterministic mock provider in production; it never downloads weights or sends evidence text to an external embedding service.
