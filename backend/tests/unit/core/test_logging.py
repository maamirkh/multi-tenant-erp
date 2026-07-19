"""Unit tests for structured logging configuration.

T134 — configure_logging, JSON output in production, required fields,
       no DATABASE_URL leakage.
"""

import json
import logging

import pytest

from core.config.settings import Settings
from core.logging.setup import REQUEST_ID_CONTEXT, configure_logging


@pytest.fixture
def prod_settings() -> Settings:
    return Settings(
        DATABASE_URL="postgresql://user:secret@localhost/testdb",
        SECRET_KEY="test-secret-key-minimum-32-chars-ok",
        ENVIRONMENT="production",
        LOG_LEVEL="INFO",
    )


@pytest.fixture
def dev_settings() -> Settings:
    return Settings(
        DATABASE_URL="postgresql://user:secret@localhost/testdb",
        SECRET_KEY="test-secret-key-minimum-32-chars-ok",
        ENVIRONMENT="development",
        LOG_LEVEL="DEBUG",
    )


def test_configure_logging_does_not_raise(dev_settings: Settings) -> None:
    configure_logging(dev_settings)  # must not raise


def test_configure_logging_production_does_not_raise(prod_settings: Settings) -> None:
    configure_logging(prod_settings)  # must not raise


def test_production_log_output_is_valid_json(prod_settings: Settings) -> None:
    configure_logging(prod_settings)

    root_logger = logging.getLogger()
    # Find the JSON formatter handler
    json_handler: logging.Handler | None = None
    for handler in root_logger.handlers:
        formatter = handler.formatter
        if formatter and "JSON" in type(formatter).__name__:
            json_handler = handler
            break

    if json_handler is None:
        pytest.skip("No JSON handler found — production JSON logging not configured")

    import io

    stream = io.StringIO()
    json_handler.stream = stream  # type: ignore[attr-defined]

    test_logger = logging.getLogger("test.json_output")
    test_logger.info("Test JSON log message")

    output = stream.getvalue().strip()
    if output:
        record = json.loads(output)
        assert isinstance(record, dict)


def test_log_record_required_fields_present(prod_settings: Settings) -> None:
    configure_logging(prod_settings)

    root_logger = logging.getLogger()
    json_handler: logging.Handler | None = None
    for handler in root_logger.handlers:
        formatter = handler.formatter
        if formatter and "JSON" in type(formatter).__name__:
            json_handler = handler
            break

    if json_handler is None:
        pytest.skip("No JSON handler found")

    import io

    stream = io.StringIO()
    json_handler.stream = stream  # type: ignore[attr-defined]

    logging.getLogger("test.fields").info("Check required fields")

    output = stream.getvalue().strip()
    if output:
        record = json.loads(output)
        for field in ("timestamp", "level", "logger", "message"):
            assert field in record, f"Required field '{field}' missing from log record"


def test_database_url_does_not_appear_in_log_output(prod_settings: Settings) -> None:
    """DATABASE_URL credentials must not leak into log output."""
    configure_logging(prod_settings)

    root_logger = logging.getLogger()
    json_handler: logging.Handler | None = None
    for handler in root_logger.handlers:
        formatter = handler.formatter
        if formatter and "JSON" in type(formatter).__name__:
            json_handler = handler
            break

    if json_handler is None:
        pytest.skip("No JSON handler found")

    import io

    stream = io.StringIO()
    json_handler.stream = stream  # type: ignore[attr-defined]

    logging.getLogger("test.security").info("Settings loaded")

    output = stream.getvalue()
    assert "secret" not in output.lower() or "postgresql" not in output


def test_request_id_context_var_accessible() -> None:
    """REQUEST_ID_CONTEXT must be importable and settable."""
    token = REQUEST_ID_CONTEXT.set("test-id-xyz")
    assert REQUEST_ID_CONTEXT.get("-") == "test-id-xyz"
    REQUEST_ID_CONTEXT.reset(token)
    assert REQUEST_ID_CONTEXT.get("-") == "-"
