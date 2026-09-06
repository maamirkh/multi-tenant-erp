"""CapabilityRepository — data access for the `Capability` registry
(T110, ADR-3).

Read-mostly: the catalogue is configuration data (adding a future module
needs one row, no schema change), but seeding/maintaining it is out of
Phase 8's scope (no seed-service task exists in this phase's range) —
`create()` exists for completeness and test setup, not wired to any
route yet.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.platform_admin.models.capability import Capability


class CapabilityRepository:
    """Data access for the `capabilities` table."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, key: str) -> Capability | None:
        return self.db.get(Capability, key)

    def list_all(self, *, is_active: bool | None = None) -> list[Capability]:
        stmt = select(Capability).order_by(Capability.key)
        if is_active is not None:
            stmt = stmt.where(Capability.is_active == is_active)
        return list(self.db.execute(stmt).scalars().all())

    def create(
        self,
        *,
        key: str,
        module: str,
        grain: str,
        display_name: str,
        is_active: bool = True,
    ) -> Capability:
        """Stage a new capability catalogue entry. Caller commits."""
        capability = Capability(
            key=key,
            module=module,
            grain=grain,
            display_name=display_name,
            is_active=is_active,
        )
        self.db.add(capability)
        self.db.flush()
        return capability
