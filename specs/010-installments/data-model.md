# Epic 10 — Installments: Phase 1 Data Model

Derived from `spec.md` §9–§21 and `plan.md` §6–§8. Conceptual model only — no migration code (per planning stop condition). All entities inherit `TenantBaseModel` (`id` UUID PK, `company_id`, `created_at`/`updated_at`, `created_by`, `is_deleted`/`deleted_at`) unless marked **[append-only]**, which instead inherits plain `Base` with an explicit `company_id` column and no soft-delete/update path.

---

## InstallmentConfiguration

Tenant/branch-level installment policy (spec §9.1).

| Field | Type | Notes |
|---|---|---|
| `branch_id` | `UUID \| NULL` | NULL = company-level default row |
| `allowed_frequencies` | `JSONB` | e.g. `["MONTHLY","WEEKLY","QUARTERLY"]` |
| `min_term` / `max_term` | `INT` | Installment count bounds |
| `min_down_payment_pct` / `min_down_payment_amount` | `NUMERIC(5,2)` / `NUMERIC(20,6)` \| NULL | At most one populated |
| `max_financed_amount` | `NUMERIC(20,6)` \| NULL | Optional cap |
| `rounding_policy` | `VARCHAR(20)` | `ROUND_HALF_UP` default |
| `grace_period_days` | `INT` | Default 0 |
| `late_charge_policy` | `JSONB` \| NULL | Fixed/percentage, cap, frequency-limit |
| `early_settlement_policy` | `JSONB` \| NULL | Discount/adjustment rule |
| `approval_threshold_amount` | `NUMERIC(20,6)` \| NULL | Above this, approval required |
| `backdating_allowed` / `backdating_max_days` | `BOOLEAN` / `INT` \| NULL | |
| `cancellation_policy` | `JSONB` \| NULL | |
| `default_policy` | `JSONB` \| NULL | Days-overdue guidance (not auto-trigger — FR-INST-162) |
| `writeoff_requires_permission` | `BOOLEAN` | Always effectively true; column exists for future stricter policy |
| `cure_enabled` | `BOOLEAN` | Kill switch for the cure action (FR-INST-222) |
| `eligibility_rules` | `JSONB` \| NULL | Customer eligibility factors |

