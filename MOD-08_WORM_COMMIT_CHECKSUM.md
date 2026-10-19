# MOD-08 — WORM Commit + Checksum
**Phase 2: Evidence Ingestion (Final Node)**  
**SAKSHI — Explainable AI Investigation Companion**  
**Paradigm: Evidence-Constrained Modus Operandi Reconstruction (EC-MORE)**

---

## 1. Purpose
MOD-08 is the final node of the **Phase 2 — Evidence Ingestion** pipeline. Its immediate role is to consume clean, antivirus-scanned forensic evidence (`ScannedEvidenceObject` from MOD-07) and establish the cryptographic and immutable-storage boundary before handoff to Phase 3 (Security & Integrity).

```
PHASE 2 — EVIDENCE INGESTION
════════════════════════════════════════════

MOD-05: Evidence Intake
      │
      ▼ (RegisteredEvidenceObject)
MOD-06: MIME / Signature Validation
      │
      ▼ (ValidatedEvidenceObject)
MOD-07: Antivirus Scan
      │
      ▼ (ScannedEvidenceObject)
╔════════════════════════════════════════════╗
║                  MOD-08                   ║
║           WORM COMMIT + CHECKSUM          ║
║                                            ║
║  • Strict Fail-Closed AV Gate              ║
║  • Bounded Streaming SHA-256 Pre-Hash     ║
║  • Content-Addressed WORM Storage          ║
║  • Immutable Storage Reference             ║
║  • Idempotent State Transition             ║
║  • Tamper-Evident Structured Audit Logging ║
╚══════════════════════╤═════════════════════╝
                       │
                       ▼ (WORMCommittedEvidenceObject)
                 PHASE 3
           Security & Integrity
```

---

## 2. Scope & Boundary Rules

### What MOD-08 Implements:
- Consumes `ScannedEvidenceObject` strictly after MOD-07.
- Enforces a fail-closed antivirus gate (`status == 'CLEAN'` and `antivirus_status == 'CLEAN'`).
- Validates case containment and workspace path canonicalization (`os.path.realpath`).
- Computes SHA-256 pre-hash using bounded chunked streaming (1 MB chunks).
- Storage abstraction `IWORMStorage` with Write-Once-Read-Many semantics.
- Development filesystem implementation `LocalFileSystemWORMStorage` in content-addressed directories (`.worm/<sha256>`), setting read-only permissions (`stat.S_IREAD`).
- Generates canonical immutable storage references: `worm://<case_id>/<sha256>`.
- Prevents overwrite and duplicate replacement after commitment.
- Deterministic idempotency: repeated commits return the existing commitment without re-writing.
- Persists checksum and WORM metadata to the database.
- Structured audit event emission via `AuditIntegrationService`.
- Downstream contract `WORMCommittedEvidenceObject` for Phase 3 handoff.

### What MOD-08 Strictly Does NOT Implement:
- ❌ **SHA3-512 dual hashing** (reserved for Phase 3).
- ❌ **Merkle tree audit ledger** (reserved for Phase 3).
- ❌ **Production AWS S3 Object Lock backend** (reserved for Phase 3).
- ❌ **AI analysis, OCR, or contextual reconstruction** (Phase 4).
- ❌ **Evidence interpretation or timeline generation** (Phases 4-6).

---

## 3. Input Contract
MOD-08 requires a strictly validated `ScannedEvidenceObject` produced by MOD-07:

```python
class ScannedEvidenceObject(BaseModel):
    evidence_id: str
    case_id: str
    staged_file_path: str
    original_file_name: str
    verified_mime_type: str
    detected_format: str
    evidence_category: str
    file_size_bytes: int
    submitting_investigator_id: str
    mime_status: str           # Must be 'VALIDATED'
    antivirus_verdict: str     # Must be 'CLEAN'
    antivirus_scanner: str
    antivirus_scanned_at: datetime
```

- Direct intake from `RegisteredEvidenceObject` (MOD-05) is strictly prohibited.
- Direct intake from `ValidatedEvidenceObject` (MOD-06) bypassing MOD-07 is strictly prohibited.

---

## 4. Antivirus Gate (Fail-Closed)
MOD-08 enforces an unyielding fail-closed gate before reading or hashing evidence bytes:

```
Is evidence AV-clean?
       │
       ├── status == 'CLEAN' and antivirus_status == 'CLEAN' ──► PROCEED
       │
       └── Any other state (THREAT_DETECTED, QUARANTINED,
           SCANNER_UNAVAILABLE, SCAN_TIMEOUT, SCAN_ERROR,
           missing, NULL, unknown) ──────────────────────────► REJECT (Fail-Closed)
```

