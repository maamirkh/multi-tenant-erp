"""InstallmentScheduleVersion / InstallmentScheduleLine ORM models.

Both are immutable/append-only by omission — no update method exists
anywhere in ``InstallmentScheduleRepository`` (T068). Field shapes mirror
migration 065 exactly.

Spec ref: specs/010-installments/data-model.md "InstallmentScheduleVersion"
/ "InstallmentScheduleLine"; specs/010-installments/plan.md §6, §10.4.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base
from core.database.models.tenant_base import TenantBaseModel


class InstallmentScheduleVersion(TenantBaseModel):
    """One version of a contract's payment schedule — immutable once
    created; no update method exists on its repository."""

    __tablename__ = "installment_schedule_versions"
    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "version_number",
            name="uq_installment_schedule_versions_contract_number",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'SUPERSEDED')",
            name="ck_installment_schedule_versions_status",
        ),
        {
            "comment": (
                "One version of a contract's payment schedule — immutable "
                "once created, no update method exists on its repository"
            )
        },
    )

    contract_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "installment_contracts.id",
            name="fk_installment_schedule_versions_contract_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="DRAFT"
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    generated_by: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class InstallmentScheduleLine(Base):
    """One contractual due obligation — append-only. Does not inherit
    ``TenantBaseModel``: no ``is_deleted``, ``deleted_at``, ``created_by``,
    or ``updated_at`` column exists at all (mirrors accounting's
    ``JournalLine``). ``waived_*``/``voided_*`` are the only mutable
    exceptions, set once via a controlled workflow in later phases."""

    __tablename__ = "installment_schedule_lines"
    __table_args__ = (
        UniqueConstraint(
            "schedule_version_id",
            "sequence",
            name="uq_installment_schedule_lines_version_sequence",
        ),
        CheckConstraint(
            "scheduled_amount > 0",
            name="ck_installment_schedule_lines_positive_amount",
        ),
        {
            "comment": (
                "Append-only contractual due obligations — no UPDATE path "
                "exists for scheduled_amount/due_date, ever"
            )
        },
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    schedule_version_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "installment_schedule_versions.id",
            name="fk_installment_schedule_lines_schedule_version_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    waived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    waived_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    waived_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    voided_by: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    voided_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
