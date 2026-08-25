"""Installments module API router.

Phase 1 (module foundation): empty router, no endpoints yet. Endpoint
groups are added incrementally starting Phase 2 (Configuration & Plans),
mirroring ``modules/crm/router.py``'s own incremental-growth convention.
Not yet mounted into ``api/v1/router.py`` — mounting happens once the
first real endpoint group exists.

Spec ref: specs/010-installments/plan.md §23.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["installments"])
