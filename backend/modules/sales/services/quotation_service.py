"""Sales Quotation application service — Phase 3.

Services:
  QuotationService    — lifecycle management, state machine, revision capture,
                         validity auto-expire, quotation-to-order conversion
  QuotationLineService — line CRUD with pricing integration

State machine (enforced at service layer):
  DRAFT → SENT_TO_CUSTOMER | CANCELLED
  SENT_TO_CUSTOMER → ACCEPTED | REJECTED | EXPIRED | CANCELLED
  ACCEPTED → CONVERTED | CANCELLED
  Terminals: REJECTED, CONVERTED, EXPIRED, CANCELLED

Spec ref: specs/007-sales-management/spec.md §Quotation
Task: T086, T087, T088, T089, T090
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from core.exceptions.base import NotFoundException
from core.utils.datetime import utcnow
from modules.sales.events import InProcessEventBus, get_event_bus
from modules.sales.events.quotation_events import (
    QuotationAccepted,
    QuotationCancelled,
    QuotationConverted,
    QuotationCreated,
    QuotationExpired,
    QuotationExpiringSoon,
    QuotationRejected,
    QuotationSent,
)
from modules.sales.models.quotation import (
    QuotationLine,
    QuotationRevision,
    SalesQuotation,
)
from modules.sales.repositories.pricing import (
    CustomerSpecificPriceRepository,
    PriceEntryRepository,
    PriceListRepository,
)
from modules.sales.repositories.quotation import (
    QuotationLineRepository,
    QuotationRevisionRepository,
    SalesQuotationRepository,
)
from modules.sales.schemas.quotation import (
    QuotationAcceptRequest,
    QuotationCancelRequest,
    QuotationConvertResponse,
    QuotationLineCreate,
    QuotationLineUpdate,
    QuotationRejectRequest,
    QuotationSendRequest,
    SalesQuotationCreate,
    SalesQuotationUpdate,
)
from modules.sales.services.pricing_service import PricingService
from modules.sales.services.sequence_service import SalesSequenceService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State machine transitions
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, list[str]] = {
    "DRAFT": ["SENT_TO_CUSTOMER", "CANCELLED"],
    "SENT_TO_CUSTOMER": ["ACCEPTED", "REJECTED", "EXPIRED", "CANCELLED"],
    "ACCEPTED": ["CONVERTED", "CANCELLED"],
    "REJECTED": [],
    "CONVERTED": [],
    "EXPIRED": [],
    "CANCELLED": [],
}

_TERMINAL_STATUSES = {"REJECTED", "CONVERTED", "EXPIRED", "CANCELLED"}


def _assert_transition(current: str, target: str) -> None:
    """Raise ValueError if the status transition is invalid."""
    allowed = _VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise ValueError(
            f"Invalid quotation status transition: {current!r} → {target!r}. "
            f"Allowed: {allowed}"
        )


# ---------------------------------------------------------------------------
# QuotationLineService
# ---------------------------------------------------------------------------


class QuotationLineService:
    """Service for managing lines within a Sales Quotation.

    Lines can only be added/updated/deleted on DRAFT quotations.
    Pricing is resolved via PricingService on line creation.
    """

    def __init__(
        self,
        db: Session,
        pricing_service: PricingService | None = None,
    ) -> None:
        self.db = db
        self._line_repo = QuotationLineRepository(db)
        self._quot_repo = SalesQuotationRepository(db)
        self._pricing = pricing_service or PricingService(
            db=db,
            price_list_repo=PriceListRepository(db),
            entry_repo=PriceEntryRepository(db),
            specific_repo=CustomerSpecificPriceRepository(db),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_draft(self, quotation: SalesQuotation) -> None:
        if quotation.status != "DRAFT":
            raise ValueError(
                f"Lines can only be modified on DRAFT quotations "
                f"(current status: {quotation.status!r})"
            )

    def _get_quotation(self, company_id: UUID, quotation_id: UUID) -> SalesQuotation:
        quot = self._quot_repo.get_by_id_or_none(quotation_id, company_id)
        if not quot:
            raise NotFoundException(f"Quotation not found: {quotation_id}")
        return quot

    def _compute_line_extended(
        self,
        unit_price: Decimal,
        quantity: Decimal,
        discount_percentage: Decimal | None,
    ) -> tuple[Decimal, Decimal | None]:
        """Return (extended_amount, discount_amount)."""
        gross = (unit_price * quantity).quantize(Decimal("0.01"))
        if discount_percentage is not None and discount_percentage > 0:
            disc = (gross * discount_percentage / Decimal("100")).quantize(
                Decimal("0.01")
            )
            return gross - disc, disc
        return gross, None

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def add_line(
        self,
        company_id: UUID,
        quotation_id: UUID,
        data: QuotationLineCreate,
        added_by: UUID | None = None,
    ) -> QuotationLine:
        """Add a line to a DRAFT quotation, resolving price via PricingService."""
        quotation = self._get_quotation(company_id, quotation_id)
        self._require_draft(quotation)

        # Resolve unit_price via 7-level hierarchy (T090)
        unit_price = data.unit_price
        if data.product_id is not None:
            try:
                resolution = self._pricing.resolve(
                    company_id=company_id,
                    product_id=data.product_id,
                    quantity=data.quantity,
                    customer_id=quotation.customer_id,  # type: ignore[arg-type]
                )
                if resolution and resolution.resolution_level < 7:
                    # Override with resolved price only if caller didn't set explicit price
                    # (unit_price=0 is treated as "not set" for price resolution)
                    if data.unit_price == Decimal("0"):
                        unit_price = resolution.unit_price
            except Exception:
                logger.debug(
                    "Price resolution failed for product %s; using caller price",
                    data.product_id,
                    exc_info=True,
                )

        line_number = self._line_repo.next_line_number(company_id, quotation_id)
        extended, disc_amount = self._compute_line_extended(
            unit_price, data.quantity, data.discount_percentage
        )

        line = QuotationLine(
            company_id=company_id,
            quotation_id=str(quotation_id),
            line_number=line_number,
            product_id=str(data.product_id) if data.product_id else None,
            description=data.description,
            quantity=data.quantity,
            unit_of_measure=data.unit_of_measure,
            unit_price=unit_price,
            discount_percentage=data.discount_percentage,
            discount_amount=disc_amount,
            tax_category=data.tax_category,
            extended_amount=extended,
            notes=data.notes,
            created_by=added_by,
        )
        self.db.add(line)
        self.db.flush()

        # Recalculate quotation totals
        _recalculate_totals(quotation, self._line_repo)
        return line

    def update_line(
        self,
        company_id: UUID,
        quotation_id: UUID,
        line_id: UUID,
        data: QuotationLineUpdate,
        updated_by: UUID | None = None,
    ) -> QuotationLine:
        """Update a line on a DRAFT quotation."""
        quotation = self._get_quotation(company_id, quotation_id)
        self._require_draft(quotation)

        line = self._line_repo.get_by_id_or_none(line_id, company_id)
        if not line or line.quotation_id != str(quotation_id):
            raise NotFoundException(f"Quotation line not found: {line_id}")

        if data.description is not None:
            line.description = data.description
        if data.quantity is not None:
            line.quantity = data.quantity
        if data.unit_of_measure is not None:
            line.unit_of_measure = data.unit_of_measure
        if data.unit_price is not None:
            line.unit_price = data.unit_price
        if data.discount_percentage is not None:
            line.discount_percentage = data.discount_percentage
        if data.tax_category is not None:
            line.tax_category = data.tax_category
        if data.notes is not None:
            line.notes = data.notes
        if updated_by:
            line.updated_by = str(updated_by)

        # Recompute line totals
        extended, disc_amount = self._compute_line_extended(
            line.unit_price, line.quantity, line.discount_percentage
        )
        line.extended_amount = extended
        line.discount_amount = disc_amount

        self.db.flush()
        _recalculate_totals(quotation, self._line_repo)
        return line

    def delete_line(
        self,
        company_id: UUID,
        quotation_id: UUID,
        line_id: UUID,
        deleted_by: UUID | None = None,
    ) -> None:
        """Soft-delete a line from a DRAFT quotation."""
        quotation = self._get_quotation(company_id, quotation_id)
        self._require_draft(quotation)

        line = self._line_repo.get_by_id_or_none(line_id, company_id)
        if not line or line.quotation_id != str(quotation_id):
            raise NotFoundException(f"Quotation line not found: {line_id}")

        line.is_deleted = True
        if deleted_by:
            line.deleted_by = str(deleted_by)
        self.db.flush()
        _recalculate_totals(quotation, self._line_repo)


# ---------------------------------------------------------------------------
# Helper: recalculate quotation totals from active lines
# ---------------------------------------------------------------------------


def _recalculate_totals(
    quotation: SalesQuotation,
    line_repo: QuotationLineRepository,
) -> None:
    """Recompute subtotal/discount_amount/total_amount from active lines."""
    lines = line_repo.list_for_quotation(quotation.company_id, quotation.id)
    subtotal = sum(ln.extended_amount for ln in lines)
    quotation.subtotal = subtotal

    # Apply header-level discount
    disc_amount = Decimal("0")
    if quotation.discount_type and quotation.discount_value:
        if quotation.discount_type == "PERCENTAGE":
            disc_amount = (
                subtotal * quotation.discount_value / Decimal("100")
            ).quantize(Decimal("0.01"))
        else:  # AMOUNT
            disc_amount = min(quotation.discount_value, subtotal)
    quotation.discount_amount = disc_amount
    quotation.total_amount = subtotal - disc_amount + quotation.tax_amount


# ---------------------------------------------------------------------------
# QuotationService
# ---------------------------------------------------------------------------


class QuotationService:
    """Core service for Sales Quotation lifecycle management.

    Responsibilities:
      - CRUD: create, read, update, list quotations
      - State machine: send, accept, reject, expire, cancel, convert
      - Revision snapshots: capture on every DRAFT → transition
      - Validity management: auto-expire overdue SENT_TO_CUSTOMER quotations
      - Domain events: publish via InProcessEventBus
    """

    def __init__(
        self,
        db: Session,
        event_bus: InProcessEventBus | None = None,
    ) -> None:
        self.db = db
        self._quot_repo = SalesQuotationRepository(db)
        self._line_repo = QuotationLineRepository(db)
        self._rev_repo = QuotationRevisionRepository(db)
        self._seq_svc = SalesSequenceService(db)
        self._event_bus = event_bus or get_event_bus()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_or_404(self, company_id: UUID, quotation_id: UUID) -> SalesQuotation:
        quot = self._quot_repo.get_by_id_or_none(quotation_id, company_id)
        if not quot:
            raise NotFoundException(f"Quotation not found: {quotation_id}")
        return quot

    def _capture_revision(
        self,
        quotation: SalesQuotation,
        modified_by: UUID,
        change_summary: str | None = None,
    ) -> QuotationRevision:
        """Create an immutable revision snapshot of the quotation + lines."""
        lines = self._line_repo.list_for_quotation(quotation.company_id, quotation.id)
        lines_snapshot = [
            {
                "id": str(ln.id),
                "line_number": ln.line_number,
                "product_id": str(ln.product_id) if ln.product_id else None,
                "description": ln.description,
                "quantity": str(ln.quantity),
                "unit_of_measure": ln.unit_of_measure,
                "unit_price": str(ln.unit_price),
                "discount_percentage": (
                    str(ln.discount_percentage) if ln.discount_percentage else None
                ),
                "discount_amount": (
                    str(ln.discount_amount) if ln.discount_amount else None
                ),
                "extended_amount": str(ln.extended_amount),
                "tax_category": ln.tax_category,
                "notes": ln.notes,
            }
            for ln in lines
        ]
        snapshot = {
            "id": str(quotation.id),
            "quotation_number": quotation.quotation_number,
            "customer_id": str(quotation.customer_id),
            "quotation_date": quotation.quotation_date,
            "validity_date": quotation.validity_date,
            "currency_code": quotation.currency_code,
            "status": quotation.status,
            "revision_number": quotation.revision_number,
            "subtotal": str(quotation.subtotal),
            "discount_type": quotation.discount_type,
            "discount_value": (
                str(quotation.discount_value) if quotation.discount_value else None
            ),
            "discount_amount": str(quotation.discount_amount),
            "tax_amount": str(quotation.tax_amount),
            "total_amount": str(quotation.total_amount),
            "lines": lines_snapshot,
        }
        revision = QuotationRevision(
            company_id=quotation.company_id,
            quotation_id=str(quotation.id),
            revision_number=quotation.revision_number,
            snapshot=snapshot,
            modified_by=str(modified_by),
            modified_at=utcnow().isoformat(),
            change_summary=change_summary,
        )
        self.db.add(revision)
        self.db.flush()
        return revision

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(
        self,
        company_id: UUID,
        data: SalesQuotationCreate,
        created_by: UUID,
    ) -> SalesQuotation:
        """Create a new DRAFT quotation with auto-generated number."""
        quotation_number = self._seq_svc.generate_next_number(
            company_id=company_id, document_type="SQ"
        )

        # Compute initial totals from provided lines
        lines_data = data.lines
        subtotal = Decimal("0")
        for line_d in lines_data:
            gross = (line_d.unit_price * line_d.quantity).quantize(Decimal("0.01"))
            if line_d.discount_percentage:
                disc = (gross * line_d.discount_percentage / Decimal("100")).quantize(
                    Decimal("0.01")
                )
                gross -= disc
            subtotal += gross

        disc_amount = Decimal("0")
        if data.discount_type and data.discount_value:
            if data.discount_type == "PERCENTAGE":
                disc_amount = (
                    subtotal * data.discount_value / Decimal("100")
                ).quantize(Decimal("0.01"))
            else:
                disc_amount = min(data.discount_value, subtotal)

        quotation = SalesQuotation(
            company_id=company_id,
            quotation_number=quotation_number,
            customer_id=str(data.customer_id),
            quotation_date=data.quotation_date,
            validity_date=data.validity_date,
            currency_code=data.currency_code,
            payment_term_id=str(data.payment_term_id) if data.payment_term_id else None,
            shipping_address_id=(
                str(data.shipping_address_id) if data.shipping_address_id else None
            ),
            billing_address_id=(
                str(data.billing_address_id) if data.billing_address_id else None
            ),
            sales_rep_id=str(data.sales_rep_id),
            status="DRAFT",
            revision_number=1,
            subtotal=subtotal,
            discount_type=data.discount_type,
            discount_value=data.discount_value,
            discount_amount=disc_amount,
            tax_amount=Decimal("0"),
            total_amount=subtotal - disc_amount,
            internal_notes=data.internal_notes,
            customer_notes=data.customer_notes,
            version=1,
            created_by=created_by,
        )
        self.db.add(quotation)
        self.db.flush()

        # Create lines
        for line_d in lines_data:
            gross = (line_d.unit_price * line_d.quantity).quantize(Decimal("0.01"))
            disc_a = None
            if line_d.discount_percentage:
                disc_a = (gross * line_d.discount_percentage / Decimal("100")).quantize(
                    Decimal("0.01")
                )
                gross -= disc_a
            ln_num = self._line_repo.next_line_number(company_id, quotation.id)
            line = QuotationLine(
                company_id=company_id,
                quotation_id=str(quotation.id),
                line_number=ln_num,
                product_id=str(line_d.product_id) if line_d.product_id else None,
                description=line_d.description,
                quantity=line_d.quantity,
                unit_of_measure=line_d.unit_of_measure,
                unit_price=line_d.unit_price,
                discount_percentage=line_d.discount_percentage,
                discount_amount=disc_a,
                tax_category=line_d.tax_category,
                extended_amount=gross,
                notes=line_d.notes,
                created_by=created_by,
            )
            self.db.add(line)
        self.db.flush()

        # Capture initial revision
        self._capture_revision(quotation, created_by, change_summary="Initial creation")

        self._event_bus.publish(
            QuotationCreated(
                aggregate_id=UUID(str(quotation.id)),
                company_id=company_id,
                quotation_id=UUID(str(quotation.id)),
                quotation_number=quotation_number,
                customer_id=UUID(str(data.customer_id)),
                sales_rep_id=UUID(str(data.sales_rep_id)),
                validity_date=data.validity_date,
                created_by=created_by,
            )
        )
        logger.info("Quotation created: %s company=%s", quotation_number, company_id)
        return quotation

    def get(self, company_id: UUID, quotation_id: UUID) -> SalesQuotation:
        """Return a quotation by ID or raise NotFoundException."""
        return self._get_or_404(company_id, quotation_id)

    def list(
        self,
        company_id: UUID,
        status: str | None = None,
        customer_id: UUID | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[SalesQuotation]:
        """List quotations with optional filters."""
        return self._quot_repo.list_for_company(
            company_id,
            status=status,
            customer_id=customer_id,
            search=search,
            skip=skip,
            limit=limit,
        )

    def count(
        self,
        company_id: UUID,
        status: str | None = None,
        customer_id: UUID | None = None,
    ) -> int:
        """Count quotations matching filters."""
        return self._quot_repo.count_for_company(company_id, status, customer_id)

    def update(
        self,
        company_id: UUID,
        quotation_id: UUID,
        data: SalesQuotationUpdate,
        updated_by: UUID,
    ) -> SalesQuotation:
        """Update a DRAFT quotation header. Increments revision_number."""
        quotation = self._get_or_404(company_id, quotation_id)
        if quotation.status != "DRAFT":
            raise ValueError(
                f"Only DRAFT quotations can be updated "
                f"(current status: {quotation.status!r})"
            )

        if data.validity_date is not None:
            quotation.validity_date = data.validity_date
        if data.currency_code is not None:
            quotation.currency_code = data.currency_code
        if data.payment_term_id is not None:
            quotation.payment_term_id = str(data.payment_term_id)
        if data.shipping_address_id is not None:
            quotation.shipping_address_id = str(data.shipping_address_id)
        if data.billing_address_id is not None:
            quotation.billing_address_id = str(data.billing_address_id)
        if data.sales_rep_id is not None:
            quotation.sales_rep_id = str(data.sales_rep_id)
        if data.discount_type is not None:
            quotation.discount_type = data.discount_type
        if data.discount_value is not None:
            quotation.discount_value = data.discount_value
        if data.internal_notes is not None:
            quotation.internal_notes = data.internal_notes
        if data.customer_notes is not None:
            quotation.customer_notes = data.customer_notes

        quotation.updated_by = str(updated_by)
        quotation.revision_number += 1

        # Recalculate totals
        _recalculate_totals(quotation, self._line_repo)
        self.db.flush()

        # Capture revision snapshot
        self._capture_revision(quotation, updated_by, change_summary="Header updated")
        return quotation

    # ------------------------------------------------------------------
    # State machine transitions
    # ------------------------------------------------------------------

    def send(
        self,
        company_id: UUID,
        quotation_id: UUID,
        request: QuotationSendRequest,
        sent_by: UUID,
    ) -> SalesQuotation:
        """Transition DRAFT → SENT_TO_CUSTOMER."""
        quotation = self._get_or_404(company_id, quotation_id)
        _assert_transition(quotation.status, "SENT_TO_CUSTOMER")

        quotation.status = "SENT_TO_CUSTOMER"
        quotation.updated_by = str(sent_by)
        if request.notes:
            quotation.internal_notes = (
                (quotation.internal_notes or "") + f"\n[SENT] {request.notes}"
            ).strip()
        self.db.flush()

        self._capture_revision(quotation, sent_by, change_summary="Sent to customer")
        self._event_bus.publish(
            QuotationSent(
                aggregate_id=UUID(str(quotation.id)),
                company_id=company_id,
                quotation_id=UUID(str(quotation.id)),
                quotation_number=quotation.quotation_number,
                customer_id=UUID(str(quotation.customer_id)),
                validity_date=quotation.validity_date,
                sent_by=sent_by,
            )
        )
        return quotation

    def accept(
        self,
        company_id: UUID,
        quotation_id: UUID,
        request: QuotationAcceptRequest,
        accepted_by: UUID,
    ) -> SalesQuotation:
        """Transition SENT_TO_CUSTOMER → ACCEPTED."""
        quotation = self._get_or_404(company_id, quotation_id)
        _assert_transition(quotation.status, "ACCEPTED")

        quotation.status = "ACCEPTED"
        quotation.updated_by = str(accepted_by)
        if request.notes:
            quotation.internal_notes = (
                (quotation.internal_notes or "") + f"\n[ACCEPTED] {request.notes}"
            ).strip()
        self.db.flush()

        self._capture_revision(
            quotation, accepted_by, change_summary="Accepted by customer"
        )
        self._event_bus.publish(
            QuotationAccepted(
                aggregate_id=UUID(str(quotation.id)),
                company_id=company_id,
                quotation_id=UUID(str(quotation.id)),
                quotation_number=quotation.quotation_number,
                customer_id=UUID(str(quotation.customer_id)),
                total_amount=float(quotation.total_amount),
                accepted_by=accepted_by,
            )
        )
        return quotation

    def reject(
        self,
        company_id: UUID,
        quotation_id: UUID,
        request: QuotationRejectRequest,
        rejected_by: UUID,
    ) -> SalesQuotation:
        """Transition SENT_TO_CUSTOMER → REJECTED (terminal)."""
        quotation = self._get_or_404(company_id, quotation_id)
        _assert_transition(quotation.status, "REJECTED")

        quotation.status = "REJECTED"
        quotation.updated_by = str(rejected_by)
        self.db.flush()

        self._capture_revision(
            quotation,
            rejected_by,
            change_summary=f"Rejected: {request.reason}",
        )
        self._event_bus.publish(
            QuotationRejected(
                aggregate_id=UUID(str(quotation.id)),
                company_id=company_id,
                quotation_id=UUID(str(quotation.id)),
                quotation_number=quotation.quotation_number,
                customer_id=UUID(str(quotation.customer_id)),
                reason=request.reason,
                rejected_by=rejected_by,
            )
        )
        return quotation

    def cancel(
        self,
        company_id: UUID,
        quotation_id: UUID,
        request: QuotationCancelRequest,
        cancelled_by: UUID,
    ) -> SalesQuotation:
        """Transition any live status → CANCELLED."""
        quotation = self._get_or_404(company_id, quotation_id)
        previous_status = quotation.status
        _assert_transition(quotation.status, "CANCELLED")

        quotation.status = "CANCELLED"
        quotation.updated_by = str(cancelled_by)
        self.db.flush()

        self._capture_revision(
            quotation,
            cancelled_by,
            change_summary=f"Cancelled: {request.reason}",
        )
        self._event_bus.publish(
            QuotationCancelled(
                aggregate_id=UUID(str(quotation.id)),
                company_id=company_id,
                quotation_id=UUID(str(quotation.id)),
                quotation_number=quotation.quotation_number,
                customer_id=UUID(str(quotation.customer_id)),
                previous_status=previous_status,
                reason=request.reason,
                cancelled_by=cancelled_by,
            )
        )
        return quotation

    def expire(
        self,
        company_id: UUID,
        quotation_id: UUID,
        expired_by: UUID | None = None,
    ) -> SalesQuotation:
        """Transition SENT_TO_CUSTOMER → EXPIRED.

        Called by the validity management process when validity_date < today.
        """
        quotation = self._get_or_404(company_id, quotation_id)
        _assert_transition(quotation.status, "EXPIRED")

        quotation.status = "EXPIRED"
        if expired_by:
            quotation.updated_by = str(expired_by)
        self.db.flush()

        actor = expired_by or UUID(int=0)
        self._capture_revision(
            quotation, actor, change_summary="Expired: validity date passed"
        )
        self._event_bus.publish(
            QuotationExpired(
                aggregate_id=UUID(str(quotation.id)),
                company_id=company_id,
                quotation_id=UUID(str(quotation.id)),
                quotation_number=quotation.quotation_number,
                customer_id=UUID(str(quotation.customer_id)),
                validity_date=quotation.validity_date,
            )
        )
        return quotation

    def convert_to_order(
        self,
        company_id: UUID,
        quotation_id: UUID,
        converted_by: UUID,
    ) -> QuotationConvertResponse:
        """Transition ACCEPTED → CONVERTED.

        Creates a Sales Order reference (Phase 5 will wire the full SalesOrder
        model). The quotation is marked CONVERTED and converted_order_id is set.

        Only ACCEPTED quotations can be converted.
        """
        quotation = self._get_or_404(company_id, quotation_id)
        _assert_transition(quotation.status, "CONVERTED")

        # Generate order number via sequence service
        order_number = self._seq_svc.generate_next_number(
            company_id=company_id, document_type="SO"
        )
        # Generate order ID (Phase 5 will create the SalesOrder row)
        order_id = uuid4()

        quotation.status = "CONVERTED"
        quotation.converted_order_id = str(order_id)
        quotation.updated_by = str(converted_by)
        self.db.flush()

        self._capture_revision(
            quotation,
            converted_by,
            change_summary=f"Converted to order {order_number}",
        )
        self._event_bus.publish(
            QuotationConverted(
                aggregate_id=UUID(str(quotation.id)),
                company_id=company_id,
                quotation_id=UUID(str(quotation.id)),
                quotation_number=quotation.quotation_number,
                customer_id=UUID(str(quotation.customer_id)),
                order_id=order_id,
                order_number=order_number,
                converted_by=converted_by,
            )
        )
        logger.info(
            "Quotation %s converted to order %s",
            quotation.quotation_number,
            order_number,
        )
        return QuotationConvertResponse(
            quotation_id=UUID(str(quotation.id)),
            quotation_number=quotation.quotation_number,
            order_id=order_id,
            order_number=order_number,
        )

    # ------------------------------------------------------------------
    # Validity management (T089)
    # ------------------------------------------------------------------

    def auto_expire_overdue(self, company_id: UUID, today: date | None = None) -> int:
        """Expire all SENT_TO_CUSTOMER quotations past their validity_date.

        Returns the count of quotations expired.
        """
        today_str = (today or date.today()).isoformat()
        overdue = self._quot_repo.list_sent_expired(company_id, today_str)

        count = 0
        for quot in overdue:
            try:
                self.expire(company_id, UUID(str(quot.id)))
                count += 1
            except Exception:
                logger.exception("Failed to expire quotation %s", quot.quotation_number)
        return count

    def publish_expiring_soon_warnings(
        self,
        company_id: UUID,
        warning_days: int = 3,
        today: date | None = None,
    ) -> int:
        """Publish QuotationExpiringSoon events for quotations expiring within warning_days.

        Returns count of warning events published.
        """
        today_d = today or date.today()
        warning_d = today_d + timedelta(days=warning_days)
        today_str = today_d.isoformat()
        warning_str = warning_d.isoformat()

        expiring = self._quot_repo.list_expiring_soon(
            company_id, today_str, warning_str
        )
        count = 0
        for quot in expiring:
            validity_d = date.fromisoformat(quot.validity_date)
            days_remaining = (validity_d - today_d).days
            self._event_bus.publish(
                QuotationExpiringSoon(
                    aggregate_id=UUID(str(quot.id)),
                    company_id=company_id,
                    quotation_id=UUID(str(quot.id)),
                    quotation_number=quot.quotation_number,
                    customer_id=UUID(str(quot.customer_id)),
                    validity_date=quot.validity_date,
                    days_remaining=days_remaining,
                )
            )
            count += 1
        return count

    # ------------------------------------------------------------------
    # Revision history
    # ------------------------------------------------------------------

    def get_revisions(
        self, company_id: UUID, quotation_id: UUID
    ) -> list[QuotationRevision]:
        """Return all revision history for a quotation."""
        self._get_or_404(company_id, quotation_id)
        return self._rev_repo.list_for_quotation(company_id, quotation_id)
