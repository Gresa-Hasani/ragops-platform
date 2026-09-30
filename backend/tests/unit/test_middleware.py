import re

import httpx
import pytest

_GENERATED_ID = re.compile(r"[0-9a-f]{32}")


async def test_generates_request_id_when_absent(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health/live")
    assert _GENERATED_ID.fullmatch(response.headers["x-request-id"])


async def test_propagates_valid_client_request_id(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health/live", headers={"X-Request-ID": "trace-abc.123"})
    assert response.headers["x-request-id"] == "trace-abc.123"


@pytest.mark.parametrize("bad_id", ["has spaces", "x" * 129, "inject;log", "<script>"])
async def test_replaces_unsafe_client_request_id(client: httpx.AsyncClient, bad_id: str) -> None:
    response = await client.get("/api/v1/health/live", headers={"X-Request-ID": bad_id})
    assert _GENERATED_ID.fullmatch(response.headers["x-request-id"])


async def test_cors_allows_configured_origin(client: httpx.AsyncClient) -> None:
    response = await client.options(
        "/api/v1/health/live",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "x-request-id" in response.headers


async def test_cors_ignores_unknown_origin(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health/live", headers={"Origin": "http://evil.test"})
    assert "access-control-allow-origin" not in response.headers
