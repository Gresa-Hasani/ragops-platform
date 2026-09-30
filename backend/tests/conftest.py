from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI

from app.core.config import Environment, LogFormat, Settings
from app.main import create_app


def make_settings(**overrides: object) -> Settings:
    """Build settings for tests, ignoring any local .env file."""
    values: dict[str, object] = {
        "environment": Environment.TEST,
        "log_format": LogFormat.CONSOLE,
        "log_level": "WARNING",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """HTTP client bound to the app, with the lifespan (engine, http client) running.

    ``raise_app_exceptions=False`` lets tests observe the 500 response produced by the
    unhandled-exception handler instead of the re-raised exception.
    """
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client,
    ):
        yield http_client
