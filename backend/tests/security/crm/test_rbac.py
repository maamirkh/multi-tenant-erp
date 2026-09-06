"""CRM RBAC permission matrix — all 19 permissions x 8 roles (T063).

Direct, exhaustive verification of spec.md §31.2's Role Access Matrix
against ``user_has_crm_permission()`` (T064), matching the exact style of
``tests/security/accounting/test_rbac.py``'s own per-code granted/denied
coverage, but exhaustive here (every cell of the matrix, not a sampled
subset) since 19x8=152 assertions is small enough to run directly.

Spec ref: specs/009-crm/spec.md §31.1-31.2; tasks.md T063 (Phase 8).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from modules.crm.services.permission_check import user_has_crm_permission
from modules.users_roles.constants import DEFAULT_ROLE_PERMISSIONS
from tests.fixtures.auth_fixtures import create_test_user
from tests.fixtures.users_roles_fixtures import (
    create_member_with_role,
    seed_system_roles,
)

# spec.md §31.2's Role Access Matrix, transcribed cell-for-cell.
_ROLE_SLUGS = (
    "owner",
    "admin",
    "manager",
    "accountant",
    "salesperson",
    "cashier",
    "store-keeper",
    "viewer",
)

_MATRIX: dict[str, dict[str, bool]] = {
    "crm.leads.view": dict(
        zip(
            _ROLE_SLUGS, (True, True, True, True, True, False, False, True), strict=True
        )
    ),
    "crm.leads.create": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, True, False, True, False, False, False),
            strict=True,
        )
    ),
    "crm.leads.update": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, True, False, True, False, False, False),
            strict=True,
        )
    ),
    "crm.leads.delete": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, True, False, False, False, False, False),
            strict=True,
        )
    ),
    "crm.leads.assign": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, True, False, False, False, False, False),
            strict=True,
        )
    ),
    "crm.leads.convert": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, True, False, True, False, False, False),
            strict=True,
        )
    ),
    "crm.opportunities.view": dict(
        zip(
            _ROLE_SLUGS, (True, True, True, True, True, False, False, True), strict=True
        )
    ),
    "crm.opportunities.create": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, True, False, True, False, False, False),
            strict=True,
        )
    ),
    "crm.opportunities.update": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, True, False, True, False, False, False),
            strict=True,
        )
    ),
    "crm.opportunities.delete": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, True, False, False, False, False, False),
            strict=True,
        )
    ),
    "crm.opportunities.assign": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, True, False, False, False, False, False),
            strict=True,
        )
    ),
    "crm.opportunities.close": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, True, False, False, False, False, False),
            strict=True,
        )
    ),
    "crm.activities.view": dict(
        zip(
            _ROLE_SLUGS, (True, True, True, True, True, False, False, True), strict=True
        )
    ),
    "crm.activities.create": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, True, False, True, False, False, False),
            strict=True,
        )
    ),
    "crm.activities.update": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, True, False, True, False, False, False),
            strict=True,
        )
    ),
    "crm.activities.delete": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, True, False, False, False, False, False),
            strict=True,
        )
    ),
    "crm.pipeline.view": dict(
        zip(
            _ROLE_SLUGS, (True, True, True, True, True, False, False, True), strict=True
        )
    ),
    "crm.pipeline.manage": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, False, False, False, False, False, False),
            strict=True,
        )
    ),
    "crm.reports.view": dict(
        zip(
            _ROLE_SLUGS,
            (True, True, True, True, False, False, False, True),
            strict=True,
        )
    ),
}


def _params() -> list[tuple[str, str, bool]]:
    return [
        (code, role, expected)
        for code, roles in _MATRIX.items()
        for role, expected in roles.items()
    ]


class TestCrmPermissionCatalogCompleteness:
    def test_exactly_19_crm_codes_and_8_roles_covered(self) -> None:
        assert len(_MATRIX) == 19
        for roles in _MATRIX.values():
            assert set(roles) == set(_ROLE_SLUGS)

    def test_matrix_matches_default_role_permissions_seed_data(self) -> None:
        """Cross-check the matrix transcribed above against the actual
        seed data in ``constants.py`` (T060/T061) — catches drift between
        this test's expectations and the real catalog."""
        for code, roles in _MATRIX.items():
            for role_slug, expected in roles.items():
                actual = code in DEFAULT_ROLE_PERMISSIONS[role_slug]
                assert actual == expected, (
                    f"{code} / {role_slug}: seed data says {actual}, "
                    f"spec.md §31.2 says {expected}"
                )


class TestCrmPermissionMatrix:
    @pytest.mark.parametrize("permission_code,role_slug,expected", _params())
    def test_role_permission_cell(
        self,
        db_session: Session,
        permission_code: str,
        role_slug: str,
        expected: bool,
    ) -> None:
        company_id = uuid4()
        seed_system_roles(db_session, company_id)
        email = f"rbac-{uuid4().hex[:10]}@example.com"
        user, _ = create_test_user(db_session, email)
        create_member_with_role(
            db_session, company_id=company_id, user_id=user.id, role_slug=role_slug
        )

        result = user_has_crm_permission(
            db_session, company_id, user.id, permission_code
        )

        assert result is expected, (
            f"{role_slug} / {permission_code}: expected {expected}, got {result}"
        )
