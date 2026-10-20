"""
Unit tests for database configuration, engine creation, dialect detection, and verification utilities.
Validates Phase 1: PostgreSQL + pgvector preparation without breaking SQLite test compatibility.
"""
import pytest
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

from app.core.config import Settings
from app.db.session import create_db_engine
from app.db.verify_connection import redact_db_url, verify_database_connection


def test_settings_sqlite_defaults(monkeypatch):
    """Verify default Settings selects SQLite and default connection pool values."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    s = Settings(_env_file=None)
    assert s.is_sqlite is True
    assert s.is_postgres is False
    assert s.DATABASE_URL.startswith("sqlite")
    assert s.DB_POOL_SIZE == 5
    assert s.DB_MAX_OVERFLOW == 10
    assert s.DB_POOL_TIMEOUT == 30
    assert s.DB_CONNECT_TIMEOUT == 10
    assert s.DB_POOL_PRE_PING is True


def test_settings_postgres_detection():
    """Verify Settings accurately identifies PostgreSQL connection strings."""
    s = Settings(DATABASE_URL="postgresql+psycopg://user:pass@localhost:5432/sakshi")
    assert s.is_postgres is True
    assert s.is_sqlite is False

    s2 = Settings(DATABASE_URL="postgresql://user:pass@localhost:5432/sakshi")
    assert s2.is_postgres is True
    assert s2.is_sqlite is False


def test_redact_db_url():
    """Ensure sensitive credentials in connection URLs are masked."""
    masked = redact_db_url("postgresql+psycopg://investigator_user:super_secret_pw@10.0.0.5:5432/sakshi_db")
    assert "super_secret_pw" not in masked
    assert "********" in masked
    assert "investigator_user" in masked
    assert "10.0.0.5:5432/sakshi_db" in masked

    # SQLite URL without credentials is unchanged
    assert redact_db_url("sqlite:///./sakshi_cases.db") == "sqlite:///./sakshi_cases.db"
    assert redact_db_url("") == ""


def test_create_db_engine_sqlite():
    """Verify SQLite engine creation configures check_same_thread=False."""
    engine = create_db_engine("sqlite:///:memory:")
    assert engine.dialect.name == "sqlite"
    engine.dispose()


def test_create_db_engine_postgres_kwargs():
    """Verify PostgreSQL engine creation configures pool and connection arguments."""
    engine = create_db_engine("postgresql+psycopg://mock_user:mock_pass@127.0.0.1:5432/mock_db")
    assert engine.dialect.name == "postgresql"
    # Pool settings are applied
    assert engine.pool.size() == 5
    assert engine.pool._max_overflow == 10
    engine.dispose()


def test_verify_database_connection_sqlite():
    """Verify connection probe against local SQLite database succeeds."""
    result = verify_database_connection("sqlite:///:memory:")
    assert result["status"] == "connected"
    assert result["dialect"] == "sqlite"
    assert "SQLite" in result["server_version"]
    assert result["pgvector_ready"] is False
    assert "SQLite is configured for local development" in result["recommendation"]


def test_verify_database_connection_unreachable_postgres():
    """Verify connection probe against offline PostgreSQL fails gracefully with sanitized error."""
    fake_url = "postgresql+psycopg://mock_officer:unexposed_password@127.0.0.1:5432/sakshi_cases"
    result = verify_database_connection(fake_url, timeout_seconds=2)
    assert result["status"] == "connection_failed"
    assert result["dialect"] == "postgresql"
    assert "unexposed_password" not in result["database_url"]
    assert "********" in result["database_url"]
    assert result["pgvector_ready"] is False
    assert "Ensure PostgreSQL service is active" in result["recommendation"]


def test_pgvector_import_and_sqlalchemy_model():
    """Verify pgvector.sqlalchemy Vector type can be imported and declared on a model without error."""
    from pgvector.sqlalchemy import Vector

    TestBase = declarative_base()

    class MockExhibitChunk(TestBase):
        __tablename__ = "mock_chunk_test"
        id = Column(Integer, primary_key=True)
        content = Column(String(255))
        embedding = Column(Vector(768))

    # Assert model attribute is declared with Vector type
    assert isinstance(MockExhibitChunk.embedding.type, Vector)
    assert MockExhibitChunk.embedding.type.dim == 768
