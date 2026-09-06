"""InstallmentIdempotencyKey ORM model.

The new, module-local, race-safe idempotency mechanism required before
any high-risk financial command (activation, collection, settlement,
reversal, rescheduling, cancellation, default, write-off) can be
implemented safely (plan.md §20, tasks.md Phase 5.5). No reusable
idempotency-key infrastructure exists anywhere else in the repository.

Plain ``Base`` (not ``TenantBaseModel``) with an explicit ``company_id``
column, matching migration 067's exact field list — no soft-delete/
``created_by``/``updated_at`` columns.

**No ``FAILED`` status.** A failed business operation rolls back its
whole transaction, including this row — ``FAILED`` could never actually
be durably committed, so it is not part of the CHECK constraint
(plan.md §20.1's explicit correction).

Spec ref: specs/010-installments/plan.md §20.1.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


class InstallmentIdempotencyKey(Base):
    """Race-safe idempotency reservation for a high-risk Installments
    command."""

    __tablename__ = "installment_idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "operation",
            "idempotency_key",
            name="uq_installment_idempotency_company_op_key",
        ),
        CheckConstraint(
            "status IN ('IN_PROGRESS', 'COMPLETED')",
            name="ck_installment_idempotency_status",
        ),
        {
            "comment": (
                "Race-safe idempotency reservations for high-risk "
                "Installments commands — INSERT...ON CONFLICT DO NOTHING "
                "targets the unique constraint above, never a bare INSERT "
                "+ caught IntegrityError"
            )
        },
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    company_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(100), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(15), nullable=False)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    contract_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
