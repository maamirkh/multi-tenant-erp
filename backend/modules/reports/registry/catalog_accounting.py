"""Report Registry entries for Accounting's 9 "Now" reports + 2 DEFERRED
stubs (T056, T122). Importing this module registers every entry and
populates ``ADAPTER_REGISTRY[ReportDomain.ACCOUNTING]``.
"""

from __future__ import annotations

from modules.reports.registry.definitions import (
    DrillDownTarget,
    ExportFormat,
    PaginationStyle,
    ReportDefinition,
    ReportDomain,
    ReportExecutionKind,
    ReportStatus,
    register,
)
from modules.reports.schemas.accounting import (
    AccountingKpiFilter,
    ApAgingFilter,
    ArAgingFilter,
    BalanceSheetFilter,
    BankCashBookFilter,
    CashFlowFilter,
    GlFilter,
    ProfitLossFilter,
    TrialBalanceFilter,
)
from modules.reports.schemas.common import FreshnessClassification
from modules.reports.services.adapters.accounting_adapter import AccountingAdapter
from modules.reports.services.adapters.base import ADAPTER_REGISTRY

ADAPTER_REGISTRY[ReportDomain.ACCOUNTING] = AccountingAdapter()

_JOURNAL_DRILL_DOWN = DrillDownTarget(
    label="View journal entry",
    target_route="/accounting/journal-entries/{journal_entry_id}",
    required_permission="accounting.journal.view",
    preserves_filters=(),
)

register(
    ReportDefinition(
        key="accounting.trial_balance",
        name="Trial Balance",
        description="Debit=Credit control per account.",
        domain=ReportDomain.ACCOUNTING,
        authoritative_source=(
            "modules.accounting.services.financial_statements."
            "FinancialStatementService.get_trial_balance"
        ),
        required_permission="reports.accounting.view",
        export_permission="reports.accounting.export",
        domain_capability_key="accounting",
        supported_filters=TrialBalanceFilter,
        supported_dimensions=("account",),
        supported_measures=("total_debit", "total_credit"),
        sortable_fields=(),
        export_formats=(ExportFormat.PDF, ExportFormat.XLSX),
        drill_down_targets=(_JOURNAL_DRILL_DOWN,),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.NONE,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )
)

register(
    ReportDefinition(
        key="accounting.gl",
        name="General Ledger",
        description="Account/journal detail, cursor-paginated.",
        domain=ReportDomain.ACCOUNTING,
        authoritative_source=(
            "modules.accounting.services.report_service.ReportService.get_gl_report"
        ),
        required_permission="reports.accounting.view",
        export_permission="reports.accounting.export",
        domain_capability_key="accounting",
        supported_filters=GlFilter,
        supported_dimensions=("account", "source"),
        supported_measures=("debit_amount", "credit_amount"),
        sortable_fields=(),
        export_formats=(ExportFormat.CSV, ExportFormat.XLSX),
        drill_down_targets=(_JOURNAL_DRILL_DOWN,),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.CURSOR,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )
)

register(
    ReportDefinition(
        key="accounting.profit_loss",
        name="Profit & Loss",
        description="Income statement.",
        domain=ReportDomain.ACCOUNTING,
        authoritative_source=(
            "modules.accounting.services.financial_statements."
            "FinancialStatementService.get_pl"
        ),
        required_permission="reports.accounting.view",
        export_permission="reports.accounting.export",
        domain_capability_key="accounting",
        supported_filters=ProfitLossFilter,
        supported_dimensions=("cost_center",),
        supported_measures=("total_revenue", "total_expense", "net_income"),
        sortable_fields=(),
        export_formats=(ExportFormat.PDF, ExportFormat.XLSX),
        drill_down_targets=(_JOURNAL_DRILL_DOWN,),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.NONE,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )
)

register(
    ReportDefinition(
        key="accounting.balance_sheet",
        name="Balance Sheet",
        description="Financial position as of a date.",
        domain=ReportDomain.ACCOUNTING,
        authoritative_source=(
            "modules.accounting.services.financial_statements."
            "FinancialStatementService.get_balance_sheet"
        ),
        required_permission="reports.accounting.view",
        export_permission="reports.accounting.export",
        domain_capability_key="accounting",
        supported_filters=BalanceSheetFilter,
        supported_dimensions=(),
        supported_measures=("total_assets", "total_liabilities", "total_equity"),
        sortable_fields=(),
        export_formats=(ExportFormat.PDF, ExportFormat.XLSX),
        drill_down_targets=(_JOURNAL_DRILL_DOWN,),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.NONE,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )
)

register(
    ReportDefinition(
        key="accounting.cash_flow",
        name="Cash Flow Statement",
        description="Indirect-method cash flow.",
        domain=ReportDomain.ACCOUNTING,
        authoritative_source=(
            "modules.accounting.services.financial_statements."
            "FinancialStatementService.get_cash_flow"
        ),
        required_permission="reports.accounting.view",
        export_permission="reports.accounting.export",
        domain_capability_key="accounting",
        supported_filters=CashFlowFilter,
        supported_dimensions=(),
        supported_measures=("net_change_in_cash",),
        sortable_fields=(),
        export_formats=(ExportFormat.PDF, ExportFormat.XLSX),
        drill_down_targets=(_JOURNAL_DRILL_DOWN,),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.NONE,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )
)

