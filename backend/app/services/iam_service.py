"""Transactional officer lifecycle and assignment services."""
import re
import secrets
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import (
    ForbiddenException,
    InvalidInvestigatorException,
    CaseNotFoundException,
)
from app.core.security import AuthenticatedInvestigator
from app.models.officer import Officer
from app.models.case_assignment import CaseAssignment
from app.models.case import Case
from app.repositories.case_repository import CaseRepository
from app.repositories.iam_repository import IAMRepository
from app.services.audit_integration import AuditIntegrationService
from app.services.firebase_auth_service import deterministic_firebase_identifier

MOBILE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
INVESTIGATOR_ROLES = {"INVESTIGATING_OFFICER"}
SUPERVISORY_ROLES = {"SUPERVISORY_OFFICER", "STATION_HEAD", "ADMIN", "SYSTEM_ADMIN"}
MANAGEMENT_ROLES = {"STATION_HEAD", "ADMIN", "SYSTEM_ADMIN"}

ROLE_CODE_MAP = {
    "INVESTIGATING_OFFICER": "IO",
    "SUPERVISORY_OFFICER": "SUP",
    "STATION_HEAD": "SHO",
    "ADMIN": "ADM",
    "SYSTEM_ADMIN": "ADM",
}


def normalize_mobile(value: str) -> str:
    """Normalize phone number to strict E.164 format."""
    value = re.sub(r"[\s().-]", "", value or "")
    if not value.startswith("+"):
        value = "+" + value
    if not MOBILE_RE.fullmatch(value):
        raise InvalidInvestigatorException("Mobile number must be a valid E.164 number (e.g. +919876543210).")
    return value


def get_role_code(role: str) -> str:
    return ROLE_CODE_MAP.get(role.upper(), role[:3].upper())


def generate_username(db: Session, role: str, year: Optional[int] = None) -> str:
    """
    Generate unique, immutable, concurrency-safe username.
    Format: SAK-<ROLE>-<YEAR>-<SEQUENCE:04d> (e.g. SAK-IO-2026-0042)
    Uses a database-backed sequence table with retry fallback to eliminate race conditions.
    """
    role_code = get_role_code(role)
    yr = year or datetime.now(timezone.utc).year
    seq_name = f"officer_{role_code}_{yr}"
    repo = IAMRepository(db)

    for _ in range(50):
        val = repo.next_sequence(seq_name)
        candidate = f"SAK-{role_code}-{yr}-{val:04d}"
        if not repo.officer_by_username(candidate):
            return candidate

    # High-entropy fallback if sequence counter collides with manual records
    return f"SAK-{role_code}-{yr}-{secrets.token_hex(4).upper()}"


def is_admin_or_manager(actor: AuthenticatedInvestigator) -> bool:
    actor_roles = set(actor.roles or [actor.role])
    return bool(actor_roles & MANAGEMENT_ROLES)


def is_supervisory(actor: AuthenticatedInvestigator) -> bool:
    actor_roles = set(actor.roles or [actor.role])
    return bool(actor_roles & SUPERVISORY_ROLES)


