from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import pytest
from sqlalchemy import text

from app.api.deps import DbSessionDep
from app.main import create_app
from tests.conftest import make_settings

pytestmark = pytest.mark.integration


@asynccontextmanager
async def _client_for(database_url: str, qdrant_url: str) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(make_settings(database_url=database_url, qdrant_url=qdrant_url))

    @app.get("/_test/db-select")
    async def db_select(session: DbSessionDep) -> dict[str, int | None]:
        return {"value": await session.scalar(text("SELECT 1"))}

    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://testserver") as client,
    ):
        yield client


async def test_ready_when_postgres_and_qdrant_are_up(
    test_database_url: str, test_qdrant_url: str
) -> None:
    async with _client_for(test_database_url, test_qdrant_url) as client:
        response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ready"
    assert {c["name"]: c["status"] for c in body["components"]} == {
        "postgres": "ok",
        "qdrant": "ok",
    }


async def test_not_ready_when_postgres_is_unreachable(test_qdrant_url: str) -> None:
    # Nothing listens on port 1, so the connection is refused immediately.
    unreachable = "postgresql+asyncpg://ragops:ragops@127.0.0.1:1/ragops_test"
    async with _client_for(unreachable, test_qdrant_url) as client:
        response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    components = {c["name"]: c for c in response.json()["components"]}
    assert components["postgres"]["status"] == "error"
    assert components["qdrant"]["status"] == "ok"


async def test_db_session_dependency_executes_queries(
    test_database_url: str, test_qdrant_url: str
) -> None:
    async with _client_for(test_database_url, test_qdrant_url) as client:
        response = await client.get("/_test/db-select")
    assert response.status_code == 200, response.text
    assert response.json() == {"value": 1}


async def test_query_against_unreachable_database_returns_structured_503(
    test_qdrant_url: str,
) -> None:
    unreachable = "postgresql+asyncpg://ragops:ragops@127.0.0.1:1/ragops_test"
    async with _client_for(unreachable, test_qdrant_url) as client:
        response = await client.get("/_test/db-select")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
