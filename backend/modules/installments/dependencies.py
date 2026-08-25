"""FastAPI dependency injection functions for the Installments module.

All DI factories are synchronous, matching the sync ``Session`` /
``get_db`` pattern used throughout the backend. Empty in Phase 1 (module
foundation) — extended incrementally in every later phase as new
repositories/services are added, mirroring
``modules/crm/dependencies.py``'s own incremental-growth convention.

Spec ref: specs/010-installments/plan.md §2, §12.
"""

from __future__ import annotations
