"""AccountingIntegrationGateway — the single controlled Installments ->
Accounting module boundary.

**[Correction 3, plan.md §12.3.4/§13]** Created here in Phase 3 (not
deferred to Phase 6) specifically so no earlier or later task is ever
tempted to import ``modules.accounting.models``/``.repositories``
directly. This is a **read-only skeleton** exposing only the live-read
operations eligibility/draft-creation genuinely need. Phase 6 (T107)
*extends* this same class with money-mutating staged/finalize methods —
one gateway, not two competing abstractions.

Imports only ``modules.accounting.services`` classes, **never**
``.models`` or ``.repositories`` — enforced by a structural/import-lint
test (mirrors the Platform-Admin structural-boundary test convention).

No Accounting balance is cached or duplicated inside Installments —
every call here is a live pass-through read against Accounting's own
authoritative state.

Spec ref: specs/010-installments/plan.md §12.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from modules.accounting.services.ar_service import AccountsReceivableService


class AccountingIntegrationGateway:
    """The single controlled module boundary between Installments and
    Accounting. Read-only in Phase 3; extended with staged/finalize
    money-mutating methods in Phase 6 (T107)."""

    def __init__(self, ar_service: AccountsReceivableService) -> None:
        self._ar_service = ar_service

    def get_invoice_outstanding_amount(
        self, company_id: UUID, sales_invoice_id: UUID
    ) -> Decimal:
        """Live read of the outstanding amount owed against a Sales
        invoice, sourced from Accounting's own ``ARTransaction`` (never a
        Sales field — Sales has no outstanding-amount column, plan.md
        §2/§13). Returns ``Decimal("0")`` if no AR transaction exists yet
        for this invoice (nothing posted, nothing outstanding)."""
        transaction = self._ar_service.find_transaction_by_source_document(
            company_id, "SalesInvoice", sales_invoice_id
        )
        if transaction is None:
            return Decimal("0")
        return transaction.outstanding_amount

    def get_ar_transaction(self, company_id: UUID, ar_transaction_id: UUID):
        """Live read of a single ``ARTransaction`` by id, or ``None`` if
        it does not exist for this company. Used starting Phase 6/9
        (late-charge tracking, ``InstallmentOutstandingService.assert_zero_outstanding()``,
        plan.md §9.3) — not consumed by Phase 3 itself."""
        return self._ar_service.get_transaction_by_id(company_id, ar_transaction_id)
