"""InstallmentPlanTemplate ORM model.

Reusable named commercial plan (spec.md §9.2, data-model.md
"InstallmentPlanTemplate"). Referenced (optionally) by
``InstallmentContract.plan_template_id`` for informational lineage only —
never dereferenced for financial truth after contract creation
(BR-INST-009).

Spec ref: specs/010-installments/data-model.md "InstallmentPlanTemplate".
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel

_ACTIVE_NAME_WHERE = text("is_deleted = false")


class InstallmentPlanTemplate(TenantBaseModel):
    """Reusable named Installments commercial plan template."""

    __tablename__ = "installment_plan_templates"
    __table_args__ = (
        Index(
            "uq_installment_plan_templates_company_name",
            "company_id",
            "name",
            unique=True,
            postgresql_where=_ACTIVE_NAME_WHERE,
            sqlite_where=_ACTIVE_NAME_WHERE,
        ),
        CheckConstraint(
            "installment_count > 0",
            name="ck_installment_plan_templates_installment_count",
        ),
        {"comment": "Reusable named Installments commercial plan templates"},
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    frequency: Mapped[str] = mapped_column(String(20), nullable=False)
    installment_count: Mapped[int] = mapped_column(Integer, nullable=False)
    down_payment_rule: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    markup_rule: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    grace_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    late_charge_policy: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    early_settlement_rule: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    applicable_product_ids: Mapped[list[str] | None] = mapped_column(
        JSONB, nullable=True
    )
    requires_approval: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
