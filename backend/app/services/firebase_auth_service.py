"""Firebase identity adapter. It deliberately contains no authorization policy."""
import re
import secrets
from typing import Any, Dict, Optional
import httpx
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.errors import (
    AuthenticationRequiredException,
    InvalidTokenException,
    TokenExpiredException,
    ForbiddenException,
    InvalidInvestigatorException,
    SakshiException,
)
from app.core.security import AuthenticatedInvestigator
from app.repositories.iam_repository import IAMRepository
from app.services.audit_integration import AuditIntegrationService


class FirebaseUnavailableException(SakshiException):
    def __init__(self, message: str = "Authentication service is temporarily unavailable."):
        super().__init__(503, "FIREBASE_UNAVAILABLE", message)


def deterministic_firebase_identifier(mobile_e164: str) -> str:
    """
    Deterministic, internal mapping between a normalized E.164 mobile number
    and a synthetic Firebase email identifier.
    
    Security properties:
    - Kept strictly internal to the authentication service.
    - Never displayed to officers or returned in API responses.
    - Not an authorization credential.
    - Deterministic across restarts and database restores.
    """
    clean_digits = re.sub(r"[^0-9]", "", mobile_e164 or "")
    if not clean_digits:
        return f"{secrets.token_urlsafe(24).lower()}@firebase.sakshi.invalid"
    return f"officer.{clean_digits}@firebase.sakshi.invalid"


def private_firebase_login_identifier() -> str:
    """Backward-compatible fallback random identifier."""
    return f"{secrets.token_urlsafe(24).lower()}@firebase.sakshi.invalid"


class FirebaseAuthenticationService:
    """Verifies Firebase tokens and resolves the authoritative local officer scope."""

    def _admin_auth(self):
        try:
            import firebase_admin
            from firebase_admin import auth
            if not firebase_admin._apps:
                firebase_admin.initialize_app(options={"projectId": settings.FIREBASE_PROJECT_ID})
            return auth
        except Exception as exc:
            raise FirebaseUnavailableException(f"Firebase Admin SDK unavailable: {exc}") from exc

    def authenticate_request(
        self,
        auth_header: Optional[str] = None,
        db: Optional[Session] = None,
        **_: Any
    ) -> AuthenticatedInvestigator:
        if not auth_header:
            raise AuthenticationRequiredException("Authentication credentials required.")
        if not auth_header.startswith("Bearer "):
            raise InvalidTokenException("Authorization header must use Bearer scheme.")
        if db is None:
            raise FirebaseUnavailableException("Database session required for identity resolution.")
        token = auth_header[7:].strip()
        if not token:
            raise AuthenticationRequiredException("Bearer token is empty.")

        try:
            auth_module = self._admin_auth()
            # Verify signature, issuer, audience, expiration, and revocation status
            claims = auth_module.verify_id_token(token, check_revoked=True)
        except FirebaseUnavailableException:
            raise
        except Exception as exc:
            exc_name = type(exc).__name__
            exc_str = str(exc).lower()
            AuditIntegrationService.record_auth_event(
                "TOKEN_VALIDATION_FAILURE",
                details={"provider": "firebase", "error_type": exc_name}
            )
            if "expired" in exc_str or "Expired" in exc_name:
                raise TokenExpiredException("Firebase ID token has expired.") from exc
            if "revoked" in exc_str or "Revoked" in exc_name:
                raise InvalidTokenException("Firebase ID token has been revoked.") from exc
            if "certificate" in exc_str or "Certificate" in exc_name or "transport" in exc_str:
                raise FirebaseUnavailableException() from exc
            raise InvalidTokenException("Invalid Firebase ID token.") from exc

        uid = claims.get("uid") or claims.get("sub")
        if not uid:
            raise InvalidTokenException("Token claims missing unique subject identifier.")

        # Resolve authoritative SAKSHI officer record
        officer = IAMRepository(db).officer_by_uid(uid)
        if not officer:
            AuditIntegrationService.record_auth_event(
                "AUTHENTICATION_FAILURE",
                subject_id=uid,
                details={"category": "unlinked_identity", "uid": uid}
            )
            raise ForbiddenException("Authentication is valid, but this account is not authorized for SAKSHI.")

        # Server-side account status check (even if token is cryptographically valid)
        if officer.status != "ACTIVE":
            AuditIntegrationService.record_auth_event(
                "AUTHENTICATION_FAILURE",
                subject_id=officer.officer_id,
                details={"category": "inactive_officer", "status": officer.status}
            )
            raise ForbiddenException(f"Officer account is {officer.status.lower()}. Access is denied.")

        if not officer.mobile_verified:
            AuditIntegrationService.record_auth_event(
                "AUTHENTICATION_FAILURE",
                subject_id=officer.officer_id,
                details={"category": "unverified_mobile"}
            )
            raise ForbiddenException("Officer mobile number has not been verified.")

        AuditIntegrationService.record_auth_event(
            "AUTHENTICATION_SUCCESS",
            subject_id=officer.officer_id,
            details={"provider": "firebase", "jurisdiction": officer.jurisdiction_id}
        )

        return AuthenticatedInvestigator(
            subject_id=officer.officer_id,
            username=officer.username,
            display_name=officer.full_name,
            email=None,
            roles=[officer.role],
            claims={"uid": uid},
            issuer="firebase",
            authentication_method="firebase",
            name=officer.full_name,
            role=officer.role,
            station_jurisdiction=officer.jurisdiction_id,
            scopes=[],
            is_authenticated=True,
            raw_claims={"uid": uid, "iss": claims.get("iss")},
        )


