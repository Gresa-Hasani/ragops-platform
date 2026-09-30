from typing import Any

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str | None
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
