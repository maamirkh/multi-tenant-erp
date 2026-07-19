---
id: "0019"
title: Phase 15 Performance Validation
stage: green
date: 2026-07-16
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: shehla83
command: /sp.implement
labels: ["phase-15","performance","backend","python","pytest","seed","companies","explain-analyze"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/scripts/seed_companies.py
  - backend/tests/performance/companies/__init__.py
  - backend/tests/performance/companies/test_company_read_performance.py
  - backend/tests/performance/companies/test_company_list_performance.py
  - specs/003-companies/quickstart.md
  - specs/003-companies/tasks.md
tests:
  - backend/tests/performance/companies/test_company_read_performance.py (2 tests — all pass)
  - backend/tests/performance/companies/test_company_list_performance.py (2 tests — all pass)
  - Full backend suite: 561/562 pass (1 pre-existing failure: test_settings_default_debug_is_false)
---

## Prompt

/sp.implement — Epic 3 Companies, Phase 15: Performance Validation (T107–T110)

## Response snapshot

**T107** — Created `backend/scripts/seed_companies.py`:
- Inserts 10,000 company rows via `psycopg2.cursor.executemany()` in 500-row chunks
- Runs in 5.2 seconds (well under 60s target)
- Idempotent (checks existing count before inserting)
- Varied statuses (pending_setup 20%, active 60%, inactive 20%), 30 countries, 20 currencies
- Bug fixed: SQLAlchemy `text()` with named params conflicted with `::businesstype` cast syntax — switched to raw psycopg2 cursor with `%s` style params and `executemany()`

**T108** — Created `backend/tests/performance/companies/test_company_read_performance.py`:
- Measures GET /api/v1/companies/{id} p95 over 50 iterations: **16.8ms** (threshold 200ms) ✓
- Measures PATCH /api/v1/companies/{id} p95 over 50 iterations: **28.9ms** (threshold 500ms) ✓
- Seeds 200 companies via ORM (`Company` model instances) into in-memory SQLite test DB
- Uses UUID-prefixed slugs to avoid UNIQUE constraint collisions across test runs

**T109** — Created `backend/tests/performance/companies/test_company_list_performance.py`:
- Measures GET /companies/admin/companies p95 over 50 iterations: **12.7ms** (threshold 500ms) ✓
- Measures GET /companies/admin/companies?search=perf p95: **14.3ms** (threshold 1000ms) ✓
- Overrides `require_super_admin` dependency via `app.dependency_overrides` since JWT always returns `roles=[]` (Epic 4 RBAC not yet implemented)

**T110** — EXPLAIN ANALYZE run against PostgreSQL 16 with 10,000 rows:
- `get_by_id` → `pk_companies` PK Index Scan (0.09ms execution) ✓
- `list_by_owner` → `ix_companies_owner_id` Index Scan (3.7ms execution) ✓
- `exists_by_name` → `ix_companies_lower_legal_name` expression Index Scan (0.2ms) ✓
- `list_all_active` → `ix_companies_status` Index Scan (3.0ms) ✓
- `audit_log_by_company` → `ix_company_audit_logs_company_id` Index Scan (0.06ms) ✓
- All results documented in `specs/003-companies/quickstart.md §10`
- Quickstart also updated with seed script usage (§8) including idempotency + reset instructions

**Bugs fixed during implementation:**
- SQLAlchemy `text()` param placeholders conflict with `::cast` syntax (`:name::type` → psycopg2 parse error). Fixed by using raw psycopg2 cursor `executemany()` with `%s` positional params.
- `Uuid(as_uuid=True)` stores as BLOB in SQLite; raw SQL string inserts create TEXT entries that don't match ORM SELECT comparisons. Fixed by using ORM `Company` model instances for test fixtures.
- Predictable slugs (`perf-read-0000`) caused UNIQUE constraint failures across test methods sharing the session-scoped SQLite engine. Fixed by UUID-prefixed slugs per fixture invocation.
- `scope="class"` fixtures cannot depend on `function`-scoped fixtures (pytest ScopeMismatch). Fixed by using function scope.
- `require_super_admin()` returns a new inner function each call; `dependency_overrides` keys on that function instance. Used `app.dependency_overrides` cleanup in `finally` block.

## Outcome

- ✅ Impact: Phase 15 complete — all performance NFRs pass; all 5 critical queries confirmed using index scans with 10,000 rows
- 🧪 Tests: 4 new performance tests pass; Full backend: 561/562 pass (1 pre-existing env issue)
- 📁 Files: 4 files created, 1 modified (quickstart.md)
- 🔁 Next prompts: Phase 16 (Security Review — T111–T116)
- 🧠 Reflection: SQLAlchemy text() parameter names conflict with PostgreSQL `::cast` syntax — use raw psycopg2 cursor for insert scripts with custom enum/JSONB casts. Uuid(as_uuid=True) stores as BLOB in SQLite, making raw SQL SELECT comparisons fail — always use ORM models for test data insertion. session-scoped SQLite engine means slug uniqueness must be enforced per test run even when transactions roll back (SQLite rollback doesn't always clean index state between function-scoped sessions sharing the same engine).

## Evaluation notes (flywheel)

- Failure modes observed: text() param vs ::cast conflict; Uuid BLOB/TEXT SQLite mismatch; slug UNIQUE collisions across tests; scope mismatch (class vs function)
- Graders run and results (PASS/FAIL): pytest 561/562 PASS (1 pre-existing), performance tests 4/4 PASS, EXPLAIN ANALYZE 5/5 Index Scan PASS
- Prompt variant (if applicable): null
- Next experiment: null
