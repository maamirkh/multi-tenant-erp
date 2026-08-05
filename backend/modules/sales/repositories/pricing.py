"""Pricing aggregate repositories — Phase 2.

Repositories:
  PriceListRepository         — CRUD + default flag enforcement
  PriceEntryRepository        — price break lookups
  CustomerSpecificPriceRepository — effective-date filtered lookups
  DiscountRuleRepository      — active rule queries with filters

Spec ref: specs/007-sales-management/plan.md — Repository Layer (Pricing)
Task: T069
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from modules.sales.models.pricing import (
    CustomerSpecificPrice,
    DiscountRule,
    PriceEntry,
    PriceList,
)
from modules.sales.repositories import BaseSalesRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PriceListRepository
# ---------------------------------------------------------------------------


class PriceListRepository(BaseSalesRepository[PriceList]):
    """Repository for PriceList aggregate.

    Enforces the single-default invariant: exactly one price list per company
    can have is_default=True. Setting a new default clears the previous one.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=PriceList)

    def get_by_name(self, company_id: UUID, name: str) -> PriceList | None:
        """Return price list by name, or None."""
        return (
            self.db.query(PriceList)
            .filter(
                PriceList.company_id == company_id,
                func.lower(PriceList.name) == func.lower(name),
                PriceList.is_deleted.is_(False),
            )
            .first()
        )

    def get_default(self, company_id: UUID) -> PriceList | None:
        """Return the company default price list, or None."""
        return (
            self.db.query(PriceList)
            .filter(
                PriceList.company_id == company_id,
                PriceList.is_default.is_(True),
                PriceList.is_deleted.is_(False),
            )
            .first()
        )

    def clear_default(self, company_id: UUID) -> None:
        """Clear is_default flag on all price lists for this company."""
        self.db.query(PriceList).filter(
            PriceList.company_id == company_id,
            PriceList.is_default.is_(True),
            PriceList.is_deleted.is_(False),
        ).update({"is_default": False}, synchronize_session="fetch")

    def list_active(
        self,
        company_id: UUID,
        as_of_date: str | None = None,
    ) -> list[PriceList]:
        """Return all active price lists for a company, ordered by priority desc."""
        q = self.db.query(PriceList).filter(
            PriceList.company_id == company_id,
            PriceList.is_active.is_(True),
            PriceList.is_deleted.is_(False),
        )
        if as_of_date:
            q = q.filter(
                PriceList.effective_from <= as_of_date,
                or_(
                    PriceList.effective_to.is_(None),
                    PriceList.effective_to >= as_of_date,
                ),
            )
        return q.order_by(PriceList.priority.desc()).all()

    def list_for_group(
        self,
        company_id: UUID,
        group_id: str,
        as_of_date: str | None = None,
    ) -> list[PriceList]:
        """Return active price lists scoped to a customer group."""
        q = self.db.query(PriceList).filter(
            PriceList.company_id == company_id,
            PriceList.customer_group_id == group_id,
            PriceList.is_active.is_(True),
            PriceList.is_deleted.is_(False),
        )
        if as_of_date:
            q = q.filter(
                PriceList.effective_from <= as_of_date,
                or_(
                    PriceList.effective_to.is_(None),
                    PriceList.effective_to >= as_of_date,
                ),
            )
        return q.order_by(PriceList.priority.desc()).all()

    def list_for_category(
        self,
        company_id: UUID,
        category_id: str,
        as_of_date: str | None = None,
    ) -> list[PriceList]:
        """Return active price lists scoped to a customer category."""
        q = self.db.query(PriceList).filter(
            PriceList.company_id == company_id,
            PriceList.customer_category_id == category_id,
            PriceList.is_active.is_(True),
            PriceList.is_deleted.is_(False),
        )
        if as_of_date:
            q = q.filter(
                PriceList.effective_from <= as_of_date,
                or_(
                    PriceList.effective_to.is_(None),
                    PriceList.effective_to >= as_of_date,
                ),
            )
        return q.order_by(PriceList.priority.desc()).all()

    def paginated(
        self,
        company_id: UUID,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[PriceList], int]:
        """Return paginated price lists for a company."""
        q = self.db.query(PriceList).filter(
            PriceList.company_id == company_id,
            PriceList.is_deleted.is_(False),
        )
        if is_active is not None:
            q = q.filter(PriceList.is_active == is_active)
        total = q.count()
        items = q.order_by(PriceList.priority.desc()).offset(skip).limit(limit).all()
        return items, total


# ---------------------------------------------------------------------------
# PriceEntryRepository
# ---------------------------------------------------------------------------


