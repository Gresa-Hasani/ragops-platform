"""Async SQLAlchemy engine and session factory construction."""

from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Dialect
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import ConnectionPoolEntry

from app.core.config import Settings
from app.core.errors import DatabaseUnavailableError


def _connect_or_raise_unavailable(
    dialect: Dialect, _record: ConnectionPoolEntry, cargs: Any, cparams: Any
) -> Any:
    """Open a DBAPI connection, reporting any failure as ``DatabaseUnavailableError``.

    Connection failures surface inconsistently: refused connections and DNS errors are
    raw ``OSError`` subclasses (not wrapped by SQLAlchemy), while authentication errors
    become ``DBAPIError``. Translating them here, and only for connection establishment,
    gives the API one well-defined error without misclassifying query errors.
    """
    try:
        return dialect.connect(*cargs, **cparams)
    except Exception as exc:
        raise DatabaseUnavailableError() from exc


def create_engine(settings: Settings) -> AsyncEngine:
    engine = create_async_engine(
        settings.database_url.get_secret_value(),
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        echo=settings.database_echo,
    )
    event.listen(engine.sync_engine, "do_connect", _connect_or_raise_unavailable)
    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
