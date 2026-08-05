"""Pricing application services — Phase 2.

Services:
  PricingService      — 7-level price resolution hierarchy
  DiscountService     — discount rule evaluation with priority and stackability
  MarginGuardService  — minimum margin validation (warn / block)
  PriceListService    — CRUD + default flag management

7-Level Price Resolution (Research Decision 3):
  Level 1: Manual Override        — explicit price provided by caller
  Level 2: Customer-Specific      — active CustomerSpecificPrice for customer+product
  Level 3: Customer Group         — PriceList scoped to customer's CustomerGroup
  Level 4: Customer Category      — PriceList scoped to customer's CustomerCategory
  Level 5: Active Price List      — highest-priority active list (unscoped)
  Level 6: Default Price List     — price list with is_default=True
  Level 7: Product Base Price     — fallback (0.0 when no price configured)

Spec ref: specs/007-sales-management/plan.md §Phase 3, research.md §Decision 3
Task: T066, T067, T068
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
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

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

PRICE_SOURCE_MANUAL = "MANUAL"
PRICE_SOURCE_CUSTOMER_SPECIFIC = "CUSTOMER_SPECIFIC"
PRICE_SOURCE_CUSTOMER_GROUP = "GROUP"
PRICE_SOURCE_CUSTOMER_CATEGORY = "CATEGORY"
PRICE_SOURCE_PRICE_LIST = "PRICE_LIST"
PRICE_SOURCE_DEFAULT_LIST = "DEFAULT_LIST"
PRICE_SOURCE_BASE_PRICE = "BASE_PRICE"


@dataclass
class PriceResolution:
    """Result of price resolution for a product + customer combination."""

    unit_price: Decimal
    price_source: str  # one of PRICE_SOURCE_* constants
    price_list_id: str | None = None
    price_list_name: str | None = None
    price_entry_id: str | None = None
    customer_specific_price_id: str | None = None
    resolution_level: int = 7  # 1–7 matching the hierarchy


@dataclass
class ApplicableDiscount:
    """A discount rule that applies to the current line/order."""

    rule_id: str
    rule_name: str
    rule_type: str  # PERCENTAGE / FIXED_AMOUNT / VOLUME / PROMOTIONAL
    discount_value: Decimal
    is_stackable: bool
    priority: int


@dataclass
class DiscountResolution:
    """Result of discount evaluation — applicable discounts after priority and stackability."""

    applicable_discounts: list[ApplicableDiscount]
    total_discount_percentage: Decimal
    total_discount_amount: Decimal
    final_price: Decimal


@dataclass
class MarginResult:
    """Result of margin guard check."""

    margin_percentage: Decimal
    passes: bool  # False when margin < threshold
    action: str  # "OK" / "WARN" / "BLOCK"
    threshold_pct: Decimal


# ---------------------------------------------------------------------------
# PricingService — 7-level resolution
# ---------------------------------------------------------------------------


class PricingService:
    """Application service for price resolution.

    Implements the 7-level price resolution hierarchy per research.md Decision 3.
    The resolved price is captured at document creation time and is immutable
    thereafter (price-at-point-of-sale invariant).

    Args:
        db:              SQLAlchemy session
        price_list_repo: PriceListRepository instance
        entry_repo:      PriceEntryRepository instance
        specific_repo:   CustomerSpecificPriceRepository instance
    """

    def __init__(
        self,
        db: Session,
        price_list_repo: PriceListRepository,
        entry_repo: PriceEntryRepository,
        specific_repo: CustomerSpecificPriceRepository,
    ) -> None:
        self.db = db
        self._pl_repo = price_list_repo
        self._entry_repo = entry_repo
        self._specific_repo = specific_repo

    def resolve_price(
        self,
        company_id: UUID,
        product_id: UUID,
        quantity: Decimal,
        customer_id: UUID | None = None,
        group_id: str | None = None,
        category_id: str | None = None,
        manual_price: Decimal | None = None,
        as_of_date: str | None = None,
    ) -> PriceResolution:
        """Resolve the unit price for a product using the 7-level hierarchy.

        Args:
            company_id:   Company scope
            product_id:   Product to price
            quantity:     Ordered quantity (for quantity break selection)
            customer_id:  Customer (needed for levels 2–4)
            group_id:     Customer's group_id string (for level 3)
            category_id:  Customer's category_id string (for level 4)
            manual_price: Explicit override price (level 1)
            as_of_date:   ISO date string YYYY-MM-DD for effective date filtering

        Returns:
            PriceResolution with resolved price and metadata.
        """
        # Level 1: Manual Override
        if manual_price is not None:
            logger.debug("price.resolve level=1 MANUAL product=%s", product_id)
            return PriceResolution(
                unit_price=manual_price,
                price_source=PRICE_SOURCE_MANUAL,
                resolution_level=1,
            )

        # Level 2: Customer-Specific Price
        if customer_id is not None:
            specific = self._specific_repo.resolve(
                company_id=company_id,
                customer_id=customer_id,
                product_id=product_id,
                quantity=quantity,
                as_of_date=as_of_date,
            )
            if specific is not None:
                logger.debug(
                    "price.resolve level=2 CUSTOMER_SPECIFIC product=%s price=%s",
                    product_id,
                    specific.unit_price,
                )
                return PriceResolution(
                    unit_price=specific.unit_price,
                    price_source=PRICE_SOURCE_CUSTOMER_SPECIFIC,
                    customer_specific_price_id=str(specific.id),
                    resolution_level=2,
                )

        # Level 3: Customer Group Price List
        if group_id:
            group_lists = self._pl_repo.list_for_group(
                company_id=company_id,
                group_id=group_id,
                as_of_date=as_of_date,
            )
            result = self._find_price_in_lists(
                company_id=company_id,
                product_id=product_id,
                quantity=quantity,
                price_lists=group_lists,
                level=3,
                source=PRICE_SOURCE_CUSTOMER_GROUP,
            )
            if result is not None:
                return result

        # Level 4: Customer Category Price List
        if category_id:
            cat_lists = self._pl_repo.list_for_category(
                company_id=company_id,
                category_id=category_id,
                as_of_date=as_of_date,
            )
            result = self._find_price_in_lists(
                company_id=company_id,
                product_id=product_id,
                quantity=quantity,
                price_lists=cat_lists,
                level=4,
                source=PRICE_SOURCE_CUSTOMER_CATEGORY,
            )
            if result is not None:
                return result

        # Levels 5 & 6: Active Price Lists (non-scoped) and Default Price List
        all_active = self._pl_repo.list_active(
            company_id=company_id,
            as_of_date=as_of_date,
        )
        # Separate default from general active lists
        general_lists = [
            pl
            for pl in all_active
            if not pl.is_default
            and pl.customer_group_id is None
            and pl.customer_category_id is None
        ]
        default_lists = [pl for pl in all_active if pl.is_default]

        # Level 5: Active Price List (non-default, non-scoped, highest priority)
        result = self._find_price_in_lists(
            company_id=company_id,
            product_id=product_id,
            quantity=quantity,
            price_lists=general_lists,
            level=5,
            source=PRICE_SOURCE_PRICE_LIST,
        )
        if result is not None:
            return result

        # Level 6: Default Price List
        result = self._find_price_in_lists(
            company_id=company_id,
            product_id=product_id,
            quantity=quantity,
            price_lists=default_lists,
            level=6,
            source=PRICE_SOURCE_DEFAULT_LIST,
        )
        if result is not None:
            return result

        # Level 7: Product Base Price (fallback — 0.0 when no price configured)
        logger.debug(
            "price.resolve level=7 BASE_PRICE product=%s — no price configured",
            product_id,
        )
        return PriceResolution(
            unit_price=Decimal("0"),
            price_source=PRICE_SOURCE_BASE_PRICE,
            resolution_level=7,
        )

    def _find_price_in_lists(
        self,
        company_id: UUID,
        product_id: UUID,
        quantity: Decimal,
        price_lists: list[PriceList],
        level: int,
        source: str,
    ) -> PriceResolution | None:
        """Search price lists in order and return the first matching PriceEntry."""
        for pl in price_lists:
            from uuid import UUID as _UUID

            pl_id = pl.id if isinstance(pl.id, _UUID) else _UUID(str(pl.id))
            entry = self._entry_repo.resolve_for_quantity(
                company_id=company_id,
                price_list_id=pl_id,
                product_id=product_id,
                quantity=quantity,
            )
            if entry is not None:
                logger.debug(
                    "price.resolve level=%d source=%s product=%s price=%s list=%s",
                    level,
                    source,
                    product_id,
                    entry.unit_price,
                    pl.name,
                )
                return PriceResolution(
                    unit_price=entry.unit_price,
                    price_source=source,
                    price_list_id=str(pl.id),
                    price_list_name=pl.name,
                    price_entry_id=str(entry.id),
                    resolution_level=level,
                )
        return None


# ---------------------------------------------------------------------------
# DiscountService
# ---------------------------------------------------------------------------


class DiscountService:
    """Application service for discount rule evaluation.

    Evaluates discount rules against a line item context, returning the
    applicable discounts in priority order with stackability applied.

    Args:
        db:              SQLAlchemy session
        discount_repo:   DiscountRuleRepository instance
    """

    def __init__(
        self,
        db: Session,
        discount_repo: DiscountRuleRepository,
    ) -> None:
        self.db = db
        self._repo = discount_repo

    def evaluate_discounts(
        self,
        company_id: UUID,
        product_id: UUID,
        quantity: Decimal,
        order_value: Decimal,
        customer_id: UUID | None = None,
        group_id: str | None = None,
        category_id: str | None = None,
        product_category_id: str | None = None,
        as_of_date: str | None = None,
    ) -> list[ApplicableDiscount]:
        """Evaluate all active discount rules and return applicable discounts.

        Rules are evaluated in priority order (highest first). Non-stackable
        rules compete — only the highest-priority non-stackable rule is applied.
        Stackable rules are combined.

        Args:
            company_id:          Company scope
            product_id:          Line item product
            quantity:            Ordered quantity
            order_value:         Total order value (for minimum_order_value rules)
            customer_id:         Customer (for SPECIFIC_CUSTOMER applicability)
            group_id:            Customer's group_id (for SPECIFIC_GROUP applicability)
            category_id:         Customer's category_id (for SPECIFIC_CATEGORY customer filter)
            product_category_id: Product's category_id (for SPECIFIC_CATEGORY product filter)
            as_of_date:          ISO date string for effective date filtering

        Returns:
            List of applicable ApplicableDiscount objects in priority order.
        """
        all_active = self._repo.get_active_rules(
            company_id=company_id,
            as_of_date=as_of_date,
        )

        applicable: list[ApplicableDiscount] = []

        for rule in all_active:
            # Customer scope filter
            if not self._matches_customer_scope(
                rule=rule,
                customer_id=customer_id,
                group_id=group_id,
                category_id=category_id,
            ):
                continue

            # Product scope filter
            if not self._matches_product_scope(
                rule=rule,
                product_id=product_id,
                product_category_id=product_category_id,
            ):
                continue

            # Quantity threshold
            if rule.minimum_quantity is not None and quantity < rule.minimum_quantity:
                continue

            # Order value threshold
            if (
                rule.minimum_order_value is not None
                and order_value < rule.minimum_order_value
            ):
                continue

            applicable.append(
                ApplicableDiscount(
                    rule_id=str(rule.id),
                    rule_name=rule.name,
                    rule_type=rule.rule_type,
                    discount_value=rule.discount_value,
                    is_stackable=rule.is_stackable,
                    priority=rule.priority,
                )
            )

        # Apply stackability logic:
        # - Collect all stackable discounts
        # - From non-stackable: keep only the highest-priority one
        stackable = [d for d in applicable if d.is_stackable]
        non_stackable = [d for d in applicable if not d.is_stackable]

        result: list[ApplicableDiscount] = list(stackable)
        if non_stackable:
            # Already sorted by priority desc from repository
            result.append(non_stackable[0])

        # Re-sort by priority desc
        result.sort(key=lambda d: d.priority, reverse=True)
        return result

    def _matches_customer_scope(
        self,
        rule: DiscountRule,
        customer_id: UUID | None,
        group_id: str | None,
        category_id: str | None,
    ) -> bool:
        """Return True if the rule applies to the given customer context."""
        if rule.applicability == "ALL_CUSTOMERS":
            return True
        if rule.applicability == "SPECIFIC_CUSTOMER":
            return customer_id is not None and rule.applicability_id == str(customer_id)
        if rule.applicability == "SPECIFIC_GROUP":
            return group_id is not None and rule.applicability_id == group_id
        if rule.applicability == "SPECIFIC_CATEGORY":
            return category_id is not None and rule.applicability_id == category_id
        return False

    def _matches_product_scope(
        self,
        rule: DiscountRule,
        product_id: UUID,
        product_category_id: str | None,
    ) -> bool:
        """Return True if the rule applies to the given product."""
        if rule.product_scope == "ALL_PRODUCTS":
            return True
        if rule.product_scope == "SPECIFIC_PRODUCT":
            return rule.product_scope_id == str(product_id)
        if rule.product_scope == "SPECIFIC_CATEGORY":
            return (
                product_category_id is not None
                and rule.product_scope_id == product_category_id
            )
        return False


# ---------------------------------------------------------------------------
# MarginGuardService
# ---------------------------------------------------------------------------


class MarginGuardService:
    """Service for minimum margin validation.

    Computes the gross margin percentage and compares against a configurable
    threshold. Returns a MarginResult indicating OK / WARN / BLOCK.

    Configured behaviour:
      - If minimum_margin_percentage is None: margin guard is disabled → always OK
      - If unit_price <= 0 or cost_price <= 0: cannot compute margin → returns WARN
      - margin < threshold: WARN (or BLOCK if block_on_low_margin=True)
      - margin >= threshold: OK
    """

    def check_margin(
        self,
        unit_price: Decimal,
        cost_price: Decimal,
        min_margin_pct: Decimal | None,
        block_on_low_margin: bool = False,
    ) -> MarginResult:
        """Check whether the unit price satisfies the minimum margin requirement.

        Args:
            unit_price:           Resolved unit price (selling price)
            cost_price:           Product cost price
            min_margin_pct:       Minimum margin percentage threshold (0–100)
            block_on_low_margin:  If True, action is BLOCK instead of WARN when below threshold

        Returns:
            MarginResult with margin_percentage, passes, action, and threshold_pct
        """
        threshold = min_margin_pct if min_margin_pct is not None else Decimal("0")

        # Guard disabled
        if min_margin_pct is None:
            return MarginResult(
                margin_percentage=Decimal("0"),
                passes=True,
                action="OK",
                threshold_pct=threshold,
            )

        # Cannot compute margin for zero or negative prices
        if unit_price <= Decimal("0") or cost_price <= Decimal("0"):
            return MarginResult(
                margin_percentage=Decimal("0"),
                passes=False,
                action="WARN",
                threshold_pct=threshold,
            )

        margin_pct = ((unit_price - cost_price) / unit_price) * Decimal("100")

        passes = margin_pct >= threshold
        if passes:
            action = "OK"
        elif block_on_low_margin:
            action = "BLOCK"
        else:
            action = "WARN"

        logger.debug(
            "margin.check unit_price=%s cost_price=%s margin_pct=%s threshold=%s action=%s",
            unit_price,
            cost_price,
            margin_pct,
            threshold,
            action,
        )

        return MarginResult(
            margin_percentage=margin_pct.quantize(Decimal("0.01")),
            passes=passes,
            action=action,
            threshold_pct=threshold,
        )


# ---------------------------------------------------------------------------
# PriceListService — CRUD + default flag management
# ---------------------------------------------------------------------------


class PriceListService:
    """Application service for PriceList + PriceEntry CRUD.

    Enforces the single-default invariant: only one price list per company
    can have is_default=True.
    """

    def __init__(
        self,
        db: Session,
        price_list_repo: PriceListRepository,
        entry_repo: PriceEntryRepository,
    ) -> None:
        self.db = db
        self._repo = price_list_repo
        self._entry_repo = entry_repo

    def create(
        self,
        company_id: UUID,
        name: str,
        currency_code: str,
        effective_from: str,
        effective_to: str | None = None,
        is_default: bool = False,
        is_active: bool = True,
        priority: int = 0,
        description: str | None = None,
        customer_group_id: UUID | None = None,
        customer_category_id: UUID | None = None,
        created_by: UUID | None = None,
    ) -> PriceList:
        """Create a new price list."""
        existing = self._repo.get_by_name(company_id=company_id, name=name)
        if existing is not None:
            raise ConflictException(
                f"Price list with name '{name}' already exists for this company"
            )

        if is_default:
            self._repo.clear_default(company_id=company_id)

        pl = PriceList(
            company_id=company_id,
            name=name,
            description=description,
            currency_code=currency_code.upper(),
            effective_from=effective_from,
            effective_to=effective_to,
            is_default=is_default,
            is_active=is_active,
            priority=priority,
            customer_group_id=str(customer_group_id) if customer_group_id else None,
            customer_category_id=(
                str(customer_category_id) if customer_category_id else None
            ),
            version=1,
            created_by=created_by,
        )
        created = self._repo.create(pl)
        logger.info(
            "price_list.created company=%s id=%s name=%s",
            company_id,
            created.id,
            name,
        )
        return created

    def update(
        self,
        company_id: UUID,
        price_list_id: UUID,
        updated_by: UUID | None = None,
        **kwargs: object,
    ) -> PriceList:
        """Update a price list. Handles default flag enforcement."""
        pl = self._get_or_raise(company_id, price_list_id)

        is_default = kwargs.pop("is_default", None)
        if is_default and not pl.is_default:
            self._repo.clear_default(company_id=company_id)
            pl.is_default = True
        elif is_default is False:
            pl.is_default = False

        for key, value in kwargs.items():
            if value is not None and hasattr(pl, key):
                setattr(pl, key, value)

        pl.version = (pl.version or 1) + 1
        return self._repo.update(pl)

    def delete(self, company_id: UUID, price_list_id: UUID) -> None:
        """Soft-delete a price list and all its entries."""
        pl = self._get_or_raise(company_id, price_list_id)
        from core.utils.datetime import utcnow

        pl.is_deleted = True
        pl.deleted_at = utcnow()
        self._repo.update(pl)
        self._entry_repo.delete_for_list(
            company_id=company_id, price_list_id=price_list_id
        )

    def get_by_id(self, company_id: UUID, price_list_id: UUID) -> PriceList:
        """Return a price list by ID or raise NotFoundException."""
        return self._get_or_raise(company_id, price_list_id)

    def _get_or_raise(self, company_id: UUID, price_list_id: UUID) -> PriceList:
        pl = self._repo.get_by_id_or_none(id=price_list_id, company_id=company_id)
        if pl is None:
            raise NotFoundException(f"Price list '{price_list_id}' not found")
        return pl

    # ---- PriceEntry management ----

    def add_entry(
        self,
        company_id: UUID,
        price_list_id: UUID,
        product_id: UUID,
        unit_price: Decimal,
        unit_of_measure: str,
        minimum_quantity: Decimal = Decimal("1"),
        created_by: UUID | None = None,
    ) -> PriceEntry:
        """Add a price entry to a price list."""
        self._get_or_raise(company_id, price_list_id)
        entry = PriceEntry(
            company_id=company_id,
            price_list_id=str(price_list_id),
            product_id=str(product_id),
            unit_price=unit_price,
            minimum_quantity=minimum_quantity,
            unit_of_measure=unit_of_measure.upper(),
            created_by=created_by,
        )
        return self._entry_repo.create(entry)

    def update_entry(
        self,
        company_id: UUID,
        entry_id: UUID,
        **kwargs: object,
    ) -> PriceEntry:
        """Update a price entry."""
        entry = self._entry_repo.get_by_id_or_none(id=entry_id, company_id=company_id)
        if entry is None:
            raise NotFoundException(f"Price entry '{entry_id}' not found")
        for key, value in kwargs.items():
            if value is not None and hasattr(entry, key):
                setattr(entry, key, value)
        return self._entry_repo.update(entry)

    def delete_entry(self, company_id: UUID, entry_id: UUID) -> None:
        """Soft-delete a price entry."""
        entry = self._entry_repo.get_by_id_or_none(id=entry_id, company_id=company_id)
        if entry is None:
            raise NotFoundException(f"Price entry '{entry_id}' not found")
        from core.utils.datetime import utcnow

        entry.is_deleted = True
        entry.deleted_at = utcnow()
        self._entry_repo.update(entry)


# ---------------------------------------------------------------------------
# CustomerSpecificPriceService — CRUD
# ---------------------------------------------------------------------------


class CustomerSpecificPriceService:
    """Application service for CustomerSpecificPrice CRUD."""

    def __init__(
        self,
        db: Session,
        repo: CustomerSpecificPriceRepository,
    ) -> None:
        self.db = db
        self._repo = repo

    def create(
        self,
        company_id: UUID,
        customer_id: UUID,
        product_id: UUID,
        unit_price: Decimal,
        effective_from: str,
        effective_to: str | None = None,
        minimum_quantity: Decimal = Decimal("1"),
        created_by: UUID | None = None,
    ) -> CustomerSpecificPrice:
        """Create a customer-specific price override."""
        record = CustomerSpecificPrice(
            company_id=company_id,
            customer_id=str(customer_id),
            product_id=str(product_id),
            unit_price=unit_price,
            effective_from=effective_from,
            effective_to=effective_to,
            minimum_quantity=minimum_quantity,
            created_by=created_by,
        )
        created = self._repo.create(record)
        logger.info(
            "customer_specific_price.created company=%s customer=%s product=%s",
            company_id,
            customer_id,
            product_id,
        )
        return created

    def update(
        self,
        company_id: UUID,
        record_id: UUID,
        **kwargs: object,
    ) -> CustomerSpecificPrice:
        """Update a customer-specific price."""
        record = self._repo.get_by_id_or_none(id=record_id, company_id=company_id)
        if record is None:
            raise NotFoundException(f"Customer-specific price '{record_id}' not found")
        for key, value in kwargs.items():
            if value is not None and hasattr(record, key):
                setattr(record, key, value)
        return self._repo.update(record)

    def delete(self, company_id: UUID, record_id: UUID) -> None:
        """Soft-delete a customer-specific price."""
        record = self._repo.get_by_id_or_none(id=record_id, company_id=company_id)
        if record is None:
            raise NotFoundException(f"Customer-specific price '{record_id}' not found")
        from core.utils.datetime import utcnow

        record.is_deleted = True
        record.deleted_at = utcnow()
        self._repo.update(record)

    def get_by_id(self, company_id: UUID, record_id: UUID) -> CustomerSpecificPrice:
        """Return a customer-specific price or raise NotFoundException."""
        record = self._repo.get_by_id_or_none(id=record_id, company_id=company_id)
        if record is None:
            raise NotFoundException(f"Customer-specific price '{record_id}' not found")
        return record


# ---------------------------------------------------------------------------
# DiscountRuleService — CRUD
# ---------------------------------------------------------------------------


class DiscountRuleService:
    """Application service for DiscountRule CRUD."""

    def __init__(
        self,
        db: Session,
        repo: DiscountRuleRepository,
    ) -> None:
        self.db = db
        self._repo = repo

    def create(
        self,
        company_id: UUID,
        name: str,
        rule_type: str,
        discount_value: Decimal,
        effective_from: str,
        applicability: str = "ALL_CUSTOMERS",
        applicability_id: UUID | None = None,
        product_scope: str = "ALL_PRODUCTS",
        product_scope_id: UUID | None = None,
        minimum_quantity: Decimal | None = None,
        minimum_order_value: Decimal | None = None,
        effective_to: str | None = None,
        is_active: bool = True,
        priority: int = 0,
        is_stackable: bool = False,
        created_by: UUID | None = None,
    ) -> DiscountRule:
        """Create a discount rule."""
        rule = DiscountRule(
            company_id=company_id,
            name=name,
            rule_type=rule_type.upper(),
            applicability=applicability.upper(),
            applicability_id=str(applicability_id) if applicability_id else None,
            product_scope=product_scope.upper(),
            product_scope_id=str(product_scope_id) if product_scope_id else None,
            minimum_quantity=minimum_quantity,
            minimum_order_value=minimum_order_value,
            discount_value=discount_value,
            effective_from=effective_from,
            effective_to=effective_to,
            is_active=is_active,
            priority=priority,
            is_stackable=is_stackable,
            created_by=created_by,
        )
        created = self._repo.create(rule)
        logger.info(
            "discount_rule.created company=%s id=%s name=%s",
            company_id,
            created.id,
            name,
        )
        return created

    def update(
        self,
        company_id: UUID,
        rule_id: UUID,
        **kwargs: object,
    ) -> DiscountRule:
        """Update a discount rule."""
        rule = self._get_or_raise(company_id, rule_id)
        for key, value in kwargs.items():
            if value is not None and hasattr(rule, key):
                setattr(rule, key, value)
        return self._repo.update(rule)

    def delete(self, company_id: UUID, rule_id: UUID) -> None:
        """Soft-delete a discount rule."""
        rule = self._get_or_raise(company_id, rule_id)
        from core.utils.datetime import utcnow

        rule.is_deleted = True
        rule.deleted_at = utcnow()
        self._repo.update(rule)

    def get_by_id(self, company_id: UUID, rule_id: UUID) -> DiscountRule:
        """Return a discount rule or raise NotFoundException."""
        return self._get_or_raise(company_id, rule_id)

    def _get_or_raise(self, company_id: UUID, rule_id: UUID) -> DiscountRule:
        rule = self._repo.get_by_id_or_none(id=rule_id, company_id=company_id)
        if rule is None:
            raise NotFoundException(f"Discount rule '{rule_id}' not found")
        return rule
