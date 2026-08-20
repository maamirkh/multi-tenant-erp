"""Plan ORM model — the SaaS commercial control plane (T103).

Persistence for `plans` (migration 058, data-model.md "Plan"). Plan
names/codes are configuration data, never hardcoded (FR-9A-151) — no
"Basic"/"Pro"/"Enterprise" ever appears in code. `billing_cycle_metadata`/
`pricing_metadata` are inert JSONB — informational only (Assumption A5),
never consulted by any enforcement logic in this Epic.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, CheckConstraint, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.base_model import BaseModel


class Plan(BaseModel):
    """A reusable SaaS offering, Platform-owned (not a tenant record)."""

    __tablename__ = "plans"
    __table_args__ = (
        UniqueConstraint("code", name="uq_plans_code"),
        CheckConstraint(
            "status IN ('draft', 'published', 'retired')", name="ck_plans_status"
        ),
    )

    code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="Configuration-driven identifier — never a hardcoded product "
        "name (FR-9A-151).",
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False, doc="Display name.")

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        doc="draft | published | retired. Matches Company.status's "
        "VARCHAR+CHECK convention, not a PG ENUM.",
    )

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_commercially_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    billing_cycle_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, doc="Informational only (Assumption A5)."
    )

    pricing_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True, doc="Informational only."
    )
