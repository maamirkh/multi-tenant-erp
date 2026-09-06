"""AccountingConfigurationService — company-level accounting settings.

One configuration record per company, created lazily with defaults on
first access — mirrors ``SalesConfigurationService`` (Epic 7).

Spec ref: specs/008-accounting-finance/tasks.md T027, T035
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.foundation import (
    AccountingConfigurationRepository,
)


class AccountingConfigurationService:
    """Application service for company-level accounting configuration."""

    def __init__(
        self, db: Session, config_repo: AccountingConfigurationRepository
    ) -> None:
        self.db = db
        self._repo = config_repo

    def get_or_create(self, company_id: UUID) -> AccountingConfiguration:
        """Return the accounting configuration for this company, creating defaults if needed."""
        config = self._repo.get_for_company(company_id=company_id)
        if config is None:
            config = AccountingConfiguration(company_id=company_id)
            config = self._repo.create(config)
        return config

    def update(self, company_id: UUID, **kwargs: object) -> AccountingConfiguration:
        """Update fields on the company's accounting configuration."""
        config = self.get_or_create(company_id=company_id)
        for key, value in kwargs.items():
            if value is not None and hasattr(config, key):
                setattr(config, key, value)
        return self._repo.update(config)
