"""Generic base repository for all DevSphere ERP modules.

**Tenant isolation contract**

Every data-access method in this class requires ``company_id`` as a mandatory
parameter.  Queries ALWAYS include ``WHERE company_id = <value>`` — this is
the structural guarantee that prevents cross-tenant data leakage.

``company_id`` is NEVER derived from client-supplied data.  It is always read
from the authenticated session context (populated by Better Auth in the
Authentication Epic).  In Phase 1 the session context is a stub; when the
Authentication Epic ships, the stub is replaced with a real value.

**Soft-delete contract**

By default all read and list operations exclude records where
``is_deleted = True``.  Pass ``include_deleted=True`` only for administrative
operations that explicitly require access to deleted records.

**Usage**::

    class ProductRepository(BaseRepository[Product]):
        pass  # inherits all CRUD methods

    # In a service:
    repo = ProductRepository(db=db, model=Product)
    product = repo.get_by_id(product_id, company_id=session.company_id)
"""

from __future__ import annotations

import logging
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database.models.tenant_base import TenantBaseModel
from core.exceptions.base import NotFoundException
from core.utils.datetime import utcnow

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType", bound=TenantBaseModel)


class BaseRepository(Generic[ModelType]):
    """Generic CRUD repository with tenant isolation and soft-delete support.

    Type parameter ``ModelType`` must be a concrete ``TenantBaseModel``
    subclass (i.e. a real database table, not an abstract model).

    Args:
        db:    SQLAlchemy ``Session`` injected by the FastAPI ``get_db``
               dependency.  The session lifetime is managed by the caller.
        model: The SQLAlchemy ORM class (not an instance) this repository
               operates on.
    """

    def __init__(self, db: Session, model: type[ModelType]) -> None:
        self.db = db
        self.model = model

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def create(self, entity: ModelType) -> ModelType:
        """Persist a new entity and return it with server-generated fields.

        The caller is responsible for populating ``company_id`` from the
        authenticated session context before calling this method.

        Args:
            entity: An unpersisted ORM instance.  ``id``, ``created_at``,
                    and ``updated_at`` are set by server defaults on INSERT.

        Returns:
            The same instance after ``db.refresh()`` — all server-generated
            fields (``id``, ``created_at``, ``updated_at``) are populated.
        """
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        logger.debug(
            "Entity created",
            extra={"model": self.model.__name__, "id": str(entity.id)},
        )
        return entity

    def update(self, entity: ModelType) -> ModelType:
        """Commit pending changes to an existing entity and refresh it.

        The caller must load the entity first (via ``get_by_id``), mutate
        its fields, then pass it to this method.  No additional tenant check
        is performed here — isolation is enforced at load time.

        Args:
            entity: An ORM instance with modified fields.

        Returns:
            The same instance after ``db.refresh()`` — ``updated_at`` is
            refreshed from the server.
        """
        self.db.commit()
        self.db.refresh(entity)
        logger.debug(
            "Entity updated",
            extra={"model": self.model.__name__, "id": str(entity.id)},
        )
        return entity

    def soft_delete(self, id: UUID, company_id: UUID) -> None:
        """Mark an entity as deleted without removing it from the database.

        Sets ``is_deleted = True`` and ``deleted_at = utcnow()``.  The
        record remains in the database for audit, compliance, and potential
        restore operations.

        Args:
            id:         Primary key of the record to delete.
            company_id: Tenant identifier — used to verify ownership before
                        deleting (raises ``NotFoundException`` on mismatch).

        Raises:
            NotFoundException: If the record does not exist, is already
                               deleted, or belongs to a different tenant.
        """
        entity = self.get_by_id(id=id, company_id=company_id)
        entity.is_deleted = True
        entity.deleted_at = utcnow()
        self.db.commit()
        logger.debug(
            "Entity soft-deleted",
            extra={"model": self.model.__name__, "id": str(id)},
        )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def get_by_id(self, id: UUID, company_id: UUID) -> ModelType:
        """Return the entity with the given ``id`` scoped to ``company_id``.

        Both conditions must be satisfied.  If the record exists but belongs
        to a different tenant, ``NotFoundException`` is raised — this
        provides the same response as "not found" to avoid information
        disclosure about records in other tenants.

        Args:
            id:         Primary key.
            company_id: Tenant identifier from the authenticated session.

        Returns:
            The matching ORM instance.

        Raises:
            NotFoundException: If no active record matches both ``id`` and
                               ``company_id``.
        """
        entity = self.get_by_id_or_none(id=id, company_id=company_id)
        if entity is None:
            raise NotFoundException(
                message=f"{self.model.__name__} with id '{id}' not found.",
                details={"id": str(id)},
            )
        return entity

    def get_by_id_or_none(self, id: UUID, company_id: UUID) -> ModelType | None:
        """Return the entity or ``None`` — never raises ``NotFoundException``.

        Useful when the absence of a record is not an error condition (e.g.
        checking for duplicates before creating).

        Args:
            id:         Primary key.
            company_id: Tenant identifier.

        Returns:
            The matching ORM instance, or ``None`` if not found or deleted.
        """
        stmt = (
            select(self.model)
            .where(self.model.id == id)
            .where(self.model.company_id == company_id)
            .where(self.model.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def list(
        self,
        company_id: UUID,
        skip: int = 0,
        limit: int = 20,
        include_deleted: bool = False,
    ) -> tuple[list[ModelType], int]:
        """Return a page of entities and the total count for pagination.

        Always filters by ``company_id``.  Soft-deleted records are excluded
        unless ``include_deleted=True`` is explicitly passed.

        Args:
            company_id:      Tenant identifier — all results are scoped to
                             this value.
            skip:            Number of records to skip (SQL OFFSET).
            limit:           Maximum records to return (SQL LIMIT).
            include_deleted: When ``True``, soft-deleted records are included.
                             Default is ``False`` (active records only).

        Returns:
            A tuple ``(items, total)`` where ``total`` is the full count
            across all pages (not just the current page).
        """
        base_stmt = select(self.model).where(self.model.company_id == company_id)
        if not include_deleted:
            base_stmt = base_stmt.where(self.model.is_deleted == False)  # noqa: E712

        # Total count (no pagination applied).
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total: int = self.db.execute(count_stmt).scalar_one()

        # Paginated results.
        rows_stmt = base_stmt.offset(skip).limit(limit)
        items: list[ModelType] = list(self.db.execute(rows_stmt).scalars().all())

        return items, total
