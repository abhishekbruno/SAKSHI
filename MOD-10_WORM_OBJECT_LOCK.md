# MOD-10: WORM Object Lock / Dual Storage
## Phase 3 — Security & Integrity

---

## Overview

MOD-10 implements the **WORM Object Lock / Dual Storage** boundary for the SAKSHI Investigation Platform. It is a **Phase 3 enhancement** that sits on top of and is architecturally distinct from the Phase 2 MOD-08 WORM Commit layer.

```
MOD-09
IntegrityProtectedEvidenceObject
          │
          ▼
┌──────────────────────────────────────┐
│              MOD-10                  │
│         WORM Object Lock             │
│                                      │
│  Dual-hash integrity binding         │
│  Canonical objlock:// reference      │
│  Retention metadata                  │
│  Overwrite protection                │
│  Deletion protection                 │
│  GOVERNANCE / COMPLIANCE modes       │
│  Append-only audit event log         │
│  IObjectLockBackend abstraction      │
│  Failure-safe (LOCK_FAILED state)    │
│  Deterministic idempotency           │
└──────────────────┬───────────────────┘
                   │
                   ▼
       ObjectLockedEvidenceObject
                   │
                   ▼
                MOD-11
         AES-256-GCM Encryption
```

---

## MOD-08 vs MOD-10 — Architectural Distinction

| Dimension | MOD-08 (Phase 2) | MOD-10 (Phase 3) |
|-----------|-----------------|-----------------|
| **Layer** | Evidence Ingestion | Security & Integrity |
| **Input** | `ScannedEvidenceObject` (CLEAN AV verdict) | `IntegrityProtectedEvidenceObject` (integrity_status == VERIFIED) |
| **Output** | `WORMCommittedEvidenceObject` | `ObjectLockedEvidenceObject` |
| **Hash** | SHA-256 pre-hash only | SHA-256 + SHA3-512 dual binding |
| **Reference format** | `worm://<case_id>/<sha256>` | `objlock://<case_id>/<sha256>+<sha3_prefix16>` |
| **Lock modes** | N/A (single level) | GOVERNANCE / COMPLIANCE |
| **Retention metadata** | None | `lock_applied_at`, `lock_retention_until` |
| **Integrity binding** | SHA-256 digest | `sha256:<val>:sha3_512:<val>` fingerprint |
| **Backend abstraction** | `IWORMStorage` | `IObjectLockBackend` (pluggable) |
| **Audit event log** | Per-operation audit events | Append-only JSON event log on evidence record |
| **Downstream** | MOD-09 | MOD-11 |

MOD-10 does **not** replace or conflict with MOD-08. The MOD-08 `worm://` reference is preserved in the `ObjectLockedEvidenceObject` and carried downstream to MOD-11.

---

## Inputs & Outputs

### Consumes
`IntegrityProtectedEvidenceObject` from MOD-09 with **strict invariants**:
- `integrity_status == 'VERIFIED'`
- `checksum_sha256` present (64 hex chars)
- `checksum_sha3_512` present (128 hex chars)

### Produces
`ObjectLockedEvidenceObject` with dual storage references:
- **MOD-08 reference**: `worm://<case_id>/<sha256>`
- **MOD-10 reference**: `objlock://<case_id>/<sha256>+<sha3_512_prefix16>`
- **Integrity binding**: `sha256:<sha256_hex>:sha3_512:<sha3_512_hex>`
- **Retention**: `lock_applied_at`, `lock_retention_until`
- **Lock mode**: GOVERNANCE or COMPLIANCE
- **Protection flags**: `lock_overwrite_protected`, `lock_delete_protected`

---

## API Endpoints

All endpoints are nested under `/api/v1/cases/{case_id}/evidence/{evidence_id}`.

### `POST /object-lock`
Apply WORM Object Lock to integrity-verified evidence.

**Query Parameters**
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `lock_mode` | string | `GOVERNANCE` | `GOVERNANCE` or `COMPLIANCE` |

**Authorization**: `evidence:object_lock` permission required.  
**Idempotent**: Repeated calls are safe — returns `already_locked: true` if already locked.

