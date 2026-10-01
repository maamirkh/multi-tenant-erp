"""KPI / Metric semantic catalog (spec §10, plan.md §8, tasks.md T146).

``METRIC_CATALOG`` mirrors spec §10's table 1:1 — 16 entries. A
``MetricDefinition`` is documentation + a stable ID for dashboard-widget/
report-column wiring — it is **never** itself a computation; every
consumer resolves a metric by calling the adapter method named in
``source_call`` (documentation only), never by re-deriving the number
locally (FR-RPT-021).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from modules.reports.registry.definitions import ReportDomain


@dataclass(frozen=True)
class MetricDefinition:
    semantic_id: str
    label: str
    description: str
    authoritative_domain: ReportDomain
    source_call: str
    date_basis: str
    money_precision: Literal["NUMERIC_15_2", "NUMERIC_20_6", "NA"]
    supports_comparison: bool
    inclusion_rule: str


METRIC_CATALOG: dict[str, MetricDefinition] = {
    m.semantic_id: m
    for m in (
        MetricDefinition(
            semantic_id="metric.sales.gross",
            label="Gross Sales",
            description="Sum of invoiced amounts before credit-note offset.",
            authoritative_domain=ReportDomain.SALES,
            source_call="sales.ReportService.run_report — sales.summary",
            date_basis="invoice_date",
            money_precision="NUMERIC_15_2",
            supports_comparison=True,
            inclusion_rule=(
                "SalesInvoice.status IN (ISSUED, PAID, CREDIT_NOTE_ISSUED); "
                "excludes DRAFT, CANCELLED"
            ),
        ),
        MetricDefinition(
            semantic_id="metric.sales.net",
            label="Net Sales",
            description="Gross Sales minus recorded credit-note offsets.",
            authoritative_domain=ReportDomain.SALES,
            source_call="sales.KPIService.get_dashboard — KPI-01 Revenue",
            date_basis="invoice_date",
            money_precision="NUMERIC_15_2",
            supports_comparison=True,
            inclusion_rule="Same invoice set as Gross Sales",
        ),
        MetricDefinition(
            semantic_id="metric.sales.order_count",
            label="Sales Order Count",
            description="Count of non-void orders created.",
            authoritative_domain=ReportDomain.SALES,
            source_call="sales.ReportService.run_report — sales.summary",
            date_basis="order_date",
            money_precision="NA",
            supports_comparison=True,
            inclusion_rule="Excludes DRAFT, REJECTED, CANCELLED",
        ),
        MetricDefinition(
            semantic_id="metric.sales.aov",
            label="Average Order Value",
            description="Net Sales divided by invoice count in the same period.",
            authoritative_domain=ReportDomain.SALES,
            source_call="derived from metric.sales.net",
            date_basis="invoice_date",
            money_precision="NUMERIC_15_2",
            supports_comparison=True,
            inclusion_rule="Derived from Net Sales",
        ),
        MetricDefinition(
            semantic_id="metric.sales.line_margin",
            label="Sales Line-Item Margin (operational)",
            description=(
                "Sum of (unit_price - cost_price) x qty across order lines — "
                "explicitly not the same figure as Recognized Gross Profit "
                "Margin."
            ),
            authoritative_domain=ReportDomain.SALES,
            source_call="sales.ReportService.run_report — sales.by_product",
            date_basis="order_date",
            money_precision="NUMERIC_15_2",
            supports_comparison=True,
            inclusion_rule="Non-cancelled order lines",
        ),
        MetricDefinition(
            semantic_id="metric.accounting.gross_profit_margin",
            label="Recognized Gross Profit Margin (financial)",
            description=(
                "Existing Accounting KPI: (Revenue - COGS) / Revenue from "
                "posted GL — the authoritative margin figure for financial "
                "reporting."
            ),
            authoritative_domain=ReportDomain.ACCOUNTING,
            source_call="accounting.FinancialKPIService.get_dashboard_kpis",
            date_basis="posting_date",
            money_precision="NUMERIC_20_6",
            supports_comparison=True,
            inclusion_rule="Posted journal entries only",
        ),
        MetricDefinition(
            semantic_id="metric.purchase.spend",
            label="Purchase Spend",
            description="Sum of PO totals.",
            authoritative_domain=ReportDomain.PURCHASE,
            source_call="purchase.KPIService.get_all_kpis — kpi_07_total_purchase_value",
            date_basis="created_at",
            money_precision="NUMERIC_15_2",
            supports_comparison=True,
            inclusion_rule=(
                "PurchaseOrder.status IN (APPROVED, PARTIALLY_RECEIVED, "
                "FULLY_RECEIVED, CLOSED); excludes DRAFT, REJECTED, CANCELLED"
            ),
        ),
        MetricDefinition(
            semantic_id="metric.ar.balance",
            label="Accounts Receivable Balance",
            description="Total outstanding customer receivables.",
            authoritative_domain=ReportDomain.ACCOUNTING,
            source_call="accounting.FinancialKPIService.get_dashboard_kpis",
            date_basis="as-of date",
            money_precision="NUMERIC_20_6",
            supports_comparison=True,
            inclusion_rule="Per AccountsReceivableService aging logic",
        ),
        MetricDefinition(
            semantic_id="metric.ap.balance",
            label="Accounts Payable Balance",
            description="Total outstanding supplier payables.",
            authoritative_domain=ReportDomain.ACCOUNTING,
            source_call="accounting.FinancialKPIService.get_dashboard_kpis",
            date_basis="as-of date",
            money_precision="NUMERIC_20_6",
            supports_comparison=True,
            inclusion_rule="Per AccountsPayableService aging logic",
        ),
        MetricDefinition(
            semantic_id="metric.ar.overdue",
            label="Overdue Receivables",
            description="AR balance outside the 'Current' aging bucket.",
            authoritative_domain=ReportDomain.ACCOUNTING,
            source_call="accounting.FinancialKPIService.get_dashboard_kpis",
            date_basis="due_date",
            money_precision="NUMERIC_20_6",
            supports_comparison=True,
            inclusion_rule="Aging buckets 1-30...120+, excludes Current",
        ),
        MetricDefinition(
            semantic_id="metric.inventory.value_operational",
            label="Operational Inventory Value (WAC)",
            description=(
                "On-hand stock valued at Weighted Average Cost — an "
                "operational costing figure, not a reconciled "
                "financial-statement balance."
            ),
            authoritative_domain=ReportDomain.INVENTORY,
            source_call="inventory.ReportQueryService.inventory_valuation",
            date_basis="as-of date",
            money_precision="NUMERIC_20_6",
            supports_comparison=True,
            inclusion_rule="StockPosition.qty_on_hand > 0",
        ),
        MetricDefinition(
            semantic_id="metric.cash.position",
            label="Cash Position",
            description="Existing Accounting KPI: total bank + cash balances.",
            authoritative_domain=ReportDomain.ACCOUNTING,
            source_call="accounting.FinancialKPIService.get_dashboard_kpis",
            date_basis="as-of date",
            money_precision="NUMERIC_20_6",
            supports_comparison=True,
            inclusion_rule="Active bank/cash accounts",
        ),
        MetricDefinition(
            semantic_id="metric.crm.pipeline_value",
            label="CRM Pipeline Value",
            description="Sum of open opportunity value.",
            authoritative_domain=ReportDomain.CRM,
            source_call="crm.CrmReportingService.get_dashboard",
            date_basis="as-of date",
            money_precision="NUMERIC_15_2",
            supports_comparison=True,
            inclusion_rule="Opportunity.status = OPEN",
        ),
        MetricDefinition(
            semantic_id="metric.crm.win_rate",
            label="CRM Win Rate",
            description="WON / (WON + LOST) closed in period.",
            authoritative_domain=ReportDomain.CRM,
            source_call="crm.CrmReportingService.get_dashboard",
            date_basis="won_at/lost_at",
            money_precision="NA",
            supports_comparison=True,
            inclusion_rule="Opportunity.status IN (WON, LOST)",
        ),
        MetricDefinition(
            semantic_id="metric.installments.outstanding",
            label="Outstanding Installment Principal",
            description="Remaining scheduled principal across serviceable contracts.",
            authoritative_domain=ReportDomain.INSTALLMENTS,
            source_call="installments.InstallmentReportingService.get_aging_report",
            date_basis="as-of date",
            money_precision="NUMERIC_20_6",
            supports_comparison=True,
            inclusion_rule="InstallmentContract.status IN (ACTIVE, DEFAULTED)",
        ),
        MetricDefinition(
            semantic_id="metric.installments.overdue",
            label="Overdue Installments",
            description="Installment lines in OVERDUE due-state.",
            authoritative_domain=ReportDomain.INSTALLMENTS,
            source_call="installments.InstallmentReportingService.get_overdue_report",
            date_basis="as-of date",
            money_precision="NUMERIC_20_6",
            supports_comparison=True,
            inclusion_rule="Per DueStateCalculator/InstallmentAgingCalculator",
        ),
    )
}
