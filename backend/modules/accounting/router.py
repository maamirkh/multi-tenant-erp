"""Accounting module API router — Phase 1 + Phase 2 endpoints.

Phase 1 endpoints:
    GET  /health                    — module health check
    GET  /feature-flags             — list all feature flags with effective state
    PUT  /feature-flags/{key}       — update a feature flag override

    GET  /configuration             — get company accounting configuration
    PUT  /configuration             — update company accounting configuration

    GET  /currencies                — list currencies (global registry)
    POST /currencies                — create a currency

    GET  /exchange-rates            — list exchange rates for this company
    POST /exchange-rates            — record a new exchange rate

Phase 2 endpoints (Chart of Accounts):
    GET    /accounts                — list accounts (?tree=true for nested hierarchy)
    POST   /accounts                — create an account
    GET    /accounts/{id}           — get account detail
    PUT    /accounts/{id}           — update an account
    DELETE /accounts/{id}           — deactivate an account (soft, invariant-checked)
    POST   /accounts/{id}/activate  — reactivate an account
    POST   /accounts/bulk-import    — bulk import accounts from CSV rows
    GET    /accounts/export         — export the full COA

    GET    /account-groups          — list account groups
    POST   /account-groups          — create an account group

    GET    /system-accounts         — get current system account assignments
    PUT    /system-accounts         — designate a system account role

    GET    /coa-templates           — list available industry COA templates
    POST   /coa-templates/apply     — apply an industry template to this company

Phase 3 endpoints (Fiscal Calendar): see specs/008-accounting-finance/tasks.md T078

Phase 4 endpoints (General Ledger — CRITICAL):
    GET  /journals                       — list/search journal entries
    POST /journals                       — create a DRAFT journal entry
    GET  /journals/{id}                  — get journal entry detail (with lines)
    POST /journals/{id}/submit           — DRAFT -> SUBMITTED
    POST /journals/{id}/approve          — SUBMITTED -> APPROVED
    POST /journals/{id}/reject           — SUBMITTED -> REJECTED
    POST /journals/{id}/post             — post a DRAFT/APPROVED entry (PostingEngine)
    POST /journals/{id}/reverse          — reverse a POSTED entry
    GET  /reports/gl                     — GL detail report (filters)

Spec ref: specs/008-accounting-finance/tasks.md T023, T035, T057, T078, T101
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth.dependencies import require_authenticated
from core.auth.interfaces import CurrentUser
from core.database.session import get_db
from core.logging.setup import REQUEST_ID_CONTEXT
from core.schemas.response import ResponseMeta, StandardResponse
from core.utils.datetime import utcnow
from modules.accounting.constants import MODULE_NAME, MODULE_VERSION
from modules.accounting.dependencies import (
    get_accounting_configuration_service,
    get_accounting_feature_flag_service,
    get_ai_service,
    get_ap_service,
    get_ar_service,
    get_audit_log_repo,
    get_bank_account_service,
    get_bank_reconciliation_service,
    get_cash_account_service,
    get_chart_of_accounts_service,
    get_cost_center_service,
    get_currency_revaluation_service,
    get_currency_service,
    get_financial_statement_service,
    get_fiscal_calendar_service,
    get_gl_report_repo,
    get_journal_entry_repo,
    get_journal_entry_service,
    get_kpi_service,
    get_payment_service,
    get_posting_engine,
    get_recurring_journal_service,
    get_report_service,
    get_tax_calculator,
    get_tax_service,
)
from modules.accounting.exceptions import (
    AccountingFeatureDisabledError,
    ApprovalPermissionDeniedError,
)
from modules.accounting.repositories.gl import (
    AccountingAuditLogRepository,
    GLReportRepository,
    JournalEntryRepository,
)
from modules.accounting.schemas.ai import (
    AnomalyFlagResponse,
    AnomalyReportRequest,
    CashFlowHistoryPeriod,
    GLEventStreamRow,
    PLHistoryPeriod,
)
from modules.accounting.schemas.ap import (
    APAgingReport,
    APAgingRow,
    APTransactionResponse,
    BillCreateRequest,
    CreditNoteCreateRequest,
    ReconcileStatementRequest,
    ReconciliationItemResponse,
    RemittanceAdviceResponse,
    SupplierLedgerResponse,
    SupplierStatementReconciliationResponse,
    SupplierStatementResponse,
)
from modules.accounting.schemas.ar import (
    ARAgingReport,
    ARAgingRow,
    ARTransactionResponse,
    CreditHoldReleaseRequest,
    CreditHoldRequest,
    CreditLimitRequest,
    CustomerLedgerResponse,
    CustomerStatementResponse,
    WriteOffRequest,
)
from modules.accounting.schemas.banking import (
    AutoMatchResultResponse,
    BankAccountCreateRequest,
    BankAccountResponse,
    BankAccountUpdateRequest,
    BankBookResponse,
    BankChargeRequest,
    BankDepositRequest,
    BankReconciliationResponse,
    BankStatementImportRequest,
    BankStatementLineResponse,
    BankTransactionResponse,
    BankTransferRequest,
    BankTransferResponse,
    ChequeCreateRequest,
    ChequeResponse,
    ChequeStatusUpdateRequest,
    ReconciliationMatchRequest,
    ReconciliationReportResponse,
    ReconciliationStartRequest,
)
from modules.accounting.schemas.cash import (
    CashAccountCreateRequest,
    CashAccountResponse,
    CashBookResponse,
    CashPaymentRequest,
    CashReceiptRequest,
    CashReconciliationRequest,
    CashReconciliationResponse,
    CashTransactionResponse,
    PettyCashReplenishmentRequest,
    PettyCashReplenishmentResponse,
    PettyCashVoucherRequest,
    PettyCashVoucherResponse,
)
from modules.accounting.schemas.coa import (
    AccountCreateRequest,
    AccountGroupCreate,
    AccountGroupRead,
    AccountResponse,
    AccountTreeNode,
    AccountUpdateRequest,
    COAImportResultRow,
    COATemplateApplyRequest,
    COATemplateInfo,
    SystemAccountConfigRequest,
)
from modules.accounting.schemas.cost import (
    CostCenterCreateRequest,
    CostCenterPLReport,
    CostCenterResponse,
    DepartmentCreateRequest,
    DepartmentResponse,
    ProjectCreateRequest,
    ProjectResponse,
)
from modules.accounting.schemas.currency import (
    RevaluationReport,
    RevaluationRequest,
)
from modules.accounting.schemas.dashboard import (
    CashPositionResponse,
    FinancialKPIResponse,
)
from modules.accounting.schemas.fiscal import (
    FiscalPeriodResponse,
    FiscalYearCreateRequest,
    FiscalYearResponse,
    FiscalYearUpdateRequest,
    OpeningBalanceImportRequest,
    OpeningBalanceResponse,
    PeriodLockRequest,
    PeriodUnlockRequest,
    YearEndCloseRequest,
)
from modules.accounting.schemas.foundation import (
    AccountingConfigurationRead,
    AccountingConfigurationUpdate,
    AccountingFeatureFlagRead,
    AccountingFeatureFlagUpdate,
    CurrencyCreate,
    CurrencyRead,
    ExchangeRateCreate,
    ExchangeRateRead,
)
from modules.accounting.schemas.gl import (
    AuditLogEntryResponse,
    AuditLogListResponse,
    BatchPostingRequest,
    BatchPostingResponse,
    GLReportRow,
    JournalEntryDetailResponse,
    JournalEntryResponse,
    JournalLineResponse,
    PostingRequest,
    PostingResult,
    RejectRequest,
    ReverseRequest,
)
from modules.accounting.schemas.payments import (
    CancelPaymentRequest,
    CustomerPaymentRequest,
    PaymentAllocationLineResponse,
    PaymentAllocationRequest,
    PaymentRefundResponse,
    PaymentResponse,
    RefundRequest,
    SupplierPaymentRequest,
    WHTCertificateResponse,
)
from modules.accounting.schemas.recurring import (
    RecurringInstanceResponse,
    RecurringTemplateCreateRequest,
    RecurringTemplateDetailResponse,
    RecurringTemplateLineResponse,
    RecurringTemplateResponse,
    RecurringTemplateUpdateRequest,
)
from modules.accounting.schemas.reports import (
    BalanceSheetReport,
    CashFlowReport,
    JournalReportResponse,
    PLReport,
    TrialBalanceReport,
)
from modules.accounting.schemas.tax import (
    TaxAmountResponse,
    TaxCalculationRequest,
    TaxCalculationResult,
    TaxCodeCreateRequest,
    TaxCodeResponse,
    TaxCodeUpdateRequest,
    TaxDetailRow,
    TaxGroupCreateRequest,
    TaxGroupLineCreateRequest,
    TaxGroupLineResponse,
    TaxGroupResponse,
    TaxRateCreateRequest,
    TaxRateResponse,
    TaxSummaryReport,
    WHTReport,
)
from modules.accounting.services.ai_service import AIReadinessService
from modules.accounting.services.ap_service import AccountsPayableService
from modules.accounting.services.ar_service import AccountsReceivableService
from modules.accounting.services.bank_service import (
    BankAccountService,
    BankReconciliationService,
)
from modules.accounting.services.cash_service import CashAccountService
from modules.accounting.services.coa_service import (
    SYSTEM_ACCOUNT_TYPE_REQUIREMENTS,
    ChartOfAccountsService,
)
from modules.accounting.services.coa_templates import COA_TEMPLATES
from modules.accounting.services.configuration_service import (
    AccountingConfigurationService,
)
from modules.accounting.services.cost_center_service import CostCenterService
from modules.accounting.services.currency_revaluation_service import (
    CurrencyRevaluationService,
)
from modules.accounting.services.currency_service import CurrencyService
from modules.accounting.services.feature_flag_service import (
    AccountingFeatureFlagService,
)
from modules.accounting.services.financial_statements import FinancialStatementService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.accounting.services.journal_service import JournalEntryService
from modules.accounting.services.kpi_service import FinancialKPIService
from modules.accounting.services.payment_service import PaymentService
from modules.accounting.services.permission_check import user_has_accounting_permission
from modules.accounting.services.posting_engine import PostingEngine
from modules.accounting.services.recurring_journal_service import (
    RecurringJournalService,
)
from modules.accounting.services.report_export import export_to_excel, export_to_pdf
from modules.accounting.services.report_service import ReportService
from modules.accounting.services.tax_calculator import TaxCalculator
from modules.accounting.services.tax_service import TaxService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["accounting"])


def _meta() -> ResponseMeta:
    return ResponseMeta(request_id=REQUEST_ID_CONTEXT.get("-"), timestamp=utcnow())


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class AccountingHealthResponse(BaseModel):
    status: str
    module: str
    version: str


@router.get(
    "/health",
    response_model=StandardResponse[AccountingHealthResponse],
    summary="Accounting module health check",
)
async def accounting_health(
    user: CurrentUser = Depends(require_authenticated),
) -> StandardResponse[AccountingHealthResponse]:
    return StandardResponse(
        data=AccountingHealthResponse(
            status="healthy",
            module=MODULE_NAME,
            version=MODULE_VERSION,
        ),
        message="Accounting module is healthy",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------


@router.get(
    "/feature-flags",
    response_model=StandardResponse[list[AccountingFeatureFlagRead]],
    summary="List all accounting feature flags",
)
async def list_feature_flags(
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    flag_service: AccountingFeatureFlagService = Depends(
        get_accounting_feature_flag_service
    ),
) -> StandardResponse[list[AccountingFeatureFlagRead]]:
    flags = flag_service.get_all(company_id=company_id)
    return StandardResponse(
        data=[AccountingFeatureFlagRead(**f) for f in flags],
        message=f"Retrieved {len(flags)} feature flags",
        meta=_meta(),
    )


@router.put(
    "/feature-flags/{flag_key}",
    response_model=StandardResponse[AccountingFeatureFlagRead],
    summary="Update an accounting feature flag",
)
async def update_feature_flag(
    company_id: UUID = Path(...),
    flag_key: str = Path(...),
    body: AccountingFeatureFlagUpdate = ...,
    user: CurrentUser = Depends(require_authenticated),
    flag_service: AccountingFeatureFlagService = Depends(
        get_accounting_feature_flag_service
    ),
    db: Session = Depends(get_db),
) -> StandardResponse[AccountingFeatureFlagRead]:
    # RBAC gap fixed during pre-Epic-9 hardening audit (2026-08-14): feature
    # flags can toggle multi-currency/tax/reconciliation behavior
    # module-wide and had no permission check, unlike the comparable
    # PUT /configuration below. Reuses the same settings-management code.
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.approvalworkflow.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.approvalworkflow.manage")
    try:
        if body.is_enabled:
            flag_service.enable(
                company_id=company_id,
                flag_key=flag_key,
                actor_id=user.user_id,
                description=body.description,
            )
        else:
            flag_service.disable(
                company_id=company_id,
                flag_key=flag_key,
                actor_id=user.user_id,
                description=body.description,
            )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    flags = flag_service.get_all(company_id=company_id)
    updated = next((f for f in flags if f["flag_key"] == flag_key), None)
    return StandardResponse(
        data=AccountingFeatureFlagRead(**updated) if updated else None,
        message=f"Feature flag '{flag_key}' updated",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Accounting Configuration
# ---------------------------------------------------------------------------


@router.get(
    "/configuration",
    response_model=StandardResponse[AccountingConfigurationRead],
    summary="Get company accounting configuration",
)
async def get_configuration(
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    config_service: AccountingConfigurationService = Depends(
        get_accounting_configuration_service
    ),
) -> StandardResponse[AccountingConfigurationRead]:
    config = config_service.get_or_create(company_id=company_id)
    return StandardResponse(
        data=AccountingConfigurationRead.model_validate(config),
        message="Accounting configuration retrieved",
        meta=_meta(),
    )


@router.put(
    "/configuration",
    response_model=StandardResponse[AccountingConfigurationRead],
    summary="Update company accounting configuration",
)
async def update_configuration(
    company_id: UUID = Path(...),
    body: AccountingConfigurationUpdate = ...,
    user: CurrentUser = Depends(require_authenticated),
    config_service: AccountingConfigurationService = Depends(
        get_accounting_configuration_service
    ),
    db: Session = Depends(get_db),
) -> StandardResponse[AccountingConfigurationRead]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.approvalworkflow.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.approvalworkflow.manage")
    config = config_service.update(
        company_id=company_id, **body.model_dump(exclude_unset=True)
    )
    return StandardResponse(
        data=AccountingConfigurationRead.model_validate(config),
        message="Accounting configuration updated",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Currencies
# ---------------------------------------------------------------------------


@router.get(
    "/currencies",
    response_model=StandardResponse[list[CurrencyRead]],
    summary="List currencies",
)
async def list_currencies(
    company_id: UUID = Path(...),
    active_only: bool = Query(False),
    user: CurrentUser = Depends(require_authenticated),
    currency_service: CurrencyService = Depends(get_currency_service),
) -> StandardResponse[list[CurrencyRead]]:
    currencies = currency_service.list_currencies(active_only=active_only)
    return StandardResponse(
        data=[CurrencyRead.model_validate(c) for c in currencies],
        message=f"Retrieved {len(currencies)} currencies",
        meta=_meta(),
    )


@router.post(
    "/currencies",
    response_model=StandardResponse[CurrencyRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create a currency",
)
async def create_currency(
    company_id: UUID = Path(...),
    body: CurrencyCreate = ...,
    user: CurrentUser = Depends(require_authenticated),
    currency_service: CurrencyService = Depends(get_currency_service),
    db: Session = Depends(get_db),
) -> StandardResponse[CurrencyRead]:
    # RBAC gap fixed during pre-Epic-9 hardening audit (2026-08-14): the
    # sibling POST /exchange-rates in this same currency domain requires
    # accounting.exchangerate.manage; currency creation had no check at all.
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.exchangerate.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.exchangerate.manage")
    try:
        currency = currency_service.create_currency(
            iso_code=body.iso_code,
            name=body.name,
            symbol=body.symbol,
            decimal_places=body.decimal_places,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return StandardResponse(
        data=CurrencyRead.model_validate(currency),
        message="Currency created",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Exchange Rates
# ---------------------------------------------------------------------------


@router.get(
    "/exchange-rates",
    response_model=StandardResponse[list[ExchangeRateRead]],
    summary="List exchange rates",
)
async def list_exchange_rates(
    company_id: UUID = Path(...),
    from_currency_code: str | None = Query(None),
    to_currency_code: str | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    user: CurrentUser = Depends(require_authenticated),
    currency_service: CurrencyService = Depends(get_currency_service),
) -> StandardResponse[list[ExchangeRateRead]]:
    rates = currency_service.list_rates(
        company_id=company_id,
        from_currency_code=from_currency_code,
        to_currency_code=to_currency_code,
        start_date=start_date,
        end_date=end_date,
    )
    return StandardResponse(
        data=[ExchangeRateRead.model_validate(r) for r in rates],
        message=f"Retrieved {len(rates)} exchange rates",
        meta=_meta(),
    )


@router.post(
    "/exchange-rates",
    response_model=StandardResponse[ExchangeRateRead],
    status_code=status.HTTP_201_CREATED,
    summary="Record a new exchange rate",
)
async def create_exchange_rate(
    company_id: UUID = Path(...),
    body: ExchangeRateCreate = ...,
    user: CurrentUser = Depends(require_authenticated),
    currency_service: CurrencyService = Depends(get_currency_service),
    db: Session = Depends(get_db),
) -> StandardResponse[ExchangeRateRead]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.exchangerate.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.exchangerate.manage")
    rate = currency_service.set_exchange_rate(
        company_id=company_id,
        from_currency_code=body.from_currency_code,
        to_currency_code=body.to_currency_code,
        rate_date=body.rate_date,
        rate=body.rate,
        rate_type=body.rate_type,
        created_by=user.user_id,
    )
    return StandardResponse(
        data=ExchangeRateRead.model_validate(rate),
        message="Exchange rate recorded",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Chart of Accounts — Accounts (Phase 2)
# ---------------------------------------------------------------------------


@router.get(
    "/accounts",
    response_model=StandardResponse[list[AccountResponse]]
    | StandardResponse[list[AccountTreeNode]],
    summary="List accounts (flat or nested tree)",
)
async def list_accounts(
    company_id: UUID = Path(...),
    tree: bool = Query(False, description="Return the nested COA hierarchy"),
    account_type: str | None = Query(None),
    user: CurrentUser = Depends(require_authenticated),
    coa_service: ChartOfAccountsService = Depends(get_chart_of_accounts_service),
) -> StandardResponse[list[AccountResponse]] | StandardResponse[list[AccountTreeNode]]:
    if tree:
        nodes = coa_service.get_coa_tree(company_id=company_id)
        return StandardResponse(
            data=[AccountTreeNode.model_validate(n) for n in nodes],
            message="COA tree retrieved",
            meta=_meta(),
        )
    accounts = coa_service.list_accounts(
        company_id=company_id, account_type=account_type
    )
    return StandardResponse(
        data=[AccountResponse.model_validate(a) for a in accounts],
        message=f"Retrieved {len(accounts)} accounts",
        meta=_meta(),
    )


@router.post(
    "/accounts",
    response_model=StandardResponse[AccountResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
async def create_account(
    company_id: UUID = Path(...),
    body: AccountCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    coa_service: ChartOfAccountsService = Depends(get_chart_of_accounts_service),
    db: Session = Depends(get_db),
) -> StandardResponse[AccountResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.coa.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.coa.manage")
    try:
        account = coa_service.create_account(
            company_id=company_id,
            created_by=user.user_id,
            **body.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return StandardResponse(
        data=AccountResponse.model_validate(account),
        message="Account created",
        meta=_meta(),
    )


@router.get(
    "/accounts/export",
    response_model=StandardResponse[list[AccountResponse]],
    summary="Export the full chart of accounts",
)
async def export_accounts(
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    coa_service: ChartOfAccountsService = Depends(get_chart_of_accounts_service),
) -> StandardResponse[list[AccountResponse]]:
    accounts = coa_service.export_coa(company_id=company_id)
    return StandardResponse(
        data=[AccountResponse.model_validate(a) for a in accounts],
        message=f"Exported {len(accounts)} accounts",
        meta=_meta(),
    )


@router.post(
    "/accounts/bulk-import",
    response_model=StandardResponse[list[COAImportResultRow]],
    summary="Bulk import accounts from parsed CSV rows",
)
async def bulk_import_accounts(
    company_id: UUID = Path(...),
    rows: list[dict[str, Any]] = ...,
    user: CurrentUser = Depends(require_authenticated),
    coa_service: ChartOfAccountsService = Depends(get_chart_of_accounts_service),
    db: Session = Depends(get_db),
) -> StandardResponse[list[COAImportResultRow]]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.coa.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.coa.manage")
    try:
        results = coa_service.bulk_import_coa(
            company_id=company_id, rows=rows, created_by=user.user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    return StandardResponse(
        data=[COAImportResultRow(**r) for r in results],
        message=f"Processed {len(results)} rows",
        meta=_meta(),
    )


@router.get(
    "/accounts/{account_id}",
    response_model=StandardResponse[AccountResponse],
    summary="Get account detail",
)
async def get_account(
    company_id: UUID = Path(...),
    account_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    coa_service: ChartOfAccountsService = Depends(get_chart_of_accounts_service),
) -> StandardResponse[AccountResponse]:
    account = coa_service.get_account(company_id=company_id, account_id=account_id)
    return StandardResponse(
        data=AccountResponse.model_validate(account),
        message="Account retrieved",
        meta=_meta(),
    )


@router.put(
    "/accounts/{account_id}",
    response_model=StandardResponse[AccountResponse],
    summary="Update an account",
)
async def update_account(
    company_id: UUID = Path(...),
    account_id: UUID = Path(...),
    body: AccountUpdateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    coa_service: ChartOfAccountsService = Depends(get_chart_of_accounts_service),
    db: Session = Depends(get_db),
) -> StandardResponse[AccountResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.coa.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.coa.manage")
    try:
        account = coa_service.update_account(
            company_id=company_id,
            account_id=account_id,
            **body.model_dump(exclude_unset=True),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    return StandardResponse(
        data=AccountResponse.model_validate(account),
        message="Account updated",
        meta=_meta(),
    )


@router.delete(
    "/accounts/{account_id}",
    response_model=StandardResponse[AccountResponse],
    summary="Deactivate an account",
)
async def deactivate_account(
    company_id: UUID = Path(...),
    account_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    coa_service: ChartOfAccountsService = Depends(get_chart_of_accounts_service),
    db: Session = Depends(get_db),
) -> StandardResponse[AccountResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.coa.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.coa.manage")
    account = coa_service.deactivate_account(
        company_id=company_id, account_id=account_id
    )
    return StandardResponse(
        data=AccountResponse.model_validate(account),
        message="Account deactivated",
        meta=_meta(),
    )


@router.post(
    "/accounts/{account_id}/activate",
    response_model=StandardResponse[AccountResponse],
    summary="Reactivate an account",
)
async def activate_account(
    company_id: UUID = Path(...),
    account_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    coa_service: ChartOfAccountsService = Depends(get_chart_of_accounts_service),
    db: Session = Depends(get_db),
) -> StandardResponse[AccountResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.coa.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.coa.manage")
    account = coa_service.activate_account(company_id=company_id, account_id=account_id)
    return StandardResponse(
        data=AccountResponse.model_validate(account),
        message="Account activated",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Chart of Accounts — Account Groups (Phase 2)
# ---------------------------------------------------------------------------


@router.get(
    "/account-groups",
    response_model=StandardResponse[list[AccountGroupRead]],
    summary="List account groups",
)
async def list_account_groups(
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    coa_service: ChartOfAccountsService = Depends(get_chart_of_accounts_service),
) -> StandardResponse[list[AccountGroupRead]]:
    groups = coa_service.list_account_groups(company_id=company_id)
    return StandardResponse(
        data=[AccountGroupRead.model_validate(g) for g in groups],
        message=f"Retrieved {len(groups)} account groups",
        meta=_meta(),
    )


@router.post(
    "/account-groups",
    response_model=StandardResponse[AccountGroupRead],
    status_code=status.HTTP_201_CREATED,
    summary="Create an account group",
)
async def create_account_group(
    company_id: UUID = Path(...),
    body: AccountGroupCreate = ...,
    user: CurrentUser = Depends(require_authenticated),
    coa_service: ChartOfAccountsService = Depends(get_chart_of_accounts_service),
    db: Session = Depends(get_db),
) -> StandardResponse[AccountGroupRead]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.coa.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.coa.manage")
    group = coa_service.create_account_group(
        company_id=company_id, created_by=user.user_id, **body.model_dump()
    )
    return StandardResponse(
        data=AccountGroupRead.model_validate(group),
        message="Account group created",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# System Accounts (Phase 2)
# ---------------------------------------------------------------------------


@router.get(
    "/system-accounts",
    response_model=StandardResponse[AccountingConfigurationRead],
    summary="Get current system account assignments",
)
async def get_system_accounts(
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    config_service: AccountingConfigurationService = Depends(
        get_accounting_configuration_service
    ),
) -> StandardResponse[AccountingConfigurationRead]:
    config = config_service.get_or_create(company_id=company_id)
    return StandardResponse(
        data=AccountingConfigurationRead.model_validate(config),
        message="System account configuration retrieved",
        meta=_meta(),
    )


@router.put(
    "/system-accounts",
    response_model=StandardResponse[AccountingConfigurationRead],
    summary="Designate a system account role",
)
async def set_system_account(
    company_id: UUID = Path(...),
    body: SystemAccountConfigRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    coa_service: ChartOfAccountsService = Depends(get_chart_of_accounts_service),
    config_service: AccountingConfigurationService = Depends(
        get_accounting_configuration_service
    ),
    db: Session = Depends(get_db),
) -> StandardResponse[AccountingConfigurationRead]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.coa.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.coa.manage")
    if body.role not in SYSTEM_ACCOUNT_TYPE_REQUIREMENTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown system account role: '{body.role}'",
        )
    try:
        coa_service.set_system_account(
            company_id=company_id, role=body.role, account_id=body.account_id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    config = config_service.get_or_create(company_id=company_id)
    return StandardResponse(
        data=AccountingConfigurationRead.model_validate(config),
        message=f"System account role '{body.role}' updated",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# COA Industry Templates (Phase 2)
# ---------------------------------------------------------------------------


@router.get(
    "/coa-templates",
    response_model=StandardResponse[list[COATemplateInfo]],
    summary="List available industry COA templates",
)
async def list_coa_templates(
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
) -> StandardResponse[list[COATemplateInfo]]:
    templates = [
        COATemplateInfo(key=t.key, label=t.label) for t in COA_TEMPLATES.values()
    ]
    return StandardResponse(
        data=templates,
        message=f"Retrieved {len(templates)} templates",
        meta=_meta(),
    )


@router.post(
    "/coa-templates/apply",
    response_model=StandardResponse[list[AccountResponse]],
    summary="Apply an industry COA template to this company",
)
async def apply_coa_template(
    company_id: UUID = Path(...),
    body: COATemplateApplyRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    coa_service: ChartOfAccountsService = Depends(get_chart_of_accounts_service),
    db: Session = Depends(get_db),
) -> StandardResponse[list[AccountResponse]]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.coa.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.coa.manage")
    try:
        accounts = coa_service.apply_template(
            company_id=company_id,
            template_key=body.template_key,
            created_by=user.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return StandardResponse(
        data=[AccountResponse.model_validate(a) for a in accounts],
        message=f"Template '{body.template_key}' applied: {len(accounts)} accounts created",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Fiscal Calendar (Phase 3)
# ---------------------------------------------------------------------------


@router.get(
    "/fiscal-years",
    response_model=StandardResponse[list[FiscalYearResponse]],
    summary="List fiscal years",
)
async def list_fiscal_years(
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    fiscal_service: FiscalCalendarService = Depends(get_fiscal_calendar_service),
) -> StandardResponse[list[FiscalYearResponse]]:
    years = fiscal_service.list_fiscal_years(company_id=company_id)
    return StandardResponse(
        data=[FiscalYearResponse.model_validate(y) for y in years],
        message=f"Retrieved {len(years)} fiscal years",
        meta=_meta(),
    )


@router.post(
    "/fiscal-years",
    response_model=StandardResponse[FiscalYearResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a fiscal year (auto-generates its monthly periods)",
)
async def create_fiscal_year(
    company_id: UUID = Path(...),
    body: FiscalYearCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    fiscal_service: FiscalCalendarService = Depends(get_fiscal_calendar_service),
    db: Session = Depends(get_db),
) -> StandardResponse[FiscalYearResponse]:
    # RBAC gap fixed during pre-Epic-9 hardening audit (2026-08-14): creating
    # the fiscal calendar is at least as foundational as locking one of its
    # periods (already gated) and had no permission check at all. Reuses
    # the same accounting.period.lock fiscal-calendar-administration code.
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.period.lock"
    ):
        raise ApprovalPermissionDeniedError("accounting.period.lock")
    try:
        year = fiscal_service.create_fiscal_year(
            company_id=company_id, created_by=user.user_id, **body.model_dump()
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    return StandardResponse(
        data=FiscalYearResponse.model_validate(year),
        message="Fiscal year created",
        meta=_meta(),
    )


@router.get(
    "/fiscal-years/{fiscal_year_id}",
    response_model=StandardResponse[FiscalYearResponse],
    summary="Get fiscal year detail",
)
async def get_fiscal_year(
    company_id: UUID = Path(...),
    fiscal_year_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    fiscal_service: FiscalCalendarService = Depends(get_fiscal_calendar_service),
) -> StandardResponse[FiscalYearResponse]:
    year = fiscal_service.get_fiscal_year(
        company_id=company_id, fiscal_year_id=fiscal_year_id
    )
    return StandardResponse(
        data=FiscalYearResponse.model_validate(year),
        message="Fiscal year retrieved",
        meta=_meta(),
    )


@router.put(
    "/fiscal-years/{fiscal_year_id}",
    response_model=StandardResponse[FiscalYearResponse],
    summary="Update a fiscal year (name / is_current only)",
)
async def update_fiscal_year(
    company_id: UUID = Path(...),
    fiscal_year_id: UUID = Path(...),
    body: FiscalYearUpdateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    fiscal_service: FiscalCalendarService = Depends(get_fiscal_calendar_service),
    db: Session = Depends(get_db),
) -> StandardResponse[FiscalYearResponse]:
    # RBAC gap fixed during pre-Epic-9 hardening audit (2026-08-14) — see
    # create_fiscal_year's comment above.
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.period.lock"
    ):
        raise ApprovalPermissionDeniedError("accounting.period.lock")
    year = fiscal_service.update_fiscal_year(
        company_id=company_id,
        fiscal_year_id=fiscal_year_id,
        **body.model_dump(exclude_unset=True),
    )
    return StandardResponse(
        data=FiscalYearResponse.model_validate(year),
        message="Fiscal year updated",
        meta=_meta(),
    )


@router.get(
    "/fiscal-years/{fiscal_year_id}/periods",
    response_model=StandardResponse[list[FiscalPeriodResponse]],
    summary="List periods for a fiscal year",
)
async def list_fiscal_periods(
    company_id: UUID = Path(...),
    fiscal_year_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    fiscal_service: FiscalCalendarService = Depends(get_fiscal_calendar_service),
) -> StandardResponse[list[FiscalPeriodResponse]]:
    periods = fiscal_service.list_periods(
        company_id=company_id, fiscal_year_id=fiscal_year_id
    )
    return StandardResponse(
        data=[FiscalPeriodResponse.model_validate(p) for p in periods],
        message=f"Retrieved {len(periods)} periods",
        meta=_meta(),
    )


@router.post(
    "/fiscal-years/{fiscal_year_id}/periods/{period_id}/lock",
    response_model=StandardResponse[FiscalPeriodResponse],
    summary="Lock a fiscal period",
)
async def lock_fiscal_period(
    company_id: UUID = Path(...),
    fiscal_year_id: UUID = Path(...),
    period_id: UUID = Path(...),
    body: PeriodLockRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    fiscal_service: FiscalCalendarService = Depends(get_fiscal_calendar_service),
    db: Session = Depends(get_db),
) -> StandardResponse[FiscalPeriodResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.period.lock"
    ):
        raise ApprovalPermissionDeniedError("accounting.period.lock")
    period = fiscal_service.lock_period(
        company_id=company_id,
        period_id=period_id,
        locked_by_user_id=user.user_id,
        lock_reason=body.lock_reason,
    )
    return StandardResponse(
        data=FiscalPeriodResponse.model_validate(period),
        message="Fiscal period locked",
        meta=_meta(),
    )


@router.post(
    "/fiscal-years/{fiscal_year_id}/periods/{period_id}/unlock",
    response_model=StandardResponse[FiscalPeriodResponse],
    summary="Unlock a fiscal period (Controller authority; reason mandatory)",
)
async def unlock_fiscal_period(
    company_id: UUID = Path(...),
    fiscal_year_id: UUID = Path(...),
    period_id: UUID = Path(...),
    body: PeriodUnlockRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    fiscal_service: FiscalCalendarService = Depends(get_fiscal_calendar_service),
    db: Session = Depends(get_db),
) -> StandardResponse[FiscalPeriodResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.period.lock"
    ):
        raise ApprovalPermissionDeniedError("accounting.period.lock")
    try:
        period = fiscal_service.unlock_period(
            company_id=company_id,
            period_id=period_id,
            unlocked_by_user_id=user.user_id,
            reason=body.reason,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    return StandardResponse(
        data=FiscalPeriodResponse.model_validate(period),
        message="Fiscal period unlocked",
        meta=_meta(),
    )


@router.get(
    "/fiscal-years/{fiscal_year_id}/opening-balances",
    response_model=StandardResponse[list[OpeningBalanceResponse]],
    summary="List opening balances for a fiscal year",
)
async def list_opening_balances(
    company_id: UUID = Path(...),
    fiscal_year_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    fiscal_service: FiscalCalendarService = Depends(get_fiscal_calendar_service),
) -> StandardResponse[list[OpeningBalanceResponse]]:
    balances = fiscal_service.list_opening_balances(
        company_id=company_id, fiscal_year_id=fiscal_year_id
    )
    return StandardResponse(
        data=[OpeningBalanceResponse.model_validate(b) for b in balances],
        message=f"Retrieved {len(balances)} opening balance lines",
        meta=_meta(),
    )


@router.post(
    "/fiscal-years/{fiscal_year_id}/opening-balances",
    response_model=StandardResponse[list[OpeningBalanceResponse]],
    status_code=status.HTTP_201_CREATED,
    summary="Set up opening balances for a fiscal year (must balance)",
)
async def setup_opening_balances(
    company_id: UUID = Path(...),
    fiscal_year_id: UUID = Path(...),
    body: OpeningBalanceImportRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    fiscal_service: FiscalCalendarService = Depends(get_fiscal_calendar_service),
    db: Session = Depends(get_db),
) -> StandardResponse[list[OpeningBalanceResponse]]:
    # RBAC gap fixed during pre-Epic-9 hardening audit (2026-08-14) — sets
    # the starting point for all financial reporting; see
    # create_fiscal_year's comment above.
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.period.lock"
    ):
        raise ApprovalPermissionDeniedError("accounting.period.lock")
    balances = fiscal_service.setup_opening_balances(
        company_id=company_id,
        fiscal_year_id=fiscal_year_id,
        lines=[line.model_dump() for line in body.lines],
        created_by=user.user_id,
    )
    return StandardResponse(
        data=[OpeningBalanceResponse.model_validate(b) for b in balances],
        message=f"Recorded {len(balances)} opening balance lines",
        meta=_meta(),
    )


@router.post(
    "/fiscal-years/{fiscal_year_id}/year-end-close",
    response_model=StandardResponse[FiscalYearResponse],
    summary="Execute the year-end close workflow",
)
async def year_end_close(
    company_id: UUID = Path(...),
    fiscal_year_id: UUID = Path(...),
    body: YearEndCloseRequest = YearEndCloseRequest(),
    user: CurrentUser = Depends(require_authenticated),
    fiscal_service: FiscalCalendarService = Depends(get_fiscal_calendar_service),
    db: Session = Depends(get_db),
) -> StandardResponse[FiscalYearResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.period.close"
    ):
        raise ApprovalPermissionDeniedError("accounting.period.close")
    year = fiscal_service.execute_year_end_close(
        company_id=company_id,
        fiscal_year_id=fiscal_year_id,
        closed_by_user_id=user.user_id,
    )
    return StandardResponse(
        data=FiscalYearResponse.model_validate(year),
        message="Year-end close completed",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# General Ledger — Journal Entries (Phase 4, CRITICAL)
# ---------------------------------------------------------------------------


def _to_detail_response(
    entry: object, posting_engine: PostingEngine
) -> JournalEntryDetailResponse:
    lines = posting_engine.get_lines(entry.id)  # type: ignore[attr-defined]
    base = JournalEntryResponse.model_validate(entry)
    return JournalEntryDetailResponse(
        **base.model_dump(),
        lines=[JournalLineResponse.model_validate(line) for line in lines],
    )


@router.get(
    "/journals",
    response_model=StandardResponse[list[JournalEntryResponse]],
    summary="List/search journal entries",
)
async def list_journals(
    company_id: UUID = Path(...),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    account_id: UUID | None = Query(None),
    fiscal_period_id: UUID | None = Query(None),
    posting_source: str | None = Query(None),
    reference: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    cost_center_id: UUID | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    user: CurrentUser = Depends(require_authenticated),
    journal_repo: JournalEntryRepository = Depends(get_journal_entry_repo),
    db: Session = Depends(get_db),
) -> StandardResponse[list[JournalEntryResponse]]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.gl.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.gl.view")
    filters = {
        "start_date": start_date,
        "end_date": end_date,
        "account_id": account_id,
        "fiscal_period_id": fiscal_period_id,
        "posting_source": posting_source,
        "reference": reference,
        "status": status_filter,
        "cost_center_id": cost_center_id,
    }
    entries, total = journal_repo.search(
        company_id=company_id, filters=filters, skip=skip, limit=limit
    )
    return StandardResponse(
        data=[JournalEntryResponse.model_validate(e) for e in entries],
        message=f"Retrieved {len(entries)} of {total} journal entries",
        meta=_meta(),
    )


@router.post(
    "/journals",
    response_model=StandardResponse[JournalEntryDetailResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a DRAFT journal entry",
)
async def create_journal(
    company_id: UUID = Path(...),
    body: PostingRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    posting_engine: PostingEngine = Depends(get_posting_engine),
    db: Session = Depends(get_db),
) -> StandardResponse[JournalEntryDetailResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.journal.create"
    ):
        raise ApprovalPermissionDeniedError("accounting.journal.create")
    entry = posting_engine.create_journal(
        company_id=company_id,
        journal_type=body.journal_type,
        posting_source=body.posting_source,
        posting_date=body.posting_date,
        lines=[line.model_dump() for line in body.lines],
        currency_code=body.currency_code,
        exchange_rate=body.exchange_rate,
        reference=body.reference,
        description=body.description,
        notes=body.notes,
        source_document_type=body.source_document_type,
        source_document_id=body.source_document_id,
        created_by=user.user_id,
    )
    return StandardResponse(
        data=_to_detail_response(entry, posting_engine),
        message="Journal entry created as DRAFT",
        meta=_meta(),
    )


@router.get(
    "/journals/{journal_id}",
    response_model=StandardResponse[JournalEntryDetailResponse],
    summary="Get journal entry detail (with lines)",
)
async def get_journal(
    company_id: UUID = Path(...),
    journal_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    posting_engine: PostingEngine = Depends(get_posting_engine),
    db: Session = Depends(get_db),
) -> StandardResponse[JournalEntryDetailResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.gl.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.gl.view")
    entry = posting_engine.get_journal(company_id=company_id, journal_id=journal_id)
    return StandardResponse(
        data=_to_detail_response(entry, posting_engine),
        message="Journal entry retrieved",
        meta=_meta(),
    )


@router.post(
    "/journals/{journal_id}/submit",
    response_model=StandardResponse[JournalEntryResponse],
    summary="Submit a DRAFT journal entry for approval",
)
async def submit_journal(
    company_id: UUID = Path(...),
    journal_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    posting_engine: PostingEngine = Depends(get_posting_engine),
) -> StandardResponse[JournalEntryResponse]:
    entry = posting_engine.submit(
        company_id=company_id, journal_id=journal_id, actor_id=user.user_id
    )
    return StandardResponse(
        data=JournalEntryResponse.model_validate(entry),
        message="Journal entry submitted",
        meta=_meta(),
    )


@router.post(
    "/journals/{journal_id}/approve",
    response_model=StandardResponse[JournalEntryResponse],
    summary="Approve a SUBMITTED journal entry",
)
async def approve_journal(
    company_id: UUID = Path(...),
    journal_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    posting_engine: PostingEngine = Depends(get_posting_engine),
) -> StandardResponse[JournalEntryResponse]:
    entry = posting_engine.approve(
        company_id=company_id, journal_id=journal_id, approver_id=user.user_id
    )
    return StandardResponse(
        data=JournalEntryResponse.model_validate(entry),
        message="Journal entry approved",
        meta=_meta(),
    )


@router.post(
    "/journals/{journal_id}/reject",
    response_model=StandardResponse[JournalEntryResponse],
    summary="Reject a SUBMITTED journal entry",
)
async def reject_journal(
    company_id: UUID = Path(...),
    journal_id: UUID = Path(...),
    body: RejectRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    posting_engine: PostingEngine = Depends(get_posting_engine),
) -> StandardResponse[JournalEntryResponse]:
    entry = posting_engine.reject(
        company_id=company_id,
        journal_id=journal_id,
        actor_id=user.user_id,
        rejection_reason=body.rejection_reason,
    )
    return StandardResponse(
        data=JournalEntryResponse.model_validate(entry),
        message="Journal entry rejected",
        meta=_meta(),
    )


@router.post(
    "/journals/{journal_id}/post",
    response_model=StandardResponse[PostingResult],
    summary="Post a DRAFT/APPROVED journal entry to the GL",
)
async def post_journal(
    company_id: UUID = Path(...),
    journal_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    posting_engine: PostingEngine = Depends(get_posting_engine),
    db: Session = Depends(get_db),
) -> StandardResponse[PostingResult]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.journal.post"
    ):
        raise ApprovalPermissionDeniedError("accounting.journal.post")
    result = posting_engine.post(
        company_id=company_id, journal_id=journal_id, actor_id=user.user_id
    )
    return StandardResponse(
        data=PostingResult.model_validate(result, from_attributes=True),
        message=f"Journal entry posted as {result.journal_number}",
        meta=_meta(),
    )


@router.post(
    "/journals/{journal_id}/reverse",
    response_model=StandardResponse[JournalEntryDetailResponse],
    summary="Reverse a POSTED journal entry",
)
async def reverse_journal(
    company_id: UUID = Path(...),
    journal_id: UUID = Path(...),
    body: ReverseRequest = ReverseRequest(),
    user: CurrentUser = Depends(require_authenticated),
    posting_engine: PostingEngine = Depends(get_posting_engine),
    db: Session = Depends(get_db),
) -> StandardResponse[JournalEntryDetailResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.journal.reverse"
    ):
        raise ApprovalPermissionDeniedError("accounting.journal.reverse")
    reversal = posting_engine.reverse(
        company_id=company_id,
        journal_id=journal_id,
        actor_id=user.user_id,
        reason=body.reason,
    )
    return StandardResponse(
        data=_to_detail_response(reversal, posting_engine),
        message=f"Journal entry reversed by {reversal.journal_number}",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# General Ledger — Report (Phase 4; cursor pagination added Phase 13, T256)
# ---------------------------------------------------------------------------


@router.get(
    "/reports/gl",
    response_model=StandardResponse[list[GLReportRow]],
    summary="General Ledger detail report (filters; offset or keyset pagination)",
)
async def gl_report(
    company_id: UUID = Path(...),
    account_id: UUID | None = Query(None),
    cost_center_id: UUID | None = Query(None),
    fiscal_period_id: UUID | None = Query(None),
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    cursor_date: date | None = Query(
        None,
        description="Keyset cursor (Phase 13, T256): posting_date of the last row "
        "from the previous page. Provide all three cursor_* params together to switch "
        "from offset to keyset pagination — scales to 500K+ rows without OFFSET cost.",
    ),
    cursor_entry_id: UUID | None = Query(
        None, description="Keyset cursor: journal_entry_id of the last row"
    ),
    cursor_line_number: int | None = Query(
        None, description="Keyset cursor: line_number of the last row"
    ),
    user: CurrentUser = Depends(require_authenticated),
    gl_report_repo: GLReportRepository = Depends(get_gl_report_repo),
    db: Session = Depends(get_db),
) -> StandardResponse[list[GLReportRow]]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.gl.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.gl.view")
    if (
        cursor_date is not None
        and cursor_entry_id is not None
        and cursor_line_number is not None
    ):
        rows, has_more = gl_report_repo.gl_detail_cursor_query(
            company_id=company_id,
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            cost_center_id=cost_center_id,
            fiscal_period_id=fiscal_period_id,
            cursor=(cursor_date, cursor_entry_id, cursor_line_number),
            limit=limit,
        )
        message = f"Retrieved {len(rows)} GL lines" + (
            " (more available)" if has_more else ""
        )
    else:
        rows, total = gl_report_repo.gl_detail_query(
            company_id=company_id,
            account_id=account_id,
            start_date=start_date,
            end_date=end_date,
            cost_center_id=cost_center_id,
            fiscal_period_id=fiscal_period_id,
            skip=skip,
            limit=limit,
        )
        message = f"Retrieved {len(rows)} of {total} GL lines"

    return StandardResponse(
        data=[GLReportRow.model_validate(r) for r in rows],
        message=message,
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Audit Trail (Phase 14, T279)
# ---------------------------------------------------------------------------


@router.get(
    "/audit-log",
    response_model=StandardResponse[AuditLogListResponse],
    summary="Filterable, paginated financial audit trail",
)
async def get_audit_log(
    company_id: UUID = Path(...),
    entity_type: str | None = Query(None),
    entity_id: UUID | None = Query(None),
    actor_user_id: UUID | None = Query(None),
    action: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user: CurrentUser = Depends(require_authenticated),
    audit_repo: AccountingAuditLogRepository = Depends(get_audit_log_repo),
    db: Session = Depends(get_db),
) -> StandardResponse[AuditLogListResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.audit.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.audit.view")
    rows, total = audit_repo.list_filtered(
        company_id=company_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return StandardResponse(
        data=AuditLogListResponse(
            entries=[AuditLogEntryResponse.model_validate(r) for r in rows],
            total=total,
            skip=skip,
            limit=limit,
        ),
        message=f"Retrieved {len(rows)} of {total} audit log entries",
        meta=_meta(),
    )


@router.get(
    "/audit-log/export",
    summary="Export the audit trail as Excel or CSV",
)
async def export_audit_log(
    company_id: UUID = Path(...),
    entity_type: str | None = Query(None),
    entity_id: UUID | None = Query(None),
    actor_user_id: UUID | None = Query(None),
    action: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    export_format: str = Query("excel", pattern="^(excel|csv)$", alias="format"),
    user: CurrentUser = Depends(require_authenticated),
    audit_repo: AccountingAuditLogRepository = Depends(get_audit_log_repo),
    db: Session = Depends(get_db),
) -> Response:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.audit.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.audit.view")
    rows, _total = audit_repo.list_filtered(
        company_id=company_id,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        skip=0,
        limit=100_000,
    )
    if export_format == "excel":
        content = export_to_excel({"entries": rows}, template="audit_log")
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=audit-log.xlsx"},
        )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["Occurred At", "Entity Type", "Entity ID", "Action", "Actor User ID", "Reason"]
    )
    for r in rows:
        writer.writerow(
            [
                r.occurred_at,
                r.entity_type,
                r.entity_id,
                r.action,
                r.actor_user_id,
                r.reason,
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit-log.csv"},
    )


# ---------------------------------------------------------------------------
# Batch Posting (Phase 5, T122)
# ---------------------------------------------------------------------------


@router.post(
    "/journals/batch-post",
    response_model=StandardResponse[BatchPostingResponse],
    summary="Post multiple journal entries atomically — all or none",
)
async def batch_post_journals(
    company_id: UUID = Path(...),
    body: BatchPostingRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    journal_service: JournalEntryService = Depends(get_journal_entry_service),
    db: Session = Depends(get_db),
) -> StandardResponse[BatchPostingResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.journal.post"
    ):
        raise ApprovalPermissionDeniedError("accounting.journal.post")
    results = journal_service.batch_post(
        company_id=company_id,
        journal_ids=body.journal_entry_ids,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=BatchPostingResponse(
            results=[
                PostingResult.model_validate(r, from_attributes=True) for r in results
            ]
        ),
        message=f"Posted {len(results)} journal entries",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Recurring Journal Templates (Phase 5)
# ---------------------------------------------------------------------------


def _to_recurring_detail_response(
    template: object, service: RecurringJournalService, company_id: UUID
) -> RecurringTemplateDetailResponse:
    lines = service.list_template_lines(company_id, template.id)  # type: ignore[attr-defined]
    base = RecurringTemplateResponse.model_validate(template)
    return RecurringTemplateDetailResponse(
        **base.model_dump(),
        lines=[RecurringTemplateLineResponse.model_validate(line) for line in lines],
    )


@router.get(
    "/recurring-journals",
    response_model=StandardResponse[list[RecurringTemplateResponse]],
    summary="List recurring journal templates",
)
async def list_recurring_templates(
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: RecurringJournalService = Depends(get_recurring_journal_service),
) -> StandardResponse[list[RecurringTemplateResponse]]:
    templates = service.list_templates(company_id=company_id)
    return StandardResponse(
        data=[RecurringTemplateResponse.model_validate(t) for t in templates],
        message=f"Retrieved {len(templates)} recurring journal templates",
        meta=_meta(),
    )


@router.post(
    "/recurring-journals",
    response_model=StandardResponse[RecurringTemplateDetailResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a recurring journal template",
)
async def create_recurring_template(
    company_id: UUID = Path(...),
    body: RecurringTemplateCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: RecurringJournalService = Depends(get_recurring_journal_service),
) -> StandardResponse[RecurringTemplateDetailResponse]:
    template = service.create_template(
        company_id=company_id,
        template_name=body.template_name,
        frequency=body.frequency,
        start_date=body.start_date,
        lines=[line.model_dump() for line in body.lines],
        end_date=body.end_date,
        auto_post=body.auto_post,
        approval_required=body.approval_required,
        currency_code=body.currency_code,
        reference=body.reference,
        description=body.description,
        created_by=user.user_id,
    )
    return StandardResponse(
        data=_to_recurring_detail_response(template, service, company_id),
        message="Recurring journal template created",
        meta=_meta(),
    )


@router.get(
    "/recurring-journals/{template_id}",
    response_model=StandardResponse[RecurringTemplateDetailResponse],
    summary="Get recurring journal template detail (with lines)",
)
async def get_recurring_template(
    company_id: UUID = Path(...),
    template_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: RecurringJournalService = Depends(get_recurring_journal_service),
) -> StandardResponse[RecurringTemplateDetailResponse]:
    template = service.get_template(company_id=company_id, template_id=template_id)
    return StandardResponse(
        data=_to_recurring_detail_response(template, service, company_id),
        message="Recurring journal template retrieved",
        meta=_meta(),
    )


@router.put(
    "/recurring-journals/{template_id}",
    response_model=StandardResponse[RecurringTemplateResponse],
    summary="Update a recurring journal template",
)
async def update_recurring_template(
    company_id: UUID = Path(...),
    template_id: UUID = Path(...),
    body: RecurringTemplateUpdateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: RecurringJournalService = Depends(get_recurring_journal_service),
) -> StandardResponse[RecurringTemplateResponse]:
    template = service.update_template(
        company_id=company_id,
        template_id=template_id,
        **body.model_dump(exclude_unset=True),
    )
    return StandardResponse(
        data=RecurringTemplateResponse.model_validate(template),
        message="Recurring journal template updated",
        meta=_meta(),
    )


@router.post(
    "/recurring-journals/{template_id}/activate",
    response_model=StandardResponse[RecurringTemplateResponse],
    summary="Activate a recurring journal template",
)
async def activate_recurring_template(
    company_id: UUID = Path(...),
    template_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: RecurringJournalService = Depends(get_recurring_journal_service),
) -> StandardResponse[RecurringTemplateResponse]:
    template = service.activate_template(company_id=company_id, template_id=template_id)
    return StandardResponse(
        data=RecurringTemplateResponse.model_validate(template),
        message="Recurring journal template activated",
        meta=_meta(),
    )


@router.post(
    "/recurring-journals/{template_id}/deactivate",
    response_model=StandardResponse[RecurringTemplateResponse],
    summary="Deactivate a recurring journal template",
)
async def deactivate_recurring_template(
    company_id: UUID = Path(...),
    template_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: RecurringJournalService = Depends(get_recurring_journal_service),
) -> StandardResponse[RecurringTemplateResponse]:
    template = service.deactivate_template(
        company_id=company_id, template_id=template_id
    )
    return StandardResponse(
        data=RecurringTemplateResponse.model_validate(template),
        message="Recurring journal template deactivated",
        meta=_meta(),
    )


@router.get(
    "/recurring-journals/{template_id}/history",
    response_model=StandardResponse[list[RecurringInstanceResponse]],
    summary="Get recurring journal template execution history",
)
async def get_recurring_template_history(
    company_id: UUID = Path(...),
    template_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: RecurringJournalService = Depends(get_recurring_journal_service),
) -> StandardResponse[list[RecurringInstanceResponse]]:
    history = service.get_template_history(
        company_id=company_id, template_id=template_id
    )
    return StandardResponse(
        data=[RecurringInstanceResponse.model_validate(h) for h in history],
        message=f"Retrieved {len(history)} execution records",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Accounts Receivable (Phase 6, T145)
# ---------------------------------------------------------------------------


def _aging_row_to_schema(row: Any) -> ARAgingRow:
    return ARAgingRow(
        customer_ledger_id=row.customer_ledger_id,
        customer_id=row.customer_id,
        current=row.current,
        days_1_30=row.days_1_30,
        days_31_60=row.days_31_60,
        days_61_90=row.days_61_90,
        days_91_120=row.days_91_120,
        days_120_plus=row.days_120_plus,
        total=row.total,
    )


@router.get(
    "/ar/customer-ledger/{customer_id}",
    response_model=StandardResponse[CustomerLedgerResponse],
    summary="Get a customer's AR subsidiary ledger",
)
async def get_customer_ledger(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: AccountsReceivableService = Depends(get_ar_service),
) -> StandardResponse[CustomerLedgerResponse]:
    ledger = service.get_customer_ledger(company_id=company_id, customer_id=customer_id)
    return StandardResponse(
        data=CustomerLedgerResponse.model_validate(ledger),
        message="Customer ledger retrieved",
        meta=_meta(),
    )


@router.get(
    "/ar/aging",
    response_model=StandardResponse[ARAgingReport],
    summary="Get the AR aging report (all customers)",
)
async def get_ar_aging_report(
    company_id: UUID = Path(...),
    as_of_date: date = Query(default_factory=date.today),
    user: CurrentUser = Depends(require_authenticated),
    service: AccountsReceivableService = Depends(get_ar_service),
) -> StandardResponse[ARAgingReport]:
    report = service.get_aging_report(company_id=company_id, as_of_date=as_of_date)
    return StandardResponse(
        data=ARAgingReport(
            as_of_date=report.as_of_date,
            rows=[_aging_row_to_schema(r) for r in report.rows],
            totals=_aging_row_to_schema(report.totals),
        ),
        message=f"AR aging report generated for {len(report.rows)} customer(s)",
        meta=_meta(),
    )


@router.get(
    "/ar/customer-statement/{customer_id}",
    response_model=StandardResponse[CustomerStatementResponse],
    summary="Generate a customer statement for a date range",
)
async def get_customer_statement(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    user: CurrentUser = Depends(require_authenticated),
    service: AccountsReceivableService = Depends(get_ar_service),
) -> StandardResponse[CustomerStatementResponse]:
    statement = service.get_customer_statement(
        company_id=company_id,
        customer_id=customer_id,
        from_date=from_date,
        to_date=to_date,
    )
    return StandardResponse(
        data=CustomerStatementResponse.model_validate(statement),
        message="Customer statement generated",
        meta=_meta(),
    )


@router.post(
    "/ar/customers/{customer_id}/credit-hold",
    response_model=StandardResponse[CustomerLedgerResponse],
    summary="Place a customer on credit hold",
)
async def place_customer_credit_hold(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    body: CreditHoldRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: AccountsReceivableService = Depends(get_ar_service),
) -> StandardResponse[CustomerLedgerResponse]:
    ledger = service.place_credit_hold(
        company_id=company_id,
        customer_id=customer_id,
        reason=body.reason,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=CustomerLedgerResponse.model_validate(ledger),
        message="Customer placed on credit hold",
        meta=_meta(),
    )


@router.post(
    "/ar/customers/{customer_id}/credit-hold/release",
    response_model=StandardResponse[CustomerLedgerResponse],
    summary="Release a customer's credit hold",
)
async def release_customer_credit_hold(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    body: CreditHoldReleaseRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: AccountsReceivableService = Depends(get_ar_service),
    db: Session = Depends(get_db),
) -> StandardResponse[CustomerLedgerResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.creditlimit.override"
    ):
        raise ApprovalPermissionDeniedError("accounting.creditlimit.override")
    ledger = service.release_credit_hold(
        company_id=company_id,
        customer_id=customer_id,
        actor_id=user.user_id,
        reason=body.reason,
    )
    return StandardResponse(
        data=CustomerLedgerResponse.model_validate(ledger),
        message="Customer credit hold released",
        meta=_meta(),
    )


@router.post(
    "/ar/customers/{customer_id}/credit-limit",
    response_model=StandardResponse[CustomerLedgerResponse],
    summary="Set a customer's credit limit",
)
async def set_customer_credit_limit(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    body: CreditLimitRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: AccountsReceivableService = Depends(get_ar_service),
    db: Session = Depends(get_db),
) -> StandardResponse[CustomerLedgerResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.creditlimit.override"
    ):
        raise ApprovalPermissionDeniedError("accounting.creditlimit.override")
    ledger = service.set_credit_limit(
        company_id=company_id,
        customer_id=customer_id,
        credit_limit=body.credit_limit,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=CustomerLedgerResponse.model_validate(ledger),
        message="Customer credit limit updated",
        meta=_meta(),
    )


@router.post(
    "/ar/transactions/{ar_transaction_id}/write-off",
    response_model=StandardResponse[ARTransactionResponse],
    summary="Write off an AR transaction's outstanding balance",
)
async def write_off_ar_transaction(
    company_id: UUID = Path(...),
    ar_transaction_id: UUID = Path(...),
    body: WriteOffRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: AccountsReceivableService = Depends(get_ar_service),
    db: Session = Depends(get_db),
) -> StandardResponse[ARTransactionResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.ar.writeoff"
    ):
        raise ApprovalPermissionDeniedError("accounting.ar.writeoff")
    transaction = service.confirm_write_off(
        company_id=company_id,
        ar_transaction_id=ar_transaction_id,
        reason=body.reason,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=ARTransactionResponse.model_validate(transaction),
        message="AR transaction written off",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Accounts Payable (Phase 7, T168)
# ---------------------------------------------------------------------------


def _ap_aging_row_to_schema(row: Any) -> APAgingRow:
    return APAgingRow(
        supplier_ledger_id=row.supplier_ledger_id,
        supplier_id=row.supplier_id,
        current=row.current,
        days_1_30=row.days_1_30,
        days_31_60=row.days_31_60,
        days_61_90=row.days_61_90,
        days_91_120=row.days_91_120,
        days_120_plus=row.days_120_plus,
        total=row.total,
    )


@router.get(
    "/ap/supplier-ledger/{supplier_id}",
    response_model=StandardResponse[SupplierLedgerResponse],
    summary="Get a supplier's AP subsidiary ledger",
)
async def get_supplier_ledger(
    company_id: UUID = Path(...),
    supplier_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: AccountsPayableService = Depends(get_ap_service),
) -> StandardResponse[SupplierLedgerResponse]:
    ledger = service.get_supplier_ledger(company_id=company_id, supplier_id=supplier_id)
    return StandardResponse(
        data=SupplierLedgerResponse.model_validate(ledger),
        message="Supplier ledger retrieved",
        meta=_meta(),
    )


@router.get(
    "/ap/aging",
    response_model=StandardResponse[APAgingReport],
    summary="Get the AP aging report (all suppliers)",
)
async def get_ap_aging_report(
    company_id: UUID = Path(...),
    as_of_date: date = Query(default_factory=date.today),
    user: CurrentUser = Depends(require_authenticated),
    service: AccountsPayableService = Depends(get_ap_service),
) -> StandardResponse[APAgingReport]:
    report = service.get_aging_report(company_id=company_id, as_of_date=as_of_date)
    return StandardResponse(
        data=APAgingReport(
            as_of_date=report.as_of_date,
            rows=[_ap_aging_row_to_schema(r) for r in report.rows],
            totals=_ap_aging_row_to_schema(report.totals),
        ),
        message=f"AP aging report generated for {len(report.rows)} supplier(s)",
        meta=_meta(),
    )


@router.get(
    "/ap/supplier-statement/{supplier_id}",
    response_model=StandardResponse[SupplierStatementResponse],
    summary="Generate a supplier statement for a date range",
)
async def get_supplier_statement(
    company_id: UUID = Path(...),
    supplier_id: UUID = Path(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    user: CurrentUser = Depends(require_authenticated),
    service: AccountsPayableService = Depends(get_ap_service),
) -> StandardResponse[SupplierStatementResponse]:
    statement = service.get_supplier_statement(
        company_id=company_id,
        supplier_id=supplier_id,
        from_date=from_date,
        to_date=to_date,
    )
    return StandardResponse(
        data=SupplierStatementResponse.model_validate(statement),
        message="Supplier statement generated",
        meta=_meta(),
    )


@router.post(
    "/ap/reconcile-statement",
    response_model=StandardResponse[SupplierStatementReconciliationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Reconcile a supplier statement against the AP ledger",
)
async def reconcile_supplier_statement(
    company_id: UUID = Path(...),
    body: ReconcileStatementRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: AccountsPayableService = Depends(get_ap_service),
) -> StandardResponse[SupplierStatementReconciliationResponse]:
    reconciliation = service.reconcile_supplier_statement(
        company_id=company_id,
        supplier_id=body.supplier_id,
        statement_date=body.statement_date,
        statement_total=body.statement_total,
        statement_lines=[line.model_dump() for line in body.statement_lines],
        actor_id=user.user_id,
    )
    items = service.get_reconciliation_items(
        company_id=company_id, reconciliation_id=reconciliation.id
    )
    response = SupplierStatementReconciliationResponse.model_validate(reconciliation)
    response.items = [ReconciliationItemResponse.model_validate(item) for item in items]
    return StandardResponse(
        data=response,
        message="Supplier statement reconciled",
        meta=_meta(),
    )


@router.get(
    "/ap/payments/{payment_id}/remittance-advice",
    response_model=StandardResponse[RemittanceAdviceResponse],
    summary="Generate remittance advice for a supplier payment",
)
async def get_remittance_advice(
    company_id: UUID = Path(...),
    payment_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: AccountsPayableService = Depends(get_ap_service),
) -> StandardResponse[RemittanceAdviceResponse]:
    advice = service.generate_remittance_advice(
        company_id=company_id, payment_id=payment_id
    )
    return StandardResponse(
        data=RemittanceAdviceResponse.model_validate(advice),
        message="Remittance advice generated",
        meta=_meta(),
    )


@router.post(
    "/ap/bills",
    response_model=StandardResponse[APTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a supplier bill (manual entry — no live Purchase event exists, T163)",
)
async def create_supplier_bill(
    company_id: UUID = Path(...),
    body: BillCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: AccountsPayableService = Depends(get_ap_service),
) -> StandardResponse[APTransactionResponse]:
    transaction, _ = service.record_supplier_bill(
        company_id=company_id,
        supplier_id=body.supplier_id,
        bill_id=uuid4(),
        bill_number=body.bill_number,
        total_amount=body.total_amount,
        currency_code=body.currency_code,
        transaction_date=body.transaction_date,
        due_date=body.due_date,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=APTransactionResponse.model_validate(transaction),
        message="Supplier bill recorded",
        meta=_meta(),
    )


@router.post(
    "/ap/credit-notes",
    response_model=StandardResponse[APTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a supplier credit note against a bill (manual entry, T164)",
)
async def create_supplier_credit_note(
    company_id: UUID = Path(...),
    body: CreditNoteCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: AccountsPayableService = Depends(get_ap_service),
) -> StandardResponse[APTransactionResponse]:
    transaction, _ = service.record_supplier_credit_note(
        company_id=company_id,
        supplier_id=body.supplier_id,
        bill_id=body.bill_id,
        bill_number=body.bill_number,
        credit_amount=body.credit_amount,
        transaction_date=body.transaction_date,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=APTransactionResponse.model_validate(transaction),
        message="Supplier credit note recorded",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Banking (Phase 8, T185)
# ---------------------------------------------------------------------------


@router.get(
    "/bank-accounts",
    response_model=StandardResponse[list[BankAccountResponse]],
    summary="List bank accounts",
)
async def list_bank_accounts(
    company_id: UUID = Path(...),
    active_only: bool = Query(False),
    user: CurrentUser = Depends(require_authenticated),
    service: BankAccountService = Depends(get_bank_account_service),
) -> StandardResponse[list[BankAccountResponse]]:
    accounts = service.list_bank_accounts(
        company_id=company_id, active_only=active_only
    )
    return StandardResponse(
        data=[BankAccountResponse.model_validate(a) for a in accounts],
        message=f"Retrieved {len(accounts)} bank account(s)",
        meta=_meta(),
    )


@router.post(
    "/bank-accounts",
    response_model=StandardResponse[BankAccountResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a bank account",
)
async def create_bank_account(
    company_id: UUID = Path(...),
    body: BankAccountCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: BankAccountService = Depends(get_bank_account_service),
    db: Session = Depends(get_db),
) -> StandardResponse[BankAccountResponse]:
    # RBAC gap fixed during pre-Epic-9 hardening audit (2026-08-14): every
    # reconciliation action on a bank account requires
    # accounting.bank.reconcile; creating/mutating the account itself and
    # moving real money via transfer/deposit below had no check at all.
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.bank.reconcile"
    ):
        raise ApprovalPermissionDeniedError("accounting.bank.reconcile")
    account = service.create_bank_account(
        company_id=company_id,
        bank_name=body.bank_name,
        account_number=body.account_number,
        currency_code=body.currency_code,
        gl_account_id=body.gl_account_id,
        branch_name=body.branch_name,
        iban=body.iban,
        swift_bic=body.swift_bic,
        opening_balance=body.opening_balance,
        opening_balance_date=body.opening_balance_date,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=BankAccountResponse.model_validate(account),
        message="Bank account created",
        meta=_meta(),
    )


@router.get(
    "/bank-accounts/{bank_account_id}",
    response_model=StandardResponse[BankAccountResponse],
    summary="Get a bank account",
)
async def get_bank_account(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: BankAccountService = Depends(get_bank_account_service),
) -> StandardResponse[BankAccountResponse]:
    account = service.get_bank_account(
        company_id=company_id, bank_account_id=bank_account_id
    )
    return StandardResponse(
        data=BankAccountResponse.model_validate(account),
        message="Bank account retrieved",
        meta=_meta(),
    )


@router.put(
    "/bank-accounts/{bank_account_id}",
    response_model=StandardResponse[BankAccountResponse],
    summary="Update a bank account",
)
async def update_bank_account(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    body: BankAccountUpdateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: BankAccountService = Depends(get_bank_account_service),
    db: Session = Depends(get_db),
) -> StandardResponse[BankAccountResponse]:
    # RBAC gap fixed during pre-Epic-9 hardening audit (2026-08-14) — see
    # create_bank_account's comment above.
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.bank.reconcile"
    ):
        raise ApprovalPermissionDeniedError("accounting.bank.reconcile")
    account = service.update_bank_account(
        company_id=company_id,
        bank_account_id=bank_account_id,
        **body.model_dump(exclude_unset=True),
    )
    return StandardResponse(
        data=BankAccountResponse.model_validate(account),
        message="Bank account updated",
        meta=_meta(),
    )


@router.get(
    "/bank-accounts/{bank_account_id}/bank-book",
    response_model=StandardResponse[BankBookResponse],
    summary="Get a bank account's bank book for a date range",
)
async def get_bank_book(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    user: CurrentUser = Depends(require_authenticated),
    service: BankAccountService = Depends(get_bank_account_service),
) -> StandardResponse[BankBookResponse]:
    book = service.get_bank_book(
        company_id=company_id,
        bank_account_id=bank_account_id,
        from_date=from_date,
        to_date=to_date,
    )
    return StandardResponse(
        data=BankBookResponse.model_validate(book),
        message="Bank book retrieved",
        meta=_meta(),
    )


@router.post(
    "/bank-accounts/{bank_account_id}/transfer",
    response_model=StandardResponse[BankTransferResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Transfer funds between two bank accounts",
)
async def transfer_between_bank_accounts(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    body: BankTransferRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: BankAccountService = Depends(get_bank_account_service),
    db: Session = Depends(get_db),
) -> StandardResponse[BankTransferResponse]:
    # RBAC gap fixed during pre-Epic-9 hardening audit (2026-08-14) — see
    # create_bank_account's comment above.
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.bank.reconcile"
    ):
        raise ApprovalPermissionDeniedError("accounting.bank.reconcile")
    from_txn, to_txn, result = service.record_bank_transfer(
        company_id=company_id,
        from_bank_account_id=bank_account_id,
        to_bank_account_id=body.to_bank_account_id,
        amount=body.amount,
        transfer_date=body.transfer_date,
        reference=body.reference,
        description=body.description,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=BankTransferResponse(
            from_transaction=BankTransactionResponse.model_validate(from_txn),
            to_transaction=BankTransactionResponse.model_validate(to_txn),
            journal_entry_id=result.journal_entry_id,
        ),
        message="Bank transfer recorded",
        meta=_meta(),
    )


@router.post(
    "/bank-accounts/{bank_account_id}/deposit",
    response_model=StandardResponse[BankTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a batched bank deposit",
)
async def deposit_to_bank_account(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    body: BankDepositRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: BankAccountService = Depends(get_bank_account_service),
    db: Session = Depends(get_db),
) -> StandardResponse[BankTransactionResponse]:
    # RBAC gap fixed during pre-Epic-9 hardening audit (2026-08-14) — see
    # create_bank_account's comment above.
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.bank.reconcile"
    ):
        raise ApprovalPermissionDeniedError("accounting.bank.reconcile")
    transaction, _ = service.record_bank_deposit(
        company_id=company_id,
        bank_account_id=bank_account_id,
        total_amount=body.total_amount,
        contra_account_id=body.contra_account_id,
        deposit_date=body.deposit_date,
        reference=body.reference,
        description=body.description,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=BankTransactionResponse.model_validate(transaction),
        message="Bank deposit recorded",
        meta=_meta(),
    )


@router.post(
    "/bank-accounts/{bank_account_id}/reconciliations",
    response_model=StandardResponse[BankReconciliationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Start a bank reconciliation session",
)
async def start_bank_reconciliation(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    body: ReconciliationStartRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: BankReconciliationService = Depends(get_bank_reconciliation_service),
    db: Session = Depends(get_db),
) -> StandardResponse[BankReconciliationResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.bank.reconcile"
    ):
        raise ApprovalPermissionDeniedError("accounting.bank.reconcile")
    reconciliation = service.start_reconciliation(
        company_id=company_id,
        bank_account_id=bank_account_id,
        statement_date=body.statement_date,
        statement_closing_balance=body.statement_closing_balance,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=BankReconciliationResponse.model_validate(reconciliation),
        message="Bank reconciliation started",
        meta=_meta(),
    )


@router.get(
    "/bank-accounts/{bank_account_id}/reconciliations/{reconciliation_id}",
    response_model=StandardResponse[ReconciliationReportResponse],
    summary="Get a bank reconciliation session's report (matched/unmatched items)",
)
async def get_bank_reconciliation_report(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    reconciliation_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: BankReconciliationService = Depends(get_bank_reconciliation_service),
) -> StandardResponse[ReconciliationReportResponse]:
    report = service.get_reconciliation_report(
        company_id=company_id, reconciliation_id=reconciliation_id
    )
    return StandardResponse(
        data=ReconciliationReportResponse.model_validate(report),
        message="Bank reconciliation report retrieved",
        meta=_meta(),
    )


@router.post(
    "/bank-accounts/{bank_account_id}/reconciliations/{reconciliation_id}/import-statement",
    response_model=StandardResponse[list[BankStatementLineResponse]],
    status_code=status.HTTP_201_CREATED,
    summary="Import bank statement lines for reconciliation",
)
async def import_bank_statement(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    reconciliation_id: UUID = Path(...),
    body: BankStatementImportRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: BankReconciliationService = Depends(get_bank_reconciliation_service),
) -> StandardResponse[list[BankStatementLineResponse]]:
    _ = reconciliation_id  # lines are scoped to the bank account, not the session, per T177
    lines = service.import_statement_lines(
        company_id=company_id,
        bank_account_id=bank_account_id,
        lines=[line.model_dump() for line in body.lines],
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=[BankStatementLineResponse.model_validate(line) for line in lines],
        message=f"Imported {len(lines)} statement line(s)",
        meta=_meta(),
    )


@router.post(
    "/bank-accounts/{bank_account_id}/reconciliations/{reconciliation_id}/auto-match",
    response_model=StandardResponse[AutoMatchResultResponse],
    summary="Run auto-match for a bank reconciliation session",
)
async def auto_match_bank_reconciliation(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    reconciliation_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: BankReconciliationService = Depends(get_bank_reconciliation_service),
    db: Session = Depends(get_db),
) -> StandardResponse[AutoMatchResultResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.bank.reconcile"
    ):
        raise ApprovalPermissionDeniedError("accounting.bank.reconcile")
    _ = bank_account_id
    result = service.run_auto_match(
        company_id=company_id,
        reconciliation_id=reconciliation_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=AutoMatchResultResponse(**result),
        message=f"Auto-match matched {result['matched_count']} item(s)",
        meta=_meta(),
    )


@router.post(
    "/bank-accounts/{bank_account_id}/reconciliations/{reconciliation_id}/manual-match",
    response_model=StandardResponse[dict[str, UUID]],
    status_code=status.HTTP_201_CREATED,
    summary="Manually match a bank transaction to a statement line",
)
async def manual_match_bank_reconciliation(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    reconciliation_id: UUID = Path(...),
    body: ReconciliationMatchRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: BankReconciliationService = Depends(get_bank_reconciliation_service),
    db: Session = Depends(get_db),
) -> StandardResponse[dict[str, UUID]]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.bank.reconcile"
    ):
        raise ApprovalPermissionDeniedError("accounting.bank.reconcile")
    _ = bank_account_id
    match = service.manual_match(
        company_id=company_id,
        reconciliation_id=reconciliation_id,
        bank_transaction_id=body.bank_transaction_id,
        statement_line_id=body.statement_line_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data={"match_id": match.id},
        message="Manual match recorded",
        meta=_meta(),
    )


@router.post(
    "/bank-accounts/{bank_account_id}/reconciliations/{reconciliation_id}/unmatch/{match_id}",
    response_model=StandardResponse[dict[str, str]],
    summary="Undo a bank reconciliation match",
)
async def unmatch_bank_reconciliation(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    reconciliation_id: UUID = Path(...),
    match_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: BankReconciliationService = Depends(get_bank_reconciliation_service),
    db: Session = Depends(get_db),
) -> StandardResponse[dict[str, str]]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.bank.reconcile"
    ):
        raise ApprovalPermissionDeniedError("accounting.bank.reconcile")
    _ = bank_account_id
    service.unmatch(
        company_id=company_id,
        reconciliation_id=reconciliation_id,
        match_id=match_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data={"status": "unmatched"},
        message="Match removed",
        meta=_meta(),
    )


@router.post(
    "/bank-accounts/{bank_account_id}/reconciliations/{reconciliation_id}/bank-charge",
    response_model=StandardResponse[BankTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Post a bank charge found on the statement",
)
async def post_bank_charge(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    reconciliation_id: UUID = Path(...),
    body: BankChargeRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: BankReconciliationService = Depends(get_bank_reconciliation_service),
    db: Session = Depends(get_db),
) -> StandardResponse[BankTransactionResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.bank.reconcile"
    ):
        raise ApprovalPermissionDeniedError("accounting.bank.reconcile")
    _ = reconciliation_id
    transaction, _result = service.post_bank_charge(
        company_id=company_id,
        bank_account_id=bank_account_id,
        amount=body.amount,
        expense_account_id=body.expense_account_id,
        charge_date=body.charge_date,
        description=body.description,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=BankTransactionResponse.model_validate(transaction),
        message="Bank charge posted",
        meta=_meta(),
    )


@router.post(
    "/bank-accounts/{bank_account_id}/reconciliations/{reconciliation_id}/complete",
    response_model=StandardResponse[BankReconciliationResponse],
    summary="Complete a bank reconciliation (requires zero difference)",
)
async def complete_bank_reconciliation(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    reconciliation_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: BankReconciliationService = Depends(get_bank_reconciliation_service),
    db: Session = Depends(get_db),
) -> StandardResponse[BankReconciliationResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.bank.reconcile"
    ):
        raise ApprovalPermissionDeniedError("accounting.bank.reconcile")
    _ = bank_account_id
    reconciliation = service.complete_reconciliation(
        company_id=company_id,
        reconciliation_id=reconciliation_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=BankReconciliationResponse.model_validate(reconciliation),
        message="Bank reconciliation completed",
        meta=_meta(),
    )


@router.post(
    "/bank-accounts/{bank_account_id}/reconciliations/{reconciliation_id}/lock",
    response_model=StandardResponse[BankReconciliationResponse],
    summary="Lock a completed bank reconciliation",
)
async def lock_bank_reconciliation(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    reconciliation_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: BankReconciliationService = Depends(get_bank_reconciliation_service),
    db: Session = Depends(get_db),
) -> StandardResponse[BankReconciliationResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.bank.reconcile"
    ):
        raise ApprovalPermissionDeniedError("accounting.bank.reconcile")
    _ = bank_account_id
    reconciliation = service.lock_reconciliation(
        company_id=company_id,
        reconciliation_id=reconciliation_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=BankReconciliationResponse.model_validate(reconciliation),
        message="Bank reconciliation locked",
        meta=_meta(),
    )


@router.get(
    "/cheques",
    response_model=StandardResponse[list[ChequeResponse]],
    summary="List cheques (optionally filtered by status)",
)
async def list_cheques(
    company_id: UUID = Path(...),
    status_filter: str | None = Query(None, alias="status"),
    user: CurrentUser = Depends(require_authenticated),
    service: BankAccountService = Depends(get_bank_account_service),
) -> StandardResponse[list[ChequeResponse]]:
    cheques = service.list_cheques(company_id=company_id, status=status_filter)
    return StandardResponse(
        data=[ChequeResponse.model_validate(c) for c in cheques],
        message=f"Retrieved {len(cheques)} cheque(s)",
        meta=_meta(),
    )


@router.post(
    "/cheques",
    response_model=StandardResponse[ChequeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Issue a new cheque",
)
async def create_cheque(
    company_id: UUID = Path(...),
    body: ChequeCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: BankAccountService = Depends(get_bank_account_service),
) -> StandardResponse[ChequeResponse]:
    cheque = service.issue_cheque(
        company_id=company_id,
        bank_account_id=body.bank_account_id,
        cheque_number=body.cheque_number,
        payee_name=body.payee_name,
        cheque_date=body.cheque_date,
        amount=body.amount,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=ChequeResponse.model_validate(cheque),
        message="Cheque issued",
        meta=_meta(),
    )


@router.post(
    "/cheques/{cheque_id}/status",
    response_model=StandardResponse[ChequeResponse],
    summary="Update a cheque's status",
)
async def update_cheque_status(
    company_id: UUID = Path(...),
    cheque_id: UUID = Path(...),
    body: ChequeStatusUpdateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: BankAccountService = Depends(get_bank_account_service),
) -> StandardResponse[ChequeResponse]:
    cheque = service.update_cheque_status(
        company_id=company_id,
        cheque_id=cheque_id,
        new_status=body.status,
        cancel_reason=body.cancel_reason,
        bank_statement_line_id=body.bank_statement_line_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=ChequeResponse.model_validate(cheque),
        message="Cheque status updated",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Cash Management (Phase 9, T198)
# ---------------------------------------------------------------------------


@router.get(
    "/cash-accounts",
    response_model=StandardResponse[list[CashAccountResponse]],
    summary="List cash accounts",
)
async def list_cash_accounts(
    company_id: UUID = Path(...),
    active_only: bool = Query(False),
    user: CurrentUser = Depends(require_authenticated),
    service: CashAccountService = Depends(get_cash_account_service),
) -> StandardResponse[list[CashAccountResponse]]:
    accounts = service.list_cash_accounts(
        company_id=company_id, active_only=active_only
    )
    return StandardResponse(
        data=[CashAccountResponse.model_validate(a) for a in accounts],
        message=f"Retrieved {len(accounts)} cash account(s)",
        meta=_meta(),
    )


@router.post(
    "/cash-accounts",
    response_model=StandardResponse[CashAccountResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a cash account",
)
async def create_cash_account(
    company_id: UUID = Path(...),
    body: CashAccountCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: CashAccountService = Depends(get_cash_account_service),
) -> StandardResponse[CashAccountResponse]:
    account = service.create_cash_account(
        company_id=company_id,
        account_name=body.account_name,
        currency_code=body.currency_code,
        gl_account_id=body.gl_account_id,
        is_petty_cash=body.is_petty_cash,
        float_amount=body.float_amount,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=CashAccountResponse.model_validate(account),
        message="Cash account created",
        meta=_meta(),
    )


@router.post(
    "/cash-accounts/{cash_account_id}/receipts",
    response_model=StandardResponse[CashTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a cash receipt",
)
async def record_cash_receipt(
    company_id: UUID = Path(...),
    cash_account_id: UUID = Path(...),
    body: CashReceiptRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: CashAccountService = Depends(get_cash_account_service),
) -> StandardResponse[CashTransactionResponse]:
    transaction, _result = service.record_cash_receipt(
        company_id=company_id,
        cash_account_id=cash_account_id,
        amount=body.amount,
        contra_account_id=body.contra_account_id,
        receipt_date=body.receipt_date,
        reference=body.reference,
        description=body.description,
        counterparty_type=body.counterparty_type,
        counterparty_id=body.counterparty_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=CashTransactionResponse.model_validate(transaction),
        message="Cash receipt recorded",
        meta=_meta(),
    )


@router.post(
    "/cash-accounts/{cash_account_id}/payments",
    response_model=StandardResponse[CashTransactionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a cash payment",
)
async def record_cash_payment(
    company_id: UUID = Path(...),
    cash_account_id: UUID = Path(...),
    body: CashPaymentRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: CashAccountService = Depends(get_cash_account_service),
) -> StandardResponse[CashTransactionResponse]:
    transaction, _result = service.record_cash_payment(
        company_id=company_id,
        cash_account_id=cash_account_id,
        amount=body.amount,
        contra_account_id=body.contra_account_id,
        payment_date=body.payment_date,
        reference=body.reference,
        description=body.description,
        counterparty_type=body.counterparty_type,
        counterparty_id=body.counterparty_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=CashTransactionResponse.model_validate(transaction),
        message="Cash payment recorded",
        meta=_meta(),
    )


@router.get(
    "/cash-accounts/{cash_account_id}/petty-cash-vouchers",
    response_model=StandardResponse[list[PettyCashVoucherResponse]],
    summary="List petty cash vouchers for a cash account",
)
async def list_petty_cash_vouchers(
    company_id: UUID = Path(...),
    cash_account_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CashAccountService = Depends(get_cash_account_service),
) -> StandardResponse[list[PettyCashVoucherResponse]]:
    vouchers = service.list_petty_cash_vouchers(
        company_id=company_id, cash_account_id=cash_account_id
    )
    return StandardResponse(
        data=[PettyCashVoucherResponse.model_validate(v) for v in vouchers],
        message=f"Retrieved {len(vouchers)} petty cash voucher(s)",
        meta=_meta(),
    )


@router.post(
    "/cash-accounts/{cash_account_id}/petty-cash-vouchers",
    response_model=StandardResponse[PettyCashVoucherResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a petty cash voucher",
)
async def create_petty_cash_voucher(
    company_id: UUID = Path(...),
    cash_account_id: UUID = Path(...),
    body: PettyCashVoucherRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: CashAccountService = Depends(get_cash_account_service),
) -> StandardResponse[PettyCashVoucherResponse]:
    voucher = service.create_petty_cash_voucher(
        company_id=company_id,
        cash_account_id=cash_account_id,
        voucher_date=body.voucher_date,
        amount=body.amount,
        expense_account_id=body.expense_account_id,
        recipient_name=body.recipient_name,
        purpose=body.purpose,
        voucher_number=body.voucher_number,
        approved_by_user_id=body.approved_by_user_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=PettyCashVoucherResponse.model_validate(voucher),
        message="Petty cash voucher created",
        meta=_meta(),
    )


@router.post(
    "/cash-accounts/{cash_account_id}/replenish",
    response_model=StandardResponse[PettyCashReplenishmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Replenish petty cash from a set of vouchers",
)
async def replenish_petty_cash(
    company_id: UUID = Path(...),
    cash_account_id: UUID = Path(...),
    body: PettyCashReplenishmentRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: CashAccountService = Depends(get_cash_account_service),
) -> StandardResponse[PettyCashReplenishmentResponse]:
    transaction, vouchers, result = service.replenish_petty_cash(
        company_id=company_id,
        cash_account_id=cash_account_id,
        voucher_ids=body.voucher_ids,
        bank_gl_account_id=body.bank_gl_account_id,
        replenishment_date=body.replenishment_date,
        reference=body.reference,
        description=body.description,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=PettyCashReplenishmentResponse(
            cash_transaction=CashTransactionResponse.model_validate(transaction),
            vouchers=[PettyCashVoucherResponse.model_validate(v) for v in vouchers],
            journal_entry_id=result.journal_entry_id,
        ),
        message="Petty cash replenished",
        meta=_meta(),
    )


@router.post(
    "/cash-accounts/{cash_account_id}/reconcile",
    response_model=StandardResponse[CashReconciliationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Reconcile physical cash count against the GL balance",
)
async def reconcile_cash(
    company_id: UUID = Path(...),
    cash_account_id: UUID = Path(...),
    body: CashReconciliationRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: CashAccountService = Depends(get_cash_account_service),
) -> StandardResponse[CashReconciliationResponse]:
    reconciliation = service.reconcile_cash(
        company_id=company_id,
        cash_account_id=cash_account_id,
        reconciliation_date=body.reconciliation_date,
        physical_count_amount=body.physical_count_amount,
        difference_account_id=body.difference_account_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=CashReconciliationResponse.model_validate(reconciliation),
        message="Cash reconciliation completed",
        meta=_meta(),
    )


@router.get(
    "/cash-accounts/{cash_account_id}/cash-book",
    response_model=StandardResponse[CashBookResponse],
    summary="Get a cash account's cash book for a date range",
)
async def get_cash_book(
    company_id: UUID = Path(...),
    cash_account_id: UUID = Path(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CashAccountService = Depends(get_cash_account_service),
) -> StandardResponse[CashBookResponse]:
    book = service.get_cash_book(
        company_id=company_id,
        cash_account_id=cash_account_id,
        from_date=from_date,
        to_date=to_date,
    )
    return StandardResponse(
        data=CashBookResponse.model_validate(book),
        message="Cash book retrieved",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Payment Processing (Phase 10, T215)
# ---------------------------------------------------------------------------


@router.get(
    "/payments/customer",
    response_model=StandardResponse[list[PaymentResponse]],
    summary="List a customer's payments",
)
async def list_customer_payments(
    company_id: UUID = Path(...),
    customer_id: UUID = Query(...),
    user: CurrentUser = Depends(require_authenticated),
    service: PaymentService = Depends(get_payment_service),
) -> StandardResponse[list[PaymentResponse]]:
    payments = service.list_customer_payments(
        company_id=company_id, customer_id=customer_id
    )
    return StandardResponse(
        data=[PaymentResponse.model_validate(p) for p in payments],
        message=f"Retrieved {len(payments)} customer payment(s)",
        meta=_meta(),
    )


@router.post(
    "/payments/customer",
    response_model=StandardResponse[PaymentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a customer payment receipt",
)
async def create_customer_payment(
    company_id: UUID = Path(...),
    body: CustomerPaymentRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: PaymentService = Depends(get_payment_service),
    db: Session = Depends(get_db),
) -> StandardResponse[PaymentResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.payment.customer.create"
    ):
        raise ApprovalPermissionDeniedError("accounting.payment.customer.create")
    payment, _result = service.create_customer_payment(
        company_id=company_id,
        customer_id=body.customer_id,
        payment_method=body.payment_method,
        payment_date=body.payment_date,
        amount=body.amount,
        currency_code=body.currency_code,
        exchange_rate=body.exchange_rate,
        payment_type=body.payment_type,
        bank_account_id=body.bank_account_id,
        cash_account_id=body.cash_account_id,
        advance_account_id=body.advance_account_id,
        reference=body.reference,
        notes=body.notes,
        cheque_id=body.cheque_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=PaymentResponse.model_validate(payment),
        message="Customer payment recorded",
        meta=_meta(),
    )


@router.get(
    "/payments/supplier",
    response_model=StandardResponse[list[PaymentResponse]],
    summary="List a supplier's payments",
)
async def list_supplier_payments(
    company_id: UUID = Path(...),
    supplier_id: UUID = Query(...),
    user: CurrentUser = Depends(require_authenticated),
    service: PaymentService = Depends(get_payment_service),
) -> StandardResponse[list[PaymentResponse]]:
    payments = service.list_supplier_payments(
        company_id=company_id, supplier_id=supplier_id
    )
    return StandardResponse(
        data=[PaymentResponse.model_validate(p) for p in payments],
        message=f"Retrieved {len(payments)} supplier payment(s)",
        meta=_meta(),
    )


@router.post(
    "/payments/supplier",
    response_model=StandardResponse[PaymentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Record a supplier payment disbursement",
)
async def create_supplier_payment(
    company_id: UUID = Path(...),
    body: SupplierPaymentRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: PaymentService = Depends(get_payment_service),
    db: Session = Depends(get_db),
) -> StandardResponse[PaymentResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.payment.supplier.create"
    ):
        raise ApprovalPermissionDeniedError("accounting.payment.supplier.create")
    payment, _result = service.create_supplier_payment(
        company_id=company_id,
        supplier_id=body.supplier_id,
        payment_method=body.payment_method,
        payment_date=body.payment_date,
        amount=body.amount,
        currency_code=body.currency_code,
        exchange_rate=body.exchange_rate,
        payment_type=body.payment_type,
        bank_account_id=body.bank_account_id,
        cash_account_id=body.cash_account_id,
        advance_account_id=body.advance_account_id,
        wht_amount=body.wht_amount,
        wht_payable_account_id=body.wht_payable_account_id,
        reference=body.reference,
        notes=body.notes,
        cheque_id=body.cheque_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=PaymentResponse.model_validate(payment),
        message="Supplier payment recorded",
        meta=_meta(),
    )


@router.post(
    "/payments/{payment_id}/approve",
    response_model=StandardResponse[PaymentResponse],
    summary="Approve a DRAFT (pending-approval) payment and post its GL entry",
)
async def approve_payment(
    company_id: UUID = Path(...),
    payment_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: PaymentService = Depends(get_payment_service),
) -> StandardResponse[PaymentResponse]:
    payment, _result = service.approve_payment(
        company_id=company_id, payment_id=payment_id, approver_id=user.user_id
    )
    return StandardResponse(
        data=PaymentResponse.model_validate(payment),
        message="Payment approved and posted",
        meta=_meta(),
    )


@router.post(
    "/payments/{payment_id}/reject",
    response_model=StandardResponse[PaymentResponse],
    summary="Reject a DRAFT (pending-approval) payment",
)
async def reject_payment(
    company_id: UUID = Path(...),
    payment_id: UUID = Path(...),
    body: RejectRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: PaymentService = Depends(get_payment_service),
) -> StandardResponse[PaymentResponse]:
    payment = service.reject_payment(
        company_id=company_id,
        payment_id=payment_id,
        actor_id=user.user_id,
        rejection_reason=body.rejection_reason,
    )
    return StandardResponse(
        data=PaymentResponse.model_validate(payment),
        message="Payment rejected",
        meta=_meta(),
    )


@router.post(
    "/payments/{payment_id}/allocate",
    response_model=StandardResponse[list[PaymentAllocationLineResponse]],
    status_code=status.HTTP_201_CREATED,
    summary="Allocate a payment against invoices/bills",
)
async def allocate_payment(
    company_id: UUID = Path(...),
    payment_id: UUID = Path(...),
    body: PaymentAllocationRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: PaymentService = Depends(get_payment_service),
) -> StandardResponse[list[PaymentAllocationLineResponse]]:
    lines = service.allocate_payment(
        company_id=company_id,
        payment_id=payment_id,
        allocation_lines=[line.model_dump() for line in body.allocation_lines],
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=[PaymentAllocationLineResponse.model_validate(line) for line in lines],
        message=f"Allocated {len(lines)} line(s)",
        meta=_meta(),
    )


@router.post(
    "/payments/{payment_id}/reallocate",
    response_model=StandardResponse[list[PaymentAllocationLineResponse]],
    summary="Reverse a payment's existing allocations and apply new ones",
)
async def reallocate_payment(
    company_id: UUID = Path(...),
    payment_id: UUID = Path(...),
    body: PaymentAllocationRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: PaymentService = Depends(get_payment_service),
) -> StandardResponse[list[PaymentAllocationLineResponse]]:
    lines = service.reallocate_payment(
        company_id=company_id,
        payment_id=payment_id,
        new_allocation_lines=[line.model_dump() for line in body.allocation_lines],
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=[PaymentAllocationLineResponse.model_validate(line) for line in lines],
        message=f"Reallocated {len(lines)} line(s)",
        meta=_meta(),
    )


@router.post(
    "/payments/{payment_id}/cancel",
    response_model=StandardResponse[PaymentResponse],
    summary="Cancel an unallocated payment",
)
async def cancel_payment(
    company_id: UUID = Path(...),
    payment_id: UUID = Path(...),
    body: CancelPaymentRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: PaymentService = Depends(get_payment_service),
) -> StandardResponse[PaymentResponse]:
    payment = service.cancel_payment(
        company_id=company_id,
        payment_id=payment_id,
        reason=body.reason,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=PaymentResponse.model_validate(payment),
        message="Payment cancelled",
        meta=_meta(),
    )


@router.post(
    "/payments/{payment_id}/refund",
    response_model=StandardResponse[PaymentRefundResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Refund a payment's unallocated (credit) balance",
)
async def refund_payment(
    company_id: UUID = Path(...),
    payment_id: UUID = Path(...),
    body: RefundRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: PaymentService = Depends(get_payment_service),
) -> StandardResponse[PaymentRefundResponse]:
    refund, _result = service.process_refund(
        company_id=company_id,
        payment_id=payment_id,
        refund_date=body.refund_date,
        amount=body.amount,
        reason=body.reason,
        bank_account_id=body.bank_account_id,
        cash_account_id=body.cash_account_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=PaymentRefundResponse.model_validate(refund),
        message="Payment refunded",
        meta=_meta(),
    )


@router.get(
    "/payments/unallocated",
    response_model=StandardResponse[list[PaymentResponse]],
    summary="List payments not yet fully allocated",
)
async def list_unallocated_payments(
    company_id: UUID = Path(...),
    party_type: str | None = Query(None),
    user: CurrentUser = Depends(require_authenticated),
    service: PaymentService = Depends(get_payment_service),
) -> StandardResponse[list[PaymentResponse]]:
    payments = service.list_unallocated_payments(
        company_id=company_id, party_type=party_type
    )
    return StandardResponse(
        data=[PaymentResponse.model_validate(p) for p in payments],
        message=f"Retrieved {len(payments)} unallocated payment(s)",
        meta=_meta(),
    )


@router.get(
    "/payments/{payment_id}/wht-certificate",
    response_model=StandardResponse[WHTCertificateResponse],
    summary="Get the withholding tax certificate for a supplier payment",
)
async def get_wht_certificate(
    company_id: UUID = Path(...),
    payment_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: PaymentService = Depends(get_payment_service),
) -> StandardResponse[WHTCertificateResponse]:
    certificate = service.get_wht_certificate(
        company_id=company_id, payment_id=payment_id
    )
    return StandardResponse(
        data=WHTCertificateResponse.model_validate(certificate),
        message="WHT certificate retrieved",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Tax Engine (Phase 11, T236)
# ---------------------------------------------------------------------------


@router.get(
    "/tax-codes",
    response_model=StandardResponse[list[TaxCodeResponse]],
    summary="List tax codes",
)
async def list_tax_codes(
    company_id: UUID = Path(...),
    active_only: bool = Query(False),
    user: CurrentUser = Depends(require_authenticated),
    service: TaxService = Depends(get_tax_service),
) -> StandardResponse[list[TaxCodeResponse]]:
    codes = service.list_tax_codes(company_id=company_id, active_only=active_only)
    return StandardResponse(
        data=[TaxCodeResponse.model_validate(c) for c in codes],
        message=f"Retrieved {len(codes)} tax code(s)",
        meta=_meta(),
    )


@router.post(
    "/tax-codes",
    response_model=StandardResponse[TaxCodeResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a tax code",
)
async def create_tax_code(
    company_id: UUID = Path(...),
    body: TaxCodeCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: TaxService = Depends(get_tax_service),
    db: Session = Depends(get_db),
) -> StandardResponse[TaxCodeResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.tax.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.tax.manage")
    tax_code = service.create_tax_code(
        company_id=company_id,
        tax_code=body.tax_code,
        tax_name=body.tax_name,
        tax_type=body.tax_type,
        applicability=body.applicability,
        gl_account_id=body.gl_account_id,
        is_input_tax_recoverable=body.is_input_tax_recoverable,
        country_code=body.country_code,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=TaxCodeResponse.model_validate(tax_code),
        message="Tax code created",
        meta=_meta(),
    )


@router.get(
    "/tax-codes/{tax_code_id}",
    response_model=StandardResponse[TaxCodeResponse],
    summary="Get a tax code",
)
async def get_tax_code(
    company_id: UUID = Path(...),
    tax_code_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: TaxService = Depends(get_tax_service),
) -> StandardResponse[TaxCodeResponse]:
    tax_code = service.get_tax_code(company_id=company_id, tax_code_id=tax_code_id)
    return StandardResponse(
        data=TaxCodeResponse.model_validate(tax_code),
        message="Tax code retrieved",
        meta=_meta(),
    )


@router.put(
    "/tax-codes/{tax_code_id}",
    response_model=StandardResponse[TaxCodeResponse],
    summary="Update a tax code",
)
async def update_tax_code(
    company_id: UUID = Path(...),
    tax_code_id: UUID = Path(...),
    body: TaxCodeUpdateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: TaxService = Depends(get_tax_service),
    db: Session = Depends(get_db),
) -> StandardResponse[TaxCodeResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.tax.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.tax.manage")
    tax_code = service.update_tax_code(
        company_id=company_id,
        tax_code_id=tax_code_id,
        **body.model_dump(exclude_unset=True),
    )
    return StandardResponse(
        data=TaxCodeResponse.model_validate(tax_code),
        message="Tax code updated",
        meta=_meta(),
    )


@router.get(
    "/tax-codes/{tax_code_id}/rates",
    response_model=StandardResponse[list[TaxRateResponse]],
    summary="List a tax code's rate history",
)
async def list_tax_rates(
    company_id: UUID = Path(...),
    tax_code_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: TaxService = Depends(get_tax_service),
) -> StandardResponse[list[TaxRateResponse]]:
    rates = service.list_tax_rates(company_id=company_id, tax_code_id=tax_code_id)
    return StandardResponse(
        data=[TaxRateResponse.model_validate(r) for r in rates],
        message=f"Retrieved {len(rates)} tax rate(s)",
        meta=_meta(),
    )


@router.post(
    "/tax-codes/{tax_code_id}/rates",
    response_model=StandardResponse[TaxRateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add a rate to a tax code's history",
)
async def create_tax_rate(
    company_id: UUID = Path(...),
    tax_code_id: UUID = Path(...),
    body: TaxRateCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: TaxService = Depends(get_tax_service),
    db: Session = Depends(get_db),
) -> StandardResponse[TaxRateResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.tax.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.tax.manage")
    rate = service.update_tax_rate(
        company_id=company_id,
        tax_code_id=tax_code_id,
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        rate=body.rate,
        rounding_rule=body.rounding_rule,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=TaxRateResponse.model_validate(rate),
        message="Tax rate added",
        meta=_meta(),
    )


@router.get(
    "/tax-groups",
    response_model=StandardResponse[list[TaxGroupResponse]],
    summary="List tax groups",
)
async def list_tax_groups(
    company_id: UUID = Path(...),
    active_only: bool = Query(False),
    user: CurrentUser = Depends(require_authenticated),
    service: TaxService = Depends(get_tax_service),
) -> StandardResponse[list[TaxGroupResponse]]:
    groups = service.list_tax_groups(company_id=company_id, active_only=active_only)
    return StandardResponse(
        data=[TaxGroupResponse.model_validate(g) for g in groups],
        message=f"Retrieved {len(groups)} tax group(s)",
        meta=_meta(),
    )


@router.post(
    "/tax-groups",
    response_model=StandardResponse[TaxGroupResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a tax group",
)
async def create_tax_group(
    company_id: UUID = Path(...),
    body: TaxGroupCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: TaxService = Depends(get_tax_service),
    db: Session = Depends(get_db),
) -> StandardResponse[TaxGroupResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.tax.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.tax.manage")
    group = service.create_tax_group(
        company_id=company_id,
        group_code=body.group_code,
        group_name=body.group_name,
        applicability=body.applicability,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=TaxGroupResponse.model_validate(group),
        message="Tax group created",
        meta=_meta(),
    )


@router.get(
    "/tax-groups/{tax_group_id}/lines",
    response_model=StandardResponse[list[TaxGroupLineResponse]],
    summary="List a tax group's member tax codes",
)
async def list_tax_group_lines(
    company_id: UUID = Path(...),
    tax_group_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: TaxService = Depends(get_tax_service),
) -> StandardResponse[list[TaxGroupLineResponse]]:
    lines = service.list_group_lines(company_id=company_id, tax_group_id=tax_group_id)
    return StandardResponse(
        data=[TaxGroupLineResponse.model_validate(line) for line in lines],
        message=f"Retrieved {len(lines)} tax group line(s)",
        meta=_meta(),
    )


@router.post(
    "/tax-groups/{tax_group_id}/lines",
    response_model=StandardResponse[TaxGroupLineResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add a member tax code to a tax group",
)
async def add_tax_group_line(
    company_id: UUID = Path(...),
    tax_group_id: UUID = Path(...),
    body: TaxGroupLineCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: TaxService = Depends(get_tax_service),
    db: Session = Depends(get_db),
) -> StandardResponse[TaxGroupLineResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.tax.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.tax.manage")
    line = service.add_group_line(
        company_id=company_id,
        tax_group_id=tax_group_id,
        tax_code_id=body.tax_code_id,
        display_order=body.display_order,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=TaxGroupLineResponse.model_validate(line),
        message="Tax group line added",
        meta=_meta(),
    )


@router.post(
    "/tax/calculate",
    response_model=StandardResponse[TaxCalculationResult],
    summary="Calculate tax for a base amount using a tax code or tax group",
)
async def calculate_tax(
    company_id: UUID = Path(...),
    body: TaxCalculationRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    calculator: TaxCalculator = Depends(get_tax_calculator),
) -> StandardResponse[TaxCalculationResult]:
    lines = calculator.calculate(
        company_id=company_id,
        tax_code_or_group_id=body.tax_code_or_group_id,
        base_amount=body.base_amount,
        transaction_date=body.transaction_date,
        is_tax_inclusive=body.is_tax_inclusive,
    )
    total = sum((line.tax_amount for line in lines), Decimal("0"))
    return StandardResponse(
        data=TaxCalculationResult(
            lines=[TaxAmountResponse.model_validate(line) for line in lines],
            total_tax_amount=total,
        ),
        message=f"Calculated {len(lines)} tax line(s)",
        meta=_meta(),
    )


@router.get(
    "/reports/tax-summary",
    response_model=StandardResponse[TaxSummaryReport],
    summary="Get the VAT/GST summary report (output tax, input tax, net payable by tax code)",
)
async def get_tax_summary_report(
    company_id: UUID = Path(...),
    period_start: date = Query(...),
    period_end: date = Query(...),
    user: CurrentUser = Depends(require_authenticated),
    service: TaxService = Depends(get_tax_service),
    db: Session = Depends(get_db),
) -> StandardResponse[TaxSummaryReport]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    report = service.get_vat_summary_report(
        company_id=company_id, period_start=period_start, period_end=period_end
    )
    return StandardResponse(
        data=TaxSummaryReport.model_validate(report),
        message="Tax summary report retrieved",
        meta=_meta(),
    )


@router.get(
    "/reports/tax-detail",
    response_model=StandardResponse[list[TaxDetailRow]],
    summary="Get the detailed tax transaction report",
)
async def get_tax_detail_report(
    company_id: UUID = Path(...),
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    tax_code_id: UUID | None = Query(None),
    user: CurrentUser = Depends(require_authenticated),
    service: TaxService = Depends(get_tax_service),
    db: Session = Depends(get_db),
) -> StandardResponse[list[TaxDetailRow]]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    rows = service.get_tax_detail_report(
        company_id=company_id,
        period_start=period_start,
        period_end=period_end,
        tax_code_id=tax_code_id,
    )
    return StandardResponse(
        data=[TaxDetailRow.model_validate(row) for row in rows],
        message=f"Retrieved {len(rows)} tax transaction(s)",
        meta=_meta(),
    )


@router.get(
    "/reports/wht",
    response_model=StandardResponse[WHTReport],
    summary="Get the withholding tax report (deducted per supplier for a period)",
)
async def get_wht_report(
    company_id: UUID = Path(...),
    period_start: date = Query(...),
    period_end: date = Query(...),
    user: CurrentUser = Depends(require_authenticated),
    service: TaxService = Depends(get_tax_service),
    db: Session = Depends(get_db),
) -> StandardResponse[WHTReport]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    report = service.get_wht_report(
        company_id=company_id, period_start=period_start, period_end=period_end
    )
    return StandardResponse(
        data=WHTReport.model_validate(report),
        message="Withholding tax report retrieved",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Cost Accounting (Phase 11, T237)
# ---------------------------------------------------------------------------


@router.get(
    "/cost-centers",
    response_model=StandardResponse[list[CostCenterResponse]],
    summary="List cost centers",
)
async def list_cost_centers(
    company_id: UUID = Path(...),
    active_only: bool = Query(False),
    user: CurrentUser = Depends(require_authenticated),
    service: CostCenterService = Depends(get_cost_center_service),
) -> StandardResponse[list[CostCenterResponse]]:
    centers = service.list_cost_centers(company_id=company_id, active_only=active_only)
    return StandardResponse(
        data=[CostCenterResponse.model_validate(c) for c in centers],
        message=f"Retrieved {len(centers)} cost center(s)",
        meta=_meta(),
    )


@router.post(
    "/cost-centers",
    response_model=StandardResponse[CostCenterResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a cost center",
)
async def create_cost_center(
    company_id: UUID = Path(...),
    body: CostCenterCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: CostCenterService = Depends(get_cost_center_service),
) -> StandardResponse[CostCenterResponse]:
    center = service.create_cost_center(
        company_id=company_id,
        center_code=body.center_code,
        center_name=body.center_name,
        department_id=body.department_id,
        responsible_user_id=body.responsible_user_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=CostCenterResponse.model_validate(center),
        message="Cost center created",
        meta=_meta(),
    )


@router.get(
    "/departments",
    response_model=StandardResponse[list[DepartmentResponse]],
    summary="List departments",
)
async def list_departments(
    company_id: UUID = Path(...),
    active_only: bool = Query(False),
    user: CurrentUser = Depends(require_authenticated),
    service: CostCenterService = Depends(get_cost_center_service),
) -> StandardResponse[list[DepartmentResponse]]:
    departments = service.list_departments(
        company_id=company_id, active_only=active_only
    )
    return StandardResponse(
        data=[DepartmentResponse.model_validate(d) for d in departments],
        message=f"Retrieved {len(departments)} department(s)",
        meta=_meta(),
    )


@router.post(
    "/departments",
    response_model=StandardResponse[DepartmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a department",
)
async def create_department(
    company_id: UUID = Path(...),
    body: DepartmentCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: CostCenterService = Depends(get_cost_center_service),
) -> StandardResponse[DepartmentResponse]:
    department = service.create_department(
        company_id=company_id,
        dept_code=body.dept_code,
        dept_name=body.dept_name,
        parent_dept_id=body.parent_dept_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=DepartmentResponse.model_validate(department),
        message="Department created",
        meta=_meta(),
    )


@router.get(
    "/projects",
    response_model=StandardResponse[list[ProjectResponse]],
    summary="List projects",
)
async def list_projects(
    company_id: UUID = Path(...),
    active_only: bool = Query(False),
    user: CurrentUser = Depends(require_authenticated),
    service: CostCenterService = Depends(get_cost_center_service),
) -> StandardResponse[list[ProjectResponse]]:
    projects = service.list_projects(company_id=company_id, active_only=active_only)
    return StandardResponse(
        data=[ProjectResponse.model_validate(p) for p in projects],
        message=f"Retrieved {len(projects)} project(s)",
        meta=_meta(),
    )


@router.post(
    "/projects",
    response_model=StandardResponse[ProjectResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
async def create_project(
    company_id: UUID = Path(...),
    body: ProjectCreateRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: CostCenterService = Depends(get_cost_center_service),
) -> StandardResponse[ProjectResponse]:
    project = service.create_project(
        company_id=company_id,
        project_code=body.project_code,
        project_name=body.project_name,
        start_date=body.start_date,
        end_date=body.end_date,
        budget_amount=body.budget_amount,
        responsible_user_id=body.responsible_user_id,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=ProjectResponse.model_validate(project),
        message="Project created",
        meta=_meta(),
    )


@router.get(
    "/reports/cost-center-pl",
    response_model=StandardResponse[CostCenterPLReport],
    summary="Get the Cost Center P&L report",
)
async def get_cost_center_pl_report(
    company_id: UUID = Path(...),
    cost_center_id: UUID = Query(...),
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    user: CurrentUser = Depends(require_authenticated),
    service: CostCenterService = Depends(get_cost_center_service),
    db: Session = Depends(get_db),
) -> StandardResponse[CostCenterPLReport]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    report = service.get_cost_center_pl_report(
        company_id=company_id,
        cost_center_id=cost_center_id,
        period_start=period_start,
        period_end=period_end,
    )
    return StandardResponse(
        data=CostCenterPLReport.model_validate(report),
        message="Cost center P&L report retrieved",
        meta=_meta(),
    )


@router.get(
    "/reports/project-pl",
    response_model=StandardResponse[CostCenterPLReport],
    summary="Get the Project P&L report",
)
async def get_project_pl_report(
    company_id: UUID = Path(...),
    project_id: UUID = Query(...),
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    user: CurrentUser = Depends(require_authenticated),
    service: CostCenterService = Depends(get_cost_center_service),
    db: Session = Depends(get_db),
) -> StandardResponse[CostCenterPLReport]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    report = service.get_project_report(
        company_id=company_id,
        project_id=project_id,
        period_start=period_start,
        period_end=period_end,
    )
    return StandardResponse(
        data=CostCenterPLReport.model_validate(report),
        message="Project P&L report retrieved",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Multi-Currency & Exchange Rates (Phase 12, T251)
# ---------------------------------------------------------------------------


@router.post(
    "/currency-revaluation",
    response_model=StandardResponse[RevaluationReport],
    status_code=status.HTTP_201_CREATED,
    summary="Run a period-end currency revaluation",
)
async def run_currency_revaluation(
    company_id: UUID = Path(...),
    body: RevaluationRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: CurrencyRevaluationService = Depends(get_currency_revaluation_service),
    db: Session = Depends(get_db),
) -> StandardResponse[RevaluationReport]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.exchangerate.manage"
    ):
        raise ApprovalPermissionDeniedError("accounting.exchangerate.manage")
    run = service.run_revaluation(
        company_id=company_id,
        period_id=body.fiscal_period_id,
        revaluation_date=body.revaluation_date,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=RevaluationReport.model_validate(run),
        message="Currency revaluation completed",
        meta=_meta(),
    )


@router.get(
    "/currency-revaluation/history",
    response_model=StandardResponse[list[RevaluationReport]],
    summary="List past currency revaluation runs",
)
async def list_currency_revaluation_history(
    company_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CurrencyRevaluationService = Depends(get_currency_revaluation_service),
) -> StandardResponse[list[RevaluationReport]]:
    runs = service.list_revaluation_history(company_id=company_id)
    return StandardResponse(
        data=[RevaluationReport.model_validate(r) for r in runs],
        message=f"Retrieved {len(runs)} revaluation run(s)",
        meta=_meta(),
    )


@router.get(
    "/currency-revaluation/{revaluation_id}/report",
    response_model=StandardResponse[RevaluationReport],
    summary="Get a currency revaluation run's full report",
)
async def get_currency_revaluation_report(
    company_id: UUID = Path(...),
    revaluation_id: UUID = Path(...),
    user: CurrentUser = Depends(require_authenticated),
    service: CurrencyRevaluationService = Depends(get_currency_revaluation_service),
) -> StandardResponse[RevaluationReport]:
    run = service.get_revaluation(company_id=company_id, run_id=revaluation_id)
    return StandardResponse(
        data=RevaluationReport.model_validate(run),
        message="Currency revaluation report retrieved",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Financial Statements & Reports (Phase 13, T260/T261)
# ---------------------------------------------------------------------------


def _export_response(
    report_data: dict[str, Any], template: str, export_format: str, filename_stem: str
) -> Response:
    """Shared PDF/Excel export responder — T261's ``?format=pdf|excel`` on
    every report endpoint below. Mirrors the ``Response(content=..., media_
    type=..., headers={"Content-Disposition": ...})`` pattern already
    established in ``modules.purchase.router``'s report export endpoints.
    """
    if export_format == "pdf":
        return Response(
            content=export_to_pdf(report_data, template),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename_stem}.pdf"
            },
        )
    return Response(
        content=export_to_excel(report_data, template),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename_stem}.xlsx"},
    )


@router.get(
    "/reports/trial-balance",
    response_model=None,
    summary="Trial Balance report (optional comparative period; PDF/Excel export)",
)
async def trial_balance_report(
    company_id: UUID = Path(...),
    period_id: UUID = Query(...),
    comparative_period_id: UUID | None = Query(None),
    export_format: str | None = Query(None, alias="format", pattern="^(pdf|excel)$"),
    user: CurrentUser = Depends(require_authenticated),
    service: FinancialStatementService = Depends(get_financial_statement_service),
    db: Session = Depends(get_db),
) -> StandardResponse[TrialBalanceReport] | Response:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    data = service.get_trial_balance(company_id, period_id, comparative_period_id)
    if export_format:
        return _export_response(data, "trial_balance", export_format, "trial_balance")
    return StandardResponse(
        data=TrialBalanceReport.model_validate(data),
        message="Trial balance retrieved",
        meta=_meta(),
    )


@router.get(
    "/reports/balance-sheet",
    response_model=None,
    summary="Balance Sheet report (optional comparative date, report currency; PDF/Excel export)",
)
async def balance_sheet_report(
    company_id: UUID = Path(...),
    as_of_date: date = Query(...),
    comparative_date: date | None = Query(None),
    report_currency: str | None = Query(None, min_length=3, max_length=3),
    export_format: str | None = Query(None, alias="format", pattern="^(pdf|excel)$"),
    user: CurrentUser = Depends(require_authenticated),
    service: FinancialStatementService = Depends(get_financial_statement_service),
    db: Session = Depends(get_db),
) -> StandardResponse[BalanceSheetReport] | Response:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    data = service.get_balance_sheet(
        company_id, as_of_date, comparative_date, report_currency
    )
    if export_format:
        return _export_response(data, "balance_sheet", export_format, "balance_sheet")
    return StandardResponse(
        data=BalanceSheetReport.from_service_dict(data),
        message="Balance sheet retrieved",
        meta=_meta(),
    )


@router.get(
    "/reports/profit-loss",
    response_model=None,
    summary="Profit & Loss report (comparative period, cost center filter; PDF/Excel export)",
)
async def profit_loss_report(
    company_id: UUID = Path(...),
    period_from: date = Query(...),
    period_to: date = Query(...),
    comparative_from: date | None = Query(None),
    comparative_to: date | None = Query(None),
    cost_center_id: UUID | None = Query(None),
    report_currency: str | None = Query(None, min_length=3, max_length=3),
    export_format: str | None = Query(None, alias="format", pattern="^(pdf|excel)$"),
    user: CurrentUser = Depends(require_authenticated),
    service: FinancialStatementService = Depends(get_financial_statement_service),
    db: Session = Depends(get_db),
) -> StandardResponse[PLReport] | Response:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    data = service.get_pl(
        company_id,
        period_from,
        period_to,
        comparative_from,
        comparative_to,
        cost_center_id,
        report_currency,
    )
    if export_format:
        return _export_response(data, "profit_loss", export_format, "profit_loss")
    return StandardResponse(
        data=PLReport.from_service_dict(data),
        message="Profit & loss statement retrieved",
        meta=_meta(),
    )


@router.get(
    "/reports/cash-flow",
    response_model=StandardResponse[CashFlowReport],
    summary="Cash Flow report (indirect method)",
)
async def cash_flow_report(
    company_id: UUID = Path(...),
    period_from: date = Query(...),
    period_to: date = Query(...),
    user: CurrentUser = Depends(require_authenticated),
    service: FinancialStatementService = Depends(get_financial_statement_service),
    db: Session = Depends(get_db),
) -> StandardResponse[CashFlowReport]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    data = service.get_cash_flow(company_id, period_from, period_to)
    return StandardResponse(
        data=CashFlowReport.model_validate(data),
        message="Cash flow statement retrieved",
        meta=_meta(),
    )


@router.get(
    "/reports/customer-ledger/{customer_id}",
    response_model=None,
    summary="Customer ledger report for a date range (PDF/Excel export)",
)
async def customer_ledger_report(
    company_id: UUID = Path(...),
    customer_id: UUID = Path(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    export_format: str | None = Query(None, alias="format", pattern="^(pdf|excel)$"),
    user: CurrentUser = Depends(require_authenticated),
    service: ReportService = Depends(get_report_service),
    db: Session = Depends(get_db),
) -> StandardResponse[CustomerStatementResponse] | Response:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    data = service.get_customer_ledger_report(
        company_id, customer_id, from_date, to_date
    )
    if export_format:
        return _export_response(
            data, "ledger_statement", export_format, "customer_ledger"
        )
    return StandardResponse(
        data=CustomerStatementResponse.model_validate(data),
        message="Customer ledger report retrieved",
        meta=_meta(),
    )


@router.get(
    "/reports/supplier-ledger/{supplier_id}",
    response_model=None,
    summary="Supplier ledger report for a date range (PDF/Excel export)",
)
async def supplier_ledger_report(
    company_id: UUID = Path(...),
    supplier_id: UUID = Path(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    export_format: str | None = Query(None, alias="format", pattern="^(pdf|excel)$"),
    user: CurrentUser = Depends(require_authenticated),
    service: ReportService = Depends(get_report_service),
    db: Session = Depends(get_db),
) -> StandardResponse[SupplierStatementResponse] | Response:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    data = service.get_supplier_ledger_report(
        company_id, supplier_id, from_date, to_date
    )
    if export_format:
        return _export_response(
            data, "ledger_statement", export_format, "supplier_ledger"
        )
    return StandardResponse(
        data=SupplierStatementResponse.model_validate(data),
        message="Supplier ledger report retrieved",
        meta=_meta(),
    )


@router.get(
    "/reports/bank-book/{bank_account_id}",
    response_model=None,
    summary="Bank book report for a date range (PDF/Excel export)",
)
async def bank_book_report(
    company_id: UUID = Path(...),
    bank_account_id: UUID = Path(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    export_format: str | None = Query(None, alias="format", pattern="^(pdf|excel)$"),
    user: CurrentUser = Depends(require_authenticated),
    service: ReportService = Depends(get_report_service),
    db: Session = Depends(get_db),
) -> StandardResponse[BankBookResponse] | Response:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    data = service.get_bank_book(company_id, bank_account_id, from_date, to_date)
    if export_format:
        return _export_response(data, "ledger_statement", export_format, "bank_book")
    return StandardResponse(
        data=BankBookResponse.model_validate(data),
        message="Bank book report retrieved",
        meta=_meta(),
    )


@router.get(
    "/reports/cash-book/{cash_account_id}",
    response_model=None,
    summary="Cash book report for a date range (PDF/Excel export)",
)
async def cash_book_report(
    company_id: UUID = Path(...),
    cash_account_id: UUID = Path(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    export_format: str | None = Query(None, alias="format", pattern="^(pdf|excel)$"),
    user: CurrentUser = Depends(require_authenticated),
    service: ReportService = Depends(get_report_service),
    db: Session = Depends(get_db),
) -> StandardResponse[CashBookResponse] | Response:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    data = service.get_cash_book(company_id, cash_account_id, from_date, to_date)
    if export_format:
        return _export_response(data, "ledger_statement", export_format, "cash_book")
    return StandardResponse(
        data=CashBookResponse.model_validate(data),
        message="Cash book report retrieved",
        meta=_meta(),
    )


@router.get(
    "/reports/journals",
    response_model=None,
    summary="Journal report for a fiscal period (PDF/Excel export)",
)
async def journal_report(
    company_id: UUID = Path(...),
    period_id: UUID = Query(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    export_format: str | None = Query(None, alias="format", pattern="^(pdf|excel)$"),
    user: CurrentUser = Depends(require_authenticated),
    service: ReportService = Depends(get_report_service),
    db: Session = Depends(get_db),
) -> StandardResponse[JournalReportResponse] | Response:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    data = service.get_journal_report(company_id, period_id, skip, limit)
    if export_format:
        return _export_response(data, "journal_report", export_format, "journal_report")
    return StandardResponse(
        data=JournalReportResponse.model_validate(data),
        message=f"Retrieved {len(data['entries'])} of {data['total']} journal entries",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# Financial Intelligence & KPI Dashboard (Phase 15, T287-T288)
# ---------------------------------------------------------------------------


@router.get(
    "/dashboard/kpis",
    response_model=StandardResponse[FinancialKPIResponse],
    summary="Get all 15 CFO dashboard KPIs with real-time values and change vs prior period",
)
async def get_dashboard_kpis(
    company_id: UUID = Path(...),
    as_of_date: date = Query(default_factory=date.today),
    user: CurrentUser = Depends(require_authenticated),
    service: FinancialKPIService = Depends(get_kpi_service),
    db: Session = Depends(get_db),
) -> StandardResponse[FinancialKPIResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    data = service.get_dashboard_kpis(company_id=company_id, as_of_date=as_of_date)
    return StandardResponse(
        data=FinancialKPIResponse.model_validate(data),
        message="Financial KPIs retrieved",
        meta=_meta(),
    )


@router.get(
    "/dashboard/cash-position",
    response_model=StandardResponse[CashPositionResponse],
    summary="Get bank + cash account balances with trend data",
)
async def get_dashboard_cash_position(
    company_id: UUID = Path(...),
    as_of_date: date = Query(default_factory=date.today),
    trend_days: int = Query(7, ge=1, le=90),
    user: CurrentUser = Depends(require_authenticated),
    service: FinancialKPIService = Depends(get_kpi_service),
    db: Session = Depends(get_db),
) -> StandardResponse[CashPositionResponse]:
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    data = service.get_cash_position(
        company_id=company_id, as_of_date=as_of_date, trend_days=trend_days
    )
    return StandardResponse(
        data=CashPositionResponse.model_validate(data),
        message="Cash position retrieved",
        meta=_meta(),
    )


# ---------------------------------------------------------------------------
# AI ERP Readiness (Phase 17, T304-T307)
#
# All four endpoints below are hard-gated by the ``accounting.ai.enabled``
# feature flag (T309: disabled -> 403 FEATURE_DISABLED; enabled -> 200 with
# data), in addition to the usual authentication requirement.
# ---------------------------------------------------------------------------


def _require_ai_enabled(
    company_id: UUID, flag_service: AccountingFeatureFlagService
) -> None:
    if not flag_service.is_enabled(company_id, "accounting.ai.enabled"):
        raise AccountingFeatureDisabledError("accounting.ai.enabled")


@router.get(
    "/events/stream",
    response_model=StandardResponse[list[GLEventStreamRow]],
    summary="Paginated POSTED journal entry event history, for ML training-data consumption",
)
async def get_gl_event_stream(
    company_id: UUID = Path(...),
    from_date: date | None = Query(None, alias="from"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user: CurrentUser = Depends(require_authenticated),
    service: AIReadinessService = Depends(get_ai_service),
    flag_service: AccountingFeatureFlagService = Depends(
        get_accounting_feature_flag_service
    ),
    db: Session = Depends(get_db),
) -> StandardResponse[list[GLEventStreamRow]]:
    _require_ai_enabled(company_id, flag_service)
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    rows, total = service.get_event_stream(
        company_id=company_id, from_date=from_date, skip=skip, limit=limit
    )
    return StandardResponse(
        data=[GLEventStreamRow.model_validate(r) for r in rows],
        message=f"Retrieved {len(rows)} of {total} journal events",
        meta=_meta(),
    )


@router.get(
    "/ai/pl-history",
    response_model=StandardResponse[list[PLHistoryPeriod]],
    summary="Last N fiscal periods' P&L, for revenue/expense forecasting models",
)
async def get_ai_pl_history(
    company_id: UUID = Path(...),
    periods: int = Query(24, ge=1, le=120),
    user: CurrentUser = Depends(require_authenticated),
    service: AIReadinessService = Depends(get_ai_service),
    flag_service: AccountingFeatureFlagService = Depends(
        get_accounting_feature_flag_service
    ),
    db: Session = Depends(get_db),
) -> StandardResponse[list[PLHistoryPeriod]]:
    _require_ai_enabled(company_id, flag_service)
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    rows = service.get_pl_history(company_id=company_id, periods=periods)
    return StandardResponse(
        data=[PLHistoryPeriod.model_validate(r) for r in rows],
        message=f"Retrieved {len(rows)} period(s) of P&L history",
        meta=_meta(),
    )


@router.get(
    "/ai/cashflow-history",
    response_model=StandardResponse[list[CashFlowHistoryPeriod]],
    summary="Last N fiscal periods' cash flow, for cash flow forecasting models",
)
async def get_ai_cashflow_history(
    company_id: UUID = Path(...),
    periods: int = Query(12, ge=1, le=120),
    user: CurrentUser = Depends(require_authenticated),
    service: AIReadinessService = Depends(get_ai_service),
    flag_service: AccountingFeatureFlagService = Depends(
        get_accounting_feature_flag_service
    ),
    db: Session = Depends(get_db),
) -> StandardResponse[list[CashFlowHistoryPeriod]]:
    _require_ai_enabled(company_id, flag_service)
    if not user_has_accounting_permission(
        db, company_id, user.user_id, "accounting.reports.view"
    ):
        raise ApprovalPermissionDeniedError("accounting.reports.view")
    rows = service.get_cashflow_history(company_id=company_id, periods=periods)
    return StandardResponse(
        data=[CashFlowHistoryPeriod.model_validate(r) for r in rows],
        message=f"Retrieved {len(rows)} period(s) of cash flow history",
        meta=_meta(),
    )


@router.post(
    "/ai/anomaly-report",
    response_model=StandardResponse[list[AnomalyFlagResponse]],
    status_code=status.HTTP_201_CREATED,
    summary="Flag journal entries as anomalies detected by an external ML model (stub)",
)
async def create_anomaly_report(
    company_id: UUID = Path(...),
    body: AnomalyReportRequest = ...,
    user: CurrentUser = Depends(require_authenticated),
    service: AIReadinessService = Depends(get_ai_service),
    flag_service: AccountingFeatureFlagService = Depends(
        get_accounting_feature_flag_service
    ),
) -> StandardResponse[list[AnomalyFlagResponse]]:
    _require_ai_enabled(company_id, flag_service)
    flags = service.record_anomaly_report(
        company_id=company_id,
        journal_entry_ids=body.journal_entry_ids,
        reason=body.reason,
        actor_id=user.user_id,
    )
    return StandardResponse(
        data=[AnomalyFlagResponse.model_validate(f) for f in flags],
        message=f"Flagged {len(flags)} journal entry(ies) as anomalies",
        meta=_meta(),
    )
