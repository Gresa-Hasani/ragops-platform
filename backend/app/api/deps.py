"""FastAPI dependencies.

Infrastructure objects (engine, HTTP client) are created once in the application
lifespan and stored on ``app.state``; these providers expose them to endpoints so
tests can override any of them via ``app.dependency_overrides``.
"""

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.observability.health import HealthCheck, PostgresHealthCheck, QdrantHealthCheck


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_engine(request: Request) -> AsyncEngine:
    engine: AsyncEngine = request.app.state.engine
    return engine


def get_http_client(request: Request) -> httpx.AsyncClient:
    client: httpx.AsyncClient = request.app.state.http_client
    return client


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
DbSessionDep = Annotated[AsyncSession, Depends(get_db_session)]


def get_health_checks(
    settings: SettingsDep,
    engine: Annotated[AsyncEngine, Depends(get_engine)],
    http_client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
) -> list[HealthCheck]:
    api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
    return [
        PostgresHealthCheck(engine),
        QdrantHealthCheck(http_client, settings.qdrant_url, api_key),
    ]
