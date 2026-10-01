"""T212 (§0.2 item 33) — the planned extension of T129's structural test
to the export route: ``GET /{report_key}/export`` dispatches only via
``ReportExportService.export()``, never ``ADAPTER_REGISTRY``/an adapter
directly. Also confirms the export service reaches adapters only after
the shared ``_authorize_and_validate()`` preamble."""

from __future__ import annotations

import ast
import inspect
import types

import modules.reports.router as router_mod
import modules.reports.services.export_service as export_service_mod

_FORBIDDEN_NAMES = frozenset({"ADAPTER_REGISTRY", "COMPOSITE_REPORT_HANDLERS"})


def _function(
    source_obj: types.ModuleType | type, name: str
) -> ast.AsyncFunctionDef | ast.FunctionDef:
    tree = ast.parse(inspect.getsource(source_obj))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name == name
        ):
            return node
    raise AssertionError(f"{name} not found")


def _called_attributes(node: ast.AST) -> list[str]:
    calls: list[str] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            target = child.func.value
            owner = target.id if isinstance(target, ast.Name) else "?"
            calls.append(f"{owner}.{child.func.attr}")
    return calls


def test_router_never_references_adapter_registries() -> None:
    tree = ast.parse(inspect.getsource(router_mod))
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id not in _FORBIDDEN_NAMES, node.id
        if isinstance(node, ast.ImportFrom):
            assert "adapters" not in (node.module or "") or all(
                alias.name not in _FORBIDDEN_NAMES for alias in node.names
            )


def test_export_route_dispatches_only_through_export_service() -> None:
    handler = _function(router_mod, "export_report")
    calls = _called_attributes(handler)
    assert "_export_service.export" in calls
    assert not any(
        c.endswith((".run", ".iter_export_rows", ".count_export_rows")) for c in calls
    )
    assert "_execution_service.execute" not in calls


def test_every_route_dispatches_through_a_service_never_an_adapter() -> None:
    source = inspect.getsource(router_mod)
    assert "ADAPTER_REGISTRY[" not in source
    assert ".run(" not in source
    assert ".iter_export_rows(" not in source
    assert ".count_export_rows(" not in source
    assert ".export_pdf(" not in source


def test_export_service_authorizes_before_touching_an_adapter() -> None:
    export_fn = _function(export_service_mod.ReportExportService, "export")
    body = ast.unparse(export_fn)
    assert body.index("_authorize_and_validate(") < body.index("ADAPTER_REGISTRY[")
    assert 'permission_kind="export"' in body or "permission_kind='export'" in body
