"""[Epic 10, Phase 13 closure] Real, live-ASGI-request regression coverage
for ``PUT /config``'s full-replace semantics.

Confirmed defect (Phase-13 verification): ``frontend/src/app/(protected)/
(installments)/installments/configuration/page.tsx`` has no form controls
for the five policy-object fields (``late_charge_policy``,
``early_settlement_policy``, ``cancellation_policy``, ``default_policy``,
``eligibility_rules``). Before the fix, its save handler omitted them from
the request body; since ``upsert_installment_configuration`` does
``body.model_dump(exclude={"branch_id"})`` (every field, not
``exclude_unset``) and ``upsert_config()`` blindly ``setattr``s every key
onto the existing row, an ordinary save silently nulled out any
previously-configured policy data.

The chosen fix keeps ``PUT /config``'s existing full-replace contract
unchanged (no backend semantic change) and instead makes the frontend
round-trip whatever it last read from ``GET /config`` for those five
fields. This test proves the contract those two facts together are
supposed to guarantee: sending back the exact shape the frontend now
sends (edited scalar fields + round-tripped policy fields) leaves the
policy fields byte/structurally equivalent and only the edited field
changes — using the real endpoint, real Postgres, no mocks.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.companies.models.company import Company
from modules.installments.repositories.feature_flag import (
    InstallmentsFeatureFlagRepository,
)
from modules.installments.services.feature_flag_service import (
    INSTALLMENTS_ENABLED_FLAG_KEY,
)
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.enums import MembershipStatus
from modules.users_roles.models.permission import Permission
from modules.users_roles.models.role import Role
from modules.users_roles.models.role_permission import RolePermission
from tests.fixtures.auth_fixtures import create_test_user

_INSTALLMENTS_PREFIX = "/api/v1/companies/{company_id}/installments"
_PERMISSION_CODE = "installments.config.manage"


def _enable_installments(db: Session, *, company_id: uuid.UUID) -> None:
    """A freshly-created test Company has no active Subscription, so
    ``PlatformEntitlementService.resolve_effective_entitlement()`` defers
    entirely to this per-company tenant toggle (no Plan ceiling to
    consult) — no platform-plan/capability-rollout scaffolding needed
    just to exercise the entitled path of a single endpoint."""
    InstallmentsFeatureFlagRepository(db).upsert(
        company_id=company_id,
        flag_key=INSTALLMENTS_ENABLED_FLAG_KEY,
        is_enabled=True,
    )
    db.commit()


def _make_company(db: Session) -> Company:
    suffix = uuid.uuid4().hex[:10]
    owner = User(email=f"config-owner-{suffix}@example.test", display_name="Owner")
    db.add(owner)
    db.flush()
    company = Company(
        id=uuid.uuid4(),
        legal_name=f"Config Co {suffix}",
        slug=f"config-co-{suffix}",
        owner_id=owner.id,
        email=f"config-co-{suffix}@example.com",
        status="active",
    )
    db.add(company)
    db.flush()
    db.commit()
    return company


def _login_with_config_permission(
    test_client: TestClient, db: Session, *, company_id: uuid.UUID
) -> str:
    suffix = uuid.uuid4().hex[:10]
    email = f"config-user-{suffix}@example.com"
    password = "ConfigUser@1234"
    create_test_user(db, email=email, password=password)
    db.commit()
    user_row = db.query(User).filter_by(email=email).one()

    if db.get(Permission, _PERMISSION_CODE) is None:
        db.add(
            Permission(
                id=_PERMISSION_CODE,
                code=_PERMISSION_CODE,
                label=_PERMISSION_CODE,
                module="installments",
                action="manage",
            )
        )
        db.flush()
    role = Role(
        company_id=company_id,
        name=f"Config Role {suffix}",
        slug=f"config-role-{suffix}",
        rank=50,
        is_system=False,
        is_active=True,
    )
    db.add(role)
    db.flush()
    db.add(RolePermission(role_id=role.id, permission_id=_PERMISSION_CODE))
    db.add(
        CompanyMember(
            company_id=company_id,
            user_id=user_row.id,
            role_id=role.id,
            status=MembershipStatus.active.value,
        )
    )
    db.commit()

    response = test_client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return str(response.json()["data"]["access_token"])


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


_SEEDED_POLICIES = {
    "late_charge_policy": {"enabled": True, "charge_type": "FIXED", "amount": "25.00"},
    "early_settlement_policy": {"discount_pct": "2.5", "requires_approval": True},
    "cancellation_policy": {"allow_after_activation": False},
    "default_policy": {"grace_days": 15, "auto_writeoff_days": 90},
    "eligibility_rules": {"min_credit_score": 600, "max_dti_pct": "40.0"},
}


class TestConfigurationPutPreservesUntouchedPolicyFields:
    def test_save_with_frontend_shape_preserves_policy_fields_and_applies_edit(
        self, installments_http_client: TestClient, pg_db_session: Session
    ) -> None:
        company = _make_company(pg_db_session)
        _enable_installments(pg_db_session, company_id=company.id)
        token = _login_with_config_permission(
            installments_http_client, pg_db_session, company_id=company.id
        )
        headers = _auth_header(token)
        base_url = _INSTALLMENTS_PREFIX.format(company_id=company.id) + "/config"

        # 1. Seed configuration with non-null values for all five policy
        # fields, via the real PUT endpoint (no direct DB writes) so the
        # seeded state is itself proven reachable through the API.
        seed_body = {
            "allowed_frequencies": ["MONTHLY"],
            "min_term": 1,
            "max_term": 60,
            **_SEEDED_POLICIES,
        }
        seed_response = installments_http_client.put(
            base_url, json=seed_body, headers=headers
        )
        assert seed_response.status_code == 200, seed_response.text
        seeded = seed_response.json()["data"]
        for key, value in _SEEDED_POLICIES.items():
            assert seeded[key] == value

        # 2. Re-read configuration (mirrors the page's GET-on-load), then
        # perform the exact save shape the fixed frontend now sends: edited
        # scalar fields plus the five policy fields round-tripped verbatim
        # from the GET response.
        get_response = installments_http_client.get(base_url, headers=headers)
        assert get_response.status_code == 200, get_response.text
        fetched = get_response.json()["data"]

        save_body = {
            "allowed_frequencies": fetched["allowed_frequencies"],
            "min_term": 5,  # the only field this save actually edits
            "max_term": fetched["max_term"],
            "min_down_payment_pct": fetched["min_down_payment_pct"],
            "min_down_payment_amount": fetched["min_down_payment_amount"],
            "max_financed_amount": fetched["max_financed_amount"],
            "rounding_policy": fetched["rounding_policy"],
            "grace_period_days": fetched["grace_period_days"],
            "late_charge_policy": fetched["late_charge_policy"],
            "early_settlement_policy": fetched["early_settlement_policy"],
            "approval_threshold_amount": fetched["approval_threshold_amount"],
            "backdating_allowed": fetched["backdating_allowed"],
            "backdating_max_days": fetched["backdating_max_days"],
            "cancellation_policy": fetched["cancellation_policy"],
            "default_policy": fetched["default_policy"],
            "writeoff_requires_permission": fetched["writeoff_requires_permission"],
            "cure_enabled": fetched["cure_enabled"],
            "eligibility_rules": fetched["eligibility_rules"],
        }
        save_response = installments_http_client.put(
            base_url, json=save_body, headers=headers
        )
        assert save_response.status_code == 200, save_response.text

        # 3. Re-read configuration once more.
        final_response = installments_http_client.get(base_url, headers=headers)
        assert final_response.status_code == 200, final_response.text
        final = final_response.json()["data"]

        # 4. Every untouched policy field is byte/structurally equivalent
        # to what was seeded — the save did not erase them.
        for key, value in _SEEDED_POLICIES.items():
            assert final[key] == value, f"{key} was altered by an unrelated save"

        # 5. The one field the save actually edited changed correctly.
        assert final["min_term"] == 5
