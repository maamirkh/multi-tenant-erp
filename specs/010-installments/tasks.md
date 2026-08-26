# Tasks: Epic 10 — Installments

**Input**: `spec.md`, `plan.md` (as corrected across three targeted correction passes), `research.md`, `data-model.md`, `contracts/installments-api.yaml`, `quickstart.md`
**Prerequisites verified at generation time**: current Alembic head is `061_platform_support_access.py` (unchanged since `plan.md` was written) — the planned migration range `062`–`071` is **confirmed valid, no renumbering required**. No material repository drift was found during re-inspection; every architectural decision in `plan.md` remains implementable as written.

**[CORRECTED — targeted correction pass]** This tasks.md was re-audited and corrected across six defect areas found in the first draft: (1) the `installment_configurations` uniqueness constraint was insufficient for PostgreSQL NULL semantics; (2) the high-risk-command idempotency graph had gaps (reversal/cancellation/write-off missing explicit `T090`-equivalent wiring, and "default" was implementable before its idempotency prerequisite existed); (3) Phase 3's eligibility/draft-creation tasks read live Accounting AR data with no defined module boundary; (4) three Phase 6 failure-injection tests referenced Installments-side entities that don't exist until later phases; (5) one dependency pointed at a model instead of the service that implements the method actually being called; (6) one dependency was self-referential/non-executable, and a full mechanical `[P]`-safety audit found and fixed 15 additional same-file parallel-marking errors. Fixing these required inserting 6 new tasks and removing 1 (a Phase-5 endpoint moved to Phase 10), so **every task from `T046` onward was renumbered** relative to the first draft — this renumbering was performed mechanically (scripted, not by hand) and the entire resulting dependency graph was validated to contain zero dangling references, zero self-references, and zero forward references (a task depending on a numerically later one).

**[CORRECTED — Correction 7, post-Phase-4 targeted gap closure]** Phase 4's closure review discovered that FR-INST-011 ("contracts created ... with fully custom terms within the tenant's configured policy bounds") had no task anywhere in this document assigning ownership of validating `frequency`/`installment_count`/`down_payment_amount`/`financed_amount` against the effective `InstallmentConfiguration` — neither Phase 3's `create_draft()` (T049) nor Phase 4's `preview()` (T069) enforced it, and both are already implemented/committed. Closed by inserting a new **Phase 4.5** (five tasks, `T073A`–`T073E`) between the already-closed Phase 4 and Phase 5, using suffixed IDs specifically so **no already-completed task (T001–T073) or already-numbered future task (T074 onward) is renumbered** — every existing dependency reference in Phases 5–15 remains valid unchanged. Phase 3/Phase 4's own exit-gate proofs are not reopened; Phase 4.5 is a strictly additive precondition retrofitted onto their already-proven call sites. See `plan.md` §10.6 for the ownership rationale.

**Organization**: This tasks.md preserves `plan.md` §36's 15-phase implementation sequence **exactly**, per explicit instruction — phases are NOT flattened or reorganized around spec.md's user stories. Where a task's completion materially advances a specific user story (US-1..US-8, spec.md §8), that is noted inline as `(→ USn)` for traceability, but phase boundaries and dependency order are authoritative. Tests are included as first-class work inside each phase (not deferred to one final phase), per explicit instruction, with Phase 15 providing final cross-cutting/E2E/regression closure.

**Format**: `- [ ] [TaskID] [P?] Description with file path — Depends on: ... (→ USn / FR-INST-xxx)`
`[P]` = safe to run in parallel (different files, no shared unfinished dependency). Absence of `[P]` means sequential/blocking.

---

## Phase 0: Database Schema (Migrations) — prerequisite for all phases

**Purpose**: Create every Installments table, constraint, and index up front, in one FK-respecting, correctly-chained Alembic sequence, so every later phase builds against real, already-existing tables (never a table before its migration exists, per plan.md §23/§30). Grouped here rather than spread across phases specifically to guarantee a single, valid, linear `down_revision` chain matching `plan.md` §30's approved `062`→`071` numbering exactly.

