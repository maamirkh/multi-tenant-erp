"""``PurchaseAdapter`` — wraps Purchase's already-implemented
``ReportService``/``KPIService`` behind the Reports ``ReportAdapter``
Protocol. Every figure is computed by an existing Purchase service
method; this adapter re-derives nothing.

All six list-shaped reports are genuine Category A (SQL-level count +
bounded fetch) as of T075's seam — page 1 online never requires a
full-population fetch for any of them. Stateless (matches
``AccountingAdapter``'s pattern).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from modules.purchase.dependencies import get_kpi_service, get_report_service
from modules.purchase.services.report_service import (
    ReportService as PurchaseReportService,
)
from modules.reports.exceptions import ReportNotFoundError
from modules.reports.schemas.common import ComparisonRequest, ReportEnvelopeMeta
from modules.reports.schemas.purchase import (
    OpenCommitmentRow,
    OpenCommitmentsFilter,
    PendingDeliveriesFilter,
    PendingDeliveryRow,
    PurchaseBySupplierFilter,
    PurchaseBySupplierRow,
    PurchaseKpiFilter,
    PurchaseKpiSet,
    PurchaseOrderSummaryRow,
    PurchaseSummaryFilter,
    SupplierPerformanceFilter,
    SupplierPerformanceRow,
    VendorReturnRow,
    VendorReturnsFilter,
)
from modules.reports.services.adapters.base import (
    AggregateReportResult,
    BaseReportResult,
    PaginatedReportResult,
)


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


class PurchaseAdapter:
    """Stateless domain adapter for ``ReportDomain.PURCHASE``'s 7 "Now"
    reports."""

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
        if report_key == "purchase.kpis":
            assert isinstance(filters, PurchaseKpiFilter)
            kpis = get_kpi_service(db)
            data = kpis.get_all_kpis(
                company_id, date_from=filters.date_from, date_to=filters.date_to
            )
            return AggregateReportResult[PurchaseKpiSet](
                meta=_meta(report_key, filters),
                data=PurchaseKpiSet.model_validate(data),
            )

        rows, total = self._run_list_report(
            db, company_id, report_key, filters, page, page_size
        )
        row_model = _ROW_MODEL_BY_KEY[report_key]
        return PaginatedReportResult[BaseModel](
            meta=_meta(report_key, filters),
            items=[row_model.model_validate(r) for r in rows],
            total=total,
        )

    def count_export_rows(
        self, db: Session, company_id: UUID, report_key: str, filters: BaseModel
    ) -> int:
        reports = get_report_service(db)
        return self._count(reports, company_id, report_key, filters)

    def iter_export_rows(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        sort: str | None,
        batch_size: int,
    ) -> Iterator[list[BaseModel]]:
        if report_key not in _ROW_MODEL_BY_KEY:
            raise ValueError(f"'{report_key}' has no export-row iteration seam.")
        row_model = _ROW_MODEL_BY_KEY[report_key]
        offset = 0
        while True:
            rows, total = self._run_list_report(
                db,
                company_id,
                report_key,
                filters,
                page=(offset // batch_size) + 1,
                page_size=batch_size,
            )
            if not rows:
                return
            batch: list[BaseModel] = [row_model.model_validate(r) for r in rows]
            yield batch
            offset += batch_size
            if offset >= total:
                return

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_list_report(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, Any]], int]:
        reports = get_report_service(db)
        skip = (page - 1) * page_size

        if report_key == "purchase.summary":
            assert isinstance(filters, PurchaseSummaryFilter)
            rows = reports.purchase_order_summary(
                company_id,
                status=filters.status,
                supplier_id=filters.supplier_id,
                date_from=filters.date_from,
                date_to=filters.date_to,
                skip=skip,
                limit=page_size,
            )
            total = reports.count_purchase_order_summary(
                company_id,
                status=filters.status,
                supplier_id=filters.supplier_id,
                date_from=filters.date_from,
                date_to=filters.date_to,
            )
            return rows, total
        if report_key == "purchase.by_supplier":
            assert isinstance(filters, PurchaseBySupplierFilter)
            rows = reports.purchase_by_supplier(
                company_id,
                date_from=filters.date_from,
                date_to=filters.date_to,
                skip=skip,
                limit=page_size,
            )
            total = reports.count_purchase_by_supplier(
                company_id, date_from=filters.date_from, date_to=filters.date_to
            )
            return rows, total
        if report_key == "purchase.supplier_performance":
            assert isinstance(filters, SupplierPerformanceFilter)
            rows = reports.supplier_performance(
                company_id,
                date_from=filters.date_from,
                date_to=filters.date_to,
                skip=skip,
                limit=page_size,
            )
            total = reports.count_supplier_performance(
                company_id, date_from=filters.date_from, date_to=filters.date_to
            )
            return rows, total
        if report_key == "purchase.open_commitments":
            assert isinstance(filters, OpenCommitmentsFilter)
            rows = reports.open_purchase_commitments(
                company_id,
                supplier_id=filters.supplier_id,
                branch_id=filters.branch_id,
                skip=skip,
                limit=page_size,
            )
            total = reports.count_open_purchase_commitments(
                company_id, supplier_id=filters.supplier_id, branch_id=filters.branch_id
            )
            return rows, total
        if report_key == "purchase.pending_deliveries":
            assert isinstance(filters, PendingDeliveriesFilter)
            rows = reports.overdue_deliveries(
                company_id,
                as_of=filters.as_of,
                branch_id=filters.branch_id,
                skip=skip,
                limit=page_size,
            )
            total = reports.count_overdue_deliveries(
                company_id, as_of=filters.as_of, branch_id=filters.branch_id
            )
            return rows, total
        if report_key == "purchase.vendor_returns":
            assert isinstance(filters, VendorReturnsFilter)
            rows = reports.vendor_return_report(
                company_id,
                date_from=filters.date_from,
                date_to=filters.date_to,
                supplier_id=filters.supplier_id,
                skip=skip,
                limit=page_size,
            )
            total = reports.count_vendor_returns(
                company_id,
                date_from=filters.date_from,
                date_to=filters.date_to,
                supplier_id=filters.supplier_id,
            )
            return rows, total
        raise ReportNotFoundError(report_key)

    def _count(
        self,
        reports: PurchaseReportService,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
    ) -> int:
        if report_key == "purchase.summary":
            assert isinstance(filters, PurchaseSummaryFilter)
            return reports.count_purchase_order_summary(
                company_id,
                status=filters.status,
                supplier_id=filters.supplier_id,
                date_from=filters.date_from,
                date_to=filters.date_to,
            )
        if report_key == "purchase.by_supplier":
            assert isinstance(filters, PurchaseBySupplierFilter)
            return reports.count_purchase_by_supplier(
                company_id, date_from=filters.date_from, date_to=filters.date_to
            )
        if report_key == "purchase.supplier_performance":
            assert isinstance(filters, SupplierPerformanceFilter)
            return reports.count_supplier_performance(
                company_id, date_from=filters.date_from, date_to=filters.date_to
            )
        if report_key == "purchase.open_commitments":
            assert isinstance(filters, OpenCommitmentsFilter)
            return reports.count_open_purchase_commitments(
                company_id, supplier_id=filters.supplier_id, branch_id=filters.branch_id
            )
        if report_key == "purchase.pending_deliveries":
            assert isinstance(filters, PendingDeliveriesFilter)
            return reports.count_overdue_deliveries(
                company_id, as_of=filters.as_of, branch_id=filters.branch_id
            )
        if report_key == "purchase.vendor_returns":
            assert isinstance(filters, VendorReturnsFilter)
            return reports.count_vendor_returns(
                company_id,
                date_from=filters.date_from,
                date_to=filters.date_to,
                supplier_id=filters.supplier_id,
            )
        raise ValueError(f"'{report_key}' has no export-row count seam.")


_ROW_MODEL_BY_KEY: dict[str, type[BaseModel]] = {
    "purchase.summary": PurchaseOrderSummaryRow,
    "purchase.by_supplier": PurchaseBySupplierRow,
    "purchase.supplier_performance": SupplierPerformanceRow,
    "purchase.open_commitments": OpenCommitmentRow,
    "purchase.pending_deliveries": PendingDeliveryRow,
    "purchase.vendor_returns": VendorReturnRow,
}
