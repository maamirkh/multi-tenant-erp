"""Customer 360 response schemas (spec §20, plan.md §14, tasks.md T160).

Section-level compound authorization (FR-RPT-111): each of the four
sections independently resolves to one of three discriminated states —
``PRESENT`` (a real, possibly-zero figure), ``OMITTED`` (an entitlement/
permission gate failed — ``not_entitled`` or ``not_permitted``), or
``UNAVAILABLE`` (authorized, but no data source configured —
``not_configured``/``no_data_source``). This two-reason schema is approved
architecture per plan.md §14 (FR-RPT-114) — retained here unchanged; the
frontend's later choice not to surface the raw reason string to end users
(T254) is a separate, non-contradictory UX decision that does not affect
this backend contract.

No field here ever sums or blends two domains' figures (FR-RPT-113) — each
``Present*Section`` carries only its own domain's measures.
"""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from modules.reports.schemas.common import CurrencyAmount


class SectionState(StrEnum):
    PRESENT = "present"
    OMITTED = "omitted"
    UNAVAILABLE = "unavailable"


class OmittedSection(BaseModel):
    state: Literal[SectionState.OMITTED] = SectionState.OMITTED
    reason: Literal["not_entitled", "not_permitted"]


class UnavailableSection(BaseModel):
    state: Literal[SectionState.UNAVAILABLE] = SectionState.UNAVAILABLE
    reason: Literal["not_configured", "no_data_source"]


class PresentSalesSection(BaseModel):
    """Sourced from ``ADAPTER_REGISTRY[ReportDomain.SALES]``'s existing
    ``sales.summary`` report, filtered by this one customer — always
    ``PRESENT`` once authorized, since Sales has no "not configured"
    concept; a real zero is a real zero (plan.md §14)."""

    state: Literal[SectionState.PRESENT] = SectionState.PRESENT
    total_revenue: Decimal | None
    """Set only when one currency (or none) is present — FR-RPT-152."""
    total_revenue_by_currency: list[CurrencyAmount] = Field(default_factory=list)
    invoice_count: int


class PresentAccountingArSection(BaseModel):
    """Sourced from the existing, unmodified
    ``AccountsReceivableService.get_customer_aging()`` — never a new
    formula. ``balance`` is a real zero when the customer has no open
    ledger yet (distinct from ``UNAVAILABLE(not_configured)``, which means
    Accounting itself has no Chart of Accounts — FR-RPT-115)."""

    state: Literal[SectionState.PRESENT] = SectionState.PRESENT
    balance: Decimal


class PresentCrmSection(BaseModel):
    """Sourced from CRM's existing, pre-Epic-11
    ``OpportunityService.list_filtered(customer_id=...)`` — never a new
    CRM seam (CRM is not one of the three sanctioned T047/T075/T087
    source-domain touches)."""

    state: Literal[SectionState.PRESENT] = SectionState.PRESENT
    open_opportunity_count: int
    open_opportunity_value: Decimal | None
    """Set only when one currency (or none) is present — FR-RPT-152."""
    open_opportunity_value_by_currency: list[CurrencyAmount] = Field(
        default_factory=list
    )


class PresentInstallmentsSection(BaseModel):
    """Sourced only from ``installments.aging``-shaped data (allow-list
    scoped by construction, plan.md §13) — never
    ``installments.dashboard``. ``read_only_servicing_continuity`` mirrors
    the Executive Dashboard's identical Installments-widget exception
    (FR-RPT-041)."""

    state: Literal[SectionState.PRESENT] = SectionState.PRESENT
    outstanding_principal: Decimal | None
    """Set only when one currency (or none) is present — FR-RPT-152."""
    outstanding_principal_by_currency: list[CurrencyAmount] = Field(
        default_factory=list
    )
    contract_count: int
    read_only_servicing_continuity: bool


SalesSection = Annotated[
    PresentSalesSection | OmittedSection | UnavailableSection,
    Field(discriminator="state"),
]
AccountingArSection = Annotated[
    PresentAccountingArSection | OmittedSection | UnavailableSection,
    Field(discriminator="state"),
]
CrmSection = Annotated[
    PresentCrmSection | OmittedSection | UnavailableSection,
    Field(discriminator="state"),
]
InstallmentsSection = Annotated[
    PresentInstallmentsSection | OmittedSection | UnavailableSection,
    Field(discriminator="state"),
]


class Customer360Response(BaseModel):
    """Identity fields (``customer_id``/``customer_name``) are always
    present once the base gate (T161/T162) passes — even when every
    section below is ``OMITTED`` (the minimum-useful-response rule,
    FR-RPT-116, T164)."""

    customer_id: UUID
    customer_name: str
    sales: SalesSection
    accounting_ar: AccountingArSection
    crm: CrmSection
    installments: InstallmentsSection
