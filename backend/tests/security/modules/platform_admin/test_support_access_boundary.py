"""[T163, T164, T165] [Gate F] Support-access security boundary —
Epic 9A Phase 12 (BR-9A-021, FR-9A-190..197, resolved OQ-2).

T163: with an active grant on a tenant holding real business data (a
genuine `Product` row), no support-access route exposes it — proven both
by a static import check (the service module and the whole platform_admin
router import no business-record repository from any of the five
modules) and live HTTP (only the 3 contract-declared paths exist; no
other support-access-scoped path returns anything).

T164: post-expiry and post-termination requests are rejected via
`assert_grant_active()`, and both transitions are recorded in the audit
trail.

T165: support access requires its own permission and a mandatory reason.

Real HTTP throughout for the route-level proofs — matching this module's
own established convention (Phase 10/11's security test files).
"""

from __future__ import annotations

import ast
import inspect
import time
import uuid
from datetime import timedelta
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.exceptions.base import NotFoundException, ValidationException
from core.utils.datetime import utcnow
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.inventory.models.product import Product
from modules.inventory.models.uom import UOM
from modules.inventory.repositories.product_repository import ProductRepository
from modules.platform_admin.exceptions import SupportAccessExpiredError
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_audit_event import PlatformAuditEvent
from modules.platform_admin.models.support_access_grant import SupportAccessGrant
from modules.platform_admin.repositories.platform_audit_repository import (
    PlatformAuditRepository,
)
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.repositories.support_access_repository import (
    SupportAccessRepository,
)
from modules.platform_admin.services.platform_audit_service import PlatformAuditService
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)
from modules.platform_admin.services.support_access_service import (
    SupportAccessService,
)
from tests.fixtures.auth_fixtures import create_test_user

_BUSINESS_MODULE_PREFIXES = (
    "modules.inventory",
    "modules.purchase",
    "modules.sales",
    "modules.accounting",
    "modules.crm",
)


def _imports_no_business_record_module(source: str) -> list[str]:
    """Return any import statement in *source* referencing one of the
    five business modules — empty list means clean."""
    tree = ast.parse(source)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if any(node.module.startswith(p) for p in _BUSINESS_MODULE_PREFIXES):
                violations.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name.startswith(p) for p in _BUSINESS_MODULE_PREFIXES):
                    violations.append(alias.name)
    return violations


class TestSupportAccessImportsNoBusinessRecordRepository:
    """[T163] Static proof: the support-access module and the whole
    platform_admin router import nothing from any of the five business
    modules — there is no code path from support access into a
    business-record table (plan.md §21)."""

    def test_support_access_service_imports_no_business_record_module(self) -> None:
        import modules.platform_admin.services.support_access_service as mod

        violations = _imports_no_business_record_module(inspect.getsource(mod))
        assert violations == [], f"forbidden imports found: {violations}"

    def test_platform_admin_router_imports_no_business_record_module(self) -> None:
        import modules.platform_admin.router as mod

        violations = _imports_no_business_record_module(inspect.getsource(mod))
        assert violations == [], f"forbidden imports found: {violations}"