register(
    ReportDefinition(
        key="accounting.ar_aging",
        name="AR Aging & Customer Statement",
        description="Receivable exposure by aging bucket.",
        domain=ReportDomain.ACCOUNTING,
        authoritative_source=(
            "modules.accounting.services.ar_service."
            "AccountsReceivableService.get_aging_report"
        ),
        required_permission="reports.accounting.view",
        export_permission="reports.accounting.export",
        domain_capability_key="accounting",
        supported_filters=ArAgingFilter,
        supported_dimensions=("customer",),
        supported_measures=("current", "days_1_30", "total"),
        sortable_fields=(),
        export_formats=(ExportFormat.PDF, ExportFormat.XLSX),
        drill_down_targets=(
            DrillDownTarget(
                label="View customer invoices",
                target_route="/accounting/ar/customers/{customer_id}",
                required_permission="accounting.ar.view",
                preserves_filters=("as_of_date",),
            ),
        ),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.OFFSET,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )
)

register(
    ReportDefinition(
        key="accounting.ap_aging",
        name="AP Aging & Supplier Statement",
        description="Payable exposure by aging bucket.",
        domain=ReportDomain.ACCOUNTING,
        authoritative_source=(
            "modules.accounting.services.ap_service."
            "AccountsPayableService.get_aging_report"
        ),
        required_permission="reports.accounting.view",
        export_permission="reports.accounting.export",
        domain_capability_key="accounting",
        supported_filters=ApAgingFilter,
        supported_dimensions=("supplier",),
        supported_measures=("current", "days_1_30", "total"),
        sortable_fields=(),
        export_formats=(ExportFormat.PDF, ExportFormat.XLSX),
        drill_down_targets=(
            DrillDownTarget(
                label="View supplier bills",
                target_route="/accounting/ap/suppliers/{supplier_id}",
                required_permission="accounting.ap.view",
                preserves_filters=("as_of_date",),
            ),
        ),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.OFFSET,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )
)

register(
    ReportDefinition(
        key="accounting.bank_cash_book",
        name="Bank Book / Cash Book",
        description="Bank/cash transaction detail with running balance.",
        domain=ReportDomain.ACCOUNTING,
        authoritative_source=(
            "modules.accounting.services.bank_service.BankAccountService.get_bank_book"
        ),
        required_permission="reports.accounting.view",
        export_permission="reports.accounting.export",
        domain_capability_key="accounting",
        supported_filters=BankCashBookFilter,
        supported_dimensions=("account",),
        supported_measures=("amount",),
        sortable_fields=(),
        export_formats=(ExportFormat.CSV, ExportFormat.XLSX),
        drill_down_targets=(),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.OFFSET,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )
)

register(
    ReportDefinition(
        key="accounting.kpis",
        name="Financial KPI Dashboard",
        description="15 existing CFO KPIs.",
        domain=ReportDomain.ACCOUNTING,
        authoritative_source=(
            "modules.accounting.services.kpi_service."
            "FinancialKPIService.get_dashboard_kpis"
        ),
        required_permission="reports.accounting.view",
        export_permission=None,
        domain_capability_key="accounting",
        supported_filters=AccountingKpiFilter,
        supported_dimensions=(),
        supported_measures=(),
        sortable_fields=(),
        export_formats=(),
        drill_down_targets=(),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.NONE,
        status=ReportStatus.NOW,
        execution_kind=ReportExecutionKind.ADAPTER,
    )
)

# ---------------------------------------------------------------------------
# DEFERRED stubs (T122) — no adapter dispatch case, unreachable via
# discovery/execution; `authoritative_source` points at Accounting's real
# existing (but unwrapped) methods.
# ---------------------------------------------------------------------------

register(
    ReportDefinition(
        key="accounting.tax",
        name="Tax Summary / Detail",
        description="Tax liability reporting (deferred).",
        domain=ReportDomain.ACCOUNTING,
        authoritative_source="modules.accounting.services.tax_service.TaxService",
        required_permission="reports.accounting.view",
        export_permission="reports.accounting.export",
        domain_capability_key="accounting",
        supported_filters=AccountingKpiFilter,
        supported_dimensions=(),
        supported_measures=(),
        sortable_fields=(),
        export_formats=(ExportFormat.PDF,),
        drill_down_targets=(),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.NONE,
        status=ReportStatus.DEFERRED,
        execution_kind=ReportExecutionKind.ADAPTER,
    )
)

register(
    ReportDefinition(
        key="accounting.cost_center_pl",
        name="Cost-Center / Project P&L",
        description="Departmental P&L (deferred).",
        domain=ReportDomain.ACCOUNTING,
        authoritative_source=(
            "modules.accounting.services.cost_center_service.CostCenterService"
        ),
        required_permission="reports.accounting.view",
        export_permission="reports.accounting.export",
        domain_capability_key="accounting",
        supported_filters=ProfitLossFilter,
        supported_dimensions=("cost_center",),
        supported_measures=("net_income",),
        sortable_fields=(),
        export_formats=(ExportFormat.PDF,),
        drill_down_targets=(),
        branch_filterable=False,
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
        pagination=PaginationStyle.NONE,
        status=ReportStatus.DEFERRED,
        execution_kind=ReportExecutionKind.ADAPTER,
    )
)
