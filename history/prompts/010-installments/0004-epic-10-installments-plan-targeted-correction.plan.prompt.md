---
id: 0004
title: Epic 10 Installments plan targeted correction
stage: plan
date: 2026-08-24
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: null
labels: [installments, epic-10, planning, correction, accounting-integration, idempotency, permission-backfill]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/010-installments/plan.md
 - specs/010-installments/research.md
 - specs/010-installments/data-model.md
tests:
 - none (planning-only correction pass; no code, migrations, or tests created per stop condition)
---

## Prompt

# Epic 10 — Installments

## `plan.md` — Targeted Technical Correction Pass

Review and update the existing:

`specs/010-installments/plan.md`

This is a **targeted technical planning correction only**.

Do NOT modify `spec.md`.

Do NOT generate `tasks.md`.

Do NOT implement code.

Do NOT create migrations.

Do NOT modify application source.

Do NOT redesign already-approved architecture unless directly required to correct one of the three issues below.

Preserve all accepted plan decisions, including: Accounting as the sole financial source of truth; InstallmentContract as aggregate root; one non-terminal contract per originating obligation; schedule versioning/historical immutability; explicit lifecycle methods; REJECTED as event, not persisted state; DEFAULTED → ACTIVE cure; origination-vs-servicing entitlement policy; tenant isolation; Platform Admin/support-access boundary; fail-closed audit; mixed concurrency strategy; modular-monolith architecture; transactional outbox decision; no new microservices/infrastructure.

Before editing, inspect the actual repository implementations relevant to each correction. Do not rely only on the current plan text.

---

# Correction 1 — Late-Charge Accounting / AR Truth

The current plan proposes `PostingEngine.post_direct()` with `DR Accounts Receivable / CR Late Fee Income` but also states that no `ARTransaction` is created because the late charge is "a fee, not a schedule obligation." This may create a mismatch between General Ledger AR, Accounting AR subledger/customer outstanding, customer ledger, and amount available for future payment allocation.

Re-inspect the actual Accounting implementation (`AccountsReceivableService`, `ARTransaction`, customer-ledger update/reconciliation logic, invoice/charge creation precedent, write-off flow, direct-posting behavior, `PaymentService`, `AllocationEngine`, any existing service that creates a non-invoice customer receivable, any adjustment/debit-note/fee mechanism already present) and determine the correct way to create a collectible customer receivable for a late charge. Answer technically: (1) Does `PostingEngine.post_direct(DR AR / CR Income)` alone increase authoritative customer AR? (2) If not, what existing service must be used so GL AR increases, AR subledger increases, customer outstanding increases, future payments can allocate against it, and reversal/waiver remains reconcilable? (3) Is a new AR transaction type/source required? (4) Can Installments accomplish this strictly through existing public Accounting services? (5) If no safe existing public service exists, define the smallest Accounting service extension needed — do not let Installments write Accounting tables directly.

A posted installment late charge MUST be represented consistently in all authoritative Accounting layers that define collectible AR — GL AR and ARTransaction/customer outstanding must never diverge in either direction. Late charges must be collectible, allocatable, reversible, auditable, fiscal-period controlled, tenant-scoped, and reconcilable. Update all affected sections (§12, §11, §25, §21, §22, §31, ADR-INST-01 if needed, risks/trade-offs, traceability). Do not alter the business rule that late charges are optional/configurable.

---

# Correction 2 — Idempotency Conflict Handling Must Be PostgreSQL/SQLAlchemy Safe

The current plan proposes: (1) INSERT IN_PROGRESS, (2) unique violation on duplicate, (3) fetch existing row, (4) inspect COMPLETED/IN_PROGRESS — all inside the same transaction. In PostgreSQL, a normal unique-constraint violation places the current transaction into an error state until rollback or savepoint recovery.

Inspect SQLAlchemy session conventions, any use of PostgreSQL `INSERT ... ON CONFLICT`, `session.begin_nested()`/savepoint precedents, conflict-handling patterns, `IntegrityError` handling conventions, transaction/rollback discipline. Choose and document one exact mechanism, evaluating Option A (`INSERT ... ON CONFLICT ... DO NOTHING ... RETURNING`, then fetch/replay/409 accordingly) vs. Option B (savepoint/nested transaction, only if it aligns better with existing conventions). Do not describe a plain unique-violation flow that leaves the outer transaction unusable.

