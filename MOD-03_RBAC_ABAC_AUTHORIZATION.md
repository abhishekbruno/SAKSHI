# MOD-03: RBAC / ABAC Authorization Specification

**SAKSHI — Explainable AI Investigation Companion for Unnatural Death Investigations using Evidence-Constrained Modus Operandi Reconstruction (EC-MORE)**  
**Phase 1 — Case Initiation | Module 3: Authorization (RBAC / ABAC)**

---

## 1. Purpose

Module 3 (MOD-03) provides the centralized, deterministic, and explainable **Authorization Engine** for the SAKSHI platform.

While MOD-02 answers the question:
> **"Who are you?"** (Authentication & Identity Attestation)

MOD-03 answers the question:
> **"What are you allowed to do with this case resource under these circumstances?"** (Authorization & Access Governance)

MOD-03 intercepts authenticated requests and evaluates them against declarative Role-Based Access Control (RBAC) and Attribute-Based Access Control (ABAC) policies before permitting any case management operation (MOD-01) or future lifecycle transition (MOD-04).

---

## 2. Authentication vs Authorization

| Dimension | MOD-02: Identity / OIDC | MOD-03: RBAC / ABAC Authorization |
| :--- | :--- | :--- |
| **Question Answered** | Who are you? | What are you permitted to do? |
| **Trust Source** | Cryptographically verified OpenID Connect token (RS256 JWT) or signed mock | Authenticated context from MOD-02 + authoritative DB entities from MOD-01 |
| **Failure Code** | `HTTP 401 Unauthorized` | `HTTP 403 Forbidden` |
| **Responsibility** | Validate signature, issuer, audience, expiry; extract subject & roles | Match roles to permissions (RBAC) and verify contextual attributes (ABAC) |
| **Boundary** | Pre-authorization perimeter gate | Resource & action policy evaluation engine |

---

## 3. Existing Authorization Architecture & Refactoring

Prior to MOD-03, authorization checks in MOD-01 were partially represented by a lightweight placeholder `PolicyEngineAuthorizationService` in `auth_service.py` with hardcoded role checks, while query filtering was inlined inside `CaseService.list_cases()`.

MOD-03 refactors this into a clean, decoupled architecture:
1. **Central Policy Engine (`app.services.authorization_service`)**: Implements `PolicyEngine`, `AuthorizationContext`, `AuthorizationDecision`, and `ROLE_PERMISSIONS`.
2. **Interface Preservation (`IAuthorizationService`)**: `PolicyEngineAuthorizationService` in `auth_service.py` preserves the contract required by `CaseService`, translating legacy calls into `AuthorizationContext` evaluations.
3. **Delegated Listing Filter**: `CaseService.list_cases()` delegates the visibility filter to `self.authz.get_case_list_filter(investigator)` rather than using hardcoded role sets.
4. **Audit Integration**: Decisions (both ALLOW and DENY) emit structured audit logs via `AuditIntegrationService.record_authorization_event`.

---

## 4. Architecture Diagram

```
                  HTTP REQUEST
                       │
                       ▼
              ┌────────────────┐
              │ MOD-02         │
              │ Identity/OIDC  │
              └───────┬────────┘
                      │
                      ▼
          AuthenticatedInvestigator
                      │
                      ▼
              ┌────────────────┐
              │ MOD-03         │
              │ Authorization  │
              └───────┬────────┘
                      │
          ┌───────────┼────────────┐
          ▼           ▼            ▼
       RBAC          ABAC       Context
          │           │            │
          └───────────┼────────────┘
                      ▼
                Policy Engine
                      │
               ┌──────┴──────┐
               │             │
             ALLOW          DENY
               │             │
               ▼             ▼
          MOD-01 Case      HTTP 403
          Management      Forbidden
```

---

## 5. RBAC Architecture

Role-Based Access Control determines whether the investigator's assigned role grants the permission required for the requested action.

### Evaluation Chain:
1. Map action (e.g. `create`, `read`, `update`, `assign`, `list`, `stage_update`) to a discrete `Permission`.
2. Retrieve permissions assigned to the investigator's roles from `ROLE_PERMISSIONS`.
3. If the required permission is not present in the role's granted set:
   - **Decision**: `DENY`
   - **Policy ID**: `RBAC_PERMISSION_DENIED`
4. If the permission is granted, control passes to ABAC evaluation.

---

## 6. Roles

> **Important**: These roles represent software application authorization roles configured for SAKSHI. They do not claim to represent statutory police organizational hierarchies.

| Role Name | Description |
| :--- | :--- |
| `INVESTIGATING_OFFICER` | Frontline investigator assigned to specific unnatural death cases. |
| `SUPERVISORY_OFFICER` | Senior supervisory officer overseeing investigations across jurisdictions. |
| `STATION_HEAD` | Officer in Charge (SHO) of a territorial police station. |
| `SUPERVISOR` | Backward-compatibility alias for supervisory officers. |
| `CASE_ADMIN` | Administrative officer managing case metadata and reassignments. |
| `SYSTEM_ADMIN` | System administrator with full diagnostic and management rights. |

