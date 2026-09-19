# Epic 11 — Reports & Analytics: Quickstart (Planning-Stage Walkthrough)

This is a scenario walkthrough for validating the architecture in `plan.md` once implemented — not a build guide (no code exists yet). It mirrors Acceptance Scenarios A, B, C, and H from `spec.md` §46 and doubles as the shape the first integration/E2E tests should take.

## Prerequisites

- Docker Compose stack running (`docker-compose up`), existing `db` PostgreSQL service.
- A tenant company with the `reports` Capability enabled (Platform Admin action, since `reports` defaults to disabled — `plan.md` §12) and the `accounting`/`sales` Capabilities entitled (their default state).
- A user holding `reports.executive.view`, `reports.sales.view`, `reports.accounting.view`, `reports.accounting.export`, `sales.invoices.read`, and `reports.saved_view.manage`.
- Representative fixture data: at least one posted `SalesInvoice`, one posted `JournalEntry`, one `InstallmentContract` (for the Case B scenario below).

## Walkthrough

1. **Discover available reports**
   `GET /companies/{company_id}/reports/discovery`
   → `200`, a list of `ReportDefinition` summaries filtered to exactly what this user's permissions + this tenant's entitlements allow — e.g. `sales.summary`, `accounting.trial_balance`, `exec.dashboard` present; any domain the tenant hasn't entitled (e.g. `crm.*` if CRM is disabled) absent entirely, never returned with a "locked" placeholder (FR-RPT-032).

2. **Run a wrapped financial statement and confirm reconciliation (Scenario A)**
   `GET /companies/{company_id}/reports/accounting.trial_balance?period=this_month`
   → `200`, `StandardResponse<TrialBalanceReport>` with debit-equals-credit totals.
   Separately: `GET /companies/{company_id}/accounting/reports/trial-balance?period=this_month` (Accounting's own existing, unmodified endpoint).
   → Both totals are byte-identical (`plan.md` §30) — this is the reconciliation test's exact shape.

3. **Load the Executive Dashboard with a disabled domain (Scenario B)**
   Given CRM is disabled for this tenant:
   `GET /companies/{company_id}/reports/dashboard?period=this_month`
   → `200`, every widget renders (Net Sales, Purchase Spend, AR/AP, Cash Position, Operational Inventory Value, Outstanding Installment Principal, Recognized Gross Profit Margin) **except** the CRM Pipeline widget, which is simply absent from the payload — no error field referencing CRM anywhere in the response (FR-RPT-041/044).

4. **Drill down and confirm independent re-authorization (Scenario C)**
   `GET /companies/{company_id}/reports/sales.by_customer?period=this_month`
   → `200`, rows include a `drill_down` reference per customer.
   Following it as a user who holds `reports.sales.view` but **not** `sales.invoices.read`:
   `GET /companies/{company_id}/sales/invoices?customer_id=...` (the underlying module's own existing, unmodified endpoint)
   → `403`, denied — even though the report itself was viewable (FR-RPT-181).

5. **Export with row-limit and audit (Scenario J / FR-RPT-217)**
   `GET /companies/{company_id}/reports/sales.summary/export?format=csv&period=this_year`
   → `200`, `Content-Disposition: attachment; filename="sales-summary_2026-01-01_2026-12-31.csv"`, a well-formed CSV whose row set is the exact union of every page the equivalent paginated online view would return for identical filters (FR-RPT-213).
   `GET /companies/{company_id}/reports/audit-log` *(internal verification, not necessarily a tenant-facing endpoint)* → exactly one new `ReportsAuditLog` row: `entity_type="ReportExport"`, `report_key="sales.summary"`, `format="CSV"`, `row_count` matching the file.

6. **Save and reload a private view (Scenario E / US-5)**
   `POST /companies/{company_id}/reports/saved-views` with `{report_key: "accounting.trial_balance", name: "Monthly TB", filter_config: {period: "this_month"}}`
   → `201`.
   As a second user in the same tenant: `GET /companies/{company_id}/reports/saved-views` → the first user's view does **not** appear (FR-RPT-205).
   After the first user's role is changed to remove `reports.accounting.view`: `GET /companies/{company_id}/reports/saved-views/{view_id}` → `403`, denied at load, never silently executed with reduced scope (FR-RPT-203).

7. **Installments servicing-continuity, Case B (Scenario H)**
   Given the tenant's `installments` entitlement is disabled but at least one `InstallmentContract` already exists:
   `GET /companies/{company_id}/reports/installments.aging?as_of=today`
   → `200`, the report still returns correctly, with a `read_only_servicing_continuity: true` metadata flag (`plan.md` §13) — not the "module not entitled" error CRM would return in the equivalent disabled scenario.

8. **Customer 360 with partial section availability (Scenario N)**
   Given CRM disabled, Installments entitled, and a user holding `reports.customer_360.view` + `reports.sales.view` + `reports.accounting.view` but **not** `reports.crm.view`:
   `GET /companies/{company_id}/reports/customer-360/{customer_id}`
   → `200`, Sales/Accounting/Installments sections present normally, CRM section explicitly `{state: "omitted", reason: "not_entitled"}` — the whole request is never denied merely because one section's gate failed (FR-RPT-111).

## Non-Goals of This Walkthrough

This quickstart does not exercise: the deferred report catalog tail (§9 spec "Deferred" rows), `crossmodule.branch_performance` (locked Deferred), any AI-consumer path (none exists), or PDF export beyond the six Accounting statement keys already covered by step 2's family. See `plan.md` §38 for the full deferred-scope list.
