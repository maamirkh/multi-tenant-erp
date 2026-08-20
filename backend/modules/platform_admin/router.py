"""Platform Administration module API router.

Empty at Phase 3 (module-skeleton stage, T032) — no route exists yet.
Not mounted into ``api/v1/router.py``; that happens once the first real
Platform routes exist (Phase 4's auth routes, per
``contracts/platform-admin-v1.yaml``).

Router discipline (once populated): routers delegate to the service
layer — no business logic in the router (plan.md §10 API Contract Lock).
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
