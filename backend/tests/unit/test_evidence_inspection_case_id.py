"""
Regression unit tests for SAKSHI Evidence Inspection & Case ID Propagation.

Verifies:
1. Evidence inspection succeeds with valid case_id and evidence_id without altering verification status.
2. Missing or null/undefined case_id raises CaseNotFoundException cleanly.
3. Missing or null/undefined evidence_id raises EvidenceNotFoundException cleanly.
4. Strict cross-case isolation: requesting evidence belonging to another case raises EvidenceNotFoundException.
5. Authorization policies: cross-jurisdiction investigator cannot inspect exhibits.
"""
import pytest
from app.services.case_service import CaseService
from app.services.evidence_intake_service import EvidenceIntakeService
from app.schemas.case import CaseCreateRequest, FIRMetadata
from app.schemas.evidence import (
    EvidenceCategory,
    EvidenceIntakeMetadata,
    EvidenceIntakeStatus,
)
from app.core.errors import (
    CaseNotFoundException,
    EvidenceNotFoundException,
    ForbiddenException,
)
from app.core.security import AuthenticatedInvestigator


@pytest.fixture
def test_case_setup(db_session, mock_io1, tmp_path):
    """Sets up an active case with registered evidence in EVIDENCE_INGESTION stage."""
    case_service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Riverside Guesthouse Inspection Verification",
        fir_metadata=FIRMetadata(
            fir_number="FIR-SYN-2026-REG-01",
            police_station="Central Police Station",
            incident_date="2026-10-18T01:50:00Z",
            jurisdiction_code="JUR-DEL-04"
        )
    )
    case_resp = case_service.create_case(payload, mock_io1)

    case_entity = case_service.repo.get_by_case_id(case_resp.case_id)
    case_entity.case_workspace_path = str(tmp_path / "case_workspace")
    case_service.repo.update(case_entity)

    # Advance stage to EVIDENCE_INGESTION
    case_service.update_stage(case_resp.case_id, "EVIDENCE_INGESTION", mock_io1)

    intake_service = EvidenceIntakeService(db_session)
    meta = EvidenceIntakeMetadata(
        evidence_category=EvidenceCategory.DOCUMENT_PDF,
        declared_mime_type="application/pdf",
        collection_location="MG Road Sector 4",
        source_device_or_person="Station Custody",
        description="Synthetic FIR document exhibit"
    )
    ev_resp = intake_service.register_evidence(
        case_id=case_resp.case_id,
        file_payload=b"%PDF-1.4 synthetic FIR file payload for testing",
        original_filename="E00_synthetic_FIR.pdf",
        metadata=meta,
        investigator=mock_io1,
    )

    return case_service.repo.get_by_case_id(case_resp.case_id), ev_resp


def test_evidence_inspection_valid_flow(db_session, test_case_setup, mock_io1):
    """Verifies that evidence inspection retrieves the correct record with exact IDs."""
    case, evidence = test_case_setup
    service = EvidenceIntakeService(db_session)

    result = service.get_evidence(
        case_id=case.case_id,
        evidence_id=evidence.evidence_id,
        investigator=mock_io1,
    )

    assert result.case_id == case.case_id
    assert result.evidence_id == evidence.evidence_id
    assert result.original_file_name == "E00_synthetic_FIR.pdf"
    assert result.status == EvidenceIntakeStatus.REGISTERED_INTAKE.value
    # Status and verification gates must NOT be modified or bypassed
    assert result.integrity_status == "UNVERIFIED"
    assert result.worm_status in (None, "")


@pytest.mark.parametrize("invalid_case_id", [None, "", "null", "undefined", "   "])
def test_evidence_inspection_rejects_invalid_or_null_case_id(db_session, test_case_setup, mock_io1, invalid_case_id):
    """Verifies that null, undefined, or blank case IDs are rejected with CaseNotFoundException."""
    _, evidence = test_case_setup
    service = EvidenceIntakeService(db_session)

    with pytest.raises(CaseNotFoundException) as exc_info:
        service.get_evidence(
            case_id=invalid_case_id,
            evidence_id=evidence.evidence_id,
            investigator=mock_io1,
        )
    assert "not found" in str(exc_info.value).lower()


@pytest.mark.parametrize("invalid_evidence_id", [None, "", "null", "undefined", "   "])
def test_evidence_inspection_rejects_invalid_or_null_evidence_id(db_session, test_case_setup, mock_io1, invalid_evidence_id):
    """Verifies that null, undefined, or blank evidence IDs are rejected with EvidenceNotFoundException."""
    case, _ = test_case_setup
    service = EvidenceIntakeService(db_session)

    with pytest.raises(EvidenceNotFoundException):
        service.get_evidence(
            case_id=case.case_id,
            evidence_id=invalid_evidence_id,
            investigator=mock_io1,
        )


def test_evidence_inspection_cross_case_isolation(db_session, test_case_setup, mock_io1, tmp_path):
    """Verifies that requesting an exhibit using a different case ID raises EvidenceNotFoundException."""
    case1, evidence1 = test_case_setup

    # Create second case
    case_service = CaseService(db_session)
    payload = CaseCreateRequest(
        title="Second Unrelated Case",
        fir_metadata=FIRMetadata(
            fir_number="FIR-SYN-2026-REG-02",
            police_station="Central Police Station",
            incident_date="2026-10-19T10:00:00Z",
            jurisdiction_code="JUR-DEL-04"
        )
    )
    case2_resp = case_service.create_case(payload, mock_io1)
    case2 = case_service.repo.get_by_case_id(case2_resp.case_id)
    case2.case_workspace_path = str(tmp_path / "case2_workspace")
    case_service.repo.update(case2)
    case_service.update_stage(case2_resp.case_id, "EVIDENCE_INGESTION", mock_io1)

    service = EvidenceIntakeService(db_session)

    # Attempting to access evidence1 through case2 must fail with EvidenceNotFoundException
    with pytest.raises(EvidenceNotFoundException):
        service.get_evidence(
            case_id=case2.case_id,
            evidence_id=evidence1.evidence_id,
            investigator=mock_io1,
        )


def test_evidence_inspection_authorization_enforced(db_session, test_case_setup):
    """Verifies that an unauthorized investigator from another jurisdiction cannot inspect evidence."""
    case, evidence = test_case_setup
    service = EvidenceIntakeService(db_session)

    unauthorized_investigator = AuthenticatedInvestigator(
        subject_id="IO-DELHI-999",
        role="INVESTIGATING_OFFICER",
        station_jurisdiction="JUR-MUMBAI-01",  # Different jurisdiction
    )

    with pytest.raises(ForbiddenException):
        service.get_evidence(
            case_id=case.case_id,
            evidence_id=evidence.evidence_id,
            investigator=unauthorized_investigator,
        )
