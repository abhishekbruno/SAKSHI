# SAKSHI: Phase 2 — Module 6: MIME / File Signature Validation (MOD-06)
## Technical Architecture & Implementation Reference

---

### 1. Module Overview & Purpose

The **MIME / File Signature Validation Service (MOD-06)** is the second stage of **Phase 2: Evidence Ingestion** in SAKSHI (**Evidence-Constrained Modus Operandi Reconstruction — EC-MORE**).

* **Source-defined Function:** `Validate actual file type`
* **Phase:** `02 — Evidence Ingestion`
* **Input:** `RegisteredEvidenceObject` from MOD-05 + Staged Raw Evidence File + Authenticated Investigator Context
* **Output:** `ValidatedEvidenceObject` (for valid evidence) or `REJECTED` state with audit record
* **Downstream Consumer:** `MOD-07 — Antivirus Scan`

#### Architectural Principle
> *"MOD-06 answers one question: 'Does the actual binary content of this registered evidence match its claimed type?' It treats file names, extensions, and client-supplied MIME headers as entirely untrusted. By inspecting true binary magic bytes, bounded memory buffers, and allowlist policies, MOD-06 rejects disguised executables, scripts, and unknown binaries before they can reach antivirus scanning or forensic analysis."*

---

### 2. Phase 2 Pipeline Flow & Position

```
                  MOD-05
              Evidence Intake
                    │
                    ▼
          RegisteredEvidenceObject
                    │
                    ▼
          ┌─────────────────────┐
          │       MOD-06        │
          │ MIME / Signature    │
          │     Validation      │
          └──────────┬──────────┘
                     │
             ┌───────┴────────┐
             │                │
           VALID           INVALID
             │                │
             ▼                ▼
          MOD-07           REJECT
         Antivirus            │
             │                ▼
             ▼             AUDIT
          MOD-08
       WORM + checksum
```

---

### 3. Input Contract (`RegisteredEvidenceObject`)

MOD-06 directly consumes the formal output contract produced by MOD-05:

```python
class RegisteredEvidenceObject(BaseModel):
    evidence_id: str
    case_id: str
    staged_file_path: str
    original_file_name: str
    declared_mime_type: str
    evidence_category: str
    file_size_bytes: int
    submitting_investigator_id: str
    intake_status: str
    registered_at: datetime
```

---

### 4. MIME Detection & Magic-Byte Architecture

1. **Bounded Header Reads**:
   - Files are never read entirely into RAM.
   - Initial `8192` bytes (8 KB) are read directly from the staged file path.
   - Supports multi-gigabyte forensic disk dumps, CCTV videos, and high-resolution autopsy photography without memory spikes.

2. **Detection Layer**:
   - **Manual High-Confidence Signatures**: Fast-path binary matching for critical formats (`%PDF`, `\xFF\xD8\xFF`, `\x89PNG\r\n\x1a\n`, `RIFF....WAVE`, `RIFF....WEBP`, `ID3`, `OggS`, `fLaC`, `\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1`).
   - **`puremagic` Library**: Deterministic python-native magic byte matcher for secondary formats with zero C-library dependencies.
   - **Plain Text / CSV Validator**: Verifies stream contains only valid printable text (ASCII/UTF-8/UTF-16) and contains zero null bytes (`\x00`).

---

### 5. Centralized Allowed Evidence Types (Allowlist)

