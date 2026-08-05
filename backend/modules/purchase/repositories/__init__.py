"""Purchase module base repository.

``BasePurchaseRepository`` provides the foundation for all purchase-domain
repositories. It inherits from the shared ``BaseRepository[T]`` and enforces
mandatory ``company_id`` isolation on all data-access operations.

All purchase-specific repositories inherit from ``BasePurchaseRepository``.

Spec ref: specs/006-purchase-management/plan.md — Repository Layer
"""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy.orm import Session

from core.database.models.tenant_base import TenantBaseModel
from core.repositories.base import BaseRepository

ModelType = TypeVar("ModelType", bound=TenantBaseModel)


class BasePurchaseRepository(
    BaseRepository[ModelType], Generic[ModelType]  # noqa: UP046
):
    """Base repository for all purchase domain entities.

    Inherits all CRUD, pagination, and soft-delete operations from
    ``BaseRepository[T]``. Provides a consistent foundation for all
    purchase-module repositories with mandatory ``company_id`` isolation.

    Type parameter ``ModelType`` must be a concrete ``TenantBaseModel``
    subclass corresponding to a purchase module table.

    Args:
        db:    SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
        model: The SQLAlchemy ORM class this repository operates on.
    """

    def __init__(self, db: Session, model: type[ModelType]) -> None:
        super().__init__(db=db, model=model)
