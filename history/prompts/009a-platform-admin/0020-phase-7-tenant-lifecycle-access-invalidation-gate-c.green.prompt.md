---
id: 0020
title: Phase 7 Tenant Lifecycle Access Invalidation Gate C
stage: green
date: 2026-08-20
surface: agent
model: claude-opus-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.implement
labels: ["platform-admin", "implement", "phase-7", "tenant-lifecycle", "gate-c", "auth-freshness"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/companies/models/company.py
 - backend/modules/companies/repositories/company_repository.py
 - backend/modules/companies/dependencies.py
 - backend/modules/users_roles/dependencies.py
 - backend/modules/platform_admin/services/company_access_service.py
 - backend/modules/platform_admin/services/tenant_lifecycle_service.py
 - backend/modules/platform_admin/schemas/tenant_lifecycle.py
 - backend/modules/platform_admin/router.py
 - backend/api/v1/router.py
 - backend/tests/unit/modules/platform_admin/test_company_access_rule.py
 - backend/tests/integration/api/v1/platform_admin/test_company_access.py
 - backend/tests/integration/services/platform_admin/test_tenant_lifecycle.py
 - backend/tests/integration/services/platform_admin/test_tenant_lifecycle_concurrency.py
 - backend/tests/integration/services/platform_admin/test_audit_fail_closed.py
 - backend/tests/security/modules/platform_admin/test_auth_freshness.py
 - backend/tests/security/modules/platform_admin/test_cross_tenant_suspension.py
 - specs/009a-platform-admin/tasks.md
tests:
 - backend/tests/unit/modules/platform_admin/test_company_access_rule.py — 9/9 passing (T085)
 - backend/tests/integration/api/v1/platform_admin/test_company_access.py — 1/1 passing (T086, rollout safety across all 5 modules)
 - backend/tests/integration/services/platform_admin/test_tenant_lifecycle.py — 4/4 passing (T091-T093)
 - backend/tests/integration/services/platform_admin/test_tenant_lifecycle_concurrency.py — 1/1 passing against REAL PostgreSQL (T094), verified zero leftover rows after teardown
 - backend/tests/integration/services/platform_admin/test_audit_fail_closed.py — 4/4 passing (2 Phase-6 T079 + 2 new T101)
 - backend/tests/security/modules/platform_admin/test_auth_freshness.py — 6/6 passing (T095-T097, T099-T100)
 - backend/tests/security/modules/platform_admin/test_cross_tenant_suspension.py — 1/1 passing (T098)
 - Combined Phase 1-7 platform_admin/bootstrap suite — 118/118 passing (94 from Phase 1-6 + 24 new)
 - T087 (full existing inventory/purchase/sales/accounting/crm API test suites against the new dependency chain) — 972 passed, 4 skipped (pre-existing, not introduced by this phase), 0 failed (45m57s). No delta from the pre-Phase-7 baseline.
---

## Prompt

# Epic 9A — MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close **Phase 7 — Tenant Lifecycle &
Company-Scoped Access Invalidation, Gate C, tasks T082-T102** of
`specs/009a-platform-admin/tasks.md` — explicitly flagged as "the most
security-sensitive phase." Same 37-section master prompt as Phases 2-6
(strict phase scope; git safety preflight; pre-implementation task
audit; repository-reality check; per-task IMPLEMENT→TEST→VERIFY→
ADVERSARIAL REVIEW→REGRESSION CHECK→CLOSE; 13-area architecture freeze
including the Authentication Freshness and Cross-Tenant Safety
sub-sections; extensive security adversarial testing — auth crossover,
session abuse, tenant lifecycle abuse; contract lock; full 3-way (now
4-way) audit fail-closed proof; full diff review; evidence-based
checkboxes; exit-condition/Gate C proof; requirement traceability; final
consistency search; PHR; pre-commit check; one coherent completion
commit; 16-part final report; final stop rule). Full verbatim text in
the conversation transcript.

## Response snapshot

**Preflight**: branch `009a-platform-admin`, clean tree, Phase 6
(`eaf6c39`) present in history.

**Repository-reality finding**: migration 057 (Phase 2, frozen) already
added `pre_suspension_status`/`access_invalidated_at` columns to the
`companies` table at the DB level, but the SQLAlchemy `Company` ORM
model was never updated to map them — deliberately deferred to this
phase per the "don't pre-create future abstractions" discipline. Added
both columns plus their 2 CHECK constraints to the ORM model, verified
they match migration 057 exactly.

**T082-T087 (company access layer)**: `assert_company_access_allowed(db,
company_id, session_id)` — status-code mapping matches
`get_current_company`'s pre-existing behaviour exactly (suspended→403,
deleted→404), so wiring it in replaces `get_current_company`'s manual
checks byte-identically while adding the watermark layer, and gives
`get_current_company_member` a check it never had at all before
(closing the actual §3.3 gap). 9 unit tests + 1 live-HTTP rollout-safety
test (NULL watermark across all 5 business modules) passing.

