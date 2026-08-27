"""InstallmentAllocationReferenceRepository — append-only data access.

Deliberately NOT a ``BaseRepository`` subclass — that base class's
``create()``/``update()`` methods commit internally and expose mutation
this table must never have (BR-INST-017: never updated or deleted, a
reversal always inserts a new row). Matches
``InstallmentAuditLogRepository``'s identical precedent.

Spec ref: specs/010-installments/data-model.md
"InstallmentAllocationReference"; specs/010-installments/plan.md §21.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from modules.installments.models.allocation_reference import (
    InstallmentAllocationReference,
)


class InstallmentAllocationReferenceRepository:
    """Append-only data access for ``installment_allocation_references``."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self, reference: InstallmentAllocationReference
    ) -> InstallmentAllocationReference:
        """Stage a new allocation-reference row for insert. Flush only —
        the caller commits together with the Accounting effect it
        explains (plan.md §21)."""
        self.db.add(reference)
        self.db.flush()
        return reference

    def list_for_contract(
        self, company_id: UUID, contract_id: UUID
    ) -> list[InstallmentAllocationReference]:
        stmt = (
            select(InstallmentAllocationReference)
            .where(InstallmentAllocationReference.company_id == company_id)
            .where(InstallmentAllocationReference.contract_id == contract_id)
            .order_by(InstallmentAllocationReference.allocated_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_for_schedule_line(
        self, company_id: UUID, schedule_line_id: UUID
    ) -> list[InstallmentAllocationReference]:
        stmt = (
            select(InstallmentAllocationReference)
            .where(InstallmentAllocationReference.company_id == company_id)
            .where(InstallmentAllocationReference.schedule_line_id == schedule_line_id)
            .order_by(InstallmentAllocationReference.allocated_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_net_allocated_by_line(
        self, company_id: UUID, schedule_line_ids: list[UUID]
    ) -> dict[UUID, Decimal]:
        """Net allocated amount per schedule line (non-reversal minus
        reversal), for every line id in ``schedule_line_ids`` that has at
        least one reference row. Lines with no rows at all are simply
        absent from the returned mapping (caller treats missing as zero)."""
        if not schedule_line_ids:
            return {}
        signed_amount = func.sum(
            case(
                (
                    InstallmentAllocationReference.is_reversal,
                    -InstallmentAllocationReference.allocated_amount,
                ),
                else_=InstallmentAllocationReference.allocated_amount,
            )
        )
        stmt = (
            select(InstallmentAllocationReference.schedule_line_id, signed_amount)
            .where(InstallmentAllocationReference.company_id == company_id)
            .where(
                InstallmentAllocationReference.schedule_line_id.in_(schedule_line_ids)
            )
            .group_by(InstallmentAllocationReference.schedule_line_id)
        )
        return dict(self.db.execute(stmt).all())

    def get_by_payment_id(
        self, company_id: UUID, accounting_payment_id: UUID
    ) -> list[InstallmentAllocationReference]:
        """All (non-reversal) allocation-reference rows created by a
        single collection event — used by ``reverse_collection()`` (T123)
        to find what to reverse."""
        stmt = (
            select(InstallmentAllocationReference)
            .where(InstallmentAllocationReference.company_id == company_id)
            .where(
                InstallmentAllocationReference.accounting_payment_id
                == accounting_payment_id
            )
            .where(InstallmentAllocationReference.is_reversal == False)  # noqa: E712
            .order_by(InstallmentAllocationReference.allocation_order)
        )
        return list(self.db.execute(stmt).scalars().all())
