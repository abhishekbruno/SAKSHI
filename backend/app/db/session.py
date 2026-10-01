"""
Database session and engine management.
Configured for SQLite (local test/dev) and production PostgreSQL via settings.DATABASE_URL.
"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

# If using sqlite, check_same_thread=False is needed for multi-threaded FastAPI workers
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency to supply a per-request database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
