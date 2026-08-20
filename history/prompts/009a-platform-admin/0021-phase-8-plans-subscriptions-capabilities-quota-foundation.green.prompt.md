---
id: 0021
title: Phase 8 Plans Subscriptions Capabilities Quota Foundation
stage: green
date: 2026-08-21
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.implement
labels: ["platform-admin", "implement", "phase-8", "plans", "subscriptions", "quota", "capabilities"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/platform_admin/models/plan.py
 - backend/modules/platform_admin/models/capability.py
 - backend/modules/platform_admin/models/plan_capability.py
 - backend/modules/platform_admin/models/subscription.py
 - backend/modules/platform_admin/models/quota.py
 - backend/modules/platform_admin/models/__init__.py
 - backend/modules/platform_admin/repositories/plan_repository.py
 - backend/modules/platform_admin/repositories/capability_repository.py
 - backend/modules/platform_admin/repositories/subscription_repository.py
 - backend/modules/platform_admin/repositories/quota_repository.py
 - backend/modules/platform_admin/services/plan_service.py
 - backend/modules/platform_admin/services/subscription_service.py
 - backend/modules/platform_admin/services/quota_service.py
 - backend/modules/platform_admin/schemas/plan.py
 - backend/modules/platform_admin/schemas/subscription.py
 - backend/modules/platform_admin/exceptions.py
 - backend/modules/platform_admin/router.py
 - backend/api/v1/router.py
 - backend/modules/companies/repositories/company_repository.py
 - backend/tests/unit/modules/platform_admin/test_quota_resolution.py
 - backend/tests/integration/services/platform_admin/test_plan_lifecycle.py
 - backend/tests/integration/services/platform_admin/test_subscription.py
 - backend/tests/integration/repositories/platform_admin/test_subscription_constraints.py
 - specs/009a-platform-admin/tasks.md
tests:
 - backend/tests/unit/modules/platform_admin/test_quota_resolution.py (15 passed)
 - backend/tests/integration/services/platform_admin/test_plan_lifecycle.py (6 passed)
 - backend/tests/integration/services/platform_admin/test_subscription.py (3 passed)
 - backend/tests/integration/repositories/platform_admin/test_subscription_constraints.py (1 passed, real PostgreSQL)
 - Full platform_admin module regression (unit + integration/services + integration/api + integration/repositories + security), Phases 1-8 combined (140 passed)
 - Companies module regression (271 passed, 6 pre-existing failures characterized as Phase-7-origin, unrelated to this phase's diff)
---

## Prompt

Phase 8 of the Epic 9A `/sp.implement` master-prompt sequence: "Plans, Subscriptions, Capabilities & Quota Foundation", Task Range T103–T117. Same 37-section master template used for every prior phase in this sequence (strict phase scope, pre-implementation task audit, repository-reality check, IMPLEMENT→TEST→VERIFY→ADVERSARIAL REVIEW→REGRESSION CHECK→CLOSE per task, frozen architecture list, migration range frozen 057-061 with no 062, contract lock against `contracts/platform-admin-v1.yaml`, 7-level testing pyramid, real PostgreSQL verification, fail-closed audit proof, self-review + adversarial completeness passes, full diff review, PHR creation, pre-commit checks, single completion commit, and a mandatory 16-part final report ending in `PHASE 8 COMPLETE — READY FOR NEXT PHASE` or `PHASE 8 NOT COMPLETE — BLOCKED`).

## Response snapshot

Implemented all 15 tasks (T103-T117):

- **T103-T106** (models): `Plan`, `Capability`, `PlanCapability`, `Subscription` — all mapped onto the already-existing, already-committed migration 058 schema (`plans`, `capabilities`, `plan_capabilities`, `subscriptions`). Verified column-by-column against migration source and via live `count=0` queries against the real PostgreSQL database.
- **T107-T109** (quota foundation): `QuotaDefinition`, `PlanQuota`, `TenantQuotaOverride` models (migration 059) + `QuotaRepository`; `QuotaService.resolve()` — the single authoritative resolver, override → PlanQuota → unlimited, five states (`ok|approaching|reached|unlimited|unavailable`), NULL `limit_value` always means unlimited (never a sentinel). `EntitlementOverride` deliberately left unmapped (Phase 9 scope). 15 unit tests, all passing.
- **T110-T111**: `PlanRepository`, `CapabilityRepository`, `SubscriptionRepository` (all flush-only writes, ADR-5); `PlanService` (create always `draft`; `publish`/`retire` enforce `draft→published→retired` via `PlanTransitionError`).
- **T112-T113**: `SubscriptionService.assign_or_change()` — ends the prior active Subscription, creates the new one, syncs `companies.subscription_id` (new flush-only `CompanyRepository.set_subscription_id()`), all inside one service-level commit with the audit row. Downgrade usage-conflict check measures the `users` quota key live (`CompanyMember` COUNT — the only genuinely-live-measurable key in this phase, matching spec.md's own worked US-5 example); rejects without `acknowledged=True`, applies and naturally reports `reached` via `QuotaService.resolve()` on next check with acknowledgement — no new persisted "over-quota" column needed.
  - **Gap found and fixed during implementation** (not explicit in the original task text): nothing was checking the target Plan's `status` before assignment, so a `draft`/`retired` Plan could be silently subscribed to. Added a `plan.status != "published"` guard raising a new `PlanNotAssignableError` (409) — this is the actual enforcement point for BR-9A-018/FR-9A-152's "a retired plan no longer appears as an assignment option."
- **T114**: `plan_router` (new) + two new operations on the existing `tenant_router`, mounted in `api/v1/router.py`. `PATCH /plans/{planId}` implements the contract's single combined "Update/publish/retire" operation via a request-body `action` field, rather than three separate endpoints — verified via live OpenAPI introspection that exactly 5 operations exist at exactly the 3 contract paths, and that all 4 permission codes were already seeded (no new permission invented).
- **T115-T117**: new test files proving retired-plan-keeps-subscriptions-but-is-unassignable (6 tests), the real-PostgreSQL partial-unique-index enforcement (1 test, mirrors T094's SessionLocal-bypass pattern, verified zero leftover rows), and end-date validation + downgrade acknowledgement including proof of zero data truncation (3 tests).

Full platform_admin regression (Phases 1-8, unit+integration+security): **140 passed, 0 failed**. Companies-module regression run as a scoped-impact check for the new `CompanyRepository.set_subscription_id()` method: 271 passed, 6 failed — all 6 traced via isolated reruns and `git diff HEAD` (files untouched by this phase) to a pre-existing Phase 7 gap (`assert_company_access_allowed()` calls in `dependencies.py` hitting stale test mocks that predate Phase 7, e.g. `Mock` objects without `session_id`) — confirmed unrelated to this phase's purely-additive diff, documented rather than fixed (out of Phase 8 scope), not hidden.

`tasks.md` T103-T117 marked `[X]` with dated Result notes; structural invariants verified (225 tasks total, sequential T1-T225, no gaps/dupes, all and only T1-T117 checked).

## Outcome

- ✅ Impact: Phase 8 complete — SaaS commercial control plane (Plans, Subscriptions, Capabilities) and the quota foundation (models + single resolver) are in place, unblocking Phase 9's entitlement resolver/rollout and Phase 11's baseline-plan seeding.
- 🧪 Tests: 140/140 platform_admin regression passing; 6 pre-existing unrelated companies-module failures characterized, not fixed (out of scope).
- 📁 Files: 17 new files, 5 modified files (see `files:` above) — all within Phase 8's declared scope; no migration 062, no `EntitlementOverride` mapping, no T125 baseline-plan pull-forward.
- 🔁 Next prompts: Phase 9 (Entitlement Resolver, Safe Rollout & Point-of-Use Enforcement — Gate D), pending explicit user instruction.
- 🧠 Reflection: The most valuable finding this phase was self-discovered, not task-specified — the original T112/T113 acceptance text never mentioned checking the target Plan's `status`, yet without that check BR-9A-018/FR-9A-152 ("retired plan no longer appears as an assignment option") had no actual enforcement point anywhere in the codebase. Caught by re-reading the acceptance criteria against the implemented behavior before writing T115's tests, not by a failing test.

## Evaluation notes (flywheel)

- Failure modes observed: A repository-reality gap (plan-status check absent from `SubscriptionService.assign_or_change()`) was found by requirement-tracing rather than by a failing test — worth deliberately doing this trace *before* writing the phase's tests in future phases, not just at self-review time.
- Graders run and results (PASS/FAIL): Master-prompt Gate/Exit-Condition check — PASS (no Gate assigned to Phase 8; T103-T117 acceptance criteria all proven). Full diff review — PASS (no scope leakage). Pre-existing-failure policy — PASS (6 companies-module failures characterized and attributed to Phase 7, not silently hidden or falsely claimed fixed).
- Prompt variant (if applicable): n/a — identical master template to Phases 5-7.
- Next experiment (smallest change to try): n/a.