**Validation**: `min_term <= max_term`; at most one of `min_down_payment_pct`/`min_down_payment_amount` set.
**Relationships**: none (referenced by, never references, `InstallmentContract`/`InstallmentPlanTemplate` — config is read at creation time and snapshotted, not FK'd).
**Constraints**: unique `(company_id, branch_id)`.

---

## InstallmentPlanTemplate

Reusable named commercial plan (spec §9.2).

| Field | Type | Notes |
|---|---|---|
| `name` | `VARCHAR(150)` | |
| `description` | `TEXT` \| NULL | |
| `is_active` | `BOOLEAN` | |
| `frequency` | `VARCHAR(20)` | |
| `installment_count` | `INT` | |
| `down_payment_rule` | `JSONB` | |
| `markup_rule` | `JSONB` \| NULL | |
| `grace_period_days` | `INT` \| NULL | Overrides config if set |
| `late_charge_policy` | `JSONB` \| NULL | Overrides config if set |
| `early_settlement_rule` | `JSONB` \| NULL | |
| `applicable_product_ids` | `JSONB` \| NULL | |
| `requires_approval` | `BOOLEAN` | |

**Validation**: `installment_count > 0`.
**Relationships**: referenced (optionally) by `InstallmentContract.plan_template_id`, informational lineage only — never dereferenced for financial truth after contract creation (BR-INST-009).
**Constraints**: unique `(company_id, name) WHERE is_deleted = false`.
**State transitions**: `is_active: true ⇄ false` only (deactivation blocks new use, never affects existing contracts — FR-INST-013).

---

## InstallmentContract — AGGREGATE ROOT

The installment agreement (spec §9.5, §11).

| Field | Type | Notes |
|---|---|---|
| `contract_number` | `VARCHAR(30)` | `IC-YYYY-NNNNNN`, tenant-scoped sequence |
| `branch_id` | `UUID` \| NULL | Reserved, unenforced |
| `customer_id` | `UUID` | No FK — cross-module reference to `sales.customers` |
| `sales_invoice_id` | `UUID` | No FK — cross-module reference to `sales.sales_invoices` |
| `plan_template_id` | `UUID` \| NULL | FK RESTRICT, informational only |
| `contract_date` | `DATE` | |
| `principal_amount` | `NUMERIC(20,6)` | |
| `down_payment_amount` | `NUMERIC(20,6)` | |
| `markup_amount` | `NUMERIC(20,6)` | Default 0 |
| `contractual_total` | `NUMERIC(20,6)` | `principal + markup` (down payment settled separately against the invoice) |
| `installment_count` | `INT` | |
| `frequency` | `VARCHAR(20)` | |
| `first_due_date` / `maturity_date` | `DATE` | |
| `currency_code` | `VARCHAR(3)` | Immutable once set — must equal originating invoice's currency (BR-INST-022) |
| `status` | `VARCHAR(20)` | See state machine below — **no `REJECTED` value** |
| `terms_snapshot` | `JSONB` | Self-sufficient explanation of the full obligation (FR-INST-041) |
| `active_schedule_version_id` | `UUID` \| NULL | FK RESTRICT to `InstallmentScheduleVersion`; NULL only pre-activation |
| `submitted_by` / `submitted_at` | `UUID` \| NULL / `TIMESTAMPTZ` \| NULL | |
| `approved_by` / `approved_at` | `UUID` \| NULL / `TIMESTAMPTZ` \| NULL | |
| `activated_at` / `closed_at` / `defaulted_at` / `cancelled_at` / `written_off_at` | `TIMESTAMPTZ` \| NULL | One populated per terminal/notable transition |
| `version` | `INT` | Optimistic-concurrency counter, default 1 |

**Validation**: `principal_amount >= 0`, `contractual_total >= 0`, `installment_count > 0`; `sum(active schedule lines) == contractual_total` exactly, enforced before `APPROVED → ACTIVE`.
**Relationships**: 1:N `InstallmentScheduleVersion`, 1:N `InstallmentLateCharge`, 1:N `InstallmentAuditLog` (by `entity_id`), 1:N `InstallmentIdempotencyKey` (by `contract_id`).
**Constraints**: unique `(company_id, contract_number)`; **partial unique** `(company_id, sales_invoice_id) WHERE status NOT IN ('CANCELLED','COMPLETED','WRITTEN_OFF')` — the one-contract-per-obligation invariant.

**State machine**:
```
DRAFT → PENDING_APPROVAL → APPROVED → ACTIVE → COMPLETED
DRAFT → APPROVED                (no approval required, FR-INST-101)
DRAFT|PENDING_APPROVAL|APPROVED → CANCELLED
PENDING_APPROVAL → DRAFT         (rejection outcome — not a REJECTED status)
ACTIVE → CANCELLED | DEFAULTED
DEFAULTED → ACTIVE               (cure, policy-gated)
DEFAULTED → COMPLETED            (full payoff while defaulted)
DEFAULTED → WRITTEN_OFF
```
No transition outside this table is legal; no generic `set_status` method exists.

**[CORRECTED]** Every transition into `COMPLETED` (from `ACTIVE` or `DEFAULTED`) is additionally gated by `InstallmentOutstandingService.assert_zero_outstanding()` (`plan.md` §9.3) — zero *schedule* outstanding is necessary but no longer sufficient; any open, unwaived late-charge `ARTransaction` linked to the contract also blocks completion.

---

## InstallmentScheduleVersion

One version of a contract's payment schedule (spec §12, §15.2).

| Field | Type | Notes |
|---|---|---|
| `contract_id` | `UUID` | FK RESTRICT |
| `version_number` | `INT` | Monotonically increasing per contract, starting at 1 |
| `status` | `VARCHAR(20)` | `DRAFT` \| `ACTIVE` \| `SUPERSEDED` |
| `generated_at` | `TIMESTAMPTZ` | |
| `generated_by` | `UUID` \| NULL | |
| `reason` | `TEXT` \| NULL | Mandatory for `version_number > 1` |

**Immutable once created** — no update method exists on its repository.
**Relationships**: 1:N `InstallmentScheduleLine`.
**Constraints**: unique `(contract_id, version_number)`.

---

## InstallmentScheduleLine **[append-only]**

One contractual due obligation (spec §12.1–12.2).

| Field | Type | Notes |
|---|---|---|
| `schedule_version_id` | `UUID` | FK RESTRICT |
| `company_id` | `UUID` | Explicit (no `TenantBaseModel`) |
| `sequence` | `INT` | 1-based order within the version |
| `due_date` | `DATE` | |
| `scheduled_amount` | `NUMERIC(20,6)` | `> 0`; residual absorbed entirely into the final line |
| `waived_at` / `waived_by` / `waived_reason` | `TIMESTAMPTZ` \| NULL / `UUID` \| NULL / `TEXT` \| NULL | The one mutable exception — set once, via a controlled workflow |
| `voided_at` / `voided_by` / `voided_reason` | `TIMESTAMPTZ` \| NULL / `UUID` \| NULL / `TEXT` \| NULL | The other mutable exception |

**Due-state** (`UPCOMING`/`DUE`/`PARTIALLY_PAID`/`PAID`/`OVERDUE`) is **not a stored column** — derived at read time from `scheduled_amount`, `due_date`, grace policy, and `SUM(InstallmentAllocationReference.allocated_amount WHERE is_reversal=false) - SUM(... WHERE is_reversal=true)` for this line.
**Constraints**: unique `(schedule_version_id, sequence)`.

---

## InstallmentAllocationReference **[append-only]**

Explains which Accounting payment/allocation satisfied which schedule line (spec §13.2, BR-INST-007).

| Field | Type | Notes |
|---|---|---|
| `contract_id` | `UUID` | FK RESTRICT |
| `schedule_line_id` | `UUID` | FK RESTRICT |
| `accounting_payment_id` | `UUID` | No FK — cross-module reference |
| `accounting_payment_allocation_line_id` | `UUID` | No FK |
| `allocated_amount` | `NUMERIC(20,6)` | |
| `allocation_order` | `INT` | Order within a single collection event |
| `is_reversal` | `BOOLEAN` | Default false |
| `reverses_allocation_reference_id` | `UUID` \| NULL | Self-FK RESTRICT; set only when `is_reversal=true` |
| `allocated_at` | `TIMESTAMPTZ` | |

**Never updated or deleted** — a reversal always inserts a new row (BR-INST-017, FR-INST-242).

**[CORRECTED, final correction pass] Financial mechanism and commit ownership**: rows are created by staging `AccountsReceivableService`/`PaymentService`/`AllocationEngine` writes flush-only (`stage_customer_payment()` + `stage_allocation()`), then flushing this row into the same session, then Installments calls the corresponding `finalize_customer_payment()`/`finalize_allocation()` as the single commit point (`plan.md` §12.3.1) — never created against an already-committed Accounting fact. `is_reversal=true` rows follow a different but equally rigorous rule: since they carry no dependency on the Accounting reversal having already happened, they are flushed *before* Installments calls `reallocate_payment()`/`cancel_payment()` (unmodified, existing methods — no Accounting-side change), so they are swept into that call's first internal commit (`plan.md` §12.3.2).

---

## InstallmentLateCharge

One occurrence of a policy-driven late charge (spec §14.2).

| Field | Type | Notes |
|---|---|---|
| `contract_id` / `schedule_line_id` | `UUID` | FK RESTRICT each |
| `charge_amount` | `NUMERIC(20,6)` | |
| `charged_at` | `TIMESTAMPTZ` | |
| `overdue_occurrence_date` | `DATE` | The specific due date this charge is for |
| `accounting_journal_entry_id` | `UUID` \| NULL | No FK; set once posted |
| `accounting_ar_transaction_id` | `UUID` \| NULL | **[CORRECTED]** No FK — cross-module reference to the `DEBIT_NOTE`-type `ARTransaction` created for this charge via Accounting's extended `adjust_receivable()`. Without this field the charge could never be linked back to the AR row that makes it collectible (via ordinary payment allocation) and reversible. See `plan.md` §12.1. |
| `waived_at` / `waived_by` / `waived_reason` | as above | Controlled waiver, distinct permission |

**Constraints**: unique `(schedule_line_id, overdue_occurrence_date)` — never charged twice for the same occurrence.

**[CORRECTED, further frozen] Financial mechanism**: creation calls Accounting's `AccountsReceivableService.stage_adjustment(transaction_type="DEBIT_NOTE", source_document_type="InstallmentLateCharge", source_document_id=<this row's id>, ...)` (flush-only — GL + `ARTransaction` + ledger recompute staged, not committed), then this row itself is flushed into the **same session**, then Installments calls `AccountsReceivableService.finalize_adjustment(staged, actor_id)` as the **single commit point** for all of it together (`plan.md` §12.1/§12.2). Waiver follows the mirror sequence via `AccountsReceivableService.reverse_adjustment()`. Both `accounting_journal_entry_id` and `accounting_ar_transaction_id` are set together, or neither is (atomic) — this row is never left referencing a committed Accounting fact that this row itself failed to commit alongside, or vice versa.

---

## InstallmentAuditLog **[append-only]**

(spec §21). See `plan.md` §17 for the full field list and fail-closed discipline. `action` values enumerate every mutation named in FR-INST-340.

---

## InstallmentsFeatureFlag

Tenant module master toggle, mirrors `CrmFeatureFlag` exactly: `flag_key` (default `'feature.installments.enabled'`), `is_enabled` (default `false`). Unique `(company_id, flag_key)`.

---

## InstallmentSequence

Contract-number generator, mirrors `SalesSequence`/`AccountingSequenceService`'s locking pattern: `document_type` (`'IC'`), `prefix`, `current_value`, `year`, `reset_yearly`, `format_pattern`. Unique `(company_id, document_type, year)`.

---

## InstallmentIdempotencyKey

See `plan.md` §20 for full schema and the corrected `INSERT...ON CONFLICT DO NOTHING...RETURNING` reservation flow. Unique `(company_id, operation, idempotency_key)`. `status` is `'IN_PROGRESS'` (transient, never durably observable by another transaction under `READ COMMITTED` isolation) or `'COMPLETED'` (the only durably-persisted value) — **[CORRECTED] `'FAILED'` was removed**: a failed business operation rolls back its whole transaction, including this row, so `'FAILED'` could never actually be committed and was dead schema.

---

## Cross-entity invariants (validation rules spanning multiple entities)

| Invariant | Enforced by |
|---|---|
| `sum(InstallmentScheduleLine.scheduled_amount for active version) == InstallmentContract.contractual_total` | Service-layer check before `APPROVED → ACTIVE`, backed by the schedule engine's deterministic residual assignment |
| At most one non-terminal `InstallmentContract` per `(company_id, sales_invoice_id)` | DB partial unique index |
| `SUM(InstallmentAllocationReference.allocated_amount, non-reversed) <= InstallmentScheduleLine.scheduled_amount` per line | Computed under a `FOR UPDATE` lock on the parent contract before any new allocation-reference insert |
| `InstallmentContract.currency_code` never changes after creation | No update path exists in the service layer for this field |
| `InstallmentLateCharge` never charged twice for the same `(schedule_line_id, overdue_occurrence_date)` | DB unique constraint |
