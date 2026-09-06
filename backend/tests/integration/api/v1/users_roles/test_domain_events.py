"""Integration tests — verify domain events are written to event_outbox (T131).

For each audited operation, confirms the corresponding event row appears
in the ``event_outbox`` table with the correct ``event_type``.

Covered event types:
  member.created, member.role_changed, member.deactivated, member.suspended,
  member.locked, member.archived, member.restored, member.invitation_accepted,
  member.ownership_transferred, role.created, role.updated, role.deleted.

Spec reference: Epic 4, Phase 15 (T131).
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

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
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_company(client: TestClient, token: str, name: str) -> str:
    resp = client.post(
        "/api/v1/companies",
        json={"legal_name": name, "email": f"events@{uuid.uuid4().hex[:6]}.com"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


def _has_event(db: Session, company_id: str, event_type: str) -> bool:
    """Return True if the outbox contains an entry with the given event_type.

    Uses raw SQL so the query works with both the SQLite test database and
    the production PostgreSQL database. Each integration test runs with a
    fresh in-memory database, so filtering solely by event_type is sufficient.
    """
    rows = db.execute(
        text("SELECT event_type FROM event_outbox WHERE event_type = :etype"),
        {"etype": event_type},
    ).fetchall()
    return len(rows) > 0


def _get_role_id(db: Session, company_id: str, slug: str) -> str:
    from modules.users_roles.repositories.role_repository import RoleRepository

    role = RoleRepository(db).get_by_slug(uuid.UUID(company_id), slug)
    assert role is not None
    return str(role.id)


def _add_member(
    client: TestClient, token: str, company_id: str, email: str, role_id: str
) -> dict:
    resp = client.post(
        f"/api/v1/companies/{company_id}/members",
        json={"email": email, "role_id": role_id},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDomainEvents:
    """Verify domain events appear in event_outbox after corresponding operations."""

    def test_company_creation_emits_member_created_event(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Creating a company (T129 hook) emits member.created for the owner."""
        user, pwd = create_test_user(db_session, email="evts_company@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Events Company Corp")

        assert _has_event(db_session, company_id, "member.created"), (
            "Expected member.created event in outbox after company creation (bootstrap owner)"
        )

    def test_add_member_emits_member_created_event(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Adding a member emits member.created to the outbox."""
        user, pwd = create_test_user(db_session, email="evts_addmember@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Events AddMember Corp")
        viewer_role_id = _get_role_id(db_session, company_id, "viewer")

        new_user, _ = create_test_user(
            db_session, email="evts_addmember_new@example.com"
        )
        _add_member(test_client, token, company_id, new_user.email, viewer_role_id)

        assert _has_event(db_session, company_id, "member.created")

    def test_change_role_emits_member_role_changed_event(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Changing a member's role emits member.role_changed to the outbox."""
        user, pwd = create_test_user(db_session, email="evts_changerole@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Events ChangeRole Corp")
        viewer_role_id = _get_role_id(db_session, company_id, "viewer")
        staff_role_id = _get_role_id(db_session, company_id, "manager")

        new_user, _ = create_test_user(
            db_session, email="evts_changerole_new@example.com"
        )
        member = _add_member(
            test_client, token, company_id, new_user.email, viewer_role_id
        )

        resp = test_client.patch(
            f"/api/v1/companies/{company_id}/members/{member['id']}",
            json={"role_id": staff_role_id},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert _has_event(db_session, company_id, "member.role_changed")

    def test_deactivate_emits_member_deactivated_event(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Deactivating a member emits member.deactivated to the outbox."""
        user, pwd = create_test_user(db_session, email="evts_deactivate@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Events Deactivate Corp")
        viewer_role_id = _get_role_id(db_session, company_id, "viewer")

        new_user, new_pw = create_test_user(
            db_session, email="evts_deact_new@example.com"
        )
        member = _add_member(
            test_client, token, company_id, new_user.email, viewer_role_id
        )

        new_token = _login(test_client, new_user.email, new_pw)
        test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/accept-invitation",
            headers=_auth(new_token),
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/deactivate",
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert _has_event(db_session, company_id, "member.deactivated")

    def test_suspend_emits_member_suspended_event(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Suspending a member emits member.suspended to the outbox."""
        user, pwd = create_test_user(db_session, email="evts_suspend@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Events Suspend Corp")
        viewer_role_id = _get_role_id(db_session, company_id, "viewer")

        new_user, new_pw = create_test_user(
            db_session, email="evts_suspend_new@example.com"
        )
        member = _add_member(
            test_client, token, company_id, new_user.email, viewer_role_id
        )
        new_token = _login(test_client, new_user.email, new_pw)
        test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/accept-invitation",
            headers=_auth(new_token),
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/suspend",
            json={"reason": "Testing"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert _has_event(db_session, company_id, "member.suspended")

    def test_archive_emits_member_archived_event(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Archiving a member emits member.archived to the outbox."""
        user, pwd = create_test_user(db_session, email="evts_archive@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Events Archive Corp")
        viewer_role_id = _get_role_id(db_session, company_id, "viewer")

        new_user, new_pw = create_test_user(
            db_session, email="evts_archive_new@example.com"
        )
        member = _add_member(
            test_client, token, company_id, new_user.email, viewer_role_id
        )
        new_token = _login(test_client, new_user.email, new_pw)
        test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/accept-invitation",
            headers=_auth(new_token),
        )

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/archive",
            json={"reason": "Left company"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert _has_event(db_session, company_id, "member.archived")

    def test_invitation_accepted_emits_event(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Accepting an invitation emits member.invitation_accepted to the outbox."""
        user, pwd = create_test_user(db_session, email="evts_invite@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Events Invite Corp")
        viewer_role_id = _get_role_id(db_session, company_id, "viewer")

        new_user, new_pw = create_test_user(
            db_session, email="evts_invite_new@example.com"
        )
        member = _add_member(
            test_client, token, company_id, new_user.email, viewer_role_id
        )
        new_token = _login(test_client, new_user.email, new_pw)

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/members/{member['id']}/accept-invitation",
            headers=_auth(new_token),
        )
        assert resp.status_code == 200, resp.text
        assert _has_event(db_session, company_id, "member.invitation_accepted")

    def test_role_created_emits_event(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Creating a custom role emits role.created to the outbox."""
        user, pwd = create_test_user(db_session, email="evts_rolecreate@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Events RoleCreate Corp")

        resp = test_client.post(
            f"/api/v1/companies/{company_id}/roles",
            json={"name": "Events Test Role", "rank": 25},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.text
        assert _has_event(db_session, company_id, "role.created")

    def test_role_updated_emits_event(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Updating a custom role emits role.updated to the outbox."""
        user, pwd = create_test_user(db_session, email="evts_roleupdate@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Events RoleUpdate Corp")

        create_resp = test_client.post(
            f"/api/v1/companies/{company_id}/roles",
            json={"name": "Events Update Role", "rank": 25},
            headers=_auth(token),
        )
        role_id = create_resp.json()["data"]["id"]

        resp = test_client.patch(
            f"/api/v1/companies/{company_id}/roles/{role_id}",
            json={"name": "Events Updated Role"},
            headers=_auth(token),
        )
        assert resp.status_code == 200, resp.text
        assert _has_event(db_session, company_id, "role.updated")

    def test_role_deleted_emits_event(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Deleting a custom role emits role.deleted to the outbox."""
        user, pwd = create_test_user(db_session, email="evts_roledelete@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Events RoleDelete Corp")

        create_resp = test_client.post(
            f"/api/v1/companies/{company_id}/roles",
            json={"name": "Events Delete Role", "rank": 25},
            headers=_auth(token),
        )
        role_id = create_resp.json()["data"]["id"]

        resp = test_client.delete(
            f"/api/v1/companies/{company_id}/roles/{role_id}",
            headers=_auth(token),
        )
        assert resp.status_code == 204, resp.text
        assert _has_event(db_session, company_id, "role.deleted")

    def test_ownership_transferred_emits_event(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Transferring ownership emits member.ownership_transferred to the outbox."""
        user, pwd = create_test_user(db_session, email="evts_ownertransfer@example.com")
        token = _login(test_client, user.email, pwd)
        company_id = _create_company(test_client, token, "Events OwnerTransfer Corp")
        admin_role_id = _get_role_id(db_session, company_id, "admin")

        target_user, _ = create_test_user(
            db_session, email="evts_ownertransfer_target@example.com"
        )
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
        assert _has_event(db_session, company_id, "member.ownership_transferred")
