"""CompanyMemberRepository — data access layer for the CompanyMember model.

All methods enforce tenant isolation via ``company_id``.  Extends
``BaseRepository[CompanyMember]`` for standard CRUD and adds member-specific
queries (duplicate check, archived lookup, status/role/department filters,
and the full-featured filtered listing added in Phase 8 / T076).

Spec reference: data-model.md Section 2.1, tasks T021, T076.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, contains_eager

from core.repositories.base import BaseRepository
from modules.auth.models.user import User
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.role import Role

logger = logging.getLogger(__name__)


class CompanyMemberRepository(BaseRepository[CompanyMember]):
    """Data access for the ``company_members`` table.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CompanyMember)

    # ── Lookup methods ─────────────────────────────────────────────────────

    def get_by_user_id(self, user_id: UUID, company_id: UUID) -> CompanyMember | None:
        """Return the active membership for a user in a company, or ``None``."""
        stmt = (
            select(CompanyMember)
            .where(CompanyMember.company_id == company_id)
            .where(CompanyMember.user_id == user_id)
            .where(CompanyMember.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_by_company_and_user(
        self,
        company_id: UUID,
        user_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> CompanyMember | None:
        """Return the membership record for a user in a company.

        When ``include_deleted=True``, returns archived/soft-deleted memberships
        to support reactivation (BR-044).
        """
        stmt = (
            select(CompanyMember)
            .where(CompanyMember.company_id == company_id)
            .where(CompanyMember.user_id == user_id)
        )
        if not include_deleted:
            stmt = stmt.where(CompanyMember.is_deleted == False)  # noqa: E712
        return self.db.execute(stmt).scalars().one_or_none()

    def get_by_employee_id(
        self, company_id: UUID, employee_id: str
    ) -> CompanyMember | None:
        """Return member by employee_id within a company, or ``None``."""
        stmt = (
            select(CompanyMember)
            .where(CompanyMember.company_id == company_id)
            .where(CompanyMember.employee_id == employee_id)
            .where(CompanyMember.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    # ── List / count ───────────────────────────────────────────────────────

    def list_by_company(
        self,
        company_id: UUID,
        *,
        skip: int = 0,
        limit: int = 20,
        status: str | None = None,
        role_id: UUID | None = None,
        department: str | None = None,
        include_deleted: bool = False,
    ) -> tuple[list[CompanyMember], int]:
        """Return paginated members for a company with optional filters."""
        stmt = select(CompanyMember).where(CompanyMember.company_id == company_id)
        if not include_deleted:
            stmt = stmt.where(CompanyMember.is_deleted == False)  # noqa: E712

        if status is not None:
            stmt = stmt.where(CompanyMember.status == status)
        if role_id is not None:
            stmt = stmt.where(CompanyMember.role_id == role_id)
        if department is not None:
            stmt = stmt.where(CompanyMember.department == department)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = self.db.execute(count_stmt).scalar_one()

        rows_stmt = (
            stmt.order_by(CompanyMember.created_at.desc()).offset(skip).limit(limit)
        )
        items = list(self.db.execute(rows_stmt).scalars().all())

        return items, total

    def count_by_company(
        self, company_id: UUID, *, include_deleted: bool = False
    ) -> int:
        """Return the total number of members in a company."""
        stmt = select(func.count()).where(CompanyMember.company_id == company_id)
        if not include_deleted:
            stmt = stmt.where(CompanyMember.is_deleted == False)  # noqa: E712
        return self.db.execute(stmt).scalar_one()

    def count_by_role(self, company_id: UUID, role_id: UUID) -> int:
        """Return the number of active members assigned to a role."""
        stmt = (
            select(func.count())
            .where(CompanyMember.company_id == company_id)
            .where(CompanyMember.role_id == role_id)
            .where(CompanyMember.is_deleted == False)  # noqa: E712
            .where(CompanyMember.status != "archived")
        )
        return self.db.execute(stmt).scalar_one()

    def count_owners(self, company_id: UUID, owner_role_id: UUID) -> int:
        """Return the number of active members with the Owner role."""
        stmt = (
            select(func.count())
            .where(CompanyMember.company_id == company_id)
            .where(CompanyMember.role_id == owner_role_id)
            .where(CompanyMember.is_deleted == False)  # noqa: E712
            .where(CompanyMember.status.in_(["active", "pending_invitation"]))
        )
        return self.db.execute(stmt).scalar_one()

    def list_by_company_filtered(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        role_id: UUID | None = None,
        department: str | None = None,
        search: str | None = None,
        sort_by: str = "name",
        sort_order: str = "asc",
        skip: int = 0,
        limit: int = 20,
        include_archived: bool = False,
    ) -> tuple[list[CompanyMember], int]:
        """Return paginated members with optional filters and text search.

        Joins ``User`` and ``Role`` tables so the returned ``CompanyMember``
        instances have their ``user`` and ``role`` relationships eagerly loaded
        (no N+1 queries).

        Args:
            company_id:       Tenant scope.
            status:           Filter by membership status string.
            role_id:          Filter to members with this role.
            department:       Exact department match (case-sensitive).
            search:           Case-insensitive substring search on
                              ``display_name``, ``email``, and ``employee_id``.
            sort_by:          Column to sort by: ``name``, ``created_at``,
                              ``role_rank``, or ``department``.
            sort_order:       ``asc`` or ``desc``.
            skip:             SQL OFFSET (0-indexed).
            limit:            SQL LIMIT (max rows returned).
            include_archived: When False (default), excludes soft-deleted rows.

        Returns:
            Tuple of ``(members, total_count)`` where ``total_count`` is the
            count of matching rows before pagination is applied.
        """
        stmt = (
            select(CompanyMember)
            .join(User, CompanyMember.user_id == User.id)
            .join(Role, CompanyMember.role_id == Role.id)
            .options(
                contains_eager(CompanyMember.user),
                contains_eager(CompanyMember.role),
            )
            .where(CompanyMember.company_id == company_id)
        )

        if not include_archived:
            stmt = stmt.where(CompanyMember.is_deleted == False)  # noqa: E712

        # ── Filters ──────────────────────────────────────────────────────────
        if status is not None:
            stmt = stmt.where(CompanyMember.status == status)
        if role_id is not None:
            stmt = stmt.where(CompanyMember.role_id == role_id)
        if department is not None:
            stmt = stmt.where(CompanyMember.department == department)
        if search is not None:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    User.display_name.ilike(pattern),
                    User.email.ilike(pattern),
                    CompanyMember.employee_id.ilike(pattern),
                )
            )

        # ── Sort ─────────────────────────────────────────────────────────────
        _sort_columns = {
            "name": User.display_name,
            "created_at": CompanyMember.created_at,
            "role_rank": Role.rank,
            "department": CompanyMember.department,
        }
        sort_col = _sort_columns.get(sort_by, User.display_name)
        sort_expr = sort_col.asc() if sort_order == "asc" else sort_col.desc()

        # ── Total count (before pagination) ──────────────────────────────────
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = self.db.execute(count_stmt).scalar_one()

        # ── Paginated rows ───────────────────────────────────────────────────
        rows_stmt = stmt.order_by(sort_expr, CompanyMember.id).offset(skip).limit(limit)
        items = list(self.db.execute(rows_stmt).scalars().unique().all())

        return items, total

    def get_deleted_by_id(
        self, member_id: UUID, company_id: UUID
    ) -> CompanyMember | None:
        """Return a soft-deleted (archived) member by ID, or ``None``.

        Used by ``restore_member`` to find archived records that are excluded
        by the standard ``get_by_id_or_none`` (which filters ``is_deleted``).
        """
        stmt = (
            select(CompanyMember)
            .where(CompanyMember.id == member_id)
            .where(CompanyMember.company_id == company_id)
            .where(CompanyMember.is_deleted == True)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()
