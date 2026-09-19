"""T085 — Structural test (FR-RPT-063): no response field named/labeled
as an AP/payable balance anywhere in ``schemas/purchase.py`` — Purchase
never derives an Accounts Payable figure; that is Accounting's sole
authority (spec §7)."""

from __future__ import annotations

import inspect

from modules.reports.schemas import purchase as purchase_schemas

_FORBIDDEN_SUBSTRINGS = ("accounts_payable", "ap_balance", "payable_balance")


def test_no_ap_field_anywhere_in_purchase_schemas() -> None:
    source = inspect.getsource(purchase_schemas)
    lowered = source.lower()
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in lowered, (
            f"found forbidden AP-derivation term: {forbidden}"
        )
