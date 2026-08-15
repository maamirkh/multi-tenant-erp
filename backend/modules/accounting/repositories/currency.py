"""Repository for currency revaluation runs — Phase 12.

Spec ref: specs/008-accounting-finance/tasks.md T247
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.models.currency import CurrencyRevaluationRun
from modules.accounting.repositories import BaseAccountingRepository


class CurrencyRevaluationRunRepository(
    BaseAccountingRepository[CurrencyRevaluationRun]
):
    """Data-access layer for the ``accounting_currency_revaluations`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CurrencyRevaluationRun)

    def list_all(self, company_id: UUID) -> list[CurrencyRevaluationRun]:
        """Return every revaluation run for a company, most recent first."""
        stmt = (
            select(CurrencyRevaluationRun)
            .where(CurrencyRevaluationRun.company_id == company_id)
            .where(CurrencyRevaluationRun.is_deleted == False)  # noqa: E712
            .order_by(CurrencyRevaluationRun.revaluation_date.desc())
        )
        return list(self.db.execute(stmt).scalars().all())
