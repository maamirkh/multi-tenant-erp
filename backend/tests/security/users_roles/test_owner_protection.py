"""T136 [P] — Owner protection security tests.

Verifies the last-Owner protection invariant:
- The last Owner of a company cannot be deactivated.
- The last Owner of a company cannot be suspended.
- The last Owner of a company cannot have their role changed (demotion).
- The last Owner of a company cannot be archived.

HTTP status for last-Owner violations:
- ``LastOwnerProtectionError`` → 409 (business conflict: would leave company
  without an Owner, not a rank/authorization failure).
- ``CannotModifyOwnRoleError`` → 409 (business rule: self-role-change prevented).
- Rank-guard failures for lifecycle endpoints return 403.

When there are multiple Owners, these operations are allowed on non-last Owners
(verified by a positive-path test after a second Owner is promoted).

Spec ref: spec.md BR-045 through BR-049, tasks T136.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import (
    create_test_member,
    seed_system_roles,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_company(client: TestClient, token: str, suffix: str) -> str:
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Owner Protection Corp {suffix}",
            "email": f"ownerprotect_{suffix}@example.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, f"Company creation failed: {resp.text}"
    return resp.json()["data"]["id"]


def _member_url(company_id: str, member_id: str, action: str = "") -> str:
    base = f"/api/v1/companies/{company_id}/members/{member_id}"
    return f"{base}/{action}" if action else base


# ---------------------------------------------------------------------------
# Fixture: company with sole Owner + one Admin
# ---------------------------------------------------------------------------


@pytest.fixture()
def sole_owner_company(test_client: TestClient, db_session: Session):
    """Seed a company where the owner is the SOLE active Owner.

    An admin member is also created so that owner-level operations can be
    attempted from the admin perspective.

    Returns dict with:
        company_id, owner_token, owner_member_id,
        admin_token, admin_member_id, role_ids (slug → str).
    """
    prefix = uuid.uuid4().hex[:8]

    owner_user, owner_pwd = create_test_user(
        db_session, email=f"sole_owner_{prefix}@example.com"
    )
    admin_user, admin_pwd = create_test_user(
        db_session, email=f"op_admin_{prefix}@example.com"
    )

    owner_token = _login(test_client, owner_user.email, owner_pwd)
    admin_token = _login(test_client, admin_user.email, admin_pwd)

    company_id_str = _create_company(test_client, owner_token, prefix)
    company_id = uuid.UUID(company_id_str)

    roles = seed_system_roles(db_session, company_id, owner_user.id)
    role_map = {r.slug: r for r in roles}

    # Bootstrap owner membership created at company creation; update to ensure role
    owner_member = create_test_member(
        db_session,
        company_id=company_id,
        user_id=owner_user.id,
        role_id=role_map["owner"].id,
    )
    admin_member = create_test_member(
        db_session,
        company_id=company_id,
        user_id=admin_user.id,
        role_id=role_map["admin"].id,
    )

    return {
        "company_id": company_id_str,
        "owner_token": owner_token,
        "owner_member_id": str(owner_member.id),
        "admin_token": admin_token,
        "admin_member_id": str(admin_member.id),
        "role_ids": {slug: str(r.id) for slug, r in role_map.items()},
    }


# ---------------------------------------------------------------------------
# Deactivation protection
# ---------------------------------------------------------------------------


class TestLastOwnerCannotBeDeactivated:
    """The last active Owner must not be deactivatable.

    ``LastOwnerProtectionError`` returns 409 to signal a business conflict.
    """

    def test_owner_cannot_deactivate_self_as_last_owner(
        self, test_client: TestClient, sole_owner_company: dict
    ) -> None:
        """Owner (sole) deactivating themselves is blocked — 409."""
        resp = test_client.post(
            _member_url(
                sole_owner_company["company_id"],
                sole_owner_company["owner_member_id"],
                "deactivate",
            ),
            headers=_auth(sole_owner_company["owner_token"]),
        )
        assert resp.status_code == 409

    def test_admin_cannot_deactivate_last_owner(
        self, test_client: TestClient, sole_owner_company: dict
    ) -> None:
        """Admin deactivating the last Owner is blocked — 409."""
        resp = test_client.post(
            _member_url(
                sole_owner_company["company_id"],
                sole_owner_company["owner_member_id"],
                "deactivate",
            ),
            headers=_auth(sole_owner_company["admin_token"]),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Suspension protection
# ---------------------------------------------------------------------------


class TestLastOwnerCannotBeSuspended:
    """The last active Owner must not be suspendable.

    ``LastOwnerProtectionError`` returns 409.
    """

    def test_admin_cannot_suspend_last_owner(
        self, test_client: TestClient, sole_owner_company: dict
    ) -> None:
        """Admin suspending the last Owner is blocked — 409."""
        resp = test_client.post(
            _member_url(
                sole_owner_company["company_id"],
                sole_owner_company["owner_member_id"],
                "suspend",
            ),
            json={"reason": "attempted suspension"},
            headers=_auth(sole_owner_company["admin_token"]),
        )
        assert resp.status_code == 409

    def test_owner_cannot_suspend_self_as_last_owner(
        self, test_client: TestClient, sole_owner_company: dict
    ) -> None:
        """Sole Owner suspending themselves is blocked — 409."""
        resp = test_client.post(
            _member_url(
                sole_owner_company["company_id"],
                sole_owner_company["owner_member_id"],
                "suspend",
            ),
            json={"reason": "self-suspension"},
            headers=_auth(sole_owner_company["owner_token"]),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Demotion protection
# ---------------------------------------------------------------------------


class TestLastOwnerCannotBeDemoted:
    """The last active Owner must not have their role changed (demotion).

    Self-role-change (BR-013) returns 409 via ``CannotModifyOwnRoleError``.
    Last-owner demotion by another actor returns 409 via ``LastOwnerProtectionError``.
    """

    def test_owner_cannot_demote_self_when_sole_owner(
        self, test_client: TestClient, sole_owner_company: dict
    ) -> None:
        """Sole Owner trying to change own role is blocked by BR-013 — 409."""
        resp = test_client.patch(
            _member_url(
                sole_owner_company["company_id"],
                sole_owner_company["owner_member_id"],
            ),
            json={"role_id": sole_owner_company["role_ids"]["admin"]},
            headers=_auth(sole_owner_company["owner_token"]),
        )
        # CannotModifyOwnRoleError fires before LastOwnerProtectionError
        assert resp.status_code == 409

    def test_demotion_allowed_when_second_owner_exists(
        self, test_client: TestClient, db_session: Session, sole_owner_company: dict
    ) -> None:
        """Demoting one of two Owners is permitted (last-owner protection clears).

        A second Owner is seeded directly via the ORM (the PATCH endpoint
        cannot assign the Owner role because actor_rank <= owner_rank is
        enforced; use the ownership transfer endpoint for transfers, or the
        ORM in tests that need two-Owner scenarios).
        """
        import uuid as _uuid

        company_id = _uuid.UUID(sole_owner_company["company_id"])

        # Create a second user and give them an Owner membership directly
        second_owner_user, second_owner_pwd = create_test_user(
            db_session, email=f"second_owner_{_uuid.uuid4().hex[:8]}@example.com"
        )
        owner_role_id = _uuid.UUID(sole_owner_company["role_ids"]["owner"])

        second_owner_member = create_test_member(
            db_session,
            company_id=company_id,
            user_id=second_owner_user.id,
            role_id=owner_role_id,
        )

        second_owner_token = _login(
            test_client, second_owner_user.email, second_owner_pwd
        )

        # Now two Owners exist; original owner can demote the second Owner to Admin
        demote_resp = test_client.patch(
            _member_url(
                sole_owner_company["company_id"],
                str(second_owner_member.id),
            ),
            json={"role_id": sole_owner_company["role_ids"]["admin"]},
            headers=_auth(sole_owner_company["owner_token"]),
        )
        assert demote_resp.status_code == 200, (
            f"Demotion of second Owner should succeed (two Owners exist); "
            f"got {demote_resp.status_code}: {demote_resp.json()}"
        )


# ---------------------------------------------------------------------------
# Archive protection
# ---------------------------------------------------------------------------


class TestLastOwnerCannotBeArchived:
    """The last active Owner must not be archivable.

    ``LastOwnerProtectionError`` returns 409.
    """

    def test_admin_cannot_archive_last_owner(
        self, test_client: TestClient, sole_owner_company: dict
    ) -> None:
        """Admin archiving the last Owner is blocked — 409."""
        resp = test_client.post(
            _member_url(
                sole_owner_company["company_id"],
                sole_owner_company["owner_member_id"],
                "archive",
            ),
            json={"reason": "hostile takeover"},
            headers=_auth(sole_owner_company["admin_token"]),
        )
        assert resp.status_code == 409

    def test_owner_cannot_archive_self_as_last_owner(
        self, test_client: TestClient, sole_owner_company: dict
    ) -> None:
        """Sole Owner archiving themselves is blocked — 409."""
        resp = test_client.post(
            _member_url(
                sole_owner_company["company_id"],
                sole_owner_company["owner_member_id"],
                "archive",
            ),
            json={"reason": "self-archive"},
            headers=_auth(sole_owner_company["owner_token"]),
        )
        assert resp.status_code == 409
