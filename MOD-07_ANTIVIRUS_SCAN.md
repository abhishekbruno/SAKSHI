# MOD-07 — Antivirus Scan
**Phase 2: Evidence Ingestion**  
**SAKSHI — Explainable AI Investigation Companion**  
**Paradigm: Evidence-Constrained Modus Operandi Reconstruction (EC-MORE)**

---

## 1. Purpose
MOD-07 is the third node in the SAKSHI Phase 2 Evidence Ingestion pipeline. It consumes the `ValidatedEvidenceObject` emitted by MOD-06 (MIME / File Signature Validation) and executes an offline, passive antivirus and malware scan on the staged evidence payload without executing or interpreting any code inside the file.

MOD-07 ensures that no known hostile payload (viruses, Trojans, worms, droppers, macro exploits, or malicious shellcode) penetrates downstream forensic analysis or reaches WORM storage (MOD-08).

```
MOD-05 Evidence Intake
        │
        ▼ (RegisteredEvidenceObject)
MOD-06 MIME / Signature Validation
        │
        ▼ (ValidatedEvidenceObject)
┌──────────────────────────────────────────────┐
│       MOD-07: ANTIVIRUS SCAN                │
│                                              │
│   Passive Inspection without Execution       │
│   Fail-Closed Security Model                 │
└──────────────────────┬───────────────────────┘
                       │
             ┌─────────┴─────────┐
             │                   │
      ClamAV Available     ClamAV Unavailable
             │                   │
             ▼                   ▼
        Scan payload       SCANNER_UNAVAILABLE
             │                   │
       ┌─────┴─────┐             │
       ▼           ▼             ▼
     CLEAN       THREAT       BLOCKED
  "No threat       │             │
   detected"       ▼             ▼
       │      QUARANTINED   MOD-08 Blocked
       ▼           │
     MOD-08        ▼
    Allowed   Audit Event
```

---

## 2. Antivirus Verdict Semantics

> [!IMPORTANT]
> **PRECISE SEMANTIC DEFINITION OF `CLEAN`:**
> 
> **`CLEAN` means that the configured antivirus scanner completed successfully and detected no threat.**
> 
> A `CLEAN` verdict represents the finding of the configured antivirus scanner and is **not an absolute guarantee that the payload contains no malware**. The system does not claim that evidence is "proven harmless", "certified benign", or "malware-free with certainty". It strictly certifies that the configured scanner inspected the payload and detected no known threat signatures or suspicious heuristic patterns.

All API responses, audit records, and internal logs conform to this semantic standard:
- Result message: `"No threat detected by the configured antivirus scanner (<scanner_name>)."`
- Audit event description: `"Antivirus scan completed with no threat detected by configured scanner."`
- API contract: `antivirus_verdict: "CLEAN"` reflects the scanner finding, never absolute forensic proof of harmlessness.

---

## 3. Scanner Selection and Fail-Closed Behavior

SAKSHI enforces an explicit, fail-closed scanner selection policy configured via application settings (`ANTIVIRUS_SCANNER`):

```
                        ANTIVIRUS_SCANNER
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
       "clamav" (Production)        "eicar_heuristic" (Dev/Test)
               │                               │
        ClamAVScanner                EicarHeuristicScanner
               │                               │
       ┌───────┴───────┐                       │
       ▼               ▼                       ▼
   Available      Unavailable          Explicit Test Scan
       │               │
  Scan Payload  SCANNER_UNAVAILABLE
                       │
               Fail-Closed (Blocked)
```

### Critical Production Invariant: No Silent Heuristic Downgrade
If `ANTIVIRUS_SCANNER="clamav"` is configured and the ClamAV daemon is unreachable, offline, times out, or fails:
- **The system MUST NEVER silently switch to `EicarHeuristicScanner` and return `CLEAN` for an arbitrary file.**
- The scan immediately terminates with `SCANNER_UNAVAILABLE` (HTTP 503), `SCAN_TIMEOUT` (HTTP 504), or `SCAN_ERROR` (HTTP 400).
- Evidence status remains in `VALIDATED` (non-clean).
- Downstream handoff contract (`ScannedEvidenceObject`) is **denied**.
- Progression to MOD-08 is strictly **blocked**.

