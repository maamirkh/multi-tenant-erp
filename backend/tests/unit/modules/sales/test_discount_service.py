"""Unit tests for DiscountService — Phase 2.

Tests:
  - Customer scope: ALL_CUSTOMERS, SPECIFIC_CUSTOMER, SPECIFIC_GROUP, SPECIFIC_CATEGORY
  - Product scope: ALL_PRODUCTS, SPECIFIC_PRODUCT, SPECIFIC_CATEGORY
  - Quantity threshold filtering
  - Order value threshold filtering
  - Stackability: non-stackable highest priority wins; stackable rules combine
  - Priority ordering of results

Task: T078
Spec ref: specs/007-sales-management/research.md §Decision 3
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from modules.sales.models.pricing import DiscountRule
from modules.sales.services.pricing_service import (
    DiscountService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rule(
    rule_type: str = "PERCENTAGE",
    applicability: str = "ALL_CUSTOMERS",
    applicability_id: str | None = None,
    product_scope: str = "ALL_PRODUCTS",
    product_scope_id: str | None = None,
    discount_value: str = "10.00",
    minimum_quantity: str | None = None,
    minimum_order_value: str | None = None,
    priority: int = 0,
    is_stackable: bool = False,
) -> DiscountRule:
    rule = DiscountRule()
    rule.id = uuid4()
    rule.company_id = uuid4()
    rule.name = f"Rule-{rule.id}"
    rule.rule_type = rule_type
    rule.applicability = applicability
    rule.applicability_id = applicability_id
    rule.product_scope = product_scope
    rule.product_scope_id = product_scope_id
    rule.discount_value = Decimal(discount_value)
    rule.minimum_quantity = Decimal(minimum_quantity) if minimum_quantity else None
    rule.minimum_order_value = (
        Decimal(minimum_order_value) if minimum_order_value else None
    )
    rule.priority = priority
    rule.is_stackable = is_stackable
    rule.is_active = True
    rule.is_deleted = False
    return rule


def _make_service(rules: list[DiscountRule]) -> DiscountService:
    repo = MagicMock()
    repo.get_active_rules.return_value = rules
    return DiscountService(db=MagicMock(), discount_repo=repo)


# ---------------------------------------------------------------------------
# Customer Scope
# ---------------------------------------------------------------------------


class TestCustomerScopeFiltering:
    def test_all_customers_applies_to_anyone(self) -> None:
        rule = _make_rule(applicability="ALL_CUSTOMERS")
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
            customer_id=None,
        )
        assert len(result) == 1
        assert result[0].rule_id == str(rule.id)

    def test_specific_customer_matches_correct_customer(self) -> None:
        customer_id = uuid4()
        rule = _make_rule(
            applicability="SPECIFIC_CUSTOMER",
            applicability_id=str(customer_id),
        )
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
            customer_id=customer_id,
        )
        assert len(result) == 1

    def test_specific_customer_excludes_wrong_customer(self) -> None:
        rule = _make_rule(
            applicability="SPECIFIC_CUSTOMER",
            applicability_id=str(uuid4()),
        )
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
            customer_id=uuid4(),  # different customer
        )
        assert len(result) == 0

    def test_specific_customer_excludes_null_customer(self) -> None:
        rule = _make_rule(
            applicability="SPECIFIC_CUSTOMER",
            applicability_id=str(uuid4()),
        )
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
            customer_id=None,
        )
        assert len(result) == 0

    def test_specific_group_matches_correct_group(self) -> None:
        group_id = str(uuid4())
        rule = _make_rule(applicability="SPECIFIC_GROUP", applicability_id=group_id)
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
            group_id=group_id,
        )
        assert len(result) == 1

    def test_specific_group_excludes_wrong_group(self) -> None:
        rule = _make_rule(applicability="SPECIFIC_GROUP", applicability_id=str(uuid4()))
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
            group_id=str(uuid4()),  # different group
        )
        assert len(result) == 0

    def test_specific_category_matches_correct_category(self) -> None:
        category_id = str(uuid4())
        rule = _make_rule(
            applicability="SPECIFIC_CATEGORY", applicability_id=category_id
        )
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
            category_id=category_id,
        )
        assert len(result) == 1

    def test_specific_category_excludes_null_category(self) -> None:
        rule = _make_rule(
            applicability="SPECIFIC_CATEGORY", applicability_id=str(uuid4())
        )
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
            category_id=None,
        )
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Product Scope
# ---------------------------------------------------------------------------


class TestProductScopeFiltering:
    def test_all_products_applies_to_any_product(self) -> None:
        rule = _make_rule(product_scope="ALL_PRODUCTS")
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
        )
        assert len(result) == 1

    def test_specific_product_matches_correct_product(self) -> None:
        product_id = uuid4()
        rule = _make_rule(
            product_scope="SPECIFIC_PRODUCT", product_scope_id=str(product_id)
        )
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=product_id,
            quantity=Decimal("1"),
            order_value=Decimal("100"),
        )
        assert len(result) == 1

    def test_specific_product_excludes_different_product(self) -> None:
        rule = _make_rule(
            product_scope="SPECIFIC_PRODUCT", product_scope_id=str(uuid4())
        )
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),  # different product
            quantity=Decimal("1"),
            order_value=Decimal("100"),
        )
        assert len(result) == 0

    def test_product_category_matches_correct_category(self) -> None:
        prod_cat_id = str(uuid4())
        rule = _make_rule(
            product_scope="SPECIFIC_CATEGORY", product_scope_id=prod_cat_id
        )
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
            product_category_id=prod_cat_id,
        )
        assert len(result) == 1

    def test_product_category_excludes_null_category(self) -> None:
        rule = _make_rule(
            product_scope="SPECIFIC_CATEGORY", product_scope_id=str(uuid4())
        )
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
            product_category_id=None,
        )
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Threshold Filtering
# ---------------------------------------------------------------------------


class TestThresholdFiltering:
    def test_quantity_meets_minimum(self) -> None:
        rule = _make_rule(minimum_quantity="5")
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("5"),
            order_value=Decimal("100"),
        )
        assert len(result) == 1

    def test_quantity_exceeds_minimum(self) -> None:
        rule = _make_rule(minimum_quantity="5")
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("10"),
            order_value=Decimal("100"),
        )
        assert len(result) == 1

    def test_quantity_below_minimum_excluded(self) -> None:
        rule = _make_rule(minimum_quantity="10")
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("9"),
            order_value=Decimal("100"),
        )
        assert len(result) == 0

    def test_order_value_meets_minimum(self) -> None:
        rule = _make_rule(minimum_order_value="500")
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("500"),
        )
        assert len(result) == 1

    def test_order_value_below_minimum_excluded(self) -> None:
        rule = _make_rule(minimum_order_value="500")
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("499"),
        )
        assert len(result) == 0

    def test_no_thresholds_always_applies(self) -> None:
        rule = _make_rule()  # no minimum_quantity or minimum_order_value
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("0"),
        )
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Stackability Logic
# ---------------------------------------------------------------------------


class TestStackabilityLogic:
    def test_non_stackable_only_highest_priority_wins(self) -> None:
        """Two non-stackable rules — only the higher priority one applies."""
        rule_high = _make_rule(discount_value="20.00", priority=100, is_stackable=False)
        rule_low = _make_rule(discount_value="10.00", priority=10, is_stackable=False)
        service = _make_service([rule_high, rule_low])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
        )
        assert len(result) == 1
        assert result[0].discount_value == Decimal("20.00")

    def test_stackable_rules_all_combine(self) -> None:
        """Two stackable rules both appear in result."""
        rule1 = _make_rule(discount_value="5.00", priority=10, is_stackable=True)
        rule2 = _make_rule(discount_value="3.00", priority=20, is_stackable=True)
        service = _make_service([rule1, rule2])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
        )
        assert len(result) == 2

    def test_mix_of_stackable_and_non_stackable(self) -> None:
        """Stackable rules all apply + highest-priority non-stackable rule applies."""
        stackable1 = _make_rule(discount_value="5.00", priority=50, is_stackable=True)
        stackable2 = _make_rule(discount_value="3.00", priority=30, is_stackable=True)
        non_stackable_high = _make_rule(
            discount_value="15.00", priority=100, is_stackable=False
        )
        non_stackable_low = _make_rule(
            discount_value="8.00", priority=10, is_stackable=False
        )

        # Repository returns rules in priority order
        service = _make_service(
            [non_stackable_high, stackable1, stackable2, non_stackable_low]
        )

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
        )
        # 2 stackable + 1 non-stackable (highest priority)
        assert len(result) == 3
        discount_values = {d.discount_value for d in result}
        assert Decimal("15.00") in discount_values  # highest non-stackable
        assert Decimal("8.00") not in discount_values  # lower non-stackable excluded
        assert Decimal("5.00") in discount_values
        assert Decimal("3.00") in discount_values

    def test_single_non_stackable_applies(self) -> None:
        """Single non-stackable rule always applies."""
        rule = _make_rule(discount_value="10.00", is_stackable=False)
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
        )
        assert len(result) == 1
        assert result[0].discount_value == Decimal("10.00")


# ---------------------------------------------------------------------------
# Priority Ordering
# ---------------------------------------------------------------------------


class TestPriorityOrdering:
    def test_results_sorted_by_priority_descending(self) -> None:
        rule_low = _make_rule(discount_value="5.00", priority=10, is_stackable=True)
        rule_mid = _make_rule(discount_value="8.00", priority=50, is_stackable=True)
        rule_high = _make_rule(discount_value="12.00", priority=100, is_stackable=True)
        service = _make_service([rule_low, rule_mid, rule_high])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
        )
        assert len(result) == 3
        assert result[0].priority == 100
        assert result[1].priority == 50
        assert result[2].priority == 10

    def test_empty_rules_returns_empty_list(self) -> None:
        service = _make_service([])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("0"),
        )
        assert result == []


# ---------------------------------------------------------------------------
# ApplicableDiscount Fields
# ---------------------------------------------------------------------------


class TestApplicableDiscountFields:
    def test_applicable_discount_has_correct_fields(self) -> None:
        rule = _make_rule(
            rule_type="PERCENTAGE",
            discount_value="15.00",
            priority=5,
            is_stackable=True,
        )
        service = _make_service([rule])

        result = service.evaluate_discounts(
            company_id=uuid4(),
            product_id=uuid4(),
            quantity=Decimal("1"),
            order_value=Decimal("100"),
        )
        assert len(result) == 1
        discount = result[0]
        assert discount.rule_id == str(rule.id)
        assert discount.rule_name == rule.name
        assert discount.rule_type == "PERCENTAGE"
        assert discount.discount_value == Decimal("15.00")
        assert discount.is_stackable is True
        assert discount.priority == 5