**Response** (`ObjectLockResult`):
```json
{
  "evidence_id": "SAKSHI-EVID-2026-ABCD1234",
  "case_id": "SAKSHI-2026-CASE-XYZW",
  "lock_status": "LOCKED",
  "lock_mode": "GOVERNANCE",
  "lock_storage_reference": "objlock://SAKSHI-2026-CASE-XYZW/abcdef...64chars...+1234567890abcdef",
  "lock_applied_at": "2026-10-02T14:00:00Z",
  "lock_retention_until": "2033-10-02T14:00:00Z",
  "lock_backend": "LOCAL_FILESYSTEM",
  "lock_overwrite_protected": true,
  "lock_delete_protected": true,
  "lock_integrity_binding": "sha256:abcdef...64...:sha3_512:fedcba...128...",
  "checksum_sha256": "abcdef...64...",
  "checksum_sha3_512": "fedcba...128...",
  "worm_storage_reference": "worm://SAKSHI-2026-CASE-XYZW/abcdef...64...",
  "message": "Evidence successfully placed under WORM Object Lock.",
  "already_locked": false
}
```

**Error responses**:
| HTTP | Error Code | Trigger |
|------|-----------|---------|
| 400 | `INTEGRITY_NOT_VERIFIED_FOR_LOCK` | MOD-09 not completed |
| 400 | `OBJECT_LOCK_FAILED` | Invalid `lock_mode` |
| 401 | `AUTHENTICATION_REQUIRED` | No credentials |
| 403 | `FORBIDDEN` | Not assigned to case |
| 404 | `CASE_NOT_FOUND` | Invalid `case_id` |
| 404 | `EVIDENCE_NOT_FOUND` | Invalid `evidence_id` |
| 500 | `OBJECT_LOCK_FAILED` | Backend failure |

---

### `GET /object-lock-contract`
Export the formal `ObjectLockedEvidenceObject` downstream handoff contract for MOD-11.

**Strict Invariants**:
- `integrity_status == 'VERIFIED'` (MOD-09 gate)
- `lock_status == 'LOCKED'` (MOD-10 gate)

**Error responses**:
| HTTP | Error Code | Trigger |
|------|-----------|---------|
| 400 | `OBJECT_NOT_LOCKED` | Evidence not yet locked |
| 401 | `AUTHENTICATION_REQUIRED` | No credentials |
| 403 | `FORBIDDEN` | Not assigned to case |

---

## Object Lock Modes

### GOVERNANCE
```
Retention enforced by application-layer controls.
Authorized administrators can override with explicit reason.
Target use: Development, QA, non-production forensic workflows.
```

### COMPLIANCE
```
Retention is absolute until lock_retention_until expires.
Cannot be reduced or overridden by any principal.
Target use: Production, regulatory, evidentiary production.
```

> **⚠️ Phase 3 Limitation**  
> Both modes are enforced by the **application-level `LocalObjectLockBackend`** in the current implementation. TRUE hardware/cloud-enforced Object Lock (e.g., AWS S3 Object Lock COMPLIANCE mode, NetApp SnapLock) requires infrastructure-level support and is the target of a future production phase.

---

## Architecture

### `IObjectLockBackend` — Pluggable Interface

```python
class IObjectLockBackend(ABC):
    def apply_lock(case_id, sha256_digest, sha3_512_digest,
                   source_file_path, lock_mode, retention_days,
                   case_workspace_path) -> Dict[str, Any]: ...

    def is_locked(case_id, sha256_digest, case_workspace_path) -> bool: ...

    def get_reference(case_id, sha256_digest, sha3_512_digest) -> str: ...

    def verify_lock_integrity(lock_storage_reference, expected_sha256,
                              case_workspace_path) -> bool: ...
```

**Phase 3 implementation**: `LocalObjectLockBackend` (`BACKEND_NAME = "LOCAL_FILESYSTEM"`)  
**Future implementations**: `S3ObjectLockBackend`, `AzureBlobImmutableBackend`, `GCSRetentionBackend`

### `LocalObjectLockBackend` — Filesystem Layout

