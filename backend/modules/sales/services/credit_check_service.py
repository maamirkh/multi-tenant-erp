"""Credit Check Service — Phase 4.

Evaluates customer credit status against order totals to determine whether
approval should be blocked or allowed. Used by ApprovalService during order
approval routing.

Credit status values (from Customer model):
  GOOD     — credit within limit; order allowed
  WARNING  — approaching credit limit; order allowed with warning flag
  EXCEEDED — credit limit exceeded; approval blocked
  HOLD     — manually placed on credit hold; approval blocked

Spec ref: specs/007-sales-management/spec.md §Credit Control
Research: research.md Decision 5
Task: T112
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from modules.sales.models.customer import Customer
from modules.sales.repositories.order import SalesOrderRepository

logger = logging.getLogger(__name__)


@dataclass
class CreditCheckResult:
    """Result of a credit check evaluation.

    Attributes:
        allowed:          Whether the order can proceed through approval.
        credit_status:    Customer's current credit_status value.
        credit_limit:     Customer's configured credit limit.
        outstanding_balance: Sum of open order totals for this customer.
        order_total:      Total amount of the order being evaluated.
        projected_balance: outstanding_balance + order_total after approval.
        message:          Human-readable explanation of the decision.
    """

    allowed: bool
    credit_status: str
    credit_limit: Decimal
    outstanding_balance: Decimal
    order_total: Decimal
    projected_balance: Decimal
    message: str


class CreditCheckService:
    """Evaluates customer credit before approval.

    Checks:
      1. Customer credit_status: HOLD and EXCEEDED block approval.
      2. Outstanding balance + order total vs credit_limit (when limit > 0).
      3. WARNING status allows but notes the approaching limit.

    The service is intentionally stateless — it queries customer and order
    data on each call to reflect the latest credit position.

    Spec ref: specs/007-sales-management/spec.md §Credit Control
    Task: T112
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._order_repo = SalesOrderRepository(db)

    def evaluate_credit(
        self,
        company_id: UUID,
        customer_id: UUID,
        order_total: Decimal,
        exclude_order_id: UUID | None = None,
    ) -> CreditCheckResult:
        """Evaluate whether the customer can take on the order total.

        Args:
            company_id:       Company context for tenant isolation.
            customer_id:      Customer to check.
            order_total:      Amount of the order being submitted.
            exclude_order_id: Optionally exclude a specific order from
                              outstanding balance (e.g. the order being
                              evaluated, to avoid double-counting).

        Returns:
            CreditCheckResult with allowed=True/False and supporting data.
        """
        customer = (
            self._db.query(Customer)
            .filter(
                Customer.company_id == company_id,
                Customer.id == customer_id,
                Customer.is_deleted.is_(False),
            )
            .first()
        )

        if customer is None:
            logger.warning(
                "CreditCheckService: customer %s not found for company %s",
                customer_id,
                company_id,
            )
            return CreditCheckResult(
                allowed=False,
                credit_status="UNKNOWN",
                credit_limit=Decimal("0"),
                outstanding_balance=Decimal("0"),
                order_total=order_total,
                projected_balance=order_total,
                message="Customer not found; approval blocked.",
            )

        credit_status: str = customer.credit_status
        credit_limit: Decimal = Decimal(str(customer.credit_limit))

        # Fetch outstanding balance from open orders
        outstanding = Decimal(
            str(
                self._order_repo.get_outstanding_total_for_customer(
                    company_id, customer_id
                )
            )
        )

        # If we're evaluating the order itself (it's already in the list),
        # subtract it to avoid double-counting
        if exclude_order_id is not None:
            # The order being evaluated may already be in the PENDING_APPROVAL
            # status and counted in outstanding. Subtract its total to get
            # the balance *before* this order.
            from modules.sales.models.order import SalesOrder  # noqa: PLC0415

            existing = (
                self._db.query(SalesOrder)
                .filter(
                    SalesOrder.company_id == company_id,
                    SalesOrder.id == exclude_order_id,
                    SalesOrder.is_deleted.is_(False),
                )
                .first()
            )
            if existing:
                existing_total = Decimal(str(existing.total_amount))
                outstanding = max(Decimal("0"), outstanding - existing_total)

        projected = outstanding + order_total

        # --- Blocking checks ---

        if credit_status == "HOLD":
            logger.info(
                "CreditCheck BLOCKED: customer %s is on credit HOLD", customer_id
            )
            return CreditCheckResult(
                allowed=False,
                credit_status=credit_status,
                credit_limit=credit_limit,
                outstanding_balance=outstanding,
                order_total=order_total,
                projected_balance=projected,
                message=(
                    "Customer is on credit hold. "
                    "Approval blocked until hold is released."
                ),
            )

        if credit_status == "EXCEEDED":
            logger.info(
                "CreditCheck BLOCKED: customer %s credit EXCEEDED (limit=%s outstanding=%s)",
                customer_id,
                credit_limit,
                outstanding,
            )
            return CreditCheckResult(
                allowed=False,
                credit_status=credit_status,
                credit_limit=credit_limit,
                outstanding_balance=outstanding,
                order_total=order_total,
                projected_balance=projected,
                message=(
                    f"Credit limit exceeded. "
                    f"Outstanding {outstanding} + order {order_total} "
                    f"= {projected} vs limit {credit_limit}."
                ),
            )

        # --- Limit exceeded even if status is GOOD/WARNING ---
        if credit_limit > 0 and projected > credit_limit:
            logger.info(
                "CreditCheck BLOCKED: projected balance %s exceeds limit %s for customer %s",
                projected,
                credit_limit,
                customer_id,
            )
            return CreditCheckResult(
                allowed=False,
                credit_status=credit_status,
                credit_limit=credit_limit,
                outstanding_balance=outstanding,
                order_total=order_total,
                projected_balance=projected,
                message=(
                    f"Approving this order would exceed credit limit. "
                    f"Projected balance {projected} > limit {credit_limit}."
                ),
            )

        # --- Warning (approaching limit) ---
        if credit_status == "WARNING":
            logger.info(
                "CreditCheck WARNING: customer %s approaching credit limit", customer_id
            )
            return CreditCheckResult(
                allowed=True,
                credit_status=credit_status,
                credit_limit=credit_limit,
                outstanding_balance=outstanding,
                order_total=order_total,
                projected_balance=projected,
                message=(
                    f"Credit warning: balance {outstanding} approaching limit {credit_limit}. "
                    f"Order allowed but flagged."
                ),
            )

        # --- GOOD ---
        logger.debug(
            "CreditCheck OK: customer %s credit GOOD (outstanding=%s limit=%s)",
            customer_id,
            outstanding,
            credit_limit,
        )
        return CreditCheckResult(
            allowed=True,
            credit_status=credit_status,
            credit_limit=credit_limit,
            outstanding_balance=outstanding,
            order_total=order_total,
            projected_balance=projected,
            message="Credit check passed.",
        )
