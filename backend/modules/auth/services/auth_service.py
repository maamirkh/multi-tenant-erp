"""AuthService — core authentication business logic.

Implements all authentication flows:
  - Login (with lockout, auto-unlock, audit logging)
  - Logout (single session)
  - Token refresh (rotation)
  - Current user profile
  - Forgot password (anti-enumeration)
  - Reset password (token consumption, history, session revocation)
  - Change password (current-password verify, history, session revocation)
  - Email verification

All methods return Pydantic schema instances; ORM models are never
returned to calling routers.

Security invariants enforced here:
  - Timing-consistent error responses for unknown email vs wrong password.
  - Anti-enumeration: forgot-password always returns successfully.
  - Password history prevents reuse.
  - Account auto-unlock after lockout duration expires.
  - All significant events emit audit log entries.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from core.auth.exceptions import (
    AccountInactiveException,
    AccountLockedException,
    AuthenticationException,
)
from core.config.settings import Settings
from core.utils.datetime import utcnow
from modules.auth.models.enums import AccountStatus, AuditEventType
from modules.auth.models.user import User
from modules.auth.models.user_credential import UserCredentials
from modules.auth.repositories.refresh_token_repository import RefreshTokenRepository
from modules.auth.repositories.session_repository import SessionRepository
from modules.auth.repositories.user_credential_repository import (
    UserCredentialRepository,
)
from modules.auth.repositories.user_repository import UserRepository
from modules.auth.services.audit_service import AuditService
from modules.auth.services.email_service import EmailService
from modules.auth.services.jwt_service import JWTService
from modules.auth.services.password_service import PasswordService
from modules.auth.services.token_service import TokenService

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication business logic service.

    Args:
        db:       SQLAlchemy session for this request.
        settings: Application settings.
    """

    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._user_repo = UserRepository(db)
        self._cred_repo = UserCredentialRepository(db)
        self._session_repo = SessionRepository(db)
        self._refresh_repo = RefreshTokenRepository(db)
        self._password_svc = PasswordService(settings)
        self._jwt_svc = JWTService(settings)
        self._token_svc = TokenService(db, settings)
        self._audit_svc = AuditService(db)
        self._email_svc = EmailService()

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(
        self,
        email: str,
        password: str,
        remember_me: bool,
        request: Request,
    ) -> LoginResult:
        """Authenticate a user and return access + refresh tokens.

        Flow (per plan.md §7.1):
          1. Normalise email.
          2. Find user — return generic error if not found (anti-enumeration).
          3. Check account status (DELETED → generic error; INACTIVE → 403).
          4. Auto-unlock if lockout duration has elapsed.
          5. Check if still locked → 423.
          6. Verify Argon2 hash.
          7. On mismatch: increment counter, lock if threshold reached, audit.
          8. On match: reset counter, create session, issue tokens, audit.

        Raises:
            AuthenticationException:   Invalid credentials or deleted account.
            AccountLockedException:    Account is temporarily locked.
            AccountInactiveException:  Account is administratively inactive.
        """
        normalised_email = PasswordService.normalise_email(email)

        user = self._user_repo.find_by_email(normalised_email)

        if user is None:
            # Anti-enumeration: identical response to wrong password.
            self._audit_svc.emit(
                AuditEventType.LOGIN_FAILURE,
                "FAILURE",
                request,
                reason="USER_NOT_FOUND",
            )
            raise AuthenticationException()

        self._check_account_status(user, request)

        credentials = self._cred_repo.get_by_user_id(user.id)

        if not self._password_svc.verify_password(password, credentials.password_hash):
            self._handle_failed_login(user, request)

        # Successful login path.
        self._user_repo.update_failed_login_count(user.id, 0)

        session = self._session_repo.create_session(
            user_id=user.id,
            ip_address=AuditService._extract_ip(request),
            user_agent=request.headers.get("user-agent"),
        )

        access_token = self._jwt_svc.create_access_token(
            user_id=user.id,
            email=user.email,
            session_id=session.id,
        )

        raw_refresh_token, _ = self._token_svc.create_refresh_token(
            user_id=user.id,
            session_id=session.id,
            remember_me=remember_me,
            ip=AuditService._extract_ip(request),
            user_agent=request.headers.get("user-agent"),
        )

        self._audit_svc.emit(
            AuditEventType.LOGIN_SUCCESS,
            "SUCCESS",
            request,
            user_id=user.id,
        )

        expire_seconds = self._settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return LoginResult(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            token_type="bearer",
            expires_in=expire_seconds,
        )

    def _check_account_status(self, user: User, request: Request) -> None:
        """Enforce account status rules; raises appropriate exceptions."""
        if user.account_status == AccountStatus.DELETED:
            # Anti-enumeration: deleted accounts behave like unknown emails.
            self._audit_svc.emit(
                AuditEventType.LOGIN_FAILURE,
                "FAILURE",
                request,
                user_id=user.id,
                reason="ACCOUNT_DELETED",
            )
            raise AuthenticationException()

        if user.account_status == AccountStatus.INACTIVE:
            self._audit_svc.emit(
                AuditEventType.LOGIN_FAILURE,
                "FAILURE",
                request,
                user_id=user.id,
                reason="ACCOUNT_INACTIVE",
            )
            raise AccountInactiveException()

        if user.account_status == AccountStatus.LOCKED:
            now = utcnow()
            if user.locked_until and user.locked_until <= now:
                # Lockout duration has elapsed — auto-unlock.
                self._user_repo.unlock_account(user.id)
                self._audit_svc.emit(
                    AuditEventType.ACCOUNT_LOCKED,
                    "SUCCESS",
                    request,
                    user_id=user.id,
                    reason="AUTO_UNLOCK",
                )
                # Refresh user state after unlock.
                user.account_status = AccountStatus.ACTIVE
                user.failed_login_count = 0
            else:
                unlocks_at = (
                    user.locked_until.isoformat() if user.locked_until else None
                )
                self._audit_svc.emit(
                    AuditEventType.LOGIN_FAILURE,
                    "FAILURE",
                    request,
                    user_id=user.id,
                    reason="ACCOUNT_LOCKED",
                )
                raise AccountLockedException(details={"unlocks_at": unlocks_at})

    def _handle_failed_login(self, user: User, request: Request) -> None:
        """Increment failed-login counter, lock if threshold reached, then raise."""
        new_count = user.failed_login_count + 1
        self._user_repo.update_failed_login_count(user.id, new_count)

        if new_count >= self._settings.AUTH_LOCKOUT_THRESHOLD:
            locked_until = utcnow() + timedelta(
                minutes=self._settings.AUTH_LOCKOUT_DURATION_MINUTES
            )
            self._user_repo.lock_account(user.id, locked_until)
            self._audit_svc.emit(
                AuditEventType.ACCOUNT_LOCKED,
                "FAILURE",
                request,
                user_id=user.id,
                reason=f"FAILED_LOGIN_ATTEMPTS_{new_count}",
            )

        self._audit_svc.emit(
            AuditEventType.LOGIN_FAILURE,
            "FAILURE",
            request,
            user_id=user.id,
            reason="INVALID_PASSWORD",
        )
        raise AuthenticationException()

    # ------------------------------------------------------------------
    # Logout
    # ------------------------------------------------------------------

    def logout(
        self,
        user_id: UUID,
        session_id: UUID,
        request: Request,
    ) -> None:
        """Revoke the current session and all its refresh tokens.

        Args:
            user_id:    The authenticated user's UUID.
            session_id: The session ID from the JWT ``sid`` claim.
            request:    Current FastAPI request (for audit logging).
        """
        from modules.auth.repositories.refresh_token_repository import (
            RefreshTokenRepository,
        )

        refresh_repo = RefreshTokenRepository(self._db)
        refresh_repo.revoke_all_by_session(session_id)
        self._session_repo.revoke_session(session_id)

        self._audit_svc.emit(
            AuditEventType.LOGOUT,
            "SUCCESS",
            request,
            user_id=user_id,
        )

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def refresh(
        self,
        raw_refresh_token: str,
        request: Request,
    ) -> RefreshResult:
        """Rotate a refresh token and issue a new access token.

        Args:
            raw_refresh_token: Raw refresh token from the client request.
            request:           Current FastAPI request.

        Returns:
            ``RefreshResult`` with new access and refresh tokens.

        Raises:
            TokenExpiredException:  Refresh token is expired.
            InvalidTokenException:  Refresh token is invalid or revoked.
            AccountLockedException: User account is locked.
            AccountInactiveException: User account is inactive.
        """
        new_raw_refresh, new_record = self._token_svc.rotate_refresh_token(
            old_raw_token=raw_refresh_token,
            ip=AuditService._extract_ip(request),
            user_agent=request.headers.get("user-agent"),
        )

        user = self._user_repo.get_by_id(new_record.user_id)
        if user.account_status != AccountStatus.ACTIVE:
            raise AccountInactiveException()

        new_access_token = self._jwt_svc.create_access_token(
            user_id=user.id,
            email=user.email,
            session_id=new_record.session_id,
        )

        self._audit_svc.emit(
            AuditEventType.TOKEN_REFRESHED,
            "SUCCESS",
            request,
            user_id=user.id,
        )

        expire_seconds = self._settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60

        return RefreshResult(
            access_token=new_access_token,
            refresh_token=new_raw_refresh,
            expires_in=expire_seconds,
        )

    # ------------------------------------------------------------------
    # Current user profile
    # ------------------------------------------------------------------

    def get_current_user_profile(self, user_id: UUID) -> UserProfileResult:
        """Return the authenticated user's profile data.

        Credential data (password hash, history) is NEVER included.

        Args:
            user_id: UUID from the validated JWT ``sub`` claim.

        Returns:
            ``UserProfileResult`` with safe user fields only.
        """
        user = self._user_repo.get_by_id(user_id)
        return UserProfileResult(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            account_status=user.account_status.value,
            is_email_verified=user.is_email_verified,
            created_at=user.created_at,
        )

    # ------------------------------------------------------------------
    # Forgot / reset password
    # ------------------------------------------------------------------

    def forgot_password(self, email: str, request: Request) -> None:
        """Initiate the password reset flow.

        Always returns successfully (anti-enumeration FR-026).
        Only generates and stores a token when the email belongs to an active account.

        Args:
            email:   Submitted email address.
            request: Current FastAPI request (for audit logging and IP capture).
        """
        normalised_email = PasswordService.normalise_email(email)
        user = self._user_repo.find_by_email(normalised_email)

        if user is None or user.account_status in (
            AccountStatus.DELETED,
            AccountStatus.INACTIVE,
        ):
            # Always audit the attempt even for unknown emails, but without user_id.
            self._audit_svc.emit(
                AuditEventType.PASSWORD_RESET_REQUESTED,
                "FAILURE",
                request,
                reason="USER_NOT_FOUND_OR_INACTIVE",
            )
            return  # Anti-enumeration: no error raised.

        raw_token = self._token_svc.create_password_reset_token(
            user_id=user.id,
            ip=AuditService._extract_ip(request),
        )
        self._email_svc.send_password_reset_email(email=user.email, token=raw_token)

        self._audit_svc.emit(
            AuditEventType.PASSWORD_RESET_REQUESTED,
            "SUCCESS",
            request,
            user_id=user.id,
        )

    def reset_password(
        self,
        raw_token: str,
        new_password: str,
        request: Request,
    ) -> None:
        """Complete the password reset flow.

        Flow:
          1. Consume the reset token (raises on invalid/expired).
          2. Validate new password complexity and history.
          3. Hash new password, update credential record.
          4. Revoke all refresh tokens for the user.
          5. Emit audit event.

        Args:
            raw_token:    Raw reset token from the reset URL.
            new_password: Candidate new password (validated here).
            request:      Current FastAPI request.

        Raises:
            InvalidTokenException:  Token is invalid or consumed.
            TokenExpiredException:  Token is expired.
            ValidationException:    New password fails policy checks.
        """
        reset_record = self._token_svc.consume_password_reset_token(raw_token)
        user_id = reset_record.user_id

        credentials: UserCredentials = self._cred_repo.get_by_user_id(user_id)

        self._password_svc.validate_new_password(
            plain=new_password,
            email="",
            history=credentials.password_history,
        )

        new_hash = self._password_svc.hash_password(new_password)
        updated_history = self._password_svc.build_updated_history(
            current_hash=credentials.password_hash,
            existing_history=credentials.password_history,
        )

        self._cred_repo.update_password_hash(
            user_id=user_id,
            new_hash=new_hash,
            history=updated_history,
            changed_at=utcnow(),
        )

        self._refresh_repo.revoke_all_by_user(user_id)
        self._session_repo.revoke_all_by_user(user_id)

        self._audit_svc.emit(
            AuditEventType.PASSWORD_RESET_COMPLETED,
            "SUCCESS",
            request,
            user_id=user_id,
        )

    # ------------------------------------------------------------------
    # Change password
    # ------------------------------------------------------------------

    def change_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
        request: Request,
    ) -> None:
        """Change password for an authenticated user.

        Flow:
          1. Load credentials.
          2. Verify current password.
          3. Validate new password policy and history.
          4. Hash and persist new password.
          5. Revoke all refresh tokens and sessions.
          6. Emit audit event.

        Raises:
            AuthenticationException: If current password does not match.
            ValidationException:     If new password fails policy.
        """
        credentials = self._cred_repo.get_by_user_id(user_id)

        if not self._password_svc.verify_password(
            current_password, credentials.password_hash
        ):
            self._audit_svc.emit(
                AuditEventType.PASSWORD_CHANGED,
                "FAILURE",
                request,
                user_id=user_id,
                reason="WRONG_CURRENT_PASSWORD",
            )
            raise AuthenticationException(
                message="Current password is incorrect.",
                details={"field": "current_password"},
            )

        user = self._user_repo.get_by_id(user_id)
        self._password_svc.validate_new_password(
            plain=new_password,
            email=user.email,
            history=credentials.password_history,
        )

        new_hash = self._password_svc.hash_password(new_password)
        updated_history = self._password_svc.build_updated_history(
            current_hash=credentials.password_hash,
            existing_history=credentials.password_history,
        )

        self._cred_repo.update_password_hash(
            user_id=user_id,
            new_hash=new_hash,
            history=updated_history,
            changed_at=utcnow(),
        )

        self._refresh_repo.revoke_all_by_user(user_id)
        self._session_repo.revoke_all_by_user(user_id)

        self._audit_svc.emit(
            AuditEventType.PASSWORD_CHANGED,
            "SUCCESS",
            request,
            user_id=user_id,
        )

    # ------------------------------------------------------------------
    # Email verification
    # ------------------------------------------------------------------

    def verify_email(self, raw_token: str, request: Request) -> None:
        """Mark a user's email as verified.

        Args:
            raw_token: Raw verification token from the verification URL.
            request:   Current FastAPI request.

        Raises:
            InvalidTokenException:  Token is invalid or already consumed.
            TokenExpiredException:  Token has expired.
        """
        record = self._token_svc.consume_email_verification_token(raw_token)

        self._user_repo.mark_email_verified(record.user_id)

        self._audit_svc.emit(
            AuditEventType.EMAIL_VERIFIED,
            "SUCCESS",
            request,
            user_id=record.user_id,
        )


# ------------------------------------------------------------------
# Result value objects (keep schemas out of the service layer)
# ------------------------------------------------------------------


class LoginResult:
    """Lightweight value object returned by ``AuthService.login``."""

    __slots__ = ("access_token", "refresh_token", "token_type", "expires_in")

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        token_type: str,
        expires_in: int,
    ) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_type = token_type
        self.expires_in = expires_in


class RefreshResult:
    """Lightweight value object returned by ``AuthService.refresh``."""

    __slots__ = ("access_token", "refresh_token", "expires_in")

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        expires_in: int,
    ) -> None:
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in


class UserProfileResult:
    """Lightweight value object returned by ``AuthService.get_current_user_profile``."""

    __slots__ = (
        "user_id",
        "email",
        "display_name",
        "account_status",
        "is_email_verified",
        "created_at",
    )

    def __init__(
        self,
        user_id: UUID,
        email: str,
        display_name: str,
        account_status: str,
        is_email_verified: bool,
        created_at: datetime,
    ) -> None:
        self.user_id = user_id
        self.email = email
        self.display_name = display_name
        self.account_status = account_status
        self.is_email_verified = is_email_verified
        self.created_at = created_at
