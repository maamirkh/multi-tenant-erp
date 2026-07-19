"""CompanyAddressRepository — data access layer for the CompanyAddress model.

Every read query includes ``WHERE company_id = :company_id`` to enforce
tenant-scoped isolation.  No address is ever accessible without a valid
``company_id``, preventing cross-tenant data leakage.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.companies.models.company_address import CompanyAddress
from modules.companies.models.enums import AddressType

logger = logging.getLogger(__name__)


class CompanyAddressRepository:
    """Data access for the ``company_addresses`` table.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Write operations ──────────────────────────────────────────────────────

    def create(self, company_id: UUID, data: dict[str, Any]) -> CompanyAddress:
        """Persist a new CompanyAddress under the given company and return it."""
        address = CompanyAddress(company_id=company_id, **data)
        self.db.add(address)
        self.db.commit()
        self.db.refresh(address)
        logger.debug(
            "CompanyAddress created",
            extra={"company_id": str(company_id), "address_id": str(address.id)},
        )
        return address

    def update(self, address: CompanyAddress, data: dict[str, Any]) -> CompanyAddress:
        """Apply ``data`` fields to ``address``, commit, and refresh."""
        for field, value in data.items():
            setattr(address, field, value)
        self.db.commit()
        self.db.refresh(address)
        logger.debug(
            "CompanyAddress updated",
            extra={
                "company_id": str(address.company_id),
                "address_id": str(address.id),
            },
        )
        return address

    def delete(self, address: CompanyAddress) -> None:
        """Permanently delete the given address record."""
        self.db.delete(address)
        self.db.commit()
        logger.debug(
            "CompanyAddress deleted",
            extra={
                "company_id": str(address.company_id),
                "address_id": str(address.id),
            },
        )

    # ── Read operations ───────────────────────────────────────────────────────

    def get_by_id(self, id: UUID, company_id: UUID) -> CompanyAddress | None:
        """Return the address if it belongs to ``company_id``, or ``None``."""
        stmt = (
            select(CompanyAddress)
            .where(CompanyAddress.id == id)
            .where(CompanyAddress.company_id == company_id)
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list_by_company(self, company_id: UUID) -> list[CompanyAddress]:
        """Return all addresses for the given company ordered by type then creation date."""
        stmt = (
            select(CompanyAddress)
            .where(CompanyAddress.company_id == company_id)
            .order_by(CompanyAddress.address_type, CompanyAddress.created_at.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_primary_by_type(
        self, company_id: UUID, address_type: AddressType
    ) -> CompanyAddress | None:
        """Return the primary address of a given type for the company, or ``None``."""
        stmt = (
            select(CompanyAddress)
            .where(CompanyAddress.company_id == company_id)
            .where(CompanyAddress.address_type == address_type)
            .where(CompanyAddress.is_primary.is_(True))
        )
        return self.db.execute(stmt).scalars().one_or_none()
