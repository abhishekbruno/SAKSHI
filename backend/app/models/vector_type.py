"""
Dual-dialect Vector type abstraction for SAKSHI Investigation Platform.

Supports:
- PostgreSQL + pgvector in production/staging (delegates to native pgvector.sqlalchemy.Vector)
- SQLite in local development and automated in-memory test suites (stores as JSON-serialized list)
"""
from typing import Optional, Any
from sqlalchemy.types import TypeDecorator, JSON
from pgvector.sqlalchemy import Vector


class CompatibleVector(TypeDecorator):
    """
    Dialect-aware vector column type:
    - PostgreSQL: compiled directly as native pgvector `VECTOR(dim)` or unconstrained `VECTOR`.
    - SQLite (dev/test): stored and parsed as a JSON-serialized list of floats.

    This ensures that:
    1. PostgreSQL maintains full pgvector indexing and vector math capabilities.
    2. SQLite test fixtures (in-memory) can create tables, insert embeddings,
       and assert properties without failing on missing pgvector extension binaries.
    3. Vector dimensions are unconstrained (dim=None) unless explicitly configured.
    """
    impl = Vector
    cache_ok = True
    comparator_factory = Vector.comparator_factory

    def __init__(self, dim: Optional[int] = None):
        self.dim = dim
        super().__init__(dim=dim)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(self.dim))
        # For SQLite and other development/testing databases
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect) -> Any:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        # Ensure list serialization for SQLite JSON storage
        if isinstance(value, (list, tuple)):
            return [float(x) for x in value]
        return value

    def process_result_value(self, value: Any, dialect) -> Any:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        if isinstance(value, list):
            return [float(x) for x in value]
        return value
