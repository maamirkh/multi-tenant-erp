---
id: 0024
title: AI ERP Readiness Phase 17 Implementation
stage: green
date: 2026-08-14
surface: agent
model: claude-sonnet-5
feature: 008-accounting-finance
branch: 008-accounting-finance
user: Muhammad Amir
command: /sp.implement
labels: ["accounting", "ai-readiness", "phase-17", "feature-flags", "anomaly-detection"]
links:
  spec: specs/008-accounting-finance/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/accounting/models/ai.py
  - backend/modules/accounting/models/__init__.py
  - backend/migrations/versions/050_accounting_ai_readiness.py
  - backend/modules/accounting/repositories/ai.py
  - backend/modules/accounting/repositories/fiscal.py
  - backend/modules/accounting/events/ai_events.py
  - backend/modules/accounting/schemas/ai.py
  - backend/modules/accounting/services/ai_service.py
  - backend/modules/accounting/exceptions.py
  - backend/modules/accounting/dependencies.py
  - backend/modules/accounting/router.py
  - backend/tests/integration/api/v1/accounting/test_ai_readiness.py
  - specs/008-accounting-finance/contracts/events.md
  - specs/008-accounting-finance/tasks.md
tests:
  - backend/tests/integration/api/v1/accounting/test_ai_readiness.py (9 tests)
  - Full accounting suite regression (unit + integration + API + performance + security)
    565 passed, 1 flaky (pre-existing T270 timing test, confirmed passes standalone), 0
    caused by this phase's changes
---

## Prompt

You are the Principal Software Architect, Chief Financial Systems Architect,
Enterprise SaaS Architect and Senior Staff Engineer for DevSphere ERP.

Implement ONLY the following phase from Epic 8 exactly as defined in the approved:

• Engineering Constitution
• Epic 8 spec.md
• Epic 8 plan.md
• Epic 8 tasks.md

Epic: Epic 8 – Accounting & Finance
Phase: 17
Phase Name: "AI ERP Readiness (US16)"

Implement ONLY this phase. Do NOT implement any future phases.

[Full instruction set covered: pre-implementation review of constitution/spec/plan/tasks,
architecture rules (modular monolith, clean architecture, DDD, repository pattern, service
layer, DI, SOLID, DRY, KISS, feature flags, soft delete, audit logging, multi-tenant SaaS,
RBAC, company isolation), accounting principles (double-entry, balanced journal validation,
immutable ledger, auditability, financial integrity, period integrity, company financial
isolation), database migration requirements, GL posting integrity requirements, API
conventions, frontend UX requirements, testing requirements, validation requirements
(formatting, linting, type checking, tests, migrations, financial validation), Docker
verification, financial validation, and a structured output report. Full verbatim text
preserved in the session transcript; abbreviated here per PHR convention for a
fully-specified, multi-thousand-word command.]

## Response snapshot

Implemented Phase 17 (T303–T309) exactly as scoped in tasks.md, after verifying Phases
1–16 were already complete (0 incomplete tasks above Phase 17 in tasks.md).

