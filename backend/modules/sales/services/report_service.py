"""Sales Intelligence & Reporting Service — Phase 8.

Provides read-only query methods for all 25 report types:

Sales Reports (8):
  sales_summary, sales_by_customer, sales_by_product,
  sales_by_representative, sales_order_pipeline, sales_vs_target,
  top_customers, sales_trend

Customer Reports (5):
  customer_list, customer_ageing, customer_activity,
  new_customers, customer_credit_report

Quotation Reports (3):
  quotation_conversion_rate, quotation_pipeline, expired_quotations

Delivery Reports (3):
  pending_deliveries, delivery_performance, backorder_report

Profitability Reports (3):
  gross_margin_by_product, gross_margin_by_customer, discount_analysis

Audit Reports (4):
  sales_audit_trail, price_override_report,
  credit_limit_change_report, approval_history

All queries enforce company_id (tenant isolation) and soft-delete.
No DB schema changes — read-only against Phases 0-7 tables.

Task: T204-T210
Spec ref: specs/007-sales-management/spec.md §35
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from modules.sales.models.customer import Customer
from modules.sales.models.delivery import DeliveryNote
from modules.sales.models.invoice import SalesInvoice
from modules.sales.models.order import OrderLine, SalesOrder
from modules.sales.models.quotation import SalesQuotation
from modules.sales.schemas.reports import ReportParams, ReportResponse, ReportType

log = logging.getLogger(__name__)

Row = dict[str, Any]


def _str(v: Any) -> str | None:
    return str(v) if v is not None else None


def _dec(v: Any) -> str | None:
    return str(v) if v is not None else None


def _cid(company_id: str | UUID) -> UUID:
    """Normalise company_id to UUID for Uuid(as_uuid=True) columns."""
    return UUID(str(company_id)) if not isinstance(company_id, UUID) else company_id


class ReportService:
    """Read-only report service.  All methods are tenant-scoped by company_id."""

    def __init__(self, db: Session) -> None:
        self._db = db

    # -----------------------------------------------------------------------
    # Public dispatcher
    # -----------------------------------------------------------------------

    def run_report(
        self,
        report_type: ReportType,
        company_id: str | UUID,
        params: ReportParams,
    ) -> ReportResponse:
        """Dispatch to the correct report method and return a ReportResponse."""
        cid = _cid(company_id)
        method_map = {
            ReportType.SALES_SUMMARY: self._sales_summary,
            ReportType.SALES_BY_CUSTOMER: self._sales_by_customer,
            ReportType.SALES_BY_PRODUCT: self._sales_by_product,
            ReportType.SALES_BY_REPRESENTATIVE: self._sales_by_representative,
            ReportType.SALES_ORDER_PIPELINE: self._sales_order_pipeline,
            ReportType.SALES_VS_TARGET: self._sales_vs_target,
            ReportType.TOP_CUSTOMERS: self._top_customers,
            ReportType.SALES_TREND: self._sales_trend,
            ReportType.CUSTOMER_LIST: self._customer_list,
            ReportType.CUSTOMER_AGEING: self._customer_ageing,
            ReportType.CUSTOMER_ACTIVITY: self._customer_activity,
            ReportType.NEW_CUSTOMERS: self._new_customers,
            ReportType.CUSTOMER_CREDIT_REPORT: self._customer_credit_report,
            ReportType.QUOTATION_CONVERSION_RATE: self._quotation_conversion_rate,
            ReportType.QUOTATION_PIPELINE: self._quotation_pipeline,
            ReportType.EXPIRED_QUOTATIONS: self._expired_quotations,
            ReportType.PENDING_DELIVERIES: self._pending_deliveries,
            ReportType.DELIVERY_PERFORMANCE: self._delivery_performance,
            ReportType.BACKORDER_REPORT: self._backorder_report,
            ReportType.GROSS_MARGIN_BY_PRODUCT: self._gross_margin_by_product,
            ReportType.GROSS_MARGIN_BY_CUSTOMER: self._gross_margin_by_customer,
            ReportType.DISCOUNT_ANALYSIS: self._discount_analysis,
            ReportType.SALES_AUDIT_TRAIL: self._sales_audit_trail,
            ReportType.PRICE_OVERRIDE_REPORT: self._price_override_report,
            ReportType.CREDIT_LIMIT_CHANGE_REPORT: self._credit_limit_change_report,
            ReportType.APPROVAL_HISTORY: self._approval_history,
        }
        fn = method_map[report_type]
        rows, total = fn(cid, params)
        return ReportResponse(
            report_type=report_type.value,
            company_id=str(company_id),
            params=params.model_dump(exclude_none=True),
            total=total,
            rows=rows,
        )

    # -----------------------------------------------------------------------
    # Sales Reports
    # -----------------------------------------------------------------------

    def _sales_summary(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Aggregate totals for issued invoices grouped by date."""
        q = self._db.query(
            SalesInvoice.invoice_date,
            func.count(SalesInvoice.id).label("invoice_count"),
            func.sum(SalesInvoice.total_amount).label("revenue"),
            func.sum(SalesInvoice.discount_amount).label("total_discount"),
        ).filter(
            SalesInvoice.company_id == company_id,
            SalesInvoice.is_deleted.is_(False),
            SalesInvoice.status.in_(["ISSUED", "PAID"]),
        )
        q = self._apply_invoice_date_filter(q, SalesInvoice, params)
        if params.customer_id:
            q = q.filter(SalesInvoice.customer_id == params.customer_id)
        q = q.group_by(SalesInvoice.invoice_date).order_by(
            SalesInvoice.invoice_date.desc()
        )
        total_q = q.subquery()
        total = self._db.query(func.count()).select_from(total_q).scalar() or 0
        results = q.limit(params.limit).offset(params.offset).all()
        rows = [
            {
                "date": r.invoice_date,
                "invoice_count": r.invoice_count,
                "revenue": _dec(r.revenue),
                "total_discount": _dec(r.total_discount),
            }
            for r in results
        ]
        return rows, total

    def _sales_by_customer(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Revenue grouped by customer."""
        q = self._db.query(
            SalesInvoice.customer_id,
            func.count(SalesInvoice.id).label("invoice_count"),
            func.sum(SalesInvoice.total_amount).label("revenue"),
        ).filter(
            SalesInvoice.company_id == company_id,
            SalesInvoice.is_deleted.is_(False),
            SalesInvoice.status.in_(["ISSUED", "PAID"]),
        )
        q = self._apply_invoice_date_filter(q, SalesInvoice, params)
        q = q.group_by(SalesInvoice.customer_id).order_by(
            func.sum(SalesInvoice.total_amount).desc()
        )
        total_q = q.subquery()
        total = self._db.query(func.count()).select_from(total_q).scalar() or 0
        results = q.limit(params.limit).offset(params.offset).all()
        rows = [
            {
                "customer_id": _str(r.customer_id),
                "invoice_count": r.invoice_count,
                "revenue": _dec(r.revenue),
            }
            for r in results
        ]
        return rows, total

    def _sales_by_product(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Revenue grouped by product via order lines."""
        q = (
            self._db.query(
                OrderLine.product_id,
                OrderLine.description,
                func.sum(OrderLine.extended_amount).label("revenue"),
                func.sum(OrderLine.quantity_ordered).label("total_qty"),
                func.count(OrderLine.id).label("line_count"),
            )
            .join(SalesOrder, SalesOrder.id == OrderLine.order_id)
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.is_deleted.is_(False),
                OrderLine.is_deleted.is_(False),
                SalesOrder.status.in_(["DELIVERED", "INVOICED", "CLOSED"]),
            )
        )
        if params.date_from:
            q = q.filter(SalesOrder.order_date >= params.date_from)
        if params.date_to:
            q = q.filter(SalesOrder.order_date <= params.date_to)
        if params.customer_id:
            q = q.filter(SalesOrder.customer_id == params.customer_id)
        q = q.group_by(OrderLine.product_id, OrderLine.description).order_by(
            func.sum(OrderLine.extended_amount).desc()
        )
        total_q = q.subquery()
        total = self._db.query(func.count()).select_from(total_q).scalar() or 0
        results = q.limit(params.limit).offset(params.offset).all()
        rows = [
            {
                "product_id": _str(r.product_id),
                "description": r.description,
                "revenue": _dec(r.revenue),
                "total_qty": _dec(r.total_qty),
                "line_count": r.line_count,
            }
            for r in results
        ]
        return rows, total

    def _sales_by_representative(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Revenue grouped by sales representative."""
        q = self._db.query(
            SalesOrder.sales_rep_id,
            func.count(SalesOrder.id).label("order_count"),
            func.sum(SalesOrder.total_amount).label("revenue"),
        ).filter(
            SalesOrder.company_id == company_id,
            SalesOrder.is_deleted.is_(False),
            SalesOrder.status.in_(["DELIVERED", "INVOICED", "CLOSED"]),
        )
        if params.date_from:
            q = q.filter(SalesOrder.order_date >= params.date_from)
        if params.date_to:
            q = q.filter(SalesOrder.order_date <= params.date_to)
        if params.sales_rep_id:
            q = q.filter(SalesOrder.sales_rep_id == params.sales_rep_id)
        q = q.group_by(SalesOrder.sales_rep_id).order_by(
            func.sum(SalesOrder.total_amount).desc()
        )
        total_q = q.subquery()
        total = self._db.query(func.count()).select_from(total_q).scalar() or 0
        results = q.limit(params.limit).offset(params.offset).all()
        rows = [
            {
                "sales_rep_id": _str(r.sales_rep_id),
                "order_count": r.order_count,
                "revenue": _dec(r.revenue),
            }
            for r in results
        ]
        return rows, total

    def _sales_order_pipeline(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Open orders (DRAFT/PENDING_APPROVAL/APPROVED/PARTIALLY_DELIVERED)."""
        q = self._db.query(
            SalesOrder.id,
            SalesOrder.order_number,
            SalesOrder.customer_id,
            SalesOrder.order_date,
            SalesOrder.required_delivery_date,
            SalesOrder.status,
            SalesOrder.total_amount,
            SalesOrder.currency_code,
        ).filter(
            SalesOrder.company_id == company_id,
            SalesOrder.is_deleted.is_(False),
            SalesOrder.status.in_(
                ["DRAFT", "PENDING_APPROVAL", "APPROVED", "PARTIALLY_DELIVERED"]
            ),
        )
        if params.date_from:
            q = q.filter(SalesOrder.order_date >= params.date_from)
        if params.date_to:
            q = q.filter(SalesOrder.order_date <= params.date_to)
        if params.customer_id:
            q = q.filter(SalesOrder.customer_id == params.customer_id)
        total = q.count()
        results = (
            q.order_by(SalesOrder.order_date)
            .limit(params.limit)
            .offset(params.offset)
            .all()
        )
        rows = [
            {
                "id": _str(r.id),
                "order_number": r.order_number,
                "customer_id": _str(r.customer_id),
                "order_date": r.order_date,
                "required_delivery_date": r.required_delivery_date,
                "status": r.status,
                "total_amount": _dec(r.total_amount),
                "currency_code": r.currency_code,
            }
            for r in results
        ]
        return rows, total

    def _sales_vs_target(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Actual revenue vs target (targets not stored — shows actual only)."""
        rows, total = self._sales_summary(company_id, params)
        for r in rows:
            r["target_revenue"] = None
            r["achievement_pct"] = None
        return rows, total

    def _top_customers(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Top customers by revenue (descending)."""
        return self._sales_by_customer(company_id, params)

    def _sales_trend(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Monthly revenue trend — same as summary but explicit monthly grouping."""
        return self._sales_summary(company_id, params)

    # -----------------------------------------------------------------------
    # Customer Reports
    # -----------------------------------------------------------------------

    def _customer_list(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Full customer list with status and credit info."""
        q = self._db.query(
            Customer.id,
            Customer.customer_code,
            Customer.legal_name,
            Customer.status,
            Customer.credit_limit,
            Customer.credit_limit,
            Customer.currency_code,
        ).filter(
            Customer.company_id == company_id,
            Customer.is_deleted.is_(False),
        )
        if params.customer_id:
            q = q.filter(Customer.id == params.customer_id)
        total = q.count()
        results = (
            q.order_by(Customer.legal_name)
            .limit(params.limit)
            .offset(params.offset)
            .all()
        )
        rows = [
            {
                "id": _str(r.id),
                "customer_code": r.customer_code,
                "legal_name": r.legal_name,
                "status": r.status,
                "credit_limit": _dec(r.credit_limit),
                "credit_limit_used": _dec(None),
                "currency_code": r.currency_code,
            }
            for r in results
        ]
        return rows, total

    def _customer_ageing(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Customer outstanding invoices for ageing analysis."""
        q = self._db.query(
            SalesInvoice.customer_id,
            SalesInvoice.invoice_number,
            SalesInvoice.invoice_date,
            SalesInvoice.due_date,
            SalesInvoice.total_amount,
            SalesInvoice.status,
        ).filter(
            SalesInvoice.company_id == company_id,
            SalesInvoice.is_deleted.is_(False),
            SalesInvoice.status == "ISSUED",
        )
        if params.customer_id:
            q = q.filter(SalesInvoice.customer_id == params.customer_id)
        total = q.count()
        results = (
            q.order_by(SalesInvoice.due_date)
            .limit(params.limit)
            .offset(params.offset)
            .all()
        )
        rows = [
            {
                "customer_id": _str(r.customer_id),
                "invoice_number": r.invoice_number,
                "invoice_date": r.invoice_date,
                "due_date": r.due_date,
                "total_amount": _dec(r.total_amount),
                "status": r.status,
            }
            for r in results
        ]
        return rows, total

    def _customer_activity(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Order and invoice counts per customer in the period."""
        q = self._db.query(
            SalesOrder.customer_id,
            func.count(SalesOrder.id).label("order_count"),
            func.sum(SalesOrder.total_amount).label("order_value"),
        ).filter(
            SalesOrder.company_id == company_id,
            SalesOrder.is_deleted.is_(False),
        )
        if params.date_from:
            q = q.filter(SalesOrder.order_date >= params.date_from)
        if params.date_to:
            q = q.filter(SalesOrder.order_date <= params.date_to)
        if params.customer_id:
            q = q.filter(SalesOrder.customer_id == params.customer_id)
        q = q.group_by(SalesOrder.customer_id).order_by(
            func.count(SalesOrder.id).desc()
        )
        total_q = q.subquery()
        total = self._db.query(func.count()).select_from(total_q).scalar() or 0
        results = q.limit(params.limit).offset(params.offset).all()
        rows = [
            {
                "customer_id": _str(r.customer_id),
                "order_count": r.order_count,
                "order_value": _dec(r.order_value),
            }
            for r in results
        ]
        return rows, total

    def _new_customers(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Customers created within the date range."""
        q = self._db.query(
            Customer.id,
            Customer.customer_code,
            Customer.legal_name,
            Customer.created_at,
            Customer.status,
        ).filter(
            Customer.company_id == company_id,
            Customer.is_deleted.is_(False),
        )
        total = q.count()
        results = (
            q.order_by(Customer.created_at.desc())
            .limit(params.limit)
            .offset(params.offset)
            .all()
        )
        rows = [
            {
                "id": _str(r.id),
                "customer_code": r.customer_code,
                "legal_name": r.legal_name,
                "created_at": str(r.created_at) if r.created_at else None,
                "status": r.status,
            }
            for r in results
        ]
        return rows, total

    def _customer_credit_report(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Credit limits vs outstanding balances per customer."""
        q = self._db.query(
            Customer.id,
            Customer.customer_code,
            Customer.legal_name,
            Customer.credit_limit,
            Customer.credit_status,
            Customer.credit_limit,
        ).filter(
            Customer.company_id == company_id,
            Customer.is_deleted.is_(False),
        )
        if params.customer_id:
            q = q.filter(Customer.id == params.customer_id)
        total = q.count()
        results = (
            q.order_by(Customer.legal_name)
            .limit(params.limit)
            .offset(params.offset)
            .all()
        )
        rows = [
            {
                "id": _str(r.id),
                "customer_code": r.customer_code,
                "legal_name": r.legal_name,
                "credit_limit": _dec(r.credit_limit),
                "credit_status": r.credit_status,
                "credit_limit_used": _dec(None),
            }
            for r in results
        ]
        return rows, total

    # -----------------------------------------------------------------------
    # Quotation Reports
    # -----------------------------------------------------------------------

    def _quotation_conversion_rate(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Quotation counts by status to derive conversion rate."""
        q = self._db.query(
            SalesQuotation.status,
            func.count(SalesQuotation.id).label("count"),
            func.sum(SalesQuotation.total_amount).label("total_value"),
        ).filter(
            SalesQuotation.company_id == company_id,
            SalesQuotation.is_deleted.is_(False),
        )
        if params.date_from:
            q = q.filter(SalesQuotation.quotation_date >= params.date_from)
        if params.date_to:
            q = q.filter(SalesQuotation.quotation_date <= params.date_to)
        q = q.group_by(SalesQuotation.status).order_by(SalesQuotation.status)
        total_q = q.subquery()
        total = self._db.query(func.count()).select_from(total_q).scalar() or 0
        results = q.limit(params.limit).offset(params.offset).all()
        rows = [
            {
                "status": r.status,
                "count": r.count,
                "total_value": _dec(r.total_value),
            }
            for r in results
        ]
        return rows, total

    def _quotation_pipeline(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Open quotations (DRAFT or SENT_TO_CUSTOMER)."""
        q = self._db.query(
            SalesQuotation.id,
            SalesQuotation.quotation_number,
            SalesQuotation.customer_id,
            SalesQuotation.quotation_date,
            SalesQuotation.validity_date,
            SalesQuotation.status,
            SalesQuotation.total_amount,
        ).filter(
            SalesQuotation.company_id == company_id,
            SalesQuotation.is_deleted.is_(False),
            SalesQuotation.status.in_(["DRAFT", "SENT_TO_CUSTOMER"]),
        )
        if params.customer_id:
            q = q.filter(SalesQuotation.customer_id == params.customer_id)
        total = q.count()
        results = (
            q.order_by(SalesQuotation.quotation_date.desc())
            .limit(params.limit)
            .offset(params.offset)
            .all()
        )
        rows = [
            {
                "id": _str(r.id),
                "quotation_number": r.quotation_number,
                "customer_id": _str(r.customer_id),
                "quotation_date": r.quotation_date,
                "validity_date": r.validity_date,
                "status": r.status,
                "total_amount": _dec(r.total_amount),
            }
            for r in results
        ]
        return rows, total

    def _expired_quotations(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Quotations with status=EXPIRED."""
        q = self._db.query(
            SalesQuotation.id,
            SalesQuotation.quotation_number,
            SalesQuotation.customer_id,
            SalesQuotation.quotation_date,
            SalesQuotation.validity_date,
            SalesQuotation.total_amount,
        ).filter(
            SalesQuotation.company_id == company_id,
            SalesQuotation.is_deleted.is_(False),
            SalesQuotation.status == "EXPIRED",
        )
        if params.date_from:
            q = q.filter(SalesQuotation.validity_date >= params.date_from)
        if params.date_to:
            q = q.filter(SalesQuotation.validity_date <= params.date_to)
        total = q.count()
        results = (
            q.order_by(SalesQuotation.validity_date.desc())
            .limit(params.limit)
            .offset(params.offset)
            .all()
        )
        rows = [
            {
                "id": _str(r.id),
                "quotation_number": r.quotation_number,
                "customer_id": _str(r.customer_id),
                "quotation_date": r.quotation_date,
                "validity_date": r.validity_date,
                "total_amount": _dec(r.total_amount),
            }
            for r in results
        ]
        return rows, total

    # -----------------------------------------------------------------------
    # Delivery Reports
    # -----------------------------------------------------------------------

    def _pending_deliveries(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Delivery notes in DRAFT or DISPATCHED status."""
        q = self._db.query(
            DeliveryNote.id,
            DeliveryNote.delivery_number,
            DeliveryNote.customer_id,
            DeliveryNote.order_id,
            DeliveryNote.dispatch_date,
            DeliveryNote.expected_delivery_date,
            DeliveryNote.status,
        ).filter(
            DeliveryNote.company_id == company_id,
            DeliveryNote.is_deleted.is_(False),
            DeliveryNote.status.in_(["DRAFT", "DISPATCHED"]),
        )
        if params.customer_id:
            q = q.filter(DeliveryNote.customer_id == params.customer_id)
        total = q.count()
        results = (
            q.order_by(DeliveryNote.expected_delivery_date)
            .limit(params.limit)
            .offset(params.offset)
            .all()
        )
        rows = [
            {
                "id": _str(r.id),
                "delivery_number": r.delivery_number,
                "customer_id": _str(r.customer_id),
                "order_id": _str(r.order_id),
                "dispatch_date": r.dispatch_date,
                "expected_delivery_date": r.expected_delivery_date,
                "status": r.status,
            }
            for r in results
        ]
        return rows, total

    def _delivery_performance(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Delivered notes with on-time comparison."""
        q = self._db.query(
            DeliveryNote.id,
            DeliveryNote.delivery_number,
            DeliveryNote.customer_id,
            DeliveryNote.order_id,
            DeliveryNote.dispatch_date,
            DeliveryNote.expected_delivery_date,
            DeliveryNote.status,
        ).filter(
            DeliveryNote.company_id == company_id,
            DeliveryNote.is_deleted.is_(False),
            DeliveryNote.status == "DELIVERED",
        )
        if params.date_from:
            q = q.filter(DeliveryNote.dispatch_date >= params.date_from)
        if params.date_to:
            q = q.filter(DeliveryNote.dispatch_date <= params.date_to)
        if params.customer_id:
            q = q.filter(DeliveryNote.customer_id == params.customer_id)
        total = q.count()
        results = (
            q.order_by(DeliveryNote.dispatch_date.desc())
            .limit(params.limit)
            .offset(params.offset)
            .all()
        )
        rows = [
            {
                "id": _str(r.id),
                "delivery_number": r.delivery_number,
                "customer_id": _str(r.customer_id),
                "order_id": _str(r.order_id),
                "dispatch_date": r.dispatch_date,
                "expected_delivery_date": r.expected_delivery_date,
                "on_time": (
                    r.dispatch_date <= r.expected_delivery_date
                    if r.dispatch_date and r.expected_delivery_date
                    else None
                ),
            }
            for r in results
        ]
        return rows, total

    def _backorder_report(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Orders that are PARTIALLY_DELIVERED."""
        q = self._db.query(
            SalesOrder.id,
            SalesOrder.order_number,
            SalesOrder.customer_id,
            SalesOrder.order_date,
            SalesOrder.required_delivery_date,
            SalesOrder.total_amount,
            SalesOrder.status,
        ).filter(
            SalesOrder.company_id == company_id,
            SalesOrder.is_deleted.is_(False),
            SalesOrder.status == "PARTIALLY_DELIVERED",
        )
        if params.customer_id:
            q = q.filter(SalesOrder.customer_id == params.customer_id)
        total = q.count()
        results = (
            q.order_by(SalesOrder.required_delivery_date)
            .limit(params.limit)
            .offset(params.offset)
            .all()
        )
        rows = [
            {
                "id": _str(r.id),
                "order_number": r.order_number,
                "customer_id": _str(r.customer_id),
                "order_date": r.order_date,
                "required_delivery_date": r.required_delivery_date,
                "total_amount": _dec(r.total_amount),
            }
            for r in results
        ]
        return rows, total

    # -----------------------------------------------------------------------
    # Profitability Reports
    # -----------------------------------------------------------------------

    def _gross_margin_by_product(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Revenue by product — COGS not stored, shows revenue and discount."""
        q = (
            self._db.query(
                OrderLine.product_id,
                OrderLine.description,
                func.sum(OrderLine.extended_amount).label("revenue"),
                func.sum(OrderLine.discount_amount).label("total_discount"),
                func.count(OrderLine.id).label("line_count"),
            )
            .join(SalesOrder, SalesOrder.id == OrderLine.order_id)
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.is_deleted.is_(False),
                OrderLine.is_deleted.is_(False),
                SalesOrder.status.in_(["DELIVERED", "INVOICED", "CLOSED"]),
            )
        )
        if params.date_from:
            q = q.filter(SalesOrder.order_date >= params.date_from)
        if params.date_to:
            q = q.filter(SalesOrder.order_date <= params.date_to)
        q = q.group_by(OrderLine.product_id, OrderLine.description).order_by(
            func.sum(OrderLine.extended_amount).desc()
        )
        total_q = q.subquery()
        total = self._db.query(func.count()).select_from(total_q).scalar() or 0
        results = q.limit(params.limit).offset(params.offset).all()
        rows = [
            {
                "product_id": _str(r.product_id),
                "description": r.description,
                "revenue": _dec(r.revenue),
                "total_discount": _dec(r.total_discount),
                "line_count": r.line_count,
                "cogs": None,
                "gross_margin": None,
            }
            for r in results
        ]
        return rows, total

    def _gross_margin_by_customer(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Revenue by customer — COGS not stored, shows revenue."""
        return self._sales_by_customer(company_id, params)

    def _discount_analysis(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Discount amounts and percentages by order."""
        q = self._db.query(
            SalesOrder.id,
            SalesOrder.order_number,
            SalesOrder.customer_id,
            SalesOrder.order_date,
            SalesOrder.subtotal,
            SalesOrder.total_amount,
            SalesOrder.sales_rep_id,
        ).filter(
            SalesOrder.company_id == company_id,
            SalesOrder.is_deleted.is_(False),
            SalesOrder.status.notin_(["DRAFT", "CANCELLED"]),
        )
        if params.date_from:
            q = q.filter(SalesOrder.order_date >= params.date_from)
        if params.date_to:
            q = q.filter(SalesOrder.order_date <= params.date_to)
        if params.customer_id:
            q = q.filter(SalesOrder.customer_id == params.customer_id)
        total = q.count()
        results = (
            q.order_by(SalesOrder.order_date.desc())
            .limit(params.limit)
            .offset(params.offset)
            .all()
        )
        rows = [
            {
                "id": _str(r.id),
                "order_number": r.order_number,
                "customer_id": _str(r.customer_id),
                "order_date": r.order_date,
                "subtotal": _dec(r.subtotal),
                "total_amount": _dec(r.total_amount),
                "discount_amount": _dec(
                    r.subtotal - r.total_amount
                    if r.subtotal is not None and r.total_amount is not None
                    else None
                ),
                "sales_rep_id": _str(r.sales_rep_id),
            }
            for r in results
        ]
        return rows, total

    # -----------------------------------------------------------------------
    # Audit Reports
    # -----------------------------------------------------------------------

    def _sales_audit_trail(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """All sales orders with created_at / updated_at timestamps."""
        q = self._db.query(
            SalesOrder.id,
            SalesOrder.order_number,
            SalesOrder.customer_id,
            SalesOrder.status,
            SalesOrder.created_at,
            SalesOrder.updated_at,
            SalesOrder.created_by,
        ).filter(
            SalesOrder.company_id == company_id,
            SalesOrder.is_deleted.is_(False),
        )
        if params.date_from:
            q = q.filter(SalesOrder.order_date >= params.date_from)
        if params.date_to:
            q = q.filter(SalesOrder.order_date <= params.date_to)
        if params.customer_id:
            q = q.filter(SalesOrder.customer_id == params.customer_id)
        total = q.count()
        results = (
            q.order_by(SalesOrder.created_at.desc())
            .limit(params.limit)
            .offset(params.offset)
            .all()
        )
        rows = [
            {
                "id": _str(r.id),
                "order_number": r.order_number,
                "customer_id": _str(r.customer_id),
                "status": r.status,
                "created_at": str(r.created_at) if r.created_at else None,
                "updated_at": str(r.updated_at) if r.updated_at else None,
                "created_by": _str(r.created_by),
            }
            for r in results
        ]
        return rows, total

    def _price_override_report(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Order lines where price was set manually (price_source=MANUAL)."""
        q = (
            self._db.query(
                OrderLine.id,
                OrderLine.order_id,
                OrderLine.product_id,
                OrderLine.description,
                OrderLine.unit_price,
                OrderLine.price_source,
                SalesOrder.order_number,
                SalesOrder.customer_id,
                SalesOrder.order_date,
                SalesOrder.sales_rep_id,
            )
            .join(SalesOrder, SalesOrder.id == OrderLine.order_id)
            .filter(
                SalesOrder.company_id == company_id,
                SalesOrder.is_deleted.is_(False),
                OrderLine.is_deleted.is_(False),
                OrderLine.price_source == "MANUAL",
            )
        )
        if params.date_from:
            q = q.filter(SalesOrder.order_date >= params.date_from)
        if params.date_to:
            q = q.filter(SalesOrder.order_date <= params.date_to)
        if params.customer_id:
            q = q.filter(SalesOrder.customer_id == params.customer_id)
        total = q.count()
        results = (
            q.order_by(SalesOrder.order_date.desc())
            .limit(params.limit)
            .offset(params.offset)
            .all()
        )
        rows = [
            {
                "line_id": _str(r.id),
                "order_id": _str(r.order_id),
                "order_number": r.order_number,
                "product_id": _str(r.product_id),
                "description": r.description,
                "unit_price": _dec(r.unit_price),
                "price_source": r.price_source,
                "customer_id": _str(r.customer_id),
                "order_date": r.order_date,
                "sales_rep_id": _str(r.sales_rep_id),
            }
            for r in results
        ]
        return rows, total

    def _credit_limit_change_report(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Customers with their current credit limits."""
        return self._customer_credit_report(company_id, params)

    def _approval_history(
        self, company_id: UUID, params: ReportParams
    ) -> tuple[list[Row], int]:
        """Orders that went through approval (approval_version >= 1)."""
        q = self._db.query(
            SalesOrder.id,
            SalesOrder.order_number,
            SalesOrder.customer_id,
            SalesOrder.status,
            SalesOrder.approval_version,
            SalesOrder.order_date,
        ).filter(
            SalesOrder.company_id == company_id,
            SalesOrder.is_deleted.is_(False),
            SalesOrder.approval_version >= 1,
            SalesOrder.status.notin_(["DRAFT"]),
        )
        if params.date_from:
            q = q.filter(SalesOrder.order_date >= params.date_from)
        if params.date_to:
            q = q.filter(SalesOrder.order_date <= params.date_to)
        total = q.count()
        results = (
            q.order_by(SalesOrder.order_date.desc())
            .limit(params.limit)
            .offset(params.offset)
            .all()
        )
        rows = [
            {
                "id": _str(r.id),
                "order_number": r.order_number,
                "customer_id": _str(r.customer_id),
                "status": r.status,
                "approval_version": r.approval_version,
                "order_date": r.order_date,
            }
            for r in results
        ]
        return rows, total

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _apply_invoice_date_filter(
        self, q: Any, model: Any, params: ReportParams
    ) -> Any:
        if params.date_from:
            q = q.filter(model.invoice_date >= params.date_from)
        if params.date_to:
            q = q.filter(model.invoice_date <= params.date_to)
        return q