```
<case_workspace>/
└── .objlock/
    └── <sha256_hex>/
        └── .object_lock_manifest.json   ← read-only, atomic write
```

### Lock Manifest Schema (`MOD10_V1`)

```json
{
  "schema_version": "MOD10_V1",
  "backend": "LOCAL_FILESYSTEM",
  "case_id": "...",
  "checksum_sha256": "...",
  "checksum_sha3_512": "...",
  "lock_integrity_binding": "sha256:<val>:sha3_512:<val>",
  "lock_storage_reference": "objlock://<case>/<sha256>+<sha3_prefix16>",
  "lock_mode": "GOVERNANCE",
  "lock_applied_at": "2026-10-02T14:00:00+00:00",
  "lock_retention_until": "2033-10-02T14:00:00+00:00",
  "retention_days": 2555,
  "lock_overwrite_protected": true,
  "lock_delete_protected": true,
  "source_file": "/path/to/staged/evidence",
  "architectural_note": "..."
}
```

---

## Database Schema (New Columns on `evidence` table)

| Column | Type | Description |
|--------|------|-------------|
| `lock_status` | String(32) | `UNLOCKED` \| `LOCKED` \| `LOCK_FAILED` |
| `lock_mode` | String(32) | `GOVERNANCE` \| `COMPLIANCE` |
| `lock_storage_reference` | String(512) | Canonical `objlock://` reference |
| `lock_applied_at` | DateTime | UTC timestamp when lock was applied |
| `lock_retention_until` | DateTime | UTC timestamp when lock expires |
| `lock_backend` | String(64) | `LOCAL_FILESYSTEM` \| ... |
| `lock_overwrite_protected` | Boolean | True if overwrite is prevented |
| `lock_delete_protected` | Boolean | True if deletion is prevented |
| `lock_integrity_binding` | String(256) | `sha256:<val>:sha3_512:<val>` |
| `lock_failure_reason` | Text | Failure message if LOCK_FAILED |
| `object_lock_event_log` | Text | Append-only JSON array of lock events |

---

## Security Properties

| Property | Implementation |
|----------|---------------|
| **Immutable object reference** | `objlock://` canonical URI tied to SHA-256 + SHA3-512 |
| **Dual-hash integrity binding** | `sha256:<val>:sha3_512:<val>` fingerprint captured at lock time |
| **Retention metadata** | `lock_applied_at` + `lock_retention_until` + `retention_days` |
| **No overwrite** | `os.chmod(read-only)` on WORM file + lock manifest |
| **No delete** | Lock manifest records deletion protection intent |
| **Case isolation** | `os.path.realpath()` boundary containment, workspace violation → `ForbiddenException` |
| **Authorization** | `evidence:object_lock` permission via MOD-03 PolicyEngine (RBAC + ABAC) |
| **Audit events** | `EVIDENCE_OBJECT_LOCK_STARTED`, `EVIDENCE_OBJECT_LOCKED`, `EVIDENCE_OBJECT_LOCK_FAILED` |
| **Append-only event log** | JSON array on `object_lock_event_log` column |
| **Failure-safe** | `LOCK_FAILED` state + failure reason on any backend error |
| **Idempotency** | Repeated lock requests are safe — returns existing state |
| **Downstream contract** | `ObjectLockedEvidenceObject` — strict invariant gate for MOD-11 |

---

## Workflow

```
1. Validate Case Existence
2. RBAC/ABAC Authorization ('evidence:object_lock')
3. Retrieve Evidence & Case Containment check
4. MOD-09 Gate: integrity_status == 'VERIFIED' and dual hashes present
5. Validate lock_mode (GOVERNANCE | COMPLIANCE)
6. Idempotency: already LOCKED? → return existing state
7. Physical Payload & Workspace Boundary Containment (realpath)
8. Audit: EVIDENCE_OBJECT_LOCK_STARTED
9. Compute dual-hash integrity binding fingerprint
10. IObjectLockBackend.apply_lock() → lock manifest written, permissions stripped
11. Atomic DB State Transition (lock_status → LOCKED, all metadata)
12. Append entry to object_lock_event_log
13. Audit: EVIDENCE_OBJECT_LOCKED
14. Return ObjectLockResult
```