- **T303**: Verified `JournalPostedEvent`'s payload against the 6 required ML fields.
  4 present (amount via total_debit/credit_base, time_of_day derivable from occurred_at,
  user_id via base envelope's actor_id, posting_source). 2 real gaps documented in
  contracts/events.md: `reference` is absent from the event payload (worked around in the
  new read-model, not retrofitted into the fire-and-forget event itself — out of this
  read-only phase's scope), and `account_type` is structurally a per-line attribute that
  can't be added to an entry-level event without a shape change.
- **T304**: `GET /events/stream?from={date}` — paginated POSTED journal history shaped for
  ML training data, built on the existing `JournalEntryRepository.search()`.
- **T305/T306**: `GET /ai/pl-history?periods=N` / `GET /ai/cashflow-history?periods=N` —
  iterate the last N fiscal periods (new `FiscalPeriodRepository.list_recent()`, cross-year,
  chronological) through the existing `FinancialStatementService.get_pl()`/`get_cash_flow()`.
- **T307**: `POST /ai/anomaly-report` — new `AccountingAnomalyFlag` model (mutable,
  `TenantBaseModel`-based — a review record, not an append-only ledger row) + migration 050;
  validates every referenced journal_entry_id exists and is POSTED (404 otherwise) before
  flagging; publishes `accounting.anomaly.detected` per flag (added to contracts/events.md).
- **T308**: `schemas/ai.py` — `GLEventStreamRow`, `PLHistoryPeriod`/`PLHistoryResponse`,
  `CashFlowHistoryPeriod`/`CashFlowHistoryResponse`, `AnomalyReportRequest`,
  `AnomalyFlagResponse`.
- **T309**: All four endpoints hard-gated by `accounting.ai.enabled` (already registered in
  Phase 1's flag catalogue, default OFF) via a new `AccountingFeatureDisabledError`
  (403, code `FEATURE_DISABLED`) — mirrors the exact convention already established by
  Inventory's `InventoryFeatureDisabledError`, distinct from RBAC's
  `ApprovalPermissionDeniedError` and the business-rule-level `WHTNotEnabledError` (422).
  9 new tests: flag-disabled → 403 on all 4 endpoints, flag-enabled → 200/201 with real
  data, ML-field content assertions, `from` filter correctness, unknown-journal-entry 404,
  cross-tenant isolation, 401 enforcement.

Docker/financial verification: applied migration 050 against the already-running live
PostgreSQL 16 container (hot-reloaded via the existing `./backend:/app` volume mount,
confirmed via `alembic current` → `050 (head)` and `\d accounting_anomaly_flags`); verified
zero startup exceptions in API container logs; confirmed all 4 new routes registered live
via `/openapi.json`. Did not attempt a full live curl business-flow smoke test — no public
user-registration endpoint exists in this API (matches the exact precedent noted in this
epic's own Phase 3 PHR, T088: business-flow verification is covered by the SQLite-backed API
test suite running the identical FastAPI app/DI wiring, not a live curl script requiring a
seed user that doesn't exist in a fresh database).

## Outcome

- ✅ Impact: Phase 17 fully implemented — GL event stream, P&L/cash flow forecasting history,
  and an anomaly-flagging capture point are all live behind a single, already-existing
  feature flag, with the one real gap (event `reference` field) explicitly documented rather
  than silently left unverified.
- 🧪 Tests: 9 new tests, all passing; full accounting regression suite 565 passed / 1
  pre-existing flaky timing test (confirmed passes standalone, unrelated to this phase) / 0
  failures caused by this work. ruff check clean on all new/changed files; mypy clean (the
  only errors mypy reports across the whole router.py file are a pre-existing, repo-wide
  `body: X = ...` FastAPI-convention false positive present on every endpoint, not something
  this phase introduced).
- 📁 Files: 1 new model, 1 new migration, 1 new repository, 1 new event class, 1 new schema
  file, 1 new service, 4 new router endpoints, 2 new exception classes, 1 new test file (9
  tests); contracts/events.md and tasks.md updated.
- 🔁 Next prompts: Phase 17 is complete and the epic is ready for Phase 18 (Testing,
  Validation & Documentation) — not started, per the "stop after completing the selected
  phase" instruction.
- 🧠 Reflection: Removed a speculative `list_all()` method from the new anomaly-flag
  repository after writing it reflexively to match neighboring repository files' shape —
  caught during self-review that no endpoint or test actually called it, which would have
  been unused, premature abstraction. Worth flagging as a pattern to watch for: matching a
  file's "usual shape" isn't sufficient justification for a method nothing calls.

## Evaluation notes (flywheel)

- Failure modes observed: One test failure during authoring — cash flow history returned
  "0" instead of "700.000000" because the test's Cash account fixture didn't set
  `is_cash_account=True`, which `GLReportRepository.cash_balance_query()` requires to
  recognize a cash/bank account; one-line fixture fix.
- Graders run and results (PASS/FAIL): ruff check PASS, mypy PASS (no new errors), pytest
  PASS (9/9 new + full accounting suite), live Docker/Postgres migration apply PASS, live
  route registration PASS (verified via /openapi.json).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
