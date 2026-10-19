# MOD-09 — Dual Hashing (SHA-256 + SHA3-512) & Integrity Verification
**Phase 3: Security & Integrity (First Node)**  
**SAKSHI — Explainable AI Investigation Companion**  
**Paradigm: Evidence-Constrained Modus Operandi Reconstruction (EC-MORE)**

---

## 1. Purpose & Pipeline Position
MOD-09 is the foundational first module of **Phase 3: Security & Integrity**. It consumes the `WORMCommittedEvidenceObject` produced by MOD-08 (WORM Commit + Checksum) and expands the cryptographic integrity boundary of forensic evidence from single-hash SHA-256 to **dual-algorithm integrity protection (SHA-256 + SHA3-512)**.

```
PHASE 2 — EVIDENCE INGESTION
═══════════════════════════════════════════════════════════════
MOD-05 (Intake) ──► MOD-06 (MIME) ──► MOD-07 (AV) ──► MOD-08 (WORM)
                                                            │
                                                            ▼ (WORMCommittedEvidenceObject)
PHASE 3 — SECURITY & INTEGRITY
═══════════════════════════════════════════════════════════════
                    ╔══════════════════════════════════════╗
                    ║                MOD-09                ║
                    ║             DUAL HASHING             ║
                    ║                                      ║
                    ║  1. Recompute SHA-256                ║
                    ║  2. Verify against MOD-08 pre-hash   ║
                    ║     (FAIL-CLOSED on mismatch)        ║
                    ║  3. Compute SHA3-512 (512-bit,       ║
                    ║     128 lowercase hex characters)    ║
                    ║  4. Mark status: VERIFIED            ║
                    ║  5. Emit structured audit records    ║
                    ╚══════════════════╤═══════════════════╝
                                       │
                                       ▼ (IntegrityProtectedEvidenceObject)
                                     MOD-10
                          (Object Lock / Dual Storage)
```

---

## 2. Core Architectural Design: Verification Over Blind Re-Hashing
MOD-09 does not blindly re-hash evidence in isolation. Rather, it explicitly acts as a **verification and cryptographic expansion boundary**:

1. **Verification of MOD-08 Pre-Hash**: The immutable evidence file is read using streaming chunked I/O. The recomputed SHA-256 digest is compared directly against the authoritative SHA-256 pre-hash established during MOD-08 WORM commitment.
   - If the hashes match $\rightarrow$ confirms the evidence bytes in WORM storage have suffered zero bit rot, corruption, or tampering.
   - If the hashes mismatch $\rightarrow$ fails closed immediately, transitions `integrity_status` to `FAILED`, emits an audit failure event, and raises `SHA256IntegrityMismatchException`.
2. **Expansion to SHA3-512**: Simultaneously during the streaming pass, a 512-bit Keccak-based SHA3-512 digest is computed.
3. **Dual Hash Binding**: Both digests are permanently bound to the evidence record, creating defense-in-depth against future collision attacks on any single algorithm family (SHA-2 vs. SHA-3).

---

## 3. Cryptographic Specification

| Property | Primary Pre-Hash (MOD-08) | Secondary Integrity Hash (MOD-09) |
| :--- | :--- | :--- |
| **Algorithm** | SHA-256 | SHA3-512 |
| **Standard** | FIPS 180-4 | FIPS 202 (Keccak permutation) |
| **Digest Length** | 256 bits (32 bytes) | 512 bits (64 bytes) |
| **Representation** | 64 lowercase hexadecimal chars | 128 lowercase hexadecimal chars |
| **Target** | Raw payload bytes on disk | Raw payload bytes on disk |
| **I/O Strategy** | Streaming (1 MB chunks) | Streaming (1 MB chunks, single pass) |

---

## 4. Input & Output Contracts

### Input Contract: `WORMCommittedEvidenceObject` (from MOD-08)
```python
class WORMCommittedEvidenceObject(BaseModel):
    evidence_id: str
    case_id: str
    staged_file_path: str
    original_file_name: str
    verified_mime_type: str
    detected_format: str
    evidence_category: str
    file_size_bytes: int
    submitting_investigator_id: str
    mime_status: Optional[str] = None
    antivirus_verdict: str
    antivirus_scanner: str
    checksum_algorithm: str = "SHA-256"
    checksum_sha256: str
    checksum_computed_at: datetime
    worm_status: str           # Must be 'COMMITTED'
    worm_storage_reference: str
    committed_at: datetime
```

### Downstream Handoff Contract: `IntegrityProtectedEvidenceObject` (for Phase 3/4)
```python
class IntegrityProtectedEvidenceObject(BaseModel):
    case_id: str
    evidence_id: str
    original_file_name: str
    evidence_category: str
    file_size_bytes: int
    worm_storage_reference: str
    checksum_sha256: str
    checksum_sha3_512: str
    integrity_status: str = "VERIFIED"
    verified_at: datetime
    source: str = "MOD-09"
```

---

