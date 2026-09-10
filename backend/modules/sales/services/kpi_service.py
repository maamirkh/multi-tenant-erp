"""Sales KPI Service — Phase 8.

Computes 12 KPIs per spec §36:

  KPI-01  Revenue                   Sum of ISSUED/PAID invoice totals
  KPI-02  Gross Margin %            (Revenue - COGS) / Revenue × 100
  KPI-03  Quotation Conversion Rate Converted / Total × 100
  KPI-04  AOV                       Revenue / Number of invoices
  KPI-05  Sales Growth Rate         (Current - Previous) / Previous × 100
  KPI-06  Customer Retention Rate   Repeat customers / Total × 100
  KPI-07  On-Time Delivery Rate     On-time / Total delivered × 100
  KPI-08  Outstanding Orders Value  Sum of APPROVED undelivered orders
  KPI-09  Return Rate               Returned value / Revenue × 100
  KPI-10  Avg Days to Fulfil        Avg days: order_date → dispatch_date
  KPI-11  Credit Utilisation        outstanding_balance / credit_limit × 100
  KPI-12  Invoice Cycle Time        Avg days: dispatch_date → invoice_date

Period window: date_from / date_to (ISO 8601 strings); defaults to current calendar month.
All queries are tenant-scoped by company_id and respect soft-delete.

Task: T211
Spec ref: specs/007-sales-management/spec.md §36
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from modules.sales.models.delivery import DeliveryNote
from modules.sales.models.invoice import SalesInvoice
from modules.sales.models.order import SalesOrder
from modules.sales.models.quotation import SalesQuotation
from modules.sales.models.sales_return import SalesReturn
from modules.sales.schemas.reports import KPIDashboard, KPIResult, KPIType

log = logging.getLogger(__name__)

_TWO = Decimal("0.01")


def _pct(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return (numerator / denominator * 100).quantize(_TWO, rounding=ROUND_HALF_UP)


def _div(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return (numerator / denominator).quantize(_TWO, rounding=ROUND_HALF_UP)


def _trend(
    current: Decimal | None, previous: Decimal | None
) -> tuple[str | None, Decimal | None]:
    if current is None or previous is None:
        return None, None
    if previous == 0:
        return ("UP" if current > 0 else "STABLE"), None
    change = _pct(current - previous, previous)
    if change is None:
        return None, None
    if change > Decimal("2"):
        return "UP", change
    if change < Decimal("-2"):
        return "DOWN", change
    return "STABLE", change


def _period_label(date_from: str | None, date_to: str | None) -> str:
    if date_from and date_to:
        return f"{date_from} – {date_to}"
    today = date.today()
    return today.strftime("%Y-%m")


def _prev_period(date_from: str | None, date_to: str | None) -> tuple[str, str]:
    """Return the previous period of equal length."""
    if date_from and date_to:
        d_from = date.fromisoformat(date_from)
        d_to = date.fromisoformat(date_to)
        delta = d_to - d_from + timedelta(days=1)
        prev_to = d_from - timedelta(days=1)
        prev_from = prev_to - delta + timedelta(days=1)
        return prev_from.isoformat(), prev_to.isoformat()
    today = date.today()
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev.isoformat(), last_prev.isoformat()


# ---------------------------------------------------------------------------
# KPIService
# ---------------------------------------------------------------------------


class KPIService:
    """Compute all 12 sales KPIs for a company and time period."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_dashboard(
        self,
        company_id: str | UUID,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> KPIDashboard:
        # Normalise to UUID object for SQLAlchemy Uuid(as_uuid=True) columns
        company_id = (
            UUID(str(company_id)) if not isinstance(company_id, UUID) else company_id
        )
        """Compute all 12 KPIs and return a KPIDashboard."""
        label = _period_label(date_from, date_to)
        prev_from, prev_to = _prev_period(date_from, date_to)

        kpis = [
            self._kpi_revenue(
                company_id, date_from, date_to, prev_from, prev_to, label
            ),
            self._kpi_gross_margin(company_id, date_from, date_to, label),
            self._kpi_quotation_conversion(
                company_id, date_from, date_to, prev_from, prev_to, label
            ),
            self._kpi_aov(company_id, date_from, date_to, prev_from, prev_to, label),
            self._kpi_sales_growth(
                company_id, date_from, date_to, prev_from, prev_to, label
            ),
            self._kpi_customer_retention(company_id, date_from, date_to, label),
            self._kpi_on_time_delivery(company_id, date_from, date_to, label),
            self._kpi_outstanding_orders(company_id, label),
            self._kpi_return_rate(company_id, date_from, date_to, label),
            self._kpi_avg_days_to_fulfil(company_id, date_from, date_to, label),
            self._kpi_credit_utilisation(company_id, label),
            self._kpi_invoice_cycle_time(company_id, date_from, date_to, label),
        ]
        return KPIDashboard(company_id=str(company_id), period_label=label, kpis=kpis)

    # -----------------------------------------------------------------------
    # KPI-01: Revenue
    # -----------------------------------------------------------------------

    def _kpi_revenue(
        self,
        company_id: UUID,
        date_from: str | None,
        date_to: str | None,
        prev_from: str,
        prev_to: str,
        label: str,
    ) -> KPIResult:
        cur = self._invoice_revenue(company_id, date_from, date_to)
        prev = self._invoice_revenue(company_id, prev_from, prev_to)
        t, chg = _trend(cur, prev)
        return KPIResult(
            kpi_id=KPIType.REVENUE.value,
            name="Revenue",
            value=cur,
            unit="USD",
            period_label=label,
            trend=t,
            change_pct=chg,
        )

    def _invoice_revenue(
        self, company_id: UUID, date_from: str | None, date_to: str | None
    ) -> Decimal | None:
        q = self._db.query(func.sum(SalesInvoice.total_amount)).filter(
            SalesInvoice.company_id == company_id,
            SalesInvoice.is_deleted.is_(False),
            SalesInvoice.status.in_(["ISSUED", "PAID"]),
        )
        if date_from:
            q = q.filter(SalesInvoice.invoice_date >= date_from)
        if date_to:
            q = q.filter(SalesInvoice.invoice_date <= date_to)
        result: Decimal | None = q.scalar()
        return result

    # -----------------------------------------------------------------------
    # KPI-02: Gross Margin %
    # -----------------------------------------------------------------------

    def _kpi_gross_margin(
        self, company_id: UUID, date_from: str | None, date_to: str | None, label: str
    ) -> KPIResult:
        # COGS not stored — gross margin cannot be fully computed.
        # Return null with an informative note.
        return KPIResult(
            kpi_id=KPIType.GROSS_MARGIN_PCT.value,
            name="Gross Margin %",
            value=None,
            unit="%",
            period_label=label,
            trend=None,
            change_pct=None,
        )

    # -----------------------------------------------------------------------
    # KPI-03: Quotation Conversion Rate
    # -----------------------------------------------------------------------

    def _kpi_quotation_conversion(
        self,
        company_id: UUID,
        date_from: str | None,
        date_to: str | None,
        prev_from: str,
        prev_to: str,
        label: str,
    ) -> KPIResult:
        cur = self._conversion_rate(company_id, date_from, date_to)
        prev = self._conversion_rate(company_id, prev_from, prev_to)
        t, chg = _trend(cur, prev)
        return KPIResult(
            kpi_id=KPIType.QUOTATION_CONVERSION_RATE.value,
            name="Quotation Conversion Rate",
            value=cur,
            unit="%",
            period_label=label,
            trend=t,
            change_pct=chg,
        )

    def _conversion_rate(
        self, company_id: UUID, date_from: str | None, date_to: str | None
    ) -> Decimal | None:
        q = self._db.query(SalesQuotation.status).filter(
            SalesQuotation.company_id == company_id,
            SalesQuotation.is_deleted.is_(False),
        )
        if date_from:
            q = q.filter(SalesQuotation.quotation_date >= date_from)
        if date_to:
            q = q.filter(SalesQuotation.quotation_date <= date_to)
        rows = q.all()
        total = len(rows)
        converted = sum(1 for r in rows if r.status == "CONVERTED")
        return _pct(Decimal(converted), Decimal(total))

    # -----------------------------------------------------------------------
    # KPI-04: Average Order Value
    # -----------------------------------------------------------------------

    def _kpi_aov(
        self,
        company_id: UUID,
        date_from: str | None,
        date_to: str | None,
        prev_from: str,
        prev_to: str,
        label: str,
    ) -> KPIResult:
        cur = self._aov(company_id, date_from, date_to)
        prev = self._aov(company_id, prev_from, prev_to)
        t, chg = _trend(cur, prev)
        return KPIResult(
            kpi_id=KPIType.AOV.value,
            name="Average Order Value",
            value=cur,
            unit="USD",
            period_label=label,
            trend=t,
            change_pct=chg,
        )

    def _aov(
        self, company_id: UUID, date_from: str | None, date_to: str | None
    ) -> Decimal | None:
        q = self._db.query(
            func.sum(SalesInvoice.total_amount),
            func.count(SalesInvoice.id),
        ).filter(
            SalesInvoice.company_id == company_id,
            SalesInvoice.is_deleted.is_(False),
            SalesInvoice.status.in_(["ISSUED", "PAID"]),
        )
        if date_from:
            q = q.filter(SalesInvoice.invoice_date >= date_from)
        if date_to:
            q = q.filter(SalesInvoice.invoice_date <= date_to)
        total_rev, count = q.one()
        return _div(total_rev, Decimal(count) if count else None)

    # -----------------------------------------------------------------------
    # KPI-05: Sales Growth Rate
    # -----------------------------------------------------------------------

    def _kpi_sales_growth(
        self,
        company_id: UUID,
        date_from: str | None,
        date_to: str | None,
        prev_from: str,
        prev_to: str,
        label: str,
    ) -> KPIResult:
        cur = self._invoice_revenue(company_id, date_from, date_to)
        prev = self._invoice_revenue(company_id, prev_from, prev_to)
        growth = None
        if cur is not None and prev is not None and prev != 0:
            growth = _pct(cur - prev, prev)
        t, _ = _trend(cur, prev)
        return KPIResult(
            kpi_id=KPIType.SALES_GROWTH_RATE.value,
            name="Sales Growth Rate",
            value=growth,
            unit="%",
            period_label=label,
            trend=t,
            change_pct=growth,
        )

    # -----------------------------------------------------------------------
    # KPI-06: Customer Retention Rate
    # -----------------------------------------------------------------------

    def _kpi_customer_retention(
        self, company_id: UUID, date_from: str | None, date_to: str | None, label: str
    ) -> KPIResult:
        # Customers who ordered in both this period and a prior period
        all_q = self._db.query(SalesOrder.customer_id).filter(
            SalesOrder.company_id == company_id,
            SalesOrder.is_deleted.is_(False),
        )
        if date_from:
            all_q = all_q.filter(SalesOrder.order_date >= date_from)
        if date_to:
            all_q = all_q.filter(SalesOrder.order_date <= date_to)
        current_customers = {r.customer_id for r in all_q.all()}

        repeat_q = self._db.query(SalesOrder.customer_id).filter(
            SalesOrder.company_id == company_id,
            SalesOrder.is_deleted.is_(False),
        )
        if date_from:
            repeat_q = repeat_q.filter(SalesOrder.order_date < date_from)
        prior_customers = {r.customer_id for r in repeat_q.all()}

        if not current_customers:
            value = None
        else:
            repeat_count = len(current_customers & prior_customers)
            value = _pct(Decimal(repeat_count), Decimal(len(current_customers)))

        return KPIResult(
            kpi_id=KPIType.CUSTOMER_RETENTION_RATE.value,
            name="Customer Retention Rate",
            value=value,
            unit="%",
            period_label=label,
        )

    # -----------------------------------------------------------------------
    # KPI-07: On-Time Delivery Rate
    # -----------------------------------------------------------------------

    def _kpi_on_time_delivery(
        self, company_id: UUID, date_from: str | None, date_to: str | None, label: str
    ) -> KPIResult:
        q = self._db.query(
            DeliveryNote.dispatch_date,
            DeliveryNote.expected_delivery_date,
        ).filter(
            DeliveryNote.company_id == company_id,
            DeliveryNote.is_deleted.is_(False),
            DeliveryNote.status == "DELIVERED",
            DeliveryNote.dispatch_date.isnot(None),
            DeliveryNote.expected_delivery_date.isnot(None),
        )
        if date_from:
            q = q.filter(DeliveryNote.dispatch_date >= date_from)
        if date_to:
            q = q.filter(DeliveryNote.dispatch_date <= date_to)
        rows = q.all()
        total = len(rows)
        on_time = sum(1 for r in rows if r.dispatch_date <= r.expected_delivery_date)
        value = _pct(Decimal(on_time), Decimal(total)) if total else None
        return KPIResult(
            kpi_id=KPIType.ON_TIME_DELIVERY_RATE.value,
            name="On-Time Delivery Rate",
            value=value,
            unit="%",
            period_label=label,
        )

    # -----------------------------------------------------------------------
    # KPI-08: Outstanding Orders Value
    # -----------------------------------------------------------------------

    def _kpi_outstanding_orders(self, company_id: UUID, label: str) -> KPIResult:
        value = (
            self._db.query(func.sum(SalesOrder.total_amount))
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.is_deleted.is_(False),
                SalesOrder.status.in_(["APPROVED", "PARTIALLY_DELIVERED"]),
            )
            .scalar()
        )
        return KPIResult(
            kpi_id=KPIType.OUTSTANDING_ORDERS_VALUE.value,
            name="Outstanding Orders Value",
            value=value,
            unit="USD",
            period_label=label,
        )

    # -----------------------------------------------------------------------
    # KPI-09: Return Rate
    # -----------------------------------------------------------------------

    def _kpi_return_rate(
        self, company_id: UUID, date_from: str | None, date_to: str | None, label: str
    ) -> KPIResult:
        # Return value for COMPLETED returns
        ret_q = self._db.query(func.sum(SalesReturn.credit_note_amount)).filter(
            SalesReturn.company_id == company_id,
            SalesReturn.is_deleted.is_(False),
            SalesReturn.status == "COMPLETED",
        )
        if date_from:
            ret_q = ret_q.filter(SalesReturn.return_date >= date_from)
        if date_to:
            ret_q = ret_q.filter(SalesReturn.return_date <= date_to)
        returned = ret_q.scalar()

        revenue = self._invoice_revenue(company_id, date_from, date_to)
        value = _pct(returned, revenue)
        return KPIResult(
            kpi_id=KPIType.RETURN_RATE.value,
            name="Return Rate",
            value=value,
            unit="%",
            period_label=label,
        )

    # -----------------------------------------------------------------------
    # KPI-10: Avg Days to Fulfil
    # -----------------------------------------------------------------------

    def _kpi_avg_days_to_fulfil(
        self, company_id: UUID, date_from: str | None, date_to: str | None, label: str
    ) -> KPIResult:
        q = (
            self._db.query(
                SalesOrder.order_date,
                DeliveryNote.dispatch_date,
            )
            .join(DeliveryNote, DeliveryNote.order_id == SalesOrder.id)
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.is_deleted.is_(False),
                DeliveryNote.is_deleted.is_(False),
                SalesOrder.order_date.isnot(None),
                DeliveryNote.dispatch_date.isnot(None),
                DeliveryNote.status == "DELIVERED",
            )
        )
        if date_from:
            q = q.filter(SalesOrder.order_date >= date_from)
        if date_to:
            q = q.filter(SalesOrder.order_date <= date_to)
        rows = q.all()
        if not rows:
            value = None
        else:
            total_days = 0
            valid = 0
            for r in rows:
                try:
                    d_order = date.fromisoformat(r.order_date)
                    d_dispatch = date.fromisoformat(r.dispatch_date)
                    total_days += (d_dispatch - d_order).days
                    valid += 1
                except (ValueError, TypeError):
                    pass
            value = _div(Decimal(total_days), Decimal(valid)) if valid else None
        return KPIResult(
            kpi_id=KPIType.AVG_DAYS_TO_FULFIL.value,
            name="Avg Days to Fulfil",
            value=value,
            unit="days",
            period_label=label,
        )

    # -----------------------------------------------------------------------
    # KPI-11: Credit Utilisation
    # -----------------------------------------------------------------------

    def _kpi_credit_utilisation(self, company_id: UUID, label: str) -> KPIResult:
        # outstanding_balance not stored on Customer; return null
        value = None
        return KPIResult(
            kpi_id=KPIType.CREDIT_UTILISATION.value,
            name="Credit Utilisation",
            value=value,
            unit="%",
            period_label=label,
        )

    # -----------------------------------------------------------------------
    # KPI-12: Invoice Cycle Time
    # -----------------------------------------------------------------------

    def _kpi_invoice_cycle_time(
        self, company_id: UUID, date_from: str | None, date_to: str | None, label: str
    ) -> KPIResult:
        """Avg days from dispatch_date → invoice_date."""
        q = (
            self._db.query(
                DeliveryNote.dispatch_date,
                SalesInvoice.invoice_date,
            )
            .join(SalesInvoice, SalesInvoice.delivery_note_id == DeliveryNote.id)
            .filter(
                DeliveryNote.company_id == company_id,
                DeliveryNote.is_deleted.is_(False),
                SalesInvoice.is_deleted.is_(False),
                DeliveryNote.dispatch_date.isnot(None),
                SalesInvoice.invoice_date.isnot(None),
                SalesInvoice.status.in_(["ISSUED", "PAID"]),
            )
        )
        if date_from:
            q = q.filter(SalesInvoice.invoice_date >= date_from)
        if date_to:
            q = q.filter(SalesInvoice.invoice_date <= date_to)
        rows = q.all()
        if not rows:
            value = None
        else:
            total_days = 0
            valid = 0
            for r in rows:
                try:
                    d_dispatch = date.fromisoformat(r.dispatch_date)
                    d_invoice = date.fromisoformat(r.invoice_date)
                    total_days += (d_invoice - d_dispatch).days
                    valid += 1
                except (ValueError, TypeError):
                    pass
            value = _div(Decimal(total_days), Decimal(valid)) if valid else None
        return KPIResult(
            kpi_id=KPIType.INVOICE_CYCLE_TIME.value,
            name="Invoice Cycle Time",
            value=value,
            unit="days",
            period_label=label,
        )
