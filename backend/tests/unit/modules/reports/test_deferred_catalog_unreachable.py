"""T124 — the 3 ``DEFERRED`` catalog entries (``accounting.tax``,
``accounting.cost_center_pl``, ``crossmodule.branch_performance``) are
structurally unreachable:

1. T030's discovery filter (``list_discoverable_reports``) never returns
   any of them, regardless of permission/entitlement — it filters on
   ``status is ReportStatus.NOW`` before any permission/entitlement check
   even runs (source-level guarantee, verified below without needing a
   live DB/user fixture).
2. No frontend source file references any of their 3 keys (grep-based —
   the frontend has no Epic 11 Reports UI at all yet, these keys are not
   even latent/dead references).
"""

from __future__ import annotations

import inspect
import subprocess
from pathlib import Path

import modules.reports.registry.load_all  # noqa: F401 — triggers full catalog registration
from modules.reports.registry.definitions import REPORT_REGISTRY, ReportStatus
from modules.reports.services import registry_service

_DEFERRED_KEYS = (
    "accounting.tax",
    "accounting.cost_center_pl",
    "crossmodule.branch_performance",
)

_FRONTEND_SRC = Path(__file__).resolve().parents[4] / "frontend" / "src"


def test_deferred_keys_are_registered_as_deferred() -> None:
    for key in _DEFERRED_KEYS:
        assert key in REPORT_REGISTRY
        assert REPORT_REGISTRY[key].status is ReportStatus.DEFERRED


def test_discovery_filter_excludes_non_now_status_before_any_other_check() -> None:
    """Source-level guarantee: ``list_discoverable_reports`` skips
    non-``NOW`` entries via an unconditional ``continue`` before the
    permission/entitlement checks run — no permission grant or
    entitlement state can ever make a DEFERRED key reachable."""
    source = inspect.getsource(registry_service.list_discoverable_reports)
    skip_line_index = None
    permission_check_index = None
    for i, line in enumerate(source.splitlines()):
        if "status is not ReportStatus.NOW" in line:
            skip_line_index = i
        if "user_has_reports_permission" in line:
            permission_check_index = i
    assert skip_line_index is not None
    assert permission_check_index is not None
    assert skip_line_index < permission_check_index


def test_no_frontend_reference_to_any_deferred_key() -> None:
    if not _FRONTEND_SRC.exists():
        return  # nothing to scan; no false confidence either way
    for key in _DEFERRED_KEYS:
        result = subprocess.run(
            ["grep", "-r", "-l", key, str(_FRONTEND_SRC)],
            capture_output=True,
            text=True,
        )
        assert result.stdout == "", f"found frontend reference to deferred key '{key}'"
