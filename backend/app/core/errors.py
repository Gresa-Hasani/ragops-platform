"""Application error hierarchy.

Domain and service code raise these framework-independent exceptions; the API layer
translates them into the structured error envelope. Each error carries a stable,
machine-readable ``code`` and a message that is safe to show to API clients.
"""

from typing import Any


class AppError(Exception):
    code: str = "INTERNAL_ERROR"
    status_code: int = 500
    default_message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, details: dict[str, Any] | None = None):
        self.message = message or self.default_message
        self.details = details
        super().__init__(self.message)


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = 404
    default_message = "The requested resource was not found."


class InvalidRequestError(AppError):
    code = "INVALID_REQUEST"
    status_code = 400
    default_message = "The request is invalid."


class ServiceUnavailableError(AppError):
    code = "SERVICE_UNAVAILABLE"
    status_code = 503
    default_message = "A required service is currently unavailable."


class DatabaseUnavailableError(ServiceUnavailableError):
    code = "DATABASE_UNAVAILABLE"
    default_message = "The database is currently unavailable."