---

## 7. Permissions

| Permission String | Description |
| :--- | :--- |
| `case:create` | Initiate a new investigation case record and workspace. |
| `case:read` | View full case metadata, workspace locator, and stage status. |
| `case:update` | Modify mutable case metadata (title, FIR details). |
| `case:list` | Query the case registry. |
| `case:assign` | Assign an investigator to a case (self-assign or reassign). |
| `case:stage:update`| Trigger lifecycle stage advancement (Stage Engine hook). |

### Role-Permission Matrix (`ROLE_PERMISSIONS`):

| Permission | `INVESTIGATING_OFFICER` | `SUPERVISORY_OFFICER` / `STATION_HEAD` | `CASE_ADMIN` | `SYSTEM_ADMIN` |
| :--- | :---: | :---: | :---: | :---: |
| `case:create` | ✅ | ✅ | ❌ | ✅ |
| `case:read` | ✅ | ✅ | ✅ | ✅ |
| `case:update` | ✅ | ✅ | ❌ | ✅ |
| `case:list` | ✅ | ✅ | ✅ | ✅ |
| `case:assign` | ✅ *(Self only)* | ✅ *(Any IO)* | ✅ *(Any IO)* | ✅ *(Any IO)* |
| `case:stage:update` | ✅ | ✅ | ❌ | ✅ |

---

## 8. ABAC Architecture

Attribute-Based Access Control evaluates contextual attributes when RBAC succeeds:

### Subject Attributes (from MOD-02):
- `subject_id`: Authoritative investigator identifier (e.g. `IO-7842-SHARMA`).
- `subject_role` / `subject_roles`: Verified application roles.
- `subject_jurisdiction`: Territorial jurisdiction code (e.g. `JUR-DEL-04`).
- `authentication_method`: Token provenance (`oidc` vs `development`).

### Resource Attributes (from MOD-01 Database):
- `resource_id`: Authoritative unique Case ID (e.g. `CASE-2026-DEL04-0001`).
- `resource_assigned_io`: The currently assigned investigating officer ID.
- `resource_jurisdiction`: Extracted from FIR metadata (`jurisdiction_code` or `police_station`).
- `resource_status`: Operational status (`ACTIVE`, `SUSPENDED`, `CLOSED`).
- `resource_stage`: Current lifecycle stage (`INITIALIZED`, etc.).

### Action & Context:
- `action`: Action requested by route handler (`create`, `read`, `update`, `assign`, `list`, `stage_update`).
- `target_io_id`: Target officer ID for assignment operations.

---

## 9. Case Access Policies

When accessing a specific case (`read`, `update`, `stage_update`), the policy engine evaluates:

1. **`CASE_ACCESS_SUPERVISORY`**: If the investigator holds a role in `SUPERVISORY_ROLES` (`SUPERVISORY_OFFICER`, `STATION_HEAD`, `ADMIN`, `SUPERVISOR`, `SYSTEM_ADMIN`), access is granted unconditionally.
2. **`CASE_ACCESS_ASSIGNED_IO`**: If the investigator's `subject_id` matches `case.assigned_io_id`, access is granted.
3. **`CASE_ACCESS_JURISDICTION`**: If the investigator's `station_jurisdiction` matches the case's `jurisdiction_code` or `police_station`, access is granted.
4. **`CASE_ACCESS_DENIED`**: If none of the above match, access is denied.

---

## 10. Case Assignment Policies

When assigning or reassigning a case (`assign`):

1. **`CASE_ASSIGN_SELF`**: If `target_io_id == subject_id`, self-assignment is permitted during case creation or updates.
2. **`CASE_ASSIGN_SUPERVISORY`**: If `target_io_id != subject_id`, the requester must hold a supervisory role in `SUPERVISORY_ROLES`.
3. **`CASE_ASSIGN_DENIED`**: If a non-supervisory investigator attempts to assign a case to another investigator, access is denied.

---

## 11. Supervisory Policy & Case Listing

For `GET /api/v1/cases` (listing):
- **Supervisory officers**: The query filter is `None`, allowing them to view and oversee all active investigations across stations.
- **Regular Investigating Officers**: The query filter is locked to `investigator.subject_id`, ensuring non-supervisors only view cases assigned to them.
- Filtering is determined directly by `PolicyEngine.get_case_list_filter(investigator)`.

---

## 12. Default-Deny Behavior

The system enforces strict **Default-Deny**:
- Any unknown role -> `RBAC_PERMISSION_DENIED` (Deny).
- Any unknown action -> `RBAC_UNKNOWN_ACTION` (Deny).
- Any unhandled context or unmatched attribute -> `CASE_ACCESS_DENIED` or `ABAC_DEFAULT_DENY` (Deny).
- Access is never granted by default; every allowable condition requires an explicit policy match.

---

## 13. Authentication Integration (MOD-02 Boundary)

MOD-03 never validates JWTs or parses raw Authorization headers.
- MOD-02's `get_current_investigator` dependency validates credentials and returns an immutable `AuthenticatedInvestigator`.
- MOD-03 dependencies (such as `require_permission`) and services receive `AuthenticatedInvestigator` and consume its verified claims (`subject_id`, `role`, `roles`, `station_jurisdiction`).

