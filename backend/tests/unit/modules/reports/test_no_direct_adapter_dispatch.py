"""T129 — Structural test (Phase-3 scope only, export doesn't exist yet):
AST-scan ``router.py`` confirms every current report-serving route
(discovery, ``{report_key}``, saved-views) dispatches only via
``ReportExecutionService``/``SavedViewService``/``registry_service``,
never ``ADAPTER_REGISTRY`` directly. Extended in Phase 6 (T212) once the
export route exists.
"""

from __future__ import annotations

import ast
import inspect

import modules.reports.router as router_mod

_FORBIDDEN_NAMES = frozenset({"ADAPTER_REGISTRY"})


def test_router_never_imports_adapter_registry() -> None:
    source = inspect.getsource(router_mod)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                assert alias.name not in _FORBIDDEN_NAMES, (
                    f"router.py must never import '{alias.name}' directly — "
                    "every dispatch goes through ReportExecutionService"
                )


def test_router_never_references_adapter_registry_by_name() -> None:
    """Belt-and-braces: even a qualified reference
    (``adapters.base.ADAPTER_REGISTRY``) would show up as a plain
    ``Name``/``Attribute`` node somewhere in the module's AST."""
    source = inspect.getsource(router_mod)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            raise AssertionError(f"router.py must never reference '{node.id}' by name")


def test_router_functions_only_call_execution_or_saved_view_or_registry_service() -> (
    None
):
    """Every route handler that executes/loads a report calls exactly one
    of ``_execution_service.execute``, ``saved_view_service.*``, or
    ``registry_service.list_discoverable_reports`` — never
    ``adapter.run()``/``ADAPTER_REGISTRY[...]`` inline."""
    source = inspect.getsource(router_mod)
    assert "_execution_service.execute(" in source
    assert "saved_view_service." in source
    assert "registry_service.list_discoverable_reports(" in source
    assert "ADAPTER_REGISTRY[" not in source
    assert ".run(" not in source
