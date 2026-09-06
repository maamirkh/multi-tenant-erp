"""Sales Approval aggregate ORM models — Phase 4.

Phase 4 entities:
  SalesApprovalMatrix  — configurable approval workflow definition
  SalesMatrixRule      — approval rules (level, amount range, approver, auto_approve)
  SalesApprovalRecord  — immutable record of each approval decision

Spec ref: specs/007-sales-management/data-model.md §Approval Aggregate
Task: T107, T108, T109
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
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

# ---------------------------------------------------------------------------
# Valid enum values
# ---------------------------------------------------------------------------

_DOCUMENT_TYPES = "('SALES_ORDER', 'SALES_RETURN')"
_APPROVAL_DECISIONS = "('PENDING', 'APPROVED', 'REJECTED')"


# ---------------------------------------------------------------------------
# SalesApprovalMatrix — aggregate root
# ---------------------------------------------------------------------------


class SalesApprovalMatrix(TenantBaseModel):
    """Configurable approval workflow matrix for sales documents.

    Each company can define multiple approval matrices for different
    document types (SALES_ORDER, SALES_RETURN). Only one matrix should be
    active per document type per company.

    Spec ref: specs/007-sales-management/data-model.md §SalesApprovalMatrix
    """

    __tablename__ = "sales_approval_matrices"
    __table_args__ = (
        Index("ix_sales_approval_matrices_company", "company_id", "document_type"),
        CheckConstraint(
            f"document_type IN {_DOCUMENT_TYPES}",
            name="ck_sales_approval_matrices_doc_type",
        ),
        {"comment": "Approval workflow matrix definitions for sales documents"},
    )

    # ---- Identity ----

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Matrix name (e.g. 'Standard SO Approval', 'High-Value Return Approval')",
    )

    # ---- Document Type ----

    document_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Document type this matrix applies to: SALES_ORDER or SALES_RETURN",
    )

    # ---- Active Status ----

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Only active matrices are used for routing",
    )


# ---------------------------------------------------------------------------
# SalesMatrixRule — owned by SalesApprovalMatrix
# ---------------------------------------------------------------------------


class SalesMatrixRule(TenantBaseModel):
    """A single rule within a SalesApprovalMatrix.

    Rules define which approver is required at which level for which
    amount range. auto_approve=True bypasses the approval step for
    matching documents (typically for low-value orders).

    Spec ref: specs/007-sales-management/data-model.md §SalesMatrixRule
    """

    __tablename__ = "sales_matrix_rules"
    __table_args__ = (
        Index("ix_sales_matrix_rules_matrix", "company_id", "matrix_id"),
        CheckConstraint("approval_level >= 1", name="ck_sales_matrix_rules_level"),
        CheckConstraint("min_amount >= 0", name="ck_sales_matrix_rules_min_amount"),
        {"comment": "Approval rules within an approval matrix"},
    )

    # ---- Parent FK ----

    matrix_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to SalesApprovalMatrix",
    )

    # ---- Approval Level ----

    approval_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Approval level (1 = first approver, 2 = second, etc.)",
    )

    # ---- Amount Range ----

    min_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False,
        server_default="0",
        doc="Minimum order/return amount for this rule to apply",
    )

    max_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Maximum order/return amount; None means no upper limit",
    )

    # ---- Approver ----

    approver_role: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Role that can approve (e.g. 'sales_manager'); nullable if approver_user_id set",
    )

    approver_user_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="Specific user who must approve; nullable if approver_role set",
    )

    # ---- Category Filter ----

    customer_category_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="Restrict rule to specific customer category; nullable = all categories",
    )

    # ---- Auto Approve ----

    auto_approve: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="If true, documents matching this rule are auto-approved (no human needed)",
    )


# ---------------------------------------------------------------------------
# SalesApprovalRecord — owned by SalesOrder/SalesReturn
# ---------------------------------------------------------------------------


class SalesApprovalRecord(TenantBaseModel):
    """Immutable record of a single approval decision.

    Created when a document is submitted for approval. Updated when the
    approver decides. Once a decision is recorded, the record is immutable.

    Invariants:
      - approver_id != requestor_id (self-approval prevention at service layer)
      - Once decision != PENDING, record cannot be modified

    Spec ref: specs/007-sales-management/data-model.md §SalesApprovalRecord
    """

    __tablename__ = "sales_approval_records"
    __table_args__ = (
        Index(
            "ix_sales_approval_records_document",
            "company_id",
            "document_type",
            "document_id",
        ),
        Index(
            "ix_sales_approval_records_approver",
            "company_id",
            "approver_id",
            "decision",
        ),
        CheckConstraint(
            f"document_type IN {_DOCUMENT_TYPES}",
            name="ck_sales_approval_records_doc_type",
        ),
        CheckConstraint(
            f"decision IN {_APPROVAL_DECISIONS}",
            name="ck_sales_approval_records_decision",
        ),
        CheckConstraint("approval_level >= 1", name="ck_sales_approval_records_level"),
        {"comment": "Immutable approval decision records for sales documents"},
    )

    # ---- Document Reference ----

    document_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="Type of document being approved: SALES_ORDER or SALES_RETURN",
    )

    document_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to the document being approved (SalesOrder.id or SalesReturn.id)",
    )

    # ---- Approval Level ----

    approval_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Which approval level this record represents",
    )

    # ---- Approver ----

    approver_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to User who is the designated approver",
    )

    # ---- Decision ----

    decision: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="PENDING",
        doc="PENDING / APPROVED / REJECTED",
    )

    comments: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Approver's comments on decision; nullable",
    )

    decided_at: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        doc="ISO 8601 datetime when decision was recorded; null if still PENDING",
    )

    # ---- Approval Version ----

    approval_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        doc="Matches SalesOrder.approval_version at time of submission",
    )
