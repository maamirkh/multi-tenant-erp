---
id: "0004"
title: Phase 1 Project Preparation
stage: green
date: 2026-07-15
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: Muhammad Amir
command: /sp.implement
labels: ["phase-1","infrastructure","minio","s3","events","outbox","companies","settings"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - docker-compose.yml
  - .env.example
  - backend/core/config/settings.py
  - backend/core/events/__init__.py
  - backend/core/events/outbox.py
  - backend/core/events/relay.py
  - backend/core/storage/__init__.py
  - backend/core/storage/s3_client.py
  - backend/modules/companies/__init__.py
  - backend/modules/companies/models/__init__.py
  - backend/modules/companies/repositories/__init__.py
  - backend/modules/companies/services/__init__.py
  - backend/modules/companies/schemas/__init__.py
  - backend/tests/fixtures/company_fixtures.py
  - specs/003-companies/tasks.md
tests:
  - tests/unit/core/test_settings.py (9/9 PASS)
---

## Prompt

/sp.implement

Epic 3 - Companies, Phase 1: Project Preparation

Implement ONLY Phase 1 tasks (T001–T008).

## Response snapshot

Implemented all 8 Phase 1 tasks:

- **T001**: Added MinIO service to `docker-compose.yml` (ports 9000/9001, `minio_data` volume, healthcheck, `server /data --console-address :9001` command)
- **T002**: Added Storage and Companies env vars to `.env.example` (`STORAGE_BACKEND`, `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`, `COMPANY_LIMIT`, `COMPANY_LOGO_MAX_BYTES`, `COMPANY_DELETION_RETENTION_DAYS`, `LOGO_RETENTION_DAYS`)
- **T003**: Added all new Pydantic settings fields to `settings.py` (storage + companies business rules). `S3_ACCESS_KEY`/`S3_SECRET_KEY` given `minioadmin` defaults so existing tests don't regress
- **T004**: Created `core/events/__init__.py` and `core/events/outbox.py` — `OutboxRecord` model (inherits `BaseModel`) + `EventOutboxRepository` with append-only `create()` method
- **T005**: Created `core/events/relay.py` — stub `relay_pending_events()` that marks unpublished records published; no actual message bus delivery
- **T006**: Created `core/storage/__init__.py` and `core/storage/s3_client.py` — abstract `StorageClient` ABC + `S3StorageClient` via `boto3`
- **T007**: Created full `modules/companies/` tree: `companies/`, `models/`, `repositories/`, `services/`, `schemas/` — all empty `__init__.py` stubs
- **T008**: Created `tests/fixtures/company_fixtures.py` — `make_company_data()`, `make_address_data()`, `make_settings_data()` pure data factory functions

**Checkpoint 1 results**: `ruff check` zero errors; `pytest tests/unit/core/test_settings.py` 9/9 PASS; all modules import cleanly.

## Outcome

- ✅ Impact: Phase 1 complete — MinIO infrastructure, transactional outbox, S3 storage client, companies module skeleton, and company test data factories all established
- 🧪 Tests: 9/9 existing settings tests pass; 0 regressions; 0 lint errors
- 📁 Files: 14 files created/modified
- 🔁 Next prompts: Run `/sp.implement` for Phase 2 (Database Models — T009–T013)
- 🧠 Reflection: `S3_ACCESS_KEY`/`S3_SECRET_KEY` made optional with dev defaults to maintain backwards compatibility with existing test `_BASE` dict pattern

## Evaluation notes (flywheel)

- Failure modes observed: Initially defined `S3_ACCESS_KEY` and `S3_SECRET_KEY` as required (`...`) which broke 7 existing tests — fixed by providing `minioadmin` defaults
- Graders run and results (PASS/FAIL): ruff PASS, pytest settings PASS
- Prompt variant (if applicable): null
- Next experiment: Consider adding settings integration tests for the new Epic 3 fields
