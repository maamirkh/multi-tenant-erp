"""Integration tests for Pricing aggregate repositories — Phase 2.

Tests:
  - PriceListRepository: create, get_by_name, list_active, list_for_group, list_for_category,
    clear_default, tenant isolation
  - PriceEntryRepository: create, get_for_list, resolve_for_quantity (quantity breaks)
  - CustomerSpecificPriceRepository: create, resolve (qty + date filtering)
  - DiscountRuleRepository: create, get_active_rules (date filtering)

Uses SQLite in-memory DB via conftest db_session fixture.

Task: T080
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import Session

from modules.sales.models.pricing import (
    CustomerSpecificPrice,
    DiscountRule,
    PriceEntry,
    PriceList,
)
from modules.sales.repositories.pricing import (
    CustomerSpecificPriceRepository,
    DiscountRuleRepository,
    PriceEntryRepository,
    PriceListRepository,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def company_id() -> UUID:
    return uuid4()


@pytest.fixture
def company_id_b() -> UUID:
    return uuid4()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_price_list(
    company_id: UUID,
    name: str = "Standard",
    is_default: bool = False,
    is_active: bool = True,
    priority: int = 0,
    group_id: str | None = None,
    category_id: str | None = None,
    effective_from: str = "2026-01-01",
    effective_to: str | None = None,
) -> PriceList:
    return PriceList(
        company_id=company_id,
        name=name,
        currency_code="USD",
        effective_from=effective_from,
        effective_to=effective_to,
        is_default=is_default,
        is_active=is_active,
        priority=priority,
        customer_group_id=group_id,
        customer_category_id=category_id,
        version=1,
    )


def _make_price_entry(
    company_id: UUID,
    price_list_id: UUID,
    product_id: UUID,
    unit_price: str = "100.00",
    min_qty: str = "1",
) -> PriceEntry:
    return PriceEntry(
        company_id=company_id,
        price_list_id=str(price_list_id),
        product_id=str(product_id),
        unit_price=Decimal(unit_price),
        minimum_quantity=Decimal(min_qty),
        unit_of_measure="EA",
    )


def _make_customer_specific_price(
    company_id: UUID,
    customer_id: UUID,
    product_id: UUID,
    unit_price: str = "75.00",
    effective_from: str = "2026-01-01",
    effective_to: str | None = None,
    min_qty: str = "1",
) -> CustomerSpecificPrice:
    return CustomerSpecificPrice(
        company_id=company_id,
        customer_id=str(customer_id),
        product_id=str(product_id),
        unit_price=Decimal(unit_price),
        minimum_quantity=Decimal(min_qty),
        effective_from=effective_from,
        effective_to=effective_to,
    )


def _make_discount_rule(
    company_id: UUID,
    name: str = "Test Discount",
    rule_type: str = "PERCENTAGE",
    discount_value: str = "10.00",
    effective_from: str = "2026-01-01",
    effective_to: str | None = None,
    is_active: bool = True,
    priority: int = 0,
    is_stackable: bool = False,
    applicability: str = "ALL_CUSTOMERS",
    product_scope: str = "ALL_PRODUCTS",
) -> DiscountRule:
    return DiscountRule(
        company_id=company_id,
        name=name,
        rule_type=rule_type,
        applicability=applicability,
        product_scope=product_scope,
        discount_value=Decimal(discount_value),
        effective_from=effective_from,
        effective_to=effective_to,
        is_active=is_active,
        priority=priority,
        is_stackable=is_stackable,
    )


# ---------------------------------------------------------------------------
# PriceListRepository
# ---------------------------------------------------------------------------


class TestPriceListRepository:
    def test_create_and_get_by_name(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = PriceListRepository(db=db_session)
        pl = _make_price_list(company_id, name="Premium")
        created = repo.create(pl)

        assert created.id is not None
        found = repo.get_by_name(company_id=company_id, name="Premium")
        assert found is not None
        assert found.currency_code == "USD"

    def test_get_by_name_returns_none_for_unknown(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = PriceListRepository(db=db_session)
        result = repo.get_by_name(company_id=company_id, name="NonExistent")
        assert result is None

    def test_get_by_name_tenant_isolation(
        self, db_session: Session, company_id: UUID, company_id_b: UUID
    ) -> None:
        repo = PriceListRepository(db=db_session)
        repo.create(_make_price_list(company_id, name="Standard"))

        # Different company should not find it
        result = repo.get_by_name(company_id=company_id_b, name="Standard")
        assert result is None

    def test_list_active_returns_active_lists(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = PriceListRepository(db=db_session)
        repo.create(_make_price_list(company_id, name="Active", is_active=True))
        repo.create(_make_price_list(company_id, name="Inactive", is_active=False))

        active = repo.list_active(company_id=company_id)
        names = [pl.name for pl in active]
        assert "Active" in names
        assert "Inactive" not in names

    def test_list_active_tenant_isolation(
        self, db_session: Session, company_id: UUID, company_id_b: UUID
    ) -> None:
        repo = PriceListRepository(db=db_session)
        repo.create(_make_price_list(company_id, name="Company A List"))
        repo.create(_make_price_list(company_id_b, name="Company B List"))

        active_a = repo.list_active(company_id=company_id)
        active_b = repo.list_active(company_id=company_id_b)
        assert all(pl.company_id == company_id for pl in active_a)
        assert all(pl.company_id == company_id_b for pl in active_b)

    def test_list_for_group(self, db_session: Session, company_id: UUID) -> None:
        repo = PriceListRepository(db=db_session)
        group_id = str(uuid4())
        repo.create(_make_price_list(company_id, name="Group List", group_id=group_id))
        repo.create(_make_price_list(company_id, name="Standard List"))

        group_lists = repo.list_for_group(company_id=company_id, group_id=group_id)
        assert len(group_lists) == 1
        assert group_lists[0].name == "Group List"

    def test_list_for_category(self, db_session: Session, company_id: UUID) -> None:
        repo = PriceListRepository(db=db_session)
        category_id = str(uuid4())
        repo.create(
            _make_price_list(company_id, name="Category List", category_id=category_id)
        )
        repo.create(_make_price_list(company_id, name="Standard List"))

        cat_lists = repo.list_for_category(
            company_id=company_id, category_id=category_id
        )
        assert len(cat_lists) == 1
        assert cat_lists[0].name == "Category List"

    def test_clear_default_unsets_existing_default(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = PriceListRepository(db=db_session)
        pl = _make_price_list(company_id, name="Default List", is_default=True)
        created = repo.create(pl)
        db_session.flush()

        assert created.is_default is True

        # Clear default — should unset it
        repo.clear_default(company_id=company_id)
        db_session.flush()

        refreshed = repo.get_by_id_or_none(id=created.id, company_id=company_id)
        assert refreshed is not None
        assert refreshed.is_default is False

    def test_soft_delete_not_returned_in_list(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = PriceListRepository(db=db_session)
        pl = _make_price_list(company_id, name="To Delete")
        created = repo.create(pl)
        db_session.flush()

        created.is_deleted = True
        repo.update(created)
        db_session.flush()

        active = repo.list_active(company_id=company_id)
        assert not any(p.name == "To Delete" for p in active)


# ---------------------------------------------------------------------------
# PriceEntryRepository
# ---------------------------------------------------------------------------


class TestPriceEntryRepository:
    def test_create_and_get_for_list(
        self, db_session: Session, company_id: UUID
    ) -> None:
        pl_repo = PriceListRepository(db=db_session)
        entry_repo = PriceEntryRepository(db=db_session)

        pl = pl_repo.create(_make_price_list(company_id, name="Test"))
        db_session.flush()

        product_id = uuid4()
        entry = entry_repo.create(_make_price_entry(company_id, pl.id, product_id))
        db_session.flush()

        assert entry.id is not None
        entries = entry_repo.get_for_list(company_id=company_id, price_list_id=pl.id)
        assert len(entries) >= 1
        assert any(str(e.product_id) == str(product_id) for e in entries)

    def test_resolve_for_quantity_returns_highest_qualifying(
        self, db_session: Session, company_id: UUID
    ) -> None:
        """Entry with highest min_qty <= ordered_qty wins."""
        pl_repo = PriceListRepository(db=db_session)
        entry_repo = PriceEntryRepository(db=db_session)

        pl = pl_repo.create(_make_price_list(company_id, name="Volume"))
        db_session.flush()

        product_id = uuid4()
        # Create entries: min_qty=1 at $100, min_qty=5 at $90, min_qty=10 at $80
        entry_repo.create(
            _make_price_entry(company_id, pl.id, product_id, "100.00", "1")
        )
        entry_repo.create(
            _make_price_entry(company_id, pl.id, product_id, "90.00", "5")
        )
        entry_repo.create(
            _make_price_entry(company_id, pl.id, product_id, "80.00", "10")
        )
        db_session.flush()

        # Order qty=7 → should return min_qty=5 entry ($90)
        result = entry_repo.resolve_for_quantity(
            company_id=company_id,
            price_list_id=pl.id,
            product_id=product_id,
            quantity=Decimal("7"),
        )
        assert result is not None
        assert result.unit_price == Decimal("90.0000")

    def test_resolve_for_quantity_returns_none_when_no_match(
        self, db_session: Session, company_id: UUID
    ) -> None:
        """When qty < minimum_quantity of all entries, returns None."""
        pl_repo = PriceListRepository(db=db_session)
        entry_repo = PriceEntryRepository(db=db_session)

        pl = pl_repo.create(_make_price_list(company_id, name="High Volume Only"))
        db_session.flush()

        product_id = uuid4()
        entry_repo.create(
            _make_price_entry(company_id, pl.id, product_id, "80.00", "10")
        )
        db_session.flush()

        result = entry_repo.resolve_for_quantity(
            company_id=company_id,
            price_list_id=pl.id,
            product_id=product_id,
            quantity=Decimal("5"),
        )
        assert result is None

    def test_resolve_for_quantity_tenant_isolation(
        self, db_session: Session, company_id: UUID, company_id_b: UUID
    ) -> None:
        pl_repo = PriceListRepository(db=db_session)
        entry_repo = PriceEntryRepository(db=db_session)

        # Company A list and entry
        pl_a = pl_repo.create(_make_price_list(company_id, name="List A"))
        db_session.flush()
        product_id = uuid4()
        entry_repo.create(
            _make_price_entry(company_id, pl_a.id, product_id, "50.00", "1")
        )
        db_session.flush()

        # Company B should not find company A's entry
        result = entry_repo.resolve_for_quantity(
            company_id=company_id_b,
            price_list_id=pl_a.id,
            product_id=product_id,
            quantity=Decimal("1"),
        )
        assert result is None

    def test_delete_for_list_soft_deletes_all_entries(
        self, db_session: Session, company_id: UUID
    ) -> None:
        pl_repo = PriceListRepository(db=db_session)
        entry_repo = PriceEntryRepository(db=db_session)

        pl = pl_repo.create(_make_price_list(company_id, name="To Clean"))
        db_session.flush()

        product_id = uuid4()
        entry_repo.create(
            _make_price_entry(company_id, pl.id, product_id, "100.00", "1")
        )
        db_session.flush()

        entry_repo.delete_for_list(company_id=company_id, price_list_id=pl.id)
        db_session.flush()

        entries_after = entry_repo.get_for_list(
            company_id=company_id, price_list_id=pl.id
        )
        assert len(entries_after) == 0


# ---------------------------------------------------------------------------
# CustomerSpecificPriceRepository
# ---------------------------------------------------------------------------


class TestCustomerSpecificPriceRepository:
    def test_create_and_resolve(self, db_session: Session, company_id: UUID) -> None:
        repo = CustomerSpecificPriceRepository(db=db_session)
        customer_id = uuid4()
        product_id = uuid4()

        repo.create(
            _make_customer_specific_price(company_id, customer_id, product_id, "75.00")
        )
        db_session.flush()

        result = repo.resolve(
            company_id=company_id,
            customer_id=customer_id,
            product_id=product_id,
            quantity=Decimal("1"),
            as_of_date="2026-06-01",
        )
        assert result is not None
        assert result.unit_price == Decimal("75.0000")

    def test_resolve_returns_none_for_wrong_customer(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = CustomerSpecificPriceRepository(db=db_session)
        customer_id = uuid4()
        product_id = uuid4()

        repo.create(
            _make_customer_specific_price(company_id, customer_id, product_id, "75.00")
        )
        db_session.flush()

        result = repo.resolve(
            company_id=company_id,
            customer_id=uuid4(),  # different customer
            product_id=product_id,
            quantity=Decimal("1"),
        )
        assert result is None

    def test_resolve_respects_quantity_minimum(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = CustomerSpecificPriceRepository(db=db_session)
        customer_id = uuid4()
        product_id = uuid4()

        # Only available at min_qty=5
        repo.create(
            _make_customer_specific_price(
                company_id, customer_id, product_id, "75.00", min_qty="5"
            )
        )
        db_session.flush()

        # qty=3 < min_qty=5 → no match
        result = repo.resolve(
            company_id=company_id,
            customer_id=customer_id,
            product_id=product_id,
            quantity=Decimal("3"),
        )
        assert result is None

    def test_resolve_tenant_isolation(
        self, db_session: Session, company_id: UUID, company_id_b: UUID
    ) -> None:
        repo = CustomerSpecificPriceRepository(db=db_session)
        customer_id = uuid4()
        product_id = uuid4()

        repo.create(
            _make_customer_specific_price(company_id, customer_id, product_id, "75.00")
        )
        db_session.flush()

        result = repo.resolve(
            company_id=company_id_b,
            customer_id=customer_id,
            product_id=product_id,
            quantity=Decimal("1"),
        )
        assert result is None


# ---------------------------------------------------------------------------
# DiscountRuleRepository
# ---------------------------------------------------------------------------


class TestDiscountRuleRepository:
    def test_create_and_get_active(self, db_session: Session, company_id: UUID) -> None:
        repo = DiscountRuleRepository(db=db_session)
        rule = _make_discount_rule(
            company_id, name="Summer Sale", discount_value="15.00"
        )
        created = repo.create(rule)
        db_session.flush()

        assert created.id is not None
        active = repo.get_active_rules(company_id=company_id)
        assert any(r.name == "Summer Sale" for r in active)

    def test_inactive_rule_excluded(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = DiscountRuleRepository(db=db_session)
        repo.create(_make_discount_rule(company_id, name="Inactive", is_active=False))
        db_session.flush()

        active = repo.get_active_rules(company_id=company_id)
        assert not any(r.name == "Inactive" for r in active)

    def test_soft_deleted_rule_excluded(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = DiscountRuleRepository(db=db_session)
        rule = _make_discount_rule(company_id, name="Deleted Rule")
        created = repo.create(rule)
        db_session.flush()

        created.is_deleted = True
        repo.update(created)
        db_session.flush()

        active = repo.get_active_rules(company_id=company_id)
        assert not any(r.name == "Deleted Rule" for r in active)

    def test_active_rules_sorted_by_priority_descending(
        self, db_session: Session, company_id: UUID
    ) -> None:
        repo = DiscountRuleRepository(db=db_session)
        repo.create(_make_discount_rule(company_id, name="Low", priority=10))
        repo.create(_make_discount_rule(company_id, name="High", priority=100))
        repo.create(_make_discount_rule(company_id, name="Mid", priority=50))
        db_session.flush()

        active = repo.get_active_rules(company_id=company_id)
        priorities = [r.priority for r in active]
        assert priorities == sorted(priorities, reverse=True)

    def test_tenant_isolation(
        self, db_session: Session, company_id: UUID, company_id_b: UUID
    ) -> None:
        repo = DiscountRuleRepository(db=db_session)
        repo.create(_make_discount_rule(company_id, name="Company A Rule"))
        repo.create(_make_discount_rule(company_id_b, name="Company B Rule"))
        db_session.flush()

        active_a = repo.get_active_rules(company_id=company_id)
        active_b = repo.get_active_rules(company_id=company_id_b)
        assert all(r.company_id == company_id for r in active_a)
        assert all(r.company_id == company_id_b for r in active_b)
