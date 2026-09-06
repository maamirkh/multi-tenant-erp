"""CurrencyService — currency registry and exchange rate management.

Responsibilities:
  - Manage the global ISO 4217 currency registry (``list_currencies``,
    ``create_currency``).
  - Manage company-scoped exchange rates (``set_exchange_rate``,
    ``list_rates``).
  - Resolve the applicable rate for a currency pair/date with 7-day
    fallback (``get_rate`` — research.md Decision 8).

Spec ref: specs/008-accounting-finance/tasks.md T032
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from modules.accounting.exceptions import ExchangeRateNotFoundError
from modules.accounting.models.foundation import Currency, ExchangeRate
from modules.accounting.repositories.foundation import (
    CurrencyRepository,
    ExchangeRateRepository,
)

logger = logging.getLogger(__name__)

DEFAULT_LOOKBACK_DAYS = 7


class CurrencyService:
    """Service for currency registry and exchange rate management.

    Args:
        db:                SQLAlchemy session.
        currency_repo:      ``CurrencyRepository`` instance (injected).
        exchange_rate_repo: ``ExchangeRateRepository`` instance (injected).
    """

    def __init__(
        self,
        db: Session,
        currency_repo: CurrencyRepository,
        exchange_rate_repo: ExchangeRateRepository,
    ) -> None:
        self.db = db
        self._currency_repo = currency_repo
        self._exchange_rate_repo = exchange_rate_repo

    # ------------------------------------------------------------------
    # Currency registry
    # ------------------------------------------------------------------

    def list_currencies(self, active_only: bool = False) -> list[Currency]:
        """Return the global currency registry.

        Args:
            active_only: If True, return only currencies with ``is_active=True``.
        """
        if active_only:
            return self._currency_repo.find_all_active()
        return self._currency_repo.list_all()

    def create_currency(
        self,
        iso_code: str,
        name: str,
        symbol: str,
        decimal_places: int = 2,
    ) -> Currency:
        """Create a new currency in the global registry.

        Raises:
            ValueError: If a currency with this ISO code already exists.
        """
        normalized_code = iso_code.upper()
        existing = self._currency_repo.find_by_code(normalized_code)
        if existing is not None:
            raise ValueError(f"Currency '{normalized_code}' already exists.")

        currency = Currency(
            iso_code=normalized_code,
            name=name,
            symbol=symbol,
            decimal_places=decimal_places,
            is_active=True,
        )
        return self._currency_repo.create(currency)

    # ------------------------------------------------------------------
    # Exchange rates
    # ------------------------------------------------------------------

    def set_exchange_rate(
        self,
        company_id: UUID,
        from_currency_code: str,
        to_currency_code: str,
        rate_date: date,
        rate: Decimal,
        rate_type: str = "SPOT",
        created_by: UUID | None = None,
    ) -> ExchangeRate:
        """Record an exchange rate for a currency pair on a given date.

        Rates are immutable once set (research.md Decision 8) — this always
        inserts a new row rather than updating an existing one, so historical
        postings that locked in a prior rate are never retroactively altered.
        """
        exchange_rate = ExchangeRate(
            company_id=company_id,
            from_currency_code=from_currency_code.upper(),
            to_currency_code=to_currency_code.upper(),
            rate_date=rate_date,
            rate=rate,
            rate_type=rate_type,
            created_by=created_by,
        )
        return self._exchange_rate_repo.create(exchange_rate)

    def get_rate(
        self,
        company_id: UUID,
        from_currency_code: str,
        to_currency_code: str,
        rate_date: date,
        rate_type: str = "SPOT",
    ) -> Decimal:
        """Resolve the applicable exchange rate for a currency pair/date.

        Resolution order (research.md Decision 8):
          1. Exact match on ``rate_date``.
          2. Most recent rate within a 7-day lookback window.
          3. Raise ``ExchangeRateNotFoundError`` if neither is found.
        """
        if from_currency_code.upper() == to_currency_code.upper():
            return Decimal("1.0")

        record = self._exchange_rate_repo.get_rate_for_date(
            company_id=company_id,
            from_currency_code=from_currency_code,
            to_currency_code=to_currency_code,
            rate_date=rate_date,
            rate_type=rate_type,
            lookback_days=DEFAULT_LOOKBACK_DAYS,
        )
        if record is None:
            raise ExchangeRateNotFoundError(
                from_currency_code=from_currency_code.upper(),
                to_currency_code=to_currency_code.upper(),
                rate_date=rate_date.isoformat(),
            )
        return record.rate

    def list_rates(
        self,
        company_id: UUID,
        from_currency_code: str | None = None,
        to_currency_code: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[ExchangeRate]:
        """List exchange rates for a company, optionally filtered by pair/range."""
        if from_currency_code and to_currency_code and start_date and end_date:
            return self._exchange_rate_repo.get_rates_for_period(
                company_id=company_id,
                from_currency_code=from_currency_code,
                to_currency_code=to_currency_code,
                start_date=start_date,
                end_date=end_date,
            )
        return self._exchange_rate_repo.list_all(company_id=company_id)
