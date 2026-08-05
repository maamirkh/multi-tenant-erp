"""Integration tests for sales report and KPI services — Phase 8.

Tests cover:
  - ReportService.run_report() for selected report types
  - KPIService.get_dashboard() returns all 12 KPIs
  - Tenant isolation: each company sees only its own data
  - Empty-state handling when no data exists
  - Export service produces non-empty CSV bytes

Task: T219
Spec ref: specs/007-sales-management/spec.md §35-§36
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from modules.sales.models.customer import Customer
from modules.sales.models.invoice import SalesInvoice
from modules.sales.models.order import SalesOrder
from modules.sales.models.quotation import SalesQuotation
from modules.sales.schemas.reports import ExportFormat, ReportParams, ReportType
from modules.sales.services.kpi_service import KPIService
from modules.sales.services.report_export_service import ReportExportService
from modules.sales.services.report_service import ReportService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _company() -> UUID:
    """Return a fresh UUID for use as company_id (TenantBaseModel uses Uuid(as_uuid=True))."""
    return uuid4()


def _customer_id() -> str:
    """customer_id columns use PG_UUID(as_uuid=False) — pass as string."""
    return str(uuid4())


def _sales_rep_id() -> str:
    return str(uuid4())


def _make_invoice(
    db: Session,
    company_id: UUID,
    customer_id: str,
    amount: Decimal = Decimal("100.00"),
    status: str = "ISSUED",
    invoice_date: str = "2026-08-01",
) -> SalesInvoice:
    inv = SalesInvoice(
        company_id=company_id,
        customer_id=customer_id,
        invoice_number=f"SI-{uuid4().hex[:8]}",
        invoice_date=invoice_date,
        due_date="2026-09-01",
        currency_code="USD",
        status=status,
        subtotal=amount,
        discount_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        charges_amount=Decimal("0"),
        total_amount=amount,
    )
    db.add(inv)
    db.flush()
    return inv


def _make_order(
    db: Session,
    company_id: UUID,
    customer_id: str,
    total: Decimal = Decimal("500.00"),
    status: str = "APPROVED",
    order_date: str = "2026-08-01",
    sales_rep_id: str | None = None,
) -> SalesOrder:
    order = SalesOrder(
        company_id=company_id,
        customer_id=customer_id,
        order_number=f"SO-{uuid4().hex[:8]}",
        order_date=order_date,
        currency_code="USD",
        status=status,
        sales_rep_id=sales_rep_id or str(uuid4()),
        subtotal=total,
        total_amount=total,
        approval_version=1,
        version=1,
    )
    db.add(order)
    db.flush()
    return order


def _make_quotation(
    db: Session,
    company_id: UUID,
    customer_id: str,
    status: str = "CONVERTED",
    total: Decimal = Decimal("200.00"),
) -> SalesQuotation:
    q = SalesQuotation(
        company_id=company_id,
        customer_id=customer_id,
        quotation_number=f"SQ-{uuid4().hex[:8]}",
        quotation_date="2026-08-01",
        validity_date="2026-08-31",
        currency_code="USD",
        status=status,
        sales_rep_id=str(uuid4()),
        subtotal=total,
        total_amount=total,
        revision_number=1,
        version=1,
    )
    db.add(q)
    db.flush()
    return q


def _make_customer(db: Session, company_id: UUID) -> Customer:
    c = Customer(
        company_id=company_id,
        customer_code=f"C-{uuid4().hex[:6]}",
        legal_name="Test Customer",
        customer_type="COMPANY",
        category_id=str(uuid4()),
        status="ACTIVE",
        currency_code="USD",
        credit_limit=Decimal("10000"),
        credit_status="GOOD",
        version=1,
    )
    db.add(c)
    db.flush()
    return c


# ---------------------------------------------------------------------------
# ReportService tests
# ---------------------------------------------------------------------------


class TestReportService:
    def test_sales_summary_returns_rows(self, db_session: Session) -> None:
        company_id = _company()
        customer_id = _customer_id()
        _make_invoice(db_session, company_id, customer_id, Decimal("300.00"))
        _make_invoice(db_session, company_id, customer_id, Decimal("700.00"))
        db_session.flush()

        svc = ReportService(db_session)
        params = ReportParams(limit=100, offset=0)
        resp = svc.run_report(ReportType.SALES_SUMMARY, company_id, params)

        assert resp.report_type == "sales_summary"
        assert resp.company_id == str(company_id)
        assert resp.total >= 1
        assert len(resp.rows) >= 1

    def test_sales_summary_tenant_isolation(self, db_session: Session) -> None:
        company_a = _company()
        company_b = _company()
        cid = _customer_id()
        _make_invoice(db_session, company_a, cid, Decimal("500.00"))
        db_session.flush()

        svc = ReportService(db_session)
        params = ReportParams(limit=100, offset=0)
        resp_b = svc.run_report(ReportType.SALES_SUMMARY, company_b, params)

        assert resp_b.total == 0

    def test_sales_order_pipeline_shows_open_orders(self, db_session: Session) -> None:
        company_id = _company()
        cid = _customer_id()
        _make_order(db_session, company_id, cid, status="APPROVED")
        _make_order(db_session, company_id, cid, status="DRAFT")
        db_session.flush()

        svc = ReportService(db_session)
        resp = svc.run_report(
            ReportType.SALES_ORDER_PIPELINE, company_id, ReportParams()
        )

        assert resp.total >= 2
        statuses = {r["status"] for r in resp.rows}
        assert "APPROVED" in statuses

    def test_quotation_pipeline_only_open(self, db_session: Session) -> None:
        company_id = _company()
        cid = _customer_id()
        _make_quotation(db_session, company_id, cid, status="DRAFT")
        _make_quotation(db_session, company_id, cid, status="CONVERTED")
        db_session.flush()

        svc = ReportService(db_session)
        resp = svc.run_report(ReportType.QUOTATION_PIPELINE, company_id, ReportParams())

        assert resp.total == 1

    def test_expired_quotations(self, db_session: Session) -> None:
        company_id = _company()
        cid = _customer_id()
        _make_quotation(db_session, company_id, cid, status="EXPIRED")
        _make_quotation(db_session, company_id, cid, status="DRAFT")
        db_session.flush()

        svc = ReportService(db_session)
        resp = svc.run_report(ReportType.EXPIRED_QUOTATIONS, company_id, ReportParams())
        assert resp.total == 1

    def test_customer_list_returns_customers(self, db_session: Session) -> None:
        company_id = _company()
        _make_customer(db_session, company_id)
        _make_customer(db_session, company_id)
        db_session.flush()

        svc = ReportService(db_session)
        resp = svc.run_report(ReportType.CUSTOMER_LIST, company_id, ReportParams())
        assert resp.total >= 2

    def test_empty_state_no_data(self, db_session: Session) -> None:
        company_id = _company()
        svc = ReportService(db_session)
        resp = svc.run_report(ReportType.SALES_SUMMARY, company_id, ReportParams())
        assert resp.total == 0
        assert resp.rows == []

    def test_date_filter_works(self, db_session: Session) -> None:
        company_id = _company()
        cid = _customer_id()
        _make_invoice(db_session, company_id, cid, invoice_date="2026-01-15")
        _make_invoice(db_session, company_id, cid, invoice_date="2026-08-01")
        db_session.flush()

        svc = ReportService(db_session)
        params = ReportParams(date_from="2026-08-01", date_to="2026-08-31")
        resp = svc.run_report(ReportType.SALES_SUMMARY, company_id, params)
        assert resp.total == 1

    def test_pagination_limit(self, db_session: Session) -> None:
        company_id = _company()
        cid = _customer_id()
        # Use different dates so each invoice appears as a separate row in grouped summary
        for i in range(5):
            _make_invoice(db_session, company_id, cid, invoice_date=f"2026-0{i+1}-01")
        db_session.flush()

        svc = ReportService(db_session)
        params = ReportParams(limit=2, offset=0)
        resp = svc.run_report(ReportType.SALES_SUMMARY, company_id, params)
        assert len(resp.rows) == 2
        assert resp.total >= 5

    def test_all_report_types_run_without_error(self, db_session: Session) -> None:
        company_id = _company()
        svc = ReportService(db_session)
        params = ReportParams(limit=10, offset=0)
        for rtype in ReportType:
            resp = svc.run_report(rtype, company_id, params)
            assert resp.report_type == rtype.value


# ---------------------------------------------------------------------------
# KPIService tests
# ---------------------------------------------------------------------------


class TestKPIService:
    def test_dashboard_returns_12_kpis(self, db_session: Session) -> None:
        company_id = _company()
        svc = KPIService(db_session)
        dashboard = svc.get_dashboard(company_id)
        assert len(dashboard.kpis) == 12

    def test_kpi_ids_are_unique(self, db_session: Session) -> None:
        company_id = _company()
        svc = KPIService(db_session)
        dashboard = svc.get_dashboard(company_id)
        ids = [k.kpi_id for k in dashboard.kpis]
        assert len(ids) == len(set(ids))

    def test_kpi_01_revenue_with_data(self, db_session: Session) -> None:
        company_id = _company()
        cid = _customer_id()
        _make_invoice(db_session, company_id, cid, Decimal("500.00"), status="ISSUED")
        _make_invoice(db_session, company_id, cid, Decimal("300.00"), status="ISSUED")
        db_session.flush()

        svc = KPIService(db_session)
        dashboard = svc.get_dashboard(company_id)
        revenue_kpi = next(k for k in dashboard.kpis if k.kpi_id == "KPI-01")
        assert revenue_kpi.value is not None
        assert Decimal(str(revenue_kpi.value)) == Decimal("800.00")

    def test_kpi_01_revenue_no_data_is_none(self, db_session: Session) -> None:
        company_id = _company()
        svc = KPIService(db_session)
        dashboard = svc.get_dashboard(company_id)
        revenue_kpi = next(k for k in dashboard.kpis if k.kpi_id == "KPI-01")
        assert revenue_kpi.value is None

    def test_kpi_08_outstanding_orders(self, db_session: Session) -> None:
        company_id = _company()
        cid = _customer_id()
        _make_order(
            db_session, company_id, cid, total=Decimal("1000.00"), status="APPROVED"
        )
        _make_order(
            db_session,
            company_id,
            cid,
            total=Decimal("500.00"),
            status="PARTIALLY_DELIVERED",
        )
        _make_order(
            db_session, company_id, cid, total=Decimal("200.00"), status="CLOSED"
        )
        db_session.flush()

        svc = KPIService(db_session)
        dashboard = svc.get_dashboard(company_id)
        outstanding_kpi = next(k for k in dashboard.kpis if k.kpi_id == "KPI-08")
        assert outstanding_kpi.value is not None
        assert Decimal(str(outstanding_kpi.value)) == Decimal("1500.00")

    def test_kpi_03_conversion_rate_100_pct(self, db_session: Session) -> None:
        company_id = _company()
        cid = _customer_id()
        _make_quotation(db_session, company_id, cid, status="CONVERTED")
        _make_quotation(db_session, company_id, cid, status="CONVERTED")
        db_session.flush()

        svc = KPIService(db_session)
        dashboard = svc.get_dashboard(company_id)
        kpi = next(k for k in dashboard.kpis if k.kpi_id == "KPI-03")
        assert kpi.value is not None
        assert Decimal(str(kpi.value)) == Decimal("100.00")

    def test_kpi_tenant_isolation(self, db_session: Session) -> None:
        company_a = _company()
        company_b = _company()
        cid = _customer_id()
        _make_invoice(db_session, company_a, cid, Decimal("999.00"))
        db_session.flush()

        svc = KPIService(db_session)
        dash_b = svc.get_dashboard(company_b)
        revenue_kpi = next(k for k in dash_b.kpis if k.kpi_id == "KPI-01")
        assert revenue_kpi.value is None

    def test_dashboard_with_period_dates(self, db_session: Session) -> None:
        company_id = _company()
        svc = KPIService(db_session)
        dashboard = svc.get_dashboard(
            company_id, date_from="2026-08-01", date_to="2026-08-31"
        )
        assert "2026-08-01" in dashboard.period_label
        assert len(dashboard.kpis) == 12


# ---------------------------------------------------------------------------
# ReportExportService tests
# ---------------------------------------------------------------------------


class TestReportExportService:
    def test_csv_export_non_empty(self, db_session: Session) -> None:
        company_id = _company()
        cid = _customer_id()
        _make_invoice(db_session, company_id, cid)
        db_session.flush()

        report_svc = ReportService(db_session)
        export_svc = ReportExportService()
        report = report_svc.run_report(
            ReportType.SALES_SUMMARY, company_id, ReportParams()
        )
        file_bytes, filename, content_type = export_svc.export(report, ExportFormat.CSV)
        assert len(file_bytes) > 0
        assert "csv" in content_type
        assert filename.endswith(".csv")
        # CSV should have at least a header line
        content = file_bytes.decode("utf-8")
        assert "\n" in content

    def test_csv_export_empty_report(self, db_session: Session) -> None:
        company_id = _company()
        report_svc = ReportService(db_session)
        export_svc = ReportExportService()
        report = report_svc.run_report(
            ReportType.SALES_SUMMARY, company_id, ReportParams()
        )
        file_bytes, filename, content_type = export_svc.export(report, ExportFormat.CSV)
        assert isinstance(file_bytes, bytes)
