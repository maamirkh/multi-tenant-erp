---
id: 0018
title: Phase 5 Platform RBAC & Owner Bootstrap Gate B
stage: green
date: 2026-08-20
surface: agent
model: claude-opus-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.implement
labels: ["platform-admin", "implement", "phase-5", "rbac", "bootstrap", "gate-b"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/platform_admin/models/platform_rbac.py
 - backend/modules/platform_admin/models/__init__.py
 - backend/modules/platform_admin/repositories/platform_rbac_repository.py
 - backend/modules/platform_admin/constants.py
 - backend/modules/platform_admin/services/platform_rbac_seed_service.py
 - backend/modules/platform_admin/services/platform_rbac_service.py
 - backend/modules/platform_admin/services/platform_administrator_service.py
 - backend/modules/platform_admin/exceptions.py
 - backend/modules/platform_admin/dependencies.py
 - backend/modules/platform_admin/bootstrap.py
 - backend/modules/platform_admin/schemas/platform_rbac.py
 - backend/modules/platform_admin/router.py
 - backend/api/v1/router.py
 - backend/tests/integration/services/platform_admin/test_bootstrap.py
 - backend/tests/integration/api/v1/platform_admin/test_administrator_rbac_routes.py
 - backend/tests/security/modules/platform_admin/test_bootstrap_abuse.py
 - backend/tests/security/modules/platform_admin/test_rbac_escalation.py
 - backend/tests/security/modules/platform_admin/test_permission_enforcement_phase5.py
 - specs/009a-platform-admin/tasks.md
tests:
 - backend/tests/integration/services/platform_admin/, backend/tests/integration/api/v1/platform_admin/, backend/tests/security/modules/platform_admin/, bootstrap tests (SQLite in-memory, real HTTP via test_client) — 77/77 passing in a combined run; +3 additional 404-path tests added during self-review, individually verified passing (80 total Phase 5 tests)
 - backend/tests/unit/modules/{auth,companies} + integration/repositories/{auth,companies} + security/{companies,users_roles} + security/test_{invalid_jwt,jwt_claims,replay_attack,token_entropy,account_lockout}.py (scoped regression for shared files api/v1/router.py, dependencies.py, exceptions.py) — 382/382 passing
 - ruff + black clean on all Phase 5 files
---

## Prompt

# Epic 9A — MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close **Phase 5 — Platform RBAC & Owner
Bootstrap, Gate B, tasks T060-T077** of `specs/009a-platform-admin/tasks.md`.
Same 37-section master prompt as Phases 2-4 (strict phase scope; git safety
preflight; pre-implementation task audit; repository-reality check; per-task
IMPLEMENT→TEST→VERIFY→ADVERSARIAL REVIEW→REGRESSION CHECK→CLOSE; 13-area
architecture freeze including RBAC and Bootstrap sub-sections; security
adversarial testing across self-escalation/last-owner/bootstrap abuse;
contract lock against `contracts/platform-admin-v1.yaml`'s operations
20-25; audit fail-closed proof for every audited mutation including
rejected attempts; full diff review; evidence-based checkboxes; exit-
condition/Gate B proof; requirement traceability; final consistency
search; PHR; pre-commit check; one coherent completion commit; 16-part
final report; final stop rule). Full verbatim text in the conversation
transcript (this session continued from a prior compacted context).

## Response snapshot

**Preflight**: branch `009a-platform-admin`, clean tree, Phase 4 (`7e0737e`) present in history.

**T060-T067 (RBAC foundation + bootstrap)**: `PlatformPermission`/`PlatformRole`/`PlatformRolePermission`/`PlatformAdminRoleAssignment` models verified column-for-column against migration 057 (already committed, zero drift). `PlatformRbacRepository` with CRUD, `has_role`, `count_active_administrators_with_role`, `get_effective_permissions`. `constants.py` extended to a `PLATFORM_PERMISSION_CATALOGUE` (code/label/area) with `PLATFORM_PERMISSION_CODES` derived from it. `PlatformRbacSeedService` idempotent (compare-before-write on role bundles — a genuine no-write no-op on reruns). `require_platform_permission(code)` dependency factory. `PlatformRbacService.assign_role()`/`remove_role_assignment()`/`assert_not_last_owner_removal()` — self-escalation and last-owner denials are now **also audited** (a gap the T075 test surfaced: the original implementation only audited the success path). Out-of-band `bootstrap.py` — Argon2 hash-format validation via `PasswordHasher().verify(hash, "dummy")`, `InvalidHash` vs `VerifyMismatchError`.

**T068/T069 (Administrator/RBAC HTTP routes)**: New `admin_router`/`rbac_router` mounted at `/platform` in `api/v1/router.py`. `PlatformAdministratorService.create()` extended with a `User`-existence check (404) — a self-review finding, since the FK/unique constraints would otherwise surface raw `IntegrityError` as 500. `PlatformRbacService.create_or_update_role()` added (rejects unknown permission codes, 422). `assign_role` route validates both `adminId` and `role_id` exist (404) — another self-review finding.

**T070-T076 (tests)**: `test_bootstrap.py`'s 7 tests rewritten leakage-robust (before/after deltas, `assigned_by IS NULL` lookup for the genuine bootstrap-owner, explicit zero-owner isolation for the first-success test) after discovering the documented cross-test `db_session` leakage property (Phase 3/4/5) extends across directories once new Phase-5 test files sort alphabetically before it. `test_bootstrap_abuse.py` (T074, 6 tests) — structural grep proof + behavioral 401/403 proof; surfaced and fixed a real production bug (`logger.info(extra={"created": ...})` colliding with `logging.LogRecord`'s reserved `created` attribute, crashing at INFO level). `test_rbac_escalation.py` (T075, 4 tests) — service-layer only, both denials proven audited. `test_permission_enforcement_phase5.py` (T076, 33 tests) — the 9-operation Gate B matrix (3 public + 6 guarded × 4 angles). `test_administrator_rbac_routes.py` (route-specific acceptance: duplicate 409, deactivate-revokes-sessions, last-owner 409, unknown-permission 422, self-escalation 403 via HTTP, plus 3 new 404 tests for the self-review findings).

