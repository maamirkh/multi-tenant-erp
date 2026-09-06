---
id: 0010
title: Epic 10 Phase 1 module foundation
stage: green
date: 2026-08-25
surface: agent
model: claude-sonnet-5
feature: 010-installments
branch: 010-installments
user: Muhammad Amir
command: /sp.implement
labels: [installments, epic-10, phase-1, module-foundation, permissions, exceptions, lifecycle-enum, entitlement]
links:
  spec: specs/010-installments/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - backend/modules/installments/__init__.py
 - backend/modules/installments/constants.py
 - backend/modules/installments/dependencies.py
 - backend/modules/installments/exceptions.py
 - backend/modules/installments/router.py
 - backend/modules/installments/events/__init__.py
 - backend/modules/installments/schemas/__init__.py
 - backend/modules/installments/schemas/base.py
 - backend/modules/users_roles/constants.py
 - backend/tests/unit/modules/installments/__init__.py
 - backend/tests/unit/modules/installments/test_lifecycle_transitions_table.py
 - backend/tests/integration/repositories/installments/__init__.py
 - backend/tests/integration/api/v1/installments/__init__.py
 - backend/tests/security/installments/__init__.py
 - backend/tests/performance/installments/__init__.py
 - specs/010-installments/tasks.md
tests:
 - backend/tests/unit/modules/installments/test_lifecycle_transitions_table.py — 7 passed
 - backend/tests/unit/modules/users_roles/ — 175 passed (regression, users_roles/constants.py touched)
 - backend/tests/integration/repositories/users_roles/, tests/integration/api/v1/users_roles/, tests/integration/api/v1/companies/, tests/security/users_roles/ — 234 passed (regression)
 - ruff check (all new/modified Phase 1 files) — all checks passed
 - manual runtime verification: module import graph, all 9 exceptions' code/http_status, exact per-role Installments permission grant counts and membership cross-checked against migration 071's `_ROLE_GRANTS` (exact match, zero mismatches)
 - live API container health check post-reload (200, database: ok) after every file change
---

## Prompt

# Epic 10 — Installments
# MASTER PHASE IMPLEMENTATION & CLOSURE PROMPT

Implement, verify, audit, and close ONLY the following phase of Epic 10.

Phase Number: `1`
Phase Name: `Module Foundation`
Task Range: `T012 to T020`

Feature Branch: 010-installments

[Full 47-section master prompt supplied verbatim by the user — identical
structure/rules to the Phase 0 closure prompt (see PHR 0009), covering:
primary objective and no-correction-pass standard; strict phase scope
(implement only T012-T020, no future-phase models/repositories/services/
routes pre-created); authoritative sources and authority order;
branch/working-tree safety; pre-implementation task audit; repository-
reality check before new abstractions; per-task IMPLEMENT/TEST/VERIFY/
NEGATIVE-PATH/DEPENDENCY-RECHECK discipline; architecture freeze
(Accounting source-of-truth, no shadow balances, named lifecycle methods
only, REJECTED never persisted, operation-sensitive entitlement,
Platform/Support boundary, no AI) — all N/A at the constants/exceptions
level this phase touches; financial-transaction/idempotency/Phase-5.5/
Phase-6 hard-gate rules — N/A, no financial workflows or idempotency-
protected commands exist yet; database & migration hard rules — N/A, no
migration work in this phase; API contract lock, data-model audit,
frontend rules — N/A; full testing pyramid; failure-injection/atomicity
proof — N/A; pre-existing-failure policy; real PostgreSQL/Docker
verification requirement; live HTTP/browser verification — N/A;
requirement traceability review; mandatory self-review and adversarial-
completeness pass; full diff review before closure; task-checkbox
truthfulness rule; exact phase Exit Condition proof requirement; hard-gate
rule — N/A; regression verification; no-correction-pass final
contradiction search; PHR requirement; pre-commit check; commit policy;
post-commit verification; the exhaustive Required Final Report template
(sections A-S); and the final stop rule.]

## Response snapshot

Verified branch (`010-installments`) and working tree matched the exact
pre-existing baseline confirmed at Phase 0's closure (only pre-existing
untracked planning docs and `CLAUDE.md`). Confirmed Phase 0's commit
(`2607731`) present in history. Re-read tasks.md T012-T020 plus plan.md
§9.1/§9.2 (lifecycle state machine, `_LEGAL_TRANSITIONS`), §15.2
(`InstallmentOperationClass`/`InstallmentAccessPolicy`), §16.1 (16-code
permission catalogue), §22 (Failure/Recovery Design, the 9-exception
mapping), §30.1 (per-role grant table, already implemented in migration
071 — used as the cross-check ground truth for T016).

