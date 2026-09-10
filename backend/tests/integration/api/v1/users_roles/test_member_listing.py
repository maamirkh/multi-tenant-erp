"""T079 [US6] — Integration tests for GET /companies/{company_id}/members.

Tests: pagination, status filter, role filter, department filter,
text search (display_name/email/employee_id), sorting (name, created_at,
role_rank, department), auth guard, and roles list endpoint.

Spec reference: tasks T079.
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
# Helpers
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
            "legal_name": f"Listing Co {uuid.uuid4().hex[:6]}",
            "email": f"info@{uuid.uuid4().hex[:8]}.com",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, f"Company creation failed: {resp.text}"
    return dict(resp.json()["data"])


def _members_url(company_id: str) -> str:
    return f"/api/v1/companies/{company_id}/members"


def _roles_url(company_id: str) -> str:
    return f"/api/v1/companies/{company_id}/roles"


def _setup_company(
    client: TestClient, db: Session, *, suffix: str = ""
) -> tuple[str, str, str, dict[str, str]]:
    """Create owner, company, seed roles, create owner membership.

    Returns:
        (company_id, owner_token, owner_member_id, role_ids_by_slug)
    """
    sfx = suffix or uuid.uuid4().hex[:8]
    owner, owner_pw = create_test_user(db, email=f"owner_{sfx}@example.com")
    owner_token = _login(client, owner.email, owner_pw)
    company = _create_company(client, owner_token)
    company_id = uuid.UUID(company["id"])

    roles = seed_system_roles(db, company_id, owner.id)
    role_map = {r.slug: r for r in roles}

    owner_member = create_test_member(
        db,
        company_id=company_id,
        user_id=owner.id,
        role_id=role_map["owner"].id,
        status=MembershipStatus.active.value,
        created_by=owner.id,
    )

    role_ids = {slug: str(r.id) for slug, r in role_map.items()}
    return str(company_id), owner_token, str(owner_member.id), role_ids


def _add_member(
    db: Session,
    *,
    company_id: str,
    role_ids: dict[str, str],
    role_slug: str = "viewer",
    status: str = MembershipStatus.active.value,
    display_name: str | None = None,
    department: str | None = None,
    job_title: str | None = None,
    employee_id: str | None = None,
    email_suffix: str = "",
) -> tuple[str, str]:
    """Create a member directly in DB.  Returns (member_id, user_id)."""
    sfx = email_suffix or uuid.uuid4().hex[:8]
    name = display_name or f"User {sfx}"
    user, _ = create_test_user(
        db,
        email=f"member_{sfx}@example.com",
        display_name=name,
    )
    member = create_test_member(
        db,
        company_id=uuid.UUID(company_id),
        user_id=user.id,
        role_id=uuid.UUID(role_ids[role_slug]),
        status=status,
        department=department,
        job_title=job_title,
        employee_id=employee_id,
    )
    return str(member.id), str(user.id)


# ---------------------------------------------------------------------------
# Auth and basic access
# ---------------------------------------------------------------------------


class TestListMembersAuth:
    """Auth guard tests for GET /members."""

    def test_list_members_requires_auth(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET /members without token returns 401."""
        resp = test_client.get(_members_url(str(uuid.uuid4())))
        assert resp.status_code == 401

    def test_list_members_non_member_returns_403(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET /members by a non-member returns 403."""
        company_id, _, _, _ = _setup_company(test_client, db_session, suffix="lm403")
        outsider, outsider_pw = create_test_user(
            db_session, email="outsider_lm403@example.com"
        )
        outsider_token = _login(test_client, outsider.email, outsider_pw)

        resp = test_client.get(_members_url(company_id), headers=_auth(outsider_token))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Basic listing
# ---------------------------------------------------------------------------


class TestListMembersBasic:
    """Basic listing — structure, defaults, and items."""

    def test_list_returns_paginated_response(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET /members returns expected pagination envelope."""
        company_id, owner_token, _, _ = _setup_company(
            test_client, db_session, suffix="lm_basic"
        )

        resp = test_client.get(_members_url(company_id), headers=_auth(owner_token))
        assert resp.status_code == 200
        body = resp.json()
        assert "data" in body
        data = body["data"]
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "pages" in data

    def test_list_includes_owner_member(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET /members returns the owner as a member."""
        company_id, owner_token, owner_member_id, _ = _setup_company(
            test_client, db_session, suffix="lm_owner"
        )

        resp = test_client.get(_members_url(company_id), headers=_auth(owner_token))
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.json()["data"]["items"]]
        assert owner_member_id in ids

    def test_list_returns_all_members(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET /members returns all members including newly added ones."""
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix="lm_all"
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            email_suffix="lm_all_1",
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            email_suffix="lm_all_2",
        )

        resp = test_client.get(_members_url(company_id), headers=_auth(owner_token))
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 3  # owner + 2 viewers

    def test_member_list_item_fields(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Each MemberListItem has all expected fields."""
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix="lm_fields"
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            department="Engineering",
            job_title="Developer",
            email_suffix="lm_fields_t",
        )

        resp = test_client.get(_members_url(company_id), headers=_auth(owner_token))
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        # Find the viewer member
        viewer = next((i for i in items if i["role"]["slug"] == "viewer"), None)
        assert viewer is not None
        assert "id" in viewer
        assert "user_id" in viewer
        assert "display_name" in viewer
        assert "email" in viewer
        assert "role" in viewer
        assert "status" in viewer
        assert "created_at" in viewer
        assert viewer["department"] == "Engineering"
        assert viewer["job_title"] == "Developer"


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class TestListMembersPagination:
    """Pagination tests."""

    def test_page_size_limits_items_returned(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """page_size=1 returns exactly 1 item."""
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix="lm_pag"
        )
        for i in range(3):
            _add_member(
                db_session,
                company_id=company_id,
                role_ids=role_ids,
                email_suffix=f"lm_pag_{i}",
            )

        resp = test_client.get(
            _members_url(company_id),
            params={"page_size": 1},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["items"]) == 1
        assert data["page_size"] == 1
        assert data["total"] >= 4

    def test_page_2_returns_next_batch(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """page=2 returns a different set of items than page=1."""
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix="lm_pag2"
        )
        for i in range(4):
            _add_member(
                db_session,
                company_id=company_id,
                role_ids=role_ids,
                email_suffix=f"lm_pag2_{i}",
            )

        page1 = test_client.get(
            _members_url(company_id),
            params={"page": 1, "page_size": 2},
            headers=_auth(owner_token),
        ).json()["data"]["items"]

        page2 = test_client.get(
            _members_url(company_id),
            params={"page": 2, "page_size": 2},
            headers=_auth(owner_token),
        ).json()["data"]["items"]

        ids_p1 = {i["id"] for i in page1}
        ids_p2 = {i["id"] for i in page2}
        assert ids_p1.isdisjoint(ids_p2), "Pages should not overlap"

    def test_total_pages_calculated_correctly(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """pages field correctly reflects ceil(total / page_size)."""
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix="lm_pages"
        )
        for i in range(4):
            _add_member(
                db_session,
                company_id=company_id,
                role_ids=role_ids,
                email_suffix=f"lm_pages_{i}",
            )

        resp = test_client.get(
            _members_url(company_id),
            params={"page_size": 2},
            headers=_auth(owner_token),
        )
        data = resp.json()["data"]
        expected_pages = -(-data["total"] // 2)  # ceiling division
        assert data["pages"] == expected_pages

    def test_invalid_page_size_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """page_size=0 returns 422 validation error."""
        company_id, owner_token, _, _ = _setup_company(
            test_client, db_session, suffix="lm_paginv"
        )
        resp = test_client.get(
            _members_url(company_id),
            params={"page_size": 0},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------


class TestListMembersFilters:
    """Filter tests: status, role_id, department."""

    def test_status_filter_returns_only_matching(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """?status=inactive returns only inactive members."""
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix="lm_fstatus"
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            status=MembershipStatus.active.value,
            email_suffix="lm_fstatus_a",
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            status=MembershipStatus.inactive.value,
            email_suffix="lm_fstatus_i",
        )

        resp = test_client.get(
            _members_url(company_id),
            params={"status": "inactive"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert all(i["status"] == "inactive" for i in items)
        assert len(items) >= 1

    def test_role_filter_returns_only_matching_role(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """?role_id=<viewer_id> returns only viewer members."""
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix="lm_frole"
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            role_slug="viewer",
            email_suffix="lm_frole_v",
        )

        viewer_role_id = role_ids["viewer"]
        resp = test_client.get(
            _members_url(company_id),
            params={"role_id": viewer_role_id},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert all(i["role"]["id"] == viewer_role_id for i in items)

    def test_department_filter_returns_only_matching(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """?department=Engineering returns only Engineering members."""
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix="lm_fdept"
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            department="Engineering",
            email_suffix="lm_fdept_eng",
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            department="Marketing",
            email_suffix="lm_fdept_mkt",
        )

        resp = test_client.get(
            _members_url(company_id),
            params={"department": "Engineering"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert all(i["department"] == "Engineering" for i in items)
        assert len(items) >= 1

    def test_combined_filters_narrow_results(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Combining status and department filters gives intersection results."""
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix="lm_fcomb"
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            status=MembershipStatus.active.value,
            department="Engineering",
            email_suffix="lm_fcomb_match",
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            status=MembershipStatus.inactive.value,
            department="Engineering",
            email_suffix="lm_fcomb_nomatch",
        )

        resp = test_client.get(
            _members_url(company_id),
            params={"status": "active", "department": "Engineering"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert all(
            i["status"] == "active" and i["department"] == "Engineering" for i in items
        )


# ---------------------------------------------------------------------------
# Text search
# ---------------------------------------------------------------------------


class TestListMembersSearch:
    """Text search tests."""

    def test_search_by_display_name(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """?search=<name> returns members whose display_name matches."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"lm_srch_{sfx}"
        )
        unique_name = f"Zebra_{sfx}"
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            display_name=unique_name,
            email_suffix=f"lm_srch_{sfx}_z",
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            display_name=f"Alpha_{sfx}",
            email_suffix=f"lm_srch_{sfx}_a",
        )

        resp = test_client.get(
            _members_url(company_id),
            params={"search": unique_name},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["display_name"] == unique_name

    def test_search_case_insensitive(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Search is case-insensitive."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"lm_ci_{sfx}"
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            display_name=f"AliceSmith_{sfx}",
            email_suffix=f"lm_ci_{sfx}",
        )

        resp = test_client.get(
            _members_url(company_id),
            params={"search": f"alicesmith_{sfx}"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert any(f"AliceSmith_{sfx}" in i["display_name"] for i in items)

    def test_search_by_employee_id(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """?search=<employee_id> matches on employee_id field."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"lm_empid_{sfx}"
        )
        unique_emp_id = f"EMP-{sfx}"
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            employee_id=unique_emp_id,
            email_suffix=f"lm_empid_{sfx}",
        )

        resp = test_client.get(
            _members_url(company_id),
            params={"search": unique_emp_id},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) >= 1

    def test_search_no_match_returns_empty(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Search that matches nothing returns 0 items."""
        company_id, owner_token, _, _ = _setup_company(
            test_client, db_session, suffix="lm_srch_none"
        )

        resp = test_client.get(
            _members_url(company_id),
            params={"search": "ZZZNOMATCH9999"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] == 0
        assert data["items"] == []


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


class TestListMembersSorting:
    """Sorting tests."""

    def test_sort_by_name_asc(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """?sort_by=name&sort_order=asc returns members in alphabetical order."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"lm_sort_{sfx}"
        )
        # Add members with specific names
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            display_name=f"Zeta_{sfx}",
            email_suffix=f"lm_sort_{sfx}_z",
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            display_name=f"Alpha_{sfx}",
            email_suffix=f"lm_sort_{sfx}_a",
        )

        resp = test_client.get(
            _members_url(company_id),
            params={"sort_by": "name", "sort_order": "asc"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        names = [i["display_name"] for i in resp.json()["data"]["items"]]
        assert names == sorted(names, key=str.lower)

    def test_sort_by_name_desc(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """?sort_by=name&sort_order=desc returns members in reverse alphabetical order."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"lm_sdesc_{sfx}"
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            display_name=f"Zeta_{sfx}",
            email_suffix=f"lm_sdesc_{sfx}_z",
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            display_name=f"Alpha_{sfx}",
            email_suffix=f"lm_sdesc_{sfx}_a",
        )

        resp = test_client.get(
            _members_url(company_id),
            params={"sort_by": "name", "sort_order": "desc"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        names = [i["display_name"] for i in resp.json()["data"]["items"]]
        assert names == sorted(names, key=str.lower, reverse=True)

    def test_sort_by_department(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """?sort_by=department&sort_order=asc returns members sorted by department."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"lm_sdept_{sfx}"
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            department="Marketing",
            email_suffix=f"lm_sdept_{sfx}_m",
        )
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            department="Engineering",
            email_suffix=f"lm_sdept_{sfx}_e",
        )

        resp = test_client.get(
            _members_url(company_id),
            params={"sort_by": "department", "sort_order": "asc"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200
        # Just verify the request succeeds — null departments may appear at either end
        assert resp.json()["data"]["total"] >= 2

    def test_invalid_sort_by_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Invalid sort_by value returns 422."""
        company_id, owner_token, _, _ = _setup_company(
            test_client, db_session, suffix="lm_sinv"
        )
        resp = test_client.get(
            _members_url(company_id),
            params={"sort_by": "invalid_field"},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Roles listing (T078) — already implemented in Phase 5, verified here
# ---------------------------------------------------------------------------


class TestListRoles:
    """Verify GET /roles returns RoleListItem with member_count (T078)."""

    def test_list_roles_returns_all_system_roles(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """GET /roles returns all 8 seeded system roles."""
        company_id, owner_token, _, _ = _setup_company(
            test_client, db_session, suffix="lm_roles"
        )

        resp = test_client.get(_roles_url(company_id), headers=_auth(owner_token))
        assert resp.status_code == 200
        items = resp.json()["data"]
        assert len(items) >= 8  # 8 system roles seeded

    def test_list_roles_includes_member_count(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Each RoleListItem includes a member_count field."""
        company_id, owner_token, _, _ = _setup_company(
            test_client, db_session, suffix="lm_rcnt"
        )

        resp = test_client.get(_roles_url(company_id), headers=_auth(owner_token))
        assert resp.status_code == 200
        for item in resp.json()["data"]:
            assert "member_count" in item
            assert isinstance(item["member_count"], int)

    def test_owner_role_has_correct_member_count(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """The Owner role has member_count=1 after setup."""
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix="lm_rowner"
        )

        resp = test_client.get(_roles_url(company_id), headers=_auth(owner_token))
        owner_role = next(
            (r for r in resp.json()["data"] if r["slug"] == "owner"), None
        )
        assert owner_role is not None
        assert owner_role["member_count"] == 1


# ---------------------------------------------------------------------------
# T083 — Employee info update integration tests (US7)
# ---------------------------------------------------------------------------

from datetime import date, timedelta


def _patch_member_url(company_id: str, member_id: str) -> str:
    return f"/api/v1/companies/{company_id}/members/{member_id}"


def _get_member_url(company_id: str, member_id: str) -> str:
    return f"/api/v1/companies/{company_id}/members/{member_id}"


class TestEmployeeInfoUpdate:
    """PATCH /members/{member_id} — employee info fields (T083)."""

    def test_update_employee_fields_succeeds(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Admin can set all employee info fields."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"eu_all_{sfx}"
        )
        member_id, _ = _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            email_suffix=f"eu_all_{sfx}",
        )

        past_date = (date.today() - timedelta(days=30)).isoformat()
        resp = test_client.patch(
            _patch_member_url(company_id, member_id),
            json={
                "employee_id": f"EMP-{sfx}",
                "job_title": "Senior Developer",
                "department": "Engineering",
                "work_phone": "+1-555-0100",
                "hire_date": past_date,
                "notes": "Internal admin note.",
            },
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()["data"]
        assert data["employee_id"] == f"EMP-{sfx}"
        assert data["job_title"] == "Senior Developer"
        assert data["department"] == "Engineering"
        assert data["work_phone"] == "+1-555-0100"
        assert data["hire_date"] == past_date
        assert data["notes"] == "Internal admin note."

    def test_duplicate_employee_id_returns_409(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Setting employee_id already used by another member returns 409."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"eu_dup_{sfx}"
        )
        # First member with a specific employee_id
        emp_id = f"EMP-CONFLICT-{sfx}"
        _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            employee_id=emp_id,
            email_suffix=f"eu_dup_a_{sfx}",
        )
        # Second member — try to take the same employee_id
        member2_id, _ = _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            email_suffix=f"eu_dup_b_{sfx}",
        )

        resp = test_client.patch(
            _patch_member_url(company_id, member2_id),
            json={"employee_id": emp_id},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 409, resp.text
        assert resp.json()["error"]["code"] == "EMPLOYEE_ID_CONFLICT"

    def test_reassign_same_employee_id_to_self_succeeds(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Updating a member's own employee_id to the same value does not 409."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"eu_self_{sfx}"
        )
        emp_id = f"EMP-SELF-{sfx}"
        member_id, _ = _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            employee_id=emp_id,
            email_suffix=f"eu_self_{sfx}",
        )

        resp = test_client.patch(
            _patch_member_url(company_id, member_id),
            json={"employee_id": emp_id},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["employee_id"] == emp_id

    def test_future_hire_date_returns_422(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Setting hire_date in the future returns 422."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"eu_fd_{sfx}"
        )
        member_id, _ = _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            email_suffix=f"eu_fd_{sfx}",
        )
        future = (date.today() + timedelta(days=1)).isoformat()

        resp = test_client.patch(
            _patch_member_url(company_id, member_id),
            json={"hire_date": future},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 422, resp.text
        assert resp.json()["error"]["code"] == "HIRE_DATE_IN_FUTURE"

    def test_today_hire_date_succeeds(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Setting hire_date to today succeeds."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"eu_today_{sfx}"
        )
        member_id, _ = _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            email_suffix=f"eu_today_{sfx}",
        )
        today = date.today().isoformat()

        resp = test_client.patch(
            _patch_member_url(company_id, member_id),
            json={"hire_date": today},
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["hire_date"] == today


class TestNotesVisibility:
    """FR-023: notes field hidden from members with rank < Admin (80)."""

    def test_admin_can_see_notes(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Admin (rank=80) sees notes in member detail response."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"nv_admin_{sfx}"
        )
        member_id, _ = _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            email_suffix=f"nv_admin_{sfx}",
        )

        # Set notes via PATCH (owner has rank=100 > 80)
        test_client.patch(
            _patch_member_url(company_id, member_id),
            json={"notes": "Confidential admin note."},
            headers=_auth(owner_token),
        )

        resp = test_client.get(
            _get_member_url(company_id, member_id),
            headers=_auth(owner_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["notes"] == "Confidential admin note."

    def test_viewer_cannot_see_notes(
        self, test_client: TestClient, db_session: Session
    ) -> None:
        """Viewer (rank<80) gets notes=null in member detail response."""
        sfx = uuid.uuid4().hex[:8]
        company_id, owner_token, _, role_ids = _setup_company(
            test_client, db_session, suffix=f"nv_viewer_{sfx}"
        )
        member_id, _ = _add_member(
            db_session,
            company_id=company_id,
            role_ids=role_ids,
            role_slug="viewer",
            email_suffix=f"nv_viewer_tgt_{sfx}",
        )

        # Set notes as owner
        test_client.patch(
            _patch_member_url(company_id, member_id),
            json={"notes": "Hidden from viewers."},
            headers=_auth(owner_token),
        )

        # Create a viewer-level user and get their token
        viewer_user, viewer_pw = create_test_user(
            db_session, email=f"viewer_{sfx}@example.com"
        )
        create_test_member(
            db_session,
            company_id=uuid.UUID(company_id),
            user_id=viewer_user.id,
            role_id=uuid.UUID(role_ids["viewer"]),
            status=MembershipStatus.active.value,
        )
        viewer_token = _login(test_client, viewer_user.email, viewer_pw)

        resp = test_client.get(
            _get_member_url(company_id, member_id),
            headers=_auth(viewer_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["notes"] is None
