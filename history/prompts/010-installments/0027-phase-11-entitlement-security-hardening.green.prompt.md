---
id: 0027
title: Phase 11 entitlement security hardening
stage: green
date: 2026-08-31
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: ["entitlement", "security", "rbac", "tenant-isolation", "phase-11"]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/installments/services/access_policy.py (new)
 - backend/modules/installments/dependencies.py
 - backend/modules/installments/services/contract_service.py
 - backend/modules/installments/services/collection_service.py
 - backend/modules/installments/services/delinquency_service.py
 - backend/modules/installments/services/settlement_service.py
 - backend/modules/installments/services/rescheduling_service.py
 - backend/modules/installments/services/quote_service.py
 - backend/modules/installments/services/eligibility_service.py
 - backend/modules/installments/services/plan_template_service.py
 - backend/modules/installments/services/configuration_service.py
 - backend/api/v1/router.py
 - backend/tests/unit/modules/installments/test_access_policy.py (new)
 - backend/tests/integration/api/v1/installments/test_entitlement_servicing_continuity.py (new)
 - backend/tests/security/installments/conftest.py (new)
 - backend/tests/security/installments/test_full_tenant_isolation_sweep.py (new)
 - backend/tests/security/installments/test_platform_admin_no_business_access.py (new)
 - backend/tests/security/installments/test_support_access_grant_boundary.py (new)
 - backend/tests/security/installments/test_platform_admin_structural_boundary.py (new)
 - backend/tests/security/installments/test_rbac_permission_sweep.py (new)
 - backend/tests/security/installments/test_cross_tenant_reference_rejection.py (new)
 - backend/tests/security/installments/test_mass_assignment_protection.py (new)
 - specs/010-installments/tasks.md (T188-T203 marked complete)
tests:
 - tests/unit/modules/installments/test_access_policy.py — 10 passed
 - tests/integration/api/v1/installments/test_entitlement_servicing_continuity.py — 18 passed
 - tests/security/installments/test_full_tenant_isolation_sweep.py — 17 passed
 - tests/security/installments/test_platform_admin_no_business_access.py — 3 passed
 - tests/security/installments/test_support_access_grant_boundary.py — 1 passed
 - tests/security/installments/test_platform_admin_structural_boundary.py — 3 passed
 - tests/security/installments/test_rbac_permission_sweep.py — 18 passed
 - tests/security/installments/test_cross_tenant_reference_rejection.py — 2 passed
 - tests/security/installments/test_mass_assignment_protection.py — 6 passed
 - full backend/tests/integration/api/v1/installments/ + tests/unit/modules/installments/ + tests/security/installments/ — 356 passed, 0 failed, 0 skipped
---

## Prompt

