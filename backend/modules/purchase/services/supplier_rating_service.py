"""Supplier Rating Service — Phase 2.

Computes and maintains supplier performance ratings based on Goods Receipt data.

Rating Formula (composite_score, 0.0–10.0):
  score = (on_time_rate * 0.40 + fill_rate * 0.40 + (100 - rejection_rate) * 0.20) / 10

  Where:
    on_time_rate    = % of GRs received on or before expected date
    fill_rate       = % of ordered quantity actually received
    rejection_rate  = % of received items rejected/returned

Weights (40%, 40%, 20%) follow spec and are hardcoded here. PurchasePolicy
stores supplier_rating_window (N = number of GRs to use for computation).

The service also supports manual override by Purchase Manager.
When a manual override is set, it replaces the composite_score on the
Supplier record (not the computed score stored in SupplierRating).

Spec ref: specs/006-purchase-management/tasks.md §T058, T059
"""

from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.purchase.events.supplier_events import SupplierRatingUpdated
from modules.purchase.models.supplier import Supplier
from modules.purchase.models.supplier_enrichment import SupplierRating

logger = logging.getLogger(__name__)

# Rating weight constants (spec §T058)
WEIGHT_ON_TIME: Decimal = Decimal("0.40")
WEIGHT_FILL: Decimal = Decimal("0.40")
WEIGHT_REJECTION: Decimal = Decimal("0.20")


