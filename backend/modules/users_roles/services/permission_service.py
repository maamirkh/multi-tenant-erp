"""PermissionService — read-only access to the permission catalogue.

Permissions are global (not company-scoped) and seeded by RoleSeedService.
This service provides list/lookup operations for the API layer.

Spec reference: tasks T049.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from modules.users_roles.models.permission import Permission
from modules.users_roles.repositories.permission_repository import (
    PermissionRepository,
)

logger = logging.getLogger(__name__)


class PermissionService:
    """Read-only permission catalogue operations.

    Args:
        permission_repo: Injected ``PermissionRepository``.
    """

    def __init__(self, permission_repo: PermissionRepository) -> None:
        self._permission_repo = permission_repo

    def list_all_permissions(self) -> list[dict[str, Any]]:
        """Return all permissions grouped by module.

        Returns:
            List of dicts with keys ``module`` and ``permissions``.
        """
        all_perms = self._permission_repo.list_all()
        groups: dict[str, list[Permission]] = defaultdict(list)
        for perm in all_perms:
            groups[perm.module].append(perm)

        return [
            {"module": module, "permissions": perms}
            for module, perms in sorted(groups.items())
        ]

    def get_permission_by_code(self, code: str) -> Permission | None:
        """Return a single permission by its code, or ``None``."""
        return self._permission_repo.get_by_code(code)

    def list_permissions_by_module(self, module: str) -> list[Permission]:
        """Return all permissions for a specific module."""
        return self._permission_repo.list_by_module(module)
