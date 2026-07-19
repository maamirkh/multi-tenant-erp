"""Company settings validation and merge service.

``CompanySettingsService`` enforces a whitelist of known settings keys with
their expected Python types and optional allowed values.  Callers submit a
partial dict; the service validates it and merges it into the existing
settings without removing keys that are absent from the update payload.

Spec reference: §4 US5, §6.5 Settings Management.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Settings registry
# ---------------------------------------------------------------------------

# Maps setting key → (expected_type, allowed_values | None)
# ``allowed_values=None`` means any value of the correct type is accepted.
ALLOWED_SETTINGS: dict[str, tuple[type, list[Any] | None]] = {
    # Invoicing
    "invoice_prefix": (str, None),
    "invoice_next_number": (int, None),
    # Purchase orders
    "po_prefix": (str, None),
    "po_next_number": (int, None),
    # Financial
    "payment_terms_days": (int, None),
    "late_fee_percentage": (float, None),
    "tax_inclusive_pricing": (bool, None),
    "multi_currency_enabled": (bool, None),
    # Workflow
    "approval_workflow_enabled": (bool, None),
    "email_notifications_enabled": (bool, None),
    # Inventory
    "low_stock_threshold": (int, None),
    # Locale overrides
    "date_display_format": (str, ["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"]),
    "number_decimal_separator": (str, [".", ","]),
    "number_thousands_separator": (str, [",", ".", " "]),
}


class CompanySettingsService:
    """Validates and merges company-level settings updates.

    This service is stateless; inject it once per application lifecycle
    (or per-request — either works because there is no shared mutable state).
    """

    def validate_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        """Validate a settings patch dict against the allowed registry.

        Each key in ``updates`` must be present in :data:`ALLOWED_SETTINGS`.
        Each value must be an instance of the registered type.  If an
        ``allowed_values`` list is configured the value must also appear in
        that list.

        Args:
            updates: Partial settings dict submitted by the caller.

        Returns:
            The same ``updates`` dict if all entries are valid.

        Raises:
            ValueError: On the first invalid key, wrong type, or disallowed
                value — with a human-readable message.
        """
        for key, value in updates.items():
            if key not in ALLOWED_SETTINGS:
                raise ValueError(
                    f"Unknown setting key '{key}'. "
                    f"Allowed keys: {sorted(ALLOWED_SETTINGS)}."
                )
            expected_type, allowed_values = ALLOWED_SETTINGS[key]
            if not isinstance(value, expected_type):
                raise ValueError(
                    f"Setting '{key}' expects type {expected_type.__name__}, "
                    f"got {type(value).__name__}."
                )
            if allowed_values is not None and value not in allowed_values:
                raise ValueError(
                    f"Setting '{key}' value {value!r} is not in allowed "
                    f"values: {allowed_values}."
                )
        return updates

    def merge_settings(
        self, existing: dict[str, Any], updates: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge ``updates`` into ``existing`` without deleting absent keys.

        Keys present in ``updates`` overwrite the corresponding entries in
        ``existing``.  Keys present only in ``existing`` are retained as-is.
        This implements a shallow patch (no nested key removal).

        Args:
            existing: Current settings dict stored on the company.
            updates: Validated patch dict from the caller.

        Returns:
            New merged dict (the original ``existing`` dict is not mutated).
        """
        merged = dict(existing)
        merged.update(updates)
        return merged
