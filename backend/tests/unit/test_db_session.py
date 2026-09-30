import pytest
from sqlalchemy import text

from app.core.errors import DatabaseUnavailableError
from app.db.session import create_engine
from tests.conftest import make_settings


async def test_connection_failures_raise_database_unavailable() -> None:
    # Nothing listens on port 1, so this fails fast without any infrastructure.
    engine = create_engine(make_settings(database_url="postgresql+asyncpg://u:p@127.0.0.1:1/db"))
    try:
        with pytest.raises(DatabaseUnavailableError) as exc_info:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        assert isinstance(exc_info.value.__cause__, OSError)
    finally:
        await engine.dispose()
