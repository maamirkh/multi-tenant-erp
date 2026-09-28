"""Module-wide constants for Reports & Analytics.

Spec ref: specs/011-reports-analytics/plan.md §6/§28/§30.

Export bounds **finalized in Phase 6 (T214)** from T213's benchmark
(``tests/unit/modules/reports/test_export_memory_benchmark.py``,
2026-09-28, 4-column typed rows through the real export service + writers):

- CSV: 50K rows -> 4.4 MB file, ~27 MB traced peak, ~1.7 s untraced.
  The planning candidate of 50,000 is confirmed.
- XLSX (openpyxl ``write_only``): ~7x CSV's per-row cost — 25K rows
  ~5.7 s untraced, 50K rows ~2x that and ~54 s under tracing. The lower
  candidate of 25,000 is confirmed as the synchronous ceiling.
- Batch size 1,000 keeps every database round-trip and per-batch Python
  object set small with no measurable throughput penalty; confirmed.
"""

from __future__ import annotations

from typing import Final

REPORTS_CAPABILITY_KEY: Final[str] = "reports"

EXPORT_ROW_LIMIT_CSV: Final[int] = 50_000
EXPORT_ROW_LIMIT_XLSX: Final[int] = 25_000
EXPORT_BATCH_SIZE: Final[int] = 1_000
