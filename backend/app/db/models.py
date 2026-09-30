"""Import point for all ORM models so Alembic autogenerate sees the full schema.

Domain tables (documents, chunks, queries, traces, experiments, ...) are added in
later phases; each new model module must be imported here.
"""

from app.db.base import Base

__all__ = ["Base"]
