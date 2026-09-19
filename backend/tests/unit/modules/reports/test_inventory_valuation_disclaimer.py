"""T096 — Structural test (FR-RPT-071/§16.2): no field named
``balance_sheet_value``/``gl_value``/``financial_value`` anywhere in
``schemas/inventory.py`` — Inventory's operational WAC valuation is never
labeled as if it were a reconciled accounting inventory balance."""

from __future__ import annotations

import inspect

from modules.reports.schemas import inventory as inventory_schemas
from modules.reports.schemas.inventory import InventoryValuationResponse

_FORBIDDEN_SUBSTRINGS = ("balance_sheet_value", "gl_value", "financial_value")


def test_no_financial_valuation_field_anywhere_in_inventory_schemas() -> None:
    source = inspect.getsource(inventory_schemas)
    lowered = source.lower()
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in lowered, (
            f"found forbidden financial-value term: {forbidden}"
        )


def test_valuation_response_requires_operational_wac_basis() -> None:
    assert "valuation_basis" in InventoryValuationResponse.model_fields
    field = InventoryValuationResponse.model_fields["valuation_basis"]
    assert field.is_required()
