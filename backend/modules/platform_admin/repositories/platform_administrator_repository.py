"""PlatformAdministratorRepository — platform-scoped data access.

Deliberately does **not** inherit ``BaseRepository`` — that class mandates
``company_id`` filtering on every method (the tenant-isolation contract
for tenant-scoped tables). A `PlatformAdministrator` has no `company_id`
at all (BR-9A-010); using `BaseRepository` here would be structurally
wrong, not merely unnecessary.

Write paths that participate in an audited mutation (``create``,
``set_active``) only ``flush()`` — never ``commit()`` — so the calling
service can commit the state change together with its audit row in one
transaction (ADR-5, mirrors ``PlatformAuditRepository``).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.platform_admin.models.platform_administrator import PlatformAdministrator


class PlatformAdministratorRepository:
    """Data access for the ``platform_administrators`` table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(
        self, platform_administrator_id: UUID
    ) -> PlatformAdministrator | None:
        return self.db.get(PlatformAdministrator, platform_administrator_id)

    def get_by_user_id(self, user_id: UUID) -> PlatformAdministrator | None:
        stmt = select(PlatformAdministrator).where(
            PlatformAdministrator.user_id == user_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_paginated(
        self, *, offset: int = 0, limit: int = 50
    ) -> tuple[list[PlatformAdministrator], int]:
        total = self.db.execute(
            select(func.count()).select_from(PlatformAdministrator)
        ).scalar_one()
        stmt = (
            select(PlatformAdministrator)
            .order_by(PlatformAdministrator.created_at)
            .offset(offset)
            .limit(limit)
        )
        rows = list(self.db.execute(stmt).scalars().all())
        return rows, total

    def create(self, administrator: PlatformAdministrator) -> PlatformAdministrator:
        """Stage a new administrator row for insert. Caller commits."""
        self.db.add(administrator)
        self.db.flush()
        return administrator

    def set_active(
        self,
        administrator: PlatformAdministrator,
        *,
        is_active: bool,
        deactivated_at: datetime | None = None,
        deactivated_by: UUID | None = None,
    ) -> PlatformAdministrator:
        """Stage an activation/deactivation state change. Caller commits."""
        administrator.is_active = is_active
        administrator.deactivated_at = deactivated_at
        administrator.deactivated_by = deactivated_by
        self.db.flush()
        return administrator
