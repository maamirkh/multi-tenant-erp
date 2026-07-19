"""Company audit log service — records immutable audit trail entries.

This service must always be called inside an open database transaction
(the same ``db`` session that owns the state-change operation).  It never
commits or rolls back; transaction control belongs to the calling service.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from modules.companies.models.company_audit_log import CompanyAuditLog
from modules.companies.repositories.company_audit_log_repository import (
    CompanyAuditLogRepository,
)


class CompanyAuditService:
    """Constructs and persists audit log records for company events.

    Inject one instance per request; the underlying repository holds the
    same ``Session`` object as the repositories inside ``CompanyService``.
    """

    def __init__(self, db: Session) -> None:
        self._repo = CompanyAuditLogRepository(db)

    def record(
        self,
        *,
        company_id: UUID,
        actor_user_id: UUID | None,
        action: str,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
        ip_address: str | None = None,
        request_id: UUID | None = None,
        user_agent: str | None = None,
    ) -> CompanyAuditLog:
        """Append one audit log entry within the current session transaction.

        Args:
            company_id: Owning company.
            actor_user_id: User who triggered the event (``None`` for system events).
            action: Event label matching spec.md §14.1 (e.g. ``"COMPANY_CREATED"``).
            before_state: Company snapshot immediately before the change.
            after_state: Company snapshot immediately after the change.
            ip_address: Requester IP (IPv4 or IPv6 string).
            request_id: Correlation UUID from the originating HTTP request.
            user_agent: Requester User-Agent header.

        Returns:
            The newly created (unflushed) ``CompanyAuditLog`` ORM instance.
        """
        # company_id is passed as a positional arg to repo.create() so it must
        # NOT also appear in data — the repo unpacks data with **data alongside
        # the explicit company_id kwarg, which would cause a TypeError.
        data: dict[str, Any] = {
            "actor_user_id": actor_user_id,
            "action": action,
            "before_state": before_state,
            "after_state": after_state,
            "ip_address": ip_address,
            "request_id": request_id,
            "user_agent": user_agent,
        }
        return self._repo.create(company_id=company_id, data=data)
