import asyncio
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _alembic(database_url: str, *args: str) -> None:
    # Alembic's env.py calls asyncio.run(), so it runs in a subprocess rather than
    # inside the test's event loop.
    subprocess.run(
        [sys.executable, "-m", "alembic", "-x", f"db_url={database_url}", *args],
        cwd=BACKEND_DIR,
        check=True,
        capture_output=True,
        text=True,
    )


async def _current_revision(database_url: str) -> str | None:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            exists = await connection.scalar(text("SELECT to_regclass('alembic_version')"))
            if exists is None:
                return None
            revision: str | None = await connection.scalar(
                text("SELECT version_num FROM alembic_version")
            )
            return revision
    finally:
        await engine.dispose()


def test_migrations_upgrade_and_downgrade_round_trip(test_database_url: str) -> None:
    _alembic(test_database_url, "downgrade", "base")
    assert asyncio.run(_current_revision(test_database_url)) is None

    _alembic(test_database_url, "upgrade", "head")
    assert asyncio.run(_current_revision(test_database_url)) == "0001"

    # Re-running is a no-op.
    _alembic(test_database_url, "upgrade", "head")
    assert asyncio.run(_current_revision(test_database_url)) == "0001"
