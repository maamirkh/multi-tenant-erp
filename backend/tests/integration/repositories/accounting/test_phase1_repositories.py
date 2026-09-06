"""Integration tests for Phase 1 accounting repositories.

Tests:
  - CurrencyRepository CRUD (global — no company_id scoping)
  - ExchangeRateRepository CRUD and company_id scoping
  - AccountingConfigurationRepository CRUD and company_id scoping
  - AccountingFeatureFlagRepository CRUD and company_id scoping

Spec ref: specs/008-accounting-finance/tasks.md T047
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from modules.accounting.models.foundation import (
    AccountingConfiguration,
    Currency,
    ExchangeRate,
)
from modules.accounting.repositories.feature_flag_repository import (
    AccountingFeatureFlagRepository,
)
from modules.accounting.repositories.foundation import (
    AccountingConfigurationRepository,
    CurrencyRepository,
    ExchangeRateRepository,
)


class TestCurrencyRepository:
    """Currency is global — no company_id scoping (data-model.md §11)."""

    def test_create_and_find_by_code(self, db_session: Session) -> None:
        repo = CurrencyRepository(db_session)
        code = f"Q{uuid4().hex[:2].upper()}"
        repo.create(
            Currency(iso_code=code, name="Test Q", symbol="Q$", decimal_places=2)
        )
        found = repo.find_by_code(code)
        assert found is not None
        assert found.name == "Test Q"

    def test_find_by_code_missing_returns_none(self, db_session: Session) -> None:
        repo = CurrencyRepository(db_session)
        assert repo.find_by_code("ZZZ_NOPE") is None

    def test_find_all_active_excludes_inactive(self, db_session: Session) -> None:
        repo = CurrencyRepository(db_session)
        active_code = f"A{uuid4().hex[:2].upper()}"
        inactive_code = f"I{uuid4().hex[:2].upper()}"
        repo.create(Currency(iso_code=active_code, name="Active", symbol="A$"))
        repo.create(
            Currency(
                iso_code=inactive_code, name="Inactive", symbol="I$", is_active=False
            )
        )
        active = repo.find_all_active()
        codes = {c.iso_code for c in active}
        assert active_code in codes
        assert inactive_code not in codes

    def test_list_all_includes_inactive(self, db_session: Session) -> None:
        repo = CurrencyRepository(db_session)
        code = f"L{uuid4().hex[:2].upper()}"
        repo.create(
            Currency(iso_code=code, name="Listed", symbol="L$", is_active=False)
        )
        all_currencies = repo.list_all()
        assert any(c.iso_code == code for c in all_currencies)


class TestExchangeRateRepository:
    def test_create_and_get_rate_for_date(self, db_session: Session) -> None:
        repo = ExchangeRateRepository(db_session)
        company_id = uuid4()
        rate = ExchangeRate(
            company_id=company_id,
            from_currency_code="USD",
            to_currency_code="EUR",
            rate_date=date(2026, 8, 5),
            rate=Decimal("0.9200"),
            rate_type="SPOT",
        )
        repo.create(rate)

        found = repo.get_rate_for_date(
            company_id=company_id,
            from_currency_code="USD",
            to_currency_code="EUR",
            rate_date=date(2026, 8, 5),
        )
        assert found is not None
        assert found.rate == Decimal("0.9200")

    def test_company_id_scoping(self, db_session: Session) -> None:
        repo = ExchangeRateRepository(db_session)
        company_a = uuid4()
        company_b = uuid4()
        repo.create(
            ExchangeRate(
                company_id=company_a,
                from_currency_code="USD",
                to_currency_code="EUR",
                rate_date=date(2026, 8, 5),
                rate=Decimal("0.9000"),
                rate_type="SPOT",
            )
        )
        # Company B should not see Company A's rate.
        found = repo.get_rate_for_date(
            company_id=company_b,
            from_currency_code="USD",
            to_currency_code="EUR",
            rate_date=date(2026, 8, 5),
        )
        assert found is None

    def test_get_rates_for_period(self, db_session: Session) -> None:
        repo = ExchangeRateRepository(db_session)
        company_id = uuid4()
        for day in (1, 2, 3):
            repo.create(
                ExchangeRate(
                    company_id=company_id,
                    from_currency_code="USD",
                    to_currency_code="GBP",
                    rate_date=date(2026, 8, day),
                    rate=Decimal("0.79") + Decimal(f"0.{day:02d}"),
                    rate_type="SPOT",
                )
            )
        rates = repo.get_rates_for_period(
            company_id=company_id,
            from_currency_code="USD",
            to_currency_code="GBP",
            start_date=date(2026, 8, 1),
            end_date=date(2026, 8, 3),
        )
        assert len(rates) == 3

    def test_list_all_for_company(self, db_session: Session) -> None:
        repo = ExchangeRateRepository(db_session)
        company_id = uuid4()
        repo.create(
            ExchangeRate(
                company_id=company_id,
                from_currency_code="USD",
                to_currency_code="PKR",
                rate_date=date(2026, 8, 5),
                rate=Decimal("278.50"),
                rate_type="SPOT",
            )
        )
        rates = repo.list_all(company_id=company_id)
        assert len(rates) == 1
        assert rates[0].to_currency_code == "PKR"


class TestAccountingConfigurationRepository:
    def test_create_and_get_for_company(self, db_session: Session) -> None:
        repo = AccountingConfigurationRepository(db_session)
        company_id = uuid4()
        config = AccountingConfiguration(company_id=company_id)
        repo.create(config)

        found = repo.get_for_company(company_id=company_id)
        assert found is not None
        assert found.base_currency_code == "USD"
        assert found.credit_warning_threshold_pct == Decimal("80.00")

    def test_company_id_scoping(self, db_session: Session) -> None:
        repo = AccountingConfigurationRepository(db_session)
        company_a = uuid4()
        company_b = uuid4()
        repo.create(AccountingConfiguration(company_id=company_a))

        assert repo.get_for_company(company_id=company_b) is None
        assert repo.get_for_company(company_id=company_a) is not None

    def test_update_persists_changes(self, db_session: Session) -> None:
        repo = AccountingConfigurationRepository(db_session)
        company_id = uuid4()
        config = repo.create(AccountingConfiguration(company_id=company_id))
        config.base_currency_code = "EUR"
        updated = repo.update(config)
        assert updated.base_currency_code == "EUR"

        refetched = repo.get_for_company(company_id=company_id)
        assert refetched is not None
        assert refetched.base_currency_code == "EUR"


class TestAccountingFeatureFlagRepository:
    def test_upsert_creates_then_updates(self, db_session: Session) -> None:
        repo = AccountingFeatureFlagRepository(db_session)
        company_id = uuid4()

        created = repo.upsert(
            company_id=company_id,
            flag_key="accounting.multicurrency.enabled",
            is_enabled=True,
        )
        assert created.is_enabled is True

        updated = repo.upsert(
            company_id=company_id,
            flag_key="accounting.multicurrency.enabled",
            is_enabled=False,
        )
        assert updated.id == created.id
        assert updated.is_enabled is False

    def test_company_id_scoping(self, db_session: Session) -> None:
        repo = AccountingFeatureFlagRepository(db_session)
        company_a = uuid4()
        company_b = uuid4()
        repo.upsert(
            company_id=company_a,
            flag_key="accounting.bulkimport.enabled",
            is_enabled=False,
        )
        assert (
            repo.get_by_key(
                company_id=company_b, flag_key="accounting.bulkimport.enabled"
            )
            is None
        )

    def test_get_all_for_company_excludes_other_companies(
        self, db_session: Session
    ) -> None:
        repo = AccountingFeatureFlagRepository(db_session)
        company_a = uuid4()
        company_b = uuid4()
        repo.upsert(
            company_id=company_a, flag_key="accounting.ai.enabled", is_enabled=True
        )
        repo.upsert(
            company_id=company_b,
            flag_key="accounting.costcenters.enabled",
            is_enabled=True,
        )
        flags_a = repo.get_all_for_company(company_id=company_a)
        keys_a = {f.flag_key for f in flags_a}
        assert "accounting.ai.enabled" in keys_a
        assert "accounting.costcenters.enabled" not in keys_a
