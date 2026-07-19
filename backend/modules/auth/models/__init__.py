"""Authentication domain ORM models.

Importing this package registers all auth models with SQLAlchemy's mapper
registry and populates ``Base.metadata`` so that Alembic ``--autogenerate``
discovers every auth table automatically.

Usage in ``migrations/env.py``::

    import modules.auth.models  # noqa: F401  — registers all auth models
"""

from modules.auth.models.audit_log import AuditLog
from modules.auth.models.email_verification_token import EmailVerificationToken
from modules.auth.models.enums import AccountStatus, AuditEventType
from modules.auth.models.password_reset_token import PasswordResetToken
from modules.auth.models.refresh_token import RefreshToken
from modules.auth.models.session import Session
from modules.auth.models.user import User
from modules.auth.models.user_credential import UserCredentials

__all__ = [
    # Enums
    "AccountStatus",
    "AuditEventType",
    # Models
    "User",
    "UserCredentials",
    "Session",
    "RefreshToken",
    "PasswordResetToken",
    "EmailVerificationToken",
    "AuditLog",
]
