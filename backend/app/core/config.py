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

    # Dedicated test database URL for automated test runs (guarantees isolation)
    TEST_DATABASE_URL: Optional[str] = Field(
        default=None,
        description="Dedicated test database URL for automated test runs. If specified, automated tests use this isolated target."
    )

    # Startup seed gate: prevents creating test cases in normal development unless explicitly enabled
    ENABLE_STARTUP_SEED: bool = Field(
        default=False,
        description="Explicitly allow startup seed routines to create test cases in the database (default: False)"
    )

    # Database engine and connection pool configuration (used when connected to PostgreSQL)
    DB_POOL_SIZE: int = Field(
        default=5,
        description="Connection pool size for PostgreSQL"
    )
    DB_MAX_OVERFLOW: int = Field(
        default=10,
        description="Maximum overflow connections beyond pool size for PostgreSQL"
    )
    DB_POOL_TIMEOUT: int = Field(
        default=30,
        description="Connection pool timeout in seconds"
    )
    DB_CONNECT_TIMEOUT: int = Field(
        default=10,
        description="PostgreSQL TCP connection establishment timeout in seconds"
    )
    DB_POOL_PRE_PING: bool = Field(
        default=True,
        description="Enable connection liveness ping on checkout (prevents stale connections)"
    )
    DB_ECHO: bool = Field(
        default=False,
        description="Enable SQLAlchemy SQL query echo logging"
    )

    # ─── RAG & Vector Embedding Configuration (Phase 3) ──────────────────────
    # Selected Model: sentence-transformers/all-MiniLM-L6-v2
    # Output Dimension: 384 (verified)
    # License: Apache 2.0 | Architecture: 6-layer MiniLM | Offline-capable: Yes
    EMBEDDING_MODEL_NAME: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Authoritative embedding model identifier for SAKSHI RAG"
    )
    EMBEDDING_DIMENSION: int = Field(
        default=384,
        description="Verified output dimension for all-MiniLM-L6-v2 (384 dimensions)"
    )
    EMBEDDING_PROVIDER: str = Field(
        default="deterministic_mock",
        description="Active embedding provider: 'deterministic_mock' (test/dev/offline) or 'sentence_transformer' (production)"
    )

    # ─── RAG Chunking Configuration ──────────────────────────────────────────
    RAG_CHUNK_SIZE: int = Field(
        default=500,
        description="Target character length per evidence chunk (500 chars ~ 80-100 words)"
    )
    RAG_CHUNK_OVERLAP: int = Field(
        default=100,
        description="Character overlap between consecutive chunks to maintain semantic continuity"
    )
    RAG_MIN_CHUNK_LENGTH: int = Field(
        default=30,
        description="Minimum character length for an indexable chunk (discards blank/header noise)"
    )
    RAG_MAX_DOC_CHARS: int = Field(
        default=10_000_000,
        description="Maximum character limit for an extracted evidence document before throttling"
    )
    RAG_SEARCH_DEFAULT_LIMIT: int = Field(
        default=10,
        description="Default number of case-scoped evidence passages returned by retrieval"
    )
    RAG_SEARCH_MAX_LIMIT: int = Field(
        default=20,
        description="Hard upper bound for a single retrieval request"
    )
    RAG_SEARCH_MAX_QUERY_CHARS: int = Field(
        default=2_000,
        description="Maximum query length accepted by the retrieval API"
    )
    RAG_SQLITE_RETRIEVAL_CANDIDATE_LIMIT: int = Field(
        default=250,
        description="Bounded eligible-chunk candidate set used by the SQLite development fallback"
    )

    # CORS configuration
    CORS_ORIGINS: List[str] = ["*"]

    # ─── MOD-07: Antivirus Scanner Configuration ──────────────────────────
    # Explicit scanner selection: 'clamav' (production) or 'eicar_heuristic' (dev/testing).
    # Critical security rule: if 'clamav' is configured and unavailable, fail-closed.
    # No silent fallback to heuristic scanner.
    ANTIVIRUS_SCANNER: str = Field(
        default="eicar_heuristic",
        description="Active antivirus scanner: 'clamav' (production) or 'eicar_heuristic' (dev/testing)"
    )
    CLAMAV_HOST: str = Field(
        default="127.0.0.1",
        description="ClamAV daemon (clamd) host or IP"
    )
    CLAMAV_PORT: int = Field(
        default=3310,
        description="ClamAV daemon (clamd) TCP port"
    )
    CLAMAV_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        description="ClamAV scan timeout in seconds"
    )

    # ─── MOD-02: Identity / OIDC Configuration ───────────────────────────
    # AUTH_MODE controls authentication strategy:
    #   "development" — deterministic local dev identity, no real token validation
    #   "oidc"        — real OIDC provider with JWT signature verification
    #   "firebase"    — Firebase Admin ID-token verification + local officer registry
    AUTH_MODE: str = Field(
        default="development",
        description="Authentication mode: 'development', 'oidc', or 'firebase'"
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

    # Firebase Admin uses Application Default Credentials (or GOOGLE_APPLICATION_CREDENTIALS)
    # on the server. FIREBASE_WEB_API_KEY is only for the server-side password exchange;
    # it is never returned to the browser.
    FIREBASE_PROJECT_ID: Optional[str] = Field(default=None)
    FIREBASE_WEB_API_KEY: Optional[str] = Field(default=None)

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

    @property
    def is_firebase_auth(self) -> bool:
        return self.AUTH_MODE.lower() == "firebase"

    @property
    def is_sqlite(self) -> bool:
        """Returns True when the active database is SQLite."""
        return self.DATABASE_URL.lower().startswith("sqlite")

    @property
    def is_postgres(self) -> bool:
        """Returns True when the active database is PostgreSQL."""
        return self.DATABASE_URL.lower().startswith("postgres")


settings = Settings()
