"""Repositories for sales master data entities.

Covers:
  - CustomerCategoryRepository    — code-unique customer categories
  - CustomerGroupRepository       — code-unique customer groups
  - SalesPaymentTermRepository    — code-unique payment terms
  - SalesReasonCodeRepository     — typed reason codes
  - SalesConfigurationRepository  — company-level configuration (singleton per company)

All repositories enforce company_id isolation via BaseSalesRepository.

Spec ref: specs/007-sales-management/data-model.md §Master Data Entities
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.sales.models.master import (
    CustomerCategory,
    CustomerGroup,
    SalesConfiguration,
    SalesPaymentTerm,
    SalesReasonCode,
)
from modules.sales.repositories import BaseSalesRepository

logger = logging.getLogger(__name__)


class CustomerCategoryRepository(BaseSalesRepository[CustomerCategory]):
    """Data-access layer for the ``customer_categories`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CustomerCategory)

    def get_by_code(self, company_id: UUID, code: str) -> CustomerCategory | None:
        """Return the category with the given code for this company, or None."""
        stmt = (
            select(CustomerCategory)
            .where(CustomerCategory.company_id == company_id)
            .where(CustomerCategory.code == code)
            .where(CustomerCategory.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_active(self, company_id: UUID) -> list[CustomerCategory]:
        """Return all active customer categories for a company."""
        stmt = (
            select(CustomerCategory)
            .where(CustomerCategory.company_id == company_id)
            .where(CustomerCategory.is_active == True)  # noqa: E712
            .where(CustomerCategory.is_deleted == False)  # noqa: E712
            .order_by(CustomerCategory.name)
        )
        return list(self.db.execute(stmt).scalars().all())


class CustomerGroupRepository(BaseSalesRepository[CustomerGroup]):
    """Data-access layer for the ``customer_groups`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=CustomerGroup)

    def get_by_code(self, company_id: UUID, code: str) -> CustomerGroup | None:
        """Return the group with the given code for this company, or None."""
        stmt = (
            select(CustomerGroup)
            .where(CustomerGroup.company_id == company_id)
            .where(CustomerGroup.code == code)
            .where(CustomerGroup.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_active(self, company_id: UUID) -> list[CustomerGroup]:
        """Return all active customer groups for a company."""
        stmt = (
            select(CustomerGroup)
            .where(CustomerGroup.company_id == company_id)
            .where(CustomerGroup.is_active == True)  # noqa: E712
            .where(CustomerGroup.is_deleted == False)  # noqa: E712
            .order_by(CustomerGroup.name)
        )
        return list(self.db.execute(stmt).scalars().all())


class SalesPaymentTermRepository(BaseSalesRepository[SalesPaymentTerm]):
    """Data-access layer for the ``sales_payment_terms`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SalesPaymentTerm)

    def get_by_code(self, company_id: UUID, code: str) -> SalesPaymentTerm | None:
        """Return the payment term with the given code for this company, or None."""
        stmt = (
            select(SalesPaymentTerm)
            .where(SalesPaymentTerm.company_id == company_id)
            .where(SalesPaymentTerm.code == code)
            .where(SalesPaymentTerm.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_active(self, company_id: UUID) -> list[SalesPaymentTerm]:
        """Return all active payment terms for a company."""
        stmt = (
            select(SalesPaymentTerm)
            .where(SalesPaymentTerm.company_id == company_id)
            .where(SalesPaymentTerm.is_active == True)  # noqa: E712
            .where(SalesPaymentTerm.is_deleted == False)  # noqa: E712
            .order_by(SalesPaymentTerm.name)
        )
        return list(self.db.execute(stmt).scalars().all())


class SalesReasonCodeRepository(BaseSalesRepository[SalesReasonCode]):
    """Data-access layer for the ``sales_reason_codes`` table."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SalesReasonCode)

    def get_by_code(
        self, company_id: UUID, code: str, reason_type: str
    ) -> SalesReasonCode | None:
        """Return the reason code matching (company_id, code, reason_type), or None."""
        stmt = (
            select(SalesReasonCode)
            .where(SalesReasonCode.company_id == company_id)
            .where(SalesReasonCode.code == code)
            .where(SalesReasonCode.reason_type == reason_type)
            .where(SalesReasonCode.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def get_by_type(self, company_id: UUID, reason_type: str) -> list[SalesReasonCode]:
        """Return all active reason codes of the given type for a company."""
        stmt = (
            select(SalesReasonCode)
            .where(SalesReasonCode.company_id == company_id)
            .where(SalesReasonCode.reason_type == reason_type)
            .where(SalesReasonCode.is_active == True)  # noqa: E712
            .where(SalesReasonCode.is_deleted == False)  # noqa: E712
            .order_by(SalesReasonCode.name)
        )
        return list(self.db.execute(stmt).scalars().all())


class SalesConfigurationRepository(BaseSalesRepository[SalesConfiguration]):
    """Data-access layer for the ``sales_configuration`` table.

    One configuration record per company. Uses upsert semantics.
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=SalesConfiguration)

    def get_for_company(self, company_id: UUID) -> SalesConfiguration | None:
        """Return the sales configuration for this company, or None if not yet configured."""
        stmt = (
            select(SalesConfiguration)
            .where(SalesConfiguration.company_id == company_id)
            .where(SalesConfiguration.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()