Researched exact repository conventions before writing anything: CRM's
module skeleton shape (`__init__.py`/`dependencies.py`/`router.py`/
`events/__init__.py` — though CRM's own files have since grown far past
their Phase-1 starting point with no preserved git history to inspect,
since CRM's entire epic was squashed into one commit, so the skeleton
shape here was designed fresh from the *current* file's documented
growth-pattern conventions, not copied from an unavailable historical
snapshot); `core/exceptions/base.py`'s four base exception classes and
confirmed their constructors do NOT accept a custom `code` override
(discovered by reading CRM's/Accounting's own `CrmException`/
`AccountingException` module-level base pattern, then deliberately chose
NOT to add an equivalent `InstallmentsException` base for Installments
since T017 explicitly names only the four narrow base classes to
subclass — used the `super().__init__(); self.code = "..."` override
idiom instead, satisfying T017's literal instruction while still
producing plan.md's mandated `FEATURE_DISABLED`/`PERIOD_LOCKED`/
`SELF_APPROVAL_NOT_ALLOWED`/`IDEMPOTENCY_*` codes); Accounting's
`(str, Enum)` status-enum convention (`JournalEntryStatus` et al.) as the
precedent for `InstallmentContractStatus`/`InstallmentOperationClass`
(plan.md's own §15.2 code block already gives `InstallmentOperationClass`
verbatim as `class InstallmentOperationClass(str, Enum)`); Accounting's
richer `AccountingPermissionDefinition`-tuple style (code/label/module/
action/description) as the explicit style T015 names for
`installments/constants.py`'s own `INSTALLMENTS_PERMISSIONS` tuple —
deliberately NOT CRM's simpler bare-`frozenset[str]` style, since T015
explicitly says "following the exact `PermissionDefinition`-tuple style
used in `modules/accounting/constants.py`"; confirmed via `grep` that
neither CRM's nor Accounting's own module-local permission tuple is
ever imported into `users_roles/constants.py` — each module's
permission catalogue is independently, deliberately duplicated in both
places (module-local file + `users_roles/constants.py`) — so `T016`'s
`INSTALLMENTS_PERMISSIONS` tuple was defined as its own second,
independent literal directly inside `users_roles/constants.py` (avoiding
a `users_roles -> installments` cross-module import that no other module
uses either) and unioned via `+ INSTALLMENTS_PERMISSIONS` onto the
existing giant `INITIAL_PERMISSIONS` tuple literal, preserving that
tuple's existing content completely unchanged.

Implemented all 9 tasks:
- **T012**: `__init__.py`, `constants.py`, `dependencies.py`, `exceptions.py`,
  `router.py` (`router = APIRouter(tags=["installments"])`),
  `events/__init__.py` — the exact vertical-slice shape, no `api/`/
  `permissions/`/`validators/` subfolders. `events/__init__.py`'s
  docstring explicitly documents *why* it does NOT mirror CRM/Sales/
  Accounting/Purchase's in-process `EventBus` pattern (ADR-INST-09:
  transactional outbox instead, since an in-process bus loses events on
  restart and Installments is money-adjacent) — nothing to define yet.
- **T013**: `InstallmentContractStatus(str, Enum)` (8 members, no
  `REJECTED`) and `_LEGAL_TRANSITIONS` (plan.md §9.2's table, copied
  verbatim using plain string literals rather than enum-member
  references, to match the plan's own given code exactly and keep T020's
  test unambiguous).
- **T014**: `InstallmentOperationClass(str, Enum)` (`ORIGINATION`,
  `SERVICING`, `READ`, `ADMIN`), same file as T013/T015, sequenced (not
  `[P]`) per the correction already recorded in tasks.md.
- **T015**: `InstallmentsPermissionDefinition` dataclass +
  `INSTALLMENTS_PERMISSIONS` tuple (16 entries, Accounting's richer
  tuple style), same file, sequenced.
- **T016**: Second, independent `INSTALLMENTS_PERMISSIONS` tuple (16
  entries, `users_roles.constants.PermissionDefinition` type) unioned
  into `INITIAL_PERMISSIONS`; 7 new per-role frozensets
  (`_INSTALLMENTS_OWNER/_ADMIN/_MANAGER/_ACCOUNTANT/_SALESPERSON/
  _CASHIER/_VIEWER`, `store-keeper` deliberately absent) unioned into
  `DEFAULT_ROLE_PERMISSIONS`'s 7 corresponding role entries.
- **T017**: 9 exceptions (`InstallmentNotFoundError`,
  `InstallmentSelfApprovalNotAllowedError`, `InstallmentIllegalTransitionError`,
  `InstallmentConcurrentModificationError`,
  `InstallmentOutstandingBalanceRemainsError`, `InstallmentsNotEntitledError`,
  `InstallmentFiscalPeriodLockedError`, `DegenerateScheduleError`,
  `InstallmentIdempotencyConflictError`), each subclassing one of
  `NotFoundException`/`ConflictException`/`ForbiddenException`/
  `ValidationException`, covering every named failure mode in plan.md §22.
- **T018**: `InstallmentsBaseSchema(BaseModel)` with
  `model_config = ConfigDict(from_attributes=True)`, mirroring
  `AccountingBaseSchema` exactly — only the one class T018 names, no
  pagination/error-detail wrapper pre-created ahead of need.
