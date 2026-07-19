"""Auth test fixtures — factory functions for creating test users and credentials.

Used by integration test suites that require seeded data in the test database.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from modules.auth.models.enums import AccountStatus
from modules.auth.models.user import User
from modules.auth.models.user_credential import UserCredentials
from modules.auth.services.password_service import PasswordService

_TEST_PASSWORD = "TestPassword@1234"
_TEST_EMAIL = "testuser@example.com"

_MINIMAL_SETTINGS_KWARGS = {
    "DATABASE_URL": "sqlite:///:memory:",
    "SECRET_KEY": "test-secret-key-minimum-32-chars-ok",
    "JWT_SECRET_KEY": "test-jwt-secret-key-min-32-chars-ok!",
}


def create_test_user(
    db: Session,
    email: str = _TEST_EMAIL,
    password: str = _TEST_PASSWORD,
    display_name: str = "Test User",
    account_status: AccountStatus = AccountStatus.ACTIVE,
    is_email_verified: bool = True,
) -> tuple[User, str]:
    """Create a test user with hashed credentials in the given session.

    This function is idempotent within a single session: if the user already
    exists (by email), it is returned without creating a duplicate.

    Args:
        db:               SQLAlchemy session bound to the test database.
        email:            Email address for the test user.
        password:         Plaintext password (will be hashed).
        display_name:     Display name shown in the UI.
        account_status:   Initial account status.
        is_email_verified: Whether the email is pre-verified.

    Returns:
        Tuple of (User ORM instance, plaintext password used).
    """
    from core.config.settings import Settings
    from modules.auth.repositories.user_repository import UserRepository

    settings = Settings(**_MINIMAL_SETTINGS_KWARGS)
    password_svc = PasswordService(settings)
    user_repo = UserRepository(db)

    existing = user_repo.find_by_email(email)
    if existing is not None:
        return existing, password

    user = User(
        email=email.lower().strip(),
        display_name=display_name,
        account_status=account_status,
        is_email_verified=is_email_verified,
    )
    db.add(user)
    db.flush()

    password_hash = password_svc.hash_password(password)
    credentials = UserCredentials(
        user_id=user.id,
        password_hash=password_hash,
        password_history=[],
        last_changed_at=datetime.now(UTC),
    )
    db.add(credentials)
    db.commit()
    db.refresh(user)

    return user, password
