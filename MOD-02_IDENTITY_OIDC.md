# MOD-02: Identity / OIDC — Authenticate Investigator

> **SAKSHI Investigation Platform**
> Phase 1 — Case Initiation
> Module 2 of 4

---

## 1. Module Purpose

MOD-02 establishes **authentication** — answering the question:

> **"Who is this investigator?"**

It does **NOT** answer:

> "What is this investigator allowed to access?"

That responsibility belongs to **MOD-03 RBAC / ABAC**.

---

## 2. Authentication vs Authorization

| Concern | Module | Question |
|---------|--------|----------|
| **Authentication** | MOD-02 (this) | Who are you? |
| **Authorization** | MOD-03 (next) | What can you do? |

These are separate security boundaries:

```
CLIENT → [MOD-02 Authentication] → [MOD-03 Authorization] → [MOD-01 Case Management]
```

---

## 3. Existing Authentication Architecture (Pre-MOD-02)

Before MOD-02, the codebase had:

- `AuthenticatedInvestigator` model in `core/security.py` — identity representation
- `DevOIDCAuthenticationService` — development-only mock that trusted raw headers
- `IAuthenticationService` / `IAuthorizationService` abstractions in `auth_service.py`
- `get_current_investigator()` dependency in `deps.py`

**Critical gaps addressed by MOD-02:**
- No real JWT validation (decode ≠ verify)
- Client-supplied `X-Investigator-Id` trusted unconditionally
- Dev auth always active regardless of environment
- No OIDC discovery or JWKS support
- No `/auth/me` endpoint

---

## 4. OIDC Architecture

```
             Investigator
                  │
                  ▼
          ┌───────────────┐
          │ OIDC Provider │
          │  (Keycloak,   │
          │   Auth0, etc) │
          └───────┬───────┘
                  │
             ID/Access Token
                  │
                  ▼
        ┌────────────────────┐
        │ SAKSHI Auth Layer  │
        │                    │
        │ Token Validation   │
        │ Issuer Validation  │
        │ Audience Validation│
        │ Signature Verify   │
        │ Expiry Check       │
        │ Identity Extraction│
        └─────────┬──────────┘
                  │
                  ▼
        ┌────────────────────┐
        │ Authenticated      │
        │ Investigator       │
        │ Context            │
        └─────────┬──────────┘
                  │
                  ▼
        ┌────────────────────┐
        │ MOD-03             │
        │ RBAC / ABAC        │
        └─────────┬──────────┘
                  │
                  ▼
        ┌────────────────────┐
        │ MOD-01             │
        │ Case Management    │
        └────────────────────┘
```

---

## 5. Token Validation Pipeline

The production `OIDCAuthenticationService` performs **verification**, not just decoding:

| Step | Validation | Action |
|------|-----------|--------|
| 1 | Token exists | Check `Authorization: Bearer <token>` header |
| 2 | Format valid | Must be `Bearer` scheme |
| 3 | **Signature valid** | Verified against JWKS public keys |
| 4 | **Issuer trusted** | Must match configured `OIDC_ISSUER_URL` |
| 5 | **Audience correct** | Must match configured `OIDC_AUDIENCE` |
| 6 | **Not expired** | `exp` claim must be in the future |
| 7 | Claims exist | `sub` (subject) claim is required |
| 8 | Algorithm permitted | Must be in `OIDC_ALGORITHMS` list |
| 9 | Identity extracted | Build `AuthenticatedInvestigator` from claims |

> ⚠️ **JWT decoding ≠ JWT verification.** MOD-02 uses `python-jose` with RSA signature verification.

---

## 6. Investigator Identity Model

```python
class AuthenticatedInvestigator:
    # MOD-02 Canonical Fields
    subject_id: str           # OIDC 'sub' claim — authoritative identity
    username: str             # OIDC 'preferred_username'
    display_name: str         # Human-readable name
    email: str                # Contact email
    roles: List[str]          # Role claims for MOD-03
    claims: Dict[str, Any]    # Sanitized identity claims
    issuer: str               # Token issuer URL
    authentication_method: str  # 'oidc' or 'development'

    # Backward Compatibility (MOD-01)
    investigator_id: str      # Property alias for subject_id
    role: str                 # Primary role string
    station_jurisdiction: str
    scopes: List[str]
    is_authenticated: bool
    raw_claims: Dict[str, Any]
```

**NOT stored:** passwords, plaintext credentials, client secrets, private keys, raw tokens.

---

## 7. Configuration

