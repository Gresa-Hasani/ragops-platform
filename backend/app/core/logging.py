"""Logging configuration.

Uses the standard library only. In JSON mode every record is a single JSON line that
includes the current request ID, which makes logs correlatable with API responses.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from app.core.config import LogFormat, Settings
from app.core.request_context import get_request_id

# Attributes present on every LogRecord; anything else was passed via ``extra=``.
_RESERVED_ATTRS = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys()
    | {"message", "asctime", "color_message"}  # color_message: uvicorn ANSI duplicate
)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Respect an explicit ``extra={"request_id": ...}`` (used by handlers that run
        # after the request context has been reset).
        if not getattr(record, "request_id", None):
            record.request_id = get_request_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in vars(record).items():
            if key not in _RESERVED_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())
    if settings.log_format is LogFormat.JSON:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s [%(request_id)s] %(name)s: %(message)s")
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level)

    # Route uvicorn's own loggers through the root handler so every line shares one format.
    for name in ("uvicorn", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    # Uvicorn's access log duplicates our request logging middleware.
    logging.getLogger("uvicorn.access").disabled = True
    # httpx logs every outgoing request (e.g. health probes) at INFO.
    logging.getLogger("httpx").setLevel(logging.WARNING)
