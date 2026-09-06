"""Unit tests for CostService — Phase 8.

Tests:
  - PO total computation with known values (exact Decimal arithmetic)
  - Header discount applied after line discounts (T195)
  - PPV formula with known values (T192)
  - PPV threshold alert detection (T193)
  - PurchaseCostEntry immutability — no update method on service (T194)
  - create_cost_entry_on_gr_confirm — snapshot creation
  - CostEntryAlreadyExistsError raised on duplicate

Task: T202
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from modules.purchase.services.cost_service import (
    CostEntryAlreadyExistsError,
    CostService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    *,
    lines=None,
    charges=None,
    po=None,
    gr=None,
    gr_lines=None,
    existing_entry=None,
) -> CostService:
    db = MagicMock()

    po_repo = MagicMock()
    po_repo.get_by_id_or_none.return_value = po or _make_po()
    po_repo.list_for_company.return_value = [po] if po else [_make_po()]

    po_line_repo = MagicMock()
    po_line_repo.list_for_po.return_value = lines or []

    po_charge_repo = MagicMock()
    po_charge_repo.list_for_po.return_value = charges or []

    gr_repo = MagicMock()
    gr_repo.get_by_id_or_none.return_value = gr or _make_gr()

    gr_line_repo = MagicMock()
    gr_line_repo.list_for_gr.return_value = gr_lines or []

    policy_repo = MagicMock()
    policy_repo.get_by_id_or_none.return_value = None

    svc = CostService(
        db=db,
        po_repo=po_repo,
        po_line_repo=po_line_repo,
        po_charge_repo=po_charge_repo,
        gr_repo=gr_repo,
        gr_line_repo=gr_line_repo,
        policy_repo=policy_repo,
    )

    # Patch internal _get_entry_for_gr to control idempotency
    svc._get_entry_for_gr = MagicMock(return_value=existing_entry)

    return svc


def _make_po(
    *,
    total_discounts="0.00",
    tax_amount="0.00",
    subtotal="0.00",
    total_charges="0.00",
    total="0.00",
    currency_code="USD",
) -> MagicMock:
    po = MagicMock()
    po.id = uuid4()
    po.po_number = "PO-2026-000001"
    po.supplier_id = str(uuid4())
    po.status = "APPROVED"
    po.currency_code = currency_code
    po.total_discounts = total_discounts
    po.tax_amount = tax_amount
    po.subtotal = subtotal
    po.total_charges = total_charges
    po.total = total
    return po


def _make_po_line(
    *,
    unit_cost="10.00",
    quantity_ordered="5.000",
    line_discount_percent=None,
    line_discount_amount=None,
) -> MagicMock:
    ln = MagicMock()
    ln.unit_cost = unit_cost
    ln.quantity_ordered = quantity_ordered
    ln.line_discount_percent = line_discount_percent
    ln.line_discount_amount = line_discount_amount
    return ln


def _make_po_charge(*, amount="25.00") -> MagicMock:
    charge = MagicMock()
    charge.amount = amount
    return charge


def _make_gr(*, po_id=None, supplier_id=None) -> MagicMock:
    gr = MagicMock()
    gr.id = uuid4()
    gr.gr_number = "GR-2026-000001"
    gr.po_id = str(po_id or uuid4())
    gr.supplier_id = str(supplier_id or uuid4())
    gr.status = "CONFIRMED"
    gr.currency_code = "USD"
    return gr


def _make_gr_line(
    *,
    unit_cost="12.00",
    po_unit_cost="10.00",
    quantity_received="5.000",
    ppv_amount="0.00",
    ppv_percentage="0.0000",
    product_id=None,
) -> MagicMock:
    ln = MagicMock()
    ln.id = uuid4()
    ln.po_line_id = str(uuid4())
    ln.product_id = product_id
    ln.unit_cost = unit_cost
    ln.po_unit_cost = po_unit_cost
    ln.quantity_received = quantity_received
    ln.ppv_amount = ppv_amount
    ln.ppv_percentage = ppv_percentage
    return ln


COMPANY_ID = uuid4()
PO_ID = uuid4()
GR_ID = uuid4()


# ---------------------------------------------------------------------------
# T191: compute_po_totals
# ---------------------------------------------------------------------------


class TestComputePOTotals:
    def test_simple_subtotal_no_discount(self):
        """2 lines × unit_cost × qty = subtotal; no charges or discounts."""
        line1 = _make_po_line(unit_cost="10.00", quantity_ordered="3.000")
        line2 = _make_po_line(unit_cost="5.00", quantity_ordered="4.000")
        svc = _make_service(lines=[line1, line2])

        result = svc.compute_po_totals(PO_ID, COMPANY_ID)

        assert result["subtotal"] == Decimal("50.00")  # 30 + 20
        assert result["total_charges"] == Decimal("0.00")
        assert result["total_discounts"] == Decimal("0.00")
        assert result["total"] == Decimal("50.00")

    def test_line_discount_percent_applied(self):
        """Line discount percent reduces line total."""
        # 100.00 × 10% discount = 90.00
        line = _make_po_line(
            unit_cost="10.00",
            quantity_ordered="10.000",
            line_discount_percent="10.00",
        )
        svc = _make_service(lines=[line])

        result = svc.compute_po_totals(PO_ID, COMPANY_ID)

        assert result["subtotal"] == Decimal("90.00")

    def test_line_discount_amount_takes_precedence(self):
        """Explicit line_discount_amount takes precedence over percent."""
        # gross = 100.00; discount_amount = 15.00 → line_total = 85.00
        line = _make_po_line(
            unit_cost="10.00",
            quantity_ordered="10.000",
            line_discount_percent="5.00",  # should be ignored
            line_discount_amount="15.00",
        )
        svc = _make_service(lines=[line])

        result = svc.compute_po_totals(PO_ID, COMPANY_ID)

        assert result["subtotal"] == Decimal("85.00")

    def test_additional_charges_added(self):
        """Additional charges are added on top of subtotal."""
        line = _make_po_line(unit_cost="100.00", quantity_ordered="1.000")
        charge1 = _make_po_charge(amount="25.00")
        charge2 = _make_po_charge(amount="10.00")
        svc = _make_service(lines=[line], charges=[charge1, charge2])

        result = svc.compute_po_totals(PO_ID, COMPANY_ID)

        assert result["subtotal"] == Decimal("100.00")
        assert result["total_charges"] == Decimal("35.00")

    def test_header_discount_applied_after_line_discounts(self):
        """Header discount applied to discounted subtotal (T195)."""
        # gross = 200.00; line discount = 20.00 → subtotal = 180.00
        # header discount = 18.00 (from PO.total_discounts)
        line = _make_po_line(
            unit_cost="20.00", quantity_ordered="10.000", line_discount_percent="10.00"
        )
        po = _make_po(total_discounts="18.00")
        svc = _make_service(lines=[line], po=po)

        result = svc.compute_po_totals(PO_ID, COMPANY_ID)

        assert result["subtotal"] == Decimal("180.00")
        assert result["total_discounts"] == Decimal("18.00")
        assert result["total"] == Decimal("162.00")  # 180 - 18

    def test_total_formula_all_components(self):
        """Total = subtotal + charges - discounts + tax."""
        line = _make_po_line(unit_cost="100.00", quantity_ordered="1.000")
        charge = _make_po_charge(amount="50.00")
        po = _make_po(total_discounts="10.00", tax_amount="15.00")
        svc = _make_service(lines=[line], charges=[charge], po=po)

        result = svc.compute_po_totals(PO_ID, COMPANY_ID)

        # 100 + 50 - 10 + 15 = 155
        assert result["total"] == Decimal("155.00")


# ---------------------------------------------------------------------------
# T192: compute_ppv
# ---------------------------------------------------------------------------


class TestComputePPV:
    def test_positive_ppv_when_gr_cost_higher_than_po(self):
        """PPV > 0 when actual unit_cost > po_unit_cost."""
        ln = _make_gr_line(
            unit_cost="12.00", po_unit_cost="10.00", quantity_received="5.000"
        )
        svc = _make_service()

        ppv_amount, ppv_pct = svc.compute_ppv(ln)

        # (12 - 10) * 5 = 10.00
        assert ppv_amount == Decimal("10.00")
        # 10 / (10 * 5) * 100 = 20%
        assert ppv_pct == Decimal("20.0000")

    def test_negative_ppv_when_gr_cost_lower(self):
        """PPV < 0 when actual unit_cost < po_unit_cost (favourable variance)."""
        ln = _make_gr_line(
            unit_cost="8.00", po_unit_cost="10.00", quantity_received="4.000"
        )
        svc = _make_service()

        ppv_amount, ppv_pct = svc.compute_ppv(ln)

        # (8 - 10) * 4 = -8.00
        assert ppv_amount == Decimal("-8.00")
        # -8 / (10 * 4) * 100 = -20%
        assert ppv_pct == Decimal("-20.0000")

    def test_zero_ppv_when_costs_equal(self):
        ln = _make_gr_line(
            unit_cost="10.00", po_unit_cost="10.00", quantity_received="3.000"
        )
        svc = _make_service()

        ppv_amount, ppv_pct = svc.compute_ppv(ln)

        assert ppv_amount == Decimal("0.00")
        assert ppv_pct == Decimal("0.0000")

    def test_ppv_percentage_zero_when_po_unit_cost_zero(self):
        """PPV% = 0 when po_unit_cost is 0 to avoid division by zero."""
        ln = _make_gr_line(
            unit_cost="10.00", po_unit_cost="0.00", quantity_received="2.000"
        )
        svc = _make_service()

        ppv_amount, ppv_pct = svc.compute_ppv(ln)

        assert ppv_amount == Decimal("20.00")
        assert ppv_pct == Decimal("0.0000")

    def test_compute_ppv_stores_values_on_line(self):
        """compute_ppv stores results on the gr_line model."""
        ln = _make_gr_line(
            unit_cost="15.00", po_unit_cost="10.00", quantity_received="2.000"
        )
        svc = _make_service()

        svc.compute_ppv(ln)

        assert ln.ppv_amount == Decimal("10.00")
        assert ln.ppv_percentage == Decimal("50.0000")


# ---------------------------------------------------------------------------
# T193: PPV threshold alerts
# ---------------------------------------------------------------------------


class TestPPVAlerts:
    def test_alert_published_when_ppv_exceeds_threshold(self):
        """PurchasePriceVarianceDetected published if abs(PPV%) > threshold."""
        gr = _make_gr()
        # PPV% = 20%, threshold default 5%
        ln = _make_gr_line(ppv_percentage="20.0000", ppv_amount="10.00")
        svc = _make_service()

        bus = MagicMock()
        with patch(
            "modules.purchase.services.cost_service.get_event_bus", return_value=bus
        ):
            with patch.object(svc, "_get_policy", return_value=None):
                svc.check_ppv_alerts(gr, [ln], COMPANY_ID)

        bus.publish.assert_called_once()

    def test_no_alert_when_ppv_within_threshold(self):
        """No event published when abs(PPV%) <= threshold."""
        gr = _make_gr()
        ln = _make_gr_line(ppv_percentage="3.0000", ppv_amount="1.50")
        svc = _make_service()

        bus = MagicMock()
        with patch(
            "modules.purchase.services.cost_service.get_event_bus", return_value=bus
        ):
            with patch.object(svc, "_get_policy", return_value=None):
                svc.check_ppv_alerts(gr, [ln], COMPANY_ID)

        bus.publish.assert_not_called()

    def test_negative_ppv_pct_triggers_alert(self):
        """Negative PPV also triggers alert if abs(PPV%) > threshold."""
        gr = _make_gr()
        ln = _make_gr_line(ppv_percentage="-10.0000", ppv_amount="-5.00")
        svc = _make_service()

        bus = MagicMock()
        with patch(
            "modules.purchase.services.cost_service.get_event_bus", return_value=bus
        ):
            with patch.object(svc, "_get_policy", return_value=None):
                svc.check_ppv_alerts(gr, [ln], COMPANY_ID)

        bus.publish.assert_called_once()


# ---------------------------------------------------------------------------
# T194: create_cost_entry_on_gr_confirm
# ---------------------------------------------------------------------------


class TestCreateCostEntry:
    def test_creates_entry_with_correct_values(self):
        """Cost entry snapshot created with correct computed totals."""
        gr = _make_gr()
        gr_lines = [
            _make_gr_line(unit_cost="20.00", quantity_received="3.000"),
            _make_gr_line(unit_cost="5.00", quantity_received="2.000"),
        ]
        svc = _make_service(gr=gr, gr_lines=gr_lines, existing_entry=None)
        # compute_po_totals is called internally; mock it
        svc.compute_po_totals = MagicMock(
            return_value={
                "subtotal": Decimal("70.00"),
                "total_charges": Decimal("10.00"),
                "total_discounts": Decimal("5.00"),
                "tax_amount": Decimal("0.00"),
                "total": Decimal("75.00"),
            }
        )

        bus = MagicMock()
        with patch(
            "modules.purchase.services.cost_service.get_event_bus", return_value=bus
        ):
            entry = svc.create_cost_entry_on_gr_confirm(
                gr=gr, lines=gr_lines, company_id=COMPANY_ID
            )

        # subtotal = 20*3 + 5*2 = 70.00
        assert entry.subtotal == Decimal("70.00")
        assert entry.total_charges == Decimal("10.00")
        assert entry.total_discounts == Decimal("5.00")
        assert entry.total == Decimal("75.00")
        svc.db.add.assert_called_once()
        bus.publish.assert_called_once()

    def test_raises_on_duplicate_entry(self):
        """CostEntryAlreadyExistsError raised when entry already exists."""
        gr = _make_gr()
        existing = MagicMock()
        svc = _make_service(gr=gr, existing_entry=existing)

        with pytest.raises(CostEntryAlreadyExistsError):
            svc.create_cost_entry_on_gr_confirm(gr=gr, lines=[], company_id=COMPANY_ID)

    def test_immutability_no_update_method(self):
        """CostService has no update_cost_entry method — immutability contract."""
        svc = _make_service()
        assert not hasattr(
            svc, "update_cost_entry"
        ), "CostService must NOT expose an update_cost_entry method — entries are immutable."
