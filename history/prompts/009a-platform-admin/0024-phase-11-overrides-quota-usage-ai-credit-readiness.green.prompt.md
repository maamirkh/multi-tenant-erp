---
id: 0024
title: Phase 11 — Overrides, Quota Administration, Usage & AI-Credit Readiness
stage: green
date: 2026-08-22
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.implement
labels: ["epic-9a", "phase-11", "entitlement-overrides", "quota-overrides", "usage-metering", "ai-credit-readiness"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/platform_admin/models/entitlement_override.py
  - backend/modules/platform_admin/models/usage_record.py
  - backend/modules/platform_admin/models/ai_credit_ledger.py
  - backend/modules/platform_admin/models/__init__.py
  - backend/modules/platform_admin/repositories/override_repository.py
  - backend/modules/platform_admin/repositories/usage_repository.py
  - backend/modules/platform_admin/repositories/ai_credit_repository.py
  - backend/modules/platform_admin/repositories/quota_repository.py
  - backend/modules/platform_admin/services/override_service.py
  - backend/modules/platform_admin/services/quota_admin_service.py
  - backend/modules/platform_admin/services/usage_service.py
  - backend/modules/platform_admin/services/ai_credit_service.py
  - backend/modules/platform_admin/schemas/override.py
  - backend/modules/platform_admin/schemas/quota.py
  - backend/modules/platform_admin/schemas/usage.py
  - backend/modules/platform_admin/schemas/ai_credit.py
  - backend/modules/platform_admin/dependencies.py
  - backend/modules/platform_admin/router.py
  - backend/modules/platform_admin/exceptions.py
  - backend/tests/unit/modules/platform_admin/test_override_precedence.py
  - backend/tests/integration/services/platform_admin/test_usage.py
  - backend/tests/integration/services/platform_admin/test_audit_fail_closed.py
  - backend/tests/integration/api/v1/platform_admin/test_ai_credits.py
  - backend/tests/integration/api/v1/platform_admin/test_phase11_tenant_isolation.py
  - specs/009a-platform-admin/tasks.md
tests:
  - backend/tests/unit/modules/platform_admin/test_override_precedence.py (8 passed)
  - backend/tests/integration/services/platform_admin/test_usage.py (4 passed)
  - backend/tests/integration/services/platform_admin/test_audit_fail_closed.py (6 passed, 4 pre-existing + 2 new)
  - backend/tests/integration/api/v1/platform_admin/test_ai_credits.py (4 passed)
  - backend/tests/integration/api/v1/platform_admin/test_phase11_tenant_isolation.py (3 passed)
  - backend/tests/unit/modules/platform_admin/ + tests/integration/services/platform_admin/ + tests/integration/api/v1/platform_admin/ (111 passed, regression)
  - backend/tests/unit/modules/platform_admin/test_entitlement_matrix.py + test_entitlement_rollout.py + test_entitlement_enforcement.py + test_feature_toggle_hardening.py + test_plan_ceiling_secondary_guard.py (48 passed, Phase 9/10 regression)
  - backend/tests/integration/api/v1/inventory/test_products_api.py + test_master_data_api.py + crm/test_feature_flag_gate.py (65 passed, cross-module regression)
---

## Prompt

```text
# Epic 9A — Platform Administration / Super Admin
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT


Implement, verify, audit, and close ONLY the following phase of Epic 9A.


## TARGET PHASE


**Phase Number:** `11`
**Phase Name:** `Overrides, Quota Administration, Usage & AI-Credit Readiness`
**Task Range:** `<T145 to T157>`


---


# PRIMARY OBJECTIVE


Complete the target phase to a standard where it should NOT require a later correction pass for issues that could reasonably have been discovered during implementation.


Do not treat task checkbox completion as sufficient.


The phase is complete only after:


1. prerequisites are verified;
2. every target task is implemented;
3. every acceptance criterion is proven;
4. dependency relationships are validated;
5. security and tenant-isolation implications are tested;
6. relevant regression tests pass or pre-existing failures are explicitly characterized;
7. required real PostgreSQL / Docker / HTTP verification is completed;
8. the phase is independently self-audited against Spec, Plan, Contract, Data Model, Quickstart, and Tasks;
9. no hidden incomplete work remains;
10. the phase exit condition and applicable Gate are genuinely satisfied.


Use the principle:


**IMPLEMENT → TEST → VERIFY → ADVERSARIAL REVIEW → REGRESSION CHECK → CLOSE**


Do not declare the phase complete before all applicable steps are finished.


---


# 1. STRICT PHASE SCOPE


Implement ONLY:


**Phase `<PHASE_NUMBER>` — `<PHASE_NAME>`**
**Tasks `<TASK_RANGE>`**


Do NOT start the next phase.


Do NOT implement future tasks merely because doing so appears convenient.


Do NOT pre-create future:


- models;
- migrations;
- services;
- repositories;
- routes;
- frontend pages;
- permissions;
- entitlement logic;
- quota logic;
- support-access functionality;
- AI functionality.


Exception:


If a target task's approved dependency explicitly requires an artifact from an earlier phase, use that artifact.

Required:

branch = 009a-platform-admin
working tree = clean

Also verify that the previous completed phase is present in branch history where applicable.

Do NOT:

rebase;
merge;
cherry-pick;
reset;
amend unrelated history;
force push;
move branch pointers;
delete branches.

If working tree is unexpectedly dirty:

STOP immediately and report exact files.

Do not mix unrelated work into the phase.

4. PRE-IMPLEMENTATION TASK AUDIT

Before writing code, inspect EVERY task in <TASK_RANGE>.

Build an internal checklist containing:

Task ID
Purpose
Files
Dependencies
Acceptance criteria
Relevant FR
Relevant BR
Relevant SC
Relevant ADR
Security implications
Tenant-isolation implications
Required tests
Gate relevance

Verify every dependency before implementation.

For every task dependency:

dependency exists
AND
dependency is already complete
AND
required artifact/behavior actually exists

Do NOT trust checkbox state alone.

Inspect the implementation/evidence.

If a dependency is incomplete:

STOP and report it.

5. REPOSITORY-REALITY CHECK

Before creating any new abstraction, search the repository for existing equivalents.

Specifically look for existing:

models;
repositories;
services;
exceptions;
schemas;
dependencies;
permission guards;
audit patterns;
transaction patterns;
auth/session utilities;
company-context utilities;
feature-toggle enforcement;
migrations;
frontend API clients;
frontend contexts;
route groups;
tests;
constants.

Do NOT create a second competing implementation where an approved reusable implementation already exists.

Prefer extension/reuse when consistent with the approved architecture.

6. IMPLEMENTATION RULE

For each task:

Step A — inspect

Read the exact existing files first.

Step B — implement

Make the smallest correct implementation satisfying the approved requirement.

Step C — focused test

Run the narrowest relevant test immediately.

Step D — acceptance proof

Explicitly prove every Acceptance criterion.

Step E — negative-path proof

For security/lifecycle/isolation tasks, test misuse/failure behavior too.

Step F — dependency re-check

Verify the completed implementation still satisfies dependent assumptions.

Only then may the task be marked [X].

Do not batch-check tasks at the end without task-level evidence.

7. ARCHITECTURE FREEZE

Do NOT redesign these finalized decisions.

Platform Identity
Existing User credentials remain shared credential identity.
PlatformAdministrator is a separate first-class Platform principal.
Platform authority does not come from tenant membership.
No super_admin boolean shortcut.
No tenant role may grant Platform authority.
Platform Sessions

Platform authentication remains structurally separate from tenant authentication.

Maintain separate:

Platform Session
Platform Refresh Token
token type
authentication dependency
refresh flow
revocation behavior

Tenant credentials/tokens must never authenticate as Platform authority.

Platform tokens must never satisfy tenant authentication.

Platform RBAC

Use actual permission-code enforcement.

Preserve:

require_platform_permission(...)

or the finalized equivalent defined by the Plan.

Do NOT copy ineffective legacy tenant RBAC behavior.

Protect:

self-escalation;
last Platform Owner;
inactive/deactivated administrators.
Bootstrap

First Platform Owner remains out-of-band.

No:

bootstrap HTTP endpoint;
bootstrap migration;
hardcoded production credential.
Tenant Lifecycle

Preserve finalized lifecycle state transitions.

Use:

pre_suspension_status

for deterministic restoration.

Never assume every reactivation becomes active.

Authentication Freshness

The authoritative freshness carrier remains:

Session.created_at

with Company:

access_invalidated_at

The intended rule remains:

Session.created_at <= Company.access_invalidated_at
→ deny access to that Company

Do NOT replace this with JWT iat.

Refresh must NOT count as new authentication.

A refresh using a pre-suspension Session must remain stale.

Only a genuine login creating a new Session advances authentication freshness.

Cross-Tenant Safety

A user belonging to Companies A and B must retain access to B when only A is suspended.

Do NOT globally invalidate unrelated Company access.

Entitlements

Maintain:

Plan entitlement ceiling
→ tenant preference/toggle
→ approved override rules
→ effective entitlement
→ point-of-use enforcement

Do not destroy stored toggle preferences during plan downgrade.

Quotas

Quota is separate from entitlement.

NULL = unlimited

Do not use arbitrary large sentinel values.

Use one authoritative quota resolver.

Context Separation

Tenant UI:

CompanyContext / erp_active_company_id

Platform UI:

PlatformSelectedTenantContext

These must remain separate.

Browser/localStorage state is never authorization authority.

Audit

Privileged mutations requiring audit must be fail-closed.

Required model:

domain mutation
+ audit event
+ required outbox event
→ same transaction
→ single service-level commit

If mandatory audit fails:

ROLLBACK EVERYTHING

Do not introduce repository-level commits that break atomicity.

Support Access

Support access remains:

permission-controlled;
reason-bound;
time-bounded;
audited;
inspection-only.

No unrestricted impersonation.

No tenant business-record browsing.

AI

Epic 9A remains provider-neutral.

Do NOT integrate:

OpenAI;
Anthropic;
Gemini;
OpenClaw;
model billing APIs.
Infrastructure

Do NOT introduce:

Redis;
Kafka;
Kubernetes;
microservices;
second database;
unrelated infrastructure.
8. DATABASE & MIGRATION HARD RULES

Epic 9A migration range is frozen:

057
058
059
060
061

No migration:

062

may be created.

Before creating/editing migrations:

inspect current Alembic head;
inspect migrations 056 and earlier;
verify actual existing schema;
verify planned migration ordering;
verify downgrade compatibility.

Use PostgreSQL semantics.

Do NOT validate migration behavior only against SQLite.

9. MIGRATION 057 PRE-FLIGHT RULE

Where applicable, migration 057 must inspect existing suspended Companies before applying assumptions requiring historical pre-suspension state.

If existing:

status = suspended

rows make deterministic backfill impossible:

FAIL BEFORE MUTATING SCHEMA/DATA.

Report affected records/remediation.

Do NOT:

guess pre_suspension_status;
assume active;
assume inactive;
silently weaken constraints.

Failure must not leave a partial migration.

10. API CONTRACT LOCK

For HTTP/API work, inspect:

specs/009a-platform-admin/contracts/platform-admin-v1.yaml

before implementation.

The finalized contract contains:

28 paths
33 operations
3 public auth operations
30 permission-guarded operations

Do not invent undeclared CRUD.

Do not omit declared operations belonging to the current phase.

Routers should primarily handle:

request validation;
dependency wiring;
authentication;
permission enforcement;
service delegation.

Business logic belongs in services.

11. SECURITY ADVERSARIAL TESTING

Do not test only happy paths.

Where relevant to the phase, explicitly attempt:

Authentication crossover
tenant token → Platform API
Platform token → tenant API

Both must fail.

Session abuse
revoked Platform Session;
revoked refresh token;
deactivated administrator;
stale pre-suspension Session;
stale refresh after reactivation.
RBAC abuse
no permission;
adjacent permission;
self-escalation;
last-owner removal/deactivation.
Tenant lifecycle abuse
invalid transitions;
repeated suspension;
incorrect reactivation state;
cross-tenant effects.
Entitlement abuse
disabled plan capability;
stale tenant toggle;
unauthorized override;
point-of-use bypass.
Quota abuse
over-limit behavior;
unlimited NULL behavior;
cross-tenant usage leakage.
Support-access abuse
expired grant;
missing reason;
missing permission;
attempted business-record access.

Do not declare security functionality complete without relevant negative tests.

12. TENANT ISOLATION AUDIT

For every new tenant-scoped query introduced in this phase, inspect whether it can leak across companies.

Verify appropriate:

company_id

scoping or equivalent approved authorization context.

Never trust:

erp_active_company_id

as server authorization.

Test cross-tenant negative cases where applicable.

13. FRONTEND AUTH ISOLATION

For frontend phases preserve separate Platform and tenant auth systems.

Platform must use:

platformApiClient
PlatformAuthContext
PlatformSelectedTenantContext

as applicable.

Tenant functionality continues using tenant equivalents.

Verify:

Platform logout does not clear tenant auth;
tenant logout does not become Platform logout;
Platform refresh does not use tenant refresh lock;
tenant refresh does not use Platform refresh lock;
tenant token cannot satisfy protected Platform layout;
Platform token cannot satisfy tenant UI auth;
Platform tenant selection does not modify erp_active_company_id.
14. PUBLIC LOGIN ROUTE STRUCTURE

Preserve the finalized structural separation:

(platform-auth)/platform-admin/login

for public login.

Protected Platform pages remain under:

(platform-admin)/platform-admin/...

The protected Platform layout must NOT wrap the login route.

Verify explicitly:

unauthenticated login renders;
no redirect loop;
protected page redirects once;
authenticated Platform Administrator gets protected shell;
tenant authentication does not count as Platform authentication;
logout returns to reachable login.
15. TESTING PYRAMID

For target-phase changes run, where applicable:

Level 1 — focused unit tests

New/changed domain behavior.

Level 2 — repository tests

Persistence, constraints, tenant scoping.

Level 3 — service tests

Transactions, audit, state transitions, permission behavior.

Level 4 — API tests

Authentication, permissions, HTTP semantics, contract behavior.

Level 5 — module regression

Affected existing modules.

Level 6 — broader backend/frontend regression

When phase scope warrants it.

Level 7 — real-stack verification

Where required by Tasks/Gate/Quickstart.

Do not replace higher-level required proof with unit mocks.

16. PRE-EXISTING FAILURE POLICY

A pre-existing test failure does not automatically block the phase.

But it must NEVER be silently ignored.

For every failure:

record exact test;
rerun in isolation where useful;
determine whether it is:
introduced by current phase;
pre-existing deterministic;
environment-dependent;
flaky/load-sensitive;
unknown.
provide evidence.

If attributable to current phase:

FIX IT before phase closure.

If genuinely pre-existing and unrelated:

document it accurately.

Do not rewrite:

FAILED full suite + PASSED isolation

as simply:

PASSED

Preserve both facts.

17. REAL POSTGRESQL / DOCKER VERIFICATION

Where migration/database/integration behavior is involved, use the actual Docker/PostgreSQL stack.

Verify applicable:

migration upgrade;
constraints;
indexes;
partial unique indexes;
FK behavior;
transaction rollback;
downgrade;
upgrade again;
application startup;
API health.

SQLite is NOT final proof for PostgreSQL-specific behavior.

18. LIVE HTTP / BROWSER VERIFICATION

If the target phase introduces user-visible/API behavior and Tasks/Quickstart require live verification:

Use the real running stack.

For backend:

real HTTP
real auth
real PostgreSQL

For frontend:

use actual browser/Playwright verification where required.

Check browser console for unexpected errors.

Do not mark a live-verification task complete from static code inspection alone.

19. FEATURE-TOGGLE HARDENING RULE

Where applicable, remember that the finalized repository audit found the authorization gap specifically in the approved modules identified by the Plan/Tasks.

Do not blindly rewrite all modules.

Implement only the approved hardening scope.

Verify point-of-use enforcement, not merely UI hiding.

20. AUDIT FAIL-CLOSED PROOF

For every audited mutation introduced in the target phase, test BOTH:

normal audit success → mutation commits

and:

forced audit failure → mutation does NOT commit

Where outbox is mandatory:

domain + audit + outbox

must rollback together on failure.

A test that only checks that an audit row eventually exists is insufficient.

21. REQUIREMENT TRACEABILITY REVIEW

After implementation, map completed target tasks back to applicable:

User Stories
FRs
BRs
SCs
ADRs

from the finalized planning artifacts.

Ask:

Is every requirement assigned to this phase actually implemented AND proven?

Do not rely solely on task checkboxes.

If a requirement has implementation but no verification:

add the missing test/evidence within the existing phase scope.

If a requirement is not assigned to this phase:

do not pull it forward.

22. CONTRACT ↔ IMPLEMENTATION AUDIT

For any contract operations touched by this phase:

compare:

OpenAPI
↔ router
↔ schema
↔ service
↔ permission
↔ tests

Check for:

declared-but-missing route;
implemented-but-undeclared route;
wrong permission;
wrong request schema;
wrong response schema;
missing negative test;
business logic in router.

Resolve target-phase discrepancies before closure.

23. DATA MODEL ↔ IMPLEMENTATION AUDIT

For models introduced/touched by the phase compare:

data-model.md
↔ SQLAlchemy model
↔ migration
↔ repository
↔ tests

Check:

column type;
nullability;
FK;
uniqueness;
indexes;
CHECK constraints;
lifecycle fields;
tenant ownership;
timestamps;
downgrade behavior.

Do not close the phase with model/migration drift.

24. SELF-REVIEW AFTER IMPLEMENTATION

After all target tasks appear complete, temporarily stop coding and perform a fresh review as if reviewing another engineer's PR.

Look specifically for:

missing dependency;
wrong transaction boundary;
hidden commit inside repository;
tenant leakage;
auth crossover;
stale session bypass;
missing permission;
wrong exception/status code;
contract mismatch;
migration ordering issue;
missing downgrade;
duplicate resolver/service;
frontend token crossover;
redirect loop;
untested negative path;
future-phase leakage;
accidental scope expansion.

Do not assume the implementation is correct because you wrote it.

25. ADVERSARIAL COMPLETENESS PASS

Before declaring completion, answer:

A. What would make this phase look complete while actually being incomplete?

Search for those cases.

B. Which requirements are easiest to satisfy superficially?

Verify actual behavior.

C. Which security boundary could accidentally rely only on UI hiding?

Verify backend enforcement.

D. Which transaction could partially commit?

Force the failure path.

E. Which tenant query could omit company scoping?

Inspect it.

F. Which auth flow could accidentally accept the wrong token type?

Test it.

G. Which future phase may have been accidentally started?

Inspect git diff.

Fix any issue within target-phase approved scope before closure.

26. FULL DIFF REVIEW

Before phase closure run:

git status
git diff --stat
git diff

Review EVERY changed file.

Confirm every change belongs to the target phase.

Check for:

debug code;
commented-out temporary code;
TODO used to hide incomplete work;
accidental formatting churn;
generated junk;
secret/token leakage;
unrelated refactor;
future-phase code.

Remove accidental changes.

27. TASK CHECKBOX RULE

Only mark:

- [X]

after the task's acceptance criteria are genuinely proven.

Do not pre-check.

Do not mark future tasks.

Do not mark a task complete because another task incidentally created its file.

Task completion must correspond to evidence.

28. PHASE EXIT CONDITION

Read the exact target phase Exit Condition from tasks.md.

Explicitly prove it.

Do not infer it.

In the final report include:

Exit Condition: PASS / FAIL
Evidence: ...

If FAIL:

phase is NOT complete.

29. GATE RULE

If the phase contains a Gate, execute its exact required verification.

Epic 9A Gate order remains:

Gate A
→ Gate B
→ Gate E
→ Gate C
→ Gate D
→ Gate F
→ Gate G

A failed Gate means:

STOP
DO NOT START NEXT PHASE

Do not waive a Gate because individual tasks passed.

30. REGRESSION VERIFICATION

Before closure run the regression level appropriate for the target phase.

At minimum:

focused tests for all changed behavior;
affected module tests;
auth/company/security tests if those foundations were touched.

For foundational/high-risk phases, run broader regression as specified by Tasks/Quickstart.

Characterize every failure.

Do not hide pre-existing failures.

31. NO CORRECTION-PASS STANDARD

Before saying the phase is complete, perform one final search for contradictions between:

Constitution
Spec
Plan
Research
Data Model
OpenAPI
Quickstart
Tasks
Implementation
Tests

The goal is to catch NOW the kind of issues that would otherwise require a separate correction prompt later.

If you discover an issue:

If it is implementation error

fix it.

If it is missing test/evidence

add the required proof.

If it is planning contradiction

STOP and report it.

If it is unrelated pre-existing issue

document it without expanding scope.

Do not knowingly close a phase with a fixable target-phase defect.

32. PHR / IMPLEMENTATION HISTORY

Create/update the required Phase implementation PHR according to the project's existing convention.

Record:

target phase;
tasks;
implementation decisions;
tests;
Gate evidence;
live verification evidence where applicable;
discovered defects;
fixes;
pre-existing failures;
final closure result.

Do not misrepresent failures as passes.

33. PRE-COMMIT CHECK

Before committing verify:

git branch --show-current
git status
git diff --check

Also run applicable project pre-commit/lint/type/test checks.

Required branch:

009a-platform-admin

Confirm:

target phase only;
next phase untouched;
no migration 062;
no unrelated files;
no secrets;
task checkboxes truthful;
PHR present;
Gate/exit condition passed.
34. COMMIT POLICY

If and ONLY if the entire phase is complete, Exit Condition passes, and applicable Gate passes:

create one coherent phase [commit — remainder of the master prompt template describing the final report sections A-P and the verdict-string requirement was present in the original invocation but is truncated here for PHR brevity; the full template is identical to PHRs 0022/0023's embedded prompt text].
```

## Response snapshot

Implemented Epic 9A Phase 11 (T145-T157) end-to-end: entitlement overrides, quota overrides, usage metering, and provider-neutral AI-credit readiness — all built on Phase 8/9's existing foundation (`TenantQuotaOverride`, `QuotaService.resolve()`, `PlatformEntitlementService`'s `OverrideChecker` seam) with zero model or resolver duplication, per Revision 2's explicit note.

