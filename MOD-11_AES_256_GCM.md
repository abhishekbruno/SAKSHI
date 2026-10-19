# MOD-11: AES-256-GCM Encryption
## Phase 3 — Security & Integrity

---

## 1. Overview

**MOD-11 (AES-256-GCM Encryption)** is the third module in **Phase 3: Security & Integrity** of the SAKSHI Investigation Platform. It establishes cryptographic confidentiality, integrity, and tamper-detection for forensic evidence objects at rest, consuming the `ObjectLockedEvidenceObject` contract produced by MOD-10 and yielding the `EncryptedEvidenceObject` downstream contract for MOD-12 (TLS 1.3 / mTLS).

```
PHASE 2 — Evidence Ingestion Pipeline
MOD-05 (Intake) → MOD-06 (MIME) → MOD-07 (AV Scan) → MOD-08 (WORM Commit)
                                                            │
                                                            ▼
PHASE 3 — Security & Integrity Pipeline
                                                            │
                                                            ▼
                                                       MOD-09 ✅
                                                    Dual Hashing
                                               (SHA-256 + SHA3-512)
                                                            │
                                                            ▼
                                                       MOD-10 ✅
                                                   WORM Object Lock
                                                (Immutable Dual Store)
                                                            │
                                                            ▼
                                                       MOD-11 ⬅️ (This Module)
                                                    AES-256-GCM
                                                  (Data At Rest)
                                                            │
                                                            ▼
                                                       MOD-12 ⬜
                                                   TLS 1.3 / mTLS
                                                  (Data In Transit)
```

---

## 2. Architectural Boundaries & Key Management

### Honest Separation of Concerns
The production architecture specifies **HSM/KMS** as the target key-management approach with per-case key isolation. MOD-11 introduces a pluggable, contract-driven `IKeyProvider` abstraction matching the pattern established by `IObjectLockBackend` in MOD-10:

```
                    MOD-11: EncryptionService
                               │
                     ┌─────────┴─────────┐
                     │                   │
               IKeyProvider         AES-256-GCM
                     │             Cipher Engine
               ┌─────┴─────┐             │
               │           │             │
            Dev/Test    HSM/KMS          │
            LocalKey   Production        │
            Provider    Contract         │
               │           │             │
               └─────┬─────┘             │
                     ▼                   ▼
                 Case Key      Authenticated Ciphertext
                     │                   │
                     └─────────┬─────────┘
                               ▼
                    EncryptedEvidenceObject
```

### Key Provider Implementations

| Provider | Environment | Mechanism | Case Isolation Enforcement |
|----------|-------------|-----------|----------------------------|
| `LocalKeyProvider` | Development, Testing, Single-Host | Persists isolated 256-bit symmetric keys in `<case_workspace>/.keys/` with mode `0600` (read-only for owner). Maintains thread-safe in-memory cache. | Strict URI binding (`localkms://cases/<case_id>/keys/...`). Cross-case key requests fail immediately with `CaseKeyIsolationException`. |
| `ProductionHSMKMSProvider` | Cloud / Air-Gapped Enterprise HSM | Architectural contract documenting AWS KMS / Cloud HSM envelope encryption (`kms:GenerateDataKey`, `kms:Decrypt` with Encryption Context `{ "case_id": case_id }`). | Hardware/KMS policy isolation. Guards development by raising a clear exception if credentials are not configured. |

---

## 3. Cryptographic Specification

| Component | Specification | Forensic / Security Rationale |
|-----------|---------------|-------------------------------|
| **Cipher Algorithm** | `AES-256-GCM` | Authenticated Encryption with Associated Data (AEAD). Provides simultaneous confidentiality and tamper-evident message authenticity. |
| **Symmetric Key Size** | 256 bits (32 bytes) | Cryptographically secure random bytes generated via `os.urandom(32)`. Scoped per case. |
| **Initialization Vector (Nonce)** | 96 bits (12 bytes) | Generated uniquely per encryption operation via `os.urandom(12)`. Uniqueness is verified in tests. |
| **Authentication Tag** | 128 bits (16 bytes) | Standard GCM authentication tag. Appended to ciphertext and stored explicitly in metadata (`auth_tag_hex`) for verification. |
| **Associated Authenticated Data (AAD)** | `case_id=<cid>\|evidence_id=<eid>\|sha256=<h1>\|sha3_512=<h2>` | Cryptographically binds ciphertext to the case identity, evidence record, and dual pre-hashes. Ciphertext cannot be transposed to another case or record without invalidating the tag. |
| **Ciphertext Checksum** | SHA-256 | Recomputed over `(ciphertext + tag)` for storage-layer integrity checks. |
| **Fail-Closed Policy** | Strict `InvalidTag` trapping | Any alteration to ciphertext, tag, nonce, or AAD causes immediate failure (`EncryptionTamperException`) and emits audit alert `ENCRYPTION_TAG_MISMATCH_TAMPER_DETECTED`. |