On any backend failure at step 10+:
```
→ lock_status → LOCK_FAILED
→ lock_failure_reason recorded
→ Audit: EVIDENCE_OBJECT_LOCK_FAILED
→ ObjectLockFailedException raised
```

---

## Authorization

| Role | `evidence:object_lock` |
|------|----------------------|
| INVESTIGATING_OFFICER | ✅ |
| SUPERVISORY_OFFICER | ✅ |
| STATION_HEAD | ✅ |
| ADMIN | ✅ |
| SUPERVISOR | ✅ |
| CASE_ADMIN | ❌ |
| SYSTEM_ADMIN | ❌ |

ABAC: Investigator must be assigned to the case (or hold a supervisory role with broad access).

---

## Test Coverage

| Category | Tests |
|----------|-------|
| `LocalObjectLockBackend` unit tests | 11 |
| Full pipeline (MOD-05 → MOD-10) | 6 |
| Gate enforcement (MOD-09 prerequisite) | 5 |
| Idempotency | 2 |
| Authorization (RBAC/ABAC) | 4 |
| `ObjectLockedEvidenceObject` contract | 5 |
| Failure-safe behavior | 1 |
| Case isolation / workspace boundary | 1 |
| Health check / module registration | 2 |
| **API integration total** | 15 |
| **Unit total** | 32 |
| **Grand total MOD-10** | **47** |

---

## Pipeline Position

```
╔══════════════════════════════════════════╗
║       SAKSHI IMPLEMENTATION STATUS       ║
╠══════════════════════════════════════════╣
║ PHASE 1 — Governance              100%   ║
║ MOD-01                              ✅   ║
║ MOD-02                              ✅   ║
║ MOD-03                              ✅   ║
║ MOD-04                              ✅   ║
║                                          ║
║ PHASE 2 — Evidence Ingestion       100% ║
║ MOD-05                              ✅   ║
║ MOD-06                              ✅   ║
║ MOD-07                              ✅   ║
║ MOD-08                              ✅   ║
║                                          ║
║ PHASE 3 — Security & Integrity            ║
║ MOD-09                              ✅   ║
║ MOD-10                              ✅   ║
║ MOD-11                              ⬜   ║
║ MOD-12                              ⬜   ║
║ MOD-13                              ⬜   ║
╚══════════════════════════════════════════╝

TOTAL VERIFIED TESTS: 267
FAILURES: 0
```

---

## Files Changed

| File | Change |
|------|--------|
| `app/models/evidence.py` | +11 MOD-10 ORM columns |
| `app/schemas/evidence.py` | `ObjectLockMode`, `ObjectLockResult`, `ObjectLockedEvidenceObject` |
| `app/core/errors.py` | `IntegrityNotVerifiedForLockException`, `ObjectLockFailedException`, `ObjectAlreadyLockedException`, `ObjectNotLockedException` |
| `app/services/authorization_service.py` | `EVIDENCE_OBJECT_LOCK` permission, role grants, ABAC routing, action mapping |
| `app/services/auth_service.py` | `check_can_object_lock_evidence` abstract + concrete |
| `app/services/object_lock_service.py` | **New** — `IObjectLockBackend`, `LocalObjectLockBackend`, `ObjectLockService` |
| `app/api/deps.py` | `get_object_lock_service` factory |
| `app/api/v1/evidence.py` | `POST /object-lock`, `GET /object-lock-contract` endpoints |
| `app/main.py` | Version 0.4.0, MOD-10 in health check |
| `tests/unit/test_object_lock_service.py` | **New** — 32 unit tests |
| `tests/integration/test_object_lock_api.py` | **New** — 15 integration tests |

---

## Downstream: MOD-11

MOD-11 (AES-256-GCM Encryption) consumes `ObjectLockedEvidenceObject` from MOD-10. It must verify:
- `source == "MOD-10"`
- `lock_status == "LOCKED"`
- `integrity_status == "VERIFIED"`
- Both `checksum_sha256` and `checksum_sha3_512` present
- `lock_storage_reference` present and begins with `objlock://`
