"""PurchasePolicyService — company-level procurement policy management.

The PurchasePolicy is a singleton per company — exactly one record exists
per company_id. It is created with system defaults on first access and
updated through explicit service calls.

Business rules:
  1. One policy record per company. Created automatically with defaults if
     it does not exist when first read.
  2. over_receipt_policy: BLOCK / WARN / ALLOW
  3. credit_limit_mode: BLOCK / WARN / OFF
  4. All changes are auditable.

Research ref: specs/006-purchase-management/research.md §Decision 10
"""

from __future__ import annotations

import logging
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from modules.purchase.models.policy import PurchasePolicy
from modules.purchase.repositories.master import PurchasePolicyRepository

logger = logging.getLogger(__name__)

VALID_OVER_RECEIPT_POLICIES = ("BLOCK", "WARN", "ALLOW")
VALID_CREDIT_LIMIT_MODES = ("BLOCK", "WARN", "OFF")


class PurchasePolicyService:
    """Application service for purchase policy management.

    Args:
        db:          SQLAlchemy session.
        policy_repo: ``PurchasePolicyRepository`` instance (injected).
    """

    def __init__(self, db: Session, policy_repo: PurchasePolicyRepository) -> None:
        self.db = db
        self._repo = policy_repo

    def get_or_create(
        self, company_id: UUID, actor_id: UUID | None = None
    ) -> PurchasePolicy:
        """Return the company policy, creating it with defaults if it doesn't exist.

        This method is idempotent — safe to call multiple times.
        """
        policy = self._repo.get_for_company(company_id=company_id)
        if policy is not None:
            return policy

        # Create with system defaults
        policy = PurchasePolicy(
            company_id=company_id,
            created_by=actor_id,
            direct_po_allowed=False,
            pr_approval_required=True,
            po_approval_required=True,
            over_receipt_policy="WARN",
            credit_limit_mode="WARN",
            ppv_alert_threshold_percent=Decimal("5.00"),
            supplier_rating_window=20,
        )
        result = self._repo.create(policy)
        logger.info(
            "Purchase policy created with defaults for company=%s actor=%s",
            company_id,
            actor_id,
        )
        return result

    def update(
        self,
        company_id: UUID,
        actor_id: UUID | None = None,
        *,
        direct_po_allowed: bool | None = None,
        pr_approval_required: bool | None = None,
        po_approval_required: bool | None = None,
        over_receipt_policy: str | None = None,
        credit_limit_mode: str | None = None,
        ppv_alert_threshold_percent: Decimal | None = None,
        supplier_rating_window: int | None = None,
    ) -> PurchasePolicy:
        """Update one or more policy fields for a company.

        Only provided (non-None) fields are updated.

        Raises:
            ValueError: If any provided policy value is invalid.
        """
        if over_receipt_policy is not None:
            self._validate_over_receipt_policy(over_receipt_policy)
        if credit_limit_mode is not None:
            self._validate_credit_limit_mode(credit_limit_mode)
        if ppv_alert_threshold_percent is not None and (
            ppv_alert_threshold_percent < 0 or ppv_alert_threshold_percent > 100
        ):
            raise ValueError("ppv_alert_threshold_percent must be between 0 and 100.")
        if supplier_rating_window is not None and supplier_rating_window < 1:
            raise ValueError("supplier_rating_window must be at least 1.")

        policy = self.get_or_create(company_id=company_id, actor_id=actor_id)

        if direct_po_allowed is not None:
            policy.direct_po_allowed = direct_po_allowed
        if pr_approval_required is not None:
            policy.pr_approval_required = pr_approval_required
        if po_approval_required is not None:
            policy.po_approval_required = po_approval_required
        if over_receipt_policy is not None:
            policy.over_receipt_policy = over_receipt_policy
        if credit_limit_mode is not None:
            policy.credit_limit_mode = credit_limit_mode
        if ppv_alert_threshold_percent is not None:
            policy.ppv_alert_threshold_percent = ppv_alert_threshold_percent
        if supplier_rating_window is not None:
            policy.supplier_rating_window = supplier_rating_window

        result = self._repo.update(policy)
        logger.info(
            "Purchase policy updated for company=%s actor=%s",
            company_id,
            actor_id,
        )
        return result

    @staticmethod
    def _validate_over_receipt_policy(value: str) -> None:
        if value not in VALID_OVER_RECEIPT_POLICIES:
            raise ValueError(
                f"Invalid over_receipt_policy: '{value}'. "
                f"Valid values: {VALID_OVER_RECEIPT_POLICIES}"
            )

    @staticmethod
    def _validate_credit_limit_mode(value: str) -> None:
        if value not in VALID_CREDIT_LIMIT_MODES:
            raise ValueError(
                f"Invalid credit_limit_mode: '{value}'. "
                f"Valid values: {VALID_CREDIT_LIMIT_MODES}"
            )
