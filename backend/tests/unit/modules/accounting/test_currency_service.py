"""Unit tests for CurrencyService.get_rate().

Tests:
  - Exact date match returns the recorded rate
  - No exact match falls back to the most recent rate within 7 days
  - No rate at all (exact or fallback) raises ExchangeRateNotFoundError
  - Same-currency pair always returns rate 1.0 without a DB lookup

Spec ref: specs/008-accounting-finance/tasks.md T046
Research ref: specs/008-accounting-finance/research.md Decision 8
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.accounting.exceptions import ExchangeRateNotFoundError
from modules.accounting.repositories.foundation import (
    CurrencyRepository,
    ExchangeRateRepository,
)
from modules.accounting.services.currency_service import CurrencyService


@pytest.fixture
def currency_service(db_session: Session) -> CurrencyService:
    return CurrencyService(
        db=db_session,
        currency_repo=CurrencyRepository(db_session),
        exchange_rate_repo=ExchangeRateRepository(db_session),
    )


class TestGetRateSameCurrency:
    def test_same_currency_returns_one_without_lookup(
        self, currency_service: CurrencyService
    ) -> None:
        rate = currency_service.get_rate(
            company_id=uuid4(),
            from_currency_code="USD",
            to_currency_code="USD",
            rate_date=date(2026, 8, 5),
        )
        assert rate == Decimal("1.0")


class TestGetRateExactMatch:
    def test_exact_date_match_returns_recorded_rate(
        self, currency_service: CurrencyService
    ) -> None:
        company_id = uuid4()
        currency_service.set_exchange_rate(
            company_id=company_id,
            from_currency_code="USD",
            to_currency_code="EUR",
            rate_date=date(2026, 8, 5),
            rate=Decimal("0.9200"),
        )
        rate = currency_service.get_rate(
            company_id=company_id,
            from_currency_code="USD",
            to_currency_code="EUR",
            rate_date=date(2026, 8, 5),
        )
        assert rate == Decimal("0.9200")


class TestGetRateFallback:
    def test_falls_back_to_most_recent_rate_within_7_days(
        self, currency_service: CurrencyService
    ) -> None:
        company_id = uuid4()
        currency_service.set_exchange_rate(
            company_id=company_id,
            from_currency_code="USD",
            to_currency_code="EUR",
            rate_date=date(2026, 8, 1),
            rate=Decimal("0.9100"),
        )
        # No rate recorded for Aug 5 — should fall back to Aug 1 (4 days prior).
        rate = currency_service.get_rate(
            company_id=company_id,
            from_currency_code="USD",
            to_currency_code="EUR",
            rate_date=date(2026, 8, 5),
        )
        assert rate == Decimal("0.9100")

    def test_uses_most_recent_within_window_not_oldest(
        self, currency_service: CurrencyService
    ) -> None:
        company_id = uuid4()
        currency_service.set_exchange_rate(
            company_id=company_id,
            from_currency_code="USD",
            to_currency_code="EUR",
            rate_date=date(2026, 7, 30),
            rate=Decimal("0.9000"),
        )
        currency_service.set_exchange_rate(
            company_id=company_id,
            from_currency_code="USD",
            to_currency_code="EUR",
            rate_date=date(2026, 8, 2),
            rate=Decimal("0.9300"),
        )
        rate = currency_service.get_rate(
            company_id=company_id,
            from_currency_code="USD",
            to_currency_code="EUR",
            rate_date=date(2026, 8, 5),
        )
        assert rate == Decimal("0.9300")

    def test_beyond_7_day_window_raises_not_found(
        self, currency_service: CurrencyService
    ) -> None:
        company_id = uuid4()
        currency_service.set_exchange_rate(
            company_id=company_id,
            from_currency_code="USD",
            to_currency_code="EUR",
            rate_date=date(2026, 7, 20),  # 16 days before lookup date
            rate=Decimal("0.9000"),
        )
        with pytest.raises(ExchangeRateNotFoundError):
            currency_service.get_rate(
                company_id=company_id,
                from_currency_code="USD",
                to_currency_code="EUR",
                rate_date=date(2026, 8, 5),
            )


class TestGetRateNotFound:
    def test_no_rate_at_all_raises_not_found(
        self, currency_service: CurrencyService
    ) -> None:
        with pytest.raises(ExchangeRateNotFoundError):
            currency_service.get_rate(
                company_id=uuid4(),
                from_currency_code="USD",
                to_currency_code="GBP",
                rate_date=date(2026, 8, 5),
            )

    def test_error_message_contains_currency_pair(
        self, currency_service: CurrencyService
    ) -> None:
        with pytest.raises(ExchangeRateNotFoundError) as exc_info:
            currency_service.get_rate(
                company_id=uuid4(),
                from_currency_code="USD",
                to_currency_code="GBP",
                rate_date=date(2026, 8, 5),
            )
        assert "USD" in str(exc_info.value)
        assert "GBP" in str(exc_info.value)


class TestCurrencyRegistry:
    def test_create_and_list_currency(self, currency_service: CurrencyService) -> None:
        code = f"Z{uuid4().hex[:2].upper()}"
        currency_service.create_currency(
            iso_code=code, name="Test Currency", symbol="Z$"
        )
        currencies = currency_service.list_currencies()
        assert any(c.iso_code == code for c in currencies)

    def test_duplicate_currency_raises_value_error(
        self, currency_service: CurrencyService
    ) -> None:
        code = f"Y{uuid4().hex[:2].upper()}"
        currency_service.create_currency(iso_code=code, name="Dup", symbol="D")
        with pytest.raises(ValueError, match="already exists"):
            currency_service.create_currency(iso_code=code, name="Dup2", symbol="D2")
