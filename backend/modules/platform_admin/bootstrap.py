"""Out-of-band Platform Owner bootstrap command (ADR-8).

Breaks the bootstrap circularity — every in-app path to create a Platform
Administrator requires an already-authenticated Platform Admin holding
`platform.admins.manage` (BR-9A-012), which is self-referential for the
very first account (spec.md Assumption A8, resolved OQ-5). This is a
standalone script, deliberately **not** an HTTP route and **not** an
Alembic migration — schema versioning and credential provisioning are
fully decoupled (plan.md §33).

Usage::

    PLATFORM_OWNER_BOOTSTRAP_EMAIL=owner@example.com \\
    PLATFORM_OWNER_BOOTSTRAP_PASSWORD_HASH='$argon2id$...' \\
    python -m modules.platform_admin.bootstrap

The password hash MUST be pre-hashed by the operator using the project's
existing Argon2id hashing utility — plaintext passwords never appear in
source, environment dumps, or logs (Constitution's "never log passwords"
rule extends to never *accepting* one here either).

Exit codes:
    0   Owner created, OR an owner already exists (safe no-op either way).
    1   Missing or invalid configuration; nothing was written.

No Click/Typer framework introduced — a single `if __name__ == "__main__"`
entrypoint, matching the "no new infrastructure" principle.
"""

from __future__ import annotations

import logging
import os
import sys
import unicodedata
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_EMAIL_VAR = "PLATFORM_OWNER_BOOTSTRAP_EMAIL"
_PASSWORD_HASH_VAR = "PLATFORM_OWNER_BOOTSTRAP_PASSWORD_HASH"
_PLATFORM_OWNER_ROLE_CODE = "platform_owner"

_email_adapter = TypeAdapter(EmailStr)


def _normalise_email(email: str) -> str:
    return unicodedata.normalize("NFKC", email).lower().strip()


def _validate_password_hash(hashed: str) -> bool:
    """True if *hashed* is a syntactically valid Argon2 hash string.

    Verifies against a dummy plaintext: `InvalidHash` means the string
    itself is malformed (invalid); `VerifyMismatchError` means the hash is
    well-formed and simply doesn't match "dummy" — which is the expected,
    correct outcome for any real hash, so it is NOT treated as invalid.
    """
    try:
        PasswordHasher().verify(hashed, "bootstrap-format-check-only")
    except VerifyMismatchError:
        return True
    except InvalidHash:
        return False
    return True


def bootstrap_platform_owner(db: Session) -> tuple[int, str]:
    """Provision the first Platform Owner, or safely no-op if one already
    exists. Returns ``(exit_code, message)``. Never overwrites an existing
    owner's credentials. Never partially writes on any failure path.
    """
    # Deferred imports: this module must remain importable even before the
    # rest of the application's settings are configured (a bootstrap
    # script legitimately runs in leaner environments than the full app).
    from modules.auth.models.user import User
    from modules.auth.models.user_credential import UserCredentials
    from modules.platform_admin.models.platform_administrator import (
        PlatformAdministrator,
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

    raw_email = os.environ.get(_EMAIL_VAR)
    raw_hash = os.environ.get(_PASSWORD_HASH_VAR)

    missing = [
        name
        for name, value in ((_EMAIL_VAR, raw_email), (_PASSWORD_HASH_VAR, raw_hash))
        if not value
    ]
    if missing:
        return 1, f"Missing required environment variable(s): {', '.join(missing)}."

    try:
        email = _normalise_email(_email_adapter.validate_python(raw_email))
    except ValidationError:
        return 1, f"{_EMAIL_VAR} is not a valid email address."

    if not _validate_password_hash(raw_hash):
        return 1, (
            f"{_PASSWORD_HASH_VAR} is not a usable Argon2 hash. Pre-hash the "
            "password with the project's existing hashing utility — never "
            "pass a plaintext password."
        )

    rbac_repo = PlatformRbacRepository(db)

    # Never overwrites an existing owner — checked before any write, and
    # regardless of whether raw_email matches that existing owner's email.
    if rbac_repo.count_active_administrators_with_role(_PLATFORM_OWNER_ROLE_CODE) > 0:
        return 0, "A Platform Owner is already provisioned; no changes made."

    # Idempotent — safe to run even if a previous partial deployment
    # already seeded these. Required before the role assignment below,
    # since platform_owner must exist as a PlatformRole row first.
    PlatformRbacSeedService(db, rbac_repo).seed_all()

    admin_repo = PlatformAdministratorRepository(db)

    user = User(email=email, display_name="Platform Owner", is_email_verified=True)
    db.add(user)
    db.flush()

    credentials = UserCredentials(
        user_id=user.id,
        password_hash=raw_hash,
        password_history=[],
        last_changed_at=datetime.now(UTC),
    )
    db.add(credentials)
    db.flush()

    administrator = PlatformAdministrator(user_id=user.id, is_active=True)
    admin_repo.create(administrator)

    owner_role = rbac_repo.get_role_by_code(_PLATFORM_OWNER_ROLE_CODE)
    if owner_role is None:
        # Defensive: seed_all() above should always create this. Fail
        # loudly rather than silently skipping the role assignment.
        db.rollback()
        return 1, (
            f"Internal error: '{_PLATFORM_OWNER_ROLE_CODE}' role was not "
            "found after seeding. Nothing was written."
        )

    rbac_repo.assign_role(
        platform_administrator_id=administrator.id,
        role_id=owner_role.id,
        assigned_by=None,
        assigned_at=datetime.now(UTC),
    )

    db.commit()
    return 0, f"Platform Owner created: administrator id {administrator.id}"


def main() -> int:
    from core.database.session import SessionLocal

    db = SessionLocal()
    try:
        exit_code, message = bootstrap_platform_owner(db)
    except Exception:
        db.rollback()
        logger.exception("Platform Owner bootstrap failed with an unexpected error")
        print("Platform Owner bootstrap failed with an unexpected error.")
        return 1
    finally:
        db.close()

    # Never logs the email/password hash — only the operator-facing
    # result, which itself never contains either (see bootstrap_platform_owner).
    log = logger.info if exit_code == 0 else logger.error
    log(
        "Platform Owner bootstrap result",
        extra={"exit_code": exit_code, "message": message},
    )

    print(message)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
