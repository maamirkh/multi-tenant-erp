"""Repository for the InstallmentContract aggregate root.

Spec ref: specs/010-installments/data-model.md "InstallmentContract";
specs/010-installments/plan.md §19 (Concurrency Strategy).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
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

    def list_filtered(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        plan_template_id: UUID | None = None,
        customer_id: UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[InstallmentContract], int]:
        """Paginated contract listing with optional status/template/
        customer filters — the Contract Register report's base query
        (tasks.md T204), the Plan/Template Performance report's grouping
        input, and the customer statement document's per-customer
        lookup (T206). Always ``company_id``-scoped; excludes
        soft-deleted rows, matching ``BaseRepository.list()``'s own
        convention."""
        base_stmt = select(InstallmentContract).where(
            InstallmentContract.company_id == company_id,
            InstallmentContract.is_deleted == False,  # noqa: E712
        )
        if status is not None:
            base_stmt = base_stmt.where(InstallmentContract.status == status)
        if plan_template_id is not None:
            base_stmt = base_stmt.where(
                InstallmentContract.plan_template_id == plan_template_id
            )
        if customer_id is not None:
            base_stmt = base_stmt.where(InstallmentContract.customer_id == customer_id)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total: int = self.db.execute(count_stmt).scalar_one()

        rows_stmt = (
            base_stmt.order_by(InstallmentContract.contract_date.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list(self.db.execute(rows_stmt).scalars().all())
        return items, total

    def count_by_status(self, company_id: UUID) -> dict[str, int]:
        """One ``GROUP BY`` query for every dashboard KPI that needs a
        contract count by lifecycle status (active contract count,
        defaulted/written-off counts, tasks.md T205) — never a Python
        loop over individually-fetched contracts."""
        stmt = (
            select(InstallmentContract.status, func.count())
            .where(InstallmentContract.company_id == company_id)
            .where(InstallmentContract.is_deleted == False)  # noqa: E712
            .group_by(InstallmentContract.status)
        )
        return {status: count for status, count in self.db.execute(stmt).all()}

    def aggregate_by_plan_template(
        self, company_id: UUID
    ) -> list[tuple[UUID | None, int, Decimal]]:
        """One ``GROUP BY`` query for the Plan/Template Performance
        report (tasks.md T204): ``(plan_template_id, contract_count,
        total_contractual_amount)`` per template, ``plan_template_id IS
        NULL`` grouping custom (non-template) contracts together."""
        stmt = (
            select(
                InstallmentContract.plan_template_id,
                func.count(),
                func.coalesce(func.sum(InstallmentContract.contractual_total), 0),
            )
            .where(InstallmentContract.company_id == company_id)
            .where(InstallmentContract.is_deleted == False)  # noqa: E712
            .group_by(InstallmentContract.plan_template_id)
        )
        return [
            (plan_template_id, count, total)
            for plan_template_id, count, total in self.db.execute(stmt).all()
        ]
