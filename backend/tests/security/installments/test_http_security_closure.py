"""[Epic 10, Phase 11 — HTTP Security Evidence Closure] Real,
live-ASGI-request evidence for the mounted Installments router (T190),
closing the gaps the read-only verification pass identified: every
previous Phase 11 test exercised services directly, never through a
real authenticated HTTP request against the actual mounted app.

Every test in this file sends a genuine request through
``installments_http_client`` — a real ``main.create_app()`` instance,
the real ``api.v1.router`` assembly (including the real T190 mount),
with ONLY ``get_db`` overridden. No Installments-specific dependency is
stubbed, bypassed, or overridden anywhere in this file. Authentication
uses the real ``/api/v1/auth/login`` endpoint (not a hand-constructed
token); RBAC uses real ``Role``/``RolePermission``/``CompanyMember``
rows resolved through the real ``user_has_installments_permission()``
chain; entitlement uses the real ``InstallmentsFeatureFlagService``.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.installments.models.contract import InstallmentContract
from modules.installments.models.idempotency import InstallmentIdempotencyKey
from modules.installments.models.plan_template import InstallmentPlanTemplate
from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.services.feature_flag_service import (
    InstallmentsFeatureFlagService,
)
from modules.platform_admin.models.platform_administrator import (
    PlatformAdministrator,
)
from modules.platform_admin.models.platform_session import PlatformSession
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService
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
    owner = User(email=f"http-owner-{suffix}@example.test", display_name="HTTP Owner")
    db.add(owner)
    db.flush()
    company = Company(
        id=company_id or uuid.uuid4(),
        legal_name=f"HTTP Closure Co {suffix}",
        slug=f"http-closure-co-{suffix}",
        owner_id=owner.id,
        email=f"http-closure-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


def _login(test_client: TestClient, db: Session, *, email: str, password: str) -> str:
    """Real login through ``/api/v1/auth/login`` — a genuine, fully-valid
    access token backed by a real DB session row, not a hand-minted JWT."""
    create_test_user(db, email=email, password=password)
    db.commit()
    response = test_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


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
    db: Session,
    *,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    codes: set[str],
) -> None:
    """Real Role/RolePermission/CompanyMember rows — the actual chain
    ``user_has_installments_permission()`` resolves through."""
    for code in codes:
        _ensure_permission(db, code)
    role = Role(
        company_id=company_id,
        name=f"HTTP Closure Role {uuid.uuid4().hex[:8]}",
        slug=f"http-closure-role-{uuid.uuid4().hex[:10]}",
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


def _enable_installments(db: Session, company_id: uuid.UUID) -> None:
    InstallmentsFeatureFlagService(
        flag_repo=InstallmentsFeatureFlagRepository(db)
    ).enable(company_id)
    db.commit()


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestHttpAuthentication:
    """[Section 1] Unauthenticated request to a mounted Installments
    endpoint is rejected before ever reaching the service."""

    def test_unauthenticated_request_is_rejected(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        company = _make_company(pg_db_session)

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id) + "/contracts"
        )
        assert response.status_code == 401, response.text

    def test_malformed_bearer_token_is_rejected(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        company = _make_company(pg_db_session)

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id) + "/contracts",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert response.status_code == 401, response.text


class TestHttpRbacDenial:
    """[Section 2] Authenticated tenant member, correct tenant, missing
    the endpoint's required permission -> denied, zero mutation."""

    def test_missing_permission_denies_plan_template_creation(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        company = _make_company(pg_db_session)
        email = f"t2-rbac-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client,
            pg_db_session,
            email=email,
            password="RbacDenial@1234",
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        # Grant a role with an UNRELATED permission only — never
        # installments.plan.manage.
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.contract.view"},
        )
        _enable_installments(pg_db_session, company.id)

        templates_before = (
            pg_db_session.execute(
                select(InstallmentPlanTemplate).where(
                    InstallmentPlanTemplate.company_id == company.id
                )
            )
            .scalars()
            .all()
        )
        assert templates_before == []

        response = installments_http_client.post(
            _INSTALLMENTS_PREFIX.format(company_id=company.id) + "/plans",
            json={
                "name": "Should Never Be Created",
                "installment_count": 6,
                "frequency": "MONTHLY",
                "down_payment_rule": {"type": "FIXED", "amount": "0"},
            },
            headers=_auth_header(token),
        )
        assert response.status_code == 403, response.text

        templates_after = (
            pg_db_session.execute(
                select(InstallmentPlanTemplate).where(
                    InstallmentPlanTemplate.company_id == company.id
                )
            )
            .scalars()
            .all()
        )
        assert templates_after == [], "RBAC denial must create ZERO business rows"


