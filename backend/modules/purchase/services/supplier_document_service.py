"""Supplier Document Service — Phase 2.

Manages compliance documents attached to suppliers.
Provides expiry alert detection for documents expiring within N days.

Spec ref: specs/006-purchase-management/tasks.md §T062
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import String, cast, select
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.purchase.models.supplier import Supplier
from modules.purchase.models.supplier_enrichment import SupplierDocument
from modules.purchase.schemas.supplier_enrichment import (
    ExpiringDocumentItem,
    ExpiringDocumentsResponse,
)

logger = logging.getLogger(__name__)

DEFAULT_EXPIRY_ALERT_DAYS = 30


class SupplierDocumentService:
    """Manages supplier compliance documents with expiry tracking."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add_document(
        self,
        company_id: UUID,
        supplier_id: UUID,
        document_type: str,
        document_number: str | None,
        issue_date: date | None,
        expiry_date: date | None,
        file_url: str | None,
        actor_id: UUID,
    ) -> SupplierDocument:
        """Add a compliance document to a supplier.

        Args:
            company_id:      Tenant isolation key.
            supplier_id:     Target Supplier UUID.
            document_type:   Document type label (e.g. 'Trade License').
            document_number: Official reference number (nullable).
            issue_date:      Date issued (nullable).
            expiry_date:     Date expires (nullable).
            file_url:        Storage URL (nullable).
            actor_id:        User creating the document.

        Returns:
            Newly created SupplierDocument.
        """
        doc = SupplierDocument(
            company_id=company_id,
            supplier_id=str(supplier_id),
            document_type=document_type,
            document_number=document_number,
            issue_date=issue_date,
            expiry_date=expiry_date,
            file_url=file_url,
            created_by=actor_id,
        )
        self.db.add(doc)
        self.db.flush()
        return doc

    def list_documents(
        self, company_id: UUID, supplier_id: UUID
    ) -> list[SupplierDocument]:
        """Return all active documents for a supplier."""
        stmt = (
            select(SupplierDocument)
            .where(SupplierDocument.company_id == company_id)
            .where(SupplierDocument.supplier_id == str(supplier_id))
            .where(SupplierDocument.is_deleted == False)  # noqa: E712
            .order_by(
                SupplierDocument.expiry_date.asc().nulls_last(),
                SupplierDocument.document_type,
            )
        )
        return list(self.db.execute(stmt).scalars().all())

    def delete_document(
        self,
        company_id: UUID,
        supplier_id: UUID,
        document_id: UUID,
        actor_id: UUID,
    ) -> None:
        """Soft-delete a supplier document.

        Raises:
            ValueError: If document not found or already deleted.
        """
        stmt = (
            select(SupplierDocument)
            .where(SupplierDocument.company_id == company_id)
            .where(SupplierDocument.supplier_id == str(supplier_id))
            .where(SupplierDocument.id == document_id)
            .where(SupplierDocument.is_deleted == False)  # noqa: E712
        )
        doc = self.db.execute(stmt).scalars().one_or_none()
        if doc is None:
            raise ValueError(
                f"Document {document_id} not found for supplier {supplier_id}"
            )

        doc.is_deleted = True
        doc.deleted_at = utcnow()
        self.db.flush()

    # ------------------------------------------------------------------
    # Expiry alert (T062)
    # ------------------------------------------------------------------

    def check_expiring_documents(
        self,
        company_id: UUID,
        alert_days: int = DEFAULT_EXPIRY_ALERT_DAYS,
    ) -> ExpiringDocumentsResponse:
        """Identify documents expiring within ``alert_days`` days.

        Called periodically (e.g. daily cron) to surface documents that
        will expire soon, so Purchase Manager can renew them.

        Args:
            company_id:  Tenant isolation key.
            alert_days:  Documents expiring within this window are returned.
                         Default: 30 days.

        Returns:
            ExpiringDocumentsResponse with list of expiring documents and
            supplier identity for each.
        """
        today = utcnow().date()
        cutoff = today + timedelta(days=alert_days)

        stmt = (
            select(SupplierDocument, Supplier)
            .join(Supplier, cast(Supplier.id, String) == SupplierDocument.supplier_id)
            .where(SupplierDocument.company_id == company_id)
            .where(SupplierDocument.is_deleted == False)  # noqa: E712
            .where(SupplierDocument.expiry_date.is_not(None))
            .where(SupplierDocument.expiry_date >= today)
            .where(SupplierDocument.expiry_date <= cutoff)
            .order_by(SupplierDocument.expiry_date.asc())
        )

        rows = self.db.execute(stmt).all()
        items: list[ExpiringDocumentItem] = []

        for doc, supplier in rows:
            expiry: date = doc.expiry_date
            days_remaining = (expiry - today).days
            items.append(
                ExpiringDocumentItem(
                    document_id=doc.id,
                    supplier_id=supplier.id,
                    supplier_code=supplier.supplier_code,
                    legal_name=supplier.legal_name,
                    document_type=doc.document_type,
                    document_number=doc.document_number,
                    expiry_date=expiry,
                    days_until_expiry=days_remaining,
                )
            )

        return ExpiringDocumentsResponse(total=len(items), documents=items)
