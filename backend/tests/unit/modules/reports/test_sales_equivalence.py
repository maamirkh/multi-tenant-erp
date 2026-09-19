"""T071 — ``ReportService.run_report()``/``KPIService.get_dashboard()``
called directly vs. ``SalesAdapter.run()`` output — identical for
``sales.summary``/``sales.kpis``.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.reports.schemas.sales import SalesKpiFilter, SalesSummaryFilter
from modules.reports.services.adapters.base import (
    AggregateReportResult,
    PaginatedReportResult,
)
from modules.reports.services.adapters.sales_adapter import SalesAdapter
from modules.sales.dependencies import get_kpi_service, get_report_service
from modules.sales.models.invoice import SalesInvoice
from modules.sales.schemas.reports import ReportParams, ReportType


def _seed_invoice(db: Session, company_id: uuid.UUID, *, amount: str) -> None:
    db.add(
        SalesInvoice(
            company_id=company_id,
            invoice_number=f"INV-{uuid.uuid4().hex[:8]}",
            customer_id=str(uuid.uuid4()),
            invoice_date="2026-01-15",
            due_date="2026-02-14",
            currency_code="USD",
            status="ISSUED",
            subtotal=Decimal(amount),
            discount_amount=Decimal("0"),
            tax_amount=Decimal("0"),
            charges_amount=Decimal("0"),
            total_amount=Decimal(amount),
            version=1,
        )
    )


def test_sales_summary_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    _seed_invoice(db_session, company_id, amount="100.00")
    _seed_invoice(db_session, company_id, amount="200.00")
    db_session.commit()

    reports = get_report_service(db_session)
    direct = reports.run_report(ReportType("sales_summary"), company_id, ReportParams())

    adapter = SalesAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "sales.summary",
        SalesSummaryFilter(),
        page=1,
        page_size=20,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, PaginatedReportResult)
    assert result.total == direct.total
    assert len(result.items) == len(direct.rows)
    assert result.items[0].revenue == Decimal(str(direct.rows[0]["revenue"]))


def test_sales_kpis_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    _seed_invoice(db_session, company_id, amount="150.00")
    db_session.commit()

    kpis = get_kpi_service(db_session)
    direct = kpis.get_dashboard(company_id, date_from=None, date_to=None)

    adapter = SalesAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "sales.kpis",
        SalesKpiFilter(),
        page=1,
        page_size=1,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, AggregateReportResult)
    assert result.data.kpis[0].value == direct.kpis[0].value
    assert len(result.data.kpis) == len(direct.kpis) == 12