class PriceEntryRepository(BaseSalesRepository[PriceEntry]):
    """Repository for PriceEntry (product prices within a price list)."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=PriceEntry)

    def get_for_list(self, company_id: UUID, price_list_id: UUID) -> list[PriceEntry]:
        """Return all active entries for a price list."""
        return (
            self.db.query(PriceEntry)
            .filter(
                PriceEntry.company_id == company_id,
                PriceEntry.price_list_id == str(price_list_id),
                PriceEntry.is_deleted.is_(False),
            )
            .order_by(PriceEntry.minimum_quantity.desc())
            .all()
        )

    def get_for_product(
        self,
        company_id: UUID,
        price_list_id: UUID,
        product_id: UUID,
    ) -> list[PriceEntry]:
        """Return all price break entries for a product in a price list, ordered by min_qty desc."""
        return (
            self.db.query(PriceEntry)
            .filter(
                PriceEntry.company_id == company_id,
                PriceEntry.price_list_id == str(price_list_id),
                PriceEntry.product_id == str(product_id),
                PriceEntry.is_deleted.is_(False),
            )
            .order_by(PriceEntry.minimum_quantity.desc())
            .all()
        )

    def resolve_for_quantity(
        self,
        company_id: UUID,
        price_list_id: UUID,
        product_id: UUID,
        quantity: Decimal,
    ) -> PriceEntry | None:
        """Return the applicable price entry for a given quantity.

        Selects the entry with the highest minimum_quantity that is <= the
        ordered quantity (quantity break logic).
        """
        return (
            self.db.query(PriceEntry)
            .filter(
                PriceEntry.company_id == company_id,
                PriceEntry.price_list_id == str(price_list_id),
                PriceEntry.product_id == str(product_id),
                PriceEntry.minimum_quantity <= quantity,
                PriceEntry.is_deleted.is_(False),
            )
            .order_by(PriceEntry.minimum_quantity.desc())
            .first()
        )

    def delete_for_list(self, company_id: UUID, price_list_id: UUID) -> int:
        """Soft-delete all entries for a price list."""
        from core.utils.datetime import utcnow

        updated = (
            self.db.query(PriceEntry)
            .filter(
                PriceEntry.company_id == company_id,
                PriceEntry.price_list_id == str(price_list_id),
                PriceEntry.is_deleted.is_(False),
            )
            .update(
                {"is_deleted": True, "deleted_at": utcnow()},
                synchronize_session="fetch",
            )
        )
        return updated


# ---------------------------------------------------------------------------
# CustomerSpecificPriceRepository
# ---------------------------------------------------------------------------


class CustomerSpecificPriceRepository(BaseSalesRepository[CustomerSpecificPrice]):
    """Repository for CustomerSpecificPrice records."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CustomerSpecificPrice)

    def resolve(
        self,
        company_id: UUID,
        customer_id: UUID,
        product_id: UUID,
        quantity: Decimal,
        as_of_date: str | None = None,
    ) -> CustomerSpecificPrice | None:
        """Return the best customer-specific price for a given quantity and date.

        Selects the entry with highest min_quantity <= ordered quantity,
        filtered by effective date.
        """
        q = self.db.query(CustomerSpecificPrice).filter(
            CustomerSpecificPrice.company_id == company_id,
            CustomerSpecificPrice.customer_id == str(customer_id),
            CustomerSpecificPrice.product_id == str(product_id),
            CustomerSpecificPrice.minimum_quantity <= quantity,
            CustomerSpecificPrice.is_deleted.is_(False),
        )
        if as_of_date:
            q = q.filter(
                CustomerSpecificPrice.effective_from <= as_of_date,
                or_(
                    CustomerSpecificPrice.effective_to.is_(None),
                    CustomerSpecificPrice.effective_to >= as_of_date,
                ),
            )
        return q.order_by(CustomerSpecificPrice.minimum_quantity.desc()).first()

    def list_for_customer(
        self,
        company_id: UUID,
        customer_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CustomerSpecificPrice], int]:
        """Return paginated customer-specific prices for a customer."""
        q = self.db.query(CustomerSpecificPrice).filter(
            CustomerSpecificPrice.company_id == company_id,
            CustomerSpecificPrice.customer_id == str(customer_id),
            CustomerSpecificPrice.is_deleted.is_(False),
        )
        total = q.count()
        items = q.offset(skip).limit(limit).all()
        return items, total

    def list_all(
        self,
        company_id: UUID,
        customer_id: UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[CustomerSpecificPrice], int]:
        """Return paginated customer-specific prices, optionally filtered by customer."""
        q = self.db.query(CustomerSpecificPrice).filter(
            CustomerSpecificPrice.company_id == company_id,
            CustomerSpecificPrice.is_deleted.is_(False),
        )
        if customer_id is not None:
            q = q.filter(CustomerSpecificPrice.customer_id == str(customer_id))
        total = q.count()
        items = q.offset(skip).limit(limit).all()
        return items, total


# ---------------------------------------------------------------------------
# DiscountRuleRepository
# ---------------------------------------------------------------------------


class DiscountRuleRepository(BaseSalesRepository[DiscountRule]):
    """Repository for DiscountRule records."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=DiscountRule)

    def get_active_rules(
        self,
        company_id: UUID,
        as_of_date: str | None = None,
    ) -> list[DiscountRule]:
        """Return all active discount rules for a company, ordered by priority desc."""
        q = self.db.query(DiscountRule).filter(
            DiscountRule.company_id == company_id,
            DiscountRule.is_active.is_(True),
            DiscountRule.is_deleted.is_(False),
        )
        if as_of_date:
            q = q.filter(
                DiscountRule.effective_from <= as_of_date,
                or_(
                    DiscountRule.effective_to.is_(None),
                    DiscountRule.effective_to >= as_of_date,
                ),
            )
        return q.order_by(DiscountRule.priority.desc()).all()

    def paginated(
        self,
        company_id: UUID,
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[DiscountRule], int]:
        """Return paginated discount rules."""
        q = self.db.query(DiscountRule).filter(
            DiscountRule.company_id == company_id,
            DiscountRule.is_deleted.is_(False),
        )
        if is_active is not None:
            q = q.filter(DiscountRule.is_active == is_active)
        total = q.count()
        items = q.order_by(DiscountRule.priority.desc()).offset(skip).limit(limit).all()
        return items, total
