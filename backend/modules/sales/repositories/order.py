"""Sales Order aggregate repositories — Phase 4.

Repositories:
  SalesOrderRepository       — CRUD + search + status filters + pipeline queries
  OrderLineRepository        — line CRUD within an order
  SalesApprovalMatrixRepository — matrix CRUD + active matrix lookup
  SalesMatrixRuleRepository  — rules within a matrix
  SalesApprovalRecordRepository — approval record management (append-mostly)

Spec ref: specs/007-sales-management/plan.md — Repository Layer (Order)
Task: T116
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from modules.sales.models.approval import (
    SalesApprovalMatrix,
    SalesApprovalRecord,
    SalesMatrixRule,
)
from modules.sales.models.order import OrderLine, SalesOrder
from modules.sales.repositories import BaseSalesRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SalesOrderRepository
# ---------------------------------------------------------------------------


class SalesOrderRepository(BaseSalesRepository[SalesOrder]):
    """Repository for SalesOrder aggregate root.

    Provides company-isolated CRUD with search, status filtering, and
    customer-level queries suitable for pipeline views.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SalesOrder)

    def get_by_number(self, company_id: UUID, order_number: str) -> SalesOrder | None:
        """Return order by its document number, or None."""
        return (
            self.db.query(SalesOrder)
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.order_number == order_number,
                SalesOrder.is_deleted.is_(False),
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
    ) -> list[SalesOrder]:
        """List orders with optional status/customer/search filters."""
        q = self.db.query(SalesOrder).filter(
            SalesOrder.company_id == company_id,
            SalesOrder.is_deleted.is_(False),
        )
        if status:
            q = q.filter(SalesOrder.status == status)
        if customer_id:
            q = q.filter(SalesOrder.customer_id == str(customer_id))
        if search:
            term = f"%{search}%"
            q = q.filter(
                or_(
                    SalesOrder.order_number.ilike(term),
                )
            )
        return q.order_by(SalesOrder.created_at.desc()).offset(skip).limit(limit).all()

    def count_for_company(
        self,
        company_id: UUID,
        status: str | None = None,
        customer_id: UUID | None = None,
    ) -> int:
        """Return the count of orders matching filters."""
        q = self.db.query(func.count(SalesOrder.id)).filter(
            SalesOrder.company_id == company_id,
            SalesOrder.is_deleted.is_(False),
        )
        if status:
            q = q.filter(SalesOrder.status == status)
        if customer_id:
            q = q.filter(SalesOrder.customer_id == str(customer_id))
        result = q.scalar()
        return result or 0

    def list_pending_approval(self, company_id: UUID) -> list[SalesOrder]:
        """Return all orders awaiting approval for a company."""
        return (
            self.db.query(SalesOrder)
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.status == "PENDING_APPROVAL",
                SalesOrder.is_deleted.is_(False),
            )
            .order_by(SalesOrder.created_at.asc())
            .all()
        )

    def list_by_customer(
        self, company_id: UUID, customer_id: UUID, skip: int = 0, limit: int = 50
    ) -> list[SalesOrder]:
        """Return all orders for a specific customer."""
        return (
            self.db.query(SalesOrder)
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.customer_id == str(customer_id),
                SalesOrder.is_deleted.is_(False),
            )
            .order_by(SalesOrder.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_outstanding_total_for_customer(
        self, company_id: UUID, customer_id: UUID
    ) -> float:
        """Return sum of total_amount for open (non-terminal) orders.

        Used by CreditCheckService to determine outstanding exposure.
        Terminal statuses: CLOSED, CANCELLED.
        """
        open_statuses = [
            "DRAFT",
            "PENDING_APPROVAL",
            "APPROVED",
            "PARTIALLY_DELIVERED",
            "DELIVERED",
            "INVOICED",
        ]
        result = (
            self.db.query(func.coalesce(func.sum(SalesOrder.total_amount), 0))
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.customer_id == str(customer_id),
                SalesOrder.status.in_(open_statuses),
                SalesOrder.is_deleted.is_(False),
            )
            .scalar()
        )
        return float(result or 0)


# ---------------------------------------------------------------------------
# OrderLineRepository
# ---------------------------------------------------------------------------


class OrderLineRepository(BaseSalesRepository[OrderLine]):
    """Repository for OrderLine entities within a SalesOrder."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=OrderLine)

    def list_for_order(self, company_id: UUID, order_id: UUID) -> list[OrderLine]:
        """Return all lines for an order, ordered by line_number."""
        return (
            self.db.query(OrderLine)
            .filter(
                OrderLine.company_id == company_id,
                OrderLine.order_id == str(order_id),
                OrderLine.is_deleted.is_(False),
            )
            .order_by(OrderLine.line_number.asc())
            .all()
        )

    def next_line_number(self, company_id: UUID, order_id: UUID) -> int:
        """Return the next available line number for an order."""
        max_ln = (
            self.db.query(func.max(OrderLine.line_number))
            .filter(
                OrderLine.company_id == company_id,
                OrderLine.order_id == str(order_id),
                OrderLine.is_deleted.is_(False),
            )
            .scalar()
        )
        return (max_ln or 0) + 1

    def delete_for_order(self, company_id: UUID, order_id: UUID) -> None:
        """Soft-delete all lines for an order."""
        self.db.query(OrderLine).filter(
            OrderLine.company_id == company_id,
            OrderLine.order_id == str(order_id),
        ).update({"is_deleted": True})


# ---------------------------------------------------------------------------
# SalesApprovalMatrixRepository
# ---------------------------------------------------------------------------


class SalesApprovalMatrixRepository(BaseSalesRepository[SalesApprovalMatrix]):
    """Repository for SalesApprovalMatrix aggregate."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SalesApprovalMatrix)

    def get_active_for_document_type(
        self, company_id: UUID, document_type: str
    ) -> SalesApprovalMatrix | None:
        """Return the active approval matrix for a given document type."""
        return (
            self.db.query(SalesApprovalMatrix)
            .filter(
                SalesApprovalMatrix.company_id == company_id,
                SalesApprovalMatrix.document_type == document_type,
                SalesApprovalMatrix.is_active.is_(True),
                SalesApprovalMatrix.is_deleted.is_(False),
            )
            .first()
        )

    def list_for_company(
        self, company_id: UUID, document_type: str | None = None
    ) -> list[SalesApprovalMatrix]:
        """List all approval matrices for a company."""
        q = self.db.query(SalesApprovalMatrix).filter(
            SalesApprovalMatrix.company_id == company_id,
            SalesApprovalMatrix.is_deleted.is_(False),
        )
        if document_type:
            q = q.filter(SalesApprovalMatrix.document_type == document_type)
        return q.order_by(SalesApprovalMatrix.name.asc()).all()


