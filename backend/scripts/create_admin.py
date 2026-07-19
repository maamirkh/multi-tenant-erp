#!/usr/bin/env python3
"""Create an initial administrator account.

Environment variables
---------------------
ADMIN_EMAIL      (required) Email address of the admin user.
ADMIN_PASSWORD   (required) Plaintext password (must satisfy the password policy).
ADMIN_NAME       (optional) Display name (default: "Administrator").

This script is idempotent: running it multiple times with the same ADMIN_EMAIL
will not create duplicate users; if the user already exists the script exits
successfully without any modifications.

Usage
-----
From the backend directory::

    ADMIN_EMAIL=admin@example.com \\
    ADMIN_PASSWORD='S3cur3P@ssw0rd!' \\
    ADMIN_NAME='System Administrator' \\
    python scripts/create_admin.py
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Ensure the backend package root is on sys.path when run directly.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Entry point — read env vars and create the admin user."""
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "").strip()
    display_name = os.environ.get("ADMIN_NAME", "Administrator").strip()

    if not email:
        logger.error("ADMIN_EMAIL environment variable is required.")
        sys.exit(1)
    if not password:
        logger.error("ADMIN_PASSWORD environment variable is required.")
        sys.exit(1)

    # Import application modules after path setup.
    from sqlalchemy.orm import Session

    from core.config.settings import get_settings
    from core.database.engine import engine
    from core.utils.datetime import utcnow
    from modules.auth.models.enums import AccountStatus
    from modules.auth.models.user import User
    from modules.auth.models.user_credential import UserCredentials
    from modules.auth.repositories.user_repository import UserRepository
    from modules.auth.services.password_service import PasswordService

    settings = get_settings()
    password_svc = PasswordService(settings)

    # Validate password complexity before touching the database.
    try:
        password_svc.validate_new_password(password, email, [])
    except Exception as exc:  # noqa: BLE001
        logger.error("Password does not meet policy requirements: %s", exc)
        sys.exit(1)

    with Session(engine) as db:
        user_repo = UserRepository(db)

        existing = user_repo.find_by_email(email)
        if existing is not None:
            logger.info(
                "Admin user already exists — no changes made.",
            )
            return

        # Create the user record.
        user = User(
            email=email,
            display_name=display_name,
            account_status=AccountStatus.ACTIVE,
            is_email_verified=True,
        )
        db.add(user)
        db.flush()

        # Hash the password and create credentials.
        password_hash = password_svc.hash_password(password)
        credentials = UserCredentials(
            user_id=user.id,
            password_hash=password_hash,
            password_history=[],
            last_changed_at=utcnow(),
        )
        db.add(credentials)
        db.commit()

        logger.info(
            "Administrator account created successfully. email=%s user_id=%s",
            email,
            user.id,
        )


if __name__ == "__main__":
    main()
