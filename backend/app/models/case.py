"""
SQLAlchemy ORM model for Case entity in SAKSHI.
Distinguishes between SOURCE-DEFINED requirements and PROPOSED implementation fields.
CRITICAL SECURITY RULE: No passwords or raw credentials are ever stored in this table.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Text, JSON
from app.db.base import Base


def get_utc_now():
    return datetime.now(timezone.utc)


class Case(Base):
    __tablename__ = "cases"

    # PROPOSED: Internal immutable database primary key (isolates internal relational integrity)
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)

    # SOURCE-DEFINED: Authoritative unique Case ID used across all downstream SAKSHI stages
    case_id = Column(String(64), unique=True, nullable=False, index=True)

    # PROPOSED: Human-readable reference or brief title of the death investigation
    title = Column(String(255), nullable=False)

    # SOURCE-DEFINED: Initial FIR metadata (FIR No, Police Station, Date/Time, Jurisdiction)
    fir_metadata = Column(JSON, nullable=False)

    # SOURCE-DEFINED: Assigned Investigating Officer identifier (stable reference, not credentials)
    assigned_io_id = Column(String(128), nullable=False, index=True)

    # SOURCE-DEFINED: Governed by Stage Engine. Initial default: "INITIALIZED" (PROPOSED initial value)
    lifecycle_stage = Column(String(64), nullable=False, default="INITIALIZED", index=True)

    # PROPOSED: Operational workflow status ("ACTIVE", "SUSPENDED", "CLOSED")
    status = Column(String(32), nullable=False, default="ACTIVE")

    # PROPOSED: Logical Case Workspace URI or reference path
    case_workspace_path = Column(String(512), nullable=False)

    # PROPOSED: Governance audit fields
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=get_utc_now, onupdate=get_utc_now)

    def __repr__(self) -> str:
        return f"<Case(case_id='{self.case_id}', title='{self.title}', stage='{self.lifecycle_stage}', io='{self.assigned_io_id}')>"
