"""[T213] Verify request-scoped memoisation of the company-access and
entitlement reads (plan.md §31).

Two concrete, currently-existing per-request duplicate reads are fixed
and proven here:

  1. `require_platform_permission(...)`'s own dependency computes
     `PlatformRbacRepository.get_effective_permissions()` — and the
     `GET /dashboard` route handler (`router.py`) *also* called it
     again, redundantly, for the same administrator within the same
     request. Both now go through `get_effective_permissions_cached()`.
  2. `require_capability_entitled(...)`'s dependency now memoises
     `PlatformEntitlementService.resolve_effective_entitlement()` per
     `(company_id, capability_key)` for the lifetime of one request —
     defensive, matching this task's explicit acceptance text, in case
     a future route depends on the same capability check twice.

Both caches live on `request.state` — a fresh object created by Starlette
for every single HTTP request — so there is no cross-request/process-
level cache, and no invalidation/consistency concern (plan.md §31).
"""

from __future__ import annotations

import types
import uuid
from unittest.mock import patch

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.platform_admin.dependencies import (
    require_capability_entitled,
    require_platform_permission,
)
from modules.platform_admin.exceptions import CapabilityNotEntitledError
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)


def _fake_request() -> types.SimpleNamespace:
    """A minimal stand-in for `starlette.requests.Request` — the
    dependencies under test only ever touch `request.state` via
    `getattr`/`setattr`, exactly like the real object."""
    return types.SimpleNamespace(state=types.SimpleNamespace())


def _make_administrator_with_permissions(
    db: Session, codes: set[str]
) -> PlatformAdministrator:
    user = User(
        email=f"t213-admin-{uuid.uuid4().hex[:12]}@example.com",
        display_name="T213 Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"t213-role-{uuid.uuid4().hex[:10]}", name="T213 Role"
    )
    rbac_repo.set_role_permissions(role.id, set(codes))
    rbac_repo.assign_role(
        platform_administrator_id=administrator.id,
        role_id=role.id,
        assigned_by=None,
        assigned_at=utcnow(),
    )
    db.commit()
    return administrator


def _call_entitlement_dep_ignoring_denial(dep, **kwargs) -> None:
    """This company has no Subscription, so the (correct) resolution is
    Unavailable — the dependency raises. That's expected business
    behaviour, orthogonal to what these tests actually verify: whether
    the underlying resolver was *called* once or twice. The denial
    itself is caught here so both calls execute regardless."""
    try:
        dep(**kwargs)
    except CapabilityNotEntitledError:
        pass


def _make_company(db: Session) -> Company:
    suffix = uuid.uuid4().hex[:10]
    owner = User(email=f"t213-owner-{suffix}@example.com", display_name="T213 Owner")
    db.add(owner)
    db.flush()
    company = Company(
        legal_name=f"T213 Co {suffix}",
        slug=f"t213-co-{suffix}",
        owner_id=owner.id,
        email=f"t213-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


class DummyPrincipal:
    def __init__(self, platform_administrator_id: uuid.UUID) -> None:
        self.platform_administrator_id = platform_administrator_id
        self.session_id = uuid.uuid4()
        self.user_id = uuid.uuid4()


class TestPermissionReadMemoisedPerRequest:
    def test_two_permission_checks_in_one_request_read_effective_permissions_once(
        self, db_session: Session
    ) -> None:
        administrator = _make_administrator_with_permissions(
            db_session, {"platform.dashboard.view", "platform.audit.read"}
        )
        principal = DummyPrincipal(administrator.id)
        request = _fake_request()

        dep_dashboard = require_platform_permission("platform.dashboard.view")
        dep_audit = require_platform_permission("platform.audit.read")

        with patch.object(
            PlatformRbacRepository,
            "get_effective_permissions",
            wraps=PlatformRbacRepository.get_effective_permissions,
            autospec=True,
        ) as spy:
            dep_dashboard(request=request, principal=principal, db=db_session)
            dep_audit(request=request, principal=principal, db=db_session)

            assert spy.call_count == 1, (
                "Two require_platform_permission() checks for the same "
                "administrator within one request must read "
                "get_effective_permissions() only once."
            )

    def test_a_second_request_gets_its_own_independent_read_not_a_stale_cache(
        self, db_session: Session
    ) -> None:
        administrator = _make_administrator_with_permissions(
            db_session, {"platform.dashboard.view"}
        )
        principal = DummyPrincipal(administrator.id)
        dep = require_platform_permission("platform.dashboard.view")

        with patch.object(
            PlatformRbacRepository,
            "get_effective_permissions",
            wraps=PlatformRbacRepository.get_effective_permissions,
            autospec=True,
        ) as spy:
            dep(request=_fake_request(), principal=principal, db=db_session)
            dep(request=_fake_request(), principal=principal, db=db_session)

            assert spy.call_count == 2, (
                "Each new Request (request.state) must get its own fresh "
                "read — this is a per-request cache, never a process-"
                "level one."
            )


class TestEntitlementReadMemoisedPerRequest:
    def test_two_entitlement_checks_for_the_same_capability_read_once_per_request(
        self, db_session: Session
    ) -> None:
        company = _make_company(db_session)
        request = _fake_request()
        dep = require_capability_entitled("crm")

        from modules.platform_admin.services.entitlement_service import (
            PlatformEntitlementService,
        )

        with patch.object(
            PlatformEntitlementService,
            "resolve_effective_entitlement",
            wraps=PlatformEntitlementService.resolve_effective_entitlement,
            autospec=True,
        ) as spy:
            _call_entitlement_dep_ignoring_denial(
                dep, request=request, company_id=company.id, db=db_session
            )
            _call_entitlement_dep_ignoring_denial(
                dep, request=request, company_id=company.id, db=db_session
            )

            assert spy.call_count == 1

    def test_different_capability_keys_are_not_conflated_in_the_same_request(
        self, db_session: Session
    ) -> None:
        company = _make_company(db_session)
        request = _fake_request()
        dep_crm = require_capability_entitled("crm")
        dep_inventory = require_capability_entitled("inventory")

        from modules.platform_admin.services.entitlement_service import (
            PlatformEntitlementService,
        )

        with patch.object(
            PlatformEntitlementService,
            "resolve_effective_entitlement",
            wraps=PlatformEntitlementService.resolve_effective_entitlement,
            autospec=True,
        ) as spy:
            _call_entitlement_dep_ignoring_denial(
                dep_crm, request=request, company_id=company.id, db=db_session
            )
            _call_entitlement_dep_ignoring_denial(
                dep_inventory, request=request, company_id=company.id, db=db_session
            )

            assert spy.call_count == 2, (
                "Distinct capability keys must each be resolved once, "
                "never conflated under one cache key."
            )
