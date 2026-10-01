"""T029 — ``csv_sanitizer.sanitize_cell()`` (spec §30 CSV formula-injection
protection)."""

from __future__ import annotations

import pytest

from modules.reports.services.csv_sanitizer import sanitize_cell


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("=SUM(A1:A10)", "'=SUM(A1:A10)"),
        ("+1234", "'+1234"),
        ("-1234", "'-1234"),
        ("@example.com", "'@example.com"),
    ],
)
def test_formula_prefixed_values_are_neutralized(raw: str, expected: str) -> None:
    assert sanitize_cell(raw) == expected


@pytest.mark.parametrize("raw", ["Acme Corp", "1234", "", "hello=world"])
def test_non_formula_values_pass_through_unmodified(raw: str) -> None:
    assert sanitize_cell(raw) == raw