Explicitly handle the race where Request A inserts IN_PROGRESS but has not committed and Request B arrives with the same key — document actual PostgreSQL behavior and the intended user-facing outcome. Required guarantees: exactly one request executes the financial effect; same key + same payload after completion replays the original response; same key + different payload returns conflict; concurrent duplicate cannot perform a duplicate financial write; failed original transaction does not permanently strand the key; idempotency state and business state remain atomic.

Also determine whether FAILED is genuinely needed as a persisted status — the current plan says failed transactions roll back the idempotency row entirely, which may make FAILED unused/dead schema. Either remove FAILED, or define a real, justified persisted-failure lifecycle — do not retain unused state merely because it was previously listed.

Update §20, §21, §22, §23 (if response semantics change), §31, §37, ADR-INST-08. Keep idempotency module-local unless repository inspection proves a safe reusable platform primitive already exists.

---

# Correction 3 — Migration 071 / Existing-Tenant Permission Backfill Must Be Deterministic

The current plan leaves migration `071_installments_permission_backfill` conditional ("only if backfilling installments permissions onto pre-existing companies' system roles is desired"). Do not leave this decision conditional before `/sp.tasks`.

Inspect actual Users/Roles permission-seeding behavior (`RoleSeedService`, permission creation/seeding, system role creation, default permission assignment, prior permission backfill migrations, `056_crm_permission_backfill.py`, any Platform Admin or Accounting permission backfills, behavior for existing tenants after deployment) and determine: (1) Will existing companies automatically receive the new `installments.*` permission records? (2) Will their system roles automatically receive appropriate permission assignments? (3) If not, is a migration required? (4) Which roles should receive which permissions by default based on existing role conventions? (5) How will custom roles behave? (6) Must custom roles remain unchanged until tenant admins explicitly grant Installments permissions?

Recommended policy unless repository conventions contradict it: all new `installments.*` permission definitions should be created for existing tenants; built-in/system roles should receive the same default mappings they would receive if the company were created after Epic 10 shipped; custom roles should not be automatically granted new financial permissions; backfill must be idempotent; existing permissions must never be removed or reset. If repository inspection supports this, make migration 071 mandatory, not conditional. The final plan must have one answer — not "maybe." Update §30, §16, deployment/backward compatibility, implementation sequence, testing strategy, final planning report.

---

# Additional Consistency Review

After correcting the three issues, verify: late-charge financial truth cannot diverge between GL and AR subledger; a late charge can actually be collected through Accounting's normal payment-allocation mechanism; late-charge reversal/waiver restores GL and AR consistently; Installments still performs no direct Accounting-table writes; idempotency duplicate handling does not leave the SQLAlchemy transaction in an aborted state; concurrent same-key requests cannot both execute; idempotency schema contains no unused lifecycle state; existing tenant permission behavior is fully deterministic; existing system roles receive intended permission backfill; custom roles are not silently over-privileged; migration numbering/dependencies remain valid; no approved spec.md business behavior has changed; no new blocking clarification has been introduced unless repository evidence genuinely requires product-owner input.

---

# Important — Do Not Reopen Accepted Design Decisions

Do NOT change (unless technically unavoidable and explicitly reported): one-contract partial unique index; NUMERIC(20,6) money strategy; final-installment residual strategy; schedule-version model; contract lifecycle; cure semantics; entitlement servicing continuity; disabled-entitlement operation classification; tenant suspension behavior; Platform Admin/support-access structural boundary; FOR UPDATE strategy for collections; optimistic versioning for approval/rejection; audit fail-closed pattern; transactional outbox; JSON-structured documents; no-background-job correctness; future AI guardrails.

---

# Scope / Files

Primary file: `specs/010-installments/plan.md`. Update other planning artifacts only if the existing SpeckitPlus workflow requires them to remain synchronized (research.md, data-model.md, contracts/installments-api.yaml, quickstart.md, planning checklist, PHR). Do not modify application code, create migrations, create tasks.md, or modify spec.md.

---

# Required Final Correction Report

