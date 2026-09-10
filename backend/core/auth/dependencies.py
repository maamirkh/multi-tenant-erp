"""Real JWT-based FastAPI authentication dependencies.

Replaces the stub dependencies in ``core/auth/interfaces.py`` with full
implementations that validate JWTs, load users from the database, and
enforce account status.

Usage::

    from core.auth.dependencies import get_current_user, require_authenticated

    @router.get("/me")
    async def get_me(user: CurrentUser = Depends(require_authenticated)):
        ...

Dependency chain:
    Authorization header
        → JWTService.decode_access_token()
        → UserRepository.get_by_id_or_none()
        → account status checks
        → CurrentUser populated
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from core.auth.exceptions import AccountInactiveException, AccountLockedException
from core.auth.interfaces import CurrentUser
from core.config.settings import Settings, get_settings
from core.database.session import get_db
from core.exceptions.base import UnauthorizedException
from core.logging.setup import SESSION_ID_CONTEXT, USER_ID_CONTEXT
from modules.auth.models.enums import AccountStatus
from modules.auth.repositories.user_repository import UserRepository
from modules.auth.services.jwt_service import JWTService

logger = logging.getLogger(__name__)


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """Extract and validate the JWT from the Authorization header.

    Returns an unauthenticated ``CurrentUser`` when no token is present
    (for optional-auth routes).  Protected routes must use
    ``require_authenticated`` which enforces ``is_authenticated == True``.

    Raises:
        UnauthorizedException:    Bearer token is missing or malformed header.
        TokenExpiredException:    Token is expired.
        AuthenticationException:  Token signature or claims are invalid.
        AccountLockedException:   User account is locked.
        AccountInactiveException: User account is inactive or deleted.
    """
    authorization: str | None = request.headers.get("Authorization")

    if not authorization:
        return CurrentUser(is_authenticated=False)

    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise UnauthorizedException(
            message="Invalid Authorization header format. Expected 'Bearer <token>'."
        )

    raw_token = parts[1].strip()
    if not raw_token:
        raise UnauthorizedException(message="Bearer token is empty.")

    jwt_svc = JWTService(settings)
    claims = jwt_svc.decode_access_token(raw_token)

    user_id: UUID = jwt_svc.extract_user_id(claims)
    session_id: UUID = jwt_svc.extract_session_id(claims)

    user_repo = UserRepository(db)
    user = user_repo.get_by_id_or_none(user_id)

    if user is None:
        raise UnauthorizedException(
            message="User associated with token no longer exists."
        )

    if user.account_status == AccountStatus.LOCKED:
        from core.utils.datetime import utcnow

        if user.locked_until and user.locked_until <= utcnow():
            pass  # Will be auto-unlocked on next login attempt
        else:
            unlocks_at = user.locked_until.isoformat() if user.locked_until else None
            raise AccountLockedException(details={"unlocks_at": unlocks_at})

    if user.account_status in (AccountStatus.INACTIVE, AccountStatus.DELETED):
        raise AccountInactiveException()

    # Propagate identity into structured log context for the remainder of this request.
    USER_ID_CONTEXT.set(str(user.id))
    SESSION_ID_CONTEXT.set(str(session_id))

    return CurrentUser(
        user_id=user.id,
        company_id=user.company_id,
        email=user.email,
        is_authenticated=True,
        roles=[],
        session_id=session_id,
    )


def require_authenticated(
    current_user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    """Dependency that enforces a valid, authenticated JWT.

    Raises:
        UnauthorizedException: If ``current_user.is_authenticated`` is False.
    """
    if not current_user.is_authenticated:
        raise UnauthorizedException(message="Authentication required.")
    return current_user


def require_user_id(user: CurrentUser) -> UUID:
    """Narrow ``CurrentUser.user_id`` (``UUID | None``, since ``CurrentUser``
    also represents the unauthenticated stub case) to a concrete ``UUID`` for
    callers downstream of ``require_authenticated``, where ``get_current_user``
    above always populates ``user_id=user.id`` before setting
    ``is_authenticated=True``. Raises rather than returning an invalid
    sentinel, so a caller that reaches this without going through
    ``require_authenticated`` fails loudly instead of passing ``None`` as an
    actor/owner id into an audit or ownership field.
    """
    if user.user_id is None:
        raise UnauthorizedException(message="Authentication required.")
    return user.user_id


def require_session_id(user: CurrentUser) -> UUID:
    """Narrow ``CurrentUser.session_id`` (``UUID | None``) the same way
    ``require_user_id`` narrows ``user_id`` — see its docstring.
    """
    if user.session_id is None:
        raise UnauthorizedException(message="Authentication required.")
    return user.session_id
