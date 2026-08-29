# Epic 10 — Installments: Phase 0 Research

Consolidated technical decisions from repository inspection of `backend/modules/{accounting,sales,crm,platform_admin,users_roles}` and `frontend/src`. Each entry resolves one NEEDS CLARIFICATION-class question from the Technical Context. Full supporting detail lives in `plan.md`.

---

## R1. Money precision

- **Decision**: `NUMERIC(20,6)` for all Installments monetary columns, `Decimal` in Python, currency code stored alongside every amount, `ROUND_HALF_UP` quantization to 6 dp for internal calculation.
- **Rationale**: Accounting (the module Installments settles against) uses `NUMERIC(20,6)`; Sales uses `NUMERIC(15,2)`. Spec Assumption A4 already resolves this in Accounting's favor. No shared `Money` value object exists to reuse despite Constitution §48 naming one.
- **Alternatives considered**: Sales' `NUMERIC(15,2)` (rejected — spec explicitly resolves against it); a new shared `Money` type in `core/` (rejected — out of scope, would be an unrequested platform-wide change).

## R2. One-contract-per-obligation enforcement

- **Decision**: PostgreSQL partial unique index — `ON installment_contracts(company_id, sales_invoice_id) WHERE status NOT IN ('CANCELLED','COMPLETED','WRITTEN_OFF')`.
- **Rationale**: `Subscription.uq_subscriptions_company_active` is an exact, existing precedent for "at most one active row per key," already trusted in production-adjacent Platform Admin code.
- **Alternatives considered**: Application-level `SELECT`-then-`INSERT` check alone (rejected — explicitly race-unsafe, forbidden by the planning brief); a DB trigger (rejected — Constitution §17 prohibits business logic in triggers).

## R3. Schedule versioning mechanism

- **Decision**: `InstallmentScheduleVersion` (immutable) + `InstallmentScheduleLine` (immutable, two narrow audited exceptions for waive/void).
- **Rationale**: BR-INST-017 and FR-INST-114 require that an active schedule is never silently overwritten and that history is never destructively rewritten. A version-number-plus-immutable-lines design satisfies both without a general-purpose event-sourcing engine.
- **Alternatives considered**: A single mutable `InstallmentSchedule` with an `edited_at` audit trail (rejected — cannot guarantee old allocation references remain valid pointers after an edit); full event sourcing (rejected — explicitly named as over-engineering in the planning brief; no repository precedent for it).

## R4. Idempotency mechanism [UPDATED — correction pass]