After the correction pass, report: exact files modified; late-charge Accounting finding (repository behavior discovered, previous risk, final corrected design); idempotency finding (exact PostgreSQL/SQLAlchemy mechanism selected, concurrent duplicate behavior, whether FAILED state remains or was removed); permission-backfill finding (behavior for new tenants, behavior for existing tenants, system-role behavior, custom-role behavior, whether migration 071 is mandatory/removed/replaced); sections/ADRs updated; any migration-sequence change; any API-contract change; confirmation Accounting remains sole financial source of truth; confirmation no spec.md business rule changed; remaining technical clarifications, if any; final status (READY FOR /sp.tasks or NOT READY FOR /sp.tasks — <exact blocker>).

---

# Stop Condition

Do NOT run `/sp.tasks`. Do NOT implement code. Do NOT create migrations. Stop after repository re-inspection, targeted `plan.md` corrections, synchronization of required planning artifacts, and the final correction report.

## Response snapshot

Re-inspected the repository for each of the three corrections before editing anything:

**Correction 1 (late-charge AR truth)**: Spawned a focused Explore agent against `modules/accounting/services/ar_service.py`, `payment_service.py`, `posting_engine.py`, `allocation_engine.py`. Found that `PostingEngine.post_direct()` alone never touches `ARTransaction`/`CustomerLedger` (it only writes `JournalEntry`/`JournalLine`) — confirming the original design's defect. Found `AccountsReceivableService.adjust_receivable()` (`ar_service.py:613-706`) is the only existing method that creates a non-invoice `ARTransaction` alongside a GL posting, using the `ADJUSTMENT` transaction_type (`DEBIT_NOTE` exists in the CHECK constraint but is never actually used anywhere). Found `adjust_receivable()` itself has a real atomicity gap (calls `post_direct()`, which commits, then inserts the `ARTransaction` and recomputes the ledger in separate later commits — unlike `record_sales_invoice()`'s correct one-transaction `stage_direct_posting()`/`finalize_and_publish()` shape) and lacks `source_document_type`/`source_document_id` params. Found the only fully-automated reversal precedent is `PaymentService.cancel_payment()`'s stage-then-`PostingEngine.reverse()` pattern. Corrected the plan to require Installments call an **extended** `adjust_receivable()` (atomic staging + `source_document_type`/`id` + configurable `transaction_type="DEBIT_NOTE"`) plus a **new** `reverse_adjustment()` method — both small, additive, backward-compatible changes inside `modules/accounting`, templated exactly on existing methods, not new architecture. Updated §7 (new `accounting_ar_transaction_id` field), §12 (new §12.1 subsection answering all 5 mandated questions + corrected Late Charge/Waiver integration-table rows), §11.3 (late charges are now ordinarily allocatable — no special-case code needed since `AllocationEngine` never filters by `transaction_type`), §21 (new Late Charge/Waiver atomic-unit rows), §22 (explicit atomicity-restored note), §31 (three new Accounting-integration test cases), §36 (Phase 6 now names the two required Accounting-side changes as an explicit prerequisite), §37 (new risk row), §38 (Delinquency traceability row updated), and ADR-INST-01 (added a correction note explaining why this was a real ADR-01 violation, now fixed).

