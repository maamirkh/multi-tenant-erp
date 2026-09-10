"""T074 [US5] — Integration tests for member lifecycle endpoints.

Tests: deactivate, reactivate, suspend, lock, archive, restore —
happy paths, auth guards, rank guards, invalid transitions, and
reason validation.

Endpoints under:
  POST /api/v1/companies/{company_id}/members/{member_id}/deactivate
  POST /api/v1/companies/{company_id}/members/{member_id}/reactivate
  POST /api/v1/companies/{company_id}/members/{member_id}/suspend
  POST /api/v1/companies/{company_id}/members/{member_id}/lock
  POST /api/v1/companies/{company_id}/members/{member_id}/archive
  POST /api/v1/companies/{company_id}/members/{member_id}/restore

Spec reference: tasks T074.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from modules.users_roles.models.enums import MembershipStatus
from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import (
    create_test_member,
    seed_system_roles,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _login(client: TestClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return str(resp.json()["data"]["access_token"])


def _auth(token: str) -> dict[str, Any]:
    return {"Authorization": f"Bearer {token}"}


def _create_company(client: TestClient, token: str) -> dict[str, Any]:
    resp = client.post(
        "/api/v1/companies",
        json={
            "legal_name": f"Lifecycle Co {uuid.uuid4().hex[:6]}",
            "email": f"info@{uuid.uuid4().hex[:8]}.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, f"Company creation failed: {resp.text}"
    return dict(resp.json()["data"])


def _url(company_id: str, member_id: str, action: str) -> str:
    return f"/api/v1/companies/{company_id}/members/{member_id}/{action}"


def _setup(
    client: TestClient,
    db: Session,
    *,
    suffix: str = "",
    target_status: str = MembershipStatus.active.value,
    target_role_slug: str = "viewer",
) -> tuple[str, str, str, str, str]:
    """Set up a company with an active Owner and a target member.

    Returns:
        (company_id, owner_token, target_member_id, target_user_id, viewer_token)
    """
    sfx = suffix or uuid.uuid4().hex[:8]

    # Owner
    owner, owner_pw = create_test_user(db, email=f"owner_{sfx}@example.com")
    owner_token = _login(client, owner.email, owner_pw)
    company = _create_company(client, owner_token)
    company_id = uuid.UUID(company["id"])

    # Seed system roles
    roles = seed_system_roles(db, company_id, owner.id)
    role_map = {r.slug: r for r in roles}

    # Owner membership (active)
    create_test_member(
        db,
        company_id=company_id,
        user_id=owner.id,
        role_id=role_map["owner"].id,
        status=MembershipStatus.active.value,
        created_by=owner.id,
    )

    # Target member
    target_user, target_pw = create_test_user(db, email=f"target_{sfx}@example.com")
    target_token = _login(client, target_user.email, target_pw)
    target_member = create_test_member(
        db,
        company_id=company_id,
        user_id=target_user.id,
        role_id=role_map[target_role_slug].id,
        status=target_status,
        created_by=owner.id,
    )

    return (
        str(company_id),
        owner_token,
        str(target_member.id),
        str(target_user.id),
        target_token,
    )


# ---------------------------------------------------------------------------
# deactivate_member
# ---------------------------------------------------------------------------


class TestDeactivateEndpoint:
    """Integration tests for POST /{member_id}/deactivate."""

    def test_deactivate_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """POST /deactivate without auth returns 401."""
        resp = test_client.post(
            _url(str(uuid.uuid4()), str(uuid.uuid4()), "deactivate")
        )
        assert resp.status_code == 401

    def test_deactivate_non_member_returns_403(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """POST /deactivate by a non-member returns 403."""
        company_id, _, target_id, _, _ = _setup(test_client, db_session, suffix="dm403")
        outsider, outsider_pw = create_test_user(
            db_session, email="outsider_dm403@example.com"
        )
        outsider_token = _login(test_client, outsider.email, outsider_pw)

        resp = test_client.post(
            _url(company_id, target_id, "deactivate"),
            headers=_auth(outsider_token),
        )
        assert resp.status_code == 403

    def test_deactivate_member_success(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Owner can deactivate an active viewer member."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client, db_session, suffix="dm_ok"
        )

        resp = test_client.post(
            _url(company_id, target_id, "deactivate"),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == MembershipStatus.inactive.value

    def test_deactivate_unknown_member_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """POST /deactivate for unknown member returns 404."""
        company_id, owner_token, _, _, _ = _setup(
            test_client, db_session, suffix="dm404"
        )

        resp = test_client.post(
            _url(company_id, str(uuid.uuid4()), "deactivate"),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 404

    def test_deactivate_already_inactive_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """POST /deactivate on already-inactive member returns 409."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client,
            db_session,
            suffix="dm_dup",
            target_status=MembershipStatus.inactive.value,
        )

        resp = test_client.post(
            _url(company_id, target_id, "deactivate"),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 409

    def test_viewer_cannot_deactivate(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A Viewer (rank < 80) is forbidden from calling /deactivate."""
        sfx = uuid.uuid4().hex[:8]
        owner, owner_pw = create_test_user(
            db_session, email=f"owner_{sfx}_rg@example.com"
        )
        owner_token = _login(test_client, owner.email, owner_pw)
        company = _create_company(test_client, owner_token)
        company_id = uuid.UUID(company["id"])

        roles = seed_system_roles(db_session, company_id, owner.id)
        role_map = {r.slug: r for r in roles}

        create_test_member(
            db_session,
            company_id=company_id,
            user_id=owner.id,
            role_id=role_map["owner"].id,
            status=MembershipStatus.active.value,
        )

        # Viewer actor
        actor_user, actor_pw = create_test_user(
            db_session, email=f"actor_{sfx}_rg@example.com"
        )
        actor_token = _login(test_client, actor_user.email, actor_pw)
        create_test_member(
            db_session,
            company_id=company_id,
            user_id=actor_user.id,
            role_id=role_map["viewer"].id,
            status=MembershipStatus.active.value,
        )

        # Viewer target
        target_user, _ = create_test_user(
            db_session, email=f"target_{sfx}_rg@example.com"
        )
        target_member = create_test_member(
            db_session,
            company_id=company_id,
            user_id=target_user.id,
            role_id=role_map["viewer"].id,
            status=MembershipStatus.active.value,
        )

        resp = test_client.post(
            _url(str(company_id), str(target_member.id), "deactivate"),
            headers=_auth(actor_token),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# reactivate_member
# ---------------------------------------------------------------------------


class TestReactivateEndpoint:
    """Integration tests for POST /{member_id}/reactivate."""

    def test_reactivate_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        resp = test_client.post(
            _url(str(uuid.uuid4()), str(uuid.uuid4()), "reactivate")
        )
        assert resp.status_code == 401

    def test_reactivate_inactive_member_success(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Owner can reactivate an inactive member."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client,
            db_session,
            suffix="ra_ok",
            target_status=MembershipStatus.inactive.value,
        )

        resp = test_client.post(
            _url(company_id, target_id, "reactivate"),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == MembershipStatus.active.value

    def test_reactivate_active_member_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Reactivating an active member returns 409 (invalid transition)."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client, db_session, suffix="ra_409"
        )

        resp = test_client.post(
            _url(company_id, target_id, "reactivate"),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 409

    def test_reactivate_suspended_member_success(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Owner can reactivate (unsuspend) a suspended member."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client,
            db_session,
            suffix="ra_sus",
            target_status=MembershipStatus.suspended.value,
        )

        resp = test_client.post(
            _url(company_id, target_id, "reactivate"),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == MembershipStatus.active.value

    def test_reactivate_locked_member_success(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Owner can unlock a locked member."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client,
            db_session,
            suffix="ra_locked",
            target_status=MembershipStatus.locked.value,
        )

        resp = test_client.post(
            _url(company_id, target_id, "reactivate"),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == MembershipStatus.active.value


# ---------------------------------------------------------------------------
# suspend_member
# ---------------------------------------------------------------------------


class TestSuspendEndpoint:
    """Integration tests for POST /{member_id}/suspend."""

    def test_suspend_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        resp = test_client.post(
            _url(str(uuid.uuid4()), str(uuid.uuid4()), "suspend"),
            json={"reason": "test"},
        )
        assert resp.status_code == 401

    def test_suspend_member_success(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Owner can suspend an active member with a reason."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client, db_session, suffix="sus_ok"
        )

        resp = test_client.post(
            _url(company_id, target_id, "suspend"),
            json={"reason": "Policy violation"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == MembershipStatus.suspended.value

    def test_suspend_missing_reason_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """POST /suspend without reason body returns 422."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client, db_session, suffix="sus_422"
        )

        resp = test_client.post(
            _url(company_id, target_id, "suspend"),
            json={},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 422

    def test_suspend_empty_reason_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """POST /suspend with empty reason string returns 422."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client, db_session, suffix="sus_er"
        )

        resp = test_client.post(
            _url(company_id, target_id, "suspend"),
            json={"reason": ""},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 422

    def test_suspend_inactive_member_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Suspending an inactive member returns 409 (invalid transition)."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client,
            db_session,
            suffix="sus_409",
            target_status=MembershipStatus.inactive.value,
        )

        resp = test_client.post(
            _url(company_id, target_id, "suspend"),
            json={"reason": "Should fail"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 409

    def test_viewer_cannot_suspend(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A Viewer (rank < 80) is forbidden from calling /suspend."""
        sfx = uuid.uuid4().hex[:8]
        owner, owner_pw = create_test_user(
            db_session, email=f"owner_{sfx}_sus_rg@example.com"
        )
        owner_token = _login(test_client, owner.email, owner_pw)
        company = _create_company(test_client, owner_token)
        company_id = uuid.UUID(company["id"])

        roles = seed_system_roles(db_session, company_id, owner.id)
        role_map = {r.slug: r for r in roles}
        create_test_member(
            db_session,
            company_id=company_id,
            user_id=owner.id,
            role_id=role_map["owner"].id,
            status=MembershipStatus.active.value,
        )

        actor_user, actor_pw = create_test_user(
            db_session, email=f"actor_{sfx}_sus_rg@example.com"
        )
        actor_token = _login(test_client, actor_user.email, actor_pw)
        create_test_member(
            db_session,
            company_id=company_id,
            user_id=actor_user.id,
            role_id=role_map["viewer"].id,
            status=MembershipStatus.active.value,
        )

        target_user, _ = create_test_user(
            db_session, email=f"target_{sfx}_sus_rg@example.com"
        )
        target_member = create_test_member(
            db_session,
            company_id=company_id,
            user_id=target_user.id,
            role_id=role_map["viewer"].id,
            status=MembershipStatus.active.value,
        )

        resp = test_client.post(
            _url(str(company_id), str(target_member.id), "suspend"),
            json={"reason": "Viewer trying to suspend"},
            headers=_auth(actor_token),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# lock_member
# ---------------------------------------------------------------------------


class TestLockEndpoint:
    """Integration tests for POST /{member_id}/lock."""

    def test_lock_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        resp = test_client.post(_url(str(uuid.uuid4()), str(uuid.uuid4()), "lock"))
        assert resp.status_code == 401

    def test_lock_member_success(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Owner can lock an active member."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client, db_session, suffix="lock_ok"
        )

        resp = test_client.post(
            _url(company_id, target_id, "lock"),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == MembershipStatus.locked.value

    def test_lock_inactive_member_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Locking an inactive member returns 409 (invalid transition)."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client,
            db_session,
            suffix="lock_409",
            target_status=MembershipStatus.inactive.value,
        )

        resp = test_client.post(
            _url(company_id, target_id, "lock"),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 409

    def test_locked_member_can_be_suspended(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A locked member can be suspended (locked → suspended is valid BR-020)."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client,
            db_session,
            suffix="lock_sus",
            target_status=MembershipStatus.locked.value,
        )

        resp = test_client.post(
            _url(company_id, target_id, "suspend"),
            json={"reason": "Security review"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == MembershipStatus.suspended.value


# ---------------------------------------------------------------------------
# archive_member
# ---------------------------------------------------------------------------


class TestArchiveEndpoint:
    """Integration tests for POST /{member_id}/archive."""

    def test_archive_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        resp = test_client.post(
            _url(str(uuid.uuid4()), str(uuid.uuid4()), "archive"),
            json={"reason": "test"},
        )
        assert resp.status_code == 401

    def test_archive_active_member_success(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Owner can archive an active member with a reason."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client, db_session, suffix="arc_ok"
        )

        resp = test_client.post(
            _url(company_id, target_id, "archive"),
            json={"reason": "Employee left company"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == MembershipStatus.archived.value

    def test_archive_missing_reason_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """POST /archive without reason body returns 422."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client, db_session, suffix="arc_422"
        )

        resp = test_client.post(
            _url(company_id, target_id, "archive"),
            json={},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 422

    def test_archive_empty_reason_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """POST /archive with empty reason returns 422."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client, db_session, suffix="arc_er"
        )

        resp = test_client.post(
            _url(company_id, target_id, "archive"),
            json={"reason": ""},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 422

    def test_archive_already_archived_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Archiving an already-archived member returns 409."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client,
            db_session,
            suffix="arc_dup",
            target_status=MembershipStatus.archived.value,
        )

        resp = test_client.post(
            _url(company_id, target_id, "archive"),
            json={"reason": "Already archived"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 409

    def test_archive_inactive_member_success(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Owner can archive an inactive member (inactive → archived is valid)."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client,
            db_session,
            suffix="arc_inact",
            target_status=MembershipStatus.inactive.value,
        )

        resp = test_client.post(
            _url(company_id, target_id, "archive"),
            json={"reason": "Cleanup"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == MembershipStatus.archived.value

    def test_viewer_cannot_archive(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """A Viewer (rank < 80) is forbidden from calling /archive."""
        sfx = uuid.uuid4().hex[:8]
        owner, owner_pw = create_test_user(
            db_session, email=f"owner_{sfx}_arc_rg@example.com"
        )
        owner_token = _login(test_client, owner.email, owner_pw)
        company = _create_company(test_client, owner_token)
        company_id = uuid.UUID(company["id"])

        roles = seed_system_roles(db_session, company_id, owner.id)
        role_map = {r.slug: r for r in roles}
        create_test_member(
            db_session,
            company_id=company_id,
            user_id=owner.id,
            role_id=role_map["owner"].id,
            status=MembershipStatus.active.value,
        )

        actor_user, actor_pw = create_test_user(
            db_session, email=f"actor_{sfx}_arc_rg@example.com"
        )
        actor_token = _login(test_client, actor_user.email, actor_pw)
        create_test_member(
            db_session,
            company_id=company_id,
            user_id=actor_user.id,
            role_id=role_map["viewer"].id,
            status=MembershipStatus.active.value,
        )

        target_user, _ = create_test_user(
            db_session, email=f"target_{sfx}_arc_rg@example.com"
        )
        target_member = create_test_member(
            db_session,
            company_id=company_id,
            user_id=target_user.id,
            role_id=role_map["viewer"].id,
            status=MembershipStatus.active.value,
        )

        resp = test_client.post(
            _url(str(company_id), str(target_member.id), "archive"),
            json={"reason": "Viewer trying to archive"},
            headers=_auth(actor_token),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# restore_member
# ---------------------------------------------------------------------------


class TestRestoreEndpoint:
    """Integration tests for POST /{member_id}/restore."""

    def test_restore_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        resp = test_client.post(_url(str(uuid.uuid4()), str(uuid.uuid4()), "restore"))
        assert resp.status_code == 401

    def test_restore_archived_member_success(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Owner can restore an archived member."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client,
            db_session,
            suffix="res_ok",
            target_status=MembershipStatus.archived.value,
        )

        # Mark the archived member's is_deleted flag (consistent with archive_member service)
        from modules.users_roles.repositories.company_member_repository import (
            CompanyMemberRepository,
        )

        member_repo = CompanyMemberRepository(db_session)
        member = member_repo.get_deleted_by_id(
            member_id=uuid.UUID(target_id), company_id=uuid.UUID(company_id)
        )
        # If not found as deleted, check if it was created as archived without is_deleted
        if member is None:
            from sqlalchemy import select

            from modules.users_roles.models.company_member import CompanyMember

            stmt = select(CompanyMember).where(CompanyMember.id == uuid.UUID(target_id))
            member = db_session.execute(stmt).scalars().one_or_none()
            if member is not None and member.status == MembershipStatus.archived.value:
                member.is_deleted = True
                from core.utils.datetime import utcnow

                member.deleted_at = utcnow()
                db_session.commit()
                db_session.refresh(member)

        resp = test_client.post(
            _url(company_id, target_id, "restore"),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == MembershipStatus.active.value

    def test_restore_active_member_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Restoring an active member returns 409 (active → active is invalid)."""
        company_id, owner_token, target_id, _, _ = _setup(
            test_client, db_session, suffix="res_409"
        )

        resp = test_client.post(
            _url(company_id, target_id, "restore"),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 409

    def test_restore_unknown_member_returns_404(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Restoring an unknown member returns 404."""
        company_id, owner_token, _, _, _ = _setup(
            test_client, db_session, suffix="res_404"
        )

        resp = test_client.post(
            _url(company_id, str(uuid.uuid4()), "restore"),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 404
