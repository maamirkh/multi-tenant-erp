---
id: 0012
title: T068 dependency and T076 auth semantics
stage: tasks
date: 2026-08-19
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.tasks
labels: ["platform-admin", "tasks", "correction", "rbac", "auth-semantics"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/009a-platform-admin/tasks.md
 - history/prompts/009a-platform-admin/0012-t068-dependency-and-t076-auth-semantics.tasks.prompt.md
tests:
 - none (task-planning correction; no code, migrations, or tests written)
---

## Prompt

We have completed the final review of Epic 9A `tasks.md`. The task plan is now
implementation-ready. Only TWO small semantic corrections remain. Please update
`tasks.md` surgically.

**FIX 1 — T068 missing dependency on T066.** T068 implements
`PATCH /administrators/{adminId}` whose acceptance already states it returns
`LastPlatformOwnerError` (409) when deactivating the final owner — a behaviour
implemented by T066 (last-Platform-Owner protection). T066 was absent from
T068's `Deps`. Required: `Deps: T064, T054, T041, T053, T066`.

**FIX 2 — T076 mischaracterises the 3 public `/auth/*` routes.** The acceptance
wording implied all 9 Phase-5 operations carry a required Platform RBAC
permission and must pass the "required permission succeeds / adjacent permission
fails" test. That is semantically incorrect: `/auth/login`, `/auth/refresh` and
`/auth/logout` are public authentication operations with no `x-permission`.
Required split — (i) 3 public auth operations: verify authentication/session/
token-boundary semantics and tenant/Platform authentication isolation, with no
RBAC permission asserted; (ii) 6 permission-guarded Administrator/RBAC
operations: required-permission-succeeds / adjacent-permission-fails /
unauthenticated-rejected / tenant-token-rejected. Preserve the constraint that
T076 tests ONLY routes existing at end of Phase 5 — no Phase 6+ routes.

Plus 15 consistency checks, a strict scope rule (no renumber, no reorder, no
regenerate, no new tasks; count stays 225; phases stay 17), and an 8-item final
report ending in the verdict "READY FOR /sp.implement" only if all checks pass.
Full verbatim text in the conversation transcript for this turn.

## Response snapshot

Two surgical edits, nothing else. No task added, removed, renumbered or reordered.

**FIX 1** — T068 `Deps` changed from `T064, T054, T041, T053` to
`T064, T054, T041, T053, T066`. T066 sits in the same phase (Phase 5) and is
numerically lower, so the edit cannot introduce a forward dependency or cycle —
confirmed by the scripted audit rather than by inspection.

**FIX 2** — T076's single-category acceptance was replaced with two explicitly
separated categories, keeping the "9 operations", "Phase-5 surface only" and
"T206 completeness" clauses intact:

- **3 public authentication operations** — annotated "no `x-permission` in the
  contract". Verifies real auth semantics instead of a permission matrix: login
  issues a `platform_access`/`platform_refresh` pair only for an **active**
  `PlatformAdministrator` and otherwise returns a generic invalid-credentials
  response; refresh rotates and rejects a revoked session or deactivated
  administrator; logout revokes the session. Plus the bidirectional
  tenant/Platform isolation boundary — a tenant token is never accepted as a
  platform session, and a `platform_access` token is never accepted by
  `get_current_user()`. Closes with "**No Platform RBAC permission is required
  or asserted for these three.**"
- **6 permission-guarded Administrator/RBAC operations** (3 from T068, 3 from
  T069) — required-permission-succeeds / adjacent-permission-fails /
  unauthenticated-rejected / tenant-token-rejected.

The closing clause now records the split (3 public + 6 guarded) explicitly so
T206 can prove completeness against the full 33-operation contract as
**30 guarded + 3 public** — which is exactly how T206 already states its own
scope, so the two tasks now reconcile arithmetically.

**Machine-verified after the edits**: 225 tasks, IDs `T001`–`T225` sequential
and unique; 17 phases; zero dependencies on non-existent tasks; zero
forward/order violations; DFS three-colour cycle detection reports acyclic; all
seven gates (A `T031`, B `T077`, E `T081`, C `T102`, D `T137`, F `T166`,
G `T225`) depend only on tasks in their own phase or earlier. Summary-table `[P]`
figure (85) matches the actual count of `[P]`-marked task lines. The `062` scan
returns only prohibition assertions (T029, T141, the migration-sequence rules)
plus the unrelated `T062` task ID and `FR-9A-062` requirement ID. Out-of-scope
scan clean — the only hits are inside the Out of Scope section itself.

## Outcome

- ✅ Impact: removed the last two semantic defects. T068's stated 409 behaviour
  now has a real dependency edge to the task that implements it, and Gate B no
  longer asks an implementer to invent a Platform permission for three endpoints
  that deliberately have none — which would have produced either a wrong test or
  a wrong route.
- 🧪 Tests: N/A (planning artifact). Test *semantics* improved: T076 now
  specifies genuine authentication-boundary assertions for the public routes
  instead of an inapplicable permission matrix.
- 📁 Files: `specs/009a-platform-admin/tasks.md` (225 tasks / 17 phases,
  unchanged counts) + this PHR. `constitution.md`, `spec.md`, `plan.md`,
  `research.md`, `data-model.md`, `contracts/`, `quickstart.md` untouched.
- 🔁 Next prompts: `/sp.implement` (not started, per instruction).
- 🧠 Reflection: both defects came from treating a route table as homogeneous.
  A missing `Deps` edge and an over-broad test assertion are the same mistake
  seen from two sides — the plan knew `/auth/*` was public (the contract has
  `security: []`) and knew T066 owned last-owner protection, but the task text
  generalised across the whole group. Worth checking, wherever a task enumerates
  "N operations", whether all N genuinely share the property being asserted.

## Evaluation notes (flywheel)

- Failure modes observed: (a) an acceptance criterion asserting behaviour whose
  implementing task was not in `Deps` — the assertion and the edge are written in
  different places and drift independently; (b) a group-level assertion applied
  to a heterogeneous group. Neither is catchable by a dependency-graph script;
  both needed the contract read as authority.
- Graders run and results (PASS/FAIL): task count PASS (225); phase count PASS
  (17); sequential/unique IDs PASS; non-existent dep references PASS (0);
  forward-dependency scan PASS (0); cycle detection PASS (acyclic); gate
  executability PASS (7/7); `[P]` reconciliation PASS (85 = 85); migration-062
  scan PASS (prohibitions only); out-of-scope leakage PASS; T069 three-operation
  invariant PASS; T177/T206 operation-count reconciliation PASS (33 = 30 + 3).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
