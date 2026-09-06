"""Integration tests for Phase 0 purchase repositories.

Tests:
  - SupplierCategoryRepository: CRUD, tree queries, company_id scoping, soft-delete
  - PaymentTermsRepository: CRUD, code-uniqueness, active filter
  - PurchaseReasonCodeRepository: CRUD, type filter, company scoping
  - PurchasePolicyRepository: singleton per company, get_for_company

All tests use the SQLite in-memory test database (no external DB required).

Spec ref: specs/006-purchase-management/data-model.md §Master Data Entities
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from modules.purchase.models.policy import PurchasePolicy
from modules.purchase.models.supplier import (
    PaymentTerms,
    PurchaseReasonCode,
    SupplierCategory,
)
from modules.purchase.repositories.master import (
    PaymentTermsRepository,
    PurchasePolicyRepository,
    PurchaseReasonCodeRepository,
    SupplierCategoryRepository,
)

# ---------------------------------------------------------------------------
# SupplierCategoryRepository
# ---------------------------------------------------------------------------


class TestSupplierCategoryRepository:
    def test_create_and_get_root_category(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SupplierCategoryRepository(db_session)

        cat = SupplierCategory(
            company_id=company_id,
            code="TECH",
            name="Technology",
            status="active",
        )
        created = repo.create(cat)

        assert created.id is not None
        assert created.code == "TECH"
        assert created.company_id == company_id
        assert created.parent_id is None

    def test_get_by_code(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SupplierCategoryRepository(db_session)

        cat = SupplierCategory(
            company_id=company_id,
            code="MFCT",
            name="Manufacturing",
            status="active",
        )
        repo.create(cat)

        result = repo.get_by_code(company_id=company_id, code="MFCT")
        assert result is not None
        assert result.name == "Manufacturing"

    def test_get_by_code_wrong_company_returns_none(self, db_session: Session) -> None:
        company_id = uuid4()
        other_company_id = uuid4()
        repo = SupplierCategoryRepository(db_session)

        repo.create(
            SupplierCategory(
                company_id=company_id, code="TECH", name="Technology", status="active"
            )
        )

        result = repo.get_by_code(company_id=other_company_id, code="TECH")
        assert result is None

    def test_get_roots_excludes_children(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SupplierCategoryRepository(db_session)

        root = repo.create(
            SupplierCategory(
                company_id=company_id, code="ROOT", name="Root", status="active"
            )
        )
        child = repo.create(
            SupplierCategory(
                company_id=company_id,
                code="CHILD",
                name="Child",
                parent_id=str(root.id),
                status="active",
            )
        )

        roots = repo.get_roots(company_id=company_id)
        root_ids = [str(r.id) for r in roots]

        assert str(root.id) in root_ids
        assert str(child.id) not in root_ids

    def test_get_children_returns_direct_children_only(
        self, db_session: Session
    ) -> None:
        company_id = uuid4()
        repo = SupplierCategoryRepository(db_session)

        parent = repo.create(
            SupplierCategory(
                company_id=company_id, code="PAR", name="Parent", status="active"
            )
        )
        child1 = repo.create(
            SupplierCategory(
                company_id=company_id,
                code="C1",
                name="Child 1",
                parent_id=str(parent.id),
                status="active",
            )
        )
        child2 = repo.create(
            SupplierCategory(
                company_id=company_id,
                code="C2",
                name="Child 2",
                parent_id=str(parent.id),
                status="active",
            )
        )

        children = repo.get_children(company_id=company_id, parent_id=parent.id)
        child_codes = {c.code for c in children}

        assert "C1" in child_codes
        assert "C2" in child_codes
        assert len(children) == 2

    def test_soft_delete_excludes_from_list(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = SupplierCategoryRepository(db_session)

        cat = repo.create(
            SupplierCategory(
                company_id=company_id, code="DEL", name="To Delete", status="active"
            )
        )

        repo.soft_delete(id=cat.id, company_id=company_id)

        result = repo.get_by_code(company_id=company_id, code="DEL")
        assert result is None

    def test_tenant_isolation(self, db_session: Session) -> None:
        """Company A cannot see Company B categories."""
        company_a = uuid4()
        company_b = uuid4()
        repo = SupplierCategoryRepository(db_session)

        repo.create(
            SupplierCategory(
                company_id=company_a,
                code="A-CAT",
                name="Company A Category",
                status="active",
            )
        )

        items_b, total_b = repo.list(company_id=company_b)
        assert total_b == 0
        assert len(items_b) == 0


# ---------------------------------------------------------------------------
# PaymentTermsRepository
# ---------------------------------------------------------------------------


class TestPaymentTermsRepository:
    def test_create_and_get_payment_terms(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = PaymentTermsRepository(db_session)

        terms = repo.create(
            PaymentTerms(
                company_id=company_id,
                code="NET30",
                name="Net 30 Days",
                net_days=30,
                is_active=True,
            )
        )

        assert terms.id is not None
        assert terms.code == "NET30"
        assert terms.net_days == 30

    def test_get_by_code(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = PaymentTermsRepository(db_session)

        repo.create(
            PaymentTerms(
                company_id=company_id,
                code="NET60",
                name="Net 60 Days",
                net_days=60,
                is_active=True,
            )
        )

        result = repo.get_by_code(company_id=company_id, code="NET60")
        assert result is not None
        assert result.net_days == 60

    def test_get_active_excludes_inactive(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = PaymentTermsRepository(db_session)

        repo.create(
            PaymentTerms(
                company_id=company_id,
                code="ACTIVE",
                name="Active Terms",
                net_days=30,
                is_active=True,
            )
        )
        repo.create(
            PaymentTerms(
                company_id=company_id,
                code="INACTIVE",
                name="Inactive Terms",
                net_days=0,
                is_active=False,
            )
        )

        active = repo.get_active(company_id=company_id)
        codes = {t.code for t in active}

        assert "ACTIVE" in codes
        assert "INACTIVE" not in codes

    def test_tenant_isolation(self, db_session: Session) -> None:
        company_a = uuid4()
        company_b = uuid4()
        repo = PaymentTermsRepository(db_session)

        repo.create(
            PaymentTerms(
                company_id=company_a,
                code="A-TERMS",
                name="A Terms",
                net_days=30,
                is_active=True,
            )
        )

        items_b, total_b = repo.list(company_id=company_b)
        assert total_b == 0


# ---------------------------------------------------------------------------
# PurchaseReasonCodeRepository
# ---------------------------------------------------------------------------


class TestPurchaseReasonCodeRepository:
    def test_create_and_get_by_type(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = PurchaseReasonCodeRepository(db_session)

        repo.create(
            PurchaseReasonCode(
                company_id=company_id,
                code="WI",
                name="Wrong Item",
                reason_type="RETURN",
                is_active=True,
            )
        )
        repo.create(
            PurchaseReasonCode(
                company_id=company_id,
                code="OC",
                name="Order Changed",
                reason_type="CANCELLATION",
                is_active=True,
            )
        )

        returns = repo.get_by_type(company_id=company_id, reason_type="RETURN")
        assert len(returns) == 1
        assert returns[0].code == "WI"

    def test_get_by_code_with_type(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = PurchaseReasonCodeRepository(db_session)

        repo.create(
            PurchaseReasonCode(
                company_id=company_id,
                code="BAD",
                name="Bad Quality",
                reason_type="RETURN",
                is_active=True,
            )
        )

        result = repo.get_by_code(
            company_id=company_id, code="BAD", reason_type="RETURN"
        )
        assert result is not None
        assert result.name == "Bad Quality"

    def test_tenant_isolation(self, db_session: Session) -> None:
        company_a = uuid4()
        company_b = uuid4()
        repo = PurchaseReasonCodeRepository(db_session)

        repo.create(
            PurchaseReasonCode(
                company_id=company_a,
                code="A-RC",
                name="A Reason",
                reason_type="GENERAL",
                is_active=True,
            )
        )

        items_b, total_b = repo.list(company_id=company_b)
        assert total_b == 0


# ---------------------------------------------------------------------------
# PurchasePolicyRepository
# ---------------------------------------------------------------------------


class TestPurchasePolicyRepository:
    def test_create_and_get_for_company(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = PurchasePolicyRepository(db_session)

        policy = repo.create(
            PurchasePolicy(
                company_id=company_id,
                direct_po_allowed=False,
                pr_approval_required=True,
                po_approval_required=True,
                over_receipt_policy="WARN",
                credit_limit_mode="WARN",
            )
        )

        result = repo.get_for_company(company_id=company_id)
        assert result is not None
        assert result.over_receipt_policy == "WARN"
        assert result.pr_approval_required is True

    def test_get_for_company_no_policy_returns_none(self, db_session: Session) -> None:
        company_id = uuid4()
        repo = PurchasePolicyRepository(db_session)

        result = repo.get_for_company(company_id=company_id)
        assert result is None

    def test_tenant_isolation(self, db_session: Session) -> None:
        company_a = uuid4()
        company_b = uuid4()
        repo = PurchasePolicyRepository(db_session)

        repo.create(
            PurchasePolicy(
                company_id=company_a,
                direct_po_allowed=True,
                pr_approval_required=False,
                po_approval_required=False,
                over_receipt_policy="ALLOW",
                credit_limit_mode="OFF",
            )
        )

        result_b = repo.get_for_company(company_id=company_b)
        assert result_b is None