| MIME Type | Format | Approved Categories | Permitted Extensions |
| :--- | :---: | :---: | :---: |
| `application/pdf` | PDF | `DOCUMENT_PDF`, `OTHER` | `.pdf` |
| `image/jpeg` | JPEG | `SCENE_PHOTO`, `AUTOPSY_PHOTO`, `OTHER` | `.jpg`, `.jpeg`, `.jfif` |
| `image/png` | PNG | `SCENE_PHOTO`, `AUTOPSY_PHOTO`, `OTHER` | `.png` |
| `image/tiff` | TIFF | `SCENE_PHOTO`, `AUTOPSY_PHOTO`, `OTHER` | `.tif`, `.tiff` |
| `image/webp` | WEBP | `SCENE_PHOTO`, `AUTOPSY_PHOTO`, `OTHER` | `.webp` |
| `audio/wav`, `audio/x-wav` | WAV | `AUDIO_RECORDING`, `OTHER` | `.wav` |
| `audio/mpeg`, `audio/mp3` | MP3 | `AUDIO_RECORDING`, `OTHER` | `.mp3` |
| `audio/ogg` | OGG | `AUDIO_RECORDING`, `OTHER` | `.ogg` |
| `audio/flac` | FLAC | `AUDIO_RECORDING`, `OTHER` | `.flac` |
| `text/csv` | CSV | `CDR_SPREADSHEET`, `OTHER` | `.csv` |
| `text/plain` | TEXT | `CDR_SPREADSHEET`, `DIGITAL_DEVICE_EXTRACTION`, `OTHER` | `.txt`, `.tsv`, `.log` |
| `application/vnd.ms-excel` | XLS | `CDR_SPREADSHEET`, `OTHER` | `.xls` |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | XLSX | `CDR_SPREADSHEET`, `OTHER` | `.xlsx` |
| `application/zip` | ZIP | `DIGITAL_DEVICE_EXTRACTION`, `OTHER` | `.zip` |
| `application/gzip` | GZIP | `DIGITAL_DEVICE_EXTRACTION`, `OTHER` | `.gz`, `.tar.gz` |
| `application/json` | JSON | `DIGITAL_DEVICE_EXTRACTION`, `OTHER` | `.json` |

---

### 6. Disallowed Signatures & Rejection Rules

Evidence is immediately **REJECTED** if:
1. **Executable Binary Detected**:
   - Windows PE (`b"MZ"`)
   - Linux ELF (`b"\x7fELF"`)
   - Mach-O Binaries (`b"\xca\xfe\xba\xbe"`, `b"\xfe\xed\xfa\xce"`, `b"\xfe\xed\xfa\xcf"`)
   - Shell Scripts (`b"#!/bin/"`, `b"#!/usr/bin/"`)
2. **Signature Mismatch**: Declared MIME does not match detected binary signature (e.g., JPEG masquerading as PDF).
3. **MIME Not in Allowlist**: Declared type is not among approved forensic evidence formats.
4. **Dangerous Extension**: Extension contradicts detected content (e.g. `.exe` on PDF content).
5. **Empty Payload**: File is 0 bytes.
6. **Unrecognized / Ambiguous Signature**: Binary headers cannot be safely identified or present polyglot conflicts.

---

### 7. Security Controls & Case Isolation

1. **Authentication (MOD-02)**: Validated Bearer JWT required for all validation calls.
2. **Authorization (MOD-03)**:
   - Evaluates `Permission.EVIDENCE_VALIDATE` (`evidence:validate`).
   - Case-level access: Assigned IO or supervisory officer required.
3. **Workspace Boundary Containment**:
   - `staged_path` must start with `case.case_workspace_path`.
   - Prevents path traversal and cross-case tampering.
4. **Cross-Case Isolation**:
   - Evidence records must match `case_id` in database query.
   - Case A cannot validate or inspect Case B evidence.

---

### 8. Audit Logging

Validation decisions trigger immutable structured audit records via `AuditIntegrationService`:

* **`AUDIT_EVIDENCE_MIME_VALIDATED`**: Emitted when binary signature matches declared MIME.
* **`AUDIT_EVIDENCE_MIME_REJECTED`**: Emitted when signature fails, mismatches, or contains dangerous payloads.
* Audit Payload includes: `evidence_id`, `case_id`, `declared_mime`, `detected_mime`, `detected_format`, `reason`, `validator_version`, `timestamp`. Never logs raw evidence content or tokens.

---

### 9. REST API Endpoints

#### 9.1 `POST /api/v1/cases/{case_id}/evidence/{evidence_id}/validate`
Validates registered evidence against true binary signature.

