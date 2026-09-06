"""PlanCapability ORM model — the Plan Entitlement ceiling (T105).

Persistence for `plan_capabilities` (migration 058, data-model.md
"PlanCapability"). plan.md §17.2's resolution table starts here: a
capability not allowed by the tenant's plan is denied regardless of any
tenant-side toggle.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.base_model import BaseModel


class PlanCapability(BaseModel):
    """Whether a given `Plan` grants a given `Capability` — the Plan
    Entitlement ceiling."""

    __tablename__ = "plan_capabilities"
    __table_args__ = (
        UniqueConstraint(
            "plan_id", "capability_key", name="uq_plan_capabilities_plan_capability"
        ),
    )

    plan_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("plans.id", ondelete="CASCADE"),
        nullable=False,
    )

    capability_key: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("capabilities.key", ondelete="RESTRICT"),
        nullable=False,
    )

    allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
