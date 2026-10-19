"""
Unit tests for FirebaseAuthenticationService and FirebaseAdminProvisioner.
"""
from unittest.mock import MagicMock, patch
import pytest
from app.core.errors import (
    AuthenticationRequiredException,
    InvalidTokenException,
    TokenExpiredException,
    ForbiddenException,
    InvalidInvestigatorException,
)
from app.models.officer import Officer
from app.models.organization import Organization, Jurisdiction, PoliceStation
from app.services.firebase_auth_service import (
    FirebaseAuthenticationService,
    FirebaseAdminProvisioner,
    FirebaseUnavailableException,
    deterministic_firebase_identifier,
)


def seed_test_officer(db, uid="fb-uid-101", status="ACTIVE", mobile="+919876543210", verified=True):
    org_id = f"ORG-{uid}"
    jur_id = f"JUR-{uid}"
    stn_id = f"STN-{uid}"
    org = Organization(organization_id=org_id, name="Test Police", code=f"TP-{uid[:4]}", created_by="ADMIN")
    jur = Jurisdiction(jurisdiction_id=jur_id, organization_id=org_id, name="Test Jur", code=f"TJ-{uid[:4]}", created_by="ADMIN")
    stn = PoliceStation(station_id=stn_id, organization_id=org_id, jurisdiction_id=jur_id, name="Test Stn", code=f"TS-{uid[:4]}", created_by="ADMIN")
    db.add_all([org, jur, stn])
    db.commit()

    officer = Officer(
        officer_id=f"OFF-{uid}",
        firebase_uid=uid,
        username=f"SAK-IO-2026-{uid[-4:]}",
        full_name="Inspector Test Officer",
        mobile_e164=mobile,
        firebase_login_identifier=deterministic_firebase_identifier(mobile),
        role="INVESTIGATING_OFFICER",
        status=status,
        mobile_verified=verified,
        organization_id=org_id,
        jurisdiction_id=jur_id,
        station_id=stn_id,
        created_by="ADMIN",
        updated_by="ADMIN",
    )
    db.add(officer)
    db.commit()
    return officer



def test_deterministic_firebase_identifier():
    id1 = deterministic_firebase_identifier("+91 98765-43210")
    id2 = deterministic_firebase_identifier("+919876543210")
    assert id1 == "officer.919876543210@firebase.sakshi.invalid"
    assert id2 == id1
    # Fallback on empty
    id3 = deterministic_firebase_identifier("")
    assert id3.endswith("@firebase.sakshi.invalid")


def test_missing_auth_header(db_session):
    svc = FirebaseAuthenticationService()
    with pytest.raises(AuthenticationRequiredException):
        svc.authenticate_request(None, db=db_session)
    with pytest.raises(AuthenticationRequiredException):
        svc.authenticate_request("", db=db_session)


def test_invalid_scheme(db_session):
    svc = FirebaseAuthenticationService()
    with pytest.raises(InvalidTokenException):
        svc.authenticate_request("Basic 12345", db=db_session)


def test_empty_bearer_token(db_session):
    svc = FirebaseAuthenticationService()
    with pytest.raises(AuthenticationRequiredException):
        svc.authenticate_request("Bearer ", db=db_session)


def test_valid_token_authenticates_officer(db_session):
    seed_test_officer(db_session, uid="fb-valid-uid")
    svc = FirebaseAuthenticationService()

    mock_auth = MagicMock()
    mock_auth.verify_id_token.return_value = {
        "uid": "fb-valid-uid",
        "iss": "https://securetoken.google.com/sakshi-test",
    }

    with patch.object(svc, "_admin_auth", return_value=mock_auth):
        investigator = svc.authenticate_request("Bearer valid.token.jwt", db=db_session)

    assert investigator.subject_id == "OFF-fb-valid-uid"
    assert investigator.username.startswith("SAK-IO-2026-")
    assert investigator.role == "INVESTIGATING_OFFICER"
    assert investigator.station_jurisdiction == "JUR-fb-valid-uid"
    assert investigator.authentication_method == "firebase"
    mock_auth.verify_id_token.assert_called_once_with("valid.token.jwt", check_revoked=True)


def test_expired_token_raises_token_expired(db_session):
    svc = FirebaseAuthenticationService()
    mock_auth = MagicMock()
    mock_auth.verify_id_token.side_effect = Exception("Firebase ID token has expired at timestamp 12345")

    with patch.object(svc, "_admin_auth", return_value=mock_auth):
        with pytest.raises(TokenExpiredException):
            svc.authenticate_request("Bearer expired.jwt", db=db_session)


