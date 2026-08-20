"""PlatformAuthService — Platform authentication business logic.

Authenticates against the **same** `User.password_hash` (shared credential
identity, plan.md §3.1) — no second password system — then requires an
**active** `PlatformAdministrator` row. Structurally separate session/
token system from tenant auth: `PlatformSession`/`PlatformRefreshToken`,
never `sessions`/`refresh_tokens` (BR-9A-003).

Anti-enumeration (T049): an unknown email, a wrong password, and a
User with no active `PlatformAdministrator` all raise the *same* generic
`AuthenticationException` — none reveals whether the email exists as a
tenant user, or exists as a tenant user without Platform authority.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from core.auth.exceptions import AuthenticationException
from core.config.settings import Settings
from core.utils.datetime import utcnow
from modules.auth.repositories.user_credential_repository import (
    UserCredentialRepository,
)
from modules.auth.repositories.user_repository import UserRepository
from modules.auth.services.audit_service import AuditService
from modules.auth.services.password_service import PasswordService
from modules.platform_admin.repositories.platform_administrator_repository import (
    PlatformAdministratorRepository,
)
from modules.platform_admin.repositories.platform_refresh_token_repository import (
    PlatformRefreshTokenRepository,
)
from modules.platform_admin.repositories.platform_session_repository import (
    PlatformSessionRepository,
)
from modules.platform_admin.services.platform_jwt_service import PlatformJwtService

logger = logging.getLogger(__name__)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass
class PlatformLoginResult:
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


@dataclass
class PlatformRefreshResult:
    access_token: str
    refresh_token: str
    expires_in: int


class PlatformAuthService:
    """Platform authentication business logic service."""

    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._user_repo = UserRepository(db)
        self._cred_repo = UserCredentialRepository(db)
        self._password_svc = PasswordService(settings)
        self._admin_repo = PlatformAdministratorRepository(db)
        self._session_repo = PlatformSessionRepository(db)
        self._refresh_repo = PlatformRefreshTokenRepository(db)
        self._jwt_svc = PlatformJwtService(settings)

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self, email: str, password: str, request: Request) -> PlatformLoginResult:
        """Authenticate against `User.password_hash`, require an active
        `PlatformAdministrator`, and issue a Platform session + tokens.

        Raises:
            AuthenticationException: Invalid credentials, or a real tenant
                user with no active Platform authority — identical response
                in every case (anti-enumeration).
        """
        normalised_email = PasswordService.normalise_email(email)
        user = self._user_repo.find_by_email(normalised_email)

        if user is None:
            raise AuthenticationException()

        credentials = self._cred_repo.get_by_user_id(user.id)
        if not self._password_svc.verify_password(password, credentials.password_hash):
            raise AuthenticationException()

        administrator = self._admin_repo.get_by_user_id(user.id)
        if administrator is None or not administrator.is_active:
            # A real tenant user, correct password, but no active Platform
            # authority — same generic response as the two cases above.
            raise AuthenticationException()

        administrator.last_login_at = utcnow()

        expires_at = utcnow() + timedelta(
            days=self._settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        session = self._session_repo.create(
            platform_administrator_id=administrator.id,
            expires_at=expires_at,
            ip_address=AuditService._extract_ip(request),
            user_agent=request.headers.get("user-agent"),
        )

        access_token = self._jwt_svc.create_access_token(
            platform_administrator_id=administrator.id, session_id=session.id
        )
        refresh_token = self._jwt_svc.create_refresh_token(
            platform_administrator_id=administrator.id, session_id=session.id
        )
        self._refresh_repo.create(
            session_id=session.id,
            token_hash=_sha256(refresh_token),
            expires_at=expires_at,
        )

        self._db.commit()

        expire_seconds = self._settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        return PlatformLoginResult(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expire_seconds,
        )

    # ------------------------------------------------------------------
    # Refresh (rotate-on-use)
    # ------------------------------------------------------------------

    def refresh(
        self, raw_refresh_token: str, request: Request
    ) -> PlatformRefreshResult:
        """Rotate a Platform refresh token and issue a new access token.

        Rejects a revoked `PlatformSession` or a deactivated administrator
        (T050's acceptance) — the same session is reused, never re-created,
        matching the tenant `refresh()` convention that keeps
        `Session.created_at` unchanged across refreshes (ADR-6 precedent).

        Raises:
            AuthenticationException: Token not `platform_refresh`-typed,
                unknown/revoked/expired token, revoked session, or
                inactive administrator.
        """
        claims = self._jwt_svc.decode_token(raw_refresh_token)
        if claims.get("typ") != "platform_refresh":
            raise AuthenticationException(
                message="Invalid or malformed Platform authentication token."
            )

        old_hash = _sha256(raw_refresh_token)
        old_token = self._refresh_repo.find_by_token_hash(old_hash)
        if old_token is None or old_token.is_revoked:
            raise AuthenticationException(
                message="Refresh token is invalid or has been revoked."
            )

        session = self._session_repo.get_by_id(old_token.session_id)
        if session is None or session.is_revoked:
            raise AuthenticationException(message="Platform session has been revoked.")

        administrator = self._admin_repo.get_by_id(session.platform_administrator_id)
        if administrator is None or not administrator.is_active:
            raise AuthenticationException(
                message="Platform Administrator account is not active."
            )

        # Revoke the old refresh token (rotate-on-use).
        old_token.is_revoked = True
        old_token.revoked_at = utcnow()
        self._db.flush()

        new_access_token = self._jwt_svc.create_access_token(
            platform_administrator_id=administrator.id, session_id=session.id
        )
        new_refresh_token = self._jwt_svc.create_refresh_token(
            platform_administrator_id=administrator.id, session_id=session.id
        )
        new_expires_at = utcnow() + timedelta(
            days=self._settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
        )
        self._refresh_repo.create(
            session_id=session.id,
            token_hash=_sha256(new_refresh_token),
            expires_at=new_expires_at,
        )

        self._db.commit()

        expire_seconds = self._settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        return PlatformRefreshResult(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=expire_seconds,
        )

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    def logout(self, session_id: UUID, request: Request) -> None:
        """Revoke the current `PlatformSession` and all its refresh tokens."""
        self._refresh_repo.revoke_all_for_session(session_id)
        self._session_repo.revoke(session_id)
        self._db.commit()
