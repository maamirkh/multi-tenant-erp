"""One-time backfill: grant the three new feature-toggle-management
permission codes to every existing company's owner/admin roles (Epic 9A
Phase 10, T141, plan.md §14 risk mitigation).

``RoleSeedService.seed_role_permissions()`` only ever runs at company
creation time (``POST /companies``) — it is never re-invoked for a
company that already exists. Adding ``inventory.settings.manage`` /
``sales.settings.manage`` / ``purchase.settings.manage`` to
``DEFAULT_ROLE_PERMISSIONS`` in ``constants.py`` therefore only reaches
*new* companies automatically; existing companies' already-seeded
``owner``/``admin`` roles need this one-time backfill so their tenant
admins can still manage feature toggles immediately after deploy
(T141's acceptance).

Standalone script, deliberately **not** an HTTP route and **not** an
Alembic migration (Epic 9A migration range is frozen at 057-061, no
062) — mirrors ``bootstrap.py``/``rollout_service.py``'s own established
out-of-band, operator-run convention for the identical problem shape.
Safe to re-run: reuses ``RoleSeedService.seed_role_permissions()``'s own
additive-only, idempotent logic unchanged.

Usage::

    python -m modules.users_roles.backfill_feature_toggle_permissions
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def backfill_all_companies(db: Session) -> int:
    """Run the backfill against every existing, non-deleted company.
    Returns the number of companies processed."""
    from modules.companies.repositories.company_repository import CompanyRepository
    from modules.users_roles.repositories.permission_repository import (
        PermissionRepository,
    )
    from modules.users_roles.repositories.role_permission_repository import (
        RolePermissionRepository,
    )
    from modules.users_roles.repositories.role_repository import RoleRepository
    from modules.users_roles.services.role_seed_service import RoleSeedService

    seed_service = RoleSeedService(
        db=db,
        role_repo=RoleRepository(db),
        permission_repo=PermissionRepository(db),
        role_permission_repo=RolePermissionRepository(db),
    )
    # Ensure the 3 new global Permission catalogue rows exist before any
    # per-company role-permission mapping references them.
    seed_service.seed_permissions()

    company_repo = CompanyRepository(db)
    company_ids: list[UUID] = []
    page = 1
    while True:
        items, total = company_repo.list_all({}, page=page, page_size=100)
        company_ids.extend(company.id for company in items)
        if len(company_ids) >= total or not items:
            break
        page += 1

    return seed_service.backfill_default_role_permissions_for_existing_companies(
        company_ids
    )


def main() -> int:
    from core.database.session import SessionLocal

    db = SessionLocal()
    try:
        processed = backfill_all_companies(db)
    except Exception:
        db.rollback()
        logger.exception("Feature-toggle permission backfill failed unexpectedly")
        print("Feature-toggle permission backfill failed unexpectedly.")
        return 1
    finally:
        db.close()

    print(f"Backfill complete: {processed} company(ies) processed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
