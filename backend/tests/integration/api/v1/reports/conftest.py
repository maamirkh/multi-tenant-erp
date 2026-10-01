"""Shared HTTP-level helpers for Epic 11 Phase 3 execution-API tests
(SQLite ``db_session``/``test_client`` from the root conftest — real
Postgres is reserved for the ``postgres/`` subdirectory, matching
``tests/integration/api/v1/installments/conftest.py``'s established
split)."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.accounting.models.coa import Account
from modules.accounting.models.foundation import AccountingConfiguration
from modules.accounting.repositories.coa import AccountRepository
from modules.accounting.repositories.fiscal import (
    FiscalPeriodRepository,
    FiscalYearRepository,
    OpeningBalanceRepository,
)
from modules.accounting.repositories.foundation import AccountingConfigurationRepository
from modules.accounting.repositories.gl import AccountingAuditLogRepository
from modules.accounting.services.audit_service import AuditLogService
from modules.accounting.services.fiscal_service import FiscalCalendarService
from modules.crm.repositories.feature_flag_repository import CrmFeatureFlagRepository
from modules.crm.services.feature_flag_service import CrmFeatureFlagService
from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.services.feature_flag_service import (
    InstallmentsFeatureFlagService,
)
from modules.platform_admin.repositories.capability_repository import (
    CapabilityRepository,
)
from modules.platform_admin.services.capability_seed_service import (
    CapabilitySeedService,
)
from modules.reports.repositories.feature_flag import ReportsFeatureFlagRepository
from modules.reports.services.feature_flag_service import REPORTS_ENABLED_FLAG_KEY
from modules.sales.models.customer import Customer
from modules.sales.models.invoice import SalesInvoice
from modules.users_roles.constants import REPORTS_PERMISSIONS
from modules.users_roles.repositories.company_member_repository import (
    CompanyMemberRepository,
)
from modules.users_roles.repositories.role_permission_repository import (
    RolePermissionRepository,
)
from tests.fixtures.auth_fixtures import create_test_user


def login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["access_token"])


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_company(client: TestClient, token: str) -> uuid.UUID:
    """Create a real company via the API so the caller becomes its owner."""
    suffix = uuid.uuid4().hex[:8]
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Reports Test Co {suffix}",
            "email": f"contact-{suffix}@reports-test.example.com",
        },
        headers=auth_header(token),
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["data"]["id"])


def enable_reports(db: Session, company_id: uuid.UUID) -> None:
    """Seed the ``reports`` capability + enable its own module toggle
    (mirrors ``test_router_mount.py``'s established gate-chain setup) —
    without this, every ``/reports/...`` request 403s before it ever
    reaches ``ReportExecutionService``."""
    CapabilitySeedService(db, CapabilityRepository(db)).seed_capabilities()
    ReportsFeatureFlagRepository(db).upsert(
        company_id=company_id, flag_key=REPORTS_ENABLED_FLAG_KEY, is_enabled=True
    )
    db.commit()


def grant_all_reports_permissions(
    db: Session, company_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """Explicitly assign every ``reports.*`` permission code to *user_id*'s
    role in *company_id* — required because FR-RPT-243 explicitly forbids
    Epic 11 from hardcoding a default role->``reports.*`` mapping in
    ``DEFAULT_ROLE_PERMISSIONS`` (unlike CRM/Installments' own
    ``_CRM_OWNER``/``_INSTALLMENTS_OWNER`` precedent); real tenants assign
    it via the existing RBAC management surface, which this simulates."""
    member = CompanyMemberRepository(db).get_by_user_id(
        user_id=user_id, company_id=company_id
    )
    assert member is not None
    role_permission_repo = RolePermissionRepository(db)
    current = role_permission_repo.get_permission_codes_for_role(member.role_id)
    updated = current | {p.code for p in REPORTS_PERMISSIONS}
    role_permission_repo.bulk_set_permissions_for_role(member.role_id, updated)
    db.commit()


def setup_company(db: Session, client: TestClient) -> tuple[str, uuid.UUID]:
    """End-to-end: create a user, log in, create+own a company, enable
    ``reports``, and grant the owner every ``reports.*`` permission code
    (FR-RPT-243 — never a default, always an explicit tenant-admin grant).
    Returns ``(token, company_id)``."""
    email = f"reports-{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"
    user, _ = create_test_user(db, email=email, password=password)
    token = login(client, email, password)
    company_id = create_company(client, token)
    enable_reports(db, company_id)
    grant_all_reports_permissions(db, company_id, user.id)
    return token, company_id


def enable_crm_and_installments(db: Session, company_id: uuid.UUID) -> None:
    """Enable CRM's and Installments' own module toggles for *company_id*
    — both default disabled (unlike core domains' always-on provider),
    needed for tests that exercise every one of the 43 real report keys,
    not just the always-entitled core-domain ones. ``provisioning_service
    =None`` skips CRM's default-Pipeline/Category provisioning (the same
    "no full provisioning chain" shortcut ``CrmFeatureFlagService``'s own
    docstring documents as sanctioned for tests)."""
    CrmFeatureFlagService(
        db=db, flag_repo=CrmFeatureFlagRepository(db), provisioning_service=None
    ).enable(company_id)
    InstallmentsFeatureFlagService(
        flag_repo=InstallmentsFeatureFlagRepository(db)
    ).enable(company_id)
    db.commit()


def reports_url(company_id: uuid.UUID | str, path: str) -> str:
    return f"/api/v1/companies/{company_id}/reports{path}"


def configure_accounting_minimal(db: Session, company_id: uuid.UUID) -> None:
    """Seed the minimum ``AccountingConfiguration`` + current fiscal year
    Accounting's own ``FinancialKPIService._require_configuration()``
    needs to stop raising ``PostingValidationError`` (mirrors
    ``tests/integration/api/v1/accounting/test_dashboard_api.py``'s own
    fixture) — without this, every Executive Dashboard widget sourced from
    ``accounting.kpis`` (AR, AP, Cash Position, Gross Profit Margin)
    renders ``UNAVAILABLE`` for any company that hasn't configured
    Accounting yet, which is the *correct*, real behavior (T148) but not
    what a test isolating some other axis (entitlement, comparison, error
    propagation) wants incidentally in its way."""
    account_repo = AccountRepository(db)
    ar = account_repo.create(
        Account(
            company_id=company_id,
            account_code="1100",
            account_name="AR",
            account_type="ASSET",
        )
    )
    fiscal_service = FiscalCalendarService(
        db=db,
        year_repo=FiscalYearRepository(db),
        period_repo=FiscalPeriodRepository(db),
        opening_balance_repo=OpeningBalanceRepository(db),
        audit_service=AuditLogService(
            db=db, audit_repo=AccountingAuditLogRepository(db)
        ),
    )
    today = date.today()
    fiscal_service.create_fiscal_year(
        company_id,
        f"FY-{uuid.uuid4().hex[:8]}",
        date(today.year, 1, 1),
        date(today.year, 12, 31),
        "USD",
        is_current=True,
    )
    AccountingConfigurationRepository(db).create(
        AccountingConfiguration(
            company_id=company_id, base_currency_code="USD", default_ar_account_id=ar.id
        )
    )
    db.commit()


def create_sales_customer(db: Session, company_id: uuid.UUID) -> Customer:
    """Insert a minimal, valid Sales ``Customer`` row directly (no HTTP
    signup flow needed — Customer 360 tests only need a real, tenant-owned
    customer to look up). ``category_id`` carries no DB-level
    ``ForeignKey`` (documented as a soft reference on the model), so any
    UUID satisfies it, matching the same "no enforced FK" convention
    Sales' own ``customer_id`` references elsewhere in this Epic rely on."""
    customer = Customer(
        company_id=company_id,
        customer_code=f"CUST-{uuid.uuid4().hex[:8]}",
        category_id=str(uuid.uuid4()),
        legal_name=f"Reports Test Customer {uuid.uuid4().hex[:6]}",
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


def grant_reports_permissions(
    db: Session, company_id: uuid.UUID, user_id: uuid.UUID, codes: set[str]
) -> None:
    """Assign *only* the given ``reports.*`` codes (plus whatever non-reports
    codes the role already had) — e.g. ``.view`` without ``.export``
    (FR-RPT-212)."""
    member = CompanyMemberRepository(db).get_by_user_id(
        user_id=user_id, company_id=company_id
    )
    assert member is not None
    role_permission_repo = RolePermissionRepository(db)
    current = {
        code
        for code in role_permission_repo.get_permission_codes_for_role(member.role_id)
        if not code.startswith("reports.")
    }
    role_permission_repo.bulk_set_permissions_for_role(member.role_id, current | codes)
    db.commit()


def setup_company_with_user(
    db: Session, client: TestClient
) -> tuple[str, uuid.UUID, uuid.UUID]:
    """Like ``setup_company`` but also returns the owner's user id.
    Returns ``(token, company_id, user_id)``."""
    email = f"reports-{uuid.uuid4().hex[:8]}@test.com"
    password = "TestPass123!"
    user, _ = create_test_user(db, email=email, password=password)
    token = login(client, email, password)
    company_id = create_company(client, token)
    enable_reports(db, company_id)
    grant_all_reports_permissions(db, company_id, user.id)
    return token, company_id, user.id


def seed_sales_invoice(
    db: Session,
    company_id: uuid.UUID,
    *,
    amount: str,
    customer_id: uuid.UUID | None = None,
    invoice_date: str = "2026-01-15",
    currency_code: str = "USD",
) -> None:
    """One ISSUED invoice — each distinct ``customer_id`` becomes its own
    ``sales.by_customer`` row, which lets export tests control row counts
    exactly."""
    db.add(
        SalesInvoice(
            company_id=company_id,
            invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
            customer_id=str(customer_id or uuid.uuid4()),
            invoice_date=invoice_date,
            due_date="2026-02-14",
            currency_code=currency_code,
            status="ISSUED",
            subtotal=Decimal(amount),
            discount_amount=Decimal("0"),
            tax_amount=Decimal("0"),
            charges_amount=Decimal("0"),
            total_amount=Decimal(amount),
            version=1,
        )
    )
    db.commit()


def export_url(company_id: uuid.UUID | str, report_key: str, fmt: str) -> str:
    return reports_url(company_id, f"/{report_key}/export?format={fmt}")


def parse_csv(content: bytes) -> list[list[str]]:
    text = content.decode("utf-8")
    if text.startswith("﻿"):
        text = text[1:]
    return list(csv.reader(io.StringIO(text)))