class TestHttpEntitlementDenialCombinedScenario:
    """[Section 3 — MANDATORY] A single integrated HTTP request:
    authenticated + correctly permissioned + entitlement DISABLED +
    ORIGINATION operation -> 403 FEATURE_DISABLED, zero mutation, zero
    idempotency reservation."""

    def test_permission_present_entitlement_disabled_origination_denied(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="DRAFT",
        )
        company = _make_company(pg_db_session, company_id=ctx["company_id"])
        email = f"t3-combined-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client,
            pg_db_session,
            email=email,
            password="Combined@1234",
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        # Permission PRESENT — the exact permission this endpoint checks.
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.contract.cancel"},
        )
        # Entitlement explicitly left DISABLED (default state — no
        # enable() call in this test, unlike every other test in this
        # file).

        response = installments_http_client.post(
            _INSTALLMENTS_PREFIX.format(company_id=company.id)
            + f"/contracts/{ctx['contract'].id}/cancel",
            json={"reason": "Combined scenario probe."},
            headers={**_auth_header(token), "Idempotency-Key": str(uuid.uuid4())},
        )

        assert response.status_code == 403, response.text
        body = response.json()
        assert body["error"]["code"] == "FEATURE_DISABLED", body

        # Zero mutation.
        refreshed = (
            pg_db_session.query(InstallmentContract)
            .filter_by(id=ctx["contract"].id)
            .one()
        )
        assert refreshed.status == "DRAFT"
        assert refreshed.cancelled_at is None

        # Zero idempotency reservation — authorize() fires before
        # self._idempotency.reserve() (structurally confirmed in the
        # read-only pass; this empirically confirms it end-to-end).
        reservations = (
            pg_db_session.execute(
                select(InstallmentIdempotencyKey)
                .where(InstallmentIdempotencyKey.company_id == company.id)
                .where(InstallmentIdempotencyKey.operation == "contract.cancel")
            )
            .scalars()
            .all()
        )
        assert reservations == [], "no idempotency reservation may be persisted"


