# Firebase IAM, Officer Registry, and Case Assignment

## Status

Implemented in source and verified with isolated SQLite service tests. This is not a
claim that Firebase or PostgreSQL has been production-validated: no Firebase project,
Admin credentials, or PostgreSQL service was available in this workspace.

## Architecture

`AUTH_MODE=firebase` selects `FirebaseAuthenticationService`. It verifies a bearer
ID token through the Firebase Admin SDK with revocation checking, then resolves the
Firebase UID to an active, mobile-verified `Officer` record. Roles, station, and
jurisdiction always come from that record, never from browser input or token custom
claims. Development authentication is rejected when `ENVIRONMENT=production`; OIDC
remains supported as an explicit alternative.

Firebase does not provide a native phone-number-plus-password provider. The optional
server-side `/api/v1/auth/login` flow normalizes an officer's E.164 mobile number,
looks up the local active officer, and exchanges a password using Firebase's supported
email/password endpoint against a random internal `@firebase.sakshi.invalid` account
identifier. That opaque identifier is not returned to clients and is not an access
credential. Password recovery and mobile-number changes require an authorized,
audited operational workflow; this implementation intentionally does not promise
email recovery for a non-mailbox identifier.

## Persistence and authorization

The additive `003_iam_officers` migration adds organizations, jurisdictions, police
stations, officers, and case-assignment history. Existing `Case.assigned_io_id` is
maintained as the current assignment projection; `case_assignments` preserves prior
assignments and reasons. Assignment requires an active Investigating Officer in the
case jurisdiction and a privileged actor in that same scope (or `ALL`). The existing
policy engine was tightened so supervisory case access requires trusted scope match
or `ALL`; it is no longer broad merely by title.

Officer onboarding is administrator-controlled. It validates the persistent hierarchy,
normalizes mobile numbers, generates random, immutable `SAK-<role>-<year>-<entropy>`
usernames, provisions Firebase server-side, and compensates by disabling a newly
created provider identity if the database insert fails. No public registration route
exists. Audit events contain IDs, status, and scope only—not passwords, tokens, or
the internal Firebase identifier.

## API

* `POST /api/v1/auth/login` (only in Firebase mode): `{"mobile_number":"+919876543210","password":"…"}` returns only an ID token and expiry.
* `POST /api/v1/organizations`, `/jurisdictions`, `/stations`: protected scope setup.
* `POST/GET /api/v1/officers`: protected officer onboarding and scoped listing.
* `POST /api/v1/officers/{officer_id}/deactivate|reactivate`: lifecycle changes.
* `POST/GET /api/v1/cases/{case_id}/assignments`: assignment/reassignment and history.

The frontend uses the login endpoint only in Firebase mode, keeps the ID token in
memory, loads `/auth/me` before navigating, and sends it as a bearer token. It does
not treat local storage, UI role selections, or a dummy button as authorization.

## Configuration and deployment

Install dependencies with `pip install -r backend/requirements.txt`, then apply
`alembic upgrade head` from `backend`. Set `AUTH_MODE=firebase`,
`FIREBASE_PROJECT_ID`, and server-side Application Default Credentials (or
`GOOGLE_APPLICATION_CREDENTIALS`). `FIREBASE_WEB_API_KEY` enables only the backend
password exchange; do not place service-account JSON or private keys in the frontend.
Configure Firebase Email/Password sign-in and authorized web domains. Verify mobiles
through an approved out-of-band process before setting `mobile_verified=true`.

## Verification

* `python -m compileall app` — passed.
* `node --check frontend/app.js` — passed.
* `pytest tests/unit/test_iam_service.py -q` — **5 passed**, 1 existing TestClient deprecation warning.
* The established broader HTTP-oriented tests could not complete in this Windows
  sandbox because the existing TestClient/AnyIO runtime hangs; they are not reported
  as passing. Firebase Admin live token verification and Firebase provisioning were
  not run because no credentials were supplied. PostgreSQL migration/index behaviour
  remains unverified because no PostgreSQL service is installed locally.

## Files

New model, repository, schema, services, API router, migration, and unit test files
are under `backend/app`, `backend/migrations`, and `backend/tests`. Configuration is
in `backend/.env.example`; `firebase-admin` was added to `backend/requirements.txt`.
No existing SQLite database was opened, recreated, or modified.
