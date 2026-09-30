"""Baseline revision.

Establishes Alembic version tracking before any domain tables exist, so every later
schema change is an explicit, reviewable migration on top of a known starting point.

Revision ID: 0001
Revises:
Create Date: 2026-09-30
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