- **T019**: Five empty test-directory packages with `__init__.py`
  (`tests/unit/modules/installments/`,
  `tests/integration/repositories/installments/`,
  `tests/integration/api/v1/installments/`,
  `tests/security/installments/`, `tests/performance/installments/`) —
  confirmed `tests/integration/api/v1/` itself has no `__init__.py`
  either (matches CRM's identical leaf-only convention).
- **T020**: `test_lifecycle_transitions_table.py` (7 tests) proving no
  `REJECTED` anywhere (key or value), transition-map keys exactly match
  the enum's value set, every transition target is a known status, the
  table matches plan.md §9.2 verbatim, terminal statuses have empty
  transition sets, and every value is a genuine `frozenset`.

Verified acceptance for every task with runtime evidence, not just
static reading: imported the full module graph
(`modules.installments.*`) inside the running API container with zero
circular-import errors; exercised all 9 exceptions live, printing
`.code`/`.http_status` for each and confirming exact matches to plan.md
§22's table (`FEATURE_DISABLED`/403, `PERIOD_LOCKED`/422,
`SELF_APPROVAL_NOT_ALLOWED`/403, `IDEMPOTENCY_PAYLOAD_MISMATCH`/409 and
the alternate `IDEMPOTENCY_UNEXPECTED_STATE` code, `NOT_FOUND`/404,
`DEGENERATE_SCHEDULE`/422, generic `CONFLICT`/409 ×3); ran T020's test
file (7/7 passed); cross-checked `INSTALLMENTS_PERMISSIONS`' 16 codes
are all present in `PERMISSION_BY_CODE` with zero duplicates against the
full 72-entry `INITIAL_PERMISSIONS`; and — the strongest single piece of
Phase 1 evidence — dynamically loaded migration 071's own
`_ROLE_GRANTS` dict at runtime and asserted **exact set equality**
(not just counts) between it and `DEFAULT_ROLE_PERMISSIONS`'
Installments-scoped grants for every one of the 8 system roles,
confirming the constants a **new** company will be seeded with are
byte-for-byte identical to what migration 071 backfills onto **existing**
companies — zero drift between the two code paths.

Ran the full pre-existing `users_roles` unit-test suite (175 passed) and
broader `users_roles`/`companies` integration + security regression
(234 passed) since `users_roles/constants.py` is a widely-shared file —
zero regressions. Confirmed live API container health (200,
`database: ok`) after every incremental file change (the container's
`WatchFiles` reload-on-change + auto-migrate hook, the same mechanism
observed during Phase 0, restarted cleanly on every edit with no startup
errors). `ruff check` clean on every new/modified file.

Full diff review (`git status`/`git diff --stat`) confirmed only
Phase-1-scoped files changed: the new `backend/modules/installments/`
tree (no `models/`/`repositories/`/`services/` — correctly deferred),
`backend/modules/users_roles/constants.py` (+225/-1, purely additive),
5 new empty test-directory packages, and `tasks.md`'s checkboxes. No
future-phase leakage found.

## Outcome

- ✅ Impact: Phase 1 (T012-T020) complete. `backend/modules/installments`
  imports cleanly; all 16 `installments.*` permission codes exist in
  `INITIAL_PERMISSIONS`; per-role default grants for every system role
  are proven byte-identical to migration 071's existing-tenant backfill;
  the full 9-exception hierarchy covers every plan.md §22 failure mode
  with the exact mandated codes/HTTP statuses; the lifecycle transition
  table is proven `REJECTED`-free and closed over the enumerated status
  set.
- 🧪 Tests: `test_lifecycle_transitions_table.py` — 7 passed. Regression:
  `users_roles` unit — 175 passed; `users_roles`/`companies`
  integration+security — 234 passed. `ruff check` — all checks passed.
- 📁 Files: 8 new files under `backend/modules/installments/`
  (+ `schemas/__init__.py`), 1 modified shared file
  (`users_roles/constants.py`), 5 new test-package `__init__.py` files +
  1 new test file, `tasks.md` checkbox update.
- 🔁 Next prompts: Phase 2 (Configuration & Plans, T021-T042) — tenant
  policy configuration, plan templates, module entitlement wiring — not
  started, per the master prompt's explicit stop rule.
- 🧠 Reflection: Two modules (CRM, Accounting) independently arrived at
  the same "duplicate the permission catalogue in both the module's own
  constants.py and users_roles/constants.py, never import across" design
  — confirmed by grep, not assumption — which resolved what would
  otherwise have been an ambiguous design choice for T016. When a
  repository convention is this consistent across independently-built
  modules, it's a stronger signal than any single module's docstring
  alone, and worth verifying by grep rather than trusting one example.

## Evaluation notes (flywheel)

- Failure modes observed: none — no defects found this phase.
- Graders run and results (PASS/FAIL): unit test suite — PASS (7/7 new,
  175/175 + 234/234 regression); ruff — PASS; runtime exception/
  permission-grant cross-checks — PASS (exact matches, zero mismatches).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): none needed — Phase 1 closed
  cleanly on the first pass.