- If `status == QUARANTINED` or `antivirus_status == THREAT_DETECTED`: raises `AntivirusThreatDetectedException` (HTTP 422).
- If status is not explicitly `CLEAN`: raises `EvidenceNotScannedException` (HTTP 400).
- Missing AV status or uninitialized scan records are never treated as clean.

---

## 5. SHA-256 Pre-Hash Algorithm
- **Target**: The actual raw evidence payload bytes on disk.
- **Excluded**: Filenames, MIME types, database IDs, and metadata timestamps are NOT included in the payload digest.
- **Algorithm**: Standard SHA-256 (`hashlib.sha256()`).
- **Encoding**: Lowercase hexadecimal string (64 characters).

---

## 6. Chunked Streaming Hashing
To support arbitrarily large forensic evidence payloads (multi-gigabyte disk dumps, CDR spreadsheets, raw video recordings) without exhausting system RAM:

```python
HASH_CHUNK_SIZE = 1048576  # 1 MB bounded buffer

def compute_sha256(file_path: str, chunk_size: int = HASH_CHUNK_SIZE) -> str:
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest().lower()
```

---

## 7. WORM Storage Abstraction (`IWORMStorage`)
The business layer is decoupled from physical storage providers via `IWORMStorage`:

```python
class IWORMStorage(ABC):
    @abstractmethod
    def put_immutable(
        self,
        case_id: str,
        sha256_digest: str,
        source_file_path: str,
        case_workspace_path: Optional[str] = None
    ) -> str:
        """Stores object once; refuses overwrite; returns immutable URI reference."""
        pass

    @abstractmethod
    def get_reference(self, case_id: str, sha256_digest: str) -> str:
        """Returns canonical immutable storage reference: worm://<case-id>/<sha256>."""
        pass

    @abstractmethod
    def exists(
        self,
        case_id: str,
        sha256_digest: str,
        case_workspace_path: Optional[str] = None
    ) -> bool:
        """Checks if content-addressed object exists in immutable storage."""
        pass

    @abstractmethod
    def verify_immutable(
        self,
        case_id: str,
        sha256_digest: str,
        case_workspace_path: Optional[str] = None
    ) -> bool:
        """Verifies integrity of committed object against claimed digest."""
        pass
```

---

## 8. Development WORM Implementation (`LocalFileSystemWORMStorage`)
- **Location**: `<case_workspace_path>/.worm/<sha256>`.
- **Atomic Staging**: Writes to a temporary file (`.tmp_<timestamp>`), verifies the computed hash matches the expected pre-hash, then performs atomic rename (`os.replace`).
- **Write-Once Enforcement**:
  - Drops write permissions using `os.chmod(dest_path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)`.
  - Rejects attempts to overwrite existing objects with differing contents (`ChecksumMismatchException` / `WORMCommitFailedException`).
- **Simulated Boundary**: Clearly documented as local WORM storage, without falsely claiming cloud-native Object Lock.

---

## 9. Immutability Semantics
Once committed to WORM storage:
- **READ**: Fully permitted for authorized investigators.
- **OVERWRITE**: Strictly forbidden through all application layers.
- **REPLACE**: Strictly forbidden.
- **DELETE**: No deletion interface exists in MOD-08. Retention management is deferred to governance layers.

---

## 10. Database Model Extensions
Seven forensic metadata columns were added to the `Evidence` ORM model (`backend/app/models/evidence.py`):

| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `checksum_algorithm` | `String(32)` | Yes | Fixed as `"SHA-256"` |
| `checksum_sha256` | `String(64)` | Yes | Hexadecimal digest (indexed) |
| `checksum_computed_at` | `DateTime(timezone=True)` | Yes | Timestamp of pre-hash computation |
| `worm_status` | `String(32)` | Yes | Status of WORM commitment (`COMMITTED`, `COMMIT_FAILED`) |
| `worm_storage_reference` | `String(512)` | Yes | Content-addressed URI (`worm://<case_id>/<sha256>`) |
| `worm_committed_at` | `DateTime(timezone=True)` | Yes | Timestamp of immutable commitment |
| `worm_commit_message` | `Text` | Yes | Human-readable commitment audit summary |

---

## 11. REST API Endpoints

### 1. `POST /api/v1/cases/{case_id}/evidence/{evidence_id}/worm-commit`
- **Authentication**: Bearer token or development `X-Investigator-Id`.
- **Authorization**: `evidence:commit`.
- **Preconditions**: Case must be open; evidence must have `status == 'CLEAN'`; physical file must exist within workspace boundary.
- **Response**: `200 OK` with `WORMCommitResult`.

