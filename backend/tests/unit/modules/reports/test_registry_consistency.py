"""T032 — Registry-consistency test (FR-RPT-004).

For every ``status == NOW`` entry, branches on ``execution_kind``:

- ``ADAPTER``: ``authoritative_source`` resolves to a real callable (via
  ``importlib``), an adapter is registered in ``ADAPTER_REGISTRY`` for its
  domain, ``supported_filters`` is a ``BaseModel`` subclass,
  ``required_permission`` is a seeded permission code,
  ``domain_capability_key`` is a known capability key, and
  pagination/export values are internally valid.
- ``COMPOSITE``: ``authoritative_source`` resolves to a real callable, a
  matching entry exists in ``COMPOSITE_REPORT_HANDLERS`` whose value **is
  the exact same callable** (checked by identity) — no
  ``ADAPTER_REGISTRY`` entry is required or checked.

For ``status == DEFERRED`` entries (either kind), ``authoritative_source``
is explicitly NOT required to resolve.

Trivially passed at Phase 0 (0 registered entries — nothing imported any
catalog_* module yet). Since Gate 2 (T125), this file's own explicit
``modules.reports.registry.load_all`` import below registers all 46 real
entries (43 NOW + 3 DEFERRED) before any test in this module runs,
including the parametrized consistency check, which now runs against the
full, real registry. Re-run unmodified at Gates 4/5 per tasks.md (their
own new COMPOSITE entries just add to what's already registered).
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest
from pydantic import BaseModel

import modules.reports.registry.load_all  # noqa: F401 — triggers full catalog registration
from modules.reports.registry.definitions import (
    REPORT_REGISTRY,
    ExportFormat,
    PaginationStyle,
    ReportDefinition,
    ReportExecutionKind,
    ReportStatus,
)
from modules.reports.services.adapters.base import (
    ADAPTER_REGISTRY,
    COMPOSITE_REPORT_HANDLERS,
)
from modules.users_roles.constants import PERMISSION_BY_CODE

_KNOWN_CAPABILITY_KEYS = frozenset(
    {"sales", "purchase", "inventory", "accounting", "crm", "installments"}
)


def _resolve_callable(dotted_path: str) -> Any:
    """Resolve ``module.sub.Class.method`` (or plain ``module.function``)
    by trying the longest importable module prefix first, then walking
    the remaining attribute chain — a straight ``rpartition(".")`` split
    only ever resolves a bare ``module.function`` path and raises
    ``ModuleNotFoundError`` for any class-qualified ``authoritative_source``
    (discovered during Phase 2's Inventory/CRM sub-phases, the first time
    this test was actually exercised against non-empty, class-method
    ``authoritative_source`` entries)."""
    parts = dotted_path.split(".")
    for i in range(len(parts) - 1, 0, -1):
        module_path = ".".join(parts[:i])
        try:
            module = importlib.import_module(module_path)
        except ModuleNotFoundError:
            continue
        target: Any = module
        for attr in parts[i:]:
            target = getattr(target, attr)
        return target
    raise ModuleNotFoundError(
        f"Could not resolve any module prefix for '{dotted_path}'"
    )


def _assert_common_invariants(definition: ReportDefinition) -> None:
    assert definition.required_permission in PERMISSION_BY_CODE, (
        f"{definition.key}: required_permission "
        f"'{definition.required_permission}' is not a seeded permission code"
    )
    if definition.export_permission is not None:
        assert definition.export_permission in PERMISSION_BY_CODE
    assert isinstance(definition.pagination, PaginationStyle)
    assert all(isinstance(fmt, ExportFormat) for fmt in definition.export_formats)


@pytest.mark.parametrize(
    "definition", list(REPORT_REGISTRY.values()), ids=lambda d: d.key
)
def test_registry_entry_is_internally_consistent(definition: ReportDefinition) -> None:
    if definition.status is ReportStatus.DEFERRED:
        # authoritative_source is explicitly NOT required to resolve yet.
        _assert_common_invariants(definition)
        return

    assert definition.status is ReportStatus.NOW
    resolved = _resolve_callable(definition.authoritative_source)
    assert callable(resolved)
    assert issubclass(definition.supported_filters, BaseModel)
    _assert_common_invariants(definition)

    if definition.execution_kind is ReportExecutionKind.ADAPTER:
        assert definition.domain_capability_key in _KNOWN_CAPABILITY_KEYS
        assert definition.domain in ADAPTER_REGISTRY
    elif definition.execution_kind is ReportExecutionKind.COMPOSITE:
        handler = COMPOSITE_REPORT_HANDLERS.get(definition.key)
        assert handler is not None, (
            f"{definition.key}: no COMPOSITE_REPORT_HANDLERS entry registered"
        )
        assert handler is resolved, (
            f"{definition.key}: registered handler is not the exact same "
            "callable authoritative_source resolves to"
        )
    else:  # pragma: no cover — exhaustive over ReportExecutionKind
        pytest.fail(f"Unknown execution_kind: {definition.execution_kind}")


def test_all_keys_are_unique() -> None:
    keys = [d.key for d in REPORT_REGISTRY.values()]
    assert len(keys) == len(set(keys))


def test_gate_5_registry_shape() -> None:
    """Gate 5 (T177, tasks.md): **45 NOW** entries (the final, complete
    count) — the 43 ``ADAPTER`` entries Gate 2 (T125) established (8 Sales
    + 7 Purchase + 8 Inventory + 9 Accounting + 4 CRM + 7 Installments),
    plus exactly 2 ``COMPOSITE`` entries, ``exec.dashboard`` (Phase 4,
    T151) and ``crossmodule.customer_360`` (Phase 5, T166) — and the same
    3 ``DEFERRED`` entries as Gate 2.

    Supersedes the prior Gate-4-only ``test_gate_4_registry_shape`` (whose
    "44 NOW, 1 COMPOSITE" assertion necessarily stopped holding once this
    phase's ``crossmodule.customer_360`` entry joined the always-imported
    ``catalog_crossmodule`` module — the registry is one shared,
    cumulative, import-time-populated structure, not a per-gate snapshot)
    — this test folds every earlier gate's own per-domain ``ADAPTER``
    counts in verbatim, still verified here, plus both ``COMPOSITE``
    entries."""
    now = [d for d in REPORT_REGISTRY.values() if d.status is ReportStatus.NOW]
    deferred = [
        d for d in REPORT_REGISTRY.values() if d.status is ReportStatus.DEFERRED
    ]

    assert len(now) == 45
    adapter_now = [d for d in now if d.execution_kind is ReportExecutionKind.ADAPTER]
    composite_now = [
        d for d in now if d.execution_kind is ReportExecutionKind.COMPOSITE
    ]
    assert len(adapter_now) == 43
    assert len(composite_now) == 2
    assert {d.key for d in composite_now} == {
        "exec.dashboard",
        "crossmodule.customer_360",
    }
    assert len(deferred) == 3
    assert {d.key for d in deferred} == {
        "accounting.tax",
        "accounting.cost_center_pl",
        "crossmodule.branch_performance",
    }

    by_domain: dict[str, int] = {}
    for d in adapter_now:
        by_domain[d.domain.value] = by_domain.get(d.domain.value, 0) + 1
    assert by_domain == {
        "sales": 8,
        "purchase": 7,
        "inventory": 8,
        "accounting": 9,
        "crm": 4,
        "installments": 7,
    }
