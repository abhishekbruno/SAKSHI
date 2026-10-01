# MOD-04: Stage Engine Specification

**SAKSHI — Explainable AI Investigation Companion for Unnatural Death Investigations using Evidence-Constrained Modus Operandi Reconstruction (EC-MORE)**  
**Phase 1 — Case Initiation | Module 4: Stage Engine**

---

## 1. Purpose & Overview

The **Stage Engine (MOD-04)** is the deterministic state machine governing the lifecycle progression of death investigations within the SAKSHI platform.

It ensures that cases advance in a forensically rigorous sequence, preventing illegal state jumps (such as closing a case before evidence is ingested and analyzed), while supporting legitimate investigative feedback loops (such as returning to evidence ingestion when analytical gaps are discovered).

---

## 2. Platform Architecture Flow

The complete Phase 1 request pipeline operates under a 4-tier chain of responsibility:

```
                    HTTP REQUEST
                         │
                         ▼
                ┌────────────────┐
                │     MOD-02     │
                │ Identity/OIDC  │
                └────────┬───────┘
                         │ "Who are you?"
                         ▼
             AuthenticatedInvestigator
                         │
                         ▼
                ┌────────────────┐
                │     MOD-03     │
                │   RBAC / ABAC  │
                └────────┬───────┘
                         │ "Are you allowed to act on this case?"
                         ▼
                ┌────────────────┐
                │     MOD-04     │
                │  Stage Engine  │
                └────────┬───────┘
                         │ "Is this lifecycle transition valid?"
                         ▼
                   Valid Transition?
                     /          \
                   NO            YES
                   │              │
                   ▼              ▼
                 400        ┌────────────┐
             Bad Request    │   MOD-01   │
             (Rejected)     │ Case State │
                            └────────────┘
```

---

## 3. Investigation Lifecycle Stages

| Stage Enum | Value | Phase Mapping | Purpose |
| :--- | :--- | :--- | :--- |
| `INITIALIZED` | `"INITIALIZED"` | Phase 1 | Initial FIR registration, Case ID established, workspace boundary allocated. |
| `EVIDENCE_INGESTION` | `"EVIDENCE_INGESTION"` | Phase 2 | Evidence Gate open; multi-modal evidence objects (photos, docs, audio) uploaded. |
| `EVIDENCE_PROCESSING`| `"EVIDENCE_PROCESSING"`| Phase 3 | SHA-256 integrity verification, OCR extraction, Whisper audio transcription. |
| `ANALYSIS` | `"ANALYSIS"` | Phase 4–7 | Event timeline reconstruction, EC-MORE reasoning, contradiction matrix evaluation. |
| `REVIEW` | `"REVIEW"` | Phase 8 | Supervisory review, final report and charge sheet drafting. |
| `CLOSED` | `"CLOSED"` | Final State | Case investigation finalized, signed, archived, or submitted to court. |
| `SUSPENDED` | `"SUSPENDED"` | Administrative | Investigation paused due to judicial stay or pending external lab analysis. |
| `REOPENED` | `"REOPENED"` | Exception | Closed case reopened by supervisory clearance upon discovery of new evidence. |

---

## 4. State Machine Transition Graph

```
             ┌───────────────┐
             │  INITIALIZED  │◄────────────┐
             └───────┬───────┘             │
                     │                     │
                     ▼                     │
         ┌───────────────────────┐         │
         │  EVIDENCE_INGESTION   │─────────┘
         └───────────┬───────────┘
                     │  ▲
                     ▼  │ (new evidence)
         ┌───────────────────────┐
         │  EVIDENCE_PROCESSING  │
         └───────────┬───────────┘
                     │  ▲
                     ▼  │ (forensic gap)
         ┌───────────────────────┐
         │       ANALYSIS        │
         └───────────┬───────────┘
                     │  ▲
                     ▼  │ (supervisor clarification)
         ┌───────────────────────┐
         │        REVIEW         │
         └───────────┬───────────┘
                     │ (Supervisory Only)
                     ▼
         ┌───────────────────────┐
         │        CLOSED         │
         └───────────┬───────────┘
                     │ (Supervisory Only)
                     ▼
         ┌───────────────────────┐
         │       REOPENED        │
         └───────────────────────┘
```

### Transition Matrix (`STAGE_TRANSITIONS`):

