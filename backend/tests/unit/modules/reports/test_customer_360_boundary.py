"""T174 — Structural test: AST-scan confirms ``customer_360_service.py``
never imports Sales' ``.repositories``/``.models`` directly — the base
customer lookup goes only through Sales' service-layer DI factory
(``modules.sales.dependencies.get_customer_service``, wrapping
``CustomerService``), matching T161's explicit boundary correction."""

from __future__ import annotations

import ast
import inspect

from modules.reports.services import customer_360_service


def _imported_module_paths(tree: ast.Module) -> list[str]:
    paths: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            paths.append(node.module)
        elif isinstance(node, ast.Import):
            paths.extend(alias.name for alias in node.names)
    return paths


def test_never_imports_sales_repositories_or_models_directly() -> None:
    source = inspect.getsource(customer_360_service)
    tree = ast.parse(source)
    imported = _imported_module_paths(tree)

    forbidden_prefixes = ("modules.sales.repositories", "modules.sales.models")
    violations = [
        path
        for path in imported
        if any(path.startswith(prefix) for prefix in forbidden_prefixes)
    ]
    assert violations == [], f"Forbidden Sales-layer imports found: {violations}"


def test_imports_sales_customer_lookup_only_via_dependencies_di() -> None:
    source = inspect.getsource(customer_360_service)
    tree = ast.parse(source)
    imported = _imported_module_paths(tree)

    sales_imports = [path for path in imported if path.startswith("modules.sales")]
    assert sales_imports == ["modules.sales.dependencies"]
