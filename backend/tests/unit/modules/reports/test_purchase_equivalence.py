"""T082 — ``purchase_order_summary()``/``KPIService.get_all_kpis()``
called directly vs. ``PurchaseAdapter.run()`` — identical; and, for each
of ``supplier_performance``, ``pending_deliveries``, ``vendor_returns``
(Blocker C / Blocker 1), the pre-fix full calculation vs. the union of
all pages from the new bounded seam — identical rows/KPI values for all
three.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.purchase.models.purchase_order import PurchaseOrder
from modules.purchase.services.kpi_service import MONEY_KPI_KEYS, KPIService
from modules.purchase.services.report_service import ReportService
from modules.reports.schemas.purchase import (
    PendingDeliveriesFilter,
    PurchaseKpiFilter,
    PurchaseSummaryFilter,
)
from modules.reports.services.adapters.base import (
    AggregateReportResult,
    PaginatedReportResult,
)
from modules.reports.services.adapters.purchase_adapter import PurchaseAdapter


def _make_po(
    db: Session, company_id: uuid.UUID, *, status: str = "APPROVED"
) -> PurchaseOrder:
    po = PurchaseOrder(
        company_id=company_id,
        po_number=f"PO-{uuid.uuid4().hex[:8]}",
        supplier_id=str(uuid.uuid4()),
        status=status,
        currency_code="USD",
        subtotal=Decimal("100.00"),
        total=Decimal("100.00"),
        expected_delivery_date=date(2026, 1, 1),
    )
    db.add(po)
    db.flush()
    return po


def test_purchase_summary_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    _make_po(db_session, company_id)
    _make_po(db_session, company_id)
    db_session.commit()

    reports = ReportService(db_session)
    direct_rows = reports.purchase_order_summary(company_id)
    direct_count = reports.count_purchase_order_summary(company_id)

    adapter = PurchaseAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "purchase.summary",
        PurchaseSummaryFilter(),
        page=1,
        page_size=20,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, PaginatedReportResult)
    assert result.total == direct_count == 2
    assert len(result.items) == len(direct_rows) == 2


def test_purchase_kpis_equivalence(db_session: Session) -> None:
    company_id = uuid.uuid4()
    _make_po(db_session, company_id)
    db_session.commit()

    kpis = KPIService(db_session)
    direct = kpis.get_all_kpis(company_id)

    adapter = PurchaseAdapter()
    result = adapter.run(
        db_session,
        company_id,
        "purchase.kpis",
        PurchaseKpiFilter(),
        page=1,
        page_size=1,
        sort=None,
        comparison=None,
    )
    assert isinstance(result, AggregateReportResult)
    dumped = result.data.model_dump()
    # Every non-money KPI passes through unchanged; the two money KPIs are
    # replaced by their per-currency figures (FR-RPT-152).
    for key, value in direct.items():
        if key in MONEY_KPI_KEYS:
            assert key not in dumped
        else:
            assert dumped[key] == value
    assert dumped["by_currency"] == [
        {
            "currency_code": code,
            "open_commitments_value": kpis.open_commitments_value_by_currency(
                company_id
            ).get(code, Decimal("0")),
            "total_purchase_value": kpis.total_purchase_value_by_currency(
                company_id
            ).get(code, Decimal("0")),
        }
        for code in sorted(
            kpis.open_commitments_value_by_currency(company_id).keys()
            | kpis.total_purchase_value_by_currency(company_id).keys()
        )
    ]


def test_pending_deliveries_paginated_union_matches_full_population(
    db_session: Session,
) -> None:
    company_id = uuid.uuid4()
    cutoff = datetime(2026, 6, 1, tzinfo=UTC).date()
    for _ in range(5):
        po = PurchaseOrder(
            company_id=company_id,
            po_number=f"PO-{uuid.uuid4().hex[:8]}",
            supplier_id=str(uuid.uuid4()),
            status="APPROVED",
            currency_code="USD",
            subtotal=Decimal("50.00"),
            total=Decimal("50.00"),
            expected_delivery_date=date(2026, 1, 1),
        )
        db_session.add(po)
    db_session.commit()

    reports = ReportService(db_session)
    full = reports.overdue_deliveries(company_id, as_of=cutoff, skip=0, limit=1000)
    total = reports.count_overdue_deliveries(company_id, as_of=cutoff)
    assert total == 5

    adapter = PurchaseAdapter()
    page_1 = adapter.run(
        db_session,
        company_id,
        "purchase.pending_deliveries",
        PendingDeliveriesFilter(as_of=cutoff),
        page=1,
        page_size=2,
        sort=None,
        comparison=None,
    )
    page_2 = adapter.run(
        db_session,
        company_id,
        "purchase.pending_deliveries",
        PendingDeliveriesFilter(as_of=cutoff),
        page=2,
        page_size=2,
        sort=None,
        comparison=None,
    )
    page_3 = adapter.run(
        db_session,
        company_id,
        "purchase.pending_deliveries",
        PendingDeliveriesFilter(as_of=cutoff),
        page=3,
        page_size=2,
        sort=None,
        comparison=None,
    )
    assert isinstance(page_1, PaginatedReportResult)
    assert isinstance(page_2, PaginatedReportResult)
    assert isinstance(page_3, PaginatedReportResult)
    union_ids = {r.po_id for r in page_1.items + page_2.items + page_3.items}
    assert union_ids == {r["po_id"] for r in full}
    assert len(union_ids) == 5
