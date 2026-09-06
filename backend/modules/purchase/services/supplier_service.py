"""Supplier application service — Phase 1 + Phase 2 enrichment.

Provides all Supplier lifecycle operations:
  - CreateSupplier
  - UpdateSupplier
  - ActivateSupplier    (DRAFT/INACTIVE → ACTIVE)
  - DeactivateSupplier  (ACTIVE → INACTIVE)
  - BlockSupplier       (ACTIVE → BLOCKED)
  - ReactivateSupplier  (BLOCKED/INACTIVE → ACTIVE)
  - ArchiveSupplier     (ACTIVE/INACTIVE → ARCHIVED)
  - SearchSuppliers
  - AddContact / UpdateContact / RemoveContact / SetPrimaryContact
  - AddAddress / UpdateAddress / RemoveAddress / SetDefaultAddress
  - check_supplier_eligible  — blocked-guard for purchase document creation

State Machine:
  DRAFT    → ACTIVE      (activate)
  ACTIVE   → INACTIVE    (deactivate)
  ACTIVE   → BLOCKED     (block — reason mandatory)
  INACTIVE → ACTIVE      (reactivate)
  BLOCKED  → ACTIVE      (reactivate)
  ACTIVE   → ARCHIVED    (archive — no open approved POs)
  INACTIVE → ARCHIVED    (archive)

Spec ref: specs/006-purchase-management/spec.md §14 Supplier Master
Task: T031, T032, T036, T037
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from core.exceptions.base import ConflictException, NotFoundException
from core.utils.datetime import utcnow
from modules.purchase.events import get_event_bus
from modules.purchase.events.supplier_events import (
    PreferredSupplierDesignated,
    SupplierActivated,
    SupplierArchived,
    SupplierBlocked,
    SupplierCreated,
    SupplierDeactivated,
    SupplierReactivated,
    SupplierUpdated,
)
from modules.purchase.models.supplier import Supplier, SupplierAddress, SupplierContact
from modules.purchase.repositories.supplier import (
    SupplierAddressRepository,
    SupplierContactRepository,
    SupplierRepository,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class InvalidSupplierTransitionError(Exception):
    """Raised when a requested status transition violates the state machine."""

    def __init__(self, current: str, requested: str) -> None:
        self.current = current
        self.requested = requested
        super().__init__(
            f"Cannot transition supplier from '{current}' to '{requested}'."
        )


class SupplierIneligibleError(Exception):
    """Raised when a BLOCKED or ARCHIVED supplier is used in a purchase document."""

    def __init__(self, supplier_id: UUID, status: str) -> None:
        self.supplier_id = supplier_id
        self.status = status
        super().__init__(
            f"Supplier '{supplier_id}' has status '{status}' and cannot be used for new purchase documents."
        )


class SupplierArchiveBlockedError(Exception):
    """Raised when archiving a supplier that has open approved purchase orders."""

    def __init__(self, supplier_id: UUID) -> None:
        super().__init__(
            f"Supplier '{supplier_id}' cannot be archived: has open approved purchase orders."
        )


class CreditLimitExceededError(Exception):
    """Raised when a PO would exceed the supplier's credit limit in BLOCK mode."""

    def __init__(
        self, supplier_id: UUID, total_exposure: Decimal, credit_limit_amount: Decimal
    ) -> None:
        self.supplier_id = supplier_id
        self.total_exposure = total_exposure
        self.credit_limit_amount = credit_limit_amount
        super().__init__(
            f"Credit limit exceeded for supplier '{supplier_id}': "
            f"exposure {total_exposure} > limit {credit_limit_amount}."
        )


# ---------------------------------------------------------------------------
# Valid transitions mapping  (current_status → set of allowed new statuses)
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"ACTIVE"},
    "ACTIVE": {"INACTIVE", "BLOCKED", "ARCHIVED"},
    "INACTIVE": {"ACTIVE", "ARCHIVED"},
    "BLOCKED": {"ACTIVE"},
    "ARCHIVED": set(),  # Terminal — no transitions allowed
}


def _assert_transition(current: str, requested: str) -> None:
    """Raise InvalidSupplierTransitionError if the transition is not allowed."""
    allowed = _VALID_TRANSITIONS.get(current, set())
    if requested not in allowed:
        raise InvalidSupplierTransitionError(current=current, requested=requested)


# ---------------------------------------------------------------------------
# SupplierService
# ---------------------------------------------------------------------------


