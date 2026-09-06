"""[T070-T073] Out-of-band Platform Owner bootstrap.

Covers tasks.md T070 (first success creates all 3 rows atomically), T071
(missing config -> non-zero, writes nothing), T072 (repeated bootstrap
with an owner present is a safe no-op), T073 (invalid config -> non-zero).
"""

from __future__ import annotations

from argon2 import PasswordHasher
from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.auth.models.user import User
from modules.platform_admin.bootstrap import (
    _EMAIL_VAR,
    _PASSWORD_HASH_VAR,
    bootstrap_platform_owner,
)
from modules.platform_admin.models.platform_administrator import PlatformAdministrator
from modules.platform_admin.models.platform_rbac import (
    PlatformAdminRoleAssignment,
    PlatformRole,
)
from modules.platform_admin.repositories.platform_administrator_repository import (
    PlatformAdministratorRepository,
)
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)
from modules.platform_admin.services.platform_rbac_seed_service import (
    PlatformRbacSeedService,
)

_VALID_HASH = PasswordHasher().hash("BootstrapTestPassword@123")


def _isolate_as_zero_owners(db: Session, rbac_repo: PlatformRbacRepository) -> None:
    """Remove every existing `platform_owner` assignment so this test's
    actual claim — a fresh bootstrap creates all three rows atomically —
    is genuinely provable. Other test files sharing this session (e.g.
    integration/api/v1/platform_admin, security/modules/platform_admin)
    may create `platform_owner`-role administrators via direct repository
    calls before this test runs; pytest's cross-directory collection
    order is not something this suite controls, and the shared
    `db_session` fixture's leakage across test functions is a documented,
    pre-existing property (Phase 3/4/5 PHRs), not something to fix here.
    """
    PlatformRbacSeedService(db, rbac_repo).seed_all()
    owner_role = rbac_repo.get_role_by_code("platform_owner")
    assert owner_role is not None
    existing_owner_ids = (
        db.execute(
            select(PlatformAdminRoleAssignment.platform_administrator_id).where(
                PlatformAdminRoleAssignment.role_id == owner_role.id
            )
        )
        .scalars()
        .all()
    )
    for admin_id in existing_owner_ids:
        rbac_repo.remove_assignment(
            platform_administrator_id=admin_id, role_id=owner_role.id
        )
    db.commit()


class TestFirstSuccessfulBootstrap:
    def test_creates_user_administrator_and_owner_assignment(
        self, db_session: Session, monkeypatch
    ) -> None:
        _isolate_as_zero_owners(db_session, PlatformRbacRepository(db_session))

        monkeypatch.setenv(_EMAIL_VAR, "owner@example.com")
        monkeypatch.setenv(_PASSWORD_HASH_VAR, _VALID_HASH)

        exit_code, message = bootstrap_platform_owner(db_session)

        assert exit_code == 0
        assert "created" in message.lower()

        user = db_session.execute(
            select(User).where(User.email == "owner@example.com")
        ).scalar_one()
        admin_repo = PlatformAdministratorRepository(db_session)
        administrator = admin_repo.get_by_user_id(user.id)
        assert administrator is not None
        assert administrator.is_active is True
        assert str(administrator.id) in message

        rbac_repo = PlatformRbacRepository(db_session)
        assert rbac_repo.has_role(administrator.id, "platform_owner")

        assignment = db_session.execute(
            select(PlatformAdminRoleAssignment).where(
                PlatformAdminRoleAssignment.platform_administrator_id
                == administrator.id
            )
        ).scalar_one()
        assert (
            assignment.assigned_by is None
        ), "bootstrap-created first assignment must have assigned_by=NULL"


# NOTE on test isolation: the shared `db_session` fixture's SAVEPOINT
# rollback does not undo state committed via service-layer `db.commit()`
# calls made by an *earlier* test function within the same pytest
# process (a pre-existing property of this fixture, discovered and
# documented in Phase 3/4 — see those phases' PHRs). `bootstrap_platform_
# owner()` commits on every path, so a Platform Owner may already exist
# by the time any given test in this file runs. Every assertion below is
# therefore written as a before/after delta or relative to state this
# test itself establishes, never as an absolute "the table is empty"
# assumption.


class TestMissingConfiguration:
    def test_missing_both_vars_exits_nonzero_and_writes_nothing(
        self, db_session: Session, monkeypatch
    ) -> None:
        monkeypatch.delenv(_EMAIL_VAR, raising=False)
        monkeypatch.delenv(_PASSWORD_HASH_VAR, raising=False)
        count_before = db_session.query(PlatformAdministrator).count()

        exit_code, message = bootstrap_platform_owner(db_session)

        assert exit_code == 1
        assert _EMAIL_VAR in message
        assert _PASSWORD_HASH_VAR in message
        assert db_session.query(PlatformAdministrator).count() == count_before

    def test_missing_password_hash_only_exits_nonzero(
        self, db_session: Session, monkeypatch
    ) -> None:
        monkeypatch.setenv(_EMAIL_VAR, "owner2@example.com")
        monkeypatch.delenv(_PASSWORD_HASH_VAR, raising=False)

        exit_code, message = bootstrap_platform_owner(db_session)

        assert exit_code == 1
        assert _PASSWORD_HASH_VAR in message
        assert (
            db_session.execute(
                select(User).where(User.email == "owner2@example.com")
            ).scalar_one_or_none()
            is None
        )

    def test_fixing_config_after_a_missing_config_failure_succeeds(
        self, db_session: Session, monkeypatch
    ) -> None:
        monkeypatch.delenv(_EMAIL_VAR, raising=False)
        monkeypatch.delenv(_PASSWORD_HASH_VAR, raising=False)
        first_exit, _ = bootstrap_platform_owner(db_session)
        assert first_exit == 1

        monkeypatch.setenv(_EMAIL_VAR, "owner3@example.com")
        monkeypatch.setenv(_PASSWORD_HASH_VAR, _VALID_HASH)
        second_exit, second_message = bootstrap_platform_owner(db_session)
        # "Succeeds" means exit 0 either way an owner already exists (from
        # an earlier test in this session) -> "already provisioned"; if
        # not -> "created". Both are the correct, non-error outcome for
        # the state actually in front of this call; what T071 requires is
        # that a MISSING-config failure never persists as a false "success"
        # once config is fixed, which the exit-code assertion proves.
        assert second_exit == 0
        assert (
            "created" in second_message.lower()
            or "already provisioned" in second_message.lower()
        )


