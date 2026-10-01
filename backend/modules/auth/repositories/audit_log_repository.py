"""AuditLogRepository — append-only data access for security audit logs.

The ``audit_logs`` table is intentionally append-only.  This repository
exposes only ``create`` and ``list_by_user_id`` — there are no ``update``
or ``delete`` methods to preserve forensic integrity.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.auth.models.audit_log import AuditLog
from modules.auth.models.enums import AuditEventType

logger = logging.getLogger(__name__)


class AuditLogRepository:
    """Data access for the ``audit_logs`` table.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        event_type: AuditEventType,
        outcome: str,
        user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        request_id: str | None = None,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Append a new audit log record.

        Args:
            event_type:  Type of security event (from ``AuditEventType`` enum).
            outcome:     ``"SUCCESS"`` or ``"FAILURE"``.
            user_id:     Associated user UUID (nullable for pre-auth failures).
            ip_address:  Client IP address.
            user_agent:  Raw User-Agent header.
            request_id:  X-Request-ID for log correlation.
            reason:      Human-readable explanation for the outcome.
            metadata:    Additional structured context (must not include secrets).

        Returns:
            The persisted ``AuditLog`` record.
        """
        log_entry = AuditLog(
            event_type=event_type,
            outcome=outcome,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            reason=reason,
            metadata_=metadata,
        )
        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)
        logger.debug(
            "Audit log created",
            extra={
                "event_type": event_type.value,
                "outcome": outcome,
                "user_id": str(user_id) if user_id else None,
            },
        )
        return log_entry

    def list_by_user_id(
        self,
        user_id: UUID,
        from_dt: datetime | None = None,
        to_dt: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditLog]:
        """Return audit log entries for *user_id*, ordered newest-first.

        Args:
            user_id: Filter by this user.
            from_dt: Inclusive lower bound on ``created_at`` (optional).
            to_dt:   Exclusive upper bound on ``created_at`` (optional).
            limit:   Maximum number of records to return (default 100).

        Returns:
            List of ``AuditLog`` records, newest first.
        """
        stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        if from_dt is not None:
            stmt = stmt.where(AuditLog.created_at >= from_dt)
        if to_dt is not None:
            stmt = stmt.where(AuditLog.created_at < to_dt)

        return list(self.db.execute(stmt).scalars().all())
