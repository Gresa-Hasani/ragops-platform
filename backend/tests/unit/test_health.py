import asyncio

import httpx
import pytest
from fastapi import FastAPI

from app.api.deps import get_health_checks
from app.observability.health import (
    ComponentStatus,
    HealthCheck,
    QdrantHealthCheck,
    run_health_checks,
)


class FakeCheck:
    def __init__(self, name: str, error: Exception | None = None, delay: float = 0.0) -> None:
        self.name = name
        self._error = error
        self._delay = delay

    async def check(self) -> None:
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error:
            raise self._error


def override_checks(app: FastAPI, checks: list[HealthCheck]) -> None:
    app.dependency_overrides[get_health_checks] = lambda: checks


async def test_liveness_does_not_touch_dependencies(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_ok_when_all_dependencies_healthy(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    override_checks(app, [FakeCheck("postgres"), FakeCheck("qdrant")])
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert [c["name"] for c in body["components"]] == ["postgres", "qdrant"]
    assert all(c["status"] == "ok" for c in body["components"])


async def test_readiness_503_when_a_dependency_fails(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    override_checks(
        app,
        [
            FakeCheck("postgres", ConnectionRefusedError("host db:5432 refused")),
            FakeCheck("qdrant"),
        ],
    )
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    postgres = body["components"][0]
    assert postgres["status"] == "error"
    # Only the exception type is exposed, not the driver message.
    assert postgres["detail"] == "ConnectionRefusedError"
    assert body["components"][1]["status"] == "ok"


async def test_run_health_checks_times_out_slow_checks() -> None:
    results = await run_health_checks([FakeCheck("slow", delay=1.0)], timeout_seconds=0.05)
    assert results[0].status is ComponentStatus.ERROR
    assert results[0].detail == "timed out after 0.05s"


async def test_run_health_checks_runs_checks_concurrently() -> None:
    checks: list[HealthCheck] = [FakeCheck(f"c{i}", delay=0.2) for i in range(5)]
    loop = asyncio.get_running_loop()
    started = loop.time()
    results = await run_health_checks(checks, timeout_seconds=2)
    assert loop.time() - started < 0.8
    assert all(r.status is ComponentStatus.OK for r in results)


@pytest.mark.parametrize(
    ("status_code", "expected"), [(200, ComponentStatus.OK), (503, ComponentStatus.ERROR)]
)
async def test_qdrant_check_uses_readyz_and_api_key(
    status_code: int, expected: ComponentStatus
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status_code)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        check = QdrantHealthCheck(http_client, "http://qdrant:6333/", api_key="k")
        [result] = await run_health_checks([check], timeout_seconds=1)

    assert result.status is expected
    assert str(seen[0].url) == "http://qdrant:6333/readyz"
    assert seen[0].headers["api-key"] == "k"
