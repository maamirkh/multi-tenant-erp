"""PlatformRbacSeedService — idempotent seeding of Platform permissions
and candidate role bundles.

Mirrors `RoleSeedService`'s check-then-create idempotency technique
(existence check via repository lookup, not a DB-level `ON CONFLICT`).
Roles/permissions are configuration data, addable without a code change
(FR-9A-140) — seeded from `constants.py`'s `PLATFORM_PERMISSION_CATALOGUE`/
`CANDIDATE_PLATFORM_ROLE_BUNDLES`, **not** a migration (ADR-8's
decoupling principle applies here too: catalogue/bundle changes should
never require a schema migration).
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from modules.platform_admin.constants import (
    CANDIDATE_PLATFORM_ROLE_BUNDLES,
    PLATFORM_PERMISSION_CATALOGUE,
)
from modules.platform_admin.repositories.platform_rbac_repository import (
    PlatformRbacRepository,
)

logger = logging.getLogger(__name__)


class PlatformRbacSeedService:
    """Seeds the Platform permission catalogue and candidate role bundles."""

    def __init__(self, db: Session, repo: PlatformRbacRepository) -> None:
        self._db = db
        self._repo = repo

    def seed_permissions(self) -> int:
        """Seed every code in `PLATFORM_PERMISSION_CATALOGUE` (idempotent).

        Returns the number of rows genuinely created (0 on a no-op rerun).
        """
        created = 0
        for entry in PLATFORM_PERMISSION_CATALOGUE:
            if self._repo.get_permission(entry["code"]) is not None:
                continue
            self._repo.create_permission(
                code=entry["code"], label=entry["label"], area=entry["area"]
            )
            created += 1
        self._db.commit()
        logger.info(
            "Platform permissions seeded",
            extra={
                "created_count": created,
                "total": len(PLATFORM_PERMISSION_CATALOGUE),
            },
        )
        return created

    def seed_role_bundles(self) -> int:
        """Seed every candidate role bundle in
        `CANDIDATE_PLATFORM_ROLE_BUNDLES` (idempotent). Requires
        `seed_permissions()` to have run first (FK to `platform_permissions`).

        Returns the number of roles genuinely created (0 on a no-op rerun).
        A role's permission bundle is only touched if it no longer matches
        the current catalogue definition — a true no-op rerun performs
        zero writes to `platform_role_permissions`, not merely an
        equivalent delete-and-recreate; this also means a later
        constants.py edit is picked up on the next seed run without
        manual intervention.
        """
        created = 0
        for bundle in CANDIDATE_PLATFORM_ROLE_BUNDLES:
            role = self._repo.get_role_by_code(bundle["code"])
            if role is None:
                role = self._repo.create_role(code=bundle["code"], name=bundle["name"])
                created += 1

            target = frozenset(bundle["permission_codes"])
            current = self._repo.get_role_permission_codes(role.id)
            if current != target:
                self._repo.set_role_permissions(role.id, set(target))
        self._db.commit()
        logger.info(
            "Platform role bundles seeded",
            extra={
                "created_count": created,
                "total": len(CANDIDATE_PLATFORM_ROLE_BUNDLES),
            },
        )
        return created

    def seed_all(self) -> None:
        """Seed permissions then role bundles, in dependency order."""
        self.seed_permissions()
        self.seed_role_bundles()
