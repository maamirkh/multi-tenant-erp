"""OpportunityRepository — data access for the ``crm_opportunities`` table.

``BaseRepository``'s inherited CRUD was pulled forward in Phase 4 for
``LeadConversionService``. ``list_filtered()`` (backing Phase 5's own
``GET /crm/opportunities``) and the aggregate methods (raw ``Decimal``/
``int`` values only, no report-shaping — for Phase 9's reporting service,
per this file's own T045 task description) are Phase 5's additions.
Phase 9 (T080) adds the by-owner/by-source/won-lost/cycle-time aggregates
the pipeline report (spec.md §40.1) needs.

Spec ref: specs/009-crm/spec.md §38.4, §40.1, §42; plan.md §8.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.crm.models.lead import Lead
from modules.crm.models.opportunity import Opportunity


class OpportunityRepository(BaseRepository[Opportunity]):
    """Data-access layer for ``crm_opportunities``."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Opportunity)

    def list_filtered(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        stage_id: UUID | None = None,
        owner_id: UUID | None = None,
        customer_id: UUID | None = None,
        expected_close_from: date | None = None,
        expected_close_to: date | None = None,
        min_value: Decimal | None = None,
        max_value: Decimal | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Opportunity], int]:
        """Return a page of Opportunities and the total matching count
        (spec.md §42's filter set)."""
        stmt = (
            select(Opportunity)
            .where(Opportunity.company_id == company_id)
            .where(Opportunity.is_deleted == False)  # noqa: E712
        )
        if status is not None:
            stmt = stmt.where(Opportunity.status == status)
        if stage_id is not None:
            stmt = stmt.where(Opportunity.stage_id == stage_id)
        if owner_id is not None:
            stmt = stmt.where(Opportunity.owner_id == str(owner_id))
        if customer_id is not None:
            stmt = stmt.where(Opportunity.customer_id == str(customer_id))
        if expected_close_from is not None:
            stmt = stmt.where(Opportunity.expected_close_date >= expected_close_from)
        if expected_close_to is not None:
            stmt = stmt.where(Opportunity.expected_close_date <= expected_close_to)
        if min_value is not None:
            stmt = stmt.where(Opportunity.value >= min_value)
        if max_value is not None:
            stmt = stmt.where(Opportunity.value <= max_value)

        total = self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()

        stmt = (
            stmt.order_by(Opportunity.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    # ------------------------------------------------------------------
    # Aggregate methods — raw values only, no report-shaping. Consumed by
    # Phase 9's CrmReportingService; kept here per T045's own scope.
    # ------------------------------------------------------------------

    def sum_value_by_stage(self, company_id: UUID) -> list[tuple[UUID, Decimal]]:
        """Sum of OPEN Opportunity ``value`` grouped by ``stage_id``."""
        stmt = (
            select(Opportunity.stage_id, func.sum(Opportunity.value))
            .where(Opportunity.company_id == company_id)
            .where(Opportunity.is_deleted == False)  # noqa: E712
            .where(Opportunity.status == "OPEN")
            .group_by(Opportunity.stage_id)
        )
        return [(row[0], row[1]) for row in self.db.execute(stmt).all()]

    def sum_weighted_value(self, company_id: UUID, *, status: str = "OPEN") -> Decimal:
        """Sum of ``value * probability / 100`` across matching Opportunities,
        computed in SQL (never a stored column — BR-010)."""
        stmt = (
            select(func.sum(Opportunity.value * Opportunity.probability / 100))
            .where(Opportunity.company_id == company_id)
            .where(Opportunity.is_deleted == False)  # noqa: E712
            .where(Opportunity.status == status)
        )
        result = self.db.execute(stmt).scalar_one_or_none()
        return Decimal(result) if result is not None else Decimal("0")

    def count_by_status(self, company_id: UUID) -> dict[str, int]:
        """Count of (non-deleted) Opportunities grouped by ``status``."""
        stmt = (
            select(Opportunity.status, func.count())
            .where(Opportunity.company_id == company_id)
            .where(Opportunity.is_deleted == False)  # noqa: E712
            .group_by(Opportunity.status)
        )
        return {row[0]: row[1] for row in self.db.execute(stmt).all()}

    def sum_value_by_owner(self, company_id: UUID) -> list[tuple[str, Decimal]]:
        """Sum of OPEN Opportunity ``value`` grouped by ``owner_id``
        (spec.md §40.1's "pipeline value by salesperson")."""
        stmt = (
            select(Opportunity.owner_id, func.sum(Opportunity.value))
            .where(Opportunity.company_id == company_id)
            .where(Opportunity.is_deleted == False)  # noqa: E712
            .where(Opportunity.status == "OPEN")
            .group_by(Opportunity.owner_id)
        )
        return [(row[0], row[1]) for row in self.db.execute(stmt).all()]

    def sum_value_by_source(
        self, company_id: UUID
    ) -> list[tuple[UUID | None, Decimal]]:
        """Sum of OPEN Opportunity ``value`` grouped by the originating
        Lead's ``source_id`` (spec.md §40.1's "pipeline value by lead
        source", traced via ``source_lead_id`` -> ``crm_leads.source_id``).
        Opportunities with no ``source_lead_id`` (manually created, not
        from a Lead conversion) are grouped under ``None``."""
        stmt = (
            select(Lead.source_id, func.sum(Opportunity.value))
            .select_from(Opportunity)
            .outerjoin(Lead, Lead.id == Opportunity.source_lead_id)
            .where(Opportunity.company_id == company_id)
            .where(Opportunity.is_deleted == False)  # noqa: E712
            .where(Opportunity.status == "OPEN")
            .group_by(Lead.source_id)
        )
        return [(row[0], row[1]) for row in self.db.execute(stmt).all()]

    def sum_value_by_status_in_period(
        self,
        company_id: UUID,
        status: str,
        date_field: str,
        date_from: date | None,
        date_to: date | None,
    ) -> Decimal:
        """Sum of ``value`` for Opportunities in ``status``, filtered by
        ``date_field`` (``"won_at"`` or ``"lost_at"``) within
        ``[date_from, date_to]`` (spec.md §40.1's won/lost value)."""
        column = getattr(Opportunity, date_field)
        stmt = (
            select(func.sum(Opportunity.value))
            .where(Opportunity.company_id == company_id)
            .where(Opportunity.is_deleted == False)  # noqa: E712
            .where(Opportunity.status == status)
        )
        if date_from is not None:
            stmt = stmt.where(
                column >= datetime.combine(date_from, datetime.min.time())
            )
        if date_to is not None:
            stmt = stmt.where(column <= datetime.combine(date_to, datetime.max.time()))
        result = self.db.execute(stmt).scalar_one_or_none()
        return Decimal(result) if result is not None else Decimal("0")

    def count_won_lost_in_period(
        self, company_id: UUID, date_from: date | None, date_to: date | None
    ) -> tuple[int, int]:
        """Return ``(won_count, lost_count)`` for the period, using each
        row's own terminal timestamp (``won_at``/``lost_at``) — spec.md
        §40.1's win rate = won / (won + lost)."""
        won_stmt = (
            select(func.count())
            .where(Opportunity.company_id == company_id)
            .where(Opportunity.is_deleted == False)  # noqa: E712
            .where(Opportunity.status == "WON")
        )
        lost_stmt = (
            select(func.count())
            .where(Opportunity.company_id == company_id)
            .where(Opportunity.is_deleted == False)  # noqa: E712
            .where(Opportunity.status == "LOST")
        )
        if date_from is not None:
            won_stmt = won_stmt.where(
                Opportunity.won_at >= datetime.combine(date_from, datetime.min.time())
            )
            lost_stmt = lost_stmt.where(
                Opportunity.lost_at >= datetime.combine(date_from, datetime.min.time())
            )
        if date_to is not None:
            won_stmt = won_stmt.where(
                Opportunity.won_at <= datetime.combine(date_to, datetime.max.time())
            )
            lost_stmt = lost_stmt.where(
                Opportunity.lost_at <= datetime.combine(date_to, datetime.max.time())
            )
        won = self.db.execute(won_stmt).scalar_one()
        lost = self.db.execute(lost_stmt).scalar_one()
        return won, lost

    def list_won_in_period(
        self, company_id: UUID, date_from: date | None, date_to: date | None
    ) -> list[Opportunity]:
        """Return WON Opportunities in the period — a small, already-
        filtered result set used by the reporting service to compute
        average deal size / average sales cycle in-process (matching
        ``modules.sales.services.kpi_service``'s own precedent for
        date-arithmetic KPIs no single portable SQL expression covers
        cleanly across SQLite/Postgres)."""
        stmt = (
            select(Opportunity)
            .where(Opportunity.company_id == company_id)
            .where(Opportunity.is_deleted == False)  # noqa: E712
            .where(Opportunity.status == "WON")
        )
        if date_from is not None:
            stmt = stmt.where(
                Opportunity.won_at >= datetime.combine(date_from, datetime.min.time())
            )
        if date_to is not None:
            stmt = stmt.where(
                Opportunity.won_at <= datetime.combine(date_to, datetime.max.time())
            )
        return list(self.db.execute(stmt).scalars().all())