class OfficerService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = IAMRepository(db)

    @staticmethod
    def officer_id() -> str:
        return f"SAK-OFC-{secrets.token_hex(8).upper()}"

    def create(self, payload, actor: AuthenticatedInvestigator, provisioner=None) -> Officer:
        if not is_admin_or_manager(actor):
            raise ForbiddenException("Only administrators and station heads may onboard officers.")

        mobile = normalize_mobile(payload.mobile_number)
        if self.repo.officer_by_mobile(mobile):
            raise InvalidInvestigatorException("An officer is already registered for this mobile number.")

        org = self.repo.organization(payload.organization_id)
        jurisdiction = self.repo.jurisdiction(payload.jurisdiction_id)
        station = self.repo.station(payload.station_id)

        if not org or not jurisdiction or not station:
            raise InvalidInvestigatorException("Organization, jurisdiction, or station does not exist.")

        if station.organization_id != org.organization_id or station.jurisdiction_id != jurisdiction.jurisdiction_id:
            raise InvalidInvestigatorException("Station does not belong to the selected organization and jurisdiction.")

        # Station Head scope validation
        actor_roles = set(actor.roles or [actor.role])
        if "STATION_HEAD" in actor_roles and "ADMIN" not in actor_roles and "SYSTEM_ADMIN" not in actor_roles:
            if actor.station_jurisdiction not in {"ALL", jurisdiction.jurisdiction_id}:
                raise ForbiddenException("Station heads may only onboard officers within their authorized jurisdiction.")

        # Deterministic internal Firebase identifier (never exposed externally)
        identifier = deterministic_firebase_identifier(mobile)
        firebase_uid = None

        if provisioner is not None:
            firebase_uid = provisioner.create_user(
                identifier,
                payload.initial_password,
                disabled=not payload.mobile_verified,
            )

        username = generate_username(self.db, payload.role)
        officer = Officer(
            officer_id=self.officer_id(),
            firebase_uid=firebase_uid,
            firebase_login_identifier=identifier,
            full_name=payload.full_name.strip(),
            mobile_e164=mobile,
            username=username,
            service_identifier=payload.service_identifier,
            role=payload.role,
            organization_id=org.organization_id,
            station_id=station.station_id,
            jurisdiction_id=jurisdiction.jurisdiction_id,
            status="ACTIVE" if payload.mobile_verified and firebase_uid else "PENDING",
            mobile_verified=payload.mobile_verified,
            created_by=actor.subject_id,
            updated_by=actor.subject_id,
        )

        try:
            self.db.add(officer)
            self.db.commit()
            self.db.refresh(officer)
        except IntegrityError as exc:
            self.db.rollback()
            # Compensation: revoke / disable external identity if DB commit failed
            if firebase_uid and provisioner:
                provisioner.disable_user(firebase_uid)
            raise InvalidInvestigatorException("Officer identity conflicts with an existing record.") from exc

        # Auditing
        AuditIntegrationService.record_event(
            "OFFICER_CREATED",
            actor.subject_id,
            "IAM",
            {"officer_id": officer.officer_id, "status": officer.status, "scope": officer.jurisdiction_id}
        )
        AuditIntegrationService.record_event(
            "USERNAME_ISSUED",
            actor.subject_id,
            "IAM",
            {"officer_id": officer.officer_id, "username": officer.username}
        )
        return officer

    def get(self, officer_id: str, actor: AuthenticatedInvestigator) -> Officer:
        officer = self.repo.officer(officer_id)
        if not officer:
            raise InvalidInvestigatorException(f"Officer '{officer_id}' not found.")
        # Scope validation for non-admin
        actor_roles = set(actor.roles or [actor.role])
        if not (actor_roles & {"ADMIN", "SYSTEM_ADMIN"}):
            if actor.station_jurisdiction not in {None, "ALL", officer.jurisdiction_id}:
                raise ForbiddenException("Cross-jurisdiction officer access is denied.")
        return officer

    def list_officers(
        self,
        actor: AuthenticatedInvestigator,
        jurisdiction_id: Optional[str] = None,
        station_id: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
        active_only: bool = False,
    ) -> List[Officer]:
        actor_roles = set(actor.roles or [actor.role])
        if not (actor_roles & {"ADMIN", "SYSTEM_ADMIN"}):
            # Restrict to actor's jurisdiction
            if actor.station_jurisdiction and actor.station_jurisdiction != "ALL":
                if jurisdiction_id and jurisdiction_id != actor.station_jurisdiction:
                    raise ForbiddenException("Access to officers in other jurisdictions is denied.")
                jurisdiction_id = actor.station_jurisdiction

        return self.repo.officers(
            jurisdiction_id=jurisdiction_id,
            station_id=station_id,
            role=role,
            status=status,
            active_only=active_only,
        )

    def change_status(
        self,
        officer_id: str,
        status: str,
        actor: AuthenticatedInvestigator,
        provisioner=None
    ) -> Officer:
        if not is_admin_or_manager(actor):
            raise ForbiddenException("Only administrators and station heads may modify officer status.")

        officer = self.repo.officer(officer_id)
        if not officer:
            raise InvalidInvestigatorException(f"Officer '{officer_id}' not found.")

        # Scope validation
        actor_roles = set(actor.roles or [actor.role])
        if not (actor_roles & {"ADMIN", "SYSTEM_ADMIN"}):
            if actor.station_jurisdiction not in {"ALL", officer.jurisdiction_id}:
                raise ForbiddenException("Cannot modify officer outside your jurisdiction.")

        old_status = officer.status
        officer.status = status
        officer.updated_by = actor.subject_id

        if status in {"SUSPENDED", "DEACTIVATED", "INACTIVE"}:
            officer.deactivated_by = actor.subject_id
            officer.deactivated_at = datetime.now(timezone.utc)
            if officer.firebase_uid and provisioner:
                provisioner.disable_user(officer.firebase_uid)
            # Log audit event for open cases requiring reassignment
            active_cases = self.db.query(Case).filter_by(assigned_io_id=officer.officer_id, status="ACTIVE").all()
            if active_cases:
                AuditIntegrationService.record_event(
                    "OFFICER_DEACTIVATED_OPEN_CASES_FLAGGED",
                    actor.subject_id,
                    "IAM",
                    {
                        "officer_id": officer.officer_id,
                        "open_case_count": len(active_cases),
                        "cases": [c.case_id for c in active_cases],
                    }
                )
        elif status == "ACTIVE":
            officer.deactivated_by = None
            officer.deactivated_at = None
            if officer.firebase_uid and provisioner:
                provisioner.enable_user(officer.firebase_uid)

        self.db.commit()
        self.db.refresh(officer)

        AuditIntegrationService.record_event(
            "OFFICER_STATUS_CHANGED",
            actor.subject_id,
            "IAM",
            {"officer_id": officer_id, "previous_status": old_status, "new_status": status}
        )
        return officer

    def transfer(
        self,
        officer_id: str,
        target_station_id: str,
        target_jurisdiction_id: str,
        reason: str,
        actor: AuthenticatedInvestigator,
    ) -> Officer:
        if not is_admin_or_manager(actor):
            raise ForbiddenException("Only administrators and station heads may transfer officers.")

        officer = self.repo.officer(officer_id)
        if not officer:
            raise InvalidInvestigatorException(f"Officer '{officer_id}' not found.")

        target_station = self.repo.station(target_station_id)
        target_jurisdiction = self.repo.jurisdiction(target_jurisdiction_id)

        if not target_station or not target_jurisdiction:
            raise InvalidInvestigatorException("Target station or jurisdiction not found.")

        if target_station.jurisdiction_id != target_jurisdiction.jurisdiction_id:
            raise InvalidInvestigatorException("Target station does not belong to the target jurisdiction.")

        actor_roles = set(actor.roles or [actor.role])
        if not (actor_roles & {"ADMIN", "SYSTEM_ADMIN"}):
            if actor.station_jurisdiction not in {"ALL", target_jurisdiction_id}:
                raise ForbiddenException("Cannot transfer officer into an unauthorized jurisdiction.")

        previous_jurisdiction = officer.jurisdiction_id
        previous_station = officer.station_id

        officer.station_id = target_station.station_id
        officer.jurisdiction_id = target_jurisdiction.jurisdiction_id
        officer.updated_by = actor.subject_id

        # Flag any cases in the prior jurisdiction that require reassignment
        open_cases = self.db.query(Case).filter_by(assigned_io_id=officer.officer_id, status="ACTIVE").all()
        if open_cases:
            AuditIntegrationService.record_event(
                "OFFICER_TRANSFER_PENDING_CASE_REASSIGNMENT",
                actor.subject_id,
                "IAM",
                {
                    "officer_id": officer.officer_id,
                    "previous_jurisdiction": previous_jurisdiction,
                    "open_cases": [c.case_id for c in open_cases],
                }
            )

        self.db.commit()
        self.db.refresh(officer)

        AuditIntegrationService.record_event(
            "OFFICER_TRANSFERRED",
            actor.subject_id,
            "IAM",
            {
                "officer_id": officer_id,
                "from_station": previous_station,
                "to_station": target_station.station_id,
                "from_jurisdiction": previous_jurisdiction,
                "to_jurisdiction": target_jurisdiction.jurisdiction_id,
                "reason": reason,
            }
        )
        return officer

    def reset_password(
        self,
        officer_id: str,
        new_password: str,
        actor: AuthenticatedInvestigator,
        provisioner=None,
    ) -> None:
        if not is_admin_or_manager(actor):
            raise ForbiddenException("Only administrators may reset officer passwords.")

        officer = self.repo.officer(officer_id)
        if not officer:
            raise InvalidInvestigatorException(f"Officer '{officer_id}' not found.")

        if not officer.firebase_uid:
            raise InvalidInvestigatorException("Officer does not have a linked identity provider account.")

        if provisioner:
            provisioner.set_user_password(officer.firebase_uid, new_password)

        AuditIntegrationService.record_event(
            "OFFICER_PASSWORD_RESET",
            actor.subject_id,
            "IAM",
            {"officer_id": officer_id}
        )

    def update(self, officer_id: str, payload, actor: AuthenticatedInvestigator) -> Officer:
        if not is_admin_or_manager(actor):
            raise ForbiddenException("Only administrators and station heads may update officer profiles.")

        officer = self.repo.officer(officer_id)
        if not officer:
            raise InvalidInvestigatorException(f"Officer '{officer_id}' not found.")

        if payload.role:
            officer.role = payload.role
        if payload.station_id:
            stn = self.repo.station(payload.station_id)
            if not stn:
                raise InvalidInvestigatorException("Station not found.")
            officer.station_id = stn.station_id
        if payload.jurisdiction_id:
            jur = self.repo.jurisdiction(payload.jurisdiction_id)
            if not jur:
                raise InvalidInvestigatorException("Jurisdiction not found.")
            officer.jurisdiction_id = jur.jurisdiction_id
        if payload.mobile_verified is not None:
            officer.mobile_verified = payload.mobile_verified

        officer.updated_by = actor.subject_id
        self.db.commit()
        self.db.refresh(officer)

        AuditIntegrationService.record_event(
            "OFFICER_UPDATED",
            actor.subject_id,
            "IAM",
            {"officer_id": officer_id}
        )
        return officer


class CaseAssignmentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = IAMRepository(db)
        self.cases = CaseRepository(db)

    def assign(
        self,
        case_id: str,
        officer_id: str,
        reason: str,
        actor: AuthenticatedInvestigator,
    ) -> CaseAssignment:
        case = self.cases.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        if not is_supervisory(actor):
            raise ForbiddenException("Only supervisory officers or administrators may assign cases.")

        officer = self.repo.officer(officer_id)
        if not officer:
            raise InvalidInvestigatorException(f"Officer '{officer_id}' not found.")

        if officer.status != "ACTIVE":
            raise InvalidInvestigatorException(f"Officer is {officer.status.lower()} and cannot be assigned to cases.")

        if not officer.mobile_verified:
            raise InvalidInvestigatorException("Officer mobile number is not verified.")

        if officer.role not in INVESTIGATOR_ROLES:
            raise InvalidInvestigatorException("Cases may only be assigned to Investigating Officers.")

        # Validate case jurisdiction
        case_meta = case.fir_metadata or {}
        case_jurisdiction = case_meta.get("jurisdiction_code") or case_meta.get("police_station")
        if not case_jurisdiction:
            raise InvalidInvestigatorException("Case does not have an established jurisdiction in FIR metadata.")

        if officer.jurisdiction_id != case_jurisdiction:
            raise InvalidInvestigatorException(
                f"Officer jurisdiction '{officer.jurisdiction_id}' does not match case jurisdiction '{case_jurisdiction}'."
            )

        # Actor scope validation
        actor_scope = actor.station_jurisdiction
        if actor_scope not in {"ALL", case_jurisdiction}:
            raise ForbiddenException("You are not authorized to assign cases outside your jurisdiction scope.")

        previous = case.assigned_io_id

        # End any current active assignment
        for item in self.db.query(CaseAssignment).filter_by(case_id=case_id, status="ACTIVE").all():
            item.status = "REASSIGNED"
            item.ended_at = datetime.now(timezone.utc)

        # Update case assigned IO
        case.assigned_io_id = officer.officer_id

        # Create new active assignment
        assignment = CaseAssignment(
            assignment_id=f"SAK-ASSIGN-{secrets.token_hex(8).upper()}",
            case_id=case_id,
            officer_id=officer.officer_id,
            previous_officer_id=previous,
            assigned_by=actor.subject_id,
            reason=reason.strip(),
            status="ACTIVE",
            assigned_at=datetime.now(timezone.utc),
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)

        AuditIntegrationService.record_event(
            "CASE_REASSIGNED" if previous else "CASE_ASSIGNED",
            actor.subject_id,
            case_id,
            {
                "previous_officer_id": previous,
                "officer_id": officer.officer_id,
                "scope": case_jurisdiction,
                "reason": reason,
            }
        )
        return assignment

    def assignments(self, case_id: str) -> List[CaseAssignment]:
        return self.repo.assignments(case_id)

    def eligible_officers(self, case_id: str, actor: AuthenticatedInvestigator) -> List[Officer]:
        case = self.cases.get_by_case_id(case_id)
        if not case:
            raise CaseNotFoundException(case_id)

        case_meta = case.fir_metadata or {}
        case_jurisdiction = case_meta.get("jurisdiction_code") or case_meta.get("police_station")
        if not case_jurisdiction:
            return []

        return self.repo.eligible_officers_for_case(case_jurisdiction)
