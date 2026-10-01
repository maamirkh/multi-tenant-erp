"""``ExecutiveDashboardService`` — the Executive Dashboard composition
(spec §13, plan.md §33 Phase 4, tasks.md T148/T149).

Each of the 10 widgets independently evaluates its own domain entitlement
+ ``reports.<domain>.view`` permission (gate fail -> ``OMITTED``, no
reason field, FR-RPT-041) then calls the metric's adapter method via
``ADAPTER_REGISTRY`` (already populated, Phase 2/3) — never a locally
re-derived formula (FR-RPT-021). The one, non-contradictory partial-
failure rule (tasks.md §0.2 item 8): a widget call is wrapped in
``except UnavailablePrerequisiteError`` **only** — this is the sole typed,
expected exception (T003) that converts a widget to ``UNAVAILABLE``;
every other exception is left uncaught here and propagates as a genuine
5xx, failing the whole request (T156) — this method never uses a bare
``except Exception``.

**Comparison caveat**: several widgets are backed by an adapter call whose
underlying report has no period/as-of-date parameter at all (CRM's
``crm.dashboard`` is always "current calendar month"; Inventory's
``inventory.valuation`` is always "right now"; Installments'
``installments.due_overdue`` is always "as of today") — a genuine,
pre-existing shape of those Phase 2 reports, not something this phase
may change (CRM/Inventory/Installments are not sanctioned T047/T075/T087
seam domains). For those widgets, ``comparison`` is always ``None``: there
is no second period to call the same adapter method against. Every other
widget calls its adapter method twice (current + comparison period, via
``date_range_service.resolve_comparison_period``) and feeds both values
into ``comparison_service.compute_comparison`` (T024) — never its own
locally recomputed trend.

**Currencies (FR-RPT-152)**: Sales, Purchase, Inventory, CRM and
Installments figures are gathered per currency and reported per currency
(each with its own comparison). A widget's single value field is set only
when exactly one currency is present — never a sum across currencies.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from modules.accounting.dependencies import (
    build_allocation_engine,
    build_ar_service,
    build_payment_service,
)
from modules.accounting.schemas.dashboard import FinancialKPIResponse
from modules.installments.repositories.allocation_reference import (
    InstallmentAllocationReferenceRepository,
)
from modules.installments.repositories.audit import InstallmentAuditLogRepository
from modules.installments.repositories.contract import InstallmentContractRepository
from modules.installments.repositories.late_charge import (
    InstallmentLateChargeRepository,
)
from modules.installments.repositories.plan_template import (
    InstallmentPlanTemplateRepository,
)
from modules.installments.repositories.schedule import InstallmentScheduleRepository
from modules.installments.services.accounting_gateway import (
    AccountingIntegrationGateway,
)
from modules.installments.services.reporting_service import InstallmentReportingService
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from modules.platform_admin.services.entitlement_service import (
    PlatformEntitlementService,
)
from modules.reports.exceptions import UnavailablePrerequisiteError
from modules.reports.registry.definitions import ReportDomain
from modules.reports.schemas.accounting import AccountingKpiFilter
from modules.reports.schemas.common import (
    ComparisonRequest,
    ComparisonResult,
    CurrencyAmount,
    DrillDownRef,
    PeriodResolution,
)
from modules.reports.schemas.crm import CrmDashboardByCurrency, CrmDashboardFilter
from modules.reports.schemas.dashboard import (
    ApWidget,
    ArWidget,
    CashPositionWidget,
    CrmPipelineWidget,
    ExecutiveDashboardResponse,
    GrossProfitMarginWidget,
    GrossSalesWidget,
    InstallmentExposureWidget,
    NetSalesWidget,
    OperationalInventoryValueWidget,
    PurchaseSpendWidget,
    WidgetState,
)
from modules.reports.schemas.installments import (
    DueOverdueFilter,
    InstallmentAgingFilter,
)
from modules.reports.schemas.inventory import (
    InventoryValuationFilter,
    InventoryValuationResponse,
)
from modules.reports.schemas.purchase import PurchaseKpiFilter, PurchaseKpiSet
from modules.reports.schemas.sales import (
    SalesKpiFilter,
    SalesKpiReport,
    SalesSummaryFilter,
    SalesSummaryRow,
)
from modules.reports.services.adapters.base import (
    ADAPTER_REGISTRY,
    AggregateReportResult,
    PaginatedReportResult,
)
from modules.reports.services.comparison_service import compute_comparison
from modules.reports.services.date_range_service import resolve_comparison_period
from modules.reports.services.installments_continuity_gate import (
    InstallmentsAccessState,
    InstallmentsServicingContinuityGate,
)
from modules.reports.services.money_normalization import normalize_amount
from modules.reports.services.permission_check import user_has_reports_permission
from modules.sales.schemas.reports import KPIType

_ZERO = Decimal("0")

#: One figure per currency code (``None`` only where the source has none).
type _Amounts = dict[str | None, Decimal]


def _add(amounts: _Amounts, code: str | None, value: Decimal) -> None:
    amounts[code] = amounts.get(code, _ZERO) + value


def _currency_amounts(
    current: _Amounts,
    prior: _Amounts | None = None,
    period: PeriodResolution | None = None,
) -> list[CurrencyAmount]:
    """Each currency's own figure, with its own comparison against the
    same currency in the prior period when one is given (FR-RPT-152)."""
    assert prior is None or period is not None
    codes = sorted(set(current) | set(prior or {}), key=lambda code: code or "")
    return [
        CurrencyAmount(
            currency_code=code,
            amount=normalize_amount(current.get(code, _ZERO)),
            comparison=(
                compute_comparison(
                    current.get(code, _ZERO),
                    prior.get(code, _ZERO),
                    is_current_period_partial=period.is_partial_current_period,
                )
                if prior is not None and period is not None
                else None
            ),
        )
        for code in codes
    ]


def _single_value(
    amounts: list[CurrencyAmount],
    period: PeriodResolution | None = None,
    *,
    compared: bool = False,
) -> tuple[Decimal | None, ComparisonResult | None]:
    """The widget's single ``value``/``comparison``: the one currency's
    figures; a genuine zero when there is no data at all; ``None`` when
    several currencies are present — never a cross-currency sum."""
    if len(amounts) == 1:
        return amounts[0].amount, amounts[0].comparison
    if not amounts:
        comparison = (
            compute_comparison(
                _ZERO, _ZERO, is_current_period_partial=period.is_partial_current_period
            )
            if compared and period is not None
            else None
        )
        return normalize_amount(_ZERO), comparison
    return None, None


def _period_dates(period: PeriodResolution) -> tuple[date, date]:
    """*period* is a half-open ``[start, end)`` interval — most source
    reports take an inclusive ``date_to``, so the exclusive UTC boundary
    is converted to the last calendar day actually inside the period."""
    start = date.fromisoformat(period.start[:10])
    end_inclusive = date.fromisoformat(period.end[:10]) - timedelta(days=1)
    return start, end_inclusive


def _build_entitlement_service(db: Session) -> PlatformEntitlementService:
    return PlatformEntitlementService(
        db=db,
        plan_repo=PlanRepository(db),
        subscription_repo=SubscriptionRepository(db),
    )


def _build_installments_reporting_service(db: Session) -> InstallmentReportingService:
    """Mirrors ``execution_service.py``'s own local copy — kept separate
    rather than cross-imported, matching that file's own stated rationale
    (construction code never shared across independent call sites)."""
    gateway = AccountingIntegrationGateway(
        ar_service=build_ar_service(db),
        payment_service=build_payment_service(db),
        allocation_engine=build_allocation_engine(db),
    )
    return InstallmentReportingService(
        contract_repo=InstallmentContractRepository(db),
        schedule_repo=InstallmentScheduleRepository(db),
        allocation_ref_repo=InstallmentAllocationReferenceRepository(db),
        late_charge_repo=InstallmentLateChargeRepository(db),
        audit_repo=InstallmentAuditLogRepository(db),
        plan_template_repo=InstallmentPlanTemplateRepository(db),
        accounting_gateway=gateway,
        access_policy=None,
    )


def _domain_entitled(
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    capability_key: str,
) -> bool:
    return entitlement_service.resolve_effective_entitlement(
        company_id=company_id, capability_key=capability_key
    ).available


def _permitted(
    db: Session,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    permission_code: str,
) -> bool:
    return user_has_reports_permission(
        db, company_id, user_id, permission_code, user_roles=user_roles
    )


def _gated(
    db: Session,
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    capability_key: str,
    permission_code: str,
) -> bool:
    return _domain_entitled(
        entitlement_service, company_id, capability_key
    ) and _permitted(db, company_id, user_id, user_roles, permission_code)


# ---------------------------------------------------------------------------
# Sales — Net Sales (KPI-01 Revenue, +trend) / Gross Sales (summed sales.summary)
# ---------------------------------------------------------------------------


def _sales_revenue(db: Session, company_id: UUID, period: PeriodResolution) -> _Amounts:
    start, end_inclusive = _period_dates(period)
    filters = SalesKpiFilter(date_from=start, date_to=end_inclusive)
    result = ADAPTER_REGISTRY[ReportDomain.SALES].run(
        db, company_id, "sales.kpis", filters, 1, 1, None, None
    )
    assert isinstance(result, AggregateReportResult)
    assert isinstance(result.data, SalesKpiReport)
    revenue: _Amounts = {}
    for block in result.data.by_currency:
        kpi = next((k for k in block.kpis if k.kpi_id == KPIType.REVENUE.value), None)
        if kpi is not None and kpi.value is not None:
            revenue[block.currency_code] = kpi.value
    return revenue


def _sales_gross(db: Session, company_id: UUID, period: PeriodResolution) -> _Amounts:
    start, end_inclusive = _period_dates(period)
    filters = SalesSummaryFilter(date_from=start, date_to=end_inclusive)
    probe = ADAPTER_REGISTRY[ReportDomain.SALES].run(
        db, company_id, "sales.summary", filters, 1, 1, None, None
    )
    assert isinstance(probe, PaginatedReportResult)
    totals: _Amounts = {}
    if probe.total == 0:
        return totals
    full = ADAPTER_REGISTRY[ReportDomain.SALES].run(
        db, company_id, "sales.summary", filters, 1, probe.total, None, None
    )
    assert isinstance(full, PaginatedReportResult)
    for row in full.items:
        assert isinstance(row, SalesSummaryRow)
        _add(totals, row.currency_code, row.revenue)
    return totals


def _net_sales_widget(
    db: Session,
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    period: PeriodResolution,
    comparison: ComparisonRequest | None,
) -> NetSalesWidget:
    if not _gated(
        db,
        entitlement_service,
        company_id,
        user_id,
        user_roles,
        "sales",
        "reports.sales.view",
    ):
        return NetSalesWidget(state=WidgetState.OMITTED)
    current = _sales_revenue(db, company_id, period)
    prior = None
    if comparison is not None:
        prior_period = resolve_comparison_period(period, comparison.comparison_type)
        prior = _sales_revenue(db, company_id, prior_period)
    amounts = _currency_amounts(current, prior, period)
    value, comparison_result = _single_value(
        amounts, period, compared=comparison is not None
    )
    return NetSalesWidget(
        state=WidgetState.PRESENT,
        value=value,
        by_currency=amounts,
        comparison=comparison_result,
        drill_down=DrillDownRef(
            label="View sales KPIs",
            target_route="/analytics/sales.kpis",
            required_permission="reports.sales.view",
        ),
    )


def _gross_sales_widget(
    db: Session,
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    period: PeriodResolution,
    comparison: ComparisonRequest | None,
) -> GrossSalesWidget:
    if not _gated(
        db,
        entitlement_service,
        company_id,
        user_id,
        user_roles,
        "sales",
        "reports.sales.view",
    ):
        return GrossSalesWidget(state=WidgetState.OMITTED)
    current = _sales_gross(db, company_id, period)
    prior = None
    if comparison is not None:
        prior_period = resolve_comparison_period(period, comparison.comparison_type)
        prior = _sales_gross(db, company_id, prior_period)
    amounts = _currency_amounts(current, prior, period)
    value, comparison_result = _single_value(
        amounts, period, compared=comparison is not None
    )
    return GrossSalesWidget(
        state=WidgetState.PRESENT,
        value=value,
        by_currency=amounts,
        comparison=comparison_result,
        drill_down=DrillDownRef(
            label="View sales summary",
            target_route="/analytics/sales.summary",
            required_permission="reports.sales.view",
        ),
    )


# ---------------------------------------------------------------------------
# Purchase — Purchase Spend (kpi_07_total_purchase_value)
# ---------------------------------------------------------------------------


def _purchase_spend(
    db: Session, company_id: UUID, period: PeriodResolution
) -> _Amounts:
    start, end_inclusive = _period_dates(period)
    filters = PurchaseKpiFilter(date_from=start, date_to=end_inclusive)
    result = ADAPTER_REGISTRY[ReportDomain.PURCHASE].run(
        db, company_id, "purchase.kpis", filters, 1, 1, None, None
    )
    assert isinstance(result, AggregateReportResult)
    assert isinstance(result.data, PurchaseKpiSet)
    return {
        block.currency_code: block.total_purchase_value
        for block in result.data.by_currency
        if block.total_purchase_value != _ZERO
    }


def _purchase_spend_widget(
    db: Session,
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    period: PeriodResolution,
    comparison: ComparisonRequest | None,
) -> PurchaseSpendWidget:
    if not _gated(
        db,
        entitlement_service,
        company_id,
        user_id,
        user_roles,
        "purchase",
        "reports.purchase.view",
    ):
        return PurchaseSpendWidget(state=WidgetState.OMITTED)
    current = _purchase_spend(db, company_id, period)
    prior = None
    if comparison is not None:
        prior_period = resolve_comparison_period(period, comparison.comparison_type)
        prior = _purchase_spend(db, company_id, prior_period)
    amounts = _currency_amounts(current, prior, period)
    value, comparison_result = _single_value(
        amounts, period, compared=comparison is not None
    )
    return PurchaseSpendWidget(
        state=WidgetState.PRESENT,
        value=value,
        by_currency=amounts,
        comparison=comparison_result,
        drill_down=DrillDownRef(
            label="View purchase KPIs",
            target_route="/analytics/purchase.kpis",
            required_permission="reports.purchase.view",
        ),
    )


# ---------------------------------------------------------------------------
# Accounting — AR / AP / Cash Position / Gross Profit Margin, all from the
# single ``accounting.kpis`` call (Category D aggregate, one Accounting
# round trip serves all four widgets' current-period figures).
# ---------------------------------------------------------------------------


def _accounting_kpis(
    db: Session, company_id: UUID, as_of_date: date
) -> FinancialKPIResponse:
    filters = AccountingKpiFilter(as_of_date=as_of_date)
    result = ADAPTER_REGISTRY[ReportDomain.ACCOUNTING].run(
        db, company_id, "accounting.kpis", filters, 1, 1, None, None
    )
    assert isinstance(result, AggregateReportResult)
    assert isinstance(result.data, FinancialKPIResponse)
    return result.data


def _ar_widget(
    db: Session,
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    period: PeriodResolution,
    comparison: ComparisonRequest | None,
) -> ArWidget:
    if not _gated(
        db,
        entitlement_service,
        company_id,
        user_id,
        user_roles,
        "accounting",
        "reports.accounting.view",
    ):
        return ArWidget(state=WidgetState.OMITTED)
    _, as_of = _period_dates(period)
    kpis = _accounting_kpis(db, company_id, as_of)
    balance = kpis.kpis["accounts_receivable_total"].current_value
    overdue_pct = kpis.kpis["ar_overdue_pct"].current_value
    # No SQL-level "AR overdue total" seam exists (only the aging bucket
    # rows and this pre-computed percentage) — this reconstructs the
    # absolute amount from two already-authoritative Accounting figures
    # (balance x pct), the same `total - current` relationship
    # ``FinancialKPIService._compute_raw`` itself uses internally, never a
    # new aging formula.
    overdue = balance * overdue_pct / Decimal("100")
    comparison_result = None
    if comparison is not None:
        prior_period = resolve_comparison_period(period, comparison.comparison_type)
        _, prior_as_of = _period_dates(prior_period)
        prior_kpis = _accounting_kpis(db, company_id, prior_as_of)
        prior_balance = prior_kpis.kpis["accounts_receivable_total"].current_value
        comparison_result = compute_comparison(
            balance,
            prior_balance,
            is_current_period_partial=period.is_partial_current_period,
        )
    return ArWidget(
        state=WidgetState.PRESENT,
        balance=normalize_amount(balance),
        overdue=normalize_amount(overdue),
        comparison=comparison_result,
        drill_down=DrillDownRef(
            label="View AR aging",
            target_route="/analytics/accounting.ar_aging",
            required_permission="reports.accounting.view",
        ),
    )


def _ap_widget(
    db: Session,
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    period: PeriodResolution,
    comparison: ComparisonRequest | None,
) -> ApWidget:
    if not _gated(
        db,
        entitlement_service,
        company_id,
        user_id,
        user_roles,
        "accounting",
        "reports.accounting.view",
    ):
        return ApWidget(state=WidgetState.OMITTED)
    _, as_of = _period_dates(period)
    kpis = _accounting_kpis(db, company_id, as_of)
    value = kpis.kpis["accounts_payable_total"].current_value
    comparison_result = None
    if comparison is not None:
        prior_period = resolve_comparison_period(period, comparison.comparison_type)
        _, prior_as_of = _period_dates(prior_period)
        prior_kpis = _accounting_kpis(db, company_id, prior_as_of)
        prior_value = prior_kpis.kpis["accounts_payable_total"].current_value
        comparison_result = compute_comparison(
            value,
            prior_value,
            is_current_period_partial=period.is_partial_current_period,
        )
    return ApWidget(
        state=WidgetState.PRESENT,
        value=normalize_amount(value),
        comparison=comparison_result,
        drill_down=DrillDownRef(
            label="View AP aging",
            target_route="/analytics/accounting.ap_aging",
            required_permission="reports.accounting.view",
        ),
    )


def _cash_position_widget(
    db: Session,
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    period: PeriodResolution,
    comparison: ComparisonRequest | None,
) -> CashPositionWidget:
    if not _gated(
        db,
        entitlement_service,
        company_id,
        user_id,
        user_roles,
        "accounting",
        "reports.accounting.view",
    ):
        return CashPositionWidget(state=WidgetState.OMITTED)
    _, as_of = _period_dates(period)
    kpis = _accounting_kpis(db, company_id, as_of)
    value = kpis.kpis["cash_position"].current_value
    comparison_result = None
    if comparison is not None:
        prior_period = resolve_comparison_period(period, comparison.comparison_type)
        _, prior_as_of = _period_dates(prior_period)
        prior_kpis = _accounting_kpis(db, company_id, prior_as_of)
        prior_value = prior_kpis.kpis["cash_position"].current_value
        comparison_result = compute_comparison(
            value,
            prior_value,
            is_current_period_partial=period.is_partial_current_period,
        )
    return CashPositionWidget(
        state=WidgetState.PRESENT,
        value=normalize_amount(value),
        comparison=comparison_result,
        drill_down=DrillDownRef(
            label="View bank/cash book",
            target_route="/analytics/accounting.bank_cash_book",
            required_permission="reports.accounting.view",
        ),
    )


def _gross_profit_margin_widget(
    db: Session,
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    period: PeriodResolution,
    comparison: ComparisonRequest | None,
) -> GrossProfitMarginWidget:
    if not _gated(
        db,
        entitlement_service,
        company_id,
        user_id,
        user_roles,
        "accounting",
        "reports.accounting.view",
    ):
        return GrossProfitMarginWidget(state=WidgetState.OMITTED)
    _, as_of = _period_dates(period)
    kpis = _accounting_kpis(db, company_id, as_of)
    value = kpis.kpis["gross_profit_margin"].current_value
    comparison_result = None
    if comparison is not None:
        prior_period = resolve_comparison_period(period, comparison.comparison_type)
        _, prior_as_of = _period_dates(prior_period)
        prior_kpis = _accounting_kpis(db, company_id, prior_as_of)
        prior_value = prior_kpis.kpis["gross_profit_margin"].current_value
        comparison_result = compute_comparison(
            value,
            prior_value,
            is_current_period_partial=period.is_partial_current_period,
        )
    return GrossProfitMarginWidget(
        state=WidgetState.PRESENT,
        value=value,
        comparison=comparison_result,
        drill_down=DrillDownRef(
            label="View financial KPI dashboard",
            target_route="/analytics/accounting.kpis",
            required_permission="reports.accounting.view",
        ),
    )


# ---------------------------------------------------------------------------
# Inventory — Operational Inventory Value (WAC). No as-of parameter exists
# on ``inventory.valuation`` (always "right now") — comparison never
# populated for this widget.
# ---------------------------------------------------------------------------


def _inventory_widget(
    db: Session,
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
) -> OperationalInventoryValueWidget:
    if not _gated(
        db,
        entitlement_service,
        company_id,
        user_id,
        user_roles,
        "inventory",
        "reports.inventory.view",
    ):
        return OperationalInventoryValueWidget(state=WidgetState.OMITTED)
    result = ADAPTER_REGISTRY[ReportDomain.INVENTORY].run(
        db,
        company_id,
        "inventory.valuation",
        InventoryValuationFilter(warehouse_id=None),
        1,
        1,
        None,
        None,
    )
    assert isinstance(result, AggregateReportResult)
    assert isinstance(result.data, InventoryValuationResponse)
    amounts = _currency_amounts(
        {t.currency_code: t.amount for t in result.data.grand_totals_by_currency}
    )
    value, _ = _single_value(amounts)
    return OperationalInventoryValueWidget(
        state=WidgetState.PRESENT,
        value=value,
        by_currency=amounts,
        valuation_basis=result.data.valuation_basis,
        comparison=None,
        drill_down=DrillDownRef(
            label="View inventory valuation",
            target_route="/analytics/inventory.valuation",
            required_permission="reports.inventory.view",
        ),
    )


# ---------------------------------------------------------------------------
# CRM — Pipeline Value + Win Rate. ``crm.dashboard`` takes no period
# parameter at all (always "current calendar month") — comparison never
# populated for this widget.
# ---------------------------------------------------------------------------


def _crm_widget(
    db: Session,
    entitlement_service: PlatformEntitlementService,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
) -> CrmPipelineWidget:
    if not _gated(
        db,
        entitlement_service,
        company_id,
        user_id,
        user_roles,
        "crm",
        "reports.crm.view",
    ):
        return CrmPipelineWidget(state=WidgetState.OMITTED)
    result = ADAPTER_REGISTRY[ReportDomain.CRM].run(
        db, company_id, "crm.dashboard", CrmDashboardFilter(), 1, 1, None, None
    )
    assert isinstance(result, AggregateReportResult)
    assert isinstance(result.data, CrmDashboardByCurrency)
    amounts = _currency_amounts(
        {v.currency_code: v.open_pipeline_value for v in result.data.by_currency}
    )
    value, _ = _single_value(amounts)
    return CrmPipelineWidget(
        state=WidgetState.PRESENT,
        pipeline_value=value,
        pipeline_value_by_currency=amounts,
        win_rate=result.data.win_rate,
        comparison=None,
        drill_down=DrillDownRef(
            label="View CRM pipeline",
            target_route="/analytics/crm.pipeline",
            required_permission="reports.crm.view",
        ),
    )


# ---------------------------------------------------------------------------
# Installments — Outstanding Principal + Overdue. The one widget with
# FR-RPT-041's three-way branch (T149): sourced only from the allow-listed
# ``installments.aging``/``installments.due_overdue``-shaped data, in both
# ENTITLED_FULL and SERVICING_CONTINUITY states, never from
# ``installments.dashboard`` (not on the allow-list). ``due_overdue`` has
# no as-of parameter (always "as of today") — comparison never populated.
# ---------------------------------------------------------------------------


def _installments_figures(
    db: Session, company_id: UUID, as_of: date
) -> tuple[_Amounts, _Amounts]:
    """Outstanding principal and overdue per contract currency."""
    aging_result = ADAPTER_REGISTRY[ReportDomain.INSTALLMENTS].run(
        db,
        company_id,
        "installments.aging",
        InstallmentAgingFilter(as_of_date=as_of),
        1,
        50_000,
        None,
        None,
    )
    assert isinstance(aging_result, PaginatedReportResult)
    principal: _Amounts = {}
    for row in aging_result.items:
        _add(
            principal,
            getattr(row, "currency_code", None),
            Decimal(str(getattr(row, "outstanding_amount", "0"))),
        )

    due_overdue_result = ADAPTER_REGISTRY[ReportDomain.INSTALLMENTS].run(
        db,
        company_id,
        "installments.due_overdue",
        DueOverdueFilter(),
        1,
        50_000,
        None,
        None,
    )
    assert isinstance(due_overdue_result, PaginatedReportResult)
    overdue: _Amounts = {}
    for row in due_overdue_result.items:
        if getattr(row, "report_type", None) == "overdue":
            _add(
                overdue,
                getattr(row, "currency_code", None),
                Decimal(str(getattr(row, "outstanding_amount", "0"))),
            )

    return principal, overdue


def _installments_widget(
    db: Session,
    gate: InstallmentsServicingContinuityGate,
    company_id: UUID,
    user_id: UUID | None,
    user_roles: list[str] | None,
    period: PeriodResolution,
) -> InstallmentExposureWidget:
    if not _permitted(db, company_id, user_id, user_roles, "reports.installments.view"):
        return InstallmentExposureWidget(state=WidgetState.OMITTED)
    state = gate.evaluate(company_id)
    if state is InstallmentsAccessState.UNAVAILABLE:
        return InstallmentExposureWidget(state=WidgetState.OMITTED)
    _, as_of = _period_dates(period)
    principal, overdue = _installments_figures(db, company_id, as_of)
    principal_amounts = _currency_amounts(principal)
    overdue_amounts = _currency_amounts(overdue)
    codes = {a.currency_code for a in principal_amounts + overdue_amounts}
    principal_value: Decimal | None
    overdue_value: Decimal | None
    if len(codes) > 1:
        # Several currencies: neither single figure is meaningful.
        principal_value, overdue_value = None, None
    else:
        principal_value, _ = _single_value(principal_amounts)
        overdue_value, _ = _single_value(overdue_amounts)
    return InstallmentExposureWidget(
        state=WidgetState.PRESENT,
        outstanding_principal=principal_value,
        overdue=overdue_value,
        outstanding_principal_by_currency=principal_amounts,
        overdue_by_currency=overdue_amounts,
        read_only_servicing_continuity=state
        is InstallmentsAccessState.SERVICING_CONTINUITY,
        comparison=None,
        drill_down=DrillDownRef(
            label="View installment aging",
            target_route="/analytics/installments.aging",
            required_permission="reports.installments.view",
        ),
    )


class ExecutiveDashboardService:
    """Stateless — every method takes ``db`` explicitly, matching every
    Phase 2/3 service's own convention."""

    def get(
        self,
        db: Session,
        *,
        company_id: UUID,
        user_id: UUID | None,
        period: PeriodResolution,
        comparison: ComparisonRequest | None,
        user_roles: list[str] | None = None,
    ) -> ExecutiveDashboardResponse:
        entitlement_service = _build_entitlement_service(db)
        installments_gate = InstallmentsServicingContinuityGate(
            entitlement_service=entitlement_service,
            reporting_service=_build_installments_reporting_service(db),
        )

        try:
            net_sales = _net_sales_widget(
                db,
                entitlement_service,
                company_id,
                user_id,
                user_roles,
                period,
                comparison,
            )
        except UnavailablePrerequisiteError:
            net_sales = NetSalesWidget(state=WidgetState.UNAVAILABLE)

        try:
            gross_sales = _gross_sales_widget(
                db,
                entitlement_service,
                company_id,
                user_id,
                user_roles,
                period,
                comparison,
            )
        except UnavailablePrerequisiteError:
            gross_sales = GrossSalesWidget(state=WidgetState.UNAVAILABLE)

        try:
            purchase_spend = _purchase_spend_widget(
                db,
                entitlement_service,
                company_id,
                user_id,
                user_roles,
                period,
                comparison,
            )
        except UnavailablePrerequisiteError:
            purchase_spend = PurchaseSpendWidget(state=WidgetState.UNAVAILABLE)

        try:
            ar = _ar_widget(
                db,
                entitlement_service,
                company_id,
                user_id,
                user_roles,
                period,
                comparison,
            )
        except UnavailablePrerequisiteError:
            ar = ArWidget(state=WidgetState.UNAVAILABLE)

        try:
            ap = _ap_widget(
                db,
                entitlement_service,
                company_id,
                user_id,
                user_roles,
                period,
                comparison,
            )
        except UnavailablePrerequisiteError:
            ap = ApWidget(state=WidgetState.UNAVAILABLE)

        try:
            cash_position = _cash_position_widget(
                db,
                entitlement_service,
                company_id,
                user_id,
                user_roles,
                period,
                comparison,
            )
        except UnavailablePrerequisiteError:
            cash_position = CashPositionWidget(state=WidgetState.UNAVAILABLE)

        try:
            operational_inventory_value = _inventory_widget(
                db, entitlement_service, company_id, user_id, user_roles
            )
        except UnavailablePrerequisiteError:
            operational_inventory_value = OperationalInventoryValueWidget(
                state=WidgetState.UNAVAILABLE
            )

        try:
            crm_pipeline = _crm_widget(
                db, entitlement_service, company_id, user_id, user_roles
            )
        except UnavailablePrerequisiteError:
            crm_pipeline = CrmPipelineWidget(state=WidgetState.UNAVAILABLE)

        try:
            installment_exposure = _installments_widget(
                db, installments_gate, company_id, user_id, user_roles, period
            )
        except UnavailablePrerequisiteError:
            installment_exposure = InstallmentExposureWidget(
                state=WidgetState.UNAVAILABLE
            )

        try:
            gross_profit_margin = _gross_profit_margin_widget(
                db,
                entitlement_service,
                company_id,
                user_id,
                user_roles,
                period,
                comparison,
            )
        except UnavailablePrerequisiteError:
            gross_profit_margin = GrossProfitMarginWidget(state=WidgetState.UNAVAILABLE)

        return ExecutiveDashboardResponse(
            period=period,
            net_sales=net_sales,
            gross_sales=gross_sales,
            purchase_spend=purchase_spend,
            ar=ar,
            ap=ap,
            cash_position=cash_position,
            operational_inventory_value=operational_inventory_value,
            crm_pipeline=crm_pipeline,
            installment_exposure=installment_exposure,
            gross_profit_margin=gross_profit_margin,
        )


dashboard_service = ExecutiveDashboardService()

#: A Python bound-method access (``instance.method``) creates a *new*
#: object every time it's evaluated (``instance.method is instance.method``
#: is ``False``) — pinning it once, here, to a stable module-level name is
#: what lets the registry-consistency test's identity check (T032) hold:
#: both ``COMPOSITE_REPORT_HANDLERS["exec.dashboard"]`` (T151) and
#: ``ReportDefinition.authoritative_source``'s resolved callable must be
#: this exact same object, not two independently-created bound methods
#: that merely compare equal.
get_dashboard = dashboard_service.get