**Gate B (T077)**: PASSED. All named deps (T055-T059, T074-T076) pass; 77/77 combined run + 3 additional tests independently verified (80 total); scoped shared-file regression 382/382 passing.

## Outcome

- ✅ Impact: Genuinely enforced Platform RBAC (ADR-2) is live; out-of-band bootstrap breaks the circularity (ADR-8); Gate B independently passable using only Phase 1-5 work.
- 🧪 Tests: 80 Phase 5 tests passing; 382 scoped regression tests passing; ruff/black clean.
- 📁 Files: 13 modified/new backend source files, 5 test files, tasks.md.
- 🔁 Next prompts: Phase 6 — Platform Audit Query Surface (Gate E), on explicit Product Owner instruction only.
- 🧠 Reflection: The cross-test leakage property of the shared `db_session` fixture is now a cross-directory concern, not just cross-function — any new test file that creates a `platform_owner`-role administrator (even via direct repository calls in test setup) must use a non-NULL `assigned_by` to avoid colliding with `test_bootstrap.py`'s "the genuine bootstrap assignment has `assigned_by IS NULL`" invariant.

## Evaluation notes (flywheel)

- Failure modes observed: (1) logging `extra={"created": ...}` colliding with `LogRecord`'s reserved attribute — only surfaces when the logger call actually fires at INFO+ level, invisible in tests that never configure logging. (2) Cross-directory test collection order silently violating a same-directory-only leakage assumption baked into an earlier phase's test.
- Graders run and results (PASS/FAIL): ruff PASS, black PASS (after one reformat pass), full Phase 5 suite PASS (80/80), scoped regression PASS (382/382).
- Prompt variant (if applicable): n/a — fixed master template.
- Next experiment (smallest change to try): n/a.
