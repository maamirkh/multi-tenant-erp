"""[T206] [Gate B — final coverage] Exhaustive permission matrix over
every Platform route.

Revision 2 split from the old Gate B task: T076
(`test_permission_enforcement_phase5.py`) proved the Phase-5 surface (9
operations — 3 public `/auth/*` + 6 Administrator/RBAC) before every
other Platform router existed. This test completes coverage now that
every router exists (Phases 4-13): the **complete** 30 permission-guarded
operations from `contracts/platform-admin-v1.yaml` (33 total minus the 3
public `/auth/*` operations already covered by T076).

For each operation: holding the required permission succeeds; holding
only an adjacent (unrelated) permission fails with 403; no
authentication fails with 401. The matrix's own completeness is also
asserted against the real YAML contract, directly, so this file cannot
silently drift out of sync with the contract the way a hand-maintained
duplicate could.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.config.settings import get_settings
from core.utils.datetime import utcnow
from modules.auth.models.session import Session as TenantSession
from modules.auth.models.user import User
from modules.auth.services.jwt_service import JWTService
from modules.companies.models.company import Company
from modules.platform_admin.models.plan import Plan
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_session import PlatformSession
from modules.platform_admin.models.support_access_grant import SupportAccessGrant
from modules.platform_admin.repositories.override_repository import OverrideRepository
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)

_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
_UNRELATED_PERMISSION = "platform.dashboard.view"

# ---------------------------------------------------------------------------
# Load the real contract — the source of truth, never a hand-duplicated copy.
# ---------------------------------------------------------------------------


def _contract_path() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = (
            parent
            / "specs"
            / "009a-platform-admin"
            / "contracts"
            / "platform-admin-v1.yaml"
        )
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "platform-admin-v1.yaml not found by walking up from "
        f"{here} — run against a full repo checkout."
    )


def _load_guarded_operations() -> list[tuple[str, str, str]]:
    """`[(METHOD, path_template_without_server_prefix, x-permission), ...]`
    for every operation that declares an `x-permission` (excludes the 3
    public `/auth/*` operations, which carry none)."""
    with _contract_path().open() as f:
        spec: dict[str, Any] = yaml.safe_load(f)
    ops: list[tuple[str, str, str]] = []
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            if method not in _HTTP_METHODS:
                continue
            permission = operation.get("x-permission")
            if permission is not None:
                ops.append((method.upper(), path, permission))
    return ops


GUARDED_OPERATIONS = _load_guarded_operations()

API_PREFIX = "/api/v1/platform"


def test_guarded_operations_are_exactly_thirty() -> None:
    assert len(GUARDED_OPERATIONS) == 30, (
        f"Expected exactly 30 permission-guarded operations "
        f"(33 total - 3 public /auth/* ops), found {len(GUARDED_OPERATIONS)}: "
        f"{GUARDED_OPERATIONS}"
    )
    # Every operation in T076's recorded Phase-5 scope is re-covered here.
    phase5_guarded = {
        ("GET", "/administrators", "platform.admins.read"),
        ("POST", "/administrators", "platform.admins.manage"),
        ("PATCH", "/administrators/{adminId}", "platform.admins.manage"),
        ("GET", "/roles", "platform.rbac.read"),
        ("POST", "/roles", "platform.rbac.manage"),
        ("POST", "/administrators/{adminId}/roles", "platform.rbac.manage"),
    }
    assert phase5_guarded.issubset(set(GUARDED_OPERATIONS))


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def _make_tenant_access_token(db: Session) -> str:
    user = User(
        email=f"tenant-matrix-{uuid.uuid4().hex[:12]}@example.test",
        display_name="Tenant User",
    )
    db.add(user)
    db.flush()
    session = TenantSession(user_id=user.id)
    db.add(session)
    db.flush()
    db.commit()
    jwt_svc = JWTService(get_settings())
    return jwt_svc.create_access_token(
        user_id=user.id, email=user.email, session_id=session.id
    )


def _make_platform_administrator(
    db: Session, *, is_active: bool = True
) -> PlatformAdministrator:
    user = User(
        email=f"platform-matrix-{uuid.uuid4().hex[:12]}@example.test",
        display_name="Platform Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=is_active)
    db.add(administrator)
    db.flush()
    db.commit()
    return administrator


def _make_platform_token_with_permissions(
    db: Session, codes: set[str]
) -> tuple[PlatformAdministrator, str]:
    """A fresh PlatformAdministrator holding EXACTLY *codes*."""
    administrator = _make_platform_administrator(db)

    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()

    role_code = f"test-matrix-role-{uuid.uuid4().hex[:10]}"
    role = rbac_repo.create_role(code=role_code, name="Test Matrix Role")
    rbac_repo.set_role_permissions(role.id, set(codes))
    rbac_repo.assign_role(
        platform_administrator_id=administrator.id,
        role_id=role.id,
        assigned_by=None,
        assigned_at=utcnow(),
    )
    db.commit()

    session = PlatformSession(
        platform_administrator_id=administrator.id,
        expires_at=utcnow() + timedelta(days=1),
    )
    db.add(session)
    db.flush()
    db.commit()

    token = PlatformJwtService(get_settings()).create_access_token(
        platform_administrator_id=administrator.id, session_id=session.id
    )
    return administrator, token


def _new_company(
    db: Session, *, status: str = "active", pre_suspension_status: str | None = None
) -> Company:
    owner = User(
        email=f"matrix-owner-{uuid.uuid4().hex[:12]}@example.test",
        display_name="Owner",
    )
    db.add(owner)
    db.flush()
    suffix = uuid.uuid4().hex[:10]
    company = Company(
        legal_name=f"Matrix Co {suffix}",
        slug=f"matrix-co-{suffix}",
        owner_id=owner.id,
        email=f"matrix-co-{suffix}@example.test",
        status=status,
        pre_suspension_status=pre_suspension_status,
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


def _new_plan(db: Session, *, status: str = "draft") -> Plan:
    suffix = uuid.uuid4().hex[:10]
    plan = Plan(
        code=f"matrix-plan-{suffix}", name=f"Matrix Plan {suffix}", status=status
    )
    db.add(plan)
    db.flush()
    db.commit()
    return plan


def _new_entitlement_override(db: Session, company: Company, actor_id: UUID) -> UUID:
    repo = OverrideRepository(db)
    override = repo.create_override(
        company_id=company.id,
        capability_key="crm",
        reason="matrix setup",
        actor_id=actor_id,
        granted_at=utcnow(),
    )
    db.commit()
    return override.id


def _new_support_access_grant(db: Session, company: Company, actor_id: UUID) -> UUID:
    grant = SupportAccessGrant(
        platform_administrator_id=actor_id,
        company_id=company.id,
        reason="matrix setup",
        started_at=utcnow(),
        expires_at=utcnow() + timedelta(hours=1),
        status="active",
    )
    db.add(grant)
    db.flush()
    db.commit()
    return grant.id


@dataclass(frozen=True)
class OpFixture:
    """A fully-resolved request for one operation, built fresh per test."""

    path: str
    body: dict[str, Any] | None


Builder = Callable[[Session, PlatformAdministrator], OpFixture]


def _build_administrators_get(db: Session, actor: PlatformAdministrator) -> OpFixture:
    return OpFixture(f"{API_PREFIX}/administrators", None)


def _build_administrators_post(db: Session, actor: PlatformAdministrator) -> OpFixture:
    new_user = User(
        email=f"matrix-new-admin-{uuid.uuid4().hex[:12]}@example.test",
        display_name="New",
    )
    db.add(new_user)
    db.commit()
    return OpFixture(f"{API_PREFIX}/administrators", {"user_id": str(new_user.id)})


def _build_administrator_patch(db: Session, actor: PlatformAdministrator) -> OpFixture:
    target = _make_platform_administrator(db, is_active=True)
    return OpFixture(f"{API_PREFIX}/administrators/{target.id}", {"is_active": True})


def _build_roles_get(db: Session, actor: PlatformAdministrator) -> OpFixture:
    return OpFixture(f"{API_PREFIX}/roles", None)


def _build_roles_post(db: Session, actor: PlatformAdministrator) -> OpFixture:
    return OpFixture(
        f"{API_PREFIX}/roles",
        {
            "code": f"matrix-created-role-{uuid.uuid4().hex[:10]}",
            "name": "Matrix Created Role",
            "permission_codes": [],
        },
    )


def _build_assign_role(db: Session, actor: PlatformAdministrator) -> OpFixture:
    target = _make_platform_administrator(db, is_active=True)
    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    analyst_role = rbac_repo.get_role_by_code("read_only_platform_analyst")
    assert analyst_role is not None
    return OpFixture(
        f"{API_PREFIX}/administrators/{target.id}/roles",
        {"role_id": str(analyst_role.id)},
    )


def _build_suspend(db: Session, actor: PlatformAdministrator) -> OpFixture:
    company = _new_company(db, status="active")
    return OpFixture(
        f"{API_PREFIX}/tenants/{company.id}/suspend", {"reason": "matrix test"}
    )


def _build_reactivate(db: Session, actor: PlatformAdministrator) -> OpFixture:
    company = _new_company(db, status="suspended", pre_suspension_status="active")
    return OpFixture(
        f"{API_PREFIX}/tenants/{company.id}/reactivate", {"reason": "matrix test"}
    )


def _build_plans_get(db: Session, actor: PlatformAdministrator) -> OpFixture:
    return OpFixture(f"{API_PREFIX}/plans", None)


def _build_plans_post(db: Session, actor: PlatformAdministrator) -> OpFixture:
    suffix = uuid.uuid4().hex[:10]
    return OpFixture(
        f"{API_PREFIX}/plans", {"code": f"matrix-plan-{suffix}", "name": "Matrix Plan"}
    )


def _build_plan_patch(db: Session, actor: PlatformAdministrator) -> OpFixture:
    plan = _new_plan(db, status="draft")
    return OpFixture(
        f"{API_PREFIX}/plans/{plan.id}", {"action": "update", "name": "Matrix Renamed"}
    )


def _build_subscription_get(db: Session, actor: PlatformAdministrator) -> OpFixture:
    company = _new_company(db)
    return OpFixture(f"{API_PREFIX}/tenants/{company.id}/subscription", None)


def _build_subscription_post(db: Session, actor: PlatformAdministrator) -> OpFixture:
    company = _new_company(db)
    plan = _new_plan(db, status="published")
    return OpFixture(
        f"{API_PREFIX}/tenants/{company.id}/subscription",
        {"plan_id": str(plan.id), "effective_date": date.today().isoformat()},
    )


def _build_entitlements_get(db: Session, actor: PlatformAdministrator) -> OpFixture:
    company = _new_company(db)
    return OpFixture(f"{API_PREFIX}/tenants/{company.id}/entitlements", None)


def _build_entitlement_override_post(
    db: Session, actor: PlatformAdministrator
) -> OpFixture:
    company = _new_company(db)
    return OpFixture(
        f"{API_PREFIX}/tenants/{company.id}/entitlement-overrides",
        {"capability_key": "crm", "reason": "matrix test"},
    )


def _build_entitlement_override_delete(
    db: Session, actor: PlatformAdministrator
) -> OpFixture:
    company = _new_company(db)
    override_id = _new_entitlement_override(db, company, actor.id)
    return OpFixture(
        f"{API_PREFIX}/tenants/{company.id}/entitlement-overrides/{override_id}", None
    )


def _build_quotas_get(db: Session, actor: PlatformAdministrator) -> OpFixture:
    company = _new_company(db)
    return OpFixture(f"{API_PREFIX}/tenants/{company.id}/quotas", None)


def _build_quota_override_post(db: Session, actor: PlatformAdministrator) -> OpFixture:
    company = _new_company(db)
    return OpFixture(
        f"{API_PREFIX}/tenants/{company.id}/quota-overrides",
        {"quota_key": "users", "reason": "matrix test"},
    )


def _build_support_access_post(db: Session, actor: PlatformAdministrator) -> OpFixture:
    company = _new_company(db)
    return OpFixture(
        f"{API_PREFIX}/tenants/{company.id}/support-access", {"reason": "matrix test"}
    )


def _build_support_access_delete(
    db: Session, actor: PlatformAdministrator
) -> OpFixture:
    company = _new_company(db)
    other_admin = _make_platform_administrator(db)
    grant_id = _new_support_access_grant(db, company, other_admin.id)
    return OpFixture(f"{API_PREFIX}/support-access/{grant_id}", None)


def _build_support_access_get(db: Session, actor: PlatformAdministrator) -> OpFixture:
    return OpFixture(f"{API_PREFIX}/support-access", None)


def _build_audit_get(db: Session, actor: PlatformAdministrator) -> OpFixture:
    return OpFixture(f"{API_PREFIX}/audit", None)


def _build_usage_get(db: Session, actor: PlatformAdministrator) -> OpFixture:
    company = _new_company(db)
    return OpFixture(f"{API_PREFIX}/tenants/{company.id}/usage", None)


def _build_ai_credits_get(db: Session, actor: PlatformAdministrator) -> OpFixture:
    company = _new_company(db)
    return OpFixture(f"{API_PREFIX}/tenants/{company.id}/ai-credits", None)


def _build_ai_credits_post(db: Session, actor: PlatformAdministrator) -> OpFixture:
    company = _new_company(db)
    return OpFixture(
        f"{API_PREFIX}/tenants/{company.id}/ai-credits",
        {"delta": "10", "reason": "matrix test"},
    )


def _build_health_get(db: Session, actor: PlatformAdministrator) -> OpFixture:
    return OpFixture(f"{API_PREFIX}/health", None)


def _build_tenants_get(db: Session, actor: PlatformAdministrator) -> OpFixture:
    return OpFixture(f"{API_PREFIX}/tenants", None)


def _build_tenant_detail_get(db: Session, actor: PlatformAdministrator) -> OpFixture:
    company = _new_company(db)
    return OpFixture(f"{API_PREFIX}/tenants/{company.id}", None)


def _build_lifecycle_history_get(
    db: Session, actor: PlatformAdministrator
) -> OpFixture:
    company = _new_company(db)
    return OpFixture(f"{API_PREFIX}/tenants/{company.id}/lifecycle-history", None)


def _build_dashboard_get(db: Session, actor: PlatformAdministrator) -> OpFixture:
    return OpFixture(f"{API_PREFIX}/dashboard", None)


OPERATION_BUILDERS: dict[tuple[str, str], Builder] = {
    ("GET", "/administrators"): _build_administrators_get,
    ("POST", "/administrators"): _build_administrators_post,
    ("PATCH", "/administrators/{adminId}"): _build_administrator_patch,
    ("GET", "/roles"): _build_roles_get,
    ("POST", "/roles"): _build_roles_post,
    ("POST", "/administrators/{adminId}/roles"): _build_assign_role,
    ("POST", "/tenants/{companyId}/suspend"): _build_suspend,
    ("POST", "/tenants/{companyId}/reactivate"): _build_reactivate,
    ("GET", "/plans"): _build_plans_get,
    ("POST", "/plans"): _build_plans_post,
    ("PATCH", "/plans/{planId}"): _build_plan_patch,
    ("GET", "/tenants/{companyId}/subscription"): _build_subscription_get,
    ("POST", "/tenants/{companyId}/subscription"): _build_subscription_post,
    ("GET", "/tenants/{companyId}/entitlements"): _build_entitlements_get,
    (
        "POST",
        "/tenants/{companyId}/entitlement-overrides",
    ): _build_entitlement_override_post,
    (
        "DELETE",
        "/tenants/{companyId}/entitlement-overrides/{overrideId}",
    ): _build_entitlement_override_delete,
    ("GET", "/tenants/{companyId}/quotas"): _build_quotas_get,
    ("POST", "/tenants/{companyId}/quota-overrides"): _build_quota_override_post,
    ("POST", "/tenants/{companyId}/support-access"): _build_support_access_post,
    ("DELETE", "/support-access/{grantId}"): _build_support_access_delete,
    ("GET", "/support-access"): _build_support_access_get,
    ("GET", "/audit"): _build_audit_get,
    ("GET", "/tenants/{companyId}/usage"): _build_usage_get,
    ("GET", "/tenants/{companyId}/ai-credits"): _build_ai_credits_get,
    ("POST", "/tenants/{companyId}/ai-credits"): _build_ai_credits_post,
    ("GET", "/health"): _build_health_get,
    ("GET", "/tenants"): _build_tenants_get,
    ("GET", "/tenants/{companyId}"): _build_tenant_detail_get,
    ("GET", "/tenants/{companyId}/lifecycle-history"): _build_lifecycle_history_get,
    ("GET", "/dashboard"): _build_dashboard_get,
}


def test_every_guarded_operation_has_a_builder() -> None:
    """The matrix is complete: no guarded contract operation is missing a
    test fixture builder, and no builder targets an undeclared operation."""
    declared = {(method, path) for method, path, _ in GUARDED_OPERATIONS}
    built = set(OPERATION_BUILDERS.keys())
    assert declared == built, (
        f"Mismatch between contract-declared operations and builders. "
        f"Missing builders: {declared - built}. Extra builders: {built - declared}."
    )


def _request(
    test_client: TestClient, method: str, fixture: OpFixture, token: str | None
) -> Any:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    kwargs: dict[str, Any] = {"headers": headers}
    if method in ("POST", "PATCH", "PUT"):
        kwargs["json"] = fixture.body if fixture.body is not None else {}
    return getattr(test_client, method.lower())(fixture.path, **kwargs)


# ---------------------------------------------------------------------------
# The exhaustive matrix: unauthenticated / tenant-token / adjacent-permission
# / required-permission, over all 30 operations.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("method,path,permission", GUARDED_OPERATIONS)
def test_guarded_operation_rejects_unauthenticated(
    test_client: TestClient,
    db_session: Session,
    method: str,
    path: str,
    permission: str,
) -> None:
    # A throwaway actor only to satisfy builders that need *an* actor id
    # for setup (e.g. as the initiator of a pre-existing resource) — the
    # request itself carries no token.
    setup_actor = _make_platform_administrator(db_session)
    fixture = OPERATION_BUILDERS[(method, path)](db_session, setup_actor)

    response = _request(test_client, method, fixture, token=None)

    assert response.status_code == 401, (
        method,
        path,
        response.status_code,
        response.text,
    )


@pytest.mark.parametrize("method,path,permission", GUARDED_OPERATIONS)
def test_guarded_operation_rejects_tenant_token(
    test_client: TestClient,
    db_session: Session,
    method: str,
    path: str,
    permission: str,
) -> None:
    setup_actor = _make_platform_administrator(db_session)
    fixture = OPERATION_BUILDERS[(method, path)](db_session, setup_actor)
    tenant_token = _make_tenant_access_token(db_session)

    response = _request(test_client, method, fixture, token=tenant_token)

    assert response.status_code == 401, (
        method,
        path,
        response.status_code,
        response.text,
    )


@pytest.mark.parametrize("method,path,permission", GUARDED_OPERATIONS)
def test_guarded_operation_rejects_adjacent_permission(
    test_client: TestClient,
    db_session: Session,
    method: str,
    path: str,
    permission: str,
) -> None:
    adjacent = (
        _UNRELATED_PERMISSION
        if permission != _UNRELATED_PERMISSION
        else "platform.audit.read"
    )
    actor, token = _make_platform_token_with_permissions(db_session, {adjacent})
    fixture = OPERATION_BUILDERS[(method, path)](db_session, actor)

    response = _request(test_client, method, fixture, token=token)

    assert response.status_code == 403, (
        method,
        path,
        response.status_code,
        response.text,
    )


@pytest.mark.parametrize("method,path,permission", GUARDED_OPERATIONS)
def test_guarded_operation_succeeds_with_required_permission(
    test_client: TestClient,
    db_session: Session,
    method: str,
    path: str,
    permission: str,
) -> None:
    actor, token = _make_platform_token_with_permissions(db_session, {permission})
    fixture = OPERATION_BUILDERS[(method, path)](db_session, actor)

    response = _request(test_client, method, fixture, token=token)

    assert response.status_code in (200, 201, 204), (
        method,
        path,
        permission,
        response.status_code,
        response.text,
    )
