import os
import sys
import logging
from logging.config import fileConfig

from sqlalchemy import engine_from_config, create_engine, pool
from alembic import context

# Prepend application path to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import application settings and ORM metadata
from app.core.config import settings
from app.db.base import Base
# Ensure all ORM models are registered with Base.metadata
import app.models
from app.db.verify_connection import redact_db_url

# Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

# Target metadata for autogenerate support
target_metadata = Base.metadata


def get_url() -> str:
    """
    Safely resolves the database connection URL.
    Prefers settings.DATABASE_URL, falling back to alembic.ini config if specified.
    """
    configured_url = config.get_main_option("sqlalchemy.url")
    url = configured_url if configured_url and configured_url.strip() else settings.DATABASE_URL
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url()
    safe_url = redact_db_url(url)
    logger.info("Running offline migrations against: %s", safe_url)

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.lower().startswith("sqlite"),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_url()
    safe_url = redact_db_url(url)
    logger.info("Running online migrations against: %s", safe_url)

    is_sqlite = url.lower().startswith("sqlite")
    connect_args = {}

    if is_sqlite:
        connect_args["check_same_thread"] = False
    else:
        connect_args["connect_timeout"] = settings.DB_CONNECT_TIMEOUT

    connectable = create_engine(
        url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=is_sqlite,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