```json
{
  "evidence_id": "SAKSHI-EVID-2026-93E14DF2",
  "case_id": "SAKSHI-CASE-2026-4AD196C4",
  "status": "COMMITTED",
  "worm_status": "COMMITTED",
  "checksum_algorithm": "SHA-256",
  "checksum_sha256": "cfd05c0b232fe3ce7fe1dba4f9a80b9f013d65fbd67d7f30feb60013b29c277b",
  "worm_storage_reference": "worm://SAKSHI-CASE-2026-4AD196C4/cfd05c0b232fe3ce7fe1dba4f9a80b9f013d65fbd67d7f30feb60013b29c277b",
  "message": "Evidence committed to WORM storage with SHA-256 pre-hash.",
  "committed_at": "2026-10-02T07:42:48.003407Z",
  "already_committed": false
}
```

### 2. `GET /api/v1/cases/{case_id}/evidence/{evidence_id}/worm-contract`
- **Purpose**: Downstream handoff contract for Phase 3 (Security & Integrity).
- **Invariant**: Strictly returns `WORMCommittedEvidenceObject` only if evidence is committed. If called prior to commitment, returns `400 Bad Request` (`EVIDENCE_NOT_COMMITTED`).

```json
{
  "evidence_id": "SAKSHI-EVID-2026-93E14DF2",
  "case_id": "SAKSHI-CASE-2026-4AD196C4",
  "staged_file_path": "/workspace/cases/CASE-01/exhibit.pdf",
  "original_file_name": "exhibit.pdf",
  "verified_mime_type": "application/pdf",
  "detected_format": "PDF",
  "evidence_category": "DOCUMENT_PDF",
  "file_size_bytes": 1048576,
  "submitting_investigator_id": "IO-7842-SHARMA",
  "mime_status": "VALIDATED",
  "antivirus_verdict": "CLEAN",
  "antivirus_scanner": "EicarHeuristicScanner",
  "checksum_algorithm": "SHA-256",
  "checksum_sha256": "cfd05c0b232fe3ce7fe1dba4f9a80b9f013d65fbd67d7f30feb60013b29c277b",
  "checksum_computed_at": "2026-10-02T07:42:48.000000Z",
  "worm_status": "COMMITTED",
  "worm_storage_reference": "worm://SAKSHI-CASE-2026-4AD196C4/cfd05c0b232fe3ce7fe1dba4f9a80b9f013d65fbd67d7f30feb60013b29c277b",
  "committed_at": "2026-10-02T07:42:48.003407Z"
}
```

---

## 12. Centralized Authorization (MOD-03)
- **Permission**: `Permission.EVIDENCE_COMMIT = "evidence:commit"`.
- **Roles**:
  - `INVESTIGATING_OFFICER` (assigned to the case): **ALLOWED**.
  - `SUPERVISORY_OFFICER` / `STATION_HEAD`: **ALLOWED**.
  - Unassigned investigator / out-of-jurisdiction: **DENIED (403 Forbidden)**.
  - Unauthenticated request: **DENIED (401 Unauthorized)**.
- **Default Deny**: No inline role checks; all decisions route through `PolicyEngineAuthorizationService`.

---

## 13. Case Containment & Path Isolation
- Before hashing or storage writes, the physical path is resolved via `os.path.realpath`.
- Verified to start strictly within `os.path.realpath(case.case_workspace_path) + os.sep`.
- Path traversals (e.g. `../../etc/passwd` or cross-case file references) trigger immediate audit alerts (`WORKSPACE_BOUNDARY_VIOLATION`) and raise `ForbiddenException` (HTTP 403).

---

## 14. Audit Trail Integration
All lifecycle operations emit structured events via `AuditIntegrationService`:

| Action | Event Type | Description |
| :--- | :--- | :--- |
| `EVIDENCE_WORM_COMMIT_STARTED` | `AUDIT_EVIDENCE_WORM_COMMIT_STARTED` | Hashing and commitment initiated |
| `EVIDENCE_SHA256_COMPUTED` | `AUDIT_EVIDENCE_SHA256_COMPUTED` | Pre-hash calculated from payload bytes |
| `EVIDENCE_WORM_COMMITTED` | `WORM_COMMIT_SUCCESS` | File stored immutably, DB state updated |
| `EVIDENCE_WORM_COMMIT_FAILED` | `WORM_COMMIT_FAILURE` | Mismatch or storage failure |

*(Audit records do not include full file contents or security credentials).*

---