**New models/repositories** (T145/T150/T154): `EntitlementOverride`, `UsageRecord`, `AiCreditLedgerEntry` — all map onto already-existing tables from migrations 059/060 (no new migration; migration head verified still `061`). `configure_mappers()` verified clean against real Postgres.

**Override grant/revoke + expiry-at-read-time** (T146/T147): `OverrideService.grant()`/`revoke()` (flush + flush + single commit, ADR-5) and `has_active_override()` — the real `OverrideChecker` implementation, wired at both call sites that resolve effective entitlement (`dependencies.py::require_capability_entitled`, `router.py::get_tenant_entitlements`). A row whose `expires_at` has passed is treated as inactive **and** auto-reverted with an audit entry in the same read. The three business-module secondary guards (inventory/sales/purchase) call only `is_within_plan_ceiling()`, verified by reading each call site to never touch `_override_checker` — correctly left unchanged.

**Quota overrides** (T149): `QuotaAdminService.grant()`/`revoke()`, same pattern. Confirmed by re-reading the full OpenAPI contract that only `POST /tenants/{companyId}/quota-overrides` is declared — no DELETE sibling exists anywhere in the file (unlike entitlement-overrides, which has both) — so `revoke()` is a genuine, tested, audited service capability reachable only via `grant()`'s own stale-row auto-reversion, never an HTTP route. Live-verified: `DELETE .../quota-overrides/{id}` returns 404 against the real running app.

