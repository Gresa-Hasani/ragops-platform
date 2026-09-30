import pytest
from pydantic import ValidationError

from app.core.config import Environment
from tests.conftest import make_settings


def test_cors_origins_are_parsed_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAGOPS_CORS_ORIGINS", "http://a.test, http://b.test,,")
    settings = make_settings()
    assert settings.cors_origins == ["http://a.test", "http://b.test"]


def test_log_level_is_normalised() -> None:
    assert make_settings(log_level="debug").log_level == "DEBUG"


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_settings(log_level="verbose")


def test_database_url_is_not_leaked_by_repr() -> None:
    settings = make_settings(database_url="postgresql+asyncpg://u:supersecret@db:5432/x")
    assert "supersecret" not in repr(settings)
    assert "supersecret" not in str(settings.model_dump())
    assert "supersecret" in settings.database_url.get_secret_value()


def test_is_production() -> None:
    assert make_settings(environment=Environment.PRODUCTION).is_production
    assert not make_settings().is_production
