"""Pydantic schemas for Settlement quote/execution request-response
(tasks.md T156).

Spec ref: specs/010-installments/contracts/installments-api.yaml
`/contracts/{contractId}/settlement/quote`,
`/contracts/{contractId}/settlement/execute`.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from modules.installments.schemas.base import InstallmentsBaseSchema


class InstallmentSettlementQuoteRequest(InstallmentsBaseSchema):
    """Request body for ``POST /contracts/{id}/settlement/quote``.

    ``as_of_date`` is echoed back on the quote and must be re-submitted
    unchanged on ``/settlement/execute`` — it plays no role in the
    settlement-amount calculation itself (no accrual/interest formula is
    defined anywhere in the approved data model), it only labels the
    quote for FR-INST-191's reproducibility guarantee and lets execution
    detect a state change since the quote was generated."""

    as_of_date: date | None = None


class InstallmentSettlementQuoteRead(InstallmentsBaseSchema):
    """Response body for a generated settlement quote (FR-INST-190)."""

    contract_id: UUID
    as_of_date: date
    schedule_outstanding: Decimal
    late_charge_outstanding: Decimal
    settlement_amount: Decimal
    currency_code: str
    early_settlement_policy: dict[str, Any] | None = None


class InstallmentSettlementExecuteRequest(InstallmentsBaseSchema):
    """Request body for ``POST /contracts/{id}/settlement/execute`` —
    ``quoted_amount``/``quoted_as_of_date`` must exactly match the most
    recently generated quote or the request is rejected as stale
    (``SETTLEMENT_QUOTE_STALE``, 409)."""

    quoted_amount: Decimal = Field(..., gt=0)
    quoted_as_of_date: date
    payment_method: str = Field(..., min_length=1)
    bank_account_id: UUID | None = None
    cash_account_id: UUID | None = None