## 5. Fail-Closed Verification Workflow
MOD-09 enforces strict fail-closed security at every step:

```
[Request to /integrity]
          │
          ▼
1. Is investigator authenticated? ─────────► NO ──► 401 Unauthorized
          │ YES
          ▼
2. Has 'evidence:verify' permission? ──────► NO ──► 403 Forbidden
          │ YES
          ▼
3. Does case exist & match evidence? ──────► NO ──► 404 / 403
          │ YES
          ▼
4. Is evidence WORM committed? ────────────► NO ──► 400 Bad Request
   (worm_status == 'COMMITTED')
          │ YES
          ▼
5. Does payload reside in case workspace? ─► NO ──► 403 Forbidden
          │ YES
          ▼
6. Stream & compute dual hashes
          │
          ▼
7. Does recomputed SHA-256 match MOD-08?
          ├── NO  ──► status = 'FAILED' ──► 422 SHA256IntegrityMismatchException
          │
          └── YES ──► status = 'VERIFIED'
                      Persist checksum_sha3_512
                      Emit EVIDENCE_INTEGRITY_VERIFIED
                      Return IntegrityVerificationResult (200 OK)
```

---

## 6. Bounded Streaming Dual Hashing
To prevent memory exhaustion on forensic disk dumps or multi-gigabyte video evidence, `compute_dual_hashes` processes the evidence payload in bounded 1 MB streaming blocks:

```python
HASH_CHUNK_SIZE = 1048576  # 1 MB

def compute_dual_hashes(file_path: str, chunk_size: int = HASH_CHUNK_SIZE) -> Tuple[str, str]:
    sha256_hasher = hashlib.sha256()
    sha3_512_hasher = hashlib.sha3_512()

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256_hasher.update(chunk)
            sha3_512_hasher.update(chunk)

    return sha256_hasher.hexdigest().lower(), sha3_512_hasher.hexdigest().lower()
```

---

## 7. Database Model Extensions
The `Evidence` ORM model (`backend/app/models/evidence.py`) was extended with 5 forensic integrity columns:

| Column | Type | Nullable | Description |
| :--- | :--- | :--- | :--- |
| `checksum_sha3_512` | `String(128)` | Yes | 128-hex-character SHA3-512 digest (indexed) |
| `sha3_512_computed_at` | `DateTime(timezone=True)` | Yes | Timestamp when SHA3-512 was calculated |
| `integrity_status` | `String(32)` | Yes | Status (`UNVERIFIED`, `VERIFIED`, `FAILED`) |
| `integrity_verified_at` | `DateTime(timezone=True)` | Yes | Timestamp of successful verification |
| `integrity_verification_message` | `Text` | Yes | Audit summary or mismatch error explanation |

*(Note: `checksum_sha256` is retained from MOD-08 to prevent redundancy).*

---

## 8. REST API Endpoints

### 1. Execute Dual Hashing & Integrity Verification
```http
POST /api/v1/cases/{case_id}/evidence/{evidence_id}/integrity
```
- **Permission**: `evidence:verify`
- **Response**: `200 OK`
```json
{
  "evidence_id": "SAKSHI-EVID-2026-F47DE961",
  "case_id": "SAKSHI-CASE-2026-BB857B59",
  "worm_storage_reference": "worm://SAKSHI-CASE-2026-BB857B59/16e84eb3d45b32b05cb1376044706e1e796373682502621309b5b730685822fb",
  "checksum_sha256": "16e84eb3d45b32b05cb1376044706e1e796373682502621309b5b730685822fb",
  "checksum_sha3_512": "320a9ea9a5ec9a7c64cfb3951f26a17b8f9e6d4c5b...",
  "integrity_status": "VERIFIED",
  "message": "Evidence dual hash integrity successfully verified (SHA-256 match, SHA3-512 generated).",
  "verified_at": "2026-10-02T08:08:50.300000Z",
  "sha256_matched": true,
  "already_verified": false
}
```

### 2. Export Downstream Integrity Contract
```http
GET /api/v1/cases/{case_id}/evidence/{evidence_id}/integrity-contract
```
- **Permission**: `evidence:read`
- **Precondition**: Evidence must have `integrity_status == 'VERIFIED'`.
- **Response**: `200 OK` returning `IntegrityProtectedEvidenceObject`.
- **Failure**: Returns `400 Bad Request` (`INTEGRITY_NOT_VERIFIED`) if requested prior to verification.

---

## 9. Structured Audit Trail
All operations emit structured, tamper-evident audit records via `AuditIntegrationService`:

