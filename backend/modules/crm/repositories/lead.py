"""LeadRepository — data access for the ``crm_leads`` table.

``find_matching_customer_candidates`` implements spec.md §16.1's
duplicate-detection priority (email -> phone -> legal_name, all
company-scoped, excluding soft-deleted Customers) for Phase 4's
``LeadConversionService``. It is built here (Phase 3, per tasks.md T025)
because ``LeadRepository`` is the natural owner of the read, but is not
called by any Lead-management code path until Phase 4. Short-circuits on
the first tier that yields a match (email checked first; phone/legal_name
are never queried once email matches) — implemented as three separate
``_match_by_*`` methods specifically so a unit test can mock them
individually without a live database (plan.md §48.1).

**Verified against the actual Sales model** (not assumed from spec.md
prose): ``Customer`` (the aggregate root) has no ``email``/``phone``
columns of its own — only ``legal_name``. Contact email/phone live on the
child ``CustomerContact`` table (``modules/sales/models/customer.py``).
The email/phone match tiers therefore join through ``CustomerContact``;
the legal_name tier queries ``Customer`` directly.

Spec ref: specs/009-crm/spec.md §16.1, §37.2, §42; plan.md §8.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from core.repositories.base import BaseRepository
from modules.crm.models.lead import Lead
from modules.sales.models.customer import Customer, CustomerContact


class LeadRepository(BaseRepository[Lead]):
    """Data-access layer for ``crm_leads``."""

    def __init__(self, db: Session) -> None:
        super().__init__(db=db, model=Lead)

    def list_filtered(
        self,
        company_id: UUID,
        *,
        status: str | None = None,
        source_id: UUID | None = None,
        owner_id: UUID | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Lead], int]:
        """Return a page of Leads and the total matching count.

        ``search`` performs an ``ILIKE`` match against name/company-name/
        email/phone (spec.md §42) — no full-text index is introduced
        pre-emptively for CRM's expected row counts.
        """
        stmt = (
            select(Lead)
            .where(Lead.company_id == company_id)
            .where(Lead.is_deleted == False)  # noqa: E712
        )
        if status is not None:
            stmt = stmt.where(Lead.status == status)
        if source_id is not None:
            stmt = stmt.where(Lead.source_id == source_id)
        if owner_id is not None:
            stmt = stmt.where(Lead.owner_id == str(owner_id))
        if created_from is not None:
            stmt = stmt.where(Lead.created_at >= created_from)
        if created_to is not None:
            stmt = stmt.where(Lead.created_at <= created_to)
        if search:
            term = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Lead.first_name.ilike(term),
                    Lead.last_name.ilike(term),
                    Lead.lead_company_name.ilike(term),
                    Lead.email.ilike(term),
                    Lead.phone.ilike(term),
                )
            )

        total = self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        ).scalar_one()

        stmt = (
            stmt.order_by(Lead.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    # ------------------------------------------------------------------
    # Customer-matching (spec.md §16.1) — built here, consumed in Phase 4
    # ------------------------------------------------------------------

    def find_matching_customer_candidates(
        self,
        company_id: UUID,
        *,
        email: str | None = None,
        phone: str | None = None,
        legal_name: str | None = None,
    ) -> list[Customer]:
        """Return existing Customers matching by email, then phone, then
        legal_name (case-insensitive), stopping at the first tier with a
        match. Excludes soft-deleted Customers (spec.md Edge Cases)."""
        if email:
            matches = self._match_by_email(company_id, email)
            if matches:
                return matches
        if phone:
            matches = self._match_by_phone(company_id, phone)
            if matches:
                return matches
        if legal_name:
            matches = self._match_by_legal_name(company_id, legal_name)
            if matches:
                return matches
        return []

    def _match_by_email(self, company_id: UUID, email: str) -> list[Customer]:
        stmt = (
            select(Customer)
            .join(CustomerContact, CustomerContact.customer_id == Customer.id)
            .where(Customer.company_id == company_id)
            .where(Customer.is_deleted == False)  # noqa: E712
            .where(CustomerContact.is_deleted == False)  # noqa: E712
            .where(func.lower(CustomerContact.email) == email.lower())
            .distinct()
        )
        return list(self.db.execute(stmt).scalars().all())

    def _match_by_phone(self, company_id: UUID, phone: str) -> list[Customer]:
        stmt = (
            select(Customer)
            .join(CustomerContact, CustomerContact.customer_id == Customer.id)
            .where(Customer.company_id == company_id)
            .where(Customer.is_deleted == False)  # noqa: E712
            .where(CustomerContact.is_deleted == False)  # noqa: E712
            .where(CustomerContact.phone == phone)
            .distinct()
        )
        return list(self.db.execute(stmt).scalars().all())

    # ------------------------------------------------------------------
    # Aggregate methods (Phase 9, T081) — raw values only, no report-
    # shaping, consumed by CrmReportingService. Spec ref: spec.md §40.2.
    # ------------------------------------------------------------------

    def count_by_status(self, company_id: UUID) -> dict[str, int]:
        """Count of (non-deleted) Leads grouped by ``status``."""
        stmt = (
            select(Lead.status, func.count())
            .where(Lead.company_id == company_id)
            .where(Lead.is_deleted == False)  # noqa: E712
            .group_by(Lead.status)
        )
        return {row[0]: row[1] for row in self.db.execute(stmt).all()}

    def count_by_source(self, company_id: UUID) -> dict[UUID | None, int]:
        """Count of (non-deleted) Leads grouped by ``source_id``."""
        stmt = (
            select(Lead.source_id, func.count())
            .where(Lead.company_id == company_id)
            .where(Lead.is_deleted == False)  # noqa: E712
            .group_by(Lead.source_id)
        )
        return {row[0]: row[1] for row in self.db.execute(stmt).all()}

    def count_total_in_period(
        self, company_id: UUID, date_from: datetime | None, date_to: datetime | None
    ) -> int:
        """Count of (non-deleted) Leads created within the period."""
        stmt = (
            select(func.count())
            .where(Lead.company_id == company_id)
            .where(Lead.is_deleted == False)  # noqa: E712
        )
        if date_from is not None:
            stmt = stmt.where(Lead.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Lead.created_at <= date_to)
        return self.db.execute(stmt).scalar_one()

    def count_converted_in_period(
        self, company_id: UUID, date_from: datetime | None, date_to: datetime | None
    ) -> int:
        """Count of Leads whose ``converted_at`` falls within the period
        (spec.md §40.2's conversion-rate numerator)."""
        stmt = (
            select(func.count())
            .where(Lead.company_id == company_id)
            .where(Lead.is_deleted == False)  # noqa: E712
            .where(Lead.status == "CONVERTED")
        )
        if date_from is not None:
            stmt = stmt.where(Lead.converted_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Lead.converted_at <= date_to)
        return self.db.execute(stmt).scalar_one()

    def count_currently_qualified(self, company_id: UUID) -> int:
        """Count of Leads currently sitting in ``QUALIFIED`` status (not
        yet converted) — the denominator half of spec.md §40.2's secondary
        "qualified-to-close" rate (``converted / qualified``). Uses
        current-state counts rather than a historical "was ever qualified"
        count, since Lead has no such flag and the audit trail's JSONB
        payload is not portably queryable across SQLite/Postgres for this
        — a deliberate, documented simplification, not an oversight."""
        stmt = (
            select(func.count())
            .where(Lead.company_id == company_id)
            .where(Lead.is_deleted == False)  # noqa: E712
            .where(Lead.status == "QUALIFIED")
        )
        return self.db.execute(stmt).scalar_one()

    def _match_by_legal_name(self, company_id: UUID, legal_name: str) -> list[Customer]:
        stmt = (
            select(Customer)
            .where(Customer.company_id == company_id)
            .where(Customer.is_deleted == False)  # noqa: E712
            .where(func.lower(Customer.legal_name) == legal_name.lower())
        )
        return list(self.db.execute(stmt).scalars().all())

    # ------------------------------------------------------------------
    # Customer 360 (spec.md §20) — built here, consumed in Phase 7
    # ------------------------------------------------------------------

    def list_converted_to_customer(
        self, company_id: UUID, customer_id: UUID
    ) -> list[Lead]:
        """Return every Lead that converted into ``customer_id`` (spec.md
        §20.1's "originating Lead" — one bounded query, most-recent-first;
        normally 0-1 rows, but a Customer can accumulate more than one
        conversion over time via the email/phone/legal_name match path)."""
        stmt = (
            select(Lead)
            .where(Lead.company_id == company_id)
            .where(Lead.is_deleted == False)  # noqa: E712
            .where(Lead.converted_customer_id == str(customer_id))
            .order_by(Lead.converted_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())
