import json
import logging

from app.core.logging import JsonFormatter, RequestIdFilter
from app.core.request_context import reset_request_id, set_request_id


def _record(**extra: object) -> logging.LogRecord:
    record = logging.LogRecord("app.test", logging.INFO, __file__, 1, "hello %s", ("world",), None)
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def _format(record: logging.LogRecord) -> dict[str, object]:
    RequestIdFilter().filter(record)
    payload: dict[str, object] = json.loads(JsonFormatter().format(record))
    return payload


def test_json_log_includes_request_id_and_extras() -> None:
    token = set_request_id("req-1")
    try:
        payload = _format(_record(duration_ms=12.5))
    finally:
        reset_request_id(token)
    assert payload["message"] == "hello world"
    assert payload["request_id"] == "req-1"
    assert payload["duration_ms"] == 12.5
    assert payload["level"] == "INFO"


def test_explicit_request_id_is_not_overwritten() -> None:
    token = set_request_id("from-context")
    try:
        payload = _format(_record(request_id="explicit"))
    finally:
        reset_request_id(token)
    assert payload["request_id"] == "explicit"


def test_request_id_placeholder_outside_requests() -> None:
    assert _format(_record())["request_id"] == "-"
