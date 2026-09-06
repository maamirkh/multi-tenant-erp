# Epic 10 — Installments: Quickstart (Planning-Stage Walkthrough)

This is a scenario walkthrough for validating the architecture in `plan.md` once implemented — not a build guide (no code exists yet). It mirrors Acceptance Scenario A from `spec.md` §29 and doubles as the shape the first E2E/integration test should take.

## Prerequisites

- Docker Compose stack running (`docker-compose up`), existing `db` PostgreSQL service.
- A tenant company with the `installments` `Capability` present on its assigned `Plan` (Platform Admin action) and `feature.installments.enabled` toggled on (`POST /installments/enable`).
- An `ISSUED` `SalesInvoice` with sufficient outstanding amount, and an eligible `Customer` (`ACTIVE` status, not blocked).
- A user holding `installments.contract.create`, `installments.contract.approve` (a **different** user than the creator — maker-checker), and `installments.contract.activate`.

## Walkthrough

1. **Check eligibility**
   `GET /companies/{company_id}/installments/eligibility?sales_invoice_id={invoice_id}`
   → `200`, `is_eligible: true`.

2. **Generate a quote** (non-persisting)
   `POST /companies/{company_id}/installments/quotes` with `{ sales_invoice_id, plan_template_id | custom terms }`
   → `200`, deterministic preview: down payment, financed principal, per-installment amounts, final-installment residual, first due date, completion date. Re-running the identical request produces byte-identical output (FR-INST-031).

3. **Create a DRAFT contract**
   `POST /companies/{company_id}/installments/contracts` with the same terms
   → `201`, `status: "DRAFT"`, `contract_number: "IC-2026-000001"`.

4. **Submit for approval**
   `POST /companies/{company_id}/installments/contracts/{id}/submit`
   → `200`, `status: "PENDING_APPROVAL"`.

5. **Approve (as a different user)**
   `POST /companies/{company_id}/installments/contracts/{id}/approve`
   → `200`, `status: "APPROVED"`. (Attempting this as the *same* user who submitted → `422 SELF_APPROVAL_NOT_ALLOWED`.)

6. **Record the required down payment** (via Accounting's existing payment endpoint, referencing the contract) — or let `activate()` require it inline per tenant policy.

7. **Activate**
   `POST /companies/{company_id}/installments/contracts/{id}/activate` with header `Idempotency-Key: <uuid>`
   → `200`, `status: "ACTIVE"`. A reconciled `InstallmentScheduleVersion` (version 1) now exists; `GET .../schedule` shows N lines whose `scheduled_amount` sums exactly to `contractual_total`.
   Repeating the identical request with the same `Idempotency-Key` → `200` with the identical stored result, no second schedule generated (FR-INST-381).

8. **Record a collection**
   `POST /companies/{company_id}/installments/contracts/{id}/collections` with `{ amount, payment_method }` and a fresh `Idempotency-Key`
   → `201`. The oldest `UPCOMING`/`DUE` line becomes `PAID` (or `PARTIALLY_PAID`); `InstallmentAllocationReference` rows now point at the Accounting `Payment`/`PaymentAllocationLine` that was created.

9. **Verify Accounting has exactly one new `Payment`** for this collection (`GET` Accounting's payment endpoint filtered by `party_id=customer_id`) — confirms no shadow ledger was created (BR-INST-004, SC-002).

10. **Repeat collections** until outstanding reaches zero → contract transitions to `COMPLETED` automatically (FR-INST-104), no manual "close" action needed.

## Tenant-isolation check (Scenario I)

Repeat step 1 (`GET .../contracts/{id}`) using a valid session for a **different** company → `404`, identical to a nonexistent ID (BR-INST-015).

## Entitlement-disabled servicing check (Scenario K)

With the tenant's `feature.installments.enabled` toggled off:
- `POST .../contracts` (new origination) → `403 FEATURE_DISABLED`.
- `POST .../contracts/{existing_id}/collections` against an already-`ACTIVE` contract → `201`, succeeds normally (FR-INST-356).
