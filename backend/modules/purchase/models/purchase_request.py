"""Purchase Request ORM models — Phase 4.

Phase 4 entities (Purchase Requests):
  PurchaseRequest — procurement requisition document
  PRLine          — individual line items on a purchase request

Note: PurchaseOrder was moved to models/purchase_order.py in Phase 5.

All FK columns use PG_UUID(as_uuid=False) (string hex FK pattern).
company_id / id use Uuid(as_uuid=True) via TenantBaseModel.

Spec ref: specs/006-purchase-management/data-model.md §Purchase Request Aggregate
Tasks: T099, T100
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)

# Note: PurchaseOrder (full model) is in models/purchase_order.py (Phase 5)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

# ---------------------------------------------------------------------------
# PurchaseRequest  (T099)
# ---------------------------------------------------------------------------

PR_STATUSES = (
    "DRAFT",
    "SUBMITTED",
    "UNDER_REVIEW",
    "APPROVED",
    "REJECTED",
    "CANCELLED",
)


class PurchaseRequest(TenantBaseModel):
    """Purchase requisition document.

    Lifecycle: DRAFT → SUBMITTED → UNDER_REVIEW → APPROVED | REJECTED
               DRAFT | SUBMITTED → CANCELLED

    Invariants:
      - pr_number is unique per company (enforced by UniqueConstraint)
      - status transitions must follow the allowed state machine
      - total_estimated_cost is the sum of all PRLine.estimated_line_total
      - Once APPROVED or REJECTED the PR may not be re-submitted
      - Once converted to PO, converted_to_po_id is set (non-nullable thereafter)
    """

    __tablename__ = "purchase_requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','SUBMITTED','UNDER_REVIEW','APPROVED','REJECTED','CANCELLED')",
            name="ck_purchase_requests_status",
        ),
        UniqueConstraint(
            "company_id", "pr_number", name="uq_purchase_requests_company_number"
        ),
        Index("ix_purchase_requests_requestor_id", "requestor_id"),
        Index("ix_purchase_requests_status", "status"),
        {"comment": "Purchase requisition documents"},
    )

    pr_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Auto-generated document number e.g. PR-2026-000001",
    )

    title: Mapped[str] = mapped_column(
        String(300),
        nullable=False,
        doc="Short descriptive title for this purchase request",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="DRAFT",
        doc="Lifecycle status: DRAFT/SUBMITTED/UNDER_REVIEW/APPROVED/REJECTED/CANCELLED",
    )

    requestor_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to user who raised this PR (string hex UUID)",
    )

    department: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Requesting department — used for DEPARTMENT approval rules",
    )

    required_by_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        doc="Date by which the goods or services must be received",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Additional notes or context for this purchase request",
    )

    total_estimated_cost: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Sum of all PRLine.estimated_line_total values",
    )

    currency_code: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        server_default="USD",
        doc="ISO 4217 currency code for all line amounts",
    )

    converted_to_po_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to PurchaseOrder created from this PR (set on conversion)",
    )

    branch_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="Reserved for future multi-branch support",
    )


# ---------------------------------------------------------------------------
# PRLine  (T100)
# ---------------------------------------------------------------------------


class PRLine(TenantBaseModel):
    """Individual line item on a purchase request.

    Invariants:
      - quantity must be > 0
      - estimated_unit_cost must be >= 0
      - estimated_line_total = quantity * estimated_unit_cost (maintained by service)
      - line_number is unique per PR
    """

    __tablename__ = "pr_lines"
    __table_args__ = (
        CheckConstraint(
            "quantity > 0",
            name="ck_pr_lines_quantity_positive",
        ),
        CheckConstraint(
            "estimated_unit_cost >= 0",
            name="ck_pr_lines_unit_cost_non_negative",
        ),
        UniqueConstraint("pr_id", "line_number", name="uq_pr_lines_pr_line"),
        Index("ix_pr_lines_pr_id", "pr_id"),
        {"comment": "Purchase request line items"},
    )

    pr_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to PurchaseRequest",
    )

    line_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="1-based sequential line number within the PR",
    )

    product_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to Epic 5 product catalog (optional — free-text description allowed)",
    )

    product_description: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        doc="Free-text description of the goods or services requested",
    )

    quantity: Mapped[object] = mapped_column(
        Numeric(15, 3),
        nullable=False,
        doc="Quantity requested — must be > 0",
    )

    uom_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="FK to unit of measure (Epic 5) — optional",
    )

    estimated_unit_cost: Mapped[object] = mapped_column(
        Numeric(15, 4),
        nullable=False,
        server_default="0.0000",
        doc="Estimated cost per unit — must be >= 0",
    )

    estimated_line_total: Mapped[object] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0.00",
        doc="Computed: quantity * estimated_unit_cost (maintained by service)",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Line-level notes",
    )
