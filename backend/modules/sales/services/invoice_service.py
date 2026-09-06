"""Sales Invoice application service — Phase 6.

Services:
  InvoiceService — full invoice lifecycle: create (from DN/SO/manual),
                   issue, cancel, credit note, view, list.

State machine (SalesInvoice.status):
  DRAFT → ISSUED | CANCELLED
  ISSUED → PAID (future) | CREDIT_NOTE_ISSUED
  PAID → (terminal)
  CANCELLED → (terminal)
  CREDIT_NOTE_ISSUED → (terminal)

Invoice creation modes (T162):
  1. from_delivery_note: map DN lines → invoice lines; one DN per invoice.
  2. from_sales_order: invoice all ordered quantities directly.
  3. manual: explicit lines provided by caller (no DN/SO required).

Gap-free numbering (T161):
  Uses SalesSequenceService with SELECT FOR UPDATE on sales_sequences table.
  Cancelled invoices retain their number (void, no reuse).

SO status auto-update (T167):
  When an invoice is issued, if the related SO is DELIVERED → INVOICED.

Due date calculation (T165):
  invoice_date + payment_term.due_days if payment_term_id is provided.
  Falls back to invoice_date (net 0) when no payment term.

Amount-in-words (T166):
  Simple English word generation for the total amount.

Spec ref: specs/007-sales-management/spec.md §18
Task: T161–T168
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
from core.utils.datetime import utcnow
from modules.sales.events import get_event_bus
from modules.sales.events.invoice_events import (
    InvoiceCancelled,
    InvoiceCreated,
    InvoiceCreditNoteIssued,
    InvoiceIssued,
)
from modules.sales.models.delivery import DeliveryNote
from modules.sales.models.invoice import InvoiceCharge, InvoiceLine, SalesInvoice
from modules.sales.models.order import SalesOrder
from modules.sales.repositories.delivery import (
    DeliveryNoteLineRepository,
    DeliveryNoteRepository,
)
from modules.sales.repositories.invoice import (
    InvoiceChargeRepository,
    InvoiceLineRepository,
    SalesInvoiceRepository,
)
from modules.sales.repositories.order import OrderLineRepository, SalesOrderRepository
from modules.sales.schemas.invoice import (
    InvoiceChargeCreate,
    InvoiceCreate,
    InvoiceCreditNoteRequest,
    InvoiceIssueRequest,
    InvoiceLineCreate,
)
from modules.sales.services.sequence_service import SalesSequenceService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, list[str]] = {
    "DRAFT": ["ISSUED", "CANCELLED"],
    "ISSUED": ["PAID", "CREDIT_NOTE_ISSUED"],
    "PAID": [],
    "CANCELLED": [],
    "CREDIT_NOTE_ISSUED": [],
}

_TERMINAL_STATUSES = {"PAID", "CANCELLED", "CREDIT_NOTE_ISSUED"}

# SO statuses eligible for direct invoicing (from order)
_INVOICEABLE_SO_STATUSES = {"APPROVED", "PARTIALLY_DELIVERED", "DELIVERED"}


def _assert_invoice_transition(current: str, target: str) -> None:
    """Raise ConflictException if the invoice status transition is invalid."""
    allowed = _VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise ConflictException(
            f"Invalid invoice status transition: {current!r} → {target!r}. "
            f"Allowed: {allowed}"
        )


# ---------------------------------------------------------------------------
# Amount-in-words helpers (T166)
# ---------------------------------------------------------------------------

_ONES = [
    "",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
_TENS = [
    "",
    "",
    "twenty",
    "thirty",
    "forty",
    "fifty",
    "sixty",
    "seventy",
    "eighty",
    "ninety",
]


def _int_to_words(n: int) -> str:
    """Convert a non-negative integer to English words."""
    if n < 0:
        return "minus " + _int_to_words(-n)
    if n == 0:
        return "zero"
    if n < 20:
        return _ONES[n]
    if n < 100:
        rest = _int_to_words(n % 10) if n % 10 else ""
        return (_TENS[n // 10] + (" " + rest if rest else "")).strip()
    if n < 1000:
        rest = _int_to_words(n % 100) if n % 100 else ""
        return (_ONES[n // 100] + " hundred" + (" " + rest if rest else "")).strip()
    if n < 1_000_000:
        rest = _int_to_words(n % 1000) if n % 1000 else ""
        return (
            _int_to_words(n // 1000) + " thousand" + (" " + rest if rest else "")
        ).strip()
    if n < 1_000_000_000:
        rest = _int_to_words(n % 1_000_000) if n % 1_000_000 else ""
        return (
            _int_to_words(n // 1_000_000) + " million" + (" " + rest if rest else "")
        ).strip()
    rest = _int_to_words(n % 1_000_000_000) if n % 1_000_000_000 else ""
    return (
        _int_to_words(n // 1_000_000_000) + " billion" + (" " + rest if rest else "")
    ).strip()


def amount_in_words(amount: Decimal, currency: str = "USD") -> str:
    """Generate a human-readable amount string.

    Example: Decimal("1234.56"), "USD" → "one thousand two hundred thirty four dollars and 56 cents"
    """
    if amount < 0:
        return f"negative {amount_in_words(-amount, currency)}"
    cents_map = {"USD": ("dollar", "dollars", "cent", "cents")}
    singular, plural, cent_singular, cent_plural = cents_map.get(
        currency, ("unit", "units", "cent", "cents")
    )
    total_cents = int(round(amount * 100))
    dollars = total_cents // 100
    cents = total_cents % 100

    dollar_words = _int_to_words(dollars)
    dollar_label = singular if dollars == 1 else plural
    result = f"{dollar_words} {dollar_label}"
    if cents:
        cent_words = _int_to_words(cents)
        cent_label = cent_singular if cents == 1 else cent_plural
        result += f" and {cent_words} {cent_label}"
    return result


# ---------------------------------------------------------------------------
# InvoiceService
# ---------------------------------------------------------------------------


class InvoiceService:
    """Orchestrates the full Sales Invoice lifecycle.

    All public methods flush to the session but do NOT commit — the caller
    (or FastAPI dependency) owns the transaction boundary.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._invoice_repo = SalesInvoiceRepository(db)
        self._line_repo = InvoiceLineRepository(db)
        self._charge_repo = InvoiceChargeRepository(db)
        self._order_repo = SalesOrderRepository(db)
        self._order_line_repo = OrderLineRepository(db)
        self._dn_repo = DeliveryNoteRepository(db)
        self._dn_line_repo = DeliveryNoteLineRepository(db)
        self._seq_service = SalesSequenceService(db=db)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_invoice_or_raise(self, company_id: UUID, invoice_id: UUID) -> SalesInvoice:
        inv = self._invoice_repo.get_by_id_or_none(invoice_id, company_id)
        if inv is None:
            raise NotFoundException(f"Invoice {invoice_id} not found.")
        return inv

    def _calculate_due_date(
        self,
        invoice_date_str: str,
        payment_term_id: str | None,
        company_id: UUID,
    ) -> str:
        """Calculate due date from invoice_date + payment term due_days."""
        inv_date = date.fromisoformat(invoice_date_str)
        if payment_term_id:
            from modules.sales.models.master import SalesPaymentTerm  # noqa: PLC0415

            # Tenant-isolation defect fixed during pre-Epic-9 hardening audit
            # (2026-08-14): payment_term_id comes from the request body and
            # was looked up with no company_id filter, letting a caller in
            # Company A pass a guessed Company B payment-term UUID and have
            # its due_days silently applied to (and the foreign id persisted
            # on) Company A's invoice.
            term = (
                self._db.query(SalesPaymentTerm)
                .filter(
                    SalesPaymentTerm.id == UUID(payment_term_id),
                    SalesPaymentTerm.company_id == company_id,
                )
                .first()
            )
            if term and term.due_days:
                return (inv_date + timedelta(days=int(term.due_days))).isoformat()
        return invoice_date_str  # net 0 default

    def _compute_line_amounts(
        self,
        line_data: InvoiceLineCreate,
        line_number: int,
        company_id: UUID,
        invoice_id: str,
    ) -> InvoiceLine:
        """Compute extended_amount and build an InvoiceLine ORM object."""
        gross = line_data.quantity * line_data.unit_price
        # Apply discount
        disc_pct = line_data.discount_percentage or Decimal("0")
        disc_amt = line_data.discount_amount or Decimal("0")
        if disc_pct:
            disc_amt = (gross * disc_pct / 100).quantize(Decimal("0.01"))
        extended = (gross - disc_amt).quantize(Decimal("0.01"))
        # Tax (future hook — default 0)
        tax_rate = line_data.tax_rate or Decimal("0")
        tax_amount = (extended * tax_rate).quantize(Decimal("0.01"))

        return InvoiceLine(
            company_id=company_id,
            invoice_id=invoice_id,
            line_number=line_number,
            product_id=str(line_data.product_id) if line_data.product_id else None,
            description=line_data.description,
            quantity=line_data.quantity,
            unit_of_measure=line_data.unit_of_measure,
            unit_price=line_data.unit_price,
            discount_percentage=line_data.discount_percentage,
            discount_amount=disc_amt if disc_amt else None,
            tax_rate=tax_rate if tax_rate else None,
            tax_amount=tax_amount,
            extended_amount=extended,
            delivery_note_line_id=(
                str(line_data.delivery_note_line_id)
                if line_data.delivery_note_line_id
                else None
            ),
            order_line_id=(
                str(line_data.order_line_id) if line_data.order_line_id else None
            ),
        )

    def _lines_from_delivery_note(
        self,
        dn: DeliveryNote,
        company_id: UUID,
        invoice_id: str,
    ) -> tuple[list[InvoiceLine], Decimal]:
        """Build invoice lines from a delivered delivery note."""
        dn_lines = self._dn_line_repo.list_for_delivery_note(company_id, dn.id)
        orm_lines = []
        subtotal = Decimal("0")
        for i, dn_line in enumerate(dn_lines, start=1):
            # Determine unit price from order line if possible
            unit_price = Decimal("0")
            if dn_line.order_line_id:
                ol = self._order_line_repo.get_by_id_or_none(
                    UUID(dn_line.order_line_id), company_id
                )
                if ol is not None:
                    unit_price = Decimal(str(ol.unit_price))
            qty = Decimal(str(dn_line.quantity_dispatched))
            extended = (qty * unit_price).quantize(Decimal("0.01"))
            line = InvoiceLine(
                company_id=company_id,
                invoice_id=invoice_id,
                line_number=i,
                product_id=dn_line.product_id if dn_line.product_id else None,
                description=dn_line.description,
                quantity=qty,
                unit_of_measure=dn_line.unit_of_measure,
                unit_price=unit_price,
                discount_percentage=None,
                discount_amount=None,
                tax_rate=None,
                tax_amount=Decimal("0"),
                extended_amount=extended,
                delivery_note_line_id=str(dn_line.id),
                order_line_id=dn_line.order_line_id if dn_line.order_line_id else None,
            )
            orm_lines.append(line)
            subtotal += extended
        return orm_lines, subtotal

    def _lines_from_sales_order(
        self,
        order: SalesOrder,
        company_id: UUID,
        invoice_id: str,
    ) -> tuple[list[InvoiceLine], Decimal]:
        """Build invoice lines from all SO lines (ordered quantities)."""
        order_lines = self._order_line_repo.list_for_order(company_id, order.id)
        orm_lines = []
        subtotal = Decimal("0")
        for i, ol in enumerate(order_lines, start=1):
            qty = Decimal(str(ol.quantity_ordered))
            unit_price = Decimal(str(ol.unit_price))
            extended = (qty * unit_price).quantize(Decimal("0.01"))
            line = InvoiceLine(
                company_id=company_id,
                invoice_id=invoice_id,
                line_number=i,
                product_id=ol.product_id if ol.product_id else None,
                description=ol.description,
                quantity=qty,
                unit_of_measure=ol.unit_of_measure,
                unit_price=unit_price,
                discount_percentage=None,
                discount_amount=None,
                tax_rate=None,
                tax_amount=Decimal("0"),
                extended_amount=extended,
                delivery_note_line_id=None,
                order_line_id=str(ol.id),
            )
            orm_lines.append(line)
            subtotal += extended
        return orm_lines, subtotal

    def _build_charges(
        self,
        charge_data_list: list[InvoiceChargeCreate],
        company_id: UUID,
        invoice_id: str,
    ) -> tuple[list[InvoiceCharge], Decimal]:
        """Build InvoiceCharge ORM objects and compute total charges amount."""
        charges = []
        total = Decimal("0")
        for cd in charge_data_list:
            charge = InvoiceCharge(
                company_id=company_id,
                invoice_id=invoice_id,
                charge_type=cd.charge_type,
                description=cd.description,
                amount=cd.amount,
                tax_applicable=cd.tax_applicable,
            )
            charges.append(charge)
            total += cd.amount
        return charges, total

    def _update_so_status_to_invoiced(
        self, order_id: str | None, company_id: UUID
    ) -> None:
        """Transition SO from DELIVERED → INVOICED when invoice is issued (T167)."""
        if not order_id:
            return
        try:
            order = (
                self._db.query(SalesOrder)
                .filter(
                    SalesOrder.id == order_id,
                    SalesOrder.company_id == company_id,
                    SalesOrder.is_deleted.is_(False),
                )
                .first()
            )
            if order and order.status == "DELIVERED":
                order.status = "INVOICED"
                order.updated_at = utcnow()
                self._db.flush()
        except Exception:  # noqa: BLE001
            logger.warning("Could not update SO %s status to INVOICED", order_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_invoice(
        self,
        company_id: UUID,
        data: InvoiceCreate,
        created_by: UUID,
    ) -> SalesInvoice:
        """Create a new SalesInvoice in DRAFT status.

        Supports three modes:
          - delivery_note_id provided: invoice from DN delivered quantities
          - order_id provided (no DN): invoice from SO ordered quantities
          - neither: manual invoice with explicit lines from data.lines

        Args:
            company_id: Tenant identifier.
            data:       InvoiceCreate payload.
            created_by: User creating the invoice.

        Returns:
            The newly created SalesInvoice ORM instance (DRAFT).

        Raises:
            NotFoundException: If referenced DN or SO does not exist.
            ConflictException: If DN is not in DISPATCHED/DELIVERED status,
                               or SO is not in an invoiceable status.
        """
        # ---- Validate references -------------------------------------------
        order: SalesOrder | None = None
        dn: DeliveryNote | None = None

        if data.delivery_note_id:
            dn = self._dn_repo.get_by_id_or_none(data.delivery_note_id, company_id)
            if dn is None:
                raise NotFoundException(
                    f"Delivery note {data.delivery_note_id} not found."
                )
            if dn.status not in ("DISPATCHED", "DELIVERED"):
                raise ConflictException(
                    f"Cannot invoice delivery note in status '{dn.status}'. "
                    "Delivery note must be DISPATCHED or DELIVERED."
                )
            if dn.order_id:
                order = self._order_repo.get_by_id_or_none(
                    UUID(dn.order_id), company_id
                )

        elif data.order_id:
            order = self._order_repo.get_by_id_or_none(data.order_id, company_id)
            if order is None:
                raise NotFoundException(f"Sales order {data.order_id} not found.")
            if order.status not in _INVOICEABLE_SO_STATUSES:
                raise ConflictException(
                    f"Cannot invoice order in status '{order.status}'. "
                    f"Order must be in: {sorted(_INVOICEABLE_SO_STATUSES)}"
                )

        # ---- Gap-free invoice number (T161) ----------------------------------
        invoice_number = self._seq_service.generate_next_number(
            company_id=company_id,
            document_type="SI",
        )

        # ---- Due date calculation (T165) -------------------------------------
        due_date = self._calculate_due_date(
            data.invoice_date,
            str(data.payment_term_id) if data.payment_term_id else None,
            company_id,
        )

        # ---- Create invoice header -------------------------------------------
        invoice = SalesInvoice(
            company_id=company_id,
            invoice_number=invoice_number,
            customer_id=str(data.customer_id),
            order_id=(
                str(order.id)
                if order
                else (str(data.order_id) if data.order_id else None)
            ),
            delivery_note_id=str(dn.id) if dn else None,
            payment_term_id=str(data.payment_term_id) if data.payment_term_id else None,
            billing_address_id=(
                str(data.billing_address_id) if data.billing_address_id else None
            ),
            invoice_date=data.invoice_date,
            due_date=due_date,
            currency_code=data.currency_code,
            status="DRAFT",
            subtotal=Decimal("0"),
            discount_amount=Decimal("0"),
            tax_amount=Decimal("0"),
            charges_amount=Decimal("0"),
            total_amount=Decimal("0"),
            internal_notes=data.internal_notes,
            customer_notes=data.customer_notes,
            created_by=created_by,
            version=1,
        )
        self._db.add(invoice)
        self._db.flush()  # get invoice.id

        invoice_id_str = str(invoice.id)

        # ---- Build lines (T162) ---------------------------------------------
        orm_lines: list[InvoiceLine] = []
        subtotal = Decimal("0")

        if dn is not None:
            orm_lines, subtotal = self._lines_from_delivery_note(
                dn, company_id, invoice_id_str
            )
        elif order is not None and not data.lines:
            orm_lines, subtotal = self._lines_from_sales_order(
                order, company_id, invoice_id_str
            )
        else:
            # Manual mode or explicit lines with order context
            for i, line_data in enumerate(data.lines, start=1):
                ol = self._compute_line_amounts(
                    line_data, i, company_id, invoice_id_str
                )
                orm_lines.append(ol)
                subtotal += ol.extended_amount

        for line in orm_lines:
            line.created_by = created_by
            self._db.add(line)

        # ---- Build charges (T166) -------------------------------------------
        orm_charges, charges_amount = self._build_charges(
            data.charges, company_id, invoice_id_str
        )
        for charge in orm_charges:
            charge.created_by = created_by
            self._db.add(charge)

        # ---- Compute totals --------------------------------------------------
        # Genuine defect found live during pre-Epic-9 hardening audit
        # (2026-08-14): sum() over an empty orm_lines iterable (a
        # zero-line invoice) returns the built-in int 0, not Decimal("0"),
        # since sum() has no explicit start value — .quantize() below then
        # crashed with AttributeError: 'int' object has no attribute
        # 'quantize'. Confirmed live: POST /sales/invoices with lines=[]
        # returned a real 500. Also flagged by mypy pre-existing
        # ("Item 'int' of 'Decimal | Literal[0]' has no attribute
        # 'quantize'") but never actually triggered until this audit
        # exercised the zero-line path. Fix: explicit Decimal("0") start.
        discount_amount = sum(
            (
                Decimal(str(ln.discount_amount)) if ln.discount_amount else Decimal("0")
                for ln in orm_lines
            ),
            start=Decimal("0"),
        )
        tax_amount = sum(
            (Decimal(str(ln.tax_amount)) for ln in orm_lines), start=Decimal("0")
        )
        total_amount = (subtotal + tax_amount + charges_amount).quantize(
            Decimal("0.01")
        )

        # ---- Amount-in-words (T166) -----------------------------------------
        words = amount_in_words(total_amount, data.currency_code)

        invoice.subtotal = subtotal.quantize(Decimal("0.01"))
        invoice.discount_amount = discount_amount.quantize(Decimal("0.01"))
        invoice.tax_amount = tax_amount.quantize(Decimal("0.01"))
        invoice.charges_amount = charges_amount.quantize(Decimal("0.01"))
        invoice.total_amount = total_amount
        invoice.amount_in_words = words
        self._db.flush()
        # Missing-commit defect fixed during Epic 1-8 live verification
        # (2026-08-14) — see backend/modules/inventory/services/
        # warehouse_service.py::create_warehouse's comment for the full
        # root-cause explanation.
        self._db.commit()

        # ---- Publish event --------------------------------------------------
        try:
            get_event_bus().publish(
                InvoiceCreated(
                    aggregate_id=invoice.id,
                    company_id=company_id,
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    customer_id=invoice.customer_id,
                    order_id=invoice.order_id,
                    delivery_note_id=invoice.delivery_note_id,
                    total_amount=str(invoice.total_amount),
                    currency_code=invoice.currency_code,
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to publish InvoiceCreated event")

        logger.info(
            "Invoice created: %s (company=%s status=DRAFT)",
            invoice.invoice_number,
            company_id,
        )
        return invoice

    def issue_invoice(
        self,
        company_id: UUID,
        invoice_id: UUID,
        data: InvoiceIssueRequest,
        issued_by: UUID,
    ) -> SalesInvoice:
        """Transition invoice from DRAFT → ISSUED.

        ISSUED invoices are immutable — no further edits (T164).
        Updates SO status DELIVERED → INVOICED (T167).

        Returns the updated SalesInvoice.
        Raises ConflictException on invalid transition.
        """
        invoice = self._get_invoice_or_raise(company_id, invoice_id)
        _assert_invoice_transition(invoice.status, "ISSUED")

        invoice.status = "ISSUED"
        invoice.updated_at = utcnow()
        self._db.flush()

        # SO status auto-update (T167)
        self._update_so_status_to_invoiced(invoice.order_id, company_id)

        # Missing-commit defect fixed during Epic 1-8 live verification
        # (2026-08-14) — see create_invoice() above. This is the exact event
        # (InvoiceIssued) Accounting's handle_sales_invoice_posted
        # subscribes to for the Sales-to-Cash integration — the invoice's
        # own ISSUED status was never durably persisted despite the event
        # firing.
        self._db.commit()

        # Publish event
        try:
            get_event_bus().publish(
                InvoiceIssued(
                    aggregate_id=invoice.id,
                    company_id=company_id,
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    customer_id=invoice.customer_id,
                    due_date=invoice.due_date,
                    total_amount=str(invoice.total_amount),
                    currency_code=invoice.currency_code,
                    issued_by=str(issued_by),
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to publish InvoiceIssued event")

        logger.info(
            "Invoice issued: %s (company=%s)",
            invoice.invoice_number,
            company_id,
        )
        return invoice

    def cancel_invoice(
        self,
        company_id: UUID,
        invoice_id: UUID,
        cancelled_by: UUID,
    ) -> SalesInvoice:
        """Cancel an invoice (DRAFT → CANCELLED).

        Cancelled invoices retain their number — no reuse (T168).
        Only DRAFT invoices can be cancelled directly.

        Returns the updated SalesInvoice.
        Raises ConflictException if not in DRAFT status.
        """
        invoice = self._get_invoice_or_raise(company_id, invoice_id)
        previous_status = invoice.status
        _assert_invoice_transition(invoice.status, "CANCELLED")

        invoice.status = "CANCELLED"
        invoice.updated_at = utcnow()
        self._db.flush()
        self._db.commit()

        # Publish event
        try:
            get_event_bus().publish(
                InvoiceCancelled(
                    aggregate_id=invoice.id,
                    company_id=company_id,
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    customer_id=invoice.customer_id,
                    previous_status=previous_status,
                    cancelled_by=str(cancelled_by),
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to publish InvoiceCancelled event")

        logger.info(
            "Invoice cancelled: %s (company=%s number_retained=%s)",
            invoice.invoice_number,
            company_id,
            invoice.invoice_number,
        )
        return invoice

    def issue_credit_note(
        self,
        company_id: UUID,
        invoice_id: UUID,
        data: InvoiceCreditNoteRequest,
        issued_by: UUID,
    ) -> SalesInvoice:
        """Issue a credit note against an ISSUED invoice (ISSUED → CREDIT_NOTE_ISSUED).

        Records the credit_note_amount on the invoice and transitions status.

        Returns the updated SalesInvoice.
        Raises ConflictException if not in ISSUED status.
        """
        invoice = self._get_invoice_or_raise(company_id, invoice_id)
        _assert_invoice_transition(invoice.status, "CREDIT_NOTE_ISSUED")

        if data.credit_note_amount > invoice.total_amount:
            raise ConflictException(
                f"Credit note amount {data.credit_note_amount} cannot exceed "
                f"invoice total {invoice.total_amount}."
            )

        invoice.status = "CREDIT_NOTE_ISSUED"
        invoice.credit_note_amount = data.credit_note_amount
        invoice.updated_at = utcnow()
        if data.notes:
            invoice.internal_notes = (
                (invoice.internal_notes or "") + f"\nCredit note: {data.notes}"
            ).strip()
        self._db.flush()
        self._db.commit()

        # Publish event
        try:
            get_event_bus().publish(
                InvoiceCreditNoteIssued(
                    aggregate_id=invoice.id,
                    company_id=company_id,
                    invoice_id=invoice.id,
                    invoice_number=invoice.invoice_number,
                    customer_id=invoice.customer_id,
                    credit_note_amount=str(data.credit_note_amount),
                    issued_by=str(issued_by),
                )
            )
        except Exception:  # noqa: BLE001
            logger.exception("Failed to publish InvoiceCreditNoteIssued event")

        logger.info(
            "Credit note issued against invoice %s (amount=%s)",
            invoice.invoice_number,
            data.credit_note_amount,
        )
        return invoice

    def get_invoice(self, company_id: UUID, invoice_id: UUID) -> SalesInvoice:
        """Return a SalesInvoice by ID, enforcing tenant isolation.

        Raises NotFoundException if not found.
        """
        return self._get_invoice_or_raise(company_id, invoice_id)

    def list_invoices(
        self,
        company_id: UUID,
        *,
        customer_id: str | None = None,
        status: str | None = None,
        order_id: str | None = None,
        delivery_note_id: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SalesInvoice], int]:
        """List invoices for a company with optional filters.

        Returns (items, total_count).
        """
        return self._invoice_repo.list_for_company(
            company_id,
            customer_id=customer_id,
            status=status,
            order_id=order_id,
            delivery_note_id=delivery_note_id,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )

    def get_invoice_lines(
        self,
        company_id: UUID,
        invoice_id: UUID,
    ) -> list[InvoiceLine]:
        """Return all lines for an invoice."""
        self._get_invoice_or_raise(company_id, invoice_id)
        return self._line_repo.list_for_invoice(company_id, invoice_id)

    def get_invoice_charges(
        self,
        company_id: UUID,
        invoice_id: UUID,
    ) -> list[InvoiceCharge]:
        """Return all charges for an invoice."""
        self._get_invoice_or_raise(company_id, invoice_id)
        return self._charge_repo.list_for_invoice(company_id, invoice_id)

    def export_pdf(
        self,
        company_id: UUID,
        invoice_id: UUID,
    ) -> bytes:
        """Export invoice as PDF (gated by feature flag sales.invoice_pdf_export).

        Returns a minimal plain-text PDF placeholder. Production PDF generation
        requires a PDF rendering library (weasyprint, reportlab, etc.).
        Spec ref: T169
        """
        invoice = self._get_invoice_or_raise(company_id, invoice_id)

        # Feature flag gate (T169)
        try:
            from modules.sales.repositories.feature_flag_repository import (  # noqa: PLC0415
                SalesFeatureFlagRepository,
            )
            from modules.sales.services.feature_flag_service import (  # noqa: PLC0415
                SalesFeatureFlagService,
            )

            flag_repo = SalesFeatureFlagRepository(self._db)
            flag_svc = SalesFeatureFlagService(db=self._db, flag_repo=flag_repo)
            if not flag_svc.is_enabled(
                "sales.invoice_pdf_export", company_id=company_id
            ):
                raise ConflictException(
                    "Invoice PDF export is not enabled for this company. "
                    "Enable the 'sales.invoice_pdf_export' feature flag to use this feature."
                )
        except ConflictException:
            raise
        except Exception:  # noqa: BLE001
            logger.warning("Could not check feature flag; proceeding with PDF export")

        # Minimal plaintext PDF (placeholder — production: use weasyprint/reportlab)
        content = (
            f"INVOICE: {invoice.invoice_number}\n"
            f"Customer: {invoice.customer_id}\n"
            f"Date: {invoice.invoice_date}\n"
            f"Due: {invoice.due_date}\n"
            f"Status: {invoice.status}\n"
            f"Total: {invoice.currency_code} {invoice.total_amount}\n"
            f"In Words: {invoice.amount_in_words or ''}\n"
        )
        return content.encode("utf-8")
