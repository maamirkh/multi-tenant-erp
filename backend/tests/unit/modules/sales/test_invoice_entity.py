"""Unit tests for Sales Invoice entity — Phase 6.

Tests:
  - All invoice status transitions (valid + invalid)
  - Terminal statuses cannot be transitioned
  - _assert_invoice_transition raises ConflictException on invalid transitions
  - amount_in_words helper correctness
  - InvoiceLineCreate validators (quantity > 0, unit_price >= 0)
  - InvoiceChargeCreate validators (amount > 0)
  - InvoiceCreditNoteRequest validators (credit_note_amount > 0)

Task: T179
Spec ref: specs/007-sales-management/spec.md §18
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from core.exceptions.base import ConflictException
from modules.sales.schemas.invoice import (
    InvoiceChargeCreate,
    InvoiceCreditNoteRequest,
    InvoiceLineCreate,
)
from modules.sales.services.invoice_service import (
    _TERMINAL_STATUSES,
    _VALID_TRANSITIONS,
    _assert_invoice_transition,
    amount_in_words,
)

# ---------------------------------------------------------------------------
# Valid transitions
# ---------------------------------------------------------------------------


class TestValidTransitions:
    def test_draft_to_issued(self) -> None:
        _assert_invoice_transition("DRAFT", "ISSUED")

    def test_draft_to_cancelled(self) -> None:
        _assert_invoice_transition("DRAFT", "CANCELLED")

    def test_issued_to_credit_note_issued(self) -> None:
        _assert_invoice_transition("ISSUED", "CREDIT_NOTE_ISSUED")

    def test_all_valid_transitions_do_not_raise(self) -> None:
        for current, targets in _VALID_TRANSITIONS.items():
            for target in targets:
                _assert_invoice_transition(current, target)


# ---------------------------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------------------------


class TestInvalidTransitions:
    def test_draft_to_paid_raises(self) -> None:
        with pytest.raises(
            ConflictException, match="Invalid invoice status transition"
        ):
            _assert_invoice_transition("DRAFT", "PAID")

    def test_draft_to_credit_note_raises(self) -> None:
        with pytest.raises(ConflictException):
            _assert_invoice_transition("DRAFT", "CREDIT_NOTE_ISSUED")

    def test_issued_to_draft_raises(self) -> None:
        with pytest.raises(ConflictException):
            _assert_invoice_transition("ISSUED", "DRAFT")

    def test_issued_to_cancelled_raises(self) -> None:
        with pytest.raises(ConflictException):
            _assert_invoice_transition("ISSUED", "CANCELLED")

    def test_cancelled_to_any_raises(self) -> None:
        for target in ["DRAFT", "ISSUED", "PAID", "CREDIT_NOTE_ISSUED"]:
            with pytest.raises(ConflictException):
                _assert_invoice_transition("CANCELLED", target)

    def test_paid_is_terminal(self) -> None:
        assert "PAID" in _TERMINAL_STATUSES
        with pytest.raises(ConflictException):
            _assert_invoice_transition("PAID", "ISSUED")

    def test_credit_note_issued_is_terminal(self) -> None:
        assert "CREDIT_NOTE_ISSUED" in _TERMINAL_STATUSES
        with pytest.raises(ConflictException):
            _assert_invoice_transition("CREDIT_NOTE_ISSUED", "ISSUED")

    def test_cancelled_is_terminal(self) -> None:
        assert "CANCELLED" in _TERMINAL_STATUSES


# ---------------------------------------------------------------------------
# amount_in_words
# ---------------------------------------------------------------------------


class TestAmountInWords:
    def test_zero(self) -> None:
        result = amount_in_words(Decimal("0.00"), "USD")
        assert "zero" in result.lower()

    def test_whole_dollar(self) -> None:
        result = amount_in_words(Decimal("1.00"), "USD")
        assert "one" in result.lower()
        assert "dollar" in result.lower()

    def test_with_cents(self) -> None:
        result = amount_in_words(Decimal("15.50"), "USD")
        assert "fifteen" in result.lower()
        assert "fifty" in result.lower()

    def test_one_cent(self) -> None:
        result = amount_in_words(Decimal("0.01"), "USD")
        assert "one" in result.lower()

    def test_hundred(self) -> None:
        result = amount_in_words(Decimal("100.00"), "USD")
        assert "hundred" in result.lower()

    def test_thousand(self) -> None:
        result = amount_in_words(Decimal("1000.00"), "USD")
        assert "thousand" in result.lower()

    def test_large_amount(self) -> None:
        result = amount_in_words(Decimal("12345.67"), "EUR")
        assert "twelve" in result.lower()
        assert "unit" in result.lower()  # non-USD currencies use "units"


# ---------------------------------------------------------------------------
# Schema validators
# ---------------------------------------------------------------------------


class TestInvoiceLineCreateValidators:
    def test_quantity_positive_ok(self) -> None:
        line = InvoiceLineCreate(
            description="Widget",
            quantity=Decimal("1.0"),
            unit_of_measure="EA",
            unit_price=Decimal("10.00"),
        )
        assert line.quantity == Decimal("1.0")

    def test_quantity_zero_raises(self) -> None:
        with pytest.raises(Exception):
            InvoiceLineCreate(
                description="Widget",
                quantity=Decimal("0"),
                unit_of_measure="EA",
                unit_price=Decimal("10.00"),
            )

    def test_quantity_negative_raises(self) -> None:
        with pytest.raises(Exception):
            InvoiceLineCreate(
                description="Widget",
                quantity=Decimal("-1"),
                unit_of_measure="EA",
                unit_price=Decimal("10.00"),
            )

    def test_unit_price_zero_ok(self) -> None:
        line = InvoiceLineCreate(
            description="Free item",
            quantity=Decimal("1"),
            unit_of_measure="EA",
            unit_price=Decimal("0"),
        )
        assert line.unit_price == Decimal("0")

    def test_unit_price_negative_raises(self) -> None:
        with pytest.raises(Exception):
            InvoiceLineCreate(
                description="Invalid",
                quantity=Decimal("1"),
                unit_of_measure="EA",
                unit_price=Decimal("-5"),
            )


class TestInvoiceChargeCreateValidators:
    def test_amount_positive_ok(self) -> None:
        charge = InvoiceChargeCreate(
            charge_type="FREIGHT",
            description="Shipping",
            amount=Decimal("25.00"),
        )
        assert charge.amount == Decimal("25.00")

    def test_amount_zero_raises(self) -> None:
        with pytest.raises(Exception):
            InvoiceChargeCreate(
                charge_type="FREIGHT",
                description="Shipping",
                amount=Decimal("0"),
            )

    def test_amount_negative_raises(self) -> None:
        with pytest.raises(Exception):
            InvoiceChargeCreate(
                charge_type="HANDLING",
                description="Handling",
                amount=Decimal("-10"),
            )

    def test_invalid_charge_type_raises(self) -> None:
        with pytest.raises(Exception):
            InvoiceChargeCreate(
                charge_type="INVALID",
                description="Bad type",
                amount=Decimal("10"),
            )


class TestInvoiceCreditNoteRequestValidators:
    def test_positive_amount_ok(self) -> None:
        req = InvoiceCreditNoteRequest(credit_note_amount=Decimal("100.00"))
        assert req.credit_note_amount == Decimal("100.00")

    def test_zero_amount_raises(self) -> None:
        with pytest.raises(Exception):
            InvoiceCreditNoteRequest(credit_note_amount=Decimal("0"))

    def test_negative_amount_raises(self) -> None:
        with pytest.raises(Exception):
            InvoiceCreditNoteRequest(credit_note_amount=Decimal("-50"))
