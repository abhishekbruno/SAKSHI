"""
MOD-02: Identity / OIDC — Authentication Tests.

Tests the authentication boundary:
    1. No Authorization header → 401
    2. Malformed Authorization header → 401
    3. Invalid token → 401
    4. Expired token → 401
    5. Invalid signature → 401
    6. Wrong issuer → 401
    7. Wrong audience → 401
    8. Missing subject claim → 401
    9. Valid token → authenticated investigator
    10. Identity extraction
    11. Development authentication works when explicitly enabled
    12. Development authentication cannot be treated as production
    13. /api/v1/auth/me without authentication → 401
    14. /api/v1/auth/me with valid identity → 200
    15. Protected case endpoint without authentication → 401
    16. Protected case endpoint with valid identity → works
    17-20. MOD-01 regression tests (covered in existing test files)

SECURITY TESTS:
    - Client cannot impersonate another investigator
    - Forged JWTs fail
    - Unsigned tokens fail
"""
import time
import json
import pytest
from datetime import datetime, timezone
from jose import jwt as jose_jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

from fastapi import status
from fastapi.testclient import TestClient

from app.core.security import AuthenticatedInvestigator
from app.services.auth_service import (
    DevAuthenticationService,
    OIDCAuthenticationService,
    OIDCDiscoveryCache,
    IAuthenticationService,
)
from app.core.errors import (
    AuthenticationRequiredException,
    InvalidTokenException,
    TokenExpiredException,
    TokenIssuerInvalidException,
    TokenAudienceInvalidException,
    IdentityClaimMissingException,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers: RSA key generation for test JWT creation
# ═══════════════════════════════════════════════════════════════════════════

def generate_rsa_keypair():
    """Generate an RSA keypair for signing test JWTs."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    return private_key


def private_key_to_pem(private_key) -> str:
    """Export private key to PEM format."""
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ).decode()


def public_key_to_jwk(private_key) -> dict:
    """Export public key as a JWK dict for JWKS."""
    from jose import jwk
    from jose.constants import ALGORITHMS
    public_key = private_key.public_key()
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    key = jwk.construct(pub_pem, algorithm=ALGORITHMS.RS256)
    jwk_dict = key.to_dict()
    jwk_dict["kid"] = "test-key-001"
    jwk_dict["use"] = "sig"
    jwk_dict["alg"] = "RS256"
    return jwk_dict


def create_test_jwt(
    private_key,
    claims: dict,
    algorithm: str = "RS256"
) -> str:
    """Create a signed JWT for testing."""
    pem = private_key_to_pem(private_key)
    return jose_jwt.encode(claims, pem, algorithm=algorithm)


def create_test_jwks(private_key) -> dict:
    """Create a JWKS document from a test key."""
    jwk_dict = public_key_to_jwk(private_key)
    return {"keys": [jwk_dict]}


# ═══════════════════════════════════════════════════════════════════════════
# Test: Development Authentication Service
# ═══════════════════════════════════════════════════════════════════════════

class TestDevAuthentication:
    """Tests for the development-only authentication service."""

    def test_bearer_token_creates_identity(self):
        """Test 9 & 10: Bearer token in dev mode creates identity with token as subject_id."""
        service = DevAuthenticationService()
        result = service.authenticate_request(auth_header="Bearer dev-token-xyz")
        assert result.subject_id == "dev-token-xyz"
        assert result.investigator_id == "dev-token-xyz"
        assert result.authentication_method == "development"
        assert result.is_authenticated is True

    def test_x_investigator_id_header_creates_identity(self):
        """Test 11: Dev authentication works when explicitly enabled."""
        service = DevAuthenticationService()
        result = service.authenticate_request(
            dev_investigator_id="IO-7842-SHARMA",
            dev_role="INVESTIGATING_OFFICER",
            dev_jurisdiction="JUR-DEL-04"
        )
        assert result.subject_id == "IO-7842-SHARMA"
        assert result.investigator_id == "IO-7842-SHARMA"
        assert result.role == "INVESTIGATING_OFFICER"
        assert result.station_jurisdiction == "JUR-DEL-04"
        assert result.authentication_method == "development"

    def test_no_credentials_raises_401(self):
        """Test 1: No Authorization header."""
        service = DevAuthenticationService()
        with pytest.raises(AuthenticationRequiredException):
            service.authenticate_request()

    def test_empty_bearer_token_falls_through(self):
        """Empty Bearer token in dev mode falls through to default dev identity."""
        service = DevAuthenticationService()
        # "Bearer " with empty token — in dev mode, falls through
        # No other headers provided → raises AuthenticationRequiredException
        result = service.authenticate_request(auth_header="Bearer ")
        # Falls through bearer branch (empty token), falls to default dev identity
        assert result.authentication_method == "development"

    def test_dev_identity_marked_as_development(self):
        """Test 12: Development authentication cannot accidentally be treated as production."""
        service = DevAuthenticationService()
        result = service.authenticate_request(dev_investigator_id="test-dev")
        assert result.authentication_method == "development"
        assert result.issuer == "sakshi-development-idp"
        assert result.claims.get("dev") is True

    def test_dev_identity_has_correct_structure(self):
        """Dev identity has all canonical MOD-02 fields."""
        service = DevAuthenticationService()
        result = service.authenticate_request(
            dev_investigator_id="IO-TEST-01",
            dev_role="SUPERVISORY_OFFICER"
        )
        assert result.subject_id == "IO-TEST-01"
        assert result.investigator_id == "IO-TEST-01"  # backward compat
        assert result.display_name == "Investigator IO-TEST-01"
        assert result.role == "SUPERVISORY_OFFICER"
        assert "SUPERVISORY_OFFICER" in result.roles
        assert result.issuer == "sakshi-development-idp"


# ═══════════════════════════════════════════════════════════════════════════
# Test: OIDC Authentication Service (Token Validation)
# ═══════════════════════════════════════════════════════════════════════════

class TestOIDCAuthentication:
    """Tests for the production OIDC authentication service with real JWT validation."""

    @pytest.fixture(autouse=True)
    def setup_keys(self):
        """Generate RSA keys for each test."""
        self.private_key = generate_rsa_keypair()
        self.jwks = create_test_jwks(self.private_key)
        self.issuer = "https://idp.sakshi-test.example.com"
        self.audience = "sakshi-test-client"

    def _create_service(self, audience=None) -> OIDCAuthenticationService:
        """Create an OIDCAuthenticationService with a pre-loaded JWKS cache."""
        service = OIDCAuthenticationService(
            issuer_url=self.issuer,
            audience=audience or self.audience,
            algorithms=["RS256"],
            discovery_enabled=False,
        )
        # Pre-load the JWKS cache to avoid network calls
        service._discovery_cache._jwks = self.jwks
        service._discovery_cache._jwks_fetched_at = time.time()
        return service

    def _valid_claims(self, **overrides) -> dict:
        """Create valid JWT claims."""
        now = int(time.time())
        claims = {
            "sub": "investigator-001",
            "iss": self.issuer,
            "aud": self.audience,
            "iat": now - 60,
            "exp": now + 3600,
            "nbf": now - 60,
            "name": "Inspector Sharma",
            "preferred_username": "sharma.inspector",
            "email": "sharma@police.gov.in",
            "roles": ["INVESTIGATING_OFFICER"],
        }
        claims.update(overrides)
        return claims

    def test_valid_token_succeeds(self):
        """Test 9: Valid token → authenticated investigator."""
        service = self._create_service()
        token = create_test_jwt(self.private_key, self._valid_claims())
        result = service.authenticate_request(auth_header=f"Bearer {token}")
        assert result.subject_id == "investigator-001"
        assert result.investigator_id == "investigator-001"
        assert result.display_name == "Inspector Sharma"
        assert result.email == "sharma@police.gov.in"
        assert result.authentication_method == "oidc"
        assert result.is_authenticated is True
        assert result.issuer == self.issuer

    def test_identity_extraction(self):
        """Test 10: Identity extraction populates all canonical fields."""
        service = self._create_service()
        claims = self._valid_claims(
            preferred_username="verma.dsp",
            name="DSP Verma",
            email="verma@police.gov.in",
            roles=["SUPERVISORY_OFFICER", "INVESTIGATING_OFFICER"],
            station_jurisdiction="JUR-DEL-CENTRAL",
        )
        token = create_test_jwt(self.private_key, claims)
        result = service.authenticate_request(auth_header=f"Bearer {token}")
        assert result.subject_id == "investigator-001"
        assert result.username == "verma.dsp"
        assert result.display_name == "DSP Verma"
        assert result.email == "verma@police.gov.in"
        assert "SUPERVISORY_OFFICER" in result.roles
        assert "INVESTIGATING_OFFICER" in result.roles
        assert result.role == "SUPERVISORY_OFFICER"  # highest priority

    def test_no_auth_header_raises_401(self):
        """Test 1: No Authorization header."""
        service = self._create_service()
        with pytest.raises(AuthenticationRequiredException):
            service.authenticate_request()

    def test_malformed_auth_header_raises_401(self):
        """Test 2: Malformed Authorization header."""
        service = self._create_service()
        with pytest.raises(InvalidTokenException):
            service.authenticate_request(auth_header="Basic dXNlcjpwYXNz")

    def test_invalid_token_raises_401(self):
        """Test 3: Invalid token (not a valid JWT)."""
        service = self._create_service()
        with pytest.raises(InvalidTokenException):
            service.authenticate_request(auth_header="Bearer not-a-jwt-at-all")

    def test_expired_token_raises_401(self):
        """Test 4: Expired token."""
        service = self._create_service()
        claims = self._valid_claims(
            exp=int(time.time()) - 3600,  # Expired 1 hour ago
            iat=int(time.time()) - 7200,
            nbf=int(time.time()) - 7200,
        )
        token = create_test_jwt(self.private_key, claims)
        with pytest.raises(TokenExpiredException):
            service.authenticate_request(auth_header=f"Bearer {token}")

    def test_invalid_signature_raises_401(self):
        """Test 5: Invalid signature (signed with different key)."""
        service = self._create_service()
        # Sign with a DIFFERENT key than what's in the JWKS
        wrong_key = generate_rsa_keypair()
        token = create_test_jwt(wrong_key, self._valid_claims())
        with pytest.raises(InvalidTokenException):
            service.authenticate_request(auth_header=f"Bearer {token}")

    def test_wrong_issuer_raises_401(self):
        """Test 6: Wrong issuer."""
        service = self._create_service()
        claims = self._valid_claims(iss="https://evil-idp.example.com")
        token = create_test_jwt(self.private_key, claims)
        with pytest.raises((TokenIssuerInvalidException, InvalidTokenException)):
            service.authenticate_request(auth_header=f"Bearer {token}")

    def test_wrong_audience_raises_401(self):
        """Test 7: Wrong audience."""
        service = self._create_service()
        claims = self._valid_claims(aud="wrong-client-id")
        token = create_test_jwt(self.private_key, claims)
        with pytest.raises((TokenAudienceInvalidException, InvalidTokenException)):
            service.authenticate_request(auth_header=f"Bearer {token}")

    def test_missing_subject_claim_raises_401(self):
        """Test 8: Missing subject claim."""
        service = self._create_service()
        claims = self._valid_claims()
        del claims["sub"]
        # Need to disable sub verification to even get past jose
        token = create_test_jwt(self.private_key, claims)
        with pytest.raises((IdentityClaimMissingException, InvalidTokenException)):
            service.authenticate_request(auth_header=f"Bearer {token}")

    def test_empty_bearer_raises_401(self):
        """Empty Bearer token."""
        service = self._create_service()
        with pytest.raises(AuthenticationRequiredException):
            service.authenticate_request(auth_header="Bearer ")

    def test_dev_headers_ignored_in_oidc_mode(self):
        """In OIDC mode, X-Investigator-Id headers are ignored — token is required."""
        service = self._create_service()
        with pytest.raises(AuthenticationRequiredException):
            service.authenticate_request(
                dev_investigator_id="IO-EVIL-IMPERSONATOR",
                dev_role="ADMIN"
            )

    def test_roles_extracted_from_realm_access(self):
        """Keycloak-style realm_access roles are extracted."""
        service = self._create_service()
        claims = self._valid_claims(
            roles=None,
            realm_access={"roles": ["SUPERVISORY_OFFICER", "ADMIN"]}
        )
        # Remove direct roles if set to None
        if claims.get("roles") is None:
            del claims["roles"]
        token = create_test_jwt(self.private_key, claims)
        result = service.authenticate_request(auth_header=f"Bearer {token}")
        assert "SUPERVISORY_OFFICER" in result.roles
        assert "ADMIN" in result.roles


# ═══════════════════════════════════════════════════════════════════════════
# Test: API Endpoints — /api/v1/auth/me
# ═══════════════════════════════════════════════════════════════════════════

class TestAuthMeAPI:
    """Integration tests for the /api/v1/auth/me endpoint."""

    def test_auth_me_without_authentication(self, client):
        """Test 13: /api/v1/auth/me without authentication → 401."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        error = response.json()
        assert error["error_code"] == "AUTHENTICATION_REQUIRED"

    def test_auth_me_with_valid_identity(self, client, auth_headers_io1):
        """Test 14: /api/v1/auth/me with valid identity → 200."""
        response = client.get("/api/v1/auth/me", headers=auth_headers_io1)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["authenticated"] is True
        assert data["subject_id"] == "IO-7842-SHARMA"
        assert data["investigator_id"] == "IO-7842-SHARMA"
        assert data["authentication_method"] == "development"
        assert data["role"] == "INVESTIGATING_OFFICER"

    def test_auth_me_with_bearer_token(self, client):
        """Bearer token in dev mode returns identity with token as subject_id."""
        response = client.get("/api/v1/auth/me", headers={
            "Authorization": "Bearer dev-test-token-123"
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["subject_id"] == "dev-test-token-123"
        assert data["authentication_method"] == "development"

    def test_auth_me_with_supervisor_identity(self, client, auth_headers_supervisor):
        """Supervisor identity is correctly represented."""
        response = client.get("/api/v1/auth/me", headers=auth_headers_supervisor)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["subject_id"] == "IO-0001-COMMISSIONER"
        assert data["role"] == "SUPERVISORY_OFFICER"


# ═══════════════════════════════════════════════════════════════════════════
# Test: API Endpoints — /api/v1/auth/status
# ═══════════════════════════════════════════════════════════════════════════

class TestAuthStatusAPI:
    """Integration tests for the /api/v1/auth/status endpoint."""

    def test_auth_status_returns_config(self, client):
        """Auth status endpoint returns non-sensitive configuration."""
        response = client.get("/api/v1/auth/status")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "auth_mode" in data
        assert "development_mode" in data
        assert "oidc_configured" in data
        # Should not contain secrets
        assert "client_secret" not in str(data)
        assert "signing_key" not in str(data)

    def test_auth_status_no_auth_required(self, client):
        """Status endpoint does not require authentication."""
        response = client.get("/api/v1/auth/status")
        assert response.status_code == status.HTTP_200_OK


# ═══════════════════════════════════════════════════════════════════════════
# Test: Security — Impersonation Prevention
# ═══════════════════════════════════════════════════════════════════════════

class TestSecurityBoundary:
    """
    Security tests ensuring the authentication boundary cannot be bypassed.
    """

    def test_client_cannot_impersonate_via_body(self, client, auth_headers_io1):
        """
        A client cannot impersonate another investigator by sending
        a different investigator_id in the request body.
        The authenticated subject must remain authoritative.
        """
        payload = {
            "title": "Impersonation Test Case",
            "fir_metadata": {
                "fir_number": "FIR-IMPERSONATE-001",
                "police_station": "Test Station"
            },
            "assigned_io_id": "IO-EVIL-IMPERSONATOR"
        }
        # IO1 creates a case but tries to assign it to an impersonator
        response = client.post("/api/v1/cases", json=payload, headers=auth_headers_io1)
        # Should fail because IO1 cannot assign to a different officer
        # (only supervisors can reassign)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_identity_comes_from_auth_not_body(self, client, auth_headers_io1):
        """
        Case creation uses the authenticated identity, not a client-supplied ID.
        When no assigned_io_id is provided, the authenticated investigator is used.
        """
        payload = {
            "title": "Auth Identity Test Case",
            "fir_metadata": {
                "fir_number": "FIR-AUTHID-001",
                "police_station": "Auth Station"
            }
        }
        response = client.post("/api/v1/cases", json=payload, headers=auth_headers_io1)
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        # The assigned IO should be the authenticated user, not a forged value
        assert data["assigned_io_id"] == "IO-7842-SHARMA"

    def test_no_token_on_protected_case_endpoint(self, client):
        """Test 15: Protected case endpoint without authentication → 401."""
        payload = {
            "title": "No Auth Case",
            "fir_metadata": {"fir_number": "FIR-NOAUTH-01", "police_station": "HQ"}
        }
        response = client.post("/api/v1/cases", json=payload)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.json()["error_code"] == "AUTHENTICATION_REQUIRED"

    def test_protected_case_with_valid_identity(self, client, auth_headers_io1):
        """Test 16: Protected case endpoint with valid identity → works."""
        payload = {
            "title": "Valid Auth Case",
            "fir_metadata": {"fir_number": "FIR-VALID-01", "police_station": "Valid Station"}
        }
        response = client.post("/api/v1/cases", json=payload, headers=auth_headers_io1)
        assert response.status_code == status.HTTP_201_CREATED

    def test_forged_jwt_fails(self):
        """Forged JWT (signed with wrong key) fails OIDC validation."""
        correct_key = generate_rsa_keypair()
        wrong_key = generate_rsa_keypair()

        service = OIDCAuthenticationService(
            issuer_url="https://idp.example.com",
            audience="sakshi",
            algorithms=["RS256"],
        )
        # Load CORRECT public key into cache
        service._discovery_cache._jwks = create_test_jwks(correct_key)
        service._discovery_cache._jwks_fetched_at = time.time()

        # Sign token with WRONG private key
        now = int(time.time())
        claims = {
            "sub": "forged-user",
            "iss": "https://idp.example.com",
            "aud": "sakshi",
            "iat": now,
            "exp": now + 3600,
            "nbf": now,
        }
        forged_token = create_test_jwt(wrong_key, claims)

        with pytest.raises(InvalidTokenException):
            service.authenticate_request(auth_header=f"Bearer {forged_token}")

    def test_unsigned_token_fails(self):
        """Unsigned / alg:none tokens must fail."""
        service = OIDCAuthenticationService(
            issuer_url="https://idp.example.com",
            audience="sakshi",
            algorithms=["RS256"],
        )
        key = generate_rsa_keypair()
        service._discovery_cache._jwks = create_test_jwks(key)
        service._discovery_cache._jwks_fetched_at = time.time()

        # Create a "none" algorithm token (manual construction)
        import base64
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "none", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(
            json.dumps({
                "sub": "unsigned-user",
                "iss": "https://idp.example.com",
                "aud": "sakshi",
                "iat": int(time.time()),
                "exp": int(time.time()) + 3600,
            }).encode()
        ).rstrip(b"=").decode()
        unsigned_token = f"{header}.{payload}."

        with pytest.raises(InvalidTokenException):
            service.authenticate_request(auth_header=f"Bearer {unsigned_token}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: OIDC Discovery Cache
# ═══════════════════════════════════════════════════════════════════════════

class TestOIDCDiscoveryCache:
    """Tests for JWKS cache behavior."""

    def test_cache_returns_cached_jwks(self):
        """JWKS cache returns cached data without re-fetching."""
        cache = OIDCDiscoveryCache("https://idp.example.com", cache_ttl=3600)
        fake_jwks = {"keys": [{"kty": "RSA", "kid": "test"}]}
        cache._jwks = fake_jwks
        cache._jwks_fetched_at = time.time()

        result = cache.get_jwks("https://idp.example.com/jwks")
        assert result == fake_jwks

    def test_cache_invalidation(self):
        """Cache invalidation forces re-fetch."""
        cache = OIDCDiscoveryCache("https://idp.example.com", cache_ttl=3600)
        cache._jwks = {"keys": []}
        cache._jwks_fetched_at = time.time()
        cache.invalidate()
        assert cache._jwks is None
        assert cache._jwks_fetched_at == 0
