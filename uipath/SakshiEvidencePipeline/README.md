# SAKSHI RPA — UiPath Studio Evidence Pipeline Integration

## 1. Overview
SAKSHI is an evidence-constrained investigation companion designed for digital forensics and criminal investigations. The Robotic Process Automation (RPA) subsystem integrates UiPath Studio with the SAKSHI FastAPI backend to automate evidence intake and verification across four authoritative stages:

1. **MOD-05 (Evidence Intake):** Registers raw evidence binary, validates case lifecycle stage (`EVIDENCE_INGESTION`), isolates file payload into the case workspace boundary, and computes SHA-256 digest.
2. **MOD-06 (MIME & Signature Validation):** Validates magic bytes/file header signatures against declared forensic MIME type.
3. **MOD-07 (Antivirus Scanning):** Passive heuristic scanning for malware/threats (fail-closed, quarantined on detection).
4. **MOD-08 (WORM Commitment):** Stores the evidence into immutable Write-Once-Read-Many (WORM) storage and generates immutable verification references.

The composite endpoint `/api/v1/cases/{case_id}/evidence/pipeline` orchestrates these four stages deterministically and returns a single structured outcome (`PipelineExecutionResult`).

---

## 2. UiPath Project Structure
The UiPath project is located under `uipath/SakshiEvidencePipeline/`:

```
uipath/SakshiEvidencePipeline/
├── project.json                   # UiPath Windows-target project descriptor
├── Config.json                     # Safe configuration template (no identity or secret)
├── Main.xaml                      # Master orchestrator workflow with retry loop
├── SubmitEvidencePipeline.xaml    # HTTP Request activity caller (multipart & resume)
├── ProcessPipelineResponse.xaml   # Deserializer, status brancher, and error classifier
└── tests/                          # Static input, authentication, and request-contract checks
```

### Dependencies
- `UiPath.System.Activities` [>= 23.10.2]
- `UiPath.WebAPI.Activities` [>= 1.18.0] (provides `HttpClient` activity)

---

## 3. Backend API Contract

### Endpoint
`POST /api/v1/cases/{case_id}/evidence/pipeline`

### Authentication
| Header | Description | Example |
| :--- | :--- | :--- |
| `X-Investigator-Id` | Development-only submitting identity | Configured in an untracked local file |
| `X-Investigator-Role` | Development-only SAKSHI role | Configured in an untracked local file |
| `X-Investigator-Jurisdiction` | Development-only jurisdiction | Configured in an untracked local file |
| `Authorization` | Required by OIDC and Firebase deployments | Managed Bearer token, never stored in this project |

The workflow sends `X-Investigator-*` headers only when `AuthenticationMode` is explicitly `development`. It intentionally stops before making any HTTP call for `oidc`, `firebase`, or an unconfigured mode: this legacy project has no managed robot-token acquisition boundary. Do not pass a bearer token through a workflow argument or store one in `Config.json`.

### Request Modes

#### A. Initial Ingestion (Multipart Form-Data)
Used when ingesting an evidence file for the first time:
- `file`: Raw binary file payload (e.g., PDF, image, spreadsheet).
- `evidence_category`: Forensic category enum (`DOCUMENT_PDF`, `SCENE_PHOTO`, `CALL_DATA_RECORD`, etc.).
- `declared_mime_type`: Client-declared MIME type (e.g., `application/pdf`).
- `description` (optional): Brief description of exhibit.
- `collection_location` (optional): Scene or hospital location.
- `source_device_or_person` (optional): Custodial source.

#### B. Safe Resume (Form-Data)
Used if a transient error (e.g. scanner timeout, 503) occurred after intake, or when resuming a staged exhibit:
- `evidence_id`: The previously returned evidence identifier (e.g. `SAKSHI-EVID-2026-XXXX`).
- **Guaranteed Safety:** A resume request **rejects** any attached file or intake metadata (HTTP 422 `InvalidEvidenceDataException`). This prevents duplicate intake records and ensures completed stages are never unsafely repeated.

---

## 4. Response Schema & Status Codes

### `PipelineExecutionResult`
```json
{
  "case_id": "SAKSHI-CASE-2026-D9B7A076",
  "evidence_id": "SAKSHI-EVID-2026-4EE87419",
  "overall_status": "SUCCESS",
  "current_stage": "WORM_COMMIT",
  "completed_stages": [
    "INTAKE",
    "MIME_VALIDATION",
    "ANTIVIRUS_SCAN",
    "WORM_COMMIT"
  ],
  "intake_status": "COMMITTED",
  "message": "Evidence completed the MOD-05 through MOD-08 pipeline.",
  "worm_storage_reference": "worm://SAKSHI-CASE-2026-D9B7A076/ab12...",
  "checksum_sha256": "ab12...",
  "already_committed": false,
  "is_retryable": false,
  "started_at": "2026-10-22T18:41:59.000000Z",
  "completed_at": "2026-10-22T18:42:01.000000Z"
}
```

