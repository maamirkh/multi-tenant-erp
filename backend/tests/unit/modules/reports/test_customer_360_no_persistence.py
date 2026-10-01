"""T175 — no ``Customer360*`` model exists anywhere in
``backend/modules/reports/models/`` (plan.md §14 point 5: "nothing is
cached, persisted, or blended — every call is a fresh composite read")."""

from __future__ import annotations

import importlib
import pkgutil

import modules.reports.models as reports_models


def test_no_customer_360_model_exists_in_reports_models_package() -> None:
    found: list[str] = []
    for module_info in pkgutil.iter_modules(reports_models.__path__):
        module = importlib.import_module(
            f"{reports_models.__name__}.{module_info.name}"
        )
        for name in dir(module):
            if name.startswith("Customer360"):
                found.append(f"{module.__name__}.{name}")

    assert found == [], f"Found persistence model(s) for Customer 360: {found}"
