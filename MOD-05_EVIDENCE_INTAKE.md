# SAKSHI: Phase 2 — Module 5: Evidence Intake (MOD-05)
## Technical Architecture & Implementation Blueprint

---

### 1. Module Overview & Purpose

The **Evidence Intake Service (MOD-05)** is the initial intake gateway of **Phase 2: Evidence Ingestion** in SAKSHI (**Evidence-Constrained Modus Operandi Reconstruction — EC-MORE**).

* **Source-defined Function:** `Register raw evidence`
* **Phase:** `02 — Evidence Ingestion`
* **Input:** Raw evidence file payload (PDFs, images, audio, CDR spreadsheets, digital dumps) + Intake metadata + Case ID + Authenticated Investigator Context
* **Output:** `RegisteredEvidenceObject` with canonical `Evidence ID` + Isolated Raw Staging Path
* **Downstream Consumer:** `MOD-06 — MIME / Signature Validation`

#### Architectural Principle
> *"MOD-05 does not validate magic bytes, scan for viruses, or commit WORM cryptographic seals. Its single responsibility is to provide a forensically disciplined intake gate: associating raw payloads with an active Case ID, generating collision-resistant Evidence IDs, recording provenance and submitting investigator accountability, and staging raw files in the isolated Case Workspace for downstream validation."*

---

### 2. Phase 2 Pipeline Flow & Boundary Separation

```
                       PHASE 1 OUTPUT
              Case ID + Case Workspace Boundary
              Auth Context + Stage: EVIDENCE_INGESTION
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                 PHASE 2 — EVIDENCE INGESTION                │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │             MOD-05: EVIDENCE INTAKE                 │   │
│   │  • Verify Case State & Ingestion Gate               │   │
│   │  • Enforce RBAC/ABAC Permissions                    │   │
│   │  • Mint Canonical Evidence ID (SAKSHI-EVID-...)     │   │
│   │  • Sanitize Filename & Store in Raw Workspace Zone  │   │
│   │  • Catalog Metadata & Record Submitting IO          │   │
│   │  • Status: REGISTERED_INTAKE                        │   │
│   └──────────────────────────┬──────────────────────────┘   │
│                              │                              │
│                              ▼ RegisteredEvidenceObject     │
│   ┌─────────────────────────────────────────────────────┐   │
│   │       MOD-06: MIME / SIGNATURE VALIDATION           │   │
│   │  (Inspect magic bytes, compare to declared type)    │   │
│   └──────────────────────────┬──────────────────────────┘   │
│                              │                              │
│                              ▼ Verified File Type           │
│   ┌─────────────────────────────────────────────────────┐   │
│   │             MOD-07: ANTIVIRUS SCAN                  │   │
│   │  (Scan stream/payload, quarantine malicious files)  │   │
│   └──────────────────────────┬──────────────────────────┘   │
│                              │                              │
│                              ▼ Clean Evidence Payload       │
│   ┌─────────────────────────────────────────────────────┐   │
│   │          MOD-08: WORM COMMIT + CHECKSUM             │   │
│   │  (Compute SHA-256 pre-hash, commit to WORM storage) │   │
│   └──────────────────────────┬──────────────────────────┘   │
│                              │                              │
└──────────────────────────────┼──────────────────────────────┘
                               │
                               ▼ Immutable Evidence Record
                     PHASE 3 — SECURITY & INTEGRITY
           (Dual Hashing, S3 Object Lock, Merkle Audit Ledger)
```

---

### 3. Strict Separation of Concerns (What MOD-05 Does vs Does NOT Do)

| Responsibility | MOD-05 (Intake) | MOD-06 (Validation) | MOD-07 (Antivirus) | MOD-08 (WORM/Hash) | Phase 3 (Security) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Associate Case ID & IO | **YES** | No | No | No | No |
| Generate Canonical Evidence ID | **YES** | No | No | No | No |
| Sanitize Filename & Path Traversal Check | **YES** | No | No | No | No |
| Stage to Workspace `raw/` Directory | **YES** | No | No | No | No |
| Record Intake Metadata & IO Audit | **YES** | No | No | No | No |
| Magic Byte / File Signature Sniffing | No | **YES** | No | No | No |
| Malicious Content / AV Scanning | No | No | **YES** | No | No |
| Pre-Hash & WORM Staging | No | No | No | **YES** | No |
| Dual Hashing (SHA-256 + SHA3-512) | No | No | No | Hand-off | **YES** |
| WORM Object Lock & Merkle Tree Ledger | No | No | No | Hand-off | **YES** |

---

### 4. Integration with Phase 1 Backend Components

MOD-05 directly connects with the verified Phase 1 infrastructure:

1. **MOD-01 Case Service (`Phase2IntegrationContract`)**:
   - Consumes `CaseRepository.get_by_case_id(case_id)`
   - Verifies case exists and workspace directory is provisioned.
   - Prepares target staging directory: `{case_workspace_path}/evidence/raw/{evidence_id}/`.