class FirebasePasswordLoginService:
    """Server-side password exchange for the mobile/password UX.

    Firebase only supports passwords for email/password accounts. Officers supply
    a verified E.164 mobile number; the server maps it to a deterministic private
    Firebase email identifier and never exposes that identifier or a refresh token.
    """

    def login(self, db: Session, mobile_e164: str, password: str) -> Dict[str, Any]:
        officer = IAMRepository(db).officer_by_mobile(mobile_e164)
        if not officer:
            AuditIntegrationService.record_auth_event(
                "LOGIN_FAILURE",
                details={"category": "unregistered_mobile", "mobile": mobile_e164[-4:]}
            )
            raise InvalidTokenException("Invalid mobile number or password.")

        if officer.status != "ACTIVE":
            AuditIntegrationService.record_auth_event(
                "LOGIN_FAILURE",
                subject_id=officer.officer_id,
                details={"category": "account_disabled", "status": officer.status}
            )
            raise ForbiddenException(f"Account is {officer.status.lower()}. Contact administrator.")

        if not officer.mobile_verified:
            AuditIntegrationService.record_auth_event(
                "LOGIN_FAILURE",
                subject_id=officer.officer_id,
                details={"category": "unverified_mobile"}
            )
            raise ForbiddenException("Officer mobile number has not been verified.")

        login_identifier = officer.firebase_login_identifier or deterministic_firebase_identifier(officer.mobile_e164)

        if not settings.FIREBASE_WEB_API_KEY:
            raise FirebaseUnavailableException("Firebase Web API configuration is missing.")

        try:
            response = httpx.post(
                "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword",
                params={"key": settings.FIREBASE_WEB_API_KEY},
                json={
                    "email": login_identifier,
                    "password": password,
                    "returnSecureToken": True,
                },
                timeout=10.0,
            )
            if response.status_code != 200:
                err_body = {}
                try:
                    err_body = response.json()
                except Exception:
                    pass
                err_msg = err_body.get("error", {}).get("message", "")
                if "USER_DISABLED" in err_msg:
                    AuditIntegrationService.record_auth_event(
                        "LOGIN_FAILURE",
                        subject_id=officer.officer_id,
                        details={"category": "provider_disabled"}
                    )
                    raise ForbiddenException("Officer account has been disabled in identity provider.")
                AuditIntegrationService.record_auth_event(
                    "LOGIN_FAILURE",
                    subject_id=officer.officer_id,
                    details={"category": "invalid_credentials"}
                )
                raise InvalidTokenException("Invalid mobile number or password.")

            payload = response.json()
            AuditIntegrationService.record_auth_event(
                "LOGIN_SUCCESS",
                subject_id=officer.officer_id,
                details={"provider": "firebase_password_exchange"}
            )
            return {
                "id_token": payload["idToken"],
                "expires_in": int(payload.get("expiresIn", 3600)),
            }
        except (InvalidTokenException, ForbiddenException):
            raise
        except Exception as exc:
            raise FirebaseUnavailableException(f"Identity provider communication error: {exc}") from exc


class FirebaseAdminProvisioner:
    """Trusted onboarding adapter; Firebase credentials never reach the browser."""

    def __init__(self, service: Optional[FirebaseAuthenticationService] = None):
        self._service = service or FirebaseAuthenticationService()

    def create_user(self, identifier: str, password: str, disabled: bool = False) -> str:
        try:
            user = self._service._admin_auth().create_user(
                email=identifier,
                password=password,
                disabled=disabled,
            )
            return user.uid
        except FirebaseUnavailableException:
            raise
        except Exception as exc:
            raise InvalidInvestigatorException(f"Unable to provision the officer identity: {exc}") from exc

    def disable_user(self, uid: str) -> None:
        try:
            auth_module = self._service._admin_auth()
            auth_module.update_user(uid, disabled=True)
            auth_module.revoke_refresh_tokens(uid)
        except Exception:
            pass  # Best-effort compensation

    def enable_user(self, uid: str) -> None:
        try:
            auth_module = self._service._admin_auth()
            auth_module.update_user(uid, disabled=False)
        except Exception:
            pass

    def set_user_password(self, uid: str, new_password: str) -> None:
        try:
            auth_module = self._service._admin_auth()
            auth_module.update_user(uid, password=new_password)
            auth_module.revoke_refresh_tokens(uid)
        except Exception as exc:
            raise InvalidInvestigatorException(f"Unable to update officer credential: {exc}") from exc
