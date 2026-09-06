"""Integration tests for PurchaseOrder repositories — Phase 5.

Tests:
  - PurchaseOrderRepository: CRUD, multi-status filter, supplier filter,
    tenant isolation, overdue query, version increment, open PO total
  - POLineRepository: list_for_po, max_line_number, update_received_qty,
    delete_all_for_po
  - POAdditionalChargeRepository: list_for_po
  - POAmendmentRepository: list_for_po, get_max_amendment_number

All tests run against SQLite in-memory DB via conftest.py fixtures.

Task: T144
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from modules.purchase.models.purchase_order import (
    POAdditionalCharge,
    POAmendment,
    POLine,
    PurchaseOrder,
)
from modules.purchase.repositories.purchase_order import (
    POAdditionalChargeRepository,
    POAmendmentRepository,
    POLineRepository,
    PurchaseOrderRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_po(
    db: Session,
    company_id: UUID,
    *,
    po_number: str = "PO-2026-000001",
    status: str = "DRAFT",
    supplier_id: str | None = None,
    expected_delivery_date: date | None = None,
    total: Decimal = Decimal("0.00"),
) -> PurchaseOrder:
    po = PurchaseOrder(
        company_id=company_id,
        po_number=po_number,
        status=status,
        supplier_id=supplier_id or str(uuid4()),
        currency_code="USD",
        subtotal=total,
        total_charges=Decimal("0.00"),
        total_discounts=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total=total,
        version=1,
    )
    if expected_delivery_date is not None:
        po.expected_delivery_date = expected_delivery_date
    db.add(po)
    db.flush()
    return po


def _add_line(
    db: Session,
    company_id: UUID,
    po_id: UUID,
    line_number: int = 1,
    description: str = "Widget",
    qty: Decimal = Decimal("5.000"),
    unit_cost: Decimal = Decimal("10.0000"),
) -> POLine:
    line = POLine(
        company_id=company_id,
        po_id=str(po_id),
        line_number=line_number,
        product_description=description,
        quantity_ordered=qty,
        unit_cost=unit_cost,
        open_quantity=qty,
        line_total=(qty * unit_cost).quantize(Decimal("0.01")),
    )
    db.add(line)
    db.flush()
    return line


def _add_charge(
    db: Session,
    company_id: UUID,
    po_id: UUID,
    charge_type: str = "FREIGHT",
    amount: Decimal = Decimal("25.00"),
) -> POAdditionalCharge:
    charge = POAdditionalCharge(
        company_id=company_id,
        po_id=str(po_id),
        charge_type=charge_type,
        description=f"{charge_type} charge",
        amount=amount,
    )
    db.add(charge)
    db.flush()
    return charge


def _add_amendment(
    db: Session,
    company_id: UUID,
    po_id: UUID,
    amendment_number: int = 1,
    reason: str = "Price correction",
) -> POAmendment:
    amend = POAmendment(
        company_id=company_id,
        po_id=str(po_id),
        amendment_number=amendment_number,
        reason=reason,
        status="PENDING",
    )
    db.add(amend)
    db.flush()
    return amend


# ===========================================================================
# PurchaseOrderRepository — CRUD
# ===========================================================================


class TestPurchaseOrderRepositoryCRUD:
    def test_create_and_get(self, db_session: Session):
        company_id = uuid4()
        repo = PurchaseOrderRepository(db_session)
        po = _add_po(db_session, company_id)

        fetched = repo.get_by_id_or_none(po.id, company_id)
        assert fetched is not None
        assert fetched.po_number == "PO-2026-000001"
        assert fetched.status == "DRAFT"

    def test_soft_delete(self, db_session: Session):
        company_id = uuid4()
        repo = PurchaseOrderRepository(db_session)
        po = _add_po(db_session, company_id)

        repo.soft_delete(po.id, company_id)
        fetched = repo.get_by_id_or_none(po.id, company_id)
        assert fetched is None

    def test_get_by_po_number(self, db_session: Session):
        company_id = uuid4()
        repo = PurchaseOrderRepository(db_session)
        _add_po(db_session, company_id, po_number="PO-2026-000042")

        found = repo.get_by_po_number("PO-2026-000042", company_id)
        assert found is not None
        assert found.po_number == "PO-2026-000042"

    def test_get_by_po_number_returns_none_for_other_company(self, db_session: Session):
        company_a = uuid4()
        company_b = uuid4()
        repo = PurchaseOrderRepository(db_session)
        _add_po(db_session, company_a, po_number="PO-2026-000001")

        result = repo.get_by_po_number("PO-2026-000001", company_b)
        assert result is None


# ===========================================================================
# PurchaseOrderRepository — list + filters
# ===========================================================================


class TestPurchaseOrderListFilters:
    def test_list_returns_company_pos_only(self, db_session: Session):
        company_a = uuid4()
        company_b = uuid4()
        repo = PurchaseOrderRepository(db_session)
        _add_po(db_session, company_a, po_number="PO-A-001")
        _add_po(db_session, company_a, po_number="PO-A-002")
        _add_po(db_session, company_b, po_number="PO-B-001")

        results = repo.list_for_company(company_a)
        assert len(results) == 2
        numbers = {po.po_number for po in results}
        assert numbers == {"PO-A-001", "PO-A-002"}

    def test_filter_by_single_status(self, db_session: Session):
        company_id = uuid4()
        repo = PurchaseOrderRepository(db_session)
        _add_po(db_session, company_id, po_number="PO-D-001", status="DRAFT")
        _add_po(db_session, company_id, po_number="PO-A-001", status="APPROVED")
        _add_po(db_session, company_id, po_number="PO-A-002", status="APPROVED")

        drafts = repo.list_for_company(company_id, status="DRAFT")
        assert len(drafts) == 1
        assert drafts[0].status == "DRAFT"

        approved = repo.list_for_company(company_id, status="APPROVED")
        assert len(approved) == 2

    def test_filter_by_multiple_statuses(self, db_session: Session):
        company_id = uuid4()
        repo = PurchaseOrderRepository(db_session)
        _add_po(db_session, company_id, po_number="PO-1", status="APPROVED")
        _add_po(db_session, company_id, po_number="PO-2", status="PARTIALLY_RECEIVED")
        _add_po(db_session, company_id, po_number="PO-3", status="CLOSED")

        open_pos = repo.list_for_company(
            company_id, statuses=["APPROVED", "PARTIALLY_RECEIVED"]
        )
        assert len(open_pos) == 2

    def test_filter_by_supplier(self, db_session: Session):
        company_id = uuid4()
        supplier_a = str(uuid4())
        supplier_b = str(uuid4())
        repo = PurchaseOrderRepository(db_session)
        _add_po(db_session, company_id, po_number="PO-SA-1", supplier_id=supplier_a)
        _add_po(db_session, company_id, po_number="PO-SA-2", supplier_id=supplier_a)
        _add_po(db_session, company_id, po_number="PO-SB-1", supplier_id=supplier_b)

        results = repo.list_for_company(company_id, supplier_id=supplier_a)
        assert len(results) == 2
        for po in results:
            assert po.supplier_id == supplier_a

    def test_count_for_company(self, db_session: Session):
        company_id = uuid4()
        repo = PurchaseOrderRepository(db_session)
        _add_po(db_session, company_id, po_number="PO-C-001", status="DRAFT")
        _add_po(db_session, company_id, po_number="PO-C-002", status="APPROVED")

        total = repo.count_for_company(company_id)
        assert total == 2

        draft_count = repo.count_for_company(company_id, status="DRAFT")
        assert draft_count == 1

    def test_excludes_soft_deleted_from_list(self, db_session: Session):
        company_id = uuid4()
        repo = PurchaseOrderRepository(db_session)
        po1 = _add_po(db_session, company_id, po_number="PO-1")
        po2 = _add_po(db_session, company_id, po_number="PO-2")
        repo.soft_delete(po2.id, company_id)

        results = repo.list_for_company(company_id)
        assert len(results) == 1
        assert results[0].id == po1.id


# ===========================================================================
# PurchaseOrderRepository — status + version increment
# ===========================================================================


class TestUpdateStatusAndVersion:
    def test_update_status_changes_status(self, db_session: Session):
        company_id = uuid4()
        repo = PurchaseOrderRepository(db_session)
        po = _add_po(db_session, company_id, status="DRAFT")

        repo.update_status(po.id, company_id, "PENDING_APPROVAL")
        db_session.expire(po)

        fetched = repo.get_by_id_or_none(po.id, company_id)
        assert fetched is not None
        assert fetched.status == "PENDING_APPROVAL"

    def test_update_status_increments_version(self, db_session: Session):
        company_id = uuid4()
        repo = PurchaseOrderRepository(db_session)
        po = _add_po(db_session, company_id, status="DRAFT")
        initial_version = po.version  # 1

        repo.update_status(po.id, company_id, "PENDING_APPROVAL")
        db_session.expire(po)

        fetched = repo.get_by_id_or_none(po.id, company_id)
        assert fetched is not None
        assert fetched.version == initial_version + 1

    def test_update_status_respects_company_isolation(self, db_session: Session):
        company_a = uuid4()
        company_b = uuid4()
        repo = PurchaseOrderRepository(db_session)
        po_a = _add_po(db_session, company_a, status="DRAFT")

        # Attempt update using wrong company_id — should not change anything
        repo.update_status(po_a.id, company_b, "APPROVED")
        db_session.expire(po_a)

        fetched = repo.get_by_id_or_none(po_a.id, company_a)
        assert fetched is not None
        assert fetched.status == "DRAFT"  # unchanged


# ===========================================================================
# PurchaseOrderRepository — overdue query
# ===========================================================================


class TestOverduePOQuery:
    def test_returns_approved_pos_with_past_delivery_date(self, db_session: Session):
        company_id = uuid4()
        repo = PurchaseOrderRepository(db_session)
        past_date = date.today() - timedelta(days=5)
        future_date = date.today() + timedelta(days=5)

        _add_po(
            db_session,
            company_id,
            po_number="PO-OVERDUE",
            status="APPROVED",
            expected_delivery_date=past_date,
        )
        _add_po(
            db_session,
            company_id,
            po_number="PO-FUTURE",
            status="APPROVED",
            expected_delivery_date=future_date,
        )

        overdue = repo.get_overdue_pos(company_id)
        assert len(overdue) == 1
        assert overdue[0].po_number == "PO-OVERDUE"

    def test_includes_partially_received_overdue(self, db_session: Session):
        company_id = uuid4()
        repo = PurchaseOrderRepository(db_session)
        past_date = date.today() - timedelta(days=2)

        _add_po(
            db_session,
            company_id,
            po_number="PO-PR-OD",
            status="PARTIALLY_RECEIVED",
            expected_delivery_date=past_date,
        )

        overdue = repo.get_overdue_pos(company_id)
        assert any(p.po_number == "PO-PR-OD" for p in overdue)

    def test_excludes_closed_cancelled_from_overdue(self, db_session: Session):
        company_id = uuid4()
        repo = PurchaseOrderRepository(db_session)
        past_date = date.today() - timedelta(days=3)

        _add_po(
            db_session,
            company_id,
            po_number="PO-CL",
            status="CLOSED",
            expected_delivery_date=past_date,
        )
        _add_po(
            db_session,
            company_id,
            po_number="PO-CA",
            status="CANCELLED",
            expected_delivery_date=past_date,
        )

        overdue = repo.get_overdue_pos(company_id)
        assert len(overdue) == 0

    def test_overdue_respects_tenant_isolation(self, db_session: Session):
        company_a = uuid4()
        company_b = uuid4()
        repo = PurchaseOrderRepository(db_session)
        past_date = date.today() - timedelta(days=1)

        _add_po(
            db_session,
            company_a,
            po_number="PO-A-OD",
            status="APPROVED",
            expected_delivery_date=past_date,
        )

        overdue_b = repo.get_overdue_pos(company_b)
        assert len(overdue_b) == 0


# ===========================================================================
# PurchaseOrderRepository — open PO total for supplier
# ===========================================================================


class TestOpenPOTotalForSupplier:
    def test_sums_open_pos_for_supplier(self, db_session: Session):
        company_id = uuid4()
        supplier_id = str(uuid4())
        repo = PurchaseOrderRepository(db_session)

        _add_po(
            db_session,
            company_id,
            po_number="PO-SU-1",
            supplier_id=supplier_id,
            status="APPROVED",
            total=Decimal("500.00"),
        )
        _add_po(
            db_session,
            company_id,
            po_number="PO-SU-2",
            supplier_id=supplier_id,
            status="PENDING_APPROVAL",
            total=Decimal("200.00"),
        )

        total = repo.get_open_po_total_for_supplier(supplier_id, company_id)
        assert total == Decimal("700.00")

    def test_excludes_closed_and_cancelled_from_total(self, db_session: Session):
        company_id = uuid4()
        supplier_id = str(uuid4())
        repo = PurchaseOrderRepository(db_session)

        _add_po(
            db_session,
            company_id,
            po_number="PO-CL",
            supplier_id=supplier_id,
            status="CLOSED",
            total=Decimal("1000.00"),
        )
        _add_po(
            db_session,
            company_id,
            po_number="PO-CA",
            supplier_id=supplier_id,
            status="CANCELLED",
            total=Decimal("500.00"),
        )

        total = repo.get_open_po_total_for_supplier(supplier_id, company_id)
        assert total == Decimal("0")

    def test_returns_zero_for_unknown_supplier(self, db_session: Session):
        company_id = uuid4()
        repo = PurchaseOrderRepository(db_session)

        total = repo.get_open_po_total_for_supplier(str(uuid4()), company_id)
        assert total == Decimal("0")


# ===========================================================================
# POLineRepository
# ===========================================================================


class TestPOLineRepository:
    def test_list_for_po_returns_lines_in_order(self, db_session: Session):
        company_id = uuid4()
        po = _add_po(db_session, company_id)
        repo = POLineRepository(db_session)

        _add_line(db_session, company_id, po.id, line_number=3)
        _add_line(db_session, company_id, po.id, line_number=1)
        _add_line(db_session, company_id, po.id, line_number=2)

        lines = repo.list_for_po(po.id, company_id)
        assert [ln.line_number for ln in lines] == [1, 2, 3]

    def test_list_for_po_excludes_soft_deleted(self, db_session: Session):
        company_id = uuid4()
        po = _add_po(db_session, company_id)
        repo = POLineRepository(db_session)

        line1 = _add_line(db_session, company_id, po.id, line_number=1)
        line2 = _add_line(db_session, company_id, po.id, line_number=2)

        repo.soft_delete(line2.id, company_id)
        lines = repo.list_for_po(po.id, company_id)
        assert len(lines) == 1
        assert lines[0].id == line1.id

    def test_get_max_line_number_no_lines(self, db_session: Session):
        company_id = uuid4()
        po = _add_po(db_session, company_id)
        repo = POLineRepository(db_session)

        assert repo.get_max_line_number(po.id, company_id) == 0

    def test_get_max_line_number_with_lines(self, db_session: Session):
        company_id = uuid4()
        po = _add_po(db_session, company_id)
        repo = POLineRepository(db_session)

        _add_line(db_session, company_id, po.id, line_number=1)
        _add_line(db_session, company_id, po.id, line_number=2)
        _add_line(db_session, company_id, po.id, line_number=5)

        assert repo.get_max_line_number(po.id, company_id) == 5

    def test_update_received_qty(self, db_session: Session):
        company_id = uuid4()
        po = _add_po(db_session, company_id)
        repo = POLineRepository(db_session)
        line = _add_line(
            db_session,
            company_id,
            po.id,
            qty=Decimal("10.000"),
            unit_cost=Decimal("5.0000"),
        )

        repo.update_received_qty(
            line.id,
            company_id,
            quantity_received=Decimal("7.000"),
            quantity_rejected=Decimal("0.000"),
            open_quantity=Decimal("3.000"),
        )
        db_session.expire(line)

        fetched = repo.get_by_id_or_none(line.id, company_id)
        assert fetched is not None
        assert Decimal(str(fetched.quantity_received)) == Decimal("7.000")
        assert Decimal(str(fetched.open_quantity)) == Decimal("3.000")

    def test_delete_all_for_po(self, db_session: Session):
        company_id = uuid4()
        po = _add_po(db_session, company_id)
        repo = POLineRepository(db_session)

        _add_line(db_session, company_id, po.id, line_number=1)
        _add_line(db_session, company_id, po.id, line_number=2)

        repo.delete_all_for_po(po.id, company_id)
        lines = repo.list_for_po(po.id, company_id)
        assert len(lines) == 0

    def test_list_for_po_tenant_isolation(self, db_session: Session):
        company_a = uuid4()
        company_b = uuid4()
        po_a = _add_po(db_session, company_a)
        repo = POLineRepository(db_session)
        _add_line(db_session, company_a, po_a.id, line_number=1)

        # Query lines for po_a.id but from company_b — should return nothing
        lines = repo.list_for_po(po_a.id, company_b)
        assert len(lines) == 0


# ===========================================================================
# POAdditionalChargeRepository
# ===========================================================================


class TestPOAdditionalChargeRepository:
    def test_list_charges_for_po(self, db_session: Session):
        company_id = uuid4()
        po = _add_po(db_session, company_id)
        repo = POAdditionalChargeRepository(db_session)

        _add_charge(
            db_session,
            company_id,
            po.id,
            charge_type="FREIGHT",
            amount=Decimal("50.00"),
        )
        _add_charge(
            db_session,
            company_id,
            po.id,
            charge_type="HANDLING",
            amount=Decimal("10.00"),
        )

        charges = repo.list_for_po(po.id, company_id)
        assert len(charges) == 2

    def test_list_charges_excludes_soft_deleted(self, db_session: Session):
        company_id = uuid4()
        po = _add_po(db_session, company_id)
        repo = POAdditionalChargeRepository(db_session)

        c1 = _add_charge(db_session, company_id, po.id, charge_type="FREIGHT")
        c2 = _add_charge(db_session, company_id, po.id, charge_type="HANDLING")
        repo.soft_delete(c2.id, company_id)

        charges = repo.list_for_po(po.id, company_id)
        assert len(charges) == 1
        assert charges[0].id == c1.id

    def test_list_charges_tenant_isolation(self, db_session: Session):
        company_a = uuid4()
        company_b = uuid4()
        po_a = _add_po(db_session, company_a)
        repo = POAdditionalChargeRepository(db_session)
        _add_charge(db_session, company_a, po_a.id)

        charges = repo.list_for_po(po_a.id, company_b)
        assert len(charges) == 0


# ===========================================================================
# POAmendmentRepository (append-only)
# ===========================================================================


class TestPOAmendmentRepository:
    def test_list_amendments_in_order(self, db_session: Session):
        company_id = uuid4()
        po = _add_po(db_session, company_id)
        repo = POAmendmentRepository(db_session)

        _add_amendment(
            db_session, company_id, po.id, amendment_number=2, reason="Second"
        )
        _add_amendment(
            db_session, company_id, po.id, amendment_number=1, reason="First"
        )

        amendments = repo.list_for_po(po.id, company_id)
        assert [a.amendment_number for a in amendments] == [1, 2]

    def test_get_max_amendment_number_zero_for_no_amendments(self, db_session: Session):
        company_id = uuid4()
        po = _add_po(db_session, company_id)
        repo = POAmendmentRepository(db_session)

        assert repo.get_max_amendment_number(po.id, company_id) == 0

    def test_get_max_amendment_number_with_amendments(self, db_session: Session):
        company_id = uuid4()
        po = _add_po(db_session, company_id)
        repo = POAmendmentRepository(db_session)

        _add_amendment(db_session, company_id, po.id, amendment_number=1)
        _add_amendment(db_session, company_id, po.id, amendment_number=2)
        _add_amendment(db_session, company_id, po.id, amendment_number=3)

        assert repo.get_max_amendment_number(po.id, company_id) == 3

    def test_list_amendments_tenant_isolation(self, db_session: Session):
        company_a = uuid4()
        company_b = uuid4()
        po_a = _add_po(db_session, company_a)
        repo = POAmendmentRepository(db_session)
        _add_amendment(db_session, company_a, po_a.id, amendment_number=1)

        amendments = repo.list_for_po(po_a.id, company_b)
        assert len(amendments) == 0