- **Decision**: New, Installments-scoped `InstallmentIdempotencyKey` table — `(company_id, operation, idempotency_key)` unique, storing a request fingerprint and a replayable result, staged in the same transaction as the guarded business operation. Reservation uses PostgreSQL `INSERT...ON CONFLICT DO NOTHING...RETURNING` (SQLAlchemy `postgresql.insert()`), never a bare `INSERT` caught for `IntegrityError`. The `FAILED` status value is removed — traced end-to-end, it can never be durably committed (a failed operation's whole transaction, including the row, rolls back), so it was dead schema.
- **Rationale**: No reusable idempotency-key infrastructure exists anywhere in the backend. The one analogous case, `RecurringJournalService`, uses a narrower business-key-plus-unique-constraint pattern (no client-supplied key, no payload fingerprinting, no stored replay result, and its actual race backstop is an *uncaught* `IntegrityError`) — a useful structural precedent for the table-design half of the problem, but its conflict-handling half is exactly the anti-pattern to avoid. Repository-wide grep confirmed zero application-code use of `INSERT...ON CONFLICT`/`postgresql.insert()` (only inside raw-SQL migrations) and zero application-code use of `session.begin_nested()`/`SAVEPOINT` (the only occurrence anywhere is a test-isolation fixture) — so neither of the two obvious conflict-handling idioms had a production precedent to lean on; `ON CONFLICT DO NOTHING` was chosen because it is the only one of the two that never puts the transaction into an aborted state, which is the property actually required here.
- **Alternatives considered**: Reuse `RecurringJournalInstance`'s exact pattern unmodified (rejected — it has no concept of a client-supplied key, payload fingerprinting, or a stored replay result, all required by FR-INST-381, and its `IntegrityError`-based backstop is unsafe for a request path where duplicate submission is an expected, not exceptional, case); a savepoint-wrapped plain `INSERT` (rejected — zero production precedent in this codebase, and strictly more complex than `ON CONFLICT DO NOTHING` for an identical outcome); build a platform-wide `core/idempotency` module (rejected — larger blast radius than this Epic should take on; the module-local table is the smallest viable version, easily promotable later).

## R5. Concurrency mechanism per operation class

- **Decision**: `SELECT ... FOR UPDATE` on `InstallmentContract` for money-mutating sequences (collection, settlement, write-off); optimistic `version` column with conditional `UPDATE ... WHERE version = expected` for discrete state transitions (approve/reject/reschedule).
- **Rationale**: Two conventions already coexist platform-wide — pessimistic locking for aggregate/sequence rows under active money math (`ARTransactionRepository.get_by_id_locked()`), and Inventory's conditional-`UPDATE` optimistic pattern for status transitions. Using each where it already fits the platform's own precedent, rather than picking one universally, matches the planning brief's explicit instruction not to apply every technique everywhere without reason.
- **Alternatives considered**: Optimistic locking everywhere (rejected for collections specifically — a multi-step Accounting round-trip makes late conflict detection a worse UX than serialization); pessimistic locking everywhere (rejected for approve/reject — unnecessarily blocks a low-contention, human-paced action).

## R6. Entitlement enforcement granularity

- **Decision**: `InstallmentAccessPolicy`, a small service class checked inline inside every service method, classifying each operation as `ORIGINATION`/`SERVICING`/`READ`/`ADMIN`. No blanket router-level entitlement dependency.
- **Rationale**: CRM's existing `require_crm_enabled` is a router-mount-level, binary gate — it cannot express "block new business, permit continued servicing," which spec FR-INST-353–358 requires. Reuses `PlatformEntitlementService.resolve_effective_entitlement()` unchanged (per FR-INST-352's explicit prohibition on competing resolution logic) and adds only a thin classification layer.
- **Alternatives considered**: Two parallel routers, one gated and one not (rejected — more moving parts than one policy class); per-endpoint FastAPI dependency functions instead of inline calls (viable alternative, not chosen — kept stylistically consistent with how every other fine-grained permission check in the codebase is already done, inline in the service/route body).

## R7. Domain event mechanism

- **Decision**: Transactional outbox (`core/events/outbox.py`), matching `companies`/`users_roles` — not the in-process `EventBus` four other business modules use.
- **Rationale**: Constitution §49 requires events to be published in the same DB transaction as the originating action ("outbox pattern or equivalent"). The in-process bus variant used by inventory/purchase/sales/accounting/crm does not persist events at all — a pre-existing constitutional gap in those modules, not a pattern to propagate into a sixth, especially for a money-adjacent domain.
- **Alternatives considered**: Copy the sibling-module in-process bus for stylistic consistency (rejected — consistency with a non-compliant pattern is not itself a virtue; the compliant, reusable outbox already exists and needs zero new infrastructure).

## R8. Audit log shape

- **Decision**: Accounting's richer `AccountingAuditLog` shape (`before_state`/`after_state`/`reason`/`session_context`/`occurred_at`, plain `Base` with explicit `company_id`) rather than CRM's minimal shape.
- **Rationale**: Installments actions are financially sensitive and frequently carry a mandatory reason (cancellation, default, write-off, waiver, cure) — matching Accounting's own justification for the richer shape.
- **Alternatives considered**: CRM's minimal shape (rejected — would need `reason`/`session_context` bolted on ad hoc, defeating the point of following an existing convention).

## R9. Branch scoping

- **Decision**: Reserve `branch_id: UUID | None` on `InstallmentConfiguration`/`InstallmentContract`; no authorization system built.
- **Rationale**: No `Branch` entity or branch-authorization system exists anywhere in the platform today (confirmed by exhaustive grep). Constitution §10 requires readiness, not an implemented entity. Building branch authorization with no platform precedent to follow would mean inventing a new, un-validated pattern — explicitly discouraged by the planning brief.
- **Alternatives considered**: Skip `branch_id` entirely (rejected — would require a schema-breaking migration later); build a full branch-authorization layer now (rejected — nothing to build it consistently against yet).

## R10. Document generation