class TestHttpServicingContinuity:
    """[Section 4] Entitlement DISABLED, valid permission present: a
    SERVICING operation (record a collection against an existing
    contract) succeeds via real HTTP (FR-INST-356)."""

    def test_record_collection_succeeds_when_entitlement_disabled(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        company = _make_company(pg_db_session, company_id=ctx["company_id"])
        email = f"t4-servicing-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client,
            pg_db_session,
            email=email,
            password="Servicing@1234",
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.collection.create"},
        )
        # Entitlement left DISABLED deliberately.

        response = installments_http_client.post(
            _INSTALLMENTS_PREFIX.format(company_id=company.id)
            + f"/contracts/{ctx['contract'].id}/collections",
            json={
                "amount": "50.00",
                "payment_method": "BANK_TRANSFER",
                "bank_account_id": str(ctx["bank_account"].id),
            },
            headers={**_auth_header(token), "Idempotency-Key": str(uuid.uuid4())},
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["accounting_payment_id"] is not None


class TestHttpTenantIsolation:
    """[Section 5] Tenant A member, real membership only in Company A,
    attempting to reach Company B's Installments resource via real
    HTTP. Tenant scoping is authenticated-context-derived
    (``get_current_company_member`` resolves membership from the JWT's
    own user_id, never from the request body)."""

    def test_read_cross_tenant_resource_rejected_and_unchanged(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx_b = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        company_b = _make_company(pg_db_session, company_id=ctx_b["company_id"])
        company_a = _make_company(pg_db_session)
        email = f"t5-tenant-a-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client,
            pg_db_session,
            email=email,
            password="TenantA@1234",
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company_a.id,
            user_id=user_row.id,
            codes={"installments.contract.view", "installments.contract.cancel"},
        )
        _enable_installments(pg_db_session, company_a.id)

        before = (
            pg_db_session.query(InstallmentContract)
            .filter_by(id=ctx_b["contract"].id)
            .one()
        )
        before_status, before_updated_at = before.status, before.updated_at

        # Tenant A's OWN company_id in the path, but Company B's
        # contractId — the actual IDOR vector, not a company_id swap.
        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company_a.id)
            + f"/contracts/{ctx_b['contract'].id}",
            headers=_auth_header(token),
        )
        assert response.status_code == 404, response.text

        after = (
            pg_db_session.query(InstallmentContract)
            .filter_by(id=ctx_b["contract"].id)
            .one()
        )
        assert after.status == before_status
        assert after.updated_at == before_updated_at
        assert after.company_id == company_b.id

    def test_mutation_cross_tenant_resource_rejected_and_unchanged(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx_b = build_active_contract_with_schedule(
            pg_db_session,
            installment_count=1,
            installment_amount=Decimal("100.00"),
            status="DRAFT",
        )
        company_b = _make_company(pg_db_session, company_id=ctx_b["company_id"])
        company_a = _make_company(pg_db_session)
        email = f"t5-tenant-a-mut-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client,
            pg_db_session,
            email=email,
            password="TenantAMut@1234",
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company_a.id,
            user_id=user_row.id,
            codes={"installments.contract.cancel"},
        )
        _enable_installments(pg_db_session, company_a.id)

        before = (
            pg_db_session.query(InstallmentContract)
            .filter_by(id=ctx_b["contract"].id)
            .one()
        )
        before_status = before.status
        assert before_status == "DRAFT"

        response = installments_http_client.post(
            _INSTALLMENTS_PREFIX.format(company_id=company_a.id)
            + f"/contracts/{ctx_b['contract'].id}/cancel",
            json={"reason": "Cross-tenant mutation probe."},
            headers={**_auth_header(token), "Idempotency-Key": str(uuid.uuid4())},
        )
        assert response.status_code == 404, response.text

        after = (
            pg_db_session.query(InstallmentContract)
            .filter_by(id=ctx_b["contract"].id)
            .one()
        )
        assert after.status == before_status
        assert after.cancelled_at is None
        assert after.company_id == company_b.id

    def test_wrong_company_id_in_path_rejected_by_membership_check(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        """The complementary case: Tenant A's authenticated user attempts
        to use Company B's id directly in the URL path — rejected by
        ``get_current_company_member`` itself (no real membership row),
        before the Installments router/service is ever reached."""
        company_a = _make_company(pg_db_session)
        company_b = _make_company(pg_db_session)
        email = f"t5-path-swap-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client,
            pg_db_session,
            email=email,
            password="PathSwap@1234",
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company_a.id,
            user_id=user_row.id,
            codes={"installments.contract.view"},
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company_b.id) + "/contracts",
            headers=_auth_header(token),
        )
        assert response.status_code == 403, response.text


