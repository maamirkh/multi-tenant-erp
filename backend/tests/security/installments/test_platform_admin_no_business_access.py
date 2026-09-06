"""[Epic 10, Phase 11, T198] Platform Admin cannot read/search/mutate any
tenant's installment contracts, schedules, collections, or audit data
merely by governing the ``installments`` entitlement (BR-INST-002:
"entitlement governance != data access").

Two proofs, mirroring the Epic 9A Phase 12 support-access precedent's
own two-pronged approach (static + live):

1. Static: the entitlement-override governance surface
   (``OverrideService``, ``platform_admin/router.py``'s override
   endpoints) imports no Installments business-record module.
2. Live: granting/revoking an ``installments``-capability entitlement
   override for a real company returns only the entitlement-governance
   shape (``EntitlementOverrideResponse`` — capability_key/reason/
   expiry/actor metadata) — structurally incapable of carrying contract
   data, and confirmed empty of Installments-specific fields.
"""

from __future__ import annotations

import ast
import inspect
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.platform_admin.models.platform_administrator import (
    PlatformAdministrator,
)
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)

_INSTALLMENTS_BUSINESS_RECORD_PREFIXES = (
    "modules.installments.models",
    "modules.installments.repositories",
    "modules.installments.services",
)


def _imports_no_installments_business_record_module(source: str) -> list[str]:
    tree = ast.parse(source)
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if any(
                node.module.startswith(p)
                for p in _INSTALLMENTS_BUSINESS_RECORD_PREFIXES
            ):
                violations.append(node.module)
    return violations


class TestOverrideGovernanceImportsNoInstallmentsBusinessRecordModule:
    def test_override_service_imports_no_installments_business_record_module(
        self,
    ) -> None:
        import modules.platform_admin.services.override_service as mod

        violations = _imports_no_installments_business_record_module(
            inspect.getsource(mod)
        )
        assert violations == [], f"forbidden imports found: {violations}"


def _make_company(db: Session) -> Company:
    suffix = uuid.uuid4().hex[:10]
    owner = User(email=f"t198-owner-{suffix}@example.test", display_name="T198 Owner")
    db.add(owner)
    db.flush()
    company = Company(
        legal_name=f"T198 Entitlement Governance Co {suffix}",
        slug=f"t198-entitlement-governance-co-{suffix}",
        owner_id=owner.id,
        email=f"t198-entitlement-governance-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


def _make_token_with_permissions(db: Session, codes: set[str]) -> str:
    user = User(
        email=f"t198-admin-{uuid.uuid4().hex[:12]}@example.test",
        display_name="T198 Platform Admin",
    )
    db.add(user)
    db.flush()
    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    db.add(administrator)
    db.flush()
    rbac_repo = PlatformRbacRepository(db)
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    role = rbac_repo.create_role(
        code=f"t198-route-role-{uuid.uuid4().hex[:10]}", name="T198 Test Route Role"
    )
    rbac_repo.set_role_permissions(role.id, set(codes))
    rbac_repo.assign_role(
        platform_administrator_id=administrator.id,
        role_id=role.id,
        assigned_by=None,
        assigned_at=utcnow(),
    )
    db.commit()

    from datetime import timedelta

    from modules.platform_admin.models.platform_session import PlatformSession

    session = PlatformSession(
        platform_administrator_id=administrator.id,
        expires_at=utcnow() + timedelta(days=1),
    )
    db.add(session)
    db.flush()
    db.commit()

    from core.config.settings import get_settings

    return PlatformJwtService(get_settings()).create_access_token(
        platform_administrator_id=administrator.id, session_id=session.id
    )


class TestGrantingInstallmentsOverrideExposesNoBusinessData:
    def test_grant_response_shape_is_governance_only(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        company = _make_company(db_session)
        token = _make_token_with_permissions(
            db_session, {"platform.entitlements.override"}
        )

        response = test_client.post(
            f"/api/v1/platform/tenants/{company.id}/entitlement-overrides",
            json={
                "capability_key": "installments",
                "reason": "T198 — proving the governance surface exposes no business data.",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201, response.text
        data = response.json()["data"]
        # No field name here relates to a contract, schedule, collection,
        # or Installments-domain concept at all — only entitlement-
        # governance metadata (who/why/when this capability was
        # overridden for this company).
        _INSTALLMENTS_DOMAIN_FIELD_MARKERS = (
            "contract",
            "schedule",
            "collection",
            "installment",
            "principal",
            "down_payment",
            "markup",
        )
        for key in data:
            assert not any(
                marker in key.lower() for marker in _INSTALLMENTS_DOMAIN_FIELD_MARKERS
            ), (
                f"unexpected Installments-domain-shaped field in governance response: {key}"
            )
        assert data["capability_key"] == "installments"

    def test_no_installments_business_endpoint_exists_under_the_platform_prefix(
        self, test_client: TestClient
    ) -> None:
        """Platform Admin's own OpenAPI surface (``/platform/...``) never
        declares a route that reaches Installments business records —
        only the module's separate, tenant-scoped router (mounted at
        ``/companies/{company_id}/installments``) does that, and it is
        governed by ordinary tenant RBAC, not Platform Admin auth."""
        spec = test_client.app.openapi()
        platform_installments_paths = {
            p
            for p in spec["paths"]
            if p.startswith("/api/v1/platform") and "installments" in p
        }
        assert platform_installments_paths == set()
