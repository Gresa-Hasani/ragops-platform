"""Dependency health checks used by the readiness endpoint.

Each check is a small object satisfying the ``HealthCheck`` protocol, so new
dependencies (e.g. an LLM provider) can be added without touching the endpoint.
Checks raise on failure; ``run_health_checks`` runs them concurrently with a timeout
and converts outcomes into ``ComponentHealth`` results.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


class ComponentStatus(StrEnum):
    OK = "ok"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    name: str
    status: ComponentStatus
    latency_ms: float
    detail: str | None = None


class HealthCheck(Protocol):
    name: str

    async def check(self) -> None:
        """Return normally when healthy; raise otherwise."""
        ...


class PostgresHealthCheck:
    name = "postgres"

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def check(self) -> None:
        async with self._engine.connect() as connection:
            await connection.execute(text("SELECT 1"))


class QdrantHealthCheck:
    name = "qdrant"

    def __init__(self, client: httpx.AsyncClient, base_url: str, api_key: str | None) -> None:
        self._client = client
        self._url = f"{base_url.rstrip('/')}/readyz"
        self._headers = {"api-key": api_key} if api_key else {}

    async def check(self) -> None:
        response = await self._client.get(self._url, headers=self._headers)
        response.raise_for_status()


async def _run_check(check: HealthCheck, timeout_seconds: float) -> ComponentHealth:
    started = time.perf_counter()
    try:
        await asyncio.wait_for(check.check(), timeout=timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - every failure mode must become a status
        latency_ms = (time.perf_counter() - started) * 1000
        # Only the exception type is exposed to clients: driver messages can contain
        # hostnames or other infrastructure details.
        detail = (
            f"timed out after {timeout_seconds}s"
            if isinstance(exc, TimeoutError)
            else type(exc).__name__
        )
        logger.warning(
            "Health check failed",
            extra={
                "component": check.name,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "cause": repr(exc.__cause__) if exc.__cause__ else None,
            },
        )
        return ComponentHealth(check.name, ComponentStatus.ERROR, round(latency_ms, 2), detail)

    latency_ms = (time.perf_counter() - started) * 1000
    return ComponentHealth(check.name, ComponentStatus.OK, round(latency_ms, 2))


async def run_health_checks(
    checks: list[HealthCheck], timeout_seconds: float
) -> list[ComponentHealth]:
    return list(await asyncio.gather(*(_run_check(c, timeout_seconds) for c in checks)))
