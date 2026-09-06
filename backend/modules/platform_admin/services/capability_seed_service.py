"""CapabilitySeedService — idempotent seeding of the five module
`Capability` rows (T124, plan.md §34 rollout step 2).

Mirrors `PlatformRbacSeedService`'s check-then-create idempotency
technique. Capability rows are configuration data (adding a future module
needs one row, no schema change, Assumption A7) — seeded here, **not** a
migration (ADR-8's decoupling principle applies here too).
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from modules.platform_admin.repositories.capability_repository import (
    CapabilityRepository,
)

logger = logging.getLogger(__name__)

# The five existing business modules, at module grain (plan.md §12) —
# every future module needs only one additional row here, never a schema
# change to `capabilities`.
MODULE_CAPABILITY_CATALOGUE: tuple[dict[str, str], ...] = (
    {"key": "inventory", "module": "inventory", "display_name": "Inventory"},
    {"key": "purchase", "module": "purchase", "display_name": "Purchase"},
    {"key": "sales", "module": "sales", "display_name": "Sales"},
    {"key": "accounting", "module": "accounting", "display_name": "Accounting"},
    {"key": "crm", "module": "crm", "display_name": "CRM"},
)


class CapabilitySeedService:
    """Seeds the module-grain `Capability` catalogue."""

    def __init__(self, db: Session, repo: CapabilityRepository) -> None:
        self._db = db
        self._repo = repo

    def seed_capabilities(self) -> int:
        """Seed every entry in `MODULE_CAPABILITY_CATALOGUE` (idempotent).

        Returns the number of rows genuinely created (0 on a no-op rerun).
        """
        created = 0
        for entry in MODULE_CAPABILITY_CATALOGUE:
            if self._repo.get(entry["key"]) is not None:
                continue
            self._repo.create(
                key=entry["key"],
                module=entry["module"],
                grain="module",
                display_name=entry["display_name"],
            )
            created += 1
        self._db.commit()
        logger.info(
            "Platform module capabilities seeded",
            extra={
                "created_count": created,
                "total": len(MODULE_CAPABILITY_CATALOGUE),
            },
        )
        return created