---

## 4. Pipeline Gate Invariants

MOD-11 enforces a strict multi-layer prerequisite gate:

```
[Inbound Request: POST /cases/{case_id}/evidence/{evidence_id}/encrypt]
                         │
                         ▼
        Is Case Valid & Investigator Authorized?
        ('evidence:encrypt' permission via PolicyEngine)
                         │ Yes
                         ▼
        MOD-09 Dual Hash Gate Passed?
        (evidence.integrity_status == 'VERIFIED'
         and dual pre-hashes present)
                         │ Yes
                         ▼
        MOD-10 WORM Object Lock Gate Passed?
        (evidence.lock_status == 'LOCKED'
         and objlock:// reference present)
                         │ Yes
                         ▼
        Already Encrypted? (Idempotency Check)
        ├── If YES: Return existing EncryptionResult (already_encrypted=True)
        └── If NO: Verify physical payload SHA-256 & SHA3-512 against record
                         │ Plaintext Matches
                         ▼
        Acquire Case-Scoped Key (LocalKeyProvider)
                         │
                         ▼
        Generate 96-bit Nonce & Construct AAD
                         │
                         ▼
        Execute AES-256-GCM Encryption
                         │
                         ▼
        Write Ciphertext to <case_workspace>/.encrypted/ (Atomic + Read-Only)
                         │
                         ▼
        In-Memory Trial Decryption Self-Verification
                         │ Decryption Matches
                         ▼
        Update DB (encryption_status = 'ENCRYPTED')
                         │
                         ▼
        Emit Structured Tamper-Evident Audit Event
                         │
                         ▼
        Yield EncryptedEvidenceObject (Contract for MOD-12)
```

---

## 5. REST API Endpoints

### 1. `POST /api/v1/cases/{case_id}/evidence/{evidence_id}/encrypt`
Applies AES-256-GCM encryption to an ObjectLocked evidence item.

**Response Schema (`EncryptionResult`)**:
```json
{
  "evidence_id": "SAKSHI-EVID-2026-F981C02A",
  "case_id": "SAKSHI-CASE-2026-A1B2C3D4",
  "encryption_status": "ENCRYPTED",
  "encryption_algorithm": "AES-256-GCM",
  "encryption_storage_reference": "enc://SAKSHI-CASE-2026-A1B2C3D4/a1b2c3d4e5f67890+9f8e7d6c5b4a3210",
  "key_reference": "localkms://cases/SAKSHI-CASE-2026-A1B2C3D4/keys/aes-256-v1",
  "key_provider": "LOCAL_DEV_KEY_PROVIDER",
  "nonce_hex": "9f8e7d6c5b4a321012345678",
  "auth_tag_hex": "4a5b6c7d8e9f0123456789abcdef0123",
  "aad_binding": "case_id=SAKSHI-CASE-2026-A1B2C3D4|evidence_id=SAKSHI-EVID-2026-F981C02A|sha256=...|sha3_512=...",
  "ciphertext_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "file_size_bytes": 1024,
  "encrypted_file_size_bytes": 1040,
  "encrypted_at": "2026-10-02T14:35:00Z",
  "checksum_sha256": "...",
  "checksum_sha3_512": "...",
  "lock_storage_reference": "objlock://SAKSHI-CASE-2026-A1B2C3D4/...",
  "message": "Evidence 'SAKSHI-EVID-2026-F981C02A' successfully encrypted under AES-256-GCM.",
  "already_encrypted": false
}
```

### 2. `GET /api/v1/cases/{case_id}/evidence/{evidence_id}/encryption-contract`
Exports the `EncryptedEvidenceObject` downstream handoff contract for MOD-12.

**Downstream Handoff Contract (`EncryptedEvidenceObject`)**:
```json
{
  "case_id": "SAKSHI-CASE-2026-A1B2C3D4",
  "evidence_id": "SAKSHI-EVID-2026-F981C02A",
  "original_file_name": "report.pdf",
  "evidence_category": "DOCUMENT_PDF",
  "file_size_bytes": 1024,
  "encrypted_file_size_bytes": 1040,
  "worm_storage_reference": "worm://...",
  "lock_storage_reference": "objlock://...",
  "encryption_storage_reference": "enc://...",
  "encryption_status": "ENCRYPTED",
  "encryption_algorithm": "AES-256-GCM",
  "key_reference": "localkms://cases/SAKSHI-CASE-2026-A1B2C3D4/keys/aes-256-v1",
  "key_provider": "LOCAL_DEV_KEY_PROVIDER",
  "nonce_hex": "9f8e7d6c5b4a321012345678",
  "auth_tag_hex": "4a5b6c7d8e9f0123456789abcdef0123",
  "aad_binding": "...",
  "checksum_sha256": "...",
  "checksum_sha3_512": "...",
  "ciphertext_sha256": "...",
  "encrypted_at": "2026-10-02T14:35:00Z",
  "source": "MOD-11"
}
```

