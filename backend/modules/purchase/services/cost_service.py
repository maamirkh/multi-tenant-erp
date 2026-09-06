"""Purchase Costing application service — Phase 8.

Responsibilities:
  compute_po_totals          — recompute PO header financial totals from lines + charges
  compute_ppv                — compute PPV for a GR line and store on the model
  check_ppv_alerts           — detect PPV threshold breaches and publish events
  create_cost_entry_on_gr_confirm — create immutable PurchaseCostEntry snapshot (called
                                    within GR confirmation transaction)
  get_po_cost_summary        — read PO financial summary
  get_gr_cost_summary        — read GR financial summary with PPV per line
  get_cost_entry_for_gr      — read PurchaseCostEntry for a confirmed GR

Business rules:
  - All arithmetic uses Python Decimal to avoid floating-point error
  - Line discount: unit_cost × qty_ordered × (1 − line_discount_percent/100)
    OR unit_cost × qty_ordered − line_discount_amount (if amount set explicitly)
  - Header discount deducted from discounted subtotal
  - Total = subtotal + total_charges − total_discounts + tax_amount
  - PPV = (gr_unit_cost − po_unit_cost) × quantity_received
  - PPV% = ppv_amount / (po_unit_cost × quantity_received) × 100  [0 if po_unit_cost = 0]
  - PPV alert published if abs(PPV%) > PurchasePolicy.ppv_alert_threshold_percent

Spec ref: specs/006-purchase-management/spec.md §19 Purchase Costing
Tasks: T191, T192, T193, T194, T195
"""

from __future__ import annotations

import logging
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.exceptions.base import NotFoundException
from core.utils.datetime import utcnow
from modules.purchase.events import get_event_bus
from modules.purchase.events.cost_events import (
    PurchaseCostRecorded,
    PurchasePriceVarianceDetected,
)
from modules.purchase.models.cost import PurchaseCostEntry
from modules.purchase.models.goods_receipt import GoodsReceipt, GRLine
from modules.purchase.models.policy import PurchasePolicy
from modules.purchase.repositories.goods_receipt import (
    GoodsReceiptRepository,
    GRLineRepository,
)
from modules.purchase.repositories.master import PurchasePolicyRepository
from modules.purchase.repositories.purchase_order import (
    POAdditionalChargeRepository,
    POLineRepository,
    PurchaseOrderRepository,
)
from modules.purchase.schemas.cost import (
    GRCostSummary,
    POCostSummary,
    PPVLine,
    PurchaseCostEntryRead,
)

logger = logging.getLogger(__name__)

_TWO = Decimal("0.01")
_FOUR = Decimal("0.0001")


class CostEntryAlreadyExistsError(Exception):
    """Raised when trying to create a duplicate cost entry for a GR."""

    def __init__(self, gr_id: str) -> None:
        super().__init__(f"PurchaseCostEntry already exists for GR {gr_id}.")


