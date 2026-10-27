"""
Regression test suite proving that automated test runs do not populate or pollute
the development Case Directory or modify the preserved Riverside Guesthouse case.
"""
import pytest
from sqlalchemy import text
from app.core.config import settings
from app.db.session import engine
from app.services.case_service import CaseService
from app.schemas.case import CaseCreateRequest, FIRMetadata
from app.core.security import AuthenticatedInvestigator
from app.repositories.case_repository import CaseRepository


PRESERVED_CASE_ID = "SAKSHI-CASE-2026-C5A64E99"
PRESERVED_EVIDENCE_ID = "SAKSHI-EVID-2026-54C01EA8"


def test_startup_seed_disabled_by_default():
    """Verify that startup fixture seeding is disabled by default in normal development."""
    assert hasattr(settings, "ENABLE_STARTUP_SEED")
    assert settings.ENABLE_STARTUP_SEED is False, (
        "ENABLE_STARTUP_SEED must default to False to prevent automated startup routines from polluting the Case Directory"
    )


def test_test_suite_uses_isolated_test_database():
    """Verify that test fixtures use a dedicated test database distinct from production/development."""
    from tests.conftest import TEST_DATABASE_URL
    assert TEST_DATABASE_URL is not None
    # Must either be in-memory SQLite or an explicit test-designated URL
    assert (
        TEST_DATABASE_URL.startswith("sqlite:///:memory:") or
        "test" in TEST_DATABASE_URL.lower()
    )


def test_case_creation_in_test_session_does_not_leak_to_development_database(db_session):
    """
    Proves that creating cases in automated test sessions persists strictly inside the test fixture
    and NEVER populates the active development database engine or pollutes the Case Directory.
    """
    mock_io = AuthenticatedInvestigator(
        subject_id="IO-ISO-TEST-001",
        investigator_id="IO-ISO-TEST-001",
        full_name="Isolation Test Officer",
        role="INVESTIGATING_OFFICER",
        jurisdiction="KERALA",
        station="Cantonment Police Station"
    )

    test_fir_number = "FIR-ISOLATION-REGRESSION-9999"
    payload = CaseCreateRequest(
        title="Ephemeral Test Case - Directory Isolation Regression",
        fir_metadata=FIRMetadata(
            fir_number=test_fir_number,
            police_station="Cantonment Police Station",
            incident_date="2026-10-26T00:00:00Z",
            report_date="2026-10-26T01:00:00Z",
            jurisdiction_code="KERALA"
        )
    )

    # Create case via CaseService using test fixture db_session
    service = CaseService(db_session)
    created = service.create_case(payload, mock_io)
    created_case_id = created.case_id

    # 1. Assert created case exists in test db_session
    repo_test = CaseRepository(db_session)
    assert repo_test.get_by_case_id(created_case_id) is not None

    # 2. Assert created case does NOT exist in the active development database engine
    with engine.connect() as dev_conn:
        leaked = dev_conn.execute(
            text("SELECT case_id FROM cases WHERE case_id = :cid OR fir_metadata->>'fir_number' = :fir"),
            {"cid": created_case_id, "fir": test_fir_number}
        ).fetchone()
        assert leaked is None, (
            f"CRITICAL FAILURE: Test case {created_case_id} leaked into active development database!"
        )


def test_preserved_case_remains_intact_and_isolated():
    """
    Verifies that the preserved Riverside Guesthouse case and evidence are intact, unpolluted,
    and have not been altered by test executions.
    """
    with engine.connect() as dev_conn:
        # Check preserved case
        pres_case = dev_conn.execute(
            text("SELECT case_id, title, status FROM cases WHERE case_id = :cid"),
            {"cid": PRESERVED_CASE_ID}
        ).fetchone()
        assert pres_case is not None, f"Preserved case {PRESERVED_CASE_ID} missing from development database!"
        assert "Riverside Guesthouse Incident" in pres_case[1]

        # Check preserved evidence
        pres_ev = dev_conn.execute(
            text("SELECT evidence_id, case_id, original_file_name, status, integrity_status FROM evidence WHERE evidence_id = :eid"),
            {"eid": PRESERVED_EVIDENCE_ID}
        ).fetchone()
        assert pres_ev is not None, f"Preserved evidence {PRESERVED_EVIDENCE_ID} missing!"
        assert pres_ev[1] == PRESERVED_CASE_ID
        assert pres_ev[2] == "E00_synthetic_FIR.pdf"
        assert pres_ev[3] == "COMMITTED"
        assert pres_ev[4] == "VERIFIED"

        # Check that the preserved case exists in the Case Directory
        all_cases = dev_conn.execute(text("SELECT case_id FROM cases")).fetchall()
        assert any(c[0] == PRESERVED_CASE_ID for c in all_cases), (
            f"Expected preserved case {PRESERVED_CASE_ID} in development Case Directory, found {[c[0] for c in all_cases]}"
        )
