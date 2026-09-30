"""``ReportParams.group_by_currency`` (Epic 11 FR-RPT-152, T297) and the
per-currency money KPIs (T298).

Off (the default), every revenue aggregate is exactly what it was before —
Sales' own report screens are unchanged. On, amounts in different
currencies land in separate rows and are never summed together.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from modules.sales.models.invoice import SalesInvoice
from modules.sales.models.order import OrderLine, SalesOrder
from modules.sales.models.sales_return import SalesReturn
from modules.sales.schemas.reports import KPIType, ReportParams, ReportType
from modules.sales.services.kpi_service import KPIService
from modules.sales.services.report_service import ReportService

DAY = "2026-08-01"


def _invoice(
    db: Session, company_id: UUID, customer_id: str, amount: str, currency: str
) -> SalesInvoice:
    invoice = SalesInvoice(
        company_id=company_id,
        customer_id=customer_id,
        invoice_number=f"SI-{uuid4().hex[:8]}",
        invoice_date=DAY,
        due_date="2026-09-01",
        currency_code=currency,
        status="ISSUED",
        subtotal=Decimal(amount),
        discount_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        charges_amount=Decimal("0"),
        total_amount=Decimal(amount),
    )
    db.add(invoice)
    db.flush()
    return invoice


def _order_line(
    db: Session, company_id: UUID, product_id: str, amount: str, currency: str
) -> None:
    order = SalesOrder(
        company_id=company_id,
        customer_id=str(uuid4()),
        order_number=f"SO-{uuid4().hex[:8]}",
        order_date=DAY,
        currency_code=currency,
        status="DELIVERED",
        sales_rep_id=str(uuid4()),
        subtotal=Decimal(amount),
        total_amount=Decimal(amount),
        approval_version=1,
        version=1,
    )
    db.add(order)
    db.flush()
    db.add(
        OrderLine(
            company_id=company_id,
            order_id=str(order.id),
            line_number=1,
            product_id=product_id,
            description="Widget",
            quantity_ordered=Decimal("1"),
            quantity_delivered=Decimal("1"),
            unit_of_measure="EA",
            unit_price=Decimal(amount),
            extended_amount=Decimal(amount),
            delivery_status="DELIVERED",
        )
    )
    db.flush()


def _run(
    db: Session, company_id: UUID, report: ReportType, *, grouped: bool
) -> list[dict[str, object]]:
    params = ReportParams(group_by_currency=grouped) if grouped else ReportParams()
    return ReportService(db).run_report(report, company_id, params).rows


def _seed(db: Session) -> UUID:
    company_id = uuid4()
    customer = str(uuid4())
    product = str(uuid4())
    _invoice(db, company_id, customer, "100.00", "USD")
    _invoice(db, company_id, customer, "5000.00", "PKR")
    _order_line(db, company_id, product, "100.00", "USD")
    _order_line(db, company_id, product, "5000.00", "PKR")
    return company_id


def test_default_output_is_unchanged(db_session: Session) -> None:
    company_id = _seed(db_session)

    summary = _run(db_session, company_id, ReportType.SALES_SUMMARY, grouped=False)
    by_customer = _run(
        db_session, company_id, ReportType.SALES_BY_CUSTOMER, grouped=False
    )
    by_product = _run(
        db_session, company_id, ReportType.SALES_BY_PRODUCT, grouped=False
    )

    # One row each, amounts summed, and no currency key — exactly the
    # pre-existing behaviour Sales' own screens rely on.
    assert [Decimal(str(r["revenue"])) for r in summary] == [Decimal("5100.00")]
    assert [Decimal(str(r["revenue"])) for r in by_customer] == [Decimal("5100.00")]
    assert [Decimal(str(r["revenue"])) for r in by_product] == [Decimal("5100.00")]
    for rows in (summary, by_customer, by_product):
        assert "currency_code" not in rows[0]


def test_grouped_output_never_sums_across_currencies(db_session: Session) -> None:
    company_id = _seed(db_session)

    for report in (
        ReportType.SALES_SUMMARY,
        ReportType.SALES_TREND,
        ReportType.SALES_BY_CUSTOMER,
        ReportType.TOP_CUSTOMERS,
        ReportType.SALES_BY_PRODUCT,
    ):
        rows = _run(db_session, company_id, report, grouped=True)
        by_currency = {r["currency_code"]: Decimal(str(r["revenue"])) for r in rows}
        assert by_currency == {
            "USD": Decimal("100.00"),
            "PKR": Decimal("5000.00"),
        }, report


def test_money_kpis_are_per_currency(db_session: Session) -> None:
    company_id = uuid4()
    customer = str(uuid4())
    _invoice(db_session, company_id, customer, "100.00", "USD")
    pkr = _invoice(db_session, company_id, customer, "5000.00", "PKR")
    # A completed return has no currency of its own: it takes its invoice's.
    db_session.add(
        SalesReturn(
            company_id=company_id,
            return_number=f"RT-{uuid4().hex[:8]}",
            customer_id=customer,
            invoice_id=str(pkr.id),
            return_date=DAY,
            reason_code_id=str(uuid4()),
            resolution_type="CREDIT_NOTE",
            status="COMPLETED",
            credit_note_amount=Decimal("500.00"),
            approval_version=1,
            version=1,
        )
    )
    db_session.flush()
    svc = KPIService(db_session)

    assert svc.currencies_in_period(company_id, DAY, DAY) == ["PKR", "USD"]
    by_currency = {
        code: {k.kpi_id: k for k in svc.get_money_kpis(company_id, code, DAY, DAY)}
        for code in ("USD", "PKR")
    }
    revenue = KPIType.REVENUE.value
    returns = KPIType.RETURN_RATE.value
    assert by_currency["USD"][revenue].value == Decimal("100.00")
    assert by_currency["USD"][revenue].unit == "USD"
    assert by_currency["PKR"][revenue].value == Decimal("5000.00")
    assert by_currency["PKR"][revenue].unit == "PKR"
    # 500 PKR returned of 5000 PKR revenue — the USD block has no return.
    assert by_currency["PKR"][returns].value == Decimal("10.00")
    assert by_currency["USD"][returns].value is None
    # get_dashboard() itself is unchanged: one cross-currency figure.
    dashboard = {k.kpi_id: k for k in svc.get_dashboard(company_id, DAY, DAY).kpis}
    assert dashboard[revenue].value == Decimal("5100.00")
