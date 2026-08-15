"""Cost Accounting ORM models — Phase 11.

Phase 11 entities:
  Department  — groups cost centers for higher-level reporting (spec.md §25.2);
                self-referencing hierarchy via parent_dept_id
  CostCenter  — an organizational unit that incurs costs (spec.md §25.1);
                belongs to a Department
  Project     — tracks revenue/costs against a defined initiative (spec.md §25.3)

Both ``CostCenter``/``Department``/``Project`` are referenced (not owned) by
``JournalLine.cost_center_id``/``department_id``/``project_id`` — those
columns already exist as plain UUID (no FK), added in Phase 4 alongside
``Account.requires_cost_center`` and the PostingEngine Step 4 validation
that already enforces "required implies present" (research.md Decision 14).
This phase does not retrofit an FK onto the append-only journal-lines
table — tasks.md T224-T246 does not list that as a task, and the existing
deferred-FK convention (e.g. ``ARPaymentAllocation.payment_id`` before
Phase 10) is precedent for referencing an aggregate that ships later
without an immediate FK.

Spec ref: specs/008-accounting-finance/spec.md §25 Cost Accounting
Tasks ref: specs/008-accounting-finance/tasks.md T228-T230
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Date,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    true,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class Department(TenantBaseModel):
    """Groups cost centers for higher-level reporting. Self-referencing hierarchy."""

    __tablename__ = "accounting_departments"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "dept_code", name="uq_accounting_departments_company_code"
        ),
        {"comment": "Department definitions, scoped per company"},
    )

    dept_code: Mapped[str] = mapped_column(String(20), nullable=False)
    dept_name: Mapped[str] = mapped_column(String(200), nullable=False)
    parent_dept_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_departments.id", ondelete="RESTRICT"),
        nullable=True,
        doc="FK to parent Department — NULL for a top-level department.",
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=true())


class CostCenter(TenantBaseModel):
    """An organizational unit that incurs (and/or generates) costs."""

    __tablename__ = "accounting_cost_centers"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "center_code", name="uq_accounting_cost_centers_company_code"
        ),
        {"comment": "Cost center definitions, scoped per company"},
    )

    center_code: Mapped[str] = mapped_column(String(20), nullable=False)
    center_name: Mapped[str] = mapped_column(String(200), nullable=False)
    department_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_departments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    responsible_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="No FK — cross-module reference to Users & Roles (Epic 4).",
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=true())


class Project(TenantBaseModel):
    """Tracks revenue and costs against a defined initiative."""

    __tablename__ = "accounting_projects"
    __table_args__ = (
        UniqueConstraint(
            "company_id", "project_code", name="uq_accounting_projects_company_code"
        ),
        {"comment": "Project definitions, scoped per company"},
    )

    project_code: Mapped[str] = mapped_column(String(20), nullable=False)
    project_name: Mapped[str] = mapped_column(String(200), nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    budget_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    responsible_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
        doc="No FK — cross-module reference to Users & Roles (Epic 4).",
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=true())
