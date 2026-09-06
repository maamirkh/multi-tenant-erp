---
id: 0016
title: Phase 3 platform domain audit foundation administrator identity
stage: green
date: 2026-08-20
surface: agent
model: claude-sonnet-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.implement
labels: ["platform-admin", "implement", "phase-3", "audit-foundation", "administrator-identity", "adr-5"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/platform_admin/__init__.py
 - backend/modules/platform_admin/constants.py
 - backend/modules/platform_admin/exceptions.py
 - backend/modules/platform_admin/dependencies.py
 - backend/modules/platform_admin/router.py
 - backend/modules/platform_admin/models/__init__.py
 - backend/modules/platform_admin/models/platform_administrator.py
 - backend/modules/platform_admin/models/platform_audit_event.py
 - backend/modules/platform_admin/repositories/__init__.py
 - backend/modules/platform_admin/repositories/platform_administrator_repository.py
 - backend/modules/platform_admin/repositories/platform_audit_repository.py
 - backend/modules/platform_admin/services/__init__.py
 - backend/modules/platform_admin/services/platform_administrator_service.py
 - backend/modules/platform_admin/services/platform_audit_service.py
 - backend/modules/platform_admin/schemas/__init__.py
 - backend/modules/platform_admin/schemas/platform_administrator.py
 - backend/modules/platform_admin/events/__init__.py
 - backend/tests/integration/services/__init__.py
 - backend/tests/integration/services/platform_admin/__init__.py
 - backend/tests/integration/services/platform_admin/test_platform_administrator.py
 - backend/tests/integration/services/platform_admin/test_audit_foundation.py
 - backend/tests/security/modules/__init__.py
 - backend/tests/security/modules/platform_admin/__init__.py
 - backend/tests/security/modules/platform_admin/test_identity_boundary.py
 - backend/tests/conftest.py
 - specs/009a-platform-admin/tasks.md
tests:
 - backend/tests/integration/services/platform_admin/ + backend/tests/security/modules/platform_admin/ (SQLite in-memory, db_session fixture) — 6 passed
 - backend/tests/unit/modules/{auth,companies}/ + integration/repositories + security/{companies,users_roles} (regression, conftest.py touched) — 1246 passed
---

## Prompt

# Epic 9A — MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close **Phase 3 — Platform Domain, Audit
Foundation & Administrator Identity, tasks T032-T044** of
`specs/009a-platform-admin/tasks.md`. Same 37-section master prompt as
Phase 2 (strict phase scope; git safety preflight; pre-implementation task
audit; repository-reality check; IMPLEMENT→TEST→VERIFY→ADVERSARIAL
REVIEW→REGRESSION CHECK→CLOSE per task; 13-area architecture freeze; audit
fail-closed proof requiring BOTH a success AND a forced-failure test per
audited mutation; contract lock — N/A this phase, no HTTP surface;
adversarial completeness pass; full diff review; evidence-based task
checkboxes; exit-condition/Gate proof; requirement traceability;
final-consistency search; PHR; pre-commit check; one coherent completion
commit only if genuinely complete; 16-part final report A-P; final stop
rule). Full verbatim text in the conversation transcript for this turn.

## Response snapshot

**Preflight**: branch `009a-platform-admin`, clean tree, Phase 2 (`a32c70a`)
present in history, pushed to origin. Checklist gate 16/16 PASS.

**Repository-reality check before writing code**: studied `modules/crm/`
and `modules/accounting/`'s directory shape (T032's own reference) and
found `handlers/` is NOT in T032's Files list — created everything T032
asks for and nothing more. Read `AccountingAuditLogRepository.create()`
and `AuditLogService.record()` in full — the codebase's only existing
fail-closed audit precedent (plan.md §3.4/§3.5) — and mirrored both
exactly: `PlatformAuditRepository.record()` does `db.add()`+`db.flush()`,
never commits; `PlatformAuditService.record()` stages via the repository
and also does not commit — the calling domain service owns the single
`db.commit()`, matching the Accounting precedent's actual call-site
convention (not the more tempting but wrong design where the audit
*service* itself commits). Confirmed via `core/exceptions/base.py` the
exact 6 typed exception base classes (401/403×3/409×2) T034 needed.
Cross-checked spec.md §15.1's permission table against every
`x-permission` in `contracts/platform-admin-v1.yaml` (21 codes, all a
strict subset of the 29-code catalogue) before writing `constants.py`, so
T033's data can't drift from what Phase 5 will actually wire up.

**Implemented T032-T041** (module skeleton, constants, exceptions, both
models, both repositories, both services, schemas) then **T042-T044**
(3 test files, 6 tests). `PlatformAdministratorService` exposes the
explicit `SessionRevoker` `Protocol` seam T040's acceptance text
requires — with none injected (the Phase 3 state), `deactivate()` performs
only the account-state change and its audit record; Phase 4's T054 will
inject a real revoker into this exact seam. Documented plainly, not
silently, that **FR-9A-031/BR-9A-011's "immediately invalidating active
platform sessions" clause is intentionally unmet by Phase 3 alone**.

