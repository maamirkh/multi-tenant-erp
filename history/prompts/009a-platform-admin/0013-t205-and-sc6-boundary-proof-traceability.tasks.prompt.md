---
id: 0013
title: T205 and SC-6 boundary proof traceability
stage: tasks
date: 2026-08-19
surface: agent
model: claude-opus-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.tasks
labels: ["platform-admin", "tasks", "traceability", "trust-boundary", "documentation"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/009a-platform-admin/tasks.md
 - history/prompts/009a-platform-admin/0013-t205-and-sc6-boundary-proof-traceability.tasks.prompt.md
tests:
 - none (documentation/traceability correction; no code, migrations, or tests written)
---

## Prompt

Review the current Epic 9A `tasks.md` and make ONLY the surgical corrections
described below. Do NOT regenerate, renumber, add/remove tasks, reorder phases,
gates or dependencies, or change architecture/scope/contracts/migrations.
Preserve T001–T225, 17 phases, all gates, migrations `057`–`061` with no `062`,
and all prior Revision 2 / Revision 3 corrections.

**Correction 1 — stale backend-proof reference in T205 Case D.** Case D said
tenant-vs-Platform auth separation at the routing layer "complements the backend
proof in T057". That is stale: T057 verifies revoked Platform sessions, not the
tenant-vs-Platform authentication boundary. The relevant proofs are T055 (tenant
token cannot access Platform APIs) and T056 (Platform token cannot satisfy tenant
authentication). Change to "complements the backend proofs in T055/T056" without
altering Case D's behaviour or acceptance criteria. T205 must still contain all
five cases A–E.

**Correction 2 — tighten SC-6 traceability.** The matrix row read
`SC-6 tenant session cannot reach platform | T052 | T055, T058`. Make it
accurately represent the trust-boundary verification: T055 is the primary
backend proof, T056 the reverse-boundary proof, T205 Case D the frontend
routing-layer proof. Preferred result `T055, T056, T205 case D`. Do NOT use T057
as the tenant-vs-Platform boundary proof.

Then a narrow consistency scan over T055, T056, T057, T058, T182, T183, T205 and
the tenant/Platform separation, token-crossover and route-protection wording,
plus a final-invariants confirmation and a 4-item report.
Full verbatim text in the conversation transcript for this turn.

## Response snapshot

Two single-line textual edits, nothing else.

**Correction 1** — T205 Case D (line 1336): "complements the backend proof in
**T057**" → "complements the backend proofs in **T055/T056**". Cases A–E and all
acceptance behaviour unchanged; the Isolation requirement clause untouched.

**Correction 2** — traceability row (line 1578):
`| SC-6 tenant session cannot reach platform | T052 | T055, T058 |` →
`| SC-6 tenant session cannot reach platform | T052 | T055 (primary), T056, T205 case D |`.
T058 was dropped because it proves only that unauthenticated requests are
rejected — it is not a tenant-token-specific test, so citing it under SC-6
overstated the evidence. This also brings the row into line with the already-
correct row at line 1555 (`Tenant vs Platform auth separation | … | T055, T056,
T180, T181, T205 case D`), which the SC-6 row had drifted from.

**Consistency scan (T055/T056/T057/T058/T182/T183/T205)** — all seven checks
pass. T055 is cited consistently as tenant-token-rejected-by-Platform-APIs
(lines 332, 1555, 1566, 1578, 1629); T056 consistently as the reverse boundary
(1555, 1566, 1578, 1629); T057 now appears **only** in its own task definition
and inside T077's numeric dependency range `T055–T059`, and is no longer cited
anywhere as a boundary proof; T058 likewise retains only its own definition and
that range, and is no longer a stand-in for a tenant-token test; T182/T183 remain
frontend HTTP-client token/refresh isolation tests; T205 Case D remains the
frontend route-protection isolation test.

**Final invariants re-verified by script**: 225 tasks, IDs T001–T225 sequential
and unique; 17 phases; all seven gates A–G present; `[P]` count 85 matching the
summary table; migrations `057`–`061` with no `062` creation anywhere; the
"28 contract paths / 33 operations", "30 permission-guarded operations",
`(platform-auth)` and `(platform-admin)` invariants all still present. Dependency
graph re-audited after the edits: zero non-existent/forward dependencies, zero
cycles.

## Outcome

- ✅ Impact: the trust-boundary evidence chain is now cited accurately in both
  places it appears. SC-6 previously pointed at a test (T058) that does not prove
  the claim, which would have let a reviewer sign off the boundary on the wrong
  evidence; T205 Case D pointed at the revoked-session test rather than either
  actual boundary proof.
- 🧪 Tests: N/A (documentation/traceability only). No test's behaviour,
  acceptance criteria or file path changed.
- 📁 Files: `specs/009a-platform-admin/tasks.md` (2 lines) + this PHR. All seven
  protected planning artifacts untouched.
- 🔁 Next prompts: `/sp.implement` (not started, per instruction).
- 🧠 Reflection: the same fact was recorded in three places (T205 Case D, the
  SC-6 row, the completeness-audit line) and two of them drifted while the third
  stayed right. Where the evidence list at line 1555 was already correct, the
  divergence was detectable purely by diffing the three citations of the same
  claim against each other — a cheaper check than re-deriving which test proves
  what.

## Evaluation notes (flywheel)

- Failure modes observed: cross-reference drift between duplicate statements of
  one fact. Worth scanning, for any claim cited in more than one place, whether
  every citation names the same supporting task IDs.
- Graders run and results (PASS/FAIL): task count PASS (225); sequential/unique
  IDs PASS; phase count PASS (17); gates A–G PASS (7/7); `[P]` reconciliation
  PASS (85 = 85); migration `062` scan PASS (none created); contract-invariant
  strings PASS; forward-dependency scan PASS (0); cycle detection PASS (acyclic);
  T055/T056/T057/T058 citation-consistency PASS; T182/T183/T205 role-consistency
  PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