All configuration via environment variables through `core/config.py`:

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_MODE` | `development` | `development` or `oidc` |
| `OIDC_ISSUER_URL` | `None` | OIDC issuer URL |
| `OIDC_AUDIENCE` | `None` | Expected JWT audience |
| `OIDC_CLIENT_ID` | `None` | OIDC client ID |
| `OIDC_JWKS_URL` | `None` | JWKS endpoint (auto-discovered if not set) |
| `OIDC_ALGORITHMS` | `["RS256"]` | Permitted JWT signing algorithms |
| `OIDC_DISCOVERY_ENABLED` | `True` | Use `.well-known/openid-configuration` |
| `OIDC_JWKS_CACHE_TTL` | `3600` | JWKS cache TTL in seconds |
| `DEV_INVESTIGATOR_SUBJECT_ID` | `dev-investigator-001` | Default dev identity |

**Nothing hardcoded:** No secrets, signing keys, or production URLs in source code.

---

## 8. Development Mode

When `AUTH_MODE=development`:

- **Accepts** `X-Investigator-Id` headers as identity (for local testing)
- **Accepts** Bearer tokens as subject_id (no signature validation)
- **Clearly marked** — `authentication_method="development"`, `issuer="sakshi-development-idp"`
- **Never silently enabled in production** — warns if `ENVIRONMENT=production` with dev auth
- **No passwords stored** — identity is header-based, not credential-based

```
⚠️  DEVELOPMENT ONLY — NOT FOR PRODUCTION USE
```

---

## 9. Production Requirements

For `AUTH_MODE=oidc`:

1. Set `OIDC_ISSUER_URL` to your OIDC provider's issuer URL
2. Set `OIDC_AUDIENCE` to the SAKSHI client ID
3. Set `OIDC_CLIENT_ID` for frontend login flows
4. Optionally set `OIDC_JWKS_URL` (or let discovery find it)
5. Ensure the IdP issues JWTs with `sub`, `preferred_username`, `name`, `email` claims

Supported providers (via standard OIDC):
- Keycloak
- Auth0
- Microsoft Entra ID
- Any standards-compliant OIDC provider

---

## 10. API Endpoints

### `GET /api/v1/auth/me` (Protected)

Returns the authenticated investigator's identity.

**Response (200):**
```json
{
    "authenticated": true,
    "subject_id": "investigator-001",
    "username": "sharma.inspector",
    "display_name": "Inspector Sharma",
    "email": "sharma@police.gov.in",
    "roles": ["INVESTIGATING_OFFICER"],
    "issuer": "https://idp.example.com",
    "authentication_method": "oidc",
    "investigator_id": "investigator-001",
    "role": "INVESTIGATING_OFFICER",
    "station_jurisdiction": null
}
```

**Error responses:**
| Condition | Status | Error Code |
|-----------|--------|------------|
| No token | 401 | `AUTHENTICATION_REQUIRED` |
| Invalid token | 401 | `INVALID_TOKEN` |
| Expired token | 401 | `TOKEN_EXPIRED` |
| Wrong issuer | 401 | `TOKEN_ISSUER_INVALID` |
| Wrong audience | 401 | `TOKEN_AUDIENCE_INVALID` |
| Missing `sub` | 401 | `IDENTITY_CLAIM_MISSING` |

### `GET /api/v1/auth/status` (Public)

Returns non-sensitive authentication configuration.

```json
{
    "auth_mode": "development",
    "oidc_configured": false,
    "issuer_url": null,
    "client_id": null,
    "development_mode": true
}
```

---

## 11. Error Handling

All errors extend `SakshiException` from `core/errors.py`:

| Error Class | Code | HTTP Status |
|------------|------|-------------|
| `AuthenticationRequiredException` | `AUTHENTICATION_REQUIRED` | 401 |
| `InvalidTokenException` | `INVALID_TOKEN` | 401 |
| `TokenExpiredException` | `TOKEN_EXPIRED` | 401 |
| `TokenIssuerInvalidException` | `TOKEN_ISSUER_INVALID` | 401 |
| `TokenAudienceInvalidException` | `TOKEN_AUDIENCE_INVALID` | 401 |
| `IdentityClaimMissingException` | `IDENTITY_CLAIM_MISSING` | 401 |
| `OIDCConfigurationException` | `OIDC_CONFIGURATION_ERROR` | 500 |

**Never leaked:** signing keys, token contents, internal cryptographic details.

---

## 12. Security Considerations

1. **Impersonation prevention:** Client-supplied `investigator_id` in request body is never trusted as identity proof. Identity comes from validated tokens.
2. **JWT verification:** Signatures verified against JWKS, not just decoded.
3. **Algorithm restriction:** Only permitted algorithms accepted (default: RS256).
4. **Token expiry:** Expired tokens rejected.
5. **Issuer/audience validation:** Only tokens from configured issuers accepted.
6. **No secrets in frontend:** No client secrets in JavaScript.
7. **Dev mode isolation:** Development auth clearly separated, warns in production.
8. **Claims sanitization:** Sensitive fields stripped before storing in identity model.

---

## 13. Audit Integration

Authentication events recorded via `AuditIntegrationService.record_auth_event()`:

| Event | Description |
|-------|-------------|
| `AUTHENTICATION_SUCCESS` | Investigator successfully authenticated |
| `AUTHENTICATION_FAILURE` | Token validation failed |
| `TOKEN_VALIDATION_FAILURE` | Specific validation step failed |

**Never logged:** access tokens, refresh tokens, client secrets, private keys.

---

## 14. Tests

```
Tests:
    MOD-01 (Case Management):  17 passed
    MOD-02 (Identity/OIDC):    32 passed
    Total:                     49 passed
    Failures:                  0
    Warnings:                  2 (deprecation, non-blocking)
