"""Integration tests for Phase 4 Purchase Request repositories — T116.

Tests:
  - PurchaseRequestRepository: CRUD, status filter, requestor filter, company isolation
  - PRLineRepository: CRUD, list_for_pr, max_line_number, delete_all_for_pr
  - update_status / update_total_cost / set_converted_to_po helpers

All tests run against SQLite in-memory DB via conftest.py fixtures.

Task: T116
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from modules.purchase.models.purchase_request import PRLine, PurchaseRequest
from modules.purchase.repositories.purchase_request import (
    PRLineRepository,
    PurchaseRequestRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_pr(
    db_session: Session,
    company_id: UUID,
    *,
    pr_number: str = "PR-2026-000001",
    title: str = "Test PR",
    status: str = "DRAFT",
    requestor_id: UUID | None = None,
) -> PurchaseRequest:
    pr = PurchaseRequest(
        company_id=company_id,
        pr_number=pr_number,
        title=title,
        status=status,
        requestor_id=str(requestor_id or uuid4()),
        total_estimated_cost=Decimal("0.00"),
        currency_code="USD",
    )
    db_session.add(pr)
    db_session.flush()
    return pr


def _add_line(
    db_session: Session,
    company_id: UUID,
    pr_id: UUID,
    line_number: int = 1,
    description: str = "Widget",
    qty: Decimal = Decimal("1.000"),
    unit_cost: Decimal = Decimal("10.0000"),
) -> PRLine:
    line = PRLine(
        company_id=company_id,
        pr_id=str(pr_id),
        line_number=line_number,
        product_description=description,
        quantity=qty,
        estimated_unit_cost=unit_cost,
        estimated_line_total=(qty * unit_cost).quantize(Decimal("0.01")),
    )
    db_session.add(line)
    db_session.flush()
    return line


# ===========================================================================
# PurchaseRequestRepository
# ===========================================================================


class TestPurchaseRequestRepository:
    def test_create_and_get(self, db_session: Session):
        repo = PurchaseRequestRepository(db_session)
        company_id = uuid4()
        pr = _add_pr(db_session, company_id)
        fetched = repo.get_by_id_or_none(pr.id, company_id)
        assert fetched is not None
        assert fetched.pr_number == "PR-2026-000001"

    def test_company_isolation(self, db_session: Session):
        repo = PurchaseRequestRepository(db_session)
        company_a = uuid4()
        company_b = uuid4()
        _add_pr(db_session, company_a)
        fetched = repo.list_for_company(company_b)
        assert fetched == []

    def test_list_for_company(self, db_session: Session):
        repo = PurchaseRequestRepository(db_session)
        company_id = uuid4()
        _add_pr(db_session, company_id, pr_number="PR-2026-000001")
        _add_pr(db_session, company_id, pr_number="PR-2026-000002")
        results = repo.list_for_company(company_id)
        assert len(results) == 2

    def test_list_filter_by_status(self, db_session: Session):
        repo = PurchaseRequestRepository(db_session)
        company_id = uuid4()
        _add_pr(db_session, company_id, pr_number="PR-001", status="DRAFT")
        _add_pr(db_session, company_id, pr_number="PR-002", status="SUBMITTED")
        drafts = repo.list_for_company(company_id, status="DRAFT")
        assert len(drafts) == 1
        assert drafts[0].status == "DRAFT"

    def test_count_for_company(self, db_session: Session):
        repo = PurchaseRequestRepository(db_session)
        company_id = uuid4()
        _add_pr(db_session, company_id, pr_number="PR-001")
        _add_pr(db_session, company_id, pr_number="PR-002")
        assert repo.count_for_company(company_id) == 2

    def test_get_by_pr_number(self, db_session: Session):
        repo = PurchaseRequestRepository(db_session)
        company_id = uuid4()
        pr = _add_pr(db_session, company_id, pr_number="PR-2026-000099")
        found = repo.get_by_pr_number("PR-2026-000099", company_id)
        assert found is not None
        assert found.id == pr.id

    def test_update_status(self, db_session: Session):
        repo = PurchaseRequestRepository(db_session)
        company_id = uuid4()
        pr = _add_pr(db_session, company_id, status="DRAFT")
        repo.update_status(pr.id, company_id, "SUBMITTED")
        db_session.expire(pr)
        updated = repo.get_by_id_or_none(pr.id, company_id)
        assert updated is not None
        assert updated.status == "SUBMITTED"

    def test_update_total_cost(self, db_session: Session):
        repo = PurchaseRequestRepository(db_session)
        company_id = uuid4()
        pr = _add_pr(db_session, company_id)
        repo.update_total_cost(pr.id, company_id, Decimal("250.00"))
        db_session.expire(pr)
        updated = repo.get_by_id_or_none(pr.id, company_id)
        assert updated is not None
        assert Decimal(str(updated.total_estimated_cost)) == Decimal("250.00")

    def test_set_converted_to_po(self, db_session: Session):
        repo = PurchaseRequestRepository(db_session)
        company_id = uuid4()
        pr = _add_pr(db_session, company_id)
        po_id = uuid4()
        repo.set_converted_to_po(pr.id, company_id, po_id)
        db_session.expire(pr)
        updated = repo.get_by_id_or_none(pr.id, company_id)
        assert updated is not None
        assert updated.converted_to_po_id == str(po_id)

    def test_soft_delete(self, db_session: Session):
        repo = PurchaseRequestRepository(db_session)
        company_id = uuid4()
        pr = _add_pr(db_session, company_id)
        repo.soft_delete(id=pr.id, company_id=company_id)
        assert repo.get_by_id_or_none(pr.id, company_id) is None

    def test_list_excludes_deleted(self, db_session: Session):
        repo = PurchaseRequestRepository(db_session)
        company_id = uuid4()
        pr = _add_pr(db_session, company_id, pr_number="PR-001")
        _add_pr(db_session, company_id, pr_number="PR-002")
        repo.soft_delete(id=pr.id, company_id=company_id)
        results = repo.list_for_company(company_id)
        assert len(results) == 1


# ===========================================================================
# PRLineRepository
# ===========================================================================


class TestPRLineRepository:
    def test_create_and_list(self, db_session: Session):
        repo = PRLineRepository(db_session)
        company_id = uuid4()
        pr = _add_pr(db_session, company_id)
        _add_line(db_session, company_id, pr.id, line_number=1)
        _add_line(db_session, company_id, pr.id, line_number=2)
        lines = repo.list_for_pr(pr.id, company_id)
        assert len(lines) == 2
        assert lines[0].line_number == 1
        assert lines[1].line_number == 2

    def test_company_isolation(self, db_session: Session):
        repo = PRLineRepository(db_session)
        company_a = uuid4()
        company_b = uuid4()
        pr_a = _add_pr(db_session, company_a)
        _add_line(db_session, company_a, pr_a.id)
        lines = repo.list_for_pr(pr_a.id, company_b)
        assert lines == []

    def test_max_line_number_empty(self, db_session: Session):
        repo = PRLineRepository(db_session)
        company_id = uuid4()
        pr = _add_pr(db_session, company_id)
        assert repo.get_max_line_number(pr.id, company_id) == 0

    def test_max_line_number_with_lines(self, db_session: Session):
        repo = PRLineRepository(db_session)
        company_id = uuid4()
        pr = _add_pr(db_session, company_id)
        _add_line(db_session, company_id, pr.id, line_number=1)
        _add_line(db_session, company_id, pr.id, line_number=2)
        _add_line(db_session, company_id, pr.id, line_number=3)
        assert repo.get_max_line_number(pr.id, company_id) == 3

    def test_soft_delete_single_line(self, db_session: Session):
        repo = PRLineRepository(db_session)
        company_id = uuid4()
        pr = _add_pr(db_session, company_id)
        line = _add_line(db_session, company_id, pr.id)
        repo.soft_delete(id=line.id, company_id=company_id)
        lines = repo.list_for_pr(pr.id, company_id)
        assert lines == []

    def test_delete_all_for_pr(self, db_session: Session):
        repo = PRLineRepository(db_session)
        company_id = uuid4()
        pr = _add_pr(db_session, company_id)
        _add_line(db_session, company_id, pr.id, line_number=1)
        _add_line(db_session, company_id, pr.id, line_number=2)
        repo.delete_all_for_pr(pr.id, company_id)
        lines = repo.list_for_pr(pr.id, company_id)
        assert lines == []
