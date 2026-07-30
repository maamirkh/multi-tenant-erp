"""Purchase Request repositories — Phase 4.

Repositories:
  PurchaseRequestRepository — CRUD + status-filtered queries for PurchaseRequest
  PRLineRepository          — CRUD + PR-scoped queries for PRLine

Both enforce company_id isolation on every query.

Spec ref: specs/006-purchase-management/data-model.md §Purchase Request Aggregate
Task: T105
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from modules.purchase.models.purchase_request import PRLine, PurchaseRequest
from modules.purchase.repositories import BasePurchaseRepository


class PurchaseRequestRepository(BasePurchaseRepository[PurchaseRequest]):
    """Repository for PurchaseRequest aggregate root.

    All methods enforce company_id isolation.
    Soft-delete is inherited from BasePurchaseRepository/BaseRepository.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=PurchaseRequest)

    # ------------------------------------------------------------------
    # Read queries
    # ------------------------------------------------------------------

    def list_for_company(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        requestor_id: UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[PurchaseRequest]:
        """Return PRs for a company with optional filters."""
        stmt = (
            select(PurchaseRequest)
            .where(PurchaseRequest.company_id == company_id)
            .where(PurchaseRequest.is_deleted == False)  # noqa: E712
            .offset(skip)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(PurchaseRequest.status == status)
        if requestor_id:
            stmt = stmt.where(PurchaseRequest.requestor_id == str(requestor_id))
        return list(self.db.execute(stmt).scalars().all())

    def count_for_company(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
    ) -> int:
        """Return total count of PRs for pagination metadata."""
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(PurchaseRequest)
            .where(PurchaseRequest.company_id == company_id)
            .where(PurchaseRequest.is_deleted == False)  # noqa: E712
        )
        if status:
            stmt = stmt.where(PurchaseRequest.status == status)
        return self.db.execute(stmt).scalar_one()

    def get_by_pr_number(
        self, pr_number: str, company_id: UUID
    ) -> PurchaseRequest | None:
        """Retrieve a PR by its document number within a company."""
        stmt = (
            select(PurchaseRequest)
            .where(PurchaseRequest.pr_number == pr_number)
            .where(PurchaseRequest.company_id == company_id)
            .where(PurchaseRequest.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalar_one_or_none()

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def update_status(
        self,
        pr_id: UUID,
        company_id: UUID,
        new_status: str,
    ) -> None:
        """Update the status of a PurchaseRequest (used by state machine)."""
        stmt = (
            update(PurchaseRequest)
            .where(PurchaseRequest.id == pr_id)
            .where(PurchaseRequest.company_id == company_id)
            .values(status=new_status)
        )
        self.db.execute(stmt)

    def update_total_cost(
        self,
        pr_id: UUID,
        company_id: UUID,
        total: Decimal,
    ) -> None:
        """Recalculate and persist the total_estimated_cost."""
        stmt = (
            update(PurchaseRequest)
            .where(PurchaseRequest.id == pr_id)
            .where(PurchaseRequest.company_id == company_id)
            .values(total_estimated_cost=total)
        )
        self.db.execute(stmt)

    def set_converted_to_po(
        self,
        pr_id: UUID,
        company_id: UUID,
        po_id: UUID,
    ) -> None:
        """Record the PO that was created from this PR."""
        stmt = (
            update(PurchaseRequest)
            .where(PurchaseRequest.id == pr_id)
            .where(PurchaseRequest.company_id == company_id)
            .values(converted_to_po_id=str(po_id))
        )
        self.db.execute(stmt)


class PRLineRepository(BasePurchaseRepository[PRLine]):
    """Repository for PRLine entities.

    All methods enforce company_id isolation via the PRLine.company_id column.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=PRLine)

    # ------------------------------------------------------------------
    # Read queries
    # ------------------------------------------------------------------

    def list_for_pr(self, pr_id: UUID, company_id: UUID) -> list[PRLine]:
        """Return all active lines for a given PR, ordered by line_number."""
        stmt = (
            select(PRLine)
            .where(PRLine.pr_id == str(pr_id))
            .where(PRLine.company_id == company_id)
            .where(PRLine.is_deleted == False)  # noqa: E712
            .order_by(PRLine.line_number)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_max_line_number(self, pr_id: UUID, company_id: UUID) -> int:
        """Return the highest line_number for a PR (0 if no lines)."""
        from sqlalchemy import func

        stmt = (
            select(func.coalesce(func.max(PRLine.line_number), 0))
            .where(PRLine.pr_id == str(pr_id))
            .where(PRLine.company_id == company_id)
            .where(PRLine.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalar_one()

    def delete_all_for_pr(self, pr_id: UUID, company_id: UUID) -> None:
        """Soft-delete all lines belonging to a PR (used on PR cancellation)."""
        from core.utils.datetime import utcnow

        stmt = (
            update(PRLine)
            .where(PRLine.pr_id == str(pr_id))
            .where(PRLine.company_id == company_id)
            .values(is_deleted=True, deleted_at=utcnow())
        )
        self.db.execute(stmt)
