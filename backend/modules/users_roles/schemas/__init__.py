"""Users & Roles schemas package — exports all schema classes."""

from modules.users_roles.schemas.invitation import InvitationResponse
from modules.users_roles.schemas.member import (
    AddMemberRequest,
    MemberDetailResponse,
    MemberListItem,
    MemberResponse,
    RoleSummary,
    UpdateMemberRequest,
)
from modules.users_roles.schemas.permission import (
    PermissionGroupResponse,
    PermissionResponse,
)
from modules.users_roles.schemas.preference import (
    PreferenceResponse,
    UpdatePreferenceRequest,
)
from modules.users_roles.schemas.profile import (
    AvatarUploadResponse,
    ProfileResponse,
    UpdateProfileRequest,
)
from modules.users_roles.schemas.role import (
    CreateRoleRequest,
    RoleDetailResponse,
    RoleListItem,
    RoleResponse,
    UpdateRoleRequest,
)

__all__ = [
    "AddMemberRequest",
    "AvatarUploadResponse",
    "CreateRoleRequest",
    "InvitationResponse",
    "MemberDetailResponse",
    "MemberListItem",
    "MemberResponse",
    "PermissionGroupResponse",
    "PermissionResponse",
    "PreferenceResponse",
    "ProfileResponse",
    "RoleDetailResponse",
    "RoleListItem",
    "RoleResponse",
    "RoleSummary",
    "UpdateMemberRequest",
    "UpdatePreferenceRequest",
    "UpdateProfileRequest",
    "UpdateRoleRequest",
]
