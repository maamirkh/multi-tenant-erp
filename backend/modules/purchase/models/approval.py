"""Purchase Approval Engine ORM models — Phase 3.

Phase 3 entities (Approval Engine):
  ApprovalMatrix  — one matrix per document type per company
  MatrixRule      — condition that routes documents to an approval level
  ApprovalLevel   — approvers assigned to a specific rule level
  ApprovalRecord  — immutable append-only record of each approval action
  ApprovalDelegate — temporary delegation of approval authority

All FK columns use PG_UUID(as_uuid=False) (string hex FK pattern).
company_id / id use Uuid(as_uuid=True) via TenantBaseModel.

Spec ref: specs/006-purchase-management/data-model.md §Approval Aggregate (Phase 4)
Tasks: T073, T074, T075, T076, T077
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

# ---------------------------------------------------------------------------
# ApprovalMatrix  (T073)
# ---------------------------------------------------------------------------


class ApprovalMatrix(TenantBaseModel):
    """Approval matrix — one active matrix per document type per company.

    Defines the overall approval configuration for a document type.
    MatrixRules hang off this matrix with conditions and approval levels.

    Document types:
      PURCHASE_REQUEST — approval of PR documents
      PURCHASE_ORDER   — approval of PO documents
      VENDOR_RETURN    — approval of RMA documents

    Invariants:
      - One active matrix per document_type per company_id.
      - Deactivating (is_active=False) disables all routing via this matrix.
    """

    __tablename__ = "approval_matrices"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ('PURCHASE_REQUEST', 'PURCHASE_ORDER', 'VENDOR_RETURN')",
            name="ck_approval_matrices_document_type",
        ),
        Index("ix_approval_matrices_company_doc", "company_id", "document_type"),
        {"comment": "Approval matrix — one per document type per company"},
    )

    document_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Document type: PURCHASE_REQUEST / PURCHASE_ORDER / VENDOR_RETURN",
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="Human-readable name for this approval matrix",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Whether this matrix is active (routing uses only active matrices)",
    )


# ---------------------------------------------------------------------------
# MatrixRule  (T074)
# ---------------------------------------------------------------------------


class MatrixRule(TenantBaseModel):
    """A condition that routes documents to a specific approval level.

    Multiple rules can exist per matrix. Rules are evaluated in order;
    the first matching rule determines the approval path.

    Condition types:
      AMOUNT_RANGE — matches if document amount is within [min_amount, max_amount]
      CATEGORY     — matches if supplier category_id equals the rule's category_id
      DEPARTMENT   — matches if requestor's department equals the rule's department
      ALWAYS       — always matches (catch-all / default rule)

    Approval modes:
      SEQUENTIAL — each level must be approved before the next is notified
      PARALLEL   — all levels are notified simultaneously
    """

    __tablename__ = "matrix_rules"
    __table_args__ = (
        CheckConstraint(
            "condition_type IN ('AMOUNT_RANGE', 'CATEGORY', 'DEPARTMENT', 'ALWAYS')",
            name="ck_matrix_rules_condition_type",
        ),
        CheckConstraint(
            "approval_mode IN ('SEQUENTIAL', 'PARALLEL')",
            name="ck_matrix_rules_approval_mode",
        ),
        CheckConstraint(
            "approval_level >= 1",
            name="ck_matrix_rules_approval_level",
        ),
        Index("ix_matrix_rules_matrix_id", "matrix_id"),
        {"comment": "Approval matrix rules — conditions that trigger approval routing"},
    )

    matrix_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to ApprovalMatrix",
    )

    condition_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="AMOUNT_RANGE / CATEGORY / DEPARTMENT / ALWAYS",
    )

    min_amount: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Minimum document amount (inclusive) for AMOUNT_RANGE condition",
    )

    max_amount: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        doc="Maximum document amount (inclusive) for AMOUNT_RANGE condition",
    )

    category_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="Supplier category FK (SupplierCategory) for CATEGORY condition",
    )

    department: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        doc="Department identifier for DEPARTMENT condition",
    )

    approval_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        doc="Starting approval level number for this rule (1-based)",
    )

    approval_mode: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="SEQUENTIAL",
        doc="SEQUENTIAL (level-by-level) or PARALLEL (simultaneous all levels)",
    )


# ---------------------------------------------------------------------------
# ApprovalLevel  (T075)
# ---------------------------------------------------------------------------


class ApprovalLevel(TenantBaseModel):
    """Approvers assigned to a specific level within a matrix rule.

    Multiple levels per rule allow multi-step approval chains.
    Approver can be identified by role (any user with that role) or
    by specific user_id.

    Approver types:
      ROLE — any authenticated user with the specified role approves
      USER — a specific named user must approve
    """

    __tablename__ = "approval_levels"
    __table_args__ = (
        CheckConstraint(
            "approver_type IN ('ROLE', 'USER')",
            name="ck_approval_levels_approver_type",
        ),
        CheckConstraint(
            "level_number >= 1",
            name="ck_approval_levels_level_number",
        ),
        CheckConstraint(
            "escalation_days >= 0",
            name="ck_approval_levels_escalation_days",
        ),
        Index("ix_approval_levels_rule_id", "rule_id"),
        {"comment": "Approver assignments per rule level"},
    )

    rule_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="FK to MatrixRule",
    )

    level_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Level position (1 = first approver, 2 = second, etc.)",
    )

    approver_type: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        doc="ROLE — any user with the role; USER — specific named user",
    )

    approver_role: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        doc="Role identifier for ROLE approver type (e.g. 'PURCHASE_MANAGER')",
    )

    approver_user_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=True,
        doc="Specific user UUID for USER approver type",
    )

    escalation_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="3",
        doc="Days before escalation if approval is not actioned",
    )


# ---------------------------------------------------------------------------
# ApprovalRecord  (T076)  — append-only
# ---------------------------------------------------------------------------


class ApprovalRecord(TenantBaseModel):
    """Immutable audit record of a single approval action.

    Created once per approval action (approve / reject / abstain / bypass).
    Never updated or deleted — the repository enforces this invariant.

    Self-approval prevention (approver_id ≠ requestor_id) is enforced
    at the service layer before this record is created.

    Invariants:
      - is_emergency_bypass=True requires bypass_justification to be non-null.
      - action=REJECTED requires comment to be non-null.
      - Once created, this record is immutable.
    """

    __tablename__ = "approval_records"
    __table_args__ = (
        CheckConstraint(
            "action IN ('APPROVED', 'REJECTED', 'ABSTAINED')",
            name="ck_approval_records_action",
        ),
        CheckConstraint(
            "document_type IN ('PURCHASE_REQUEST', 'PURCHASE_ORDER', 'VENDOR_RETURN')",
            name="ck_approval_records_document_type",
        ),
        CheckConstraint(
            "level_number >= 1",
            name="ck_approval_records_level_number",
        ),
        Index(
            "ix_approval_records_document", "company_id", "document_type", "document_id"
        ),
        Index("ix_approval_records_approver", "company_id", "approver_id"),
        {"comment": "Immutable approval action audit trail — append-only"},
    )

    document_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        doc="Document type: PURCHASE_REQUEST / PURCHASE_ORDER / VENDOR_RETURN",
    )

    document_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="UUID of the document being approved (PR id / PO id / RMA id)",
    )

    level_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="Approval level at which this action was taken",
    )

    approver_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="UUID of the user who performed this action",
    )

    action: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="APPROVED / REJECTED / ABSTAINED",
    )

    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional comment; REQUIRED when action=REJECTED",
    )

    is_emergency_bypass: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        doc="True if this record was created via emergency bypass",
    )

    bypass_justification: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Mandatory justification when is_emergency_bypass=True",
    )

    actioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="Timestamp when this approval action was performed",
    )


# ---------------------------------------------------------------------------
# ApprovalDelegate  (T077)
# ---------------------------------------------------------------------------


class ApprovalDelegate(TenantBaseModel):
    """Temporary delegation of approval authority.

    When a delegator is unavailable (vacation, travel), they can delegate
    their approval authority to another user for a specific time window.
    Optionally restricted to a specific document_type.

    Invariants:
      - valid_from < valid_until.
      - delegator_id ≠ delegate_id (cannot delegate to yourself).
      - Delegation is only active when is_active=True AND current time
        falls within [valid_from, valid_until].
    """

    __tablename__ = "approval_delegates"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "delegator_id",
            "delegate_id",
            "document_type",
            name="uq_approval_delegates_delegator_delegate_doc",
        ),
        CheckConstraint(
            "document_type IS NULL OR document_type IN ('PURCHASE_REQUEST', 'PURCHASE_ORDER', 'VENDOR_RETURN')",
            name="ck_approval_delegates_document_type",
        ),
        Index("ix_approval_delegates_delegator", "company_id", "delegator_id"),
        Index("ix_approval_delegates_delegate", "company_id", "delegate_id"),
        {"comment": "Approval authority delegation with time-bounded validity"},
    )

    delegator_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="User UUID who is delegating their approval authority",
    )

    delegate_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        nullable=False,
        doc="User UUID who receives the delegated authority",
    )

    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="Start of delegation window (inclusive)",
    )

    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        doc="End of delegation window (inclusive)",
    )

    document_type: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        doc="Limit delegation to a specific document type (NULL = applies to all)",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        doc="Whether this delegation is currently enabled",
    )