class CostService:
    """Purchase costing service.

    Immutability contract: PurchaseCostEntry has no update method.
    Once created on GR confirmation, it cannot be modified.
    """

    def __init__(
        self,
        db: Session,
        po_repo: PurchaseOrderRepository,
        po_line_repo: POLineRepository,
        po_charge_repo: POAdditionalChargeRepository,
        gr_repo: GoodsReceiptRepository,
        gr_line_repo: GRLineRepository,
        policy_repo: PurchasePolicyRepository,
    ) -> None:
        self.db = db
        self.po_repo = po_repo
        self.po_line_repo = po_line_repo
        self.po_charge_repo = po_charge_repo
        self.gr_repo = gr_repo
        self.gr_line_repo = gr_line_repo
        self.policy_repo = policy_repo

    # ------------------------------------------------------------------
    # T191: compute_po_totals
    # ------------------------------------------------------------------

    def compute_po_totals(self, po_id: UUID, company_id: UUID) -> dict[str, Decimal]:
        """Recompute PO header financial totals from lines + additional charges.

        Discount precedence:
          1. line_discount_amount (explicit amount) takes priority over line_discount_percent
          2. Header discount (total_discounts on PO) is applied to discounted subtotal

        Total = subtotal + total_charges − total_discounts + tax_amount
        All arithmetic uses Python Decimal.
        """
        po = self.po_repo.get_by_id_or_none(po_id, company_id)
        if not po:
            raise NotFoundException(f"PurchaseOrder {po_id} not found.")

        lines = self.po_line_repo.list_for_po(po_id, company_id)
        charges = self.po_charge_repo.list_for_po(po_id, company_id)

        # Subtotal: sum of discounted line totals (T195)
        subtotal = Decimal("0.00")
        for ln in lines:
            unit_cost = Decimal(str(ln.unit_cost))
            qty = Decimal(str(ln.quantity_ordered))
            gross = (unit_cost * qty).quantize(_TWO, rounding=ROUND_HALF_UP)

            if ln.line_discount_amount is not None:
                discount_amount = Decimal(str(ln.line_discount_amount))
                line_total = (gross - discount_amount).quantize(
                    _TWO, rounding=ROUND_HALF_UP
                )
            elif ln.line_discount_percent is not None:
                pct = Decimal(str(ln.line_discount_percent))
                discount_amount = (gross * pct / Decimal("100")).quantize(
                    _TWO, rounding=ROUND_HALF_UP
                )
                line_total = (gross - discount_amount).quantize(
                    _TWO, rounding=ROUND_HALF_UP
                )
            else:
                line_total = gross

            subtotal += max(Decimal("0.00"), line_total)

        # Additional charges total
        total_charges = sum(
            (Decimal(str(c.amount)) for c in charges),
            Decimal("0.00"),
        ).quantize(_TWO, rounding=ROUND_HALF_UP)

        # Header-level discount (from PO.total_discounts — stored externally)
        total_discounts = Decimal(str(po.total_discounts or "0.00")).quantize(
            _TWO, rounding=ROUND_HALF_UP
        )

        # Tax amount (captured, not computed)
        tax_amount = Decimal(str(po.tax_amount or "0.00")).quantize(
            _TWO, rounding=ROUND_HALF_UP
        )

        total = (subtotal + total_charges - total_discounts + tax_amount).quantize(
            _TWO, rounding=ROUND_HALF_UP
        )

        return {
            "subtotal": subtotal,
            "total_charges": total_charges,
            "total_discounts": total_discounts,
            "tax_amount": tax_amount,
            "total": max(Decimal("0.00"), total),
        }

    # ------------------------------------------------------------------
    # T192: compute_ppv
    # ------------------------------------------------------------------

    def compute_ppv(self, gr_line: GRLine) -> tuple[Decimal, Decimal]:
        """Compute PPV for a GR line and persist the result on the model.

        PPV amount      = (unit_cost − po_unit_cost) × quantity_received
        PPV percentage  = ppv_amount / (po_unit_cost × quantity_received) × 100
                          (returns 0 when po_unit_cost = 0)

        Returns (ppv_amount, ppv_percentage) — both stored on gr_line.
        """
        unit_cost = Decimal(str(gr_line.unit_cost))
        po_unit_cost = Decimal(str(gr_line.po_unit_cost))
        qty = Decimal(str(gr_line.quantity_received))

        ppv_amount = ((unit_cost - po_unit_cost) * qty).quantize(
            _TWO, rounding=ROUND_HALF_UP
        )

        denominator = po_unit_cost * qty
        if denominator == Decimal("0"):
            ppv_percentage = Decimal("0.0000")
        else:
            ppv_percentage = (ppv_amount / denominator * Decimal("100")).quantize(
                _FOUR, rounding=ROUND_HALF_UP
            )

        gr_line.ppv_amount = ppv_amount
        gr_line.ppv_percentage = ppv_percentage
        return ppv_amount, ppv_percentage

    # ------------------------------------------------------------------
    # T193: PPV threshold alert
    # ------------------------------------------------------------------

    def check_ppv_alerts(
        self,
        gr: GoodsReceipt,
        lines: list[GRLine],
        company_id: UUID,
    ) -> None:
        """Publish PurchasePriceVarianceDetected for lines exceeding the threshold.

        Reads PurchasePolicy.ppv_alert_threshold_percent for the company.
        If no policy configured, defaults to 5.0% threshold.
        """
        policy = self._get_policy(company_id)
        threshold = (
            Decimal(str(policy.ppv_alert_threshold_percent))
            if policy
            else Decimal("5.00")
        )

        bus = get_event_bus()
        for ln in lines:
            ppv_pct = Decimal(str(ln.ppv_percentage))
            if abs(ppv_pct) > threshold:
                event = PurchasePriceVarianceDetected.create(
                    aggregate_id=ln.id,
                    company_id=company_id,
                    gr_id=str(gr.id),
                    gr_line_id=str(ln.id),
                    po_id=str(gr.po_id),
                    product_id=str(ln.product_id) if ln.product_id else "",
                    ppv_amount=str(ln.ppv_amount),
                    ppv_percentage=str(ln.ppv_percentage),
                    threshold_percent=str(threshold),
                )
                bus.publish(event)
                logger.warning(
                    "PPV alert: GRLine %s PPV=%.4f%% exceeds threshold %.2f%%",
                    ln.id,
                    float(ppv_pct),
                    float(threshold),
                )

    # ------------------------------------------------------------------
    # T194: create_cost_entry_on_gr_confirm
    # ------------------------------------------------------------------

    def create_cost_entry_on_gr_confirm(
        self,
        gr: GoodsReceipt,
        lines: list[GRLine],
        company_id: UUID,
        cost_date: date | None = None,
    ) -> PurchaseCostEntry:
        """Create an immutable PurchaseCostEntry snapshot on GR confirmation.

        Called within the GR confirmation transaction. Raises CostEntryAlreadyExistsError
        if an entry already exists for this GR (idempotency guard).
        """
        gr_id_str = str(gr.id)

        # Idempotency guard
        existing = self._get_entry_for_gr(gr_id_str, company_id)
        if existing:
            raise CostEntryAlreadyExistsError(gr_id_str)

        # Compute subtotal from GR lines (actual received cost)
        subtotal = sum(
            (Decimal(str(ln.unit_cost)) * Decimal(str(ln.quantity_received))).quantize(
                _TWO, rounding=ROUND_HALF_UP
            )
            for ln in lines
        )

        # Get PO financial summary for charges, discounts and tax
        po_id = UUID(str(gr.po_id))
        try:
            totals = self.compute_po_totals(po_id, company_id)
            total_charges = totals["total_charges"]
            total_discounts = totals["total_discounts"]
            tax_amount = totals["tax_amount"]
        except Exception:
            logger.exception(
                "Failed to compute PO totals for cost entry, defaulting to 0"
            )
            total_charges = Decimal("0.00")
            total_discounts = Decimal("0.00")
            tax_amount = Decimal("0.00")

        total = (subtotal + total_charges - total_discounts + tax_amount).quantize(
            _TWO, rounding=ROUND_HALF_UP
        )
        total = max(Decimal("0.00"), total)

        entry = PurchaseCostEntry(
            company_id=company_id,
            gr_id=gr_id_str,
            po_id=str(gr.po_id),
            supplier_id=str(gr.supplier_id) if gr.supplier_id else "",
            cost_date=cost_date or utcnow().date(),
            subtotal=subtotal,
            total_charges=total_charges,
            total_discounts=total_discounts,
            tax_amount=tax_amount,
            total=total,
            credit_note_pending=False,
            currency_code=getattr(gr, "currency_code", "USD") or "USD",
        )
        self.db.add(entry)
        self.db.flush()

        # Publish domain event
        bus = get_event_bus()
        event = PurchaseCostRecorded.create(
            aggregate_id=entry.id,
            company_id=company_id,
            gr_id=gr_id_str,
            po_id=str(gr.po_id),
            supplier_id=entry.supplier_id,
            subtotal=str(subtotal),
            total_charges=str(total_charges),
            total_discounts=str(total_discounts),
            tax_amount=str(tax_amount),
            total=str(total),
        )
        bus.publish(event)

        return entry

    # ------------------------------------------------------------------
    # Read methods (T198 support)
    # ------------------------------------------------------------------

    def get_po_cost_summary(self, po_id: UUID, company_id: UUID) -> POCostSummary:
        """Return current financial summary for a PO."""
        po = self.po_repo.get_by_id_or_none(po_id, company_id)
        if not po:
            raise NotFoundException(f"PurchaseOrder {po_id} not found.")
        return POCostSummary(
            po_id=str(po.id),
            po_number=po.po_number,
            supplier_id=po.supplier_id,
            status=po.status,
            currency_code=po.currency_code,
            subtotal=Decimal(str(po.subtotal)),
            total_charges=Decimal(str(po.total_charges)),
            total_discounts=Decimal(str(po.total_discounts)),
            tax_amount=Decimal(str(po.tax_amount)),
            total=Decimal(str(po.total)),
        )

    def get_gr_cost_summary(self, gr_id: UUID, company_id: UUID) -> GRCostSummary:
        """Return cost summary for a GR with PPV per line."""
        gr = self.gr_repo.get_by_id_or_none(gr_id, company_id)
        if not gr:
            raise NotFoundException(f"GoodsReceipt {gr_id} not found.")

        lines = self.gr_line_repo.list_for_gr(gr_id, company_id)

        ppv_lines = []
        total_ppv = Decimal("0.00")
        subtotal = Decimal("0.00")

        for ln in lines:
            qty = Decimal(str(ln.quantity_received))
            unit_cost = Decimal(str(ln.unit_cost))
            po_unit_cost = Decimal(str(ln.po_unit_cost))
            ppv_amount = Decimal(str(ln.ppv_amount))
            ppv_pct = Decimal(str(ln.ppv_percentage))

            subtotal += (unit_cost * qty).quantize(_TWO, rounding=ROUND_HALF_UP)
            total_ppv += ppv_amount

            ppv_lines.append(
                PPVLine(
                    gr_line_id=str(ln.id),
                    po_line_id=str(ln.po_line_id),
                    product_id=str(ln.product_id) if ln.product_id else None,
                    quantity_received=qty,
                    unit_cost=unit_cost,
                    po_unit_cost=po_unit_cost,
                    ppv_amount=ppv_amount,
                    ppv_percentage=ppv_pct,
                )
            )

        return GRCostSummary(
            gr_id=str(gr.id),
            gr_number=gr.gr_number,
            po_id=str(gr.po_id),
            supplier_id=str(gr.supplier_id) if gr.supplier_id else "",
            status=gr.status,
            subtotal=subtotal,
            ppv_lines=ppv_lines,
            total_ppv_amount=total_ppv.quantize(_TWO, rounding=ROUND_HALF_UP),
        )

    def get_cost_entry_for_gr(
        self, gr_id: UUID, company_id: UUID
    ) -> PurchaseCostEntryRead:
        """Return the PurchaseCostEntry for a confirmed GR."""
        entry = self._get_entry_for_gr(str(gr_id), company_id)
        if not entry:
            raise NotFoundException(
                f"No PurchaseCostEntry found for GoodsReceipt {gr_id}."
            )
        return PurchaseCostEntryRead.model_validate(entry)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_policy(self, company_id: UUID) -> PurchasePolicy | None:
        stmt = (
            select(PurchasePolicy)
            .where(PurchasePolicy.company_id == company_id)
            .where(PurchasePolicy.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()

    def _get_entry_for_gr(
        self, gr_id_str: str, company_id: UUID
    ) -> PurchaseCostEntry | None:
        stmt = (
            select(PurchaseCostEntry)
            .where(PurchaseCostEntry.company_id == company_id)
            .where(PurchaseCostEntry.gr_id == gr_id_str)
            .where(PurchaseCostEntry.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()
