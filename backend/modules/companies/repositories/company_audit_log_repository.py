"""CompanyAuditLogRepository — append-only data access for CompanyAuditLog.

Audit logs are immutable records.  This repository exposes ONLY ``create``
and ``list_by_company``; any attempt to call ``update`` or ``delete`` raises
``NotImplementedError`` to prevent accidental mutation of the audit trail.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.companies.models.company_audit_log import CompanyAuditLog

logger = logging.getLogger(__name__)


class CompanyAuditLogRepository:
    """Append-only data access for the ``company_audit_logs`` table.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Write operations ──────────────────────────────────────────────────────

    def create(self, company_id: UUID, data: dict[str, Any]) -> CompanyAuditLog:
        """Insert a new audit log record and return it.

        ``data`` must include at minimum ``action`` (str).  Optional keys:
        ``actor_user_id``, ``before_state``, ``after_state``, ``ip_address``,
        ``user_agent``, ``request_id``, ``metadata_``.
        """
        log = CompanyAuditLog(company_id=company_id, **data)
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        logger.info(
            "CompanyAuditLog created",
            extra={
                "company_id": str(company_id),
                "audit_log_id": str(log.id),
                "action": log.action,
            },
        )
        return log

    def update(self, *args: object, **kwargs: object) -> None:
        """Not implemented — audit logs are immutable."""
        raise NotImplementedError(
            "CompanyAuditLog records are immutable and cannot be updated."
        )

    def delete(self, *args: object, **kwargs: object) -> None:
        """Not implemented — audit logs are immutable."""
        raise NotImplementedError(
            "CompanyAuditLog records are immutable and cannot be deleted."
        )

    # ── Read operations ───────────────────────────────────────────────────────

    def list_by_company(
        self,
        company_id: UUID,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[CompanyAuditLog], int]:
        """Return a paginated audit log for the given company.

        Supported filter keys:
          - ``action`` (str): filter by exact action label
          - ``actor_user_id`` (UUID): filter by actor
        """
        filters = filters or {}
        stmt = select(CompanyAuditLog).where(CompanyAuditLog.company_id == company_id)

        if action := filters.get("action"):
            stmt = stmt.where(CompanyAuditLog.action == action)

        if actor_id := filters.get("actor_user_id"):
            stmt = stmt.where(CompanyAuditLog.actor_user_id == actor_id)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = self.db.execute(count_stmt).scalar_one()

        offset = (page - 1) * page_size
        rows_stmt = (
            stmt.order_by(CompanyAuditLog.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items = list(self.db.execute(rows_stmt).scalars().all())

        return items, total
