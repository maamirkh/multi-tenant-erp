"""Sales master data services.

Application-layer services for master data CRUD operations:
  - CustomerCategoryService
  - CustomerGroupService
  - SalesPaymentTermService
  - SalesReasonCodeService
  - SalesConfigurationService

All services enforce business invariants (code uniqueness per company)
and delegate persistence to the corresponding repository.

Spec ref: specs/007-sales-management/plan.md — Application Layer
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
from modules.sales.models.master import (
    CustomerCategory,
    CustomerGroup,
    SalesConfiguration,
    SalesPaymentTerm,
    SalesReasonCode,
)
from modules.sales.repositories.master import (
    CustomerCategoryRepository,
    CustomerGroupRepository,
    SalesConfigurationRepository,
    SalesPaymentTermRepository,
    SalesReasonCodeRepository,
)

logger = logging.getLogger(__name__)


class CustomerCategoryService:
    """Application service for customer category management."""

    def __init__(self, db: Session, category_repo: CustomerCategoryRepository) -> None:
        self.db = db
        self._repo = category_repo

    def create(
        self,
        company_id: UUID,
        code: str,
        name: str,
        description: str | None = None,
        default_payment_term_id: UUID | None = None,
        default_credit_limit: float = 0,
        created_by: UUID | None = None,
    ) -> CustomerCategory:
        existing = self._repo.get_by_code(company_id=company_id, code=code)
        if existing is not None:
            raise ConflictException(
                f"Customer category with code '{code}' already exists for this company"
            )
        category = CustomerCategory(
            company_id=company_id,
            code=code,
            name=name,
            description=description,
            default_payment_term_id=(
                str(default_payment_term_id) if default_payment_term_id else None
            ),
            default_credit_limit=default_credit_limit,
            created_by=created_by,
        )
        return self._repo.create(category)

    def update(
        self, company_id: UUID, category_id: UUID, **kwargs: object
    ) -> CustomerCategory:
        category = self._repo.get_by_id_or_none(id=category_id, company_id=company_id)
        if category is None:
            raise NotFoundException("Customer category not found")
        for key, value in kwargs.items():
            if value is not None and hasattr(category, key):
                setattr(category, key, value)
        return self._repo.update(category)

    def get_all(self, company_id: UUID) -> list[CustomerCategory]:
        return self._repo.get_active(company_id=company_id)

    def list_all(
        self, company_id: UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[CustomerCategory], int]:
        return self._repo.list(company_id=company_id, skip=skip, limit=limit)


class CustomerGroupService:
    """Application service for customer group management."""

    def __init__(self, db: Session, group_repo: CustomerGroupRepository) -> None:
        self.db = db
        self._repo = group_repo

    def create(
        self,
        company_id: UUID,
        code: str,
        name: str,
        description: str | None = None,
        created_by: UUID | None = None,
    ) -> CustomerGroup:
        existing = self._repo.get_by_code(company_id=company_id, code=code)
        if existing is not None:
            raise ConflictException(
                f"Customer group with code '{code}' already exists for this company"
            )
        group = CustomerGroup(
            company_id=company_id,
            code=code,
            name=name,
            description=description,
            created_by=created_by,
        )
        return self._repo.create(group)

    def update(
        self, company_id: UUID, group_id: UUID, **kwargs: object
    ) -> CustomerGroup:
        group = self._repo.get_by_id_or_none(id=group_id, company_id=company_id)
        if group is None:
            raise NotFoundException("Customer group not found")
        for key, value in kwargs.items():
            if value is not None and hasattr(group, key):
                setattr(group, key, value)
        return self._repo.update(group)

    def get_all(self, company_id: UUID) -> list[CustomerGroup]:
        return self._repo.get_active(company_id=company_id)

    def list_all(
        self, company_id: UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[CustomerGroup], int]:
        return self._repo.list(company_id=company_id, skip=skip, limit=limit)


class SalesPaymentTermService:
    """Application service for sales payment term management."""

    def __init__(self, db: Session, terms_repo: SalesPaymentTermRepository) -> None:
        self.db = db
        self._repo = terms_repo

    def create(
        self,
        company_id: UUID,
        code: str,
        name: str,
        due_days: int,
        discount_days: int | None = None,
        discount_percent: float | None = None,
        description: str | None = None,
        created_by: UUID | None = None,
    ) -> SalesPaymentTerm:
        existing = self._repo.get_by_code(company_id=company_id, code=code)
        if existing is not None:
            raise ConflictException(
                f"Payment term with code '{code}' already exists for this company"
            )
        term = SalesPaymentTerm(
            company_id=company_id,
            code=code,
            name=name,
            due_days=due_days,
            discount_days=discount_days,
            discount_percent=discount_percent,
            description=description,
            created_by=created_by,
        )
        return self._repo.create(term)

    def update(
        self, company_id: UUID, term_id: UUID, **kwargs: object
    ) -> SalesPaymentTerm:
        term = self._repo.get_by_id_or_none(id=term_id, company_id=company_id)
        if term is None:
            raise NotFoundException("Payment term not found")
        for key, value in kwargs.items():
            if value is not None and hasattr(term, key):
                setattr(term, key, value)
        return self._repo.update(term)

    def get_all(self, company_id: UUID) -> list[SalesPaymentTerm]:
        return self._repo.get_active(company_id=company_id)

    def list_all(
        self, company_id: UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[SalesPaymentTerm], int]:
        return self._repo.list(company_id=company_id, skip=skip, limit=limit)


class SalesReasonCodeService:
    """Application service for sales reason code management."""

    def __init__(self, db: Session, reason_repo: SalesReasonCodeRepository) -> None:
        self.db = db
        self._repo = reason_repo

    def create(
        self,
        company_id: UUID,
        code: str,
        name: str,
        reason_type: str,
        created_by: UUID | None = None,
    ) -> SalesReasonCode:
        existing = self._repo.get_by_code(
            company_id=company_id, code=code, reason_type=reason_type
        )
        if existing is not None:
            raise ConflictException(
                f"Reason code '{code}' of type '{reason_type}' already exists"
            )
        reason = SalesReasonCode(
            company_id=company_id,
            code=code,
            name=name,
            reason_type=reason_type,
            created_by=created_by,
        )
        return self._repo.create(reason)

    def update(
        self, company_id: UUID, reason_id: UUID, **kwargs: object
    ) -> SalesReasonCode:
        reason = self._repo.get_by_id_or_none(id=reason_id, company_id=company_id)
        if reason is None:
            raise NotFoundException("Reason code not found")
        for key, value in kwargs.items():
            if value is not None and hasattr(reason, key):
                setattr(reason, key, value)
        return self._repo.update(reason)

    def get_by_type(self, company_id: UUID, reason_type: str) -> list[SalesReasonCode]:
        return self._repo.get_by_type(company_id=company_id, reason_type=reason_type)

    def list_all(
        self, company_id: UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[SalesReasonCode], int]:
        return self._repo.list(company_id=company_id, skip=skip, limit=limit)


class SalesConfigurationService:
    """Application service for company-level sales configuration."""

    def __init__(self, db: Session, config_repo: SalesConfigurationRepository) -> None:
        self.db = db
        self._repo = config_repo

    def get_or_create(self, company_id: UUID) -> SalesConfiguration:
        """Return the sales configuration for this company, creating defaults if needed."""
        config = self._repo.get_for_company(company_id=company_id)
        if config is None:
            config = SalesConfiguration(company_id=company_id)
            config = self._repo.create(config)
        return config

    def update(self, company_id: UUID, **kwargs: object) -> SalesConfiguration:
        config = self.get_or_create(company_id=company_id)
        for key, value in kwargs.items():
            if value is not None and hasattr(config, key):
                setattr(config, key, value)
        return self._repo.update(config)
