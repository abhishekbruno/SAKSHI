"""
MOD-02: Identity / OIDC — Authentication Service for SAKSHI Investigation Platform.

Implements the authentication boundary:
    - WHO is this investigator? (authentication)
    - NOT what can they do — that belongs to MOD-03 RBAC/ABAC.

Architecture:
    IAuthenticationService (abstract)
        ├── OIDCAuthenticationService    — Production: real JWT/OIDC validation
        └── DevAuthenticationService     — Development-only: deterministic mock identity

CRITICAL SECURITY RULES:
    - No passwords or raw credentials are stored or accepted.
    - JWT decoding ≠ JWT verification. Signatures MUST be verified.
    - Client-supplied investigator IDs are NEVER trusted as proof of identity.
    - Development auth is NEVER silently enabled in production.
    - Tokens, secrets, and private keys are NEVER logged.
"""
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List

from app.core.config import settings
from app.core.security import AuthenticatedInvestigator
from app.core.errors import (
    AuthenticationRequiredException,
    InvalidTokenException,
    TokenExpiredException,
    TokenIssuerInvalidException,
    TokenAudienceInvalidException,
    IdentityClaimMissingException,
    OIDCConfigurationException,
    ForbiddenException,
    UnauthorizedException,
)
from app.core.logging import log_event
from app.models.case import Case

logger = logging.getLogger("sakshi.mod02.auth")


# ═══════════════════════════════════════════════════════════════════════════
# Authentication Service Interface
# ═══════════════════════════════════════════════════════════════════════════

class IAuthenticationService(ABC):
    """
    Abstract authentication boundary.
    Implementations validate credentials and extract investigator identity.
    """

    @abstractmethod
    def authenticate_request(
        self,
        auth_header: Optional[str] = None,
        dev_investigator_id: Optional[str] = None,
        dev_role: Optional[str] = None,
        dev_jurisdiction: Optional[str] = None
    ) -> AuthenticatedInvestigator:
        """
        Validate credentials and return an authenticated investigator.
        Raises AuthenticationRequiredException or InvalidTokenException on failure.
        """
        pass


# ═══════════════════════════════════════════════════════════════════════════
# OIDC Discovery & JWKS Cache
# ═══════════════════════════════════════════════════════════════════════════

