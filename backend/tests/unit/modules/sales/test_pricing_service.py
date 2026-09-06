"""Unit tests for PricingService — Phase 2.

Tests:
  - All 7 resolution levels with known values
  - Quantity break resolution (highest min_quantity <= ordered quantity)
  - Default price list fallback
  - Manual override short-circuits all levels
  - Missing price returns BASE_PRICE (level 7)

Task: T077
Spec ref: specs/007-sales-management/research.md §Decision 3
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from modules.sales.models.pricing import CustomerSpecificPrice, PriceEntry, PriceList
from modules.sales.services.pricing_service import (
    PRICE_SOURCE_BASE_PRICE,
    PRICE_SOURCE_CUSTOMER_CATEGORY,
    PRICE_SOURCE_CUSTOMER_GROUP,
    PRICE_SOURCE_CUSTOMER_SPECIFIC,
    PRICE_SOURCE_DEFAULT_LIST,
    PRICE_SOURCE_MANUAL,
    PRICE_SOURCE_PRICE_LIST,
    PricingService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_price_list(
    name: str = "Standard",
    is_default: bool = False,
    priority: int = 0,
    group_id: str | None = None,
    category_id: str | None = None,
) -> PriceList:
    pl = PriceList()
    pl.id = uuid4()
    pl.company_id = uuid4()
    pl.name = name
    pl.currency_code = "USD"
    pl.effective_from = "2026-01-01"
    pl.effective_to = None
    pl.is_default = is_default
    pl.is_active = True
    pl.priority = priority
    pl.customer_group_id = group_id
    pl.customer_category_id = category_id
    pl.version = 1
    pl.is_deleted = False
    return pl


def _make_price_entry(unit_price: str, min_qty: str = "1") -> PriceEntry:
    e = PriceEntry()
    e.id = uuid4()
    e.company_id = uuid4()
    e.price_list_id = str(uuid4())
    e.product_id = str(uuid4())
    e.unit_price = Decimal(unit_price)
    e.minimum_quantity = Decimal(min_qty)
    e.unit_of_measure = "EA"
    e.is_deleted = False
    return e


def _make_customer_specific_price(unit_price: str) -> CustomerSpecificPrice:
    sp = CustomerSpecificPrice()
    sp.id = uuid4()
    sp.company_id = uuid4()
    sp.customer_id = str(uuid4())
    sp.product_id = str(uuid4())
    sp.unit_price = Decimal(unit_price)
    sp.minimum_quantity = Decimal("1")
    sp.effective_from = "2026-01-01"
    sp.effective_to = None
    sp.is_deleted = False
    return sp


def _make_service(
    specific_result: CustomerSpecificPrice | None = None,
    group_lists: list[PriceList] | None = None,
    category_lists: list[PriceList] | None = None,
    active_lists: list[PriceList] | None = None,
    entry_result: PriceEntry | None = None,
) -> PricingService:
    """Build PricingService with mocked repositories."""
    pl_repo = MagicMock()
    entry_repo = MagicMock()
    specific_repo = MagicMock()

    specific_repo.resolve.return_value = specific_result
    pl_repo.list_for_group.return_value = group_lists or []
    pl_repo.list_for_category.return_value = category_lists or []
    pl_repo.list_active.return_value = active_lists or []
    entry_repo.resolve_for_quantity.return_value = entry_result

    return PricingService(
        db=MagicMock(),
        price_list_repo=pl_repo,
        entry_repo=entry_repo,
        specific_repo=specific_repo,
    )


# ---------------------------------------------------------------------------
# Level 1: Manual Override
# ---------------------------------------------------------------------------


class TestLevel1ManualOverride:
    def test_manual_price_returns_level_1(self) -> None:
        service = _make_service()
        result = service.resolve_price(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("5"),
            manual_price=Decimal("99.99"),
        )
        assert result.unit_price == Decimal("99.99")
        assert result.price_source == PRICE_SOURCE_MANUAL
        assert result.resolution_level == 1

    def test_manual_price_zero_still_returns_level_1(self) -> None:
        service = _make_service()
        result = service.resolve_price(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            manual_price=Decimal("0"),
        )
        assert result.unit_price == Decimal("0")
        assert result.price_source == PRICE_SOURCE_MANUAL
        assert result.resolution_level == 1


# ---------------------------------------------------------------------------
# Level 2: Customer-Specific Price
# ---------------------------------------------------------------------------


class TestLevel2CustomerSpecificPrice:
    def test_customer_specific_price_returns_level_2(self) -> None:
        specific = _make_customer_specific_price("45.00")
        service = _make_service(specific_result=specific)

        result = service.resolve_price(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("3"),
            customer_id=uuid4(),
        )
        assert result.unit_price == Decimal("45.00")
        assert result.price_source == PRICE_SOURCE_CUSTOMER_SPECIFIC
        assert result.resolution_level == 2
        assert result.customer_specific_price_id == str(specific.id)

    def test_no_customer_id_skips_level_2(self) -> None:
        service = _make_service()
        result = service.resolve_price(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            customer_id=None,
        )
        # Falls through to level 7
        assert result.resolution_level == 7


# ---------------------------------------------------------------------------
# Level 3: Customer Group Price List
# ---------------------------------------------------------------------------


class TestLevel3CustomerGroup:
    def test_group_price_list_returns_level_3(self) -> None:
        group_id = str(uuid4())
        pl = _make_price_list(name="Group Pricing", group_id=group_id)
        entry = _make_price_entry("38.00")

        service = _make_service(
            specific_result=None,
            group_lists=[pl],
            entry_result=entry,
        )

        result = service.resolve_price(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("2"),
            customer_id=uuid4(),
            group_id=group_id,
        )
        assert result.unit_price == Decimal("38.00")
        assert result.price_source == PRICE_SOURCE_CUSTOMER_GROUP
        assert result.resolution_level == 3

    def test_no_group_id_skips_level_3(self) -> None:
        service = _make_service()
        result = service.resolve_price(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            group_id=None,
        )
        assert result.resolution_level == 7


# ---------------------------------------------------------------------------
# Level 4: Customer Category Price List
# ---------------------------------------------------------------------------


class TestLevel4CustomerCategory:
    def test_category_price_list_returns_level_4(self) -> None:
        category_id = str(uuid4())
        pl = _make_price_list(name="Category Pricing", category_id=category_id)
        entry = _make_price_entry("42.00")

        pl_repo = MagicMock()
        entry_repo = MagicMock()
        specific_repo = MagicMock()

        specific_repo.resolve.return_value = None
        pl_repo.list_for_group.return_value = []
        pl_repo.list_for_category.return_value = [pl]
        pl_repo.list_active.return_value = []
        entry_repo.resolve_for_quantity.return_value = entry

        service = PricingService(
            db=MagicMock(),
            price_list_repo=pl_repo,
            entry_repo=entry_repo,
            specific_repo=specific_repo,
        )

        result = service.resolve_price(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            customer_id=uuid4(),
            group_id=None,
            category_id=category_id,
        )
        assert result.unit_price == Decimal("42.00")
        assert result.price_source == PRICE_SOURCE_CUSTOMER_CATEGORY
        assert result.resolution_level == 4


# ---------------------------------------------------------------------------
# Level 5: Active Price List
# ---------------------------------------------------------------------------


class TestLevel5ActivePriceList:
    def test_active_price_list_returns_level_5(self) -> None:
        pl = _make_price_list(name="Standard", is_default=False, priority=10)
        entry = _make_price_entry("50.00")

        pl_repo = MagicMock()
        entry_repo = MagicMock()
        specific_repo = MagicMock()

        specific_repo.resolve.return_value = None
        pl_repo.list_for_group.return_value = []
        pl_repo.list_for_category.return_value = []
        # list_active returns non-default list
        pl_repo.list_active.return_value = [pl]
        entry_repo.resolve_for_quantity.return_value = entry

        service = PricingService(
            db=MagicMock(),
            price_list_repo=pl_repo,
            entry_repo=entry_repo,
            specific_repo=specific_repo,
        )

        result = service.resolve_price(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            customer_id=uuid4(),
        )
        assert result.unit_price == Decimal("50.00")
        assert result.price_source == PRICE_SOURCE_PRICE_LIST
        assert result.resolution_level == 5

    def test_higher_priority_list_wins_at_level_5(self) -> None:
        """Price lists returned in priority desc order — first match wins."""
        pl_high = _make_price_list(name="Premium", is_default=False, priority=100)
        pl_low = _make_price_list(name="Standard", is_default=False, priority=10)

        entry_high = _make_price_entry("60.00")
        entry_low = _make_price_entry("50.00")

        pl_repo = MagicMock()
        entry_repo = MagicMock()
        specific_repo = MagicMock()

        specific_repo.resolve.return_value = None
        pl_repo.list_for_group.return_value = []
        pl_repo.list_for_category.return_value = []
        pl_repo.list_active.return_value = [pl_high, pl_low]
        # First call returns high-priority price, second would return low
        entry_repo.resolve_for_quantity.side_effect = [entry_high, entry_low]

        service = PricingService(
            db=MagicMock(),
            price_list_repo=pl_repo,
            entry_repo=entry_repo,
            specific_repo=specific_repo,
        )

        result = service.resolve_price(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
        )
        assert result.unit_price == Decimal("60.00")
        assert result.resolution_level == 5


# ---------------------------------------------------------------------------
# Level 6: Default Price List
# ---------------------------------------------------------------------------


class TestLevel6DefaultPriceList:
    def test_default_price_list_returns_level_6(self) -> None:
        pl_default = _make_price_list(name="Default", is_default=True, priority=0)
        entry = _make_price_entry("55.00")

        pl_repo = MagicMock()
        entry_repo = MagicMock()
        specific_repo = MagicMock()

        specific_repo.resolve.return_value = None
        pl_repo.list_for_group.return_value = []
        pl_repo.list_for_category.return_value = []
        # list_active returns only the default list (no general lists)
        pl_repo.list_active.return_value = [pl_default]
        entry_repo.resolve_for_quantity.return_value = entry

        service = PricingService(
            db=MagicMock(),
            price_list_repo=pl_repo,
            entry_repo=entry_repo,
            specific_repo=specific_repo,
        )

        result = service.resolve_price(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
        )
        assert result.unit_price == Decimal("55.00")
        assert result.price_source == PRICE_SOURCE_DEFAULT_LIST
        assert result.resolution_level == 6


# ---------------------------------------------------------------------------
# Level 7: Product Base Price (fallback)
# ---------------------------------------------------------------------------


class TestLevel7BasePrice:
    def test_no_price_found_returns_level_7(self) -> None:
        service = _make_service()
        result = service.resolve_price(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
        )
        assert result.unit_price == Decimal("0")
        assert result.price_source == PRICE_SOURCE_BASE_PRICE
        assert result.resolution_level == 7


# ---------------------------------------------------------------------------
# Quantity Break Resolution
# ---------------------------------------------------------------------------


class TestQuantityBreakResolution:
    def test_quantity_break_selects_highest_qualifying_min_qty(self) -> None:
        """When quantity=10, the entry with min_qty=10 wins over min_qty=1."""
        pl = _make_price_list(name="Volume Pricing", is_default=True)
        entry_for_10 = _make_price_entry("20.00", min_qty="10")

        pl_repo = MagicMock()
        entry_repo = MagicMock()
        specific_repo = MagicMock()

        specific_repo.resolve.return_value = None
        pl_repo.list_for_group.return_value = []
        pl_repo.list_for_category.return_value = []
        pl_repo.list_active.return_value = [pl]
        # Repository already filters by min_qty <= ordered_qty and returns highest match
        entry_repo.resolve_for_quantity.return_value = entry_for_10

        service = PricingService(
            db=MagicMock(),
            price_list_repo=pl_repo,
            entry_repo=entry_repo,
            specific_repo=specific_repo,
        )

        result = service.resolve_price(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("10"),
        )
        assert result.unit_price == Decimal("20.00")

    def test_quantity_below_min_qty_falls_through(self) -> None:
        """When quantity=1 but only entry with min_qty=10 exists, no match found."""
        pl = _make_price_list(name="Volume Only", is_default=True)

        pl_repo = MagicMock()
        entry_repo = MagicMock()
        specific_repo = MagicMock()

        specific_repo.resolve.return_value = None
        pl_repo.list_for_group.return_value = []
        pl_repo.list_for_category.return_value = []
        pl_repo.list_active.return_value = [pl]
        # No entry qualifies (min_qty > ordered qty)
        entry_repo.resolve_for_quantity.return_value = None

        service = PricingService(
            db=MagicMock(),
            price_list_repo=pl_repo,
            entry_repo=entry_repo,
            specific_repo=specific_repo,
        )

        result = service.resolve_price(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
        )
        assert result.resolution_level == 7
        assert result.price_source == PRICE_SOURCE_BASE_PRICE


# ---------------------------------------------------------------------------
# Resolution Level Ordering
# ---------------------------------------------------------------------------


class TestResolutionOrdering:
    def test_customer_specific_beats_price_list(self) -> None:
        """Customer-specific price (level 2) wins over any price list (level 5)."""
        specific = _make_customer_specific_price("30.00")
        pl = _make_price_list(name="Standard", is_default=True)
        entry = _make_price_entry("50.00")

        pl_repo = MagicMock()
        entry_repo = MagicMock()
        specific_repo = MagicMock()

        specific_repo.resolve.return_value = specific
        pl_repo.list_for_group.return_value = []
        pl_repo.list_for_category.return_value = []
        pl_repo.list_active.return_value = [pl]
        entry_repo.resolve_for_quantity.return_value = entry

        service = PricingService(
            db=MagicMock(),
            price_list_repo=pl_repo,
            entry_repo=entry_repo,
            specific_repo=specific_repo,
        )

        result = service.resolve_price(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("5"),
            customer_id=uuid4(),
        )
        assert result.unit_price == Decimal("30.00")
        assert result.price_source == PRICE_SOURCE_CUSTOMER_SPECIFIC
        assert result.resolution_level == 2
