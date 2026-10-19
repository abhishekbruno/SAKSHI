"""
Database connection and pgvector extension verification utility for SAKSHI.
Provides automated diagnostic probes for both SQLite (dev/test) and PostgreSQL + pgvector (production).

Can be imported programmatically or run via CLI:
    python -m app.db.verify_connection [optional_db_url]
"""
import sys
import re
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.core.config import settings
from app.db.session import create_db_engine


def redact_db_url(url: str) -> str:
    """Masks credentials in database connection URLs for safe logging and display."""
    if not url:
        return ""
    # Pattern matching scheme://user:password@host...
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:********@", url)


def verify_database_connection(
    db_url: Optional[str] = None,
    timeout_seconds: int = 5
) -> Dict[str, Any]:
    """
    Probes database connectivity and pgvector extension availability.

    Returns a structured dictionary containing:
    - status: 'connected' | 'connection_failed'
    - dialect: 'postgresql' | 'sqlite' | other
    - database_url: redacted connection URL
    - server_version: database version string
    - pgvector_ready: boolean indicating vector extension is installed and functioning
    - details: supplementary diagnostic facts
    - recommendation: guidance for configuration or missing prerequisites
    """
    target_url = db_url or settings.DATABASE_URL
    redacted_url = redact_db_url(target_url)

    engine_probe = None
    try:
        # Create single-use probe engine with fast timeout
        engine_kwargs: Dict[str, Any] = {"echo": False}
        if target_url.lower().startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            engine_kwargs["connect_args"] = {"connect_timeout": timeout_seconds}
            engine_kwargs["pool_pre_ping"] = False

        engine_probe = create_engine(target_url, **engine_kwargs)
        with engine_probe.connect() as conn:
            dialect_name = engine_probe.dialect.name

            if dialect_name == "postgresql":
                # 1. Fetch PostgreSQL version
                pg_version_row = conn.execute(text("SELECT version();")).fetchone()
                pg_version = pg_version_row[0] if pg_version_row else "Unknown"

                # 2. Check if vector extension is installed
                ext_query = conn.execute(
                    text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")
                ).fetchone()

                # 3. Check if vector extension is available in pg_available_extensions
                avail_query = conn.execute(
                    text("SELECT name, default_version FROM pg_available_extensions WHERE name = 'vector';")
                ).fetchone()

                pgvector_installed = ext_query is not None
                pgvector_available = avail_query is not None
                vector_math_working = False

                if pgvector_installed:
                    # Test basic vector operation
                    try:
                        test_vec = conn.execute(text("SELECT '[1,2,3]'::vector;")).scalar()
                        vector_math_working = test_vec is not None
                    except Exception as vec_err:
                        vector_math_working = False

                result = {
                    "status": "connected",
                    "dialect": "postgresql",
                    "database_url": redacted_url,
                    "server_version": pg_version,
                    "pgvector_ready": pgvector_installed and vector_math_working,
                    "pgvector_installed": pgvector_installed,
                    "pgvector_version": ext_query[1] if ext_query else None,
                    "pgvector_package_available": pgvector_available,
                    "vector_math_operational": vector_math_working,
                    "details": {
                        "extension_status": (
                            "INSTALLED_AND_FUNCTIONAL" if (pgvector_installed and vector_math_working)
                            else ("INSTALLED_BUT_FAILED_OPERATION" if pgvector_installed
                            else ("AVAILABLE_NOT_INSTALLED" if pgvector_available else "NOT_FOUND_ON_SERVER"))
                        )
                    }
                }

                if not pgvector_installed:
                    if pgvector_available:
                        result["recommendation"] = (
                            "pgvector is available on the PostgreSQL server but not enabled in this database. "
                            "Execute: CREATE EXTENSION IF NOT EXISTS vector;"
                        )
                    else:
                        result["recommendation"] = (
                            "pgvector extension binary is not installed on the PostgreSQL server. "
                            "Install postgresql-server-dev and pgvector before enabling."
                        )
                elif not vector_math_working:
                    result["recommendation"] = "pgvector is installed but vector type cast failed. Check extension integrity."
                else:
                    result["recommendation"] = "PostgreSQL and pgvector are fully operational for SAKSHI RAG."

                return result

            elif dialect_name == "sqlite":
                # Fetch SQLite version
                sqlite_version_row = conn.execute(text("SELECT sqlite_version();")).fetchone()
                sqlite_version = sqlite_version_row[0] if sqlite_version_row else "Unknown"

                # Check existing core tables
                tables_row = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('cases', 'evidence');")
                ).fetchall()
                found_tables = [r[0] for r in tables_row]

                return {
                    "status": "connected",
                    "dialect": "sqlite",
                    "database_url": redacted_url,
                    "server_version": f"SQLite {sqlite_version}",
                    "pgvector_ready": False,
                    "pgvector_installed": False,
                    "details": {
                        "mode": "development_or_testing",
                        "core_tables_present": found_tables,
                    },
                    "recommendation": (
                        "Active database is SQLite. SQLite is configured for local development and test suite execution. "
                        "To use PostgreSQL + pgvector for RAG in staging/production, configure DATABASE_URL in .env "
                        "(e.g., DATABASE_URL=postgresql+psycopg://sakshi_user:password@localhost:5432/sakshi_db)."
                    )
                }

            else:
                return {
                    "status": "connected",
                    "dialect": dialect_name,
                    "database_url": redacted_url,
                    "server_version": "Unknown dialect",
                    "pgvector_ready": False,
                    "recommendation": f"Dialect '{dialect_name}' is not officially supported for SAKSHI RAG."
                }

    except OperationalError as oe:
        # Expected when PostgreSQL is not running or credentials/host invalid
        return {
            "status": "connection_failed",
            "dialect": "postgresql" if "postgres" in target_url.lower() else "unknown",
            "database_url": redacted_url,
            "error_type": "OperationalError",
            "error_message": str(oe.orig) if hasattr(oe, "orig") else str(oe),
            "pgvector_ready": False,
            "recommendation": (
                "Could not connect to database server. Ensure PostgreSQL service is active, "
                "host and port are reachable, and DATABASE_URL credentials are correct."
            )
        }
    except SQLAlchemyError as se:
        return {
            "status": "connection_failed",
            "dialect": "postgresql" if "postgres" in target_url.lower() else "unknown",
            "database_url": redacted_url,
            "error_type": type(se).__name__,
            "error_message": str(se),
            "pgvector_ready": False,
            "recommendation": "Database connection failed. Check driver and connection string format."
        }
    except Exception as exc:
        return {
            "status": "connection_failed",
            "dialect": "unknown",
            "database_url": redacted_url,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "pgvector_ready": False,
            "recommendation": f"Unexpected error during connection probe: {str(exc)}"
        }
    finally:
        if engine_probe is not None:
            engine_probe.dispose()


