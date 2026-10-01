"""SQLAlchemy engine — application-level singleton.

The engine is created once at module import time using the resolved
``Settings`` instance.  All database connections flow through this single
engine so that connection pool settings (``pool_size``, ``max_overflow``)
are applied uniformly.

Key configuration choices:
  - ``pool_pre_ping=True``: validates each connection before use; detects
    stale connections that were dropped by the server or network.
  - ``pool_size`` / ``max_overflow``: driven by ``Settings`` so they can be
    tuned per environment without code changes.
  - Echo is intentionally disabled; query logging is handled via the
    structured logging layer if needed.
  - ``lock_timeout``: PostgreSQL session-level lock_timeout applied on every
    new connection. Prevents indefinite waits on SELECT FOR UPDATE operations
    (e.g. StockPosition concurrent writes). Set via DB_LOCK_TIMEOUT_SECONDS.
    Phase 11 — T278.

Import rules:
  - Import ``engine`` from this module to get the shared engine instance.
  - Do NOT re-create the engine elsewhere.
"""

import logging

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection

from core.config.settings import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

engine: Engine = create_engine(
    _settings.DATABASE_URL,
    pool_size=_settings.DB_POOL_SIZE,
    max_overflow=_settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    echo=False,
)


# ---------------------------------------------------------------------------
# PostgreSQL lock_timeout — T278 Phase 11 Performance Optimisation
# ---------------------------------------------------------------------------
# Apply lock_timeout on every new connection so that SELECT FOR UPDATE on
# inventory_stock_positions does not wait indefinitely under concurrent load.
# SQLite connections (test environment) are silently skipped.


@event.listens_for(engine, "connect")
def _set_pg_lock_timeout(
    dbapi_connection: DBAPIConnection, connection_record: object
) -> None:  # noqa: ARG001
    """Set PostgreSQL lock_timeout on every new connection.

    Skipped for SQLite (test environment) since it uses a different dialect.
    Only applied when DB_LOCK_TIMEOUT_SECONDS > 0.
    """
    timeout_seconds = _settings.DB_LOCK_TIMEOUT_SECONDS
    if timeout_seconds <= 0:
        return

    # Check for SQLite — it does not support lock_timeout
    db_url = _settings.DATABASE_URL
    if db_url.startswith("sqlite"):
        return

    try:
        cursor = dbapi_connection.cursor()
        cursor.execute(f"SET lock_timeout = '{timeout_seconds}s'")
        cursor.close()
    except Exception:  # noqa: BLE001
        # Non-fatal: log and continue. A failed lock_timeout set should not
        # prevent the application from starting.
        logger.warning(
            "Failed to set PostgreSQL lock_timeout=%ds on new connection",
            timeout_seconds,
        )


logger.debug(
    "SQLAlchemy engine created",
    extra={
        "pool_size": _settings.DB_POOL_SIZE,
        "max_overflow": _settings.DB_MAX_OVERFLOW,
        "lock_timeout_seconds": _settings.DB_LOCK_TIMEOUT_SECONDS,
    },
)