2. **MOD-02 Identity / OIDC (`AuthenticatedInvestigator`)**:
   - Ingestion endpoints require valid Bearer token authentication.
   - Extracts verified `investigator_id`, `role`, and assigned `police_station`.

3. **MOD-03 RBAC / ABAC Authorization**:
   - Introduces new permissions to `Permission` enum:
     - `EVIDENCE_CREATE = "evidence:create"`
     - `EVIDENCE_READ = "evidence:read"`
     - `EVIDENCE_LIST = "evidence:list"`
   - Checks investigator authorization:
     - `check_can_intake_evidence(investigator, case)`: Requires `evidence:create` permission AND case station/IO alignment.

4. **MOD-04 Stage Engine (`lifecycle_stage`)**:
   - Verifies case is in an evidence-receptive stage (`EVIDENCE_INGESTION`, or permitted feedback loop from `EVIDENCE_PROCESSING`/`ANALYSIS`).
   - Rejects intake if case is `INITIALIZED` (must advance to `EVIDENCE_INGESTION` first), `SUSPENDED`, or `CLOSED`.

---

### 5. Evidence Data Model & Schema

#### 5.1 Database Entity: `Evidence` (`evidence` table)

```python
class Evidence(Base):
    __tablename__ = "evidence"

    # Internal DB Primary Key
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)

    # Canonical Unique Evidence ID (e.g., SAKSHI-EVID-2026-7B2A109C)
    evidence_id = Column(String(64), unique=True, nullable=False, index=True)

    # Reference to parent Case
    case_id = Column(String(64), ForeignKey("cases.case_id"), nullable=False, index=True)

    # Original & Sanitized Filename
    original_file_name = Column(String(255), nullable=False)
    stored_file_name = Column(String(255), nullable=False)

    # Evidence Type / Forensic Category
    evidence_category = Column(String(64), nullable=False, index=True)
    # Categories: DOCUMENT_PDF, SCENE_PHOTO, AUTOPSY_PHOTO, AUDIO_RECORDING, CDR_SPREADSHEET, DIGITAL_DEVICE_EXTRACTION, OTHER

    # Declared MIME Type (Client-provided; verified later in MOD-06)
    declared_mime_type = Column(String(128), nullable=False)

    # File size in bytes
    file_size_bytes = Column(Integer, nullable=False)

    # Forensic intake metadata
    collection_datetime = Column(DateTime(timezone=True), nullable=True)
    collection_location = Column(String(255), nullable=True)
    source_device_or_person = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)

    # Submitting Investigator Reference
    submitting_investigator_id = Column(String(128), nullable=False, index=True)

    # Intake Stage Status
    # Stages: REGISTERED_INTAKE, PENDING_MIME_VALIDATION, QUARANTINED, COMMITTED
    status = Column(String(64), nullable=False, default="REGISTERED_INTAKE", index=True)

    # Physical Staging Location (Relative to workspace boundary)
    raw_storage_path = Column(String(512), nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)
```

#### 5.2 Forensic Categories Supported

1. `DOCUMENT_PDF`: Inquest reports, medical records, seizure memos, witness statements.
2. `SCENE_PHOTO`: Crime scene photographs, physical trace images.
3. `AUTOPSY_PHOTO`: Post-mortem visual examination images, injury close-ups.
4. `AUDIO_RECORDING`: Emergency 112 calls, dispatch radio, witness voice memos.
5. `CDR_SPREADSHEET`: Call Detail Records, cell tower dumps (CSV/XLSX).
6. `DIGITAL_DEVICE_EXTRACTION`: Mobile phone extractions, CCTV clips, hard drive dumps.
7. `OTHER`: Miscellaneous physical or digital artifacts.

---

### 6. API Specification

#### 6.1 `POST /api/v1/cases/{case_id}/evidence`
**Multipart/form-data upload** registering a new raw evidence item.

* **Headers:** `Authorization: Bearer <token>`
* **Form Fields:**
  - `file`: Binary file upload
  - `evidence_category`: String (`DOCUMENT_PDF`, `SCENE_PHOTO`, `AUDIO_RECORDING`, `CDR_SPREADSHEET`, etc.)
  - `declared_mime_type`: String (e.g. `application/pdf`, `image/jpeg`, `audio/wav`, `text/csv`)
  - `collection_datetime`: Optional ISO-8601 string
  - `collection_location`: Optional string (e.g. `"Room 204, Riverview Apartments"`)
  - `source_device_or_person`: Optional string (e.g. `"Victim's iPhone 13"`)
  - `description`: Optional text describing evidence item

