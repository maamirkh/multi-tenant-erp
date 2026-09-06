"""Sales Return repositories — Phase 7.

Repositories:
  SalesReturnRepository  — CRUD + status/customer/order filters; tenant-safe
  ReturnLineRepository   — CRUD + return_id filter

All queries enforce company_id isolation.

Spec ref: specs/007-sales-management/plan.md §Repository Layer
Task: T191
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from modules.sales.models.sales_return import ReturnLine, SalesReturn


class SalesReturnRepository:
    """Repository for SalesReturn aggregate root."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id_or_none(
        self,
        return_id: UUID,
        company_id: UUID,
    ) -> SalesReturn | None:
        return (
            self._db.query(SalesReturn)
            .filter(
                SalesReturn.id == return_id,
                SalesReturn.company_id == company_id,
                SalesReturn.is_deleted.is_(False),
            )
            .first()
        )

    def get_by_number(
        self,
        company_id: UUID,
        return_number: str,
    ) -> SalesReturn | None:
        return (
            self._db.query(SalesReturn)
            .filter(
                SalesReturn.company_id == company_id,
                SalesReturn.return_number == return_number,
                SalesReturn.is_deleted.is_(False),
            )
            .first()
        )

    def list_for_company(
        self,
        company_id: UUID,
        *,
        customer_id: str | None = None,
        status: str | None = None,
        order_id: str | None = None,
        resolution_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SalesReturn], int]:
        q = self._db.query(SalesReturn).filter(
            SalesReturn.company_id == company_id,
            SalesReturn.is_deleted.is_(False),
        )
        if customer_id:
            q = q.filter(SalesReturn.customer_id == customer_id)
        if status:
            q = q.filter(SalesReturn.status == status)
        if order_id:
            q = q.filter(SalesReturn.order_id == order_id)
        if resolution_type:
            q = q.filter(SalesReturn.resolution_type == resolution_type)

        total = q.count()
        items = (
            q.order_by(SalesReturn.return_number.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return items, total


class ReturnLineRepository:
    """Repository for ReturnLine owned entities."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_return(
        self,
        company_id: UUID,
        return_id: UUID,
    ) -> list[ReturnLine]:
        return (
            self._db.query(ReturnLine)
            .filter(
                ReturnLine.company_id == company_id,
                ReturnLine.return_id == str(return_id),
                ReturnLine.is_deleted.is_(False),
            )
            .all()
        )

    def get_by_id_or_none(
        self,
        line_id: UUID,
        company_id: UUID,
    ) -> ReturnLine | None:
        return (
            self._db.query(ReturnLine)
            .filter(
                ReturnLine.id == line_id,
                ReturnLine.company_id == company_id,
                ReturnLine.is_deleted.is_(False),
            )
            .first()
        )
