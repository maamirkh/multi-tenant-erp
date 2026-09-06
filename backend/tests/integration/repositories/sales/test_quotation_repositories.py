"""Integration tests for Quotation aggregate repositories — Phase 3.

Tests:
  - SalesQuotationRepository: create, get, list, count, list_sent_expired
  - QuotationLineRepository: create, list, next_line_number, delete_for_quotation
  - QuotationRevisionRepository: create, list_for_quotation, get_latest
  - Company isolation (tenant boundary enforcement)

Task: T102
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from modules.sales.models.quotation import (
    QuotationLine,
    QuotationRevision,
    SalesQuotation,
)
from modules.sales.repositories.quotation import (
    QuotationLineRepository,
    QuotationRevisionRepository,
    SalesQuotationRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_quotation(
    company_id: UUID,
    customer_id: str,
    status: str = "DRAFT",
    quotation_number: str | None = None,
    validity_date: str = "2026-09-01",
) -> SalesQuotation:
    q = SalesQuotation(
        company_id=company_id,
        quotation_number=quotation_number or f"SQ-TEST-{uuid4().hex[:6]}",
        customer_id=customer_id,
        quotation_date="2026-08-02",
        validity_date=validity_date,
        currency_code="USD",
        sales_rep_id=str(uuid4()),
        status=status,
        revision_number=1,
        subtotal=Decimal("100.00"),
        discount_amount=Decimal("0"),
        tax_amount=Decimal("0"),
        total_amount=Decimal("100.00"),
        version=1,
    )
    return q


def _make_line(
    company_id: UUID, quotation_id: str, line_number: int = 1
) -> QuotationLine:
    return QuotationLine(
        company_id=company_id,
        quotation_id=quotation_id,
        line_number=line_number,
        description=f"Test product line {line_number}",
        quantity=Decimal("5"),
        unit_of_measure="EA",
        unit_price=Decimal("20.00"),
        extended_amount=Decimal("100.00"),
    )


# ---------------------------------------------------------------------------
# SalesQuotationRepository tests
# ---------------------------------------------------------------------------


class TestSalesQuotationRepository:
    def test_create_and_get(self, db_session: Session) -> None:
        company_id = uuid4()
        customer_id = str(uuid4())
        repo = SalesQuotationRepository(db_session)

        quot = _make_quotation(
            company_id, customer_id, quotation_number="SQ-2026-000001"
        )
        db_session.add(quot)
        db_session.flush()

        fetched = repo.get_by_id_or_none(quot.id, company_id)
        assert fetched is not None
        assert str(fetched.id) == str(quot.id)
        assert fetched.quotation_number == "SQ-2026-000001"

    def test_get_by_number(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesQuotationRepository(db_session)

        quot = _make_quotation(company_id, str(uuid4()), quotation_number="SQ-FIND-001")
        db_session.add(quot)
        db_session.flush()

        found = repo.get_by_number(company_id, "SQ-FIND-001")
        assert found is not None
        assert found.quotation_number == "SQ-FIND-001"

    def test_get_by_number_not_found(self, db_session: Session) -> None:
        repo = SalesQuotationRepository(db_session)
        result = repo.get_by_number(uuid4(), "SQ-NONEXISTENT")
        assert result is None

    def test_list_for_company(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesQuotationRepository(db_session)

        for i in range(3):
            db_session.add(
                _make_quotation(
                    company_id, str(uuid4()), quotation_number=f"SQ-L-{i:03d}"
                )
            )
        # Different company
        db_session.add(
            _make_quotation(uuid4(), str(uuid4()), quotation_number="SQ-OTHER")
        )
        db_session.flush()

        results = repo.list_for_company(company_id)
        assert len(results) == 3

    def test_list_for_company_status_filter(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesQuotationRepository(db_session)
        customer_id = str(uuid4())

        db_session.add(_make_quotation(company_id, customer_id, status="DRAFT"))
        db_session.add(
            _make_quotation(
                company_id,
                customer_id,
                status="SENT_TO_CUSTOMER",
                quotation_number=f"SQ-S-{uuid4().hex[:6]}",
            )
        )
        db_session.flush()

        drafts = repo.list_for_company(company_id, status="DRAFT")
        assert all(q.status == "DRAFT" for q in drafts)

    def test_count_for_company(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesQuotationRepository(db_session)

        for i in range(4):
            db_session.add(
                _make_quotation(
                    company_id, str(uuid4()), quotation_number=f"SQ-C-{i:03d}"
                )
            )
        db_session.flush()

        count = repo.count_for_company(company_id)
        assert count == 4

    def test_list_sent_expired(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesQuotationRepository(db_session)

        # Overdue sent quotation
        q1 = _make_quotation(
            company_id,
            str(uuid4()),
            status="SENT_TO_CUSTOMER",
            validity_date="2026-07-01",
            quotation_number=f"SQ-E-{uuid4().hex[:6]}",
        )
        # Still valid sent quotation
        q2 = _make_quotation(
            company_id,
            str(uuid4()),
            status="SENT_TO_CUSTOMER",
            validity_date="2099-12-31",
            quotation_number=f"SQ-V-{uuid4().hex[:6]}",
        )
        db_session.add(q1)
        db_session.add(q2)
        db_session.flush()

        expired = repo.list_sent_expired(company_id, "2026-08-02")
        ids = {str(e.id) for e in expired}
        assert str(q1.id) in ids
        assert str(q2.id) not in ids

    def test_tenant_isolation(self, db_session: Session) -> None:
        company_a = uuid4()
        company_b = uuid4()
        repo = SalesQuotationRepository(db_session)

        db_session.add(
            _make_quotation(company_a, str(uuid4()), quotation_number="SQ-A-001")
        )
        db_session.add(
            _make_quotation(company_b, str(uuid4()), quotation_number="SQ-B-001")
        )
        db_session.flush()

        a_results = repo.list_for_company(company_a)
        b_results = repo.list_for_company(company_b)
        assert len(a_results) == 1
        assert len(b_results) == 1
        assert a_results[0].quotation_number == "SQ-A-001"
        assert b_results[0].quotation_number == "SQ-B-001"

    def test_soft_delete_excluded_from_list(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SalesQuotationRepository(db_session)

        quot = _make_quotation(company_id, str(uuid4()))
        quot.is_deleted = True
        db_session.add(quot)
        db_session.flush()

        results = repo.list_for_company(company_id)
        assert len(results) == 0


# ---------------------------------------------------------------------------
# QuotationLineRepository tests
# ---------------------------------------------------------------------------


class TestQuotationLineRepository:
    def test_create_and_list(self, db_session: Session) -> None:
        company_id = uuid4()
        quot = _make_quotation(company_id, str(uuid4()))
        db_session.add(quot)
        db_session.flush()

        line_repo = QuotationLineRepository(db_session)
        line = _make_line(company_id, str(quot.id), line_number=1)
        db_session.add(line)
        db_session.flush()

        lines = line_repo.list_for_quotation(company_id, quot.id)
        assert len(lines) == 1
        assert lines[0].description == "Test product line 1"

    def test_next_line_number_empty(self, db_session: Session) -> None:
        company_id = uuid4()
        quot = _make_quotation(company_id, str(uuid4()))
        db_session.add(quot)
        db_session.flush()

        repo = QuotationLineRepository(db_session)
        next_ln = repo.next_line_number(company_id, quot.id)
        assert next_ln == 1

    def test_next_line_number_increments(self, db_session: Session) -> None:
        company_id = uuid4()
        quot = _make_quotation(company_id, str(uuid4()))
        db_session.add(quot)
        db_session.flush()

        repo = QuotationLineRepository(db_session)
        for i in range(3):
            line = _make_line(company_id, str(quot.id), line_number=i + 1)
            db_session.add(line)
        db_session.flush()

        next_ln = repo.next_line_number(company_id, quot.id)
        assert next_ln == 4

    def test_ordered_by_line_number(self, db_session: Session) -> None:
        company_id = uuid4()
        quot = _make_quotation(company_id, str(uuid4()))
        db_session.add(quot)
        db_session.flush()

        repo = QuotationLineRepository(db_session)
        for i in [3, 1, 2]:
            line = _make_line(company_id, str(quot.id), line_number=i)
            db_session.add(line)
        db_session.flush()

        lines = repo.list_for_quotation(company_id, quot.id)
        assert [ln.line_number for ln in lines] == [1, 2, 3]

    def test_delete_for_quotation(self, db_session: Session) -> None:
        company_id = uuid4()
        quot = _make_quotation(company_id, str(uuid4()))
        db_session.add(quot)
        db_session.flush()

        repo = QuotationLineRepository(db_session)
        for i in range(2):
            db_session.add(_make_line(company_id, str(quot.id), line_number=i + 1))
        db_session.flush()

        repo.delete_for_quotation(company_id, quot.id)
        db_session.flush()

        remaining = repo.list_for_quotation(company_id, quot.id)
        assert len(remaining) == 0

    def test_tenant_isolation(self, db_session: Session) -> None:
        company_a = uuid4()
        company_b = uuid4()

        quot_a = _make_quotation(company_a, str(uuid4()))
        quot_b = _make_quotation(company_b, str(uuid4()))
        db_session.add(quot_a)
        db_session.add(quot_b)
        db_session.flush()

        db_session.add(_make_line(company_a, str(quot_a.id), line_number=1))
        db_session.add(_make_line(company_b, str(quot_b.id), line_number=1))
        db_session.flush()

        repo = QuotationLineRepository(db_session)
        a_lines = repo.list_for_quotation(company_a, quot_a.id)
        b_lines = repo.list_for_quotation(company_b, quot_b.id)
        assert len(a_lines) == 1
        assert len(b_lines) == 1


# ---------------------------------------------------------------------------
# QuotationRevisionRepository tests
# ---------------------------------------------------------------------------


class TestQuotationRevisionRepository:
    def _make_revision(
        self,
        company_id: UUID,
        quotation_id: str,
        revision_number: int = 1,
    ) -> QuotationRevision:
        return QuotationRevision(
            company_id=company_id,
            quotation_id=quotation_id,
            revision_number=revision_number,
            snapshot={"status": "DRAFT", "total_amount": "100.00", "lines": []},
            modified_by=str(uuid4()),
            modified_at="2026-08-02T10:00:00",
            change_summary=f"Revision {revision_number}",
        )

    def test_create_and_list(self, db_session: Session) -> None:
        company_id = uuid4()
        quot = _make_quotation(company_id, str(uuid4()))
        db_session.add(quot)
        db_session.flush()

        repo = QuotationRevisionRepository(db_session)
        rev = self._make_revision(company_id, str(quot.id), revision_number=1)
        db_session.add(rev)
        db_session.flush()

        revisions = repo.list_for_quotation(company_id, quot.id)
        assert len(revisions) == 1
        assert revisions[0].revision_number == 1

    def test_ordered_by_revision_number(self, db_session: Session) -> None:
        company_id = uuid4()
        quot = _make_quotation(company_id, str(uuid4()))
        db_session.add(quot)
        db_session.flush()

        repo = QuotationRevisionRepository(db_session)
        for i in [3, 1, 2]:
            db_session.add(
                self._make_revision(company_id, str(quot.id), revision_number=i)
            )
        db_session.flush()

        revisions = repo.list_for_quotation(company_id, quot.id)
        assert [r.revision_number for r in revisions] == [1, 2, 3]

    def test_get_latest(self, db_session: Session) -> None:
        company_id = uuid4()
        quot = _make_quotation(company_id, str(uuid4()))
        db_session.add(quot)
        db_session.flush()

        repo = QuotationRevisionRepository(db_session)
        for i in [1, 2, 3]:
            db_session.add(
                self._make_revision(company_id, str(quot.id), revision_number=i)
            )
        db_session.flush()

        latest = repo.get_latest(company_id, quot.id)
        assert latest is not None
        assert latest.revision_number == 3

    def test_get_latest_returns_none_when_empty(self, db_session: Session) -> None:
        company_id = uuid4()
        quot = _make_quotation(company_id, str(uuid4()))
        db_session.add(quot)
        db_session.flush()

        repo = QuotationRevisionRepository(db_session)
        result = repo.get_latest(company_id, quot.id)
        assert result is None

    def test_snapshot_jsonb_stored_and_retrieved(self, db_session: Session) -> None:
        company_id = uuid4()
        quot = _make_quotation(company_id, str(uuid4()))
        db_session.add(quot)
        db_session.flush()

        snapshot = {
            "status": "SENT_TO_CUSTOMER",
            "total_amount": "250.00",
            "lines": [{"description": "Widget", "extended_amount": "250.00"}],
        }
        rev = QuotationRevision(
            company_id=company_id,
            quotation_id=str(quot.id),
            revision_number=1,
            snapshot=snapshot,
            modified_by=str(uuid4()),
            modified_at="2026-08-02T12:00:00",
        )
        db_session.add(rev)
        db_session.flush()

        repo = QuotationRevisionRepository(db_session)
        latest = repo.get_latest(company_id, quot.id)
        assert latest is not None
        # Snapshot is stored and can be read back (may be dict or string in SQLite)
        snap = latest.snapshot
        if isinstance(snap, str):
            import json

            snap = json.loads(snap)
        assert snap["status"] == "SENT_TO_CUSTOMER"
        assert len(snap["lines"]) == 1
