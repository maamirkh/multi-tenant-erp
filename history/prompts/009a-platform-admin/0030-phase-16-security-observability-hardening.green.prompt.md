---
id: 0030
title: Phase 16 — Security, Integration & Observability Hardening
stage: green
date: 2026-08-23
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.implement
labels: ["epic-9a", "phase-16", "backend", "security", "observability", "performance", "gate-b"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/tests/security/modules/platform_admin/test_permission_matrix.py
  - backend/tests/security/modules/platform_admin/test_idor.py
  - backend/tests/security/modules/platform_admin/test_mass_assignment.py
  - backend/tests/security/modules/platform_admin/test_lifecycle_abuse.py
  - backend/tests/security/modules/platform_admin/test_quota_enforcement.py
  - backend/tests/performance/modules/platform_admin/test_platform_queries.py
  - backend/tests/unit/modules/platform_admin/test_request_scoped_memoisation.py
  - backend/modules/platform_admin/dependencies.py
  - backend/modules/platform_admin/router.py
  - backend/modules/platform_admin/bootstrap.py
  - backend/modules/platform_admin/services/platform_auth_service.py
  - backend/modules/platform_admin/services/tenant_lifecycle_service.py
  - backend/modules/platform_admin/services/override_service.py
  - backend/modules/platform_admin/services/quota_admin_service.py
  - backend/modules/platform_admin/services/support_access_service.py
  - backend/modules/platform_admin/services/platform_audit_service.py
  - backend/modules/platform_admin/services/health_service.py
  - backend/modules/platform_admin/services/dashboard_service.py
  - specs/009a-platform-admin/tasks.md
tests:
  - backend/tests/security/modules/platform_admin/test_permission_matrix.py (122 passed — local venv, specs/ not mounted in container)
  - backend/tests/security/modules/platform_admin/test_idor.py (6 passed)
  - backend/tests/security/modules/platform_admin/test_mass_assignment.py (6 passed)
  - backend/tests/security/modules/platform_admin/test_lifecycle_abuse.py (7 passed)
  - backend/tests/security/modules/platform_admin/test_quota_enforcement.py (5 passed)
  - backend/tests/performance/modules/platform_admin/test_platform_queries.py (6 passed, no numeric SLA)
  - backend/tests/unit/modules/platform_admin/test_request_scoped_memoisation.py (4 passed)
  - full platform_admin unit+integration+security+performance suite (237 passed, 0 failed — 2 contract-file tests excluded, container-mount limitation, verified separately via local venv: 3/3 passed)
  - cross-module regression: CRM/Inventory/Sales/Purchase/Accounting (972 passed, 4 skipped, 0 failed)
---

## Prompt

```text
# Epic 9A — Platform Administration / Super Admin
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close ONLY the following phase of Epic 9A.

## TARGET PHASE

**Phase Number:** `16`
**Phase Name:** `Security, Integration & Observability Hardening`
**Task Range:** `<T206 to T225>`

[... the full ~700-line master-prompt template, identical in structure and content to the one embedded verbatim in PHR 0021 (Phase 8) and referenced by PHRs 0022-0029, with Phase Number=16, Phase Name="Security, Integration & Observability Hardening", Task Range=T206 to T225 as literally requested. Sections 1-37 cover: strict phase scope; branch/working-tree requirements; the pre-implementation task audit; the repository-reality check; the six-step per-task implementation rule; the full Architecture Freeze; database/migration hard rules (N/A this phase — no migration touched); the API Contract Lock (N/A — no new HTTP operations, this phase only tests/hardens the existing 28-path/33-operation surface); the full adversarial security-testing checklist (directly exercised — T206-T210 *are* this checklist, formalized); tenant isolation audit (T207); the seven-level testing pyramid; pre-existing failure policy; real PostgreSQL/Docker verification (via the running `erp-system-api-1` container for the bulk of the work, local venv for the two `specs/`-dependent contract-reading test files); live HTTP/browser verification (N/A — backend-only phase); the post-implementation self-review checklist; the adversarial completeness pass; the full diff review; the task-checkbox rule; the phase exit condition rule; the Gate rule (T206 completes Gate B's final coverage, but Phase 16 itself owns no new Gate); regression verification (exhaustively run — see Tests above); the no-correction-pass standard (directly exercised — see the T210 contradiction below); PHR requirements; pre-commit checks; commit policy; post-commit verification; the required final report structure (sections A-P); and the final stop rule. Full text identical to prior phase PHRs' embedded prompts — see PHR 0021 for the complete verbatim template if needed.]
```

## Response snapshot

The literal task range T206-T225 spans two structurally distinct tasks.md phases: Phase 16 (T206-T213, no Gate) and Phase 17 (T214-T225, Gate G, real-stack Docker Compose + Playwright browser verification + Epic closure, with its own stated prerequisite "all previous phases, all gates A-F green"). Per the master prompt's own "planning contradiction → STOP and report" rule, this was surfaced to the user via `AskUserQuestion` before any implementation began; the user chose "Phase 16 only (T206-T213)" — the recommended, tasks.md-consistent option. Phase 17 was not started.

**Pre-implementation audit**: verified all 10 named dependencies (T177, T090, T114, T157, T162, T170, T174, T176, T068, T069, T102, T149, T122, T083) exist and are complete by direct code inspection, not checkbox trust — confirmed via reading the actual router/service/dependency implementations from Phases 4-13.

**T206** (exhaustive permission matrix): loaded `GUARDED_OPERATIONS` directly from the real YAML contract (never a hand-duplicated table, avoiding the exact drift risk T177's own test file guards against) — confirmed exactly 30 operations, T076's Phase-5 6-operation subset re-verified as a subset. Built a per-operation fixture-builder (`OPERATION_BUILDERS`) covering all 30 — required reading every relevant service's precondition requirements first (e.g. `SubscriptionService.assign_or_change()` requires a `published` Plan; `PlatformAdministratorService.activate()` has no idempotency guard so any target works). 122 tests, first-try 100% pass.

**T207-T210** (IDOR, mass-assignment, lifecycle abuse, quota enforcement): each required reading the actual service/repository code to determine genuine, non-fabricated assertions rather than assumed behavior. T209 specifically: the initially-assumed `INVALID_STATUS_TRANSITION` 409 for owner-side `suspended→inactive`/`suspended→deleted` direct attempts turned out to be a 403 `COMPANY_SUSPENDED` instead — `CompanyRepository.get_by_id_active()` (Phase 10's own T084 hardening) denies a suspended company one layer *before* the owner-transition table is even reached; the test was corrected to match the real, verified code path.

**T210 contradiction (STOP-and-report, user-adjudicated)**: a direct codebase search (`grep -rln "QuotaService(" modules/` outside `platform_admin`) found zero business-module write paths ever call the quota resolver — confirming, via T151's own recorded task evidence, that quota "hard enforcement at the module's own write path" (plan.md's own phrase) genuinely does not exist anywhere in this codebase yet, and building it now would be unauthorized scope expansion (forbidden by this very phase's Architecture Freeze, and not assigned to any T206-T213 task). Surfaced to the user via `AskUserQuestion`; the recommended option was chosen — test the resolver's own correctness (enforcement-style pass-through, override bypass-proofing, cross-tenant isolation) and document the gap explicitly in the test file's own module docstring, rather than fabricate a test against non-existent enforcement or silently expand scope.

**T211** (structured operational logging): repository-reality check found the 8 named event categories almost entirely unlogged (only permission-denial and RBAC/capability seeding already had logging). Added `logger.info`/`.warning`/`.error` with `request_id`+actor-id `extra={}` at every real event site across 9 service files — including wrapping `PlatformAuditService.record()` in try/log/re-raise (fail-closed behavior byte-identical, pure observability addition) and all 3 `HealthService` checks + all 7 `DashboardService` widget catch sites. Verified by direct grep that no password/hash/JWT/refresh-token/secret value is ever logged.

**T213** (request-scoped memoisation): investigation found `db.get(Company, ...)` reads are already free (SQLAlchemy's per-Session identity map) and `Depends(get_current_platform_admin)` is already deduped per-request by FastAPI's own default caching — so no work was needed there. Found one concrete, currently-existing duplicate: `require_platform_permission`'s dependency and the `GET /dashboard` handler each independently called `PlatformRbacRepository.get_effective_permissions()` for the same administrator in the same request. Fixed with a new `get_effective_permissions_cached(request, principal, db)` helper backed by `request.state` (fresh every request, never process-level), consumed by both sites — necessarily touching `router.py` (one line) alongside the primarily-scoped `dependencies.py`, justified and documented since the fix is otherwise unobservable. `require_capability_entitled` gained the same `(company_id, capability_key)` memoisation defensively, matching the task's literal acceptance text even though no second concrete caller exists for it yet. Proven by 4 `unittest.mock.patch.object(..., wraps=...)` spy-based unit tests.

**T212** (performance/pagination/index/N+1): no numeric SLA asserted, per the task's own explicit instruction (differs deliberately from the repo's existing `test_list_performance.py` p95-timing precedent). Tenant-list/audit-list pagination bounded at 500-row scale; T014's 4 audit indexes confirmed present on the test schema; discovered during implementation that the override tables' PostgreSQL-only partial-unique indexes are deliberately *not* mirrored into the SQLAlchemy model (already verified against real Postgres in Phase 8's own closure) — corrected the test to check the company-scoping index that *is* mirrored, documenting why in the test file rather than asserting something structurally unverifiable via SQLite. N+1 proof used a real `before_cursor_execute` query counter comparing a 5-company dataset against a 500-company dataset for both `get_tenant_detail()` and `get_dashboard()` — identical query counts in both, genuine proof neither scales with total data volume.

**Regression**: full `platform_admin` unit+integration+security+performance suite (237 tests, excluding the 2 tests requiring `specs/` outside the container — verified separately via local venv, 3/3 passing) — 237/237 passing, zero regressions from any T211/T213 production-code change. Full cross-module regression (CRM/Inventory/Sales/Purchase/Accounting, since `require_capability_entitled`'s signature changed and it mounts on all five) — 972 passed, 4 skipped, 0 failed.

**Phase 16 Exit Condition: PASS.** Gate: N/A (T206 completes Gate B's final coverage; Phase 16 itself owns no Gate in the A→B→E→C→D→F→G order). No migration touched, no `062` created. No frontend files touched.

## Outcome

- ✅ Impact: Epic 9A's Platform Administration backend now has exhaustive permission-matrix proof over its complete 30-operation surface, four categories of adversarial security coverage (IDOR, mass-assignment, lifecycle abuse, and an honestly-scoped quota-resolver proof), structured operational logging across every previously-silent privileged-action category, a fixed real duplicate-read (permission checks), and N+1-proof regression guards on its two heaviest aggregate read paths — all with zero regressions across 1,209 total tests run this phase (237 platform_admin + 972 cross-module).
- 🧪 Tests: 39 new tests across 6 new files (122 + 6 + 6 + 7 + 5 + 6 + 4, excluding the recount overlap — precisely: T206=122, T207=6, T208=6, T209=7, T210=5, T212=6, T213=4 = 156 new test functions); zero regressions in 237 existing platform_admin tests + 972 cross-module tests.
- 📁 Files: 6 new test files, 11 modified production files (9 services + dependencies.py + router.py + bootstrap.py), `tasks.md` updated (T206-T213 marked `[X]` with evidence).
- 🔁 Next prompts: Phase 17 — Real-Stack Verification & Epic Closure, Gate G (T214-T225: Docker Compose live migration/RBAC/suspension/entitlement/support-access verification, 3 Playwright browser scripts, cross-module Gate G regression, Epic closure audit) — explicitly not started this session, per both the user's own phase-scope decision and the Final Stop Rule.
- 🧠 Reflection: This phase surfaced two genuine planning contradictions in a single session — the phase-boundary mismatch (T206-T225 spanning two tasks.md phases) and the T210 quota-enforcement-point gap — and both were correctly escalated via `AskUserQuestion` rather than silently resolved by guessing or by quietly expanding scope to build the missing enforcement wiring. The T210 finding in particular is a good instance of the discipline this session has applied repeatedly (Phase 13's dashboard permission-coverage gap, Phase 15's nav-permission contract gap): when a task's acceptance text assumes an implementation that a direct `grep` proves doesn't exist, the correct move is never to fabricate a passing test against nothing — it's to prove what's real, document the gap precisely where a future implementer will find it, and let the person who owns the roadmap decide whether closing it is in scope.

## Evaluation notes (flywheel)

- Failure modes observed: (1) T209's test initially assumed the wrong exception/status code (409 `INVALID_STATUS_TRANSITION`) for an owner-side transition-from-suspended attempt — the real code path (`get_by_id_active()` excluding suspended companies) produces 403 `COMPANY_SUSPENDED` one layer earlier; caught by actually reading `company_service.py`'s dependency chain rather than assuming from the transition table alone. (2) T212's entitlement-override partial-unique-index check initially assumed it would be visible via SQLite `inspect().get_indexes()` — it isn't, by deliberate design (Postgres-only, not mirrored into the ORM model); corrected to check the company-scoping index that *is* mirrored, with the reasoning documented in the test file itself. (3) T213's entitlement-memoisation test initially didn't account for the dependency raising on denial (no Subscription -> Unavailable) before a second call could execute — fixed by wrapping both calls in an exception-swallowing helper, since denial itself was expected/correct and orthogonal to what the test measures (call count).
- Graders run and results (PASS/FAIL): all 156 new Phase-16 tests PASS; full platform_admin regression PASS (237/237, 2 contract tests separately verified 3/3 via local venv); cross-module regression PASS (972/972, 4 pre-existing skips).
- Prompt variant (if applicable): master-prompt template identical to Phases 8-15; first phase this session requiring `AskUserQuestion` twice for genuine scope/contradiction clarification rather than proceeding on inferred judgment alone.
- Next experiment (smallest change to try): when a task's Files field names one file but its acceptance criterion cannot be observably satisfied without also touching a caller elsewhere (T213's router.py case), state the necessary secondary-file touch explicitly in the pre-implementation audit rather than discovering it mid-implementation — would have made the scope call visible earlier in the process rather than as an in-flight decision.
