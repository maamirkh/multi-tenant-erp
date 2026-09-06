---
id: 0010
title: Tasks dependency correction pass
stage: tasks
date: 2026-08-19
surface: agent
model: claude-opus-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.tasks
labels: ["platform-admin", "tasks", "correction", "dependency-graph"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/009a-platform-admin/tasks.md
 - history/prompts/009a-platform-admin/0010-tasks-dependency-correction-pass.tasks.prompt.md
tests:
 - none (task-planning correction; no code, migrations, or tests written)
---

## Prompt

Perform a TARGETED CORRECTION PASS on the existing Epic 9A `tasks.md`.

[Brief identifying six dependency/order defects with required corrections, plus a global dependency audit, gate audit, traceability/document-consistency requirements, and a list of ~30 non-negotiable architectural guardrails to preserve.
**Defect 1** — T037 `PlatformAdministratorService` (Phase 3) depends on T050 `PlatformSessionRepository` (Phase 4): invalid forward dependency/phase cycle. Split so the domain foundation stays in Phase 3 and session-aware deactivation moves to Phase 4; preserve BR-9A-011 without weakening session invalidation.
**Defect 2** — T068 (Gate B permission matrix) depends on "every router task in Phases 7–13" while T070 (Gate B) blocks Phase 7: `Gate B → T068 → Phases 7–13 → Gate B`. Separate the early trust-boundary/RBAC proof from the final exhaustive route-permission audit.
**Defect 3** — T075 (Phase 6 / Gate E) depends on T085 (Phase 7 lifecycle), and its acceptance text describes suspension while T085 is reactivation. Fix without weakening fail-closed audit; use the plan/spec as authority.
**Defect 4** — T105 declares `Deps: T104, T130 (quota resolver)` but T130 is Inventory toggle hardening; the real resolver (T142) sits in Phase 11, so a cosmetic ID swap would create another forward dependency. Reorganise rather than renumber; preserve FR-9A-165/166.
**Defect 5** — T117 (Phase 9) uses `PlanQuota` before T141 (Phase 11) creates it. Move the minimum quota foundation earlier; no duplicated model/resolver; NULL = unlimited, never a sentinel.
**Defect 6** — T133 permits "additive permission-seed migration **or** RoleSeedService", which could produce a forbidden migration `062`. Determine the approved mechanism and state explicitly that no `062` may be created; STOP and report if plan.md genuinely conflicts.
Full verbatim text in the conversation transcript for this turn.]

## Response snapshot

**Verified authority before deciding.** Defect 6 was resolved definitively by plan.md line 572, which names the mechanism explicitly — *"seeded via the existing `RoleSeedService` convention"* — and `backend/modules/users_roles/services/role_seed_service.py` exists and is already idempotent ("Safe to call multiple times — uses database unique constraints to skip duplicates"). No plan.md conflict, so no STOP was warranted and no `062` was invented. For defect 3, quickstart.md §9 explicitly permits *"the `CompanyStatus` change (or whichever privileged mutation was under test)"*, and plan.md §32 does not mandate suspension specifically — so an earlier real audited mutation is a legitimate Gate E proof.

**Two additional defects found during the global audit**, neither in the brief:
- **Audit foundation inversion**: `PlatformAuditEvent`/repository/service lived in Phase 6, yet T037 (Phase 3) and T060 (Phase 5) both claimed "every change is audited" — consuming an audit service that did not exist yet. plan.md §36 Phase A actually groups audit foundation *with* identity/RBAC, so my original phase split introduced this. Fixed by moving the three audit-foundation tasks into Phase 3.
- **API-level test before APIs exist**: old T041 asserted "deactivated Platform Administrator cannot access Platform APIs" from Phase 3, before any Platform route existed (Phase 4). Moved to Phase 4 as T059, where it also becomes the API-level proof of the new T054.

**Corrections applied**: T037 split into T040 (domain, audited, no session dep) + T054 (session-revoking deactivation, Phase 4), with T047 `PlatformSessionRepository` ordered before both consumers. Gate B split into T074 (Phase-5 scope, records which routes are in scope) + T203 (Phase 16 exhaustive matrix over the full contract surface). Gate E's proof re-based onto T065 role assignment (Phase 5), with a **new T099** adding the full 3-way state+audit+outbox atomicity proof inside Phase 7 under Gate C — strengthening rather than weakening the requirement. Quota foundation (models + the single resolver) moved to Phase 8 as T105/T106, so T111 downgrade validation and T123 baseline plan both consume infrastructure that exists; Phase 11 retains override/admin workflows via a new T147 that reuses the same model and resolver (no duplication). T139 now names `RoleSeedService` and `users_roles/constants.py` explicitly with a bold "NO NEW MIGRATION `062`" acceptance clause and a STOP instruction if backfill proves impossible.

Renumbered T001→T222 (net +5: three splits, one new atomicity proof, one separated quota-admin workflow). Updated every dependent reference, the Critical Gates table (now carrying an explicit "depends only on" column and the A→B→E→C→D→F→G ordering), Task Summary, dependency graph, hard ordering rules, parallel examples, traceability matrix, gate checklist and completeness audit.

**Machine-verified the result** with a parser over the file: 222 tasks sequential and unique; **zero** forward/order violations; **zero** cycles (DFS three-colour); all seven gates depend only on tasks in their own phase or earlier. Caught one arithmetic slip in the summary table (`[P]` 82 vs actual 84) and corrected the two affected phase rows.

## Outcome

- ✅ Impact: the task graph is now provably executable — three genuine circular/forward dependencies that would have deadlocked implementation are gone, and two further defects the brief had not spotted were found and fixed. No architectural decision, gate, security guarantee or scope boundary was weakened; Gate E coverage actually increased (two proofs instead of one).
- 🧪 Tests: N/A (planning artifact). Verification was a scripted dependency-graph audit rather than a test suite.
- 📁 Files: `specs/009a-platform-admin/tasks.md` (rewritten in place, 222 tasks / 17 phases) + this PHR. `constitution.md`, `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` all untouched.
- 🔁 Next prompts: `/sp.implement` (not started, per instruction).
- 🧠 Reflection: the two defects I found beyond the brief were both the same failure mode as the six reported — a *service* placed in a later phase than the tasks that consume it. Writing a parser to check the invariant mechanically, rather than re-reading 1500 lines, is what surfaced them and is what should have run at the end of the original generation pass.

## Evaluation notes (flywheel)

- Failure modes observed: (a) the original generation created phase boundaries that split a foundation (audit) from its consumers — worth checking "is every service created before its first consumer?" as a generation-time invariant, not just a review-time one; (b) a hand-tallied `[P]` count was wrong for the second time in this epic, confirming that any aggregate number in a generated document should be machine-derived.
- Graders run and results (PASS/FAIL): sequential/unique IDs PASS (222); forward-dependency scan PASS (0 violations); cycle detection PASS (acyclic); gate-executability audit PASS (7/7); stale-ID scan PASS; migration-062 scan PASS; out-of-scope leakage PASS; summary-table reconciliation PASS after correction.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