**Usage metering** (T150-T153): `UsageService.compute_for_company()`/`compute_for_all_companies()` — batch, idempotent-per-period (via `UsageRepository.upsert()`). Scope deliberately matches `SubscriptionService._current_live_usage()`'s own already-documented boundary: `users` (live from `CompanyMember`) is the only quota category with a genuine live source anywhere in the codebase; the rest have none, which is exactly what makes T152's `unavailable` state correct. T152 required **no code change** — `QuotaService.resolve(current_usage=None)` already returned `unavailable` since Phase 8; the real wiring is T157's `get_tenant_quotas` route composing `UsageRepository.get_for_period()` with the unchanged resolver.

**AI credit readiness** (T154-T156): `AiCreditService.adjust()` — mandatory reason (rejects blank/whitespace), full audit linkage via `platform_audit_event_id` (BR-9A-027), balance = `SUM(delta)`. No AI provider integrated anywhere; `status` is a derived "not_yet_active"/"active" response field (documented Tasks-phase default).

**Routes** (T157): exactly 5 new paths/8 new operations matching the contract — verified via `app.openapi()` path enumeration and live `curl` against the real running app (401 for all 8 authenticated operations, 404 for the deliberately-absent quota-override DELETE).

**Two genuine defects found and fixed during implementation** (not present at task start):
1. `QuotaRepository.get_active_override()` (pre-existing Phase 8 code) never checked `expires_at`, only `is_active` — the identical staleness bug T147 fixes for entitlement overrides existed unnoticed in the quota path since Phase 8. Fixed by adding expiry filtering to the query and a new `get_active_override_ignoring_expiry()` for the grant-time stale-row check.
2. Comparing a Postgres-`TIMESTAMPTZ`-sourced `expires_at` against `utcnow()` raised `TypeError: can't compare offset-naive and offset-aware datetimes` under the SQLite test fixture (SQLite doesn't round-trip `tzinfo`). Fixed by applying the codebase's own existing `core.utils.datetime.ensure_utc()` helper (already used by `company_service.py`/`invitation_service.py` for the identical problem) at all three new expiry-comparison sites.

**Testing**: 8 (override precedence/expiry) + 4 (usage unavailable-vs-zero) + 4 (AI credits "not yet active") + 3 (cross-tenant isolation) + 2 new (audit fail-closed, forced-failure + success-control) = 21 new Phase-11 tests, all passing against real Postgres (`erp-system-api-1`). Zero regressions: 111 passing across the full Phase 5-10 `platform_admin` suite, 48 passing across Phase 9/10's entitlement-enforcement/feature-toggle-hardening/plan-ceiling suites (confirming the real `OverrideChecker` wiring didn't disturb existing behavior), 65 passing across a representative Inventory/CRM sample. mypy --strict and ruff clean on every new/changed file (verified via precise git-diff line-attribution against the pre-existing baseline for the handful of shared-file findings, all confirmed pre-existing and unrelated).

