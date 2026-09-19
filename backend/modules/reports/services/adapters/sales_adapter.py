"""``SalesAdapter`` — wraps Sales' already-implemented
``ReportService.run_report()`` / ``KPIService.get_dashboard()`` /
``ReturnService.list_returns()`` behind the Reports ``ReportAdapter``
Protocol. Every figure is computed by an existing Sales service method;
this adapter re-derives nothing.

Stateless (matches ``AccountingAdapter``'s pattern) — builds the one
Sales service it needs, fresh, per call, from ``modules.sales.dependencies``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from modules.reports.exceptions import ReportNotFoundError
from modules.reports.schemas.common import ComparisonRequest, ReportEnvelopeMeta
from modules.reports.schemas.sales import (
    QuotationPipelineFilter,
    QuotationPipelineRow,
    SalesByCustomerFilter,
    SalesByCustomerRow,
    SalesByProductFilter,
    SalesByProductRow,
    SalesKpiFilter,
    SalesReturnRow,
    SalesReturnsFilter,
    SalesSummaryFilter,
    SalesSummaryRow,
    SalesTrendFilter,
    TopCustomersFilter,
)
from modules.reports.services.adapters.base import (
    AggregateReportResult,
    BaseReportResult,
    PaginatedReportResult,
)
from modules.sales.dependencies import (
    get_kpi_service,
    get_report_service,
    get_return_service,
)
from modules.sales.schemas.reports import KPIDashboard, ReportParams, ReportType

_UNAVAILABLE_REFERENCE = "[unavailable reference]"

_ROW_MODEL_BY_KEY: dict[str, type[BaseModel]] = {
    "sales.summary": SalesSummaryRow,
    "sales.by_customer": SalesByCustomerRow,
    "sales.by_product": SalesByProductRow,
    "sales.top_customers": SalesByCustomerRow,
    "sales.trend": SalesSummaryRow,
    "sales.quotation_pipeline": QuotationPipelineRow,
}

_REPORT_TYPE_BY_KEY = {
    "sales.summary": "sales_summary",
    "sales.by_customer": "sales_by_customer",
    "sales.by_product": "sales_by_product",
    "sales.top_customers": "top_customers",
    "sales.trend": "sales_trend",
    "sales.quotation_pipeline": "quotation_pipeline",
}


def _meta(report_key: str, filters: BaseModel) -> ReportEnvelopeMeta:
    from modules.reports.schemas.common import FreshnessClassification, PeriodResolution

    return ReportEnvelopeMeta(
        report_key=report_key,
        applied_filters=filters.model_dump(mode="json"),
        period=PeriodResolution(
            start="1970-01-01T00:00:00+00:00",
            end="1970-01-01T00:00:00+00:00",
            timezone="UTC",
        ),
        freshness=FreshnessClassification.TRANSACTIONAL_LIVE,
    )


def _resolve_customer_name(
    db: Session, company_id: UUID, customer_id: str | None
) -> str:
    """FR-RPT-053: Sales carries no DB-level FK on ``customer_id`` — a
    dangling reference is a real, expected case, never an error. Returns
    the literal ``"[unavailable reference]"`` rather than raising."""
    if not customer_id:
        return _UNAVAILABLE_REFERENCE
    try:
        customer_uuid = UUID(customer_id)
    except ValueError:
        return _UNAVAILABLE_REFERENCE

    from modules.sales.dependencies import get_customer_repo

    customer = get_customer_repo(db).get_by_id_or_none(customer_uuid, company_id)
    return customer.legal_name if customer is not None else _UNAVAILABLE_REFERENCE


def _enrich_row(
    row_model: type[BaseModel], raw_row: dict[str, Any], db: Session, company_id: UUID
) -> BaseModel:
    if row_model is SalesByCustomerRow:
        raw_row = {
            **raw_row,
            "customer_name": _resolve_customer_name(
                db, company_id, raw_row.get("customer_id")
            ),
        }
    return row_model.model_validate(raw_row)


class SalesAdapter:
    """Stateless domain adapter for ``ReportDomain.SALES``'s 8 "Now" reports."""

    def run(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        page: int,
        page_size: int,
        sort: str | None,
        comparison: ComparisonRequest | None,
    ) -> BaseReportResult:
        if report_key in _REPORT_TYPE_BY_KEY:
            rows, total = self._run_report_service(
                db, company_id, report_key, filters, page, page_size
            )
            row_model = _ROW_MODEL_BY_KEY[report_key]
            return PaginatedReportResult[BaseModel](
                meta=_meta(report_key, filters),
                items=[_enrich_row(row_model, r, db, company_id) for r in rows],
                total=total,
            )
        if report_key == "sales.returns":
            assert isinstance(filters, SalesReturnsFilter)
            returns = get_return_service(db)
            offset = (page - 1) * page_size
            items, total = returns.list_returns(
                company_id,
                customer_id=filters.customer_id,
                status=filters.status,
                order_id=filters.order_id,
                resolution_type=filters.resolution_type,
                limit=page_size,
                offset=offset,
            )
            return PaginatedReportResult[SalesReturnRow](
                meta=_meta(report_key, filters),
                items=[SalesReturnRow.model_validate(r) for r in items],
                total=total,
            )
        if report_key == "sales.kpis":
            assert isinstance(filters, SalesKpiFilter)
            kpis = get_kpi_service(db)
            dashboard = kpis.get_dashboard(
                company_id,
                date_from=filters.date_from.isoformat() if filters.date_from else None,
                date_to=filters.date_to.isoformat() if filters.date_to else None,
            )
            return AggregateReportResult[KPIDashboard](
                meta=_meta(report_key, filters), data=dashboard
            )
        raise ReportNotFoundError(report_key)

    def count_export_rows(
        self, db: Session, company_id: UUID, report_key: str, filters: BaseModel
    ) -> int:
        if report_key in _REPORT_TYPE_BY_KEY:
            _rows, total = self._run_report_service(
                db, company_id, report_key, filters, page=1, page_size=1
            )
            return total
        if report_key == "sales.returns":
            assert isinstance(filters, SalesReturnsFilter)
            returns = get_return_service(db)
            _items, total = returns.list_returns(
                company_id,
                customer_id=filters.customer_id,
                status=filters.status,
                order_id=filters.order_id,
                resolution_type=filters.resolution_type,
                limit=1,
                offset=0,
            )
            return total
        raise ValueError(f"'{report_key}' has no export-row count seam.")

    def iter_export_rows(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        sort: str | None,
        batch_size: int,
    ) -> Iterator[list[BaseModel]]:
        if report_key in _REPORT_TYPE_BY_KEY:
            row_model = _ROW_MODEL_BY_KEY[report_key]
            offset = 0
            while True:
                rows, total = self._run_report_service(
                    db,
                    company_id,
                    report_key,
                    filters,
                    page=(offset // batch_size) + 1,
                    page_size=batch_size,
                )
                if not rows:
                    return
                batch: list[BaseModel] = [
                    _enrich_row(row_model, r, db, company_id) for r in rows
                ]
                yield batch
                offset += batch_size
                if offset >= total:
                    return
        elif report_key == "sales.returns":
            assert isinstance(filters, SalesReturnsFilter)
            returns = get_return_service(db)
            offset = 0
            while True:
                items, total = returns.list_returns(
                    company_id,
                    customer_id=filters.customer_id,
                    status=filters.status,
                    order_id=filters.order_id,
                    resolution_type=filters.resolution_type,
                    limit=batch_size,
                    offset=offset,
                )
                if not items:
                    return
                return_batch: list[BaseModel] = [
                    SalesReturnRow.model_validate(r) for r in items
                ]
                yield return_batch
                offset += batch_size
                if offset >= total:
                    return
        else:
            raise ValueError(f"'{report_key}' has no export-row iteration seam.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_report_service(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        assert isinstance(
            filters,
            SalesSummaryFilter
            | SalesByCustomerFilter
            | SalesByProductFilter
            | TopCustomersFilter
            | SalesTrendFilter
            | QuotationPipelineFilter,
        )
        params_kwargs: dict[str, Any] = {
            "limit": page_size,
            "offset": (page - 1) * page_size,
        }
        if isinstance(
            filters,
            SalesSummaryFilter
            | SalesByCustomerFilter
            | SalesByProductFilter
            | TopCustomersFilter
            | SalesTrendFilter,
        ):
            if filters.date_from is not None:
                params_kwargs["date_from"] = filters.date_from.isoformat()
            if filters.date_to is not None:
                params_kwargs["date_to"] = filters.date_to.isoformat()
        if isinstance(filters, SalesSummaryFilter | SalesByProductFilter) and (
            filters.customer_id is not None
        ):
            params_kwargs["customer_id"] = filters.customer_id
        if (
            isinstance(filters, QuotationPipelineFilter)
            and filters.customer_id is not None
        ):
            params_kwargs["customer_id"] = filters.customer_id
        if isinstance(filters, TopCustomersFilter):
            params_kwargs["limit"] = filters.limit

        params = ReportParams(**params_kwargs)
        reports = get_report_service(db)
        response = reports.run_report(
            ReportType(_REPORT_TYPE_BY_KEY[report_key]), company_id, params
        )
        return response.rows, response.total
