# Domain Events Contract: Epic 8 — Accounting & Finance

**Version**: 1.0
**Date**: 2026-08-05
**Transport**: InProcessEventBus (monolith) → Message Broker (future microservices)

---

## Event Schema Conventions

All events follow the DevSphere ERP event envelope standard:

```
{
  "event_id": "<uuid>",
  "event_type": "<domain>.<aggregate>.<verb>",
  "event_version": "1.0",
  "tenant_id": "<uuid>",
  "company_id": "<uuid>",
  "occurred_at": "<ISO-8601 UTC>",
  "raised_by_user_id": "<uuid | null (system)>",
  "payload": { ... }
}
```

---

## Events Published by Accounting (Outbound)

### `accounting.journal.posted`

Raised every time a journal entry is finalized and reflected in the GL.

**Payload**:
```json
{
  "journal_entry_id": "<uuid>",
  "journal_number": "JE-2026-001234",
  "journal_type": "STANDARD | ADJUSTING | REVERSING | AUTOMATED | ...",
  "source": "MANUAL | SALES | PURCHASE | INVENTORY | BANK | CASH | PAYMENT | RECURRING",
  "source_document_type": "SALES_INVOICE | PURCHASE_BILL | ... | null",
  "source_document_id": "<uuid | null>",
  "posting_date": "2026-08-05",
  "fiscal_period_id": "<uuid>",
  "total_debit_base_currency": "1500.00",
  "currency_code": "USD"
}
```

**Consumers**: Reporting (Epic 11), Audit

---

### `accounting.journal.reversed`

Raised when a reversal entry is posted for a prior journal.

**Payload**:
```json
{
  "original_journal_entry_id": "<uuid>",
  "original_journal_number": "JE-2026-001200",
  "reversal_journal_entry_id": "<uuid>",
  "reversal_journal_number": "JE-2026-001235",
  "reversal_date": "2026-08-05",
  "reason": "Correction of incorrect account"
}
```

---

### `accounting.period.locked`

Raised when an accounting period is locked. All operational modules (Sales, Purchase, Inventory) must reject new postings to this period.

**Payload**:
```json
{
  "fiscal_year_id": "<uuid>",
  "fiscal_period_id": "<uuid>",
  "period_number": 7,
  "period_name": "July 2026",
  "period_start_date": "2026-07-01",
  "period_end_date": "2026-07-31",
  "locked_by_user_id": "<uuid>",
  "lock_reason": "Month-end close initiated"
}
```

**Consumers**: Sales (Epic 7), Purchase (Epic 6), Inventory (Epic 5) — all must block postings to locked period

---

### `accounting.period.unlocked`

Raised when a locked period is re-opened by a Controller/CFO.

**Payload**:
```json
{
  "fiscal_period_id": "<uuid>",
  "period_name": "July 2026",
  "unlocked_by_user_id": "<uuid>",
  "reason": "Missing invoice discovered; re-opening for 24 hours"
}
```

---

### `accounting.period.closed`

Raised when a period is permanently closed. Cannot be unlocked.

**Payload**:
```json
{
  "fiscal_period_id": "<uuid>",
  "period_name": "July 2026",
  "closed_at": "2026-08-10T08:30:00Z"
}
```

---

### `accounting.fiscalyear.closed`

Raised when the year-end close process is completed.

**Payload**:
```json
{
  "fiscal_year_id": "<uuid>",
  "fiscal_year_name": "FY 2026",
  "closing_journal_entry_id": "<uuid>",
  "net_income_transferred": "125000.00",
  "retained_earnings_account_id": "<uuid>",
  "closed_at": "2026-01-15T10:00:00Z"
}
```

---

### `accounting.payment.received`

Raised when a customer payment is posted.

**Payload**:
```json
{
  "payment_id": "<uuid>",
  "customer_id": "<uuid>",
  "payment_date": "2026-08-05",
  "payment_method": "BANK_TRANSFER | CASH | CHEQUE | CARD",
  "amount_foreign": "5000.00",
  "amount_base": "5000.00",
  "currency_code": "USD",
  "bank_account_id": "<uuid | null>",
  "allocations": [
    {"ar_transaction_id": "<uuid>", "allocated_amount": "5000.00"}
  ],
  "journal_entry_id": "<uuid>"
}
```

**Consumers**: Sales (Epic 7) — update invoice payment status; CRM (Epic 9 future)

---

### `accounting.payment.made`

Raised when a supplier payment is posted.

**Payload**:
```json
{
  "payment_id": "<uuid>",
  "supplier_id": "<uuid>",
  "payment_date": "2026-08-05",
  "payment_method": "BANK_TRANSFER | CHEQUE",
  "amount_base": "8500.00",
  "currency_code": "USD",
  "bank_account_id": "<uuid>",
  "allocations": [
    {"ap_transaction_id": "<uuid>", "allocated_amount": "8500.00"}
  ],
  "journal_entry_id": "<uuid>"
}
```

**Consumers**: Purchase (Epic 6) — update bill payment status

---

### `accounting.ar.invoice.overdue`

Raised daily by a background job for invoices that have passed their due date.

**Payload**:
```json
{
  "ar_transaction_id": "<uuid>",
  "customer_id": "<uuid>",
  "invoice_number": "INV-2026-000345",
  "original_due_date": "2026-07-15",
  "days_overdue": 21,
  "outstanding_amount_base": "12500.00",
  "currency_code": "USD"
}
```

**Consumers**: AR Clerk notification, Collections workflow, CRM (Epic 9)

---

### `accounting.ar.customer.credithold`

Raised when a customer is placed on credit hold.