### 3. `POST /api/v1/cases/{case_id}/evidence/{evidence_id}/verify-encryption`
Performs cryptographic verification without exposing plaintext to the caller.

**Response Schema (`EncryptionVerificationResult`)**:
```json
{
  "evidence_id": "SAKSHI-EVID-2026-F981C02A",
  "case_id": "SAKSHI-CASE-2026-A1B2C3D4",
  "encryption_status": "ENCRYPTED",
  "verification_status": "VERIFIED",
  "tag_valid": true,
  "ciphertext_integrity_matched": true,
  "dual_hash_integrity_matched": true,
  "key_reference": "localkms://...",
  "verified_at": "2026-10-02T14:36:00Z",
  "message": "AES-256-GCM encryption verified: authentication tag, ciphertext hash, and dual-hash integrity validated."
}
```

---

## 6. Database Schema Extensions

The `evidence` table in `app/models/evidence.py` has been updated with the following columns:

| Column | Type | Index | Description |
|--------|------|:-----:|-------------|
| `encryption_status` | `VARCHAR(32)` | Yes | `UNENCRYPTED` \| `ENCRYPTED` \| `ENCRYPTION_FAILED` |
| `encryption_algorithm` | `VARCHAR(32)` | No | `AES-256-GCM` |
| `encryption_key_reference` | `VARCHAR(256)` | No | Case-scoped key reference URI (`localkms://cases/<case_id>/keys/...`) |
| `encryption_key_provider` | `VARCHAR(64)` | No | Active key provider backend (`LOCAL_DEV_KEY_PROVIDER` \| `AWS_KMS`) |
| `encryption_storage_reference` | `VARCHAR(512)` | No | Canonical reference `enc://<case_id>/<sha256_prefix>+<nonce_prefix>` |
| `encryption_nonce_hex` | `VARCHAR(64)` | No | 96-bit (12 bytes) IV/nonce in hex (24 chars) |
| `encryption_auth_tag_hex` | `VARCHAR(64)` | No | 128-bit (16 bytes) GCM authentication tag in hex (32 chars) |
| `encryption_aad` | `TEXT` | No | Associated Authenticated Data bound to ciphertext |
| `ciphertext_sha256` | `VARCHAR(64)` | Yes | SHA-256 checksum of the encrypted payload file |
| `encrypted_file_size_bytes` | `INTEGER` | No | Measured byte length of ciphertext + tag |
| `encrypted_file_path` | `VARCHAR(512)` | No | Absolute filesystem path within isolated case workspace |
| `encrypted_at` | `DATETIME(tz)` | No | UTC timestamp of successful encryption |
| `encryption_failure_reason` | `TEXT` | No | Error message if encryption status transitioned to `ENCRYPTION_FAILED` |
| `encryption_event_log` | `TEXT` | No | Append-only JSON array of encryption lifecycle events |

---

## 7. Verification & Test Results

```
========================================================================
MOD-11 Verification Summary
========================================================================
Component                                          Status
-------------------------------------------------- --------------------
Consumes ObjectLockedEvidenceObject (MOD-10)       ✅ Complete
AES-256-GCM Authenticated Encryption               ✅ Complete
96-bit Nonce Generation & Uniqueness                ✅ Complete
128-bit GCM Auth Tag Verification                  ✅ Complete
Cryptographic AAD Binding                          ✅ Complete
Pluggable IKeyProvider Abstraction                ✅ Complete
LocalKeyProvider (Dev/Test Case Isolation)        ✅ Complete
ProductionHSMKMSProvider (Architectural Contract)  ✅ Complete
Trial Decryption & Round-Trip Dual-Hash Checks     ✅ Complete
Fail-Closed Tamper Detection (Ciphertext & Tag)    ✅ Complete
Idempotent Re-Encryption Check                     ✅ Complete
Produces EncryptedEvidenceObject (for MOD-12)     ✅ Complete
RBAC Authorization ('evidence:encrypt')            ✅ Complete
Audit Events via AuditIntegrationService           ✅ Complete
Unit Tests                                         20 Passed
Integration Tests                                  11 Passed
Total Test Suite                                   298 Passed (0 Failures)
========================================================================
```

---

## 8. Next Step: MOD-12 — TLS 1.3 / mTLS

The completion of MOD-11 prepares the downstream contract:
```
EncryptedEvidenceObject (MOD-11)
          │
          ▼
       MOD-12
    TLS 1.3/mTLS
   Data In Transit
```
MOD-12 will establish cryptographic transit security (mutual TLS / TLS 1.3 cipher suites) for the SAKSHI platform.
