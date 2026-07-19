"""Abstract multi-tenant base model with soft-delete support.

All business entity tables in the DevSphere ERP platform inherit from
``TenantBaseModel``.  This class enforces two foundational platform contracts:

1. **Multi-tenant isolation** — every business record is scoped to a
   ``company_id``.  The ``BaseRepository`` makes ``company_id`` a mandatory
   parameter on every data-access method, ensuring cross-tenant data leakage
   is structurally impossible at the persistence layer.

2. **Soft delete** — records are never hard-deleted in normal operation.
   ``is_deleted=True`` + ``deleted_at=<timestamp>`` marks a record as deleted
   while retaining it for audit, compliance, and potential restore operations.

FK constraint deferred:
  - ``company_id`` will gain a FK constraint to ``companies.id`` in the
    Company Management Epic via an Alembic migration.
  - ``created_by`` will gain a FK constraint to ``users.id`` in the User
    Management Epic via an Alembic migration.
  Both constraints are intentionally absent in Epic 1 because the referenced
  tables do not yet exist.

Soft-delete lifecycle::

    Active   (is_deleted=False, deleted_at=NULL)
        │  soft_delete()
        ▼
    Deleted  (is_deleted=True, deleted_at=<utcnow>)
        │  restore()  [future, requires authorization]
        ▼
    Active   (is_deleted=False, deleted_at=NULL)
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Uuid, false
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.base_model import BaseModel


class TenantBaseModel(BaseModel):
    """Abstract business-entity model with multi-tenant isolation and soft delete.

    Inherits ``id``, ``created_at``, ``updated_at`` from ``BaseModel``.

    Additional columns:
      - ``company_id``  — required; identifies the owning tenant.
      - ``created_by``  — optional until User Management Epic adds FK.
      - ``is_deleted``  — soft-delete flag (default False).
      - ``deleted_at``  — soft-delete timestamp (NULL when active).
    """

    __abstract__ = True

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        index=True,
        doc=(
            "Tenant identifier. All queries MUST filter by this field. "
            "FK to companies.id is added in the Company Management Epic."
        ),
    )

    created_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc=(
            "UUID of the user who created this record. Nullable until the "
            "User Management Epic adds the FK to users.id."
        ),
    )

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=false(),
        doc="Soft-delete flag. False = active record; True = logically deleted.",
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc=(
            "UTC timestamp when the record was soft-deleted. "
            "Must be NULL when is_deleted=False and non-NULL when is_deleted=True."
        ),
    )
