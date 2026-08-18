"""Customer360Service — dedicated read/query service (plan.md §14, ADR-6).

A single ``get_customer_360()`` call issues a small, fixed number of
bounded queries that does NOT scale with the number of Opportunities/
Activities/Sales documents a Customer has accumulated — no per-row
follow-up query is issued for any item in a returned list (no N+1):

  1. ``CustomerRepository.get_by_id_or_none()``            (Sales, read-only)
  2. ``LeadRepository.list_converted_to_customer()``        (CRM)
  3. ``OpportunityRepository.list_filtered(customer_id=..)`` (CRM, bounded)
  4. ``ActivityRepository.list_filtered(customer_id=..)``    (CRM, bounded)
  5. ``AccountsReceivableService.get_customer_ledger()``     (Accounting, read-only)
  6. ``AccountsReceivableService.get_customer_aging()``      (Accounting, read-only)

plus four small ``COUNT(*)``-style Sales summary queries (quotations,
orders, invoices, deliveries — spec.md §20.1's "counts/summaries only, no
full document fetches"). This service never issues an ``INSERT``/
``UPDATE``/``DELETE`` of any kind (plan.md ADR-6/§16) — it is read-only,
end to end.

``last_interaction``/``next_follow_up`` are computed in-process from the
already-fetched Activity/Lead lists (plan.md §14) — no extra query.

Spec ref: specs/009-crm/spec.md §20, §22; plan.md §14, §16, ADR-3, ADR-6.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.accounting.exceptions import CustomerLedgerNotFoundError
from modules.accounting.services.ar_service import AccountsReceivableService
from modules.crm.exceptions import CustomerNotFoundError
from modules.crm.models.activity import Activity
from modules.crm.models.lead import Lead
from modules.crm.models.opportunity import Opportunity
from modules.crm.repositories.activity import ActivityRepository
from modules.crm.repositories.lead import LeadRepository
from modules.crm.repositories.opportunity import OpportunityRepository
from modules.sales.models.customer import Customer
from modules.sales.models.delivery import DeliveryNote
from modules.sales.models.invoice import SalesInvoice
from modules.sales.models.order import SalesOrder
from modules.sales.models.quotation import SalesQuotation
from modules.sales.repositories.customer import CustomerRepository

#: Bounded page size for the Opportunities/Activities sub-lists (spec.md
#: NFR-003's 1-second p95 target assumes bounded, not unbounded, sub-lists).
_LIST_LIMIT = 50


@dataclass(frozen=True)
class SalesHistorySummaryResult:
    quotation_count: int
    order_count: int
    invoice_count: int
    delivery_count: int


@dataclass(frozen=True)
class FinancialSummaryResult:
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


@dataclass(frozen=True)
class Customer360Result:
    customer: Customer
    converted_leads: list[Lead]
    opportunities: list[Opportunity]
    activities: list[Activity]
    sales_history: SalesHistorySummaryResult
    financial_summary: FinancialSummaryResult
    last_interaction: datetime | None
    next_follow_up: date | None


class Customer360Service:
    """Read-only composition of CRM + Sales + Accounting data for a single
    Customer (spec.md §20). Never writes anything, anywhere."""

    def __init__(
        self,
        db: Session,
        customer_repo: CustomerRepository,
        lead_repo: LeadRepository,
        opportunity_repo: OpportunityRepository,
        activity_repo: ActivityRepository,
        ar_service: AccountsReceivableService,
    ) -> None:
        self.db = db
        self._customer_repo = customer_repo
        self._lead_repo = lead_repo
        self._opportunity_repo = opportunity_repo
        self._activity_repo = activity_repo
        self._ar_service = ar_service

    def get_customer_360(
        self, company_id: UUID, customer_id: UUID
    ) -> Customer360Result:
        # Cross-tenant / non-existent Customer -> 404 before any other query
        # runs (spec.md §30.2 — no partial leak of CRM data for an
        # inaccessible Customer).
        customer = self._customer_repo.get_by_id_or_none(customer_id, company_id)
        if customer is None:
            raise CustomerNotFoundError(str(customer_id))

        converted_leads = self._lead_repo.list_converted_to_customer(
            company_id, customer_id
        )
        opportunities, _ = self._opportunity_repo.list_filtered(
            company_id, customer_id=customer_id, page=1, page_size=_LIST_LIMIT
        )
        activities, _ = self._activity_repo.list_filtered(
            company_id, customer_id=customer_id, page=1, page_size=_LIST_LIMIT
        )

        sales_history = self._get_sales_history(company_id, customer_id)
        financial_summary = self._get_financial_summary(company_id, customer_id)

        last_interaction = max(
            (a.completed_at for a in activities if a.completed_at is not None),
            default=None,
        )
        follow_up_candidates: list[date] = [
            a.due_date.date()
            for a in activities
            if a.status == "PLANNED" and a.due_date is not None
        ]
        follow_up_candidates += [
            lead.next_follow_up_date
            for lead in converted_leads
            if lead.next_follow_up_date is not None
        ]
        next_follow_up = min(follow_up_candidates, default=None)

        return Customer360Result(
            customer=customer,
            converted_leads=converted_leads,
            opportunities=opportunities,
            activities=activities,
            sales_history=sales_history,
            financial_summary=financial_summary,
            last_interaction=last_interaction,
            next_follow_up=next_follow_up,
        )

    # ------------------------------------------------------------------
    # Sales summary counts — single COUNT(*)-style queries, never a full
    # document fetch (spec.md §20.1). Issued directly against the Sales
    # ORM models (read-only SELECT) rather than adding new methods to
    # Sales' own repositories, since not every Sales repository already
    # exposes a customer-scoped count method and Sales files may not be
    # modified by this epic (plan.md §29.3).
    # ------------------------------------------------------------------

    def _get_sales_history(
        self, company_id: UUID, customer_id: UUID
    ) -> SalesHistorySummaryResult:
        customer_id_str = str(customer_id)
        return SalesHistorySummaryResult(
            quotation_count=self.db.execute(
                select(func.count())
                .select_from(SalesQuotation)
                .where(SalesQuotation.company_id == company_id)
                .where(SalesQuotation.customer_id == customer_id_str)
                .where(SalesQuotation.is_deleted == False)  # noqa: E712
            ).scalar_one(),
            order_count=self.db.execute(
                select(func.count())
                .select_from(SalesOrder)
                .where(SalesOrder.company_id == company_id)
                .where(SalesOrder.customer_id == customer_id_str)
                .where(SalesOrder.is_deleted == False)  # noqa: E712
            ).scalar_one(),
            invoice_count=self.db.execute(
                select(func.count())
                .select_from(SalesInvoice)
                .where(SalesInvoice.company_id == company_id)
                .where(SalesInvoice.customer_id == customer_id_str)
                .where(SalesInvoice.is_deleted == False)  # noqa: E712
            ).scalar_one(),
            delivery_count=self.db.execute(
                select(func.count())
                .select_from(DeliveryNote)
                .where(DeliveryNote.company_id == company_id)
                .where(DeliveryNote.customer_id == customer_id_str)
                .where(DeliveryNote.is_deleted == False)  # noqa: E712
            ).scalar_one(),
        )

    # ------------------------------------------------------------------
    # Financial summary — live Accounting reads only, never cached
    # (spec.md §20.2, AC-16). A Customer with no AR activity yet has no
    # CustomerLedger row at all; that is not an error for Customer 360
    # (AC-17 graceful degradation) — it degrades to zero/GOOD defaults.
    # ------------------------------------------------------------------

    def _get_financial_summary(
        self, company_id: UUID, customer_id: UUID
    ) -> FinancialSummaryResult:
        as_of_date = utcnow().date()
        try:
            ledger = self._ar_service.get_customer_ledger(company_id, customer_id)
        except CustomerLedgerNotFoundError:
            return FinancialSummaryResult(
                total_outstanding_base=Decimal("0"),
                credit_limit=Decimal("0"),
                credit_status="GOOD",
                as_of_date=as_of_date,
                current=Decimal("0"),
                days_1_30=Decimal("0"),
                days_31_60=Decimal("0"),
                days_61_90=Decimal("0"),
                days_91_120=Decimal("0"),
                days_120_plus=Decimal("0"),
            )

        aging_row = self._ar_service.get_customer_aging(
            company_id, customer_id, as_of_date=as_of_date
        )
        return FinancialSummaryResult(
            total_outstanding_base=ledger.total_outstanding_base,
            credit_limit=ledger.credit_limit,
            credit_status=ledger.credit_status,
            as_of_date=as_of_date,
            current=aging_row.current if aging_row else Decimal("0"),
            days_1_30=aging_row.days_1_30 if aging_row else Decimal("0"),
            days_31_60=aging_row.days_31_60 if aging_row else Decimal("0"),
            days_61_90=aging_row.days_61_90 if aging_row else Decimal("0"),
            days_91_120=aging_row.days_91_120 if aging_row else Decimal("0"),
            days_120_plus=aging_row.days_120_plus if aging_row else Decimal("0"),
        )
