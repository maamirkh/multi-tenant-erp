"""AlertEvaluationService — post-write stock intelligence hook.

Called by StockLedgerService after every stock write within the same
transaction.  Evaluates current qty_on_hand against thresholds and:

  1. Creates a LowStockAlert if a threshold is breached and no OPEN alert of
     the same type already exists (deduplication).
  2. Auto-resolves any OPEN alerts of the same type if the stock is now above
     the threshold.
  3. Creates a ReorderSuggestion when a LOW_STOCK alert is raised and a
     matching active ReorderRule exists.
  4. Publishes domain events via the EventBus (non-blocking; handler errors
     are caught and logged).

Alert priority / evaluation order:
  OUT_OF_STOCK       — qty == 0  (highest priority)
  SAFETY_STOCK_BREACH — qty < safety_stock (and qty > 0)
  LOW_STOCK          — qty <= reorder_level (and qty > safety_stock)
  OVERSTOCK          — qty > maximum_stock  (gated by feature flag)

Spec ref: specs/005-inventory-management/spec.md §15 / FR-IO-016
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from core.utils.datetime import utcnow
from modules.inventory.constants import INVENTORY_FLAG_BY_KEY
from modules.inventory.domain_events import (
    LowStockAlertRaised,
    ReorderSuggestionGenerated,
)
from modules.inventory.events import get_event_bus
from modules.inventory.models.alerts import LowStockAlert, ReorderSuggestion
from modules.inventory.models.stock import StockPosition
from modules.inventory.repositories.alerts_repository import (
    LowStockAlertRepository,
    ReorderRuleRepository,
    ReorderSuggestionRepository,
)
from modules.inventory.repositories.feature_flag_repository import FeatureFlagRepository

logger = logging.getLogger(__name__)

# Flag key for overstock alerts
_OVERSTOCK_FLAG = "inventory.overstock_alerts"


class AlertEvaluationService:
    """Evaluates stock thresholds and manages alert lifecycle.

    Designed to be called within the same SQLAlchemy Session / transaction as
    the stock write — all writes are flushed but NOT committed here.
    """

    def __init__(
        self,
        db: Session,
        alert_repo: LowStockAlertRepository,
        rule_repo: ReorderRuleRepository,
        suggestion_repo: ReorderSuggestionRepository,
        flag_repo: FeatureFlagRepository,
    ) -> None:
        self._db = db
        self._alert_repo = alert_repo
        self._rule_repo = rule_repo
        self._suggestion_repo = suggestion_repo
        self._flag_repo = flag_repo

    # ------------------------------------------------------------------
    # Main evaluation entry point
    # ------------------------------------------------------------------

    def evaluate(self, *, company_id: UUID, position: StockPosition) -> None:
        """Evaluate thresholds for a stock position and act on breaches.

        This method is called after every stock write.  It is intentionally
        non-raising — any exception is caught and logged so that a faulty
        alert evaluation never blocks a stock write from completing.

        Args:
            company_id: Tenant identifier.
            position:   The StockPosition that was just updated.
        """
        try:
            self._evaluate_unsafe(company_id=company_id, position=position)
        except Exception:  # noqa: BLE001
            logger.exception(
                "AlertEvaluationService: unexpected error evaluating alerts "
                "for company=%s product=%s warehouse=%s",
                company_id,
                position.product_id,
                position.warehouse_id,
            )

    def _evaluate_unsafe(self, *, company_id: UUID, position: StockPosition) -> None:
        qty = Decimal(str(position.qty_on_hand))
        product_id_str = str(position.product_id)
        warehouse_id_str = str(position.warehouse_id)
        product_id = UUID(product_id_str)
        warehouse_id = UUID(warehouse_id_str)
        variant_id: UUID | None = (
            UUID(str(position.variant_id)) if position.variant_id else None
        )

        safety_stock = Decimal(str(position.safety_stock))
        reorder_level = Decimal(str(position.reorder_level))
        maximum_stock: Decimal | None = (
            Decimal(str(position.maximum_stock))
            if position.maximum_stock is not None
            else None
        )

        # Determine which thresholds are breached
        is_out_of_stock = qty == Decimal("0")
        is_safety_breach = (
            qty < safety_stock and safety_stock > 0 and not is_out_of_stock
        )
        is_low_stock = (
            qty <= reorder_level
            and reorder_level > 0
            and not is_out_of_stock
            and not is_safety_breach
        )
        overstock_enabled = self._is_flag_enabled(
            company_id=company_id, flag_key=_OVERSTOCK_FLAG
        )
        is_overstock = (
            overstock_enabled and maximum_stock is not None and qty > maximum_stock
        )

        # Evaluate each alert type
        self._handle_alert(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            variant_id=variant_id,
            alert_type="OUT_OF_STOCK",
            breached=is_out_of_stock,
            current_qty=qty,
            threshold_qty=Decimal("0"),
        )
        self._handle_alert(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            variant_id=variant_id,
            alert_type="SAFETY_STOCK_BREACH",
            breached=is_safety_breach,
            current_qty=qty,
            threshold_qty=safety_stock,
        )
        alert_id = self._handle_alert(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            variant_id=variant_id,
            alert_type="LOW_STOCK",
            breached=is_low_stock,
            current_qty=qty,
            threshold_qty=reorder_level,
        )
        # When LOW_STOCK is newly created, generate a reorder suggestion
        if alert_id is not None and is_low_stock:
            self._maybe_create_suggestion(
                company_id=company_id,
                product_id=product_id,
                warehouse_id=warehouse_id,
                variant_id=variant_id,
                triggered_by_alert_id=alert_id,
            )

        if overstock_enabled:
            self._handle_alert(
                company_id=company_id,
                product_id=product_id,
                warehouse_id=warehouse_id,
                variant_id=variant_id,
                alert_type="OVERSTOCK",
                breached=is_overstock,
                current_qty=qty,
                threshold_qty=maximum_stock or Decimal("0"),
            )

    # ------------------------------------------------------------------
    # Alert lifecycle
    # ------------------------------------------------------------------

    def _handle_alert(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        variant_id: UUID | None,
        alert_type: str,
        breached: bool,
        current_qty: Decimal,
        threshold_qty: Decimal,
    ) -> UUID | None:
        """Create or resolve an alert of a given type.

        Returns:
            The UUID of a newly created alert, or None if no new alert was
            created (either existing, auto-resolved, or no breach).
        """
        existing = self._alert_repo.get_open_alert(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            alert_type=alert_type,
        )

        if breached:
            if existing is not None:
                # Update current_quantity on existing OPEN alert
                existing.current_quantity = current_qty
                self._db.flush()
                return None  # already open, no new alert

            # Create new OPEN alert
            alert = LowStockAlert(
                id=uuid4(),
                company_id=company_id,
                product_id=str(product_id),
                variant_id=str(variant_id) if variant_id else None,
                warehouse_id=str(warehouse_id),
                alert_type=alert_type,
                status="OPEN",
                current_quantity=current_qty,
                threshold_quantity=threshold_qty,
            )
            self._db.add(alert)
            self._db.flush()
            logger.info(
                "Alert created: company=%s product=%s wh=%s type=%s qty=%s",
                company_id,
                product_id,
                warehouse_id,
                alert_type,
                current_qty,
            )
            self._publish_alert_event(alert=alert, company_id=company_id)
            return alert.id
        else:
            # Threshold no longer breached — auto-resolve any OPEN alert
            if existing is not None:
                existing.status = "RESOLVED"
                existing.resolved_at = utcnow()
                existing.current_quantity = current_qty
                self._db.flush()
                logger.info(
                    "Alert auto-resolved: company=%s product=%s wh=%s type=%s",
                    company_id,
                    product_id,
                    warehouse_id,
                    alert_type,
                )
            return None

    # ------------------------------------------------------------------
    # Reorder suggestion (T223)
    # ------------------------------------------------------------------

    def _maybe_create_suggestion(
        self,
        *,
        company_id: UUID,
        product_id: UUID,
        warehouse_id: UUID,
        variant_id: UUID | None,
        triggered_by_alert_id: UUID,
    ) -> None:
        """Create a ReorderSuggestion if a matching active rule exists."""
        rules = self._rule_repo.get_for_product(
            company_id=company_id,
            product_id=product_id,
            warehouse_id=warehouse_id,
            variant_id=variant_id,
            active_only=True,
        )
        if not rules:
            return

        rule = rules[0]  # take most specific rule (warehouse-specific first)
        suggestion = ReorderSuggestion(
            id=uuid4(),
            company_id=company_id,
            product_id=str(product_id),
            variant_id=str(variant_id) if variant_id else None,
            warehouse_id=str(warehouse_id),
            suggested_quantity=Decimal(str(rule.reorder_quantity)),
            triggered_by_alert_id=str(triggered_by_alert_id),
            status="PENDING",
        )
        self._db.add(suggestion)
        self._db.flush()
        get_event_bus().publish(
            ReorderSuggestionGenerated(
                aggregate_id=product_id,
                company_id=company_id,
                product_id=str(product_id),
                warehouse_id=str(warehouse_id),
                suggested_qty=str(rule.reorder_quantity),
                suggestion_id=str(suggestion.id),
            )
        )
        logger.info(
            "Reorder suggestion created: company=%s product=%s wh=%s qty=%s",
            company_id,
            product_id,
            warehouse_id,
            rule.reorder_quantity,
        )

    # ------------------------------------------------------------------
    # Domain event publishing (T224)
    # ------------------------------------------------------------------

    def _publish_alert_event(self, *, alert: LowStockAlert, company_id: UUID) -> None:
        """Publish a domain event for a newly created alert."""
        get_event_bus().publish(
            LowStockAlertRaised(
                aggregate_id=alert.id,
                company_id=company_id,
                product_id=str(alert.product_id),
                warehouse_id=str(alert.warehouse_id),
                current_qty=(
                    str(alert.current_qty) if hasattr(alert, "current_qty") else "0"
                ),
                minimum_stock=(
                    str(alert.threshold_qty) if hasattr(alert, "threshold_qty") else "0"
                ),
                alert_id=str(alert.id),
            )
        )

    # ------------------------------------------------------------------
    # Feature flag helper
    # ------------------------------------------------------------------

    def _is_flag_enabled(self, *, company_id: UUID, flag_key: str) -> bool:
        """Return the effective enabled state of a feature flag.

        Checks DB override first; falls back to the definition default.
        """
        override = self._flag_repo.get_by_key(company_id=company_id, flag_key=flag_key)
        if override is not None:
            return override.is_enabled
        # Fall back to the default defined in constants
        definition = INVENTORY_FLAG_BY_KEY.get(flag_key)
        return definition.default_enabled if definition else False
