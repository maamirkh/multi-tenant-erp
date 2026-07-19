"""Authentication and Authorization Abstractions.

This module defines ONLY interfaces (Protocol classes) and stub FastAPI
dependencies. No real authentication is performed here.

Design rule: Better Auth (or any future provider) must plug into these
abstractions without touching the Repository Layer or Service Layer.

Dependency injection chain:
    HTTP Request
        ↓
    AuthHookMiddleware  (middleware/auth_hook.py)
        ↓
    get_current_user()  ← defined here (stub)
        ↓
    Service Layer       (unchanged by auth implementation)
        ↓
    Repository Layer    (unchanged by auth implementation)
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from fastapi import HTTPException, Request, status

# ---------------------------------------------------------------------------
# Value objects / domain types
# ---------------------------------------------------------------------------


class CurrentUser:
    """Lightweight representation of an authenticated principal.

    Populated by the auth provider and consumed by Service layer dependencies.
    All fields are optional so that the stub (unauthenticated) case is valid
    during development; enforcement happens in the real implementation.
    """

    def __init__(
        self,
        *,
        user_id: UUID | None = None,
        company_id: UUID | None = None,
        email: str | None = None,
        roles: list[str] | None = None,
        is_authenticated: bool = False,
        session_id: UUID | None = None,
    ) -> None:
        self.user_id = user_id
        self.company_id = company_id
        self.email = email
        self.roles: list[str] = roles or []
        self.is_authenticated = is_authenticated
        self.session_id = session_id

    def __repr__(self) -> str:
        return (
            f"CurrentUser(user_id={self.user_id!r}, "
            f"company_id={self.company_id!r}, "
            f"session_id={self.session_id!r}, "
            f"is_authenticated={self.is_authenticated!r})"
        )


class SessionContext:
    """Carries request-scoped session metadata.

    Populated alongside CurrentUser; kept separate so that session
    concerns (expiry, refresh) are decoupled from identity.
    """

    def __init__(
        self,
        *,
        session_id: str | None = None,
        expires_at: Any = None,
    ) -> None:
        self.session_id = session_id
        self.expires_at = expires_at


# ---------------------------------------------------------------------------
# Provider Protocols — implement these to swap auth backends
# ---------------------------------------------------------------------------


@runtime_checkable
class AuthenticationProvider(Protocol):
    """Contract for any authentication backend (Better Auth, JWT, …)."""

    async def authenticate(self, request: Request) -> CurrentUser:
        """Extract and validate identity from the request.

        Returns a CurrentUser (may have is_authenticated=False for
        optional-auth routes). Raises HTTP 401 for invalid credentials.
        """
        ...


@runtime_checkable
class AuthorizationProvider(Protocol):
    """Contract for permission / role-based access control."""

    def has_permission(self, user: CurrentUser, permission: str) -> bool:
        """Return True if *user* holds *permission*."""
        ...

    def has_role(self, user: CurrentUser, role: str) -> bool:
        """Return True if *user* has *role*."""
        ...


# ---------------------------------------------------------------------------
# Permission / Role abstractions
# ---------------------------------------------------------------------------


class Permission:
    """Immutable named permission token.

    Usage::

        READ_INVENTORY = Permission("inventory:read")
        WRITE_INVENTORY = Permission("inventory:write")
    """

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return f"Permission({self._name!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Permission):
            return self._name == other._name
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._name)


class Role:
    """Immutable named role token.

    Usage::

        ADMIN = Role("admin")
        VIEWER = Role("viewer")
    """

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return f"Role({self._name!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Role):
            return self._name == other._name
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._name)


# ---------------------------------------------------------------------------
# FastAPI dependency stubs
# ---------------------------------------------------------------------------


async def get_current_user_stub(request: Request) -> CurrentUser:
    """Stub dependency — returns an unauthenticated CurrentUser.

    REPLACE IN AUTHENTICATION EPIC: wire this to the Better Auth adapter
    that reads the session from request.state (set by AuthHookMiddleware).

    FastAPI usage::

        @router.get("/me")
        async def get_me(user: CurrentUser = Depends(get_current_user_stub)):
            ...
    """
    return CurrentUser(is_authenticated=False)


async def require_authenticated_stub(request: Request) -> CurrentUser:
    """Stub dependency — always raises HTTP 401.

    Use this on endpoints that will require authentication once Better Auth
    is wired up. It acts as a compile-time reminder that the endpoint is
    protected and prevents accidental anonymous access in production before
    real auth is connected.
    """
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Auth provider not yet configured.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def require_permission_stub(permission: Permission) -> Any:
    """Factory that returns a stub dependency enforcing *permission*.

    REPLACE IN AUTHENTICATION EPIC with a real permission checker.

    FastAPI usage::

        @router.delete("/items/{id}")
        async def delete_item(
            _: None = Depends(require_permission_stub(DELETE_ITEMS)),
        ):
            ...
    """

    async def _dependency(request: Request) -> None:  # noqa: ARG001
        # Stub: no enforcement until auth is wired.
        return None

    return _dependency
