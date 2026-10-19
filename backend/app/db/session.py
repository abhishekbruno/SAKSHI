"""
Database session and engine management for SAKSHI Investigation Platform.
Supports dual-dialect execution:
- Local development & in-memory testing: SQLite (check_same_thread=False)
- Production & staging: PostgreSQL + pgvector (connection pooling, pre-ping)
"""
from typing import Generator, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings


def create_db_engine(db_url: str):
    """
    Constructs an engine with dialect-optimized connection arguments.
    Ensures SQLite thread-safety for FastAPI and robust connection pooling for PostgreSQL.
    """
    engine_kwargs: Dict[str, Any] = {
        "echo": settings.DB_ECHO,
    }

    if db_url.lower().startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL / non-SQLite production configuration
        engine_kwargs["connect_args"] = {"connect_timeout": settings.DB_CONNECT_TIMEOUT}
        engine_kwargs["pool_pre_ping"] = settings.DB_POOL_PRE_PING
        engine_kwargs["pool_size"] = settings.DB_POOL_SIZE
        engine_kwargs["max_overflow"] = settings.DB_MAX_OVERFLOW
        engine_kwargs["pool_timeout"] = settings.DB_POOL_TIMEOUT

    return create_engine(db_url, **engine_kwargs)


engine = create_db_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency to supply a per-request database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