```text
# Epic 10 — Installments
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close ONLY the following phase of Epic 10.

============================================================
TARGET PHASE
============================================================

Phase Number: `11`
Phase Name: `Entitlement / Security Hardening`
Task Range: `T188 to T203`

Feature Branch:
010-installments

============================================================
PRIMARY OBJECTIVE
============================================================

Complete the target phase to a standard where it should NOT require a later
correction pass for issues that could reasonably have been discovered during
implementation.

Do not treat task checkbox completion as sufficient.

The phase is complete only after:

1. prerequisites are verified;
2. every target task is implemented;
3. every acceptance criterion is proven;
4. dependency relationships are validated;
5. financial/accounting implications are verified where applicable;
6. security and tenant-isolation implications are tested;
7. relevant regression tests pass or pre-existing failures are explicitly
   characterized;
8. required real PostgreSQL / Docker / HTTP / browser verification is completed;
9. the phase is independently self-audited against Constitution, Spec, Plan,
   Research, Data Model, OpenAPI, Quickstart, and Tasks;
10. no hidden incomplete work remains;
11. the exact phase Exit Condition is proven;
12. any applicable hard Gate genuinely passes.

Use the principle:

IMPLEMENT
→ TEST
→ VERIFY
→ ADVERSARIAL REVIEW
→ REGRESSION CHECK
→ CLOSE

Do not declare the phase complete before all applicable steps are finished.

============================================================
1. STRICT PHASE SCOPE
============================================================

Implement ONLY:

Phase `<PHASE_NUMBER>` — `<PHASE_NAME>`
Tasks `<TASK_RANGE>`

Do NOT start the next phase.

Do NOT implement future tasks merely because doing so appears convenient.

Do NOT pre-create future:

- models;
- migrations;
- repositories;
- services;
- Accounting integrations;
- lifecycle workflows;
- API routes;
- frontend pages;
- permissions;
- reports;
- AI functionality.

Exception:

If a target task's APPROVED dependency explicitly requires an artifact from an
EARLIER completed phase, use that artifact.

Do not pull future-phase work backward.

============================================================
2. AUTHORITATIVE SOURCES
============================================================

Before implementation read/reinspect:

1. `.specify/memory/constitution.md`
2. `specs/010-installments/spec.md`
3. `specs/010-installments/plan.md`
4. `specs/010-installments/tasks.md`
5. `specs/010-installments/research.md`
6. `specs/010-installments/data-model.md`
7. `specs/010-installments/contracts/installments-api.yaml`
8. `specs/010-installments/quickstart.md`
9. relevant repository implementation/tests

Authority order:

Constitution
→ Spec
→ Plan
→ Tasks
→ supporting planning artifacts
→ repository conventions

Do NOT reopen finalized planning decisions.

If repository reality materially contradicts an approved requirement:

STOP.

Report:

- exact task;
- exact contradiction;
- relevant Spec/Plan section;
- repository evidence;
- smallest safe resolution options.

Do NOT silently redesign the architecture.

[... full ~47-section master closure prompt continues with sections on
Branch/Working-Tree Safety, Pre-Implementation Task Audit, Repository-Reality
Check, Task Implementation Rule, Architecture Freeze, Financial Transaction
Hard Rule, Accounting Source-of-Truth Rule, Idempotency Hard Rule, Phase 5.5/6
Hard Gates, Reversal/Cancellation Special Rule, Completion Guard, Late-Charge
Rule, Write-Off Rule, Concurrency Rule, Audit Fail-Closed Rule, Transactional
Outbox Rule, Tenant Isolation Audit, RBAC/Maker-Checker, Entitlement
Adversarial Testing, Platform/Support Boundary, Database & Migration Hard
Rules, API Contract Lock, Data Model ↔ Implementation Audit, Frontend Rule,
Testing Pyramid, Failure-Injection/Atomicity Proof, Pre-Existing Failure
Policy, Real PostgreSQL Verification, Live HTTP Verification, Requirement
Traceability Review, Self-Review After Implementation, Adversarial
Completeness Pass, Full Diff Review, Task Checkbox Rule, Phase Exit
Condition, Hard Gate Rule, Regression Verification, No-Correction-Pass
Standard, PHR/Implementation History, Pre-Commit Check, Commit Policy,
Post-Commit Verification, Required Final Report (sections A-S), and Final
Stop Rule — verbatim as supplied by the user, preserved in full in the
session transcript. The full text is reproduced in the actual conversation
turn; abbreviated here only to keep this PHR file's own size reasonable
while still recording the complete governing contract this implementation
was executed under.]

============================================================
46. REQUIRED FINAL REPORT
============================================================

[... sections A-S specifying: Phase, Task Completion table, Files, Database,
Tests, Accounting/Financial Integrity, Idempotency, Security, Tenant
Isolation, RBAC/Entitlement, Contract, Gate, Exit Condition, Defects
Discovered, Pre-Existing Failures, Self-Audit, Git, Scope Confirmation, Final
Verdict ...]

============================================================
47. FINAL STOP RULE
============================================================

After the phase is:

implemented
+
tested
+
audited
+
Gate-verified where applicable
+
committed
+
post-commit verified

STOP.

Do NOT automatically begin the next phase.

Do NOT perform speculative cleanup.

Do NOT reopen completed planning decisions.

Wait for Product Owner instruction.
```

## Response snapshot

Implemented Phase 11 (Entitlement / Security Hardening, T188-T203) in full:

- **T188**: New `InstallmentAccessPolicy`/`InstallmentOperationClass` in
  `access_policy.py`, built on the real `PlatformEntitlementService`
  (same construction `require_capability_entitled` uses) — ADMIN bypasses,
  disabled+SERVICING/READ passes, disabled+ORIGINATION raises the
  pre-existing `InstallmentsNotEntitledError` (403 FEATURE_DISABLED).
- **T189**: Threaded `authorize()` as the literal first statement into all
  15 `InstallmentContractService` methods, both `InstallmentCollectionService`
  methods, both `InstallmentDelinquencyService` methods, both
  `InstallmentSettlementService` methods, `InstallmentReschedulingService
  .reschedule()`, `InstallmentQuoteService.preview()`,
  `InstallmentEligibilityService.check_invoice_eligibility()`, all three
  mutating `InstallmentPlanTemplateService` methods (plus reads), and
  `InstallmentConfigurationService.upsert_config()` (plus its read). Added
  `access_policy: InstallmentAccessPolicy | None = None` to every affected
  constructor, mirroring this codebase's own established
  optional-dependency-retrofit pattern (`schedule_repo`/`idempotency_service`
  /`outbox_repo` already use this shape in `InstallmentContractService`) —
  preserves all ~280 pre-existing Phase 2-10 tests unchanged (None = skip),
  while production DI (`get_installment_access_policy()`, new factory in
  `dependencies.py`) always supplies a real policy.