class SupplierService:
    """Application service for the Supplier aggregate lifecycle.

    All operations are synchronous and wrapped in the caller's transaction.
    Domain events are published to the module-level EventBus on commit.
    """

    def __init__(
        self,
        db: Session,
        supplier_repo: SupplierRepository,
        contact_repo: SupplierContactRepository,
        address_repo: SupplierAddressRepository,
    ) -> None:
        self.db = db
        self._repo = supplier_repo
        self._contact_repo = contact_repo
        self._address_repo = address_repo
        self._event_bus = get_event_bus()

    # -----------------------------------------------------------------------
    # Create
    # -----------------------------------------------------------------------

    def create(
        self,
        company_id: UUID,
        supplier_code: str,
        legal_name: str,
        supplier_type: str = "GOODS",
        vendor_code: str | None = None,
        trading_name: str | None = None,
        category_id: UUID | None = None,
        payment_terms_id: UUID | None = None,
        currency_code: str = "USD",
        tax_registration_number: str | None = None,
        tax_category: str | None = None,
        tax_region: str | None = None,
        website: str | None = None,
        notes: str | None = None,
        lead_time_days: int | None = None,
        actor_id: UUID | None = None,
    ) -> Supplier:
        """Create a new supplier in DRAFT status.

        Raises:
            ConflictException: If supplier_code already exists for this company.
        """
        # Uniqueness invariant
        existing = self._repo.get_by_code(
            company_id=company_id, supplier_code=supplier_code
        )
        if existing is not None:
            raise ConflictException(
                message=f"Supplier code '{supplier_code}' already exists for this company.",
                details={"supplier_code": supplier_code},
            )

        supplier = Supplier(
            company_id=company_id,
            supplier_code=supplier_code.upper().strip(),
            legal_name=legal_name.strip(),
            vendor_code=vendor_code,
            trading_name=trading_name,
            supplier_type=supplier_type.upper(),
            status="DRAFT",
            category_id=str(category_id) if category_id else None,
            payment_terms_id=str(payment_terms_id) if payment_terms_id else None,
            currency_code=currency_code.upper(),
            tax_registration_number=tax_registration_number,
            tax_category=tax_category,
            tax_region=tax_region,
            website=website,
            notes=notes,
            lead_time_days=lead_time_days,
            is_preferred=False,
        )
        if actor_id:
            supplier.created_by = actor_id

        self.db.add(supplier)
        self.db.flush()
        # Missing-commit defect fixed during Epic 1-8 live verification
        # (2026-08-14) — see backend/modules/inventory/services/
        # warehouse_service.py::create_warehouse's comment for the full
        # root-cause explanation.
        self.db.commit()

        self._event_bus.publish(
            SupplierCreated.create(
                supplier_id=supplier.id,
                company_id=company_id,
                supplier_code=supplier.supplier_code,
                legal_name=supplier.legal_name,
                actor_id=actor_id,
            )
        )

        logger.info("Supplier created: %s (%s)", supplier.id, supplier.supplier_code)
        return supplier

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    def update(
        self,
        supplier_id: UUID,
        company_id: UUID,
        vendor_code: str | None = None,
        legal_name: str | None = None,
        trading_name: str | None = None,
        supplier_type: str | None = None,
        category_id: UUID | None = None,
        payment_terms_id: UUID | None = None,
        currency_code: str | None = None,
        tax_registration_number: str | None = None,
        tax_category: str | None = None,
        tax_region: str | None = None,
        website: str | None = None,
        notes: str | None = None,
        lead_time_days: int | None = None,
        actor_id: UUID | None = None,
    ) -> Supplier:
        """Update mutable fields on a supplier.

        Raises:
            NotFoundException: If supplier not found.
        """
        supplier = self._get_or_raise(supplier_id=supplier_id, company_id=company_id)

        changed_fields: list[str] = []

        def _set(attr: str, value: object) -> None:
            if value is not None and getattr(supplier, attr) != value:
                setattr(supplier, attr, value)
                changed_fields.append(attr)

        _set("vendor_code", vendor_code)
        _set("legal_name", legal_name.strip() if legal_name else None)
        _set("trading_name", trading_name)
        _set("supplier_type", supplier_type.upper() if supplier_type else None)
        _set("category_id", str(category_id) if category_id else None)
        _set("payment_terms_id", str(payment_terms_id) if payment_terms_id else None)
        _set("currency_code", currency_code.upper() if currency_code else None)
        _set("tax_registration_number", tax_registration_number)
        _set("tax_category", tax_category)
        _set("tax_region", tax_region)
        _set("website", website)
        _set("notes", notes)
        _set("lead_time_days", lead_time_days)

        if changed_fields:
            supplier.updated_at = utcnow()
            if actor_id:
                supplier.updated_by = str(actor_id)
            self.db.flush()
            # Missing-commit defect fixed during pre-Epic-9 hardening audit
            # (2026-08-14) — see create()'s comment above.
            self.db.commit()

            self._event_bus.publish(
                SupplierUpdated.create(
                    supplier_id=supplier.id,
                    company_id=company_id,
                    changed_fields=changed_fields,
                    actor_id=actor_id,
                )
            )

        return supplier

    # -----------------------------------------------------------------------
    # Lifecycle transitions
    # -----------------------------------------------------------------------

    def activate(
        self,
        supplier_id: UUID,
        company_id: UUID,
        actor_id: UUID | None = None,
    ) -> Supplier:
        """Transition a DRAFT or INACTIVE supplier to ACTIVE.

        Raises:
            InvalidSupplierTransitionError: If current status doesn't allow → ACTIVE.
        """
        supplier = self._get_or_raise(supplier_id=supplier_id, company_id=company_id)
        previous_status = supplier.status
        _assert_transition(current=previous_status, requested="ACTIVE")

        supplier.status = "ACTIVE"
        supplier.updated_at = utcnow()
        if actor_id:
            supplier.updated_by = str(actor_id)
        self.db.flush()
        self.db.commit()

        self._event_bus.publish(
            SupplierActivated.create(
                supplier_id=supplier.id,
                company_id=company_id,
                previous_status=previous_status,
                actor_id=actor_id,
            )
        )
        return supplier

    def deactivate(
        self,
        supplier_id: UUID,
        company_id: UUID,
        reason: str | None = None,
        actor_id: UUID | None = None,
    ) -> Supplier:
        """Transition an ACTIVE supplier to INACTIVE."""
        supplier = self._get_or_raise(supplier_id=supplier_id, company_id=company_id)
        _assert_transition(current=supplier.status, requested="INACTIVE")

        supplier.status = "INACTIVE"
        supplier.updated_at = utcnow()
        if actor_id:
            supplier.updated_by = str(actor_id)
        self.db.flush()
        self.db.commit()

        self._event_bus.publish(
            SupplierDeactivated.create(
                supplier_id=supplier.id,
                company_id=company_id,
                reason=reason,
                actor_id=actor_id,
            )
        )
        return supplier

    def block(
        self,
        supplier_id: UUID,
        company_id: UUID,
        reason: str,
        actor_id: UUID | None = None,
    ) -> Supplier:
        """Transition an ACTIVE supplier to BLOCKED.

        Reason is mandatory for audit purposes.
        """
        if not reason or not reason.strip():
            raise ValueError("Block reason is mandatory.")

        supplier = self._get_or_raise(supplier_id=supplier_id, company_id=company_id)
        _assert_transition(current=supplier.status, requested="BLOCKED")

        supplier.status = "BLOCKED"
        supplier.updated_at = utcnow()
        if actor_id:
            supplier.updated_by = str(actor_id)
        self.db.flush()
        self.db.commit()

        self._event_bus.publish(
            SupplierBlocked.create(
                supplier_id=supplier.id,
                company_id=company_id,
                reason=reason.strip(),
                actor_id=actor_id,
            )
        )
        return supplier

    def reactivate(
        self,
        supplier_id: UUID,
        company_id: UUID,
        reason: str | None = None,
        actor_id: UUID | None = None,
    ) -> Supplier:
        """Transition a BLOCKED or INACTIVE supplier back to ACTIVE."""
        supplier = self._get_or_raise(supplier_id=supplier_id, company_id=company_id)
        previous_status = supplier.status
        _assert_transition(current=previous_status, requested="ACTIVE")

        supplier.status = "ACTIVE"
        supplier.updated_at = utcnow()
        if actor_id:
            supplier.updated_by = str(actor_id)
        self.db.flush()
        self.db.commit()

        self._event_bus.publish(
            SupplierReactivated.create(
                supplier_id=supplier.id,
                company_id=company_id,
                previous_status=previous_status,
                reason=reason,
                actor_id=actor_id,
            )
        )
        return supplier

    def archive(
        self,
        supplier_id: UUID,
        company_id: UUID,
        actor_id: UUID | None = None,
        has_open_pos: bool = False,
    ) -> Supplier:
        """Transition an ACTIVE or INACTIVE supplier to ARCHIVED.

        Args:
            has_open_pos: The caller must check whether there are open approved
                          POs for this supplier.  Pass True to block archiving.

        Raises:
            SupplierArchiveBlockedError: If supplier has open approved POs.
            InvalidSupplierTransitionError: If current status doesn't allow archiving.
        """
        if has_open_pos:
            raise SupplierArchiveBlockedError(supplier_id=supplier_id)

        supplier = self._get_or_raise(supplier_id=supplier_id, company_id=company_id)
        previous_status = supplier.status
        _assert_transition(current=previous_status, requested="ARCHIVED")

        supplier.status = "ARCHIVED"
        supplier.updated_at = utcnow()
        if actor_id:
            supplier.updated_by = str(actor_id)
        self.db.flush()
        self.db.commit()

        self._event_bus.publish(
            SupplierArchived.create(
                supplier_id=supplier.id,
                company_id=company_id,
                previous_status=previous_status,
                actor_id=actor_id,
            )
        )
        return supplier

    # -----------------------------------------------------------------------
    # Blocked-guard (T037) — called before PO creation
    # -----------------------------------------------------------------------

    def check_supplier_eligible(self, supplier_id: UUID, company_id: UUID) -> Supplier:
        """Verify that a supplier is eligible for a new purchase document.

        A supplier is ineligible if its status is BLOCKED or ARCHIVED.

        Raises:
            NotFoundException:       If supplier not found.
            SupplierIneligibleError: If supplier is BLOCKED or ARCHIVED.
        """
        supplier = self._get_or_raise(supplier_id=supplier_id, company_id=company_id)
        if supplier.status in ("BLOCKED", "ARCHIVED"):
            raise SupplierIneligibleError(
                supplier_id=supplier_id, status=supplier.status
            )
        return supplier

    # -----------------------------------------------------------------------
    # Search
    # -----------------------------------------------------------------------

    def search(
        self,
        company_id: UUID,
        query: str | None = None,
        status: str | None = None,
        category_id: UUID | None = None,
        supplier_type: str | None = None,
        is_preferred: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Supplier], int]:
        """Search suppliers. Returns (items, total_count)."""
        return self._repo.search(
            company_id=company_id,
            query=query,
            status=status,
            category_id=category_id,
            supplier_type=supplier_type,
            is_preferred=is_preferred,
            skip=skip,
            limit=limit,
        )

    # -----------------------------------------------------------------------
    # Contact management
    # -----------------------------------------------------------------------

    def add_contact(
        self,
        supplier_id: UUID,
        company_id: UUID,
        first_name: str,
        last_name: str,
        role: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        mobile: str | None = None,
        is_primary: bool = False,
        actor_id: UUID | None = None,
    ) -> SupplierContact:
        """Add a new contact to a supplier."""
        self._get_or_raise(supplier_id=supplier_id, company_id=company_id)

        if is_primary:
            self._contact_repo.clear_primary(
                company_id=company_id, supplier_id=supplier_id
            )

        contact = SupplierContact(
            company_id=company_id,
            supplier_id=str(supplier_id),
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            role=role,
            email=email,
            phone=phone,
            mobile=mobile,
            is_primary=is_primary,
        )
        if actor_id:
            contact.created_by = actor_id

        self.db.add(contact)
        self.db.flush()
        self.db.commit()
        return contact

    def update_contact(
        self,
        contact_id: UUID,
        supplier_id: UUID,
        company_id: UUID,
        first_name: str | None = None,
        last_name: str | None = None,
        role: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        mobile: str | None = None,
        is_primary: bool | None = None,
        actor_id: UUID | None = None,
    ) -> SupplierContact:
        """Update a supplier contact."""
        contact = self._contact_repo.get_by_id(id=contact_id, company_id=company_id)

        if first_name is not None:
            contact.first_name = first_name.strip()
        if last_name is not None:
            contact.last_name = last_name.strip()
        if role is not None:
            contact.role = role
        if email is not None:
            contact.email = email
        if phone is not None:
            contact.phone = phone
        if mobile is not None:
            contact.mobile = mobile
        if is_primary is not None:
            if is_primary:
                self._contact_repo.clear_primary(
                    company_id=company_id, supplier_id=UUID(contact.supplier_id)
                )
            contact.is_primary = is_primary

        contact.updated_at = utcnow()
        if actor_id:
            contact.updated_by = str(actor_id)
        self.db.flush()
        self.db.commit()
        return contact

    def remove_contact(
        self, contact_id: UUID, supplier_id: UUID, company_id: UUID
    ) -> None:
        """Soft-delete a supplier contact."""
        contact = self._contact_repo.get_by_id(id=contact_id, company_id=company_id)
        contact.is_deleted = True
        contact.deleted_at = utcnow()
        self.db.flush()
        self.db.commit()

    def set_primary_contact(
        self, contact_id: UUID, supplier_id: UUID, company_id: UUID
    ) -> SupplierContact:
        """Set a contact as the primary contact (clears any existing primary)."""
        self._contact_repo.clear_primary(company_id=company_id, supplier_id=supplier_id)
        contact = self._contact_repo.get_by_id(id=contact_id, company_id=company_id)
        contact.is_primary = True
        contact.updated_at = utcnow()
        self.db.flush()
        self.db.commit()
        return contact

    # -----------------------------------------------------------------------
    # Address management
    # -----------------------------------------------------------------------

    def add_address(
        self,
        supplier_id: UUID,
        company_id: UUID,
        address_type: str,
        address_line_1: str,
        city: str,
        country_code: str,
        address_line_2: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        is_default: bool = False,
        actor_id: UUID | None = None,
    ) -> SupplierAddress:
        """Add a new address to a supplier."""
        self._get_or_raise(supplier_id=supplier_id, company_id=company_id)

        if is_default:
            self._address_repo.clear_default(
                company_id=company_id,
                supplier_id=supplier_id,
                address_type=address_type,
            )

        address = SupplierAddress(
            company_id=company_id,
            supplier_id=str(supplier_id),
            address_type=address_type.upper(),
            address_line_1=address_line_1.strip(),
            address_line_2=address_line_2,
            city=city.strip(),
            state=state,
            postal_code=postal_code,
            country_code=country_code.upper(),
            is_default=is_default,
        )
        if actor_id:
            address.created_by = actor_id

        self.db.add(address)
        self.db.flush()
        self.db.commit()
        return address

    def update_address(
        self,
        address_id: UUID,
        supplier_id: UUID,
        company_id: UUID,
        address_line_1: str | None = None,
        address_line_2: str | None = None,
        city: str | None = None,
        state: str | None = None,
        postal_code: str | None = None,
        country_code: str | None = None,
        is_default: bool | None = None,
        actor_id: UUID | None = None,
    ) -> SupplierAddress:
        """Update a supplier address."""
        address = self._address_repo.get_by_id(id=address_id, company_id=company_id)

        if address_line_1 is not None:
            address.address_line_1 = address_line_1.strip()
        if address_line_2 is not None:
            address.address_line_2 = address_line_2
        if city is not None:
            address.city = city.strip()
        if state is not None:
            address.state = state
        if postal_code is not None:
            address.postal_code = postal_code
        if country_code is not None:
            address.country_code = country_code.upper()
        if is_default is not None:
            if is_default:
                self._address_repo.clear_default(
                    company_id=company_id,
                    supplier_id=UUID(address.supplier_id),
                    address_type=address.address_type,
                )
            address.is_default = is_default

        address.updated_at = utcnow()
        if actor_id:
            address.updated_by = str(actor_id)
        self.db.flush()
        self.db.commit()
        return address

    def remove_address(
        self, address_id: UUID, supplier_id: UUID, company_id: UUID
    ) -> None:
        """Soft-delete a supplier address."""
        address = self._address_repo.get_by_id(id=address_id, company_id=company_id)
        address.is_deleted = True
        address.deleted_at = utcnow()
        self.db.flush()
        self.db.commit()

    def set_default_address(
        self, address_id: UUID, supplier_id: UUID, company_id: UUID
    ) -> SupplierAddress:
        """Set an address as the default for its type."""
        address = self._address_repo.get_by_id(id=address_id, company_id=company_id)
        self._address_repo.clear_default(
            company_id=company_id,
            supplier_id=UUID(address.supplier_id),
            address_type=address.address_type,
        )
        address.is_default = True
        address.updated_at = utcnow()
        self.db.flush()
        self.db.commit()
        return address

    # -----------------------------------------------------------------------
    # Phase 2 — Credit limit enforcement (T060)
    # -----------------------------------------------------------------------

    def check_credit_limit(
        self,
        company_id: UUID,
        supplier_id: UUID,
        new_po_total: Decimal,
        outstanding_po_value: Decimal = Decimal("0"),
    ) -> dict:
        """Check whether a new PO would breach the supplier's credit limit.

        Called at PO approval time. Evaluates outstanding open PO value +
        new PO total against the supplier's CreditLimit.credit_limit_amount.

        Enforcement modes:
          BLOCK — raises CreditLimitExceededError (PO approval must be rejected)
          WARN  — returns warning result (caller logs/notifies, PO proceeds)
          OFF   — skips check entirely

        When no CreditLimit record exists for the supplier the company-level
        PurchasePolicy.credit_limit_mode is used as fallback (defaults to WARN).

        Args:
            company_id:           Tenant isolation key.
            supplier_id:          Supplier being evaluated.
            new_po_total:         Total value of the PO being approved.
            outstanding_po_value: Sum of all open approved POs for this supplier.

        Returns:
            dict with keys: exceeds_limit (bool), action (str), total_exposure,
            credit_limit_amount, enforcement_mode.
        """
        from sqlalchemy import select

        from modules.purchase.models.supplier_enrichment import CreditLimit

        stmt = (
            select(CreditLimit)
            .where(CreditLimit.company_id == company_id)
            .where(CreditLimit.supplier_id == str(supplier_id))
            .where(CreditLimit.is_deleted == False)  # noqa: E712
        )
        credit_limit = self.db.execute(stmt).scalars().one_or_none()

        if credit_limit is None:
            return {
                "exceeds_limit": False,
                "action": "SKIPPED",
                "total_exposure": outstanding_po_value + new_po_total,
                "credit_limit_amount": Decimal("0"),
                "enforcement_mode": "OFF",
            }

        mode = credit_limit.enforcement_mode
        if mode == "OFF":
            return {
                "exceeds_limit": False,
                "action": "SKIPPED",
                "total_exposure": outstanding_po_value + new_po_total,
                "credit_limit_amount": credit_limit.credit_limit_amount,
                "enforcement_mode": mode,
            }

        total_exposure = outstanding_po_value + new_po_total
        exceeds = total_exposure > credit_limit.credit_limit_amount

        action = "ALLOWED"
        if exceeds:
            if mode == "BLOCK":
                action = "BLOCKED"
            elif mode == "WARN":
                action = "WARNED"

        result = {
            "exceeds_limit": exceeds,
            "action": action,
            "total_exposure": total_exposure,
            "credit_limit_amount": credit_limit.credit_limit_amount,
            "enforcement_mode": mode,
        }

        if mode == "BLOCK" and exceeds:
            raise CreditLimitExceededError(
                supplier_id=supplier_id,
                total_exposure=total_exposure,
                credit_limit_amount=credit_limit.credit_limit_amount,
            )

        return result

    # -----------------------------------------------------------------------
    # Phase 2 — Preferred supplier designation (T061)
    # -----------------------------------------------------------------------

    def set_preferred(
        self,
        supplier_id: UUID,
        company_id: UUID,
        is_preferred: bool,
        actor_id: UUID,
        require_manager_role: bool = True,
    ) -> Supplier:
        """Set or clear the preferred flag on a supplier.

        Purchase Manager role restriction is enforced at the API layer
        (require_manager_role=True is the default; set False in tests
        that bypass RBAC).

        Args:
            supplier_id:          Target Supplier UUID.
            company_id:           Tenant isolation key.
            is_preferred:         New preferred state.
            actor_id:             User performing the change.
            require_manager_role: If True, caller must have verified PM role.

        Returns:
            Updated Supplier record.
        """
        supplier = self._get_or_raise(supplier_id=supplier_id, company_id=company_id)
        previous = supplier.is_preferred

        if previous == is_preferred:
            return supplier  # No-op

        supplier.is_preferred = is_preferred
        supplier.updated_at = utcnow()
        self.db.flush()

        self._event_bus.publish(
            PreferredSupplierDesignated.create(
                supplier_id=supplier_id,
                company_id=company_id,
                is_preferred=is_preferred,
                previous_preferred=previous,
                actor_id=actor_id,
            )
        )

        return supplier

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _get_or_raise(self, supplier_id: UUID, company_id: UUID) -> Supplier:
        """Return a supplier or raise NotFoundException."""
        supplier = self._repo.get_by_id_or_none(id=supplier_id, company_id=company_id)
        if supplier is None:
            raise NotFoundException(
                message=f"Supplier '{supplier_id}' not found.",
                details={"supplier_id": str(supplier_id)},
            )
        return supplier