**T088-T090 (TenantLifecycleService + routes)**: Discovered
`CompanyRepository.update()`/`soft_delete()`/`restore()` all auto-commit
internally — incompatible with ADR-5 atomicity. Added 3 new flush-only
methods (`get_for_update`, `suspend`, `reactivate`) rather than reusing
the auto-committing ones; left the tenant-side `CompanyService`'s
pre-existing non-atomic pattern untouched (out of scope). Reused the
already-defined-but-never-instantiated `CompanySuspendedEvent`/
`CompanySuspensionLiftedEvent` and the already-defined-but-never-raised
`TenantLifecycleTransitionError`. Two new routes with mandatory,
whitespace-rejecting `reason` validation.

**T091-T094 (lifecycle tests)**: Active/inactive round-trips, repeated-
transition rejection, and — for T094 — a genuine real-PostgreSQL
concurrency test connecting directly via `SessionLocal()` (bypassing the
SQLite `db_session` fixture entirely) with two threads and a deliberate
lock-hold delay to force genuine row-lock contention; verified zero
leftover test data via direct `psql` query after teardown.

**T095-T100 (Gate C security tests)**: Old access token denied, refresh-
bypass guard (the single most safety-critical assertion in the phase),
genuine-login restoration, cross-tenant isolation, multi-device
semantics, and manipulation resistance. Discovered and fixed a genuine
test-environment precision bug along the way: SQLite's whole-second
`CURRENT_TIMESTAMP` (backing `Session.created_at`'s `server_default`)
vs. the watermark's Python-side microsecond `datetime.now(UTC)` produced
same-second ties in fast automated tests, incorrectly denying a genuine
new login — fixed with an explicit test-only delay, documented as a
test-environment artifact (real humans take more than a second to log
back in), not a production gap.

**T101 (4-way atomicity)**: Extended Phase 6's `test_audit_fail_closed.py`
(same file, not a duplicate) with the fuller proof against the real
suspension mutation — all 4 pieces (status, `pre_suspension_status`,
`access_invalidated_at`, `OutboxRecord`) verified rolled back together on
forced failure, and genuinely committed together on success.

**T102 (Gate C sign-off)**: PASSED — all named dependencies (T091-T101)
green.

## Outcome

- ✅ Impact: Tenant suspension/reactivation is now a real, atomic,
  audited capability with genuine company-scoped, authentication-time-
  keyed access invalidation across all five business modules — the
  single most security-critical property in Epic 9A.
- 🧪 Tests: 26 new Phase 7 tests passing; combined Phase 1-7
  platform_admin suite 118/118 passing; T087's full 5-module regression
  972 passed, 4 pre-existing skips, 0 failed.
- 📁 Files: 6 modified backend source files, 3 new services/schemas, 7
  new/extended test files, tasks.md.
- 🔁 Next prompts: Phase 8 — Plans, Subscriptions, Capabilities & Quota
  Foundation, on explicit Product Owner instruction only.
- 🧠 Reflection: When a shared test fixture's timestamp resolution is
  coarser than the production code's, same-tick ties in fast automated
  tests can produce a false negative on a `<=` boundary condition that
  is correct in production — the fix belongs in the test (force a real
  time gap), not in loosening the production comparison.

## Evaluation notes (flywheel)

- Failure modes observed: (1) SQLite `CURRENT_TIMESTAMP` whole-second
  resolution causing same-tick watermark ties in T097/T099. (2)
  `CompanyRepository`'s pre-existing write methods all auto-commit,
  silently incompatible with the ADR-5 pattern this phase's write path
  required — caught via inspection before writing the service, not via
  a failing test.
- Graders run and results (PASS/FAIL): ruff PASS, black PASS (after one
  reformat pass), all 26 new Phase 7 tests PASS, combined 118-test suite
  PASS, T087 pending confirmation.
- Prompt variant (if applicable): n/a — fixed master template.
- Next experiment (smallest change to try): n/a.
