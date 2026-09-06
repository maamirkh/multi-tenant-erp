"""Repositories for Tax Engine entities — Phase 11.

  TaxCodeRepository      — tax code CRUD + code/type/applicability lookups
  TaxRateRepository       — rate-history CRUD + effective-date resolution
  TaxGroupRepository      — tax group CRUD
  TaxGroupLineRepository  — group membership CRUD

Spec ref: specs/008-accounting-finance/tasks.md T224-T227
Data model: specs/008-accounting-finance/data-model.md line 512 (TaxCodeRepository)
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.models.tax import TaxCode, TaxGroup, TaxGroupLine, TaxRate
from modules.accounting.repositories import BaseAccountingRepository


class TaxCodeRepository(BaseAccountingRepository[TaxCode]):
    """Data-access layer for the ``accounting_tax_codes`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=TaxCode)

    def find_by_code(self, company_id: UUID, tax_code: str) -> TaxCode | None:
        stmt = (
            select(TaxCode)
            .where(TaxCode.company_id == company_id)
            .where(TaxCode.tax_code == tax_code)
            .where(TaxCode.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_all(self, company_id: UUID, active_only: bool = False) -> list[TaxCode]:
        stmt = (
            select(TaxCode)
            .where(TaxCode.company_id == company_id)
            .where(TaxCode.is_deleted == False)  # noqa: E712
            .order_by(TaxCode.tax_code)
        )
        if active_only:
            stmt = stmt.where(TaxCode.is_active == True)  # noqa: E712
        return list(self.db.execute(stmt).scalars().all())

    def find_active_by_type(self, company_id: UUID, tax_type: str) -> list[TaxCode]:
        stmt = (
            select(TaxCode)
            .where(TaxCode.company_id == company_id)
            .where(TaxCode.tax_type == tax_type)
            .where(TaxCode.is_active == True)  # noqa: E712
            .where(TaxCode.is_deleted == False)  # noqa: E712
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_applicable(self, company_id: UUID, applicability: str) -> list[TaxCode]:
        """Active tax codes usable for a SALES or PURCHASES transaction —
        includes codes explicitly scoped to that side plus BOTH-scoped codes.
        """
        stmt = (
            select(TaxCode)
            .where(TaxCode.company_id == company_id)
            .where(TaxCode.is_active == True)  # noqa: E712
            .where(TaxCode.is_deleted == False)  # noqa: E712
            .where(TaxCode.applicability.in_([applicability, "BOTH"]))
        )
        return list(self.db.execute(stmt).scalars().all())


class TaxRateRepository(BaseAccountingRepository[TaxRate]):
    """Data-access layer for the ``accounting_tax_rates`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=TaxRate)

    def find_by_tax_code(self, company_id: UUID, tax_code_id: UUID) -> list[TaxRate]:
        stmt = (
            select(TaxRate)
            .where(TaxRate.company_id == company_id)
            .where(TaxRate.tax_code_id == tax_code_id)
            .where(TaxRate.is_deleted == False)  # noqa: E712
            .order_by(TaxRate.effective_from)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_effective_at(
        self, company_id: UUID, tax_code_id: UUID, as_of_date: date
    ) -> TaxRate | None:
        """The single rate whose ``[effective_from, effective_to]`` range
        covers ``as_of_date`` (data-model.md §2.9: "Tax calculations use
        the rate effective on the transaction date").
        """
        stmt = (
            select(TaxRate)
            .where(TaxRate.company_id == company_id)
            .where(TaxRate.tax_code_id == tax_code_id)
            .where(TaxRate.is_deleted == False)  # noqa: E712
            .where(TaxRate.effective_from <= as_of_date)
            .where(
                (TaxRate.effective_to.is_(None)) | (TaxRate.effective_to >= as_of_date)
            )
        )
        return self.db.execute(stmt).scalars().one_or_none()


class TaxGroupRepository(BaseAccountingRepository[TaxGroup]):
    """Data-access layer for the ``accounting_tax_groups`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=TaxGroup)

    def find_by_code(self, company_id: UUID, group_code: str) -> TaxGroup | None:
        stmt = (
            select(TaxGroup)
            .where(TaxGroup.company_id == company_id)
            .where(TaxGroup.group_code == group_code)
            .where(TaxGroup.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_all(self, company_id: UUID, active_only: bool = False) -> list[TaxGroup]:
        stmt = (
            select(TaxGroup)
            .where(TaxGroup.company_id == company_id)
            .where(TaxGroup.is_deleted == False)  # noqa: E712
            .order_by(TaxGroup.group_code)
        )
        if active_only:
            stmt = stmt.where(TaxGroup.is_active == True)  # noqa: E712
        return list(self.db.execute(stmt).scalars().all())


class TaxGroupLineRepository(BaseAccountingRepository[TaxGroupLine]):
    """Data-access layer for the ``accounting_tax_group_lines`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=TaxGroupLine)

    def find_by_group(self, company_id: UUID, tax_group_id: UUID) -> list[TaxGroupLine]:
        stmt = (
            select(TaxGroupLine)
            .where(TaxGroupLine.company_id == company_id)
            .where(TaxGroupLine.tax_group_id == tax_group_id)
            .where(TaxGroupLine.is_deleted == False)  # noqa: E712
            .order_by(TaxGroupLine.display_order)
        )
        return list(self.db.execute(stmt).scalars().all())
