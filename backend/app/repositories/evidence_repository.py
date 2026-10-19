"""
Repository layer for Evidence entities.
Encapsulates all database query logic and transactions for evidence items.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.evidence import Evidence


class EvidenceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_evidence_id(self, evidence_id: str) -> Optional[Evidence]:
        """Fetch an evidence object by its canonical public Evidence ID."""
        return self.db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()

    def get_by_id(self, internal_id: str) -> Optional[Evidence]:
        """Fetch an evidence entity by internal UUID primary key."""
        return self.db.query(Evidence).filter(Evidence.id == internal_id).first()

    def create(self, evidence: Evidence) -> Evidence:
        """Persist a new registered evidence record with transaction commit."""
        self.db.add(evidence)
        self.db.commit()
        self.db.refresh(evidence)
        return evidence

    def list_by_case_id(self, case_id: str, skip: int = 0, limit: int = 100) -> List[Evidence]:
        """Retrieve all evidence registered under a specific case."""
        return (
            self.db.query(Evidence)
            .filter(Evidence.case_id == case_id)
            .order_by(Evidence.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_by_case_id(self, case_id: str) -> int:
        """Count total registered evidence items for a case."""
        return (
            self.db.query(func.count(Evidence.id))
            .filter(Evidence.case_id == case_id)
            .scalar() or 0
        )

    def update(self, evidence: Evidence) -> Evidence:
        """Persist modifications to an evidence entity."""
        self.db.commit()
        self.db.refresh(evidence)
        return evidence
