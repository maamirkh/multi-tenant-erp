"""Currency Revaluation ORM model — Phase 12.

Phase 12 entities:
  CurrencyRevaluationRun — one row per executed period-end revaluation run,
                            persisting the full report (per-transaction lines
                            as JSONB) so ``GET .../history`` and
                            ``GET .../{id}/report`` can be served without
                            recomputing unrealized gain/loss after the fact.

No dedicated table for this exists in data-model.md (§4.5 describes
``CurrencyRevaluationService`` as a domain service returning "revaluation
report data", not a persisted aggregate) — this table is the minimal
persistence needed to satisfy tasks.md T251's two read endpoints, following
the same "session row + JSONB detail" shape already used by
``SupplierStatementReconciliation``/``AccountingAuditLog`` elsewhere in this
module.

Spec ref: specs/008-accounting-finance/spec.md §24 Multi-Currency
Tasks ref: specs/008-accounting-finance/tasks.md T247, T251
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from core.database.models.tenant_base import TenantBaseModel


class CurrencyRevaluationRun(TenantBaseModel):
    """One executed period-end currency revaluation run.

    ``lines`` is a JSONB array of per-transaction revaluation detail
    (``RevaluationLine`` shape — see schemas/currency.py), captured at run
    time. ``journal_entry_id`` is NULL when the run found no open foreign
    currency exposure (nothing to post).
    """

    __tablename__ = "accounting_currency_revaluations"
    __table_args__ = (
        {"comment": "Period-end currency revaluation runs, scoped per company"},
    )

    fiscal_period_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_fiscal_periods.id", ondelete="RESTRICT"),
        nullable=False,
    )
    revaluation_date: Mapped[date] = mapped_column(Date, nullable=False)
    currencies_revalued: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    total_unrealized_gain_base: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    total_unrealized_loss_base: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    net_gain_loss_base: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), server_default="0", nullable=False
    )
    journal_entry_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("accounting_journal_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    lines: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
