# ADR-0004: GL Account Resolution for Sales/Purchase/Inventory Integration Events

> **Scope**: Document decision clusters, not individual technology choices. Group related decisions that work together (e.g., "Frontend Stack" not separate ADRs for framework, styling, deployment).

- **Status:** Proposed
- **Date:** 2026-08-05
- **Feature:** 008-accounting-finance
- **Context:** Epic 8 (Accounting & Finance) Phase 0 verification (tasks T007, T008, T010) confirmed that the inbound integration event contract described in `specs/008-accounting-finance/contracts/events.md` §"Events Consumed by Accounting" and `data-model.md` §7.2 does not match what Epics 5–7 actually built. The documented contract assumes Sales/Purchase already publish GL-aware "posted" events (`sales.invoice.posted`, `purchase.bill.posted`, `purchase.creditnote.posted`) carrying embedded chart-of-accounts routing (`ar_account_id`, `revenue_account_id`, `tax_liability_account_id`, per-line tax breakdowns). In reality: Sales publishes `sales.invoice.issued` (class `InvoiceIssued`, `modules/sales/events/invoice_events.py`) with only `invoice_id, invoice_number, customer_id, due_date, total_amount, currency_code, issued_by` — no account fields, no line-level or tax breakdown. Purchase has no Bill/Invoice/AP entity or event at all — spec 006 §60.2 explicitly lists "Invoice Processing", "Three-Way Matching", and "Accounts Payable" as Epic 8's own future scope, not something Epic 6 already built. Inventory's adjustment events (`InventoryAdjustmentSubmitted`, `InventoryAdjustmentApproved`, `StockAdjusted`) carry no account fields either. Root cause: Sales and Purchase were built before the Chart of Accounts existed (Epic 8 introduces it), so they structurally cannot know which GL account anything should post to. This decision must be resolved before Phase 4's `IntegrationEventHandlerService` (T099) and Phase 5/6's live handlers (`HandleSalesInvoicePosted`, `HandlePurchaseBillPosted`, etc.) can be implemented.

<!-- Significance checklist (ALL must be true to justify this ADR)
     1) Impact: Long-term consequence for architecture/platform/security?
     2) Alternatives: Multiple viable options considered with tradeoffs?
     3) Scope: Cross-cutting concern (not an isolated detail)?
     If any are false, prefer capturing as a PHR note instead of an ADR. -->

## Decision

Adopt a **two-tier, configuration-driven GL account resolution strategy**, combined with an explicit correction to how Accounting integrates with each upstream module:

1. **Control accounts (header level)** — resolved via single company-wide defaults on `AccountingConfiguration` (already planned in T027: `default_ar_account_id`, `default_ap_account_id`, `default_exchange_gain_account_id`, `default_exchange_loss_account_id`, `default_bad_debt_account_id`, `default_retained_earnings_account_id`). Add four new fields to the same entity for this decision: `default_revenue_account_id`, `default_expense_account_id`, `default_tax_liability_account_id` (output tax), `default_input_tax_account_id` (recoverable input tax). One value per company, per BR-029/BR-030 and INV-003/INV-004 (AR/AP control account balances must always reconcile to a single control account) — this is not a per-line concept.

2. **Sales integration (Phase 5)** — subscribe to the *actual* event `sales.invoice.issued` (not the documented `sales.invoice.posted`). Because its payload carries only `total_amount` with no tax/line breakdown, `HandleSalesInvoiceIssued` calls a new **public, read-only service method** exposed by the Sales module (e.g. `SalesInvoiceReadService.get_invoice_with_lines(invoice_id, company_id)`) to retrieve the detail needed for a correct DR AR / CR Revenue / CR Tax posting. This is a cross-module *service* call through a defined public interface (Constitution §12), never a direct read of Sales' repositories or ORM models.

3. **Purchase integration (Phase 6)** — there is no `purchase.bill.posted` to subscribe to because Purchase never built a Bill/AP concept (spec 006 §60.2). Accounts Payable's supplier-bill capture (entry, optionally CSV/API import, three-way match against PO/GR references) is built **inside the Accounting module itself** in Phase 6, using Purchase's existing PO/GR data (read via a similar public read-service, not events) only for match validation. The bill is created and posted directly through PostingEngine — no inbound event is needed for bill creation itself, since Accounting is both the producer and consumer of that transaction.

4. **Inventory integration (Phase 4)** — subscribe to the actual events (`InventoryAdjustmentApproved` as the posting trigger, not `InventoryAdjustmentSubmitted`), resolving to the single default Inventory Adjustment control account the same way as (1). Whether these events carry a costed monetary value sufficient for GL posting is not yet confirmed and is called out as a residual open item for Phase 4 implementation, not resolved by this ADR.