| Action | Event Type | Trigger | Key Details |
| :--- | :--- | :--- | :--- |
| `EVIDENCE_INTEGRITY_VERIFICATION_STARTED` | `AUDIT_EVIDENCE_INTEGRITY_VERIFICATION_STARTED` | Endpoint invoked | `evidence_id`, `case_id`, `worm_storage_reference`, `mod08_sha256` |
| `EVIDENCE_SHA256_VERIFIED` | `AUDIT_EVIDENCE_SHA256_VERIFIED` | SHA-256 match | `evidence_id`, `case_id`, `sha256` |
| `EVIDENCE_SHA3_512_COMPUTED` | `AUDIT_EVIDENCE_SHA3_512_COMPUTED` | SHA3-512 generated | `evidence_id`, `case_id`, `sha3_512` |
| `EVIDENCE_INTEGRITY_VERIFIED` | `INTEGRITY_VERIFICATION_SUCCESS` | Success | `evidence_id`, `case_id`, dual digests, status |
| `EVIDENCE_INTEGRITY_FAILED` | `INTEGRITY_VERIFICATION_FAILURE` | Mismatch / failure | `evidence_id`, expected vs. actual digests, error reason |

---

## 10. Failure Matrix

| Situation | HTTP Status | Error Code | Integrity Status | Downstream Contract? |
| :--- | :--- | :--- | :--- | :--- |
| Clean WORM evidence | 200 OK | — | `VERIFIED` | **ALLOWED** |
| Evidence not WORM committed | 400 Bad Request | `EVIDENCE_NOT_WORM_COMMITTED` | Unchanged | **BLOCKED** |
| SHA-256 digest mismatch | 422 Unprocessable | `SHA256_INTEGRITY_MISMATCH` | `FAILED` | **BLOCKED** |
| Physical file missing | 404 Not Found | `EVIDENCE_FILE_NOT_FOUND` | `FAILED` | **BLOCKED** |
| Workspace path traversal | 403 Forbidden | `FORBIDDEN` | `FAILED` | **BLOCKED** |
| Out-of-jurisdiction IO | 403 Forbidden | `FORBIDDEN` | Unchanged | **BLOCKED** |
| Unauthenticated request | 401 Unauthorized | `UNAUTHORIZED` | Unchanged | **BLOCKED** |
| Contract fetched before verify | 400 Bad Request | `INTEGRITY_NOT_VERIFIED` | Unchanged | **BLOCKED** |
| Repeated verification | 200 OK | — | `VERIFIED` (`already_verified=True`) | **ALLOWED** |

---

## 11. Verification & Testing

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\main project\backend
collected 220 items

tests\integration\test_antivirus_scan_api.py ..........                  [ 10 passed ]
tests\integration\test_cases_api.py ........                             [  8 passed ]
tests\integration\test_evidence_api.py ......                            [  6 passed ]
tests\integration\test_integrity_api.py .........                       [  9 passed ]
tests\integration\test_mime_validation_api.py .......                    [  7 passed ]
tests\integration\test_worm_commit_api.py .........                      [  9 passed ]
tests\unit\test_antivirus_scan_service.py ............................   [ 28 passed ]
tests\unit\test_auth_service.py .................................        [ 33 passed ]
tests\unit\test_authorization_service.py .........................       [ 25 passed ]
tests\unit\test_case_service.py ........                                 [  8 passed ]
tests\unit\test_evidence_intake_service.py .........                     [  9 passed ]
tests\unit\test_integrity_service.py ...............                     [ 15 passed ]
tests\unit\test_mime_validation_service.py ..................            [ 18 passed ]
tests\unit\test_stage_engine.py ..................                       [ 18 passed ]
tests\unit\test_worm_commit_service.py .................                 [ 17 passed ]

======================= 220 passed, 3 warnings in 4.89s =======================
```

- **Previous Baseline:** 196 passed.
- **New Tests Added:** **24 tests** (15 unit tests + 9 integration tests).
- **Final Result:** **220 passed, 0 failures (100% passing)**.

---

## 12. Definition of Done Checklist

- [x] SHA-256 pre-hash from MOD-08 is verified against recomputed bytes.
- [x] SHA3-512 is implemented and produces 128 lowercase hex characters.
- [x] Streaming chunked I/O processes arbitrarily large files in bounded memory.
- [x] Database model updated with 5 integrity fields (`checksum_sha3_512`, `integrity_status`, etc.).
- [x] Schema contracts created (`IntegrityVerificationResult`, `IntegrityProtectedEvidenceObject`).
- [x] REST API endpoints implemented (`POST /integrity` and `GET /integrity-contract`).
- [x] Centralized RBAC/ABAC authorization integrated (`evidence:verify`).
- [x] Case boundary isolation and path containment enforced.
- [x] Fail-closed behavior on mismatch, missing files, and uncommitted evidence.
- [x] Deterministic idempotency for repeated verification requests.
- [x] Structured audit logging for all integrity events.
- [x] Unit tests cover all 15 test plan scenarios.
- [x] Integration tests cover all 9 pipeline and API scenarios.
- [x] Full regression test passes with zero failures (220/220).
- [x] Comprehensive documentation created (`MOD-09_DUAL_HASHING.md`).
- [x] Downstream handoff contract (`IntegrityProtectedEvidenceObject`) exported for MOD-10 / Phase 4.