### Status Code Mapping
| Status Code | `overall_status` | UiPath Handling Strategy |
| :--- | :--- | :--- |
| `201 Created` | `SUCCESS` | Normal completion. Log WORM reference & checksum. Do not retry. |
| `200 OK` | `SUCCESS` | Resumed completion (`already_committed: true`). Do not retry. |
| `422 Unprocessable` | `MIME_VALIDATION_FAILED` | Magic bytes mismatch. Log forensic rejection alert. Do not retry. |
| `422 Unprocessable` | `ANTIVIRUS_QUARANTINED` | Malware detected. Log quarantine security alert. Do not retry. |
| `503 Unavailable` | `RETRYABLE_ERROR` | Scanner unavailable/timeout. Retry with backoff using `evidence_id`. |
| `401 Unauthorized` | N/A | Missing/invalid credentials. Terminate robot with fatal alert. |
| `403 Forbidden` | N/A | Unauthorized case access. Terminate robot with security incident. |
| `500 Server Error` | `WORM_COMMIT_FAILED` / `INTAKE_FAILED` | Permanent storage failure. Log forensic error. Do not retry intake. |

---

## 5. UiPath Studio Operator Instructions

### Prerequisites
1. **UiPath Studio 2023.10+** (Windows .NET 6/8 target framework).
2. **Package Feeds:** Ensure the Official UiPath feed (`https://pkgs.dev.azure.com/uipath/Public.Feeds/_packaging/UiPath-Official/nuget/v3/index.json`) is enabled.

### Configuration
1. Open UiPath Studio.
2. Select **Open a Local Project** and navigate to `uipath/SakshiEvidencePipeline/project.json`.
3. Treat checked-in `Config.json` as a fail-closed template. For a development-only run, copy it to `Config.local.json` and pass that absolute path as `in_ConfigPath`. The local file is ignored by Git.
4. In the local file, set `AuthenticationMode` to `development` and provide the development investigator ID, role, and jurisdiction that will also create and own the test case. Keep `ApiBaseUrl`, timeouts, and retry limits environment-specific.

The project does not yet support OIDC or Firebase robot authentication. That requires a design decision for managed token acquisition and rotation outside the XAML and configuration files.

### Running in Studio
1. Obtain an authorized, server-issued `case_id` using the procedure below. Do not type a guessed or static Case ID.
2. In the **Properties** panel for `Main.xaml`, provide the arguments:
   - `in_CaseId`: Exactly the `case_id` returned by SAKSHI.
   - `in_EvidenceFilePath`: Absolute path to an existing evidence file on the robot host.
   - `in_EvidenceCategory`: `DOCUMENT_PDF`.
   - `in_DeclaredMimeType`: `application/pdf`.
   - `in_ConfigPath`: Absolute path to the untracked development configuration file.
3. Click **Run File** or **Debug File**.
4. Inspect the Output panel for audit logs:
   - Verify `PIPELINE_EXECUTION_STARTED`
   - Verify stage milestones: `INTAKE` -> `MIME_VALIDATION` -> `ANTIVIRUS_SCAN` -> `WORM_COMMIT`
   - Verify `out_WormStorageReference` and `out_Sha256Checksum` are populated upon completion.

### Safe development procedure

Use the same explicit development identity for all three API calls and in `Config.local.json`. This obtains a genuine Case ID from existing SAKSHI case management; it does not create an alternate case system.

```powershell
$apiBase = 'http://localhost:8000/api/v1'
$investigatorId = Read-Host 'Development investigator ID'
$investigatorRole = Read-Host 'Development role'
$investigatorJurisdiction = Read-Host 'Development jurisdiction'
$headers = @{
  'X-Investigator-Id' = $investigatorId
  'X-Investigator-Role' = $investigatorRole
  'X-Investigator-Jurisdiction' = $investigatorJurisdiction
}
$firNumber = "DEV-UIPATH-$([guid]::NewGuid().ToString('N').Substring(0, 12))"
$payload = @{
  title = 'Development UiPath evidence pipeline verification'
  fir_metadata = @{
    fir_number = $firNumber
    police_station = 'Development test station'
    jurisdiction_code = $investigatorJurisdiction
  }
} | ConvertTo-Json -Depth 4
$case = Invoke-RestMethod -Method Post -Uri "$apiBase/cases" -Headers $headers -ContentType 'application/json' -Body $payload
$case.case_id

Invoke-RestMethod -Method Post -Uri "$apiBase/cases/$($case.case_id)/stage" -Headers $headers -ContentType 'application/json' -Body '{"lifecycle_stage":"EVIDENCE_INGESTION"}'

$evidencePath = (Resolve-Path -LiteralPath (Read-Host 'Absolute path to a clean test PDF on this robot')).Path
if (-not (Test-Path -LiteralPath $evidencePath -PathType Leaf)) { throw 'Evidence file is not accessible to this robot.' }
```

Then set `in_CaseId` to `$case.case_id` and `in_EvidenceFilePath` to `$evidencePath` in Studio. For a `503` response, UiPath retains the returned `evidence_id` and sends an `evidence_id`-only resume request; it must not submit the original multipart file again.

---

## 6. Security & Audit Logging Guarantees
- **No Payload Leaks:** Raw binary payloads and forensic exhibits are never logged to UiPath Orchestrator logs or standard stdout logs.
- **Credential Protection:** Tokens and passwords match `*password*`, `*token*`, and `*secret*` masks in `project.json` runtime options.
- **Authentication Boundary:** No access token, password, or investigator identity is stored in the committed UiPath configuration or hardcoded in XAML. Development headers are explicitly opt-in and blocked for every other configured mode.
- **Fail-Closed Security:** Operational scanner timeouts result in `RETRYABLE_ERROR` (503) rather than passing unverified evidence to WORM storage.
- **Backward Compatibility:** All existing individual evidence endpoints (`/cases/{case_id}/evidence`, `/validate`, `/scan`, `/worm-commit`, `/integrity`, `/object-lock`, `/encrypt`) remain fully functional.
