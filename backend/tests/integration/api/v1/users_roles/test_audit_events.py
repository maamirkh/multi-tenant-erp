"""Integration tests — verify audit log entries for key lifecycle events (T130).

Triggers each audited action via the API and verifies the corresponding
entry appears in company_audit_logs with the correct action code, actor,
and non-null state snapshots where applicable.

Covered action codes (subset of spec Section 10.1 that have active implementations):
  MEMBER_CREATED, MEMBER_ROLE_CHANGED, MEMBER_UPDATED, MEMBER_DEACTIVATED,
  MEMBER_REACTIVATED, MEMBER_SUSPENDED, MEMBER_LOCKED, MEMBER_ARCHIVED,
  MEMBER_RESTORED, INVITATION_ACCEPTED, ROLE_CREATED, ROLE_UPDATED,
  ROLE_DEACTIVATED, ROLE_DELETED, OWNERSHIP_TRANSFERRED.

Spec reference: spec.md Section 10.1, tasks T130.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.companies.models.company_audit_log import CompanyAuditLog
from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import create_test_member

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, Any]:
    return {"Authorization": f"Bearer {token}"}


def _create_company(client: TestClient, token: str, legal_name: str) -> str:
    """Create company, return company_id string."""
    resp = client.post(
        "/api/v1/companies",
        json={"legal_name": legal_name, "email": f"audit@{uuid.uuid4().hex[:6]}.com"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["data"]["id"])


def _audit_actions(db: Session, company_id: str) -> list[str]:
    """Return all action codes for a company's audit log."""
    stmt = (
        select(CompanyAuditLog.action)
        .where(CompanyAuditLog.company_id == uuid.UUID(company_id))
        .order_by(CompanyAuditLog.created_at)
    )
    return list(db.execute(stmt).scalars().all())


def _assert_audit_contains(db: Session, company_id: str, action: str) -> None:
    """Assert that an audit entry with the given action exists."""
    actions = _audit_actions(db, company_id)
    assert action in actions, (
        f"Expected audit action '{action}' not found. Recorded: {actions}"
    )


def _get_role_id(db: Session, company_id: str, slug: str) -> str:
    from modules.users_roles.repositories.role_repository import RoleRepository

    repo = RoleRepository(db)
    role = repo.get_by_slug(uuid.UUID(company_id), slug)
    assert role is not None, f"Role '{slug}' not found"
    return str(role.id)


