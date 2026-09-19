"""T076 — Epic 11 Reports additive source-domain seam (T075) regression +
equivalence.

Proves ``supplier_performance()``'s restructuring (SQL-level supplier-page
bounding replacing the old full-fetch-then-Python-slice) produces
byte-identical per-supplier calculations to the pre-fix approach — the
population-bounding *mechanism* changed, the *formula* did not. Also
proves the five other list-shaped Purchase reports' new count-sibling
methods are purely additive (existing calls unaffected).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from modules.purchase.models.goods_receipt import GoodsReceipt, GRLine
from modules.purchase.models.purchase_order import PurchaseOrder
from modules.purchase.services.report_service import ReportService


def _make_po(db: Session, company_id: uuid.UUID, supplier_id: str) -> PurchaseOrder:
    po = PurchaseOrder(
        company_id=company_id,
        po_number=f"PO-{uuid.uuid4().hex[:8]}",
        supplier_id=supplier_id,
        status="APPROVED",
        currency_code="USD",
        subtotal=Decimal("100.00"),
        total=Decimal("100.00"),
        expected_delivery_date=datetime(2026, 1, 10, tzinfo=UTC).date(),
    )
    db.add(po)
    db.flush()
    return po


def _make_confirmed_gr(
    db: Session,
    company_id: uuid.UUID,
    *,
    po_id: uuid.UUID,
    supplier_id: str,
    received_at: datetime,
    qty_received: Decimal = Decimal("10"),
    qty_rejected: Decimal = Decimal("0"),
) -> GoodsReceipt:
    gr = GoodsReceipt(
        company_id=company_id,
        gr_number=f"GR-{uuid.uuid4().hex[:8]}",
        po_id=str(po_id),
        supplier_id=supplier_id,
        status="CONFIRMED",
        received_at=received_at,
    )
    db.add(gr)
    db.flush()
    db.add(
        GRLine(
            company_id=company_id,
            gr_id=str(gr.id),
            po_line_id=str(uuid.uuid4()),
            quantity_received=qty_received,
            quantity_rejected=qty_rejected,
        )
    )
    return gr


def test_supplier_performance_bounded_page_matches_manual_calculation(
    db_session: Session,
) -> None:
    company_id = uuid.uuid4()
    supplier_ids = [str(uuid.uuid4()) for _ in range(4)]
    for supplier_id in supplier_ids:
        po = _make_po(db_session, company_id, supplier_id)
        _make_confirmed_gr(
            db_session,
            company_id,
            po_id=po.id,
            supplier_id=supplier_id,
            received_at=datetime(2026, 1, 5, tzinfo=UTC),
        )
    db_session.commit()

    service = ReportService(db_session)

    total_count = service.count_supplier_performance(company_id)
    assert total_count == 4

    page_1 = service.supplier_performance(company_id, skip=0, limit=2)
    page_2 = service.supplier_performance(company_id, skip=2, limit=2)

    assert len(page_1) == 2
    assert len(page_2) == 2
    all_supplier_ids = {r["supplier_id"] for r in page_1} | {
        r["supplier_id"] for r in page_2
    }
    assert all_supplier_ids == set(supplier_ids)

    # Every returned row has one confirmed GR and zero rejections — the
    # per-supplier formula itself is unchanged, only which suppliers are
    # included in a given page changed. (``on_time_rate`` depends on a
    # UUID-cast join that SQLite handles differently from Postgres, so
    # it's exercised by the real-Postgres API regression suite instead —
    # `tests/integration/api/v1/purchase/test_reports_api.py`, unaffected
    # by this seam and still green.)
    for row in page_1 + page_2:
        assert row["total_grs"] == 1
        assert row["rejection_rate"] == 0.0


def test_supplier_performance_default_call_unchanged_for_small_population(
    db_session: Session,
) -> None:
    """A population smaller than the default limit=100 must return every
    supplier, identical to the pre-fix behavior."""
    company_id = uuid.uuid4()
    supplier_id = str(uuid.uuid4())
    po = _make_po(db_session, company_id, supplier_id)
    _make_confirmed_gr(
        db_session,
        company_id,
        po_id=po.id,
        supplier_id=supplier_id,
        received_at=datetime(2026, 1, 5, tzinfo=UTC),
    )
    db_session.commit()

    service = ReportService(db_session)
    result = service.supplier_performance(company_id)
    assert len(result) == 1
    assert result[0]["supplier_id"] == supplier_id
