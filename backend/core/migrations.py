"""Alembic migration runner.

Provides a single entry point for running database migrations at application
startup. Using the Alembic Python API (rather than subprocess) allows the
migration to share the same process and logging configuration.
"""

import logging
import os

from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)

_ALEMBIC_INI = os.path.join(os.path.dirname(os.path.dirname(__file__)), "alembic.ini")


def run_migrations(alembic_ini: str = _ALEMBIC_INI) -> None:
    """Run pending Alembic migrations (upgrade to head).

    This function is called at application startup (before the server starts
    accepting requests) so that the database schema is always current.

    Args:
        alembic_ini: Path to alembic.ini. Defaults to the file located one
                     directory above this module (i.e. backend/alembic.ini).
    """
    logger.info("Running database migrations", extra={"alembic_ini": alembic_ini})

    try:
        cfg = Config(alembic_ini)
        command.upgrade(cfg, "head")
    except Exception:
        logger.exception(
            "Database migration failed — application may not start correctly"
        )
        raise
    finally:
        # Alembic's fileConfig() reconfigures the root logger (level → WARN,
        # handler → stderr) which silences all post-migration application logs.
        # Restore the application's logging setup so subsequent messages use the
        # correct format, level, and output stream.
        from core.config.settings import get_settings
        from core.logging.setup import configure_logging

        configure_logging(get_settings())

    logger.info("Database migrations complete")
