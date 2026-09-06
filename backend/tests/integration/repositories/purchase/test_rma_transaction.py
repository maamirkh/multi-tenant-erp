"""Integration tests for RMA repository transaction behaviour — T186.

Tests:
  - VendorReturnRepository: create, get_by_id_or_none, list_for_company
  - VendorReturnRepository: update_status transitions
  - VendorReturnRepository: status/gr_id/supplier_id filters
  - ReturnLineRepository: list_for_rma, delete_all_for_rma
  - Company isolation: RMA from company A invisible to company B
  - Soft-delete: is_deleted=True rows excluded from reads

Task: T186
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from modules.purchase.models.vendor_return import ReturnLine, VendorReturn
from modules.purchase.repositories.vendor_return import (
    ReturnLineRepository,
    VendorReturnRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rma(
    db: Session,
    company_id,
    gr_id: str | None = None,
    status: str = "DRAFT",
    supplier_id: str | None = None,
) -> VendorReturn:
    rma = VendorReturn(
        id=uuid4(),
        company_id=company_id,
        rma_number=f"RMA-TEST-{uuid4().hex[:8]}",
        status=status,
        gr_id=gr_id or str(uuid4()),
        supplier_id=supplier_id or str(uuid4()),
        credit_note_pending=False,
    )
    db.add(rma)
    db.flush()
    return rma


def _make_return_line(
    db: Session,
    rma: VendorReturn,
    gr_line_id: str | None = None,
    qty_returned: str = "3.000",
) -> ReturnLine:
    ln = ReturnLine(
        id=uuid4(),
        company_id=rma.company_id,
        return_id=str(rma.id),
        gr_line_id=gr_line_id or str(uuid4()),
        quantity_returned=Decimal(qty_returned),
    )
    db.add(ln)
    db.flush()
    return ln


# ---------------------------------------------------------------------------
# VendorReturnRepository tests
# ---------------------------------------------------------------------------


class TestVendorReturnRepository:
    def test_get_by_id_returns_rma(self, db_session: Session):
        cid = uuid4()
        rma = _make_rma(db_session, cid)
        repo = VendorReturnRepository(db_session)

        fetched = repo.get_by_id_or_none(rma.id, cid)
        assert fetched is not None
        assert fetched.id == rma.id
        assert fetched.status == "DRAFT"

    def test_get_by_id_wrong_company_returns_none(self, db_session: Session):
        cid_a = uuid4()
        cid_b = uuid4()
        rma = _make_rma(db_session, cid_a)
        repo = VendorReturnRepository(db_session)

        result = repo.get_by_id_or_none(rma.id, cid_b)
        assert result is None

    def test_list_for_company_returns_all(self, db_session: Session):
        cid = uuid4()
        _make_rma(db_session, cid)
        _make_rma(db_session, cid)
        repo = VendorReturnRepository(db_session)

        items = repo.list_for_company(cid)
        assert len(items) >= 2

    def test_list_for_company_status_filter(self, db_session: Session):
        cid = uuid4()
        _make_rma(db_session, cid, status="DRAFT")
        _make_rma(db_session, cid, status="SUBMITTED")
        repo = VendorReturnRepository(db_session)

        drafts = repo.list_for_company(cid, status="DRAFT")
        submitted = repo.list_for_company(cid, status="SUBMITTED")
        assert all(r.status == "DRAFT" for r in drafts)
        assert all(r.status == "SUBMITTED" for r in submitted)

    def test_list_for_company_gr_id_filter(self, db_session: Session):
        cid = uuid4()
        gr_id = str(uuid4())
        _make_rma(db_session, cid, gr_id=gr_id)
        _make_rma(db_session, cid)  # different GR
        repo = VendorReturnRepository(db_session)

        filtered = repo.list_for_company(cid, gr_id=gr_id)
        assert len(filtered) == 1
        assert filtered[0].gr_id == gr_id

    def test_update_status_changes_status(self, db_session: Session):
        cid = uuid4()
        rma = _make_rma(db_session, cid, status="DRAFT")
        repo = VendorReturnRepository(db_session)

        repo.update_status(rma.id, cid, "SUBMITTED")

        fetched = repo.get_by_id_or_none(rma.id, cid)
        assert fetched.status == "SUBMITTED"

    def test_soft_deleted_rma_not_returned(self, db_session: Session):
        cid = uuid4()
        rma = _make_rma(db_session, cid)
        rma.is_deleted = True
        db_session.flush()
        repo = VendorReturnRepository(db_session)

        result = repo.get_by_id_or_none(rma.id, cid)
        assert result is None

        items = repo.list_for_company(cid)
        assert all(item.id != rma.id for item in items)

    def test_count_for_company(self, db_session: Session):
        cid = uuid4()
        _make_rma(db_session, cid)
        _make_rma(db_session, cid)
        repo = VendorReturnRepository(db_session)

        total = repo.count_for_company(cid)
        assert total >= 2


# ---------------------------------------------------------------------------
# ReturnLineRepository tests
# ---------------------------------------------------------------------------


class TestReturnLineRepository:
    def test_list_for_rma_returns_lines(self, db_session: Session):
        cid = uuid4()
        rma = _make_rma(db_session, cid)
        _make_return_line(db_session, rma)
        _make_return_line(db_session, rma)
        repo = ReturnLineRepository(db_session)

        lines = repo.list_for_rma(rma.id, cid)
        assert len(lines) == 2

    def test_list_for_rma_tenant_isolation(self, db_session: Session):
        cid_a = uuid4()
        cid_b = uuid4()
        rma_a = _make_rma(db_session, cid_a)
        _make_return_line(db_session, rma_a)
        repo = ReturnLineRepository(db_session)

        lines_b = repo.list_for_rma(rma_a.id, cid_b)
        assert len(lines_b) == 0

    def test_delete_all_for_rma_soft_deletes(self, db_session: Session):
        cid = uuid4()
        rma = _make_rma(db_session, cid)
        _make_return_line(db_session, rma)
        _make_return_line(db_session, rma)
        repo = ReturnLineRepository(db_session)

        count = repo.delete_all_for_rma(rma.id, cid)
        assert count == 2

        remaining = repo.list_for_rma(rma.id, cid)
        assert len(remaining) == 0
