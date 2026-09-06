---
id: 0023
title: Phase 10 — Existing Feature-Toggle Mutation Hardening
stage: green
date: 2026-08-22
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.implement
labels: ["epic-9a", "phase-10", "feature-toggle", "rbac-hardening"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/inventory/router.py
  - backend/modules/inventory/constants.py
  - backend/modules/inventory/exceptions.py
  - backend/modules/inventory/services/permission_check.py
  - backend/modules/sales/router.py
  - backend/modules/sales/constants.py
  - backend/modules/sales/services/permission_check.py
  - backend/modules/purchase/router.py
  - backend/modules/purchase/constants.py
  - backend/modules/purchase/services/permission_check.py
  - backend/modules/users_roles/constants.py
  - backend/modules/users_roles/services/role_seed_service.py
  - backend/modules/users_roles/backfill_feature_toggle_permissions.py
  - backend/modules/platform_admin/services/entitlement_service.py
  - backend/tests/security/modules/platform_admin/test_feature_toggle_hardening.py
  - backend/tests/unit/modules/platform_admin/test_plan_ceiling_secondary_guard.py
  - backend/tests/unit/modules/users_roles/test_feature_toggle_permission_backfill.py
  - specs/009a-platform-admin/tasks.md
tests:
  - backend/tests/security/modules/platform_admin/test_feature_toggle_hardening.py (16 passed)
  - backend/tests/unit/modules/platform_admin/test_plan_ceiling_secondary_guard.py (4 passed)
  - backend/tests/unit/modules/users_roles/test_feature_toggle_permission_backfill.py (2 passed)
  - backend/tests/e2e/purchase/, tests/integration/api/v1/purchase/, tests/integration/purchase/ (65 passed, regression)
  - backend/tests/security/sales/, tests/integration/api/v1/sales/test_phase0_api.py (116 passed, regression)
  - real production database: python -m modules.users_roles.backfill_feature_toggle_permissions (26 companies, verified via direct SQL, re-run idempotent)
  - ruff check: all changed/new files clean
  - mypy --strict: zero new errors attributable to Phase 10 (2 found in new file, fixed; all remaining pre-existing in untouched code)
---

## Prompt

```text
# Epic 9A — Platform Administration / Super Admin
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT


Implement, verify, audit, and close ONLY the following phase of Epic 9A.


## TARGET PHASE


**Phase Number:** `10`
**Phase Name:** `Existing Feature-Toggle Mutation Hardening`
**Task Range:** `<T138 to T144>`


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

create one coherent phase completion commit.

Preferred:

feat(009a): complete Phase <PHASE_NUMBER> — <PHASE_NAME>

For verification-only phases:

chore(009a): complete Phase <PHASE_NUMBER> — <PHASE_NAME>

or appropriate test(009a):.

Do NOT:

amend previous unrelated commits;
squash prior history;
force push;
automatically push unless explicitly instructed.

If phase is incomplete:

DO NOT create a misleading completion commit.

35. POST-COMMIT VERIFICATION

After commit run:

git branch --show-current
git status
git log -1 --oneline

Verify:

branch = 009a-platform-admin
working tree = clean

Also verify the commit contains only legitimate target-phase files.

Do NOT start the next phase.

36. REQUIRED FINAL REPORT

Your final response must contain ALL of the following.

A. Phase
Phase number
Phase name
Task range
B. Task completion

For each target task:

Task ID | COMPLETE/INCOMPLETE | evidence
C. Files
created
modified
deleted
D. Database

If applicable:

migrations created/modified
upgrade result
downgrade result
PostgreSQL verification
confirmation no migration 062 exists
E. Tests

Report exact counts where available:

passed
failed
skipped
warnings

Do not summarize a non-zero-failure suite as simply "green."

F. Security

Report relevant negative-path results.

G. Tenant isolation

Report applicable cross-tenant verification.

H. Contract

Report applicable OpenAPI ↔ implementation verification.

I. Gate
Gate: N/A / PASS / FAIL

with evidence.

J. Exit Condition
PASS / FAIL

with evidence.

K. Defects discovered

List every real defect discovered during implementation/self-review.

For each:

Defect
Cause
Fix
Verification
L. Pre-existing failures

List separately from Epic 9A regressions.

M. Self-audit

Explicitly report results of:

architecture review;
dependency review;
security review;
tenant-isolation review;
transaction review;
contract review;
future-phase leakage review.
N. Git
commit hash
active branch
git status
O. Scope confirmation

Explicitly confirm:

Next phase NOT started.
No unauthorized architecture change.
No migration 062.
No unrelated scope expansion.
P. Final verdict

Use EXACTLY one:

PHASE <PHASE_NUMBER> COMPLETE — READY FOR NEXT PHASE

or:

PHASE <PHASE_NUMBER> NOT COMPLETE — BLOCKED

If blocked, state the exact blocker.

37. FINAL STOP RULE

After the phase is:

implemented
+ tested
+ audited
+ Gate-verified where applicable
+ committed
+ post-commit verified

STOP.

Do NOT automatically begin the next phase.

Do NOT perform speculative cleanup.

Do NOT reopen completed planning decisions.

Wait for Product Owner instruction.
```

## Response snapshot

Implemented Phase 10 (T138-T144): hardened the three confirmed-vulnerable
modules' (Inventory, Sales, Purchase) `PUT .../feature-flags/{flag_key}`
endpoints, each now requiring a new `<module>.settings.manage` permission
(replicating Accounting's existing `user_has_accounting_permission`
pattern exactly — a new `permission_check.py` per module) plus a
secondary entitlement-ceiling guard (new
`PlatformEntitlementService.is_within_plan_ceiling()`, FR-9A-185).
Accounting and CRM sources untouched (regression-proven). The three new
permission codes were added to `users_roles/constants.py` and backfilled
onto every already-existing company's owner/admin roles via a new
`RoleSeedService` method plus a standalone operator script (mirroring
Phase 9's `rollout_service.py` convention) — live-run against the real
production database (26 companies, verified via direct SQL).

**Two real findings surfaced during implementation, both investigated
directly rather than assumed away**: (1) a test-fixture bug in T143's own
CRM regression test (the "viewer" test user was, by fixture construction,
also `company.owner_id`, trivially passing `require_admin_or_above()`'s
owner bypass regardless of role — fixed with a genuinely-separate-owner
fixture); (2) T144's secondary guard is, for these three modules,
unreachable-for-denial in production — verified by inspecting the actual
HTTP response body from a raw debug call, which carried Phase 9's
*primary* mount-level gate's error shape, not the secondary guard's own.
Confirmed via code reasoning this is structural (both gates check the
identical module-grain capability) and not a contradiction of plan.md
(which itself says removing the secondary guard "would not create a
runtime bypass"). Documented precisely in both router comments and two
test files' docstrings; added a direct unit test
(`test_plan_ceiling_secondary_guard.py`) proving the guard method's own
logic correctly, since the HTTP path alone cannot demonstrate it
independently of the primary gate.

## Outcome

- ✅ Impact: Phase 10 complete. The FR-9A-183/184/185 authorization gap
  on Inventory/Sales/Purchase's feature-toggle mutation endpoints is
  closed; existing tenant admins retain access immediately post-deploy
  (backfill live-verified); Accounting/CRM's already-correct gates
  proven unchanged.
- 🧪 Tests: 22 new Phase-10 tests green (16 hardening + 4 secondary-guard
  unit + 2 backfill unit), all against real PostgreSQL. Regression: 65
  purchase tests + 116 sales tests green (every pre-existing test file
  found to touch the modified endpoints). `ruff`/`mypy` clean on all
  new/changed files (2 genuine mypy findings in the new backfill script
  fixed; all other findings pre-existing in untouched code).
- 📁 Files: 3 new `permission_check.py` files (one per hardened module),
  1 new operator backfill script, 3 new test files, 10 modified files
  (3 routers, 3 module `constants.py`, 1 `exceptions.py`, `users_roles/
  constants.py`, `role_seed_service.py`, `entitlement_service.py`).
  Zero changes to Accounting or CRM.
- 🔁 Next prompts: Phase 11 (Overrides, Quota Administration, Usage &
  AI-Credit Readiness) — not started, per this phase's strict scope
  boundary.
- 🧠 Reflection: The CRM fixture bug and the secondary-guard reachability
  finding were both caught only because every claimed-passing test was
  independently re-verified against a raw response body / a fresh
  reasoning pass, not because either was anticipated in advance — the
  same "verify the actual mechanism, don't trust the assertion passing"
  discipline that caught Phase 9's two real defects.

## Evaluation notes (flywheel)

- Failure modes observed: (1) a test fixture that accidentally validated
  a different code path than intended (company.owner_id coincidence);
  (2) new code that is logically correct and match the plan's letter
  exactly, yet practically unreachable given an earlier phase's own
  architecture — caught only by inspecting the literal HTTP response
  body of a raw debug call, not by the passing test suite alone.
- Graders run and results (PASS/FAIL): Exit Condition — PASS (see
  tasks.md T138-T144 Result entries and Phase 10 Exit Condition line).
- Prompt variant (if applicable): n/a — master phase-closure prompt used
  as supplied, no variant.
- Next experiment (smallest change to try): n/a.
