import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.exc import OperationalError

from app.core.errors import InvalidRequestError, NotFoundError


@pytest.fixture
def app(app: FastAPI) -> FastAPI:
    """Extend the app with routes that raise each kind of error."""

    @app.get("/_test/not-found")
    async def raise_not_found() -> None:
        raise NotFoundError("Document 42 was not found.", details={"id": 42})

    @app.get("/_test/invalid")
    async def raise_invalid() -> None:
        raise InvalidRequestError()

    @app.get("/_test/db-down")
    async def raise_db_down() -> None:
        raise OperationalError("SELECT 1", {}, ConnectionRefusedError("password=hunter2"))

    @app.get("/_test/crash")
    async def raise_unexpected() -> None:
        raise RuntimeError("internal secret detail")

    @app.get("/_test/validated")
    async def validated(limit: int) -> dict[str, int]:
        return {"limit": limit}

    return app


async def test_app_error_is_rendered_as_structured_error(client: httpx.AsyncClient) -> None:
    response = await client.get("/_test/not-found")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["message"] == "Document 42 was not found."
    assert error["details"] == {"id": 42}
    assert error["request_id"] == response.headers["x-request-id"]


async def test_app_error_default_message(client: httpx.AsyncClient) -> None:
    response = await client.get("/_test/invalid")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "INVALID_REQUEST"
    assert error["message"] == "The request is invalid."
    assert "details" not in error


async def test_database_errors_map_to_database_unavailable(client: httpx.AsyncClient) -> None:
    response = await client.get("/_test/db-down")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "hunter2" not in response.text


async def test_unhandled_exception_returns_safe_500(client: httpx.AsyncClient) -> None:
    response = await client.get("/_test/crash")
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["code"] == "INTERNAL_ERROR"
    assert "secret" not in response.text
    # The request ID survives although this handler runs outside the request middleware.
    assert error["request_id"]
    assert response.headers["x-request-id"] == error["request_id"]


async def test_validation_error_does_not_echo_input(client: httpx.AsyncClient) -> None:
    response = await client.get("/_test/validated", params={"limit": "not-a-number"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["details"]["errors"][0]["loc"] == ["query", "limit"]
    assert "not-a-number" not in response.text


async def test_unknown_route_returns_structured_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_wrong_method_returns_structured_405(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/health/live")
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert "GET" in response.headers["allow"]