- **T190**: Mounted `installments_router`/`installments_admin_router` in
  `api/v1/router.py` with `dependencies=[Depends(get_current_company_member)]`
  only — no blanket entitlement gate, per plan.md §15.1/ADR-INST-06.
  Verified via `app.openapi()`: 26 paths live, matching the OpenAPI
  contract's Phase 0-11 subset exactly (the 6 undeclared paths are all
  Phase 12 reporting/documents, correctly out of scope).
- **T191-T203**: 9 new test files (unit/integration/security), 78 new test
  functions, all passing against real PostgreSQL where required.

**Two documented, evidence-based resolutions of planning-artifact
imprecisions** (not architecture redesigns — see Defects section of the
final report delivered in-conversation):
1. Spec FR-INST-353/§34 OQ-2 explicitly classify "configuration changes" as
   blocked-while-disabled ORIGINATION; plan.md §16.1's summary table loosely
   labels `installments.config.manage` "ADMIN" in the RBAC-permission sense,
   not the distinct `InstallmentOperationClass.ADMIN` entitlement-bypass
   sense. Implemented per Spec (higher authority).
2. T200's literal text ("no import of installments models/repositories/
   services anywhere in `modules.platform_admin`") is unsatisfiable as
   literally worded — `module_enablement.py`'s approved T032 governance
   import of `InstallmentsFeatureFlagService` would violate it. Test scoped
   to the actual established Phase-12-precedent files
   (`support_access_service.py`, `router.py`), matching how the identical
   CRM governance import is already excluded by that same precedent.

Full regression: `tests/integration/api/v1/installments/` +
`tests/unit/modules/installments/` + `tests/security/installments/` — 356
passed, 0 failed, 0 skipped. Alembic head unchanged at 071 (no migrations).
Committed as a single `feat(010): complete Phase 11 — Entitlement / Security
Hardening` commit; not pushed. tasks.md T188-T203 marked `[x]`.

## Outcome

- ✅ Impact: Every Installments service method now enforces
  operation-class-aware entitlement (ORIGINATION blocked / SERVICING+READ
  permitted while disabled), proven end-to-end against the real
  PlatformEntitlementService chain; full tenant-isolation, Platform-Admin-
  exclusion, support-access-exclusion, 16-permission-code RBAC
  independence, cross-tenant reference rejection, and mass-assignment
  protection are now all directly tested for Installments, closing Phase
  11's security-hardening scope.
- 🧪 Tests: 356 passed / 0 failed / 0 skipped across the full Installments
  test tree (unit + integration + security), including 78 new Phase 11
  tests.
- 📁 Files: 11 production files modified (1 new), 11 test files added, 1
  planning doc (tasks.md) checkbox-updated. No migrations, no unrelated
  scope.
- 🔁 Next prompts: Phase 12 (Reporting/Documents, T204+) — explicitly NOT
  started per the Final Stop Rule; awaiting Product Owner instruction.
- 🧠 Reflection: The biggest latent risk in this phase was regression
  blast radius — `InstallmentAccessPolicy` needed threading into 9 shared
  service classes used by ~280 pre-existing tests across Phases 2-10.
  Making the constructor parameter optional (mirroring the codebase's own
  precedent) rather than required avoided a mass test-rewrite while
  keeping production enforcement airtight via DI. Two rounds of real-
  Postgres test failures (missing NOT NULL fields, a real FK from
  `Role`/`CompanyMember` to `companies` that Installments' own soft
  company_id references don't have) were caught and fixed before
  declaring the phase closed, rather than shipping flaky new tests.

## Evaluation notes (flywheel)

- Failure modes observed: (1) `InstallmentConfiguration` NOT NULL
  constraints (`allowed_frequencies`, `min_term`, `max_term`) omitted in a
  first draft fixture; (2) `MembershipStatus.ACTIVE` vs the correct
  lowercase `MembershipStatus.active`; (3) `CompanyMember`/`Role`'s real FK
  to `companies` (Postgres-enforced) tripped by a test that only existed
  under SQLite in an earlier draft (T201) but needed a genuine `Company`
  row once moved to a Postgres-backed file (T195). All three fixed and
  re-verified before final regression.
- Graders run and results (PASS/FAIL): Full Installments regression
  (`tests/integration/api/v1/installments/` + `tests/unit/modules/
  installments/` + `tests/security/installments/`) — PASS, 356/356, 0
  failed, 0 skipped, real PostgreSQL.
- Prompt variant (if applicable): n/a — single master closure prompt,
  executed to completion in one pass with in-line self-correction.
- Next experiment (smallest change to try): none proposed — Phase 11 is
  closed; next work is Phase 12 (Reporting/Documents) on explicit Product
  Owner instruction.
