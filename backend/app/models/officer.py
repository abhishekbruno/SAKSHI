"""Officer identity record.  Firebase proves identity; this table grants scope."""
import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from app.db.base import Base
from app.models.organization import utc_now


class IdSequence(Base):
    """Concurrency-safe sequence counter for atomic username generation."""
    __tablename__ = "id_sequences"
    name = Column(String(64), primary_key=True)
    current_value = Column(Integer, nullable=False, default=0)


class Officer(Base):
    __tablename__ = "officers"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    officer_id = Column(String(64), unique=True, nullable=False, index=True)
    firebase_uid = Column(String(128), unique=True, nullable=True, index=True)
    # A private, random Firebase email identifier; never returned by API responses.
    firebase_login_identifier = Column(String(255), unique=True, nullable=True)
    full_name = Column(String(255), nullable=False)
    mobile_e164 = Column(String(16), unique=True, nullable=False, index=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    service_identifier = Column(String(128), unique=True, nullable=True, index=True)
    role = Column(String(64), nullable=False, index=True)
    organization_id = Column(String(64), ForeignKey("organizations.organization_id"), nullable=False, index=True)
    station_id = Column(String(64), ForeignKey("police_stations.station_id"), nullable=False, index=True)
    jurisdiction_id = Column(String(64), ForeignKey("jurisdictions.jurisdiction_id"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    mobile_verified = Column(Boolean, nullable=False, default=False)
    created_by = Column(String(128), nullable=False)
    updated_by = Column(String(128), nullable=False)
    deactivated_by = Column(String(128), nullable=True)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)