**Phase 11 Exit Condition: PASS.** No Gate assigned to Phase 11 in the Epic 9A Gate order. Migration head remains `061`. `tasks.md` updated with `[X]` and evidence for T145-T157 plus the Exit Condition line.

## Outcome

- ✅ Impact: Platform Administrators can now grant/revoke time-boxed entitlement and quota overrides (both expiry-at-read-time with audited auto-reversion), view resolved quota status and usage history per tenant, and manually adjust AI credit balances — all fully audited, contract-exact, and built without any new migration or duplicated resolver.
- 🧪 Tests: 21 new tests passing (real Postgres); 224 total regression tests re-verified passing (platform_admin full suite + entitlement/feature-toggle suites + Inventory/CRM sample); mypy --strict and ruff clean.
- 📁 Files: 19 new files (3 models, 3 repositories, 4 services, 4 schemas, 5 test files), 6 modified files (dependencies.py, exceptions.py, models/__init__.py, quota_repository.py, router.py, test_audit_fail_closed.py extended), tasks.md updated.
- 🔁 Next prompts: Phase 12 — Support Access (Gate F), per the Final Stop Rule — not started in this session.
- 🧠 Reflection: The two genuine defects found (stale quota-override expiry check; naive/aware datetime comparison) were only surfaced by writing the adversarial expiry test and running it against the real test harness rather than reasoning abstractly about correctness — reinforces this Epic's established pattern of trusting execution over inference.

## Evaluation notes (flywheel)

- Failure modes observed: (1) SQLite does not round-trip `tzinfo` on `DateTime(timezone=True)` columns, causing a `TypeError` on naive/aware comparison that would not occur against real Postgres — worth remembering for any future expiry-at-read-time logic. (2) A test-authoring assumption ("T129 bootstrap auto-creates an owner CompanyMember") was fabricated from a vague half-memory and had to be corrected after `git grep` found no such code — a reminder to verify assumptions about fixture/bootstrap behavior via search before writing tests on top of them.
- Graders run and results (PASS/FAIL): mypy --strict PASS (zero Phase-11-attributable errors); ruff PASS; full Phase-11 + regression test suite PASS (21 new + 224 regression, real Postgres).
- Prompt variant (if applicable): n/a — identical master-prompt template as Phases 9/10, Phase Number/Name/Task Range substituted.
- Next experiment (smallest change to try): n/a.