### Explicit `EicarHeuristicScanner` Usage
`EicarHeuristicScanner` is an **explicit scanner choice** designed for development, unit testing, and deterministic CI environments.
- It is only invoked when `ANTIVIRUS_SCANNER="eicar_heuristic"` is explicitly set or passed to the service.
- It identifies standard harmless EICAR test artifacts (`X5O!P%@AP[4\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*`) and suspicious NOP sled shellcode sequences.
- It clearly identifies its scanner identity in all outputs as `scanner_name = "EicarHeuristicScanner"`.
- It is never misrepresented as a ClamAV scan.

---

## 4. Scope & Boundary Rules

### What MOD-07 Implements:
- Passive inspection of staged file bytes without executing or loading binaries.
- Engine abstraction (`IAntivirusScanner`) decoupling business logic from concrete AV scanners.
- Standard harmless EICAR detection and heuristic exploit pattern analysis.
- Fail-closed security architecture: scanner timeouts, missing daemons, and connection failures strictly halt progression and reject `CLEAN` certification.
- State transitions: `VALIDATED` $\rightarrow$ `CLEAN` or `QUARANTINED`.
- Downstream handoff contract: `ScannedEvidenceObject` strictly available only for `CLEAN` evidence.
- Full RBAC / ABAC authorization integration using MOD-03 (`evidence:scan`).
- Workspace path canonicalization and case boundary isolation.
- Tamper-evident structured audit logging via `AuditIntegrationService`.

### What MOD-07 Strictly Does NOT Implement:
- File MIME or magic-byte validation (handled by MOD-06).
- Program execution or script execution (prohibited).
- Cryptographic hashing (SHA-256 / SHA3-512) and WORM storage commitment (reserved for MOD-08).
- Object Lock, dual hashing, and Merkle audit ledgers (reserved for Phase 3).
- AI analysis, OCR, or contextual modus operandi reconstruction (Phase 4).

---

## 5. Input & Output Contracts

### Input Contract: `ValidatedEvidenceObject` (from MOD-06)
```python
class ValidatedEvidenceObject(BaseModel):
    evidence_id: str
    case_id: str
    staged_file_path: str
    original_file_name: str
    verified_mime_type: str
    detected_format: str
    evidence_category: str
    file_size_bytes: int
    submitting_investigator_id: str
    validation_status: str  # Must be 'VALIDATED'
    validated_at: datetime
```

### Downstream Handoff Contract: `ScannedEvidenceObject` (to MOD-08)
Strictly generated **only** if verdict is `CLEAN` and no threat was detected:
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
    mime_status: str           # "VALIDATED"
    antivirus_verdict: str     # "CLEAN"
    antivirus_scanner: str     # e.g. "ClamAVScanner" or "EicarHeuristicScanner"
    antivirus_scanned_at: datetime
```

### API Scan Result: `AntivirusScanResult`
```python
class AntivirusScanResult(BaseModel):
    evidence_id: str
    case_id: str
    verdict: AntivirusVerdict  # CLEAN, THREAT_DETECTED, SCAN_ERROR, SCANNER_UNAVAILABLE, SCAN_TIMEOUT
    status: str                # "CLEAN", "QUARANTINED", "ERROR"
    scanner_name: str
    scanner_version: str
    threat_name: Optional[str] = None
    message: str               # "No threat detected by the configured antivirus scanner (<scanner_name>)."
    duration_ms: Optional[float] = None
    scanned_at: datetime