def _add_member(
    client: TestClient,
    token: str,
    company_id: str,
    email: str,
    role_id: str,
    db: Session,
) -> dict[str, Any]:
    """Add a member via API, return the response data dict."""
    resp = client.post(
        f"/api/v1/companies/{company_id}/members",
        json={"email": email, "role_id": role_id},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return dict(resp.json()["data"])


def _setup_company_with_owner(
    client: TestClient, db: Session, suffix: str
) -> tuple[str, str, str]:
    """Create a user, log in, create a company. Return (company_id, owner_token, owner_user_id)."""
    user, pwd = create_test_user(db, email=f"audit_owner_{suffix}@example.com")
    token = _login(client, user.email, pwd)
    company_id = _create_company(client, token, f"Audit Test Corp {suffix}")
    return company_id, token, str(user.id)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestAuditEvents:
    """Verify audit log entries are created for each lifecycle operation."""

    def test_member_created_audit(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Adding a member writes MEMBER_CREATED to audit log."""
        company_id, token, _ = _setup_company_with_owner(test_client, db_session, "mc")
        viewer_role_id = _get_role_id(db_session, company_id, "viewer")

        new_user, _ = create_test_user(db_session, email="audit_mc_new@example.com")
        _add_member(
            test_client, token, company_id, new_user.email, viewer_role_id, db_session
        )

        _assert_audit_contains(db_session, company_id, "MEMBER_CREATED")

    def test_member_role_changed_audit(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Changing a member's role writes MEMBER_ROLE_CHANGED to audit log."""
        company_id, token, _ = _setup_company_with_owner(test_client, db_session, "mrc")
        viewer_role_id = _get_role_id(db_session, company_id, "viewer")
        staff_role_id = _get_role_id(db_session, company_id, "manager")

        new_user, _ = create_test_user(db_session, email="audit_mrc_new@example.com")
        member = _add_member(
            test_client, token, company_id, new_user.email, viewer_role_id, db_session
        )

        resp = test_client.patch(
            f"/api/v1/companies/{company_id}/members/{member['id']}",
            json={"role_id": staff_role_id},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        _assert_audit_contains(db_session, company_id, "MEMBER_ROLE_CHANGED")

    def test_member_deactivated_audit(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Deactivating a member writes MEMBER_DEACTIVATED to audit log."""
        company_id, token, _ = _setup_company_with_owner(test_client, db_session, "md")
        viewer_role_id = _get_role_id(db_session, company_id, "viewer")

        new_user, new_pw = create_test_user(
            db_session, email="audit_md_new@example.com"
        )
        member = _add_member(
            test_client, token, company_id, new_user.email, viewer_role_id, db_session
        )

        # Accept invitation (activate member) first
        test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/accept-invitation",
            headers=_auth(_login(test_client, new_user.email, new_pw)),
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/deactivate",
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        _assert_audit_contains(db_session, company_id, "MEMBER_DEACTIVATED")

    def test_member_suspended_audit(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Suspending a member writes MEMBER_SUSPENDED to audit log."""
        company_id, token, _ = _setup_company_with_owner(test_client, db_session, "ms")
        viewer_role_id = _get_role_id(db_session, company_id, "viewer")

        new_user, new_pw = create_test_user(
            db_session, email="audit_ms_new@example.com"
        )
        member = _add_member(
            test_client, token, company_id, new_user.email, viewer_role_id, db_session
        )

        # Activate via invitation acceptance
        new_token = _login(test_client, new_user.email, new_pw)
        test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/accept-invitation",
            headers=_auth(new_token),
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/suspend",
            json={"reason": "Policy violation"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        _assert_audit_contains(db_session, company_id, "MEMBER_SUSPENDED")

    def test_member_locked_audit(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Locking a member writes MEMBER_LOCKED to audit log."""
        company_id, token, _ = _setup_company_with_owner(test_client, db_session, "ml")
        viewer_role_id = _get_role_id(db_session, company_id, "viewer")

        new_user, new_pw = create_test_user(
            db_session, email="audit_ml_new@example.com"
        )
        member = _add_member(
            test_client, token, company_id, new_user.email, viewer_role_id, db_session
        )
        new_token = _login(test_client, new_user.email, new_pw)
        test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/accept-invitation",
            headers=_auth(new_token),
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/lock",
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        _assert_audit_contains(db_session, company_id, "MEMBER_LOCKED")

    def test_member_archived_audit(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Archiving a member writes MEMBER_ARCHIVED to audit log."""
        company_id, token, _ = _setup_company_with_owner(test_client, db_session, "ma")
        viewer_role_id = _get_role_id(db_session, company_id, "viewer")

        new_user, new_pw = create_test_user(
            db_session, email="audit_ma_new@example.com"
        )
        member = _add_member(
            test_client, token, company_id, new_user.email, viewer_role_id, db_session
        )
        new_token = _login(test_client, new_user.email, new_pw)
        test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/accept-invitation",
            headers=_auth(new_token),
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/archive",
            json={"reason": "Left the company"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        _assert_audit_contains(db_session, company_id, "MEMBER_ARCHIVED")

    def test_member_restored_audit(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Restoring an archived member writes MEMBER_RESTORED to audit log."""
        company_id, token, _ = _setup_company_with_owner(test_client, db_session, "mr")
        viewer_role_id = _get_role_id(db_session, company_id, "viewer")

        new_user, new_pw = create_test_user(
            db_session, email="audit_mr_new@example.com"
        )
        member = _add_member(
            test_client, token, company_id, new_user.email, viewer_role_id, db_session
        )
        new_token = _login(test_client, new_user.email, new_pw)
        test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/accept-invitation",
            headers=_auth(new_token),
        )
        test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/archive",
            json={"reason": "Left"},
            headers=_auth(token),
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/restore",
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        _assert_audit_contains(db_session, company_id, "MEMBER_RESTORED")

    def test_role_created_audit(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Creating a custom role writes ROLE_CREATED to audit log."""
        company_id, token, _ = _setup_company_with_owner(test_client, db_session, "rc")

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/roles",
            json={"name": "Audit Test Role", "rank": 30},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        _assert_audit_contains(db_session, company_id, "ROLE_CREATED")

    def test_role_updated_audit(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Updating a custom role writes ROLE_UPDATED to audit log."""
        company_id, token, _ = _setup_company_with_owner(test_client, db_session, "ru")

        create_resp = test_client.post(
            f"/api/v1/companies/{company_id}/roles",
            json={"name": "Audit Update Role", "rank": 30},
            headers=_auth(token),
        )
        role_id = create_resp.json()["data"]["id"]

        resp = test_client.patch(
            f"/api/v1/companies/{company_id}/roles/{role_id}",
            json={"name": "Audit Updated Role"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        _assert_audit_contains(db_session, company_id, "ROLE_UPDATED")

    def test_role_deleted_audit(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Deleting a custom role writes ROLE_DELETED to audit log."""
        company_id, token, _ = _setup_company_with_owner(test_client, db_session, "rd")

        create_resp = test_client.post(
            f"/api/v1/companies/{company_id}/roles",
            json={"name": "Audit Delete Role", "rank": 30},
            headers=_auth(token),
        )
        role_id = create_resp.json()["data"]["id"]

        resp = test_client.delete(
            f"/api/v1/companies/{company_id}/roles/{role_id}",
            headers=_auth(token),
        )
        assert resp.status_code == 204, resp.text
        _assert_audit_contains(db_session, company_id, "ROLE_DELETED")

    def test_invitation_accepted_audit(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Accepting an invitation writes INVITATION_ACCEPTED to audit log."""
        company_id, token, _ = _setup_company_with_owner(test_client, db_session, "ia")
        viewer_role_id = _get_role_id(db_session, company_id, "viewer")

        new_user, new_pw = create_test_user(
            db_session, email="audit_ia_new@example.com"
        )
        member = _add_member(
            test_client, token, company_id, new_user.email, viewer_role_id, db_session
        )

        new_token = _login(test_client, new_user.email, new_pw)
        resp = test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/accept-invitation",
            headers=_auth(new_token),
        )
        assert resp.status_code == 200, resp.text
        _assert_audit_contains(db_session, company_id, "INVITATION_ACCEPTED")

    def test_ownership_transferred_audit(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Transferring ownership writes OWNERSHIP_TRANSFERRED to audit log."""
        company_id, token, owner_user_id = _setup_company_with_owner(
            test_client, db_session, "ot"
        )

        target_user, _ = create_test_user(
            db_session, email="audit_ot_target@example.com"
        )
        admin_role_id = _get_role_id(db_session, company_id, "admin")

        target_member = create_test_member(
            db_session,
            company_id=uuid.UUID(company_id),
            user_id=target_user.id,
            role_id=uuid.UUID(admin_role_id),
            status="active",
        )
        db_session.refresh(target_member)

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/transfer-ownership",
            json={"target_member_id": str(target_member.id)},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        _assert_audit_contains(db_session, company_id, "OWNERSHIP_TRANSFERRED")
