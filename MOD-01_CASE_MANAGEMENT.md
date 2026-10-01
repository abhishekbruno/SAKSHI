# SAKSHI: Phase 1 — Module 1: Case Management Service (MOD-01)
## Technical Implementation & Architectural Reference

---

### 1. Module Purpose
The **Case Management Service (MOD-01)** is the foundational administrative and governance component of SAKSHI (**Evidence-Constrained Modus Operandi Reconstruction — EC-MORE**).

*   **Source-defined Function:** `Create case / assign IO`
*   **Phase:** `01 — Case Initiation`
*   **Input:** `FIR metadata + IO credentials`
*   **Output:** `Case workspace + Case ID`
*   **Downstream Consumer:** `02 — Evidence Ingestion`

**Architectural Principle:**
> *"MOD-01 does not investigate the case. It establishes the controlled case context, anchors the unique Case ID, binds human accountability via the Investigating Officer (IO), and provisions the isolated Case Workspace required for downstream multi-modal evidence ingestion."*

---

### 2. Architecture & Separation of Concerns

```
                     [ Client / Investigator ]
                                 │
                                 ▼
                     [ Authentication Boundary ]
                   (Identity / OIDC Subject Token)
                                 │
                                 ▼
                     [ Authorization Boundary ]
                       (RBAC / ABAC Policies)
                                 │
                                 ▼
               ┌───────────────────────────────────┐
               │  CASE MANAGEMENT SERVICE (MOD-01) │
               │   • Create Case                   │
               │   • Assign IO                     │
               │   • Mint Canonical Case ID        │
               │   • Provision Case Workspace      │
               └─────────────────┬─────────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
       [ Case Repository ]              [ Stage Engine Hook ]
                 │                      (Lifecycle: INITIALIZED)
                 ▼                               │
        [ Database Storage ]                     ▼
   (cases table: PostgreSQL/SQLite)    [ Phase 1 Output Contract ]
                                                 │
                                                 ▼
                                   Phase 02 — Evidence Ingestion
```

---

### 3. Folder Structure

```
c:\main project\
├── backend\
│   ├── app\
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI application factory & lifespan
│   │   ├── config.py                   # Pydantic BaseSettings environment config
│   │   ├── api\
│   │   │   ├── deps.py                 # Dependency injection (Auth & Session)
│   │   │   └── v1\
│   │   │       └── cases.py            # REST endpoints (/api/v1/cases)
│   │   ├── core\
│   │   │   ├── errors.py               # Standardized error hierarchy
│   │   │   ├── logging.py              # Structured JSON audit logging
│   │   │   └── security.py             # AuthenticatedInvestigator abstraction
│   │   ├── db\
│   │   │   ├── base.py                 # SQLAlchemy declarative base
│   │   │   └── session.py              # Database session & engine management
│   │   ├── models\
│   │   │   └── case.py                 # SQLAlchemy Case entity
│   │   ├── schemas\
│   │   │   └── case.py                 # Pydantic validation schemas
│   │   ├── repositories\
│   │   │   └── case_repository.py      # Transactional data access
│   │   └── services\
│   │       ├── auth_service.py         # OIDC Auth & RBAC/ABAC policy engine
│   │       ├── audit_integration.py    # Governance audit stub
│   │       └── case_service.py         # Domain business logic (Create/Assign)
│   ├── tests\
│   │   ├── conftest.py                 # Pytest fixtures & in-memory test DB
│   │   ├── unit\
│   │   │   └── test_case_service.py    # Domain invariants & logic unit tests
│   │   └── integration\
│   │       └── test_cases_api.py       # REST API contracts & security tests
│   └── requirements.txt
├── frontend\                           # Minimal Case Management UI
│   ├── index.html                      # Forensic interface
│   ├── style.css                       # SAKSHI dark navy / cyan aesthetic
│   └── app.js                          # Client-side API integration
└── MOD-01_CASE_MANAGEMENT.md           # This document
```

---

### 4. Database Model: Source-Defined vs. Proposed Decisions

The `Case` entity cleanly separates source-mandated fields from proposed implementation decisions:

| Field Name | Type | Classification | Purpose & Rationale |
| :--- | :--- | :--- | :--- |
| `case_id` | `VARCHAR(64)` (UQ, Index) | **Source-Defined** | Authoritative global Case ID anchoring all downstream stages. |
| `fir_metadata` | `JSON` | **Source-Defined** | Stores initial FIR attributes (FIR No., Station, Date, Jurisdiction). |
| `assigned_io_id` | `VARCHAR(128)` (Index) | **Source-Defined** | Bound reference to the assigned Investigating Officer. |
| `lifecycle_stage` | `VARCHAR(64)` | **Source-Defined** | Lifecycle state governed by Stage Engine (default: `INITIALIZED`). |
| `id` | `VARCHAR(36)` (PK) | *Proposed Implementation* | Internal UUIDv4 primary key (isolates internal relational integrity). |
| `title` | `VARCHAR(255)` | *Proposed Implementation* | Concise descriptive reference of the death investigation. |
| `status` | `VARCHAR(32)` | *Proposed Implementation* | Operational workflow status (`ACTIVE`, `SUSPENDED`, `CLOSED`). |
| `case_workspace_path` | `VARCHAR(512)` | *Proposed Implementation* | Logical workspace storage boundary URI (`/sakshi/workspaces/...`). |
| `created_by` | `VARCHAR(128)` | *Proposed Implementation* | Audit identity of initiating user. |
| `created_at` | `TIMESTAMP` | *Proposed Implementation* | UTC creation timestamp. |
| `updated_at` | `TIMESTAMP` | *Proposed Implementation* | UTC timestamp of last modification. |

