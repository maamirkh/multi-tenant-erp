---
id: 0011
title: Platform API routes and login route fix
stage: tasks
date: 2026-08-19
surface: agent
model: claude-opus-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.tasks
labels: ["platform-admin", "tasks", "correction", "api-routes", "nextjs-routing"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/009a-platform-admin/tasks.md
 - history/prompts/009a-platform-admin/0011-platform-api-routes-and-login-route-fix.tasks.prompt.md
tests:
 - none (task-planning correction; no code, migrations, or tests written)
---

## Prompt

# Epic 9A — `/sp.tasks` — Final Targeted Correction Pass

[Brief limited to two implementation-readiness blockers, with strict do-not-modify constraints on constitution/spec/plan/research/data-model/contracts/quickstart, a list of ~30 previous corrections to preserve, a task-ID/dependency policy, a global dependency re-check, traceability and completeness-audit requirements, and a 24-item final report.
**Blocker 1** — explicit Platform Administrator / RBAC backend API route tasks are missing. Services, `require_platform_permission`, auth routes, frontend Administrator/Roles pages, Gate B and contract conformance all exist, but no task implements the HTTP routes those depend on. The OpenAPI contract is authoritative for the exact surface; do not invent CRUD. Route tasks must specify router file, endpoint/method, permission, schemas, service dependency, audit requirement, error behaviour, pagination, contract traceability; must delegate to services; mutations fail-closed audited per ADR-5; deactivation must call the completed T054 session-revoking path; last-owner and self-escalation protections preserved; Gate B must then genuinely test the Phase-5 surface without reintroducing the old cycle; frontend pages must depend on API tasks; contract conformance must include them.
**Blocker 2** — the Platform login page was planned inside the same `(platform-admin)` route group whose layout redirects unauthenticated users, creating a `login → guard → login` App Router loop. Required a route/layout structure that structurally keeps `/platform-admin/login` outside the protected layout, using repository conventions, no middleware, no collision — plus explicit frontend tests A–E (no-loop login, protected redirect, authenticated render, tenant-auth-doesn't-count, logout).
Full verbatim text in the conversation transcript for this turn.]

## Response snapshot

**Contract read as authority first.** Parsed `platform-admin-v1.yaml`: **28 paths / 33 operations**. The Administrator/RBAC surface is exactly six operations — `GET/POST /administrators`, `PATCH /administrators/{adminId}`, `GET/POST /roles`, `POST /administrators/{adminId}/roles`. Confirmed by grep that **no existing task implemented any of them** (only an incidental mention in a bootstrap-abuse test). Notably the contract declares **no** `GET /permissions` catalogue and **no** `DELETE` role-assignment route, so both were explicitly listed as "not implemented — inventing CRUD is forbidden; would require a contract change first" rather than silently added.

**Blocker 2 resolved from repository precedent rather than invention**: `frontend/src/app/` already contains `(auth)/login` as a public group sibling to the redirecting `(protected)/` group. Mirrored exactly — login moves to `(platform-auth)/platform-admin/login/page.tsx`, protected pages stay under `(platform-admin)/platform-admin/`, with the guard layout at `(platform-admin)/platform-admin/layout.tsx`. Route groups are stripped from URLs so both contribute to `/platform-admin/*` with no collision, and the guard structurally cannot wrap login. T190's dependency was also changed from T188 (the guard) to T183 (`PlatformAuthContext`) — the login page must not depend on the guard it is exempt from.

**Mechanical renumber before content edits.** Rather than hand-editing ~1500 lines, ran a descending-order regex renumber to open exactly three slots (T068, T069, T205), verified the result had precisely those three gaps and zero duplicates, then inserted the new tasks. This avoided the class of stale-ID error that hand-renumbering invites.

Added **T068** (Administrator routes), **T069** (RBAC routes), **T205** (route-guard tests A–E). Updated T076 Gate B test to depend on T068/T069 and to cover the 9 operations genuinely existing at end of Phase 5; T177 contract conformance and T206 exhaustive matrix to include them; T198/T199 frontend pages to depend on the API tasks plus `platformApiClient` (T179) with explicit "never a Python service" acceptance; T188 to document the chosen route structure inline; summary table, traceability matrix, hard-ordering rules, parallel examples and completeness audit throughout.

**Machine-verified the result**: 225 tasks sequential and unique; zero dependencies on non-existent tasks; **zero** forward/order violations; **zero** cycles; all seven gates depend only on their own phase or earlier. Also re-confirmed every prior correction survived (T054 split, T099 3-way atomicity, T105 quota foundation, RoleSeedService, `Session.created_at`, migration preflight, `PlatformSelectedTenantContext`) and that the single remaining `062` string in the file is T029's *prohibition* assertion.

## Outcome

- ✅ Impact: closed the last two implementation-readiness blockers. The frontend Administrator/Roles pages and Gate B now rest on real, contract-traceable HTTP route tasks instead of an implied surface, and the Platform login page can no longer produce an App Router redirect loop. All 33 contract operations now have explicit implementation coverage.
- 🧪 Tests: N/A (planning artifact). Test *coverage* grew: 6 newly-covered operations in Gate B's scope and the exhaustive matrix, plus five explicit route-guard cases including the tenant-auth-doesn't-count case that complements the backend token-boundary proof.
- 📁 Files: `specs/009a-platform-admin/tasks.md` (225 tasks / 17 phases) + this PHR. All seven protected planning artifacts untouched.
- 🔁 Next prompts: `/sp.implement` (not started, per instruction).
- 🧠 Reflection: both blockers were "the plan described a thing without creating it" — the API surface was referenced by four different tasks yet built by none, and the login page's acceptance text *claimed* it was outside the guarded shell while the file path put it inside. The generalisable check is: for anything a task's acceptance criteria assert, is there a task that actually produces it, and does the stated file path make the assertion structurally true?

## Evaluation notes (flywheel)

- Failure modes observed: (a) an implied-but-unbuilt API surface passed three prior review passes because every *consumer* existed — reviewing consumers is not the same as reviewing producers; (b) an acceptance clause ("outside the guarded shell") contradicted its own `Files:` path, which no prose review caught. Both argue for structural/mechanical checks over re-reading.
- Graders run and results (PASS/FAIL): unique+sequential IDs PASS (225); non-existent dep references PASS (0); forward-dependency scan PASS (0); cycle detection PASS (acyclic); gate executability PASS (7/7); out-of-range ID scan PASS; migration-062 scan PASS (sole hit is the prohibition); out-of-scope leakage PASS; prior-correction preservation PASS (7/7 spot-checked).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
