from typing import Literal

from pydantic import BaseModel

from app.observability.health import ComponentStatus


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ComponentHealthSchema(BaseModel):
    name: str
    status: ComponentStatus
    latency_ms: float
    detail: str | None = None


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    components: list[ComponentHealthSchema]