- [x] T001 Create migration `062_installments_foundation.py` in `backend/migrations/versions/` — `down_revision="061"` — creates `installments_feature_flags` (company_id, flag_key default `'feature.installments.enabled'`, is_enabled default false, unique `(company_id, flag_key)`), `installment_sequences` (document_type CHECK `IN ('IC')`, prefix, current_value, year, reset_yearly, format_pattern, unique `(company_id, document_type, year)`), `installment_configurations` (all fields per plan.md §7.1) — **[CORRECTED]** a plain `UNIQUE(company_id, branch_id)` is insufficient because PostgreSQL treats multiple `NULL`s in `branch_id` as distinct, so it would never actually block a second company-level row; instead create **two explicit partial unique indexes**: `uq_installment_configurations_branch ON installment_configurations(company_id, branch_id) WHERE branch_id IS NOT NULL` (branch-specific overrides — different branches coexist, a duplicate for the same branch is rejected) and `uq_installment_configurations_company_default ON installment_configurations(company_id) WHERE branch_id IS NULL` (at most one company-level/default row per company) — working `downgrade()` (drops both partial indexes before dropping the table) — (→ plan.md §30)
- [x] T002 Create migration `063_installments_templates.py` — `down_revision="062"` — creates `installment_plan_templates` (fields per plan.md §7.1, unique `(company_id, name) WHERE is_deleted=false`, FK to none external) — working `downgrade()`
- [x] T003 Create migration `064_installments_contracts.py` — `down_revision="063"` — creates `installment_contracts` (all fields per plan.md §7.1, `version INT DEFAULT 1`, unique `(company_id, contract_number)`, **partial unique index** `uq_installment_contracts_one_nonterminal_per_obligation ON installment_contracts(company_id, sales_invoice_id) WHERE status NOT IN ('CANCELLED','COMPLETED','WRITTEN_OFF')`, `ck_installment_contracts_status` CHECK enumerating the 8 lifecycle states with **no `REJECTED`**, `ck_installment_contracts_positive_amounts`) — working `downgrade()` — (→ BR-INST-INST-042 one-contract invariant)
- [x] T004 Create migration `065_installments_schedule.py` — `down_revision="064"` — creates `installment_schedule_versions` (FK `contract_id` RESTRICT, unique `(contract_id, version_number)`, `ck_installment_schedule_versions_status`) and `installment_schedule_lines` (plain `Base`, explicit `company_id`, FK `schedule_version_id` RESTRICT, unique `(schedule_version_id, sequence)`, `ck_installment_schedule_lines_positive_amount`, `waived_at/by/reason`, `voided_at/by/reason`, **no `updated_at`/soft-delete columns** — append-only) — working `downgrade()`
- [x] T005 Create migration `066_installments_allocation_and_charges.py` — `down_revision="065"` — creates `installment_allocation_references` (plain `Base`, explicit `company_id`, FKs `contract_id`/`schedule_line_id` RESTRICT, no FK on `accounting_payment_id`/`accounting_payment_allocation_line_id`, self-FK `reverses_allocation_reference_id` RESTRICT, **append-only**) and `installment_late_charges` (FKs `contract_id`/`schedule_line_id` RESTRICT, `accounting_journal_entry_id` no-FK, `accounting_ar_transaction_id` no-FK **[corrected field, plan.md §7.1]**, unique `(schedule_line_id, overdue_occurrence_date)`, `waived_at/by/reason`) — working `downgrade()`
- [x] T006 Create migration `067_installments_idempotency.py` — `down_revision="066"` — creates `installment_idempotency_keys` (`status VARCHAR(15) CHECK IN ('IN_PROGRESS','COMPLETED')` — **no `FAILED` value**, per plan.md §20.1 corrected — unique `(company_id, operation, idempotency_key)`) — working `downgrade()`
- [x] T007 Create migration `068_installments_audit.py` — `down_revision="067"` — creates `installment_audit_log` (plain `Base`, explicit `company_id`, `entity_type/entity_id/action/actor_user_id/occurred_at/before_state/after_state/session_context/reason`, **append-only**) — working `downgrade()`
- [x] T008 Create migration `069_installments_indexes.py` — `down_revision="068"` — creates every composite/covering index from plan.md §33 not already created inline with its owning table (`ix_installment_contracts_company_customer`, `ix_installment_contracts_company_invoice`, `ix_installment_contracts_company_status`, `ix_installment_contracts_company_branch`, `ix_installment_schedule_lines_version_due_date`, `ix_installment_schedule_lines_due_date`, `ix_installment_allocation_references_line`, `ix_installment_allocation_references_payment`, `ix_installment_audit_log_entity`, `ix_installment_audit_log_time`, `ix_installment_plan_templates_active`) — working `downgrade()`
- [x] T009 Create migration `070_installments_capability_seed.py` — `down_revision="069"` — pure `op.execute()` SQL, `INSERT INTO capabilities (key, module, display_name, grain, is_active) VALUES ('installments','installments','Installments','module',true) ON CONFLICT (key) DO NOTHING` (mirrors `056_crm_permission_backfill.py`'s style, no app-code import) — working `downgrade()` (`DELETE FROM capabilities WHERE key='installments'`, guarded to skip if referenced by `plan_capabilities`)
- [x] T010 Create migration `071_installments_permission_backfill.py` — `down_revision="070"` — pure `op.execute()` SQL, idempotent `ON CONFLICT DO NOTHING` INSERTs of all 16 `installments.*` permission codes into `permissions`, and default grants into `role_permissions` scoped `WHERE r.is_system = true` per the exact per-role table in plan.md §30.1 (owner/admin: all 16; manager: `contract.view/approve/reschedule/cancel/default/writeoff`, `charge.waive`, `settlement.execute`, `contract.cure`, `report.view`; accountant: `contract.view`, `collection.reverse`, `settlement.execute`, `report.view`; salesperson: `contract.view/create`, `plan.manage`; cashier: `contract.view`, `collection.create`; store-keeper: none; viewer: `contract.view`, `report.view`) — **mandatory, not conditional** (plan.md §30.1) — working `downgrade()` (delete `role_permissions` rows before `permissions` rows, matching `056`'s child-before-parent order)
- [x] T011 Run full bidirectional migration verification (`alembic upgrade head` then `alembic downgrade 061` then `alembic upgrade head` again) against a real Postgres test database, per the project's existing migration-verification convention — Depends on: T001-T010

**PHASE 0 EXIT GATE**: All 10 migrations apply and downgrade cleanly against real Postgres; the partial unique index and every CHECK constraint are verified present via `\d installment_contracts` (or equivalent introspection); no existing table is altered; `alembic upgrade head` from a fresh empty database succeeds end-to-end.

---

## Phase 1: Module Foundation

**Purpose**: Module skeleton, permission codes, domain enums/exceptions, base schemas — the non-negotiable scaffolding every later phase imports.

- [x] T012 Create `backend/modules/installments/__init__.py`, `constants.py`, `dependencies.py`, `exceptions.py`, `router.py` (empty `APIRouter(tags=["installments"])`), `events/__init__.py` as empty/skeleton files matching the exact vertical-slice shape used by `modules/accounting`/`modules/crm` (no `api/`/`permissions/`/`validators/` subfolders, per plan.md §2/§12)
- [x] T013 [P] Define `InstallmentContractStatus` enum (`DRAFT, PENDING_APPROVAL, APPROVED, ACTIVE, DEFAULTED, COMPLETED, CANCELLED, WRITTEN_OFF` — **no `REJECTED`**) and the `_LEGAL_TRANSITIONS` dict skeleton in `backend/modules/installments/constants.py` (plan.md §9.1/§9.2)
- [x] T014 **[CORRECTED — Correction 6: removed incorrect `[P]` marker]** Define `InstallmentOperationClass` enum (`ORIGINATION, SERVICING, READ, ADMIN`) in `backend/modules/installments/constants.py` (plan.md §15.2) — **not parallel-safe with T013/T015**: all three edit the same file — Depends on: T013
- [x] T015 **[CORRECTED — Correction 6: removed incorrect `[P]` marker]** Define all 16 `installments.*` permission code constants (dot-notation, matching plan.md §16.1's table incl. `installments.contract.cure`) in `backend/modules/installments/constants.py`, following the exact `PermissionDefinition`-tuple style used in `modules/accounting/constants.py` — **not parallel-safe with T013/T014**: all three edit the same file — Depends on: T014
- [x] T016 [P] Add `INSTALLMENTS_PERMISSIONS` tuple and per-system-role frozensets (`_INSTALLMENTS_OWNER`, `_INSTALLMENTS_ADMIN`, `_INSTALLMENTS_MANAGER`, `_INSTALLMENTS_ACCOUNTANT`, `_INSTALLMENTS_SALESPERSON`, `_INSTALLMENTS_CASHIER`, `_INSTALLMENTS_VIEWER` — matching T010's migration grant table exactly) unioned into `INITIAL_PERMISSIONS`/`DEFAULT_ROLE_PERMISSIONS` in `backend/modules/users_roles/constants.py`, so `RoleSeedService` grants them to every **new** company automatically (plan.md §30.1 point 1) — Depends on: T015
- [x] T017 [P] Define the Installments exception hierarchy in `backend/modules/installments/exceptions.py`: `InstallmentNotFoundError`, `InstallmentSelfApprovalNotAllowedError`, `InstallmentIllegalTransitionError`, `InstallmentConcurrentModificationError`, `InstallmentOutstandingBalanceRemainsError`, `InstallmentsNotEntitledError`, `InstallmentFiscalPeriodLockedError`, `DegenerateScheduleError`, `InstallmentIdempotencyConflictError` — each subclassing the appropriate `core/exceptions/base.py` class (`NotFoundException`, `ConflictException`, `ForbiddenException`, `ValidationException`) with a documented error `code`
- [x] T018 [P] Create `backend/modules/installments/schemas/base.py` with `InstallmentsBaseSchema` (Pydantic v2 base) mirroring `modules/accounting/schemas/base.py`'s conventions
- [x] T019 [P] Create empty test-directory scaffolding with `__init__.py`: `backend/tests/unit/modules/installments/`, `backend/tests/integration/repositories/installments/`, `backend/tests/integration/api/v1/installments/`, `backend/tests/security/installments/`, `backend/tests/performance/installments/`
- [x] T020 [P] Unit test: `_LEGAL_TRANSITIONS` table has no path to a persisted `REJECTED` value and no transition outside the enumerated set is present, in `backend/tests/unit/modules/installments/test_lifecycle_transitions_table.py` — Depends on: T013

**PHASE 1 EXIT GATE**: `backend/modules/installments` imports cleanly with zero circular-import errors; all 16 permission codes exist in `INITIAL_PERMISSIONS`; a freshly-created test company automatically receives the correct per-role grants (verified by T016's own seeding, exercised in Phase 2 testing); exception hierarchy covers every named failure mode in plan.md §22.

---

## Phase 2: Configuration & Plans

**Purpose**: Tenant policy configuration, plan templates, module entitlement wiring — everything a contract will later snapshot from.

- [x] T021 [P] Create `InstallmentConfiguration` SQLAlchemy model in `backend/modules/installments/models/configuration.py` (`TenantBaseModel`, all fields per plan.md §7.1/data-model.md) — **[CORRECTED]** `__table_args__` declares the two partial unique indexes from T001 (`uq_installment_configurations_branch WHERE branch_id IS NOT NULL`, `uq_installment_configurations_company_default WHERE branch_id IS NULL`), matching the migration exactly — Depends on: T001
- [x] T022 [P] Create `InstallmentPlanTemplate` model in `backend/modules/installments/models/plan_template.py` — Depends on: T002
- [x] T023 [P] Create `InstallmentsFeatureFlag` model in `backend/modules/installments/models/feature_flag.py` (mirrors `CrmFeatureFlag` exactly) — Depends on: T001
- [x] T024 [P] Create `InstallmentSequence` model in `backend/modules/installments/models/sequence.py` — Depends on: T001
- [x] T025 `InstallmentConfigurationRepository(BaseRepository[InstallmentConfiguration])` in `backend/modules/installments/repositories/configuration.py` — company_id-scoped, `get_effective_config(company_id, branch_id)` (branch override → company fallback) — Depends on: T021
- [x] T026 [P] `InstallmentPlanTemplateRepository` in `backend/modules/installments/repositories/plan_template.py` — Depends on: T022
- [x] T027 [P] `InstallmentsFeatureFlagRepository` in `backend/modules/installments/repositories/feature_flag.py` (mirrors `CrmFeatureFlagRepository`) — Depends on: T023
- [x] T028 [P] `InstallmentSequenceRepository` with a `generate_next_number(company_id)` method using `SELECT...FOR UPDATE` locked-row increment, mirroring `SalesSequenceService`/`AccountingSequenceService`'s exact locking pattern, formatting `IC-YYYY-NNNNNN`, in `backend/modules/installments/repositories/sequence.py` — Depends on: T024
- [x] T029 `InstallmentConfigurationService` in `backend/modules/installments/services/configuration_service.py` — get/update effective config, validates `min_term <= max_term` and at most one of `min_down_payment_pct`/`min_down_payment_amount` set — Depends on: T025
- [x] T030 `InstallmentPlanTemplateService` in `backend/modules/installments/services/plan_template_service.py` — create/edit/deactivate, enforces unique-name-per-company — Depends on: T026
- [x] T031 `InstallmentsFeatureFlagService` (mirrors `CrmFeatureFlagService`: `is_enabled()`/`enable()`/`disable()`) in `backend/modules/installments/services/feature_flag_service.py` — Depends on: T027
- [x] T032 `InstallmentsModuleEnablementProvider(ModuleEnablementProvider)` implementing `is_enabled(company_id)` via T031, registered in `modules/platform_admin/services/module_enablement.py`'s `get_module_enablement_provider()` factory alongside `CrmModuleEnablementProvider` — Depends on: T031
- [x] T033 Add `{"key": "installments", "module": "installments", "display_name": "Installments"}` to `CapabilitySeedService.MODULE_CAPABILITY_CATALOGUE` in `modules/platform_admin/services/capability_seed_service.py` — Depends on: T009
- [x] T034 [P] `user_has_installments_permission(db, company_id, user_id, code, *, user_roles=None)` free function in `backend/modules/installments/services/permission_check.py`, mirroring `user_has_accounting_permission()` exactly — Depends on: T015
- [x] T035 [P] Pydantic schemas for Configuration/PlanTemplate CRUD in `backend/modules/installments/schemas/configuration.py`, `schemas/plan_template.py` — Depends on: T018
- [x] T036 Endpoint group: Configuration (`GET/PUT /companies/{company_id}/installments/config`, `GET/PUT .../config/branches/{branchId}`) in `backend/modules/installments/router.py`, permission `installments.config.manage`, operation class ADMIN — Depends on: T029, T034, T035
- [x] T037 Endpoint group: Plans/Templates (`GET/POST /plans`, `GET/PATCH /plans/{id}`, `POST /plans/{id}/deactivate`) in `router.py`, permission `installments.plan.manage`, operation class ORIGINATION — Depends on: T030, T034, T035
- [x] T038 [P] `InstallmentAuditService`/`InstallmentAuditLog` model+repository+service (flush-only `record()`, mirroring `AuditLogService`'s "caller MUST commit" contract exactly) in `backend/modules/installments/models/audit.py`, `repositories/audit.py`, `services/audit_service.py` — Depends on: T007
- [x] T039 Repository test (real Postgres — partial unique indexes are Postgres-specific, not SQLite-provable, mirroring the `057-061`/T053 precedent): `InstallmentConfigurationRepository`/`InstallmentPlanTemplateRepository` tenant isolation (two-tenant fixture, mirroring `test_tenant_isolation.py`'s `two_tenants` pattern) **[CORRECTED — amended to also prove the T001 uniqueness invariant]** plus: (a) only one company-level configuration (`branch_id IS NULL`) may exist per company — a second attempt is rejected by `uq_installment_configurations_company_default`; (b) two different branch overrides for the same company coexist without conflict; (c) a duplicate configuration for the *same* branch is rejected by `uq_installment_configurations_branch` — in `backend/tests/integration/repositories/installments/test_configuration_repository.py` — Depends on: T025, T026, Phase 0 (T011) — no longer `[P]` (now requires the real-Postgres fixture, shared with other Phase-0-dependent tests, not safely parallel with a purely-SQLite-scoped test)
- [x] T040 [P] Service test: template deactivation blocks new use but leaves existing contracts unaffected (placeholder assertion against template state only, full contract-linkage test deferred to Phase 3) in `backend/tests/unit/modules/installments/test_plan_template_service.py` — Depends on: T030
- [x] T041 [P] Integration test: `InstallmentsModuleEnablementProvider`/`Capability` registration — a Platform Admin can grant/toggle the `installments` capability and it resolves via `PlatformEntitlementService.resolve_effective_entitlement()` exactly per the CRM precedent, in `backend/tests/integration/api/v1/installments/test_entitlement_registration.py` — Depends on: T032, T033
- [x] T042 **[CORRECTED — Correction 6: removed incorrect `[P]` marker]** Admin endpoint group (`GET /installments/status`, `POST /installments/enable`, `POST /installments/disable`), rank-gated (`ADMIN_RANK`), reachable regardless of entitlement state (mirrors CRM's `admin_router`), in `router.py` — **not parallel-safe**: T036/T037 also write `router.py` within this phase, so all three must be sequenced against each other despite touching logically-separate endpoint groups — Depends on: T031, T034, T036, T037

**PHASE 2 EXIT GATE**: A test company can have its Installments module toggled on/off; effective configuration resolves branch-override-then-company-fallback correctly; plan templates are creatable/deactivatable; the `installments` Capability is registered and resolves through the unmodified `PlatformEntitlementService`; tenant isolation proven for both new tables.

---

## Phase 3: Contract Persistence

**Purpose**: `InstallmentContract` aggregate root, tenant-scoped numbering, the one-contract-per-obligation invariant (DB + service layer).

- [x] T043 `InstallmentContract` SQLAlchemy model in `backend/modules/installments/models/contract.py` (all fields per plan.md §7.1/data-model.md, `version` optimistic-concurrency column) — Depends on: T003
- [x] T044 `InstallmentContractRepository(BaseRepository[InstallmentContract])` in `backend/modules/installments/repositories/contract.py` — `get_by_id_or_none(id, company_id)`, `get_by_id_locked(id, company_id)` (`SELECT...FOR UPDATE`), `find_active_by_sales_invoice(company_id, sales_invoice_id)`, conditional-`UPDATE...WHERE version=expected` method for optimistic transitions (mirrors `adjustment_repository.py`'s pattern) — Depends on: T043
- [x] T045 [P] Read-only cross-module accessor: `SalesInvoiceReadGateway`/`SalesCustomerReadGateway` thin wrappers importing `modules.sales.repositories.{invoice,customer}` directly (read-only, mirrors `Customer360Service`'s pattern) in `backend/modules/installments/services/sales_read_gateway.py` — Depends on: T012
- [x] T046 **[NEW — Correction 3: single controlled Installments→Accounting boundary, introduced early]** `AccountingIntegrationGateway` **read-only skeleton** in `backend/modules/installments/services/accounting_gateway.py` — created here (Phase 3), not deferred to Phase 6, specifically so no earlier task is ever tempted to import `modules.accounting.models`/`.repositories` directly. Exposes only the live-read operations eligibility/draft-creation genuinely need: `get_invoice_outstanding_amount(company_id, sales_invoice_id)` and `get_ar_transaction(company_id, ar_transaction_id)`, each calling an existing **read-only** `AccountsReceivableService` method (e.g. `get_open_transactions()`/a targeted lookup — no new Accounting-side method required for reads) — imports only `modules.accounting.services` classes, **never** `.models` or `.repositories` — include, as part of this task, a grep-based structural/import-lint check (mirroring the Platform-Admin structural-boundary test convention, T200/renumbered) confirming `accounting_gateway.py` contains no `from modules.accounting.models` / `from modules.accounting.repositories` import, re-run again after Phase 6 extends this same class. This is the **same class** Phase 6 (T107, renumbered) later *extends* with money-mutating staged/finalize methods — **one gateway, not two competing abstractions**. No Accounting balance is cached or duplicated inside Installments; every call is a live pass-through read — Depends on: T012
- [x] T047 `InstallmentEligibilityService.check_invoice_eligibility(company_id, sales_invoice_id)` in `backend/modules/installments/services/eligibility_service.py` — asserts invoice `status=="ISSUED"`, sufficient outstanding via `AccountingIntegrationGateway.get_invoice_outstanding_amount()` **[CORRECTED — now depends on the explicit read-boundary gateway, not an undefined "Accounting AR read"]** (not a Sales field, per plan.md §13), customer `ACTIVE`/not blocked — Depends on: T045, T046
- [x] T048 Terms-snapshot builder: pure function `build_terms_snapshot(...) -> dict` in `backend/modules/installments/services/contract_service.py`, self-sufficient JSONB explanation of the obligation (FR-INST-041) — Depends on: T043
- [x] T049 `InstallmentContractService.create_draft(company_id, ...)` — computes `financed_principal = invoice_outstanding_amount - down_payment` from `AccountingIntegrationGateway.get_invoice_outstanding_amount()` (T046, never a stale/duplicated field, FR-INST-261), assigns `contract_number` via `InstallmentSequenceRepository.generate_next_number()`'s locked increment, sets `status=DRAFT`, calls terms-snapshot builder (T048) — pre-checks the one-contract-per-obligation invariant for a clean 409 (DB partial unique index is the real backstop) — in `services/contract_service.py` — **[CORRECTED — Correction 5]** dependency corrected from the sequence *model* (T024) to the task that actually *implements* the locked number-generation method (T028) — calling a method requires depending on its implementer, not merely the table it reads/writes — Depends on: T044, T047, T048, T028, T046
- [x] T050 [P] Pydantic schemas for Contract create/read/summary in `backend/modules/installments/schemas/contract.py` — Depends on: T018
- [x] T051 Endpoint group: Contracts (`GET /contracts`, `GET /contracts/{id}`, `POST /contracts`) in `router.py`, permissions `installments.contract.view`/`.create`, operation classes READ/ORIGINATION — Depends on: T049, T034, T050
- [x] T052 Endpoint group: Eligibility (`GET /eligibility?sales_invoice_id=`) in `router.py` — Depends on: T047, T034
- [x] T053 [P] Repository test (real Postgres): concurrent draft-creation race against the same `sales_invoice_id` — assert exactly one succeeds via the partial unique index, the loser receives a clean `409` translated from `IntegrityError`, in `backend/tests/integration/repositories/installments/test_contract_one_per_obligation.py` — Depends on: T044, Phase 0 (T011)
- [x] T054 [P] Repository test: `InstallmentContract` tenant isolation and IDOR (cross-tenant `get_by_id_or_none` returns `None` → service maps to 404 indistinguishable from non-existence) in `backend/tests/security/installments/test_contract_tenant_isolation.py` — Depends on: T044
- [x] T055 [P] Service test: `create_draft()` rejects a cross-tenant `sales_invoice_id` reference and a currency mismatch is impossible (`currency_code` always sourced from the invoice) in `backend/tests/unit/modules/installments/test_contract_creation.py` — Depends on: T049
- [x] T056 **[CORRECTED — Correction 6: removed incorrect `[P]` marker]** Service test: pre-existing partial invoice payments correctly reduce `financed_principal` (FR-INST-261) — same file as T055 (`test_contract_creation.py`), **not parallel-safe with it** — Depends on: T049, T055

**PHASE 3 EXIT GATE**: A draft contract can be created against an eligible invoice; the one-contract-per-obligation invariant is proven race-safe under real Postgres; cross-tenant access is indistinguishable from non-existence; contract numbering is gap-free and tenant-scoped.

---

## Phase 4: Schedule Engine

**Purpose**: Deterministic, pure, DB/HTTP-independent schedule generation — unit-tested before any persistence integration, per explicit instruction.

- [x] T057 [P] Pure `ScheduleEngine.generate(principal, down_payment, markup, installment_count, frequency, first_due_date, rounding_policy) -> ScheduleGenerationResult` in `backend/modules/installments/services/schedule_engine.py` — zero DB/HTTP imports (plan.md §10.1)
- [x] T058 **[CORRECTED — Correction 6: removed incorrect `[P]` marker]** `_add_months(d, n)` month-end-clamping helper (day 31 anchored → month's actual last day) using stdlib `calendar.monthrange()`, in `schedule_engine.py` — **not parallel-safe with T060**: both edit `schedule_engine.py` — Depends on: T057
- [x] T059 [P] `get_business_date()` single business-date source helper (never ad hoc `datetime.now()`), in `backend/modules/installments/services/business_date.py`
- [x] T060 Amount-splitting/residual logic: `base_line_amount = round(total/count, 6); last = total - sum(others)`, raising `DegenerateScheduleError` if the final line would be `<= 0`, in `schedule_engine.py` — Depends on: T057, T017, T058
- [x] T061 [P] Unit test: monthly/weekly/quarterly frequency due-date sequencing in `backend/tests/unit/modules/installments/test_schedule_engine_frequency.py` — Depends on: T057, T058
- [x] T062 [P] Unit test: month-end anchoring (day-31-in-30-day-month clamping) in `backend/tests/unit/modules/installments/test_schedule_engine_month_end.py` — Depends on: T058
- [x] T063 [P] Unit test: leap-year date arithmetic correctness in `backend/tests/unit/modules/installments/test_schedule_engine_leap_year.py` — Depends on: T058
- [x] T064 [P] Unit test: `ROUND_HALF_UP` quantization to `Decimal("0.000001")` and exact `sum(lines) == contractual_total` reconciliation (BR-INST-005) in `backend/tests/unit/modules/installments/test_schedule_engine_rounding.py` — Depends on: T060
- [x] T065 [P] Unit test: degenerate final-installment (zero/negative) is rejected with `DegenerateScheduleError`, never silently produced (spec §28 edge case) in `backend/tests/unit/modules/installments/test_schedule_engine_degenerate.py` — Depends on: T060
- [x] T066 [P] Unit test: identical inputs → byte-identical output across repeated calls (determinism, FR-INST-031/BR-INST-019) in `backend/tests/unit/modules/installments/test_schedule_engine_determinism.py` — Depends on: T057
- [x] T067 `InstallmentScheduleVersion`/`InstallmentScheduleLine` models in `backend/modules/installments/models/schedule.py` — Depends on: T004
- [x] T068 `InstallmentScheduleRepository` — persists a version + lines atomically (flush only, no independent commit — caller owns the transaction per plan.md §21), `get_active_version(contract_id)`, `get_version(contract_id, version_number)`, no `update_schedule_line()` method (immutability enforced by omission) — in `backend/modules/installments/repositories/schedule.py` — Depends on: T067
- [x] T069 `InstallmentQuoteService.preview(...)` — calls `ScheduleEngine.generate()` directly, returns the result with **zero persistence and zero audit event** (FR-INST-032) — in `backend/modules/installments/services/quote_service.py` — Depends on: T057
- [x] T070 [P] Pydantic schema for the quote/preview response in `backend/modules/installments/schemas/schedule.py` — Depends on: T018
- [x] T071 Endpoint: Quote/Preview (`POST /quotes`) in `router.py`, permission `installments.contract.create`, operation class ORIGINATION — Depends on: T069, T034, T070
- [x] T072 [P] Repository test: schedule-version immutability — assert no update method exists on `InstallmentScheduleRepository` (a "doesn't exist" structural test, mirroring plan.md §31's own instruction) in `backend/tests/integration/repositories/installments/test_schedule_immutability.py` — Depends on: T068
- [x] T073 [P] Repository test: `InstallmentScheduleLine` append-only persistence and unique `(schedule_version_id, sequence)` in `backend/tests/integration/repositories/installments/test_schedule_persistence.py` — Depends on: T068

**PHASE 4 EXIT GATE**: `ScheduleEngine` is 100% unit-tested with zero DB/HTTP dependency; quote preview is provably non-mutating and non-audited; schedule persistence is structurally immutable (no update path exists in code).

---

## Phase 4.5: Installment Terms Policy Validation **[NEW — Correction 7, retrofit gate]**

**Purpose**: Close the confirmed FR-INST-011 gap — "installment contracts ... created ... with fully custom terms within the tenant's configured policy bounds" had no assigned implementation task. Retrofits the two already-completed call sites (Phase 3's `create_draft()`, Phase 4's `preview()`) with **one** shared validator; does not reopen either phase's own exit-gate proof. See plan.md §10.6.

Task IDs are suffixed (`T073A`–`T073E`) specifically so no existing task number — completed or not-yet-started — is renumbered.

- [x] T073A [P] `InstallmentTermsPolicyValidator.validate(config, *, frequency, installment_count, down_payment_amount, financed_amount)` in `backend/modules/installments/services/terms_policy_validator.py` — the single, reusable, stateless implementation of FR-INST-011's policy-bounds check: `frequency` must be a member of `InstallmentConfiguration.allowed_frequencies`; `installment_count` must be within `[min_term, max_term]`; `down_payment_amount` must satisfy whichever of `min_down_payment_pct`/`min_down_payment_amount` is configured (T029 already guarantees at most one is set); `financed_amount` must not exceed `max_financed_amount` when configured. Raises the new `InstallmentTermsPolicyViolationError` (added to `exceptions.py` in this same task — subclasses `ValidationException`, `code="TERMS_POLICY_VIOLATION"`, `details` names the specific violated field(s)) — never a bare `ValueError`/unhandled 500. `config is None` (tenant has no configuration row yet) means "no bounds configured," not "everything forbidden" — the validator is a no-op in that case — Depends on: T029, T017
- [x] T073B Retrofit `InstallmentQuoteService.preview()` (T069) to call `InstallmentTermsPolicyValidator.validate()` — using the same effective-configuration lookup `preview()` already performs for `rounding_policy`, no second config read — before invoking `ScheduleEngine.generate()`, propagating `InstallmentTermsPolicyViolationError` as the OpenAPI-documented `/quotes` `422` response — in `backend/modules/installments/services/quote_service.py` — Depends on: T073A, T069
- [x] T073C Retrofit `InstallmentContractService.create_draft()` (T049) to call the **same** `InstallmentTermsPolicyValidator.validate()` (imported, never reimplemented) before constructing/persisting the `InstallmentContract` row, so direct contract creation cannot bypass the policy check enforced at quote time — in `backend/modules/installments/services/contract_service.py` — Depends on: T073A, T049
- [x] T073D [P] Unit tests for `InstallmentTermsPolicyValidator` in `backend/tests/unit/modules/installments/test_terms_policy_validator.py`: valid terms pass; disallowed frequency rejected; `installment_count` below configured `min_term` rejected; `installment_count` above configured `max_term` rejected; `down_payment_amount` below the configured minimum (both `min_down_payment_pct` and `min_down_payment_amount` variants) rejected; `financed_amount` exceeding `max_financed_amount` rejected; a branch-specific override (`InstallmentConfigurationService.get_effective_config(company_id, branch_id)`) is honored over the company-level default row when both exist for the same company — Depends on: T073A
- [x] T073E [P] Regression/structural test proving single-validator reuse (no duplicated policy logic) in `backend/tests/unit/modules/installments/test_terms_policy_enforced_everywhere.py`: (1) identical disallowed terms are rejected identically by both `InstallmentQuoteService.preview()` and `InstallmentContractService.create_draft()`, raising the same `InstallmentTermsPolicyViolationError`/`code`; (2) a structural `inspect.getsource()` check confirms `contract_service.py` contains no independently-reimplemented bounds comparison (no second `allowed_frequencies`/`min_term`/`max_term`/`min_down_payment`/`max_financed_amount` check outside a call into `InstallmentTermsPolicyValidator`); (3) calling `InstallmentContractService.create_draft()` directly with out-of-policy terms (bypassing `/quotes`/the router entirely) still raises — proving the check is service-layer-enforced, not merely front-end or router-level — Depends on: T073B, T073C

**PHASE 4.5 EXIT GATE**: `InstallmentTermsPolicyValidator` is the single implementation of FR-INST-011's policy-bounds check; both `preview()` and `create_draft()` call it — never a second copy; a direct `create_draft()` call that bypasses `/quotes` entirely is still rejected for out-of-policy terms; branch-override-vs-company-fallback resolution is proven; an unconfigured tenant is never wrongly blocked.

---

## Phase 5: Contract Lifecycle

**Purpose**: Explicit named lifecycle methods, `_LEGAL_TRANSITIONS` enforcement, maker-checker on approve/reject — no generic `set_status()`.

- [x] T074 `InstallmentContractService.submit(contract_id, actor_id)` — `DRAFT→PENDING_APPROVAL` or `DRAFT→APPROVED` if no threshold applies (FR-INST-101), asserts `_LEGAL_TRANSITIONS`, audits, in `services/contract_service.py` — Depends on: T049, T038, T013
- [x] T075 `InstallmentContractService.approve(contract_id, approver_id)` — asserts `contract.submitted_by != approver_id` or raises `InstallmentSelfApprovalNotAllowedError`, checks `installments.contract.approve`, transitions `PENDING_APPROVAL→APPROVED`, audits — Depends on: T074, T034
- [x] T076 `InstallmentContractService.reject(contract_id, reason, rejecter_id)` — **same distinct-approver check as `approve()`, applied symmetrically from day one** (plan.md §16.2, explicitly avoiding the documented Accounting historical gap), transitions `PENDING_APPROVAL→DRAFT`, audits `action="REJECTED"` (never a persisted status), mandatory `reason` — Depends on: T075
- [x] T077 `InstallmentContractService.cancel(contract_id, reason, actor_id)` — legality varies by stage (DRAFT/PENDING_APPROVAL/APPROVED: free; ACTIVE-no-collections: free; ACTIVE-with-activity: delegates to reversal, wired in Phase 10) — stub the no-financial-activity path now, financial-activity path completed in Phase 10 — Depends on: T074
- [x] T078 `InstallmentContractService.mark_defaulted(contract_id, reason, actor_id)` — **[CORRECTED — scope narrowed to the internal lifecycle/domain-transition primitive only]** the pure `ACTIVE→DEFAULTED` state-machine transition (`_LEGAL_TRANSITIONS` guard, `status` mutation, mandatory-reason validation) plus staging the audit row (flush only) — **zero Accounting calls**. This method is **internal only**: it is not idempotency-protected, is not directly reachable via any router endpoint, and MUST NOT be called from `router.py`. The externally-callable, idempotency-protected "default" **command** is a separate orchestration task that cannot exist before Phase 5.5 — see the new default-command-orchestration task in Phase 10 — Depends on: T074
- [x] T079 [P] Pydantic schemas for submit/approve/reject/cancel/default request bodies in `backend/modules/installments/schemas/contract.py` — Depends on: T050
- [x] T080 Endpoint group: Submission/Approval/Rejection (`POST /contracts/{id}/submit|approve|reject`) in `router.py`, permissions `.create`/`.approve`, operation class ORIGINATION — Depends on: T074, T075, T076, T034, T079
- [x] T081 [P] Unit test: full `_LEGAL_TRANSITIONS` matrix — every legal transition succeeds, a representative sample of illegal transitions raises `InstallmentIllegalTransitionError`, in `backend/tests/unit/modules/installments/test_lifecycle_transition_matrix.py` — Depends on: T074-T078
- [x] T082 [P] Service test: self-approval denied on **both** `approve()` and `reject()` (explicit regression guard against the documented Accounting/Payment historical gap) in `backend/tests/unit/modules/installments/test_maker_checker.py` — Depends on: T075, T076
- [x] T083 [P] Service test: rejection returns contract to `DRAFT`, never persists `REJECTED`, and the rejection event remains permanently visible in `InstallmentAuditLog` even after resubmission in `backend/tests/unit/modules/installments/test_rejection_not_persisted.py` — Depends on: T076
- [x] T084 [P] Security test: no public `set_status()`/`update_status()` method exists on `InstallmentContractService` (structural/reflective test) in `backend/tests/security/installments/test_no_generic_status_setter.py` — Depends on: T074-T078

**PHASE 5 EXIT GATE**: Every legal lifecycle transition is implemented via a named method; illegal transitions are provably rejected; `REJECTED` is never a persisted status; self-approval is denied symmetrically on approve and reject; no generic status-setter exists anywhere in the public interface.

---

## Phase 5.5: Idempotency Primitive (HARD PREREQUISITE for Phases 7–10's high-risk commands)

**Purpose**: The new, module-local, race-safe idempotency mechanism — required before any high-risk financial command (activation, collection, settlement, reversal, rescheduling, cancellation, default, write-off) can be implemented safely.

- [x] T085 `InstallmentIdempotencyKey` model in `backend/modules/installments/models/idempotency.py` (`status CHECK IN ('IN_PROGRESS','COMPLETED')` — no `FAILED`) — Depends on: T006
- [x] T086 `InstallmentIdempotencyService.reserve(company_id, operation, idempotency_key, request_fingerprint, contract_id) -> ReservationResult` in `backend/modules/installments/services/idempotency_service.py` — uses SQLAlchemy `postgresql.insert(...).on_conflict_do_nothing(index_elements=["company_id","operation","idempotency_key"]).returning(...)` **exactly per plan.md §20.2** — never a bare `INSERT` + caught `IntegrityError` — Depends on: T085
- [x] T087 `InstallmentIdempotencyService.complete(reservation_id, result_payload)` — `UPDATE...SET status='COMPLETED', result_payload=..., completed_at=now()`, flush only (caller commits) — Depends on: T086
- [x] T088 Wire `InstallmentIdempotencyService` to translate reservation outcomes into the exact two-normal-outcome contract (replay on `COMPLETED`+matching fingerprint; `409 IDEMPOTENCY_PAYLOAD_MISMATCH` on `COMPLETED`+mismatched fingerprint) plus the defensive-only `409 IDEMPOTENCY_UNEXPECTED_STATE` branch for an observed `IN_PROGRESS` row (plan.md §20.2/§20.3) — in `idempotency_service.py` — Depends on: T086
- [x] T089 [P] Concurrency test (real Postgres, two DB sessions): concurrent same-key/same-payload requests — session A wins, session B blocks then replays A's result after A commits; assert exactly one financial-adjacent effect (use a placeholder staged write for this test, real financial workflows tested in later phases) — in `backend/tests/integration/repositories/installments/test_idempotency_concurrency.py` — Depends on: T086, Phase 0 (T011)
- [x] T090 **[CORRECTED — Correction 6: removed incorrect `[P]` marker, same implied file as T089]** Concurrency test: concurrent same-key/different-payload — B receives `409 IDEMPOTENCY_PAYLOAD_MISMATCH` after A commits, never both proceed — same file as T089 (`test_idempotency_concurrency.py`), **not parallel-safe with it** — Depends on: T086, T089
- [x] T091 **[CORRECTED — Correction 6: removed incorrect `[P]` marker, same implied file as T089/T090]** Concurrency test: first request's business logic fails after reservation succeeds — whole transaction (including the `IN_PROGRESS` row) rolls back; a retried request with the same key succeeds fresh, key never permanently stranded — same file as T089/T090, **not parallel-safe with them** — Depends on: T086, T090
- [x] T092 [P] Unit test: the reservation `INSERT...ON CONFLICT DO NOTHING` statement never raises `IntegrityError` and never leaves the SQLAlchemy session in an aborted state (assert subsequent statements in the same session succeed post-duplicate-attempt) — **[CORRECTED — explicit distinct file, genuinely different test type (SQLite/unit-level, not the real-Postgres concurrency suite)]** in `backend/tests/unit/modules/installments/test_idempotency_reservation_no_abort.py` — Depends on: T086
- [x] T093 [P] Repository test: idempotency keys are scoped `(company_id, operation, idempotency_key)` — same key reused under a **different** `company_id` or **different** `operation` is treated as an independent key (tenant/operation isolation) in `backend/tests/integration/repositories/installments/test_idempotency_scoping.py` — Depends on: T085

**PHASE 5.5 EXIT GATE**: The idempotency primitive is proven race-safe under real Postgres for all three normal-outcome scenarios; the session-abort failure mode is proven absent; no `FAILED` status is ever persisted; tenant/operation scoping is proven. **No Phase 7–10 high-risk-command task may begin implementation until this gate passes.**

---

## Phase 6: Accounting Integration — ⚠️ CRITICAL HARD GATE ⚠️

**Purpose**: Implement and prove every required Accounting-side staged/finalize extension **before** any dependent Installments money-mutating workflow (Phases 7–10) is implemented. This is the single most important dependency boundary in the entire task graph (plan.md §12.3). All nine new/changed Accounting methods are additive, backward-compatible extractions of existing internals — never new architecture, never a rewrite of `PostingEngine`/`AllocationEngine`'s own logic.

### 6.1 — `AccountsReceivableService` staged/finalize extensions (late charge + write-off)

- [ ] T094 In `backend/modules/accounting/services/ar_service.py`: extract `adjust_receivable()`'s existing logic into a new `stage_adjustment(company_id, customer_id, amount, contra_account_id, reason, posting_date, transaction_type="ADJUSTMENT", source_document_type=None, source_document_id=None, actor_id=None) -> StagedAdjustment` — calls `PostingEngine.stage_direct_posting()` (not `post_direct()`), builds+flushes the `ARTransaction` with the new `transaction_type`/`source_document_type`/`source_document_id` params, recomputes the ledger via `db.add(ledger)` (flush only) — **no commit anywhere in this method** — Depends on: Phase 0
- [ ] T095 In `ar_service.py`: add `finalize_adjustment(staged: StagedAdjustment, actor_id) -> ARTransaction` — thin wrapper calling `self._engine.finalize_and_publish(staged.journal_entry, staged.journal_number, staged.posted_at, actor_id)` — the **sole** commit point — Depends on: T094
- [ ] T096 In `ar_service.py`: rewrite `adjust_receivable(...)` as a thin, 100%-backward-compatible wrapper: `staged = self.stage_adjustment(...); return self.finalize_adjustment(staged, actor_id)` — zero signature/behavior change for existing standalone callers — Depends on: T094, T095
- [ ] T097 In `ar_service.py`: add `reverse_adjustment(company_id, ar_transaction_id, reason, actor_id) -> ARTransaction` — modeled directly on `PaymentService.cancel_payment()`'s stage-then-`PostingEngine.reverse()` pattern (zero `outstanding_amount`, recompute ledger — both flush-only — then call `PostingEngine.reverse()`, whose single commit covers both) — Depends on: T094
- [ ] T098 In `ar_service.py`: extract `confirm_write_off()`'s existing logic into a new `stage_write_off(company_id, ar_transaction_id, reason, actor_id) -> StagedWriteOff` — calls `stage_direct_posting()` (not `post_direct()`), sets `transaction.status`/`outstanding_amount` via `db.add()`+`db.flush()` directly (**not** `self._transactions.update()`, whose internal commit must be avoided per plan.md §2's confirmed finding), inlines the ledger recompute as `db.add(ledger)`+`db.flush()` directly (**not** `self._ledgers.update()`) — **no commit anywhere** — Depends on: Phase 0
- [ ] T099 In `ar_service.py`: add `finalize_write_off(staged: StagedWriteOff, actor_id) -> ARTransaction` — thin wrapper calling `finalize_and_publish()`, the sole commit for GL + transaction status + ledger recompute together — Depends on: T098
- [ ] T100 In `ar_service.py`: rewrite `confirm_write_off(...)` as a thin, backward-compatible wrapper of `stage_write_off()`+`finalize_write_off()` — Depends on: T098, T099

### 6.2 — `PaymentService` + `AllocationEngine` staged/finalize extensions (down payment, collection, settlement)

- [ ] T101 In `backend/modules/accounting/services/payment_service.py`: extract `create_customer_payment()`'s immediate-post-branch logic into `stage_customer_payment(...) -> StagedCustomerPayment | DraftPaymentResult` — for the above-threshold DRAFT branch, preserve its existing early commit unchanged (self-contained, no Accounting truth created yet, out of scope per plan.md §12.3.1) and return `DraftPaymentResult(payment)`; for the immediate-post branch, stage GL via `stage_direct_posting()`, build+flush `Payment`+credit `ARTransaction`, recompute the ledger (flush only) — **no commit** in this branch — Depends on: Phase 0
- [ ] T102 In `payment_service.py`: add `finalize_customer_payment(staged: StagedCustomerPayment, actor_id) -> tuple[Payment, PostingResult]` — thin wrapper calling `finalize_and_publish()` — Depends on: T101
- [ ] T103 In `payment_service.py`: rewrite `create_customer_payment(...)` as a thin, backward-compatible wrapper — Depends on: T101, T102
- [ ] T104 In `backend/modules/accounting/services/allocation_engine.py`: extract `allocate()`'s per-line-loop logic into `stage_allocation(company_id, payment_id, allocation_lines, actor_id) -> StagedAllocation` — every write already uses `db.add()`+`db.flush()` directly (confirmed no hidden repository-`.update()` commits, plan.md §2) — stop **before** the final `finalize_and_publish()`/bare-commit block — Depends on: Phase 0
- [ ] T105 In `allocation_engine.py`: add `finalize_allocation(staged: StagedAllocation, actor_id) -> list[PaymentAllocationLine]` — replicates the existing final block exactly (one `finalize_and_publish()` per staged FX-adjustment entry, or a bare `db.commit()` if none) — Depends on: T104
- [ ] T106 In `allocation_engine.py`: rewrite `allocate(...)` as a thin, backward-compatible wrapper — Depends on: T104, T105

### 6.3 — Installments-side integration gateway and outstanding guard

- [ ] T107 **[CORRECTED — Correction 3: EXTENDS the Phase-3 read-only skeleton (T046), does not create a second/competing gateway class]** Extend `AccountingIntegrationGateway` in `backend/modules/installments/services/accounting_gateway.py` with the money-mutating methods: `record_down_payment()`, `record_collection()`, `reverse_payment()`, `post_late_charge()`, `reverse_late_charge()`, `writeoff()`, each following the exact stage→Installments-rows→finalize-last sequence from plan.md §12.3.1–§12.3.3 — still the **single** module-boundary crossing point; still imports only `modules.accounting.services` classes, never `.models`/`.repositories` — **not parallel-safe with T046** (same file) — Depends on: T046, T096, T097, T100, T103, T106
- [ ] T108 `InstallmentOutstandingService.assert_zero_outstanding(company_id, contract_id)` in `backend/modules/installments/services/outstanding_service.py` — checks schedule outstanding (derived, Phase 4) **and** every linked, non-waived `InstallmentLateCharge`'s live `ARTransaction.outstanding_amount`/`status` via `AccountingIntegrationGateway`'s read path — raises `InstallmentOutstandingBalanceRemainsError(kind=...)` — pure live-read, no duplicated balance (plan.md §9.3) — Depends on: T107

### 6.4 — Backward-compatibility regression proof

- [ ] T109 [P] Regression test: every existing standalone caller of `adjust_receivable()` (grep all call sites in `modules/accounting`) still passes its full existing test suite unmodified — in `backend/tests/integration/repositories/accounting/test_adjust_receivable_backward_compat.py` — Depends on: T096
- [ ] T110 [P] Regression test: every existing standalone caller of `confirm_write_off()` still passes unmodified — Depends on: T100
- [ ] T111 [P] Regression test: every existing standalone caller of `create_customer_payment()` still passes unmodified (incl. the above-threshold DRAFT branch's exact prior behavior) — Depends on: T103
- [ ] T112 [P] Regression test: every existing standalone caller of `allocate()` still passes unmodified — Depends on: T106
- [ ] T113 Run the **full existing Accounting regression suite** (`backend/tests/{unit,integration,security,performance}/**/accounting/`) and confirm 100% green — Depends on: T109-T112

### 6.5 — Forced-failure atomicity tests (release-critical, not optional)

- [ ] T114 [P] **[CORRECTED — Correction 4, Layer A: Accounting-only, no forward reference to not-yet-existing Installments entities]** Real-Postgres forced-failure test: fail *after* `stage_adjustment()` flushes GL/`ARTransaction`/ledger but *before* `finalize_adjustment()` — assert **all** of `JournalEntry`, `ARTransaction`, `CustomerLedger.total_outstanding_base` change are absent post-rollback (a generic caller-supplied placeholder row flushed alongside, standing in for "the caller's own rows," is also confirmed absent — proving the staging point, not any specific Installments entity, which is proven separately once it exists, see the Phase 8 late-charge Layer-B test) — in `backend/tests/integration/repositories/accounting/test_stage_adjustment_atomicity.py` — Depends on: T095
- [ ] T115 [P] **[CORRECTED — Layer A: Accounting-only]** Real-Postgres forced-failure test: fail *after* `stage_customer_payment()`+`stage_allocation()` flush but *before* `finalize_customer_payment()` — assert Payment, credit `ARTransaction`, `PaymentAllocationLine`, target-transaction outstanding change are **all** absent post-rollback (Installments-side row absence proven separately once `InstallmentAllocationReference` exists, see the Phase 7 collection Layer-B test) — in `backend/tests/integration/repositories/accounting/test_stage_customer_payment_atomicity.py` — Depends on: T102, T105
- [ ] T116 [P] **[CORRECTED — Layer A: Accounting-only]** Real-Postgres forced-failure test: fail between `stage_write_off()` and `finalize_write_off()` — assert `JournalEntry`, `ARTransaction` status/outstanding change, `CustomerLedger` recompute are **all** absent post-rollback — this is the test that would have caught `confirm_write_off()`'s pre-existing three-commit defect (Installments-side contract-status absence proven separately once the full write-off orchestration exists, see the Phase 10 write-off Layer-B test) — in `backend/tests/integration/repositories/accounting/test_stage_write_off_atomicity.py` — Depends on: T099
- [ ] T117 [P] Fiscal-period propagation test: an attempted staged posting dated into a locked period raises `PostingValidationError` (translated to `InstallmentFiscalPeriodLockedError`) **before** any staging occurs, for `stage_adjustment()`, `stage_customer_payment()`, and `stage_write_off()` — in `backend/tests/integration/api/v1/installments/test_fiscal_period_propagation.py` — Depends on: T094, T098, T101

**PHASE 6 EXIT GATE**: All nine new/changed Accounting methods implemented; every existing standalone caller passes unmodified (T113 green); no premature commit exists in any staged method — **Layer A** (Accounting-only atomicity, verified by T114–T116, which reference no Installments-side entity that doesn't yet exist); fiscal-period validation propagates correctly (T117); zero direct Installments→Accounting table writes (structural — `AccountingIntegrationGateway`, now extended from its Phase-3 read-only skeleton, imports no `.models`/`.repositories`); `InstallmentOutstandingService` reads live Accounting state with no duplicated balance. **[CORRECTED]** Full end-to-end (Accounting + Installments rows together) atomicity proof — **Layer B** — is deferred to the earliest phase where the relevant Installments entity actually exists (Phase 7 for collection, Phase 8 for late charge, Phase 10 for write-off) and does **not** block this gate, since Layer A already proves the Accounting-side half is safe and Layer B cannot physically be written before its referenced model exists. **No Phase 7, 8, 9, or 10 task may begin until this gate passes.**

---

## Phase 7: Collections

**Purpose**: Collection orchestration, allocation policy, partial/multi/advance payments, reversal — built directly on Phase 6's staged APIs.

- [ ] T118 `InstallmentAllocationReference` model in `backend/modules/installments/models/allocation_reference.py` — Depends on: T005
- [ ] T119 `InstallmentAllocationReferenceRepository` (append-only — no update method) in `backend/modules/installments/repositories/allocation_reference.py` — Depends on: T118
- [ ] T120 Pure `InstallmentAllocationPolicy.allocate_oldest_first(payment_amount, schedule_lines_outstanding) -> list[AllocationInstruction]` in `backend/modules/installments/services/allocation_policy.py` — sorted by due_date ASC, greedy consumption — Depends on: T012
- [ ] T121 `InstallmentCollectionService.record_collection(company_id, contract_id, amount, payment_method, idempotency_key, actor_id)` in `backend/modules/installments/services/collection_service.py` — full sequence: idempotency reservation (T086) → `FOR UPDATE` lock on `InstallmentContract` (T044) → outstanding calculation → `InstallmentAllocationPolicy.allocate_oldest_first()` → `AccountingIntegrationGateway.record_collection()` staged writes (T107) → `InstallmentAllocationReference` rows staged → `InstallmentOutstandingService.assert_zero_outstanding()` (T108) → if passes, `complete()` → `InstallmentAuditLog` staged → outbox event staged → idempotency completion staged → Accounting finalize calls **last** — Depends on: T086, T107, T108, T119, T120
- [ ] T122 `InstallmentContractService.complete()` — internal method, `ACTIVE→COMPLETED`/`DEFAULTED→COMPLETED`, requires `assert_zero_outstanding()` to have already passed (called only from T121 and later Phase 9) — Depends on: T108, T074
- [ ] T123 `InstallmentCollectionService.reverse_collection(company_id, contract_id, collection_id, idempotency_key, actor_id)` — **[CORRECTED — explicit idempotency wiring]** idempotency reservation (T086) → `FOR UPDATE` lock on `InstallmentContract` (T044) → validate the collection belongs to this contract and is reversible → stages `InstallmentAllocationReference(is_reversal=true, ...)` rows + audit + outbox + idempotency completion **first**, then calls `AccountingIntegrationGateway.reverse_payment()` (→ `reallocate_payment(new_allocation_lines=[])`, unmodified) **last** — no Accounting-side code change, per plan.md §12.3.2's staging-order discipline — rollback (failure before the Accounting call) leaves the idempotency row absent, not stranded `IN_PROGRESS` — Depends on: T107, T119, T086, T044
- [ ] T124 `InstallmentContractService.activate(company_id, contract_id, idempotency_key, actor_id)` — **[CORRECTED — explicit idempotency wiring]** idempotency reservation (T086) → `FOR UPDATE` lock on `InstallmentContract` (T044) → validates eligibility → (if down payment required) `AccountingIntegrationGateway.record_down_payment()` staged → `ScheduleEngine.generate()` (Phase 4) → persists `InstallmentScheduleVersion`+lines staged → reconciliation check (BR-INST-005) → status `APPROVED→ACTIVE` staged → audit staged → outbox staged → idempotency completion staged → Accounting finalize calls **last** (the actual commit) — rollback on any failure leaves the idempotency row absent, never stranded `IN_PROGRESS` — Depends on: T068, T107, T075, T086, T044
- [ ] T125 [P] Pydantic schemas for Collection/Reversal request-response in `backend/modules/installments/schemas/collection.py` — Depends on: T018
- [ ] T126 Endpoint: Activation (`POST /contracts/{id}/activate`) in `router.py`, permission `installments.contract.activate`, operation class ORIGINATION, idempotency required — Depends on: T124, T034, T125
- [ ] T127 Endpoint group: Collections (`POST /contracts/{id}/collections`) in `router.py`, permission `installments.collection.create`, operation class SERVICING, idempotency required — Depends on: T121, T034, T125
- [ ] T128 Endpoint: Reversals (`POST /collections/{id}/reverse`) in `router.py`, permission `installments.collection.reverse`, operation class SERVICING, idempotency required — Depends on: T123, T034, T125
- [ ] T129 Endpoint: Schedules (`GET /contracts/{id}/schedule`, `GET /contracts/{id}/schedule/versions/{v}`) in `router.py`, permission `installments.contract.view`, operation class READ — Depends on: T068, T034
- [ ] T130 [P] Unit test: exact/partial/multi-installment/advance payment allocation via `allocate_oldest_first()` in `backend/tests/unit/modules/installments/test_allocation_policy.py` — Depends on: T120
- [ ] T131 [P] Service test: collection recording (exact/partial/multi-installment/advance scenarios, Scenarios B/C/D) in `backend/tests/integration/api/v1/installments/test_collection_service.py` — Depends on: T121
- [ ] T132 [P] Service test: reversal — reversal-reference rows correctly reference the original, original rows untouched (BR-INST-017) in `backend/tests/integration/api/v1/installments/test_reversal_service.py` — Depends on: T123
- [ ] T133 [P] Service test: reversal/cancellation intermediate-state resume — force-fail between `reallocate_payment()`'s completion and a subsequent `cancel_payment()` call; assert the payment is left `POSTED`/unallocated (valid, explainable state); a retried reversal with the same idempotency key resumes by calling only `cancel_payment()`, never re-attempting `reallocate_payment()` — in `backend/tests/integration/api/v1/installments/test_reversal_intermediate_state.py` — Depends on: T123
- [ ] T134 [P] Service test: `record_collection()` reaching zero outstanding auto-transitions the contract to `COMPLETED` (FR-INST-104) — in `backend/tests/integration/api/v1/installments/test_collection_completion.py` — Depends on: T121, T122
- [ ] T135 [P] Accounting integration test: no duplicate `Payment`/`ARTransaction`/`JournalEntry` per collection (assert exactly one of each) in `backend/tests/integration/api/v1/installments/test_collection_no_duplication.py` — Depends on: T121
- [ ] T136 [P] **[NEW — Correction 4, Layer B: full cross-module collection atomicity, placed here because `InstallmentAllocationReference` (T118) and the complete `record_collection()` orchestration (T121) now both exist]** Real-Postgres forced-failure test: fail *after* `stage_customer_payment()`+`stage_allocation()` flush and *after* `InstallmentAllocationReference`/`InstallmentAuditLog`/outbox/idempotency-completion are staged, but *before* `finalize_customer_payment()` — assert **all** of `Payment`, credit `ARTransaction`, `PaymentAllocationLine`, target-transaction outstanding change, `InstallmentAllocationReference`, `InstallmentAuditLog`, outbox event, and the idempotency-key row are simultaneously absent post-rollback (the key becomes available again for retry, not stranded `IN_PROGRESS`) — in `backend/tests/integration/api/v1/installments/test_collection_atomicity.py` — Depends on: T102, T105, T118, T121, T086
- [ ] T137 [P] Concurrency test (real Postgres): two concurrent full-amount collections against the last remaining installment — exactly one succeeds via the `FOR UPDATE` lock (Scenario J, BR-INST-011) — Depends on: T121, Phase 0

**PHASE 7 EXIT GATE**: A contract can be activated with a down payment, collected against with every payment shape (exact/partial/multi/advance), reversed with correct staging-order atomicity, and auto-completes at zero outstanding — all proven under real Postgres concurrency, all traced through `InstallmentAllocationReference` back to authoritative Accounting records (BR-INST-007/SC-002).

---

## Phase 8: Delinquency

**Purpose**: Due-state derivation, overdue/grace, aging, late charges/waiver — late-charge AR truth wired through Phase 6.

- [ ] T138 Pure `DueStateCalculator` in `backend/modules/installments/services/due_state.py` — derives `UPCOMING/DUE/PARTIALLY_PAID/PAID/OVERDUE` from `scheduled_amount`, `due_date`, grace policy, and live `SUM(InstallmentAllocationReference)`; reads `waived_at`/`voided_at` for the two controlled exceptions — Depends on: T119
- [ ] T139 `InstallmentAgingCalculator` — module-local free function replicating Accounting's exact bucket boundaries (`current/1-30/31-60/61-90/91-120/120+`) per spec Assumption A7 — in `backend/modules/installments/services/aging_calculator.py` — Depends on: T138
- [ ] T140 `InstallmentLateCharge` model in `backend/modules/installments/models/late_charge.py` — Depends on: T005
- [ ] T141 `InstallmentLateChargeRepository` in `backend/modules/installments/repositories/late_charge.py` — `list_for_contract()`, unique `(schedule_line_id, overdue_occurrence_date)` enforcement — Depends on: T140
- [ ] T142 `InstallmentDelinquencyService.apply_late_charge(company_id, contract_id, schedule_line_id, actor_id)` — policy check (enabled, not already charged this occurrence) → `FOR UPDATE` lock on `InstallmentContract` (**added specifically so Concurrency Test D holds**, plan.md §21) → `AccountingIntegrationGateway.post_late_charge()` → `stage_adjustment(transaction_type="DEBIT_NOTE", source_document_type="InstallmentLateCharge", source_document_id=...)` staged → `InstallmentLateCharge` row staged (both `accounting_journal_entry_id`/`accounting_ar_transaction_id` set) → audit staged → outbox staged → `finalize_adjustment()` called **last** — in `backend/modules/installments/services/delinquency_service.py` — Depends on: T107, T141
- [ ] T143 `InstallmentDelinquencyService.waive_late_charge(company_id, contract_id, late_charge_id, reason, actor_id)` — `FOR UPDATE` lock on `InstallmentContract` → stages `waived_at/by/reason` + audit + outbox **first** → calls `AccountingIntegrationGateway.reverse_late_charge()` (→ `reverse_adjustment()`) **last**, only if the charge was actually posted — permission `installments.charge.waive`, distinct from `collection.create` — Depends on: T142
- [ ] T144 [P] Pydantic schemas for late charge/waiver in `backend/modules/installments/schemas/delinquency.py` — Depends on: T018
- [ ] T145 Wire late-charge apply/waive into `InstallmentDelinquencyService` (no dedicated endpoints — invoked internally by the optional background reminder job, Phase 12, and via a service-level admin action if the tenant enables manual charge application) — Depends on: T142, T143
- [ ] T146 [P] Unit test: aging-bucket boundary values (0/1/30/31/60/61/90/91/120/121 days overdue) in `backend/tests/unit/modules/installments/test_aging_calculator.py` — Depends on: T139
- [ ] T147 [P] Unit test: due-state derivation for all 5 derivable states + the 2 controlled-workflow states in `backend/tests/unit/modules/installments/test_due_state_calculator.py` — Depends on: T138
- [ ] T148 [P] Service test: overdue read-time correctness independent of any background job having run (BR-INST-019, Scenario E) in `backend/tests/integration/api/v1/installments/test_overdue_read_time.py` — Depends on: T138
- [ ] T149 [P] Accounting integration test: late-charge GL/AR consistency — exactly one `JournalEntry`, one `DEBIT_NOTE` `ARTransaction`, one `CustomerLedger` recompute, all three present or all three absent — in `backend/tests/integration/api/v1/installments/test_late_charge_consistency.py` — Depends on: T142
- [ ] T150 [P] Accounting integration test: late-charge collectibility — a subsequent ordinary customer payment, allocated via `allocate_oldest_first()`, satisfies the late charge's `ARTransaction` with no special-case code path (plan.md §11.3) — **[CORRECTED — explicit distinct file to remove ambiguity]** in `backend/tests/integration/api/v1/installments/test_late_charge_collectibility.py` — Depends on: T142, T121
- [ ] T151 [P] Accounting integration test: late-charge waiver reconciliation — GL reversal, `ARTransaction.outstanding_amount=0`, and ledger recompute all land together — **[CORRECTED — explicit distinct file]** in `backend/tests/integration/api/v1/installments/test_late_charge_waiver_reconciliation.py` — Depends on: T143
- [ ] T152 [P] **[NEW — Correction 4, Layer B: full cross-module late-charge atomicity, placed here because `InstallmentLateCharge` (T140) and `apply_late_charge()` (T142) now both exist]** Real-Postgres forced-failure test: fail *after* `stage_adjustment()` flushes GL/`ARTransaction`/ledger and *after* `InstallmentLateCharge`/`InstallmentAuditLog`/outbox are staged, but *before* `finalize_adjustment()` — assert **all** of `JournalEntry`, `ARTransaction`, `CustomerLedger` change, `InstallmentLateCharge`, `InstallmentAuditLog`, outbox event are simultaneously absent post-rollback — in `backend/tests/integration/api/v1/installments/test_late_charge_atomicity.py` — Depends on: T095, T140, T142
- [ ] T153 [P] Concurrency test (real Postgres): collection zeroing schedule outstanding races a concurrent late-charge post/waiver on the same contract — the shared `FOR UPDATE` lock serializes them; `assert_zero_outstanding()` never observes a torn combination (Concurrency Test D, plan.md §31) — Depends on: T121, T142, T108

**PHASE 8 EXIT GATE**: Due-state and aging are correct at read time with zero background-job dependency; late charges are genuinely collectible/reversible AR, never GL-only; the collection/late-charge race is proven serialized under real Postgres.

---

## Phase 9: Settlement

**Purpose**: Quote generation (non-mutating), execution (mutating), completion via the authoritative guard.

- [ ] T154 `InstallmentSettlementService.generate_quote(company_id, contract_id, as_of_date)` — pure read+calculation, **no Accounting call** (FR-INST-192), includes any open late-charge `ARTransaction` outstanding in the quoted amount (not schedule principal alone, per plan.md §9.3's corrected Early Settlement row) — audited even though non-mutating (FR-INST-341) — in `backend/modules/installments/services/settlement_service.py` — Depends on: T138, T108
- [ ] T155 `InstallmentSettlementService.execute(company_id, contract_id, idempotency_key, actor_id)` — **[CORRECTED — explicit idempotency wiring]** reserves its **own** idempotency key (T086, scoped `operation="settlement.execute"`, distinct from the collection it wraps) → `FOR UPDATE` lock on `InstallmentContract` (T044) → reuses `InstallmentCollectionService.record_collection()`'s exact atomic sequence (T121) at the full remaining amount → `InstallmentOutstandingService.assert_zero_outstanding()` → `complete()` → idempotency completion staged → Accounting finalize calls **last** — Depends on: T121, T108, T154, T086, T044
- [ ] T156 [P] Pydantic schemas for settlement quote/execution in `backend/modules/installments/schemas/settlement.py` — Depends on: T018
- [ ] T157 Endpoint: Settlement Quotes (`POST /contracts/{id}/settlement/quote`) in `router.py`, permission `installments.settlement.execute`, operation class SERVICING — Depends on: T154, T034, T156
- [ ] T158 Endpoint: Settlement Execution (`POST /contracts/{id}/settlement/execute`) in `router.py`, same permission, idempotency required — Depends on: T155, T034, T156
- [ ] T159 [P] Unit test: settlement quote reproducibility (same state + as-of-date → same quote) in `backend/tests/unit/modules/installments/test_settlement_calculation.py` — Depends on: T154
- [ ] T160 [P] Service test: settlement quote generation is provably non-mutating (no contract/schedule state change, no Accounting call) in `backend/tests/integration/api/v1/installments/test_settlement_quote.py` — Depends on: T154
- [ ] T161 [P] Service test: settlement execution with 3+ remaining installments → `COMPLETED`, zero outstanding remains (Scenario F) in `backend/tests/integration/api/v1/installments/test_settlement_execution.py` — Depends on: T155
- [ ] T162 **[CORRECTED — Correction 6: removed incorrect `[P]` marker, same implied file as T161]** Service test: a stale/expired settlement quote is rejected at execution time, a new quote must be generated (spec §28 edge case) — same file as T161 (`test_settlement_execution.py`), **not parallel-safe with it** — Depends on: T155, T161
- [ ] T163 [P] Completion-guard Test A: all scheduled lines paid but one late-charge `ARTransaction` remains open → settlement/collection completion is withheld, contract stays `ACTIVE`/`DEFAULTED` — in `backend/tests/integration/api/v1/installments/test_completion_guard.py` — Depends on: T108, T155
- [ ] T164 **[CORRECTED — Correction 6: removed incorrect `[P]` marker]** Completion-guard Test B: scheduled + late-charge AR both fully paid → contract completes — same file as T163 (`test_completion_guard.py`), **not parallel-safe with it** — Depends on: T108, T155, T163
- [ ] T165 **[CORRECTED — Correction 6: removed incorrect `[P]` marker]** Completion-guard Test C: scheduled paid + late charge validly waived → contract completes — same file as T163/T164, **not parallel-safe with them** — Depends on: T108, T143, T155, T164

**PHASE 9 EXIT GATE**: Settlement quotes are reproducible and non-mutating; execution correctly reuses the collection atomic path; the authoritative completion guard (Tests A/B/C) is proven across settlement, ordinary collection, and defaulted payoff.

---

## Phase 10: Advanced Lifecycle

**Purpose**: Reschedule (versioning), cancellation (with reversal), the externally-callable **default command** (the Phase-5 primitive wrapped with idempotency), cure, write-off.

- [ ] T166 **[NEW — Correction 2: the externally-callable, idempotency-protected "default" command, distinct from Phase 5's internal `mark_defaulted()` transition primitive]** `InstallmentContractService.default_command(company_id, contract_id, reason, idempotency_key, actor_id)` in `services/contract_service.py` — idempotency reservation (T086) → `FOR UPDATE` lock on `InstallmentContract` (T044) → calls the internal `mark_defaulted()` primitive (T078) → audit already staged by T078 → outbox staged → idempotency completion staged → single commit **last**. This orchestration wrapper is what makes "default" a genuine high-risk idempotency-protected command; it structurally **cannot** exist before Phase 5.5 (T086), which is exactly why it was moved out of Phase 5 — Depends on: T078, T086, T044
- [ ] T167 **[MOVED from Phase 5, formerly T080 — Correction 2]** Endpoint: Default (`POST /contracts/{id}/default`) in `router.py`, permission `installments.contract.default`, operation class ORIGINATION, **idempotency required** — now correctly wired to call `default_command()` (T166), not the internal primitive directly — Depends on: T166, T034, T079
- [ ] T168 `InstallmentReschedulingService.reschedule(company_id, contract_id, new_terms, reason, idempotency_key, actor_id)` — **[CORRECTED — explicit idempotency-first ordering]** idempotency reservation (T086) → `FOR UPDATE` lock on `InstallmentContract` (T044) → maker-checker check (same discipline as `approve()`) → `ScheduleEngine.generate()` for the **remaining obligation only** (rejects any principal/markup/count change — FR-INST-202) → new `InstallmentScheduleVersion` persisted staged, prior version superseded staged → `active_schedule_version_id` updated staged → audit staged → outbox staged → idempotency completion staged → single commit **last** — in `backend/modules/installments/services/rescheduling_service.py` — Depends on: T068, T057, T086, T044
- [ ] T169 Complete `InstallmentContractService.cancel(company_id, contract_id, reason, idempotency_key, actor_id)`'s financial-activity branch — **[CORRECTED — explicit idempotency wiring]** idempotency reservation (T086) → `FOR UPDATE` lock on `InstallmentContract` (T044) → stages status transition + audit + outbox + idempotency completion **first**, then delegates to `AccountingIntegrationGateway.reverse_payment()` **last** (same staging-order discipline as T123) — rollback before the Accounting call leaves no idempotency row stranded — Depends on: T077, T107, T086, T044
- [ ] T170 `InstallmentContractService.cure(company_id, contract_id, reason, actor_id)` — policy-gated (`InstallmentConfiguration.cure_enabled`), permission `installments.contract.cure` (**distinct from `collection.create`**, checked exclusively), `DEFAULTED→ACTIVE`, audit, outbox — never creates a new contract, never deletes default/delinquency history, never touches Accounting, never rewrites original terms — Depends on: T029, T034, T078
- [ ] T171 `InstallmentContractService.writeoff(company_id, contract_id, reason, idempotency_key, actor_id)` — **[CORRECTED — explicit idempotency wiring]** idempotency reservation (T086) → `FOR UPDATE` lock on `InstallmentContract` (T044) → `AccountingIntegrationGateway.writeoff()` (→ `stage_write_off()` staged) → status transition + audit + outbox + idempotency completion staged → `finalize_write_off()` called **last** — permission `installments.contract.writeoff`, distinct from `default`/`collection.create` — rollback before `finalize_write_off()` leaves no stranded `IN_PROGRESS` row — Depends on: T107, T078, T086, T044
- [ ] T172 [P] Pydantic schemas for reschedule/cancel/cure/writeoff in `backend/modules/installments/schemas/lifecycle.py` — Depends on: T018
- [ ] T173 Endpoint: Rescheduling (`POST /contracts/{id}/reschedule`) in `router.py`, permission `installments.contract.reschedule`, operation class ORIGINATION, idempotency required — Depends on: T168, T034, T172
- [ ] T174 Endpoint: Cancellation (`POST /contracts/{id}/cancel`) in `router.py`, permission `installments.contract.cancel`, operation class ORIGINATION, idempotency required — Depends on: T169, T034, T172
- [ ] T175 Endpoint: Cure (`POST /contracts/{id}/cure`) in `router.py`, permission `installments.contract.cure`, operation class SERVICING — Depends on: T170, T034, T172
- [ ] T176 Endpoint: Write-Off (`POST /contracts/{id}/writeoff`) in `router.py`, permission `installments.contract.writeoff`, operation class ORIGINATION, idempotency required — Depends on: T171, T034, T172
- [ ] T177 [P] Service test: reschedule creates a new schedule version, prior version's lines and any linked `InstallmentAllocationReference` rows remain valid pointers into history (BR-INST-017) in `backend/tests/integration/api/v1/installments/test_reschedule.py` — Depends on: T168
- [ ] T178 **[CORRECTED — Correction 6: removed incorrect `[P]` marker, same implied file as T177]** Service test: reschedule maker-checker — requester ≠ approver enforced identically to contract approval — same file as T177 (`test_reschedule.py`), **not parallel-safe with it** — Depends on: T168, T177
- [ ] T179 **[CORRECTED — Correction 6: removed incorrect `[P]` marker, same implied file as T177/T178]** Service test: reschedule rejects any attempt to change principal/markup/installment_count (restructuring), only due-date changes accepted (FR-INST-202) — same file as T177/T178, **not parallel-safe with them** — Depends on: T168, T178
- [ ] T180 [P] Service test: cure — policy-disabled tenant never sees the action succeed even with the permission (true kill switch, ADR-INST-12) in `backend/tests/integration/api/v1/installments/test_cure.py` — Depends on: T170
- [ ] T181 **[CORRECTED — Correction 6: removed incorrect `[P]` marker, same implied file as T180]** Service test: cure preserves the historical `DEFAULTED` event and all delinquency history, never rewrites original terms, never touches Accounting — same file as T180 (`test_cure.py`), **not parallel-safe with it** — Depends on: T170, T180
- [ ] T182 [P] Security test: `installments.contract.cure` is never satisfiable via `installments.collection.create` (permission-code independence, explicit regression guard) in `backend/tests/security/installments/test_cure_permission_isolation.py` — Depends on: T170
- [ ] T183 [P] Accounting integration test: write-off integration confirms `stage_write_off()`/`finalize_write_off()` each called exactly once, no direct Installments→Accounting table write, in `backend/tests/integration/api/v1/installments/test_writeoff_integration.py` — Depends on: T171
- [ ] T184 [P] **[NEW — Correction 4, Layer B: full cross-module write-off atomicity, placed here because the complete write-off orchestration (T171) now exists]** Real-Postgres forced-failure test: fail *after* `stage_write_off()` flushes GL/`ARTransaction`/ledger and *after* the contract's `WRITTEN_OFF` status/`InstallmentAuditLog`/outbox/idempotency-completion are staged, but *before* `finalize_write_off()` — assert **all** of `JournalEntry`, `ARTransaction` status/outstanding change, `CustomerLedger` recompute, contract `WRITTEN_OFF` status, `InstallmentAuditLog`, outbox event, and the idempotency-key row are simultaneously absent post-rollback — in `backend/tests/integration/api/v1/installments/test_writeoff_atomicity.py` — Depends on: T099, T171
- [ ] T185 [P] Service test: `DEFAULTED→COMPLETED` full payoff (Scenario, spec §28 edge case) does not force an unnecessary cure first (FR-INST-104) — Depends on: T121, T122
- [ ] T186 [P] Concurrency test (real Postgres): concurrent write-off vs. collection on the same `DEFAULTED` contract — the shared `FOR UPDATE` lock ensures at most one succeeds cleanly (BR-INST-011/013) in `backend/tests/integration/api/v1/installments/test_writeoff_collection_race.py` — Depends on: T121, T171
- [ ] T187 [P] Concurrency test: concurrent approval/rejection on the same `PENDING_APPROVAL` contract — deterministic conflict via the optimistic `version` column, never a silent overwrite (FR-INST-382) — Depends on: T075, T076, T044

**PHASE 10 EXIT GATE**: Reschedule, cancellation, cure, and write-off are all implemented with correct commit ownership, maker-checker where required, and distinct permission gating; all named concurrency races (write-off/collection, approve/reject) are proven safe under real Postgres.

---

## Phase 11: Entitlement / Security Hardening

**Purpose**: Full `InstallmentAccessPolicy` wiring across every endpoint; exhaustive tenant-suspension, Platform Admin, and support-access boundary proof; IDOR sweep.

- [ ] T188 `InstallmentAccessPolicy.authorize(company_id, operation)` in `backend/modules/installments/services/access_policy.py` — classifies every operation as ORIGINATION/SERVICING/READ/ADMIN, calls (unmodified) `PlatformEntitlementService.resolve_effective_entitlement(company_id, "installments")`, bypasses the check entirely for ADMIN, permits SERVICING/READ when disabled, blocks only ORIGINATION (plan.md §15.2) — Depends on: T032
- [ ] T189 Thread `InstallmentAccessPolicy.authorize()` as the first call inside **every** service method across Phases 2–10 (submit, approve, reject, activate, cancel, mark_defaulted, cure, complete, writeoff, record_collection, reverse_collection, apply_late_charge, waive_late_charge, generate_quote, execute settlement, reschedule) — audit sweep, not new logic — Depends on: T188, T074-T078, T121, T123, T142, T143, T154, T155, T168, T170, T171
- [ ] T190 Mount `installments_router` with `dependencies=[Depends(get_current_company_member)]` **only** — no blanket entitlement dependency at mount time (explicitly diverging from CRM's `require_crm_enabled` router-level gate) — in `backend/api/v1/router.py` — Depends on: T012
- [ ] T191 [P] Unit test: `InstallmentAccessPolicy` operation-class matrix — every (entitlement-state × operation-class) combination produces the exact expected allow/deny outcome, in `backend/tests/unit/modules/installments/test_access_policy.py` — Depends on: T188
- [ ] T192 [P] Entitlement test: enabled tenant — all operations pass RBAC as normal — **[CORRECTED — explicit shared file for the T192-T196 entitlement-servicing-continuity cluster]** in `backend/tests/integration/api/v1/installments/test_entitlement_servicing_continuity.py` — Depends on: T189
- [ ] T193 **[CORRECTED — Correction 6: removed incorrect `[P]` marker, same file as T192]** Entitlement test: disabled tenant — origination denied (new quote, new contract, activation of a new contract, plan/template CRUD, configuration changes, reschedule, cancel, default, writeoff) with `403 FEATURE_DISABLED` — same file as T192, **not parallel-safe with it** — Depends on: T189, T192
- [ ] T194 **[CORRECTED — same file as T192/T193]** Entitlement test: disabled tenant — servicing allowed (collection, settlement execution, existing-contract viewing/statements) on an already-`ACTIVE`/`DEFAULTED` contract (Scenario K, FR-INST-356) — **not parallel-safe with T192/T193** — Depends on: T189, T193
- [ ] T195 **[CORRECTED — same file as T192-T194]** Entitlement test: disabled tenant — normal RBAC still enforced (a servicing action still requires its own permission code) — **not parallel-safe with T192-T194** — Depends on: T189, T194
- [ ] T196 **[CORRECTED — same file as T192-T195]** Entitlement test: suspended tenant remains denied identically to every other module, via the shared `get_current_company_member` path — no Installments-specific suspension mechanism exists (structural/negative test: grep confirms no `Company.status` check inside `InstallmentAccessPolicy`) — **not parallel-safe with T192-T195** — Depends on: T188, T195
- [ ] T197 [P] Security test: Tenant A cannot reach Tenant B's contract by ID, by search, by collection, by settlement (full sweep across every endpoint group) in `backend/tests/security/installments/test_full_tenant_isolation_sweep.py` — Depends on: T189
- [ ] T198 [P] Security test: Platform Admin cannot read/search/mutate any tenant's installment contracts, schedules, collections, or audit data merely by governing the `installments` entitlement (BR-INST-002) — **[CORRECTED — explicit distinct file]** in `backend/tests/security/installments/test_platform_admin_no_business_access.py` — Depends on: T033
- [ ] T199 [P] Security test: an active Epic 9A `SupportAccessGrant` cannot read Installments business records (Scenario L) — **[CORRECTED — explicit distinct file]** in `backend/tests/security/installments/test_support_access_grant_boundary.py` — Depends on: T033
- [ ] T200 [P] Structural/static test: `modules.platform_admin` contains no import of `modules.installments.models`/`.repositories`/`.services` (statically-provable guarantee, mirroring the Phase 12 support-access precedent) in `backend/tests/security/installments/test_platform_admin_structural_boundary.py`
- [ ] T201 [P] Security test: each of the 16 `installments.*` permission codes independently denies when absent (per-code sweep) in `backend/tests/security/installments/test_rbac_permission_sweep.py` — Depends on: T189
- [ ] T202 [P] Security test: cross-tenant `sales_invoice_id`/`customer_id` reference at contract creation is rejected, indistinguishable from an unrelated validation failure (BR-INST-015) — **[CORRECTED — explicit distinct file]** in `backend/tests/security/installments/test_cross_tenant_reference_rejection.py` — Depends on: T049
- [ ] T203 [P] Security test: mass-assignment — `company_id`/`branch_id`/ownership fields are never accepted from any request body (Pydantic schemas structurally omit them; a test posts them anyway and confirms they're ignored) — **[CORRECTED — explicit distinct file]** in `backend/tests/security/installments/test_mass_assignment_protection.py` — Depends on: T036, T051

**PHASE 11 EXIT GATE**: Every service method enforces `InstallmentAccessPolicy` before RBAC; disabled-entitlement servicing continuity is proven end-to-end (Scenario K, SC-006); tenant isolation, Platform Admin exclusion, and support-access exclusion are proven across every endpoint (Scenario I/L, SC-003); no IDOR path remains.

---

## Phase 12: Reporting / Documents

**Purpose**: Operational reports, dashboard, JSON-structured documents — distinguishing Installments-contractual from Accounting-authoritative data sources.

- [ ] T204 `InstallmentReportingService` in `backend/modules/installments/services/reporting_service.py` — contract register, collection report (sourced from Accounting `Payment`/`PaymentAllocationLine` via `InstallmentAllocationReference` joins, never re-derived), due/overdue report (same derivation as T138), aging report (T139), settlement report, default/write-off report (write-off amount always sourced from Accounting), plan/template performance — Depends on: T138, T139, T107
- [ ] T205 Dashboard KPI aggregation — active contract count, outstanding, due today/this month, collected today/this month, overdue amount/count, collection rate, aging distribution, defaulted/written-off balance, upcoming receivables — non-double-counting derivation (FR-INST-081) — in `reporting_service.py` — Depends on: T204
- [ ] T206 `InstallmentDocumentService` in `backend/modules/installments/services/document_service.py` — `get_agreement()`, `get_schedule_document()`, `get_customer_statement()` — plain structured JSON, read-only (no repository write calls), mirrors `AccountsPayableService.generate_remittance_advice()`'s precedent — Depends on: T048, T068
- [ ] T207 [P] `InstallmentCustomerSummaryService.get_summary(company_id, customer_id)` in `backend/modules/installments/services/customer_summary_service.py` — read-only, importable directly by CRM's `Customer360Service` (no CRM-side change made in this Epic — the interface exists, CRM's own import is out of this Epic's scope) — Depends on: T204
- [ ] T208 [P] Pydantic schemas for reports/dashboard/documents in `backend/modules/installments/schemas/reports.py` — Depends on: T018
- [ ] T209 Endpoint group: Reports/Dashboard (`GET /reports/{reportType}`, `GET /dashboard`) in `router.py`, permission `installments.report.view`, operation class READ, `PaginatedResponse` — Depends on: T204, T205, T034, T208
- [ ] T210 Endpoint group: Documents/Statements (`GET /contracts/{id}/documents/{agreement|schedule|settlement-quote}`, `GET /customers/{id}/statement`) in `router.py`, permission `installments.contract.view`, operation class READ — Depends on: T206, T034, T208
- [ ] T211 [P] Service test: no double-counting across dashboard KPI buckets (an overdue amount excluded from "due this month" once it has crossed into overdue) in `backend/tests/unit/modules/installments/test_dashboard_no_double_count.py` — Depends on: T205
- [ ] T212 [P] Service test: every document-generation method makes zero repository write calls (read-only proof) in `backend/tests/unit/modules/installments/test_documents_non_mutating.py` — Depends on: T206
- [ ] T213 [P] Performance test: report/list pagination remains responsive under volume, no N+1 query pattern (batch-load allocation references per page, never per-line) in `backend/tests/performance/installments/test_report_pagination.py` — Depends on: T204, T209

**PHASE 12 EXIT GATE**: Every report's figures trace to the correct authoritative source (Installments-contractual vs. Accounting-financial, per plan.md §25's truth-source table); documents are provably non-mutating; no N+1 patterns exist in list/report endpoints.

---

## Phase 13: Frontend

**Purpose**: Operational UI following current (not legacy) frontend conventions — TanStack Query, stacked-section detail pages, the CRM entitlement-banner pattern. Ordered strictly after its corresponding backend endpoint exists.

- [ ] T214 [P] `frontend/src/lib/api/installments.ts` — typed API client mirroring `src/lib/api/crm.ts`'s hand-mirrored-from-Pydantic-schema convention — Depends on: T051 (and progressively every later endpoint group as it lands)
- [ ] T215 [P] `frontend/src/schemas/installments.ts` — zod schemas mirroring `src/schemas/users-roles.ts`'s convention — Depends on: T214
- [ ] T216 [P] `frontend/src/hooks/installments/useInstallmentsPermissions.ts` + `useHasInstallmentsPermission()` — mirrors `useCrmPermissions.ts` exactly, fail-safe (hide on load failure) — Depends on: T214
- [ ] T217 [P] `frontend/src/components/installments/apiErrors.ts` (`classifyInstallmentsError`) + `InstallmentsStateBanner.tsx` — mirrors `crm/apiErrors.ts` + `CrmStateBanner.tsx`, distinguishes `403 FEATURE_DISABLED` from ordinary `403 forbidden` — Depends on: T214
- [ ] T218 [P] `frontend/src/components/installments/StatusBadge.tsx` — per-module status-color map (`INSTALLMENT_STATUS_COLORS`), matching `crm/StatusBadge.tsx`'s convention, no shared design-system `Badge` (none exists) — Depends on: T214
- [ ] T219 [P] `frontend/src/app/(protected)/(installments)/layout.tsx` — pass-through placeholder, matches every other module — Depends on: T214
- [ ] T220 `frontend/src/hooks/installments/{useContract,useContracts,useCreateContract}.ts` — real `useQuery`/`useMutation`, query keys `['contract', id]`/`['contracts', filters]`, mirrors `useCompany.ts` — Depends on: T214, T051
- [ ] T221 `frontend/src/app/(protected)/(installments)/contracts/page.tsx` — list + filters + pagination — Depends on: T220, T216
- [ ] T222 `frontend/src/app/(protected)/(installments)/contracts/new/page.tsx` — quote → draft creation form (RHF + zod) — Depends on: T215, T071, T216, T217
- [ ] T223 `frontend/src/hooks/installments/{useSchedule,useCollections,useRecordCollection,useReverseCollection}.ts` — Depends on: T129, T127, T128
- [ ] T224 `frontend/src/app/(protected)/(installments)/contracts/[contractId]/page.tsx` — **Contract Detail, the operational center**: header (contract number + status badge + permission-gated lifecycle action buttons) → summary cards → stacked bordered `<section>`s for Terms/Schedule/Payments/Delinquency/Audit-History/Documents (no `Tabs` component invented — none exists in the design system) → `LoadingState`/`EmptyState`/`ErrorState`/`PermissionDeniedState` from `platform-admin/DataState.tsx` — Depends on: T220, T223, T216, T218
- [ ] T225 `frontend/src/app/(protected)/(installments)/contracts/[contractId]/collect/page.tsx` — record-collection form — Depends on: T223
- [ ] T226 `frontend/src/app/(protected)/(installments)/contracts/[contractId]/reschedule/page.tsx` — reschedule form — Depends on: T173
- [ ] T227 `frontend/src/app/(protected)/(installments)/approvals/page.tsx` — approval queue (list of `PENDING_APPROVAL` contracts, approve/reject actions) — Depends on: T080, T220
- [ ] T228 `frontend/src/app/(protected)/(installments)/plans/page.tsx` — templates list/CRUD — Depends on: T037, T216, T217
- [ ] T229 `frontend/src/app/(protected)/(installments)/configuration/page.tsx` — tenant policy config — Depends on: T036, T216, T217
- [ ] T230 `frontend/src/app/(protected)/(installments)/installments-dashboard/page.tsx` — KPI cards, due/overdue summary — Depends on: T209
- [ ] T231 `frontend/src/app/(protected)/(installments)/reports/page.tsx` — contract register/collection/overdue/aging/settlement/write-off reports — Depends on: T209
- [ ] T232 Entitlement-disabled UI behavior: `contracts/new`, `plans`, `configuration` pages render `InstallmentsStateBanner`'s `featureDisabled` variant in place of form/list content on `403 FEATURE_DISABLED`; `contracts/[contractId]` and its collection/reversal/settlement actions remain fully reachable regardless (backend-authoritative, UI is guidance only) — Depends on: T217, T222, T224, T228, T229
- [ ] T233 [P] Jest hook test for every new `useX` hook (mirroring `useCompany.test.ts`'s `renderHook`+mocked-api-client pattern) in `frontend/src/hooks/installments/__tests__/` — Depends on: T220, T223
- [ ] T234 [P] Component test: `InstallmentsStateBanner` renders the correct variant for `FEATURE_DISABLED` vs. ordinary `403` vs. generic error — Depends on: T217
- [ ] T235 [P] Component test: permission-gated action buttons on the Contract Detail page hide (not merely disable) when the corresponding permission is absent — Depends on: T224, T216

**PHASE 13 EXIT GATE**: Every user-facing workflow has its backend endpoint already implemented and tested before its frontend task begins (verified by the Depends-on chain above); entitlement-disabled state permits servicing while blocking origination in the UI, matching backend policy exactly; no new design-system primitives (Tabs, Badge, Table) were invented.

---

## Phase 14: Concurrency / Idempotency Hardening

**Purpose**: Final, dedicated real-Postgres race-condition sweep beyond what individual phases already covered — closing any remaining gap.

- [ ] T236 [P] Real-Postgres concurrency test: duplicate contract creation race, repeated at scale (10 concurrent attempts against the same invoice) — exactly one succeeds — in `backend/tests/integration/repositories/installments/test_concurrency_hardening.py` — Depends on: T053
- [ ] T237 [P] Real-Postgres concurrency test: simultaneous collections against the same contract from multiple sessions — no over-collection under sustained concurrent load — **[CORRECTED — explicit distinct file to remove same-file ambiguity with T236/T238-T241]** in `backend/tests/integration/repositories/installments/test_concurrency_collections_scale.py` — Depends on: T137
- [ ] T238 [P] Real-Postgres concurrency test: collection vs. late charge race, repeated at scale — **[CORRECTED — explicit distinct file]** in `backend/tests/integration/repositories/installments/test_concurrency_collection_vs_late_charge_scale.py` — Depends on: T153
- [ ] T239 [P] Real-Postgres concurrency test: collection vs. settlement execution race — no double-execution — **[CORRECTED — explicit distinct file]** in `backend/tests/integration/repositories/installments/test_concurrency_collection_vs_settlement_scale.py` — Depends on: T121, T155
- [ ] T240 [P] Real-Postgres concurrency test: concurrent lifecycle transition attempts (approve/reject, cure/writeoff) at scale — deterministic conflict every time, never a silent overwrite — **[CORRECTED — explicit distinct file]** in `backend/tests/integration/repositories/installments/test_concurrency_lifecycle_transitions_scale.py` — Depends on: T187, T186
- [ ] T241 [P] Real-Postgres concurrency test: duplicate idempotency-key submission under sustained concurrent load (20 concurrent identical requests) — exactly one financial effect — **[CORRECTED — explicit distinct file]** in `backend/tests/integration/repositories/installments/test_concurrency_idempotency_scale.py` — Depends on: T089
- [ ] T242 Confirm no test in the entire Installments suite relies on SQLite-only behavior for locking/partial-index assertions (grep sweep of `tests/integration/repositories/installments/` and `tests/integration/api/v1/installments/` for real-Postgres fixture usage on every concurrency-relevant test) — Depends on: T236-T241

**PHASE 14 EXIT GATE**: Every critical race named in plan.md §19/§31 has dedicated, passing, real-Postgres coverage — not SQLite-approximated coverage.

---

## Phase 15: Integration / E2E / Regression

**Purpose**: Cross-module integration, Playwright E2E, full backend/frontend regression closure.

- [ ] T243 [P] E2E: standard installment contract — quote → submit → approve (different user) → activate with down payment → collect to completion (Scenario A) — Playwright, in `frontend/e2e/installments/t-standard-contract.spec.ts` — Depends on: T224, T225
- [ ] T244 [P] E2E: partial collection (Scenario B) — **[CORRECTED — explicit distinct file, one-per-scenario matching T243's naming pattern]** in `frontend/e2e/installments/t-partial-collection.spec.ts` — Depends on: T225
- [ ] T245 [P] E2E: overdue read (Scenario E) — **[CORRECTED]** in `frontend/e2e/installments/t-overdue-read.spec.ts` — Depends on: T224
- [ ] T246 [P] E2E: early settlement (Scenario F) — **[CORRECTED]** in `frontend/e2e/installments/t-early-settlement.spec.ts` — Depends on: T224
- [ ] T247 [P] E2E: disabled-entitlement servicing continuity (Scenario K) — two-browser-context, mirroring `t220-suspension-flow.spec.ts`'s pattern — **[CORRECTED]** in `frontend/e2e/installments/t-entitlement-disabled-servicing.spec.ts` — Depends on: T232
- [ ] T248 [P] E2E: tenant isolation (Scenario I) — **[CORRECTED]** in `frontend/e2e/installments/t-tenant-isolation.spec.ts` — Depends on: T224
- [ ] T249 [P] E2E: Platform Admin/support-access boundary (Scenario L) — **[CORRECTED]** in `frontend/e2e/installments/t-platform-admin-boundary.spec.ts` — Depends on: T198, T199
- [ ] T250 [P] E2E: multi-installment collection (Scenario C) — **[CORRECTED]** in `frontend/e2e/installments/t-multi-installment-collection.spec.ts` — Depends on: T225
- [ ] T251 [P] E2E: advance payment (Scenario D) — **[CORRECTED]** in `frontend/e2e/installments/t-advance-payment.spec.ts` — Depends on: T225
- [ ] T252 [P] E2E: late charge + subsequent payment collectibility — **[CORRECTED]** in `frontend/e2e/installments/t-late-charge-collectibility.spec.ts` — Depends on: T224, T225
- [ ] T253 [P] E2E: default → cure — **[CORRECTED]** in `frontend/e2e/installments/t-default-cure.spec.ts` — Depends on: T224
- [ ] T254 [P] E2E: write-off — **[CORRECTED]** in `frontend/e2e/installments/t-writeoff.spec.ts` — Depends on: T224
- [ ] T255 [P] E2E: reversal/cancellation — **[CORRECTED]** in `frontend/e2e/installments/t-reversal-cancellation.spec.ts` — Depends on: T224
- [ ] T256 Full backend regression: `backend/tests/{unit,integration,security,performance}/**/installments/` — 100% green — Depends on: T012-T241
- [ ] T257 Full Accounting regression re-run (post-Phase-6-through-14 changes, confirming zero drift introduced by later phases): `backend/tests/**/accounting/` — 100% green — Depends on: T113
- [ ] T258 Full Sales/CRM/Platform Admin/Users-Roles regression: confirm zero regressions from the shared-file/entitlement-registration changes — **[CORRECTED — Correction 6: the original draft's dependency here was a self-referential, non-executable placeholder ("depends on its own prerequisites") and has been replaced with explicit real task IDs]** — Depends on: T010 (permission backfill migration touching `users_roles`' `permissions`/`role_permissions` tables), T016 (`users_roles/constants.py` union edit), T032 (`platform_admin`'s `module_enablement.py` factory edit), T033 (`platform_admin`'s `capability_seed_service.py` catalogue edit), T009 (capability-seed migration) — i.e. every task that touches a file owned by a sibling module
- [ ] T259 Frontend full regression: `npm test` + `npm run e2e` — 100% green — Depends on: T233-T255
- [ ] T260 Cross-module integration test: Sales' `InvoiceCreditNoteIssued`/`InvoiceCancelled` event subscription correctly flags an Installments contract `requires_review=true` without auto-cancelling (Scenario H) — in `backend/tests/integration/api/v1/installments/test_sales_event_subscription.py` — Depends on: T045
- [ ] T261 Full bidirectional migration re-verification (`alembic upgrade head` → `downgrade 061` → `upgrade head`) one final time against the complete, fully-implemented schema — Depends on: T011, T256

**PHASE 15 EXIT GATE**: All 12 acceptance scenarios (A–L) pass end-to-end; full backend, frontend, and cross-module regression suites are green; zero drift introduced into Sales/Accounting/CRM/Platform Admin/Users-Roles.

---

## Dependencies & Execution Order

```
Phase 0 (Migrations)
   ↓
Phase 1 (Module Foundation)
   ↓
Phase 2 (Configuration & Plans)
   ↓
Phase 3 (Contract Persistence)
   ↓
Phase 4 (Schedule Engine)
   ↓
Phase 5 (Contract Lifecycle)
   ↓
Phase 5.5 (Idempotency Primitive) ──────────────┐
   ↓                                             │ HARD GATE — no high-risk
Phase 6 (Accounting Integration) ← HARD GATE ────┘   command before this passes
   ↓
   ├──→ Phase 7 (Collections)
   ├──→ Phase 8 (Delinquency)      [depends on Phase 6 + Phase 7's FOR UPDATE lock discipline]
   └──→ Phase 9 (Settlement)        [depends on Phase 6 + Phase 7's collection path]
          ↓
        Phase 10 (Advanced Lifecycle)
          ↓
        Phase 11 (Entitlement / Security Hardening)
          ↓
        Phase 12 (Reporting / Documents)
          ↓
        Phase 13 (Frontend)  [each task individually depends on its own backend endpoint]
          ↓
        Phase 14 (Concurrency / Idempotency Hardening)
          ↓
        Phase 15 (Integration / E2E / Regression)
```

**Absolute hard gates** (explicitly called out per the governing instructions):
- **Phase 5.5 gate** → before any idempotency-protected command in Phases 7–10 (activation, collection, settlement, reversal, rescheduling, cancellation, default, write-off).
- **Phase 6 gate** → before any task in Phases 7, 8, 9, or 10 that calls `AccountingIntegrationGateway`.

## Parallel Execution Guidance

`[P]` tasks share no file, no unfinished API dependency, and no shared transaction contract. **[CORRECTED — Correction 6: every example below directly re-verified against the file, post-renumbering, not hand-computed; the pre-correction version of this list included at least one false positive (`T013–T020`, which incorrectly implied three tasks editing the same `constants.py` were mutually parallel).** Representative parallel batches:
- Phase 1: T013, T017, T018, T019, T020 (T013 is the sole safe starting point for `constants.py`; T014/T015 are now explicitly sequential *after* T013 within that same file — not part of this batch)
- Phase 2: T021–T024 (four distinct model files)
- Phase 4: T057, T059, T061–T066 (T057 stands alone as the first `schedule_engine.py` task; T059 is a genuinely different file, `business_date.py`; T058/T060 are now sequential within `schedule_engine.py` — not part of this batch; T061–T066 are six independent unit-test files against the completed `ScheduleEngine`)
- Phase 4.5: T073A alone (sole starting point — T073B/T073C each depend on it and separately edit already-existing files `quote_service.py`/`contract_service.py`, never parallel with each other or with T073A); T073D is parallel-safe with T073B/T073C (independent new test file, depends only on T073A); T073E is sequential last (depends on both T073B and T073C)
- Phase 6.4: T109–T112 (four independent regression-test files)
- Phase 6.5: T114–T117 (four independent forced-failure test files, now correctly Layer-A/Accounting-only in scope)
- Phase 11: T192 (starts the now-sequential entitlement-continuity cluster alone), T200–T203 (four independent, explicitly-distinct-file security tests)
- Phase 13: T214, T216–T219 (T215 depends on T214 sequentially for the zod schemas; the rest are independent new-file scaffolding tasks)
- Phase 15: T243–T255 (thirteen independent Playwright spec files, each now given an explicit distinct filename)

**Known same-file clusters corrected during the [P] audit** (now sequential, not parallel, despite superficially looking like independent test/config items): `T013→T014→T015` (`constants.py`); `T057→T058`, `T057→T060` (`schedule_engine.py`); `T054→T055` (`test_contract_creation.py`); `T089→T090→T091` (`test_idempotency_concurrency.py`); `T161→T162→T163` (`test_completion_guard.py`, IDs unchanged but now explicitly sequential); `T173→T174→T175` (`test_reschedule.py`); `T176→T177` (`test_cure.py`); `T192→T193→T194→T195→T196` (`test_entitlement_servicing_continuity.py`); `T036`/`T037`/`T042` and every other `router.py`-writing endpoint-group task (never parallel with each other); `T046` (Phase 3 read-only gateway skeleton) → the Phase 6 task that extends it (same file, `accounting_gateway.py`).

Tasks **not** marked `[P]` within the same phase either modify the same file (e.g., every `router.py` endpoint-group task, the clusters listed above), extend the same class across steps (e.g., T094→T095→T096), or depend on an immediately-preceding test proving architectural correctness — these must run sequentially even within a nominally parallelizable phase.

---

## Requirement Traceability

### FR-INST coverage (by group — see plan.md §38.1 for the full component-level matrix)

| FR group | Covered by |
|---|---|
| §9.1 Configuration | T021, T025, T029, T036, T039 |
| §9.2 Plans/Templates | T022, T026, T030, T037, T040 |
| §9.2 Custom-terms policy bounds (FR-INST-011) | **T073A-T073E** [NEW — Correction 7] |
| §9.3 Eligibility | T047, T052, T055 |
| §9.4 Quote/Preview | T057-T066, T069, T071, **T073A, T073B** [NEW — Correction 7, policy-bounds retrofit] |
| §9.5 Contract data | T043-T049, T053-T056, **T073A, T073C** [NEW — Correction 7, policy-bounds retrofit] |
| §9.6 Notifications | T107 (outbox events), Phase 8/9/10 event-staging steps |
| §9.7 Documents | T206, T210, T212 |
| §9.8 Search/Views | T044, T051, T129 |
| §9.9 Dashboard | T205, T211 |
| §9.10 API/Contract | all endpoint tasks (T036, T037, T051, T052, T071, T080, T167, T126-T129, T157, T158, T173-T176, T209, T210) |
| §11 Lifecycle | T074-T084 |
| §12 Schedule | T057-T073 |
| §13 Collection/Allocation | T118-T137 |
| §13.3 Down Payments | T101-T103, T107, T124 |
| §14 Delinquency | T138-T153 |
| §15.1 Settlement | T154-T165 |
| §15.2 Amendments | T168, T177-T179 |
| §15.3 Cancellation | T077, T169, T174 |
| §15.4 Default | T078, T166, T167, T170, T180-T182, T185 |
| §15.5 Write-Off | T098-T100, T171, T176, T183, **T184** [NEW — Layer-B write-off atomicity] |
| §15.6 Refunds/Reversals | T097, T123, T128, T132, T133 |
| §16 Sales Integration | T045, **T046** [NEW — read-boundary gateway], T047, T260 |
| §17 Accounting Integration | T094-T117 (all of Phase 6, incl. **T046** [NEW — Phase 3 read-only skeleton later extended by Phase 6]), plus the Layer-B cross-module proofs **T136, T152, T184** [NEW] once their referenced Installments entities exist |
| §18 Inventory/CRM | T207 (no Inventory task exists — structurally absent, by design) |
| §19 Multi-Tenancy | T054, T197, T202 |
| §19.2 Platform Admin | T198, T199, T200 |
| §20 RBAC | T015, T016, T034, T201 |
| §20.2 Maker-Checker | T075, T076, T082, T168, T178 |
| §21 Audit | T038, T189 (threaded everywhere) |
| §22 Entitlement | T031-T033, T188-T196 |
| §23 Reporting | T204, T205, T209, T211 |
| §24 Security | T188-T203 (all of Phase 11) |
| §25 Concurrency/Idempotency | T085-T093, T137, T153, T186, T187, T236-T241 |
| §26 Failure/Recovery | T114-T117 (Layer A), **T136, T152, T184** [NEW — Layer B], T133 |

### BR-INST coverage

| Rule | Covered by |
|---|---|
| BR-INST-001, 015 | T054, T197, T202 |
| BR-INST-002 | T198 |
| BR-INST-003 | T047, T049, T202 |
| BR-INST-004 | T046, T107 (structural — imports only `.services`, never `.models`/`.repositories`), T200 |
| BR-INST-005 | T064, T124 (reconciliation check) |
| BR-INST-006 | T089-T092, T136, T137, T152, T184 |
| BR-INST-007 | T119, T121, T135 |
| BR-INST-008 | T081, T084 |
| BR-INST-009 | T040, T055 |
| BR-INST-010 | T108, T163-T165 |
| BR-INST-011 | T137, T186 |
| BR-INST-012 | T171, T183 |
| BR-INST-013 | T078, T186 |
| BR-INST-014 | T194 |
| BR-INST-016 | T038, T189 |
| BR-INST-017 | T068, T072, T119, T132, T177 |
| BR-INST-018 | T064 |
| BR-INST-019 | T066, T148 |
| BR-INST-020 | (no autonomous-mutation code path exists — structurally absent, no task needed) |
| BR-INST-021 | T117 |
| BR-INST-022 | T055 |

### Scenario coverage

| Scenario | Covered by |
|---|---|
| A | T243 |
| B | T131, T244 |
| C | T131, T250 |
| D | T131, T251 |
| E | T148, T245 |
| F | T161, T246 |
| G | (payment reversal → collection-reversal reconciliation) T132 |
| H | T260 |
| I | T197, T248 |
| J | T137 |
| K | T193-T195, T247 |
| L | T198, T199, T249 |

### Success Criteria coverage

| SC | Covered by |
|---|---|
| SC-001 | T124 (activation reconciliation) |
| SC-002 | T119, T135, T150 |
| SC-003 | T197, T198, T199 |
| SC-004 | T137, T186, T236-T241 |
| SC-005 | T038, T189 (audit sweep) |
| SC-006 | T194, T247 |
| SC-007 | Full traceability tables above — every BR-INST-001–022 maps to at least one test task |

**No orphan requirements.**
