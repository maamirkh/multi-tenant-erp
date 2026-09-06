"""Capability ORM model — the generic module/feature entitlement registry
(T104, ADR-3).

Persistence for `capabilities` (migration 058, data-model.md
"Capability"). `key` is the primary key (mirrors `PlatformPermission`'s
code-as-PK convention) — adding a future module needs one row here, no
schema change and no per-module boolean column on `Company` (Assumption
A7).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class Capability(Base):
    """Entitlement capability catalogue entry — e.g. `"inventory"`,
    `"sales"`, `"purchase"`, `"accounting"`, `"crm"`.
    """

    __tablename__ = "capabilities"
    __table_args__ = (
        CheckConstraint("grain IN ('module', 'feature')", name="ck_capabilities_grain"),
    )

    key: Mapped[str] = mapped_column(
        String(50), primary_key=True, doc="e.g. 'inventory'. Also the primary key."
    )

    module: Mapped[str] = mapped_column(String(50), nullable=False)

    grain: Mapped[str] = mapped_column(
        String(20), nullable=False, doc="module | feature (Assumption A7)."
    )

    display_name: Mapped[str] = mapped_column(String(150), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