*Zero-Password Rule:* Under no circumstance are passwords or authentication credentials stored in the `Case` entity.

---

### 5. API Endpoints (Version 1: `/api/v1/cases`)

| HTTP Method | Path | Summary | Auth Required | Downstream / Consumer |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/api/v1/cases` | Create a new case & initialize workspace | Yes | Phase 1 Workspace Initializer |
| **GET** | `/api/v1/cases/{case_id}` | Retrieve case by Case ID | Yes | Case View & Downstream Check |
| **GET** | `/api/v1/cases` | List authorized cases for IO | Yes | Investigator Dashboard |
| **PATCH** | `/api/v1/cases/{case_id}` | Update permitted metadata | Yes | Case Administration |
| **POST** | `/api/v1/cases/{case_id}/assign-investigator` | Associate/reassign IO | Yes (Supervisory) | Administrative Governance |
| **GET** | `/api/v1/cases/{case_id}/stage` | Query lifecycle state | Yes | Stage Engine / Evidence Gate |
| **POST** | `/api/v1/cases/{case_id}/stage` | Advance lifecycle state | Yes | Stage Engine Hook |
| **GET** | `/api/v1/cases/{case_id}/phase2-contract` | Export Phase 2 handoff contract | Yes | Phase 2 Evidence Ingestion |

---

### 6. Authentication Boundary

*   **Role Separation:** The Authentication Layer answers *"Who is the investigator?"* Case Management answers *"Which investigation is being initiated and who is assigned?"*
*   **Abstraction Interface:** `IAuthenticationService` extracts an `AuthenticatedInvestigator` object containing `investigator_id`, `role`, `station_jurisdiction`, and verified scopes.
*   **Production vs. Development:**
    *   *Production:* Validates OIDC JWTs against the identity provider's JWKS endpoint.
    *   *Local Development:* `DevOIDCAuthenticationService` accepts simulated Bearer tokens or `X-Investigator-*` development headers without bypassing internal validation.

---

### 7. Authorization Boundary (RBAC / ABAC)

*   **Policy Engine:** `PolicyEngineAuthorizationService` enforces access boundaries:
    *   Case initiation requires an authorized role (`INVESTIGATING_OFFICER`, `SUPERVISORY_OFFICER`, etc.).
    *   Case reading is restricted to the assigned IO or supervisory officers (`SUPERVISORY_OFFICER`, `STATION_HEAD`). Cross-case snooping by unassigned officers is strictly blocked (`403 FORBIDDEN`).
    *   Reassigning a case to another officer requires supervisory clearance.
    *   Client-supplied `investigator_id` is never blindly trusted.

---

### 8. Case ID Design

*   **Immutability:** Once generated, the Case ID never changes during updates or lifecycle state transitions.
*   **Strategy:** Derived from cryptographically secure random entropy (`secrets.token_hex(4)`):
    *   Format: `SAKSHI-CASE-{YYYY}-{HEX8}` (e.g., `SAKSHI-CASE-2026-8F3E9A21`).
*   **Privacy Invariant:** Does not encode victim names, suspect references, or sensitive investigative facts into the identifier.
*   **Downstream Reference:** Acts as the stable foreign key across subsequent phases (evidence objects, extracted events, timeline intervals, and contradiction matrices).

---

### 9. Phase 2 Integration Contract

Phase 1 concludes by exporting this formal contract to **Phase 2 (Evidence Ingestion)**:

```json
{
  "case_id": "SAKSHI-CASE-2026-8F3E9A21",
  "case_workspace_boundary": {
    "workspace_path": "/sakshi/workspaces/SAKSHI-CASE-2026-8F3E9A21",
    "status": "ACTIVE",
    "ingestion_gate_open": true
  },
  "authorized_io_id": "IO-7842-SHARMA",
  "lifecycle_stage": "INITIALIZED",
  "provenance": {
    "fir_number": "FIR-2026-0814",
    "police_station": "Central Forensic Division",
    "created_at": "2026-09-30T14:25:00.000000+00:00"
  }
}
```

Phase 2 will verify that `ingestion_gate_open == True` and that incoming physical or documentary evidence matches this `case_id` before computing SHA-256 hashes or storing evidence objects in Phase 3.

---

### 10. Local Development & Testing Instructions

#### Run Test Suite
```powershell
cd "c:\main project\backend"
& "c:\main project\backend\.venv\Scripts\pytest.exe" -v
```

#### Run Backend Server Locally
```powershell
cd "c:\main project\backend"
& "c:\main project\backend\.venv\Scripts\uvicorn.exe" app.main:app --reload --port 8000
```
Interactive Swagger Documentation available at: `http://127.0.0.1:8000/docs`

#### Open Frontend Interface
Open `c:\main project\frontend\index.html` in any modern web browser or serve via HTTP.
