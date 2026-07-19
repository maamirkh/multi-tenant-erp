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

Import rules:
  - Import ``engine`` from this module to get the shared engine instance.
  - Do NOT re-create the engine elsewhere.
"""

import logging

from sqlalchemy import Engine, create_engine

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

logger.debug(
    "SQLAlchemy engine created",
    extra={
        "pool_size": _settings.DB_POOL_SIZE,
        "max_overflow": _settings.DB_MAX_OVERFLOW,
    },
)
