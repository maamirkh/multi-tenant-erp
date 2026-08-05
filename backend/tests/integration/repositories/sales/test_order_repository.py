"""Integration tests for Sales Order repositories — Phase 4.

Tests:
  - SalesOrderRepository: create, get_by_id_or_none, get_by_number, list_for_company,
    count_for_company, list_pending_approval, list_by_customer,
    get_outstanding_total_for_customer, soft-delete isolation
  - OrderLineRepository: list_for_order, next_line_number
  - Tenant isolation (company_id boundary enforcement)

Task: T132
Spec ref: specs/007-sales-management/spec.md §Sales Orders
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from modules.sales.models.order import OrderLine, SalesOrder
from modules.sales.repositories.order import OrderLineRepository, SalesOrderRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_order(
    company_id: UUID,
    customer_id: str | None = None,
    status: str = "DRAFT",
    order_number: str | None = None,
    total_amount: str = "0.00",
) -> SalesOrder:
    return SalesOrder(
        company_id=company_id,
        order_number=order_number or f"SO-TEST-{uuid4().hex[:8]}",
        customer_id=customer_id or str(uuid4()),
        order_date="2026-08-02",
        currency_code="USD",
        sales_rep_id=str(uuid4()),
        priority="NORMAL",
        status=status,
        subtotal=Decimal(total_amount),
        discount_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        charges_amount=Decimal("0"),
        total_amount=Decimal(total_amount),
        approval_version=1,
        version=1,
    )


def _make_line(
    company_id: UUID,
    order_id: str,
    line_number: int = 1,
    qty: str = "5",
    price: str = "20.00",
) -> OrderLine:
    ext = (Decimal(qty) * Decimal(price)).quantize(Decimal("0.01"))
    return OrderLine(
        company_id=company_id,
        order_id=order_id,
        line_number=line_number,
        description=f"Test product line {line_number}",
        quantity_ordered=Decimal(qty),
        quantity_delivered=Decimal("0"),
        unit_of_measure="EA",
        unit_price=Decimal(price),
        extended_amount=ext,
        delivery_status="PENDING",
    )


# ---------------------------------------------------------------------------
# SalesOrderRepository
# ---------------------------------------------------------------------------


class TestSalesOrderRepository:
    def test_create_and_get_by_id(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesOrderRepository(db_session)
        order = _make_order(company_id)
        db_session.add(order)
        db_session.flush()

        found = repo.get_by_id_or_none(order.id, company_id)
        assert found is not None
        assert found.order_number == order.order_number

    def test_get_by_id_returns_none_for_missing(self, db_session: Session) -> None:
        repo = SalesOrderRepository(db_session)
        result = repo.get_by_id_or_none(uuid4(), uuid4())
        assert result is None

    def test_get_by_number(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesOrderRepository(db_session)
        num = f"SO-2026-{uuid4().hex[:6]}"
        order = _make_order(company_id, order_number=num)
        db_session.add(order)
        db_session.flush()

        found = repo.get_by_number(company_id, num)
        assert found is not None
        assert found.order_number == num

    def test_get_by_number_returns_none_for_missing(self, db_session: Session) -> None:
        repo = SalesOrderRepository(db_session)
        result = repo.get_by_number(uuid4(), "SO-NONEXISTENT")
        assert result is None

    def test_list_for_company_returns_all(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesOrderRepository(db_session)
        for _ in range(3):
            db_session.add(_make_order(company_id))
        db_session.flush()

        results = repo.list_for_company(company_id)
        assert len(results) >= 3

    def test_list_for_company_status_filter(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesOrderRepository(db_session)
        db_session.add(_make_order(company_id, status="DRAFT"))
        db_session.add(_make_order(company_id, status="APPROVED"))
        db_session.flush()

        drafts = repo.list_for_company(company_id, status="DRAFT")
        assert all(o.status == "DRAFT" for o in drafts)

        approved = repo.list_for_company(company_id, status="APPROVED")
        assert all(o.status == "APPROVED" for o in approved)

    def test_list_for_company_customer_filter(self, db_session: Session) -> None:
        company_id = uuid4()
        cust_a = str(uuid4())
        cust_b = str(uuid4())
        repo = SalesOrderRepository(db_session)
        db_session.add(_make_order(company_id, customer_id=cust_a))
        db_session.add(_make_order(company_id, customer_id=cust_b))
        db_session.flush()

        results = repo.list_for_company(company_id, customer_id=UUID(cust_a))
        assert all(o.customer_id == cust_a for o in results)
        assert len(results) >= 1

    def test_list_for_company_search_filter(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesOrderRepository(db_session)
        unique_num = f"SO-UNIQUE-{uuid4().hex[:6]}"
        db_session.add(_make_order(company_id, order_number=unique_num))
        db_session.flush()

        results = repo.list_for_company(company_id, search="SO-UNIQUE")
        assert any(o.order_number == unique_num for o in results)

    def test_count_for_company(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesOrderRepository(db_session)
        for _ in range(4):
            db_session.add(_make_order(company_id))
        db_session.flush()

        count = repo.count_for_company(company_id)
        assert count >= 4

    def test_count_with_status_filter(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesOrderRepository(db_session)
        db_session.add(_make_order(company_id, status="DRAFT"))
        db_session.add(_make_order(company_id, status="DRAFT"))
        db_session.add(_make_order(company_id, status="APPROVED"))
        db_session.flush()

        draft_count = repo.count_for_company(company_id, status="DRAFT")
        assert draft_count >= 2

    def test_list_pending_approval(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesOrderRepository(db_session)
        db_session.add(_make_order(company_id, status="PENDING_APPROVAL"))
        db_session.add(_make_order(company_id, status="DRAFT"))
        db_session.flush()

        pending = repo.list_pending_approval(company_id)
        assert all(o.status == "PENDING_APPROVAL" for o in pending)
        assert len(pending) >= 1

    def test_list_by_customer(self, db_session: Session) -> None:
        company_id = uuid4()
        cust_id = uuid4()
        repo = SalesOrderRepository(db_session)
        db_session.add(_make_order(company_id, customer_id=str(cust_id)))
        db_session.add(_make_order(company_id, customer_id=str(cust_id)))
        db_session.add(_make_order(company_id))  # different customer
        db_session.flush()

        results = repo.list_by_customer(company_id, cust_id)
        assert all(o.customer_id == str(cust_id) for o in results)
        assert len(results) >= 2

    def test_get_outstanding_total_for_customer(self, db_session: Session) -> None:
        company_id = uuid4()
        cust_id = uuid4()
        repo = SalesOrderRepository(db_session)
        db_session.add(
            _make_order(
                company_id,
                customer_id=str(cust_id),
                status="APPROVED",
                total_amount="1000.00",
            )
        )
        db_session.add(
            _make_order(
                company_id,
                customer_id=str(cust_id),
                status="PENDING_APPROVAL",
                total_amount="2000.00",
            )
        )
        db_session.add(
            _make_order(
                company_id,
                customer_id=str(cust_id),
                status="CLOSED",
                total_amount="500.00",
            )
        )  # excluded
        db_session.flush()

        total = repo.get_outstanding_total_for_customer(company_id, cust_id)
        assert Decimal(str(total)) >= Decimal("3000.00")
        assert Decimal(str(total)) < Decimal("3500.00")  # CLOSED not counted

    def test_soft_delete_excludes_from_results(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesOrderRepository(db_session)
        order = _make_order(company_id)
        db_session.add(order)
        db_session.flush()

        # Soft-delete
        order.is_deleted = True
        db_session.flush()

        found = repo.get_by_id_or_none(order.id, company_id)
        assert found is None

    def test_tenant_isolation(self, db_session: Session) -> None:
        """Orders from company A are not visible to company B."""
        company_a = uuid4()
        company_b = uuid4()
        repo = SalesOrderRepository(db_session)

        order_a = _make_order(company_a)
        db_session.add(order_a)
        db_session.flush()

        # Company B cannot see company A's order
        found = repo.get_by_id_or_none(order_a.id, company_b)
        assert found is None

        results_b = repo.list_for_company(company_b)
        ids = [o.id for o in results_b]
        assert order_a.id not in ids


# ---------------------------------------------------------------------------
# OrderLineRepository
# ---------------------------------------------------------------------------


class TestOrderLineRepository:
    def test_list_for_order(self, db_session: Session) -> None:
        company_id = uuid4()
        order = _make_order(company_id)
        db_session.add(order)
        db_session.flush()

        line_repo = OrderLineRepository(db_session)
        line1 = _make_line(company_id, str(order.id), line_number=1)
        line2 = _make_line(company_id, str(order.id), line_number=2)
        db_session.add(line1)
        db_session.add(line2)
        db_session.flush()

        lines = line_repo.list_for_order(company_id, order.id)
        assert len(lines) == 2
        numbers = {ln.line_number for ln in lines}
        assert numbers == {1, 2}

    def test_next_line_number_starts_at_one(self, db_session: Session) -> None:
        company_id = uuid4()
        order = _make_order(company_id)
        db_session.add(order)
        db_session.flush()

        line_repo = OrderLineRepository(db_session)
        next_num = line_repo.next_line_number(company_id, order.id)
        assert next_num == 1

    def test_next_line_number_increments(self, db_session: Session) -> None:
        company_id = uuid4()
        order = _make_order(company_id)
        db_session.add(order)
        db_session.flush()

        line_repo = OrderLineRepository(db_session)
        line = _make_line(company_id, str(order.id), line_number=1)
        db_session.add(line)
        db_session.flush()

        next_num = line_repo.next_line_number(company_id, order.id)
        assert next_num == 2

    def test_soft_deleted_lines_excluded(self, db_session: Session) -> None:
        company_id = uuid4()
        order = _make_order(company_id)
        db_session.add(order)
        db_session.flush()

        line_repo = OrderLineRepository(db_session)
        line = _make_line(company_id, str(order.id), line_number=1)
        db_session.add(line)
        db_session.flush()

        line.is_deleted = True
        db_session.flush()

        lines = line_repo.list_for_order(company_id, order.id)
        assert len(lines) == 0
