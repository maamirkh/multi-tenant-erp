"""UserRepository — data access layer for the User model.

Auth models use ``BaseModel`` (not ``TenantBaseModel``) so they have no
``company_id`` or ``is_deleted`` columns.  This repository therefore does
NOT extend ``BaseRepository`` and implements only the methods required by
the authentication domain.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from core.exceptions.base import NotFoundException
from core.utils.datetime import utcnow
from modules.auth.models.enums import AccountStatus
from modules.auth.models.user import User

logger = logging.getLogger(__name__)


class UserRepository:
    """Data access for the ``users`` table.

    Args:
        db: SQLAlchemy ``Session`` injected by the FastAPI ``get_db`` dependency.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: UUID) -> User:
        """Return user by primary key or raise ``NotFoundException``."""
        user = self.get_by_id_or_none(user_id)
        if user is None:
            raise NotFoundException(
                message=f"User '{user_id}' not found.",
                details={"user_id": str(user_id)},
            )
        return user

    def get_by_id_or_none(self, user_id: UUID) -> User | None:
        """Return user by primary key or ``None``."""
        stmt = select(User).where(User.id == user_id)
        return self.db.execute(stmt).scalars().one_or_none()

    def find_by_email(self, email: str) -> User | None:
        """Return the user whose email matches (case-insensitive) or ``None``.

        Email is lowercased before lookup to ensure consistent matching
        regardless of the casing used during registration.
        """
        normalised = email.lower().strip()
        stmt = select(User).where(User.email == normalised)
        return self.db.execute(stmt).scalars().one_or_none()

    def create(self, user: User) -> User:
        """Persist a new user and return it with server-generated fields."""
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.debug("User created", extra={"user_id": str(user.id)})
        return user

    def update_failed_login_count(self, user_id: UUID, count: int) -> None:
        """Overwrite the failed-login counter for *user_id*."""
        self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(failed_login_count=count, updated_at=utcnow())
        )
        self.db.commit()

    def lock_account(self, user_id: UUID, locked_until: datetime) -> None:
        """Set account status to LOCKED and record the unlock time."""
        self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                account_status=AccountStatus.LOCKED,
                locked_until=locked_until,
                updated_at=utcnow(),
            )
        )
        self.db.commit()
        logger.info("Account locked", extra={"user_id": str(user_id)})

    def unlock_account(self, user_id: UUID) -> None:
        """Clear the lock, reset the failed-login counter, and set status ACTIVE."""
        self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                account_status=AccountStatus.ACTIVE,
                locked_until=None,
                failed_login_count=0,
                updated_at=utcnow(),
            )
        )
        self.db.commit()
        logger.info("Account unlocked", extra={"user_id": str(user_id)})

    def update_account_status(self, user_id: UUID, status: AccountStatus) -> None:
        """Update the lifecycle status of a user account."""
        self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(account_status=status, updated_at=utcnow())
        )
        self.db.commit()

    def mark_email_verified(self, user_id: UUID) -> None:
        """Set ``is_email_verified = True`` for *user_id*."""
        self.db.execute(
            update(User)
            .where(User.id == user_id)
            .values(is_email_verified=True, updated_at=utcnow())
        )
        self.db.commit()
