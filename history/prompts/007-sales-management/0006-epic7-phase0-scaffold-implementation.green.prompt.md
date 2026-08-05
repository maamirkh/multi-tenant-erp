---
id: "0006"
title: "Epic 7 Phase 0 Scaffold Implementation"
stage: green
date: 2026-07-31
surface: agent
model: claude-opus-4-6
feature: 007-sales-management
branch: 007-sales-management
user: shehla83
command: /sp.implement
labels: ["sales", "phase0", "scaffold", "foundation", "epic7"]
links:
  spec: specs/007-sales-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/sales/__init__.py
  - backend/modules/sales/constants.py
  - backend/modules/sales/dependencies.py
  - backend/modules/sales/router.py
  - backend/modules/sales/events/__init__.py
  - backend/modules/sales/models/__init__.py
  - backend/modules/sales/models/master.py
  - backend/modules/sales/models/feature_flag.py
  - backend/modules/sales/repositories/__init__.py
  - backend/modules/sales/repositories/master.py
  - backend/modules/sales/repositories/feature_flag_repository.py
  - backend/modules/sales/schemas/__init__.py
  - backend/modules/sales/schemas/base.py
  - backend/modules/sales/schemas/master.py
  - backend/modules/sales/services/__init__.py
  - backend/modules/sales/services/sequence_service.py
  - backend/modules/sales/services/feature_flag_service.py
  - backend/modules/sales/services/master_data_service.py
  - backend/migrations/versions/025_sales_foundation.py
  - backend/api/v1/router.py
  - backend/tests/conftest.py
  - backend/tests/unit/modules/sales/test_constants.py
  - backend/tests/unit/modules/sales/test_events.py
  - backend/tests/unit/modules/sales/test_master_data.py
  - backend/tests/unit/modules/sales/test_sequence_service.py
  - backend/tests/integration/repositories/sales/test_phase0_repositories.py
  - backend/tests/integration/api/v1/sales/test_phase0_api.py
  - frontend/src/app/(protected)/(sales)/layout.tsx
  - frontend/src/app/(protected)/(sales)/settings/page.tsx
  - frontend/src/app/(protected)/(sales)/settings/categories/page.tsx
  - frontend/src/lib/api/sales.ts
tests:
  - backend/tests/unit/modules/sales/test_constants.py (15 passed)
  - backend/tests/unit/modules/sales/test_events.py (9 passed)
  - backend/tests/unit/modules/sales/test_master_data.py (16 passed)
  - backend/tests/unit/modules/sales/test_sequence_service.py (6 passed)
  - backend/tests/integration/repositories/sales/test_phase0_repositories.py (12 passed)
  - backend/tests/integration/api/v1/sales/test_phase0_api.py (10 passed)
---

## Prompt

/sp.implement — Epic 7 Sales Management, Phase 0: Module Scaffold & Cross-Cutting Foundation. Implement all 31 tasks (T001-T031) from tasks.md following Engineering Constitution, spec.md, plan.md exactly. Maintain compatibility with Epics 0-6. Production-ready code, no TODOs, no placeholders.

## Response snapshot

Implemented all 31 Phase 0 tasks for Epic 7 Sales Management. Created the complete sales module scaffold following the established purchase module patterns from Epic 6.

**Backend (27 files):**
- Module skeleton: `__init__.py`, constants (38 permissions, 14 feature flags, 5 document types), events (SalesDomainEvent + InProcessEventBus), base repository, base schemas
- 6 ORM models: CustomerCategory, CustomerGroup, SalesPaymentTerm, SalesReasonCode, SalesSequence, SalesConfiguration + SalesFeatureFlag
- 5 repositories with code-unique-per-company queries, active filters, tenant isolation
- 7 services: CategoryService, GroupService, PaymentTermService, ReasonCodeService, ConfigurationService (get_or_create), SequenceService (SELECT FOR UPDATE), FeatureFlagService
- DI factory with all repo/service dependencies
- Full API router: health, feature flags, categories CRUD, groups CRUD, payment terms CRUD, reason codes CRUD, configuration get/update
- Alembic migration 025_sales_foundation creating 7 tables
- conftest.py updated to import sales models for SQLite test DB

**Frontend (4 files):**
- Sales layout, API client with typed interfaces, settings pages with tabbed management

**Tests (68 total, all passing):**
- 46 unit tests: constants, events, schemas, sequence service
- 12 repository integration tests: CRUD, uniqueness, tenant isolation
- 10 API integration tests: health, categories, groups, terms, codes, flags, configuration

**Key fixes during testing:**
- Fixed `get_multi` → `list` (base repo method name mismatch)
- Fixed UUID handling for SQLite test DB (UUID objects vs strings)
- Fixed API tests to use `create_test_user` + login pattern matching purchase module

## Outcome

- ✅ Impact: Complete Phase 0 foundation for Epic 7 Sales Management — all 31 tasks implemented and verified
- 🧪 Tests: 68/68 passed (46 unit + 12 repo integration + 10 API integration)
- 📁 Files: 31 created, 2 modified (api/v1/router.py, tests/conftest.py)
- 🔁 Next prompts: Phase 1 Customer Master implementation (T032-T061)
- 🧠 Reflection: Pattern reuse from Epic 6 purchase module accelerated implementation. Key learning: SQLite test DB requires UUID objects (not strings) for Uuid(as_uuid=True) columns. Docker compose DB service had stale container state but API container worked for test execution.

## Evaluation notes (flywheel)

- Failure modes observed: get_multi vs list method name mismatch; str vs UUID for SQLite; Docker compose stale container reference for DB service
- Graders run and results (PASS/FAIL): All 68 tests PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