class TestRepeatedBootstrapIsSafeNoOp:
    def test_second_bootstrap_with_owner_present_is_a_no_op(
        self, db_session: Session, monkeypatch
    ) -> None:
        # Establish a definite baseline owner for THIS test, tolerating
        # that one may already exist from cross-test leakage (in which
        # case this call itself is already a no-op — still a valid
        # baseline to assert against).
        monkeypatch.setenv(_EMAIL_VAR, "first-owner@example.com")
        monkeypatch.setenv(_PASSWORD_HASH_VAR, _VALID_HASH)
        baseline_exit, _ = bootstrap_platform_owner(db_session)
        assert baseline_exit == 0

        count_before = db_session.query(PlatformAdministrator).count()
        assert count_before >= 1
        # Look up the administrator actually holding `platform_owner`,
        # NOT just any `PlatformAdministrator` row — other test files in
        # this same session (e.g. test_platform_administrator.py) create
        # bare administrators with no role assignment and no
        # `UserCredentials` row at all, and leakage means those rows can
        # already be present here (see the module-level NOTE above).
        # Bootstrap always creates its owner with credentials + the
        # `platform_owner` role atomically, so this lookup is unambiguous.
        # `assigned_by IS NULL` uniquely identifies the bootstrap-created
        # first assignment (migration 057's column comment; also asserted
        # by TestFirstSuccessfulBootstrap above) — other tests that assign
        # `platform_owner` to a second administrator always pass an actor,
        # so this stays unambiguous even if such a test ran earlier in
        # this session.
        owner_admin_id = (
            db_session.execute(
                select(PlatformAdminRoleAssignment.platform_administrator_id)
                .join(
                    PlatformRole, PlatformRole.id == PlatformAdminRoleAssignment.role_id
                )
                .where(
                    PlatformRole.code == "platform_owner",
                    PlatformAdminRoleAssignment.assigned_by.is_(None),
                )
            )
            .scalars()
            .first()
        )
        assert owner_admin_id is not None
        existing_admin = db_session.get(PlatformAdministrator, owner_admin_id)
        baseline_user = db_session.execute(
            select(User).where(User.id == existing_admin.user_id)
        ).scalar_one()
        baseline_hash = baseline_user.credentials.password_hash

        # A DIFFERENT email/hash presented on the second run — must still
        # be a no-op, since an owner already exists (regardless of email).
        different_hash = PasswordHasher().hash("ADifferentPassword@456")
        monkeypatch.setenv(_EMAIL_VAR, "second-owner@example.com")
        monkeypatch.setenv(_PASSWORD_HASH_VAR, different_hash)
        second_exit, second_message = bootstrap_platform_owner(db_session)

        assert second_exit == 0
        assert "already provisioned" in second_message.lower()
        assert db_session.query(PlatformAdministrator).count() == count_before
        assert (
            db_session.execute(
                select(User).where(User.email == "second-owner@example.com")
            ).scalar_one_or_none()
            is None
        )
        # The pre-existing owner's credentials are byte-for-byte unchanged.
        db_session.refresh(baseline_user)
        assert baseline_user.credentials.password_hash == baseline_hash


class TestInvalidConfiguration:
    def test_malformed_email_exits_nonzero_and_writes_nothing(
        self, db_session: Session, monkeypatch
    ) -> None:
        monkeypatch.setenv(_EMAIL_VAR, "not-an-email")
        monkeypatch.setenv(_PASSWORD_HASH_VAR, _VALID_HASH)
        count_before = db_session.query(PlatformAdministrator).count()

        exit_code, message = bootstrap_platform_owner(db_session)

        assert exit_code == 1
        assert "email" in message.lower()
        assert db_session.query(PlatformAdministrator).count() == count_before

    def test_unusable_password_hash_exits_nonzero_and_writes_nothing(
        self, db_session: Session, monkeypatch
    ) -> None:
        monkeypatch.setenv(_EMAIL_VAR, "owner4@example.com")
        monkeypatch.setenv(_PASSWORD_HASH_VAR, "definitely-not-an-argon2-hash")

        exit_code, message = bootstrap_platform_owner(db_session)

        assert exit_code == 1
        assert "hash" in message.lower()
        assert (
            db_session.execute(
                select(User).where(User.email == "owner4@example.com")
            ).scalar_one_or_none()
            is None
        )
