"""FastAPI dependency injection functions for the Platform Administration
module.

Empty at Phase 3 (module-skeleton stage, T032) — no Platform authentication
dependency (``require_platform_permission`` or equivalent) exists yet.
Phase 4 (Platform Authentication / Session Boundary) adds the Platform
session/token dependencies; Phase 5 adds RBAC enforcement dependencies.

All DI factories will be synchronous, matching the sync ``Session`` /
``get_db`` pattern used throughout the backend (plan.md §4).
"""

from __future__ import annotations
