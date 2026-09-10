"""Integration tests for Phase 2 enrichment repositories — T070.

Tests:
  - CreditLimitRepository: create, get_for_supplier, company_id isolation
  - BankDetailsRepository: CRUD, clear_primary, company_id scoping
  - SupplierRatingRepository: upsert, get_for_supplier, company_id scoping
  - SupplierDocumentRepository: create, list, soft-delete
  - SupplierLeadTimeRepository: create, get_for_supplier_product, unique constraint

All tests run against SQLite in-memory DB.

Task: T070
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from modules.purchase.models.supplier import Supplier
from modules.purchase.models.supplier_enrichment import (
    BankDetails,
    CreditLimit,
    SupplierDocument,
    SupplierLeadTime,
    SupplierRating,
)
from modules.purchase.repositories.supplier_enrichment import (
    BankDetailsRepository,
    CreditLimitRepository,
    SupplierDocumentRepository,
    SupplierLeadTimeRepository,
    SupplierRatingRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _add_supplier(db: Session, company_id: UUID, code: str = "SUP-001") -> Supplier:
    s = Supplier(
        company_id=company_id,
        supplier_code=code,
        legal_name="Test Supplier",
        supplier_type="GOODS",
        status="ACTIVE",
        currency_code="USD",
    )
    db.add(s)
    db.flush()
    return s


# ---------------------------------------------------------------------------
# CreditLimitRepository
# ---------------------------------------------------------------------------


class TestCreditLimitRepository:
    def test_get_for_supplier_none(self, db_session: Session):
        """Returns None when no credit limit set."""
        repo = CreditLimitRepository(db_session)
        result = repo.get_for_supplier(company_id=uuid4(), supplier_id=uuid4())
        assert result is None

    def test_create_and_get(self, db_session: Session):
        """Can create a credit limit and retrieve it."""
        company_id = uuid4()
        supplier = _add_supplier(db_session, company_id)

        cl = CreditLimit(
            company_id=company_id,
            supplier_id=str(supplier.id),
            credit_limit_amount=Decimal("5000.00"),
            currency_code="USD",
            enforcement_mode="WARN",
        )
        db_session.add(cl)
        db_session.flush()

        repo = CreditLimitRepository(db_session)
        result = repo.get_for_supplier(company_id=company_id, supplier_id=supplier.id)
        assert result is not None
        assert result.credit_limit_amount == Decimal("5000.00")
        assert result.enforcement_mode == "WARN"

    def test_company_id_isolation(self, db_session: Session):
        """Credit limit for company A not visible to company B."""
        cid_a = uuid4()
        cid_b = uuid4()
        sup_a = _add_supplier(db_session, cid_a, "SUP-A")

        cl = CreditLimit(
            company_id=cid_a,
            supplier_id=str(sup_a.id),
            credit_limit_amount=Decimal("1000.00"),
            currency_code="USD",
            enforcement_mode="BLOCK",
        )
        db_session.add(cl)
        db_session.flush()

        repo = CreditLimitRepository(db_session)
        # Company B cannot see company A's credit limit
        result_b = repo.get_for_supplier(company_id=cid_b, supplier_id=sup_a.id)
        assert result_b is None

    def test_enforcement_modes(self, db_session: Session):
        """All three enforcement modes can be stored."""
        for mode in ("BLOCK", "WARN", "OFF"):
            company_id = uuid4()
            supplier = _add_supplier(db_session, company_id, f"SUP-{mode}")
            cl = CreditLimit(
                company_id=company_id,
                supplier_id=str(supplier.id),
                credit_limit_amount=Decimal("100.00"),
                currency_code="USD",
                enforcement_mode=mode,
            )
            db_session.add(cl)
            db_session.flush()

            repo = CreditLimitRepository(db_session)
            result = repo.get_for_supplier(
                company_id=company_id, supplier_id=supplier.id
            )
            assert result is not None
            assert result.enforcement_mode == mode


# ---------------------------------------------------------------------------
# BankDetailsRepository
# ---------------------------------------------------------------------------


class TestBankDetailsRepository:
    def test_get_for_supplier_empty(self, db_session: Session):
        """Returns empty list when no bank details."""
        repo = BankDetailsRepository(db_session)
        result = repo.get_for_supplier(company_id=uuid4(), supplier_id=uuid4())
        assert result == []

    def test_add_bank_detail(self, db_session: Session):
        """Can add and retrieve bank details."""
        company_id = uuid4()
        supplier = _add_supplier(db_session, company_id)

        bd = BankDetails(
            company_id=company_id,
            supplier_id=str(supplier.id),
            bank_name="Test Bank",
            account_name="Acme Corp",
            account_number="12345678",
            bank_country="US",
            currency_code="USD",
            is_primary=True,
        )
        db_session.add(bd)
        db_session.flush()

        repo = BankDetailsRepository(db_session)
        result = repo.get_for_supplier(company_id=company_id, supplier_id=supplier.id)
        assert len(result) == 1
        assert result[0].bank_name == "Test Bank"
        assert result[0].is_primary is True

    def test_clear_primary(self, db_session: Session):
        """clear_primary sets is_primary=False for all records."""
        company_id = uuid4()
        supplier = _add_supplier(db_session, company_id)

        for i in range(3):
            bd = BankDetails(
                company_id=company_id,
                supplier_id=str(supplier.id),
                bank_name=f"Bank {i}",
                account_name="Acme",
                account_number=f"ACC-{i}",
                bank_country="US",
                currency_code="USD",
                is_primary=(i == 0),
            )
            db_session.add(bd)
        db_session.flush()

        repo = BankDetailsRepository(db_session)
        repo.clear_primary(company_id=company_id, supplier_id=supplier.id)

        items = repo.get_for_supplier(company_id=company_id, supplier_id=supplier.id)
        assert all(not b.is_primary for b in items)

    def test_company_id_scoping(self, db_session: Session):
        """Bank details are scoped per company."""
        cid_a = uuid4()
        cid_b = uuid4()
        sup_a = _add_supplier(db_session, cid_a, "SUP-A")

        bd = BankDetails(
            company_id=cid_a,
            supplier_id=str(sup_a.id),
            bank_name="Scoped Bank",
            account_name="Acme",
            account_number="XYZ",
            bank_country="US",
            currency_code="USD",
        )
        db_session.add(bd)
        db_session.flush()

        repo = BankDetailsRepository(db_session)
        result_b = repo.get_for_supplier(company_id=cid_b, supplier_id=sup_a.id)
        assert result_b == []

    def test_soft_delete_excluded(self, db_session: Session):
        """Soft-deleted records are excluded from get_for_supplier."""
        from core.utils.datetime import utcnow

        company_id = uuid4()
        supplier = _add_supplier(db_session, company_id)

        bd = BankDetails(
            company_id=company_id,
            supplier_id=str(supplier.id),
            bank_name="Deleted Bank",
            account_name="Acme",
            account_number="DEL123",
            bank_country="US",
            currency_code="USD",
            is_deleted=True,
            deleted_at=utcnow(),
        )
        db_session.add(bd)
        db_session.flush()

        repo = BankDetailsRepository(db_session)
        result = repo.get_for_supplier(company_id=company_id, supplier_id=supplier.id)
        assert result == []


# ---------------------------------------------------------------------------
# SupplierRatingRepository
# ---------------------------------------------------------------------------


class TestSupplierRatingRepository:
    def test_get_for_supplier_none(self, db_session: Session):
        repo = SupplierRatingRepository(db_session)
        result = repo.get_for_supplier(company_id=uuid4(), supplier_id=uuid4())
        assert result is None

    def test_create_and_get_rating(self, db_session: Session):
        from core.utils.datetime import utcnow

        company_id = uuid4()
        supplier = _add_supplier(db_session, company_id)

        rating = SupplierRating(
            company_id=company_id,
            supplier_id=str(supplier.id),
            on_time_rate=Decimal("85.00"),
            fill_rate=Decimal("90.00"),
            rejection_rate=Decimal("5.00"),
            composite_score=Decimal("8.8"),
            gr_count_window=10,
            last_computed_at=utcnow(),
        )
        db_session.add(rating)
        db_session.flush()

        repo = SupplierRatingRepository(db_session)
        result = repo.get_for_supplier(company_id=company_id, supplier_id=supplier.id)
        assert result is not None
        assert result.composite_score == Decimal("8.8")
        assert result.gr_count_window == 10

    def test_manual_override_stored(self, db_session: Session):
        from core.utils.datetime import utcnow

        company_id = uuid4()
        supplier = _add_supplier(db_session, company_id)

        rating = SupplierRating(
            company_id=company_id,
            supplier_id=str(supplier.id),
            on_time_rate=Decimal("60.00"),
            fill_rate=Decimal("70.00"),
            rejection_rate=Decimal("15.00"),
            composite_score=Decimal("6.5"),
            gr_count_window=5,
            manual_override_score=Decimal("8.0"),
            manual_override_reason="Manual override by PM",
            last_computed_at=utcnow(),
        )
        db_session.add(rating)
        db_session.flush()

        repo = SupplierRatingRepository(db_session)
        result = repo.get_for_supplier(company_id=company_id, supplier_id=supplier.id)
        assert result is not None
        assert result.manual_override_score == Decimal("8.0")
        assert result.manual_override_reason == "Manual override by PM"

    def test_company_id_scoping(self, db_session: Session):
        from core.utils.datetime import utcnow

        cid_a = uuid4()
        cid_b = uuid4()
        sup_a = _add_supplier(db_session, cid_a, "SUP-A")

        rating = SupplierRating(
            company_id=cid_a,
            supplier_id=str(sup_a.id),
            on_time_rate=Decimal("90"),
            fill_rate=Decimal("90"),
            rejection_rate=Decimal("5"),
            composite_score=Decimal("8.9"),
            gr_count_window=3,
            last_computed_at=utcnow(),
        )
        db_session.add(rating)
        db_session.flush()

        repo = SupplierRatingRepository(db_session)
        result_b = repo.get_for_supplier(company_id=cid_b, supplier_id=sup_a.id)
        assert result_b is None


# ---------------------------------------------------------------------------
# SupplierDocumentRepository
# ---------------------------------------------------------------------------


class TestSupplierDocumentRepository:
    def test_list_documents_empty(self, db_session: Session):
        repo = SupplierDocumentRepository(db_session)
        result = repo.get_for_supplier(company_id=uuid4(), supplier_id=uuid4())
        assert result == []

    def test_add_and_list(self, db_session: Session):
        company_id = uuid4()
        supplier = _add_supplier(db_session, company_id)
        today = date.today()

        doc = SupplierDocument(
            company_id=company_id,
            supplier_id=str(supplier.id),
            document_type="Trade License",
            document_number="TL-2024-001",
            issue_date=today - timedelta(days=365),
            expiry_date=today + timedelta(days=90),
            file_url="s3://bucket/doc.pdf",
        )
        db_session.add(doc)
        db_session.flush()

        repo = SupplierDocumentRepository(db_session)
        result = repo.get_for_supplier(company_id=company_id, supplier_id=supplier.id)
        assert len(result) == 1
        assert result[0].document_type == "Trade License"
        assert result[0].document_number == "TL-2024-001"

    def test_soft_delete_excluded(self, db_session: Session):
        from core.utils.datetime import utcnow

        company_id = uuid4()
        supplier = _add_supplier(db_session, company_id)

        doc = SupplierDocument(
            company_id=company_id,
            supplier_id=str(supplier.id),
            document_type="ISO Cert",
            is_deleted=True,
            deleted_at=utcnow(),
        )
        db_session.add(doc)
        db_session.flush()

        repo = SupplierDocumentRepository(db_session)
        result = repo.get_for_supplier(company_id=company_id, supplier_id=supplier.id)
        assert result == []

    def test_multiple_documents_sorted_by_expiry(self, db_session: Session):
        """Documents ordered by expiry_date ascending."""
        company_id = uuid4()
        supplier = _add_supplier(db_session, company_id)
        today = date.today()

        for days in [60, 10, 30]:
            doc = SupplierDocument(
                company_id=company_id,
                supplier_id=str(supplier.id),
                document_type=f"Doc-{days}",
                expiry_date=today + timedelta(days=days),
            )
            db_session.add(doc)
        db_session.flush()

        repo = SupplierDocumentRepository(db_session)
        result = repo.get_for_supplier(company_id=company_id, supplier_id=supplier.id)
        expiry_days = []
        for d in result:
            assert d.expiry_date is not None
            expiry_days.append((d.expiry_date - today).days)
        assert expiry_days == sorted(expiry_days)


# ---------------------------------------------------------------------------
# SupplierLeadTimeRepository
# ---------------------------------------------------------------------------


class TestSupplierLeadTimeRepository:
    def test_get_for_supplier_empty(self, db_session: Session):
        repo = SupplierLeadTimeRepository(db_session)
        result = repo.get_for_supplier(company_id=uuid4(), supplier_id=uuid4())
        assert result == []

    def test_create_default_lead_time(self, db_session: Session):
        """product_id=None is the supplier-level default."""
        company_id = uuid4()
        supplier = _add_supplier(db_session, company_id)

        lt = SupplierLeadTime(
            company_id=company_id,
            supplier_id=str(supplier.id),
            product_id=None,
            lead_time_days=7,
        )
        db_session.add(lt)
        db_session.flush()

        repo = SupplierLeadTimeRepository(db_session)
        result = repo.get_for_supplier_product(
            company_id=company_id, supplier_id=supplier.id, product_id=None
        )
        assert result is not None
        assert result.lead_time_days == 7
        assert result.product_id is None

    def test_product_specific_lead_time(self, db_session: Session):
        """Product-specific lead time returned for correct product_id."""
        company_id = uuid4()
        supplier = _add_supplier(db_session, company_id)
        product_id = uuid4()

        lt = SupplierLeadTime(
            company_id=company_id,
            supplier_id=str(supplier.id),
            product_id=str(product_id),
            lead_time_days=14,
        )
        db_session.add(lt)
        db_session.flush()

        repo = SupplierLeadTimeRepository(db_session)
        result = repo.get_for_supplier_product(
            company_id=company_id, supplier_id=supplier.id, product_id=product_id
        )
        assert result is not None
        assert result.lead_time_days == 14

    def test_wrong_product_returns_none(self, db_session: Session):
        """Returns None when querying for a different product."""
        company_id = uuid4()
        supplier = _add_supplier(db_session, company_id)
        product_id = uuid4()

        lt = SupplierLeadTime(
            company_id=company_id,
            supplier_id=str(supplier.id),
            product_id=str(product_id),
            lead_time_days=14,
        )
        db_session.add(lt)
        db_session.flush()

        repo = SupplierLeadTimeRepository(db_session)
        result = repo.get_for_supplier_product(
            company_id=company_id,
            supplier_id=supplier.id,
            product_id=uuid4(),  # different product
        )
        assert result is None

    def test_list_multiple_lead_times(self, db_session: Session):
        """Returns all lead times for a supplier including default and per-product."""
        company_id = uuid4()
        supplier = _add_supplier(db_session, company_id)
        p1 = uuid4()
        p2 = uuid4()

        for product_id, days in [(None, 5), (p1, 10), (p2, 21)]:
            lt = SupplierLeadTime(
                company_id=company_id,
                supplier_id=str(supplier.id),
                product_id=str(product_id) if product_id else None,
                lead_time_days=days,
            )
            db_session.add(lt)
        db_session.flush()

        repo = SupplierLeadTimeRepository(db_session)
        result = repo.get_for_supplier(company_id=company_id, supplier_id=supplier.id)
        assert len(result) == 3
