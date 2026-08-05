"""Sales Quotation aggregate repositories — Phase 3.

Repositories:
  SalesQuotationRepository  — CRUD + search + status filters
  QuotationLineRepository   — line CRUD within a quotation
  QuotationRevisionRepository — revision history (append-only)

Spec ref: specs/007-sales-management/plan.md — Repository Layer (Quotation)
Task: T091
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from modules.sales.models.quotation import (
    QuotationLine,
    QuotationRevision,
    SalesQuotation,
)
from modules.sales.repositories import BaseSalesRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SalesQuotationRepository
# ---------------------------------------------------------------------------


class SalesQuotationRepository(BaseSalesRepository[SalesQuotation]):
    """Repository for SalesQuotation aggregate root.

    Provides company-isolated CRUD with search, status filtering, and
    customer-level queries.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SalesQuotation)

    def get_by_number(
        self, company_id: UUID, quotation_number: str
    ) -> SalesQuotation | None:
        """Return quotation by its document number, or None."""
        return (
            self.db.query(SalesQuotation)
            .filter(
                SalesQuotation.company_id == company_id,
                SalesQuotation.quotation_number == quotation_number,
                SalesQuotation.is_deleted.is_(False),
            )
            .first()
        )

    def list_for_company(
        self,
        company_id: UUID,
        status: str | None = None,
        customer_id: UUID | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[SalesQuotation]:
        """List quotations with optional status/customer/search filters."""
        q = self.db.query(SalesQuotation).filter(
            SalesQuotation.company_id == company_id,
            SalesQuotation.is_deleted.is_(False),
        )
        if status:
            q = q.filter(SalesQuotation.status == status)
        if customer_id:
            q = q.filter(SalesQuotation.customer_id == str(customer_id))
        if search:
            term = f"%{search}%"
            q = q.filter(
                or_(
                    SalesQuotation.quotation_number.ilike(term),
                    func.lower(SalesQuotation.customer_notes).contains(
                        func.lower(search)
                    ),
                )
            )
        return (
            q.order_by(SalesQuotation.created_at.desc()).offset(skip).limit(limit).all()
        )

    def count_for_company(
        self,
        company_id: UUID,
        status: str | None = None,
        customer_id: UUID | None = None,
    ) -> int:
        """Count quotations matching filters."""
        q = self.db.query(func.count(SalesQuotation.id)).filter(
            SalesQuotation.company_id == company_id,
            SalesQuotation.is_deleted.is_(False),
        )
        if status:
            q = q.filter(SalesQuotation.status == status)
        if customer_id:
            q = q.filter(SalesQuotation.customer_id == str(customer_id))
        return q.scalar() or 0

    def list_sent_expired(self, company_id: UUID, today: str) -> list[SalesQuotation]:
        """Return SENT_TO_CUSTOMER quotations whose validity_date < today."""
        return (
            self.db.query(SalesQuotation)
            .filter(
                SalesQuotation.company_id == company_id,
                SalesQuotation.status == "SENT_TO_CUSTOMER",
                SalesQuotation.validity_date < today,
                SalesQuotation.is_deleted.is_(False),
            )
            .all()
        )

    def list_expiring_soon(
        self, company_id: UUID, today: str, warning_date: str
    ) -> list[SalesQuotation]:
        """Return SENT_TO_CUSTOMER quotations expiring between today and warning_date."""
        return (
            self.db.query(SalesQuotation)
            .filter(
                SalesQuotation.company_id == company_id,
                SalesQuotation.status == "SENT_TO_CUSTOMER",
                SalesQuotation.validity_date >= today,
                SalesQuotation.validity_date <= warning_date,
                SalesQuotation.is_deleted.is_(False),
            )
            .all()
        )


# ---------------------------------------------------------------------------
# QuotationLineRepository
# ---------------------------------------------------------------------------


class QuotationLineRepository(BaseSalesRepository[QuotationLine]):
    """Repository for QuotationLine entities.

    Lines belong to a SalesQuotation and must be queried with company_id
    isolation.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=QuotationLine)

    def list_for_quotation(
        self, company_id: UUID, quotation_id: UUID
    ) -> list[QuotationLine]:
        """Return all active lines for a quotation, ordered by line_number."""
        return (
            self.db.query(QuotationLine)
            .filter(
                QuotationLine.company_id == company_id,
                QuotationLine.quotation_id == str(quotation_id),
                QuotationLine.is_deleted.is_(False),
            )
            .order_by(QuotationLine.line_number)
            .all()
        )

    def next_line_number(self, company_id: UUID, quotation_id: UUID) -> int:
        """Return next sequential line_number for this quotation."""
        max_ln = (
            self.db.query(func.max(QuotationLine.line_number))
            .filter(
                QuotationLine.company_id == company_id,
                QuotationLine.quotation_id == str(quotation_id),
                QuotationLine.is_deleted.is_(False),
            )
            .scalar()
        )
        return (max_ln or 0) + 1

    def delete_for_quotation(self, company_id: UUID, quotation_id: UUID) -> None:
        """Soft-delete all lines for a quotation."""
        self.db.query(QuotationLine).filter(
            QuotationLine.company_id == company_id,
            QuotationLine.quotation_id == str(quotation_id),
            QuotationLine.is_deleted.is_(False),
        ).update({"is_deleted": True}, synchronize_session="fetch")


# ---------------------------------------------------------------------------
# QuotationRevisionRepository
# ---------------------------------------------------------------------------


class QuotationRevisionRepository(BaseSalesRepository[QuotationRevision]):
    """Repository for QuotationRevision entities (append-only history).

    Revisions are immutable once created — no updates or deletes.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=QuotationRevision)

    def list_for_quotation(
        self, company_id: UUID, quotation_id: UUID
    ) -> list[QuotationRevision]:
        """Return all revisions for a quotation ordered by revision_number."""
        return (
            self.db.query(QuotationRevision)
            .filter(
                QuotationRevision.company_id == company_id,
                QuotationRevision.quotation_id == str(quotation_id),
            )
            .order_by(QuotationRevision.revision_number)
            .all()
        )

    def get_latest(
        self, company_id: UUID, quotation_id: UUID
    ) -> QuotationRevision | None:
        """Return the most recent revision for a quotation."""
        return (
            self.db.query(QuotationRevision)
            .filter(
                QuotationRevision.company_id == company_id,
                QuotationRevision.quotation_id == str(quotation_id),
            )
            .order_by(QuotationRevision.revision_number.desc())
            .first()
        )
