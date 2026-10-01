"""
Pytest fixtures and configuration for SAKSHI test suite.
Uses an isolated in-memory SQLite database per test session.

Supports both MOD-01 (Case Management) and MOD-02 (Identity/OIDC) tests.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.core.security import AuthenticatedInvestigator

# Isolated in-memory SQLite for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ─── MOD-01/MOD-02 Compatible Auth Headers (Development Mode) ───────────
# These use X-Investigator-Id headers which are accepted in dev mode.

@pytest.fixture
def auth_headers_io1():
    return {
        "X-Investigator-Id": "IO-7842-SHARMA",
        "X-Investigator-Role": "INVESTIGATING_OFFICER",
        "X-Investigator-Jurisdiction": "JUR-DEL-04"
    }


@pytest.fixture
def auth_headers_io2():
    return {
        "X-Investigator-Id": "IO-9912-VERMA",
        "X-Investigator-Role": "INVESTIGATING_OFFICER",
        "X-Investigator-Jurisdiction": "JUR-DEL-05"
    }


@pytest.fixture
def auth_headers_supervisor():
    return {
        "X-Investigator-Id": "IO-0001-COMMISSIONER",
        "X-Investigator-Role": "SUPERVISORY_OFFICER",
        "X-Investigator-Jurisdiction": "ALL"
    }


# ─── MOD-01/MOD-02 Compatible Investigator Models ──────────────────────
# Updated to use subject_id (canonical) while preserving investigator_id alias.

@pytest.fixture
def mock_io1():
    return AuthenticatedInvestigator(
        subject_id="IO-7842-SHARMA",
        display_name="Inspector Sharma",
        name="Inspector Sharma",
        role="INVESTIGATING_OFFICER",
        station_jurisdiction="JUR-DEL-04",
        is_authenticated=True,
        authentication_method="development",
    )


@pytest.fixture
def mock_io2():
    return AuthenticatedInvestigator(
        subject_id="IO-9912-VERMA",
        display_name="Inspector Verma",
        name="Inspector Verma",
        role="INVESTIGATING_OFFICER",
        station_jurisdiction="JUR-DEL-05",
        is_authenticated=True,
        authentication_method="development",
    )


@pytest.fixture
def mock_supervisor():
    return AuthenticatedInvestigator(
        subject_id="IO-0001-COMMISSIONER",
        display_name="DCP Roy",
        name="DCP Roy",
        role="SUPERVISORY_OFFICER",
        station_jurisdiction="ALL",
        is_authenticated=True,
        authentication_method="development",
    )