**Response (201 Created):**
```json
{
  "evidence_id": "SAKSHI-EVID-2026-9C4B1E72",
  "case_id": "SAKSHI-CASE-2026-8F3E9A21",
  "original_file_name": "inquest_report.pdf",
  "evidence_category": "DOCUMENT_PDF",
  "declared_mime_type": "application/pdf",
  "file_size_bytes": 1048576,
  "status": "REGISTERED_INTAKE",
  "submitting_investigator_id": "IO-7842-SHARMA",
  "collection_datetime": "2026-10-02T08:30:00Z",
  "collection_location": "Civil Hospital Mortuary",
  "source_device_or_person": "Dr. V. Rao, Forensic Pathologist",
  "description": "Preliminary inquest examination notes",
  "created_at": "2026-10-02T10:50:00Z"
}
```

#### 6.2 `GET /api/v1/cases/{case_id}/evidence`
List all registered evidence items for the designated case.

**Response (200 OK):**
```json
{
  "case_id": "SAKSHI-CASE-2026-8F3E9A21",
  "total": 3,
  "items": [
    {
      "evidence_id": "SAKSHI-EVID-2026-9C4B1E72",
      "evidence_category": "DOCUMENT_PDF",
      "declared_mime_type": "application/pdf",
      "file_size_bytes": 1048576,
      "status": "REGISTERED_INTAKE",
      "created_at": "2026-10-02T10:50:00Z"
    }
  ]
}
```

#### 6.3 `GET /api/v1/cases/{case_id}/evidence/{evidence_id}`
Retrieve complete metadata record for an individual evidence item.

---

### 7. Downstream Contract to MOD-06 (`RegisteredEvidenceObject`)

The formal python dataclass / Pydantic contract handed to **MOD-06 (MIME / Signature Validation)**:

```python
class RegisteredEvidenceObject(BaseModel):
    """
    Contract produced by MOD-05 Evidence Intake for MOD-06 MIME Validation.
    """
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

### 8. Implementation Blueprint & Action Plan

#### Step 1: Core Domain Models & Schemas
* Add `backend/app/models/evidence.py` (SQLAlchemy ORM model).
* Add `backend/app/schemas/evidence.py` (Pydantic validation schemas & `RegisteredEvidenceObject`).

#### Step 2: Permissions & Policy Extensions (MOD-03)
* Update `backend/app/services/authorization_service.py` to add `Permission.EVIDENCE_CREATE`, `Permission.EVIDENCE_READ`, `Permission.EVIDENCE_LIST`.
* Add authorization checks `check_can_intake_evidence()` and `check_can_read_evidence()`.

#### Step 3: Evidence Repository & File Staging Service
* Add `backend/app/repositories/evidence_repository.py` (DB transactions).
* Add `backend/app/services/evidence_intake_service.py`:
  - Enforce Stage Engine state check (`EVIDENCE_INGESTION`).
  - Generate canonical `SAKSHI-EVID-{YYYY}-{HEX8}` ID.
  - Sanitize filenames (strip directory traversal `..`, illegal characters).
  - Persist file stream into `{case_workspace}/evidence/raw/{evidence_id}/{filename}`.
  - Record audit log `AUDIT_EVIDENCE_INTAKE`.

#### Step 4: API Endpoints & Router Mounting
* Add `backend/app/api/v1/evidence.py` (`POST /cases/{case_id}/evidence`, `GET /cases/{case_id}/evidence`, etc.).
* Mount router in `backend/app/main.py`.

#### Step 5: Test Suite
* Unit tests: `backend/tests/unit/test_evidence_intake_service.py` (Stage check, ID generation, path sanitization, metadata capture).
* Integration tests: `backend/tests/integration/test_evidence_api.py` (Upload multipart, list, get, authz rejections).

---

### 8. Implementation Verification & Test Results

The module implementation has been completed and verified across unit and integration suites:

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.4.2, pluggy-1.6.0
rootdir: C:\main project\backend
collected 107 items

tests\integration\test_cases_api.py ........                             [  7%]
tests\integration\test_evidence_api.py ......                            [ 13%]
tests\unit\test_auth_service.py .................................        [ 43%]
tests\unit\test_authorization_service.py .........................       [ 67%]
tests\unit\test_case_service.py ........                                 [ 74%]
tests\unit\test_evidence_intake_service.py .........                     [ 83%]
tests\unit\test_stage_engine.py ..................                       [100%]

======================= 107 passed, 1 warning in 2.13s ========================
```

- **MOD-01 Case Management**: 16 passed
- **MOD-02 Identity / OIDC**: 33 passed
- **MOD-03 RBAC / ABAC**: 25 passed
- **MOD-04 Stage Engine**: 18 passed
- **MOD-05 Evidence Intake**: 15 passed (9 unit + 6 integration)
- **Total**: 107 passed (0 failures)

---

### 9. Module Status & Downstream Hand-off

* **MOD-05: Evidence Intake is 100% COMPLETE.**
* **Next Module in Phase 2:** `MOD-06 — MIME / Signature Validation`
  - Consumes `RegisteredEvidenceObject` contract
  - Performs magic-byte inspection and true binary signature comparison against `declared_mime_type`.

