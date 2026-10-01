"""
Configuration management for SAKSHI Investigation Platform.
Phase 1: Case Initiation — MOD-01 Case Management + MOD-02 Identity/OIDC.

PROPOSED IMPLEMENTATION DECISION: Uses Pydantic BaseSettings for environment-driven configuration.
All OIDC / Identity settings are sourced from environment variables; no secrets are hardcoded.
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    PROJECT_NAME: str = "SAKSHI Investigation Platform"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = Field(
        default="development",
        description="Environment: development, test, production"
    )

    # Database configuration
    # Default to local SQLite for development/testing; seamless override with PostgreSQL connection string
    DATABASE_URL: str = Field(
        default="sqlite:///./sakshi_cases.db",
        description="Database connection URL (PostgreSQL or SQLite)"
    )

    # CORS configuration
    CORS_ORIGINS: List[str] = ["*"]

    # ─── MOD-02: Identity / OIDC Configuration ───────────────────────────
    # AUTH_MODE controls authentication strategy:
    #   "development" — deterministic local dev identity, no real token validation
    #   "oidc"        — real OIDC provider with JWT signature verification
    AUTH_MODE: str = Field(
        default="development",
        description="Authentication mode: 'development' (mock identity) or 'oidc' (real provider)"
    )

    # OIDC Provider settings (required when AUTH_MODE=oidc)
    OIDC_ISSUER_URL: Optional[str] = Field(
        default=None,
        description="OIDC issuer URL, e.g. https://idp.example.com/realms/sakshi"
    )
    OIDC_AUDIENCE: Optional[str] = Field(
        default=None,
        description="Expected JWT audience claim (typically the SAKSHI client ID)"
    )
    OIDC_CLIENT_ID: Optional[str] = Field(
        default=None,
        description="OIDC client ID for the SAKSHI application"
    )
    OIDC_JWKS_URL: Optional[str] = Field(
        default=None,
        description="JWKS endpoint URL. If not set, derived from OIDC discovery."
    )
    OIDC_ALGORITHMS: List[str] = Field(
        default=["RS256"],
        description="Permitted JWT signing algorithms"
    )
    OIDC_DISCOVERY_ENABLED: bool = Field(
        default=True,
        description="Whether to use .well-known/openid-configuration discovery"
    )

    # JWKS cache TTL in seconds (avoids re-downloading keys on every request)
    OIDC_JWKS_CACHE_TTL: int = Field(
        default=3600,
        description="JWKS cache time-to-live in seconds"
    )

    # Development-mode identity defaults (only used when AUTH_MODE=development)
    DEV_INVESTIGATOR_SUBJECT_ID: str = Field(
        default="dev-investigator-001",
        description="Default subject_id for development-only authentication"
    )
    DEV_INVESTIGATOR_NAME: str = Field(
        default="Dev Inspector (Development Only)",
        description="Default display name for development-only authentication"
    )
    DEV_INVESTIGATOR_EMAIL: str = Field(
        default="dev.inspector@sakshi.local",
        description="Default email for development-only authentication"
    )

    # Legacy compat — preserved for backward compatibility with existing config references
    OIDC_ISSUER: Optional[str] = None
    DEV_AUTH_BYPASS: bool = Field(
        default=True,
        description="DEPRECATED: Use AUTH_MODE instead. Preserved for backward compatibility."
    )

    model_config = {
        "case_sensitive": True,
        "env_file": ".env"
    }

    @property
    def is_development_auth(self) -> bool:
        """Returns True when authentication is in development/mock mode."""
        return self.AUTH_MODE.lower() == "development"

    @property
    def is_oidc_auth(self) -> bool:
        """Returns True when real OIDC authentication is configured."""
        return self.AUTH_MODE.lower() == "oidc"


settings = Settings()