class OIDCDiscoveryCache:
    """
    Caches OIDC discovery metadata and JWKS keys.
    Fetches from {issuer}/.well-known/openid-configuration.
    Handles key rotation by re-fetching when cache expires.

    SECURITY: Does not cache tokens. Only caches public keys and discovery metadata.
    """

    def __init__(self, issuer_url: str, cache_ttl: int = 3600):
        self._issuer_url = issuer_url.rstrip("/")
        self._cache_ttl = cache_ttl
        self._discovery_metadata: Optional[Dict[str, Any]] = None
        self._jwks: Optional[Dict[str, Any]] = None
        self._jwks_fetched_at: float = 0
        self._discovery_fetched_at: float = 0

    @property
    def discovery_url(self) -> str:
        return f"{self._issuer_url}/.well-known/openid-configuration"

    def get_discovery_metadata(self) -> Dict[str, Any]:
        """
        Fetch and cache OIDC discovery metadata.
        Raises OIDCConfigurationException on failure.
        """
        now = time.time()
        if self._discovery_metadata and (now - self._discovery_fetched_at) < self._cache_ttl:
            return self._discovery_metadata

        try:
            import httpx
            response = httpx.get(self.discovery_url, timeout=10.0)
            response.raise_for_status()
            self._discovery_metadata = response.json()
            self._discovery_fetched_at = now
            return self._discovery_metadata
        except Exception as e:
            log_event(
                event_type="OIDC_DISCOVERY_FAILURE",
                message=f"Failed to fetch OIDC discovery from {self.discovery_url}: {type(e).__name__}"
            )
            raise OIDCConfigurationException(
                f"Failed to fetch OIDC discovery metadata from {self.discovery_url}"
            )

    def get_jwks(self, jwks_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch and cache JWKS (JSON Web Key Set) for token signature verification.
        Falls back to discovery-derived jwks_uri if no explicit URL provided.
        """
        now = time.time()
        if self._jwks and (now - self._jwks_fetched_at) < self._cache_ttl:
            return self._jwks

        if not jwks_url:
            metadata = self.get_discovery_metadata()
            jwks_url = metadata.get("jwks_uri")
            if not jwks_url:
                raise OIDCConfigurationException("JWKS URI not found in OIDC discovery metadata.")

        try:
            import httpx
            response = httpx.get(jwks_url, timeout=10.0)
            response.raise_for_status()
            self._jwks = response.json()
            self._jwks_fetched_at = now
            return self._jwks
        except Exception as e:
            log_event(
                event_type="JWKS_FETCH_FAILURE",
                message=f"Failed to fetch JWKS from {jwks_url}: {type(e).__name__}"
            )
            raise OIDCConfigurationException(
                f"Failed to fetch JWKS from {jwks_url}"
            )

    def invalidate(self):
        """Force re-fetch on next access (e.g. after key rotation detection)."""
        self._jwks = None
        self._jwks_fetched_at = 0
        self._discovery_metadata = None
        self._discovery_fetched_at = 0


# ═══════════════════════════════════════════════════════════════════════════
# Production OIDC Authentication Service
# ═══════════════════════════════════════════════════════════════════════════

class OIDCAuthenticationService(IAuthenticationService):
    """
    Production authentication service implementing real OIDC JWT validation.

    Validation pipeline:
        1. Token exists (Authorization: Bearer <token>)
        2. Token format is valid
        3. Token signature is valid (verified against JWKS)
        4. Token issuer is trusted
        5. Token audience is correct
        6. Token is not expired
        7. Required identity claims exist (sub)
        8. Algorithm is permitted
        9. Subject identity is extracted

    SECURITY: This is JWT VERIFICATION, not just JWT DECODING.
    """

    def __init__(
        self,
        issuer_url: str,
        audience: Optional[str] = None,
        algorithms: Optional[List[str]] = None,
        jwks_url: Optional[str] = None,
        cache_ttl: int = 3600,
        discovery_enabled: bool = True,
    ):
        self._issuer_url = issuer_url.rstrip("/")
        self._audience = audience
        self._algorithms = algorithms or ["RS256"]
        self._jwks_url = jwks_url
        self._discovery_enabled = discovery_enabled
        self._discovery_cache = OIDCDiscoveryCache(issuer_url, cache_ttl)

    def authenticate_request(
        self,
        auth_header: Optional[str] = None,
        dev_investigator_id: Optional[str] = None,
        dev_role: Optional[str] = None,
        dev_jurisdiction: Optional[str] = None
    ) -> AuthenticatedInvestigator:
        """
        Validate a Bearer JWT token and extract investigator identity.
        dev_* parameters are IGNORED in production OIDC mode.
        """
        # Step 1: Token must exist
        if not auth_header:
            raise AuthenticationRequiredException()

        # Step 2: Token format must be valid
        if not auth_header.startswith("Bearer "):
            raise InvalidTokenException("Authorization header must use Bearer scheme.")

        token = auth_header[7:].strip()
        if not token:
            raise AuthenticationRequiredException("Bearer token is empty.")

        # Steps 3-9: Full JWT verification
        return self._validate_and_extract(token)

    def _validate_and_extract(self, token: str) -> AuthenticatedInvestigator:
        """
        Full JWT validation pipeline:
        - Verify signature against JWKS
        - Verify issuer
        - Verify audience
        - Verify expiration
        - Verify algorithm
        - Extract identity claims
        """
        from jose import jwt, JWTError, ExpiredSignatureError

        # Fetch signing keys
        try:
            jwks = self._discovery_cache.get_jwks(self._jwks_url)
        except OIDCConfigurationException:
            raise

        # Build verification options
        options = {
            "verify_signature": True,
            "verify_aud": self._audience is not None,
            "verify_iss": True,
            "verify_exp": True,
            "verify_nbf": True,
            "verify_iat": True,
            "verify_sub": True,
        }

        try:
            # Decode AND verify the token
            payload = jwt.decode(
                token,
                jwks,
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer_url,
                options=options
            )
        except ExpiredSignatureError:
            log_event(
                event_type="AUTHENTICATION_FAILURE",
                message="Token validation failed: token expired"
            )
            raise TokenExpiredException()
        except JWTError as e:
            error_msg = str(e).lower()
            if "audience" in error_msg:
                log_event(
                    event_type="AUTHENTICATION_FAILURE",
                    message="Token validation failed: audience mismatch"
                )
                raise TokenAudienceInvalidException()
            if "issuer" in error_msg:
                log_event(
                    event_type="AUTHENTICATION_FAILURE",
                    message="Token validation failed: issuer mismatch"
                )
                raise TokenIssuerInvalidException()
            if "signature" in error_msg or "verification" in error_msg:
                log_event(
                    event_type="AUTHENTICATION_FAILURE",
                    message="Token validation failed: signature verification failed"
                )
                raise InvalidTokenException("Token signature verification failed.")

            log_event(
                event_type="AUTHENTICATION_FAILURE",
                message=f"Token validation failed: {type(e).__name__}"
            )
            raise InvalidTokenException()

        # Step 7: Required identity claims
        subject_id = payload.get("sub")
        if not subject_id:
            raise IdentityClaimMissingException("sub")

        # Step 9: Extract identity
        investigator = AuthenticatedInvestigator(
            subject_id=subject_id,
            username=payload.get("preferred_username"),
            display_name=payload.get("name", payload.get("preferred_username", f"Officer {subject_id}")),
            email=payload.get("email"),
            roles=self._extract_roles(payload),
            claims=self._sanitize_claims(payload),
            issuer=payload.get("iss"),
            authentication_method="oidc",
            # Legacy compatibility fields
            name=payload.get("name", payload.get("preferred_username", f"Officer {subject_id}")),
            role=self._extract_primary_role(payload),
            station_jurisdiction=payload.get("station_jurisdiction"),
            scopes=payload.get("scope", "").split() if isinstance(payload.get("scope"), str) else [],
            is_authenticated=True,
            raw_claims=self._sanitize_claims(payload),
        )

        log_event(
            event_type="AUTHENTICATION_SUCCESS",
            message=f"Investigator authenticated via OIDC",
            investigator_id=subject_id
        )

        return investigator

    @staticmethod
    def _extract_roles(payload: Dict[str, Any]) -> List[str]:
        """Extract roles from standard OIDC claim locations."""
        roles = []
        # Direct roles claim
        if "roles" in payload:
            roles.extend(payload["roles"] if isinstance(payload["roles"], list) else [payload["roles"]])
        # Realm access (Keycloak pattern)
        realm_access = payload.get("realm_access", {})
        if isinstance(realm_access, dict) and "roles" in realm_access:
            roles.extend(realm_access["roles"])
        # Resource access (Keycloak pattern)
        resource_access = payload.get("resource_access", {})
        if isinstance(resource_access, dict):
            for resource in resource_access.values():
                if isinstance(resource, dict) and "roles" in resource:
                    roles.extend(resource["roles"])
        return list(set(roles))

    @staticmethod
    def _extract_primary_role(payload: Dict[str, Any]) -> str:
        """Extract primary role for legacy compatibility with MOD-01."""
        roles = OIDCAuthenticationService._extract_roles(payload)
        # Priority order for SAKSHI roles
        role_priority = ["ADMIN", "STATION_HEAD", "SUPERVISORY_OFFICER", "INVESTIGATING_OFFICER"]
        for r in role_priority:
            if r in roles:
                return r
        return roles[0] if roles else "INVESTIGATING_OFFICER"

    @staticmethod
    def _sanitize_claims(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive fields from claims before storing in the identity model.
        SECURITY: Never include tokens, signatures, or cryptographic material.
        """
        sensitive_keys = {"nonce", "at_hash", "c_hash", "s_hash", "auth_time"}
        return {k: v for k, v in payload.items() if k not in sensitive_keys}


# ═══════════════════════════════════════════════════════════════════════════
# Development-Only Authentication Service
# ═══════════════════════════════════════════════════════════════════════════

class DevAuthenticationService(IAuthenticationService):
    """
    ╔══════════════════════════════════════════════════════════════════╗
    ║  ⚠️  DEVELOPMENT ONLY — NOT FOR PRODUCTION USE                ║
    ║                                                                ║
    ║  Creates deterministic local investigator identities for       ║
    ║  development and testing. Never silently activates in          ║
    ║  production. Does not validate real tokens.                    ║
    ╚══════════════════════════════════════════════════════════════════╝
    """

    DEV_ISSUER = "sakshi-development-idp"

    def authenticate_request(
        self,
        auth_header: Optional[str] = None,
        dev_investigator_id: Optional[str] = None,
        dev_role: Optional[str] = None,
        dev_jurisdiction: Optional[str] = None
    ) -> AuthenticatedInvestigator:
        """
        Development-only authentication.

        Accepts:
            - Bearer token: uses token value as subject_id (no signature validation)
            - X-Investigator-Id header: uses header value as subject_id
            - No credentials: returns default dev investigator

        SECURITY: This service is ONLY instantiated when AUTH_MODE=development.
        """
        subject_id = settings.DEV_INVESTIGATOR_SUBJECT_ID
        display_name = settings.DEV_INVESTIGATOR_NAME
        email = settings.DEV_INVESTIGATOR_EMAIL
        role = dev_role or "INVESTIGATING_OFFICER"
        jurisdiction = dev_jurisdiction

        # If Bearer token is provided, use it as the subject_id
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if token:
                subject_id = token
                display_name = f"Officer {token}"

        # If X-Investigator-Id header is provided, use it as the subject_id
        elif dev_investigator_id:
            subject_id = dev_investigator_id.strip()
            display_name = f"Investigator {subject_id}"

        # If neither, require at least one credential
        elif not auth_header and not dev_investigator_id:
            raise AuthenticationRequiredException(
                "No authentication credentials provided. "
                "In development mode, provide a Bearer token or X-Investigator-Id header."
            )

        investigator = AuthenticatedInvestigator(
            # MOD-02 canonical fields
            subject_id=subject_id,
            username=subject_id,
            display_name=display_name,
            email=email,
            roles=[role],
            claims={"sub": subject_id, "iss": self.DEV_ISSUER, "dev": True},
            issuer=self.DEV_ISSUER,
            authentication_method="development",
            # Legacy compatibility fields
            name=display_name,
            role=role,
            station_jurisdiction=jurisdiction,
            scopes=["cases:read", "cases:write"],
            is_authenticated=True,
            raw_claims={"sub": subject_id, "iss": self.DEV_ISSUER, "dev": True},
        )

        log_event(
            event_type="AUTHENTICATION_SUCCESS",
            message=f"[DEVELOPMENT] Investigator authenticated via dev-mode identity",
            investigator_id=subject_id
        )

        return investigator


# ═══════════════════════════════════════════════════════════════════════════
# Authorization Service Interface (MOD-03 boundary — preserved from MOD-01)
# ═══════════════════════════════════════════════════════════════════════════

class IAuthorizationService(ABC):
    """
    Abstract authorization boundary (MOD-03 RBAC/ABAC).
    These interfaces are defined here for backward compatibility with MOD-01.
    Full implementation belongs to MOD-03.
    """
    @abstractmethod
    def check_can_create_case(self, investigator: AuthenticatedInvestigator, target_station: Optional[str] = None) -> None:
        pass

    @abstractmethod
    def check_can_read_case(self, investigator: AuthenticatedInvestigator, case: Case) -> None:
        pass

    @abstractmethod
    def check_can_modify_case(self, investigator: AuthenticatedInvestigator, case: Case) -> None:
        pass

    @abstractmethod
    def check_can_assign_io(self, investigator: AuthenticatedInvestigator, target_io_id: str, case: Optional[Case] = None) -> None:
        pass

    @abstractmethod
    def get_case_list_filter(self, investigator: AuthenticatedInvestigator) -> Optional[str]:
        pass


class PolicyEngineAuthorizationService(IAuthorizationService):
    """
    MOD-03: RBAC / ABAC policy evaluator.

    Delegates to the centralized PolicyEngine for all authorization decisions.
    Preserves the IAuthorizationService interface consumed by CaseService.

    Architecture:
        CaseService → IAuthorizationService.check_*()
            → PolicyEngine.evaluate(AuthorizationContext)
                → AuthorizationDecision (ALLOW / DENY)
    """

    def __init__(self):
        from app.services.authorization_service import policy_engine, AuthorizationContext
        self._engine = policy_engine
        self._AuthorizationContext = AuthorizationContext

    def check_can_create_case(self, investigator: AuthenticatedInvestigator, target_station: Optional[str] = None) -> None:
        ctx = self._AuthorizationContext.from_investigator(
            investigator, action="create"
        )
        decision = self._engine.evaluate(ctx)
        self._audit_and_enforce(decision, investigator)

    def check_can_read_case(self, investigator: AuthenticatedInvestigator, case: Case) -> None:
        ctx = self._AuthorizationContext.from_investigator(
            investigator, action="read", case=case
        )
        decision = self._engine.evaluate(ctx)
        self._audit_and_enforce(decision, investigator)

    def check_can_modify_case(self, investigator: AuthenticatedInvestigator, case: Case) -> None:
        ctx = self._AuthorizationContext.from_investigator(
            investigator, action="update", case=case
        )
        decision = self._engine.evaluate(ctx)
        self._audit_and_enforce(decision, investigator)

    def check_can_assign_io(self, investigator: AuthenticatedInvestigator, target_io_id: str, case: Optional[Case] = None) -> None:
        ctx = self._AuthorizationContext.from_investigator(
            investigator, action="assign", case=case, target_io_id=target_io_id
        )
        decision = self._engine.evaluate(ctx)
        self._audit_and_enforce(decision, investigator)

    def get_case_list_filter(self, investigator: AuthenticatedInvestigator) -> Optional[str]:
        """
        Returns the IO filter for case listing.
        Supervisory → None (all cases). Regular IO → own cases only.
        """
        return self._engine.get_case_list_filter(investigator)

    @staticmethod
    def _audit_and_enforce(decision, investigator: AuthenticatedInvestigator) -> None:
        """Log the authorization decision and enforce denial."""
        from app.services.audit_integration import AuditIntegrationService

        if decision.allowed:
            log_event(
                event_type="AUTHORIZATION_ALLOWED",
                message=f"Authorization ALLOWED: {decision.policy_id} — {decision.reason}",
                investigator_id=decision.subject_id,
                case_id=decision.resource_id,
            )
            AuditIntegrationService.record_authorization_event(
                decision="ALLOW",
                subject_id=decision.subject_id,
                action=decision.action,
                resource_type=decision.resource_type,
                resource_id=decision.resource_id,
                policy_id=decision.policy_id,
                reason=decision.reason,
            )
        else:
            log_event(
                event_type="AUTHORIZATION_DENIED",
                message=f"Authorization DENIED: {decision.policy_id} — {decision.reason}",
                investigator_id=decision.subject_id,
                case_id=decision.resource_id,
            )
            AuditIntegrationService.record_authorization_event(
                decision="DENY",
                subject_id=decision.subject_id,
                action=decision.action,
                resource_type=decision.resource_type,
                resource_id=decision.resource_id,
                policy_id=decision.policy_id,
                reason=decision.reason,
            )
            raise ForbiddenException(decision.to_safe_client_message())


# ═══════════════════════════════════════════════════════════════════════════
# Service Factory — creates the correct auth service based on configuration
# ═══════════════════════════════════════════════════════════════════════════

def _create_authentication_service() -> IAuthenticationService:
    """
    Factory that selects the authentication service based on AUTH_MODE configuration.

    AUTH_MODE=development → DevAuthenticationService (mock identity, no token validation)
    AUTH_MODE=oidc        → OIDCAuthenticationService (real JWT/OIDC validation)
    """
    if settings.is_oidc_auth:
        if not settings.OIDC_ISSUER_URL:
            raise OIDCConfigurationException(
                "AUTH_MODE is 'oidc' but OIDC_ISSUER_URL is not configured. "
                "Set the OIDC_ISSUER_URL environment variable."
            )
        return OIDCAuthenticationService(
            issuer_url=settings.OIDC_ISSUER_URL,
            audience=settings.OIDC_AUDIENCE,
            algorithms=settings.OIDC_ALGORITHMS,
            jwks_url=settings.OIDC_JWKS_URL,
            cache_ttl=settings.OIDC_JWKS_CACHE_TTL,
            discovery_enabled=settings.OIDC_DISCOVERY_ENABLED,
        )
    else:
        if settings.ENVIRONMENT == "production":
            log_event(
                event_type="SECURITY_WARNING",
                message="⚠️  AUTH_MODE is 'development' in a PRODUCTION environment. "
                        "This is a security risk. Set AUTH_MODE=oidc for production."
            )
        return DevAuthenticationService()


# Default singleton instances
auth_service: IAuthenticationService = _create_authentication_service()
authorization_service = PolicyEngineAuthorizationService()
