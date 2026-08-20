"""PlatformAuditQueryService — the audit read/query surface (T078,
FR-9A-200).

Read-only: delegates entirely to ``PlatformAuditRepository.list_filtered()``
(T036, extended this phase). No route exists yet — ``GET /platform/audit``
is T170 (Phase 13), after the dashboard/tenant-directory services this
route composes with also exist; this phase deliberately provides the
service layer only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from modules.platform_admin.models.platform_audit_event import PlatformAuditEvent
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)


class PlatformAuditQueryService:
    """Domain service for the platform-level, cross-tenant audit view."""

    def __init__(self, repo: PlatformAuditRepository) -> None:
        self._repo = repo

    def query(
        self,
        *,
        actor_platform_administrator_id: UUID | None = None,
        company_id: UUID | None = None,
        action: str | None = None,
        target_type: str | None = None,
        target_id: UUID | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        outcome: Literal["success", "denied"] | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[PlatformAuditEvent], int]:
        """Filtered, paginated audit query. Returns ``(items, total)``.

        See ``PlatformAuditRepository.list_filtered()`` for the exact
        filter semantics — this service is a thin pass-through today;
        it is the seam future phases (e.g. T170's route, T168's tenant
        360° view) call through rather than reaching into the repository
        directly.
        """
        return self._repo.list_filtered(
            actor_platform_administrator_id=actor_platform_administrator_id,
            company_id=company_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            created_after=created_after,
            created_before=created_before,
            outcome=outcome,
            offset=offset,
            limit=limit,
        )
