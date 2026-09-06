"""Pydantic schemas for Customer 360 (spec.md §20) — Phase 7.

Customer 360 is a pure read-model composition — every schema here is a
response type only (no ``*Create``/``*Update`` variants). Financial figures
(``FinancialSummary``) are always populated directly from
``AccountsReceivableService``'s own response objects at request time, never
from a stored/cached CRM value (spec.md §20.2, BR — AC-16).

Spec ref: specs/009-crm/spec.md §20, §38.6; plan.md §14, ADR-6.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from modules.crm.schemas.activity import ActivityRead
from modules.crm.schemas.base import CrmBaseSchema
from modules.crm.schemas.lead import LeadRead
from modules.crm.schemas.opportunity import OpportunityRead


class CustomerSummary(CrmBaseSchema):
    """Core Customer identity fields, read live from Sales' ``Customer`` —
    never duplicated/persisted CRM-side (§20.1)."""

    id: UUID
    customer_code: str
    legal_name: str
    trading_name: str | None
    status: str
    currency_code: str


class SalesHistorySummary(CrmBaseSchema):
    """Counts only — never full document fetches (spec.md §20.1)."""

    quotation_count: int
    order_count: int
    invoice_count: int
    delivery_count: int


class FinancialSummary(CrmBaseSchema):
    """Live Accounts Receivable figures — always fetched fresh from
    ``AccountsReceivableService`` on every request, never cached (§20.2,
    AC-16). A Customer with no AR activity yet (no ``CustomerLedger`` row)
    degrades to all-zero/``GOOD`` values rather than a 404 (AC-17)."""

    total_outstanding_base: Decimal
    credit_limit: Decimal
    credit_status: str
    as_of_date: date
    current: Decimal
    days_1_30: Decimal
    days_31_60: Decimal
    days_61_90: Decimal
    days_91_120: Decimal
    days_120_plus: Decimal


class Customer360(CrmBaseSchema):
    """Response body for ``GET /crm/customers/{customer_id}/360``."""

    customer: CustomerSummary
    converted_leads: list[LeadRead]
    opportunities: list[OpportunityRead]
    activities: list[ActivityRead]
    sales_history: SalesHistorySummary
    financial_summary: FinancialSummary
    last_interaction: datetime | None
    next_follow_up: date | None
