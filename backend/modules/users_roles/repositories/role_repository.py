"""RoleRepository — data access layer for the Role model.

All methods enforce tenant isolation via ``company_id``.  Extends
``BaseRepository[Role]`` for standard CRUD and adds role-specific
queries (slug lookup, system roles, custom role counting).

Spec reference: data-model.md Section 2.2, tasks T022.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.users_roles.models.role import Role

logger = logging.getLogger(__name__)


class RoleRepository(BaseRepository[Role]):
    """Data access for the ``roles`` table.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Role)

    # ── Lookup methods ─────────────────────────────────────────────────────

    def get_by_slug(self, company_id: UUID, slug: str) -> Role | None:
        """Return the role with the given slug in a company, or ``None``."""
        stmt = (
            select(Role)
            .where(Role.company_id == company_id)
            .where(Role.slug == slug)
            .where(Role.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_by_name(self, company_id: UUID, name: str) -> Role | None:
        """Return the role with the given name (case-insensitive), or ``None``."""
        stmt = (
            select(Role)
            .where(Role.company_id == company_id)
            .where(func.lower(Role.name) == name.lower())
            .where(Role.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    # ── List / count ───────────────────────────────────────────────────────

    def list_by_company(
        self,
        company_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        include_inactive: bool = False,
    ) -> tuple[list[Role], int]:
        """Return paginated roles for a company."""
        stmt = (
            select(Role)
            .where(Role.company_id == company_id)
            .where(Role.is_deleted == False)  # noqa: E712
        )
        if not include_inactive:
            stmt = stmt.where(Role.is_active == True)  # noqa: E712

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = self.db.execute(count_stmt).scalar_one()

        rows_stmt = stmt.order_by(Role.rank.desc()).offset(skip).limit(limit)
        items = list(self.db.execute(rows_stmt).scalars().all())

        return items, total

    def get_system_roles(self, company_id: UUID) -> list[Role]:
        """Return all system roles for a company."""
        stmt = (
            select(Role)
            .where(Role.company_id == company_id)
            .where(Role.is_system == True)  # noqa: E712
            .where(Role.is_deleted == False)  # noqa: E712
            .order_by(Role.rank.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_custom_roles(self, company_id: UUID) -> int:
        """Return the number of custom (non-system) roles in a company."""
        stmt = (
            select(func.count())
            .where(Role.company_id == company_id)
            .where(Role.is_system == False)  # noqa: E712
            .where(Role.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalar_one()