**Success Response (200 OK — Valid):**
```json
{
  "evidence_id": "SAKSHI-EVID-2026-9C4B1E72",
  "case_id": "SAKSHI-CASE-2026-8F3E9A21",
  "valid": true,
  "status": "VALIDATED",
  "declared_mime": "application/pdf",
  "detected_mime": "application/pdf",
  "detected_format": "PDF",
  "declared_extension": ".pdf",
  "validation_reason": "Binary signature matches declared MIME 'application/pdf' (PDF).",
  "validator_version": "SAKSHI-MIME-V1.0",
  "validated_at": "2026-10-02T11:40:00Z"
}
```

**Success Response (200 OK — Rejected):**
```json
{
  "evidence_id": "SAKSHI-EVID-2026-9C4B1E72",
  "case_id": "SAKSHI-CASE-2026-8F3E9A21",
  "valid": false,
  "status": "REJECTED",
  "declared_mime": "application/pdf",
  "detected_mime": "image/jpeg",
  "detected_format": "JPEG",
  "declared_extension": ".pdf",
  "validation_reason": "Binary signature mismatch: declared MIME is 'application/pdf', but actual binary signature corresponds to 'image/jpeg' (JPEG).",
  "validator_version": "SAKSHI-MIME-V1.0",
  "validated_at": "2026-10-02T11:40:00Z"
}
```

#### 9.2 `GET /api/v1/cases/{case_id}/evidence/{evidence_id}/validated-contract`
Exports `ValidatedEvidenceObject` handoff contract for MOD-07 (Antivirus Scan).
* **200 OK**: If evidence has `status == 'VALIDATED'`.
* **400 Bad Request**: If evidence has `status == 'REJECTED'` or `REGISTERED_INTAKE` (`EVIDENCE_VALIDATION_FAILED`).

---

### 10. Downstream Hand-off Contract to MOD-07 (`ValidatedEvidenceObject`)

```python
class ValidatedEvidenceObject(BaseModel):
    """
    Contract produced by MOD-06 (MIME / Signature Validation) and consumed by MOD-07 (Antivirus Scan).
    Strict Invariant: Only files with status == 'VALIDATED' can yield this contract.
    """
    evidence_id: str
    case_id: str
    staged_file_path: str
    original_file_name: str
    verified_mime_type: str
    detected_format: str
    evidence_category: str
    file_size_bytes: int
    submitting_investigator_id: str
    validation_status: str
    validated_at: datetime
```

---

### 11. Test Verification

Complete test suite across Phase 1 and Phase 2:
```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\main project\backend
plugins: anyio-4.15.1, asyncio-0.26.0
collected 132 items

tests\integration\test_cases_api.py ........                             [  6%]
tests\integration\test_evidence_api.py ......                            [ 10%]
tests\integration\test_mime_validation_api.py .......                    [ 15%]
tests\unit\test_auth_service.py .................................        [ 40%]
tests\unit\test_authorization_service.py .........................       [ 59%]
tests\unit\test_case_service.py ........                                 [ 65%]
tests\unit\test_evidence_intake_service.py .........                     [ 72%]
tests\unit\test_mime_validation_service.py ..................            [ 86%]
tests\unit\test_stage_engine.py ..................                       [100%]

======================= 132 passed, 1 warning in 2.62s ========================
```

* **MOD-01 Case Management**: 16 passed
* **MOD-02 Identity / OIDC**: 33 passed
* **MOD-03 RBAC / ABAC**: 25 passed
* **MOD-04 Stage Engine**: 18 passed
* **MOD-05 Evidence Intake**: 15 passed
* **MOD-06 MIME / Signature Validation**: 25 passed (18 unit + 7 integration)
* **Total**: **132 passed (0 failures)**

---

### 12. Known Limitations & Next Module

* **MOD-06 does NOT perform Antivirus Scanning**: Delegated strictly to **MOD-07**.
* **MOD-06 does NOT perform WORM commit, dual hashing, or Object Locking**: Delegated to **MOD-08** and **Phase 3**.
* **Next Module in Phase 2:** `MOD-07 — Antivirus Scan`.