class SupplierRatingService:
    """Computes and manages supplier performance ratings.

    This service is called:
      1. After each GR confirmation (recompute_from_grs)
      2. Explicitly by Purchase Manager for manual override

    The service is intentionally decoupled from the GoodsReceiptService
    (which lives in a later Phase) by accepting raw metric values as input.
    This allows Phase 2 tests to exercise the rating logic without needing
    a full GR implementation.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Core formula
    # ------------------------------------------------------------------

    @staticmethod
    def compute_composite_score(
        on_time_rate: Decimal,
        fill_rate: Decimal,
        rejection_rate: Decimal,
    ) -> Decimal:
        """Compute the composite score from the three performance rates.

        Formula:
          score = (on_time_rate * 0.40 + fill_rate * 0.40 + (100 - rejection_rate) * 0.20) / 10

        Result is clamped to [0.0, 10.0] and rounded to 1 decimal place.

        Args:
            on_time_rate:   0.00–100.00 (% on-time deliveries)
            fill_rate:      0.00–100.00 (% fill rate)
            rejection_rate: 0.00–100.00 (% rejection rate — lower is better)

        Returns:
            Decimal: composite score in range [0.0, 10.0]
        """
        quality_rate = Decimal("100") - rejection_rate
        raw = (
            on_time_rate * WEIGHT_ON_TIME
            + fill_rate * WEIGHT_FILL
            + quality_rate * WEIGHT_REJECTION
        ) / Decimal("10")

        # Clamp to valid range
        raw = max(Decimal("0"), min(Decimal("10"), raw))
        return raw.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

    # ------------------------------------------------------------------
    # Upsert rating record
    # ------------------------------------------------------------------

    def upsert_rating(
        self,
        company_id: UUID,
        supplier_id: UUID,
        on_time_rate: Decimal,
        fill_rate: Decimal,
        rejection_rate: Decimal,
        gr_count_window: int,
        actor_id: UUID | None = None,
    ) -> SupplierRating:
        """Create or update the SupplierRating record for a supplier.

        Also updates Supplier.rating_score with the new composite score
        (or with manual_override_score if one is set).

        Args:
            company_id:      Tenant isolation key.
            supplier_id:     UUID of the Supplier aggregate.
            on_time_rate:    Percentage of on-time deliveries (0–100).
            fill_rate:       Percentage of fill rate (0–100).
            rejection_rate:  Percentage of rejection rate (0–100).
            gr_count_window: Number of GR records used for this computation.
            actor_id:        User who triggered this recomputation (if applicable).

        Returns:
            Updated (or newly created) SupplierRating record.
        """
        composite = self.compute_composite_score(
            on_time_rate, fill_rate, rejection_rate
        )

        # Load or create SupplierRating record
        stmt = (
            select(SupplierRating)
            .where(SupplierRating.company_id == company_id)
            .where(SupplierRating.supplier_id == str(supplier_id))
            .where(SupplierRating.is_deleted == False)  # noqa: E712
        )
        rating = self.db.execute(stmt).scalars().one_or_none()

        now = utcnow()
        if rating is None:
            rating = SupplierRating(
                company_id=company_id,
                supplier_id=str(supplier_id),
                on_time_rate=on_time_rate,
                fill_rate=fill_rate,
                rejection_rate=rejection_rate,
                composite_score=composite,
                gr_count_window=gr_count_window,
                last_computed_at=now,
                created_by=actor_id,
            )
            self.db.add(rating)
        else:
            rating.on_time_rate = on_time_rate
            rating.fill_rate = fill_rate
            rating.rejection_rate = rejection_rate
            rating.composite_score = composite
            rating.gr_count_window = gr_count_window
            rating.last_computed_at = now

        self.db.flush()

        # Determine effective score (manual override takes precedence)
        effective_score = (
            rating.manual_override_score
            if rating.manual_override_score is not None
            else composite
        )

        # Update Supplier.rating_score
        supplier_stmt = (
            select(Supplier)
            .where(Supplier.company_id == company_id)
            .where(Supplier.id == supplier_id)
        )
        supplier = self.db.execute(supplier_stmt).scalars().one_or_none()
        if supplier is not None:
            supplier.rating_score = effective_score
            self.db.flush()

        # Publish domain event
        try:
            from core.events.bus import get_event_bus

            get_event_bus().publish(
                SupplierRatingUpdated.create(
                    supplier_id=supplier_id,
                    company_id=company_id,
                    composite_score=composite,
                    gr_count_window=gr_count_window,
                    is_manual_override=False,
                    actor_id=actor_id,
                )
            )
        except Exception:
            logger.exception("Failed to publish SupplierRatingUpdated event")

        return rating

    # ------------------------------------------------------------------
    # Manual override
    # ------------------------------------------------------------------

    def set_manual_override(
        self,
        company_id: UUID,
        supplier_id: UUID,
        override_score: Decimal,
        override_reason: str,
        actor_id: UUID,
    ) -> SupplierRating:
        """Set a manual override score (Purchase Manager only).

        The override replaces the computed score on Supplier.rating_score.
        The underlying computed metrics (on_time_rate, etc.) are preserved.

        Args:
            company_id:      Tenant isolation key.
            supplier_id:     UUID of the Supplier aggregate.
            override_score:  Score in range [0.0, 10.0].
            override_reason: Mandatory justification text.
            actor_id:        Purchase Manager user ID.

        Returns:
            Updated SupplierRating with manual override applied.
        """
        stmt = (
            select(SupplierRating)
            .where(SupplierRating.company_id == company_id)
            .where(SupplierRating.supplier_id == str(supplier_id))
            .where(SupplierRating.is_deleted == False)  # noqa: E712
        )
        rating = self.db.execute(stmt).scalars().one_or_none()

        now = utcnow()
        if rating is None:
            # Create a minimal rating record with the override
            rating = SupplierRating(
                company_id=company_id,
                supplier_id=str(supplier_id),
                on_time_rate=Decimal("0"),
                fill_rate=Decimal("0"),
                rejection_rate=Decimal("0"),
                composite_score=Decimal("0"),
                gr_count_window=0,
                manual_override_score=override_score,
                manual_override_reason=override_reason,
                last_computed_at=now,
                created_by=actor_id,
            )
            self.db.add(rating)
        else:
            rating.manual_override_score = override_score
            rating.manual_override_reason = override_reason

        self.db.flush()

        # Update Supplier.rating_score with override
        supplier_stmt = (
            select(Supplier)
            .where(Supplier.company_id == company_id)
            .where(Supplier.id == supplier_id)
        )
        supplier = self.db.execute(supplier_stmt).scalars().one_or_none()
        if supplier is not None:
            supplier.rating_score = override_score
            self.db.flush()

        # Publish event
        try:
            from core.events.bus import get_event_bus

            get_event_bus().publish(
                SupplierRatingUpdated.create(
                    supplier_id=supplier_id,
                    company_id=company_id,
                    composite_score=override_score,
                    gr_count_window=rating.gr_count_window,
                    is_manual_override=True,
                    actor_id=actor_id,
                )
            )
        except Exception:
            logger.exception("Failed to publish SupplierRatingUpdated event")

        return rating

    def clear_manual_override(
        self,
        company_id: UUID,
        supplier_id: UUID,
        actor_id: UUID,
    ) -> SupplierRating:
        """Remove the manual override and restore the computed score.

        Args:
            company_id:   Tenant isolation key.
            supplier_id:  UUID of the Supplier aggregate.
            actor_id:     User performing the clear action.

        Returns:
            Updated SupplierRating with override cleared.

        Raises:
            ValueError: If no rating record exists for this supplier.
        """
        stmt = (
            select(SupplierRating)
            .where(SupplierRating.company_id == company_id)
            .where(SupplierRating.supplier_id == str(supplier_id))
            .where(SupplierRating.is_deleted == False)  # noqa: E712
        )
        rating = self.db.execute(stmt).scalars().one_or_none()
        if rating is None:
            raise ValueError(f"No rating record found for supplier {supplier_id}")

        rating.manual_override_score = None
        rating.manual_override_reason = None
        self.db.flush()

        # Restore computed score on Supplier
        supplier_stmt = (
            select(Supplier)
            .where(Supplier.company_id == company_id)
            .where(Supplier.id == supplier_id)
        )
        supplier = self.db.execute(supplier_stmt).scalars().one_or_none()
        if supplier is not None:
            supplier.rating_score = rating.composite_score
            self.db.flush()

        return rating

    def get_rating(self, company_id: UUID, supplier_id: UUID) -> SupplierRating | None:
        """Return the SupplierRating record for a supplier, or None."""
        stmt = (
            select(SupplierRating)
            .where(SupplierRating.company_id == company_id)
            .where(SupplierRating.supplier_id == str(supplier_id))
            .where(SupplierRating.is_deleted == False)  # noqa: E712
        )
        return self.db.execute(stmt).scalars().one_or_none()
