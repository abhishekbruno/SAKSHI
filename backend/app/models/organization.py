"""Persistent, data-driven organisational scope for SAKSHI IAM."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, String
from app.db.base import Base


def utc_now():
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class Jurisdiction(Base):
    __tablename__ = "jurisdictions"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    jurisdiction_id = Column(String(64), unique=True, nullable=False, index=True)
    organization_id = Column(String(64), ForeignKey("organizations.organization_id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class PoliceStation(Base):
    __tablename__ = "police_stations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    station_id = Column(String(64), unique=True, nullable=False, index=True)
    organization_id = Column(String(64), ForeignKey("organizations.organization_id"), nullable=False, index=True)
    jurisdiction_id = Column(String(64), ForeignKey("jurisdictions.jurisdiction_id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="ACTIVE", index=True)
    created_by = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
