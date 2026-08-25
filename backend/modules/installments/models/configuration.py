"""InstallmentConfiguration ORM model.

Tenant/branch-level installment policy (spec.md §9.1, data-model.md
"InstallmentConfiguration"). ``branch_id IS NULL`` marks the company-level
default row; a non-NULL ``branch_id`` marks a branch-specific override.

**[CORRECTED — T001/T021]** ``__table_args__`` declares the two partial
unique indexes created by migration 062 verbatim — a plain
``UniqueConstraint(company_id, branch_id)`` would be insufficient because
PostgreSQL treats multiple NULLs in ``branch_id`` as distinct, so it would
never actually block a second company-level (default) row.

Spec ref: specs/010-installments/data-model.md "InstallmentConfiguration";
specs/010-installments/plan.md §7.1/§7.2.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

_BRANCH_OVERRIDE_WHERE = text("branch_id IS NOT NULL")
_COMPANY_DEFAULT_WHERE = text("branch_id IS NULL")


class InstallmentConfiguration(TenantBaseModel):
    """Tenant/branch-level Installments policy configuration."""

    __tablename__ = "installment_configurations"
    __table_args__ = (
        Index(
            "uq_installment_configurations_branch",
            "company_id",
            "branch_id",
            unique=True,
            postgresql_where=_BRANCH_OVERRIDE_WHERE,
            sqlite_where=_BRANCH_OVERRIDE_WHERE,
        ),
        Index(
            "uq_installment_configurations_company_default",
            "company_id",
            unique=True,
            postgresql_where=_COMPANY_DEFAULT_WHERE,
            sqlite_where=_COMPANY_DEFAULT_WHERE,
        ),
        {"comment": "Tenant/branch-level Installments policy configuration"},
    )

    branch_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        doc="NULL = company-level default row; non-NULL = branch override",
    )
    allowed_frequencies: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    min_term: Mapped[int] = mapped_column(Integer, nullable=False)
    max_term: Mapped[int] = mapped_column(Integer, nullable=False)
    min_down_payment_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True
    )
    min_down_payment_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 6), nullable=True
    )
    max_financed_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 6), nullable=True
    )
    rounding_policy: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="ROUND_HALF_UP"
    )
    grace_period_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    late_charge_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    early_settlement_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approval_threshold_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 6), nullable=True
    )
    backdating_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    backdating_max_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cancellation_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    default_policy: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    writeoff_requires_permission: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    cure_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    eligibility_rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
