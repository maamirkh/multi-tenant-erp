"""Pydantic schemas for Reports/Dashboard/Documents (tasks.md T208).

Spec ref: specs/010-installments/contracts/installments-api.yaml
`/reports/{reportType}`, `/dashboard`, `/contracts/{id}/documents/*`,
`/customers/{id}/statement`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import RootModel

from modules.installments.schemas.base import InstallmentsBaseSchema


class InstallmentReportRow(RootModel[dict[str, Any]]):
    """A single report row — deliberately generic (the 8 report types
    named by the OpenAPI contract's `reportType` enum have genuinely
    heterogeneous columns; every concrete row is one of
    ``InstallmentReportingService``'s own ``dict`` outputs, always
    including its own ``report_type`` key)."""


class InstallmentDashboard(InstallmentsBaseSchema):
    """Response body for ``GET /dashboard`` (FR-INST-080/081)."""

    active_contract_count: int
    outstanding_amount: Decimal
    due_today_amount: Decimal
    due_this_month_amount: Decimal
    collected_today_amount: Decimal
    collected_this_month_amount: Decimal
    overdue_amount: Decimal
    overdue_count: int
    collection_rate: Decimal
    aging_distribution: dict[str, Decimal]
    defaulted_balance: Decimal
    written_off_balance: Decimal
    upcoming_receivables_amount: Decimal


class InstallmentAgreementView(InstallmentsBaseSchema):
    """Response body for ``GET /contracts/{id}/documents/agreement``."""

    document_type: str
    contract_id: UUID
    contract_number: str
    customer_id: UUID
    status: str
    contract_date: str
    contractual_total: Decimal
    principal_amount: Decimal
    down_payment_amount: Decimal
    markup_amount: Decimal
    installment_count: int
    frequency: str
    first_due_date: str
    maturity_date: str
    currency_code: str
    terms_snapshot: dict[str, Any]


class InstallmentScheduleDocumentLine(InstallmentsBaseSchema):
    sequence: int
    due_date: str
    scheduled_amount: Decimal
    allocated_amount: Decimal
    waived_at: str | None = None
    voided_at: str | None = None


class InstallmentScheduleDocument(InstallmentsBaseSchema):
    """Response body for ``GET /contracts/{id}/documents/schedule``."""

    document_type: str
    contract_id: UUID
    contract_number: str
    version_number: int
    generated_at: str | None = None
    lines: list[InstallmentScheduleDocumentLine]


class InstallmentCustomerStatementContract(InstallmentsBaseSchema):
    contract_id: UUID
    contract_number: str
    status: str
    contractual_total: Decimal
    schedule_outstanding: Decimal | None = None


class InstallmentCustomerStatement(InstallmentsBaseSchema):
    """Response body for ``GET /customers/{id}/statement``."""

    document_type: str
    customer_id: UUID
    contracts: list[InstallmentCustomerStatementContract]
