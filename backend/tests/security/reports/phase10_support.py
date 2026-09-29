"""Shared fixtures for Epic 11 Phase 10 security matrices (T261–T265).

Domain on/off is driven through the platform's **real** entitlement
mechanism — an active ``Subscription`` whose ``Plan`` capability ceiling
includes or excludes the capability (``PlatformEntitlementService.
resolve_effective_entitlement``) — never by mocking the entitlement
service, so every matrix cell exercises the production gate chain.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.platform_admin.models.plan import Plan
from modules.platform_admin.repositories.plan_repository import PlanRepository
from modules.platform_admin.repositories.subscription_repository import (
    SubscriptionRepository,
)
from tests.integration.api.v1.reports.conftest import (
    auth_header,
    enable_crm_and_installments,
    grant_reports_permissions,
    setup_company_with_user,
)

ALL_CAPABILITIES = (
    "sales",
    "purchase",
    "inventory",
    "accounting",
    "crm",
    "installments",
    "reports",
)


class TenantHarness:
    """One company + its owner, with a mutable Plan ceiling and a mutable
    ``reports.*`` permission set."""

    def __init__(self, db: Session, client: TestClient) -> None:
        self.db = db
        self.client = client
        token, self.company_id, self.user_id = setup_company_with_user(db, client)
        self.headers = auth_header(token)
        enable_crm_and_installments(db, self.company_id)
        plan_repo = PlanRepository(db)
        self.plan: Plan = plan_repo.create(
            code=f"p10-{uuid.uuid4().hex[:10]}",
            name="Phase 10 matrix plan",
            status="published",
        )
        SubscriptionRepository(db).create(
            company_id=self.company_id,
            plan_id=self.plan.id,
            status="active",
            effective_date=date(2026, 1, 1),
            actor_id=self.user_id,
        )
        db.commit()
        self.set_capabilities()

    def set_capabilities(self, **overrides: bool) -> None:
        """All capabilities allowed unless overridden (e.g. ``reports=False``)."""
        capability_map = {key: True for key in ALL_CAPABILITIES}
        capability_map.update(overrides)
        PlanRepository(self.db).set_capabilities(self.plan.id, capability_map)
        self.db.commit()

    def set_permissions(self, codes: set[str]) -> None:
        grant_reports_permissions(self.db, self.company_id, self.user_id, codes)

    def url(self, path: str, company_id: uuid.UUID | None = None) -> str:
        return f"/api/v1/companies/{company_id or self.company_id}/reports{path}"

    def get(
        self, path: str, company_id: uuid.UUID | None = None
    ) -> tuple[int, str | None]:
        """``(status, error_code)`` for a GET — ``error_code`` is ``None``
        on success or when the body isn't the standard error envelope."""
        resp = self.client.get(self.url(path, company_id), headers=self.headers)
        code: str | None = None
        if resp.status_code >= 400 and resp.headers.get("content-type", "").startswith(
            "application/json"
        ):
            code = resp.json().get("error", {}).get("code")
        return resp.status_code, code


# ---------------------------------------------------------------------------
# Platform Admin (T264/T265) — mirrors the established Epic 9A/Epic 10
# precedent (tests/security/installments/test_platform_admin_no_business_access.py)
# ---------------------------------------------------------------------------


def make_platform_admin_token(db: Session, codes: set[str] | None = None) -> str:
    """A real Platform Administrator session token holding *codes*
    (default: every platform permission — the strongest admin)."""
    from datetime import timedelta

    from core.config.settings import get_settings
    from core.utils.datetime import utcnow
    from modules.auth.models.user import User
    from modules.platform_admin.constants import PLATFORM_PERMISSION_CODES
    from modules.platform_admin.models.platform_administrator import (
        PlatformAdministrator,
    )
    from modules.platform_admin.models.platform_session import PlatformSession
    from modules.platform_admin.repositories.platform_rbac_repository import (
        PlatformRbacRepository,
    )
    from modules.platform_admin.services.platform_jwt_service import (
        PlatformJwtService,
    )
    from modules.platform_admin.services.platform_rbac_seed_service import (
        PlatformRbacSeedService,
    )

    granted = codes if codes is not None else set(PLATFORM_PERMISSION_CODES)
    user = User(
        email=f"p10-platform-{uuid.uuid4().hex[:12]}@example.test",
        display_name="P10 Platform Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"p10-role-{uuid.uuid4().hex[:10]}", name="P10 Platform Role"
    )
    rbac_repo.set_role_permissions(role.id, set(granted))
    rbac_repo.assign_role(
        platform_administrator_id=administrator.id,
        role_id=role.id,
        assigned_by=None,
        assigned_at=utcnow(),
    )
    session = PlatformSession(
        platform_administrator_id=administrator.id,
        expires_at=utcnow() + timedelta(days=1),
    )
    db.add(session)
    db.flush()
    db.commit()
    return PlatformJwtService(get_settings()).create_access_token(
        platform_administrator_id=administrator.id, session_id=session.id
    )


def tenant_report_paths(customer_id: uuid.UUID, view_id: str) -> tuple[str, ...]:
    """Every tenant-scoped Reports read surface (relative to /reports)."""
    return (
        "/discovery",
        "/sales.summary",
        "/sales.summary/export?format=csv",
        "/dashboard",
        f"/customer-360/{customer_id}",
        "/saved-views",
        f"/saved-views/{view_id}",
    )


# The one sanctioned governance-only coupling (T006, Expected File Map):
# Platform Admin reads/writes Reports' own module toggle — entitlement
# governance, never report data (same exception BR-INST-002 grants
# Installments/CRM in module_enablement.py).
APPROVED_REPORTS_GOVERNANCE_IMPORTS = frozenset(
    {
        "modules.reports.repositories.feature_flag",
        "modules.reports.services.feature_flag_service",
    }
)


def reports_imports(source: str) -> list[str]:
    import ast

    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "modules.reports" or node.module.startswith(
                "modules.reports."
            ):
                found.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "modules.reports" or alias.name.startswith(
                    "modules.reports."
                ):
                    found.append(alias.name)
    return found
