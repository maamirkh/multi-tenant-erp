"""Users & Roles module exception hierarchy.

All exceptions inherit from ``ApplicationException`` via the module-level
``UsersRolesException`` base so the global FastAPI exception handler converts
them to typed ``ErrorResponse`` JSON automatically.

Error codes and HTTP status codes match plan.md Section 18.1 exactly.
No imports from SQLAlchemy, FastAPI, or Starlette — this module is pure Python.
"""

from __future__ import annotations

from core.exceptions.base import ApplicationException


class UsersRolesException(ApplicationException):
    """Base exception for all Users & Roles module errors."""

    def __init__(
        self,
        message: str,
        code: str = "USERS_ROLES_ERROR",
        details: dict[str, object] | None = None,
        http_status: int = 500,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            details=details,
            http_status=http_status,
        )


# ── 400 Bad Request ──────────────────────────────────────────────────────────


class AvatarTooLargeError(UsersRolesException):
    """Avatar file exceeds the configured maximum size."""

    def __init__(
        self,
        message: str = "Avatar file exceeds the maximum allowed size.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message, code="AVATAR_TOO_LARGE", details=details, http_status=400
        )


class AvatarInvalidFormatError(UsersRolesException):
    """Avatar file has an unsupported MIME type or extension."""

    def __init__(
        self,
        message: str = "Unsupported avatar file format.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="AVATAR_INVALID_FORMAT",
            details=details,
            http_status=400,
        )


class AvatarInvalidContentError(UsersRolesException):
    """Avatar file's magic bytes do not match the declared content type."""

    def __init__(
        self,
        message: str = "Avatar file content does not match its declared type.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="AVATAR_INVALID_CONTENT",
            details=details,
            http_status=400,
        )


# ── 403 Forbidden ────────────────────────────────────────────────────────────


class InsufficientRankError(UsersRolesException):
    """Actor's role rank is not high enough to manage the target member."""

    def __init__(
        self,
        message: str = "You do not have sufficient rank to perform this action.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message, code="INSUFFICIENT_RANK", details=details, http_status=403
        )


class SystemRoleImmutableError(UsersRolesException):
    """Attempted to modify or delete a system-defined role."""

    def __init__(
        self,
        message: str = "System roles cannot be modified or deleted.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="SYSTEM_ROLE_IMMUTABLE",
            details=details,
            http_status=403,
        )


# ── 404 Not Found ────────────────────────────────────────────────────────────


class MemberNotFoundError(UsersRolesException):
    """Requested company member does not exist or is not visible."""

    def __init__(
        self,
        message: str = "Company member not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message, code="MEMBER_NOT_FOUND", details=details, http_status=404
        )


class RoleNotFoundError(UsersRolesException):
    """Requested role does not exist in this company."""

    def __init__(
        self,
        message: str = "Role not found.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message, code="ROLE_NOT_FOUND", details=details, http_status=404
        )


# ── 409 Conflict ─────────────────────────────────────────────────────────────


class MemberAlreadyExistsError(UsersRolesException):
    """A membership already exists for this user in this company."""

    def __init__(
        self,
        message: str = "A membership already exists for this user in this company.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="MEMBER_ALREADY_EXISTS",
            details=details,
            http_status=409,
        )


class MemberLimitExceededError(UsersRolesException):
    """Company has reached the maximum number of members."""

    def __init__(
        self,
        message: str = "Company has reached the maximum number of members.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="MEMBER_LIMIT_EXCEEDED",
            details=details,
            http_status=409,
        )


class InvalidStatusTransitionError(UsersRolesException):
    """Requested membership status change is not permitted from the current status."""

    def __init__(
        self,
        message: str = "This status transition is not permitted.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="INVALID_STATUS_TRANSITION",
            details=details,
            http_status=409,
        )


class LastOwnerProtectionError(UsersRolesException):
    """Cannot remove or demote the last Owner of a company."""

    def __init__(
        self,
        message: str = "Cannot remove or change the role of the last company owner.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="LAST_OWNER_PROTECTION",
            details=details,
            http_status=409,
        )


class CannotModifyOwnRoleError(UsersRolesException):
    """A member cannot change their own role assignment."""

    def __init__(
        self,
        message: str = "You cannot modify your own role assignment.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="CANNOT_MODIFY_OWN_ROLE",
            details=details,
            http_status=409,
        )


class RoleNameConflictError(UsersRolesException):
    """Role name or slug already exists in this company."""

    def __init__(
        self,
        message: str = "A role with this name already exists in this company.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message, code="ROLE_NAME_CONFLICT", details=details, http_status=409
        )


class RoleHasActiveAssignmentsError(UsersRolesException):
    """Cannot delete a role that has members assigned to it."""

    def __init__(
        self,
        message: str = "Cannot delete a role that has active member assignments.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="ROLE_HAS_ACTIVE_ASSIGNMENTS",
            details=details,
            http_status=409,
        )


class CustomRoleLimitExceededError(UsersRolesException):
    """Company has reached the maximum number of custom roles."""

    def __init__(
        self,
        message: str = "Company has reached the maximum number of custom roles.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="CUSTOM_ROLE_LIMIT_EXCEEDED",
            details=details,
            http_status=409,
        )


class EmployeeIdConflictError(UsersRolesException):
    """Employee ID is already in use within this company."""

    def __init__(
        self,
        message: str = "This employee ID is already in use within the company.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="EMPLOYEE_ID_CONFLICT",
            details=details,
            http_status=409,
        )


# ── 410 Gone ─────────────────────────────────────────────────────────────────


class InvitationExpiredError(UsersRolesException):
    """Membership invitation has expired and can no longer be accepted."""

    def __init__(
        self,
        message: str = "This invitation has expired.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message, code="INVITATION_EXPIRED", details=details, http_status=410
        )


# ── 422 Unprocessable Entity ─────────────────────────────────────────────────


class InvalidRoleRankError(UsersRolesException):
    """Custom role rank is outside the permitted range."""

    def __init__(
        self,
        message: str = "Role rank is outside the permitted range.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message, code="INVALID_ROLE_RANK", details=details, http_status=422
        )


class HireDateInFutureError(UsersRolesException):
    """Hire date is set to a future date, which is not permitted."""

    def __init__(
        self,
        message: str = "Hire date cannot be in the future.",
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="HIRE_DATE_IN_FUTURE",
            details=details,
            http_status=422,
        )
