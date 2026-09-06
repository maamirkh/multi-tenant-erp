"""Accounting module base repository.

``BaseAccountingRepository`` provides the foundation for all accounting-domain
repositories. It inherits from the shared ``BaseRepository[T]`` and enforces
mandatory ``company_id`` isolation on all data-access operations, matching
the pattern established in Epics 5-7 (see ``BaseSalesRepository``,
``BasePurchaseRepository``).

All accounting-specific repositories inherit from
``BaseAccountingRepository``.

Note: append-only financial tables (``accounting_journal_lines``,
``accounting_audit_log``) do NOT use this base class — they have no
soft-delete or update path by design (data-model.md §1). Their repositories
implement only ``create`` and read operations directly.

Spec ref: specs/008-accounting-finance/plan.md — Repository Layer
"""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from core.database.models.tenant_base import TenantBaseModel
from core.repositories.base import BaseRepository

ModelType = TypeVar("ModelType", bound=TenantBaseModel)


class BaseAccountingRepository(
    BaseRepository[ModelType],
    Generic[ModelType],  # noqa: UP046
):
    """Base repository for all accounting domain entities.

    Inherits all CRUD, pagination, and soft-delete operations from
    ``BaseRepository[T]``. Provides a consistent foundation for all
    accounting-module repositories with mandatory ``company_id`` isolation.

    Type parameter ``ModelType`` must be a concrete ``TenantBaseModel``
    subclass corresponding to an accounting module table.

    Args:
        db:    SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
        model: The SQLAlchemy ORM class this repository operates on.
    """

    def __init__(self, db: Session, model: type[ModelType]) -> None:
        super().__init__(db=db, model=model)
