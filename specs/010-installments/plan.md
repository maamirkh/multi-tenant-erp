# Epic 10 — Installments: Implementation Plan

**Feature Branch**: `010-installments` | **Status**: Planning complete — ready for `/sp.tasks` | **Author**: Claude (planning agent) | **Date**: 2026-08-24

**Input**: `specs/010-installments/spec.md` (v1.1.0, all Open Questions permanently resolved) + full repository inspection of `backend/modules/{accounting,sales,crm,platform_admin,users_roles}` and `frontend/src`.

This document is a **technical plan**, not a specification. It does not redefine any business rule, invariant, or lifecycle decision in `spec.md`. Every FR-INST-*, BR-INST-*, and Scenario referenced below is treated as fixed; this plan only decides *how* the existing repository's architecture implements it.

---

## Table of Contents

1. [Technical Context](#1-technical-context)
2. [Repository Findings](#2-repository-findings)
3. [Constitution Compliance](#3-constitution-compliance)
4. [Architecture Overview](#4-architecture-overview)
5. [Domain Boundary](#5-domain-boundary)
6. [Domain Model](#6-domain-model)
7. [Database / Persistence Design](#7-database--persistence-design)
8. [Money & Precision Strategy](#8-money--precision-strategy)
9. [Installment Lifecycle Architecture](#9-installment-lifecycle-architecture)
10. [Schedule Engine](#10-schedule-engine)
11. [Collection / Allocation Architecture](#11-collection--allocation-architecture)
12. [Accounting Integration](#12-accounting-integration)
13. [Sales Integration](#13-sales-integration)
14. [CRM / Inventory Integration](#14-crm--inventory-integration)
15. [Entitlement Architecture](#15-entitlement-architecture)
16. [RBAC / Maker-Checker](#16-rbac--maker-checker)
17. [Audit Architecture](#17-audit-architecture)
18. [Multi-Tenant / Branch Isolation](#18-multi-tenant--branch-isolation)
19. [Concurrency Strategy](#19-concurrency-strategy)
20. [Idempotency Strategy](#20-idempotency-strategy)
21. [Transaction / Atomicity Boundaries](#21-transaction--atomicity-boundaries)
22. [Failure / Recovery Design](#22-failure--recovery-design)
23. [API Architecture](#23-api-architecture)
24. [Frontend Architecture](#24-frontend-architecture)
25. [Reporting / Query Architecture](#25-reporting--query-architecture)
26. [Domain Events](#26-domain-events)
27. [Documents / Statements](#27-documents--statements)
28. [Background Processing](#28-background-processing)
29. [Security Architecture](#29-security-architecture)
30. [Migration Strategy](#30-migration-strategy)
31. [Testing Strategy](#31-testing-strategy)
32. [Observability](#32-observability)
33. [Performance / Indexing](#33-performance--indexing)
34. [Deployment / Backward Compatibility](#34-deployment--backward-compatibility)
35. [Future AI Readiness](#35-future-ai-readiness)
36. [Implementation Sequence / Dependency Graph](#36-implementation-sequence--dependency-graph)
37. [Risks / Trade-Offs](#37-risks--trade-offs)
38. [Requirement Traceability](#38-requirement-traceability)
39. [Open Technical Decisions](#39-open-technical-decisions)
40. [Architecture Decision Records](#40-architecture-decision-records)

---

## 1. Technical Context

| Item | Value |
|---|---|
| Language / Runtime | Python 3.12+ (backend), TypeScript 5.x strict (frontend) |
| Backend Framework | FastAPI 0.115+, Pydantic v2, SQLAlchemy 2.x (async-capable ORM, used synchronously — existing convention) |
| Migrations | Alembic, sequential project-wide numbering. Current head: `061_platform_support_access.py`. Installments starts at `062`. |
| Frontend Framework | Next.js 16 App Router, TanStack Query, TailwindCSS, `react-hook-form` + `zod` |
| Database | PostgreSQL 16 (existing `db` Docker Compose service) — no new datastore |
| Auth | Existing hand-rolled JWT auth (`core/auth`), tenant sessions, Platform Admin sessions are a structurally separate token type |
| New module | `backend/modules/installments/` — new vertical slice; `frontend/src/app/(protected)/(installments)/` — new route group |
| New infrastructure | **None required.** Reuses PostgreSQL, existing `core/events/outbox.py`, existing Alembic chain, existing Docker Compose stack. |
| NEEDS CLARIFICATION | None — repository inspection resolved every open technical question (see [§39](#39-open-technical-decisions)). |

---

## 2. Repository Findings

Repository inspection (5 parallel research passes across Accounting, Sales, Platform Admin/CRM, cross-cutting backend conventions, and frontend) produced the concrete precedents this plan builds on. Key findings, condensed:

| Area | Finding | Where confirmed |
|---|---|---|
| Money precision | Accounting uses `NUMERIC(20,6)` for amounts, `NUMERIC(20,10)` for FX rates. Sales uses `NUMERIC(15,2)`. No shared `Money` value object exists despite Constitution §48. | `modules/accounting/models/{payments,ar,gl}.py`, `modules/sales/models/{invoice,order}.py` |
| Payment/AR truth | `Payment` + `PaymentAllocationLine` + `ARTransaction` (+ `CustomerLedger` materialized cache, reconciled from `SUM(outstanding_amount)`) is the complete financial-truth chain. Every `Payment` creates a paired credit `ARTransaction`. Cross-module references use a **plain `party_type`/`party_id` pair with no FK** — not an ORM relationship. | `modules/accounting/models/payments.py`, `models/ar.py`, `services/payment_service.py` |
| GL posting boundary | `PostingEngine` is the sole GL writer. `stage_direct_posting()` + `finalize_and_publish()` is the two-phase API that lets a caller (e.g. `PaymentService`) add its own rows into the *same* DB transaction as the GL write before one final commit. `post_direct()` is the simpler all-in-one variant for single-write cases. | `modules/accounting/services/posting_engine.py:541-587` |
| Fiscal period gate | Enforced inside `PostingEngine` step 3 (`PostingValidationError`), independent of a secondary `FiscalCalendarService` check used elsewhere. Any caller through `PostingEngine` inherits the gate automatically. | `posting_engine.py:665-670` |
| Aging | `AgingCalculator._bucket_for()` is a free function with buckets `current/1-30/31-60/61-90/91-120/120+`, reusable as-is. | `services/aging_calculator.py` |
| Write-off | Not a distinct model — a state transition (`ARTransaction.status → WRITTEN_OFF`) plus one `PostingEngine.post_direct()` call (DR Bad Debt Expense / CR AR). | `services/ar_service.py:712-809` |
| **[Correction pass] Non-invoice AR adjustment** | `AccountsReceivableService.adjust_receivable()` is the **only** place in the codebase that creates a non-invoice `ARTransaction` (`transaction_type="ADJUSTMENT"`; `"DEBIT_NOTE"` is a valid CHECK-constraint value but is **never actually used** anywhere). It has a real atomicity gap: it calls `PostingEngine.post_direct()` (which commits) and only *afterward* inserts the `ARTransaction` and recomputes the ledger in **separate, later commits** — unlike `record_sales_invoice()`, which stages everything (GL + `ARTransaction` + ledger mutation) into one `stage_direct_posting()`/`finalize_and_publish()` unit. It also has no `source_document_type`/`source_document_id` parameters, so a caller cannot link the resulting `ARTransaction` back to its own record. `AllocationEngine`/`get_open_transactions()` never filter by `transaction_type`, so once a correctly-created `ADJUSTMENT`/`DEBIT_NOTE` `ARTransaction` exists, it is already fully payment-allocatable with zero further Accounting-side work. | `services/ar_service.py:613-706` (`adjust_receivable`), contrast `services/ar_service.py:153-250` (`record_sales_invoice`'s correct atomic shape) |
| **[Correction pass] ARTransaction reversal precedent** | No generic reversal path exists for an `ADJUSTMENT`/`DEBIT_NOTE` row today (even `confirm_write_off()`'s own docstring admits recovery is "a manual follow-up step, not automated"). The one **fully automated** precedent is `PaymentService.cancel_payment()`: stage (flush, not commit) an AR-side state change, then call `PostingEngine.reverse()`, whose own single commit makes both atomic. | `services/payment_service.py:969-1028` |
| **[Micro-correction pass] Exact commit ownership of `PostingEngine`'s two-phase API** | Precisely re-verified by line number: `stage_direct_posting()` (`posting_engine.py:564-611`) builds and **flushes only** — no `db.commit()` anywhere in its body, confirmed by grepping every `self.db.commit()` call site in the file (lines 206, 349, 398, 442, 466, 503, **624**, 828 — none inside `stage_direct_posting()`'s own line range). `finalize_and_publish()` (`posting_engine.py:614-632`) is the **sole** commit point for that pair — `self.db.commit()` at line 624, followed by `db.refresh(entry)` and the domain-event publish. `finalize_and_publish()`'s own docstring is explicit: "Commit the current transaction... Pairs with `stage_direct_posting()`." Its required parameters (`entry`, `journal_number`, `posted_at` — the exact tuple `stage_direct_posting()` returns) make the two-phase contract mechanically precise: whatever else has been `flush()`-ed into the same SQLAlchemy session between the two calls is committed together with the journal entry when `finalize_and_publish()` runs. **This confirms the corrected §12.1 extension must expose an equivalent staged/finalize split on `AccountsReceivableService` itself** — the existing (pass-2-corrected) `adjust_receivable()` still calls `finalize_and_publish()` (i.e. commits) internally before returning to its caller, which is exactly wrong for a cross-module caller that needs to add its own rows *before* that commit. `reverse()` (`posting_engine.py:744-833`) is a separate, single-phase method with its own commit at line 828 — no staged variant exists or is needed for it, since a reversal has no analogous "add more rows before commit" requirement from Installments' side beyond what `PaymentService.cancel_payment()` already demonstrates (stage AR-side change, then call `reverse()`, whose commit covers both — this pattern already works correctly as designed and needs no further split). | `services/posting_engine.py:564-632`, `:744-833` |
| **[Final correction pass] `create_customer_payment()`'s exact commit points** | Two branches, precisely re-read line-by-line: (1) the above-threshold **DRAFT** branch (`payment_service.py:229-279`) builds a `DRAFT` `Payment`, flushes, audits, then `self.db.commit()` at **line 278** and returns `(pending, None)` — no GL/AR/ledger writes exist yet at all, so this branch is a genuinely self-contained, already-atomic unit with nothing for Installments to bundle. (2) the normal **immediate-post** branch calls `stage_direct_posting()` (line 295, flush only), builds+flushes the `Payment` row, builds+flushes a credit `ARTransaction`, calls `_recompute_customer_ledger_balance()` (flush only, confirmed via its own body: `self.db.add(ledger)`, no commit), then `self._engine.finalize_and_publish(...)` at **line 374** — the sole commit for this branch, committing the payment, the credit `ARTransaction`, and the ledger recompute together. **Confirms `create_customer_payment()` needs the identical stage/finalize split already applied to `adjust_receivable()`** for its immediate-post branch; the DRAFT branch is out of scope for this fix (nothing to bundle). | `services/payment_service.py:196-383` |
| **[Final correction pass] `AllocationEngine.allocate()`'s exact commit points** | Re-read in full (`allocation_engine.py:103-276`): every write inside the per-line loop (`PaymentAllocationLine`, the target transaction's `outstanding_amount`/`status`, the payment's own credit-transaction `outstanding_amount`/`status`) uses `self.db.add(...)` + `self.db.flush()` directly — **no repository `.update()`/`.create()` calls**, so no hidden early commit inside the loop. The **only** commit(s) happen in the final block (lines 260-268): if any FX-gain/loss adjustment journal entries were staged during the loop, `finalize_and_publish()` is called once per staged entry (lines 262-266); otherwise a bare `self.db.commit()` (line 268). Because every business write precedes this final block, `allocate()` already has the same "everything flushed, commit(s) only at the very end" shape as `adjust_receivable()`'s corrected form — it needs the identical stage/finalize split, with the one nuance that "finalize" may issue **more than one** `finalize_and_publish()` call (one per FX-adjustment entry) — all of them downstream of the same fully-flushed state, so only the *first* call's commit is the actual atomicity-defining moment; subsequent calls in the same finalize step commit an already-durable state and only add their own entry's journal-numbering/event-publish bookkeeping. | `services/allocation_engine.py:103-276` |
| **[Final correction pass] `reallocate_payment()`'s exact commit points — genuinely multi-commit, not a simple single-final-commit shape** | Re-read in full (`payment_service.py:877-961`): unlike every other method inspected, this one commits **inside a loop**, once per existing allocation line being reversed — either via `self._engine.reverse(...)` (its own commit) or a bare `self.db.commit()` (line 950) when no gain/loss entry exists for that line — **and then a further `self.db.commit()`** (line 959) after setting `payment.status = "POSTED"`, **and then** it calls `self._allocation_engine.allocate(...)` (line 961), which has its own additional final commit(s). This is structurally the most eager-committing method in the codebase and would require refactoring its own internal loop (N commits → N flushes) to produce a true single-final-commit shape — a materially larger, more invasive change than any other fix in this plan. **Resolution** ([§12.3](#123-final-correction-pass-generalized-commit-ownership-across-every-installmentsaccounting-workflow)): rather than refactor this method, Installments relies on a narrower, already-sufficient guarantee — stage Installments' own rows *before calling* `reallocate_payment()`/`cancel_payment()` at all, so they are swept into that call's *first* internal commit; no Accounting-side code change is required for reversal/cancellation. | `services/payment_service.py:877-961` |
| **[Final correction pass] `cancel_payment()`'s exact commit point** | Re-read in full (`payment_service.py:969-1032`): builds/flushes the `payment.status="CANCELLED"` change and the credit-transaction soft-delete via `self.db.add(...)` + one `self.db.flush()` (line 1015), then either `self._engine.reverse(...)` (its own commit) or a bare `self.db.commit()` (line 1024) if there was no GL entry to reverse. Exactly **one** commit point, no loop — simpler than `reallocate_payment()`, but note it can only be called on a payment with **zero active allocations** (`credit_transaction.outstanding_amount != -payment.amount_base` raises `PaymentCancellationNotAllowedError` otherwise, line ~992) — so for an allocated Installments collection, `reallocate_payment(new_allocation_lines=[])` must run *first* to un-allocate it before `cancel_payment()` can run at all. | `services/payment_service.py:969-1032` |
| **[Final correction pass] `confirm_write_off()`'s exact commit points — three separate commits, the same bug class the first correction pass fixed in `adjust_receivable()`, never fixed here** | Re-read in full (`ar_service.py:734-807`): calls `self._engine.post_direct(...)` (line ~763) — which commits **immediately** (per [§2](#2-repository-findings)'s `post_direct()` finding: it's `stage_direct_posting()`+`finalize_and_publish()` bundled). **Only after that commit returns** does the method set `transaction.status = WRITTEN_OFF`/`outstanding_amount = 0`, record audit, then call `self._transactions.update(transaction)` — confirmed via `core/repositories/base.py:92-106` that `BaseRepository.update()` **itself commits** (line 106) — a **second** commit, then `self._recompute_ledger_balance(...)` → `self._ledgers.update(ledger)` — **another** `BaseRepository.update()` call, a **third** commit. This is exactly the atomicity defect the first correction pass found and fixed in `adjust_receivable()`, confirmed present and never fixed in `confirm_write_off()`. | `services/ar_service.py:734-807`, `core/repositories/base.py:92-106` |
| Idempotency | **No reusable idempotency-key infrastructure exists anywhere in the backend.** The one analogous case (`RecurringJournalService`) uses an app-level existence pre-check plus a DB unique constraint on a *business key* — not a client-supplied idempotency token, and its actual race backstop is an uncaught `IntegrityError` (not gracefully handled). Installments must build its own primitive (see [§20](#20-idempotency-strategy)). | `services/recurring_journal_service.py`, cross-cutting research §7 |
| **[Correction pass] Conflict-handling precedent** | **Zero use of `INSERT...ON CONFLICT` or `postgresql.insert()` exists anywhere in application code** (only inside raw-SQL Alembic migrations, e.g. `056_crm_permission_backfill.py`). **Zero use of `session.begin_nested()`/`SAVEPOINT` exists anywhere in application code** — the only occurrence in the entire backend is `tests/conftest.py`'s test-isolation fixture, not a production pattern. The dominant production convention is "check-then-create" (an explicit existence pre-check before insert, e.g. `platform_administrator_service.py:80-86`), which the codebase's own docstring explains is deliberate specifically *to avoid* a raw `IntegrityError` surfacing mid-request. | cross-cutting grep across `modules/`, `core/`; `tests/conftest.py:189` |
| **[Correction pass] Permission backfill precedent** | `RoleSeedService` seeds `INITIAL_PERMISSIONS`/`DEFAULT_ROLE_PERMISSIONS` (read from `users_roles/constants.py`) **only at company-creation time**. Existing companies do **not** retroactively receive permission codes added to `constants.py` after they were created — this is exactly why `056_crm_permission_backfill.py` exists (CRM shipped, then had to backfill its 19 new permission codes onto every pre-existing company's system roles). That migration is pure `op.execute()` SQL (no app-code import, matching every migration in the repo), idempotent via `ON CONFLICT DO NOTHING` on `permissions.id` and `role_permissions`' unique constraint, scoped to `role.is_system = true` — custom (non-system) roles are **never** touched by the backfill, and two of the eight system roles (`cashier`, `store-keeper`) received **zero** CRM grants because CRM has no relevance to those roles. | `migrations/versions/056_crm_permission_backfill.py:1-40` |
| Concurrency | No optimistic version-column pattern is platform-universal. Two competing conventions exist: `SELECT...FOR UPDATE` on aggregate/sequence rows (Accounting, sequence services), and a `version` int column with **conditional `UPDATE...WHERE version=expected`** (Inventory's `adjustment_repository.py` — the stronger of two sibling conventions; Sales uses a weaker load-mutate-commit variant). | cross-cutting research §8 |
| One-row-per-key invariant precedent | `Subscription` already uses a **Postgres partial unique index** — `uq_subscriptions_company_active ON subscriptions(company_id) WHERE status='active'` — to enforce "at most one active row per key" at the DB level. This is the exact mechanism the one-contract-per-obligation rule needs. | `migrations/versions/058_platform_plans_entitlements.py:202-208` |
| Maker-checker | `SelfApprovalNotAllowedError`, enforced in the **service layer** (not router), comparing `created_by` vs. approver. The codebase has a documented history of forgetting to apply the same check to the "opposite" action (reject vs. approve) — both `PostingEngine.reject()` and `PaymentService.reject_payment()` needed a hardening retrofit. | `posting_engine.py:353-420`, `payment_service.py:611-843` |
| Audit | Two per-module shapes exist: CRM's minimal `CrmAuditLog` (`TenantBaseModel`, no reason/session_context) and Accounting's richer `AccountingAuditLog` (plain `Base` + explicit `company_id`, adds `reason` + `session_context` + `occurred_at`). Both are staged via `flush()` only; the caller's single `db.commit()` makes the audit write atomic with the business mutation (fail-closed by construction). | `modules/crm/models/audit.py`, `modules/accounting/models/gl.py:285-322`, `services/audit_service.py` |
| Entitlement | `Capability(grain='module'|'feature')` + `Plan` + `PlanCapability` + `Subscription` + `EntitlementOverride`, resolved by `PlatformEntitlementService.resolve_effective_entitlement()` with precedence **Override → Plan ceiling → Tenant Toggle** (falls back to toggle alone if no active Subscription exists, for backward compatibility). `ModuleEnablementProvider` is a `Protocol` with a `CrmModuleEnablementProvider` and a `DefaultAlwaysEnabledModuleProvider`, selected by a factory keyed on `capability_key`. | `modules/platform_admin/services/entitlement_service.py`, `module_enablement.py` |
| CRM's module gate is a *blunt* instrument | `require_crm_enabled` is mounted as a **router-level** dependency — it blocks the *entire* CRM router when disabled. This cannot express Installments' origination-vs-servicing split (FR-INST-353–358) and must **not** be copied as-is. | `modules/crm/dependencies.py:273-284`, `api/v1/router.py:165-181` |
| Support-access boundary | Structural, not a query filter: Platform Admin's `TenantDirectoryService` imports zero business-module repositories — a statically-provable guarantee, not a runtime check. As long as Installments' tenant routes only mount under `get_current_company_member` and no Platform Admin service imports Installments repositories, the same boundary holds automatically. | `modules/platform_admin/services/tenant_directory_service.py:11-14` |
| Tenant suspension | Enforced once, globally, inside `get_current_company_member` (`assert_company_access_allowed`) — upstream of and independent from any module-specific entitlement check. Modules must **not** duplicate this check. | `modules/platform_admin/services/company_access_service.py:36-72` |
| RBAC pattern | Dot-notation permission codes declared in each module's `constants.py`; checked via a free function `user_has_<module>_permission()` called **inline inside the route/service body** — not a FastAPI dependency or decorator. | `modules/accounting/services/permission_check.py`, cross-cutting research §1 |
| Domain events | **Two incompatible mechanisms coexist.** An in-process, non-durable `EventBus` (used by inventory/purchase/sales/accounting/crm — events are lost on restart, never persisted) and a **transactional outbox** (`core/events/outbox.py`, used by `companies`/`users_roles`) that is the *only* mechanism actually satisfying Constitution §49 ("events MUST be published within the same DB transaction... outbox pattern or equivalent"). | cross-cutting research §6 |
| Module structure | Every module: `constants.py`, `dependencies.py`, `exceptions.py`, `router.py`, `events/`, (`handlers/` where needed), `models/`, `repositories/`, `schemas/`, `services/`. No `api/`, `permissions/`, or `validators/` subfolders anywhere — despite Constitution §12's diagram, this is the actual, consistent convention across five modules. Tests live centrally under `backend/tests/{unit,integration,security,performance}/**/<module>/`, not inside the module. | all module inspections |
| Sales boundary | `SalesInvoice` carries **no `outstanding_amount`/`paid_amount`** — that is Accounting's `ARTransaction`. No ORM `relationship()` exists anywhere in Sales (plain FK-id columns, manual joins). `InvoiceCreditNoteIssued`/`InvoiceCancelled` are published on Sales' in-process bus — the correct subscription point for Installments to detect post-activation invoice correction. | `modules/sales/models/invoice.py`, `services/invoice_service.py` |
| Customer ownership | CRM has **no Customer model of its own** — it imports Sales' `Customer` directly. `Customer360Service` is the precedent for cross-module, read-only, no-N+1 composition (Sales + CRM + Accounting) without duplicating ownership. | `modules/crm/services/customer_360_service.py` |
| Branch scoping | **No `branch_id` column exists anywhere** — not in Sales, not in `TenantBaseModel`, not in any inspected module. Constitution §10 only requires readiness, not an implemented Branch entity. | cross-cutting research §9, Sales research §5 |
| Frontend routing | Routes are **flat**, not `/companies/{companyId}/...`-nested — the active company is resolved client-side from `localStorage`. TanStack Query is the modern convention (Companies/Users-Roles/Platform-Admin); CRM/Accounting/Sales still use manual `useEffect` fetches (legacy, not to be copied for a new module). | frontend research §1–2 |
| Frontend detail-page pattern | Stacked bordered `<section>` cards with `LoadingState`/`EmptyState`/`ErrorState`/`PermissionDeniedState` from `platform-admin/DataState.tsx` — **no `Tabs` component exists in the design system.** | frontend research §3 |
| Frontend entitlement banner | CRM's exact 3-file pattern (`apiErrors.ts` classifying `403 FEATURE_DISABLED`, a `*StateBanner.tsx`) is the precedent to replicate. | frontend research §5 |

---

## 3. Constitution Compliance

| Constitution Section | Compliance Design |
|---|---|
| §5 Modular Monolith | Installments is one more module inside the existing monolith; no microservice, no new deployable, no new database. |
| §9 Multi-Tenant Principles | Every table inherits `TenantBaseModel`; every repository method takes `company_id`; every route sits behind `get_current_company_member`. |
| §10 Multi-Branch Readiness | `branch_id: UUID | None` reserved on `InstallmentContract`/`InstallmentCollection`/`InstallmentConfiguration` (nullable, unenforced FK since no platform `Branch` entity exists yet) — ready, not over-built. |
| §11 Feature Toggles | `InstallmentsFeatureFlag` (`feature.installments.enabled`) mirrors CRM's flag exactly, but the *route gating* deliberately does not mirror CRM's blunt router-level cutoff — see [§15](#15-entitlement-architecture) and ADR-INST-06. |
| §12 Module Design | Standard vertical slice: `constants.py, dependencies.py, exceptions.py, router.py, events/, models/, repositories/, schemas/, services/` — matching the *actual* convention, not the Constitution diagram's `api/`/`permissions/`/`validators/` folders (which no existing module uses either). |
| §13/§14/§15 Repository/Service/API layering | Repositories: DB access only, `company_id`-scoped. Services: all business logic, no HTTP imports. API: thin controllers (validate → authN → authZ → call service → return schema). |
| §16 AuthN/AuthZ | Every endpoint requires `require_authenticated` + `get_current_company_member`; every mutating action separately checks a permission code via `user_has_installments_permission()`. |
| §17 Database Principles / Money Handling | `NUMERIC(20,6)` for all amounts (Accounting-compatible, per spec Assumption A4), `Decimal` in Python, currency code stored alongside every amount, explicit `ROUND_HALF_UP` quantization documented in [§8](#8-money--precision-strategy). Soft-delete (`is_deleted`/`deleted_at`) on all mutable tables; append-only tables (`InstallmentAuditLog`, `InstallmentScheduleLine`) have no delete path at all. |
| §18 Migration Policy | Additive-only migrations, sequential numbering from `062`, every migration has a working `downgrade()`. |
| §19 Security Principles | OWASP-aligned: parameterized ORM queries only, RBAC on every protected endpoint, no internal error detail leaked, least-privilege permission codes. |
| §21 Error Handling | Reuses `core/exceptions/base.py` hierarchy (`NotFoundException`, `ConflictException`, `ForbiddenException`, `ValidationException`) — no new exception base class. |
| §22 Logging | `logger.info("Installment contract activated", extra={"company_id":..., "contract_id":...})` pattern, ambient `request_id`/`user_id` via existing `ContextVar`s. |
| §25 Performance | No N+1 patterns; pagination via existing `PaginatedResponse`/`PaginationParams`. |
| §35 Audit Trail | `InstallmentAuditLog` follows Accounting's richer shape (adds `reason`, `session_context`) since Installments actions are financially sensitive and frequently require a mandatory reason. |
| §37 SaaS Readiness | Installments plugs into the existing `Capability`/`Plan`/`Subscription`/`EntitlementOverride` model — no parallel entitlement system. |
| §46 Business Configuration Philosophy | `InstallmentConfiguration` is the tenant-configurable policy row; nothing about frequencies, terms, grace periods, or thresholds is hardcoded. |
| §48 Shared Kernel | No competing `Money` type is introduced; Installments uses the same bare `Decimal`+`currency_code` convention every other module already uses (the Shared Kernel's `Money` value object does not actually exist in the repository despite being named in the Constitution — noted as a pre-existing gap, not one Installments should silently "fix" by inventing its own version). |
| §49 Event-Driven Communication | Installments uses the **transactional outbox** (`core/events/outbox.py`), the only mechanism in the repository that satisfies this section's "same DB transaction" requirement — a deliberate deviation from sibling modules' non-compliant in-process bus (see ADR-INST-09). |
| §50 Platform Administration | Platform Admin governs only the `installments` Capability/entitlement; Installments never grants Platform Admin business-record access; `SupportAccessGrant`'s exclusion holds structurally (Installments is never imported by `platform_admin`). |

**Gate evaluation**: No unjustified violations. The one deliberate deviation (outbox over in-process bus) is documented as ADR-INST-09 and is a *stricter* compliance choice, not a relaxation.

---

## 4. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         DEVSPHERE ERP — MODULAR MONOLITH                 │
│                                                                          │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐   ┌──────────────────┐ │
│  │  Sales   │   │   CRM    │   │ Installments │   │    Accounting     │ │
│  │ (owns    │   │ (owns    │   │  (NEW —      │   │ (owns financial   │ │
│  │ invoice, │◄──┤ activity/│──►│  owns        │──►│  truth: Payment,  │ │
│  │ customer,│   │  note    │   │  contract,   │   │  AR, GL, fiscal   │ │
│  │ order)   │   │ context) │   │  schedule,   │   │  periods)         │ │
│  │          │   │          │   │  collection  │   │                   │ │
│  │          │   │          │   │  orchestr.)  │   │                   │ │
│  └────┬─────┘   └────┬─────┘   └──────┬───────┘   └─────────┬─────────┘ │
│       │              │                │                     │           │
│       │        reads Sales'    references Sales      calls PostingEngine│
│       │        Customer via    invoice_id (no FK      /  AR service via │
│       │        direct import   duplication)            stage_direct_/   │
│       │                        subscribes to           finalize_and_    │
│       │                        Sales' InvoiceCredit-    publish(); never │
│       │                        NoteIssued/Cancelled     writes GL/AR    │
│       │                        events                   tables directly │
│  ─────┴──────────────┴────────────────┴─────────────────────┴────────── │
│                          Shared Platform Layer                           │
│         (core/auth, core/database, core/events/outbox, core/logging,    │
│          core/exceptions, core/repositories/base)                       │
│  ────────────────────────────────────────────────────────────────────── │
│              platform_admin (Capability/Plan/Subscription/              │
│              EntitlementOverride/SupportAccessGrant — governs            │
│              Installments' entitlement only, never its data)            │
│  ────────────────────────────────────────────────────────────────────── │
│                          PostgreSQL 16 (single DB)                      │
└──────────────────────────────────────────────────────────────────────────┘
```

Installments is a **new vertical slice**, not a new architectural layer. It calls Accounting through Accounting's existing public service interfaces (`PostingEngine`, `AccountsReceivableService`, `AllocationEngine`) exactly as `PaymentService` itself does internally — never through direct table writes. It calls Sales only through read-only repository lookups (`SalesInvoiceRepository.get_by_id_or_none`) and subscribes to Sales' domain events — never writes to Sales tables.

---

## 5. Domain Boundary

Per spec §7, restated as an implementation contract:

| Concern | Owner | Installments' relationship to it |
|---|---|---|
| Sale/invoice lifecycle, immutability, credit notes | **Sales** (`modules/sales`) | Read-only reference by `sales_invoice_id`; subscribes to `InvoiceCreditNoteIssued`/`InvoiceCancelled` |
| Customer master, credit limit, credit status | **Sales** (`Customer` model — CRM has none of its own) | Read-only reference by `customer_id`; never writes `customers` table |
| GL, AR, payments, allocations, fiscal periods, write-off posting | **Accounting** (`modules/accounting`) | Calls `PostingEngine`/`AccountsReceivableService`/`AllocationEngine` through their public service methods; never touches `accounting_*` tables directly |
| CRM activities/notes, Customer 360 | **CRM** (`modules/crm`) | Installments exposes a read-only summary service method CRM's `Customer360Service` can import directly (mirrors how that service already imports Accounting's `AccountsReceivableService`); Installments does not write CRM's `crm_activities` table itself, but MAY create activity rows through CRM's own service interface where the tenant uses CRM notes (FR-INST-291, "SHOULD") |
| Inventory / stock movement | **Inventory** (`modules/inventory`) | No interaction whatsoever — FR-INST-280/281 forbid any stock effect from Installments |
| Installment contract, terms snapshot, schedule, due-state, collection orchestration, delinquency, settlement business logic | **Installments** (new) | Owns everything else |

**Explicit non-duplication enforcement points** (mapping BR-INST-004 to code):
- No `installment_payments` table exists — collections write to Accounting's `Payment`/`ARTransaction` via `PostingEngine`.
- No `installment_journal_entries` table exists.
- `InstallmentContract` stores no `customer_name`/`customer_email` — only `customer_id` (FK, RESTRICT).
- `InstallmentContract` stores a **terms snapshot**, not a live foreign key to `InstallmentPlanTemplate` fields — template edits never retroactively change a contract (FR-INST-012).

---

## 6. Domain Model

```
InstallmentConfiguration  (1 per company, optional branch override)
        │  (referenced by, snapshotted into)
        ▼
InstallmentPlanTemplate  (0..N per company)
        │  (optionally referenced by, always snapshotted into)
        ▼
InstallmentContract  ── AGGREGATE ROOT ──────────────────────────┐
   │  references (no FK duplication): company_id, branch_id?,    │
   │    customer_id (→ sales.customers), sales_invoice_id         │
   │    (→ sales.sales_invoices), plan_template_id? (→ above)     │
   │  owns: terms snapshot (JSONB + typed columns), status,        │
   │    contract_number (tenant-scoped sequence)                   │
   │                                                                 │
   ├──1:N──► InstallmentScheduleVersion (immutable per version)     │
   │             │                                                   │
   │             └──1:N──► InstallmentScheduleLine (immutable)       │
   │                            │                                     │
   │                            └──1:N──► InstallmentAllocationReference
   │                                          (points to Accounting's │
   │                                           Payment + PaymentAllocationLine
   │                                           — reference/explanation only)
   │
   ├──1:N──► InstallmentLateCharge (optional, policy-gated)
   ├──1:N──► InstallmentAuditLog
   └──1:N──► InstallmentIdempotencyKey (scoped by contract_id where applicable)

InstallmentsFeatureFlag  (1 per company — module master toggle, CRM precedent)
InstallmentSequence      (contract-number generator, per company)
```

### Entity summary

| Entity | Purpose | Mutability |
|---|---|---|
| `InstallmentConfiguration` | Company-level (+ optional branch override) policy: frequencies, min/max term, down-payment rule, grace period, late-charge policy, early-settlement policy, approval thresholds, backdating/cancellation rules, default/write-off/cure policy. | Mutable; changes never retroactively affect existing contracts (BR-INST-009) because contracts snapshot terms, not reference config live. |
| `InstallmentPlanTemplate` | Reusable named commercial plan (e.g. "6 Monthly, 0% Markup"). | Mutable/deactivatable; edits never mutate contracts already created from it (FR-INST-012). |
| `InstallmentContract` | Aggregate root — the installment agreement. | Terms snapshot immutable once `ACTIVE`+ (BR-INST-008); status transitions only through named service methods (no `set_status`). |
| `InstallmentScheduleVersion` | One version of the payment schedule; `version_number` monotonically increasing per contract. | **Immutable once created.** Rescheduling creates a new version; never edits an existing one (BR-INST-017, FR-INST-201). |
| `InstallmentScheduleLine` | One contractual due obligation within a schedule version. | **Immutable** (`sequence`, `due_date`, `scheduled_amount` never change post-creation). Two narrow, explicit, audited exceptions: `waived_at`/`waived_reason` and `voided_at`/`voided_reason` columns for the controlled WAIVED/CANCELLED due-states — everything else (UPCOMING/DUE/PARTIALLY_PAID/PAID/OVERDUE) is derived at read time. |
| `InstallmentAllocationReference` | Explains which Accounting `Payment`/`PaymentAllocationLine` satisfied how much of which `InstallmentScheduleLine`. | Append-only; a reversal creates a new reference row, never edits/deletes the original (BR-INST-017, FR-INST-242). |
| `InstallmentLateCharge` | One occurrence of a policy-driven late charge on one overdue schedule line. | Append-only + a `waived_at`/`waived_by`/`waived_reason` triple for the controlled waiver action. |
| `InstallmentAuditLog` | Append-only audit trail for every privileged Installments mutation. | Append-only; no update/delete method exists. |
| `InstallmentsFeatureFlag` | Tenant module master toggle (`feature.installments.enabled`), CRM precedent. | Mutable (enable/disable). |
| `InstallmentSequence` | Tenant-scoped contract-number generator (`IC-YYYY-NNNNNN`). | Mutated only via locked increment. |
| `InstallmentIdempotencyKey` | New primitive (no existing platform equivalent) — see [§20](#20-idempotency-strategy). | **[CORRECTED]** `IN_PROGRESS → COMPLETED`, then immutable — no persisted `FAILED` state; a failed business operation rolls back the entire transaction, including this row, so the key simply becomes available again for retry. |

Every entity above inherits `TenantBaseModel` (UUID PK server-generated, `company_id`, `created_at`/`updated_at`, `created_by`, `is_deleted`/`deleted_at`) **except**: `InstallmentScheduleLine`, `InstallmentAllocationReference`, and `InstallmentAuditLog`, which follow the platform's documented append-only exception (plain `Base` + explicit `company_id`, no `updated_at`/soft-delete — matching `JournalLine` and `AccountingAuditLog`).

---

## 7. Database / Persistence Design

### 7.1 Tables (conceptual — no migration code, per stop condition)

| Table | Key columns (beyond `TenantBaseModel`/`Base` defaults) |
|---|---|
| `installment_configurations` | `branch_id UUID NULL`, `allowed_frequencies JSONB`, `min_term INT`, `max_term INT`, `min_down_payment_pct NUMERIC(5,2) NULL`, `min_down_payment_amount NUMERIC(20,6) NULL`, `max_financed_amount NUMERIC(20,6) NULL`, `rounding_policy VARCHAR(20)`, `grace_period_days INT DEFAULT 0`, `late_charge_policy JSONB NULL`, `early_settlement_policy JSONB NULL`, `approval_threshold_amount NUMERIC(20,6) NULL`, `backdating_allowed BOOLEAN DEFAULT false`, `backdating_max_days INT NULL`, `cancellation_policy JSONB NULL`, `default_policy JSONB NULL`, `writeoff_requires_permission BOOLEAN DEFAULT true`, `cure_enabled BOOLEAN DEFAULT false`, `eligibility_rules JSONB NULL`. Unique `(company_id, branch_id)` where `branch_id IS NOT NULL`; unique `(company_id) WHERE branch_id IS NULL` (one company-level row). |
| `installment_plan_templates` | `name VARCHAR(150)`, `description TEXT NULL`, `is_active BOOLEAN`, `frequency VARCHAR(20)`, `installment_count INT`, `down_payment_rule JSONB`, `markup_rule JSONB NULL`, `grace_period_days INT NULL`, `late_charge_policy JSONB NULL`, `early_settlement_rule JSONB NULL`, `applicable_product_ids JSONB NULL`, `requires_approval BOOLEAN`. Unique `(company_id, name) WHERE is_deleted = false`. |
| `installment_contracts` | `contract_number VARCHAR(30)`, `branch_id UUID NULL`, `customer_id UUID NOT NULL` (no FK — cross-module reference, Accounting's `party_id` convention), `sales_invoice_id UUID NOT NULL` (no FK, same convention), `plan_template_id UUID NULL` (FK RESTRICT — informational lineage only, never dereferenced for financial truth), `contract_date DATE`, `principal_amount NUMERIC(20,6)`, `down_payment_amount NUMERIC(20,6)`, `markup_amount NUMERIC(20,6) DEFAULT 0`, `contractual_total NUMERIC(20,6)`, `installment_count INT`, `frequency VARCHAR(20)`, `first_due_date DATE`, `maturity_date DATE`, `currency_code VARCHAR(3)`, `status VARCHAR(20)`, `terms_snapshot JSONB NOT NULL`, `active_schedule_version_id UUID NULL` (FK to `installment_schedule_versions`, RESTRICT), `submitted_by UUID NULL`, `submitted_at TIMESTAMPTZ NULL`, `approved_by UUID NULL`, `approved_at TIMESTAMPTZ NULL`, `activated_at TIMESTAMPTZ NULL`, `closed_at TIMESTAMPTZ NULL`, `defaulted_at TIMESTAMPTZ NULL`, `cancelled_at TIMESTAMPTZ NULL`, `written_off_at TIMESTAMPTZ NULL`, `version INT NOT NULL DEFAULT 1` (optimistic concurrency, [§19](#19-concurrency-strategy)). |
| `installment_schedule_versions` | `contract_id UUID NOT NULL` (FK RESTRICT), `version_number INT`, `status VARCHAR(20)` (`DRAFT`\|`ACTIVE`\|`SUPERSEDED`), `generated_at TIMESTAMPTZ`, `generated_by UUID NULL`, `reason TEXT NULL` (mandatory for versions > 1). Unique `(contract_id, version_number)`. |
| `installment_schedule_lines` (append-only, plain `Base`) | `schedule_version_id UUID NOT NULL` (FK RESTRICT), `company_id UUID NOT NULL` (explicit — no `TenantBaseModel`), `sequence INT`, `due_date DATE`, `scheduled_amount NUMERIC(20,6)`, `waived_at TIMESTAMPTZ NULL`, `waived_by UUID NULL`, `waived_reason TEXT NULL`, `voided_at TIMESTAMPTZ NULL`, `voided_by UUID NULL`, `voided_reason TEXT NULL`. Unique `(schedule_version_id, sequence)`. |
| `installment_allocation_references` (append-only, plain `Base`) | `company_id UUID NOT NULL`, `contract_id UUID NOT NULL` (FK RESTRICT), `schedule_line_id UUID NOT NULL` (FK RESTRICT), `accounting_payment_id UUID NOT NULL` (no FK — cross-module reference), `accounting_payment_allocation_line_id UUID NOT NULL` (no FK), `allocated_amount NUMERIC(20,6)`, `allocation_order INT`, `is_reversal BOOLEAN DEFAULT false`, `reverses_allocation_reference_id UUID NULL` (self-FK RESTRICT), `allocated_at TIMESTAMPTZ`. |
| `installment_late_charges` | `contract_id UUID NOT NULL` (FK RESTRICT), `schedule_line_id UUID NOT NULL` (FK RESTRICT), `charge_amount NUMERIC(20,6)`, `charged_at TIMESTAMPTZ`, `overdue_occurrence_date DATE` (the specific due date this charge is for — unique per line to prevent double-charging), `accounting_journal_entry_id UUID NULL` (no FK), `accounting_ar_transaction_id UUID NULL` (no FK — cross-module reference to the `DEBIT_NOTE`-type `ARTransaction` created for this charge; **[corrected]** see [§12](#12-accounting-integration), previously missing — without it the charge could never be linked back to the AR row that makes it collectible/reversible), `waived_at TIMESTAMPTZ NULL`, `waived_by UUID NULL`, `waived_reason TEXT NULL`. Unique `(schedule_line_id, overdue_occurrence_date)`. |
| `installment_audit_log` (append-only, plain `Base`) | `company_id UUID NOT NULL`, `entity_type VARCHAR(50)`, `entity_id UUID`, `action VARCHAR(50)`, `actor_user_id UUID NULL`, `occurred_at TIMESTAMPTZ`, `before_state JSONB NULL`, `after_state JSONB NULL`, `session_context JSONB NULL`, `reason TEXT NULL`. |
| `installments_feature_flags` | `flag_key VARCHAR(50) DEFAULT 'feature.installments.enabled'`, `is_enabled BOOLEAN DEFAULT false`. Unique `(company_id, flag_key)`. |
| `installment_sequences` | `document_type VARCHAR(10) CHECK IN ('IC')`, `prefix VARCHAR(10)`, `current_value INT`, `year INT`, `reset_yearly BOOLEAN`, `format_pattern VARCHAR(30)`. Unique `(company_id, document_type, year)`. |
| `installment_idempotency_keys` | See [§20](#20-idempotency-strategy) for full schema. |

### 7.2 Constraints (explicit identification per meta-§28)

| Constraint | Type | Purpose |
|---|---|---|
| `uq_installment_contracts_company_number` | Unique | `(company_id, contract_number)` — tenant-scoped numbering |
| `uq_installment_contracts_one_nonterminal_per_obligation` | **Partial unique index** | `ON installment_contracts (company_id, sales_invoice_id) WHERE status NOT IN ('CANCELLED','COMPLETED','WRITTEN_OFF')` — the DB-level enforcement of the one-contract-per-obligation rule (mirrors `uq_subscriptions_company_active`, see [§2](#2-repository-findings)) |
| `uq_installment_schedule_versions_contract_number` | Unique | `(contract_id, version_number)` |
| `uq_installment_schedule_lines_version_sequence` | Unique | `(schedule_version_id, sequence)` |
| `uq_installment_late_charges_line_occurrence` | Unique | `(schedule_line_id, overdue_occurrence_date)` — prevents double-charging the same overdue occurrence (FR-INST-171) |
| `uq_installments_feature_flags_company_key` | Unique | `(company_id, flag_key)` |
| `uq_installment_sequences_company_type_year` | Unique | `(company_id, document_type, year)` |
| `uq_installment_idempotency_company_op_key` | Unique | `(company_id, operation, idempotency_key)` |
| `ck_installment_contracts_status` | Check | `status IN ('DRAFT','PENDING_APPROVAL','APPROVED','ACTIVE','DEFAULTED','COMPLETED','CANCELLED','WRITTEN_OFF')` — **no `REJECTED`** |
| `ck_installment_contracts_positive_amounts` | Check | `principal_amount >= 0 AND contractual_total >= 0 AND installment_count > 0` |
| `ck_installment_schedule_versions_status` | Check | `status IN ('DRAFT','ACTIVE','SUPERSEDED')` |
| `ck_installment_schedule_lines_positive_amount` | Check | `scheduled_amount > 0` |
| FKs on all `*_id` columns pointing **within** Installments (`schedule_version_id`, `schedule_line_id`, `plan_template_id`, `contract_id`) | `ON DELETE RESTRICT` | Matches platform convention — financial/history rows are never cascade-deleted |
| No FK on `customer_id`, `sales_invoice_id`, `branch_id`, `accounting_payment_id`, `accounting_payment_allocation_line_id`, `journal_entry_id` | — | Cross-module references follow the established `party_id`/`source_document_id` convention (no FK across module boundaries) |

**Nullable decisions**: `branch_id` nullable everywhere (no Branch entity yet); `plan_template_id` nullable (custom-terms contracts allowed per FR-INST-011); `active_schedule_version_id` nullable only while `status = DRAFT`/`PENDING_APPROVAL` (no schedule exists yet).

**No unsafe cascades**: every FK is `RESTRICT`. Soft-delete (`is_deleted`) is the only "removal" path for mutable rows; append-only rows have no removal path at all.

---

## 8. Money & Precision Strategy

Resolves spec Assumption A4 and BR-INST-018 into concrete types:

| Layer | Type | Notes |
|---|---|---|
| PostgreSQL | `NUMERIC(20,6)` for amounts, `NUMERIC(5,2)` for percentages (down-payment %, markup %), `NUMERIC(20,10)` if any FX-adjacent field is ever needed (not required by spec — Installments introduces no new multi-currency behavior per FR-INST-253) | Matches Accounting exactly, not Sales — per spec Assumption A4, since installment schedules settle against AR |
| Python | `decimal.Decimal` everywhere; **never `float`** | No shared `Money` value object exists in the repository (Constitution §48's Shared Kernel is aspirational, not implemented) — Installments follows the same bare-`Decimal`-plus-`currency_code` convention as every other module, rather than inventing a new one |
| Pydantic v2 | Plain `Decimal` fields with `Field(gt=0)`/`Field(ge=0)` constraints, matching `schemas/payments.py`'s convention | No custom `Money` validator exists to reuse |
| Calculation precision | All intermediate schedule math performed at full `Decimal` precision (no premature rounding), quantized to `Decimal("0.000001")` (6 dp) only when writing to a schedule line or contract total field | Matches Accounting's own `_AMOUNT_QUANT = Decimal("0.000001")` convention (`currency_revaluation_service.py`) |
| Rounding | `ROUND_HALF_UP`, applied via `.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)` — tenant-configurable only via `InstallmentConfiguration.rounding_policy` if a tenant needs `ROUND_HALF_EVEN` (mirrors Accounting's `RoundingRule` enum in `tax_calculator.py`, reused conceptually, not imported cross-module) | Explicit, documented, never implicit float rounding (Constitution §17) |
| Presentation precision | 2 decimal places for currency display, matching every other module's UI convention — a formatting concern at the API/schema boundary, not a storage concern | |
| **Final-installment residual** | `sum(all lines except last) = round(contractual_total / installment_count, 6) × (installment_count - 1)`; `last_line_amount = contractual_total - sum(all other lines)`, computed by subtraction (never independently rounded) | Guarantees BR-INST-005 (`sum(schedule) == contract.contractual_total`) **exactly**, deterministically, every time — this is the schedule engine's core invariant, detailed in [§10](#10-schedule-engine) |
| Reconciliation check | `InstallmentContract.activate()` validates `sum(schedule_lines.scheduled_amount) == contractual_total` before allowing `APPROVED → ACTIVE` (FR-INST-113); a mismatch raises a domain exception and blocks activation — never silently rounds again |

---

## 9. Installment Lifecycle Architecture

### 9.1 State machine (persisted `status` column — no `REJECTED` state, per spec §11.1)

```
DRAFT ──submit()──► PENDING_APPROVAL ──approve()──► APPROVED ──activate()──► ACTIVE
  ▲                        │                                                    │
  │                    reject()                                          ┌──────┼──────┬─────────────┐
  └────────────────────────┘                                       cancel()  default() (payoff)   (payoff)
                                                                          │        │                   │
                                                                          ▼        ▼                   ▼
                                                                    CANCELLED  DEFAULTED ───cure()──► ACTIVE
                                                                                    │
                                                                          ┌─────────┼─────────┐
                                                                     writeoff()   (payoff)   (payoff)
                                                                          ▼           ▼
                                                                    WRITTEN_OFF   COMPLETED
```

Also: `DRAFT → CANCELLED`, `PENDING_APPROVAL → CANCELLED`, `APPROVED → CANCELLED` (pre-activation cancellation, FR-INST-210); `ACTIVE → COMPLETED` (ordinary payoff or early settlement).

### 9.2 Implementation pattern: explicit named service methods, no generic `set_status`

Following FR-INST-106 and the platform's own established pattern (`SalesOrder`'s `_TRANSITIONS` dict + `_assert_invoice_transition()` guard in `invoice_service.py`), `InstallmentContractService` implements:

```python
_LEGAL_TRANSITIONS: dict[str, frozenset[str]] = {
    "DRAFT": frozenset({"PENDING_APPROVAL", "APPROVED", "CANCELLED"}),  # direct→APPROVED when no approval required (FR-INST-101)
    "PENDING_APPROVAL": frozenset({"APPROVED", "DRAFT", "CANCELLED"}),   # DRAFT = reject outcome
    "APPROVED": frozenset({"ACTIVE", "CANCELLED"}),
    "ACTIVE": frozenset({"COMPLETED", "CANCELLED", "DEFAULTED"}),
    "DEFAULTED": frozenset({"ACTIVE", "COMPLETED", "WRITTEN_OFF"}),      # ACTIVE = cure
    "COMPLETED": frozenset(),      # terminal
    "CANCELLED": frozenset(),      # terminal
    "WRITTEN_OFF": frozenset(),    # terminal
}
```
One method per **named business action** — `submit()`, `approve()`, `reject(reason)`, `activate()`, `cancel(reason)`, `mark_defaulted(reason)`, `cure(reason?)`, `complete()` (internal, invoked by the collection/settlement path when outstanding reaches zero — FR-INST-104), `writeoff(reason)` — each internally asserts `new_status in _LEGAL_TRANSITIONS[current_status]` before mutating, exactly mirroring `_assert_invoice_transition()`. There is **no** `update_status(new_status: str)` method anywhere in the public service interface — satisfying FR-INST-106 by construction, not by convention alone.

**`REJECTED` handling** (FR-INST-102, §11.1's note): `reject(contract_id, reason, actor_id)` is a distinct method from `approve()`, requires the same distinct-approver check ([§16.2](#162-maker-checker-implementation)), writes an `InstallmentAuditLog` row with `action="REJECTED"`, and transitions `status: PENDING_APPROVAL → DRAFT`. The rejection event is permanently visible in `installment_audit_log`; nothing about it is destroyed on resubmission.

**Cure vs. direct completion** (FR-INST-104/105/222, §15.4 of spec): `DEFAULTED → ACTIVE` (`cure()`) and `DEFAULTED → COMPLETED` (`complete()`, invoked automatically when a collection under the servicing-continuity path brings outstanding to zero) are **two separate code paths with two separate permissions** ([§16.1](#161-permission-catalogue)) — `cure()` is never silently invoked by the collection-recording flow; `complete()` from `DEFAULTED` requires *zero* additional permission beyond ordinary collection because it's a natural consequence of authoritative payoff, not a discretionary lifecycle action.

### 9.3 [CORRECTED] Authoritative completion guard — `InstallmentOutstandingService.assert_zero_outstanding()`

The original design let `complete()` be triggered whenever `sum(schedule_line outstanding) == 0`. This is **no longer sufficient** now that a late charge can create its own, separate Accounting `ARTransaction` ([§12.1](#121-corrected-late-charge-ar-truth--repository-re-inspection-and-resolution)): a contract can reach zero *scheduled* outstanding while an open, unpaid late-charge `ARTransaction` still exists — and BR-INST-010 ("a contract cannot transition to `COMPLETED` while any authoritative outstanding obligation remains against it") makes no exception for late charges. Completing the contract in that state would let a customer's genuine outstanding balance become invisible to Installments' own lifecycle even though Accounting still correctly shows it as owed — not a duplicated-truth bug, but a **lifecycle-state-vs-truth mismatch** bug (the contract claims "done" while Accounting disagrees).

**Corrected rule**: `InstallmentContractService.complete()` (and every other code path that might transition a contract to `COMPLETED`) MUST first call a new, single, authoritative check:

```python
class InstallmentOutstandingService:
    def assert_zero_outstanding(self, company_id: UUID, contract_id: UUID) -> None:
        """Raise InstallmentOutstandingBalanceRemainsError unless every
        authoritative obligation linked to this contract is fully satisfied,
        waived, reversed, or written off. Reads Accounting directly — never
        a locally-cached/derived total."""
        schedule_outstanding = self._schedule_outstanding(company_id, contract_id)   # §10/derived, per line
        if schedule_outstanding > 0:
            raise InstallmentOutstandingBalanceRemainsError(kind="SCHEDULE")

        for charge in self._late_charge_repo.list_for_contract(company_id, contract_id):
            if charge.waived_at is not None:
                continue   # validly waived — never blocks completion
            if charge.accounting_ar_transaction_id is None:
                continue   # never actually posted (e.g. policy disabled after creation) — nothing owed
            ar_txn = self._ar_gateway.get_ar_transaction(charge.accounting_ar_transaction_id)  # live Accounting read
            if ar_txn.outstanding_amount > 0 and ar_txn.status not in ("WRITTEN_OFF",):
                raise InstallmentOutstandingBalanceRemainsError(kind="LATE_CHARGE", ar_transaction_id=ar_txn.id)
        # Extensibility: any FUTURE Installments-created Accounting receivable type
        # (none exists beyond late charges as of Epic 10) must be added as an
        # additional loop here, following the identical live-Accounting-read
        # pattern — never a locally duplicated balance.
```

This is a **read-only** check against live Accounting state (via `AccountsReceivableService`'s public read methods, e.g. a direct `ARTransaction` lookup by ID — no new write capability, no duplicated balance stored inside Installments). It does **not** replace the existing schedule-outstanding derivation ([§10](#10-schedule-engine)/[§25](#25-reporting--query-architecture)) — it *adds* the late-charge check alongside it, both gating the same single `complete()` transition.

**Applied to every completion path** (superseding the earlier, schedule-only description at each site — cross-referenced from [§11](#11-collection--allocation-architecture), [§12](#12-accounting-integration) Early Settlement row, [§21](#21-transaction--atomicity-boundaries) Collection row, and [§38](#38-requirement-traceability)'s BR-INST-010 row):

| Completion path | Guard call |
|---|---|
| Ordinary collection reaching zero schedule outstanding | `assert_zero_outstanding()` called before `complete()`; if it raises (an open late charge remains), the contract stays `ACTIVE`/`DEFAULTED` — the collection itself still succeeds and commits (the payment was real), only the *contract-level* `COMPLETED` transition is withheld |
| Early settlement execution | Same guard, called at the same point in `InstallmentSettlementService.execute()` — a settlement quote that only accounted for scheduled principal, not an open late charge, must not be allowed to silently close the contract; see [§39](#39-open-technical-decisions) for the settlement-quote scope note this implies |
| `DEFAULTED → COMPLETED` (servicing-continuity full payoff) | Same guard — a defaulted contract with a lingering unpaid late charge does not complete, it remains `DEFAULTED` (still fully serviceable per FR-INST-356) until the charge is also satisfied or waived |
| Contract detail balance / dashboard "outstanding" figure | Reads the same two sources (schedule + late-charge `ARTransaction`s) the guard checks, so the displayed balance and the completion decision can never disagree with each other |

**No duplicated Accounting balance is introduced** — `assert_zero_outstanding()` performs live reads against Accounting's own `ARTransaction.outstanding_amount`/`status` for every late charge, exactly the same authoritative source [§25](#25-reporting--query-architecture) already designates for "paid"/"outstanding" figures. This satisfies BR-INST-004 and BR-INST-010 together, not just BR-INST-010 alone.

---

## 10. Schedule Engine

### 10.1 Design: pure domain function, zero I/O

```
ScheduleEngine.generate(
    principal: Decimal, down_payment: Decimal, markup: Decimal,
    installment_count: int, frequency: Frequency, first_due_date: date,
    rounding_policy: RoundingPolicy,
) -> ScheduleGenerationResult  # list[ScheduleLineDraft] + contractual_total
```
Lives in `modules/installments/services/schedule_engine.py` as free functions / a stateless class taking **only primitive and value-object inputs** — no DB session, no HTTP context, no repository calls. This satisfies the spec's explicit requirement that schedule generation be "independently unit-testable without requiring HTTP or database interaction" (FR-INST §10 preamble) and mirrors the existing pattern of `tax_calculator.py`'s pure calculation functions.

### 10.2 Due-date calculation

- **First due date**: `contract.activation_date + configured_offset_days` (offset from `InstallmentConfiguration`, default 0 = due-date-anchored-to-activation), or an explicit tenant-entered first due date if the tenant's policy allows override.
- **Subsequent due dates**: `add_frequency(previous_due_date, frequency)` — `frequency ∈ {WEEKLY, MONTHLY, QUARTERLY}` (custom frequency only if `InstallmentConfiguration.allowed_frequencies` includes a tenant-defined interval-in-days value, per FR-INST-001's "custom" allowance).
- **Month-end anchoring**: uses Python's `calendar.monthrange()` to clamp — a due date anchored to day 31 in a 30-day month resolves to that month's last day (FR-INST-111), computed via a pure `_add_months(d: date, n: int) -> date` helper (no external date library needed — stdlib `datetime`/`calendar` suffice).
- **Leap years**: handled automatically by stdlib `date` arithmetic for month/day-based frequencies; no custom leap-year branch needed since `WEEKLY`/`MONTHLY`/`QUARTERLY` never depend on a fixed 365/366-day-year assumption.
- **Business-date convention**: schedule-generation "as of" date and all due-date evaluation use the same business-date source Accounting already uses (server UTC date, converted to tenant-local only at presentation) — never `datetime.now()` read ad hoc inside a service; a single `get_business_date()` helper (new, trivial, module-local) is used consistently, satisfying FR-INST-115.

### 10.3 Amount splitting and residual (BR-INST-005, FR-INST-112, [§8](#8-money--precision-strategy))

```python
base_line_amount = (contractual_total / installment_count).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
lines = [base_line_amount] * (installment_count - 1)
last_line_amount = contractual_total - sum(lines)   # residual absorbed entirely here — never distributed
if last_line_amount <= 0:
    raise DegenerateScheduleError(...)   # FR-INST edge case: reject rather than produce a zero/negative final line
lines.append(last_line_amount)
```
Deterministic and reproducible: identical inputs always produce identical output (FR-INST-031, BR-INST-019) — no randomness, no wall-clock dependency beyond the explicit `as_of_date`/`first_due_date` parameters.

### 10.4 Versioning integration

`ScheduleEngine.generate()` is called by `InstallmentContractService.activate()` (first version, `version_number=1`) and by `InstallmentReschedulingService.reschedule()` (subsequent versions). The engine itself is version-agnostic — versioning is a persistence-layer concern ([§6](#6-domain-model), [§9](#9-installment-lifecycle-architecture)), not a schedule-math concern. Rescheduling **only** recomputes due dates for the *remaining unpaid* obligation within the existing `contractual_total` (FR-INST-202 explicitly forbids re-financing/restructuring); already-satisfied `InstallmentAllocationReference` rows are untouched and continue to point at the original (now-superseded) schedule version's lines — history remains fully explainable (BR-INST-017).

### 10.5 Preview (quote) vs. authoritative schedule

`ScheduleEngine.generate()` is called with identical logic for both:
- **Preview** (FR-INST-030–032): `InstallmentQuoteService.preview()` calls the engine and returns the result directly to the API without persisting anything — no `InstallmentContract` row, no `InstallmentScheduleVersion` row, no audit event (explicitly required by FR-INST-032 to be indistinguishable from an ordinary read).
- **Authoritative**: `InstallmentContractService.activate()` calls the same engine and persists the result as `InstallmentScheduleVersion(status=ACTIVE)` + `InstallmentScheduleLine` rows, inside the activation transaction ([§21](#21-transaction--atomicity-boundaries)).

### 10.6 Terms Policy Validation **[NEW — Correction 7]**

**Gap closed**: FR-INST-011 requires that a contract "created either from a template or with fully custom terms" stay "within the tenant's configured policy bounds" (`InstallmentConfiguration.allowed_frequencies`/`min_term`/`max_term`/`min_down_payment_pct`/`min_down_payment_amount`/`max_financed_amount`). Neither `InstallmentContractService.create_draft()` (Phase 3) nor `InstallmentQuoteService.preview()` (Phase 4, [§10.5](#105-preview-quote-vs-authoritative-schedule) above) originally enforced this — both accepted arbitrary caller-supplied terms. No task in the original breakdown assigned this ownership; this was discovered and closed as a targeted tasks.md correction (Phase 4.5, `tasks.md`) rather than by reopening Phase 3/4's own already-proven exit gates.

**Ownership**: exactly one component, `InstallmentTermsPolicyValidator` (`modules/installments/services/terms_policy_validator.py`), is the sole implementation of this check. It takes the effective `InstallmentConfiguration` (resolved via `InstallmentConfigurationService.get_effective_config()` — branch override or company fallback, [§7](#7-configuration-domain) semantics unchanged) plus the proposed terms, and raises `InstallmentTermsPolicyViolationError` (a `ValidationException` subclass, `code="TERMS_POLICY_VIOLATION"`) on any violation. Both `InstallmentQuoteService.preview()` and `InstallmentContractService.create_draft()` call this **same** validator — never two independently-maintained copies of the bounds check — so a caller cannot bypass policy enforcement by skipping `/quotes` and calling contract creation directly. An unconfigured tenant (`get_effective_config()` returns `None`) is treated as "no bounds configured," not "everything forbidden" — consistent with `InstallmentConfiguration` being optional at Phase 2.

This does not reopen Phase 3's or Phase 4's frozen exit-gate proofs (`create_draft()`'s one-contract-per-obligation invariant, `ScheduleEngine`'s own determinism/rounding correctness) — it is a strictly additive precondition check inserted before each of those already-proven code paths runs.

---

## 11. Collection / Allocation Architecture

### 11.1 Allocation policy (FR-INST-140–142)

`InstallmentAllocationPolicy.allocate_oldest_first(payment_amount: Decimal, schedule_lines: list[ScheduleLineOutstanding]) -> list[AllocationInstruction]` — a pure function, sorted by `due_date ASC`, greedily consuming `payment_amount` against each line's outstanding balance (`scheduled_amount - sum(prior non-reversed allocation_references)`) until exhausted or lines run out (remainder becomes an Accounting-side advance/credit per FR-INST-132, never invented by Installments). Tenant-configurable alternative policies are structurally possible (a `Protocol` with one production implementation) but **not built** in Epic 10 — spec does not require one, and building an unused strategy interface would violate meta-§40's "no unnecessary abstraction" instruction. The single `allocate_oldest_first` implementation is the only one shipped.

### 11.2 Collection orchestration flow

```
InstallmentCollectionService.record_collection(
    company_id, contract_id, amount, payment_method, idempotency_key, actor_id
)
  1. InstallmentAccessPolicy.authorize(SERVICING, ...)         [§15]
  2. user_has_installments_permission(..., "installments.collection.create")
  3. Idempotency pre-check/reservation                          [§20]
  4. SELECT ... FOR UPDATE on InstallmentContract row            [§19]
  5. Assert contract.status IN (ACTIVE, DEFAULTED)
  6. Load active schedule version's lines + existing allocation references
     → compute outstanding per line
  7. InstallmentAllocationPolicy.allocate_oldest_first(amount, outstanding_lines)
  8. AccountingPaymentGateway.record_customer_payment(
         company_id, customer_id, amount, allocations=[(ar_transaction_id, amount), ...]
     )  → calls Accounting's PaymentService.create_customer_payment(), which itself
         uses PostingEngine.stage_direct_posting()/finalize_and_publish() internally
  9. Persist InstallmentAllocationReference rows (one per (schedule_line, accounting
     allocation line) pair), inside the SAME db session/transaction as step 8's staged
     writes — see [§21]
 10. If resulting schedule outstanding == 0: **[CORRECTED]** call
     `InstallmentOutstandingService.assert_zero_outstanding()` (§9.3) — only if it
     does NOT raise (no open late-charge AR remains) does
     `InstallmentContractService.complete()` proceed (or leave
     DEFAULTED→COMPLETED per FR-INST-104); otherwise the collection itself still
     commits normally, the contract simply stays ACTIVE/DEFAULTED
 11. InstallmentAuditLog.record(action="COLLECTED", ...)         [§17]
 12. Outbox event: InstallmentCollected                          [§26]
 13. Mark idempotency key COMPLETED, store result                [§20]
 14. ONE db.commit()
```

### 11.3 Where AR truth lives vs. what Installments stores

Installments **does not** create its own `ARTransaction` for the installment schedule as a whole — the originating `SalesInvoice`'s existing AR obligation (already created by Sales/Accounting at invoice-issue time, per the existing Sales→Accounting integration) is what collections allocate against. `InstallmentAllocationReference` rows are pure explanation/mapping metadata: "this much of Accounting's `PaymentAllocationLine` X satisfied schedule line Y." This is the concrete mechanism satisfying BR-INST-007 without creating a second ledger (BR-INST-004).

**Down payment** is the one case where Installments *does* need a fresh AR-side event distinct from the original invoice AR, because a down payment is a partial pre-activation payment against the same invoice obligation — it is recorded via the identical `AccountingPaymentGateway.record_customer_payment()` call used for ordinary collections, allocated against the same invoice's `ARTransaction`, before `activate()` is permitted to proceed (FR-INST-103/150/151).

**[CORRECTED] Late charges are collectible through this same allocation mechanism, not a separate one.** Once a late charge is posted via `stage_adjustment()`+`finalize_adjustment()` ([§12.1](#121-corrected-late-charge-ar-truth--repository-re-inspection-and-resolution)/[§12.2](#122-corrected-general-commit-ownership-contract-for-cross-module-accounting-calls)), it exists as an ordinary `DEBIT_NOTE`-type `ARTransaction` with a positive `outstanding_amount`. Neither `AllocationEngine.allocate()` nor `ARTransactionRepository.get_open_transactions()` filter by `transaction_type` — a customer payment allocated by `InstallmentAllocationPolicy.allocate_oldest_first()` can therefore satisfy a late-charge `ARTransaction` exactly as it would any schedule-line-backed obligation, with no special-case code required in the allocation policy itself. Whether the oldest-outstanding-first ordering considers a late charge's `ARTransaction` alongside schedule-line outstanding is a service-level ordering decision (by due date / charge date), not an Accounting-integration concern — Accounting treats every open `ARTransaction` identically regardless of which Installments concept produced it.

---

## 12. Accounting Integration

This is the most detailed and most constrained section, per meta-§12's explicit instruction. **No Installments code ever imports `modules.accounting.models` or `modules.accounting.repositories` — only `modules.accounting.services` public classes**, mirroring how CRM's `Customer360Service` imports `AccountsReceivableService` directly rather than querying Accounting's tables.

A single new service, `AccountingIntegrationGateway` (`modules/installments/services/accounting_gateway.py`), is the **only** module-boundary crossing point — every operation below funnels through it, so there is exactly one place that knows how to call Accounting.

| Operation | Caller → Callee | Transaction owner | Authoritative data written | Installments metadata written | Failure behavior | Audit | Domain event |
|---|---|---|---|---|---|---|---|
| **Down payment** [**CORRECTED, commit ownership frozen**] | `InstallmentContractService.activate()` → `AccountingIntegrationGateway.record_down_payment()` → Accounting `PaymentService.stage_customer_payment()` + `AllocationEngine.stage_allocation()` (both flush-only) → Installments stages its own rows → `AccountingIntegrationGateway` calls `finalize_customer_payment()` then `finalize_allocation()` **last**, as `activate()`'s own final steps — see [§12.3.1](#1231-activation--down-payment-collection-settlement-payment--paymentservice--allocationengine) | **Installments' service method** (`activate()`) — single final commit for GL + `Payment` + credit `ARTransaction` + allocation lines + `InstallmentScheduleVersion`/`Line` + contract status + audit + outbox together | `accounting_payments`, `accounting_payment_allocation_lines`, `accounting_ar_transactions.outstanding_amount`, GL journal — all staged until Installments' own final commit | none beyond the contract's `down_payment_amount` snapshot field (already set at DRAFT time) | If Accounting raises (e.g. `PostingValidationError`) at any staging step, `activate()` re-raises as `InstallmentActivationFailedError` — **no** state change is committed anywhere, verified by the same class of forced-failure test as [§12.1](#121-corrected-late-charge-ar-truth--repository-re-inspection-and-resolution) (see [§21](#21-transaction--atomicity-boundaries)) | `InstallmentAuditLog(action="DOWN_PAYMENT_RECORDED")`, staged before the final commit | none separate — folded into `InstallmentContractActivated` |
| **Collection** [**CORRECTED, commit ownership frozen**] | `InstallmentCollectionService.record_collection()` → `AccountingIntegrationGateway.record_collection()` → Accounting `PaymentService.stage_customer_payment()` + `AllocationEngine.stage_allocation()` (both flush-only) → Installments stages `InstallmentAllocationReference` rows + audit + outbox + idempotency completion → `finalize_customer_payment()` then `finalize_allocation()` called **last**, by Installments — see [§12.3.1](#1231-activation--down-payment-collection-settlement-payment--paymentservice--allocationengine) | **Installments' service method** | Same tables as above, per collection — all staged until Installments' own final commit | `installment_allocation_references` rows, staged in the **same** session/commit as the Accounting rows above | Same atomic-fail-closed pattern, now proven end-to-end (not just Accounting-internally) by the forced-failure integration test in [§12.3.1](#1231-activation--down-payment-collection-settlement-payment--paymentservice--allocationengine) | `InstallmentAuditLog(action="COLLECTED")`, staged before the final commit | `InstallmentCollected` |
| **Payment allocation mapping** | (part of the collection flow above) | — | `accounting_payment_allocation_lines` (Accounting decides *how* to split across its own concept of outstanding) | `installment_allocation_references` (Installments decides *which schedule line* each Accounting allocation line corresponds to, via the oldest-first policy computed *before* calling Accounting, then reconciled 1:1 against Accounting's actual allocation lines returned) | — | — | — |
| **Reversal** [**CORRECTED, commit ownership frozen**] | `InstallmentCollectionService.reverse_collection()` → `AccountingIntegrationGateway.reverse_payment()` → Installments stages its own reversal rows **first**, then calls Accounting `PaymentService.reallocate_payment(new_allocation_lines=[])` [+ `cancel_payment()` if full reversal, not just un-allocation] **last** — no Accounting-side code change; see [§12.3.2](#1232-collection-reversal--cancellation-with-financial-reversal--reallocate_payment--cancel_payment) for why staging-order alone is sufficient here and the honestly-flagged limitation of the two-call sequence | **Installments' service method**, via staging-before-calling (not a staged/finalize method pair — `reallocate_payment()`'s own internal multi-commit loop is unmodified, see [§2](#2-repository-findings)) | Accounting reverses/re-allocates per its own existing (unmodified) mechanism | New `installment_allocation_references` rows with `is_reversal=true`, `reverses_allocation_reference_id` set — **original rows untouched** (BR-INST-017), staged *before* the Accounting call so they are swept into its first internal commit | If Installments' own staging fails, nothing has committed yet (whole attempt rolls back); once staging succeeds and `reallocate_payment()` begins, its first internal commit already includes Installments' rows — see [§12.3.2](#1232-collection-reversal--cancellation-with-financial-reversal--reallocate_payment--cancel_payment) for the intermediate-state/idempotency-resume handling between the two Accounting calls | `InstallmentAuditLog(action="COLLECTION_REVERSED")`, staged before the Accounting call | `InstallmentCollectionReversed` |
| **Late charge** [**CORRECTED, commit ownership frozen**] | `InstallmentDelinquencyService.apply_late_charge()` → `AccountingIntegrationGateway.post_late_charge()` → Accounting `AccountsReceivableService.stage_adjustment(transaction_type="DEBIT_NOTE", source_document_type="InstallmentLateCharge", source_document_id=late_charge.id, contra_account_id=<tenant's configured Late Fee Income account>)` (flush only — **no commit**) → Installments stages `installment_late_charges` + audit + outbox into the **same session** → Installments' service method calls `AccountsReceivableService.finalize_adjustment(staged, actor_id)` as its **own last step** — see [§12.2](#122-corrected-general-commit-ownership-contract-for-cross-module-accounting-calls) for the full sequence and required extension | **Installments' service method** (not Accounting) — this is the explicit answer to "who owns the final commit," per [§12.2](#122-corrected-general-commit-ownership-contract-for-cross-module-accounting-calls) | GL (DR AR / CR Late Fee Income) **and** a `DEBIT_NOTE`-type `ARTransaction` (`outstanding_amount=charge_amount`, `status="OPEN"`) **and** `CustomerLedger.total_outstanding_base` recompute, all staged (flush-only) until Installments' own `finalize_adjustment()` call | `installment_late_charges` row, `accounting_journal_entry_id` **and** `accounting_ar_transaction_id` both set, staged in the **same** session/commit as the Accounting rows above (not a separate later write) | Atomic — GL, `ARTransaction`, ledger recompute, `installment_late_charges`, `InstallmentAuditLog`, and the outbox event either **all** commit together or **none** do (verified by the forced-failure integration test in [§12.2](#122-corrected-general-commit-ownership-contract-for-cross-module-accounting-calls)); period-lock failure blocks the whole charge but leaves the overdue *state* correctly derived regardless (FR-INST §14.1 edge case) | `InstallmentAuditLog(action="LATE_CHARGE_APPLIED")`, staged before `finalize_adjustment()`, not after | none (low-value; visible via contract read) |
| **Waiver** [**CORRECTED, commit ownership frozen**] | `InstallmentDelinquencyService.waive_late_charge()` — **no Accounting call if the charge was never posted**; if already posted, calls `AccountingIntegrationGateway.reverse_late_charge()` → Accounting `AccountsReceivableService.reverse_adjustment(ar_transaction_id, reason, actor_id)`, which stages the AR-side zeroing/ledger recompute and calls `PostingEngine.reverse()` (single-phase, its own sole commit — see [§2](#2-repository-findings) for why `reverse()` needs no further split) **after** Installments has staged `installment_late_charges.waived_at/by/reason` + audit + outbox into the same session | **Installments' service method** — it calls `reverse_adjustment()` only once its own rows are already staged, matching the same ownership rule as the Late Charge row above | GL reversal entry **and** the `ARTransaction`'s outstanding zeroed/status updated **and** ledger recompute, atomically | `installment_late_charges.waived_at/by/reason`, staged before `reverse_adjustment()` is called | Atomic — same all-or-nothing guarantee as Late Charge | `InstallmentAuditLog(action="LATE_CHARGE_WAIVED")`, staged before `reverse_adjustment()` | none |
| **Early settlement** | `InstallmentSettlementService.generate_quote()` — **no Accounting call, pure read+calculation** (FR-INST-192), **[CORRECTED]** must include any open late-charge `ARTransaction` outstanding in the quoted amount, not schedule principal alone. `InstallmentSettlementService.execute()` (once the authoritative settlement payment already exists — same `record_collection()` path above, at the settlement amount) → **[CORRECTED]** `InstallmentOutstandingService.assert_zero_outstanding()` (§9.3) → only then `complete()` | Installments' service method | Same as Collection | none extra — settlement is "collection for the full remaining amount," now defined to include late-charge AR | Same as Collection | `InstallmentAuditLog(action="SETTLEMENT_QUOTED")` at quote time (spec requires audit even for the quote — FR-INST-341 lists "settlement quote generation" as auditable), `action="SETTLED"` at execution | `InstallmentSettled` |
| **Cancellation** [**CORRECTED, commit ownership frozen**] | `InstallmentContractService.cancel()` → if contract has financial activity, Installments stages its own status-transition rows **first**, then delegates to `AccountingIntegrationGateway.reverse_payment()` **last** (reusing the Reversal path — [§12.3.2](#1232-collection-reversal--cancellation-with-financial-reversal--reallocate_payment--cancel_payment)) | **Installments' service method**, same staging-before-calling discipline as Reversal | Accounting reversal, if applicable, per its own (unmodified) mechanism | `installment_audit_log`, contract status — staged *before* the Accounting call | If Installments' own staging fails, nothing has committed (cancellation itself never proceeds); once staging succeeds and the required reversal begins, its first internal commit already includes Installments' status change (FR-INST-212 satisfied end-to-end, not just Accounting-internally) | `InstallmentAuditLog(action="CANCELLED")`, staged before the Accounting call | `InstallmentCancelled` |
| **Default** | `InstallmentContractService.mark_defaulted()` — **no Accounting call at all**, confirmed unchanged by this correction pass | Installments' service method | none | contract status, `defaulted_at`, reason | N/A — pure Installments state change | `InstallmentAuditLog(action="DEFAULTED")` | `InstallmentDefaulted` |
| **Write-off** [**CORRECTED, commit ownership frozen**] | `InstallmentContractService.writeoff()` → `AccountingIntegrationGateway.writeoff()` → Accounting `AccountsReceivableService.stage_write_off()` (flush only) → Installments stages contract status + audit + outbox → `finalize_write_off()` called **last**, by Installments — see [§12.3.3](#1233-write-off--accountsreceivableserviceconfirm_write_off) | **Installments' service method** — single final commit for GL + `ARTransaction` status/outstanding + `CustomerLedger` recompute + contract status + audit + outbox together (previously **three separate** Accounting-internal commits, per [§2](#2-repository-findings)) | `accounting_ar_transactions.status=WRITTEN_OFF`, GL write-off posting (DR Bad Debt / CR AR), `CustomerLedger` recompute — all staged until Installments' own final commit | contract status, `written_off_at`, staged before the final commit | Atomic end-to-end (not just within Accounting) — Accounting's own permission/config-missing failures propagate and block the whole operation *before any commit occurs anywhere*, verified by a forced-failure integration test analogous to [§12.1](#121-corrected-late-charge-ar-truth--repository-re-inspection-and-resolution)'s | `InstallmentAuditLog(action="WRITTEN_OFF")`, staged before the final commit | `InstallmentWrittenOff` |
| **Fiscal period** | Every posting-producing call above goes **through** `PostingEngine`, inheriting its Step-3 fiscal-period gate automatically | — | — | — | `PostingValidationError("Period is locked/closed")` propagates as `InstallmentFiscalPeriodLockedError` (BR-INST-021, FR-INST-393) | — | — |

**Explicit confirmation (per meta-§12's "Default" requirement)**: `mark_defaulted()` contains **zero** calls to `AccountingIntegrationGateway` — grep-verifiable at implementation time, matching BR-INST-013's requirement that reaching `DEFAULTED` never implies a posting.

**No direct writes to Accounting tables** — every row in the table above under "Authoritative data written" is written exclusively by an Accounting service method call, never by an Installments repository. This is enforced structurally (Installments' `repositories/` package contains no `Accounting*Repository` class and never imports `modules.accounting.models`).

### 12.1 [CORRECTED] Late-charge AR truth — repository re-inspection and resolution

The original plan proposed `PostingEngine.post_direct(DR AR / CR Late Fee Income)` with no `ARTransaction`, reasoning "it's a fee, not a schedule obligation." Re-inspection of `AccountsReceivableService`/`ARTransaction`/`CustomerLedger`/`AllocationEngine` proves this was wrong: it would have increased GL Accounts Receivable while leaving the AR subledger, `CustomerLedger.total_outstanding_base`, and future-payment-allocatable balance completely unchanged — exactly the GL-vs-subledger divergence this correction pass was tasked to eliminate. Answering the five mandated questions directly:

1. **Does `PostingEngine.post_direct(DR AR / CR Income)` alone increase authoritative customer AR?** No. `PostingEngine` only ever writes `JournalEntry`/`JournalLine` — it has no knowledge of `ARTransaction` or `CustomerLedger` at all. AR "truth" for allocation/aging/statement purposes lives entirely in `ARTransaction`/`CustomerLedger`, which `post_direct()` never touches.
2. **What existing service must be used instead?** `AccountsReceivableService.adjust_receivable()` (`ar_service.py:613-706`) — the only method in the codebase that already creates a non-invoice `ARTransaction` alongside a GL posting. It is *not* wired to a REST endpoint, so calling it as an in-process Python service dependency (the same way `Customer360Service` already imports `AccountsReceivableService`) is exactly the intended, existing cross-module integration shape — no HTTP round-trip, no new coupling pattern.
3. **Is a new Accounting-side AR transaction type/source required?** No new *type* — `DEBIT_NOTE` already exists in the `ARTransaction.transaction_type` CHECK constraint (`models/ar.py`) but has never been used by any service; it is the semantically correct choice for a customer-owed charge (distinct from `ADJUSTMENT`'s existing use for disputes/corrections). No migration is needed for this.
4. **Can Installments accomplish this strictly through existing public Accounting services?** **Not quite as-is.** `adjust_receivable()` has two concrete gaps relative to what a genuinely safe cross-module call needs: (a) a real atomicity gap — it calls `post_direct()` (which commits immediately) and only *afterward* inserts the `ARTransaction` and recomputes the ledger in separate, later commits, rather than staging everything into one `stage_direct_posting()`/`finalize_and_publish()` unit the way `record_sales_invoice()` correctly does; (b) it has no `source_document_type`/`source_document_id` parameters, so a caller cannot link the resulting `ARTransaction` back to its own `InstallmentLateCharge` row.
5. **Smallest safe Accounting-side extension** (required, per meta-instruction "if no safe existing public service exists, define the smallest Accounting service extension needed — do not let Installments write Accounting tables directly"). **[Micro-correction pass — commit ownership made explicit]** Re-inspection of `PostingEngine.stage_direct_posting()`/`finalize_and_publish()`'s exact commit boundary ([§2](#2-repository-findings)) proved that a corrected-but-still-single-method `adjust_receivable()` (as the prior correction pass left it) is *still* insufficient for Installments' purposes: it calls `finalize_and_publish()` — which commits — internally, before ever returning control to its caller. That means by the time `AccountingIntegrationGateway.post_late_charge()` gets a result back, GL/AR/ledger are **already committed**, and any subsequent failure while Installments stages `InstallmentLateCharge`/audit/outbox would leave those rows missing against an already-committed Accounting change — precisely the atomicity gap this correction pass exists to close. The extension is therefore a **three-method split**, not a two-parameter signature change:
   - **`AccountsReceivableService.stage_adjustment(db, company_id, customer_id, amount, contra_account_id, reason, posting_date, transaction_type="ADJUSTMENT", source_document_type=None, source_document_id=None, actor_id=None) -> StagedAdjustment`** — **new method**. Performs exactly what `stage_direct_posting()` + the `ARTransaction` build + the ledger recompute do, all via `flush()` only — **no commit**. Returns a small `StagedAdjustment(ar_transaction, journal_entry, journal_number, posted_at)` dataclass — the same `(entry, journal_number, posted_at)` tuple `PostingEngine.stage_direct_posting()` itself returns, plus the flushed-but-uncommitted `ARTransaction`. Mirrors `record_sales_invoice()`'s internal shape exactly, just stopping one step earlier.
   - **`AccountsReceivableService.finalize_adjustment(staged: StagedAdjustment, actor_id) -> ARTransaction`** — **new method**. A thin wrapper: calls `self._engine.finalize_and_publish(staged.journal_entry, staged.journal_number, staged.posted_at, actor_id)` (the **sole** commit point) and returns the now-committed, refreshed `ARTransaction`. Nothing else — no new business logic, purely the finalize half.
   - **`adjust_receivable(...)` (the existing public method)** — becomes a **thin, 100%-backward-compatible wrapper**: `staged = self.stage_adjustment(...); return self.finalize_adjustment(staged, actor_id)`. Every existing standalone caller of `adjust_receivable()` sees identical behavior, identical return type, identical single-call ergonomics, and identical commit-then-return timing as before this change — nothing about its public contract changes.
   - **`AccountsReceivableService.reverse_adjustment(company_id, ar_transaction_id, reason, actor_id)`** — new method, unchanged from the prior correction pass's design: modeled on `PaymentService.cancel_payment()`'s stage-then-`PostingEngine.reverse()` pattern. `reverse()` itself is single-phase (no staged variant needed — see [§2](#2-repository-findings)'s finding on why), so this method's own commit point is `reverse()`'s single `db.commit()`; it does **not** need a further staged/finalize split of its own **unless** a future caller needs to add more rows before that specific commit (Installments' waiver flow, per [§12.2](#122-corrected-general-commit-ownership-contract-for-cross-module-accounting-calls) below, does — see that section for how `reverse_adjustment()` itself is threaded into the same pattern).

   All four methods land in `modules/accounting`, not `modules/installments` — Installments' `AccountingIntegrationGateway` calls `stage_adjustment()`/`finalize_adjustment()` directly (never the wrapper `adjust_receivable()`, which would commit too early for its purposes) and never writes an `ARTransaction`/`JournalEntry` row itself. Flagged explicitly in [§36](#36-implementation-sequence--dependency-graph) (Phase 6) and [§37](#37-risks--trade-offs) as a small, coordinated, cross-module prerequisite — not new architecture, since every piece is templated on a method that already exists and already follows the identical shape being extended toward.

**Consistency guarantee this restores** (verified against the correction's own required outcome): once a late charge is posted via `stage_adjustment()` + `finalize_adjustment()`, `GL AR` and `ARTransaction.outstanding_amount`/`CustomerLedger.total_outstanding_base` increase together, in the same commit, every time — the divergent-truth failure mode the correction identified is now structurally impossible. **[Micro-correction pass]** The *further* guarantee this split restores: `InstallmentLateCharge`, `InstallmentAuditLog`, and the outbox event row are staged into the same session *before* `finalize_adjustment()` is ever called, so they commit together with GL/AR/ledger in that one call — see [§12.2](#122-corrected-general-commit-ownership-contract-for-cross-module-accounting-calls) for the full sequence and [§21](#21-transaction--atomicity-boundaries) for the updated atomic-unit description.

### 12.2 [CORRECTED] General commit-ownership contract for cross-module Accounting calls

This section makes explicit, as its own named architectural rule, what [§12.1](#121-corrected-late-charge-ar-truth--repository-re-inspection-and-resolution)'s fix implements for the late-charge/waiver case specifically:

> **When an Accounting service method is invoked from Installments as part of a larger atomic Installments workflow, that method MUST expose a staged (flush-only, no-commit) variant, and Installments' own service method — never Accounting's — owns the single final commit for the whole unit of work.**

Concrete sequence for late charge (mirrors the pattern for waiver via `reverse_adjustment()`'s own staged half, and is the template for any future Installments↔Accounting integration point that needs this property):

```text
InstallmentDelinquencyService.apply_late_charge()   [owns the transaction/session]
        ↓
staged = ar_service.stage_adjustment(db, ..., source_document_type="InstallmentLateCharge",
                                      source_document_id=late_charge.id)
        # flush only — GL JournalEntry+Lines and the ARTransaction now exist in the
        # session, fully built, but NOT committed; CustomerLedger already recomputed
        # in-session too
        ↓
late_charge.accounting_journal_entry_id = staged.journal_entry.id
late_charge.accounting_ar_transaction_id = staged.ar_transaction.id
db.add(late_charge); db.flush()                      # Installments' own row, staged
        ↓
installment_audit_service.record(...)                 # flush only
outbox_repo.create(...)                                # flush only (core/events/outbox.py)
        ↓
ar_service.finalize_adjustment(staged, actor_id)       # <-- the ONE commit for
        ↓                                                  everything above
return
```

**Explicit answer to "who owns the final commit"** (the correction's own required question): **Installments' service method owns it**, by being the one that calls `finalize_adjustment()` — a public `AccountsReceivableService` method — as its own last step, after every Installments-side row has already been flushed into the same session. Accounting never independently decides when to commit on Installments' behalf; it only provides the mechanism (`finalize_adjustment()` → `PostingEngine.finalize_and_publish()`) that Installments' code explicitly invokes at the moment it has finished staging everything.

**Design pattern chosen**: **Pattern C** (refactor existing method internals, backward-compatible) combined with **Pattern A**'s spirit (a staged API Installments calls) — `adjust_receivable()`'s existing internals are split into `stage_adjustment()`/`finalize_adjustment()` rather than duplicated, so there is exactly one implementation of the AR-adjustment business logic, reused by both the standalone wrapper and the cross-module staged path. This was chosen over inventing a `commit=False` boolean parameter (rejected — no existing Accounting method uses a boolean commit-toggle parameter anywhere in the codebase; the stage/finalize *method pair* is the established, already-precedented idiom via `PostingEngine` itself, so extending that same idiom one layer up into `AccountsReceivableService` is more consistent than introducing a new parameter-based convention).

**Required integration test** (per the correction's explicit instruction): force a failure *after* `stage_adjustment()` has flushed the GL/AR/ledger rows but *before* `InstallmentLateCharge`/audit/outbox staging completes (e.g. raise inside a test-injected fault right after the `late_charge` flush, before `finalize_adjustment()` is called) — assert, against a real Postgres connection post-rollback, that **all** of the following are simultaneously absent: the `JournalEntry`, the `ARTransaction`, any `CustomerLedger.total_outstanding_base` change, the `InstallmentLateCharge` row, the `InstallmentAuditLog` row, and the outbox event row. No partial commit is acceptable, and this test is the direct, executable proof that none occurs. See [§31](#31-testing-strategy) for this test's placement in the layered testing strategy.

### 12.3 [Final correction pass] Generalized commit ownership across every Installments↔Accounting workflow

[§12.2](#122-corrected-general-commit-ownership-contract-for-cross-module-accounting-calls) proved the commit-ownership contract for late charges specifically. This section re-verifies and applies the identical hard invariant — **for every Installments financial workflow, either ALL Accounting + Installments writes commit together, or NONE commit** — to every other money-mutating integration point, per fresh, method-by-method repository re-inspection ([§2](#2-repository-findings)).

#### 12.3.1 Activation / Down payment, Collection, Settlement payment — `PaymentService` + `AllocationEngine`

**Exact methods called**: `PaymentService.create_customer_payment()` (creates the `Payment` + its paired credit `ARTransaction`) **and**, separately, `AllocationEngine.allocate()` (allocates that credit against the target `ARTransaction` — the originating invoice's, for a down payment; a schedule-line-backed obligation's, for an ordinary collection or settlement). Both are genuinely required — `create_customer_payment()` alone never allocates anything (confirmed: it only ever creates an unallocated `PAYMENT`/`ADVANCE` credit transaction; allocation is always a separate, explicit `AllocationEngine.allocate()` call, per [§2](#2-repository-findings)).

**Early-commit problem found**: Both methods commit internally before returning (`create_customer_payment()`'s immediate-post branch via `finalize_and_publish()` at line 374; `allocate()` via its own final `finalize_and_publish()`/bare-commit block) — identical bug class to the original late-charge defect, now confirmed present in the two methods every down payment, collection, and settlement payment depends on.

**Required extension** (mirrors [§12.1](#121-corrected-late-charge-ar-truth--repository-re-inspection-and-resolution)'s pattern exactly):
- **`PaymentService.stage_customer_payment(...) -> StagedCustomerPayment | DraftPaymentResult`** — replicates `create_customer_payment()`'s immediate-post branch via flush-only writes (stages the GL entry via `stage_direct_posting()`, builds+flushes the `Payment` and its credit `ARTransaction`, recomputes the ledger — all flush, no commit). For the pre-existing above-threshold DRAFT branch (no GL/AR truth created at all), it performs the *same* early commit as today and returns a `DraftPaymentResult(payment)` sentinel — that branch needs no split, since there is nothing yet for Installments to bundle with it.
- **`PaymentService.finalize_customer_payment(staged: StagedCustomerPayment, actor_id) -> tuple[Payment, PostingResult]`** — thin wrapper calling `finalize_and_publish()`, the sole commit for the immediate-post branch.
- **`create_customer_payment()`** becomes a thin, 100%-backward-compatible wrapper of both (unchanged behavior/return type for every existing standalone caller).
- **`AllocationEngine.stage_allocation(...) -> StagedAllocation`** — replicates `allocate()`'s per-line loop via flush-only writes (`PaymentAllocationLine`, target-transaction outstanding/status, credit-transaction outstanding/status, `payment.status="ALLOCATED"` — no repository `.update()` calls, matching the existing method's own already-flush-only internal writes). Returns `StagedAllocation(allocation_lines, payment, staged_fx_entries)`.
- **`AllocationEngine.finalize_allocation(staged: StagedAllocation, actor_id) -> list[PaymentAllocationLine]`** — replicates the existing final block exactly (one `finalize_and_publish()` per staged FX-adjustment entry, or a bare `db.commit()` if none). **Documented honestly, not oversimplified**: if `staged_fx_entries` has more than one entry, this method issues more than one commit-triggering call — but because every business-relevant write (Accounting's *and* Installments') is already flushed before the *first* of these calls, that first call is the true atomicity boundary; any further calls in the same step commit an already-durable state and only add their own FX-adjustment entry's journal-numbering/event-publish bookkeeping, a narrower, pre-existing Accounting-internal concern this plan does not need to (and does not) change.
- **`allocate()`** becomes a thin, backward-compatible wrapper of both.

**Corrected sequence** (Installments' service method owns the transaction throughout):
```text
staged_payment = payment_service.stage_customer_payment(...)              # flush only
if isinstance(staged_payment, DraftPaymentResult):
    # No GL/AR truth exists yet — nothing to bundle. Installments records
    # the collection as pending Accounting approval, stages its own audit
    # noting that, and commits here; a later Accounting approval event
    # triggers a separate, subsequent allocation flow, not covered further
    # by this section (an existing, pre-Installments Accounting workflow).
    ...; db.commit(); return

staged_allocation = allocation_engine.stage_allocation(
    company_id, staged_payment.payment.id, allocation_lines, actor_id
)                                                                          # flush only

for line in staged_allocation.allocation_lines:
    db.add(InstallmentAllocationReference(..., accounting_payment_id=staged_payment.payment.id,
                                           accounting_payment_allocation_line_id=line.id, ...))
db.flush()
installment_audit_service.record(...)          # flush
outbox_repo.create(...)                        # flush
idempotency_row.status = "COMPLETED"           # flush

payment_service.finalize_customer_payment(staged_payment, actor_id)       # <-- FIRST commit;
                                                                            #     durably persists
                                                                            #     EVERYTHING above
allocation_engine.finalize_allocation(staged_allocation, actor_id)        # finalizes any
                                                                            # FX-adjustment entries
```
**Applies identically** to down payment (target = originating invoice's `ARTransaction`), ordinary collection (target = due schedule line(s)' backing obligation), and settlement payment (target = the full remaining obligation, per the plan's existing "settlement is collection for the full remaining amount" design, [§12](#12-accounting-integration) Early Settlement row) — the only difference between the three is which `ARTransaction`(s) the `allocation_lines` argument targets, never the commit-ownership mechanics.

#### 12.3.2 Collection reversal / Cancellation-with-financial-reversal — `reallocate_payment()` + `cancel_payment()`

**Exact methods called**: `PaymentService.reallocate_payment(company_id, payment_id, new_allocation_lines=[], actor_id)` (reverses every existing allocation line for the payment, returning it to unallocated `POSTED` status — the correct existing mechanism for "undo this collection's allocation," confirmed by reading its full body: an empty `new_allocation_lines` list makes its trailing `self._allocation_engine.allocate(...)` call a no-op loop, leaving the payment unallocated) **and**, if the payment itself should be fully reversed (not merely left as unallocated credit — the behavior FR-INST-131/240 call for), `PaymentService.cancel_payment(company_id, payment_id, reason, actor_id)` afterward (which requires the payment to already have zero active allocations — hence `reallocate_payment()` must run first).

**Early-commit problem found — the deepest one in the codebase**: `reallocate_payment()` commits **inside a loop**, once per existing allocation line being reversed (via `PostingEngine.reverse()`'s own commit, or a bare `db.commit()`), **plus** a further commit after `payment.status = "POSTED"`, **plus** whatever `allocate()`'s own trailing call commits. `cancel_payment()` has one simpler, single commit point. Genuinely refactoring `reallocate_payment()`'s loop into a flush-only shape (N commits → N flushes, deferring all of them to one final commit) would be a materially larger, more invasive change to existing, already-shipped Accounting behavior than any other fix in this plan — and would touch a method with its own existing standalone callers and its own existing test suite for an internal commit pattern that has nothing to do with Installments.

**Resolution — no Accounting-side code change required**, using a narrower guarantee that is provably sufficient for this specific case: **Installments stages every one of its own rows (the reversal `InstallmentAllocationReference(is_reversal=true, reverses_allocation_reference_id=...)` rows, audit, outbox, idempotency completion) *before* calling `reallocate_payment()`/`cancel_payment()` at all.** None of Installments' reversal-reference rows depend on the Accounting reversal having already happened — they only record "this much, of this original allocation, is being reversed, for this reason," which is known and true the moment the reversal is *requested*, not only once Accounting has finished processing it. Because of this, the *first* commit that occurs anywhere inside `reallocate_payment()`'s loop necessarily sweeps in everything Installments already flushed beforehand — satisfying the hard invariant exactly: if Installments' own staging fails, nothing (Accounting or Installments) has committed yet and the whole attempt rolls back cleanly; once Installments' staging succeeds and the Accounting call begins, the *first* thing that commits already includes Installments' rows. Any *further* internal commits inside `reallocate_payment()`'s own loop (for subsequent existing-allocation-lines being reversed) are that method's own pre-existing, already-shipped, already-tested atomicity behavior for its *own* multi-line reversal case — unrelated to and unworsened by Installments calling it, and explicitly out of this plan's scope to alter (per this correction's own "do not redesign... unrelated sections" instruction).

**Corrected sequence**:
```text
for original_ref in installment_allocation_references_being_reversed:
    db.add(InstallmentAllocationReference(is_reversal=True,
            reverses_allocation_reference_id=original_ref.id, ...))
db.flush()
installment_audit_service.record(...)          # flush
outbox_repo.create(...)                        # flush
idempotency_row.status = "COMPLETED"           # flush

payment_service.reallocate_payment(company_id, payment_id, new_allocation_lines=[], actor_id)
                                                # <-- first internal commit sweeps in everything above
if full_cancellation_required:
    payment_service.cancel_payment(company_id, payment_id, reason, actor_id)
                                                # separate, subsequent call/commit — see below
```
**Honest limitation, explicitly flagged rather than hidden**: because `reallocate_payment()` and `cancel_payment()` are two *separate* method calls, a failure that occurs *after* `reallocate_payment()`'s own commit(s) but *before* `cancel_payment()` completes would leave the payment un-allocated (Installments' reversal-reference rows already correctly durable) but not yet cancelled — an intermediate, still-fully-explainable state (an unallocated `Payment` in `POSTED` status is itself a valid, already-existing Accounting concept, not a corrupt one), not a violation of BR-INST-004/BR-INST-017. `InstallmentCollectionService.reverse_collection()`'s own idempotency key ([§20](#20-idempotency-strategy)) covers exactly this: a retried reversal request with the same key, if it reaches this intermediate state, resumes by simply calling `cancel_payment()` on its own (the un-allocation already happened and is idempotently detectable via the payment's own `status`), rather than re-attempting `reallocate_payment()` against an already-unallocated payment.

#### 12.3.3 Write-off — `AccountsReceivableService.confirm_write_off()`

**Exact method called**: `AccountsReceivableService.confirm_write_off()`.

**Early-commit problem found — three separate commits, the exact bug class the first correction pass already fixed once, never fixed here**: `confirm_write_off()` calls `PostingEngine.post_direct()` (commits immediately — it is `stage_direct_posting()`+`finalize_and_publish()` bundled), and only *afterward* sets `transaction.status = WRITTEN_OFF`/zeroes `outstanding_amount` via `self._transactions.update(transaction)` — confirmed, by reading `core/repositories/base.py:92-106`, that `BaseRepository.update()` itself calls `db.commit()` — a **second** commit — and then `self._recompute_ledger_balance(...)` → `self._ledgers.update(ledger)`, **another** `BaseRepository.update()` call, a **third** commit.

**Required extension** (identical pattern to §12.1's `adjust_receivable()` fix, this time also eliminating the two additional repository-`.update()`-triggered commits, not just the `post_direct()` one):
- **`AccountsReceivableService.stage_write_off(company_id, ar_transaction_id, reason, actor_id) -> StagedWriteOff`** — replicates `confirm_write_off()`'s full logic via flush-only writes throughout: `stage_direct_posting()` (not `post_direct()`) for the GL entry; `db.add(transaction); db.flush()` directly for the status/outstanding-amount change (**not** `self._transactions.update()`, whose internal commit is exactly what must be avoided); `self._audit.record(...)` (already flush-only, unchanged); the ledger recompute inlined as `db.add(ledger); db.flush()` directly (**not** `self._ledgers.update()`). Returns `StagedWriteOff(ar_transaction, journal_entry, journal_number, posted_at)`.
- **`AccountsReceivableService.finalize_write_off(staged: StagedWriteOff, actor_id) -> ARTransaction`** — thin wrapper calling `finalize_and_publish()`, the sole commit for GL + the transaction status change + the ledger recompute together.
- **`confirm_write_off()`** becomes a thin, backward-compatible wrapper of both.

**Corrected sequence**:
```text
staged_writeoff = ar_service.stage_write_off(company_id, ar_transaction_id, reason, actor_id)  # flush only
contract.status = "WRITTEN_OFF"; contract.written_off_at = utcnow()
db.add(contract); db.flush()
installment_audit_service.record(...)          # flush
outbox_repo.create(...)                        # flush
idempotency_row.status = "COMPLETED"           # flush

ar_service.finalize_write_off(staged_writeoff, actor_id)   # <-- the ONE commit for everything above
```

#### 12.3.4 Summary table — commit ownership per workflow

| Workflow | Accounting method(s) | Early-commit problem? | Fix |
|---|---|---|---|
| Down payment | `create_customer_payment()` + `allocate()` | Yes, both | New `stage_customer_payment()`/`finalize_customer_payment()` + `stage_allocation()`/`finalize_allocation()` ([§12.3.1](#1231-activation--down-payment-collection-settlement-payment--paymentservice--allocationengine)) |
| Collection | `create_customer_payment()` + `allocate()` | Yes, both | Same as above |
| Settlement payment | `create_customer_payment()` + `allocate()` | Yes, both | Same as above |
| Late charge | `adjust_receivable()` | Yes ([§12.1](#121-corrected-late-charge-ar-truth--repository-re-inspection-and-resolution)) | `stage_adjustment()`/`finalize_adjustment()` (prior pass) |
| Late-charge waiver | `reverse_adjustment()` | No — single-phase, called last, after Installments' own rows are already staged | None needed (prior pass) |
| Collection reversal | `reallocate_payment()` [+ `cancel_payment()`] | Yes — deeply so (multi-commit loop) | No Accounting-side change; stage Installments' rows *before* calling ([§12.3.2](#1232-collection-reversal--cancellation-with-financial-reversal--reallocate_payment--cancel_payment)) |
| Cancellation with financial activity | `reallocate_payment()` + `cancel_payment()` | Yes | Same as above |
| Write-off | `confirm_write_off()` | Yes — **three** separate commits | New `stage_write_off()`/`finalize_write_off()` ([§12.3.3](#1233-write-off--accountsreceivableserviceconfirm_write_off)) |
| Default | *(none — confirmed zero Accounting calls)* | N/A | N/A |

**Every workflow above now satisfies the hard invariant** — either every Accounting write and every Installments write for that workflow commit together, or none of them do — through one of exactly two mechanisms: a new staged/finalize method pair (down payment, collection, settlement, late charge, write-off), or a proven "stage Installments' rows before the first Accounting commit in the sequence" ordering discipline requiring no Accounting-side change at all (collection reversal, cancellation, late-charge waiver).

---

## 13. Sales Integration

| Concern | Design |
|---|---|
| Contract creation eligibility | `InstallmentEligibilityService.check_invoice_eligibility(company_id, sales_invoice_id)` reads `SalesInvoiceRepository.get_by_id_or_none()` **directly** (read-only cross-module repository import — same pattern `Customer360Service` uses for `CustomerRepository`), asserts `status == "ISSUED"` and sufficient outstanding amount (via Accounting's `ARTransaction`, not a Sales field — Sales has no outstanding-amount column, per [§2](#2-repository-findings)) |
| One-contract-per-obligation | Enforced by the partial unique index ([§7.2](#72-constraints)) plus a pre-check in `InstallmentContractService.create_draft()` — DB constraint is the final backstop; the pre-check exists purely for a clean 409 error message rather than a raw `IntegrityError` |
| Pre-existing partial payments | `InstallmentContractService.create_draft()` computes `financed_principal = invoice_outstanding_amount - down_payment`, reading `invoice_outstanding_amount` from Accounting's `ARTransaction` (never a stale/duplicated field) — correctly excludes already-satisfied amounts (FR-INST-261) |
| Currency | `InstallmentContract.currency_code` is set once from `SalesInvoice.currency_code` at draft-creation time and is immutable thereafter (BR-INST-022, FR-INST-253) |
| Post-activation invoice correction | `modules/installments/handlers/sales_integration_handlers.py` subscribes to Sales' in-process event bus for `InvoiceCreditNoteIssued` and `InvoiceCancelled` (`modules.sales.events.get_event_bus().subscribe(...)`). Handler sets a **non-terminal flag** `requires_review = true` + `InstallmentAuditLog(action="ORIGINATING_INVOICE_CORRECTED")` on any contract referencing that invoice — it does **not** auto-cancel or auto-adjust the contract (Scenario H requires an authorized human action to resolve it, never a silent auto-transition) |
| No stock/inventory effect | `InstallmentCollectionService` and `InstallmentContractService` contain no calls into `modules.inventory` at all — structurally absent, satisfying FR-INST-280/281 by omission |
| Document numbering | `InstallmentSequence` is a **new, Installments-owned table** (not a reuse of `SalesSequence`, whose `document_type` CHECK constraint is hardcoded to Sales' 5 codes) — replicates `SalesSequenceService`'s `SELECT...FOR UPDATE`-then-increment locking pattern verbatim, formatted `IC-YYYY-NNNNNN` |

---

## 14. CRM / Inventory Integration

| Concern | Design |
|---|---|
| Inventory | **No integration point exists.** No Installments service, repository, or handler imports anything from `modules.inventory`. |
| Customer 360 exposure | `InstallmentCustomerSummaryService.get_summary(company_id, customer_id) -> InstallmentCustomerSummary` (active contracts, outstanding, overdue, next due date, payment history, completed/defaulted contracts) is a small, read-only, permission-agnostic service method CRM's `Customer360Service` can import directly, exactly mirroring how `Customer360Service` already imports Accounting's `AccountsReceivableService.get_customer_ledger()`. Installments does not modify `Customer360Service` itself in this plan (that is a CRM-module change, out of this plan's blast radius) — it only guarantees the importable interface exists. |
| CRM activity/notes reuse (FR-INST-291, "SHOULD") | Where a tenant uses CRM, `InstallmentCollectionService`/`InstallmentDelinquencyService` MAY call CRM's `ActivityService.create_activity()` (via CRM's public service interface, not its repository) to log a collection-related note as a CRM `Activity` row with `activity_type="NOTE"` and the loose `customer_id` FK CRM's `Activity` model already supports. This is optional (tenant-configuration-gated) and additive — Installments' own `InstallmentAuditLog` remains the authoritative record regardless of whether CRM activity-mirroring is enabled. |

---

## 15. Entitlement Architecture

### 15.1 Why CRM's router-level gate cannot be reused as-is

CRM's `require_crm_enabled` blocks the **entire router** when disabled — appropriate for CRM (spec has no CRM-equivalent of "existing obligations must remain serviceable"). Installments' spec (§22.3/22.4, FR-INST-353–358) requires **operation-level** granularity: origination blocked, servicing/read permitted. A blanket router-mount gate cannot express this. See ADR-INST-06.

### 15.2 `InstallmentAccessPolicy` — the centralized policy service

```python
class InstallmentOperationClass(str, Enum):
    ORIGINATION = "ORIGINATION"   # new quote, new contract, activation of a NEW contract,
                                   # plan/template CRUD, configuration changes, reschedule,
                                   # cancel, default, writeoff (FR-INST-353/357 — all blocked while disabled)
    SERVICING   = "SERVICING"     # view existing contract/schedule/history, collection,
                                   # allocation, reversal/correction, ordinary payoff,
                                   # early settlement of an EXISTING contract, statements
    READ        = "READ"          # pure read of existing data — always allowed if entitled
                                   # OR if the target contract already exists (servicing-adjacent)
    ADMIN       = "ADMIN"         # module enable/disable toggle itself — reachable while disabled
                                   # (chicken-and-egg, same as CRM's admin_router)

class InstallmentAccessPolicy:
    def authorize(self, *, company_id: UUID, operation: InstallmentOperationClass) -> None:
        if operation is InstallmentOperationClass.ADMIN:
            return  # tenant toggle management is never gated by its own state
        entitlement = self._entitlement_service.resolve_effective_entitlement(
            company_id=company_id, capability_key="installments"
        )
        if entitlement.is_available:
            return
        if operation in (InstallmentOperationClass.SERVICING, InstallmentOperationClass.READ):
            return  # FR-INST-356: existing-obligation servicing continues under disabled entitlement
        raise InstallmentsNotEntitledError()  # ORIGINATION only — FR-INST-353
```

**Where checked**: inside each **service method**, not the router, and not cached across requests — mirrors `require_capability_entitled`'s existing "never cross-request cached" discipline (reused via the same `PlatformEntitlementService.resolve_effective_entitlement()` call). Every `InstallmentContractService`/`InstallmentCollectionService`/etc. method starts with `self._access_policy.authorize(company_id=..., operation=...)` **before** the RBAC permission check and before any repository call — so a mid-flight entitlement change is only ever observed at the start of the *next* request, never mid-transaction (no TOCTOU window wider than any other module's identical entitlement check already has).

**Router mounting**: `installments_router` is mounted with `dependencies=[Depends(get_current_company_member)]` **only** — no blanket entitlement dependency at mount time, unlike CRM/Accounting. `installments_admin_router` (status/enable/disable) is mounted identically, since `ADMIN` operations bypass the policy entirely.

### 15.3 Suspended tenant vs. disabled module (spec §17 requirement, restated)

No separate mechanism is built. Suspension is already enforced upstream, once, inside `get_current_company_member` ([§2](#2-repository-findings)) — Installments' routes inherit this automatically by using the same dependency every other tenant-scoped router uses. `InstallmentAccessPolicy` never re-checks `Company.status`, exactly matching the documented principle in `PlatformEntitlementService`'s own docstring ("company lifecycle is that layer's concern, not this resolver's — duplicating it here would be a second, divergent enforcement point").

### 15.4 Registration

- New `Capability` row: `{"key": "installments", "module": "installments", "display_name": "Installments"}` added to `CapabilitySeedService.MODULE_CAPABILITY_CATALOGUE`.
- New `InstallmentsModuleEnablementProvider(ModuleEnablementProvider)` wrapping `InstallmentsFeatureFlagService`, registered in `get_module_enablement_provider()`'s factory alongside `CrmModuleEnablementProvider`.
- `InstallmentsFeatureFlagService`/`InstallmentsFeatureFlag` mirror `CrmFeatureFlagService`/`CrmFeatureFlag` exactly (single `flag_key="feature.installments.enabled"`, defaults `False`, `enable()`/`disable()`).

---

## 16. RBAC / Maker-Checker

### 16.1 Permission catalogue (implements spec §20.1 exactly, plus the required cure permission)

| Permission code | Capability | Operation class |
|---|---|---|
| `installments.config.manage` | Configure tenant-level policy | ADMIN |
| `installments.plan.manage` | Create/edit/deactivate templates | ORIGINATION |
| `installments.contract.view` | View contracts and schedules | READ |
| `installments.contract.create` | Create a draft contract / quote | ORIGINATION |
| `installments.contract.approve` | Approve a submitted contract | ORIGINATION |
| `installments.contract.activate` | Activate an approved contract | ORIGINATION |
| `installments.collection.create` | Record a collection | SERVICING |
| `installments.collection.reverse` | Reverse a recorded collection | SERVICING |
| `installments.charge.waive` | Waive a late charge | SERVICING |
| `installments.contract.reschedule` | Controlled due-date amendment | ORIGINATION |
| `installments.contract.cancel` | Cancel a contract | ORIGINATION |
| `installments.contract.default` | Mark a contract defaulted | ORIGINATION |
| `installments.contract.cure` | **New** — restore `DEFAULTED → ACTIVE`, distinct from `collection.create` per spec's explicit requirement (§9 meta-prompt, FR-INST-222) | SERVICING |
| `installments.contract.writeoff` | Write off a defaulted balance | ORIGINATION |
| `installments.settlement.execute` | Generate/execute early settlement | SERVICING |
| `installments.report.view` | View reports/dashboards | READ |

Each permission is independently checked (`user_has_installments_permission(db, company_id, user_id, code)`) inline at the top of each service method, mirroring `user_has_accounting_permission`. Holding one never implies another (FR-INST-320/321). `installments.contract.cure` is deliberately **not** satisfied by `installments.collection.create` — `cure()`'s service method checks the `cure` code exclusively, so a cashier who can record collections cannot cure a defaulted contract.

**[CORRECTED] New-tenant vs. existing-tenant permission availability**: these 16 codes reach a **new** company automatically (via `RoleSeedService` reading `constants.py` at company-creation time); an **existing** company only receives them through the now-mandatory backfill migration `071_installments_permission_backfill` — see [§30.1](#301-corrected-migration-071-is-mandatory-not-conditional) for the full repository-grounded justification and the exact default system-role grant table. This distinction is deploy-time-only and has no bearing on the permission-check logic itself, which is identical regardless of when a company received its grants.

### 16.2 Maker-checker implementation

`InstallmentContractService.approve()` and `.reject()` both perform, before anything else:
```python
if contract.submitted_by is not None and contract.submitted_by == approver_id:
    raise InstallmentSelfApprovalNotAllowedError()
```
— a module-local exception mirroring `SelfApprovalNotAllowedError`'s exact shape, **applied identically to both `approve()` and `reject()`** from day one (explicitly avoiding the documented Accounting/Payment history of forgetting the mirror action — [§2](#2-repository-findings)).

Per spec FR-INST-330–332 and the meta-prompt's explicit ask to evaluate rescheduling/write-off/waiver:
| Action | Maker-checker required? | Rationale |
|---|---|---|
| Contract approval | **Yes** — submitter ≠ approver | FR-INST-330, explicit |
| Write-off | **Yes** — distinct permission (`writeoff` ≠ `default` ≠ `collection.create`); tenant MAY additionally configure "defaulter ≠ writer-off" as a stricter policy via `InstallmentConfiguration.writeoff_requires_permission`-adjacent config, but the codebase does **not** hard-require distinct actors beyond distinct permissions (FR-INST-331 makes this explicitly optional/tenant-configurable, not mandatory) | FR-INST-331 |
| Late-charge waiver | **No self-approval concept** (there's no "submitter"), but a **distinct permission** from ordinary collection (`installments.charge.waive` ≠ `installments.collection.create`) | FR-INST-332 |
| Rescheduling | **Yes** — spec explicitly requires "the same maker-checker discipline as contract approval" (FR-INST-201); implemented identically to `approve()`/`reject()`, requiring a distinct approver from whoever requested the reschedule | FR-INST-201 |

---

## 17. Audit Architecture

`InstallmentAuditLog` (plain `Base`, explicit `company_id` — matching `AccountingAuditLog`'s richer shape over CRM's minimal one, since Installments actions are financially sensitive and frequently carry a mandatory reason):

```python
class InstallmentAuditLog(Base):
    __tablename__ = "installment_audit_log"
    id: Mapped[UUID]              # server-generated
    company_id: Mapped[UUID]      # indexed
    entity_type: Mapped[str]      # "InstallmentContract" | "InstallmentScheduleLine" | ...
    entity_id: Mapped[UUID]
    action: Mapped[str]           # "CREATED"|"SUBMITTED"|"APPROVED"|"REJECTED"|"ACTIVATED"|
                                   # "COLLECTED"|"ALLOCATED"|"COLLECTION_REVERSED"|
                                   # "LATE_CHARGE_APPLIED"|"LATE_CHARGE_WAIVED"|"RESCHEDULED"|
                                   # "SETTLEMENT_QUOTED"|"SETTLED"|"CANCELLED"|"DEFAULTED"|
                                   # "CURED"|"WRITTEN_OFF"|"CONFIGURATION_CHANGED"|"TEMPLATE_CHANGED"
    actor_user_id: Mapped[UUID | None]
    occurred_at: Mapped[datetime]
    before_state: Mapped[dict | None]   # JSONB
    after_state: Mapped[dict | None]    # JSONB
    session_context: Mapped[dict | None]  # JSONB — request_id, IP, user agent (ContextVars)
    reason: Mapped[str | None]
```

**Fail-closed discipline** (BR-9A-024 precedent, applied identically): `InstallmentAuditService.record()` only `db.add()` + `db.flush()`s — never commits. Every service method that mutates state calls `record()` **before** its single `db.commit()`. If the flush raises (constraint violation, connection loss), the exception propagates up through the service method, the transaction rolls back, and **the business mutation is never committed either** — audit failure and business failure are the same failure by construction, not by a separate try/except.

**Access control**: reading audit history requires `installments.contract.view` (spec explicitly allows reusing this or "a dedicated audit-view permission" — this plan reuses `contract.view` rather than adding a 17th permission code, since no spec requirement forces a separate one and the smallest-viable-change principle favors reuse).

**Coverage**: every action enumerated in spec §21 (FR-INST-340) maps 1:1 to an `action` value above — see [§38](#38-requirement-traceability).

---

## 18. Multi-Tenant / Branch Isolation

- Every table inherits `TenantBaseModel` (or the documented append-only exception with an explicit `company_id` column) — no exceptions.
- Every `InstallmentXRepository` subclasses `BaseRepository[InstallmentX]` and receives `company_id` as a mandatory parameter on every custom query method, exactly matching `CustomerLedgerRepository`'s pattern ([§2](#2-repository-findings)).
- Every route sits behind `get_current_company_member` (path-parameter `company_id`, validated against active membership).
- **Cross-tenant lookup behavior**: `get_by_id_or_none(id, company_id)` returns `None` → service raises `NotFoundException` (404) — identical response whether the contract doesn't exist or belongs to another tenant (BR-INST-015, FR-INST-372), reusing the platform's existing dual-status convention (403 for "not a company member at all" vs. 404 for "record exists elsewhere," per cross-cutting research §10).
- **Contract numbering** is tenant-scoped (`uq_installment_contracts_company_number`), matching FR-INST-040's "tenant-scoped, sequential" requirement.
- **Branch**: `branch_id: UUID | None` reserved on `InstallmentConfiguration` (company-level fallback: `WHERE branch_id IS NULL` row), `InstallmentContract`, and reporting/collection filters — nullable, no FK (no `Branch` entity exists platform-wide yet, per [§2](#2-repository-findings)). This satisfies Constitution §10's "should be ready" without inventing branch authorization that has no platform precedent to follow (explicitly avoiding meta-§22's "do not create a new branch authorization system"). When the platform eventually adds a `Branch` entity, `branch_id` becomes a real FK via an additive migration — no rework of Installments' own schema needed.

---

## 19. Concurrency Strategy

| Race condition | Protection mechanism | Why this one |
|---|---|---|
| Duplicate non-terminal contract per obligation | **Partial unique index** `uq_installment_contracts_one_nonterminal_per_obligation` ([§7.2](#72-constraints)) | DB-level, race-proof by construction — two concurrent `INSERT`s cannot both succeed regardless of application-layer timing; mirrors the platform's own `Subscription` precedent |
| Over-collection | `SELECT ... FOR UPDATE` on the `InstallmentContract` row at the start of `record_collection()`/`execute_settlement()`, held for the duration of the transaction, **plus** Accounting's own `AllocationEngine` re-validates `allocated <= outstanding` independently (defense in depth — Installments' lock serializes concurrent Installments-side requests; Accounting's own lock on `ARTransaction` serializes at the ledger level regardless of caller) | Matches the platform's dominant pessimistic-locking convention for money-mutating rows (`ARTransactionRepository.get_by_id_locked()`) rather than introducing optimistic versioning for a scenario that's fundamentally about serializing a sequence of financial writes, not detecting a stale read |
| Double settlement | Same contract-row lock as collection (settlement execution *is* a collection at the full remaining amount) + `status` re-checked under the lock (`ACTIVE`/`DEFAULTED` required) — a second concurrent settlement attempt sees `status=COMPLETED` post-lock and fails cleanly | |
| Duplicate activation | Same contract-row lock + `_LEGAL_TRANSITIONS` guard under the lock (`APPROVED → ACTIVE` only) | |
| Concurrent schedule modification | `InstallmentScheduleVersion` rows are immutable once created — there is nothing to "concurrently modify"; a reschedule attempt while another reschedule is in-flight is serialized by the same contract-row lock (rescheduling requires the lock to read the current `active_schedule_version_id` before writing a new one) | |
| Concurrent approval/rejection | `InstallmentContract.version` **optimistic** column, conditional `UPDATE installment_contracts SET status=..., version=version+1 WHERE id=... AND version=:expected` (Inventory's `adjustment_repository.py` pattern — the stronger of the two sibling conventions, chosen because approval/rejection is a low-contention, human-paced action where "fail fast with a clear conflict" beats holding a row lock across a request that might include human-latency approval-threshold lookups) | Zero rows updated → `InstallmentConcurrentModificationError` (409) — the losing request never silently overwrites (FR-INST-382) |
| Collection/write-off race | Same contract-row `FOR UPDATE` lock — `writeoff()` re-checks `status == DEFAULTED` under the lock; a collection that completed the contract first (bringing status to `COMPLETED`) causes a concurrently-arriving `writeoff()` to fail the status check cleanly, never both succeeding (BR-INST-011/013 jointly protected) | |
| Collection/reversal race | Same contract-row lock serializes both operations against the same contract | |
| Negative remaining balance | Structurally impossible: outstanding is always computed as `scheduled_amount - sum(non-reversed allocation references)` **under the same lock** that gates new allocation-reference writes — no code path can write an allocation exceeding the just-computed outstanding, and the lock prevents a second writer from computing a stale outstanding value | FR-INST-384 |
| **[CORRECTED]** Premature completion (a collection zeroing schedule outstanding races a late-charge post/waiver on the same contract) | Same `FOR UPDATE` lock on `InstallmentContract`, now taken by **both** collection/settlement and late-charge post/waiver ([§21](#21-transaction--atomicity-boundaries)) — `InstallmentOutstandingService.assert_zero_outstanding()` ([§9.3](#93-corrected-authoritative-completion-guard--installmentoutstandingserviceassert_zero_outstanding)) always runs under this lock, so it can never observe a torn combination of "schedule just zeroed" and "late charge about to post/about to be waived" | BR-INST-010, [§31](#31-testing-strategy) Concurrency Test D |

**Why not optimistic locking everywhere?** Money-mutating sequences (collection, settlement, write-off) benefit from serializing the entire read-compute-write sequence under one lock, matching Accounting's own established pattern for the same class of problem. Low-contention, discrete state transitions (approve/reject) benefit from optimistic locking's better throughput and clearer conflict semantics for human-paced actions. Using both, purposefully, for the class of operation each suits — not "every technique simultaneously without reason" (meta-§14's explicit warning) — is the design.

---

## 20. Idempotency Strategy

No reusable idempotency-key infrastructure exists anywhere in the repository ([§2](#2-repository-findings)). This plan introduces **one new, Installments-scoped primitive** — the smallest viable new abstraction the spec's FR-INST-092/373/380-384 genuinely require, not a platform-wide change.

**[CORRECTED, correction pass]**: The original design's conflict-handling flow ("attempt `INSERT`, catch the unique violation, fetch the existing row") is unsafe under PostgreSQL — a unique-constraint violation aborts the current transaction; every statement after it (including the fetch it described) would fail with `InFailedSqlTransaction` unless a `SAVEPOINT` were used to recover, and repository inspection found **zero production use of `session.begin_nested()`/`SAVEPOINT` anywhere in this codebase** (the only occurrence at all is `tests/conftest.py`'s test-isolation fixture — not a pattern to copy into application code) and **zero use of `INSERT...ON CONFLICT`/`postgresql.insert()` in application code either** (only inside raw-SQL Alembic migrations). The corrected design below uses `INSERT...ON CONFLICT DO NOTHING...RETURNING`, which **never raises an error** for the conflicting case — eliminating the aborted-transaction problem by construction rather than by recovering from it.

### 20.1 Schema [CORRECTED]

```
installment_idempotency_keys
  id                  UUID PK
  company_id          UUID NOT NULL
  operation           VARCHAR(40) NOT NULL   -- 'contract.activate'|'collection.create'|
                                              -- 'settlement.execute'|'collection.reverse'|
                                              -- 'contract.reschedule'|'contract.cancel'|
                                              -- 'contract.default'|'contract.writeoff'
  idempotency_key     VARCHAR(100) NOT NULL  -- client-supplied (header: Idempotency-Key)
  request_fingerprint VARCHAR(64) NOT NULL   -- SHA-256 of normalized request payload
  status              VARCHAR(15) NOT NULL   -- 'IN_PROGRESS'|'COMPLETED'  ('FAILED' removed — see rationale below)
  result_payload      JSONB NULL             -- stored response, replayed verbatim on repeat
  contract_id         UUID NULL              -- scoping/debug convenience
  created_at          TIMESTAMPTZ NOT NULL
  completed_at        TIMESTAMPTZ NULL
```
`UNIQUE (company_id, operation, idempotency_key)` — this is `uq_installment_idempotency_company_op_key` ([§7.2](#72-constraints)), the exact index the `ON CONFLICT` clause below targets.

**`FAILED` removed as dead schema.** The original plan listed `FAILED` but also stated "failed transactions roll back the idempotency row entirely" — those two statements are contradictory: if the whole transaction (including the idempotency row) rolls back on failure, `FAILED` can never actually be durably persisted or observed by any reader, in or outside the transaction. Tracing the actual lifecycle confirms this: the row is inserted `IN_PROGRESS` and, on success, updated to `COMPLETED` immediately before the one `db.commit()`; on any failure, the whole transaction — including that `IN_PROGRESS` row — rolls back and the key becomes available again. There is no code path that ever commits a `FAILED` row. Per the correction's explicit instruction not to retain unused state, it is removed from the CHECK constraint rather than kept "for completeness." If the business later wants a durable record of failed attempts, that is a deliberate, separate design (e.g. a side audit-log entry written in its own short transaction after the main rollback) — not a silent addition to this table's lifecycle, and not needed by any current spec requirement.

**Is `IN_PROGRESS` itself ever durably observable by another transaction?** No, and this is the mechanism's key safety property, not a gap: under PostgreSQL's default `READ COMMITTED` isolation, an uncommitted row is invisible to every other session. By the time any other transaction can see this row at all, it is either `COMPLETED` (the original transaction committed) or it does not exist (the original transaction rolled back). `IN_PROGRESS` is retained in the schema because it is a real, meaningful value *within* the owning transaction's own lifecycle (inserted, then flipped to `COMPLETED` right before commit) — it is not unused, it is simply never cross-transaction-readable, which is exactly the guarantee the correction asked for.

### 20.2 Flow [CORRECTED — `INSERT...ON CONFLICT DO NOTHING...RETURNING`]

```python
# Step 1 — reservation attempt. This statement NEVER raises IntegrityError:
# ON CONFLICT DO NOTHING guarantees a clean, non-erroring outcome either way,
# so the surrounding transaction is never put into an aborted state by this call.
stmt = (
    pg_insert(InstallmentIdempotencyKey)
    .values(
        company_id=company_id, operation=operation, idempotency_key=key,
        request_fingerprint=fingerprint, status="IN_PROGRESS",
        contract_id=contract_id, created_at=utcnow(),
    )
    .on_conflict_do_nothing(
        index_elements=["company_id", "operation", "idempotency_key"]
    )
    .returning(InstallmentIdempotencyKey.id)
)
reserved_id = db.execute(stmt).scalar_one_or_none()

if reserved_id is not None:
    # This request won the reservation — proceed with the business operation in
    # the SAME transaction; it ends with UPDATE ... SET status='COMPLETED',
    # result_payload=... immediately before the single db.commit() (§21).
    ...
else:
    # A conflicting row already exists. If the other request's INSERT is still
    # uncommitted, THIS statement blocks (standard PostgreSQL unique-index
    # insert behavior — the second inserter waits on the first's row-level lock
    # until it commits or rolls back) BEFORE returning control here. Because of
    # that block, by the time this branch actually runs, the other transaction
    # has ALWAYS already resolved one way or the other — there is no normal
    # timing window in which this SELECT can observe a row that is still
    # IN_PROGRESS from another session (PostgreSQL READ COMMITTED never makes
    # an uncommitted row visible to a different session in the first place; the
    # unique-index block is what removes the *other* possible race, "read
    # before the writer even started"). No explicit `SELECT ... FOR UPDATE` is
    # needed to achieve this serialization; it is inherent to how a unique
    # index handles a concurrent conflicting insert.
    existing = db.execute(
        select(InstallmentIdempotencyKey).where(
            InstallmentIdempotencyKey.company_id == company_id,
            InstallmentIdempotencyKey.operation == operation,
            InstallmentIdempotencyKey.idempotency_key == key,
        )
    ).scalar_one()
    if existing.status == "COMPLETED" and existing.request_fingerprint == fingerprint:
        return existing.result_payload   # replay — no reprocessing (FR-INST-381)
    elif existing.status == "COMPLETED":
        raise ConflictException("idempotency key reused with a different payload")
    else:
        # [CORRECTED — defensive branch only, NOT the normal concurrency
        # contract] existing.status == "IN_PROGRESS" here would mean this
        # SELECT observed a row from another session's still-open transaction —
        # something READ COMMITTED visibility rules and the unique-index block
        # above should make impossible under normal operation. This branch is
        # retained purely as a defensive guard against an unforeseen isolation-
        # level change or a future refactor that breaks the single-session-per-
        # request assumption, NOT as a documented, expected response a client
        # should ever normally receive. It must never be presented to a caller
        # as "the usual meaning of a 409" — see §20.3.
        raise ConflictException("unexpected: reservation row visible but not resolved")
```

### 20.3 Concurrent-duplicate correctness — explicit PostgreSQL behavior [CORRECTED — clarified primary vs. defensive outcomes]

**The two outcomes below are the entire normal concurrency contract.** There is no third "request already in progress" outcome under normal operation — it was incorrectly presented as a primary expected outcome in the prior correction pass and is corrected here.

```text
Request A wins reservation (INSERT ... ON CONFLICT succeeds, reserved_id set)
        ↓
Request B's INSERT for the same key blocks at the unique-index conflict
        ↓
A resolves
        │
        ├── A commits (business operation succeeded)
        │        ↓
        │   B's blocked INSERT unblocks, sees the now-committed row,
        │   inserts nothing (ON CONFLICT DO NOTHING), reserved_id is None
        │        ↓
        │   B reads A's COMPLETED row
        │        ├── same request_fingerprint  → replay stored result_payload (FR-INST-381)
        │        └── different request_fingerprint → 409 "idempotency key reused
        │                                              with a different payload"
        │
        └── A rolls back (business operation failed)
                 ↓
            B's blocked INSERT unblocks, finds no committed conflicting row,
            B's own INSERT succeeds, reserved_id is set
                 ↓
            B becomes the new owner of the request and executes normally
            — the key was never permanently stranded by A's failure
```

| Scenario | Outcome |
|---|---|
| A inserts `IN_PROGRESS` (uncommitted); B arrives with the same key before A commits | B's `INSERT...ON CONFLICT` **blocks** (does not error, does not proceed) until A's transaction resolves — standard PostgreSQL behavior for a second inserter racing a not-yet-committed conflicting unique-index entry |
| A commits successfully | B's blocked insert unblocks, sees the now-committed conflict, inserts nothing (`ON CONFLICT DO NOTHING`), `reserved_id is None` → B reads A's `COMPLETED` row and either replays (fingerprint match) or 409s (mismatch) — **exactly one financial effect occurred (A's)** |
| A's transaction fails and rolls back (including its `IN_PROGRESS` row) | B's blocked insert unblocks, finds no conflicting committed row, its own `INSERT` **succeeds**, `reserved_id` is set → B proceeds fresh, as the first genuine attempt — **the key is never permanently stranded by a failed attempt** |
| Same key, same payload, replayed after A's success | Fingerprint matches → stored `result_payload` returned verbatim, zero reprocessing, zero new financial effect |
| Same key, different payload | Fingerprint mismatch → `409 Conflict`, clear and distinct from the defensive branch below |
| **[Defensive, not normal]** `existing.status == "IN_PROGRESS"` observed by another session's `SELECT` | Should never occur under READ COMMITTED + the unique-index block above; retained only as a defensive guard, surfaced as a distinct, clearly-labeled 409 that is never described to API clients as an ordinary "try again" response |

All required guarantees (exactly one execution; replay on match; conflict on mismatch; no duplicate financial write under concurrency; no permanently stranded key after failure) hold as direct, provable consequences of PostgreSQL's own MVCC/unique-index locking semantics for the **two normal outcomes** above — none of them depend on explicit application-level locking, a savepoint, a retry loop, or cross-transaction visibility of an `IN_PROGRESS` row.

### 20.4 Design rationale

- **Business-key + fingerprint, not a bespoke token scheme** — matches the platform's one existing analogous case (`RecurringJournalInstance`'s unique-constraint-on-business-key pattern), scoped by `(company_id, operation, key)` rather than a global key namespace, per FR-INST-092's requirement that idempotency be operation-scoped and tenant-scoped.
- **`INSERT...ON CONFLICT DO NOTHING...RETURNING` over a bare unique-violation catch** [CORRECTED] — the bare-catch approach the original plan proposed is unsafe in PostgreSQL (aborts the transaction); `ON CONFLICT DO NOTHING` never raises for the conflicting case, so no `SAVEPOINT`/recovery logic is ever needed. This is a deliberate, first-of-its-kind use of a construct with no prior precedent in this codebase's application code — chosen because it is the objectively correct tool for "safely reserve a unique row without erroring on contention," not because of stylistic preference (see ADR-INST-08 for the full alternatives analysis, including why a savepoint-based approach was rejected despite being *option B* in scope).
- **Same transaction as the business write** — the idempotency row's fate (`COMPLETED` vs. rolled back entirely) is atomically tied to the business operation's fate, satisfying "no partially applied state" ([§22](#22-failure--recovery-design)).
- **No expiration/retention policy** is defined by spec, so none is implemented (avoiding a fabricated numeric TTL — matching the same "don't fabricate what the spec doesn't require" discipline the spec itself applies to NFRs, Assumption A8).
- Applied to exactly the 8 commands spec names as high-risk: `activation`, `collection`, `settlement`, `reversal`, `rescheduling`, `cancellation`, `default`, `write-off`.

---

## 21. Transaction / Atomicity Boundaries

Every high-risk workflow is **one Python-level unit of work, one `db.commit()`**, following the platform's dominant discipline exactly (PostingEngine: "every state-changing method performs exactly ONE `db.commit()`"). Cross-module calls into Accounting use `stage_direct_posting()`/`finalize_and_publish()` specifically so Installments' own rows can be added via `flush()` between them, landing in the **same** database transaction/commit as the Accounting write — this is the mechanism, not distributed-transaction coordination (both modules share one PostgreSQL connection/session per request; there is no cross-service network boundary to span).

| Workflow | Atomic unit (all via `flush()`, one final `commit()`) |
|---|---|
| **Activation** [**CORRECTED — commit ownership frozen**] | validate eligibility → (if down payment required) `PaymentService.stage_customer_payment()` + `AllocationEngine.stage_allocation()` (flush only, [§12.3.1](#1231-activation--down-payment-collection-settlement-payment--paymentservice--allocationengine)) → `ScheduleEngine.generate()` → persist `InstallmentScheduleVersion`+lines → reconciliation check (BR-INST-005) → status `APPROVED→ACTIVE` → `InstallmentAuditLog` → outbox event row → `PaymentService.finalize_customer_payment()` then `AllocationEngine.finalize_allocation()` called **last** — **the first of these is the actual commit** |
| **Collection** [**CORRECTED — commit ownership frozen**] | idempotency reservation → `FOR UPDATE` lock → outstanding calculation → `PaymentService.stage_customer_payment()` + `AllocationEngine.stage_allocation()` (flush only) → `InstallmentAllocationReference` rows → (if schedule outstanding=0) `InstallmentOutstandingService.assert_zero_outstanding()` → only if it passes, `complete()` → `InstallmentAuditLog` → outbox event → idempotency row → `PaymentService.finalize_customer_payment()` then `AllocationEngine.finalize_allocation()` called **last** — **the first of these is the actual commit** |
| **Settlement** | quote generation is its own read-only unit (no commit needed beyond the audit record for the quote itself); execution reuses the Collection atomic unit at the settlement amount |
| **Reversal** [**CORRECTED — commit ownership frozen, no Accounting-side change**] | idempotency reservation → lock → new `InstallmentAllocationReference(is_reversal=true)` rows → recompute contract/schedule due-state (derived, no write needed) → `InstallmentAuditLog` → outbox event → idempotency row → **then**, last, `PaymentService.reallocate_payment(new_allocation_lines=[])` [+ `cancel_payment()` if full reversal] — **its first internal commit is the actual commit**, per [§12.3.2](#1232-collection-reversal--cancellation-with-financial-reversal--reallocate_payment--cancel_payment)'s staging-order guarantee |
| **Cancellation** [**CORRECTED — commit ownership frozen, no Accounting-side change**] | lock → (if financial activity exists) status transition + audit staged **first** → **then**, last, the reversal sub-unit (same staging-order call as Reversal above) — **its first internal commit is the actual commit** |
| **Default** | lock → status transition (no Accounting call) → `InstallmentAuditLog` → outbox event → **commit** |
| **Cure** | lock → policy check → status transition → `InstallmentAuditLog` → outbox event → **commit** |
| **Late charge** [**CORRECTED — contract-row lock added, commit ownership frozen**] | `FOR UPDATE` lock on the parent `InstallmentContract` (the same lock collection/settlement/write-off take — this is what makes Concurrency Test D's serialization guarantee true, [§31](#31-testing-strategy)) → policy check (charge enabled, not already charged for this occurrence) → `AccountsReceivableService.stage_adjustment()` (flush only — GL + `ARTransaction` + ledger recompute staged, **not committed**, [§12.2](#122-corrected-general-commit-ownership-contract-for-cross-module-accounting-calls)) → `installment_late_charges` row staged (both `accounting_journal_entry_id` and `accounting_ar_transaction_id` set) → `InstallmentAuditLog` staged → outbox event row staged → `AccountsReceivableService.finalize_adjustment()` called **last**, by Installments — **this single call is the commit** |
| **Late-charge waiver** [**CORRECTED — contract-row lock added, commit ownership frozen**] | `FOR UPDATE` lock on the parent `InstallmentContract` (same reason as above) → `installment_late_charges.waived_at/by/reason` staged → `InstallmentAuditLog` staged → outbox event row staged → `AccountsReceivableService.reverse_adjustment()` called **last**, by Installments (internally stages the AR-side zeroing/ledger recompute, then calls `PostingEngine.reverse()`) — **`reverse()`'s single commit is the commit** for everything staged above, only if the charge was actually posted |
| **Write-off** [**CORRECTED — commit ownership frozen**] | lock → `AccountsReceivableService.stage_write_off()` (flush only) → status transition → `InstallmentAuditLog` → outbox event → `AccountsReceivableService.finalize_write_off()` called **last** — **this is the actual commit**, per [§12.3.3](#1233-write-off--accountsreceivableserviceconfirm_write_off) |
| **Rescheduling** | lock → maker-checker check → `ScheduleEngine.generate()` (remaining obligation only) → new `InstallmentScheduleVersion`+lines → supersede prior version → `active_schedule_version_id` update → `InstallmentAuditLog` → outbox event → **commit** |

**No distributed-transaction complexity is introduced** — every step above executes against the same SQLAlchemy `Session`/DB connection within one FastAPI request, consistent with meta-§13's explicit instruction to avoid this unless repository reality requires it (it does not: Accounting and Installments share one PostgreSQL database).

**[CORRECTED]** Every "idempotency reservation" step above is now specifically the `INSERT...ON CONFLICT DO NOTHING...RETURNING` statement from [§20.2](#202-flow-corrected--insertonconflict-do-nothingreturning), executed as the **first** statement of the transaction, before any other business writes — this ordering matters: if the reservation is not won (`reserved_id is None`), the transaction can cleanly stop with a 409 or a replayed result without ever having staged any business-side writes to roll back.

---

## 22. Failure / Recovery Design

| Failure condition | Handling |
|---|---|
| Accounting posting failure (any `PostingEngine`/`AccountsReceivableService` exception) | Propagates up, transaction rolls back in full — no Installments row is left committed without its Accounting counterpart (FR-INST-273/390) |
| Locked/closed fiscal period | `PostingValidationError` → mapped to `InstallmentFiscalPeriodLockedError` (422, documented code `PERIOD_LOCKED`) — clear, specific error, not generic (FR-INST-393) |
| Schedule generation failure (e.g. degenerate final line) | `DegenerateScheduleError` raised **before** any persistence — activation never partially proceeds |
| Invalid configuration | `ValidationException` (422) at the service boundary before any state change |
| Stale/conflicting contract version | `InstallmentConcurrentModificationError` (409) from the optimistic-lock conditional update — no state change occurs |
| Disabled module (origination only) | `InstallmentsNotEntitledError` (403, code `FEATURE_DISABLED`) — mirrors CRM's existing client-facing error shape exactly, for frontend-classification reuse ([§24](#24-frontend-architecture)) |
| Suspended tenant | `CompanySuspendedError` — raised upstream by `get_current_company_member`, Installments' own code never reached |
| Duplicate request (idempotency) | **[CORRECTED, further clarified]** `INSERT...ON CONFLICT DO NOTHING` resolves the reservation attempt without ever raising `IntegrityError` or aborting the transaction ([§20.2](#202-flow-corrected--insertonconflict-do-nothingreturning)). Under normal operation there are exactly two outcomes for a concurrent duplicate, both only reachable **after** the first request's transaction has resolved (PostgreSQL blocks the second inserter until then): 200/201 with the stored result replayed (same payload), or 409 "different payload" (different payload). A third, purely defensive 409 exists only for the theoretically-unreachable case of observing another session's still-`IN_PROGRESS` row ([§20.3](#203-concurrent-duplicate-correctness--explicit-postgresql-behavior-corrected--clarified-primary-vs-defensive-outcomes)) — never silent reprocessing, never a transaction left unusable mid-request |
| Cross-tenant reference | `NotFoundException` (404) — indistinguishable from non-existence (BR-INST-015) |
| Unavailable dependency (Accounting call raises an unexpected exception) | Propagates as a 5xx `InfrastructureException`-derived error; transaction rolls back; **no partial state** — this is structurally guaranteed by the single-commit discipline, not by explicit compensating logic |

**No half-completed financial workflow can remain**: because every workflow in [§21](#21-transaction--atomicity-boundaries) is exactly one `db.commit()`, a failure at *any* step — Installments-side or Accounting-side — rolls back the entire unit of work, including the sequence-number increment, the idempotency reservation, and the audit stage. This is the same guarantee `PostingEngine` already provides for its own callers; Installments inherits it by using the same session/transaction rather than by building new compensating-transaction logic.

**[CORRECTED, further frozen]** This guarantee now explicitly covers the late-charge path end-to-end, not just its Accounting-internal half: `stage_adjustment()` stages the GL posting, the `ARTransaction` insert, and the `CustomerLedger` recompute (flush only); Installments then stages `InstallmentLateCharge`/audit/outbox into the **same** session; only `finalize_adjustment()` — called last, by Installments — commits all of it together ([§12.1](#121-corrected-late-charge-ar-truth--repository-re-inspection-and-resolution)/[§12.2](#122-corrected-general-commit-ownership-contract-for-cross-module-accounting-calls)). A fiscal-period-lock failure, any other `PostingValidationError`, or any failure while staging Installments' own rows now correctly leaves **zero** trace in any of the six places (GL, `ARTransaction`, ledger, `InstallmentLateCharge`, `InstallmentAuditLog`, outbox) — proven by the forced-failure integration test in [§12.2](#122-corrected-general-commit-ownership-contract-for-cross-module-accounting-calls).

**[CORRECTED, final correction pass — generalized to every workflow]** The identical guarantee now applies, end-to-end, to every other Installments↔Accounting integration point, per [§12.3](#123-final-correction-pass-generalized-commit-ownership-across-every-installmentsaccounting-workflow)'s method-by-method re-verification: down payment, collection, and settlement payment (new `stage_customer_payment()`/`finalize_customer_payment()` + `stage_allocation()`/`finalize_allocation()`), and write-off (new `stage_write_off()`/`finalize_write_off()`, closing a **three**-separate-commit defect that had never been fixed before this pass). Collection reversal and cancellation-with-reversal reach the same guarantee through a different, equally rigorous mechanism — no Accounting-side code change, but a strict staging-order discipline (Installments' own rows always flush *before* the first Accounting call in the sequence) — with one honestly-documented, narrower residual case: because `reallocate_payment()`/`cancel_payment()` are two separate calls, a failure strictly *between* them can leave a reversal partially complete (un-allocated but not yet cancelled) — a fully-explainable, non-corrupt intermediate Accounting state, not a truth divergence, and one the idempotency key's resume logic already handles ([§12.3.2](#1232-collection-reversal--cancellation-with-financial-reversal--reallocate_payment--cancel_payment)).

---

## 23. API Architecture

Mounted at `/api/v1/companies/{company_id}/installments`, `dependencies=[Depends(get_current_company_member)]` (no blanket entitlement gate — see [§15](#15-entitlement-architecture)). `installments_admin_router` mounted alongside for the enable/disable/status endpoints. Standard envelope (`StandardResponse[T]`/`ErrorResponse`/`PaginatedResponse[T]`) throughout. Explicit command endpoints for every lifecycle transition — no generic `PATCH /contracts/{id}` status mutation anywhere (meta-§24's explicit instruction, and matches FR-INST-106).

| Group | Method + conceptual path | Permission | Op class | Idempotency | Key failure codes |
|---|---|---|---|---|---|
| **Configuration** | `GET/PUT /config` (+ `/config/branches/{branchId}`) | `installments.config.manage` | ADMIN | No | 422 validation |
| **Plans/Templates** | `GET/POST /plans`, `GET/PATCH /plans/{id}`, `POST /plans/{id}/deactivate` | `installments.plan.manage` | ORIGINATION | No | 409 (name conflict) |
| **Eligibility** | `GET /eligibility?sales_invoice_id=` | `installments.contract.create` | ORIGINATION | No | 422 (ineligible, with reason) |
| **Quote/Preview** | `POST /quotes` (no persistence) | `installments.contract.create` | ORIGINATION | No | 422 |
| **Contracts** | `GET /contracts`, `GET /contracts/{id}`, `POST /contracts` (DRAFT) | `.view` / `.create` | READ / ORIGINATION | No (create is not "high-risk" per spec's 8-command list — DRAFT has no financial effect) | 404, 422 |
| **Submission/Approval/Rejection** | `POST /contracts/{id}/submit`, `POST /contracts/{id}/approve`, `POST /contracts/{id}/reject` | `.create` (submit) / `.approve` (approve+reject) | ORIGINATION | No | 422 (self-approval), 409 (bad transition) |
| **Activation** | `POST /contracts/{id}/activate` | `.activate` | ORIGINATION | **Yes** | 409 (down payment insufficient), 422 (period locked) |
| **Schedules** | `GET /contracts/{id}/schedule` (current version), `GET /contracts/{id}/schedule/versions/{v}` | `.view` | READ | No | 404 |
| **Collections** | `POST /contracts/{id}/collections` | `.collection.create` | SERVICING | **Yes** | 409 (over-collection guard), 422 (period locked) |
| **Reversals** | `POST /collections/{id}/reverse` | `.collection.reverse` | SERVICING | **Yes** | 409 |
| **Settlement Quotes** | `POST /contracts/{id}/settlement/quote` (no persistence beyond audit) | `.settlement.execute` | SERVICING | No | 422 |
| **Settlement Execution** | `POST /contracts/{id}/settlement/execute` | `.settlement.execute` | SERVICING | **Yes** | 409 (stale quote) |
| **Rescheduling** | `POST /contracts/{id}/reschedule` | `.reschedule` | ORIGINATION | **Yes** | 422 (restructuring rejected — FR-INST-202) |
| **Cancellation** | `POST /contracts/{id}/cancel` | `.cancel` | ORIGINATION | **Yes** | 409 |
| **Default** | `POST /contracts/{id}/default` | `.default` | ORIGINATION | **Yes** | 409 |
| **Cure** | `POST /contracts/{id}/cure` | `.cure` | SERVICING | No (not in spec's 8-command idempotency list, but low-risk to add — **not added**, smallest viable change) | 422 (policy not enabled) |
| **Write-Off** | `POST /contracts/{id}/writeoff` | `.writeoff` | ORIGINATION | **Yes** | 403 (insufficient permission), 409 |
| **Reports/Dashboard** | `GET /reports/{report-type}`, `GET /dashboard` | `.report.view` | READ | No | — |
| **Documents/Statements** | `GET /contracts/{id}/documents/agreement`, `.../schedule`, `.../settlement-quote`, `GET /customers/{id}/statement` | `.view` | READ | No | — |
| **Admin** | `GET /installments/status`, `POST /installments/enable`, `POST /installments/disable` | rank-based (`ADMIN_RANK`, matching CRM's `admin_router`) | ADMIN | No | — |

Every endpoint: input validated via Pydantic schema → `require_authenticated` + `get_current_company_member` → inline `InstallmentAccessPolicy.authorize()` + `user_has_installments_permission()` → service call → response schema. 4xx for business-rule violations, 5xx for infrastructure, internal detail never leaked (Constitution §21, reusing the existing global exception handler — no new handler needed).

**[CORRECTED, further clarified] Idempotent-endpoint response semantics** (the 8 endpoints marked "Yes" under Idempotency): a request whose `Idempotency-Key` reservation succeeds returns the normal success status code (200/201) for that operation. A request replaying an already-`COMPLETED` key with a matching payload also returns the **original** success status code with the **original, stored** response body — a replay is never distinguishable in status code from the first successful call, only via the response body being byte-identical (FR-INST-381's "returning the original result for a repeated key"). Under normal operation, a duplicate request only ever reaches a decision **after** the first request's transaction has already resolved (PostgreSQL blocks the second reservation attempt until then, per [§20.3](#203-concurrent-duplicate-correctness--explicit-postgresql-behavior-corrected--clarified-primary-vs-defensive-outcomes)) — so a conflicting-payload duplicate returns `409 Conflict` with error code `IDEMPOTENCY_PAYLOAD_MISMATCH`. A separate, purely defensive `409 IDEMPOTENCY_UNEXPECTED_STATE` code exists for the theoretically-unreachable "observed another session's still-in-progress row" case, but is never documented to API clients as an ordinary "retry" response.

---

## 24. Frontend Architecture

Consistent with frontend research findings — flat routing (not `companies/[companyId]/...`), TanStack Query (the modern convention, not the legacy manual-fetch pattern CRM/Accounting/Sales still use), stacked bordered `<section>` cards (no `Tabs` component exists), `react-hook-form` + `zod`.

### 24.1 Routes

```
frontend/src/app/(protected)/(installments)/
  layout.tsx                          — pass-through, matches every other module's placeholder
  installments-dashboard/page.tsx     — KPI cards, due/overdue summary
  contracts/page.tsx                  — list + filters + pagination
  contracts/new/page.tsx              — quote → draft creation form (RHF + zod)
  contracts/[contractId]/page.tsx     — CONTRACT DETAIL — the operational center
  contracts/[contractId]/collect/page.tsx     — record-collection form
  contracts/[contractId]/reschedule/page.tsx  — reschedule form
  approvals/page.tsx                  — approval queue
  plans/page.tsx                      — templates list/CRUD
  configuration/page.tsx              — tenant policy config
  reports/page.tsx                    — contract register / collection / overdue / aging / settlement / write-off reports
```

### 24.2 Contract Detail page — sections (stacked `<section>` cards, mirroring the Tenant Detail page pattern)

Header (contract number + status badge + lifecycle action buttons, each gated by `useHasInstallmentsPermission`) → Summary cards (customer, invoice ref, totals, next due) → **Terms** section → **Schedule** section (table, current version, with a "view prior version" link if superseded versions exist) → **Payments** section (collection history + allocation explanation) → **Delinquency** section (overdue amount, days-overdue, aging bucket — visible only if applicable) → **Audit/History** section → **Documents** section (agreement/schedule/statement download links).

### 24.3 Supporting infrastructure (new files, one-to-one mirrors of existing precedents)

| New file | Mirrors |
|---|---|
| `src/lib/api/installments.ts` | `src/lib/api/crm.ts` (typed client, hand-mirrored from backend Pydantic schemas) |
| `src/hooks/installments/use{Contract,Contracts,CreateContract,RecordCollection,...}.ts` | `src/hooks/companies/useCompany.ts` (real `useQuery`/`useMutation`, query keys `['contract', id]`/`['contracts', filters]`) |
| `src/hooks/installments/useInstallmentsPermissions.ts` + `useHasInstallmentsPermission()` | `src/hooks/crm/useCrmPermissions.ts` — fail-safe (hide on load failure, never assume allowed) |
| `src/components/installments/apiErrors.ts` (`classifyInstallmentsError`) + `InstallmentsStateBanner.tsx` | `src/components/crm/apiErrors.ts` + `CrmStateBanner.tsx` — classifies `403 FEATURE_DISABLED` distinctly from ordinary `403 forbidden` |
| `src/components/installments/StatusBadge.tsx` | `src/components/crm/StatusBadge.tsx` — per-module status-color map, not a shared design-system `Badge` (none exists) |
| `src/schemas/installments.ts` (zod schemas) | `src/schemas/users-roles.ts` |

### 24.4 Entitlement-disabled UI behavior (meta-§26)

Because the backend policy is operation-class-aware ([§15](#15-entitlement-architecture)), the frontend does **not** hide the whole module when disabled:
- `contracts/[contractId]/page.tsx` and its collection/reversal/settlement actions remain fully reachable and functional (backend permits SERVICING).
- `contracts/new/page.tsx`, `plans/page.tsx`, `configuration/page.tsx` render `InstallmentsStateBanner`'s `featureDisabled` variant in place of their form/list content when a `403 FEATURE_DISABLED` is classified, with copy distinguishing this from ordinary CRM-style "module not enabled" (since here it specifically means "no *new* business, existing contracts still work").
- No route-level redirect and no nav-level hiding (there is no nav-gating precedent to extend — Sidebar doesn't yet list any business module, per frontend research §5) — gating happens per-page/per-action, exactly where the backend's `InstallmentOperationClass` boundary falls.
- Backend remains authoritative in all cases — the frontend banner is UX guidance, never the enforcement point (meta-§25's explicit reminder).

### 24.5 Testing

Jest `renderHook` + mocked api-client (matching `useCompany.test.ts`) for every new hook. Playwright E2E specs (matching `t220-suspension-flow.spec.ts`'s create→action→assert-state, two-browser-context pattern) for: standard contract lifecycle (quote→approve→activate→collect→complete), partial collection, overdue read, early settlement, disabled-entitlement servicing, tenant isolation, Platform Admin/support-access boundary.

---

## 25. Reporting / Query Architecture

Per FR-INST-360–362 and meta-§27's explicit instruction to distinguish contractual data from authoritative financial data:

| Report | Source of truth | Notes |
|---|---|---|
| Contract register | Installments (`installment_contracts` + terms snapshot) | Pure Installments data |
| Collection report | **Accounting** (`Payment`/`PaymentAllocationLine`, filtered via `installment_allocation_references` join) | Installments never invents a competing "amount collected" figure |
| Due / Overdue report | Installments schedule lines + Accounting allocation sums, computed at read time (same derivation as [§10](#10-schedule-engine)/[§9](#9-installment-lifecycle-architecture)'s due-state logic) | No materialized "status" column to drift from truth |
| Aging report | **Accounting's `AgingCalculator._bucket_for()` bucket definitions, reused conceptually** (same 6 buckets, same day-count logic) — a module-local `InstallmentAgingCalculator` free function, since Installments schedule lines are not literal `ARTransaction` rows and thus can't call Accounting's calculator directly, but must replicate its exact bucket boundaries per spec Assumption A7 | Prevents "two truths for the same customer" (spec's own named risk) |
| Customer statement | Installments schedule + Accounting payment history, composed read-only | Document, not a mutation ([§27](#27-documents--statements)) |
| Settlement report | Installments (`SETTLED` audit events + contract closure data) | |
| Default/write-off report | Installments (`defaulted_at`/`written_off_at` + audit) cross-checked against Accounting's `ARTransaction.status=WRITTEN_OFF` for the write-off figure specifically | Write-off *amount* always sourced from Accounting, never re-derived independently |
| Plan/template performance | Installments only (contract counts/outcomes grouped by `plan_template_id`) | |
| Dashboard KPIs | Mix per FR-INST-080 — computed once per request from the same non-double-counting derivation used by Due/Overdue (an amount crossing into overdue is excluded from "due this month," per FR-INST-081) | No separate KPI-cache table in Epic 10 — see [§28](#28-background-processing) for the only sanctioned exception (materialized *projection*, not truth) |

All list/report endpoints use `PaginatedResponse`/`PaginationParams`, tenant-scoped, no N+1 (batch-load allocation references per page of schedule lines rather than per-line queries).

---

## 26. Domain Events

Per ADR-INST-09 ([§40](#40-architecture-decision-records)), Installments publishes through the **transactional outbox** (`core/events/outbox.py`), not the non-durable in-process bus used by sibling business modules — the only mechanism that actually satisfies Constitution §49.

| Event | Producer | Consumers (future-ready; none required to exist in Epic 10) | Payload principles | Timing |
|---|---|---|---|---|
| `InstallmentContractActivated` | `InstallmentContractService.activate()` | Notifications (future), CRM (future activity mirroring), reporting refresh | `contract_id`, `company_id`, `customer_id`, `sales_invoice_id`, `contractual_total`, `installment_count`, `first_due_date` — no PII beyond IDs already public within the tenant | Same transaction/commit as activation |
| `InstallmentCollected` | `InstallmentCollectionService.record_collection()` | Notifications, CRM activity mirroring, future reporting | `contract_id`, `amount`, `allocation_summary` (line IDs + amounts, not raw payment PII) | Same transaction as collection |
| `InstallmentCollectionReversed` | `InstallmentCollectionService.reverse_collection()` | Notifications | `contract_id`, `reversed_allocation_reference_id`, `amount` | Same transaction |
| `InstallmentOverdue` | Emitted by an optional background job ([§28](#28-background-processing)) that scans for newly-overdue lines — **never** the sole source of overdue truth, purely a notification trigger | Notifications only | `contract_id`, `schedule_line_id`, `days_overdue` | Not transactional with any user-facing mutation (background-job emitted) |
| `InstallmentSettled` | `InstallmentSettlementService.execute()` | Notifications, reporting | `contract_id`, `settlement_amount` | Same transaction as settlement |
| `InstallmentDefaulted` | `InstallmentContractService.mark_defaulted()` | Notifications, future collections-prioritization AI consumer | `contract_id`, `reason` | Same transaction |
| `InstallmentCured` | `InstallmentContractService.cure()` | Notifications | `contract_id` | Same transaction |
| `InstallmentWrittenOff` | `InstallmentContractService.writeoff()` | Reporting | `contract_id`, `amount` | Same transaction |
| `InstallmentCancelled` | `InstallmentContractService.cancel()` | Notifications | `contract_id`, `reason` | Same transaction |

All names past-tense (Constitution §49). Idempotent consumption is the consumer's responsibility (each `OutboxRecord` carries a stable `event_id`/`aggregate_id`, matching the pattern already established by `users_roles`' outbox events). No sensitive tenant data (customer name, phone, address) is embedded in any payload — only IDs, amounts, and dates already visible to any tenant-scoped reader.

---

## 27. Documents / Statements

No PDF/document-rendering infrastructure exists anywhere in the backend ([§2](#2-repository-findings)) — Purchase's document services are unrelated and not reusable. Installments follows Accounting's own pattern for "receipt-like" output: **plain structured JSON**, not a rendered artifact, mirroring `AccountsPayableService.generate_remittance_advice()` exactly.

| Document | Implementation |
|---|---|
| Installment agreement | `InstallmentDocumentService.get_agreement(contract_id)` — assembles a read-only dict/schema from `terms_snapshot` + contract fields; returned as `StandardResponse[InstallmentAgreementView]` JSON |
| Payment schedule | `InstallmentDocumentService.get_schedule_document(contract_id)` — schedule lines + allocation summary, same JSON pattern |
| Settlement quotation | Reuses `InstallmentSettlementService.generate_quote()`'s output directly — already a structured, non-mutating read |
| Customer installment statement | `InstallmentDocumentService.get_customer_statement(customer_id)` — composes across all of a customer's contracts, read-only |

All four are **read-only with respect to contract/financial state** by construction (no service listed above calls a repository's write method). If the tenant needs an actual printable PDF, that is new infrastructure this Epic does not build (flagged, not silently assumed) — see [§39](#39-open-technical-decisions).

---

## 28. Background Processing

Per meta-§31's explicit instruction, correctness of overdue state **never** depends on a background job — every due-state read is computed live from schedule lines + allocation references + business date + grace policy ([§10](#10-schedule-engine)/[§25](#25-reporting--query-architecture)). No Celery/Redis is introduced (none exists in the platform today; adding one solely for Installments' convenience would violate meta-§40).

The **only** sanctioned background usage in Epic 10:
- An optional, low-priority scheduled job (reusing whatever the platform's existing task-running mechanism is — none was found in this inspection pass beyond `RecurringJournalService`'s own scheduling pattern, which itself does not describe a generic scheduler; if no generic scheduler exists platform-wide, this job is simply **deferred out of Epic 10's implementation scope** and left as a documented future addition, since spec explicitly says background jobs "MAY" be used, not "MUST") that scans for schedule lines that just crossed into `OVERDUE` and emits `InstallmentOverdue` events for notification purposes only. It reads the same live-computed due-state logic — it does not maintain a separate, potentially-stale status column.
- No materialized reporting-refresh table is introduced in Epic 10 (dashboard KPIs are computed per-request, per [§25](#25-reporting--query-architecture)) — if performance testing later proves this insufficient at scale, a materialized *projection* (clearly labeled non-authoritative, with a documented reconciliation job) would be a follow-up decision, not a Epic 10 commitment (avoiding premature optimization per Constitution §25).

---

## 29. Security Architecture

| Control | Implementation |
|---|---|
| Authentication | Every endpoint requires `require_authenticated` (existing JWT dependency) |
| RBAC | Every mutating (and `view`) endpoint checks a specific `installments.*` permission code inline — no endpoint relies on company-membership alone |
| Tenant isolation | `get_current_company_member` + `company_id`-scoped repositories at every layer ([§18](#18-multi-tenant--branch-isolation)) |
| Branch scoping | Reserved column, not yet an authorization boundary (no platform precedent exists to build against) |
| IDOR | `get_by_id_or_none(id, company_id)` → 404 for both "doesn't exist" and "exists in another tenant" — no differentiating signal (BR-INST-015) |
| Mass assignment | `company_id`/`branch_id`/ownership fields are **never** accepted from request bodies for creation — always derived from the authenticated path `company_id` and service-computed defaults; Pydantic input schemas simply omit these fields entirely (structural prevention, not a runtime strip) |
| Lifecycle authorization | Named service methods only, each independently permission-checked ([§9](#9-installment-lifecycle-architecture)/[§16](#16-rbac--maker-checker)) |
| Maker-checker | [§16.2](#162-maker-checker-implementation) |
| Platform Admin boundary | Structural exclusion — Installments is never imported by `platform_admin` ([§2](#2-repository-findings)) |
| Support-access boundary | Same structural guarantee; verified by a security test asserting `modules.platform_admin` contains no import of `modules.installments.models`/`.repositories` (a static-analysis-style test, mirroring the "statically-provable guarantee" language already used for Phase 12's own support-access tests) |
| Idempotency/replay | [§20](#20-idempotency-strategy) |
| Audit fail-closed | [§17](#17-audit-architecture) |
| Safe errors | Reuses the existing global exception handler — no new error-serialization path, no stack traces ever reach the client in production |
| Sensitive logging | `logger.info(..., extra={"company_id":..., "contract_id":...})` only — never customer PII, never full payment payloads, matching platform convention |
| Financial command validation | Every amount validated server-side (`Decimal`, `Field(gt=0)`) regardless of client-side validation; settlement/collection amounts re-validated against live outstanding under lock, never trusted from a stale client-side quote |

**Security-boundary tests to write** (mapped to [§31](#31-testing-strategy)): tenant-A-cannot-reach-tenant-B (contract by ID, by search, by collection, by settlement), Platform-Admin-cannot-read-contracts, active-`SupportAccessGrant`-cannot-read-contracts, missing-permission-denied per permission code, self-approval-denied, self-approval-denied-on-reject-too (explicitly covering the documented historical gap), cross-tenant-invoice-reference-rejected-at-creation.

---

## 30. Migration Strategy

Sequential, additive-only, starting at `062` (confirmed current head: `061_platform_support_access.py`). No migration ever rewrites existing Sales/Accounting data; no pre-existing sale is ever auto-converted into an installment contract (FR-INST-260, enforced simply by there being no such migration).

| # | Migration | Contents | Depends on |
|---|---|---|---|
| 062 | `installments_foundation` | `installments_feature_flags`, `installment_sequences`, `installment_configurations` | Company/tenant tables (existing) |
| 063 | `installments_templates` | `installment_plan_templates` | 062 |
| 064 | `installments_contracts` | `installment_contracts` (incl. the partial unique index) | 062, Sales `sales_invoices`/`customers` tables must already exist (they do) |
| 065 | `installments_schedule` | `installment_schedule_versions`, `installment_schedule_lines` (FK to 064) | 064 |
| 066 | `installments_allocation_and_charges` | `installment_allocation_references`, `installment_late_charges` (FK to 065) | 065 |
| 067 | `installments_idempotency` | `installment_idempotency_keys` | 062 |
| 068 | `installments_audit` | `installment_audit_log` | 062 |
| 069 | `installments_indexes` | Any composite/covering indexes not already created inline with their owning table ([§33](#33-performance--indexing)) | 062–068 |
| 070 | `installments_capability_seed` | `op.execute()` INSERT of the `installments` `Capability` row (idempotent `ON CONFLICT DO NOTHING`, mirroring `056_crm_permission_backfill.py`'s style) — schema-only otherwise, since `installments.*` permission codes are added to `users_roles/constants.py` (`INITIAL_PERMISSIONS`/`DEFAULT_ROLE_PERMISSIONS`) and take effect for **new** companies automatically via `RoleSeedService`, no migration needed for those | 058 (`platform_plans_entitlements`) |
| 071 | `installments_permission_backfill` **[CORRECTED — now mandatory, not conditional]** | Backfills the 16 `installments.*` permissions and their default system-role grants for companies created **before** Epic 10 ships — see [§30.1](#301-corrected-migration-071-is-mandatory-not-conditional) below for the repository-grounded justification and the exact per-role grant table. Pure `op.execute()` SQL, no app-code import, `ON CONFLICT DO NOTHING` on `permissions.id` and `role_permissions`' unique constraint, scoped to `role.is_system = true` — structurally identical to `056_crm_permission_backfill.py` | `installments.*` codes existing in `constants.py` (a code change landing in the same PR, not a migration) |

**Downgrade behavior**: every migration's `downgrade()` drops what it created, in reverse dependency order (070/071 delete backfilled `role_permissions` rows before `permissions`/`capabilities` rows, matching `056`'s child-before-parent convention).

### 30.1 [CORRECTED] Migration 071 is mandatory, not conditional

The original plan left migration 071 conditional ("only if backfilling... is desired"). Repository re-inspection of `RoleSeedService`, `constants.py`'s seeding mechanism, and `056_crm_permission_backfill.py` resolves this into one deterministic answer:

1. **Will existing companies automatically receive the new `installments.*` permission records?** No. `RoleSeedService.seed_all()` reads `INITIAL_PERMISSIONS`/`DEFAULT_ROLE_PERMISSIONS` from `constants.py` **only at company-creation time**. A company created before the `installments.*` entries land in `constants.py` will never see them appear on its own — there is no retroactive re-seed trigger anywhere in the codebase.
2. **Will their system roles automatically receive appropriate permission assignments?** No, for the same reason.
3. **Is a migration required?** **Yes — unconditionally.** This is not a judgment call; it is the same fact pattern `056_crm_permission_backfill.py` was written to solve, and CRM's own migration exists precisely because the answer to questions 1–2 was "no" for CRM too. There is no alternative deterministic automatic-backfill mechanism anywhere in the platform (no ORM event listener, no startup reconciliation job, no trigger) — a migration is the only mechanism this codebase actually uses for this exact problem.
4. **Which roles receive which permissions?** Following the exact per-role frozenset convention already established for CRM/Accounting (`_CRM_OWNER`, `_CRM_ADMIN`, `_CRM_MANAGER`, `_CRM_ACCOUNTANT`, `_CRM_SALESPERSON`, `_CRM_VIEWER` in `constants.py`), mapped onto spec §4's own Installments actor table rather than blindly copied from CRM's exact role-set (CRM granted zero permissions to `cashier`/`store-keeper`; Installments' spec explicitly names **Cashier/Collector** as an actor who records collections, so this plan deliberately deviates from CRM's "cashier gets zero" precedent where spec's own actor table requires it):

   | System role | Installments permissions granted |
   |---|---|
   | `owner` | all 16 (full authority, matching spec §4's "Company Owner/Admin") |
   | `admin` | all 16 |
   | `manager` | `contract.view`, `contract.approve`, `contract.reschedule`, `contract.cancel`, `contract.default`, `contract.writeoff`, `charge.waive`, `settlement.execute`, `contract.cure`, `report.view` (matches spec §4's "Approver (Sales Manager/Finance Manager)") |
   | `accountant` | `contract.view`, `collection.reverse`, `settlement.execute`, `report.view` (matches spec §4's "Accountant/Finance User" — consumes installment-driven accounting events, does not originate contracts) |
   | `salesperson` | `contract.view`, `contract.create`, `plan.manage` (view-only on plans is implied by `contract.view`; create/edit of templates reuses `salesperson`'s existing CRM-adjacent authoring role) — matches spec §4's "Sales/Installment Officer" |
   | `cashier` | `contract.view`, `collection.create` **[deliberate deviation from CRM's zero-grant precedent, justified by spec §4's explicit Cashier/Collector actor definition]** |
   | `store-keeper` | none — no relevance to Installments, matching CRM's own precedent for this role |
   | `viewer` | `contract.view`, `report.view` (matches spec §4's "Auditor/Read-Only User") |

   `config.manage` is granted only to `owner`/`admin` (tenant-policy authority), consistent with every other module's treatment of `*.settings.manage`-class permissions.
5. **How will custom roles behave?** Unaffected. `056`'s backfill SQL filters `WHERE r.is_system = true` — the identical filter is used here, so no custom (tenant-defined) role receives any new grant automatically.
6. **Must custom roles remain unchanged until a tenant admin explicitly grants Installments permissions?** Yes — this is the existing, unbroken platform policy (a role is only as privileged as what was explicitly assigned to it), and migration 071 does not touch `role_permissions` rows for any `role.is_system = false` row, by construction of the `WHERE` clause above.

**Idempotency**: identical to `056` — `ON CONFLICT DO NOTHING` on `permissions.id` (PK) and on `role_permissions`' `(role_id, permission_id)` unique constraint means re-running this migration produces zero duplicate rows and never removes an existing grant.
**No existing permission is ever removed or reset** — the migration only ever `INSERT`s, never `DELETE`s or `UPDATE`s, matching `056`'s own scope exactly.

**No production-safe concurrent-index concerns beyond the platform's existing convention** — no migration in this list creates an index on a pre-existing, already-large table (`installment_*` tables are all new and empty at migration time), so `CREATE INDEX CONCURRENTLY` is not required (unlike, hypothetically, adding an index to `sales_invoices`).

---

## 31. Testing Strategy

Mirrors the platform's centralized-under-`backend/tests/` convention (not co-located in the module):

```
backend/tests/unit/modules/installments/            # ScheduleEngine, AllocationPolicy, DueStateCalculator,
                                                       # money rounding, lifecycle _LEGAL_TRANSITIONS, aging bucket logic
backend/tests/integration/repositories/installments/ # tenant isolation, partial-unique-index (real Postgres),
                                                       # schedule persistence, allocation reference persistence, audit persistence
backend/tests/integration/api/v1/installments/       # full HTTP lifecycle flows
backend/tests/integration/migrations/                # partial unique index / CHECK constraints (real Postgres only,
                                                       # mirroring the 057-061 precedent)
backend/tests/security/installments/                 # tenant isolation, IDOR, Platform Admin boundary, support-access
                                                       # boundary, RBAC-per-permission-code, maker-checker (incl. reject)
backend/tests/performance/installments/               # list/report pagination under volume, N+1 checks
```

| Layer | Representative cases |
|---|---|
| Unit | Schedule generation (monthly/weekly/quarterly, month-end clamping, residual assignment, degenerate-final-line rejection), lifecycle transition matrix (every legal + a sample of illegal transitions), oldest-first allocation policy, due-state derivation (all 5 derivable states + the 2 controlled-workflow states), aging-bucket boundary values, entitlement-policy operation-class matrix (`InstallmentAccessPolicy`) |
| Repository | Tenant isolation (two-tenant fixture, mirroring `test_tenant_isolation.py`'s `two_tenants` fixture pattern), partial unique index rejects a second non-terminal contract for the same invoice (real Postgres), schedule-version immutability (no update method exists — a "doesn't exist" test, i.e. asserting the repository class has no `update_schedule_line` method), allocation-reference append-only persistence, audit persistence |
| Service | Activation (incl. reconciliation-check failure), approval/rejection (incl. self-approval on both), collection (exact/partial/multi-installment/advance), reversal, settlement (quote non-mutating, execution mutating), rescheduling (maker-checker, version immutability), cancellation (by stage), default, cure (policy-gated), write-off, **disabled-entitlement servicing** (collection/settlement succeed, new-contract/reschedule/cancel/default/writeoff denied). **[CORRECTED — required completion-guard tests A–C]** **Test A**: all scheduled lines paid but one late-charge `ARTransaction` remains open → `assert_zero_outstanding()` raises, contract remains `ACTIVE`/`DEFAULTED`, not `COMPLETED` (the underlying collection itself still commits successfully). **Test B**: scheduled lines paid and the late-charge `ARTransaction` is also fully paid (its own `outstanding_amount` reaches 0 via ordinary allocation) → contract completes normally. **Test C**: scheduled lines paid and the late charge is validly waived (`waived_at` set, `reverse_adjustment()` already zeroed the `ARTransaction`) → contract completes normally, the waived charge never blocks it. |
| Accounting integration | No duplicate `Payment`/`ARTransaction`/`JournalEntry` created per collection (assert exactly one of each per collection), period-lock respected (attempt a collection dated into a locked period → `PERIOD_LOCKED`), reversal reconciliation (post-reversal outstanding matches Accounting exactly), write-off integration (confirms `AccountsReceivableService.stage_write_off()`/`finalize_write_off()` called exactly once each, no direct table write), settlement reconciliation, **[CORRECTED]** late-charge GL/AR consistency (posting a late charge produces exactly one `JournalEntry` **and** exactly one `DEBIT_NOTE` `ARTransaction` **and** one `CustomerLedger.total_outstanding_base` recompute, all three visible or all three absent — assert never a partial subset), late-charge collectibility (a subsequent ordinary customer payment, allocated via the normal oldest-first policy, can satisfy the late charge's `ARTransaction` with no special-case code path), late-charge waiver reconciliation (post-waiver, GL reversal and `ARTransaction.outstanding_amount=0` and ledger recompute all land together), **[CORRECTED — required commit-ownership integration test, [§12.2](#122-corrected-general-commit-ownership-contract-for-cross-module-accounting-calls)]** a real-Postgres test that force-fails *after* `stage_adjustment()` has flushed GL/`ARTransaction`/ledger but *before* `finalize_adjustment()` is called (i.e. after `InstallmentLateCharge` is flushed but before the final commit) — assert the post-rollback database contains **none** of: the `JournalEntry`, the `ARTransaction`, the `CustomerLedger` change, the `InstallmentLateCharge` row, the `InstallmentAuditLog` row, or the outbox event row — proving the six-way atomic unit has no partial-commit failure mode. **[CORRECTED — final correction pass, generalized commit-ownership tests, [§12.3](#123-final-correction-pass-generalized-commit-ownership-across-every-installmentsaccounting-workflow)]** (a) *Down payment / Collection / Settlement*: a real-Postgres test that force-fails after `stage_customer_payment()` + `stage_allocation()` have flushed `Payment`/credit-`ARTransaction`/allocation-line/target-outstanding rows but *before* `InstallmentAllocationReference`/audit/outbox staging completes, and a second variant that force-fails *after* Installments' own staging but *before* `finalize_customer_payment()` — both must leave the post-rollback database with **none** of: `Payment`, credit `ARTransaction`, `PaymentAllocationLine`, target-transaction outstanding change, `InstallmentScheduleVersion`/`Line` (for activation) or `InstallmentAllocationReference` (for collection/settlement), `InstallmentAuditLog`, outbox event. (b) *Write-off*: identical shape, force-failing between `stage_write_off()` and `finalize_write_off()` — assert **none** of `JournalEntry`, `ARTransaction` status/outstanding change, `CustomerLedger` recompute, contract `WRITTEN_OFF` status, `InstallmentAuditLog`, outbox event survive rollback (this is the test that would have caught `confirm_write_off()`'s pre-existing three-commit defect had it existed before this pass). (c) *Reversal/Cancellation intermediate-state test*: force-fail *between* `reallocate_payment()`'s completion and a subsequent `cancel_payment()` call — assert the payment is left `POSTED`/unallocated (a valid, explainable Accounting state, not corrupt) and that a retried reversal request (same idempotency key) correctly detects this state and resumes by calling only `cancel_payment()`, never re-attempting `reallocate_payment()` against an already-unallocated payment ([§12.3.2](#1232-collection-reversal--cancellation-with-financial-reversal--reallocate_payment--cancel_payment)'s documented limitation, verified rather than merely asserted). |
| Security | Tenant A cannot reach Tenant B by ID/search/collection/settlement; Platform Admin cannot read contracts; active `SupportAccessGrant` cannot read contracts; each of the 16 permission codes independently denies when absent; self-approval denied on both approve and reject; cross-tenant invoice reference rejected at contract creation |
| Concurrency | Two concurrent full-amount collections against the last remaining installment → exactly one succeeds (real Postgres, two DB sessions); duplicate contract creation race against the partial unique index; concurrent approve/reject → deterministic conflict via optimistic version; concurrent settlement execution → no double-execution; concurrent collection/write-off → no double-effect. **[CORRECTED — required Test D]** Concurrent last-installment payment + late-charge state mutation cannot produce premature completion: with the contract row locked (`FOR UPDATE`) by the collection that would otherwise zero out schedule outstanding, a concurrently-attempted late-charge post/waiver on the same contract is serialized by that same lock — `assert_zero_outstanding()` always observes a fully consistent, non-racing view of both schedule and late-charge state, never a snapshot caught mid-mutation. |
| Idempotency | **[CORRECTED, further clarified — three required concurrency test cases, matching the two normal outcomes plus rollback-ownership]** (1) *Concurrent same-key, same-payload* (two real DB sessions): session A wins the reservation and proceeds; session B's reservation attempt blocks; A commits; B unblocks, sees `COMPLETED` with a matching fingerprint, and replays A's stored result — assert exactly one financial effect exists in Accounting regardless of both requests having been submitted. (2) *Concurrent same-key, different-payload*: same blocking sequence; B unblocks post-A-commit and receives `409 IDEMPOTENCY_PAYLOAD_MISMATCH` — assert exactly one financial effect (A's), and B's request was never processed. (3) *First request rolls back*: A's reservation succeeds but its business logic then fails (e.g. induced `PostingValidationError`); the whole transaction, including A's `IN_PROGRESS` row, rolls back; B's blocked reservation attempt then **succeeds** and B executes as the true first attempt — assert the key was never permanently stranded and exactly one financial effect exists (B's). No test should depend on observing an `IN_PROGRESS` row from another session — that branch is defensive-only and is not exercised by these three cases. Also: assert the `INSERT...ON CONFLICT DO NOTHING` reservation statement never raises `IntegrityError` and never leaves the SQLAlchemy session in an aborted state (session remains usable for subsequent statements within the same request after a duplicate-key reservation attempt). |
| Entitlement | Enabled tenant — all operations pass RBAC as normal; disabled tenant — origination denied, servicing (collection, settlement) allowed; suspended tenant — denied identically to every other module (via the shared `get_current_company_member` test, not a new mechanism) |
| Frontend | Jest hook tests for every new `useX` hook (mirroring `useCompany.test.ts`); Playwright E2E: standard contract lifecycle, partial collection, overdue read, early settlement, disabled-entitlement servicing, tenant isolation, Platform Admin/support-access boundary (7 flows, matching meta-§35's explicit list) |

---

## 32. Observability

- Structured `logger.info`/`logger.warning` calls at every mutating service-method boundary, `extra={"company_id":..., "contract_id":..., ...entity-specific identifiers}` — matching `member_service.py`'s convention exactly; `request_id`/`user_id` arrive ambiently via existing `ContextVar`s, never passed manually.
- No new logging infrastructure — reuses `core/logging/setup.py`'s JSON formatter in production.
- Health/readiness: Installments introduces no new external dependency, so no new `/health` sub-check is required beyond the existing DB-connectivity check.
- Audit log ([§17](#17-audit-architecture)) is a business/compliance record, deliberately separate from application logs (Constitution §35's explicit requirement) — no conflation of the two.

---

## 33. Performance / Indexing

| Index | Table | Purpose |
|---|---|---|
| `ix_installment_contracts_company_id` | `installment_contracts` | Base tenant-scoping index (from `TenantBaseModel`) |
| `ix_installment_contracts_company_customer` | `installment_contracts(company_id, customer_id)` | Customer-scoped contract lookups (Customer 360, statements) |
| `ix_installment_contracts_company_invoice` | `installment_contracts(company_id, sales_invoice_id)` | Eligibility check, one-contract-per-obligation pre-check |
| `ix_installment_contracts_company_status` | `installment_contracts(company_id, status)` | Operational views (active/overdue/completed filters, FR-INST-070) |
| `ix_installment_contracts_company_branch` | `installment_contracts(company_id, branch_id)` | Branch-scoped reporting, once branches exist |
| `ix_installment_schedule_lines_version_due_date` | `installment_schedule_lines(schedule_version_id, due_date)` | Due/overdue queries, schedule rendering in due-date order |
| `ix_installment_schedule_lines_due_date` | `installment_schedule_lines(due_date)` (cross-contract) | Tenant-wide due-today/due-this-week/overdue dashboard queries — paired with a `company_id` filter via the owning contract; if profiling later shows this insufficient, a denormalized `company_id` column on the line table is the documented follow-up (not built preemptively) |
| `ix_installment_allocation_references_line` | `installment_allocation_references(schedule_line_id)` | Outstanding computation (sum allocations per line) |
| `ix_installment_allocation_references_payment` | `installment_allocation_references(accounting_payment_id)` | "Which schedule lines did this Accounting payment satisfy" reverse lookups |
| `ix_installment_audit_log_entity` | `installment_audit_log(company_id, entity_type, entity_id)` | Audit-history-per-entity reads |
| `ix_installment_audit_log_time` | `installment_audit_log(company_id, occurred_at)` | Audit-timeline reads |
| `ix_installment_idempotency_lookup` | (covered by the unique constraint itself) `installment_idempotency_keys(company_id, operation, idempotency_key)` | Idempotency check is a single indexed lookup |
| `ix_installment_plan_templates_active` | `installment_plan_templates(company_id, is_active)` | Template-picker queries exclude inactive templates efficiently |

No N+1 patterns: schedule-line + allocation-reference reads for a contract detail page are two batch queries (all lines for the version, all allocation references for those line IDs via `IN (...)`), never per-line queries — matching Constitution §25's explicit prohibition and `Customer360Service`'s own "no-N+1" design discipline.

---

## 34. Deployment / Backward Compatibility

- No new Docker service, no new environment variable beyond what the existing PostgreSQL connection already provides.
- New module ships **disabled by default** for every tenant (`InstallmentsFeatureFlag.is_enabled` defaults `false`, and the `installments` `Capability` starts un-granted on every existing `Plan` until a Platform Admin explicitly adds it) — zero behavior change for any existing tenant on deploy day.
- No existing table is altered by any Installments migration — every migration in [§30](#30-migration-strategy) only `CREATE TABLE`s (plus the two permission/capability-seed `INSERT`-only migrations). **[CORRECTED]** Migration 071 (permission backfill) is now mandatory, not conditional ([§30.1](#301-corrected-migration-071-is-mandatory-not-conditional)) — it still only `INSERT`s (idempotently, `ON CONFLICT DO NOTHING`) into the pre-existing `permissions`/`role_permissions` tables and never alters or removes an existing row, so this bullet's guarantee holds exactly as before; every existing tenant simply gains 16 dormant, un-toggled permission grants on its system roles at deploy time, with zero behavioral effect until that tenant is also entitled and opts the module on.
- Rollback: standard `alembic downgrade` chain; since no existing data is touched, a full rollback of all Installments migrations is safe at any point before real tenant data exists in the new tables.
- API versioning: mounted under the existing `/api/v1/` prefix — no new API version introduced (module addition, not a breaking change to any existing endpoint).

---

## 35. Future AI Readiness

No AI is implemented in this Epic (no vector DB, no LLM dependency, no agent framework — meta-§39's explicit prohibition). The following read-only service methods are structured to be directly consumable by a future AI orchestration layer **without becoming financial or authorization truth themselves**:

| Future AI consumer need | Installments' clean boundary |
|---|---|
| Contract explanation | `InstallmentContractService.get_explained_view(contract_id)` — structured terms + status + audit summary, already needed for the frontend Contract Detail page, reusable as-is |
| Payment schedule | `GET /contracts/{id}/schedule` — already a structured, paginated read |
| Next due | Due-state derivation service ([§10](#10-schedule-engine)) — a pure function, trivially callable from any future orchestration layer |
| Overdue exposure | `InstallmentAgingCalculator` + Delinquency service reads |
| Customer payment pattern | `InstallmentCustomerSummaryService.get_summary()` ([§14](#14-crm--inventory-integration)) already aggregates payment history per customer |
| Collection prioritization | Overdue + aging + customer-summary reads compose directly; no new service required |
| Settlement information | `generate_quote()`'s output is already structured and non-mutating |

**Guardrails preserved by construction**: AI cannot bypass RBAC (every read-path above still requires the same permission checks as a human caller would — there is no "AI service account" bypass built), cannot autonomously waive/write-off/settle/reverse/mutate (every mutating method requires an `actor_user_id` tied to a real authenticated, permissioned session — no service method accepts `actor_id=None` for a privileged mutation), and cannot become Accounting truth (every figure a future AI layer would read is itself already sourced from Accounting or clearly labeled Installments-contractual, per [§25](#25-reporting--query-architecture)'s explicit truth-source table).

---

## 36. Implementation Sequence / Dependency Graph

The user's proposed 15-phase baseline is sound and is adopted with two adjustments, explained below.

| Phase | Contents | Adjustment from baseline |
|---|---|---|
| **1 — Domain Foundation** | Module skeleton (`constants.py`, `dependencies.py`, `exceptions.py`, `events/`), permission codes, domain enums (`status`, `InstallmentOperationClass`), exception hierarchy, base schemas | none |
| **2 — Configuration & Plans** | `InstallmentConfiguration`, branch overrides, `InstallmentPlanTemplate`, `InstallmentsFeatureFlag` + `InstallmentsModuleEnablementProvider` + `Capability` registration | none |
| **3 — Contract Persistence** | `InstallmentContract` model/repository, `InstallmentSequence`, one-contract-per-obligation partial unique index, terms snapshot | none |
| **4 — Schedule Engine** | `ScheduleEngine` (pure, unit-tested first per Constitution §31's "tests before/alongside implementation"), `InstallmentScheduleVersion`/`Line` persistence, rounding/residual | none |
| **5 — Contract Lifecycle** | DRAFT→PENDING_APPROVAL→APPROVED→ACTIVE, `_LEGAL_TRANSITIONS` guard, maker-checker on approve/reject | none |
| **5.5 — Idempotency Primitive** *(new, inserted)* | `InstallmentIdempotencyKey` — built here, **before** Phase 6/7 need it, since no reusable platform primitive exists ([§20](#20-idempotency-strategy)) and every subsequent phase's high-risk commands depend on it | **Inserted** — the baseline didn't allocate a phase for this because it assumed a reusable component existed; repository inspection found none, so it needs its own slot rather than being bolted on ad hoc inside Phase 6 or 7 |
| **6 — Accounting Integration** | `AccountingIntegrationGateway`, `InstallmentOutstandingService` skeleton (§9.3), down-payment recording, AR read integration, fiscal-period propagation. **[Correction passes — prerequisite, fully generalized by the final correction pass]** Also where **every** coordinated `modules/accounting` change lands, per [§12.3](#123-final-correction-pass-generalized-commit-ownership-across-every-installmentsaccounting-workflow)'s complete method-by-method re-verification: (1) `AccountsReceivableService.stage_adjustment()`/`finalize_adjustment()`/`reverse_adjustment()` (late charge/waiver, [§12.1](#121-corrected-late-charge-ar-truth--repository-re-inspection-and-resolution)); (2) `PaymentService.stage_customer_payment()`/`finalize_customer_payment()` + `AllocationEngine.stage_allocation()`/`finalize_allocation()` (down payment, collection, settlement, [§12.3.1](#1231-activation--down-payment-collection-settlement-payment--paymentservice--allocationengine)); (3) `AccountsReceivableService.stage_write_off()`/`finalize_write_off()` (write-off, [§12.3.3](#1233-write-off--accountsreceivableserviceconfirm_write_off) — closing a **three**-commit defect, the worst found). Collection reversal/cancellation require **no** Accounting-side code change (staging-order discipline only, [§12.3.2](#1232-collection-reversal--cancellation-with-financial-reversal--reallocate_payment--cancel_payment)). **Nine new/changed Accounting methods total across three staged/finalize pairs**, all required *before* Phase 7 (Collections)/Phase 8 (Delinquency)/Phase 10 (Advanced Lifecycle, for write-off) can implement their respective workflows with correct end-to-end commit ownership | **Prerequisite fully generalized** — the first correction pass fixed late charges only; the micro-correction pass proved that fix's own shape needed refining; this final pass proved the identical defect existed, undetected, in every other Accounting integration point (down payment/collection/settlement/write-off) and fixed all of them with the same proven pattern, while proving reversal/cancellation need no code change at all |
| **7 — Collections** | Collection orchestration, allocation policy, partial/multi-installment/advance payment, reversal — depends on Phase 5.5 | none |
| **8 — Delinquency** | Due-state derivation, overdue/grace, aging, late charges, waiver | none |
| **9 — Settlement** | Quotes, execution, `DEFAULTED→COMPLETED` direct-payoff path | none |
| **10 — Advanced Lifecycle** | Reschedule (schedule versioning), cancellation, default, cure, write-off | none |
| **11 — Entitlement / Security Hardening** | `InstallmentAccessPolicy` full operation-class wiring across every endpoint, tenant-suspension confirmation tests, Platform Admin/support-access boundary tests, IDOR sweep | **Note**: `InstallmentAccessPolicy`'s *skeleton* is actually needed as early as Phase 1 (every service method calls it) — Phase 11 is where its *entitlement-disabled behavioral correctness* is exhaustively tested and hardened, not where the class first appears |
| **12 — Reporting / Documents** | Dashboard, reports, statements, agreement/schedule documents | none |
| **13 — Frontend** | Operational UI, permission-gated actions, service-only disabled state | none |
| **14 — Concurrency / Idempotency Hardening** | Real-Postgres race-condition tests (partial unique index, `FOR UPDATE` serialization, optimistic-version conflicts) | none |
| **15 — Integration / E2E / Regression** | Cross-module integration tests, Playwright, full backend/frontend regression | none |

**Dependency graph** (topological): `1 → 2 → 3 → 4 → 5 → 5.5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14 → 15`, with `11`'s policy-skeleton work actually starting alongside `1` (a cross-cutting concern threaded through every phase, formally hardened/tested in `11`) — this is the only structural deviation from a strictly linear reading of the baseline, and it is a *test-and-harden* reordering, not a *build* reordering (the class exists from Phase 1; Phase 11 is where its correctness is proven exhaustively).

---

## 37. Risks / Trade-Offs

| Risk | Mitigation | Trade-off accepted |
|---|---|---|
| New idempotency primitive is genuinely new infrastructure (no platform precedent to copy exactly) | Modeled as tightly as possible on the one existing analogous case (`RecurringJournalInstance`'s business-key + unique-constraint pattern); scoped strictly to Installments' own table, not proposed as a platform-wide `core/` addition | Slightly more implementation effort than "just reuse an existing thing" — accepted because spec explicitly requires idempotency on 8 named high-risk commands and no reusable component exists |
| Outbox usage deviates from 4 of the 5 sibling business modules' in-process-bus convention | Explicitly documented as ADR-INST-09, justified by Constitution §49 compliance (the in-process bus doesn't actually satisfy the Constitution) | A future reader comparing Installments' `events/` folder to Accounting's `events/` folder will see a different shape — mitigated by the ADR being easy to find and the reasoning being sound, not arbitrary |
| `InstallmentAccessPolicy`'s operation-class check must be threaded into *every* service method individually (no router-level shortcut) | Centralized as one small, thoroughly unit-tested class; a missed call site is a real risk class, mitigated by Phase 11's exhaustive per-endpoint entitlement test sweep | More call sites to get right than a single router dependency — accepted because spec's origination-vs-servicing split cannot be expressed any other way given the existing `require_capability_entitled` primitive's router-only granularity |
| No `Branch` entity exists yet, so `branch_id` is an unenforced nullable column | Documented explicitly as a forward-compatible placeholder, not built out further | If/when Branch ships platform-wide, an additive FK migration is needed — acceptable, matches Constitution §10's "should be ready," not "must be built" |
| Money-precision mismatch between Sales (15,2) and Accounting (20,6) | Resolved per spec Assumption A4 in Accounting's favor, carried through consistently in every Installments money column | None — this was already resolved by the spec; the plan just avoids reintroducing ambiguity |
| No document-rendering (PDF) infrastructure exists | Installments ships JSON-structured "documents" only, matching Accounting's own precedent; flagged as an open point rather than silently building new PDF infrastructure | If the business genuinely needs printable PDFs, that's a follow-up decision outside this Epic's blast radius |
| **[Correction passes, fully generalized by the final correction pass]** Correct, atomic cross-module integration requires coordinated changes *inside* `modules/accounting` for **every** money-mutating Installments workflow, not just late charges — nine new/changed methods across three staged/finalize pairs (`stage_adjustment()`/`finalize_adjustment()`, `stage_customer_payment()`/`finalize_customer_payment()`, `stage_allocation()`/`finalize_allocation()`, `stage_write_off()`/`finalize_write_off()`, plus `reverse_adjustment()`) — Installments cannot ship *any* of down payment, collection, settlement, late charges, or write-off correctly-atomically without them ([§12.3](#123-final-correction-pass-generalized-commit-ownership-across-every-installmentsaccounting-workflow)) | All changes are additive/backward-compatible, templated exactly on existing methods and the existing `PostingEngine.stage_direct_posting()`/`finalize_and_publish()` two-phase idiom (`record_sales_invoice()`, `PaymentService.cancel_payment()`) rather than new architecture; scheduled explicitly in Phase 6 ([§36](#36-implementation-sequence--dependency-graph)) as named prerequisites, not discovered mid-implementation. Collection reversal/cancellation need **zero** Accounting-side changes at all — proven sufficient via a staging-order discipline alone | A meaningful amount of cross-module coordination — nine methods, not the two the first correction pass estimated — is required before Phases 6/7/8/10 can be implemented — accepted because every alternative considered (the original bare-`post_direct()` design, the first pass's single-method extensions, or simply not verifying the other workflows at all) would have shipped a real atomicity defect somewhere in the system; `confirm_write_off()`'s **three**-separate-commit defect in particular was completely undetected until this pass's explicit, method-by-method re-inspection — a concrete demonstration of why the correction's own "do not assume, explicitly inspect" instruction mattered |
| **[Correction pass]** `postgresql.insert().on_conflict_do_nothing()` (SQLAlchemy's Postgres-dialect-specific construct) has zero prior usage anywhere in this codebase's application code | Chosen because it is the only mechanism that solves the idempotency race without ever placing the transaction in an aborted state — the alternative, a bare unique-violation catch, is explicitly what this correction pass was tasked to eliminate; documented in detail in [§20](#20-idempotency-strategy) and ADR-INST-08 | A future reader will see one construct in Installments' repository layer with no sibling-module precedent to compare against — mitigated by the ADR's explicit reasoning being easy to find |

---

## 38. Requirement Traceability

### 38.1 By functional-requirement group

| Spec group | Component / Persistence | Integration | API | Test layer |
|---|---|---|---|---|
| §9.1 Configuration (FR-INST-001–004) | `InstallmentConfiguration` | — | Configuration group | Unit (validation), Repository, Service |
| §9.2 Plans/Templates (FR-INST-010–013) | `InstallmentPlanTemplate` | — | Plans/Templates group | Unit, Repository, Service |
| §9.3 Eligibility (FR-INST-020–023) | `InstallmentEligibilityService` | Sales (`Customer`, `SalesInvoice` reads) | Eligibility group | Unit, Service |
| §9.4 Quote/Preview (FR-INST-030–032) | `ScheduleEngine`, `InstallmentQuoteService` | — | Quote/Preview group | Unit (determinism) |
| §9.5 Contract data (FR-INST-040–042) | `InstallmentContract`, `InstallmentSequence`, partial unique index | Sales (invoice ref) | Contracts group | Repository (invariant), Service |
| §9.6 Notifications (FR-INST-050–051) | Outbox events ([§26](#26-domain-events)) | — | (event-driven, no dedicated endpoint) | — |
| §9.7 Documents (FR-INST-060–061) | `InstallmentDocumentService` | — | Documents/Statements group | Service (non-mutation assertion) |
| §9.8 Search/Views (FR-INST-070–072) | Repository query methods | — | Contracts `GET /contracts` | Repository, Performance |
| §9.9 Dashboard (FR-INST-080–081) | Reporting service | Accounting (collection figures) | Reports/Dashboard group | Service (no-double-count) |
| §9.10 API/Contract (FR-INST-090–093) | — | — | All groups | Integration (API) |
| §10 Business Rules (BR-INST-001–022) | See [§38.2](#382-by-business-rule) | | | |
| §11 Lifecycle (FR-INST-100–108) | `InstallmentContractService`, `_LEGAL_TRANSITIONS` | — | Submission/Approval/Rejection/Activation groups | Unit (transition matrix), Service |
| §12 Schedule (FR-INST-110–122) | `ScheduleEngine`, `InstallmentScheduleVersion/Line` | — | Schedules group | Unit, Repository |
| §13 Collection/Allocation (FR-INST-130–142) | `InstallmentCollectionService`, `InstallmentAllocationPolicy` | Accounting `PaymentService`/`AllocationEngine` | Collections group | Unit, Service, Accounting integration |
| §13.3 Down Payments (FR-INST-150–152) | `InstallmentContractService.activate()` | **[CORRECTED]** Accounting `PaymentService.stage_customer_payment()`/`finalize_customer_payment()` + `AllocationEngine.stage_allocation()`/`finalize_allocation()`, see [§12.3.1](#1231-activation--down-payment-collection-settlement-payment--paymentservice--allocationengine) | Activation group | Service, Accounting integration (incl. forced-failure commit-ownership test) |
| §14 Delinquency (FR-INST-160–181) | `InstallmentDelinquencyService`, `InstallmentAgingCalculator`, `InstallmentOutstandingService` ([§9.3](#93-corrected-authoritative-completion-guard--installmentoutstandingserviceassert_zero_outstanding)) | Accounting (**[CORRECTED, further frozen]** `AccountsReceivableService.stage_adjustment()`/`finalize_adjustment()`/`reverse_adjustment()` for charges — not `PostingEngine` directly, not a single `adjust_receivable()` call either, see [§12.1](#121-corrected-late-charge-ar-truth--repository-re-inspection-and-resolution)/[§12.2](#122-corrected-general-commit-ownership-contract-for-cross-module-accounting-calls)) | Reports group, contract detail | Unit (aging boundaries), Service, **[CORRECTED]** Accounting integration (GL/AR/ledger consistency, commit-ownership forced-failure test) |
| §15.1 Settlement (FR-INST-190–192) | `InstallmentSettlementService` | Accounting `PaymentService` | Settlement Quotes/Execution groups | Unit (reproducibility), Service |
| §15.2 Amendments (FR-INST-200–203) | `InstallmentReschedulingService`, new `InstallmentScheduleVersion` | — | Rescheduling group | Unit, Service (maker-checker) |
| §15.3 Cancellation (FR-INST-210–212) | `InstallmentContractService.cancel()` | **[CORRECTED]** Accounting (reversal, conditional) via `reallocate_payment()`/`cancel_payment()`, staging-order discipline, no Accounting-side change, see [§12.3.2](#1232-collection-reversal--cancellation-with-financial-reversal--reallocate_payment--cancel_payment) | Cancellation group | Service, **[CORRECTED]** Accounting integration (intermediate-state test) |
| §15.4 Default (FR-INST-220–222) | `InstallmentContractService.mark_defaulted()/cure()` | none (default), none (cure — policy read only) | Default/Cure groups | Service |
| §15.5 Write-Off (FR-INST-230–232) | `InstallmentContractService.writeoff()` | **[CORRECTED]** Accounting `AccountsReceivableService.stage_write_off()`/`finalize_write_off()` (not `confirm_write_off()` directly — that method becomes a thin backward-compatible wrapper), see [§12.3.3](#1233-write-off--accountsreceivableserviceconfirm_write_off) | Write-Off group | Service, Accounting integration (incl. forced-failure commit-ownership test) |
| §15.6 Refunds/Reversals (FR-INST-240–242) | `InstallmentAllocationReference(is_reversal)` | **[CORRECTED]** Accounting reversal mechanism (`reallocate_payment()`/`cancel_payment()`), staging-order discipline, see [§12.3.2](#1232-collection-reversal--cancellation-with-financial-reversal--reallocate_payment--cancel_payment) | Reversals group | Service, Accounting integration |
| §16 Sales Integration (FR-INST-250–261) | `InstallmentEligibilityService`, `sales_integration_handlers.py` | Sales (read + event subscription) | Eligibility, Contracts groups | Service, Security (cross-tenant invoice ref) |
| §17 Accounting Integration (FR-INST-270–274) | `AccountingIntegrationGateway` | Accounting (all service classes) | (cross-cutting) | Accounting integration (full suite) |
| §18 Inventory/CRM (FR-INST-280–291) | (Inventory: none), `InstallmentCustomerSummaryService` | CRM (`Customer360Service` import point), none (Inventory) | (no dedicated endpoint; CRM imports directly) | Service |
| §19 Multi-Tenancy (FR-INST-300–302) | All repositories | — | All endpoints | Security (tenant isolation) |
| §19.2 Platform Admin (FR-INST-310–311) | (structural exclusion) | — | — | Security (Platform Admin/support-access boundary) |
| §20 RBAC (FR-INST-320–321) | `user_has_installments_permission()` | — | All endpoints | Security (per-permission-code) |
| §20.2 Maker-Checker (FR-INST-330–332) | `InstallmentContractService.approve/reject/reschedule` | — | Approval/Rejection, Rescheduling groups | Service, Security |
| §21 Audit (FR-INST-340–343) | `InstallmentAuditLog`, `InstallmentAuditService` | — | (cross-cutting) | Repository (persistence), Service (fail-closed) |
| §22 Entitlement (FR-INST-350–358) | `InstallmentAccessPolicy`, `InstallmentsFeatureFlag`, `Capability` registration | Platform Admin (`PlatformEntitlementService`) | Admin group, (cross-cutting policy on all groups) | Unit (policy matrix), Service (entitlement) |
| §23 Reporting (FR-INST-360–362) | Reporting services | Accounting (financial figures) | Reports/Dashboard group | Service (no-double-count) |
| §24 Security (FR-INST-370–376) | (cross-cutting) | — | All endpoints | Security (full suite) |
| §25 Concurrency/Idempotency (FR-INST-380–384) | [§19](#19-concurrency-strategy)/[§20](#20-idempotency-strategy) | Accounting (defense-in-depth locks) | Collections, Activation, Settlement, Reversals, Rescheduling, Cancellation, Default, Write-Off groups | Concurrency, Idempotency |
| §26 Failure/Recovery (FR-INST-390–394) | [§21](#21-transaction--atomicity-boundaries)/[§22](#22-failure--recovery-design) | — | All mutating endpoints | Service (failure-path), Integration |

### 38.2 By business rule

| Rule | Implementation destination |
|---|---|
| BR-INST-001, 015 | [§18](#18-multi-tenant--branch-isolation) tenant isolation + IDOR design |
| BR-INST-002 | [§15](#15-entitlement-architecture) — entitlement governance ≠ data access |
| BR-INST-003 | [§13](#13-sales-integration) — contract always references authoritative Sales entities, no FK duplication |
| BR-INST-004 | [§12](#12-accounting-integration) — no shadow financial records, enforced structurally (no Accounting table writes from Installments) |
| BR-INST-005 | [§8](#8-money--precision-strategy) / [§10.3](#103-amount-splitting-and-residual-br-inst-005-fr-inst-112-8) — exact residual reconciliation |
| BR-INST-006 | [§20](#20-idempotency-strategy) + [§19](#19-concurrency-strategy) |
| BR-INST-007 | [§11.3](#113-where-ar-truth-lives-vs-what-installments-stores) — `InstallmentAllocationReference` |
| BR-INST-008 | [§9.2](#92-implementation-pattern-explicit-named-service-methods-no-generic-set_status) — no destructive edit path for `ACTIVE`+ terms |
| BR-INST-009 | [§6](#6-domain-model) — terms snapshot, never a live config/template reference |
| BR-INST-010 | **[CORRECTED]** [§9.3](#93-corrected-authoritative-completion-guard--installmentoutstandingserviceassert_zero_outstanding) — `complete()` requires `InstallmentOutstandingService.assert_zero_outstanding()` to pass, covering both schedule outstanding and any open late-charge AR, not schedule outstanding alone |
| BR-INST-011 | [§19](#19-concurrency-strategy) — over-collection races |
| BR-INST-012 | [§12](#12-accounting-integration) write-off row |
| BR-INST-013 | [§12](#12-accounting-integration) default row (no posting) + [§19](#19-concurrency-strategy) collection/write-off race |
| BR-INST-014 | [§15](#15-entitlement-architecture) servicing continuity |
| BR-INST-016 | [§17](#17-audit-architecture) |
| BR-INST-017 | [§6](#6-domain-model) — schedule versioning, append-only allocation references |
| BR-INST-018 | [§8](#8-money--precision-strategy) |
| BR-INST-019 | [§10](#10-schedule-engine) / [§9](#9-installment-lifecycle-architecture) — deterministic, read-time derivation |
| BR-INST-020 | [§35](#35-future-ai-readiness) — no autonomous mutation path |
| BR-INST-021 | [§12](#12-accounting-integration) fiscal-period row |
| BR-INST-022 | [§13](#13-sales-integration) — currency immutability |

### 38.3 By scenario / success criterion

| ID | Implementation destination |
|---|---|
| Scenario A (standard sale) | [§9](#9-installment-lifecycle-architecture) + [§10](#10-schedule-engine) + [§12](#12-accounting-integration) down payment/collection rows |
| Scenario B (partial payment) | [§11](#11-collection--allocation-architecture) |
| Scenario C (multi-installment payment) | [§11.1](#111-allocation-policy-fr-inst-140142) |
| Scenario D (advance payment) | [§11.1](#111-allocation-policy-fr-inst-140142) |
| Scenario E (overdue) | [§10](#10-schedule-engine) due-state + [§25](#25-reporting--query-architecture) aging |
| Scenario F (early settlement) | [§12](#12-accounting-integration) settlement row |
| Scenario G (payment reversal) | [§12](#12-accounting-integration) reversal row |
| Scenario H (sale return interaction) | [§13](#13-sales-integration) event-subscription handler |
| Scenario I (tenant isolation) | [§18](#18-multi-tenant--branch-isolation), [§31](#31-testing-strategy) security tests |
| Scenario J (concurrent collection) | [§19](#19-concurrency-strategy) |
| Scenario K (entitlement disabled) | [§15](#15-entitlement-architecture) |
| Scenario L (support access) | [§2](#2-repository-findings) structural boundary, [§29](#29-security-architecture) |
| SC-001 – SC-007 | Covered jointly by [§10](#10-schedule-engine)(SC-001), [§11.3](#113-where-ar-truth-lives-vs-what-installments-stores)(SC-002), [§18](#18-multi-tenant--branch-isolation)(SC-003), [§19](#19-concurrency-strategy)(SC-004), [§17](#17-audit-architecture)(SC-005), [§15](#15-entitlement-architecture)(SC-006), [§31](#31-testing-strategy) as a whole (SC-007) |

**No orphan requirements**: every FR-INST group, every BR-INST-*, every Scenario A–L, and every SC-001–007 has an explicit destination above.

---

## 39. Open Technical Decisions

### 39.1 Resolved Technical Decisions

All decisions the meta-prompt flagged as requiring repository-grounded resolution were resolved during inspection:

- Money precision: Accounting's `NUMERIC(20,6)`, not Sales' `NUMERIC(15,2)` — [§8](#8-money--precision-strategy).
- Schedule versioning mechanism: dedicated `InstallmentScheduleVersion` entity with immutable child lines — [§6](#6-domain-model)/[§10.4](#104-versioning-integration).
- One-contract-per-obligation enforcement: PostgreSQL partial unique index, following the `Subscription` precedent — [§7.2](#72-constraints).
- Idempotency mechanism: new module-local primitive, modeled on the `RecurringJournalInstance` business-key pattern — [§20](#20-idempotency-strategy).
- Concurrency mechanism per race class: mixed `FOR UPDATE` (money sequences) + optimistic `version` column (discrete approvals) — [§19](#19-concurrency-strategy).
- Entitlement enforcement granularity: per-service-method `InstallmentAccessPolicy`, not a router-level gate — [§15](#15-entitlement-architecture), ADR-INST-06.
- Domain event mechanism: transactional outbox, not the in-process bus — [§26](#26-domain-events), ADR-INST-09.
- Audit log shape: Accounting's richer shape (adds `reason`/`session_context`) over CRM's minimal one — [§17](#17-audit-architecture).
- Branch scoping: reserved nullable column, no authorization system built (none exists platform-wide to extend) — [§18](#18-multi-tenant--branch-isolation).
- Document generation: JSON-structured, matching Accounting's `generate_remittance_advice()` precedent, not new PDF infrastructure — [§27](#27-documents--statements).
- Background processing: none required for correctness; one optional notification-only job, explicitly not load-bearing — [§28](#28-background-processing).

### 39.2 Blocking Technical Clarifications

**None.** Repository inspection resolved every technical choice the meta-prompt's structure anticipated might need one. The two items flagged above as "genuinely new infrastructure" (idempotency primitive, JSON-only documents) are *design decisions this plan makes*, not open questions requiring product-owner input — they do not touch any approved business requirement in `spec.md` (per meta-§41, no business-requirement drift is proposed anywhere in this plan).

**No blocking technical clarifications remain. Ready for `/sp.tasks`.**

---

## 40. Architecture Decision Records

### ADR-INST-01 — Accounting remains the sole financial source of truth

**Decision**: Installments never writes to `accounting_*` tables directly; every financial fact flows through Accounting's public service classes (`PostingEngine`, `PaymentService`, `AllocationEngine`, `AccountsReceivableService`).
**Rationale**: BR-INST-004 is a hard spec requirement; repository inspection confirms Accounting already exposes exactly the service-boundary methods (`stage_direct_posting`/`finalize_and_publish`) needed for atomic cross-module writes without table-level coupling.
**Consequences**: Installments' own tables never contain a "paid amount" column that could drift from Accounting's figures — every "paid" display value is either read live from Accounting or derived from `InstallmentAllocationReference`, which itself only ever points at Accounting rows.
**[CORRECTED, correction pass]**: This principle is now also the reason late charges could **not** be implemented as a bare `PostingEngine.post_direct()` call with no `ARTransaction` (the original plan's draft) — that design would have created GL-vs-subledger truth that diverged from Accounting's own `ARTransaction`/`CustomerLedger` figures, effectively becoming a small shadow-truth incident even though no new table was involved. The corrected design ([§12.1](#121-corrected-late-charge-ar-truth--repository-re-inspection-and-resolution)) closes this by requiring every AR-increasing Installments action, including late charges, to go through a method that keeps GL and the AR subledger atomically consistent — the same discipline this ADR already required for collections and write-offs, now applied without exception to late charges too.
**[CORRECTED, micro-correction pass]**: A single atomically-consistent Accounting write is still not enough on its own — this ADR's guarantee extends one level further: **Accounting must never commit before Installments has staged its own related rows into the same transaction.** A method that internally commits GL/AR/ledger truth first and only lets Installments add its own metadata afterward would satisfy this ADR's letter (Accounting's own figures stay internally consistent) while violating its spirit (Installments' explanatory/audit records could still end up missing against an already-committed Accounting fact, if the later step failed). [§12.2](#122-corrected-general-commit-ownership-contract-for-cross-module-accounting-calls) makes this explicit as its own named contract, with Installments' own service method — never Accounting's — always owning the single final commit for any cross-module workflow.
**[CORRECTED, final correction pass]**: [§12.3](#123-final-correction-pass-generalized-commit-ownership-across-every-installmentsaccounting-workflow) proves this same guarantee holds for **every** Installments↔Accounting integration point, not only late charges — method-by-method re-inspection found the identical early-commit defect in `create_customer_payment()`, `AllocationEngine.allocate()`, and, most severely, `confirm_write_off()` (three separate internal commits, never previously fixed), and found that `reallocate_payment()`/`cancel_payment()` (used for reversal/cancellation) achieve the same guarantee through a staging-order discipline requiring no Accounting-side change at all. This ADR's principle — Accounting is the sole financial source of truth, and that truth must never exist in a state Installments' own explanatory records disagree with, even transiently across a commit boundary — now holds for the full set of Installments' money-mutating operations, not a subset.

### ADR-INST-02 — `InstallmentContract` is the Installments aggregate root

**Decision**: All schedule, allocation-reference, late-charge, and lifecycle state hangs off `InstallmentContract`; no other entity can exist independently of a contract.
**Rationale**: Matches spec §7's ownership partition and the platform's existing aggregate-root convention (`SalesInvoice`, `JournalEntry`).
**Alternatives considered**: A separate `InstallmentAccount`-style entity wrapping multiple contracts per customer — rejected as unnecessary; spec's one-contract-per-obligation rule means the contract itself is already the natural aggregation unit.

### ADR-INST-03 — One non-terminal contract per originating obligation, enforced by a PostgreSQL partial unique index

**Decision**: `uq_installment_contracts_one_nonterminal_per_obligation ON installment_contracts(company_id, sales_invoice_id) WHERE status NOT IN ('CANCELLED','COMPLETED','WRITTEN_OFF')`.
**Rationale**: Repository inspection found an exact precedent (`Subscription`'s `uq_subscriptions_company_active`) proving this pattern is both idiomatic and already trusted in production-adjacent code for "at most one active row per key." A `SELECT`-then-`INSERT` check alone (explicitly forbidden by the meta-prompt) cannot prevent the race; the DB constraint can.
**Consequences**: A concurrent double-submission surfaces as a `409 Conflict` (translated from the underlying `IntegrityError`) rather than a silent double-contract — application-layer pre-check exists only to produce a clean error message, not as the actual protection.

### ADR-INST-04 — Schedule terms are snapshotted; active schedules are versioned, never destructively edited

**Decision**: `InstallmentScheduleVersion` (immutable once created) + `InstallmentScheduleLine` (immutable, with two narrow audited exceptions for waive/void). Rescheduling creates version N+1 and supersedes version N; it never mutates version N's rows.
**Rationale**: BR-INST-017 (never destructively rewrite history) and FR-INST-114 (no silent overwrite of an active schedule) are both hard requirements; a mutable-line design would make either impossible to guarantee structurally.
**Consequences**: `InstallmentAllocationReference` rows always remain valid pointers to the schedule-line version they were recorded against, even after a reschedule — full historical explainability is preserved by construction, not by convention.

### ADR-INST-05 — Derived due-state vs. persisted financial state

**Decision**: `UPCOMING`/`DUE`/`PARTIALLY_PAID`/`PAID`/`OVERDUE` are computed at read time from `scheduled_amount`, `due_date`, grace policy, and the live sum of non-reversed `InstallmentAllocationReference` rows. Only `WAIVED`/`VOIDED` are persisted (as narrow, explicit, audited timestamp+reason columns), because those two states cannot be derived from any combination of date/amount data — they represent a genuinely new fact a human introduced.
**Rationale**: FR-INST-120–122 and BR-INST-019 require correctness independent of any background job having run; a persisted, freely-mutable status column would risk drifting from the authoritative Accounting allocation data it should represent.
**Consequences**: Every schedule-line read does a small amount of read-time computation (cheap: one aggregation over already-indexed allocation-reference rows) rather than a single column read — an explicit, accepted trade-off matching Constitution §25's "correctness before premature optimization."

### ADR-INST-06 — Origination-vs-servicing entitlement policy, enforced per service method, not per router mount

**Decision**: `InstallmentAccessPolicy.authorize(operation_class, ...)` is called inside every service method; the router itself carries no blanket entitlement dependency (unlike CRM's `require_crm_enabled`).
**Rationale**: FR-INST-353–358 require different behavior for different operations under the *same* disabled-entitlement condition — a capability CRM's existing `require_capability_entitled`/`require_crm_enabled` router-level gate structurally cannot express (it is binary: whole router blocked or not). Building a second, competing entitlement-resolution algorithm was explicitly forbidden (FR-INST-352); this design reuses `PlatformEntitlementService.resolve_effective_entitlement()` unchanged and only adds a thin operation-classification layer on top.
**Alternatives considered**: (a) Two separate routers (one gated, one not) — rejected as more complex and error-prone than one policy class with a classification enum. (b) Per-endpoint FastAPI dependencies (`Depends(require_installments_servicing)`, `Depends(require_installments_origination)`) — viable and roughly equivalent; this plan prefers the explicit in-service-method call because every other fine-grained authorization check in this codebase (permission checks) is already done the same way (inline, not as a dependency), so this keeps the two checks visually/stylistically adjacent in the code rather than split across a dependency list and a method body.
**Consequences**: More call sites must get this right (mitigated by Phase 11's exhaustive test sweep, [§36](#36-implementation-sequence--dependency-graph)) — accepted because the alternative (a router-level gate) cannot satisfy the spec at all.

### ADR-INST-07 — Concurrency strategy for collections: pessimistic row lock, not optimistic versioning

**Decision**: `SELECT ... FOR UPDATE` on `InstallmentContract` for the duration of any money-mutating sequence (collection, settlement, write-off), combined with Accounting's own independent locking as defense-in-depth.
**Rationale**: Collections involve a multi-step read-compute-write sequence (compute outstanding → allocate → call Accounting → persist references) where an optimistic-version conflict would be detected only at the very end, after significant wasted work and a confusing user-facing retry; a lock held for the sequence's duration matches Accounting's own established pattern for the identical class of problem (`ARTransactionRepository.get_by_id_locked()`).
**Alternatives considered**: Optimistic `version` column on `InstallmentContract` for collections too — rejected specifically for this operation class (still used for approval/rejection, [§19](#19-concurrency-strategy)) because collection's multi-step Accounting round-trip makes "detect conflict, ask user to retry" a worse experience than "serialize and proceed."

### ADR-INST-08 — Idempotency architecture: new module-local primitive, `ON CONFLICT DO NOTHING` conflict handling

**Decision**: `InstallmentIdempotencyKey` table, scoped `(company_id, operation, idempotency_key)`, storing a request fingerprint and replayable result, staged in the same transaction as the business operation it guards. **[CORRECTED, correction pass]** Reservation uses PostgreSQL `INSERT...ON CONFLICT DO NOTHING...RETURNING` (via SQLAlchemy's `postgresql.insert()` construct), never a bare `INSERT` with a caught `IntegrityError`. The `FAILED` status value is removed from the schema (see [§20.1](#201-schema-corrected)).
**Rationale**: Repository-wide inspection found zero reusable idempotency-key infrastructure; the closest analog (`RecurringJournalService`) uses a narrower business-key pattern unsuitable for client-supplied replay keys across arbitrary request types, and its own race backstop (an uncaught `IntegrityError`) is precisely the failure mode this ADR's conflict-handling decision needs to avoid. Spec's FR-INST-092/373/380-384 are unambiguous requirements that cannot be satisfied without building this.
**Alternatives considered** (per the correction's explicit Option A/Option B framing):
- **Option A — `INSERT...ON CONFLICT DO NOTHING...RETURNING` (chosen)**: never raises an error for the conflicting case; PostgreSQL's own row-level lock on the unique index naturally serializes a genuinely concurrent duplicate (the second inserter blocks until the first resolves) with no extra application-level locking needed. Zero prior use of this construct exists in this codebase's application code (only inside raw-SQL migrations) — a deliberate, justified first use, not an oversight.
- **Option B — Savepoint (`session.begin_nested()`) around a plain `INSERT`, catching `IntegrityError` and rolling back to the savepoint**: rejected. Repository inspection found **zero production use of savepoints anywhere in the codebase** — the only occurrence at all is a test-isolation fixture — so this option would introduce a second, genuinely novel pattern (nested-transaction lifecycle management) for no benefit over Option A, which solves the identical problem in one statement with no error path at all. Choosing Option A over Option B is not "picking the more familiar one" (neither has precedent) — it is picking the simpler, more directly correct one.
- **Bare `INSERT` + catch `IntegrityError` (the original, uncorrected design)**: rejected — this is the exact anti-pattern the correction pass identified. In PostgreSQL, a unique-constraint violation aborts the current transaction; every statement issued afterward (including a "fetch the existing row" recovery step) fails with `InFailedSqlTransaction` unless a savepoint had been established beforehand — which the original design did not do.
**Consequences**: This is new infrastructure, scoped deliberately narrowly (Installments' own table, not a `core/` addition) so it does not become an unrequested platform-wide change — if a future epic needs the same capability, promoting this table's design (including its `ON CONFLICT`-based reservation pattern) to `core/` is a natural, low-risk follow-up, not something this plan presumes to do unilaterally.
**[CORRECTED, further clarified]**: The normal concurrency contract has exactly **two** outcomes (replay on commit-then-matching-fingerprint; conflict on commit-then-mismatched-fingerprint), both reachable only after PostgreSQL's own unique-index block has serialized the two requests — not three. A `409` for "observed an in-progress row" is retained purely as a defensive branch (READ COMMITTED visibility rules make it unreachable under normal operation) and must never be documented to API clients as an expected "try again" response, correcting an earlier overstatement of that branch's normalcy.

### ADR-INST-09 — Cross-module event mechanism: transactional outbox, not the in-process bus

**Decision**: Installments publishes domain events via `core/events/outbox.py`, matching `companies`/`users_roles`, not the non-durable `InProcessEventBus` pattern four other business modules (inventory/purchase/sales/accounting/crm) currently use.
**Rationale**: Constitution §49 explicitly requires "events MUST be published within the same database transaction as the originating action (outbox pattern or equivalent)." Repository inspection confirmed the in-process bus variant does **not** satisfy this (events are lost on process restart, never persisted) — it is a pre-existing, undocumented constitutional gap in four sibling modules, not a pattern this plan should propagate into a sixth. Installments is money-adjacent (payment schedules, delinquency, future notification triggers) where losing an event silently is a worse outcome than in, say, a CRM lead-status-changed notification.
**Alternatives considered**: Copy the sibling-module in-process bus for consistency with "how business modules do it today" — rejected because consistency with a non-compliant pattern is not a virtue the Constitution asks for, and the outbox is already a proven, existing, unused-by-business-modules component requiring zero new infrastructure to adopt.
**Consequences**: Installments' `events/` folder will look structurally different from Accounting's/CRM's/Sales' (no local `EventBus`/`get_event_bus()` singleton) — flagged in [§37](#37-risks--trade-offs) as an accepted, justified inconsistency, not an oversight.

### ADR-INST-10 — Audit fail-closed architecture

**Decision**: `InstallmentAuditService.record()` only `flush()`s; the owning service method's single `db.commit()` is the only commit point, so an audit-write failure and a business-mutation failure are the same rollback, not two independently-handled failure modes.
**Rationale**: Directly matches Accounting's own documented discipline (`services/audit_service.py`'s explicit "caller MUST commit" contract) and BR-9A-024's fail-closed precedent, both proven patterns in this codebase already.
**Consequences**: No explicit try/except-around-audit code is ever needed or written — the guarantee is structural (one commit, staged writes before it), not procedural.

### ADR-INST-11 — `REJECTED` is an event, not a persisted lifecycle state

**Decision**: `InstallmentContract.status` never holds the literal value `REJECTED`; `reject()` transitions `PENDING_APPROVAL → DRAFT` and writes an `InstallmentAuditLog(action="REJECTED")` row as the permanent record of the event.
**Rationale**: Spec §11.1's note is explicit and non-negotiable; this matches the existing `_TRANSITIONS`-dict convention already used by `SalesOrder` (`REJECTED → DRAFT (revision)` is itself modeled as a real, transient status there — Installments deliberately does **not** copy that detail, since spec explicitly forbids `REJECTED` as a persisted value for this Epic, a documented, deliberate difference from the closest Sales precedent).
**Consequences**: Any query for "how many contracts were rejected" must query the audit log, not `GROUP BY status` — an explicit, accepted trade-off since spec treats rejection as a workflow event, not a durable classification.

### ADR-INST-12 — `DEFAULTED → ACTIVE` cure semantics

**Decision**: `cure()` is a distinct service method requiring the distinct `installments.contract.cure` permission (never satisfiable via `collection.create`), policy-gated by `InstallmentConfiguration.cure_enabled`, auditable, and structurally incapable of creating a new contract, deleting default/delinquency history, or altering Accounting history (it contains zero calls to any write method on any of those).
**Rationale**: FR-INST-222 and the meta-prompt's explicit instruction to avoid accidentally authorizing cure through the collection permission both point to the same design; `_LEGAL_TRANSITIONS["DEFAULTED"]` including `"ACTIVE"` makes the transition legal, while the separate permission check makes it authorized — two independent gates, matching the platform's general preference for permission-code granularity over transition-table permissiveness alone.
**Consequences**: A tenant that has not enabled curing (`cure_enabled=false`) never sees the action succeed even for a user holding the permission — the policy check runs before the transition-table check, so disabling curing at the tenant level is a true kill switch, not merely a UI hint.

---

**Plan status**: Complete. No blocking technical clarifications remain. **READY FOR `/sp.tasks`.**
