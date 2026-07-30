"""Integration tests for GR repository transaction behaviour — T164.

Tests:
  - GoodsReceiptRepository: create, get_by_id_or_none, list_for_company
  - GoodsReceiptRepository: update_status DRAFT → CONFIRMED
  - GoodsReceiptRepository: list_confirmed_for_po / has_confirmed_gr_for_po
  - GRLineRepository: list_for_gr, get_received_qty_for_po_line
  - GRLineRepository: delete_all_for_gr (soft-delete)
  - Company isolation: GR from company A invisible to company B
  - Soft-delete: is_deleted=True rows are excluded from reads

Task: T164
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from modules.purchase.models.goods_receipt import GoodsReceipt, GRLine
from modules.purchase.repositories.goods_receipt import (
    GoodsReceiptRepository,
    GRLineRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_gr(
    db: Session, company_id, po_id: str | None = None, status: str = "DRAFT"
) -> GoodsReceipt:
    gr = GoodsReceipt(
        id=uuid4(),
        company_id=company_id,
        gr_number=f"GR-TEST-{uuid4().hex[:8]}",
        status=status,
        po_id=po_id or str(uuid4()),
        supplier_id=str(uuid4()),
        landed_cost_ready=True,
    )
    db.add(gr)
    db.flush()
    return gr


def _make_gr_line(
    db: Session,
    gr: GoodsReceipt,
    po_line_id: str | None = None,
    qty_received: str = "5.000",
) -> GRLine:
    ln = GRLine(
        id=uuid4(),
        company_id=gr.company_id,
        gr_id=str(gr.id),
        po_line_id=po_line_id or str(uuid4()),
        quantity_received=Decimal(qty_received),
        quantity_rejected=Decimal("0.000"),
        unit_cost=Decimal("100.0000"),
        po_unit_cost=Decimal("100.0000"),
        ppv_amount=Decimal("0.00"),
        ppv_percentage=Decimal("0.0000"),
    )
    db.add(ln)
    db.flush()
    return ln


# ---------------------------------------------------------------------------
# GoodsReceiptRepository tests
# ---------------------------------------------------------------------------


class TestGoodsReceiptRepository:
    def test_get_by_id_returns_gr(self, db_session: Session):
        cid = uuid4()
        gr = _make_gr(db_session, cid)
        repo = GoodsReceiptRepository(db_session)

        fetched = repo.get_by_id_or_none(gr.id, cid)
        assert fetched is not None
        assert fetched.id == gr.id
        assert fetched.status == "DRAFT"

    def test_get_by_id_wrong_company_returns_none(self, db_session: Session):
        cid_a = uuid4()
        cid_b = uuid4()
        gr = _make_gr(db_session, cid_a)
        repo = GoodsReceiptRepository(db_session)

        result = repo.get_by_id_or_none(gr.id, cid_b)
        assert result is None

    def test_list_for_company_returns_all(self, db_session: Session):
        cid = uuid4()
        _make_gr(db_session, cid)
        _make_gr(db_session, cid)
        repo = GoodsReceiptRepository(db_session)

        items = repo.list_for_company(cid)
        assert len(items) >= 2

    def test_list_for_company_status_filter(self, db_session: Session):
        cid = uuid4()
        _make_gr(db_session, cid, status="DRAFT")
        _make_gr(db_session, cid, status="CONFIRMED")
        repo = GoodsReceiptRepository(db_session)

        drafts = repo.list_for_company(cid, status="DRAFT")
        confirmed = repo.list_for_company(cid, status="CONFIRMED")
        assert all(gr.status == "DRAFT" for gr in drafts)
        assert all(gr.status == "CONFIRMED" for gr in confirmed)

    def test_update_status_changes_status(self, db_session: Session):
        cid = uuid4()
        gr = _make_gr(db_session, cid, status="DRAFT")
        repo = GoodsReceiptRepository(db_session)

        repo.update_status(gr.id, cid, "CONFIRMED")

        fetched = repo.get_by_id_or_none(gr.id, cid)
        assert fetched.status == "CONFIRMED"

    def test_has_confirmed_gr_for_po_false_when_none(self, db_session: Session):
        cid = uuid4()
        po_id = str(uuid4())
        repo = GoodsReceiptRepository(db_session)

        result = repo.has_confirmed_gr_for_po(po_id, cid)
        assert result is False

    def test_has_confirmed_gr_for_po_true_when_exists(self, db_session: Session):
        cid = uuid4()
        po_id = str(uuid4())
        _make_gr(db_session, cid, po_id=po_id, status="CONFIRMED")
        repo = GoodsReceiptRepository(db_session)

        result = repo.has_confirmed_gr_for_po(po_id, cid)
        assert result is True

    def test_list_confirmed_for_po(self, db_session: Session):
        cid = uuid4()
        po_id = str(uuid4())
        _make_gr(db_session, cid, po_id=po_id, status="CONFIRMED")
        _make_gr(db_session, cid, po_id=po_id, status="DRAFT")
        repo = GoodsReceiptRepository(db_session)

        items = repo.list_confirmed_for_po(po_id, cid)
        assert len(items) == 1
        assert items[0].status == "CONFIRMED"

    def test_soft_deleted_gr_not_returned(self, db_session: Session):
        cid = uuid4()
        gr = _make_gr(db_session, cid)
        gr.is_deleted = True
        db_session.flush()
        repo = GoodsReceiptRepository(db_session)

        result = repo.get_by_id_or_none(gr.id, cid)
        assert result is None

        items = repo.list_for_company(cid)
        assert all(item.id != gr.id for item in items)


# ---------------------------------------------------------------------------
# GRLineRepository tests
# ---------------------------------------------------------------------------


class TestGRLineRepository:
    def test_list_for_gr_returns_lines(self, db_session: Session):
        cid = uuid4()
        gr = _make_gr(db_session, cid)
        _make_gr_line(db_session, gr)
        _make_gr_line(db_session, gr)
        repo = GRLineRepository(db_session)

        lines = repo.list_for_gr(gr.id, cid)
        assert len(lines) == 2

    def test_list_for_gr_tenant_isolation(self, db_session: Session):
        cid_a = uuid4()
        cid_b = uuid4()
        gr_a = _make_gr(db_session, cid_a)
        _make_gr_line(db_session, gr_a)
        repo = GRLineRepository(db_session)

        # Company B cannot see company A's GR lines
        lines_b = repo.list_for_gr(gr_a.id, cid_b)
        assert len(lines_b) == 0

    def test_get_received_qty_for_po_line_sums_confirmed(self, db_session: Session):
        cid = uuid4()
        po_line_id = str(uuid4())

        # CONFIRMED GR → should be included
        gr_confirmed = _make_gr(db_session, cid, status="CONFIRMED")
        _make_gr_line(
            db_session, gr_confirmed, po_line_id=po_line_id, qty_received="6.000"
        )

        # DRAFT GR → should NOT be included
        gr_draft = _make_gr(db_session, cid, status="DRAFT")
        _make_gr_line(db_session, gr_draft, po_line_id=po_line_id, qty_received="4.000")

        repo = GRLineRepository(db_session)
        total = repo.get_received_qty_for_po_line(po_line_id, cid)
        assert total == Decimal("6.000")

    def test_get_received_qty_zero_when_no_confirmed(self, db_session: Session):
        cid = uuid4()
        po_line_id = str(uuid4())
        repo = GRLineRepository(db_session)

        total = repo.get_received_qty_for_po_line(po_line_id, cid)
        assert total == Decimal("0")

    def test_delete_all_for_gr_soft_deletes(self, db_session: Session):
        cid = uuid4()
        gr = _make_gr(db_session, cid)
        _make_gr_line(db_session, gr)
        _make_gr_line(db_session, gr)
        repo = GRLineRepository(db_session)

        count = repo.delete_all_for_gr(gr.id, cid)
        assert count == 2

        remaining = repo.list_for_gr(gr.id, cid)
        assert len(remaining) == 0

    def test_count_for_company(self, db_session: Session):
        cid = uuid4()
        _make_gr(db_session, cid)
        _make_gr(db_session, cid)
        repo = GoodsReceiptRepository(db_session)

        total = repo.count_for_company(cid)
        assert total >= 2
