"""InstallmentTermsPolicyValidator — the single implementation of
FR-INST-011's policy-bounds check.

Both ``InstallmentQuoteService.preview()`` and
``InstallmentContractService.create_draft()`` call this **same**
stateless function — never two independently-maintained copies of the
same bounds check (plan.md §10.6, tasks.md Phase 4.5).

Spec ref: specs/010-installments/spec.md FR-INST-011;
specs/010-installments/plan.md §10.6.
"""

from __future__ import annotations

from decimal import Decimal

from modules.installments.exceptions import InstallmentTermsPolicyViolationError
from modules.installments.models.configuration import InstallmentConfiguration


class InstallmentTermsPolicyValidator:
    """Validates proposed installment terms against the effective
    ``InstallmentConfiguration`` for a tenant/branch."""

    @staticmethod
    def validate(
        config: InstallmentConfiguration | None,
        *,
        frequency: str,
        installment_count: int,
        principal_amount: Decimal,
        down_payment_amount: Decimal,
        financed_amount: Decimal,
    ) -> None:
        """Raises ``InstallmentTermsPolicyViolationError`` naming every
        violated field if any check fails.

        ``config is None`` (the tenant has no configuration row yet)
        means "no bounds configured," not "everything forbidden" — this
        is a no-op in that case, consistent with ``InstallmentConfiguration``
        being optional since Phase 2.

        ``principal_amount`` is the pre-down-payment eligible/outstanding
        amount (needed to evaluate a percentage-based minimum down
        payment); ``financed_amount`` is the post-down-payment,
        post-markup contractual total evaluated against
        ``max_financed_amount``.
        """
        if config is None:
            return

        violations: dict[str, str] = {}

        if frequency not in config.allowed_frequencies:
            violations["frequency"] = (
                f"{frequency!r} is not an allowed frequency "
                f"({sorted(config.allowed_frequencies)})."
            )

        if not (config.min_term <= installment_count <= config.max_term):
            violations["installment_count"] = (
                f"{installment_count} is outside the configured range "
                f"[{config.min_term}, {config.max_term}]."
            )

        if config.min_down_payment_amount is not None:
            if down_payment_amount < config.min_down_payment_amount:
                violations["down_payment_amount"] = (
                    f"{down_payment_amount} is below the configured minimum "
                    f"of {config.min_down_payment_amount}."
                )
        elif config.min_down_payment_pct is not None:
            required = (principal_amount * config.min_down_payment_pct) / Decimal("100")
            if down_payment_amount < required:
                violations["down_payment_amount"] = (
                    f"{down_payment_amount} is below the configured minimum of "
                    f"{config.min_down_payment_pct}% ({required})."
                )

        if (
            config.max_financed_amount is not None
            and financed_amount > config.max_financed_amount
        ):
            violations["financed_amount"] = (
                f"{financed_amount} exceeds the configured maximum of "
                f"{config.max_financed_amount}."
            )

        if violations:
            raise InstallmentTermsPolicyViolationError(violations)
