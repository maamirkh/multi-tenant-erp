"""T055 — ``encode_cursor``/``decode_cursor`` round-trip exactly."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from modules.reports.services.adapters.accounting_adapter import (
    decode_cursor,
    encode_cursor,
)


def test_cursor_round_trips_exactly() -> None:
    original = (date(2026, 3, 15), uuid4(), 3)
    encoded = encode_cursor(original)
    assert isinstance(encoded, str)
    decoded = decode_cursor(encoded)
    assert decoded == original
