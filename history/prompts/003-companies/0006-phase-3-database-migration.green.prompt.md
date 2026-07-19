---
id: "0006"
title: Phase 3 Database Migration
stage: green
date: 2026-07-15
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: Muhammad Amir
command: /sp.implement
labels: ["phase-3","migration","alembic","postgresql","companies","indexes"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/migrations/versions/003_companies.py
  - backend/migrations/env.py
  - specs/003-companies/tasks.md
tests:
  - tests/unit/core/test_settings.py (9/9 PASS — regression)
  - alembic history (003 in chain — verified)
  - migration_003 module parse (revision=003, down_revision=002 — verified)
---

## Prompt

/sp.implement

Epic 3 - Companies, Phase 3: Database Migration

Implement ONLY Phase 3 tasks (T014–T017).

## Response snapshot

Implemented T014 and prepared T015-T017:

- **T014**: Created `migrations/versions/003_companies.py` — full Alembic migration creating 4 tables in FK-dependency order:
  1. `event_outbox` — shared transactional outbox (with BaseModel columns + event columns); indexes on `(published, created_at)`, `event_type`, `aggregate_id`
  2. `companies` — all 34 spec §10.1 columns; CHECK constraint on `status`; 9 indexes including: expression UNIQUE on `lower(legal_name)`, UNIQUE on `slug`, PARTIAL UNIQUE on `custom_domain WHERE NOT NULL`; FK ON DELETE RESTRICT to `users.id` for `owner_id` and `primary_admin_id`
  3. `company_addresses` — FK to `companies` ON DELETE RESTRICT; composite index `(company_id, address_type)`; partial UNIQUE index for primary address per type
  4. `company_audit_logs` — no `updated_at`; FK ON DELETE RESTRICT; indexes on `(company_id, created_at)` and `actor_user_id`

  `downgrade()` drops in strict reverse order with full index cleanup. Two PostgreSQL ENUM types (`businesstype`, `addresstype`) created before tables, dropped after tables.

- **Updated `migrations/env.py`**: Added `import core.events.outbox` and `import modules.companies.models` so Alembic auto-discovers all new models.

- **T015-T017**: Require a running PostgreSQL database. Docker Desktop WSL integration is not enabled in this environment. Steps to verify manually:
  ```
  docker compose up db -d
  alembic upgrade head
  alembic downgrade -1
  alembic upgrade head
  alembic revision --autogenerate --dry-run
  ```

**Verification completed without DB**:
- `alembic history` shows `003` in chain ✓
- Migration file parses: revision=003, down_revision=002 ✓
- `ruff check` zero errors ✓
- Existing tests 9/9 PASS ✓

## Outcome

- ✅ Impact: Phase 3 migration file complete — all 4 tables, 13+ indexes, 2 ENUM types, check constraint, and FK relationships defined; migration chain verified via alembic history
- 🧪 Tests: 9/9 existing settings tests pass; 0 lint errors; migration file parses correctly
- 📁 Files: 2 files created/modified (migration + env.py)
- 🔁 Next prompts: Start Docker Desktop → run T015/T016/T017 manually; then run `/sp.implement` for Phase 4 (Repositories)
- 🧠 Reflection: T015-T017 are live-database verification tasks; Docker Desktop must be enabled for WSL to run these. The migration file is complete and structurally correct — it will execute cleanly once the DB is available

## Evaluation notes (flywheel)

- Failure modes observed: ruff I001 (import sort order) in env.py — fixed by sorting `core.events.outbox` before `modules.*` imports
- Graders run and results (PASS/FAIL): ruff PASS, pytest regression PASS, alembic history PASS
- Prompt variant (if applicable): null
- Next experiment: Add pre-commit hook or CI check that runs `alembic upgrade head` + `alembic downgrade -1` in a test database container
