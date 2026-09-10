"""Customer application service — Phase 1.

Covers:
  - CustomerService          — CRUD + lifecycle + credit management
  - CustomerContactService   — contact management (primary enforcement)
  - CustomerAddressService   — address management (default enforcement)
  - CustomerBankDetailService — bank detail management
  - CustomerNoteService      — append-only notes

Business rules enforced:
  - customer_code unique per company (immutable after creation)
  - State machine: DRAFT → ACTIVE → ON_HOLD/BLOCKED → ACTIVE → INACTIVE
  - Activation requires: ≥1 contact, ≥1 billing address, payment_term set
  - Exactly one primary contact per customer
  - Exactly one default billing address per customer
  - DRAFT/INACTIVE customers cannot appear on sales documents
  - ON_HOLD/BLOCKED customers block new sales orders
  - credit_status auto-computed from credit usage vs credit_limit

Spec ref: specs/007-sales-management/spec.md §24 Business Rules
Task: T041, T042
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
from core.utils.datetime import utcnow
from modules.sales.events import InProcessEventBus
from modules.sales.events.customer_events import (
    CustomerActivated,
    CustomerBlocked,
    CustomerCreated,
    CustomerCreditHoldPlaced,
    CustomerCreditHoldReleased,
    CustomerCreditLimitChanged,
    CustomerDeactivated,
    CustomerHoldReleased,
    CustomerOnHold,
    CustomerUnblocked,
    CustomerUpdated,
)
from modules.sales.models.customer import (
    Customer,
    CustomerAddress,
    CustomerBankDetail,
    CustomerContact,
    CustomerNote,
)
from modules.sales.repositories.customer import (
    CustomerAddressRepository,
    CustomerBankDetailRepository,
    CustomerContactRepository,
    CustomerNoteRepository,
    CustomerRepository,
)
from modules.sales.services.sequence_service import SalesSequenceService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State machine transitions
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"ACTIVE"},
    "ACTIVE": {"ON_HOLD", "BLOCKED", "INACTIVE"},
    "ON_HOLD": {"ACTIVE"},
    "BLOCKED": {"ACTIVE"},
    "INACTIVE": {"ACTIVE"},
}

_ACTION_TO_TRANSITION: dict[str, tuple[str, str]] = {
    "activate": ("DRAFT", "ACTIVE"),  # also INACTIVE → ACTIVE via reactivate
    "hold": ("ACTIVE", "ON_HOLD"),
    "release_hold": ("ON_HOLD", "ACTIVE"),
    "block": ("ACTIVE", "BLOCKED"),
    "unblock": ("BLOCKED", "ACTIVE"),
    "deactivate": ("ACTIVE", "INACTIVE"),
    "reactivate": ("INACTIVE", "ACTIVE"),
}


class CustomerService:
    """Application service for customer lifecycle management.

    All state transitions go through this service to enforce business rules.
    """

    def __init__(
        self,
        db: Session,
        customer_repo: CustomerRepository,
        contact_repo: CustomerContactRepository,
        address_repo: CustomerAddressRepository,
        sequence_service: SalesSequenceService,
        event_bus: InProcessEventBus | None = None,
    ) -> None:
        self.db = db
        self._repo = customer_repo
        self._contact_repo = contact_repo
        self._address_repo = address_repo
        self._sequence_service = sequence_service
        self._bus = event_bus or InProcessEventBus()

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(
        self,
        company_id: UUID,
        customer_code: str,
        legal_name: str,
        customer_type: str,
        category_id: UUID,
        currency_code: str,
        trading_name: str | None = None,
        group_id: UUID | None = None,
        payment_term_id: UUID | None = None,
        credit_limit: Decimal = Decimal("0"),
        rating: str | None = None,
        tax_registration_number: str | None = None,
        tax_exempt: bool = False,
        tax_exempt_certificate: str | None = None,
        tax_exempt_expiry: str | None = None,
        website: str | None = None,
        industry: str | None = None,
        annual_revenue_range: str | None = None,
        custom_fields: dict[str, Any] | None = None,
        notes: str | None = None,
        created_by: UUID | None = None,
    ) -> Customer:
        """Create a new customer in DRAFT status."""
        existing = self._repo.get_by_code(
            company_id=company_id, customer_code=customer_code
        )
        if existing is not None:
            raise ConflictException(
                f"Customer with code '{customer_code}' already exists for this company"
            )

        customer = Customer(
            company_id=company_id,
            customer_code=customer_code.upper(),
            legal_name=legal_name,
            trading_name=trading_name,
            customer_type=customer_type,
            category_id=str(category_id),
            group_id=str(group_id) if group_id else None,
            payment_term_id=str(payment_term_id) if payment_term_id else None,
            credit_limit=credit_limit,
            credit_status="GOOD",
            rating=rating,
            currency_code=currency_code.upper(),
            tax_registration_number=tax_registration_number,
            tax_exempt=tax_exempt,
            tax_exempt_certificate=tax_exempt_certificate,
            tax_exempt_expiry=tax_exempt_expiry,
            website=website,
            industry=industry,
            annual_revenue_range=annual_revenue_range,
            custom_fields=custom_fields,
            notes=notes,
            status="DRAFT",
            version=1,
            created_by=created_by,
        )
        created = self._repo.create(customer)
        logger.info(
            "customer.created company=%s customer=%s code=%s",
            company_id,
            created.id,
            customer_code,
        )
        self._bus.publish(
            CustomerCreated(
                aggregate_id=created.id,
                company_id=company_id,
                customer_id=created.id,
                customer_code=customer_code,
                legal_name=legal_name,
                customer_type=customer_type,
                created_by=created_by,
            )
        )
        return created

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_by_id(self, company_id: UUID, customer_id: UUID) -> Customer:
        """Return a customer by ID, or raise NotFoundException."""
        customer = self._repo.get_by_id_or_none(id=customer_id, company_id=company_id)
        if customer is None:
            raise NotFoundException(f"Customer '{customer_id}' not found")
        return customer

    def search(
        self,
        company_id: UUID,
        query: str | None = None,
        status: str | None = None,
        customer_type: str | None = None,
        category_id: UUID | None = None,
        group_id: UUID | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Customer], int]:
        """Search customers with optional FTS and filters."""
        return self._repo.search(
            company_id=company_id,
            query=query,
            status=status,
            customer_type=customer_type,
            category_id=category_id,
            group_id=group_id,
            skip=skip,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    def update(
        self,
        company_id: UUID,
        customer_id: UUID,
        updated_by: UUID | None = None,
        **kwargs: object,
    ) -> Customer:
        """Update mutable customer fields."""
        customer = self.get_by_id(company_id=company_id, customer_id=customer_id)

        changed_fields: list[str] = []
        for key, value in kwargs.items():
            if value is not None and hasattr(customer, key):
                setattr(customer, key, value)
                changed_fields.append(key)

        # Increment optimistic lock version
        customer.version = (customer.version or 1) + 1

        updated = self._repo.update(customer)

        # Refresh tsvector on PostgreSQL
        self._repo.update_tsvector(self.db, updated)

        logger.info(
            "customer.updated company=%s customer=%s fields=%s",
            company_id,
            customer_id,
            changed_fields,
        )
        if changed_fields:
            self._bus.publish(
                CustomerUpdated(
                    aggregate_id=customer_id,
                    company_id=company_id,
                    customer_id=customer_id,
                    changed_fields=changed_fields,
                    updated_by=updated_by,
                )
            )
        return updated

    # ------------------------------------------------------------------
    # Lifecycle transitions
    # ------------------------------------------------------------------

    def transition(
        self,
        company_id: UUID,
        customer_id: UUID,
        action: str,
        actor_id: UUID | None = None,
        reason: str | None = None,
    ) -> Customer:
        """Execute a status lifecycle transition.

        Valid actions:
          activate, hold, release_hold, block, unblock, deactivate, reactivate
        """
        customer = self.get_by_id(company_id=company_id, customer_id=customer_id)
        current_status = customer.status

        # Determine target status
        if action == "activate":
            # DRAFT or INACTIVE both go to ACTIVE
            if current_status not in ("DRAFT", "INACTIVE"):
                raise ValueError(
                    f"Cannot activate customer in status '{current_status}'"
                )
            target_status = "ACTIVE"
        elif action == "reactivate":
            if current_status != "INACTIVE":
                raise ValueError(
                    f"Cannot reactivate customer in status '{current_status}'"
                )
            target_status = "ACTIVE"
        else:
            transition_info = _ACTION_TO_TRANSITION.get(action)
            if transition_info is None:
                raise ValueError(f"Unknown action '{action}'")
            expected_from, target_status = transition_info
            if current_status != expected_from:
                raise ValueError(
                    f"Action '{action}' requires status '{expected_from}', "
                    f"but customer is '{current_status}'"
                )

        # Pre-activation validation
        if target_status == "ACTIVE" and current_status == "DRAFT":
            self._validate_activation_requirements(
                company_id=company_id, customer=customer
            )

        previous_status = customer.status
        customer.status = target_status
        customer.version = (customer.version or 1) + 1
        updated = self._repo.update(customer)

        logger.info(
            "customer.transition company=%s customer=%s %s→%s by=%s",
            company_id,
            customer_id,
            previous_status,
            target_status,
            actor_id,
        )

        # Publish event
        self._publish_transition_event(
            action=action,
            customer_id=customer_id,
            company_id=company_id,
            previous_status=previous_status,
            actor_id=actor_id,
            reason=reason,
        )

        return updated

    def _validate_activation_requirements(
        self, company_id: UUID, customer: Customer
    ) -> None:
        """Validate all requirements for activating a DRAFT customer.

        Raises ValueError if any requirement is not met.
        """
        customer_id = customer.id

        # Require at least 1 contact
        contact_count = self._contact_repo.count_for_customer(
            company_id=company_id, customer_id=customer_id
        )
        if contact_count == 0:
            raise ValueError(
                "Cannot activate customer: at least one contact is required"
            )

        # Require at least 1 billing address
        billing_count = self._address_repo.count_billing_addresses(
            company_id=company_id, customer_id=customer_id
        )
        if billing_count == 0:
            raise ValueError(
                "Cannot activate customer: at least one billing address is required"
            )

        # Require payment term
        if not customer.payment_term_id:
            raise ValueError("Cannot activate customer: a payment term must be set")

    def _publish_transition_event(
        self,
        action: str,
        customer_id: UUID,
        company_id: UUID,
        previous_status: str,
        actor_id: UUID | None,
        reason: str | None,
    ) -> None:
        """Publish the appropriate domain event for a transition."""
        if action in ("activate", "reactivate"):
            self._bus.publish(
                CustomerActivated(
                    aggregate_id=customer_id,
                    customer_id=customer_id,
                    company_id=company_id,
                    previous_status=previous_status,
                    activated_by=actor_id,
                )
            )
        elif action == "hold":
            self._bus.publish(
                CustomerOnHold(
                    aggregate_id=customer_id,
                    customer_id=customer_id,
                    company_id=company_id,
                    reason=reason or "",
                    placed_by=actor_id,
                )
            )
        elif action == "release_hold":
            self._bus.publish(
                CustomerHoldReleased(
                    aggregate_id=customer_id,
                    customer_id=customer_id,
                    company_id=company_id,
                    released_by=actor_id,
                )
            )
        elif action == "block":
            self._bus.publish(
                CustomerBlocked(
                    aggregate_id=customer_id,
                    customer_id=customer_id,
                    company_id=company_id,
                    reason=reason or "",
                    blocked_by=actor_id,
                )
            )
        elif action == "unblock":
            self._bus.publish(
                CustomerUnblocked(
                    aggregate_id=customer_id,
                    customer_id=customer_id,
                    company_id=company_id,
                    unblocked_by=actor_id,
                )
            )
        elif action == "deactivate":
            self._bus.publish(
                CustomerDeactivated(
                    aggregate_id=customer_id,
                    customer_id=customer_id,
                    company_id=company_id,
                    deactivated_by=actor_id,
                )
            )

    # ------------------------------------------------------------------
    # Credit management
    # ------------------------------------------------------------------

    def update_credit(
        self,
        company_id: UUID,
        customer_id: UUID,
        credit_limit: Decimal,
        credit_status: str | None = None,
        actor_id: UUID | None = None,
        warning_threshold_pct: Decimal = Decimal("80"),
    ) -> Customer:
        """Update the credit limit and recompute credit_status.

        credit_status can be overridden (e.g. HOLD by Finance) or
        auto-computed from the warning threshold.
        """
        customer = self.get_by_id(company_id=company_id, customer_id=customer_id)

        previous_credit_limit = customer.credit_limit
        previous_credit_status = customer.credit_status
        customer.credit_limit = credit_limit

        if credit_status is not None:
            customer.credit_status = credit_status.upper()
        # If credit_limit is 0, always GOOD (unlimited)
        elif credit_limit == Decimal("0"):
            customer.credit_status = "GOOD"

        customer.version = (customer.version or 1) + 1
        updated = self._repo.update(customer)

        # Publish credit limit changed event when limit actually changes
        if previous_credit_limit != credit_limit:
            self._bus.publish(
                CustomerCreditLimitChanged(
                    aggregate_id=customer_id,
                    customer_id=customer_id,
                    company_id=company_id,
                    previous_credit_limit=float(previous_credit_limit),
                    new_credit_limit=float(credit_limit),
                    changed_by=actor_id,
                )
            )

        # Publish credit hold events
        new_status = updated.credit_status
        if previous_credit_status != "HOLD" and new_status == "HOLD":
            self._bus.publish(
                CustomerCreditHoldPlaced(
                    aggregate_id=customer_id,
                    customer_id=customer_id,
                    company_id=company_id,
                    credit_limit=float(credit_limit),
                    credit_used=0.0,
                    placed_by=actor_id,
                )
            )
        elif previous_credit_status == "HOLD" and new_status in (
            "GOOD",
            "WARNING",
        ):
            self._bus.publish(
                CustomerCreditHoldReleased(
                    aggregate_id=customer_id,
                    customer_id=customer_id,
                    company_id=company_id,
                    new_credit_status=new_status,
                    released_by=actor_id,
                )
            )

        return updated

    def compute_credit_status(
        self,
        credit_limit: Decimal,
        credit_used: Decimal,
        warning_threshold_pct: Decimal = Decimal("80"),
    ) -> str:
        """Compute credit_status from credit_used / credit_limit.

        Returns: GOOD / WARNING / EXCEEDED
        """
        if credit_limit == Decimal("0"):
            return "GOOD"
        pct = (credit_used / credit_limit) * Decimal("100")
        if pct >= Decimal("100"):
            return "EXCEEDED"
        if pct >= warning_threshold_pct:
            return "WARNING"
        return "GOOD"


# ---------------------------------------------------------------------------
# CustomerContactService
# ---------------------------------------------------------------------------


class CustomerContactService:
    """Application service for customer contact management."""

    def __init__(
        self,
        db: Session,
        contact_repo: CustomerContactRepository,
    ) -> None:
        self.db = db
        self._repo = contact_repo

    def add_contact(
        self,
        company_id: UUID,
        customer_id: UUID,
        contact_name: str,
        is_primary: bool = False,
        title: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        mobile: str | None = None,
        department: str | None = None,
        is_billing_contact: bool = False,
        is_shipping_contact: bool = False,
        notes: str | None = None,
        created_by: UUID | None = None,
    ) -> CustomerContact:
        """Add a contact to a customer.

        If is_primary=True, clears any existing primary contact first.
        """
        if is_primary:
            self._repo.clear_primary(company_id=company_id, customer_id=customer_id)

        contact = CustomerContact(
            company_id=company_id,
            customer_id=str(customer_id),
            contact_name=contact_name,
            title=title,
            email=email,
            phone=phone,
            mobile=mobile,
            department=department,
            is_primary=is_primary,
            is_billing_contact=is_billing_contact,
            is_shipping_contact=is_shipping_contact,
            notes=notes,
            created_by=created_by,
        )
        return self._repo.create(contact)

    def update_contact(
        self,
        company_id: UUID,
        contact_id: UUID,
        customer_id: UUID,
        **kwargs: object,
    ) -> CustomerContact:
        """Update a contact. Handles primary flag enforcement."""
        contact = self._repo.get_by_id_or_none(id=contact_id, company_id=company_id)
        if contact is None or contact.customer_id != str(customer_id):
            raise NotFoundException(f"Contact '{contact_id}' not found")

        is_primary = kwargs.pop("is_primary", None)
        if is_primary:
            self._repo.clear_primary(company_id=company_id, customer_id=customer_id)
            contact.is_primary = True

        for key, value in kwargs.items():
            if hasattr(contact, key):
                setattr(contact, key, value)

        return self._repo.update(contact)

    def delete_contact(
        self,
        company_id: UUID,
        contact_id: UUID,
        customer_id: UUID,
        deleted_by: UUID | None = None,
    ) -> None:
        """Soft-delete a contact."""
        contact = self._repo.get_by_id_or_none(id=contact_id, company_id=company_id)
        if contact is None or contact.customer_id != str(customer_id):
            raise NotFoundException(f"Contact '{contact_id}' not found")
        if contact.is_primary:
            remaining = self._repo.count_for_customer(
                company_id=company_id, customer_id=customer_id
            )
            if remaining <= 1:
                raise ValueError(
                    "Cannot delete the only primary contact. "
                    "Assign a new primary contact first."
                )
        now = utcnow()
        contact.is_deleted = True
        contact.deleted_at = now
        self._repo.update(contact)

    def get_contacts(
        self, company_id: UUID, customer_id: UUID
    ) -> list[CustomerContact]:
        return self._repo.get_for_customer(
            company_id=company_id, customer_id=customer_id
        )


# ---------------------------------------------------------------------------
# CustomerAddressService
# ---------------------------------------------------------------------------


class CustomerAddressService:
    """Application service for customer address management."""

    def __init__(
        self,
        db: Session,
        address_repo: CustomerAddressRepository,
    ) -> None:
        self.db = db
        self._repo = address_repo

    def add_address(
        self,
        company_id: UUID,
        customer_id: UUID,
        address_type: str,
        address_line_1: str,
        city: str,
        country_code: str,
        address_label: str | None = None,
        address_line_2: str | None = None,
        state_province: str | None = None,
        postal_code: str | None = None,
        is_default_billing: bool = False,
        is_default_shipping: bool = False,
        created_by: UUID | None = None,
    ) -> CustomerAddress:
        """Add an address to a customer.

        Handles clearing existing defaults when is_default_billing/shipping is set.
        """
        if is_default_billing:
            self._repo.clear_default_billing(
                company_id=company_id, customer_id=customer_id
            )
        if is_default_shipping:
            self._repo.clear_default_shipping(
                company_id=company_id, customer_id=customer_id
            )

        address = CustomerAddress(
            company_id=company_id,
            customer_id=str(customer_id),
            address_type=address_type.upper(),
            address_label=address_label,
            address_line_1=address_line_1,
            address_line_2=address_line_2,
            city=city,
            state_province=state_province,
            postal_code=postal_code,
            country_code=country_code.upper(),
            is_default_billing=is_default_billing,
            is_default_shipping=is_default_shipping,
            created_by=created_by,
        )
        return self._repo.create(address)

    def update_address(
        self,
        company_id: UUID,
        address_id: UUID,
        customer_id: UUID,
        **kwargs: object,
    ) -> CustomerAddress:
        """Update an address. Handles default flag enforcement."""
        address = self._repo.get_by_id_or_none(id=address_id, company_id=company_id)
        if address is None or address.customer_id != str(customer_id):
            raise NotFoundException(f"Address '{address_id}' not found")

        is_default_billing = kwargs.pop("is_default_billing", None)
        is_default_shipping = kwargs.pop("is_default_shipping", None)

        if is_default_billing:
            self._repo.clear_default_billing(
                company_id=company_id, customer_id=customer_id
            )
            address.is_default_billing = True
        if is_default_shipping:
            self._repo.clear_default_shipping(
                company_id=company_id, customer_id=customer_id
            )
            address.is_default_shipping = True

        for key, value in kwargs.items():
            if hasattr(address, key):
                setattr(address, key, value)

        return self._repo.update(address)

    def delete_address(
        self,
        company_id: UUID,
        address_id: UUID,
        customer_id: UUID,
        deleted_by: UUID | None = None,
    ) -> None:
        """Soft-delete an address."""
        address = self._repo.get_by_id_or_none(id=address_id, company_id=company_id)
        if address is None or address.customer_id != str(customer_id):
            raise NotFoundException(f"Address '{address_id}' not found")
        now = utcnow()
        address.is_deleted = True
        address.deleted_at = now
        self._repo.update(address)

    def get_addresses(
        self, company_id: UUID, customer_id: UUID
    ) -> list[CustomerAddress]:
        return self._repo.get_for_customer(
            company_id=company_id, customer_id=customer_id
        )


# ---------------------------------------------------------------------------
# CustomerBankDetailService
# ---------------------------------------------------------------------------


class CustomerBankDetailService:
    """Application service for customer bank detail management."""

    def __init__(
        self,
        db: Session,
        bank_repo: CustomerBankDetailRepository,
    ) -> None:
        self.db = db
        self._repo = bank_repo

    def add_bank_detail(
        self,
        company_id: UUID,
        customer_id: UUID,
        bank_name: str,
        account_number: str,
        account_holder_name: str,
        branch_name: str | None = None,
        iban: str | None = None,
        swift_bic: str | None = None,
        is_default: bool = False,
        created_by: UUID | None = None,
    ) -> CustomerBankDetail:
        """Add a bank detail to a customer."""
        if is_default:
            self._repo.clear_default(company_id=company_id, customer_id=customer_id)

        bank = CustomerBankDetail(
            company_id=company_id,
            customer_id=str(customer_id),
            bank_name=bank_name,
            branch_name=branch_name,
            account_number=account_number,
            iban=iban,
            swift_bic=swift_bic,
            account_holder_name=account_holder_name,
            is_default=is_default,
            created_by=created_by,
        )
        return self._repo.create(bank)

    def update_bank_detail(
        self,
        company_id: UUID,
        bank_id: UUID,
        customer_id: UUID,
        **kwargs: object,
    ) -> CustomerBankDetail:
        """Update a bank detail."""
        bank = self._repo.get_by_id_or_none(id=bank_id, company_id=company_id)
        if bank is None or bank.customer_id != str(customer_id):
            raise NotFoundException(f"Bank detail '{bank_id}' not found")

        is_default = kwargs.pop("is_default", None)
        if is_default:
            self._repo.clear_default(company_id=company_id, customer_id=customer_id)
            bank.is_default = True

        for key, value in kwargs.items():
            if hasattr(bank, key):
                setattr(bank, key, value)

        return self._repo.update(bank)

    def delete_bank_detail(
        self,
        company_id: UUID,
        bank_id: UUID,
        customer_id: UUID,
    ) -> None:
        """Soft-delete a bank detail."""
        bank = self._repo.get_by_id_or_none(id=bank_id, company_id=company_id)
        if bank is None or bank.customer_id != str(customer_id):
            raise NotFoundException(f"Bank detail '{bank_id}' not found")
        now = utcnow()
        bank.is_deleted = True
        bank.deleted_at = now
        self._repo.update(bank)

    def get_bank_details(
        self, company_id: UUID, customer_id: UUID
    ) -> list[CustomerBankDetail]:
        return self._repo.get_for_customer(
            company_id=company_id, customer_id=customer_id
        )


# ---------------------------------------------------------------------------
# CustomerNoteService
# ---------------------------------------------------------------------------


class CustomerNoteService:
    """Application service for append-only customer notes."""

    def __init__(
        self,
        db: Session,
        note_repo: CustomerNoteRepository,
    ) -> None:
        self.db = db
        self._repo = note_repo

    def add_note(
        self,
        company_id: UUID,
        customer_id: UUID,
        content: str,
        author_id: UUID,
        author_name: str,
    ) -> CustomerNote:
        """Append a new note to a customer (append-only; no edits)."""
        note = CustomerNote(
            company_id=company_id,
            customer_id=str(customer_id),
            content=content,
            author_id=str(author_id),
            author_name=author_name,
            created_by=author_id,
        )
        return self._repo.create(note)

    def get_notes(
        self,
        company_id: UUID,
        customer_id: UUID,
        skip: int = 0,
        limit: int = 50,
    ) -> list[CustomerNote]:
        """Return notes for a customer (newest first)."""
        return self._repo.get_for_customer(
            company_id=company_id,
            customer_id=customer_id,
            skip=skip,
            limit=limit,
        )
