from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import SettingsDep, get_health_checks
from app.observability.health import ComponentStatus, HealthCheck, run_health_checks
from app.schemas.health import ComponentHealthSchema, LivenessResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", summary="Liveness probe")
async def liveness() -> LivenessResponse:
    """Reports that the process is running. Performs no dependency checks."""
    return LivenessResponse()


@router.get(
    "/ready",
    summary="Readiness probe",
    responses={503: {"model": ReadinessResponse, "description": "A dependency is unavailable"}},
)
async def readiness(
    response: Response,
    settings: SettingsDep,
    checks: Annotated[list[HealthCheck], Depends(get_health_checks)],
) -> ReadinessResponse:
    """Checks every required dependency concurrently; returns 503 if any is unavailable."""
    results = await run_health_checks(checks, settings.health_check_timeout_seconds)
    ready = all(r.status is ComponentStatus.OK for r in results)
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        components=[
            ComponentHealthSchema(
                name=r.name, status=r.status, latency_ms=r.latency_ms, detail=r.detail
            )
            for r in results
        ],
    )