**Two self-review defects found and fixed before any test ran**: (1) a
manual `python -c` import check (deliberately run *without*
`companies.models` pre-imported) showed `PlatformAuditEvent.company_id`
resolving to `NullType()` — SQLAlchemy's implicit `type_annotation_map`
inference for FK-typed UUID columns depends on the FK's target table
already being registered in `Base.metadata`; fixed by giving every UUID
column an explicit `Uuid(as_uuid=True)` type in both new models, making
every column's type independent of import order. (2) A real cross-test
data-leakage discovery during testing (below), fixed in test code.

**Audit fail-closed proof went beyond T044's literal wording**, per the
master prompt's §20 standard ("a test that only checks an audit row
eventually exists is insufficient"): added a second test that patches
`PlatformAuditService.record` to raise, proving the `is_active` state
change does not survive (`db_session.rollback()` restores `True`) and
zero deactivate-audit rows exist, since `db.commit()` is never reached.

**Real defect discovered during test execution, root-caused, and fixed
within scope, not worked around**: running the new tests together
produced a `UNIQUE constraint failed: users.email` and a false-failing
"zero rows" assertion. Isolated the cause with targeted single-file runs:
`session.commit()` calls made through the service layer (as opposed to
plain `flush()`-only tests elsewhere in the codebase) are not being
undone by the shared root `conftest.py`'s per-test SAVEPOINT-rollback
teardown, so data committed in one test function was visible to a later
one in the same pytest process — a pre-existing latent property of the
project's `db_session` fixture (`join_transaction_mode="create_savepoint"`
+ SQLite), not a defect in Epic 9A's own code, and out of Phase 3's scope
to fix in the shared fixture. Fixed by making every new test defensive
instead: unique `uuid4()`-suffixed emails/slugs per call, and scoping
every "does not exist" assertion to the specifically-created entity's id
rather than a table-wide `count()` — the semantically correct check for
BR-9A-001/BR-9A-010 anyway ("this specific tenant user has no Platform
identity", not "the whole table is empty").

**Wired `modules.platform_admin.models` into the root `tests/conftest.py`
import block** (one line) — the same mechanical registration step every
prior module (accounting, auth, companies, crm, inventory, purchase,
sales, users_roles) required when introduced, needed so
`Base.metadata.create_all()` creates the two new tables in the SQLite
test engine. Ran a broader regression afterward (auth/companies unit,
all repository integration tests, companies/users_roles security tests —
1246 tests) to confirm this shared-file touch caused zero collateral
damage.

**Black reformatted 5 files** (line-wrapping only) on the first commit
attempt; re-ran the full 6-test Phase 3 suite and ruff afterward —
unchanged pass count, zero lint findings.

## Outcome

- ✅ Impact: the fail-closed audit foundation (ADR-5) now exists with
  proof going beyond its literal task text, and the `PlatformAdministrator`
  principal is provably independent of tenant identity in both directions
  (BR-9A-010: valid with zero memberships; BR-9A-001: tenant owner/admin
  role grants nothing). Every later audited mutation in Phases 3-12 now
  has a real, tested pattern to extend rather than invent.
- 🧪 Tests: 6/6 new Phase-3 tests passed (SQLite in-memory); 1246/1246
  regression tests passed for the shared-conftest.py touch's blast radius.
- 📁 Files: 17 new files under `backend/modules/platform_admin/`, 6 new
  test files (+ 4 `__init__.py`) under 2 new test-package trees, 1-line
  addition to `backend/tests/conftest.py`, `tasks.md` (13 tasks marked
  `[X]` with evidence) + this PHR. No migrations, no routes mounted, no
  frontend files — zero future-phase leakage.
- 🔁 Next prompts: Phase 4 (Platform Authentication / Session Boundary) —
  not started, per the strict phase-lock scope and final stop rule.
- 🧠 Reflection: both real defects this phase (the `NullType()` column and
  the cross-test SAVEPOINT leak) were invisible to a first read of the
  code and only surfaced by *actually running* a standalone import and a
  multi-test-in-one-file run — reinforcing that "self-review as if
  reviewing another engineer's PR" is necessary but not sufficient; the
  master prompt's insistence on execution-based verification at every
  step is what caught what a code-only review would have missed.

## Evaluation notes (flywheel)

- Failure modes observed: (a) implicit ORM type inference silently
  depending on unrelated modules' import order — a class of bug that only
  manifests when a file is imported in an unusual order, exactly the kind
  of thing a full-suite test run (which always imports everything) can
  mask; caught only by a deliberately minimal standalone import test. (b)
  A test-fixture property (cross-test commit visibility) that is
  invisible when tests are written assuming "the docstring says rollback
  isolates" without empirically verifying it for the specific case of a
  service-layer `commit()` — the fix (scope assertions to owned entities)
  is also simply better practice regardless of the fixture's behavior.
- Graders run and results (PASS/FAIL): task count PASS (225); phase count
  PASS (17); T001-T044 exclusively marked `[X]` PASS; Phase-3 test suite
  PASS (6/6); regression suite PASS (1246/1246); full diff review PASS
  (26 files, all in-scope, no future-phase leakage, no secrets, no debug
  code); requirement traceability matrix reconciliation PASS (4 rows
  spot-checked: US-8, FR-9A-204, BR-9A-001/002/003, SC-4 — zero drift);
  black/ruff PASS after reformatting.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): when a new module's tests are
  the first in the suite to rely on service-layer `db.commit()` within a
  single test function followed by a second test function reusing similar
  data, verify fixture isolation empirically before writing count-based
  assertions, rather than after a failure surfaces it.
