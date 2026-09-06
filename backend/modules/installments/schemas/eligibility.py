"""Pydantic schema for the Installments eligibility check response.

Spec ref: specs/010-installments/contracts/installments-api.yaml
`/eligibility`.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from modules.installments.schemas.base import InstallmentsBaseSchema


class EligibilityResultRead(InstallmentsBaseSchema):
    """Response body for ``GET /eligibility`` — returned only on a
    passed eligibility check (ineligibility is a 422 with a documented
    reason code, never a 200 with ``eligible=false``)."""

    sales_invoice_id: UUID
    customer_id: UUID
    currency_code: str
    outstanding_amount: Decimal