def _make_administrator(db: Session, *, label: str) -> PlatformAdministrator:
    user = User(
        email=f"t163-{label}-{uuid.uuid4().hex[:10]}@example.test",
        display_name=f"T163 {label}",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _make_token_with_permissions(db: Session, codes: set[str]) -> str:
    user = User(
        email=f"t163-admin-{uuid.uuid4().hex[:12]}@example.test",
        display_name="T163 Platform Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"t163-route-role-{uuid.uuid4().hex[:10]}", name="T163 Test Route Role"
    )
    rbac_repo.set_role_permissions(role.id, set(codes))
    rbac_repo.assign_role(
        platform_administrator_id=administrator.id,
        role_id=role.id,
        assigned_by=None,
        assigned_at=utcnow(),
    )
    db.commit()

    from datetime import timedelta as _td

    from modules.platform_admin.models.platform_session import PlatformSession

    session = PlatformSession(
        platform_administrator_id=administrator.id,
        expires_at=utcnow() + _td(days=1),
    )
    db.add(session)
    db.flush()
    db.commit()

    from core.config.settings import get_settings

    return PlatformJwtService(get_settings()).create_access_token(
        platform_administrator_id=administrator.id, session_id=session.id
    )


def _make_company_with_real_business_data(db: Session) -> Company:
    """A tenant holding at least one genuine business record (a
    `Product`) — the concrete case quickstart.md §7 requires."""
    suffix = uuid.uuid4().hex[:10]
    owner = User(email=f"t163-owner-{suffix}@example.test", display_name="T163 Owner")
    db.add(owner)
    db.flush()
    company = Company(
        legal_name=f"T163 Support Access Co {suffix}",
        slug=f"t163-support-access-co-{suffix}",
        owner_id=owner.id,
        email=f"t163-support-access-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()

    uom = UOM(
        company_id=company.id,
        code="PCS",
        name="Pieces",
        uom_type="UNIT",
        status="active",
    )
    db.add(uom)
    db.flush()

    product = Product(
        company_id=company.id,
        product_code=f"T163-PROD-{suffix}",
        name="T163 Confidential Business Product",
        product_type="STANDARD",
        status="DRAFT",
        base_uom_id=str(uom.id),
    )
    product.search_vector = ProductRepository.build_search_vector(product)
    db.add(product)
    db.flush()
    db.commit()
    return company


def _support_access_service(db: Session) -> SupportAccessService:
    return SupportAccessService(
        db=db,
        repo=SupportAccessRepository(db),
        audit=PlatformAuditService(db, PlatformAuditRepository(db)),
    )


class TestSupportAccessCannotReachBusinessRecords:
    """[T163] Live proof: with an active grant on a tenant holding real
    business data, no support-access endpoint exposes it — because no
    such endpoint exists at all (only initiate/terminate/list)."""

    def test_only_the_three_contract_paths_exist(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company = _make_company_with_real_business_data(db_session)
        actor = _make_administrator(db_session, label="grant-actor")
        _support_access_service(db_session).initiate(
            company_id=company.id,
            reason="T163 — proving the boundary with real business data present.",
            actor_platform_administrator_id=actor.id,
        )

        app = cast(FastAPI, test_client.app)
        spec = app.openapi()
        support_access_paths = {p for p in spec["paths"] if "support-access" in p}
        assert support_access_paths == {
            "/api/v1/platform/tenants/{companyId}/support-access",
            "/api/v1/platform/support-access/{grantId}",
            "/api/v1/platform/support-access",
        }

    def test_no_support_access_endpoint_returns_the_product_data(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company = _make_company_with_real_business_data(db_session)
        token = _make_token_with_permissions(
            db_session, {"platform.support_access.read"}
        )

        response = test_client.get(
            "/api/v1/platform/support-access",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, response.text
        body = response.text
        # The confidential product name must never appear anywhere in the
        # support-access surface's own response.
        assert "Confidential Business Product" not in body


class TestSupportAccessExpiryAndTerminationEndAccess:
    """[T164] Post-expiry and post-termination requests are rejected;
    both are recorded in the audit trail."""

    def test_expired_grant_is_rejected_and_auto_expiry_is_audited(
        self, db_session: Session
    ) -> None:
        actor = _make_administrator(db_session, label="expiry-actor")
        company = _make_company_with_real_business_data(db_session)
        service = _support_access_service(db_session)

        grant = service.initiate(
            company_id=company.id,
            reason="T164 expiry test.",
            actor_platform_administrator_id=actor.id,
        )
        # Force expiry into the near future, then let real time pass —
        # satisfies the model's own `expires_at > started_at` CHECK
        # constraint while still genuinely expiring relative to now().
        grant.expires_at = utcnow() + timedelta(milliseconds=50)
        db_session.commit()
        time.sleep(0.2)

        with pytest.raises(SupportAccessExpiredError):
            service.assert_grant_active(grant.id)

        db_session.refresh(grant)
        assert grant.status == "expired"

        events, total = PlatformAuditRepository(db_session).list_filtered(
            target_id=grant.id, action="support_access.auto_expire"
        )
        assert total == 1

    def test_terminated_grant_is_rejected_and_termination_is_audited(
        self, db_session: Session
    ) -> None:
        actor = _make_administrator(db_session, label="terminate-actor")
        company = _make_company_with_real_business_data(db_session)
        service = _support_access_service(db_session)

        grant = service.initiate(
            company_id=company.id,
            reason="T164 termination test.",
            actor_platform_administrator_id=actor.id,
        )
        service.terminate(grant_id=grant.id, actor_platform_administrator_id=actor.id)

        with pytest.raises(SupportAccessExpiredError):
            service.assert_grant_active(grant.id)

        db_session.refresh(grant)
        assert grant.status == "terminated"
        assert grant.ended_at is not None
        assert grant.ended_by == actor.id

        events, total = PlatformAuditRepository(db_session).list_filtered(
            target_id=grant.id, action="support_access.terminate"
        )
        assert total == 1

    def test_terminate_on_already_expired_grant_reports_expired_not_terminated(
        self, db_session: Session
    ) -> None:
        actor = _make_administrator(db_session, label="double-actor")
        company = _make_company_with_real_business_data(db_session)
        service = _support_access_service(db_session)

        grant = service.initiate(
            company_id=company.id,
            reason="T164 double-transition test.",
            actor_platform_administrator_id=actor.id,
        )
        grant.expires_at = utcnow() + timedelta(milliseconds=50)
        db_session.commit()
        time.sleep(0.2)

        with pytest.raises(SupportAccessExpiredError):
            service.terminate(
                grant_id=grant.id, actor_platform_administrator_id=actor.id
            )

        db_session.refresh(grant)
        # Never overwritten by a false "terminated" transition.
        assert grant.status == "expired"
        assert grant.ended_by is None

    def test_terminate_missing_grant_raises_not_found(
        self, db_session: Session
    ) -> None:
        actor = _make_administrator(db_session, label="missing-actor")
        service = _support_access_service(db_session)

        with pytest.raises(NotFoundException):
            service.terminate(
                grant_id=uuid.uuid4(), actor_platform_administrator_id=actor.id
            )

    def test_record_action_within_active_grant_writes_action_level_audit(
        self, db_session: Session
    ) -> None:
        """[T161 proof, exercised here] The per-action audit seam writes
        a PlatformAuditEvent with support_access_grant_id populated, in
        addition to the grant's own start/end rows."""
        actor = _make_administrator(db_session, label="action-actor")
        company = _make_company_with_real_business_data(db_session)
        service = _support_access_service(db_session)

        grant = service.initiate(
            company_id=company.id,
            reason="T161 per-action audit test.",
            actor_platform_administrator_id=actor.id,
        )
        service.record_action(
            grant_id=grant.id, action="support_access.read.tenant_configuration"
        )
        db_session.commit()

        event = (
            db_session.query(PlatformAuditEvent)
            .filter(
                PlatformAuditEvent.support_access_grant_id == grant.id,
                PlatformAuditEvent.action == "support_access.read.tenant_configuration",
            )
            .one_or_none()
        )
        assert event is not None
        assert event.company_id == company.id

    def test_record_action_on_expired_grant_is_rejected(
        self, db_session: Session
    ) -> None:
        actor = _make_administrator(db_session, label="action-expired-actor")
        company = _make_company_with_real_business_data(db_session)
        service = _support_access_service(db_session)

        grant = service.initiate(
            company_id=company.id,
            reason="T161 expired-grant rejection test.",
            actor_platform_administrator_id=actor.id,
        )
        grant.expires_at = utcnow() + timedelta(milliseconds=50)
        db_session.commit()
        time.sleep(0.2)

        with pytest.raises(SupportAccessExpiredError):
            service.record_action(grant_id=grant.id, action="support_access.read.x")


class TestSupportAccessRequiresPermissionAndReason:
    """[T165] Support access requires its own permission and a reason."""

    def test_initiate_without_permission_is_forbidden(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(db_session, {"platform.tenants.read"})
        company = _make_company_with_real_business_data(db_session)

        response = test_client.post(
            f"/api/v1/platform/tenants/{company.id}/support-access",
            json={"reason": "Should be forbidden."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403, response.text

    def test_initiate_without_reason_is_rejected_before_grant_created(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(
            db_session, {"platform.support_access.initiate"}
        )
        company = _make_company_with_real_business_data(db_session)

        response = test_client.post(
            f"/api/v1/platform/tenants/{company.id}/support-access",
            json={"reason": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422, response.text

        remaining = (
            db_session.query(SupportAccessGrant)
            .filter(SupportAccessGrant.company_id == company.id)
            .all()
        )
        assert remaining == []

    def test_initiate_with_whitespace_only_reason_is_rejected_at_service_layer(
        self, db_session: Session
    ) -> None:
        actor = _make_administrator(db_session, label="blank-reason-actor")
        company = _make_company_with_real_business_data(db_session)
        service = _support_access_service(db_session)

        with pytest.raises(ValidationException):
            service.initiate(
                company_id=company.id,
                reason="   ",
                actor_platform_administrator_id=actor.id,
            )

    def test_initiate_with_valid_permission_and_reason_succeeds(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        token = _make_token_with_permissions(
            db_session, {"platform.support_access.initiate"}
        )
        company = _make_company_with_real_business_data(db_session)

        response = test_client.post(
            f"/api/v1/platform/tenants/{company.id}/support-access",
            json={"reason": "Investigating a customer-reported billing issue."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["status"] == "active"
        assert data["company_id"] == str(company.id)


class TestSupportAccessRejectsTenantTokenCrossover:
    """[master prompt §11] A tenant-typed access token must never
    authenticate against this phase's new Platform-scoped attack surface
    — the same structural boundary Phase 4 established (distinct `typ`
    claim, `get_current_platform_admin` rejects any token whose `sub`
    does not resolve to a `PlatformAdministrator.id`), proven directly
    against the 3 routes this phase adds."""

    def test_tenant_access_token_rejected_by_initiate(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"t163-tenant-user-{uuid.uuid4().hex[:10]}@example.com"
        password = "TenantCrossover@123"
        _, _ = create_test_user(db_session, email=email, password=password)
        db_session.commit()
        login = test_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert login.status_code == 200, login.text
        tenant_token = login.json()["data"]["access_token"]

        company = _make_company_with_real_business_data(db_session)
        response = test_client.post(
            f"/api/v1/platform/tenants/{company.id}/support-access",
            json={"reason": "Attempted tenant-token crossover."},
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        assert response.status_code == 401, response.text

    def test_tenant_access_token_rejected_by_list(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        email = f"t163-tenant-user2-{uuid.uuid4().hex[:10]}@example.com"
        password = "TenantCrossover@123"
        _, _ = create_test_user(db_session, email=email, password=password)
        db_session.commit()
        login = test_client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}
        )
        assert login.status_code == 200, login.text
        tenant_token = login.json()["data"]["access_token"]

        response = test_client.get(
            "/api/v1/platform/support-access",
            headers={"Authorization": f"Bearer {tenant_token}"},
        )
        assert response.status_code == 401, response.text
