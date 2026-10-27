"""
Unit tests for individual case deletion and forensic archival (MOD-01 / MOD-03).
Verifies:
1. Authorized investigator can archive/delete their assigned case.
2. Unauthorized investigator cannot delete another officer's case (ABAC/RBAC).
3. Soft-delete / archival preserves forensic data, exhibits, and audit trail.
4. Active case register filters out archived cases.
5. Non-target cases remain present and untouched.
6. Idempotent repeated delete requests.
7. Non-existent case handling.
"""
import pytest
from app.services.case_service import CaseService
from app.schemas.case import CaseCreateRequest, FIRMetadata
from app.core.errors import CaseNotFoundException, ForbiddenException
from app.core.security import AuthenticatedInvestigator
from app.models.evidence import Evidence
from app.repositories.evidence_repository import EvidenceRepository


def test_authorized_assigned_io_can_delete_case(db_session, mock_io1):
    service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Inquiry for Archival Test",
        fir_metadata=FIRMetadata(fir_number="FIR-DEL-001", police_station="Station Alpha")
    )
    created = service.create_case(payload, mock_io1)
    case_id = created.case_id

    # Authorized deletion
    resp = service.delete_case(case_id, mock_io1, reason="Test inquiry completed and closed")
    assert resp.success is True
    assert resp.case_id == case_id
    assert resp.status == "ARCHIVED"

    # Verify case is removed from active listing
    active_cases, total = service.list_cases(mock_io1, include_archived=False)
    assert not any(c.case_id == case_id for c in active_cases)

    # Verify case record is preserved in database with ARCHIVED status
    archived_case = service.repo.get_by_case_id(case_id)
    assert archived_case is not None
    assert archived_case.status == "ARCHIVED"


def test_unauthorized_investigator_cannot_delete_case(db_session, mock_io1, mock_io2):
    service = CaseService(db_session)
    # IO1 creates a case
    payload = CaseCreateRequest(
        title="IO1 Protected Inquiry",
        fir_metadata=FIRMetadata(fir_number="FIR-DEL-002", police_station="Station Alpha")
    )
    created = service.create_case(payload, mock_io1)
    case_id = created.case_id

    # IO2 attempts to delete IO1's case -> Must be denied
    with pytest.raises(ForbiddenException):
        service.delete_case(case_id, mock_io2, reason="Unauthorized deletion attempt")

    # Invariant: Case must remain active and unchanged
    check_case = service.repo.get_by_case_id(case_id)
    assert check_case.status == "ACTIVE"


def test_single_case_isolation_and_preservation(db_session, mock_io1):
    service = CaseService(db_session)
    # Create Case A
    case_a = service.create_case(
        CaseCreateRequest(
            title="Case A - Target for Deletion",
            fir_metadata=FIRMetadata(fir_number="FIR-DEL-003A", police_station="Station Beta")
        ),
        mock_io1
    )
    # Create Case B
    case_b = service.create_case(
        CaseCreateRequest(
            title="Case B - Must Remain Untouched",
            fir_metadata=FIRMetadata(fir_number="FIR-DEL-003B", police_station="Station Beta")
        ),
        mock_io1
    )

    # Delete Case A
    service.delete_case(case_a.case_id, mock_io1)

    # Invariant: Case B remains ACTIVE, present in list, and untouched
    active_cases, _ = service.list_cases(mock_io1, include_archived=False)
    active_ids = [c.case_id for c in active_cases]
    assert case_a.case_id not in active_ids
    assert case_b.case_id in active_ids

    b_record = service.repo.get_by_case_id(case_b.case_id)
    assert b_record.status == "ACTIVE"
    assert b_record.title == "Case B - Must Remain Untouched"


def test_forensic_evidence_preservation_on_case_archival(db_session, mock_io1):
    service = CaseService(db_session)
    created = service.create_case(
        CaseCreateRequest(
            title="Case With Evidence Exhibits",
            fir_metadata=FIRMetadata(fir_number="FIR-DEL-004", police_station="Station Gamma")
        ),
        mock_io1
    )
    case_id = created.case_id

    # Add mock evidence exhibit
    ev_repo = EvidenceRepository(db_session)
    exhibit = Evidence(
        evidence_id="EXH-TEST-001",
        case_id=case_id,
        original_file_name="crime_scene_photo.jpg",
        stored_file_name="EXH-TEST-001.jpg",
        evidence_category="SCENE_PHOTO",
        declared_mime_type="image/jpeg",
        checksum_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        file_size_bytes=2048,
        status="COMMITTED",
        integrity_status="VERIFIED",
        raw_storage_path=f"/sakshi/evidence/{case_id}/EXH-TEST-001.jpg",
        submitting_investigator_id=mock_io1.investigator_id
    )
    db_session.add(exhibit)
    db_session.commit()

    # Delete / archive the case
    service.delete_case(case_id, mock_io1)

    # Forensic Invariant: Exhibit must still exist and retain intact hash and metadata
    saved_exhibit = ev_repo.get_by_evidence_id("EXH-TEST-001")
    assert saved_exhibit is not None
    assert saved_exhibit.checksum_sha256 == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert saved_exhibit.integrity_status == "VERIFIED"


def test_repeated_delete_is_idempotent(db_session, mock_io1):
    service = CaseService(db_session)
    created = service.create_case(
        CaseCreateRequest(
            title="Idempotency Test Case",
            fir_metadata=FIRMetadata(fir_number="FIR-DEL-005", police_station="Station Delta")
        ),
        mock_io1
    )
    case_id = created.case_id

    # First delete
    res1 = service.delete_case(case_id, mock_io1)
    assert res1.success is True
    assert res1.status == "ARCHIVED"

    # Second delete (repeated request) must not crash or error
    res2 = service.delete_case(case_id, mock_io1)
    assert res2.success is True
    assert res2.status == "ARCHIVED"
    assert "already archived" in res2.message.lower()


def test_delete_nonexistent_case_raises_404(db_session, mock_io1):
    service = CaseService(db_session)
    with pytest.raises(CaseNotFoundException):
        service.delete_case("SAKSHI-CASE-NONEXISTENT-9999", mock_io1)