<!-- For technology stacks, list all components:
     - Framework: Next.js 14 (App Router)
     - Styling: Tailwind CSS v3
     - Deployment: Vercel
     - State Management: React Context (start simple)
-->

## Consequences

### Positive

- Sales, Purchase, and Inventory (Epics 5–7) remain structurally untouched except for one small additive public read-service method on Sales — consistent with plan.md's Constitution Check goal of "no modifications to prior epic code beyond event subscription registration," with the one documented exception in (2).
- Control accounts are explicit, company-configurable, and auditable (Constitution §46 Business Configuration Philosophy: configuration over hardcoding) rather than inferred by convention.
- Accounts Payable's bill capture living inside Accounting matches spec 006 §60.2's own statement that this is Epic 8's scope, not a retrofit of Epic 6.
- Establishes a clean incremental path: per-category/product account mapping (richer than a single default revenue/expense account) can be added later (e.g. alongside Phase 10 Tax Engine & Cost Centers) without a breaking change — it only adds a lookup step before the default is used.

### Negative

- Requires one new public method on the Sales module (`SalesInvoiceReadService`) — a genuine modification to Epic 7, not merely new Epic 8 code. This should be scoped and reviewed as a small, additive, backward-compatible change; if the team prefers zero Epic 7 changes, the fallback is posting from `sales.invoice.issued`'s `total_amount` alone with no tax split, which under-serves BR-024/BR-026 tax accuracy — noted as an explicit trade-off, not silently chosen.
- Phase 6 (Accounts Payable) is larger in scope than `plan.md`/`tasks.md` currently size it — it must build supplier-bill capture and matching UI/API, not just an event handler. Phase 6's complexity estimate ("Medium-High") may need revisiting when `/sp.tasks` is next run for that phase.
- Using a single default revenue/expense/tax account per company (rather than per-product-category mapping) means all Sales/Purchase lines post to the same GL accounts regardless of product category until a future enhancement lands — acceptable for initial correctness (every transaction still balances and reconciles) but a known limitation for segment-level P&L reporting.
- The Inventory event payload's sufficiency for GL-postable monetary values is unresolved by this ADR and must be confirmed during Phase 4 implementation.

## Alternatives Considered

**Alternative A — Retrofit Sales/Purchase/Inventory to embed GL account IDs and full tax/line breakdowns in their event payloads** (matches the original spec/data-model/events.md assumption). Rejected: requires giving Epics 5–7 Chart-of-Accounts awareness they were never designed to have, violates DDD bounded-context separation (Sales should not know about Accounting's schema), and contradicts plan.md's own Constitution Check line that Epics 1–7 interfaces are consumed without modification.

**Alternative B — Convention-based account auto-resolution** (PostingEngine picks "the one active leaf account of type Revenue" automatically, no explicit configuration). Rejected: ambiguous the moment a company's COA has more than one Revenue account (the seeded industry templates in Phase 2 do), and violates Constitution §46's explicit preference for configuration over implicit convention.

**Alternative C — Full per-product/account-group mapping table from day one** (NetSuite-style item-to-GL mapping, richer than a single default). Deferred, not rejected: the right eventual design, but premature for Phase 4–6's first working implementation per YAGNI/KISS (Constitution §7); revisit alongside Phase 10 (Tax Engine & Cost Centers).

**Alternative D — Direct cross-module database/ORM read from Accounting into Sales'/Purchase's tables**, bypassing their service layers. Rejected: violates Constitution §12 (modules communicate through defined interfaces only) and §13 (repositories are private to their owning module).

<!-- Group alternatives by cluster:
     Alternative Stack A: Remix + styled-components + Cloudflare
     Alternative Stack B: Vite + vanilla CSS + AWS Amplify
     Why rejected: Less integrated, more setup complexity
-->

## References

- Feature Spec: `specs/008-accounting-finance/spec.md` (BR-024–BR-033, INV-003, INV-004, §38 Cross-Module Dependencies)
- Implementation Plan: `specs/008-accounting-finance/plan.md` (Constitution Check; Phase 4 §"General Ledger & PostingEngine"; Phase 5 §"Accounts Receivable"; Phase 6 §"Accounts Payable")
- Related: `specs/008-accounting-finance/quickstart.md` §"Phase 0 Verification Findings"; `specs/008-accounting-finance/tasks.md` T007, T008, T010, T027, T099
- Upstream epics: `specs/006-purchase-management/spec.md` §60.2 (Accounts Payable listed as Epic 8 future scope); `specs/007-sales-management/spec.md` §6 (Accounts Receivable / Payment Collection listed as Epic 8+ future scope)
- Related ADRs: none (first ADR for Epic 8)
- Evaluator Evidence: `history/prompts/008-accounting-finance/0005-epic-8-phase-0-architecture-preparation.green.prompt.md`
