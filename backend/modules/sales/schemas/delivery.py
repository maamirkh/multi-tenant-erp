"""Delivery Note Pydantic schemas — Phase 5.

Schemas:
  DeliveryNoteLineCreate — create a delivery note line
  DeliveryNoteLineRead   — full line response
  DeliveryNoteCreate     — create a new delivery note (DRAFT)
  DeliveryNoteRead       — full delivery note response
  DeliveryNoteListItem   — minimal representation for list views
  DeliveryNoteDispatch   — dispatch payload (DRAFT → DISPATCHED)

Spec ref: specs/007-sales-management/plan.md §API Contracts
Task: T145
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import field_validator

from modules.sales.schemas.base import SalesBaseSchema

# ---------------------------------------------------------------------------
# DeliveryNoteLine schemas
# ---------------------------------------------------------------------------


class DeliveryNoteLineCreate(SalesBaseSchema):
    order_line_id: UUID
    product_id: UUID | None = None
    description: str
    quantity_dispatched: Decimal
    unit_of_measure: str
    notes: str | None = None

    @field_validator("quantity_dispatched")
    @classmethod
    def must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("quantity_dispatched must be positive")
        return v


class DeliveryNoteLineRead(SalesBaseSchema):
    id: UUID
    company_id: UUID
    delivery_note_id: str
    order_line_id: str
    product_id: str | None
    description: str
    quantity_dispatched: Decimal
    unit_of_measure: str
    notes: str | None
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None


# ---------------------------------------------------------------------------
# DeliveryNote create / update
# ---------------------------------------------------------------------------


class DeliveryNoteCreate(SalesBaseSchema):
    order_id: UUID
    shipping_address_id: UUID | None = None
    expected_delivery_date: str | None = None
    carrier: str | None = None
    tracking_number: str | None = None
    total_packages: int | None = None
    total_weight: Decimal | None = None
    internal_notes: str | None = None
    lines: list[DeliveryNoteLineCreate]

    @field_validator("lines")
    @classmethod
    def must_have_lines(
        cls, v: list[DeliveryNoteLineCreate]
    ) -> list[DeliveryNoteLineCreate]:
        if not v:
            raise ValueError("Delivery note must have at least one line")
        return v


class DeliveryNoteDispatch(SalesBaseSchema):
    """Payload for DRAFT → DISPATCHED transition."""

    dispatch_date: str
    carrier: str | None = None
    tracking_number: str | None = None
    total_packages: int | None = None
    total_weight: Decimal | None = None


# ---------------------------------------------------------------------------
# DeliveryNote read
# ---------------------------------------------------------------------------


class DeliveryNoteRead(SalesBaseSchema):
    id: UUID
    company_id: UUID
    delivery_number: str
    order_id: str
    customer_id: str
    shipping_address_id: str | None
    dispatch_date: str | None
    expected_delivery_date: str | None
    carrier: str | None
    tracking_number: str | None
    status: str
    total_packages: int | None
    total_weight: Decimal | None
    dispatched_by: str | None
    internal_notes: str | None
    version: int
    is_deleted: bool
    created_at: datetime | None
    updated_at: datetime | None
    lines: list[DeliveryNoteLineRead] = []


class DeliveryNoteListItem(SalesBaseSchema):
    id: UUID
    delivery_number: str
    order_id: str
    customer_id: str
    status: str
    dispatch_date: str | None
    carrier: str | None
    tracking_number: str | None
    total_packages: int | None
    created_at: datetime | None


class DeliveryNoteListResponse(SalesBaseSchema):
    items: list[DeliveryNoteListItem]
    total: int
    limit: int
    offset: int