# ---------------------------------------------------------------------------
# SalesMatrixRuleRepository
# ---------------------------------------------------------------------------


class SalesMatrixRuleRepository(BaseSalesRepository[SalesMatrixRule]):
    """Repository for SalesMatrixRule entities within an approval matrix."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SalesMatrixRule)

    def list_for_matrix(
        self, company_id: UUID, matrix_id: UUID
    ) -> list[SalesMatrixRule]:
        """Return all rules for a matrix, ordered by level then amount."""
        return (
            self.db.query(SalesMatrixRule)
            .filter(
                SalesMatrixRule.company_id == company_id,
                SalesMatrixRule.matrix_id == str(matrix_id),
                SalesMatrixRule.is_deleted.is_(False),
            )
            .order_by(
                SalesMatrixRule.approval_level.asc(),
                SalesMatrixRule.min_amount.asc(),
            )
            .all()
        )

    def delete_for_matrix(self, company_id: UUID, matrix_id: UUID) -> None:
        """Soft-delete all rules for a matrix."""
        self.db.query(SalesMatrixRule).filter(
            SalesMatrixRule.company_id == company_id,
            SalesMatrixRule.matrix_id == str(matrix_id),
        ).update({"is_deleted": True})


# ---------------------------------------------------------------------------
# SalesApprovalRecordRepository
# ---------------------------------------------------------------------------


class SalesApprovalRecordRepository(BaseSalesRepository[SalesApprovalRecord]):
    """Repository for SalesApprovalRecord — append-mostly, immutable after decision."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SalesApprovalRecord)

    def list_for_document(
        self,
        company_id: UUID,
        document_type: str,
        document_id: UUID,
    ) -> list[SalesApprovalRecord]:
        """Return all approval records for a document, ordered by level."""
        return (
            self.db.query(SalesApprovalRecord)
            .filter(
                SalesApprovalRecord.company_id == company_id,
                SalesApprovalRecord.document_type == document_type,
                SalesApprovalRecord.document_id == str(document_id),
                SalesApprovalRecord.is_deleted.is_(False),
            )
            .order_by(
                SalesApprovalRecord.approval_version.asc(),
                SalesApprovalRecord.approval_level.asc(),
            )
            .all()
        )

    def get_pending_for_approver(
        self, company_id: UUID, approver_id: UUID
    ) -> list[SalesApprovalRecord]:
        """Return all pending approval records assigned to a specific approver."""
        return (
            self.db.query(SalesApprovalRecord)
            .filter(
                SalesApprovalRecord.company_id == company_id,
                SalesApprovalRecord.approver_id == str(approver_id),
                SalesApprovalRecord.decision == "PENDING",
                SalesApprovalRecord.is_deleted.is_(False),
            )
            .order_by(SalesApprovalRecord.created_at.asc())
            .all()
        )

    def get_pending_for_document(
        self,
        company_id: UUID,
        document_type: str,
        document_id: UUID,
        approval_version: int,
    ) -> list[SalesApprovalRecord]:
        """Return pending records for current approval cycle of a document."""
        return (
            self.db.query(SalesApprovalRecord)
            .filter(
                SalesApprovalRecord.company_id == company_id,
                SalesApprovalRecord.document_type == document_type,
                SalesApprovalRecord.document_id == str(document_id),
                SalesApprovalRecord.approval_version == approval_version,
                SalesApprovalRecord.decision == "PENDING",
                SalesApprovalRecord.is_deleted.is_(False),
            )
            .order_by(SalesApprovalRecord.approval_level.asc())
            .all()
        )

    def invalidate_for_document(
        self,
        company_id: UUID,
        document_type: str,
        document_id: UUID,
        approval_version: int,
    ) -> None:
        """Soft-delete all pending records for a given approval version.

        Used when an order is rejected and resubmitted (new approval_version).
        """
        self.db.query(SalesApprovalRecord).filter(
            SalesApprovalRecord.company_id == company_id,
            SalesApprovalRecord.document_type == document_type,
            SalesApprovalRecord.document_id == str(document_id),
            SalesApprovalRecord.approval_version == approval_version,
            SalesApprovalRecord.decision == "PENDING",
        ).update({"is_deleted": True})