- **Decision**: Plain structured JSON responses (`InstallmentDocumentService`), mirroring Accounting's `AccountsPayableService.generate_remittance_advice()` — no PDF rendering.
- **Rationale**: No document/PDF-rendering infrastructure exists anywhere in the backend outside Purchase's unrelated, non-reusable services. Building new rendering infrastructure is out of this Epic's scope unless the business later requires it.
- **Alternatives considered**: Build new PDF infrastructure now (rejected — new infrastructure with no existing pattern to follow, flagged instead as a follow-up decision).

## R11. Background processing

- **Decision**: No background job is required for correctness (all due-state is read-time-derived). One optional, non-load-bearing job may emit `InstallmentOverdue` notification-trigger events; no generic platform scheduler was found to hang it on, so it is deferred out of Epic 10's implementation scope.
- **Rationale**: Spec explicitly says background jobs "MAY" be used for reminders/notifications, never as the source of contractual truth (FR-INST §31 preamble). No Celery/Redis/generic scheduler exists platform-wide, and introducing one solely for this optional convenience would violate the "no unnecessary infrastructure" instruction.
- **Alternatives considered**: Build a new scheduler for this one job (rejected — disproportionate to a non-essential feature).

## R12. Late-charge AR mechanism [UPDATED — micro-correction pass]

