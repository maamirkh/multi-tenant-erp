"""[Epic 10, Phase 11, T201] Security test — each of the 16
``installments.*`` permission codes independently denies when absent
(per-code sweep, plan.md §16.1: "each permission independently checked
... holding one never implies another", FR-INST-320/321).

Generalizes ``test_cure_permission_isolation.py``'s (T182) two-code
proof to the complete catalogue: for every code, a role granted ONLY
that code satisfies it and denies all 15 others — proven against the
real ``user_has_installments_permission()`` resolution chain
(``CompanyMember`` -> ``Role`` -> ``RolePermission`` -> ``Permission``).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from modules.installments.constants import INSTALLMENTS_PERMISSIONS
from modules.installments.services.permission_check import (
    user_has_installments_permission,
)
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.enums import MembershipStatus
from modules.users_roles.models.permission import Permission
from modules.users_roles.models.role import Role
from modules.users_roles.models.role_permission import RolePermission
from tests.fixtures.auth_fixtures import create_test_user

_ALL_CODES = tuple(definition.code for definition in INSTALLMENTS_PERMISSIONS)


def _ensure_permission(db: Session, code: str) -> None:
    if db.get(Permission, code) is not None:
        return
    db.add(
        Permission(
            id=code, code=code, label=code, module="installments", action="manage"
        )
    )
    db.flush()


class TestSixteenPermissionCodesCatalogue:
    def test_exactly_sixteen_codes_defined(self) -> None:
        assert len(_ALL_CODES) == 16
        assert len(set(_ALL_CODES)) == 16, "no duplicate permission codes"


class TestPermissionSweepGrantedCodeAllowsAllOthersDeny:
    @pytest.mark.parametrize("granted_code", _ALL_CODES)
    def test_granting_only_this_code_satisfies_only_this_code(
        self, db_session: Session, granted_code: str
    ) -> None:
        company_id = uuid.uuid4()
        user, _ = create_test_user(
            db_session, email=f"t201-{uuid.uuid4().hex[:10]}@example.com"
        )

        for code in _ALL_CODES:
            _ensure_permission(db_session, code)

        role = Role(
            company_id=company_id,
            name=f"T201 Single-Permission Role ({granted_code})",
            slug=f"t201-role-{uuid.uuid4().hex[:10]}",
            rank=50,
            is_system=False,
            is_active=True,
        )
        db_session.add(role)
        db_session.flush()

        db_session.add(RolePermission(role_id=role.id, permission_id=granted_code))
        db_session.flush()

        db_session.add(
            CompanyMember(
                company_id=company_id,
                user_id=user.id,
                role_id=role.id,
                status=MembershipStatus.active.value,
            )
        )
        db_session.commit()

        for code in _ALL_CODES:
            allowed = user_has_installments_permission(
                db_session, company_id, user.id, code
            )
            if code == granted_code:
                assert allowed is True, f"granted code {code!r} must be satisfied"
            else:
                assert allowed is False, (
                    f"unrelated code {code!r} must NOT be satisfied merely "
                    f"because {granted_code!r} is held"
                )


class TestPermissionSweepNoRoleDeniesEverything:
    def test_member_with_an_empty_role_denies_every_code(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        user, _ = create_test_user(
            db_session, email=f"t201-norole-{uuid.uuid4().hex[:10]}@example.com"
        )
        for code in _ALL_CODES:
            _ensure_permission(db_session, code)

        empty_role = Role(
            company_id=company_id,
            name="T201 Empty Role",
            slug=f"t201-empty-role-{uuid.uuid4().hex[:10]}",
            rank=10,
            is_system=False,
            is_active=True,
        )
        db_session.add(empty_role)
        db_session.flush()

        db_session.add(
            CompanyMember(
                company_id=company_id,
                user_id=user.id,
                role_id=empty_role.id,
                status=MembershipStatus.active.value,
            )
        )
        db_session.commit()

        for code in _ALL_CODES:
            assert (
                user_has_installments_permission(db_session, company_id, user.id, code)
                is False
            )
