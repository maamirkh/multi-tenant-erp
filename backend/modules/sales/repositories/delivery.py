"""Delivery Note repositories — Phase 5.

Repositories:
  DeliveryNoteRepository     — CRUD + order filter, status filter, date range
  DeliveryNoteLineRepository — CRUD + delivery note filter

All queries enforce company_id isolation.

Spec ref: specs/007-sales-management/plan.md §Repository Layer
Task: T144
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from modules.sales.models.delivery import DeliveryNote, DeliveryNoteLine


class DeliveryNoteRepository:
    """Repository for DeliveryNote aggregate root."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id_or_none(
        self,
        delivery_note_id: UUID,
        company_id: UUID,
    ) -> DeliveryNote | None:
        return (
            self._db.query(DeliveryNote)
            .filter(
                DeliveryNote.id == delivery_note_id,
                DeliveryNote.company_id == company_id,
                DeliveryNote.is_deleted.is_(False),
            )
            .first()
        )

    def get_by_number(
        self,
        company_id: UUID,
        delivery_number: str,
    ) -> DeliveryNote | None:
        return (
            self._db.query(DeliveryNote)
            .filter(
                DeliveryNote.company_id == company_id,
                DeliveryNote.delivery_number == delivery_number,
                DeliveryNote.is_deleted.is_(False),
            )
            .first()
        )

    def list_for_company(
        self,
        company_id: UUID,
        *,
        order_id: UUID | None = None,
        status: str | None = None,
        customer_id: UUID | None = None,
        dispatch_date_from: str | None = None,
        dispatch_date_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DeliveryNote]:
        q = self._db.query(DeliveryNote).filter(
            DeliveryNote.company_id == company_id,
            DeliveryNote.is_deleted.is_(False),
        )
        if order_id is not None:
            q = q.filter(DeliveryNote.order_id == str(order_id))
        if status is not None:
            q = q.filter(DeliveryNote.status == status)
        if customer_id is not None:
            q = q.filter(DeliveryNote.customer_id == str(customer_id))
        if dispatch_date_from is not None:
            q = q.filter(DeliveryNote.dispatch_date >= dispatch_date_from)
        if dispatch_date_to is not None:
            q = q.filter(DeliveryNote.dispatch_date <= dispatch_date_to)
        return (
            q.order_by(DeliveryNote.created_at.desc()).offset(offset).limit(limit).all()
        )

    def count_for_company(
        self,
        company_id: UUID,
        *,
        order_id: UUID | None = None,
        status: str | None = None,
    ) -> int:
        q = self._db.query(func.count(DeliveryNote.id)).filter(
            DeliveryNote.company_id == company_id,
            DeliveryNote.is_deleted.is_(False),
        )
        if order_id is not None:
            q = q.filter(DeliveryNote.order_id == str(order_id))
        if status is not None:
            q = q.filter(DeliveryNote.status == status)
        return q.scalar() or 0

    def list_for_order(
        self,
        company_id: UUID,
        order_id: UUID,
    ) -> list[DeliveryNote]:
        """Return all non-cancelled DNs for a given order."""
        return (
            self._db.query(DeliveryNote)
            .filter(
                DeliveryNote.company_id == company_id,
                DeliveryNote.order_id == str(order_id),
                DeliveryNote.status != "CANCELLED",
                DeliveryNote.is_deleted.is_(False),
            )
            .all()
        )

    def get_total_dispatched_for_order_line(
        self,
        company_id: UUID,
        order_line_id: UUID,
    ) -> Decimal:
        """Return the total quantity dispatched across all non-cancelled DNs for a given order line.

        Used for cumulative quantity validation before creating a new DN line.
        """
        result = (
            self._db.query(func.sum(DeliveryNoteLine.quantity_dispatched))
            .join(
                DeliveryNote,
                DeliveryNote.id == DeliveryNoteLine.delivery_note_id,
            )
            .filter(
                DeliveryNoteLine.company_id == company_id,
                DeliveryNoteLine.order_line_id == str(order_line_id),
                DeliveryNote.status != "CANCELLED",
                DeliveryNoteLine.is_deleted.is_(False),
                DeliveryNote.is_deleted.is_(False),
            )
            .scalar()
        )
        return Decimal(str(result)) if result is not None else Decimal("0")


class DeliveryNoteLineRepository:
    """Repository for DeliveryNoteLine entities."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_delivery_note(
        self,
        company_id: UUID,
        delivery_note_id: UUID,
    ) -> list[DeliveryNoteLine]:
        return (
            self._db.query(DeliveryNoteLine)
            .filter(
                DeliveryNoteLine.company_id == company_id,
                DeliveryNoteLine.delivery_note_id == str(delivery_note_id),
                DeliveryNoteLine.is_deleted.is_(False),
            )
            .order_by(DeliveryNoteLine.created_at.asc())
            .all()
        )

    def get_by_id_or_none(
        self,
        line_id: UUID,
        company_id: UUID,
    ) -> DeliveryNoteLine | None:
        return (
            self._db.query(DeliveryNoteLine)
            .filter(
                DeliveryNoteLine.id == line_id,
                DeliveryNoteLine.company_id == company_id,
                DeliveryNoteLine.is_deleted.is_(False),
            )
            .first()
        )
