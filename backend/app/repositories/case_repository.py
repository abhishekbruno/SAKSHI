"""
Repository layer for Case entities.
Encapsulates all database query logic, transaction boundaries, and isolation.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.case import Case


class CaseRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_case_id(self, case_id: str) -> Optional[Case]:
        """Fetch a case by its authoritative public Case ID."""
        return self.db.query(Case).filter(Case.case_id == case_id).first()

    def get_by_id(self, internal_id: str) -> Optional[Case]:
        """Fetch a case by its internal primary key."""
        return self.db.query(Case).filter(Case.id == internal_id).first()

    def find_existing_by_fir(self, fir_number: str, police_station: str) -> Optional[Case]:
        """
        Check for duplicate case creation by checking FIR Number and originating police station.
        """
        cases = self.db.query(Case).all()
        for c in cases:
            meta = c.fir_metadata or {}
            if (
                meta.get("fir_number", "").strip().lower() == fir_number.strip().lower() and
                meta.get("police_station", "").strip().lower() == police_station.strip().lower()
            ):
                return c
        return None

    def create(self, case: Case) -> Case:
        """Persist a new case entity with transaction commit."""
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)
        return case

    def list_cases(
        self,
        assigned_io_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[Case]:
        """Retrieve paginated cases, optionally filtered by assigned IO."""
        query = self.db.query(Case)
        if assigned_io_id:
            query = query.filter(Case.assigned_io_id == assigned_io_id)
        return query.order_by(Case.created_at.desc()).offset(skip).limit(limit).all()

    def count_cases(self, assigned_io_id: Optional[str] = None) -> int:
        """Count total cases for pagination."""
        query = self.db.query(func.count(Case.id))
        if assigned_io_id:
            query = query.filter(Case.assigned_io_id == assigned_io_id)
        return query.scalar() or 0

    def update(self, case: Case) -> Case:
        """Persist modifications to an existing case entity."""
        self.db.commit()
        self.db.refresh(case)
        return case
