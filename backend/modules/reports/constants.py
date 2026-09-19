"""Module-wide constants for Reports & Analytics.

Spec ref: specs/011-reports-analytics/plan.md §6/§28/§30 (export bounds,
finalized in Phase 6 once benchmarked; the values here are the
benchmark-driven starting candidates cited by plan.md).
"""

from __future__ import annotations

from typing import Final

REPORTS_CAPABILITY_KEY: Final[str] = "reports"

EXPORT_ROW_LIMIT_CSV: Final[int] = 50_000
EXPORT_ROW_LIMIT_XLSX: Final[int] = 25_000
EXPORT_BATCH_SIZE: Final[int] = 1_000
