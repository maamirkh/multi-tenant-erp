"""[Epic 10, Phase 10, T182] Security test — ``installments.contract.cure``
is never satisfiable via ``installments.collection.create`` (permission-
code independence, explicit regression guard, FR-INST-320/321).

A cashier who can record collections must NOT be able to cure a
defaulted contract — the two are deliberately distinct permission codes
(plan.md §16.1's "each permission independently checked... holding one
never implies another"). This proves it against the real
``user_has_installments_permission()`` resolution chain (``CompanyMember``
-> ``Role`` -> ``RolePermission`` -> ``Permission``), not merely by
reading the source.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from modules.installments.services.permission_check import (
    user_has_installments_permission,
)
from modules.users_roles.models.company_member import CompanyMember
from modules.users_roles.models.enums import MembershipStatus
from modules.users_roles.models.permission import Permission
from modules.users_roles.models.role import Role
from modules.users_roles.models.role_permission import RolePermission
from tests.fixtures.auth_fixtures import create_test_user

_CURE = "installments.contract.cure"
_COLLECTION_CREATE = "installments.collection.create"


def _ensure_permission(db: Session, code: str) -> None:
    if db.get(Permission, code) is not None:
        return
    db.add(
        Permission(
            id=code,
            code=code,
            label=code,
            module="installments",
            action="manage",
        )
    )
    db.flush()


class TestCurePermissionIsolation:
    def test_collection_create_permission_does_not_satisfy_cure(
        self, db_session: Session
    ) -> None:
        company_id = uuid.uuid4()
        user, _ = create_test_user(
            db_session, email=f"cashier_{uuid.uuid4().hex[:8]}@example.com"
        )

        _ensure_permission(db_session, _CURE)
        _ensure_permission(db_session, _COLLECTION_CREATE)

        role = Role(
            company_id=company_id,
            name="Cashier",
            slug=f"cashier-{uuid.uuid4().hex[:8]}",
            rank=50,
            is_system=False,
            is_active=True,
        )
        db_session.add(role)
        db_session.flush()

        # Grants collection.create ONLY — never cure.
        db_session.add(
            RolePermission(role_id=role.id, permission_id=_COLLECTION_CREATE)
        )
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

        # Positive control: the granted permission IS satisfied.
        assert (
            user_has_installments_permission(
                db_session, company_id, user.id, _COLLECTION_CREATE
            )
            is True
        )
        # The regression guard: an unrelated, distinct permission is NOT
        # satisfied merely because collection.create is held.
        assert (
            user_has_installments_permission(db_session, company_id, user.id, _CURE)
            is False
        )

    def test_cure_permission_does_not_satisfy_collection_create(
        self, db_session: Session
    ) -> None:
        """Symmetric guard — the independence holds in both directions."""
        company_id = uuid.uuid4()
        user, _ = create_test_user(
            db_session, email=f"collector_{uuid.uuid4().hex[:8]}@example.com"
        )

        _ensure_permission(db_session, _CURE)
        _ensure_permission(db_session, _COLLECTION_CREATE)

        role = Role(
            company_id=company_id,
            name="Collections Manager",
            slug=f"collections-mgr-{uuid.uuid4().hex[:8]}",
            rank=60,
            is_system=False,
            is_active=True,
        )
        db_session.add(role)
        db_session.flush()

        db_session.add(RolePermission(role_id=role.id, permission_id=_CURE))
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

        assert (
            user_has_installments_permission(db_session, company_id, user.id, _CURE)
            is True
        )
        assert (
            user_has_installments_permission(
                db_session, company_id, user.id, _COLLECTION_CREATE
            )
            is False
        )