class TestHttpValidHappyPath:
    """[Section 6] Correct authentication + tenant + entitlement +
    permission -> the mounted runtime path is genuinely functional, not
    merely deny-only."""

    def test_plan_template_creation_succeeds_end_to_end(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        company = _make_company(pg_db_session)
        email = f"t6-happy-{uuid.uuid4().hex[:10]}@example.com"
        token = _login(
            installments_http_client,
            pg_db_session,
            email=email,
            password="HappyPath@1234",
        )
        user_row = pg_db_session.query(User).filter_by(email=email).one()
        _grant_membership_with_permissions(
            pg_db_session,
            company_id=company.id,
            user_id=user_row.id,
            codes={"installments.plan.manage"},
        )
        _enable_installments(pg_db_session, company.id)

        response = installments_http_client.post(
            _INSTALLMENTS_PREFIX.format(company_id=company.id) + "/plans",
            json={
                "name": "Happy Path Plan",
                "installment_count": 12,
                "frequency": "MONTHLY",
                "down_payment_rule": {"type": "FIXED", "amount": "0"},
            },
            headers=_auth_header(token),
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["data"]["name"] == "Happy Path Plan"
        assert body["data"]["company_id"] == str(company.id)
        assert "message" in body
        assert "meta" in body

        persisted = (
            pg_db_session.execute(
                select(InstallmentPlanTemplate).where(
                    InstallmentPlanTemplate.company_id == company.id
                )
            )
            .scalars()
            .all()
        )
        assert len(persisted) == 1
        assert persisted[0].name == "Happy Path Plan"


class TestHttpPlatformJwtRejection:
    """[Section 7] A valid Platform Admin JWT, with no tenant
    ``CompanyMember`` identity, attempting a tenant Installments
    endpoint -> rejected, live HTTP.

    Empirical note (not a Phase-11 defect — pre-existing Epic 2/9A
    infrastructure, unrelated to Installments): the tenant
    ``JWTService.decode_access_token()``/``get_current_user()`` chain
    never inspects the token's own ``typ`` claim. A Platform token
    shares the same signing secret/issuer/audience as a tenant token
    (only ``typ`` and the ``sub`` semantics differ), so it decodes
    successfully here; rejection instead occurs because the token's
    ``sub`` (a ``PlatformAdministrator.id``) does not match any real
    ``User.id`` row, so ``UserRepository.get_by_id_or_none()`` returns
    ``None`` and ``get_current_user()`` raises. The net behavioural
    outcome required here (Platform authority alone does not satisfy
    tenant auth) holds, but via a coincidental id-lookup miss rather
    than an explicit, defensive ``typ``-claim check — the mirror image
    of the tenant-token-crossover boundary already defended explicitly
    on the Platform Admin side (T163's
    ``TestSupportAccessRejectsTenantTokenCrossover``, which the
    Platform side's ``get_current_platform_admin`` DOES check via a
    distinct claim path)."""

    def test_platform_jwt_rejected_by_tenant_endpoint(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        ctx = build_active_contract_with_schedule(
            pg_db_session, installment_count=1, installment_amount=Decimal("100.00")
        )
        company = _make_company(pg_db_session, company_id=ctx["company_id"])

        admin_user = User(
            email=f"t7-platform-{uuid.uuid4().hex[:10]}@example.test",
            display_name="T7 Platform Admin",
        )
        pg_db_session.add(admin_user)
        pg_db_session.flush()
        administrator = PlatformAdministrator(user_id=admin_user.id, is_active=True)
        pg_db_session.add(administrator)
        pg_db_session.flush()
        platform_session = PlatformSession(
            platform_administrator_id=administrator.id,
            expires_at=utcnow() + timedelta(days=1),
        )
        pg_db_session.add(platform_session)
        pg_db_session.flush()
        pg_db_session.commit()

        from core.config.settings import get_settings

        platform_token = PlatformJwtService(get_settings()).create_access_token(
            platform_administrator_id=administrator.id, session_id=platform_session.id
        )

        response = installments_http_client.get(
            _INSTALLMENTS_PREFIX.format(company_id=company.id) + "/contracts",
            headers=_auth_header(platform_token),
        )
        assert response.status_code == 401, response.text
        assert "Confidential" not in response.text
        assert str(ctx["contract"].id) not in response.text