- **Decision**: Late charges are posted through a **new staged/finalize method pair** on `AccountsReceivableService`: `stage_adjustment(...)` (flush-only, no commit — builds the GL posting via `PostingEngine.stage_direct_posting()`, the `DEBIT_NOTE`-type `ARTransaction`, and the `CustomerLedger` recompute) and `finalize_adjustment(staged, actor_id)` (a thin wrapper calling `PostingEngine.finalize_and_publish()` — the sole commit point). The existing `adjust_receivable()` becomes a 100%-backward-compatible wrapper of both, unchanged for its existing standalone callers. A new `reverse_adjustment()` handles waivers. Installments' `AccountingIntegrationGateway` calls `stage_adjustment()`, stages its own `InstallmentLateCharge`/audit/outbox rows into the same session, then calls `finalize_adjustment()` **itself, last** — making Installments' own service method the owner of the single final commit for the whole cross-module unit of work.
- **Rationale**: The originally planned `PostingEngine.post_direct(DR AR / CR Income)`-only design would have increased GL Accounts Receivable while leaving `ARTransaction`/`CustomerLedger.total_outstanding_base` completely unchanged — a GL-vs-subledger truth divergence, fixed by the first correction pass. That fix alone (a single, still-internally-committing `adjust_receivable()` extension) left a *second*, narrower atomicity gap: `adjust_receivable()` still called `finalize_and_publish()` (which commits) internally, before Installments ever got a chance to stage its own rows — so a failure while staging `InstallmentLateCharge`/audit/outbox could leave those rows missing against an already-committed Accounting fact. Precise re-inspection of `PostingEngine.stage_direct_posting()`/`finalize_and_publish()`'s exact commit boundary (confirmed by line number: the only `db.commit()` in that pair is inside `finalize_and_publish()`) proved the fix requires splitting the AR-side logic itself into the identical two-phase shape, not just adding parameters to a single method.
- **Alternatives considered**: A `commit=False` boolean parameter on `adjust_receivable()` (rejected — no existing Accounting method anywhere in the codebase uses a boolean commit-toggle parameter; the stage/finalize method-pair is the established, already-precedented idiom via `PostingEngine` itself, more consistent to extend one layer up than to introduce a new convention); leave the late charge as a bare GL posting with no `ARTransaction` (rejected — this was the original defect); invent a new Installments-owned AR mechanism (rejected — would violate BR-INST-004's prohibition on shadow AR).

## R13. Permission backfill for pre-existing tenants [NEW — correction pass]

- **Decision**: Migration `071_installments_permission_backfill` is **mandatory**, not conditional — structurally identical to `056_crm_permission_backfill.py` (pure `op.execute()` SQL, `ON CONFLICT DO NOTHING`, scoped to `role.is_system = true`), with an explicit per-system-role default grant table derived from spec §4's actor descriptions (see `plan.md` §30.1).
- **Rationale**: `RoleSeedService` only seeds `INITIAL_PERMISSIONS`/`DEFAULT_ROLE_PERMISSIONS` (read from `constants.py`) at company-creation time — a pre-existing company never retroactively receives permission codes added to `constants.py` after its own creation. `056_crm_permission_backfill.py` exists specifically because CRM hit this exact gap; there is no other deterministic, automatic backfill mechanism anywhere in the platform (no ORM event listener, no startup reconciliation job).
- **Alternatives considered**: Leave it conditional/deferred to a later decision (rejected — explicitly disallowed by this correction pass; "the final plan must have one answer, not maybe"); auto-grant to all roles including custom ones (rejected — violates the existing platform policy that custom roles are only as privileged as what was explicitly assigned, mirrored exactly by `056`'s `role.is_system = true` filter); grant CRM's exact role set unchanged (rejected — CRM granted zero permissions to `cashier`, but Installments' own spec explicitly names Cashier/Collector as a collection-recording actor, so blindly copying CRM's role-set would under-grant relative to spec's own actor table).

## R14. Cross-module Accounting commit ownership [NEW — micro-correction pass]

- **Decision**: General rule — any Accounting service method Installments calls as part of a larger atomic Installments workflow must expose a staged (flush-only) variant; Installments' own service method always owns the single final commit by calling the corresponding finalize method as its own last step, after every Installments-side row is already staged into the same session.
- **Rationale**: Precise re-inspection of `PostingEngine.stage_direct_posting()`/`finalize_and_publish()` (`posting_engine.py:564-632`) confirmed the *only* commit in that pair is inside `finalize_and_publish()`, and that method's docstring is explicit about pairing with the staged half specifically so a caller can add more writes before committing. This is an existing, already-precedented idiom (used internally by `record_sales_invoice()`, `create_customer_payment()`) — the fix is to extend the identical idiom one layer up into `AccountsReceivableService`, not to invent a new commit-control mechanism.
- **Alternatives considered**: A `commit=False` parameter (rejected — no precedent, less explicit than a method-pair); letting Accounting decide when to commit and having Installments poll/retry to add its rows afterward (rejected — reintroduces the exact atomicity gap this decision closes, and is architecturally far more complex for no benefit).

## R15. Commit ownership generalized across every Installments↔Accounting workflow [NEW — final correction pass]

- **Decision**: Method-by-method re-inspection (not assumption) of every named workflow — activation/down payment, collection, settlement payment, collection reversal, cancellation-with-reversal, write-off. Confirmed the identical early-commit defect R14 fixed for late charges also exists in `PaymentService.create_customer_payment()` (down payment/collection/settlement) and `AccountsReceivableService.confirm_write_off()` (write-off, **three** separate internal commits — the worst case found). Fixed both with the identical staged/finalize method-pair pattern: `stage_customer_payment()`/`finalize_customer_payment()`, `AllocationEngine.stage_allocation()`/`finalize_allocation()`, `stage_write_off()`/`finalize_write_off()`. By contrast, `PaymentService.reallocate_payment()` (used for reversal) has a genuinely different shape — it commits **inside a loop**, once per existing allocation line — refactoring it would be a materially larger, more invasive change than any other fix in this plan. Proved a narrower guarantee is sufficient instead: Installments' own rows have no dependency on the reversal having already happened, so staging them *before* calling `reallocate_payment()`/`cancel_payment()` at all is enough — the first internal commit inside those (unmodified) methods necessarily sweeps in everything Installments already flushed. No Accounting-side code change is needed for reversal or cancellation.
- **Rationale**: The correction's own instruction — "do not assume an Accounting method is staged merely because it internally uses `stage_direct_posting()`; explicitly inspect whether it later calls `finalize_and_publish()` before returning" — proved essential: `confirm_write_off()`'s three-commit defect (one via `post_direct()`, two more via `BaseRepository.update()`'s own internal commit, confirmed at `core/repositories/base.py:106`) would have gone completely undetected without this explicit, line-by-line re-inspection.
- **Alternatives considered**: Refactoring `reallocate_payment()`'s internal loop into a flush-only shape (rejected — a materially larger, more invasive change to existing, already-shipped, already-tested Accounting behavior than any other fix in this plan, for a guarantee the staging-order discipline already provides without it); treating reversal/cancellation's two-call sequence (`reallocate_payment()` then `cancel_payment()`) as a single atomic unit end-to-end (rejected as unachievable without the same large refactor — instead, the narrower, honestly-documented residual case is handled via idempotency-key resume logic, not hidden).

---

**All NEEDS CLARIFICATION items resolved**, including the five correction-pass findings above. No unknowns remain for Phase 1 design.