```

---

## 6. Scanner Matrix & Outcomes

| Situation | Scanner Verdict | Evidence Status | Downstream Contract? | MOD-08 Handoff? |
| :--- | :--- | :--- | :--- | :--- |
| ClamAV scans + no threat | `CLEAN` | `CLEAN` | Available (`ScannedEvidenceObject`) | **ALLOWED** |
| ClamAV detects malware | `THREAT_DETECTED` | `QUARANTINED` | Rejected (422) | **BLOCKED** |
| ClamAV daemon unavailable | `SCANNER_UNAVAILABLE` | `VALIDATED` | Rejected (503) | **BLOCKED** |
| ClamAV scan timeout | `SCAN_TIMEOUT` | `VALIDATED` | Rejected (504) | **BLOCKED** |
| ClamAV internal error | `SCAN_ERROR` | `VALIDATED` | Rejected (400) | **BLOCKED** |
| Explicit Heuristic + EICAR | `THREAT_DETECTED` | `QUARANTINED` | Rejected (422) | **BLOCKED** |
| Explicit Heuristic + normal file | `CLEAN` | `CLEAN` | Available (`ScannedEvidenceObject`) | **ALLOWED** |

---

## 7. RBAC / ABAC Authorization & Boundary Isolation

- **Permission**: `evidence:scan` (`Permission.EVIDENCE_SCAN`).
- **Enforcement**: Integrated with MOD-03 centralized policy engine. Requires authenticated investigator holding `INVESTIGATING_OFFICER` (assigned to case), `SUPERVISORY_OFFICER`, or `STATION_HEAD`.
- **Default Deny**: Unauthenticated $\rightarrow$ 401; Unauthorized $\rightarrow$ 403.
- **Case Isolation**: Canonical path resolution (`os.path.realpath`) verifies storage location resides strictly within `case.case_workspace_path`. Directory traversal (`../../`) triggers `WORKSPACE_BOUNDARY_VIOLATION` audit log and immediate 403 Forbidden.

---

## 8. Audit Trail Integration

| Action | Event Type | Trigger | Key Details |
| :--- | :--- | :--- | :--- |
| `EVIDENCE_AV_SCAN_STARTED` | `AUDIT_EVIDENCE_AV_SCAN_STARTED` | Scan initiated | `evidence_id`, `case_id`, `scanner`, `scanner_version` |
| `EVIDENCE_AV_CLEAN` | `ANTIVIRUS_SCAN_CLEAN` | No threat detected | `evidence_id`, `case_id`, `verdict`, `scanner`, `semantic_meaning` |
| `EVIDENCE_AV_THREAT_DETECTED` | `ANTIVIRUS_THREAT_DETECTED` | Threat found | `evidence_id`, `threat_name`, `message`, `scanner` |
| `EVIDENCE_AV_SCAN_ERROR` | `ANTIVIRUS_SCAN_FAILURE` | Scanner fail/timeout | `evidence_id`, `failure_reason`, `verdict`, `scanner` |

---

## 9. Verification & Test Suite

The complete test suite runs against SQLite in-memory databases with 100% test isolation:

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0
collected 170 items

tests\integration\test_antivirus_scan_api.py ..........                  [ 10 passed ]
tests\integration\test_cases_api.py ........                             [  8 passed ]
tests\integration\test_evidence_api.py ......                            [  6 passed ]
tests\integration\test_mime_validation_api.py .......                    [  7 passed ]
tests\unit\test_antivirus_scan_service.py ............................   [ 28 passed ]
tests\unit\test_auth_service.py .................................        [ 33 passed ]
tests\unit\test_authorization_service.py .........................       [ 25 passed ]
tests\unit\test_case_service.py ........                                 [  8 passed ]
tests\unit\test_evidence_intake_service.py .........                     [  9 passed ]
tests\unit\test_mime_validation_service.py ..................            [ 18 passed ]
tests\unit\test_stage_engine.py ..................                       [ 18 passed ]

======================= 170 passed, 1 warning in 3.24s ========================
```

- **Previous Baseline**: 162 passed (0 failures).
- **Hardening Tests Added**: 8 unit tests (Clean Semantics, ClamAV Unavailable, No Unsafe Fallback, Explicit Heuristic EICAR, Explicit Heuristic Clean, ClamAV Timeout, ClamAV Error, Scanner Identity).
- **Final Total**: **170 passed (0 failures)**.

---

## 10. Boundary with MOD-08

> [!IMPORTANT]
> **MOD-07 DOES NOT PROVIDE CRYPTOGRAPHIC IMMUTABILITY.**
> 
> MOD-07 only certifies that the staged payload was scanned by the configured engine and no threat was detected.
> The calculation of authoritative SHA-256 pre-hashes, conversion to read-only WORM storage, and downstream hash commitment belong exclusively to **MOD-08: WORM Commit + Checksum**.
