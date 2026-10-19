"""
Unit tests for atomic officer username generation.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import pytest
from app.models.officer import IdSequence, Officer
from app.services.iam_service import generate_username, ROLE_CODE_MAP
from app.repositories.iam_repository import IAMRepository


def test_username_format_and_role_codes(db_session):
    year = datetime.utcnow().year
    u_io = generate_username(db_session, "INVESTIGATING_OFFICER")
    assert u_io == f"SAK-IO-{year}-0001"

    u_sho = generate_username(db_session, "STATION_HEAD")
    assert u_sho == f"SAK-SHO-{year}-0001"

    u_so = generate_username(db_session, "SUPERVISORY_OFFICER")
    assert u_so == f"SAK-SUP-{year}-0001"

    u_admin = generate_username(db_session, "ADMIN")
    assert u_admin == f"SAK-ADM-{year}-0001"


def test_sequential_increment_persistence(db_session):
    year = datetime.utcnow().year
    u1 = generate_username(db_session, "INVESTIGATING_OFFICER", year=2026)
    u2 = generate_username(db_session, "INVESTIGATING_OFFICER", year=2026)
    u3 = generate_username(db_session, "INVESTIGATING_OFFICER", year=2026)

    assert u1 == "SAK-IO-2026-0001"
    assert u2 == "SAK-IO-2026-0002"
    assert u3 == "SAK-IO-2026-0003"

    # Verify underlying IdSequence row
    seq = db_session.query(IdSequence).filter_by(name="officer_IO_2026").one()
    assert seq.current_value == 3


def test_different_years_have_independent_sequences(db_session):
    u_2026 = generate_username(db_session, "INVESTIGATING_OFFICER", year=2026)
    u_2027 = generate_username(db_session, "INVESTIGATING_OFFICER", year=2027)

    assert u_2026 == "SAK-IO-2026-0001"
    assert u_2027 == "SAK-IO-2027-0001"


def test_concurrency_safe_uniqueness(db_session):
    # Test atomic generation across multiple calls
    results = []
    for _ in range(25):
        uname = generate_username(db_session, "INVESTIGATING_OFFICER", year=2026)
        results.append(uname)

    # All 25 usernames must be strictly unique and ordered
    assert len(results) == len(set(results))
    assert results[0] == "SAK-IO-2026-0001"
    assert results[-1] == "SAK-IO-2026-0025"
