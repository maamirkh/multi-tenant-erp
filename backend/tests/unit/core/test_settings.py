"""Unit tests for Settings configuration.

T135 — ValidationError on missing required fields, correct defaults.
"""

import pytest
from pydantic import ValidationError

from core.config.settings import Settings


def test_settings_raises_when_database_url_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Remove env var and bypass .env file so pydantic-settings cannot find the value.
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            SECRET_KEY="test-secret-key-minimum-32-chars-ok",
            JWT_SECRET_KEY="test-jwt-secret-key-minimum-32-chars-ok",
        )
    assert "DATABASE_URL" in str(exc_info.value)


def test_settings_raises_when_secret_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Remove env var and bypass .env file so pydantic-settings cannot find the value.
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql://u:p@localhost/db",
            JWT_SECRET_KEY="test-jwt-secret-key-minimum-32-chars-ok",
        )
    assert "SECRET_KEY" in str(exc_info.value)


_BASE = dict(
    _env_file=None,
    DATABASE_URL="postgresql://u:p@localhost/db",
    SECRET_KEY="test-secret-key-minimum-32-chars-ok",
    JWT_SECRET_KEY="test-jwt-secret-key-minimum-32-chars-ok",
)


def test_settings_loads_with_required_vars() -> None:
    settings = Settings(**_BASE)  # type: ignore[arg-type]
    assert settings.DATABASE_URL == "postgresql://u:p@localhost/db"
    assert settings.SECRET_KEY == "test-secret-key-minimum-32-chars-ok"


def test_settings_default_debug_is_false(monkeypatch: pytest.MonkeyPatch) -> None:
    # _env_file=None only bypasses the .env FILE — it does not protect against
    # os.environ already carrying DEBUG from an earlier in-process load_dotenv()
    # call (e.g. migrations/env.py, invoked by any real-Postgres test that ran
    # earlier in the same pytest session). Isolate explicitly like the two
    # ValidationError tests above already do.
    monkeypatch.delenv("DEBUG", raising=False)
    settings = Settings(**_BASE)  # type: ignore[arg-type]
    assert settings.DEBUG is False


def test_settings_default_log_level_is_info() -> None:
    settings = Settings(**_BASE)  # type: ignore[arg-type]
    assert settings.LOG_LEVEL == "INFO"


def test_settings_default_api_version() -> None:
    settings = Settings(**_BASE)  # type: ignore[arg-type]
    assert settings.API_VERSION == "1.0.0"


def test_settings_default_db_pool_size() -> None:
    settings = Settings(**_BASE)  # type: ignore[arg-type]
    assert settings.DB_POOL_SIZE == 5


def test_settings_default_db_max_overflow() -> None:
    settings = Settings(**_BASE)  # type: ignore[arg-type]
    assert settings.DB_MAX_OVERFLOW == 10


def test_settings_environment_can_be_overridden() -> None:
    settings = Settings(**{**_BASE, "ENVIRONMENT": "testing"})  # type: ignore[arg-type]
    assert settings.ENVIRONMENT == "testing"
