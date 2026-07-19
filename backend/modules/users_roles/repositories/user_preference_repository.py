"""UserPreferenceRepository — data access layer for UserPreference model.

UserPreference is user-scoped (not company-scoped) and has a 1:1
relationship with User.  It does NOT extend ``BaseRepository`` because
``BaseRepository`` requires TenantBaseModel (which has ``company_id``).

Spec reference: data-model.md Section 2.5, tasks T057.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.users_roles.models.user_preference import UserPreference

logger = logging.getLogger(__name__)

# Default values for a newly created preference record.
_DEFAULTS: dict[str, Any] = {
    "language": "en",
    "timezone": "UTC",
    "date_format": "YYYY-MM-DD",
    "number_format": "en-US",
    "theme": "system",
    "notification_preferences": {},
}


class UserPreferenceRepository:
    """Data access for the ``user_preferences`` table.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Read ───────────────────────────────────────────────────────────────

    def get_by_user_id(self, user_id: UUID) -> UserPreference | None:
        """Return the preference record for ``user_id``, or ``None``."""
        stmt = select(UserPreference).where(UserPreference.user_id == user_id)
        return self.db.execute(stmt).scalars().one_or_none()

    # ── Write ──────────────────────────────────────────────────────────────

    def create_with_defaults(self, user_id: UUID) -> UserPreference:
        """Create a new preference record with sensible default values.

        Args:
            user_id: The owning user's UUID.

        Returns:
            The newly created ``UserPreference`` instance (server fields populated).
        """
        pref = UserPreference(user_id=user_id, **_DEFAULTS)
        self.db.add(pref)
        self.db.commit()
        self.db.refresh(pref)
        logger.debug(
            "UserPreference created with defaults",
            extra={"user_id": str(user_id)},
        )
        return pref

    def create_or_update(
        self, user_id: UUID, updates: dict[str, Any]
    ) -> UserPreference:
        """Upsert preference values for ``user_id``.

        Fetches the existing record (or creates one with defaults first),
        applies the provided ``updates``, then commits and refreshes.

        Args:
            user_id: The owning user's UUID.
            updates: Mapping of column names to new values.  Only provided
                keys are modified; omitted keys retain their current value.

        Returns:
            The updated ``UserPreference`` instance.
        """
        pref = self.get_by_user_id(user_id)
        if pref is None:
            pref = UserPreference(user_id=user_id, **_DEFAULTS)
            self.db.add(pref)

        for key, value in updates.items():
            setattr(pref, key, value)

        self.db.commit()
        self.db.refresh(pref)
        logger.debug(
            "UserPreference updated",
            extra={"user_id": str(user_id), "fields": list(updates.keys())},
        )
        return pref