---

## 14. MOD-01 Integration

`CaseService` coordinates all case actions through the `IAuthorizationService` facade:
- `create_case`: `authz.check_can_create_case(investigator, station)` and `authz.check_can_assign_io(investigator, target_io)`
- `get_case`: `authz.check_can_read_case(investigator, case)`
- `update_case`: `authz.check_can_modify_case(investigator, case)`
- `list_cases`: `authz.get_case_list_filter(investigator)`
- `assign_investigator`: `authz.check_can_assign_io(investigator, target_io_id, case)`
- `update_stage`: `authz.check_can_modify_case(investigator, case)`
- `get_phase2_contract`: `authz.check_can_read_case(investigator, case)`

---

## 15. Security Protections

1. **Insecure Direct Object Reference (IDOR)**:
   Investigator `IO-1` requesting `/api/v1/cases/CASE-2` cannot access data belonging to `IO-2` unless authorized by jurisdiction or supervisor status.
2. **Actor vs Assignee Spoofing**:
   Clients cannot specify an arbitrary `investigator_id` in the request body to execute actions as another officer. The actor is always extracted from the validated token.
3. **Role Escalation Prevention**:
   Headers such as `X-Investigator-Role` or body attributes claiming elevated roles are discarded in production OIDC mode and overridden by verified JWT claims.
4. **Jurisdiction Spoofing Prevention**:
   Client-supplied station/jurisdiction strings in payload bodies do not alter the authenticated officer's trusted jurisdiction.
5. **No Token Leakage**:
   Neither logs nor client error responses ever leak signing keys, tokens, or internal policy evaluation structures.

---

## 16. Audit Events

Every authorization decision is recorded via `AuditIntegrationService.record_authorization_event()`:

### ALLOW Event:
```json
{
  "event_type": "AUDIT_AUTHZ_ALLOW",
  "message": "Authorization ALLOW: action='read' resource='case:CASE-01' subject='IO-7842' policy='CASE_ACCESS_ASSIGNED_IO'",
  "metadata": {
    "decision": "ALLOW",
    "subject_id": "IO-7842",
    "action": "read",
    "resource_type": "case",
    "resource_id": "CASE-01",
    "policy_id": "CASE_ACCESS_ASSIGNED_IO",
    "reason": "Investigator is the assigned IO for this case.",
    "timestamp": "2026-10-01T23:55:00.000000+00:00"
  }
}
```

### DENY Event:
```json
{
  "event_type": "AUDIT_AUTHZ_DENY",
  "message": "Authorization DENY: action='update' resource='case:CASE-01' subject='IO-9912' policy='CASE_ACCESS_DENIED'",
  "metadata": {
    "decision": "DENY",
    "subject_id": "IO-9912",
    "action": "update",
    "resource_type": "case",
    "resource_id": "CASE-01",
    "policy_id": "CASE_ACCESS_DENIED",
    "reason": "Investigator is not assigned to this case, does not hold a supervisory role, and jurisdiction does not match.",
    "timestamp": "2026-10-01T23:55:01.000000+00:00"
  }
}
```

---

## 17. API Behavior

- **Unauthenticated**: Returns `401 Unauthorized` (`AUTHENTICATION_REQUIRED`).
- **Authenticated but Unauthorized**: Returns `403 Forbidden` (`FORBIDDEN`) with safe message:
  ```json
  {
    "error_code": "FORBIDDEN",
    "message": "Access denied: you are not authorized to perform this operation.",
    "details": null
  }
  ```
- **Authenticated and Authorized**: Request completes normally with `200 OK` or `201 Created`.

---

## 18. Test Results

Comprehensive pytest suite covers all regression and authorization scenarios:

```
collected 74 items

backend/tests/integration/test_cases_api.py ........                     [ 10%]
backend/tests/unit/test_auth_service.py ................................ [ 54%]
.                                                                        [ 55%]
backend/tests/unit/test_authorization_service.py ......................... [ 89%]
backend/tests/unit/test_case_service.py ........                         [100%]

======================= 74 passed, 2 warnings in 1.80s ========================
```

- **MOD-01 Tests**: 16 passed
- **MOD-02 Tests**: 33 passed
- **MOD-03 Tests**: 25 passed
- **Total**: 74 passed (0 failures)

---

## 19. Known Limitations

1. **Dynamic Policy Reloading**: `ROLE_PERMISSIONS` is currently loaded in-memory at application startup. Future phases will support database-backed policy storage and dynamic reloading without service restart.
2. **Sub-case Resource Granularity**: Granular access to individual evidence files, forensic notes, or victim statements will be introduced during Phase 2 (Evidence Ingestion).

---

## 20. Future Policy Configuration

In Phase 2, the Policy Engine will expand to support:
- `evidence:ingest`
- `evidence:read`
- `evidence:hash:verify`
- Chain-of-custody transfer authorization
- Multi-station task forces (temporary cross-jurisdiction delegation)
