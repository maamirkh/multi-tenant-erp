#!/usr/bin/env python3
"""Cleanup expired authentication records.

Removes stale data that accumulates over time:

* Expired refresh tokens
* Expired password reset tokens
* Expired email verification tokens
* Revoked sessions older than the audit log retention window
* Audit log entries older than ``AUDIT_LOG_RETENTION_DAYS``

This script is designed for scheduled (cron) execution.  It is safe to run
concurrently — bulk DELETEs use atomic SQL and PostgreSQL's MVCC prevents
races.

Usage
-----
From the backend directory::

    python scripts/cleanup_auth.py

Recommended cron (daily at 03:00 UTC)::

    0 3 * * * cd /app/backend && python scripts/cleanup_auth.py >> /var/log/cleanup.log 2>&1
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure the backend package root is on sys.path when run directly.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Entry point — delete expired/stale auth records."""
    from datetime import timedelta
    from typing import Any, cast

    from sqlalchemy import CursorResult, delete
    from sqlalchemy.orm import Session

    from core.config.settings import get_settings
    from core.database.engine import engine
    from core.utils.datetime import utcnow
    from modules.auth.models.audit_log import AuditLog
    from modules.auth.models.email_verification_token import EmailVerificationToken
    from modules.auth.models.password_reset_token import PasswordResetToken
    from modules.auth.models.refresh_token import RefreshToken
    from modules.auth.models.session import Session as AuthSession

    settings = get_settings()
    now = utcnow()
    retention_cutoff = now - timedelta(days=settings.AUDIT_LOG_RETENTION_DAYS)

    logger.info(
        "Starting auth cleanup. retention_cutoff=%s",
        retention_cutoff.isoformat(),
    )

    with Session(engine) as db:
        # 1. Expired refresh tokens.
        rt_result = cast(
            CursorResult[Any],
            db.execute(delete(RefreshToken).where(RefreshToken.expires_at <= now)),
        )
        rt_count: int = rt_result.rowcount
        logger.info("Deleted %d expired refresh token(s).", rt_count)

        # 2. Expired password reset tokens.
        prt_result = cast(
            CursorResult[Any],
            db.execute(
                delete(PasswordResetToken).where(PasswordResetToken.expires_at <= now)
            ),
        )
        prt_count: int = prt_result.rowcount
        logger.info("Deleted %d expired password reset token(s).", prt_count)

        # 3. Expired email verification tokens.
        evt_result = cast(
            CursorResult[Any],
            db.execute(
                delete(EmailVerificationToken).where(
                    EmailVerificationToken.expires_at <= now
                )
            ),
        )
        evt_count: int = evt_result.rowcount
        logger.info("Deleted %d expired email verification token(s).", evt_count)

        # 4. Revoked sessions beyond the retention window.
        sess_result = cast(
            CursorResult[Any],
            db.execute(
                delete(AuthSession).where(
                    AuthSession.is_revoked == True,  # noqa: E712
                    AuthSession.revoked_at <= retention_cutoff,
                )
            ),
        )
        sess_count: int = sess_result.rowcount
        logger.info("Deleted %d old revoked session(s).", sess_count)

        # 5. Audit logs older than the retention window.
        al_result = cast(
            CursorResult[Any],
            db.execute(delete(AuditLog).where(AuditLog.created_at <= retention_cutoff)),
        )
        al_count: int = al_result.rowcount
        logger.info(
            "Deleted %d audit log entr(ies) older than %d days.",
            al_count,
            settings.AUDIT_LOG_RETENTION_DAYS,
        )

        db.commit()

    total = rt_count + prt_count + evt_count + sess_count + al_count
    logger.info("Auth cleanup complete. total_deleted=%d", total)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        logger.error("Cleanup failed: %s", exc, exc_info=True)
        sys.exit(1)
