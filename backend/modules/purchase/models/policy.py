"""Purchase Policy and Sequence ORM models.

PurchasePolicy: Company-level procurement policy configuration.
  One record per company — the authoritative source of procurement governance.

PurchaseSequence: Auto-numbering sequences for purchase documents.
  Incremented with SELECT FOR UPDATE to guarantee uniqueness under concurrency.

Spec ref: specs/006-purchase-management/data-model.md §PurchasePolicy, §PurchaseSequence
Research ref: specs/006-purchase-management/research.md §Decision 9, §Decision 10
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class PurchasePolicy(TenantBaseModel):
    """Company-level procurement policy configuration.

    One record per company (enforced via unique constraint on company_id).
    Created automatically with system defaults when a company first uses
    the purchase module.

    Over-receipt policy values: BLOCK / WARN / ALLOW
    Credit limit mode values:   BLOCK / WARN / OFF
    """

    __tablename__ = "purchase_policies"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_purchase_policy_company"),
        CheckConstraint(
            "over_receipt_policy IN ('BLOCK', 'WARN', 'ALLOW')",
            name="ck_purchase_policy_over_receipt",
        ),
        CheckConstraint(
            "credit_limit_mode IN ('BLOCK', 'WARN', 'OFF')",
            name="ck_purchase_policy_credit_mode",
        ),
        CheckConstraint(
            "ppv_alert_threshold_percent >= 0 AND ppv_alert_threshold_percent <= 100",
            name="ck_purchase_policy_ppv_threshold",
        ),
        CheckConstraint(
            "supplier_rating_window >= 1",
            name="ck_purchase_policy_rating_window",
        ),
        {
            "comment": "Company-level procurement policy configuration — one row per company"
        },
    )

    # Procurement workflow flags
    direct_po_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="Allow PO creation without a preceding Purchase Request (default: false)",
    )

    pr_approval_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Require approval for all Purchase Requests (default: true)",
    )

    po_approval_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Require approval for all Purchase Orders (default: true)",
    )

    # Receiving policy
    over_receipt_policy: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="WARN",
        doc="Policy when GR quantity exceeds PO quantity: BLOCK / WARN / ALLOW",
    )

    # Credit limit enforcement
    credit_limit_mode: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="WARN",
        doc="Credit limit enforcement at PO approval: BLOCK / WARN / OFF",
    )

    # PPV alert threshold
    ppv_alert_threshold_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default="5.00",
        doc="PPV alert threshold percentage (default 5.00%). 0 = always alert.",
    )

    # Supplier rating configuration
    supplier_rating_window: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="20",
        doc="Number of GRs to include in supplier rating computation (default 20)",
    )


class PurchaseSequence(TenantBaseModel):
    """Auto-numbering sequence for purchase documents.

    Each (company_id, document_type, year) combination has exactly one
    sequence record. The ``current_value`` is incremented with SELECT FOR UPDATE
    to guarantee uniqueness under concurrent document creation.

    Document types: PR / PO / GR / RMA
    Format example: PO-2026-000147
    """

    __tablename__ = "purchase_sequences"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "document_type",
            "year",
            name="uq_purchase_seq_company_type_year",
        ),
        Index("ix_purchase_sequences_type", "document_type"),
        CheckConstraint(
            "document_type IN ('PR', 'PO', 'GR', 'RMA')",
            name="ck_purchase_seq_document_type",
        ),
        CheckConstraint(
            "current_value >= 0",
            name="ck_purchase_seq_current_value",
        ),
        {
            "comment": "Auto-numbering sequences for purchase documents, locked with SELECT FOR UPDATE"
        },
    )

    document_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="Document type: PR / PO / GR / RMA",
    )

    prefix: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="''",
        doc="Company-configurable prefix (e.g. 'PO', 'PR')",
    )

    current_value: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="0",
        doc="Last issued sequence number — incremented atomically with SELECT FOR UPDATE",
    )

    year: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        doc="Year component for year-based reset (NULL if reset_yearly=False)",
    )

    reset_yearly: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Reset sequence counter at the start of each calendar year",
    )

    format_pattern: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default="'{PREFIX}-{YEAR}-{SEQ:06d}'",
        doc="Number format pattern, e.g. '{PREFIX}-{YEAR}-{SEQ:06d}'",
    )
