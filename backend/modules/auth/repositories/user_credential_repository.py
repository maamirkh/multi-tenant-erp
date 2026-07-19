"""UserCredentialRepository — data access for hashed password storage."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from core.exceptions.base import NotFoundException
from core.utils.datetime import utcnow
from modules.auth.models.user_credential import UserCredentials

logger = logging.getLogger(__name__)


class UserCredentialRepository:
    """Data access for the ``user_credentials`` table.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user_id(self, user_id: UUID) -> UserCredentials:
        """Return credentials for *user_id* or raise ``NotFoundException``."""
        stmt = select(UserCredentials).where(UserCredentials.user_id == user_id)
        creds = self.db.execute(stmt).scalars().one_or_none()
        if creds is None:
            raise NotFoundException(
                message=f"Credentials for user '{user_id}' not found.",
                details={"user_id": str(user_id)},
            )
        return creds

    def create(self, credentials: UserCredentials) -> UserCredentials:
        """Persist new credentials and return the refreshed record."""
        self.db.add(credentials)
        self.db.commit()
        self.db.refresh(credentials)
        logger.debug("Credentials created", extra={"user_id": str(credentials.user_id)})
        return credentials

    def update_password_hash(
        self,
        user_id: UUID,
        new_hash: str,
        history: list[str],
        changed_at: datetime,
    ) -> None:
        """Replace the stored hash and update password history.

        Args:
            user_id:    Target user.
            new_hash:   Argon2id hash of the new password.
            history:    Updated list of previous hashes (oldest-first).
            changed_at: Timestamp of the password change.
        """
        self.db.execute(
            update(UserCredentials)
            .where(UserCredentials.user_id == user_id)
            .values(
                password_hash=new_hash,
                password_history=history,
                last_changed_at=changed_at,
                updated_at=utcnow(),
            )
        )
        self.db.commit()
        logger.info("Password hash updated", extra={"user_id": str(user_id)})