## 15. Atomicity & Failure Ordering
1. **Verification before writing**: Pre-hash is computed from source file.
2. **Atomic staging**: Stream-copied to temp file while computing a secondary verification hash.
3. **Integrity check**: If written bytes do not match pre-hash, temp file is unlinked, and `ChecksumMismatchException` is raised.
4. **Storage rename**: Atomic rename (`os.replace`) to content address.
5. **Database update**: `status` and `worm_status` are set to `COMMITTED` only after successful storage write.
6. **Audit success**: Recorded upon database commit.

---

## 16. Idempotency Behavior
WORM commitment is fully deterministic:
- If an evidence item has already been successfully committed (`status == 'COMMITTED'`, `worm_status == 'COMMITTED'`), repeat calls return the existing commitment record with `already_committed = true`.
- Overwriting or re-hashing with different data is strictly rejected.

---

## 17. Verification & Testing

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\main project\backend
plugins: anyio-4.15.1, asyncio-0.26.0
collected 196 items

tests\integration\test_antivirus_scan_api.py ..........                  [ 10 passed ]
tests\integration\test_cases_api.py ........                             [  8 passed ]
tests\integration\test_evidence_api.py ......                            [  6 passed ]
tests\integration\test_mime_validation_api.py .......                    [  7 passed ]
tests\integration\test_worm_commit_api.py .........                      [  9 passed ]
tests\unit\test_antivirus_scan_service.py ............................   [ 28 passed ]
tests\unit\test_auth_service.py .................................        [ 33 passed ]
tests\unit\test_authorization_service.py .........................       [ 25 passed ]
tests\unit\test_case_service.py ........                                 [  8 passed ]
tests\unit\test_evidence_intake_service.py .........                     [  9 passed ]
tests\unit\test_mime_validation_service.py ..................            [ 18 passed ]
tests\unit\test_stage_engine.py ..................                       [ 18 passed ]
tests\unit\test_worm_commit_service.py .................                 [ 17 passed ]

======================= 196 passed, 2 warnings in 3.99s =======================
```

- **Previous Baseline**: 170 passed (162 original + 8 MOD-07 hardening).
- **New Tests Added**: 26 tests (17 unit + 9 integration).
- **Final Result**: **196 passed, 0 failures (100% passing)**.

---

## 18. Known Limitations
1. **Development Storage**: The default `LocalFileSystemWORMStorage` relies on filesystem read-only attributes (`stat.S_IREAD`). It simulates WORM behavior for development and testing environments but is not hardware-enforced cloud Object Lock.
2. **Single Algorithm Pre-Hash**: MOD-08 pre-hashes exclusively with SHA-256. Dual integrity hashing is deferred to Phase 3.

---

## 19. Phase 3 Boundary Confirmation

> [!IMPORTANT]
> **CONFIRMATION OF ARCHITECTURAL BOUNDARY:**
> 
> MOD-08 strictly establishes the **Phase 2 SHA-256 pre-hash and WORM commitment boundary**.
> 
> MOD-08 **DOES NOT** implement:
> - SHA3-512 dual hashing
> - Merkle tree audit ledger
> - Production AWS S3 Object Lock backend
> - Automated AI evidence interpretation
> 
> All of these capabilities belong exclusively to **Phase 3 (Security & Integrity)** and subsequent phases.

---

## 20. Definition of Done Checklist

- [x] `ScannedEvidenceObject` is the required input contract.
- [x] Only successful `CLEAN` AV results can proceed (fail-closed).
- [x] SHA-256 is calculated from actual evidence payload bytes.
- [x] Hashing is streamed in 1 MB chunks without buffering entire files in memory.
- [x] SHA-256 digest is persisted to database model.
- [x] WORM storage abstraction (`IWORMStorage`) defined and implemented.
- [x] Canonical immutable storage reference generated (`worm://<case_id>/<sha256>`).
- [x] Overwrites and duplicate commitments are prevented.
- [x] Repeated commit behavior is deterministic and idempotent.
- [x] Case workspace containment is enforced with path canonicalization.
- [x] Centralized RBAC/ABAC authorization (`evidence:commit`) is enforced.
- [x] DEFAULT DENY remains active.
- [x] Structured audit logging records all lifecycle events.
- [x] Failure paths handle missing files, traversal, and checksum mismatches.
- [x] Large files are supported safely.
- [x] REST API endpoints (`/worm-commit` and `/worm-contract`) implemented.
- [x] Comprehensive unit and integration tests created.
- [x] Comprehensive documentation completed.
- [x] All 170 baseline tests remain passing.
- [x] All 26 new MOD-08 tests pass (196 total passing, 0 failures).
- [x] No Phase 3 functionality is prematurely claimed or implemented.
- [x] No unrelated modules or regressions introduced.
