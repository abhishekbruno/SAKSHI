"""Database-only queries for IAM entities; callers enforce policy before mutation."""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.organization import Organization, Jurisdiction, PoliceStation
from app.models.officer import Officer, IdSequence
from app.models.case_assignment import CaseAssignment


class IAMRepository:
    def __init__(self, db: Session):
        self.db = db

    def organization(self, organization_id: str) -> Optional[Organization]:
        return self.db.query(Organization).filter_by(organization_id=organization_id, status="ACTIVE").first()

    def list_organizations(self) -> List[Organization]:
        return self.db.query(Organization).filter_by(status="ACTIVE").order_by(Organization.name).all()

    def jurisdiction(self, jurisdiction_id: str) -> Optional[Jurisdiction]:
        return self.db.query(Jurisdiction).filter_by(jurisdiction_id=jurisdiction_id, status="ACTIVE").first()

    def list_jurisdictions(self, organization_id: Optional[str] = None) -> List[Jurisdiction]:
        query = self.db.query(Jurisdiction).filter_by(status="ACTIVE")
        if organization_id:
            query = query.filter_by(organization_id=organization_id)
        return query.order_by(Jurisdiction.name).all()

    def station(self, station_id: str) -> Optional[PoliceStation]:
        return self.db.query(PoliceStation).filter_by(station_id=station_id, status="ACTIVE").first()

    def list_stations(self, jurisdiction_id: Optional[str] = None, organization_id: Optional[str] = None) -> List[PoliceStation]:
        query = self.db.query(PoliceStation).filter_by(status="ACTIVE")
        if jurisdiction_id:
            query = query.filter_by(jurisdiction_id=jurisdiction_id)
        if organization_id:
            query = query.filter_by(organization_id=organization_id)
        return query.order_by(PoliceStation.name).all()

    def officer(self, officer_id: str) -> Optional[Officer]:
        return self.db.query(Officer).filter_by(officer_id=officer_id).first()

    def officer_by_uid(self, firebase_uid: str) -> Optional[Officer]:
        return self.db.query(Officer).filter_by(firebase_uid=firebase_uid).first()

    def officer_by_mobile(self, mobile: str) -> Optional[Officer]:
        return self.db.query(Officer).filter_by(mobile_e164=mobile).first()

    def officer_by_username(self, username: str) -> Optional[Officer]:
        return self.db.query(Officer).filter_by(username=username).first()

    def officers(
        self,
        jurisdiction_id: Optional[str] = None,
        station_id: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
        active_only: bool = False,
    ) -> List[Officer]:
        query = self.db.query(Officer)
        if jurisdiction_id:
            query = query.filter(Officer.jurisdiction_id == jurisdiction_id)
        if station_id:
            query = query.filter(Officer.station_id == station_id)
        if role:
            query = query.filter(Officer.role == role)
        if status:
            query = query.filter(Officer.status == status)
        elif active_only:
            query = query.filter(Officer.status == "ACTIVE")
        return query.order_by(Officer.full_name).all()

    def eligible_officers_for_case(self, case_jurisdiction: str) -> List[Officer]:
        """Returns eligible active investigating officers for a case in the specified jurisdiction."""
        return (
            self.db.query(Officer)
            .filter(
                Officer.jurisdiction_id == case_jurisdiction,
                Officer.status == "ACTIVE",
                Officer.mobile_verified.is_(True),
                Officer.role == "INVESTIGATING_OFFICER",
            )
            .order_by(Officer.full_name)
            .all()
        )

    def assignments(self, case_id: str) -> List[CaseAssignment]:
        return self.db.query(CaseAssignment).filter(CaseAssignment.case_id == case_id).order_by(CaseAssignment.assigned_at.desc()).all()

    def active_assignment(self, case_id: str) -> Optional[CaseAssignment]:
        return self.db.query(CaseAssignment).filter_by(case_id=case_id, status="ACTIVE").first()

    def next_sequence(self, name: str) -> int:
        """Atomically get next value for a named sequence."""
        try:
            seq = self.db.query(IdSequence).filter_by(name=name).with_for_update().first()
        except Exception:
            # Fallback if dialect does not support with_for_update in current transaction
            seq = self.db.query(IdSequence).filter_by(name=name).first()

        if seq is None:
            seq = IdSequence(name=name, current_value=1)
            self.db.add(seq)
            self.db.flush()
            return 1
        else:
            seq.current_value += 1
            self.db.flush()
            return seq.current_value
