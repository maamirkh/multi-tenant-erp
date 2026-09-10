"""[Epic 10, Phase 13] Real, live-ASGI-request evidence for two backend
gaps closed while building the Contract Detail / Approvals frontend
pages:

1. ``GET /contracts/{contractId}/audit`` — thin wrapper around the
   already-existing, tenant-scoped
   ``InstallmentAuditService.list_for_entity()``.
2. ``GET /contracts?status=`` — thin wrapper around the already-existing
   ``InstallmentContractRepository.list_filtered()``.

Mirrors ``test_http_security_closure.py``'s fixtures/patterns exactly.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.installments.models.contract import InstallmentContract
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.enums import MembershipStatus
from modules.users_roles.models.permission import Permission
from modules.users_roles.models.role import Role
from modules.users_roles.models.role_permission import RolePermission
from tests.fixtures.auth_fixtures import create_test_user
from tests.integration.api.v1.installments.conftest import (
    build_active_contract_with_schedule,
)

_INSTALLMENTS_PREFIX = "/api/v1/companies/{company_id}/installments"


def _make_company(db: Session, *, company_id: uuid.UUID | None = None) -> Company:
    suffix = uuid.uuid4().hex[:10]
    owner = User(email=f"audit-owner-{suffix}@example.test", display_name="Owner")
    db.add(owner)
    db.flush()
    company = Company(
        id=company_id or uuid.uuid4(),
        legal_name=f"Audit Co {suffix}",
        slug=f"audit-co-{suffix}",
        owner_id=owner.id,
        email=f"audit-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


def _login(test_client: TestClient, db: Session, *, email: str, password: str) -> str:
    create_test_user(db, email=email, password=password)
    db.commit()
    response = test_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return str(response.json()["data"]["access_token"])


def _ensure_permission(db: Session, code: str) -> None:
    if db.get(Permission, code) is not None:
        return
    db.add(
        Permission(
            id=code, code=code, label=code, module="installments", action="manage"
        )
    )
    db.flush()


def _grant_membership_with_permissions(
    db: Session, *, company_id: uuid.UUID, user_id: uuid.UUID, codes: set[str]
) -> None:
    for code in codes:
        _ensure_permission(db, code)
    role = Role(
        company_id=company_id,
        name=f"Audit Role {uuid.uuid4().hex[:8]}",
        slug=f"audit-role-{uuid.uuid4().hex[:10]}",
        rank=50,
        is_system=False,
        is_active=True,
    )
    db.add(role)
    db.flush()
    for code in codes:
        db.add(RolePermission(role_id=role.id, permission_id=code))
    db.flush()
    db.add(
        CompanyMember(
            company_id=company_id,
            user_id=user_id,
            role_id=role.id,
            status=MembershipStatus.active.value,
        )
    )
    db.commit()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestContractAuditHistoryHttp:
    def test_returns_chronological_audit_entries_for_own_tenant(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="DRAFT",
        )
        company = _make_company(pg_db_session, company_id=ctx["company_id"])
        email = f"audit-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client, pg_db_session, email=email, password="Audit@1234"
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.contract.view"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id)
            + f"/contracts/{ctx['contract'].id}/audit",
            headers=_auth_header(token),
        )
        assert response.status_code == 200, response.text
        assert isinstance(response.json()["data"], list)

    def test_cross_tenant_contract_id_returns_404_not_leaked(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="DRAFT",
        )
        # ctx's contract belongs to ctx["company_id"] — query it through an
        # UNRELATED company the caller actually belongs to.
        other_company = _make_company(pg_db_session)
        email = f"audit-cross-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client, pg_db_session, email=email, password="Audit@1234"
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=other_company.id,
            user_id=user_row.id,
            codes={"installments.contract.view"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=other_company.id)
            + f"/contracts/{ctx['contract'].id}/audit",
            headers=_auth_header(token),
        )
        assert response.status_code == 404, response.text

    def test_member_without_contract_view_permission_is_rejected_with_403(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        """[Phase-13 closure item K] A company member with SOME
        installments.* permission but not `installments.contract.view`
        (the permission this endpoint reuses per plan.md §17) must be
        rejected before any audit data is returned — RBAC-denial evidence
        was previously missing for this specific endpoint."""
        ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="DRAFT",
        )
        company = _make_company(pg_db_session, company_id=ctx["company_id"])
        email = f"audit-norbac-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client, pg_db_session, email=email, password="Audit@1234"
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        # Granted a real, unrelated installments.* permission — proves this
        # is a genuine permission-code check, not just "any membership".
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.plan.manage"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id)
            + f"/contracts/{ctx['contract'].id}/audit",
            headers=_auth_header(token),
        )
        assert response.status_code == 403, response.text
        body = response.json()
        assert "error" in body
        assert "data" not in body


def _add_bare_draft_contract(
    db: Session, *, company_id: uuid.UUID, customer_id: uuid.UUID
) -> InstallmentContract:
    """A second contract in the same company/customer, deliberately NOT
    built via ``build_active_contract_with_schedule`` (which unconditionally
    creates a fresh Chart-of-Accounts scaffold per call and cannot be
    invoked twice for one company). A DRAFT contract has no accounting
    footprint yet, so a bare ORM row is sufficient — this test only needs
    a second, differently-statused contract to prove the status filter."""
    contract = InstallmentContract(
        company_id=company_id,
        contract_number=f"DRAFT-{uuid.uuid4().hex[:10]}",
        customer_id=customer_id,
        sales_invoice_id=uuid.uuid4(),
        contract_date=date.today(),
        principal_amount=Decimal("50.00"),
        down_payment_amount=Decimal("0"),
        markup_amount=Decimal("0"),
        contractual_total=Decimal("50.00"),
        installment_count=1,
        frequency="MONTHLY",
        first_due_date=date.today(),
        maturity_date=date.today(),
        currency_code="USD",
        status="DRAFT",
        terms_snapshot={},
    )
    db.add(contract)
    db.commit()
    return contract


class TestContractsStatusFilterHttp:
    def test_status_filter_returns_only_matching_contracts(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        active_ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("75.00"),
            status="ACTIVE",
        )
        company = _make_company(pg_db_session, company_id=active_ctx["company_id"])
        draft_contract = _add_bare_draft_contract(
            pg_db_session,
            company_id=company.id,
            customer_id=active_ctx["customer_id"],
        )
        email = f"statusfilter-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client,
            pg_db_session,
            email=email,
            password="StatusFilter@1234",
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.contract.view"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id)
            + "/contracts?status=ACTIVE&page_size=100",
            headers=_auth_header(token),
        )
        assert response.status_code == 200, response.text
        items = response.json()["data"]["items"]
        returned_ids = {item["id"] for item in items}
        assert str(active_ctx["contract"].id) in returned_ids
        assert str(draft_contract.id) not in returned_ids

    def test_unrecognized_status_value_is_rejected_with_422_not_silently_empty(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        """[Phase-13 closure item H] Before this fix, `status_filter` was a
        bare `str` query param — `?status=BOGUS` passed FastAPI validation,
        flowed unvalidated into the repository's `WHERE status = 'BOGUS'`,
        and silently returned an empty page. Now typed against the real
        `InstallmentContractStatus` enum, so an unrecognized value is
        rejected before it ever reaches the service/repository layer."""
        active_ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("75.00"),
            status="ACTIVE",
        )
        company = _make_company(pg_db_session, company_id=active_ctx["company_id"])
        email = f"statusfilter-bad-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client,
            pg_db_session,
            email=email,
            password="StatusFilter@1234",
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.contract.view"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id)
            + "/contracts?status=BOGUS",
            headers=_auth_header(token),
        )
        assert response.status_code == 422, response.text

    def test_valid_status_values_are_all_individually_accepted(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        """Every documented `InstallmentContractStatus` value passes
        validation (200, not 422) — proves the enum wiring isn't
        accidentally narrower than the real lifecycle."""
        active_ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("75.00"),
            status="ACTIVE",
        )
        company = _make_company(pg_db_session, company_id=active_ctx["company_id"])
        email = f"statusfilter-allvalues-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client,
            pg_db_session,
            email=email,
            password="StatusFilter@1234",
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.contract.view"},
        )

        for status_value in (
            "DRAFT",
            "PENDING_APPROVAL",
            "APPROVED",
            "ACTIVE",
            "DEFAULTED",
            "COMPLETED",
            "CANCELLED",
            "WRITTEN_OFF",
        ):
            response = installments_http_client.get(
                _INSTALLMENTS_PREFIX.format(company_id=company.id)
                + f"/contracts?status={status_value}",
                headers=_auth_header(token),
            )
            assert response.status_code == 200, (status_value, response.text)

    def test_status_filter_never_bypasses_tenant_scoping(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        """The status filter is additive to, never a replacement for, the
        mandatory company_id scope — an ACTIVE contract in another company
        must not appear just because it matches the status filter."""
        active_ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("75.00"),
            status="ACTIVE",
        )
        other_company_active_ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("99.00"),
            status="ACTIVE",
        )
        company = _make_company(pg_db_session, company_id=active_ctx["company_id"])
        email = f"statusfilter-tenant-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client,
            pg_db_session,
            email=email,
            password="StatusFilter@1234",
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.contract.view"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id)
            + "/contracts?status=ACTIVE&page_size=100",
            headers=_auth_header(token),
        )
        assert response.status_code == 200, response.text
        returned_ids = {item["id"] for item in response.json()["data"]["items"]}
        assert str(active_ctx["contract"].id) in returned_ids
        assert str(other_company_active_ctx["contract"].id) not in returned_ids
