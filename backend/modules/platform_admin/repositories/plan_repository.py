"""PlanRepository — data access for `Plan` and its `PlanCapability`
entitlement ceiling (T110).

Deliberately does **not** inherit `BaseRepository` (mandates `company_id`
filtering — wrong for `Plan`, a platform-scoped table). Write paths
`flush()` only, never `commit()` (ADR-5) — the calling service
(`PlanService`, T111) owns the transaction boundary alongside its audit
row.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modules.platform_admin.models.plan import Plan
from modules.platform_admin.models.plan_capability import PlanCapability


class PlanRepository:
    """Data access for the `plans` and `plan_capabilities` tables."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Plan
    # ------------------------------------------------------------------

    def get_by_id(self, plan_id: UUID) -> Plan | None:
        return self.db.get(Plan, plan_id)

    def get_by_code(self, code: str) -> Plan | None:
        stmt = select(Plan).where(Plan.code == code)
        return self.db.execute(stmt).scalars().one_or_none()

    def list_paginated(
        self, *, status: str | None = None, offset: int = 0, limit: int = 50
    ) -> tuple[list[Plan], int]:
        stmt = select(Plan)
        if status is not None:
            stmt = stmt.where(Plan.status == status)

        total = self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()

        rows_stmt = stmt.order_by(Plan.created_at).offset(offset).limit(limit)
        items = list(self.db.execute(rows_stmt).scalars().all())
        return items, total

    def create(self, *, code: str, name: str, status: str, **extra: Any) -> Plan:
        """Stage a new Plan. Caller commits."""
        plan = Plan(code=code, name=name, status=status, **extra)
        self.db.add(plan)
        self.db.flush()
        return plan

    def update_fields(self, plan: Plan, **fields: Any) -> Plan:
        """Stage field updates on an existing Plan. Caller commits."""
        for field, value in fields.items():
            setattr(plan, field, value)
        self.db.flush()
        return plan

    # ------------------------------------------------------------------
    # PlanCapability — the Plan Entitlement ceiling
    # ------------------------------------------------------------------

    def get_capability_map(self, plan_id: UUID) -> dict[str, bool]:
        stmt = select(PlanCapability.capability_key, PlanCapability.allowed).where(
            PlanCapability.plan_id == plan_id
        )
        return dict(self.db.execute(stmt).all())

    def set_capabilities(self, plan_id: UUID, capability_map: dict[str, bool]) -> None:
        """Replace a Plan's capability ceiling wholesale. Caller commits."""
        self.db.query(PlanCapability).filter(PlanCapability.plan_id == plan_id).delete(
            synchronize_session=False
        )
        for capability_key, allowed in capability_map.items():
            self.db.add(
                PlanCapability(
                    plan_id=plan_id, capability_key=capability_key, allowed=allowed
                )
            )
        self.db.flush()