```

### Test Coverage

| # | Test | Category |
|---|------|----------|
| 1 | No Authorization header → 401 | Authentication |
| 2 | Malformed Authorization header → 401 | Authentication |
| 3 | Invalid token → 401 | Authentication |
| 4 | Expired token → 401 | Authentication |
| 5 | Invalid signature → 401 | Authentication |
| 6 | Wrong issuer → 401 | Authentication |
| 7 | Wrong audience → 401 | Authentication |
| 8 | Missing subject claim → 401 | Authentication |
| 9 | Valid token → authenticated investigator | Authentication |
| 10 | Identity extraction | Authentication |
| 11 | Development auth works when enabled | Development |
| 12 | Dev auth cannot be treated as production | Development |
| 13 | `/auth/me` without authentication → 401 | API |
| 14 | `/auth/me` with valid identity → 200 | API |
| 15 | Protected case endpoint without auth → 401 | API |
| 16 | Protected case endpoint with auth → works | API |
| 17-20 | MOD-01 regression tests all pass | Regression |
| — | Client cannot impersonate via body | Security |
| — | Forged JWTs fail | Security |
| — | Unsigned tokens fail | Security |
| — | JWKS caching works | OIDC |

---

## 15. MOD-01 Integration

MOD-02 integrates with MOD-01 without breaking existing functionality:

```
MOD-02 Identity/OIDC
        ↓
Authenticated Investigator (subject_id → investigator_id)
        ↓
MOD-03 Authorization (placeholder)
        ↓
MOD-01 Case Management (CaseService.create_case)
        ↓
case.assigned_io_id = investigator.investigator_id
```

- `AuthenticatedInvestigator.investigator_id` property returns `subject_id` for backward compatibility
- All existing MOD-01 tests pass without modification (except `subject_id` field rename)
- Case creation still uses authenticated identity, not client-supplied IDs

---

## 16. MOD-03 Integration Boundary

MOD-02 **stops at authentication.** The following are explicitly NOT implemented:

- Case access policies
- Station-level permissions
- Supervisory access controls
- Case ownership authorization
- Attribute-based case restrictions

These belong to **MOD-03 RBAC / ABAC**, which is the next module.

The `IAuthorizationService` interface and `PolicyEngineAuthorizationService` placeholder are preserved from MOD-01 for continuity.

---

## 17. Known Limitations

| Limitation | Status | Resolution |
|-----------|--------|------------|
| No external OIDC provider deployed | Development only | Configure provider and set `AUTH_MODE=oidc` |
| OIDC discovery requires network access | By design | Cache TTL reduces frequency |
| Token refresh not implemented | Planned | Client-side responsibility in OIDC flow |
| No investigator database table | Intentional | External IdP is authority; internal table deferred until needed |
| Dev auth uses header-based identity | Development only | Never enabled in production |
| `DEV_AUTH_BYPASS` config preserved | Deprecated | Use `AUTH_MODE` instead |

---

## Files Created

| File | Purpose |
|------|---------|
| `app/api/v1/auth.py` | Auth API endpoints (`/auth/me`, `/auth/status`) |
| `app/schemas/auth.py` | Auth response schemas |
| `tests/unit/test_auth_service.py` | Comprehensive auth test suite (32 tests) |
| `MOD-02_IDENTITY_OIDC.md` | This documentation |

## Files Modified

| File | Change |
|------|--------|
| `app/core/config.py` | Added OIDC config, AUTH_MODE, dev defaults |
| `app/core/security.py` | Canonical `AuthenticatedInvestigator` with OIDC fields |
| `app/core/errors.py` | Added 7 authentication error types |
| `app/services/auth_service.py` | `OIDCAuthenticationService`, `DevAuthenticationService`, JWKS cache |
| `app/services/audit_integration.py` | Added `record_auth_event()` method |
| `app/api/deps.py` | Updated imports, clarified auth flow documentation |
| `app/main.py` | Registered auth router, updated version/description |
| `requirements.txt` | Added `python-jose[cryptography]`, `cryptography` |
| `tests/conftest.py` | Updated fixtures for `subject_id` field |
| `tests/unit/test_case_service.py` | Fixed `subject_id` usage |
| `tests/integration/test_cases_api.py` | Updated error code assertion |
| `frontend/app.js` | Auth integration (dev login, `/auth/me`, `/auth/status`) |
| `frontend/index.html` | Dev login panel, auth indicators |
| `frontend/style.css` | Auth UI styles |

---

## NEXT

```
PHASE 1 — CASE INITIATION
│
├── ✅ MOD-01 Case Management Service
│      └── Create case / Case ID / Workspace / IO association
│
├── ✅ MOD-02 Identity / OIDC
│      └── Authenticate investigator
│
├── 🔨 MOD-03 RBAC / ABAC
│      └── Restrict access
│
└── ⏳ MOD-04 Stage Engine
       └── Control lifecycle
```
