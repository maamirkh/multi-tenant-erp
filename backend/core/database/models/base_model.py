"""Abstract base ORM model providing identity and audit timestamps.

Every concrete database table model in the DevSphere ERP platform inherits
from ``BaseModel`` (directly) or ``TenantBaseModel`` (which extends
``BaseModel``).  No additional columns are inherited here beyond identity
and timestamps — business fields are added in concrete models.

Column design:
  - ``id``: UUID primary key generated server-side via ``gen_random_uuid()``.
    Client code never supplies an ``id`` value; it is always assigned by
    PostgreSQL on INSERT.
  - ``created_at``: immutable insert timestamp; the ORM never writes to this
    column after the initial INSERT.
  - ``updated_at``: auto-updated by the ORM on every UPDATE via ``onupdate``.
    The application must NOT set this field manually.

All datetime columns are timezone-aware (``TIMESTAMPTZ`` in PostgreSQL) so
that data stored from multiple time zones sorts and compares correctly.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class BaseModel(Base):
    """Abstract root model — provides ``id``, ``created_at``, ``updated_at``.

    Set ``__abstract__ = True`` so SQLAlchemy never creates a ``base_model``
    table.  Subclasses define ``__tablename__`` and become concrete tables.
    """

    __abstract__ = True

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
        doc="Primary key; UUID generated server-side on INSERT.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="UTC timestamp of record creation; immutable after INSERT.",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="UTC timestamp of last modification; auto-updated by the ORM.",
    )