def test_revoked_token_raises_invalid_token(db_session):
    svc = FirebaseAuthenticationService()
    mock_auth = MagicMock()
    mock_auth.verify_id_token.side_effect = Exception("Firebase ID token has been revoked")

    with patch.object(svc, "_admin_auth", return_value=mock_auth):
        with pytest.raises(InvalidTokenException):
            svc.authenticate_request("Bearer revoked.jwt", db=db_session)


def test_firebase_unavailable_raises_503(db_session):
    svc = FirebaseAuthenticationService()
    mock_auth = MagicMock()
    mock_auth.verify_id_token.side_effect = Exception("Failed to fetch public key certificates transport error")

    with patch.object(svc, "_admin_auth", return_value=mock_auth):
        with pytest.raises(FirebaseUnavailableException):
            svc.authenticate_request("Bearer cert.error.jwt", db=db_session)


def test_unlinked_firebase_identity_is_forbidden(db_session):
    # Valid Firebase token for UID that has no matching SAKSHI officer record
    svc = FirebaseAuthenticationService()
    mock_auth = MagicMock()
    mock_auth.verify_id_token.return_value = {"uid": "unregistered-uid"}

    with patch.object(svc, "_admin_auth", return_value=mock_auth):
        with pytest.raises(ForbiddenException) as exc_info:
            svc.authenticate_request("Bearer unlinked.jwt", db=db_session)
    assert "not authorized for SAKSHI" in str(exc_info.value.detail)


def test_deactivated_officer_denied_access(db_session):
    # Cryptographically valid token for an officer who has been deactivated
    seed_test_officer(db_session, uid="fb-deactivated-uid", status="INACTIVE")
    svc = FirebaseAuthenticationService()
    mock_auth = MagicMock()
    mock_auth.verify_id_token.return_value = {"uid": "fb-deactivated-uid"}

    with patch.object(svc, "_admin_auth", return_value=mock_auth):
        with pytest.raises(ForbiddenException) as exc_info:
            svc.authenticate_request("Bearer deactivated.jwt", db=db_session)
    assert "inactive" in str(exc_info.value.detail).lower()


def test_suspended_officer_denied_access(db_session):
    seed_test_officer(db_session, uid="fb-suspended-uid", status="SUSPENDED")
    svc = FirebaseAuthenticationService()
    mock_auth = MagicMock()
    mock_auth.verify_id_token.return_value = {"uid": "fb-suspended-uid"}

    with patch.object(svc, "_admin_auth", return_value=mock_auth):
        with pytest.raises(ForbiddenException) as exc_info:
            svc.authenticate_request("Bearer suspended.jwt", db=db_session)
    assert "suspended" in str(exc_info.value.detail).lower()


def test_unverified_mobile_officer_denied_access(db_session):
    seed_test_officer(db_session, uid="fb-unverified-uid", verified=False)
    svc = FirebaseAuthenticationService()
    mock_auth = MagicMock()
    mock_auth.verify_id_token.return_value = {"uid": "fb-unverified-uid"}

    with patch.object(svc, "_admin_auth", return_value=mock_auth):
        with pytest.raises(ForbiddenException) as exc_info:
            svc.authenticate_request("Bearer unverified.jwt", db=db_session)
    assert "verified" in str(exc_info.value.detail).lower()



def test_firebase_admin_provisioner():
    svc = FirebaseAuthenticationService()
    mock_auth = MagicMock()
    user_record = MagicMock()
    user_record.uid = "new-fb-uid-999"
    mock_auth.create_user.return_value = user_record

    with patch.object(svc, "_admin_auth", return_value=mock_auth):
        provisioner = FirebaseAdminProvisioner(svc)
        uid = provisioner.create_user("officer.999@firebase.sakshi.invalid", "StrongPass123!")
        assert uid == "new-fb-uid-999"
        mock_auth.create_user.assert_called_once_with(
            email="officer.999@firebase.sakshi.invalid",
            password="StrongPass123!",
            disabled=False
        )

        provisioner.disable_user("new-fb-uid-999")
        mock_auth.update_user.assert_called_with("new-fb-uid-999", disabled=True)
        mock_auth.revoke_refresh_tokens.assert_called_with("new-fb-uid-999")

        provisioner.enable_user("new-fb-uid-999")
        mock_auth.update_user.assert_called_with("new-fb-uid-999", disabled=False)

        provisioner.set_user_password("new-fb-uid-999", "NewStrongPass456!")
        mock_auth.update_user.assert_called_with("new-fb-uid-999", password="NewStrongPass456!")
