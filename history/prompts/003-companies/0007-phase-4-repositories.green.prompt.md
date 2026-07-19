---
id: "0007"
title: Phase 4 Repositories
stage: green
date: 2026-07-15
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: Muhammad Amir
command: /sp.implement
labels: ["phase-4","repositories","companies","integration-tests","sqlite","tenant-isolation"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/companies/repositories/company_repository.py
  - backend/modules/companies/repositories/company_address_repository.py
  - backend/modules/companies/repositories/company_audit_log_repository.py
  - backend/modules/companies/repositories/__init__.py
  - backend/tests/integration/repositories/companies/__init__.py
  - backend/tests/integration/repositories/companies/test_company_repository.py
  - backend/tests/integration/repositories/companies/test_company_address_repository.py
  - backend/tests/conftest.py
  - backend/modules/companies/models/company.py
  - specs/003-companies/tasks.md
tests:
  - tests/integration/repositories/companies/test_company_repository.py (22 tests PASS)
  - tests/integration/repositories/companies/test_company_address_repository.py (11 tests PASS)
  - Full regression: 338 tests PASS
---

## Prompt

/sp.implement

Epic 3 - Companies, Phase 4: Repositories

Implement ONLY Phase 4 tasks (T018–T022).

## Response snapshot

Implemented T018–T022 (all 5 tasks):

- **T018**: `CompanyRepository` — standalone (does NOT inherit `BaseRepository` since `Company` is `BaseModel`, not `TenantBaseModel`). Methods: `create`, `update`, `soft_delete`, `restore`, `get_by_id`, `get_by_id_active`, `get_by_slug`, `get_by_legal_name`, `exists_by_name`, `exists_by_slug`, `list_by_owner`, `list_all` (paginated, with status/country/search/include_deleted filters).

- **T019**: `CompanyAddressRepository` — every read query scoped to `WHERE company_id = :company_id` for tenant isolation. Methods: `create`, `update`, `delete`, `get_by_id`, `list_by_company`, `get_primary_by_type`.

- **T020**: `CompanyAuditLogRepository` — append-only. `update()` and `delete()` both raise `NotImplementedError`. Methods: `create`, `list_by_company` (paginated with action/actor filters).

- **T021**: `test_company_repository.py` — 22 integration tests covering create, get_by_id, get_by_slug, exists_by_name (case-insensitive), exists_by_slug, soft_delete, restore, list_by_owner, list_all (pagination + include_deleted).

- **T022**: `test_company_address_repository.py` — 11 integration tests covering create, get_by_id with correct/wrong company_id (tenant isolation), list_by_company, update, delete, get_primary_by_type.

**Bug fixes discovered and applied during Phase 4**:
1. `conftest.py`: Added imports for `core.events.outbox`, `modules.auth.models`, `modules.companies.models` so `Base.metadata.create_all()` finds the `users` table referenced by `companies.owner_id` FK.
2. `company.py`: Changed three `server_default=text("'{}'::jsonb")` to `server_default=text("'{}'")`  — SQLite doesn't understand `::jsonb` cast syntax; PostgreSQL accepts bare `'{}'` on JSONB columns.
3. `company_fixtures.py`: Changed `owner_id` from `str(uuid.uuid4())` to `uuid.uuid4()` (UUID object) — `Uuid(as_uuid=True)` with SQLite calls `.hex` on the value, which fails for strings.

## Outcome

- ✅ Impact: Phase 4 complete — 3 repository classes + 2 test files + `__init__.py` re-export; 33 new integration tests; 3 SQLite-compatibility bug fixes in existing files
- 🧪 Tests: 33/33 new integration tests PASS; full regression 338/338 PASS; 0 lint errors
- 📁 Files: 7 new files created, 3 existing files modified
- 🔁 Next prompts: Run `/sp.implement` for Phase 5 (Validators and Exceptions — T023–T025)
- 🧠 Reflection: SQLite compatibility issues surface reliably during integration tests: `::jsonb` cast syntax, `str` vs `UUID` objects for Uuid(as_uuid=True) columns, and missing FK-referenced tables in metadata. Fixing these at the source (model/fixture level) keeps the test infrastructure clean.

## Evaluation notes (flywheel)

- Failure modes observed: (1) `NoReferencedTableError` for `users` table — fixed by importing all models in conftest; (2) `unrecognized token ":"` from `'{}'::jsonb` server defaults — fixed by removing `::jsonb` cast; (3) `AttributeError: 'str' object has no attribute 'hex'` on UUID insert — fixed by using UUID objects in fixture
- Graders run and results (PASS/FAIL): ruff PASS, pytest 33/33 PASS, regression 338/338 PASS
- Prompt variant (if applicable): null
- Next experiment: Add a conftest-level `@pytest.fixture(scope="session", autouse=True)` that asserts `Base.metadata.tables.keys()` contains all expected table names, catching FK resolution failures early
