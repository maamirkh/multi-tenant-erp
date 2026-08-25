"""Repository for the InstallmentContract aggregate root.

Spec ref: specs/010-installments/data-model.md "InstallmentContract";
specs/010-installments/plan.md §19 (Concurrency Strategy).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.installments.exceptions import InstallmentConcurrentModificationError
from modules.installments.models.contract import InstallmentContract


class InstallmentContractRepository(BaseRepository[InstallmentContract]):
    """Data-access layer for ``installment_contracts``."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=InstallmentContract)

    def get_by_id_locked(
        self, id: UUID, company_id: UUID
    ) -> InstallmentContract | None:
        """Lock the contract row for the duration of the caller's
        transaction — used by every money-mutating serialized operation
        (collection, settlement, write-off, plan.md §19)."""
        stmt = (
            select(InstallmentContract)
            .where(InstallmentContract.id == id)
            .where(InstallmentContract.company_id == company_id)
            .where(InstallmentContract.is_deleted == False)  # noqa: E712
            .with_for_update()
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def find_active_by_sales_invoice(
        self, company_id: UUID, sales_invoice_id: UUID
    ) -> InstallmentContract | None:
        """Return the non-terminal contract for this invoice, if any —
        the service-layer pre-check for BR-INST-042's one-contract-per-
        obligation invariant (the DB partial unique index is the real
        backstop, never bypassed by this check alone)."""
        stmt = (
            select(InstallmentContract)
            .where(InstallmentContract.company_id == company_id)
            .where(InstallmentContract.sales_invoice_id == sales_invoice_id)
            .where(
                InstallmentContract.status.notin_(
                    ("CANCELLED", "COMPLETED", "WRITTEN_OFF")
                )
            )
            .where(InstallmentContract.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def update_with_version_check(
        self,
        *,
        contract_id: UUID,
        company_id: UUID,
        expected_version: int,
        **fields: object,
    ) -> InstallmentContract:
        """Conditional ``UPDATE ... WHERE version = :expected`` for
        optimistic-lock lifecycle transitions (approve/reject, plan.md
        §19) — mirrors ``AdjustmentRepository.update_status()``'s exact
        pattern: a single atomic UPDATE with ``RETURNING``, never a
        separate SELECT-then-UPDATE.

        Raises:
            InstallmentConcurrentModificationError: zero rows matched —
                the contract does not exist, belongs to another tenant,
                or a concurrent writer already changed its version.
        """
        values: dict[str, object] = {
            "version": expected_version + 1,
            **fields,
        }
        stmt = (
            update(InstallmentContract)
            .where(InstallmentContract.id == contract_id)
            .where(InstallmentContract.company_id == company_id)
            .where(InstallmentContract.version == expected_version)
            .where(InstallmentContract.is_deleted == False)  # noqa: E712
            .values(**values)
            .returning(InstallmentContract)
        )
        result = self.db.execute(stmt).scalars().one_or_none()
        if result is None:
            raise InstallmentConcurrentModificationError(str(contract_id))
        return result
