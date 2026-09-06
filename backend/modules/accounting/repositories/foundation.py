"""Repositories for accounting foundation entities — Phase 1.

  AccountingConfigurationRepository — one-row-per-company settings
  CurrencyRepository                — global reference data (no company_id scoping)
  ExchangeRateRepository            — company-scoped exchange rate history

Spec ref: specs/008-accounting-finance/tasks.md T034
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.accounting.models.foundation import (
    AccountingConfiguration,
    Currency,
    ExchangeRate,
)
from modules.accounting.repositories import BaseAccountingRepository

logger = logging.getLogger(__name__)


class AccountingConfigurationRepository(
    BaseAccountingRepository[AccountingConfiguration]
):
    """Data-access layer for the ``accounting_configurations`` table.

    One configuration record per company.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=AccountingConfiguration)

    def get_for_company(self, company_id: UUID) -> AccountingConfiguration | None:
        """Return the accounting configuration for this company, or None."""
        stmt = (
            select(AccountingConfiguration)
            .where(AccountingConfiguration.company_id == company_id)
            .where(AccountingConfiguration.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()


logger = logging.getLogger(__name__)


class CurrencyRepository:
    """Data-access layer for the global ``accounting_currencies`` table.

    Currency is explicitly global (not company-scoped — see
    ``models.foundation.Currency`` docstring), so this repository does not
    extend ``BaseAccountingRepository`` (which enforces mandatory
    ``company_id`` isolation). All methods here operate across the entire
    shared currency registry.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, entity: Currency) -> Currency:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def find_by_code(self, iso_code: str) -> Currency | None:
        """Return the currency with the given ISO code, or None."""
        stmt = select(Currency).where(Currency.iso_code == iso_code.upper())
        return self.db.execute(stmt).scalars().one_or_none()

    def find_all_active(self) -> list[Currency]:
        """Return all active currencies, ordered by ISO code."""
        stmt = (
            select(Currency)
            .where(Currency.is_active == True)  # noqa: E712
            .order_by(Currency.iso_code)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_all(self) -> list[Currency]:
        """Return all currencies (active and inactive), ordered by ISO code."""
        stmt = select(Currency).order_by(Currency.iso_code)
        return list(self.db.execute(stmt).scalars().all())


class ExchangeRateRepository(BaseAccountingRepository[ExchangeRate]):
    """Data-access layer for the company-scoped ``accounting_exchange_rates`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=ExchangeRate)

    def get_rate_for_date(
        self,
        company_id: UUID,
        from_currency_code: str,
        to_currency_code: str,
        rate_date: date,
        rate_type: str = "SPOT",
        lookback_days: int = 7,
    ) -> ExchangeRate | None:
        """Return the applicable exchange rate for a date, with fallback.

        Resolution order (research.md Decision 8):
          1. Exact match on ``rate_date``.
          2. Most recent rate within ``lookback_days`` prior to ``rate_date``.
          3. ``None`` if neither is found — caller raises the domain error.
        """
        exact_stmt = (
            select(ExchangeRate)
            .where(ExchangeRate.company_id == company_id)
            .where(ExchangeRate.from_currency_code == from_currency_code.upper())
            .where(ExchangeRate.to_currency_code == to_currency_code.upper())
            .where(ExchangeRate.rate_date == rate_date)
            .where(ExchangeRate.rate_type == rate_type)
            .where(ExchangeRate.is_deleted == False)  # noqa: E712
        )
        exact = self.db.execute(exact_stmt).scalars().one_or_none()
        if exact is not None:
            return exact

        earliest_allowed = rate_date - timedelta(days=lookback_days)
        fallback_stmt = (
            select(ExchangeRate)
            .where(ExchangeRate.company_id == company_id)
            .where(ExchangeRate.from_currency_code == from_currency_code.upper())
            .where(ExchangeRate.to_currency_code == to_currency_code.upper())
            .where(ExchangeRate.rate_type == rate_type)
            .where(ExchangeRate.rate_date >= earliest_allowed)
            .where(ExchangeRate.rate_date < rate_date)
            .where(ExchangeRate.is_deleted == False)  # noqa: E712
            .order_by(ExchangeRate.rate_date.desc())
            .limit(1)
        )
        return self.db.execute(fallback_stmt).scalars().one_or_none()

    def get_rates_for_period(
        self,
        company_id: UUID,
        from_currency_code: str,
        to_currency_code: str,
        start_date: date,
        end_date: date,
    ) -> list[ExchangeRate]:
        """Return all rates for a currency pair within a date range."""
        stmt = (
            select(ExchangeRate)
            .where(ExchangeRate.company_id == company_id)
            .where(ExchangeRate.from_currency_code == from_currency_code.upper())
            .where(ExchangeRate.to_currency_code == to_currency_code.upper())
            .where(ExchangeRate.rate_date >= start_date)
            .where(ExchangeRate.rate_date <= end_date)
            .where(ExchangeRate.is_deleted == False)  # noqa: E712
            .order_by(ExchangeRate.rate_date)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_all(self, company_id: UUID) -> list[ExchangeRate]:
        """Return all exchange rates for a company, most recent first."""
        stmt = (
            select(ExchangeRate)
            .where(ExchangeRate.company_id == company_id)
            .where(ExchangeRate.is_deleted == False)  # noqa: E712
            .order_by(ExchangeRate.rate_date.desc())
        )
        return list(self.db.execute(stmt).scalars().all())
