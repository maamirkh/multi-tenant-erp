"""CompanyRepository — data access layer for the Company model.

``Company`` inherits ``BaseModel`` (not ``TenantBaseModel``) because it IS
the tenant entity.  ``BaseRepository`` (which expects ``TenantBaseModel``) is
therefore not used here.  This repository follows the same implementation
style as ``UserRepository`` in the auth module.

All queries that return non-deleted companies include
``WHERE status != 'deleted'`` by default.  The SuperAdmin ``list_all``
method accepts ``include_deleted=True`` to bypass this filter.

Case-insensitive legal name uniqueness is implemented at the application
layer via ``lower()`` in the SELECT.  The database-level uniqueness is
enforced by the ``ix_companies_lower_legal_name`` expression index created
in migration 003.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from modules.companies.models.company import Company
from modules.companies.models.enums import CompanyStatus

logger = logging.getLogger(__name__)


class CompanyRepository:
    """Data access for the ``companies`` table.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Write operations ──────────────────────────────────────────────────────

    def create(self, data: dict[str, Any]) -> Company:
        """Persist a new Company and return it with server-generated fields."""
        company = Company(**data)
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        logger.debug("Company created", extra={"company_id": str(company.id)})
        return company

    def update(self, company: Company, data: dict[str, Any]) -> Company:
        """Apply ``data`` fields to ``company``, commit, and refresh."""
        for field, value in data.items():
            setattr(company, field, value)
        self.db.commit()
        self.db.refresh(company)
        logger.debug("Company updated", extra={"company_id": str(company.id)})
        return company

    def soft_delete(
        self, company: Company, deleted_at: datetime, reason: str
    ) -> Company:
        """Set status to 'deleted', record deletion timestamp and reason."""
        company.status = CompanyStatus.deleted.value
        company.deleted_at = deleted_at
        company.deletion_reason = reason
        self.db.commit()
        self.db.refresh(company)
        logger.info("Company soft-deleted", extra={"company_id": str(company.id)})
        return company

    def restore(self, company: Company) -> Company:
        """Restore a soft-deleted company to 'inactive' status."""
        company.status = CompanyStatus.inactive.value
        company.deleted_at = None
        company.deletion_reason = None
        self.db.commit()
        self.db.refresh(company)
        logger.info("Company restored", extra={"company_id": str(company.id)})
        return company

    # ── Flush-only lifecycle writes (Epic 9A, ADR-5) ────────────────────────
    #
    # Deliberately do NOT commit, unlike every other write method above —
    # TenantLifecycleService (platform_admin) owns a single service-level
    # commit that combines this state change with its audit row and outbox
    # record atomically (mirrors PlatformAdministratorRepository.set_active()
    # and every other Platform-actor-initiated mutation in this Epic).

    def suspend(
        self,
        company: Company,
        *,
        pre_suspension_status: str,
        access_invalidated_at: datetime,
    ) -> Company:
        """Stage a suspension state change. Caller commits."""
        company.status = CompanyStatus.suspended.value
        company.pre_suspension_status = pre_suspension_status
        company.access_invalidated_at = access_invalidated_at
        self.db.flush()
        return company

    def reactivate(self, company: Company, *, restored_status: str) -> Company:
        """Stage a reactivation state change. Caller commits.

        ``access_invalidated_at`` is deliberately left untouched — it is
        never cleared on reactivation (ADR-6/FR-9A-018), so pre-suspension
        Sessions stay refused for this company even after the status is
        restored; only a genuine new login can advance past the watermark.
        """
        company.status = restored_status
        company.pre_suspension_status = None
        self.db.flush()
        return company

    def set_subscription_id(self, company: Company, subscription_id) -> Company:
        """Stage a sync of the denormalised `subscription_id` pointer to
        the tenant's current `Subscription` (Epic 9A ADR-9,
        `SubscriptionService`, T112). The `subscriptions` table's own
        partial-unique-active index remains the authoritative source of
        truth — this column is query convenience only. Caller commits.
        """
        company.subscription_id = subscription_id
        self.db.flush()
        return company

    # ── Read operations ───────────────────────────────────────────────────────

    def get_by_id(self, id: UUID) -> Company | None:
        """Return the Company with the given ``id``, or ``None``."""
        stmt = select(Company).where(Company.id == id)
        return self.db.execute(stmt).scalars().one_or_none()

    def get_for_update(self, id: UUID) -> Company | None:
        """Return the Company row locked with ``SELECT ... FOR UPDATE``.

        Used by ``TenantLifecycleService`` (Epic 9A, T088/T089) so that two
        concurrent suspend/reactivate attempts against the same company
        serialize instead of racing (plan.md §36). Not meaningfully
        testable on SQLite — real PostgreSQL only (T094).
        """
        stmt = select(Company).where(Company.id == id).with_for_update()
        return self.db.execute(stmt).scalars().one_or_none()

    def get_by_id_active(self, id: UUID) -> Company | None:
        """Return the Company if it is active, ``None`` if deleted or suspended."""
        stmt = (
            select(Company)
            .where(Company.id == id)
            .where(
                Company.status.notin_(
                    [CompanyStatus.deleted.value, CompanyStatus.suspended.value]
                )
            )
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_by_slug(self, slug: str) -> Company | None:
        """Return the Company whose slug matches exactly, or ``None``."""
        stmt = select(Company).where(Company.slug == slug)
        return self.db.execute(stmt).scalars().one_or_none()

    def get_by_legal_name(self, name: str) -> Company | None:
        """Return the Company whose legal name matches case-insensitively, or ``None``."""
        stmt = select(Company).where(func.lower(Company.legal_name) == name.lower())
        return self.db.execute(stmt).scalars().one_or_none()

    def exists_by_name(self, name: str, exclude_id: UUID | None = None) -> bool:
        """Return ``True`` if any company has the given legal name (case-insensitive)."""
        stmt = select(Company.id).where(func.lower(Company.legal_name) == name.lower())
        if exclude_id is not None:
            stmt = stmt.where(Company.id != exclude_id)
        return self.db.execute(stmt).first() is not None

    def exists_by_slug(self, slug: str, exclude_id: UUID | None = None) -> bool:
        """Return ``True`` if any company has the given slug."""
        stmt = select(Company.id).where(Company.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Company.id != exclude_id)
        return self.db.execute(stmt).first() is not None

    def list_by_owner(self, owner_id: UUID) -> list[Company]:
        """Return all non-deleted companies owned by ``owner_id``."""
        stmt = (
            select(Company)
            .where(Company.owner_id == owner_id)
            .where(Company.status != CompanyStatus.deleted.value)
            .order_by(Company.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_without_subscription(self) -> list[Company]:
        """Return all non-deleted companies with no `subscription_id` yet
        (Epic 9A, `RolloutService`, T126). Bulk-assigning only these makes
        the rollout step naturally idempotent and re-runnable: a company
        already assigned in a prior run is never revisited.
        """
        stmt = (
            select(Company)
            .where(Company.subscription_id.is_(None))
            .where(Company.status != CompanyStatus.deleted.value)
            .order_by(Company.created_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    _SORTABLE_COLUMNS: dict[str, Any] = {
        "created_at": Company.created_at,
        "legal_name": Company.legal_name,
        "status": Company.status,
    }

    def list_all(
        self,
        filters: dict[str, Any],
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Company], int]:
        """SuperAdmin / Platform Admin: return a paginated list of all
        companies with optional filters.

        Supported filter keys:
          - ``status`` (str): filter by exact status value
          - ``country`` (str): filter by country ISO code
          - ``search`` (str): case-insensitive substring match on
            legal_name or slug (the Platform Tenants page's own
            placeholder text promises "name or slug" search — T192)
          - ``include_deleted`` (bool): include deleted companies (default False)

        ``sort_by`` is restricted to a fixed whitelist (``created_at``,
        ``legal_name``, ``status``) — never a caller-supplied raw column
        name, which would otherwise be an injection surface.
        """
        include_deleted = filters.get("include_deleted", False)
        stmt = select(Company)

        if not include_deleted:
            stmt = stmt.where(Company.status != CompanyStatus.deleted.value)

        if status := filters.get("status"):
            stmt = stmt.where(Company.status == status)

        if country := filters.get("country"):
            stmt = stmt.where(Company.country == country)

        if search := filters.get("search"):
            search_lower = search.lower()
            stmt = stmt.where(
                or_(
                    func.lower(Company.legal_name).contains(search_lower),
                    func.lower(Company.slug).contains(search_lower),
                )
            )

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = self.db.execute(count_stmt).scalar_one()

        sort_column = self._SORTABLE_COLUMNS.get(sort_by, Company.created_at)
        order_clause = sort_column.asc() if sort_order == "asc" else sort_column.desc()

        offset = (page - 1) * page_size
        rows_stmt = stmt.order_by(order_clause).offset(offset).limit(page_size)
        items = list(self.db.execute(rows_stmt).scalars().all())

        return items, total