| Current Stage | Permitted Target Stages | Notes |
| :--- | :--- | :--- |
| `INITIALIZED` | `EVIDENCE_INGESTION`, `SUSPENDED` | Initial advancement to evidence gate |
| `EVIDENCE_INGESTION` | `EVIDENCE_PROCESSING`, `INITIALIZED`, `SUSPENDED` | Advance or rollback before locking |
| `EVIDENCE_PROCESSING`| `ANALYSIS`, `EVIDENCE_INGESTION`, `SUSPENDED` | Proceed to analysis or request more items |
| `ANALYSIS` | `REVIEW`, `EVIDENCE_INGESTION`, `SUSPENDED` | Send for review or loop back on evidence gaps |
| `REVIEW` | `CLOSED`, `ANALYSIS`, `EVIDENCE_INGESTION`, `SUSPENDED` | Finalize or reject back to analytical team |
| `SUSPENDED` | Any prior active state | Resumes from prior operational state |
| `CLOSED` | `REOPENED` | Requires supervisory authority |
| `REOPENED` | `EVIDENCE_INGESTION`, `ANALYSIS`, `SUSPENDED` | Resumes active investigation loop |

---

## 5. Transition Rules & Invariants

1. **Deterministic Legality**: Only transitions explicitly present in the transition graph are permitted. All others yield an immediate `InvalidStageException` (HTTP 400).
2. **Anti-Skipping Protection**: Direct jumps that bypass mandatory investigation stages (e.g. `INITIALIZED -> CLOSED` or `INITIALIZED -> ANALYSIS`) are strictly rejected.
3. **Idempotent / Redundant Check**: Attempting to transition to the current stage (e.g. `INITIALIZED -> INITIALIZED`) is rejected.
4. **Supervisory Clearance**:
   - `REVIEW -> CLOSED`: Only supervisory roles (`SUPERVISORY_OFFICER`, `STATION_HEAD`, `ADMIN`) can officially close a case.
   - `CLOSED -> REOPENED`: Only supervisory roles can reopen an archived case.
5. **Unknown Stage Protection**: Any unrecognized stage string returns a clear error listing the valid canonical stages.

---

## 6. API Endpoints

### 1. `GET /api/v1/cases/{case_id}/stage`
Returns current stage metadata and permissible target transitions:
```json
{
  "case_id": "SAKSHI-CASE-2026-8F3E9A21",
  "lifecycle_stage": "INITIALIZED",
  "status": "ACTIVE",
  "allowed_transitions": [
    "EVIDENCE_INGESTION",
    "SUSPENDED"
  ]
}
```

### 2. `POST /api/v1/cases/{case_id}/stage`
Advances the case lifecycle stage if permitted by Stage Engine:

**Request Payload:**
```json
{
  "lifecycle_stage": "EVIDENCE_INGESTION"
}
```

**Success (200 OK):**
Returns updated `CaseResponse` reflecting new `lifecycle_stage`.

**Invalid Transition (400 Bad Request):**
```json
{
  "error_code": "INVALID_STAGE",
  "message": "Invalid lifecycle transition from 'INITIALIZED' to 'CLOSED'. Permitted transitions: ['EVIDENCE_INGESTION', 'SUSPENDED']",
  "details": null
}
```

---

## 7. Audit Logging

Every state transition produces a structured audit record:
```json
{
  "event_type": "AUDIT_STAGE_TRANSITION",
  "message": "Audit action 'STAGE_TRANSITION' on case 'SAKSHI-CASE-2026-8F3E9A21'",
  "case_id": "SAKSHI-CASE-2026-8F3E9A21",
  "investigator_id": "IO-7842-SHARMA",
  "extra_data": {
    "action": "STAGE_TRANSITION",
    "details": {
      "previous_stage": "INITIALIZED",
      "new_stage": "EVIDENCE_INGESTION",
      "reason": "Lifecycle transition from 'INITIALIZED' to 'EVIDENCE_INGESTION' is valid."
    }
  }
}
```

---

## 8. Test Verification

Complete test suite across Phase 1:
```
======================= 92 passed, 2 warnings in 1.81s ========================
```
- **MOD-01 Case Management**: 16 passed
- **MOD-02 Identity / OIDC**: 33 passed
- **MOD-03 RBAC / ABAC**: 25 passed
- **MOD-04 Stage Engine**: 18 passed
- **Total**: 92 passed (0 failures)

---

## 9. Phase 1 Completion Status

With MOD-04 implemented, tested, and verified:
- **MOD-01**: Case Management Service (Complete)
- **MOD-02**: Identity / OIDC Authentication Boundary (Complete)
- **MOD-03**: RBAC / ABAC Authorization Engine (Complete)
- **MOD-04**: Stage Engine Lifecycle Governance (Complete)

**Phase 1 — Case Initiation is 100% COMPLETE.**

---

## 10. Next: Phase 2 — Evidence Ingestion

The platform is now ready for **Phase 2 — Evidence Ingestion**, consuming the Phase 1 Integration Contract:
- Multi-modal evidence object intake (documents, autopsy photos, scene recordings, digital files).
- Verification of Case ID stability and `ingestion_gate_open: True`.
- Cryptographic SHA-256 pre-hashing and chain-of-custody binding.