def main():
    """CLI diagnostic entrypoint."""
    probe_url = sys.argv[1] if len(sys.argv) > 1 else None
    print("=" * 70)
    print("SAKSHI — Database & pgvector Diagnostic Verifier")
    print("=" * 70)

    result = verify_database_connection(probe_url)

    print(f"Status:        {result.get('status').upper()}")
    print(f"Dialect:       {result.get('dialect')}")
    print(f"Target URL:    {result.get('database_url')}")

    if result.get("status") == "connected":
        print(f"Server Ver:    {result.get('server_version')}")
        print(f"pgvector Ready:{result.get('pgvector_ready')}")
        if result.get("dialect") == "postgresql":
            print(f"pgvector Ext:  {result.get('pgvector_installed')} (v{result.get('pgvector_version')})")
            print(f"Vector Math:   {result.get('vector_math_operational')}")
        elif result.get("dialect") == "sqlite":
            tables = result.get("details", {}).get("core_tables_present", [])
            print(f"Core Tables:   {', '.join(tables) if tables else 'None yet (will initialize on startup)'}")
    else:
        print(f"Error Type:    {result.get('error_type')}")
        print(f"Error Message: {result.get('error_message')}")

    print("-" * 70)
    print(f"Guidance:\n{result.get('recommendation')}")
    print("=" * 70)

    if result.get("status") == "connected":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
