---
id: 0017
title: Phase 4 platform authentication session boundary
stage: green
date: 2026-08-20
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.implement
labels: ["platform-admin", "implement", "phase-4", "authentication", "session-boundary", "jwt"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/platform_admin/models/platform_session.py
 - backend/modules/platform_admin/models/platform_refresh_token.py
 - backend/modules/platform_admin/models/__init__.py
 - backend/modules/platform_admin/repositories/platform_session_repository.py
 - backend/modules/platform_admin/repositories/platform_refresh_token_repository.py
 - backend/modules/platform_admin/services/platform_jwt_service.py
 - backend/modules/platform_admin/services/platform_auth_service.py
 - backend/modules/platform_admin/schemas/platform_auth.py
 - backend/modules/platform_admin/dependencies.py
 - backend/modules/platform_admin/router.py
 - backend/api/v1/router.py
 - backend/tests/security/modules/platform_admin/test_token_boundary.py
 - backend/tests/security/modules/platform_admin/test_platform_session.py
 - backend/tests/security/modules/platform_admin/test_identity_boundary.py
 - specs/009a-platform-admin/tasks.md
tests:
 - backend/tests/integration/services/platform_admin/ + backend/tests/security/modules/platform_admin/ (SQLite in-memory, real HTTP via test_client) — 19 passed
 - backend/tests/unit/modules/{auth,companies} + integration/repositories + security/{companies,users_roles} + security/test_{invalid_jwt,jwt_claims,replay_attack,token_entropy,account_lockout}.py (regression) — 1275 passed
---

## Prompt

# Epic 9A — MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close **Phase 4 — Platform Authentication /
Session Boundary, tasks T045-T059** of `specs/009a-platform-admin/tasks.md`.
Same 37-section master prompt as Phases 2-3 (strict phase scope; git safety
preflight; pre-implementation task audit; repository-reality check; per-task
IMPLEMENT→TEST→VERIFY→ADVERSARIAL REVIEW→REGRESSION CHECK→CLOSE; 13-area
architecture freeze including the Platform-Session and Bootstrap
sub-sections; security adversarial testing across authentication crossover
and session/RBAC abuse; contract lock against
`contracts/platform-admin-v1.yaml`'s 3 public `/auth/*` operations; audit
fail-closed proof for every audited mutation; full diff review; evidence-
based checkboxes; exit-condition/Gate proof; requirement traceability; final
consistency search; PHR; pre-commit check; one coherent completion commit;
16-part final report; final stop rule). Full verbatim text in the
conversation transcript.

## Response snapshot

**Preflight**: branch `009a-platform-admin`, clean tree, Phase 3 (`919aaef`)
present in history and pushed. Checklist gate 16/16 PASS.

**Repository-reality check before writing code**: read the tenant
`AuthService`/`JWTService`/`TokenService`/`SessionRepository`/
`core/auth/dependencies.py::get_current_user()` in full to mirror the
established pattern exactly, and discovered the single most consequential
fact of this phase: **`get_current_user()` has zero `typ`-claim checking
logic** — confirmed by grep, only one `"typ"` literal exists anywhere in
tenant auth code (`"typ": "access"` at token-creation time; nothing checks
it at validation time). T052's own acceptance explicitly freezes this
function ("makes no change to `get_current_user()`"), yet T056 requires a
platform token to be rejected by it "(wrong typ)". Resolved by design, not
by touching the frozen function: Platform tokens carry `sub` =
`PlatformAdministrator.id`, not `User.id` — a value that structurally
cannot resolve to any `users.id` row, so `get_current_user()`'s own
`UserRepository.get_by_id_or_none()` lookup already rejects it, unmodified.
This is the kind of planning-vs-repository-reality gap the master prompt's
own instructions require surfacing rather than silently working around;
documented explicitly in T048/T056's Result annotations and in code
comments at the point of design (`platform_jwt_service.py`,
`dependencies.py`).

**A second, narrower planning-narrative inaccuracy found and documented,
not corrected past its own scope**: plan.md's line 291 parenthetical
("tenant tokens use `typ: access/refresh` today") does not match repository
reality — tenant refresh tokens are opaque `secrets.token_urlsafe()`
strings, never JWTs, so there is no tenant `typ: "refresh"` anywhere. T048's
own acceptance ("refresh `typ="platform_refresh"`") is unambiguous and
self-contained regardless, and data-model.md's `PlatformRefreshToken.
token_hash` field accommodates a JWT-format raw credential exactly as an
opaque one — so Platform refresh tokens were built as genuine signed JWTs
(a deliberate departure from the tenant pattern, not an error), with only
their SHA-256 hash persisted, matching the schema precisely.

**Implemented T045-T054** (2 models, `PlatformSessionRepository` +
an implicitly-necessary `PlatformRefreshTokenRepository`, `PlatformJwtService`,
`PlatformAuthService` with login/refresh/logout, `schemas/platform_auth.py`,
`get_current_platform_admin()`, the router mount, and T054's completion —
which required **zero code changes** to `platform_administrator_service.py`
since Phase 3 already built the `SessionRevoker` seam and
`PlatformSessionRepository.revoke_all_for_administrator()` structurally
satisfies that `Protocol` with no adapter class needed).

**Contract audit (§22) caught a real discrepancy before closure**:
`contracts/platform-admin-v1.yaml`'s `/auth/logout` declares `204 No
Content`, but the initial implementation returned `200` + a `StandardResponse`
body (mirroring the tenant `/auth/logout` convention). Fixed to
`status_code=204`, `response_model=None`, matching the existing `204`
pattern already used elsewhere in this codebase (`crm/router.py`'s
`DELETE /leads/{id}`); the now-orphaned `PlatformLogoutResponse` schema was
deleted rather than left as dead code. All 5 downstream test assertions
that checked `200` for a successful logout call were corrected to `204`.

**Two real test-authoring defects found and fixed during testing, not
worked around**: (1) `PlatformLoginRequest.email: EmailStr` rejects the
`.test` TLD as an RFC 2606 reserved special-use domain — several test
emails using `@example.test` (fine for direct-ORM construction, which
skips Pydantic validation) failed once routed through the real HTTP login
endpoint; switched those specific emails to `.com`, with an inline comment
explaining why the distinction matters. (2) A forced-audit-failure test's
own audit-event query initially matched the *earlier, legitimately
successful* `create()` call's audit row rather than proving anything about
the failed `deactivate()` call — tightened the query to filter on the
specific `action` string.

**Wrote 19 tests across 3 files** covering T055 (tenant token → Platform
API denied, correctly scoped to the one Phase-4 route that actually
requires auth — `/auth/logout` — since `/auth/login`/`/auth/refresh` are
contractually public), T056 (platform token rejected by `get_current_user()`,
tested against both `/auth/me` and `/auth/logout`), T057 (logout then reuse
→ 401), T058 (unauthenticated/malformed header → 401), T059 (real
HTTP login → real deactivation via the real `SessionRevoker` → DB-level
`is_revoked=True` confirmation → same token rejected). Went beyond the
literal task list per the master prompt's adversarial-completeness and
fail-closed standards: 4 additional tests for T050's refresh
rotate-on-use (success, replay-of-rotated-token rejected, revoked-session
rejected, tenant-typed-token rejected), a second forced-audit-failure test
proving T054's 3-way atomicity (state + audit + session revocation all
fail to commit together, not just the first two — a genuinely new
combination Phase 3's audit test didn't have any session to exercise), and
a reverse-direction typ-crossover test (a `platform_refresh`-typed token
rejected when presented as an access token).

**Regression**: the platform_admin suite (19 tests) plus a properly-scoped
regression (auth/companies unit, all repository integration tests,
companies/users_roles security tests, JWT/replay/entropy/lockout security
tests — 1275 tests) covering every shared file this phase touched
(`api/v1/router.py`, `models/__init__.py`). A first regression attempt
scoped to the entire `tests/integration/api/v1` directory (every module's
full API suite) was abandoned mid-run after ~15 minutes made only marginal
progress against a clearly disproportionate scope for a one-line additive
router mount — the OpenAPI schema itself (573 paths, zero duplicates,
already checked when verifying T053) was already strong structural
evidence the mount didn't collide with anything; the properly-scoped rerun
completed cleanly in under 4 minutes.

## Outcome

- ✅ Impact: Platform Administrators can now authenticate through a
  genuinely separate session/token system — mutually unusable with tenant
  auth in both directions, verified empirically rather than assumed from
  the `typ` claim's mere existence. BR-9A-011 (session-revoking
  deactivation) is now fully, not partially, satisfied. `get_current_user()`
  remains byte-for-byte unmodified, confirmed via `git diff`.
- 🧪 Tests: 19/19 new Phase-4 tests passed; 1275/1275 regression tests
  passed for every shared file touched.
- 📁 Files: 8 new files under `backend/modules/platform_admin/`, 2 new test
  files (+ 1 existing test file extended), `api/v1/router.py` (mount),
  `models/__init__.py` (registration), `tasks.md` (15 tasks marked `[X]`)
  + this PHR. No migrations, no Phase 5 RBAC code, no frontend files.
- 🔁 Next prompts: Phase 5 (Platform RBAC & Owner Bootstrap — Gate B) — not
  started, per the strict phase-lock scope and final stop rule.
- 🧠 Reflection: the `get_current_user()` typ-check gap is the clearest
  example yet in this epic of the master prompt's own warning — "a test
  that only checks that X eventually exists is insufficient" generalizes to
  "a design description that asserts a mechanism exists is insufficient";
  only reading the actual current implementation (not the planning
  artifact's characterization of it) surfaced that the described mechanism
  didn't exist, and the fix had to work within the explicit constraint that
  the function was frozen — producing a structurally cleaner design
  (distinct `sub` semantics) than the one originally imagined.

## Evaluation notes (flywheel)

- Failure modes observed: (a) trusted a planning artifact's parenthetical
  characterization of existing code ("tenant tokens use typ: access/refresh
  today") without independently verifying it — caught only because
  implementing the SAME claim for the Platform side required checking the
  tenant precedent directly; (b) an overly broad regression-scope choice
  (an entire directory covering every module) wasted real background-task
  time before being caught and corrected to match the actual blast radius
  of a one-line additive change — proportional regression scope should be
  decided from the actual diff, not defaulted to "run everything nearby."
- Graders run and results (PASS/FAIL): task count PASS (225); phase count
  PASS (17); T001-T059 exclusively marked `[X]` PASS; Phase-4 test suite
  PASS (19/19); regression suite PASS (1275/1275); full diff review PASS
  (15 files, all in-scope, no future-phase leakage, no secrets, no debug
  code); contract audit PASS (1 real discrepancy found and fixed —
  `/auth/logout` 204 vs 200); requirement traceability matrix reconciliation
  PASS (6 rows spot-checked, zero drift); black/ruff PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): when a planning artifact makes
  a factual claim about *existing* (not new) code as justification for a
  design choice, verify that claim against the actual file before relying
  on it, the same way a claim about a *new* requirement would be verified
  against the task's own acceptance text.