**Correction 2 (idempotency conflict handling)**: Grepped the entire backend for `ON CONFLICT`/`postgresql.insert` (found zero application-code usage, only inside raw-SQL migrations) and `begin_nested`/`SAVEPOINT` (found zero application-code usage — the only occurrence anywhere is `tests/conftest.py`'s test-isolation fixture) and `IntegrityError` handling (found the dominant convention is "check-then-create," explicitly to avoid ever hitting a raw `IntegrityError` mid-request). Confirmed the original plan's bare-unique-violation-catch flow was indeed unsafe (would abort the transaction with no savepoint to recover to). Redesigned §20 around `INSERT...ON CONFLICT DO NOTHING...RETURNING` (SQLAlchemy `postgresql.insert()`), which never raises for the conflicting case; documented PostgreSQL's actual concurrent-insert blocking behavior (the second inserter blocks on the first's row-level lock until it resolves, naturally serializing without any explicit `SELECT...FOR UPDATE`) in a new §20.3 table covering all five required guarantees. Traced the `FAILED` status end-to-end and confirmed it can never actually be committed under the single-transaction design (a failed operation's whole transaction, including the row, rolls back) — removed it from the schema as genuinely dead state, keeping only `IN_PROGRESS` (real but never cross-transaction-observable, per `READ COMMITTED` MVCC semantics) and `COMPLETED`. Updated §20 (full rewrite), §21 (reservation-ordering clarification), §22 (failure-table row), §23 (new idempotent-response-semantics paragraph), §31 (three new/expanded idempotency test cases), §37 (new risk row about first-use-of-`ON CONFLICT`-in-this-codebase), and ADR-INST-08 (full rewrite with an explicit Option A vs. Option B vs. original-bare-catch alternatives analysis).

**Correction 3 (permission backfill)**: Re-confirmed via direct grep/read of `056_crm_permission_backfill.py` (structure, idempotency mechanism, `role.is_system = true` scoping, explicit "cashier/store-keeper receive zero grants" precedent) and `constants.py`'s per-role frozenset convention (`_CRM_OWNER`, `_CRM_ADMIN`, etc.) that `RoleSeedService` only seeds new companies at creation time — an existing company never retroactively receives permission codes added to `constants.py` later, which is exactly why `056` had to exist for CRM. Concluded migration 071 must be **mandatory, not conditional** — one deterministic answer, not "maybe," as required. Designed an explicit 8-system-role default grant table for the 16 `installments.*` permissions, deliberately deviating from CRM's "cashier gets zero" precedent for the `cashier` role specifically (granting `contract.view`+`collection.create`) because spec §4 explicitly names Cashier/Collector as a collection-recording actor — a spec-grounded, justified departure from blind precedent-copying. Updated §30 (migration 071 reclassified as mandatory + new §30.1 answering all 6 mandated questions with the full role-grant table), §16 (new-tenant-vs-existing-tenant clarifying note), §34 (deployment-impact clarification confirming zero behavioral change despite the new dormant grants).

Verified the 13-point consistency-review checklist explicitly (see final correction report). Synchronized `research.md` (rewrote R4, added R12 and R13) and `data-model.md` (`InstallmentLateCharge` gained `accounting_ar_transaction_id` + a corrected-mechanism note; `InstallmentIdempotencyKey` gained the corrected status-value explanation). No change was needed to `contracts/installments-api.yaml` or `quickstart.md` (neither encodes the corrected internals at a level requiring edits). No accepted design decision listed in the "do not reopen" section was touched. `spec.md` was not modified. No code, migrations, or `tasks.md` were created, per the stop condition.

## Outcome

- ✅ Impact: All three identified plan defects (a genuine GL-vs-AR-subledger truth divergence risk in the late-charge design; an unsafe PostgreSQL conflict-handling flow that would have aborted transactions in production; an underspecified "maybe" on existing-tenant permission backfill) are now corrected with repository-grounded, atomically-consistent designs — `plan.md` is materially safer to implement against than before this pass.
- 🧪 Tests: none created (planning-only correction pass) — the testing strategy sections (§31) were expanded with the specific new test cases each correction requires.
- 📁 Files: specs/010-installments/{plan.md, research.md, data-model.md} updated; this PHR.
- 🔁 Next prompts: `/sp.tasks` to decompose the corrected plan.md into executable tasks — the Phase 6 (Accounting Integration) task breakdown should explicitly sequence the two required `modules/accounting` extensions (`adjust_receivable()` extension, new `reverse_adjustment()`) before any Phase 8 (Delinquency/late-charge) task.
- 🧠 Reflection: All three corrections shared a common shape — the original plan's design was *architecturally reasonable in intent* but hadn't been checked against the *exact* transactional/MVCC/seeding-timing behavior of the specific mechanism it was building on (PostingEngine's table scope, PostgreSQL's unique-violation transaction-abort behavior, RoleSeedService's creation-time-only seeding). Re-inspecting the precise mechanics (not just the existence of a pattern) each time was what surfaced the defect and the fix simultaneously.

## Evaluation notes (flywheel)

- Failure modes observed: none in this pass's own execution — the original plan.md's three flagged defects were exactly the failure modes this correction pass was designed to catch, confirming the value of a dedicated re-inspection-before-editing correction workflow over trusting a first-pass plan's internal consistency.
- Graders run and results (PASS/FAIL): N/A — planning-only phase, no automated grading harness invoked.
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): For future `/sp.plan` first passes on integration-heavy epics, consider a mandatory "trace the exact transaction/commit boundary of every proposed cross-module call" check before finalizing — this would likely have caught Correction 1's atomicity gap and Correction 2's unsafe conflict handling during the original planning pass rather than requiring a dedicated correction pass afterward.
