"""Pydantic schemas for Phase 3 Approval Engine.

Covers:
  ApprovalMatrix  — create/update/read
  MatrixRule      — create/update/read
  ApprovalLevel   — create/update/read
  ApprovalRecord  — read only (created by approve/reject/bypass actions)
  ApprovalDelegate — create/update/read
  ApprovalAction  — approve / reject / bypass request bodies

Spec ref: specs/006-purchase-management/data-model.md §Approval Aggregate
Task: T089
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator

from modules.purchase.schemas.base import PurchaseBaseSchema

# ---------------------------------------------------------------------------
# ApprovalMatrix
# ---------------------------------------------------------------------------

DOCUMENT_TYPES = ("PURCHASE_REQUEST", "PURCHASE_ORDER", "VENDOR_RETURN")
CONDITION_TYPES = ("AMOUNT_RANGE", "CATEGORY", "DEPARTMENT", "ALWAYS")
APPROVAL_MODES = ("SEQUENTIAL", "PARALLEL")
APPROVER_TYPES = ("ROLE", "USER")
ACTIONS = ("APPROVED", "REJECTED", "ABSTAINED")


class ApprovalMatrixCreate(PurchaseBaseSchema):
    """Create a new approval matrix for a document type."""

    document_type: str = Field(
        ..., description="PURCHASE_REQUEST / PURCHASE_ORDER / VENDOR_RETURN"
    )
    name: str = Field(..., min_length=1, max_length=200)
    is_active: bool = True

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        if v not in DOCUMENT_TYPES:
            raise ValueError(f"document_type must be one of {DOCUMENT_TYPES}")
        return v


class ApprovalMatrixUpdate(PurchaseBaseSchema):
    """Update an existing approval matrix."""

    name: str | None = Field(None, min_length=1, max_length=200)
    is_active: bool | None = None


class ApprovalMatrixRead(PurchaseBaseSchema):
    """Response schema for an approval matrix."""

    id: UUID
    company_id: UUID
    document_type: str
    name: str
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# MatrixRule
# ---------------------------------------------------------------------------


class MatrixRuleCreate(PurchaseBaseSchema):
    """Add a rule to an approval matrix."""

    condition_type: str = Field(
        ..., description="AMOUNT_RANGE / CATEGORY / DEPARTMENT / ALWAYS"
    )
    min_amount: Decimal | None = Field(None, ge=0)
    max_amount: Decimal | None = Field(None, ge=0)
    category_id: UUID | None = None
    department: str | None = Field(None, max_length=100)
    approval_level: int = Field(1, ge=1)
    approval_mode: str = Field("SEQUENTIAL", description="SEQUENTIAL / PARALLEL")

    @field_validator("condition_type")
    @classmethod
    def validate_condition_type(cls, v: str) -> str:
        if v not in CONDITION_TYPES:
            raise ValueError(f"condition_type must be one of {CONDITION_TYPES}")
        return v

    @field_validator("approval_mode")
    @classmethod
    def validate_approval_mode(cls, v: str) -> str:
        if v not in APPROVAL_MODES:
            raise ValueError(f"approval_mode must be one of {APPROVAL_MODES}")
        return v


class MatrixRuleUpdate(PurchaseBaseSchema):
    """Update a matrix rule."""

    condition_type: str | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None
    category_id: UUID | None = None
    department: str | None = None
    approval_level: int | None = Field(None, ge=1)
    approval_mode: str | None = None


class MatrixRuleRead(PurchaseBaseSchema):
    """Response schema for a matrix rule."""

    id: UUID
    company_id: UUID
    matrix_id: str
    condition_type: str
    min_amount: Decimal | None
    max_amount: Decimal | None
    category_id: str | None
    department: str | None
    approval_level: int
    approval_mode: str
    created_at: datetime


# ---------------------------------------------------------------------------
# ApprovalLevel
# ---------------------------------------------------------------------------


class ApprovalLevelCreate(PurchaseBaseSchema):
    """Add an approver level to a rule."""

    level_number: int = Field(..., ge=1)
    approver_type: str = Field(..., description="ROLE / USER")
    approver_role: str | None = Field(None, max_length=50)
    approver_user_id: UUID | None = None
    escalation_days: int = Field(3, ge=0)

    @field_validator("approver_type")
    @classmethod
    def validate_approver_type(cls, v: str) -> str:
        if v not in APPROVER_TYPES:
            raise ValueError(f"approver_type must be one of {APPROVER_TYPES}")
        return v


class ApprovalLevelUpdate(PurchaseBaseSchema):
    """Update an approver level."""

    approver_type: str | None = None
    approver_role: str | None = None
    approver_user_id: UUID | None = None
    escalation_days: int | None = Field(None, ge=0)


class ApprovalLevelRead(PurchaseBaseSchema):
    """Response schema for an approval level."""

    id: UUID
    company_id: UUID
    rule_id: str
    level_number: int
    approver_type: str
    approver_role: str | None
    approver_user_id: str | None
    escalation_days: int
    created_at: datetime


# ---------------------------------------------------------------------------
# ApprovalRecord
# ---------------------------------------------------------------------------


class ApprovalRecordRead(PurchaseBaseSchema):
    """Response schema for an approval record (immutable)."""

    id: UUID
    company_id: UUID
    document_type: str
    document_id: str
    level_number: int
    approver_id: str
    action: str
    comment: str | None
    is_emergency_bypass: bool
    bypass_justification: str | None
    actioned_at: datetime
    created_at: datetime


# ---------------------------------------------------------------------------
# ApprovalAction request bodies
# ---------------------------------------------------------------------------


class ApproveAction(PurchaseBaseSchema):
    """Request body for approving a document at a given level."""

    document_type: str = Field(
        ..., description="PURCHASE_REQUEST / PURCHASE_ORDER / VENDOR_RETURN"
    )
    document_id: UUID
    level_number: int = Field(..., ge=1)
    comment: str | None = Field(None, max_length=2000)

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        if v not in DOCUMENT_TYPES:
            raise ValueError(f"document_type must be one of {DOCUMENT_TYPES}")
        return v


class RejectAction(PurchaseBaseSchema):
    """Request body for rejecting a document (comment is required)."""

    document_type: str = Field(
        ..., description="PURCHASE_REQUEST / PURCHASE_ORDER / VENDOR_RETURN"
    )
    document_id: UUID
    level_number: int = Field(..., ge=1)
    comment: str = Field(
        ..., min_length=1, max_length=2000, description="Rejection reason is mandatory"
    )

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        if v not in DOCUMENT_TYPES:
            raise ValueError(f"document_type must be one of {DOCUMENT_TYPES}")
        return v


class EmergencyBypassAction(PurchaseBaseSchema):
    """Request body for emergency bypass (Purchase Manager only)."""

    document_type: str = Field(
        ..., description="PURCHASE_REQUEST / PURCHASE_ORDER / VENDOR_RETURN"
    )
    document_id: UUID
    justification: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Mandatory justification for bypass",
    )

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        if v not in DOCUMENT_TYPES:
            raise ValueError(f"document_type must be one of {DOCUMENT_TYPES}")
        return v


# ---------------------------------------------------------------------------
# ApprovalDelegate
# ---------------------------------------------------------------------------


class ApprovalDelegateCreate(PurchaseBaseSchema):
    """Create an approval delegation."""

    delegate_id: UUID
    valid_from: datetime
    valid_until: datetime
    document_type: str | None = Field(None, description="NULL = all document types")
    is_active: bool = True

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str | None) -> str | None:
        if v is not None and v not in DOCUMENT_TYPES:
            raise ValueError(f"document_type must be one of {DOCUMENT_TYPES} or null")
        return v


class ApprovalDelegateUpdate(PurchaseBaseSchema):
    """Update an approval delegation."""

    valid_from: datetime | None = None
    valid_until: datetime | None = None
    document_type: str | None = None
    is_active: bool | None = None


class ApprovalDelegateRead(PurchaseBaseSchema):
    """Response schema for an approval delegation."""

    id: UUID
    company_id: UUID
    delegator_id: str
    delegate_id: str
    valid_from: datetime
    valid_until: datetime
    document_type: str | None
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# ApprovalStatus (approval engine status query)
# ---------------------------------------------------------------------------


class ApprovalStatusRead(PurchaseBaseSchema):
    """Current approval status for a document."""

    document_type: str
    document_id: str
    is_approved: bool
    is_rejected: bool
    current_level: int
    records: list[ApprovalRecordRead]


# ---------------------------------------------------------------------------
# RouteForApprovalResult (returned by route_for_approval)
# ---------------------------------------------------------------------------


class RouteForApprovalResult(PurchaseBaseSchema):
    """Result of routing a document for approval."""

    document_type: str
    document_id: str
    auto_approved: bool
    matrix_found: bool
    applicable_rule_id: str | None
    required_levels: list[ApprovalLevelRead]
    message: str
