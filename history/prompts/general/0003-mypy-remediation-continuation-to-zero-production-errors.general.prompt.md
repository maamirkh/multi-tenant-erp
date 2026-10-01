---
id: 0003
title: MyPy remediation continuation to zero production errors
stage: refactor
date: 2026-09-08
surface: agent
model: claude-sonnet-5
feature: none
branch: fix/mypy-remediation
user: Muhammad Amir
command: continuation of repository-wide MyPy remediation
labels: ["mypy", "type-safety", "ci", "tech-debt", "remediation"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - backend/pyproject.toml
 - .github/workflows/backend.yml
 - backend/modules/**/*.py (production, ~40 files — see Final Report)
 - backend/tests/**/*.py (~280 files — see Final Report)
 - backend/migrations/versions/040-047_*.py
tests:
 - backend: mypy . (production: 0 errors, tests: 876 errors, down from 1909)
 - backend: poetry run pytest tests/unit tests/security (3765 passed, 0 failures, 82 pre-existing DB-connectivity errors)
 - backend: poetry run pytest tests/unit/modules/purchase tests/integration/api/v1/purchase (full pass)
 - backend: poetry run ruff check . / ruff format --check . (clean)
 - backend: app boot smoke test via `from main import create_app; create_app()` (OK)
---

## Prompt

The user's verbatim continuation instruction (abbreviated; full text preserved in conversation history):

"Continue the existing Pre-Epic-11 MyPy remediation... The first pass was useful but is NOT complete... Preferred target: MyPy = 0 errors... Priority 1: resolve ALL remaining first-party production errors before test typing... Priority 2: explicitly investigate every suspicious attr-defined/contract error before suppressing it (named: possible BankDetails attribute mismatch, and modules/sales/router.py's `SalesApprovalMatrixRead.__fields__` approval-matrix code)... Priority 3: cross-module contract audit (Sales↔Accounting, Purchase↔Accounting, Inventory↔Sales/Purchase, CRM↔Sales, Installments↔Sales, Installments↔Accounting, Platform Admin↔tenancy/entitlements)... Priority 4: tests, only after production reaches zero, preferred target tests = 0 too... Suppression Policy: no broad ignores, no file-wide ignores, no package exclusion, no Any flooding; any new ignore must have a specific error code and justification... Regression Requirements: mypy ., Ruff, full backend test suite, migrations validation, Docker/backend build... CI Goal: once MyPy is clean, make it a genuine blocking gate if the workflow supports it... Business/Security Safety: no semantic changes unless MyPy exposes a genuine runtime bug, in which case make the smallest tested correction and report it... Git: commit logically... Final Report must contain exact counts, root causes, genuine bugs discovered, cross-module findings, all config changes, all suppressions, full test results, CI-gate status, files changed, commits, remaining debt, explicit READY/NOT READY recommendation... STOP after remediation and validation. Do not create Epic 11 spec/plan/tasks/implementation."

## Response snapshot

Starting point: production 271 errors / tests 1911 errors (from the first pass's end state). Worked module-by-module through Purchase, Sales, Inventory, Auth, Platform Admin, Users/Roles, and Installments, applying root-cause fixes (see Final Report for the full catalogue): FastAPI `response_model` inference crash fix, `AccountingIntegrationGateway` Protocol-based typing (preserves the accounting.models import ban), sentinel-pattern (`EllipsisType`) typing for PATCH "not provided" params, `Mapped[float]`-over-`Numeric` → `Mapped[Decimal]` correction across Inventory's Stock/Alerts models, purchase/sales domain-event dataclass `UUID`→`str` field-type correction, `sum()` `Literal[0]` elimination via explicit `start=`, and class-level `list`/`dict` builtin-shadowing fixes via `import builtins`. Found and fixed two genuine, previously-undetected bugs: (1) `sales/router.py`'s `list_approval_matrices()` built a `result` list with `SalesApprovalMatrixRead.__fields__` (Pydantic-v1 metadata, not real rules) then discarded it and returned an unrelated, never-populated list — every tenant's approval-matrix rules silently returned empty; (2) `InvoiceService.export_pdf()`'s feature-flag check called `is_enabled(flag_key, company_id=company_id)` against a `(company_id, flag_key)`-ordered signature, always raising `TypeError`, silently swallowed by a bare `except Exception`, so the `sales.invoice_pdf_export` flag was never actually enforced. Both fixed with regression tests. Production reached exactly 0 MyPy errors. Continued into Priority 4 (not strictly required to start until production was clean) and reduced tests from 1909 → 876 via safe, root-cause, non-`Any`-flooding fixes (bare generic parameterization, `no-any-return` wrapping, a narrowly-justified `method-assign` override addition for `tests.*`, `Settings(**dict[str,...])` spread typing, `TestClient.app` → `cast(FastAPI, ...)`). Discovered and fixed a self-inflicted CRLF→LF line-ending corruption across 98 files caused by Python's `open().read()/write()` round-trip in batch-fix scripts (all restored to the repo's native CRLF). Discovered CI already runs `mypy .` unconditionally (explaining the earlier "mypy failure aside" merge tolerance); split it into a blocking production-only step (now safe to enable, 0 errors) and a non-blocking informational tests step. Full regression run: 3765+ tests passing, 0 new failures (2 stale hardcoded feature-flag-count assertions found and fixed as a direct consequence of adding `sales.invoice_pdf_export` to the catalogue), only the pre-existing real-Postgres-credential-mismatch environment gap remains (documented, unrelated to typing). Did not create any Epic 11 artifacts, per the explicit STOP instruction.

## Outcome

- ✅ Impact: Production first-party code (modules/, core/, api/, migrations/, scripts/) at 0 MyPy errors (from 4710 at the true start of remediation, 271 at this continuation's start). CI's MyPy step split so production regressions now hard-fail merges. Two genuine, previously-invisible business-logic bugs fixed with regression tests. Test-suite MyPy backlog cut more than half (1909 → 876), tracked as the one explicitly acknowledged remaining gap.
- 🧪 Tests: `pytest tests/unit tests/security` 3765 passed / 0 failed / 82 pre-existing env errors; targeted purchase/sales/inventory/auth/platform_admin/users_roles integration suites fully green; `ruff check .` and `ruff format --check .` clean; app boots via `create_app()`.
- 📁 Files: 325 files changed (production modules, tests, `backend/pyproject.toml`, `.github/workflows/backend.yml`); see Final Report message in conversation for the complete categorized list.
- 🔁 Next prompts: a dedicated "tests = 0 MyPy" follow-up pass (876 errors remaining, dominated by `attr-defined`/`arg-type`/`union-attr` from Mock-vs-real-class typing and duck-typed test-double classes vs. Protocols); real-Postgres test-credential provisioning fix (environment-level, unrelated to this remediation) so the ~90 DB-dependent tests can run in this sandbox.
- 🧠 Reflection: Root-cause pattern-hunting (grep for repeated shapes, fix the shared abstraction once) scaled far better than per-error patching across both production and test code. Two lessons cost real time: (1) Python's `open(...).read()/write()` text-mode round-trip silently normalizes CRLF→LF on this Windows-drive-backed repo — any multi-file batch script must round-trip in binary mode or restore line endings afterward; (2) declaring a FastAPI route's return type without `response_model=None` changes runtime behavior (Pydantic tries to build a schema from the annotation), not just static types — verified by booting the app after every router-typing change, which caught a real crash before it reached tests.

## Evaluation notes (flywheel)

- Failure modes observed: batch-script CRLF corruption (98 files, caught via `git diff --stat` sanity-checking, not proactively); one wrong assumption that adding `# type: ignore[arg-type]` on ORM-constructor keyword args would be necessary (mypy doesn't type-check declarative-model `__init__` kwargs at all, so the ignores were dead on arrival — caught via `unused-ignore`).
- Graders run and results (PASS/FAIL): mypy production = PASS (0 errors); ruff lint/format = PASS; full regression suite = PASS (0 unexpected failures); app-boot smoke test = PASS; Docker image build = NOT RUN (registry-credential access blocked in this sandbox, unrelated to code changes).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): triage the 381 test `attr-defined` errors by root cause cluster (Mock `.return_value`/`.assert_called*` access on real-class-typed attributes vs. genuine stale test/product mismatches) before attempting further bulk fixes, since the Mock-typing cluster has no clean mechanical fix short of per-site `cast(MagicMock, ...)` or restructuring test factories to return typed mocks directly.