**Payload**:
```json
{
  "customer_id": "<uuid>",
  "customer_code": "CUST-001",
  "credit_hold_reason": "Outstanding invoices 90+ days overdue",
  "placed_by_user_id": "<uuid>",
  "placed_at": "2026-08-05T14:30:00Z"
}
```

**Consumers**: Sales (Epic 7) — MUST block new order/invoice creation for this customer

---

### `accounting.ar.customer.credithold.released`

Raised when a credit hold is released.

**Payload**:
```json
{
  "customer_id": "<uuid>",
  "released_by_user_id": "<uuid>",
  "released_at": "2026-08-10T09:00:00Z",
  "reason": "Customer paid outstanding balance"
}
```

**Consumers**: Sales (Epic 7) — re-enable order creation for this customer

---

### `accounting.ar.customer.creditlimit.warning`

Raised when a customer's outstanding AR reaches the warning threshold (default 80% of limit).

**Payload**:
```json
{
  "customer_id": "<uuid>",
  "current_outstanding_base": "8000.00",
  "credit_limit_base": "10000.00",
  "utilization_percentage": 80.0,
  "currency_code": "USD"
}
```

**Consumers**: Sales (Epic 7) — warn sales rep; CRM (Epic 9) — flag account

---

### `accounting.ap.bill.due`

Raised for bills approaching their due date (configurable days-before, default 7).

**Payload**:
```json
{
  "ap_transaction_id": "<uuid>",
  "supplier_id": "<uuid>",
  "bill_number": "BILL-2026-000789",
  "due_date": "2026-08-12",
  "days_until_due": 7,
  "outstanding_amount_base": "6750.00"
}
```

**Consumers**: AP Clerk notification

---

### `accounting.bank.reconciled`

Raised when a bank reconciliation session is completed and locked.

**Payload**:
```json
{
  "bank_account_id": "<uuid>",
  "bank_account_name": "Main Current Account",
  "statement_date": "2026-07-31",
  "statement_closing_balance": "125430.50",
  "gl_balance_at_date": "125430.50",
  "reconciliation_id": "<uuid>"
}
```

---

### `accounting.revaluation.completed`

Raised when a period-end currency revaluation is executed.

**Payload**:
```json
{
  "fiscal_period_id": "<uuid>",
  "revaluation_date": "2026-07-31",
  "currencies_revalued": ["EUR", "GBP"],
  "total_unrealized_gain_base": "1250.00",
  "total_unrealized_loss_base": "380.00",
  "net_gain_loss_base": "870.00",
  "journal_entry_id": "<uuid>"
}
```

---

## Events Consumed by Accounting (Inbound)

### `sales.invoice.posted` (from Epic 7)

**Handler**: `IntegrationEventHandlerService.handle_sales_invoice_posted`

**Expected Payload**:
```json
{
  "invoice_id": "<uuid>",
  "invoice_number": "INV-2026-000123",
  "customer_id": "<uuid>",
  "invoice_date": "2026-08-05",
  "due_date": "2026-09-04",
  "currency_code": "USD",
  "exchange_rate": 1.0,
  "subtotal_base": "10000.00",
  "tax_total_base": "500.00",
  "grand_total_base": "10500.00",
  "lines": [
    {
      "line_number": 1,
      "product_id": "<uuid>",
      "revenue_account_id": "<uuid>",
      "tax_code_id": "<uuid>",
      "net_amount_base": "10000.00",
      "tax_amount_base": "500.00"
    }
  ],
  "ar_account_id": "<uuid>",
  "tax_liability_account_id": "<uuid>"
}
```

**GL Posting Generated**:
- DR: Accounts Receivable (ar_account_id) = grand_total_base
- CR: Revenue Account (revenue_account_id) = net_amount_base
- CR: Tax Liability (tax_liability_account_id) = tax_amount_base

---

### `sales.creditnote.posted` (from Epic 7)

**GL Posting Generated**:
- DR: Revenue Account = net_amount_base
- DR: Tax Liability = tax_amount_base
- CR: Accounts Receivable = grand_total_base

---

### `purchase.bill.posted` (from Epic 6)

**Handler**: `IntegrationEventHandlerService.handle_purchase_bill_posted`

**GL Posting Generated**:
- DR: Expense or Inventory Account (per bill line) = net_amount_base
- DR: Input Tax Recoverable = tax_amount_base (for VAT/GST)
- CR: Accounts Payable (ap_account_id) = grand_total_base

---

### `purchase.creditnote.posted` (from Epic 6)

**GL Posting Generated**:
- DR: Accounts Payable = grand_total_base
- CR: Expense or Inventory Account = net_amount_base
- CR: Input Tax Recoverable = tax_amount_base

---

### `inventory.adjustment.posted` (from Epic 5)

**Handler**: `IntegrationEventHandlerService.handle_inventory_adjustment_posted`

**GL Posting Generated** (for positive adjustment):
- DR: Inventory Control Account = adjustment_value_base
- CR: Inventory Adjustment Account = adjustment_value_base

For negative adjustment, signs are reversed.

---

## Event Versioning

- Events are versioned by `event_version` field
- Schema changes to existing events require a new version (`"2.0"`)
- Consumers must handle both versions during transition window
- Breaking changes (field removal, type changes) increment major version
- Additive changes (new optional fields) do not require version increment

---

## Integration Guarantees

| Guarantee | Implementation |
|-----------|----------------|
| At-most-once delivery (monolith) | InProcessEventBus; event published within same transaction as action |
| Idempotency | Each handler checks `source_document_id` for existing GL entry before creating; duplicates are rejected with warning, not error |
| Ordering | InProcessEventBus delivers synchronously; ordering preserved within transaction |
| Dead letter | Failed handlers log to `accounting_event_errors` table; manual retry available |
