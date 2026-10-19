"""Append-only case assignment history; Case.assigned_io_id remains the active projection."""
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from app.db.base import Base
from app.models.organization import utc_now


class CaseAssignment(Base):
    __tablename__ = "case_assignments"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assignment_id = Column(String(64), unique=True, nullable=False, index=True)
    case_id = Column(String(64), ForeignKey("cases.case_id"), nullable=False, index=True)
    officer_id = Column(String(64), ForeignKey("officers.officer_id"), nullable=False, index=True)
    previous_officer_id = Column(String(64), nullable=True)
    assigned_by = Column(String(128), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    assigned_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    ended_at = Column(DateTime(timezone=True), nullable=True)
