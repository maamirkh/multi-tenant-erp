"""``InventoryAdapter`` — wraps Inventory's already-implemented
``ReportQueryService``/``KPIService``/``LowStockAlertRepository`` behind
the Reports ``ReportAdapter`` Protocol. Every figure is computed by an
existing Inventory service/repository method; this adapter re-derives
nothing.

``inventory.stock_position`` is deliberately backed by
``ReportQueryService.stock_ledger`` — the pre-existing, genuinely
SQL-bounded (real ``COUNT`` + ``LIMIT``/``OFFSET``) movement-ledger query
— rather than the unbounded ``stock_position_report`` method, which T087
intentionally left untouched (only 3 seams were sanctioned: T047, T075,
T087, and ``stock_ledger`` already satisfied the bounded-read requirement
without needing one). ``dead_stock``/``movement_velocity``/``stock_aging``
use T087's new bounded+count siblings; ``low_stock`` uses
``LowStockAlertRepository``'s new ``count_for_company``. ``summary``/
``valuation``/``kpis`` are aggregate (no pagination).

``valuation_basis="operational_wac"`` is injected here, not by Inventory's
own service (FR-RPT-071) — a deliberate disclaimer that this is Inventory's
own operational WAC figure, never reconciled against Accounting's GL
balance. Stateless (matches ``AccountingAdapter``'s pattern).
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from modules.inventory.dependencies import (
    get_alert_repo,
    get_kpi_service,
    get_report_service,
)
from modules.inventory.models.alerts import LowStockAlert
from modules.reports.exceptions import ReportNotFoundError
from modules.reports.schemas.common import ComparisonRequest, ReportEnvelopeMeta
from modules.reports.schemas.inventory import (
    DeadStockFilter,
    InventoryKpiFilter,
    InventoryKpiSet,
    InventoryReportRow,
    InventorySummaryFilter,
    InventorySummaryResponse,
    InventoryValuationFilter,
    InventoryValuationResponse,
    LowStockFilter,
    MovementVelocityFilter,
    StockAgingFilter,
    StockPositionFilter,
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


def _alert_row(alert: LowStockAlert) -> dict[str, Any]:
    return {
        "alert_id": str(alert.id),
        "product_id": alert.product_id,
        "variant_id": alert.variant_id,
        "warehouse_id": alert.warehouse_id,
        "alert_type": alert.alert_type,
        "status": alert.status,
        "current_quantity": alert.current_quantity,
        "threshold_quantity": alert.threshold_quantity,
        "acknowledged_at": alert.acknowledged_at,
        "resolved_at": alert.resolved_at,
        "created_at": alert.created_at,
    }


class InventoryAdapter:
    """Stateless domain adapter for ``ReportDomain.INVENTORY``'s 8 "Now"
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
        if report_key == "inventory.summary":
            assert isinstance(filters, InventorySummaryFilter)
            reports = get_report_service(db)
            data = reports.inventory_summary(
                company_id=company_id,
                warehouse_id=filters.warehouse_id,
                category_id=filters.category_id,
            )
            return AggregateReportResult[InventorySummaryResponse](
                meta=_meta(report_key, filters),
                data=InventorySummaryResponse.model_validate(data),
            )
        if report_key == "inventory.valuation":
            assert isinstance(filters, InventoryValuationFilter)
            reports = get_report_service(db)
            data = reports.inventory_valuation(
                company_id=company_id, warehouse_id=filters.warehouse_id
            )
            return AggregateReportResult[InventoryValuationResponse](
                meta=_meta(report_key, filters),
                data=InventoryValuationResponse.model_validate(
                    {**data, "valuation_basis": "operational_wac"}
                ),
            )
        if report_key == "inventory.kpis":
            assert isinstance(filters, InventoryKpiFilter)
            kpis = get_kpi_service(db)
            data = kpis.compute(company_id=company_id, period_days=filters.period_days)
            return AggregateReportResult[InventoryKpiSet](
                meta=_meta(report_key, filters),
                data=InventoryKpiSet.model_validate(data),
            )

        rows, total = self._run_list_report(
            db, company_id, report_key, filters, page, page_size
        )
        return PaginatedReportResult[InventoryReportRow](
            meta=_meta(report_key, filters),
            items=[InventoryReportRow.model_validate(r) for r in rows],
            total=total,
        )

    def export_row_model(self, report_key: str) -> type[BaseModel]:
        if report_key not in _LIST_REPORT_KEYS:
            raise ValueError(f"'{report_key}' has no export-row iteration seam.")
        return InventoryReportRow

    def count_export_rows(
        self, db: Session, company_id: UUID, report_key: str, filters: BaseModel
    ) -> int:
        return self._count(db, company_id, report_key, filters)

    def iter_export_rows(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
        sort: str | None,
        batch_size: int,
    ) -> Iterator[list[BaseModel]]:
        if report_key not in _LIST_REPORT_KEYS:
            raise ValueError(f"'{report_key}' has no export-row iteration seam.")
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
            batch: list[BaseModel] = [
                InventoryReportRow.model_validate(r) for r in rows
            ]
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
        skip = (page - 1) * page_size

        if report_key == "inventory.stock_position":
            assert isinstance(filters, StockPositionFilter)
            reports = get_report_service(db)
            ledger = reports.stock_ledger(
                company_id=company_id,
                product_id=filters.product_id,
                warehouse_id=filters.warehouse_id,
                date_from=filters.date_from,
                date_to=filters.date_to,
                limit=page_size,
                offset=skip,
            )
            return ledger["rows"], int(ledger["total_rows"])
        if report_key == "inventory.dead_stock":
            assert isinstance(filters, DeadStockFilter)
            reports = get_report_service(db)
            result = reports.dead_stock(
                company_id=company_id,
                threshold_days=filters.threshold_days,
                limit=page_size,
                offset=skip,
            )
            total = reports.count_dead_stock(
                company_id=company_id, threshold_days=filters.threshold_days
            )
            return result["rows"], total
        if report_key == "inventory.movement_velocity":
            assert isinstance(filters, MovementVelocityFilter)
            reports = get_report_service(db)
            result = reports.movement_velocity(
                company_id=company_id,
                date_from=filters.date_from,
                date_to=filters.date_to,
                limit=page_size,
                offset=skip,
            )
            total = reports.count_movement_velocity(
                company_id=company_id,
                date_from=filters.date_from,
                date_to=filters.date_to,
            )
            return result["rows"], total
        if report_key == "inventory.stock_aging":
            assert isinstance(filters, StockAgingFilter)
            reports = get_report_service(db)
            result = reports.stock_aging(
                company_id=company_id,
                warehouse_id=filters.warehouse_id,
                limit=page_size,
                offset=skip,
            )
            total = reports.count_stock_aging(
                company_id=company_id, warehouse_id=filters.warehouse_id
            )
            return result["rows"], total
        if report_key == "inventory.low_stock":
            assert isinstance(filters, LowStockFilter)
            alert_repo = get_alert_repo(db)
            alerts = alert_repo.list_for_company(
                company_id=company_id,
                status=filters.status,
                alert_type=filters.alert_type,
                product_id=filters.product_id,
                warehouse_id=filters.warehouse_id,
                limit=page_size,
                offset=skip,
            )
            total = alert_repo.count_for_company(
                company_id=company_id,
                status=filters.status,
                alert_type=filters.alert_type,
                product_id=filters.product_id,
                warehouse_id=filters.warehouse_id,
            )
            return [_alert_row(a) for a in alerts], total
        raise ReportNotFoundError(report_key)

    def _count(
        self,
        db: Session,
        company_id: UUID,
        report_key: str,
        filters: BaseModel,
    ) -> int:
        if report_key == "inventory.stock_position":
            assert isinstance(filters, StockPositionFilter)
            reports = get_report_service(db)
            ledger = reports.stock_ledger(
                company_id=company_id,
                product_id=filters.product_id,
                warehouse_id=filters.warehouse_id,
                date_from=filters.date_from,
                date_to=filters.date_to,
                limit=1,
                offset=0,
            )
            return int(ledger["total_rows"])
        if report_key == "inventory.dead_stock":
            assert isinstance(filters, DeadStockFilter)
            reports = get_report_service(db)
            return reports.count_dead_stock(
                company_id=company_id, threshold_days=filters.threshold_days
            )
        if report_key == "inventory.movement_velocity":
            assert isinstance(filters, MovementVelocityFilter)
            reports = get_report_service(db)
            return reports.count_movement_velocity(
                company_id=company_id,
                date_from=filters.date_from,
                date_to=filters.date_to,
            )
        if report_key == "inventory.stock_aging":
            assert isinstance(filters, StockAgingFilter)
            reports = get_report_service(db)
            return reports.count_stock_aging(
                company_id=company_id, warehouse_id=filters.warehouse_id
            )
        if report_key == "inventory.low_stock":
            assert isinstance(filters, LowStockFilter)
            alert_repo = get_alert_repo(db)
            return alert_repo.count_for_company(
                company_id=company_id,
                status=filters.status,
                alert_type=filters.alert_type,
                product_id=filters.product_id,
                warehouse_id=filters.warehouse_id,
            )
        raise ValueError(f"'{report_key}' has no export-row count seam.")


_LIST_REPORT_KEYS: frozenset[str] = frozenset(
    {
        "inventory.stock_position",
        "inventory.dead_stock",
        "inventory.movement_velocity",
        "inventory.stock_aging",
        "inventory.low_stock",
    }
)
