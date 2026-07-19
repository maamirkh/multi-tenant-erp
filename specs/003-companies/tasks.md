# Tasks: Epic 3 — Companies

**Branch**: `003-companies`
**Created**: 2026-07-15
**SSOT References**: [spec.md](./spec.md) | [plan.md](./plan.md)
**Status**: Ready for Implementation

---

## Format Legend

```
- [ ] [TaskID] [P?] [Story?] Description with exact file path
```

- `[P]` — Parallelizable: can run simultaneously with other `[P]` tasks in same phase
- `[US1]–[US6]` — User Story label (maps to spec.md Section 4)
- No story label — Foundational task (serves all stories)

## User Story Map

| Label | Story | Priority | Spec Reference |
|-------|-------|----------|---------------|
| US1 | Company Creation | P1 | spec.md §4 US1 |
| US2 | Company Profile Management | P1 | spec.md §4 US2 |
| US3 | Company Activation and Deactivation | P2 | spec.md §4 US3 |
| US4 | Company Soft Delete and Restore | P3 | spec.md §4 US4 |
| US5 | Company Settings Management | P2 | spec.md §4 US5 |
| US6 | Company Listing and Search (SuperAdmin) | P2 | spec.md §4 US6 |

---

## Phase 1: Project Preparation

**Objective**: Establish all shared infrastructure, Docker services, environment configuration, and module skeleton required before any company-specific code is written.

**Scope**: `core/events/`, `core/storage/`, `docker-compose.yml`, `.env.example`, module `__init__.py` files, MinIO service.

**Dependencies**: Epic 2 (Auth) merged and stable. Docker Compose running. No company business logic in this phase.

**Database Impact**: None.

**API Impact**: None.

**Frontend Impact**: None.

**Files Expected To Change**:
- `docker-compose.yml`
- `.env.example`
- `backend/core/events/__init__.py` (new)
- `backend/core/events/outbox.py` (new)
- `backend/core/storage/__init__.py` (new)
- `backend/core/storage/s3_client.py` (new)
- `backend/core/config/settings.py`
- `backend/modules/companies/__init__.py` (new, empty)
- `backend/modules/companies/models/__init__.py` (new, empty)
- `backend/modules/companies/repositories/__init__.py` (new, empty)
- `backend/modules/companies/services/__init__.py` (new, empty)
- `backend/modules/companies/schemas/__init__.py` (new, empty)

**Files That Must NOT Change**: All existing `modules/auth/` files. All existing `core/auth/` files. All existing migration files.

---

### Tasks

- [x] T001 Add MinIO service definition to `docker-compose.yml` with ports 9000/9001, `minio_data` named volume, health check, and startup command `server /data --console-address :9001`
- [x] T002 Add all new environment variables to `.env.example`: `STORAGE_BACKEND`, `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION`, `COMPANY_LIMIT`, `COMPANY_LOGO_MAX_BYTES`, `COMPANY_DELETION_RETENTION_DAYS`, `LOGO_RETENTION_DAYS` with placeholder values and inline comments
- [x] T003 Add all new settings fields to `backend/core/config/settings.py`: `storage_backend`, `s3_endpoint`, `s3_bucket`, `s3_access_key`, `s3_secret_key`, `s3_region`, `company_limit`, `company_logo_max_bytes`, `company_deletion_retention_days`, `logo_retention_days` using existing Pydantic settings pattern
- [x] T004 [P] Create `backend/core/events/__init__.py` and `backend/core/events/outbox.py` defining the `OutboxRecord` SQLAlchemy model (`id`, `event_type`, `aggregate_id`, `aggregate_type`, `payload`, `metadata`, `published`, `published_at`, `created_at`) and `EventOutboxRepository` with append-only `create()` method — no update or delete methods
- [x] T005 [P] Create `backend/core/events/relay.py` as a stub background relay: a function `relay_pending_events()` that queries `published=False` records, logs them, and marks `published=True` — implementation is a no-op stub; actual message bus delivery is deferred to a future epic
- [x] T006 [P] Create `backend/core/storage/__init__.py` and `backend/core/storage/s3_client.py` defining abstract `StorageClient` base class with methods `upload(file, key) -> str`, `delete(key) -> None`, `get_url(key) -> str`, and concrete `S3StorageClient` implementation using `boto3` pointing to the configured S3/MinIO endpoint
- [x] T007 Create the full `backend/modules/companies/` directory tree with empty `__init__.py` files in: `companies/`, `companies/models/`, `companies/repositories/`, `companies/services/`, `companies/schemas/` — no logic, only `__init__.py` stubs
- [x] T008 [P] Create `backend/tests/fixtures/company_fixtures.py` defining pytest factory fixtures: `make_company_data()` (dict with all required fields), `make_address_data()`, `make_settings_data()` — no database interaction yet, pure data factories

---

### Checkpoint 1

**Questions to Verify**:
- Does `docker compose up` start MinIO alongside the existing services without error?
- Is MinIO console accessible at `http://localhost:9001`?
- Does `python -c "from backend.core.storage.s3_client import S3StorageClient"` import without error?
- Does `python -c "from backend.core.events.outbox import OutboxRecord"` import without error?
- Does `python -c "from backend.core.config.settings import get_settings; s = get_settings()"` load new settings fields?

**Required Tests**: `pytest tests/unit/core/test_settings.py` must pass (existing test, must not regress). Run `ruff check backend/core/events/ backend/core/storage/` — zero lint errors.

**Expected Result**: All services start. New infrastructure modules import cleanly. Existing tests unaffected.

**Go / No-Go**: GO only if MinIO starts, all new modules import, and existing auth tests pass without regression.

---

**DO NOT IMPLEMENT in Phase 1**:
- Any company model, schema, service, or router
- Any database migration
- Any frontend code
- Any logo validation logic (module exists but no validation yet)
- The actual event relay to a message bus

---

## Phase 2: Database Models

**Objective**: Define all SQLAlchemy ORM models for the companies module. No database changes yet — models only.

**Scope**: `modules/companies/models/` package. All four model files and the `enums.py`.

**Dependencies**: Phase 1 complete. `core/database/models/base_model.py` (existing `BaseModel`).

**Database Impact**: None (models are Python classes — no DDL until Phase 3).

**API Impact**: None.

**Frontend Impact**: None.

**Files Expected To Change**:
- `backend/modules/companies/models/enums.py` (new)
- `backend/modules/companies/models/company.py` (new)
- `backend/modules/companies/models/company_address.py` (new)
- `backend/modules/companies/models/company_audit_log.py` (new)
- `backend/modules/companies/models/__init__.py`

**Files That Must NOT Change**: All existing auth models. `core/database/` files. Migration files.

---

### Tasks

- [x] T009 Create `backend/modules/companies/models/enums.py` defining three Python enums using `str, Enum`: `CompanyStatus` (`pending_setup`, `active`, `inactive`, `suspended`, `deleted`), `AddressType` (`registered`, `mailing`, `billing`, `shipping`), `BusinessType` (`sole_proprietor`, `partnership`, `llc`, `corporation`, `non_profit`, `other`)
- [x] T010 Create `backend/modules/companies/models/company.py` defining `Company` SQLAlchemy model inheriting `BaseModel`; all columns from spec.md §10.1: `legal_name`, `trade_name`, `slug`, `status` (VARCHAR with CHECK), `owner_id` (FK → users.id), `primary_admin_id` (FK → users.id, nullable), `email`, `phone_primary`, `phone_secondary`, `website`, `tax_number`, `registration_number`, `business_category`, `business_type`, `incorporation_date`, `default_currency`, `default_timezone`, `default_language`, `country`, `fiscal_year_start_month`, `date_format`, `number_format` (JSONB), `logo_url`, `logo_previous_url`, `brand_color_primary`, `brand_color_secondary`, `tagline`, `settings` (JSONB), `metadata` (JSONB), `subscription_id` (nullable), `custom_domain` (nullable), `deleted_at`, `deletion_reason`; use `Mapped[type]` and `mapped_column()` SQLAlchemy 2.x syntax throughout
- [x] T011 [P] Create `backend/modules/companies/models/company_address.py` defining `CompanyAddress` model inheriting `BaseModel`; columns: `company_id` (UUID FK → companies.id, ON DELETE RESTRICT), `address_type` (AddressType enum), `street_line_1`, `street_line_2` (nullable), `city`, `state_province` (nullable), `postal_code` (nullable), `country` (CHAR 2); `is_primary` (Boolean, default False); `__table_args__` with composite unique constraint on `(company_id, address_type)` where `is_primary=True`
- [x] T012 [P] Create `backend/modules/companies/models/company_audit_log.py` defining `CompanyAuditLog` model; columns: `id` (UUID PK), `company_id` (UUID FK → companies.id, ON DELETE RESTRICT), `actor_user_id` (UUID, nullable), `action` (VARCHAR 100), `before_state` (JSONB, nullable), `after_state` (JSONB, nullable), `ip_address` (INET type from SQLAlchemy's postgresql dialect, nullable), `user_agent` (TEXT, nullable), `request_id` (UUID, nullable), `metadata` (JSONB, nullable), `created_at` (TIMESTAMPTZ, NOT NULL, server_default=now()); NO `updated_at`; no `__init__` method that allows update — model is append-only by convention
- [x] T013 Update `backend/modules/companies/models/__init__.py` to re-export `Company`, `CompanyAddress`, `CompanyAuditLog`, `CompanyStatus`, `AddressType`, `BusinessType` so Alembic's `env.py` can discover all models via a single import

---

### Checkpoint 2

**Questions to Verify**:
- Do all model classes import without error: `from backend.modules.companies.models import Company, CompanyAddress, CompanyAuditLog`?
- Do all enum values match spec.md §2 (Terminology) exactly?
- Does `Company.__tablename__` equal `"companies"`?
- Does `CompanyAuditLog` have no `updated_at` column?
- Are all foreign key relationships using `ON DELETE RESTRICT`?

**Required Tests**: `python -m pytest tests/unit/modules/companies/ -k "model"` if model unit tests exist; otherwise `python -c "from backend.modules.companies.models import Company; print(Company.__table__.columns.keys())"` — all expected columns present. `ruff check backend/modules/companies/models/` — zero errors.

**Expected Result**: All models importable. All columns present. Alembic can discover models.

**Go / No-Go**: GO only if all models import cleanly and enum values are correct.

---

**DO NOT IMPLEMENT in Phase 2**:
- Database migration (Phase 3)
- Repository methods (Phase 4)
- Service logic (Phase 7)
- API routes (Phase 9)
- Frontend code (Phase 10+)
- Any business validation logic

---

## Phase 3: Database Migration

**Objective**: Create and verify the Alembic migration that creates all companies module tables with all indexes, unique constraints, and foreign keys.

**Scope**: Single migration file `003_companies.py`. Verification only — no application code changes.

**Dependencies**: Phase 2 complete. All models importable by Alembic's `env.py`. PostgreSQL running in Docker.

**Database Impact**: Creates `event_outbox`, `companies`, `company_addresses`, `company_audit_logs` tables. All indexes as specified in plan.md §9.5.

**API Impact**: None.

**Frontend Impact**: None.

**Files Expected To Change**:
- `backend/migrations/versions/003_companies.py` (new)
- `backend/migrations/env.py` (add companies models import if not already auto-discovered)

**Files That Must NOT Change**: Previous migration files (`001_`, `002_`). All model files.

---

### Tasks

- [x] T014 Create `backend/migrations/versions/003_companies.py` with Alembic migration; `upgrade()` creates tables in this order: (1) `event_outbox` table with all columns, (2) `companies` table with all columns, check constraint on `status`, case-insensitive expression index on `lower(legal_name)`, unique index on `slug`, all other indexes from plan.md §9.5 table, (3) `company_addresses` table with FK to `companies`, composite index on `(company_id, address_type)`, (4) `company_audit_logs` table with FK to `companies`, composite index on `(company_id, created_at)`, index on `actor_user_id`; `downgrade()` drops in reverse order: `company_audit_logs`, `company_addresses`, `companies`, `event_outbox`
- [ ] T015 Run `alembic upgrade head` against the development PostgreSQL instance and verify: all four tables exist, all indexes exist (query `pg_indexes`), all check constraints exist (query `pg_constraint`), all FK relationships exist with `ON DELETE RESTRICT` — **REQUIRES: Docker Desktop running (`docker compose up db`)**
- [ ] T016 Run `alembic downgrade -1` and verify all four tables are dropped cleanly, then run `alembic upgrade head` again to restore — confirms migration is fully reversible — **REQUIRES: Docker Desktop running**
- [ ] T017 Verify Alembic detects no pending auto-generated migrations: run `alembic revision --autogenerate --dry-run` and confirm output shows no changes (models match migration exactly) — **REQUIRES: Docker Desktop running**

---

### Checkpoint 3

**Questions to Verify**:
- Does `alembic upgrade head` complete with exit code 0?
- Does `alembic downgrade -1` complete with exit code 0?
- Does a second `alembic upgrade head` after downgrade succeed?
- Do all 13 indexes from plan.md §9.5 exist in `pg_indexes`?
- Does the `lower(legal_name)` expression index exist?
- Does the partial unique index on `custom_domain WHERE custom_domain IS NOT NULL` exist?

**Required Tests**: Manual psql verification of `\d companies`, `\d company_audit_logs`, `\d event_outbox`. Run `alembic history` — migration 003 shows in chain.

**Expected Result**: All tables, indexes, and constraints created. Migration is fully reversible.

**Go / No-Go**: GO only if migration is bidirectionally clean and all indexes verified present.

---

**DO NOT IMPLEMENT in Phase 3**:
- Repository queries (Phase 4)
- Any seed data
- Application-level database access
- Frontend migrations or changes

---

## Phase 4: Repositories

**Objective**: Implement all data access layer components. All database read and write operations for the companies module live here and nowhere else.

**Scope**: All four repository classes in `modules/companies/repositories/`.

**Dependencies**: Phase 3 complete (tables must exist). `core/repositories/base.py` (existing `BaseRepository`).

**Database Impact**: Read and write operations on the four tables. No schema changes.

**API Impact**: None.

**Frontend Impact**: None.

**Files Expected To Change**:
- `backend/modules/companies/repositories/company_repository.py` (new)
- `backend/modules/companies/repositories/company_address_repository.py` (new)
- `backend/modules/companies/repositories/company_audit_log_repository.py` (new)
- `backend/modules/companies/repositories/__init__.py`
- `backend/tests/integration/repositories/companies/__init__.py` (new)
- `backend/tests/integration/repositories/companies/test_company_repository.py` (new)
- `backend/tests/integration/repositories/companies/test_company_address_repository.py` (new)

**Files That Must NOT Change**: Model files. Migration files. Existing auth repositories.

---

### Tasks

- [x] T018 Create `backend/modules/companies/repositories/company_repository.py` implementing `CompanyRepository(BaseRepository)` with methods: `create(data: dict) -> Company`, `get_by_id(id: UUID) -> Company | None`, `get_by_id_active(id: UUID) -> Company | None` (excludes deleted/suspended), `get_by_slug(slug: str) -> Company | None`, `get_by_legal_name(name: str) -> Company | None` (case-insensitive via `lower()`), `update(company: Company, data: dict) -> Company`, `soft_delete(company: Company, deleted_at: datetime, reason: str) -> Company`, `restore(company: Company) -> Company`, `exists_by_name(name: str, exclude_id: UUID | None = None) -> bool`, `exists_by_slug(slug: str, exclude_id: UUID | None = None) -> bool`, `list_by_owner(owner_id: UUID) -> list[Company]`, `list_all(filters: dict, page: int, page_size: int) -> tuple[list[Company], int]` (SuperAdmin only, supports status/country/search/include_deleted filters); all queries use `WHERE company_id = :id` or appropriate indexed column; default queries exclude `status = 'deleted'`
- [x] T019 [P] Create `backend/modules/companies/repositories/company_address_repository.py` implementing `CompanyAddressRepository(BaseRepository)` with methods: `create(company_id: UUID, data: dict) -> CompanyAddress`, `get_by_id(id: UUID, company_id: UUID) -> CompanyAddress | None`, `list_by_company(company_id: UUID) -> list[CompanyAddress]`, `update(address: CompanyAddress, data: dict) -> CompanyAddress`, `delete(address: CompanyAddress) -> None`; every query MUST include `WHERE company_id = :company_id`
- [x] T020 [P] Create `backend/modules/companies/repositories/company_audit_log_repository.py` implementing `CompanyAuditLogRepository` with methods: `create(data: dict) -> CompanyAuditLog` (INSERT only), `list_by_company(company_id: UUID, filters: dict, page: int, page_size: int) -> tuple[list[CompanyAuditLog], int]`; NO `update()` method; NO `delete()` method; repository class MUST raise `NotImplementedError` if any update/delete path is attempted
- [x] T021 Create `backend/tests/integration/repositories/companies/test_company_repository.py` covering: create returns Company with correct fields, get_by_id returns correct record, get_by_id returns None for non-existent, legal_name uniqueness — second insert with same name (case-insensitive) raises IntegrityError, slug uniqueness — second insert with same slug raises IntegrityError, soft_delete sets status=deleted and deleted_at, list_by_owner excludes deleted companies by default, list_all SuperAdmin returns all records, exists_by_name returns True/False correctly, restore sets status=inactive and clears deleted_at
- [x] T022 [P] Create `backend/tests/integration/repositories/companies/test_company_address_repository.py` covering: create address, list_by_company returns only company's addresses (not another company's), get_by_id with wrong company_id returns None (tenant isolation), update address, delete address

---

### Checkpoint 4

**Questions to Verify**:
- Do all repository integration tests pass against the test PostgreSQL?
- Does inserting a duplicate `legal_name` (case-insensitive) raise `IntegrityError`?
- Does `list_by_company` on `CompanyAddressRepository` with a cross-tenant `company_id` return empty list?
- Does `CompanyAuditLogRepository` raise `NotImplementedError` when update is called?
- Does `get_by_id_active` return `None` for a deleted company?

**Required Tests**: `pytest tests/integration/repositories/companies/ -v` — all tests green. `ruff check backend/modules/companies/repositories/` — zero errors.

**Expected Result**: 100% repository test pass rate. Tenant isolation confirmed at DB query level.

**Go / No-Go**: GO only if all integration tests pass and tenant isolation is verified.

---

**DO NOT IMPLEMENT in Phase 4**:
- Service layer (Phase 7)
- API endpoints (Phase 9)
- Any business rules (those live in services)
- Frontend code
- Audit log entries (service responsibility)

---

## Phase 5: Validators and Exceptions

**Objective**: Define all field validator functions and the complete module-specific exception hierarchy. These are pure Python — no database or HTTP dependency.

**Scope**: `validators.py` and `exceptions.py` in `modules/companies/`.

**Dependencies**: Phase 1 complete. Python `zoneinfo` standard library. No database or framework dependency.

**Database Impact**: None.

**API Impact**: None.

**Frontend Impact**: None.

**Files Expected To Change**:
- `backend/modules/companies/validators.py` (new)
- `backend/modules/companies/exceptions.py` (new)
- `backend/tests/unit/modules/companies/test_company_validators.py` (new)
- `backend/tests/unit/modules/companies/__init__.py` (new)

**Files That Must NOT Change**: All model files. All repository files.

---

### Tasks

- [x] T023 Create `backend/modules/companies/exceptions.py` defining the complete exception hierarchy; all classes inherit `AppException` from `core/exceptions/base.py`; define 14 exception classes: `CompanyNotFoundError` (404), `CompanyNameConflictError` (409), `SlugConflictError` (409), `SlugImmutableError` (422), `InvalidStatusTransitionError` (409), `CompanySuspendedError` (403), `CompanyIncompleteError` (422, carries `missing_fields: list[str]`), `CompanyPurgedError` (410), `ActiveSubscriptionError` (409), `ForceDeleteRequiredError` (422), `CurrencyChangeWarningError` (422), `LogoTooLargeError` (400), `LogoInvalidFormatError` (400), `LogoInvalidContentError` (400); each carries an `error_code` string constant matching the error codes in spec.md §12.2 exactly
- [x] T024 Create `backend/modules/companies/validators.py` defining seven validator functions (pure functions, no side effects): `validate_iso_4217_currency(value: str) -> str` (validate against embedded 180+ code set), `validate_iana_timezone(value: str) -> str` (use `zoneinfo.available_timezones()`), `validate_iso_3166_country(value: str) -> str` (validate against embedded 249-code set), `validate_hex_color(value: str) -> str` (normalize to `#RRGGBB` format), `validate_e164_phone(value: str) -> str` (E.164 regex: `^\+[1-9]\d{1,14}$`), `validate_slug_format(value: str) -> str` (regex `^[a-z0-9][a-z0-9-]{0,98}[a-z0-9]$`, reject consecutive hyphens), `validate_bcp47_language(value: str) -> str` (validate against supported locales list); each raises `ValueError` with descriptive message on invalid input
- [x] T025 Create `backend/tests/unit/modules/companies/test_company_validators.py` testing each validator with: one valid input case, three invalid input cases (boundary, format, wrong type); verify `ValueError` is raised with non-empty message for all invalid cases; verify valid input is returned (possibly normalized) unchanged for all valid cases

---

### Checkpoint 5

**Questions to Verify**:
- Do all 14 exception classes instantiate with correct `error_code` attribute?
- Does `validate_iso_4217_currency("USD")` return `"USD"`?
- Does `validate_iso_4217_currency("XYZ")` raise `ValueError`?
- Does `validate_iana_timezone("America/New_York")` return without error?
- Does `validate_iana_timezone("Fake/Zone")` raise `ValueError`?
- Does `validate_hex_color("#ff5733")` normalize to `"#FF5733"`?
- Does `validate_slug_format("a--b")` (consecutive hyphens) raise `ValueError`?

**Required Tests**: `pytest tests/unit/modules/companies/test_company_validators.py -v` — 100% pass, 100% coverage on all 7 functions. `ruff check backend/modules/companies/validators.py backend/modules/companies/exceptions.py` — zero errors.

**Expected Result**: All validator and exception tests pass. No imports from SQLAlchemy or FastAPI in these files.

**Go / No-Go**: GO only if all validator tests pass with full coverage and exceptions have correct error_code attributes.

---

**DO NOT IMPLEMENT in Phase 5**:
- Pydantic schemas (Phase 6)
- Service methods (Phase 7)
- API routes (Phase 9)
- Slug auto-derivation (that is a service-layer concern using these validators)

---

## Phase 6: Pydantic Schemas

**Objective**: Define all Pydantic v2 request and response schemas for the companies module. Validators from Phase 5 are wired in here.

**Scope**: `modules/companies/schemas/` package. Five schema files.

**Dependencies**: Phase 5 complete (validators and exceptions). Pydantic v2 installed.

**Database Impact**: None.

**API Impact**: None (schemas are not yet connected to endpoints).

**Frontend Impact**: None.

**Files Expected To Change**:
- `backend/modules/companies/schemas/company.py` (new)
- `backend/modules/companies/schemas/address.py` (new)
- `backend/modules/companies/schemas/settings.py` (new)
- `backend/modules/companies/schemas/status.py` (new)
- `backend/modules/companies/schemas/audit.py` (new)
- `backend/modules/companies/schemas/__init__.py`

**Files That Must NOT Change**: validators.py, exceptions.py, model files, repository files.

---

### Tasks

- [x] T026 Create `backend/modules/companies/schemas/company.py` defining: `CreateCompanyRequest` (required: `legal_name`, `email`; optional: `trade_name`, `phone_primary`, `country`, `default_currency` default `"USD"`, `default_language` default `"en-US"`, `default_timezone` default `"UTC"`, `slug`; field validators call Phase 5 functions), `UpdateCompanyRequest` (all optional, same fields as create plus: `phone_secondary`, `website`, `tax_number`, `registration_number`, `business_category`, `business_type`, `incorporation_date`, `fiscal_year_start_month`, `date_format`, `brand_color_primary`, `brand_color_secondary`, `tagline`; include `confirm_currency_change: bool = False` for currency changes), `CompanyResponse` (id, legal_name, trade_name, slug, status, owner_id, email, country, default_currency, default_language, default_timezone, created_at, updated_at), `CompanyDetailResponse` (all fields including sensitive fields with role-based masking serializer — `tax_number` and `registration_number` are masked `"****"` unless requester role is `owner`, `admin`, or `accountant`), `CompanyListItem` (subset: id, legal_name, slug, status, country, default_currency, created_at)
- [x] T027 [P] Create `backend/modules/companies/schemas/address.py` defining: `CreateAddressRequest`, `UpdateAddressRequest`, `CompanyAddressResponse` with all address fields from spec.md §10.1 `company_addresses` entity; `address_type` validated against `AddressType` enum
- [x] T028 [P] Create `backend/modules/companies/schemas/settings.py` defining: `UpdateSettingsRequest` (settings: dict[str, Any]), `CompanySettingsResponse` (company_id: UUID, settings: dict, updated_at: datetime)
- [x] T029 [P] Create `backend/modules/companies/schemas/status.py` defining: `DeactivateRequest` (reason: str, max 1000 chars, required), `DeleteCompanyRequest` (reason: str required, force_delete: bool = False, confirm_delete: bool required must be True), `ActivateResponse`, `DeactivateResponse`, `DeleteCompanyResponse` (id, status, deleted_at, message), `RestoreResponse`
- [x] T030 [P] Create `backend/modules/companies/schemas/audit.py` defining: `AuditLogEntryResponse` (id, company_id, actor_user_id, action, before_state, after_state, ip_address, user_agent, request_id, created_at), `AuditLogListResponse` using existing `PaginatedResponse` generic from `core/schemas/pagination.py`

---

### Checkpoint 6

**Questions to Verify**:
- Does `CreateCompanyRequest(legal_name="A", email="a@b.com")` instantiate successfully?
- Does `CreateCompanyRequest(legal_name="A", email="a@b.com", default_currency="XYZ")` raise `ValidationError` with field `default_currency`?
- Does `CreateCompanyRequest(legal_name="A", email="not-an-email")` raise `ValidationError` with field `email`?
- Does `CompanyDetailResponse` mask `tax_number` as `"****"` for non-authorized roles?
- Does `DeleteCompanyRequest(reason="test", confirm_delete=False)` raise `ValidationError`?

**Required Tests**: `python -c "from backend.modules.companies.schemas import CreateCompanyRequest"` — zero import errors. Run schema instantiation tests manually or via `pytest -k schema`. `mypy backend/modules/companies/schemas/` — zero type errors (if mypy configured).

**Expected Result**: All schemas importable. Validators fire on field input. Sensitive field masking works.

**Go / No-Go**: GO only if all schemas validate correctly and sensitive field masking is confirmed.

---

**DO NOT IMPLEMENT in Phase 6**:
- Service methods (Phase 7)
- API router wiring (Phase 9)
- Frontend TypeScript types (Phase 10)

---

## Phase 7: Domain Services

**Objective**: Implement all business logic. The service layer is the core of the companies module. All business rules (BR-001 to BR-029) are enforced here.

**Scope**: `modules/companies/services/` — four service classes. `modules/companies/events.py` — domain event definitions.

**Dependencies**: Phases 4, 5, 6 complete. `core/events/outbox.py` (Phase 1). `core/storage/s3_client.py` (Phase 1).

**Database Impact**: Read and write via repositories within atomic transactions.

**API Impact**: None (services not yet exposed via HTTP).

**Frontend Impact**: None.

**Files Expected To Change**:
- `backend/modules/companies/events.py` (new)
- `backend/modules/companies/services/company_service.py` (new)
- `backend/modules/companies/services/company_audit_service.py` (new)
- `backend/modules/companies/services/company_logo_service.py` (new)
- `backend/modules/companies/services/company_settings_service.py` (new)
- `backend/modules/companies/services/__init__.py`
- `backend/tests/unit/modules/companies/test_company_service.py` (new)
- `backend/tests/unit/modules/companies/test_company_audit_service.py` (new)
- `backend/tests/unit/modules/companies/test_company_logo_service.py` (new)
- `backend/tests/unit/modules/companies/test_company_settings_service.py` (new)

**Files That Must NOT Change**: Model files, migration files, repository files, schema files, validators.py, exceptions.py.

---

### Tasks

- [x] T031 Create `backend/modules/companies/events.py` defining 11 domain event payload dataclasses: `CompanyCreatedEvent`, `CompanyUpdatedEvent`, `CompanyActivatedEvent`, `CompanyDeactivatedEvent`, `CompanySuspendedEvent`, `CompanySuspensionLiftedEvent`, `CompanyDeletedEvent`, `CompanyRestoredEvent`, `CompanyPermanentlyPurgedEvent`, `CompanyLogoUploadedEvent`, `CompanyAdminChangedEvent`; each is a `@dataclass` with typed fields matching spec.md §14.1 payload definitions; each implements `to_outbox_record(correlation_id: str, actor_id: UUID | None) -> dict` returning the dict for `EventOutboxRepository.create()`
- [x] T032 Create `backend/modules/companies/services/company_audit_service.py` implementing `CompanyAuditService` with single method `record(session, company_id, actor_user_id, action, before_state, after_state, ip_address, request_id, user_agent) -> CompanyAuditLog`; constructs the audit log record and calls `CompanyAuditLogRepository.create()` within the passed session; must be called inside the same transaction as the originating operation
- [x] T033 [P] Create `backend/modules/companies/services/company_logo_service.py` implementing `CompanyLogoService` with methods: `validate_file(file_bytes: bytes, filename: str) -> str` (uses `python-magic` to detect MIME from bytes, validates against allowed types, validates size ≤ COMPANY_LOGO_MAX_BYTES, returns detected MIME type; raises `LogoInvalidContentError`, `LogoInvalidFormatError`, `LogoTooLargeError`), `upload(file_bytes: bytes, company_id: UUID, mime_type: str) -> str` (generates UUID-based key, uploads to S3 client, returns URL), `schedule_previous_cleanup(previous_url: str | None) -> None` (stub: logs the URL for cleanup; actual deletion is a future background job)
- [x] T034 [P] Create `backend/modules/companies/services/company_settings_service.py` implementing `CompanySettingsService` with: `ALLOWED_SETTINGS` dict constant mapping setting key → (type, allowed_values | None), `validate_settings(updates: dict) -> dict` (rejects unknown keys, validates value types and allowed values; raises `ValueError` per invalid key), `merge_settings(existing: dict, updates: dict) -> dict` (returns merged dict; does not delete existing keys not in updates)
- [x] T035 Create `backend/modules/companies/services/company_service.py` implementing `CompanyService` with all lifecycle methods; inject `CompanyRepository`, `CompanyAddressRepository`, `CompanyAuditLogRepository`, `EventOutboxRepository`, `CompanyLogoService`, `CompanySettingsService`, `CompanyAuditService` via `__init__`; implement all methods within `async with session.begin()` transactions: `create_company(actor_id, data, request_context) -> Company` (derives slug, checks uniqueness, creates company, records audit, publishes `CompanyCreatedEvent`), `update_company(company_id, actor_id, data, request_context) -> Company` (partial update, enforces slug immutability after activation, warns on currency change, records audit, publishes `CompanyUpdatedEvent`), `activate_company(company_id, actor_id, request_context) -> Company` (validates required fields complete; transitions from `pending_setup`/`inactive` to `active`; records audit; publishes `CompanyActivatedEvent`), `deactivate_company(company_id, actor_id, reason, request_context) -> Company` (transitions from `active` to `inactive`; records audit; publishes `CompanyDeactivatedEvent`), `soft_delete_company(company_id, actor_id, reason, force_delete, request_context) -> Company` (validates no active subscription; warns if active transactions unless force_delete=True; transitions to `deleted`; records audit; publishes `CompanyDeletedEvent`), `restore_company(company_id, actor_id, request_context) -> Company` (validates within 90-day window; transitions to `inactive`; records audit; publishes `CompanyRestoredEvent`), `get_company(company_id, requester_id) -> Company`, `list_user_companies(owner_id) -> list[Company]`, `list_all_companies(filters, page, page_size) -> tuple[list[Company], int]`; all status transitions validated against the transition table in spec.md §5.6; invalid transitions raise `InvalidStatusTransitionError`
- [x] T036 Create `backend/tests/unit/modules/companies/test_company_service.py` with unit tests for `CompanyService`; mock all repositories and external services; cover: successful company creation with slug derivation, duplicate name raises `CompanyNameConflictError`, duplicate slug handled with auto-suffix, valid status transitions succeed, invalid transitions raise `InvalidStatusTransitionError`, company activation fails if required fields missing, soft delete within 90 days succeeds, restore beyond 90 days raises `CompanyPurgedError`, currency change without confirm_currency_change flag raises `CurrencyChangeWarningError`, suspended company cannot be reactivated by owner only by super_admin
- [x] T037 [P] Create `backend/tests/unit/modules/companies/test_company_logo_service.py` covering: valid PNG bytes pass validation, valid JPEG bytes pass validation, SVG with script content raises `LogoInvalidContentError`, file exceeding size limit raises `LogoTooLargeError`, unsupported MIME type raises `LogoInvalidFormatError`, PNG file renamed as `.exe` detected correctly as PNG via magic bytes, upload returns URL, `schedule_previous_cleanup` logs and does not error
- [x] T038 [P] Create `backend/tests/unit/modules/companies/test_company_settings_service.py` covering: known setting key with valid value succeeds, unknown setting key raises `ValueError`, invalid value type raises `ValueError`, merge keeps existing keys not in update, merge overwrites keys present in update

---

### Checkpoint 7

**Questions to Verify**:
- Does `CompanyService.create_company()` derive a slug from legal name correctly (lowercase, hyphenated)?
- Does `CompanyService.create_company()` raise `CompanyNameConflictError` when name already exists?
- Does activating a company with missing `default_currency` raise `CompanyIncompleteError`?
- Does `CompanyService.soft_delete_company()` raise `CompanyPurgedError` if `deleted_at` > 90 days?
- Does `CompanyLogoService.validate_file()` detect a PNG renamed as `.exe` as valid PNG via magic bytes?
- Are audit log entries written inside the same transaction as the state change?
- Are domain events written to the outbox in the same transaction?

**Required Tests**: `pytest tests/unit/modules/companies/ -v --cov=backend/modules/companies/services/ --cov-report=term-missing` — minimum 90% branch coverage on all service files.

**Expected Result**: All service unit tests pass. Business rules BR-001 through BR-029 each covered by at least one test.

**Go / No-Go**: GO only if 90%+ branch coverage achieved and all 14 exception types are triggered in tests.

---

**DO NOT IMPLEMENT in Phase 7**:
- API routes (Phase 9)
- FastAPI dependency functions (Phase 8)
- Frontend code
- Rate limiting (Phase 11)
- Actual S3 upload in tests (mock it)

---

## Phase 8: Authorization and Dependencies

**Objective**: Implement all FastAPI dependency injection functions and role-based authorization guards. These connect the auth system (Epic 2) to the companies module.

**Scope**: `modules/companies/dependencies.py`. No business logic — only auth wiring.

**Dependencies**: Phase 7 complete. `core/auth/dependencies.py` (existing `get_current_user()`). Epic 2's `User` model and JWT context.

**Database Impact**: Reads `companies` table to validate membership. No writes.

**API Impact**: None (dependencies not yet wired to endpoints).

**Frontend Impact**: None.

**Files Expected To Change**:
- `backend/modules/companies/dependencies.py` (new)
- `backend/tests/unit/modules/companies/test_company_dependencies.py` (new)

**Files That Must NOT Change**: `core/auth/` files. Existing `modules/auth/` files.

---

### Tasks

- [x] T039 Create `backend/modules/companies/dependencies.py` implementing all DI factory functions: `get_company_service(session: AsyncSession = Depends(get_db)) -> CompanyService` (wires all repositories and services), `get_company_audit_service(session: AsyncSession = Depends(get_db)) -> CompanyAuditService`, `get_company_logo_service(storage: StorageClient = Depends(get_storage)) -> CompanyLogoService`, `async def get_current_company(company_id: UUID, current_user: User = Depends(get_current_user), service: CompanyService = Depends(get_company_service)) -> Company` (validates user membership; returns company or raises `CompanyNotFoundError` / `CompanySuspendedError`); role-guard factory `require_role(allowed_roles: list[str])` returning a dependency that checks `current_user.role` within company context and raises `HTTPException(403)` if insufficient; shorthand factories: `require_owner()`, `require_admin_or_above()`, `require_super_admin()`
- [x] T040 **Phase 1 RBAC note**: Until Epic 4 (Users/RBAC) creates the `company_members` table, membership validation simplifies to: the user is a member if `company.owner_id == current_user.id`; the SuperAdmin role is determined by `current_user.is_superadmin` flag (boolean added to User model in this task if not present, else use existing field); document this simplification clearly in `dependencies.py` with a `# TODO Epic-4: replace with company_members table lookup` comment
- [x] T041 Create `backend/tests/unit/modules/companies/test_company_dependencies.py` testing: `get_current_company` returns company when owner_id matches user, `get_current_company` raises 404 when company does not exist, `get_current_company` raises 403 with COMPANY_SUSPENDED when company is suspended, `require_owner()` passes for owner, `require_owner()` raises 403 for non-owner, `require_super_admin()` passes for super_admin, `require_super_admin()` raises 403 for regular user

---

### Checkpoint 8

**Questions to Verify**:
- Does `get_current_company` return the company for the owner user?
- Does `get_current_company` raise 403 for a user who is not the company owner?
- Does `get_current_company` raise 403 with code `COMPANY_SUSPENDED` for a suspended company?
- Does `require_super_admin()` raise 403 for a non-superadmin user?
- Are all TODO comments placed for Epic 4 RBAC replacement?

**Required Tests**: `pytest tests/unit/modules/companies/test_company_dependencies.py -v` — all tests pass. No integration with live database needed (mock repositories).

**Expected Result**: All dependency unit tests pass. Auth integration is wired but testable without live auth service.

**Go / No-Go**: GO only if all dependency tests pass and RBAC TODO comments are in place.

---

**DO NOT IMPLEMENT in Phase 8**:
- API endpoint handlers (Phase 9)
- Frontend auth integration (Phase 10)
- Full RBAC from Epic 4 (future)
- `company_members` table (Epic 4)

---

## Phase 9: API Router

**Objective**: Wire all 14 company API endpoints. Route handlers are thin — they validate input (Pydantic), authorize (dependencies), delegate to service, and return response schema.

**Scope**: `modules/companies/router.py`. Register in `api/v1/router.py`. `modules/companies/__init__.py` public exports.

**Dependencies**: Phases 6, 7, 8 complete. All schemas, services, and dependencies ready.

**Database Impact**: All lifecycle operations via services.

**API Impact**: 14 new endpoints available under `/api/v1/companies`.

**Frontend Impact**: None yet (Phase 10).

**Files Expected To Change**:
- `backend/modules/companies/router.py` (new)
- `backend/modules/companies/__init__.py`
- `backend/api/v1/router.py`
- `backend/tests/integration/api/v1/companies/__init__.py` (new)
- `backend/tests/integration/api/v1/companies/test_create_company.py` (new)
- `backend/tests/integration/api/v1/companies/test_get_company.py` (new)
- `backend/tests/integration/api/v1/companies/test_update_company.py` (new)
- `backend/tests/integration/api/v1/companies/test_company_status.py` (new)
- `backend/tests/integration/api/v1/companies/test_delete_restore.py` (new)
- `backend/tests/integration/api/v1/companies/test_company_settings.py` (new)
- `backend/tests/integration/api/v1/companies/test_company_logo.py` (new)
- `backend/tests/integration/api/v1/companies/test_company_addresses.py` (new)
- `backend/tests/integration/api/v1/companies/test_audit_log.py` (new)
- `backend/tests/integration/api/v1/companies/test_superadmin_list.py` (new)

**Files That Must NOT Change**: auth router, core files, model files, service files.

---

### Tasks

- [X] T042 [US1] Create `backend/modules/companies/router.py` implementing `APIRouter(prefix="", tags=["companies"])`; implement `POST /` endpoint (`create_company`): accepts `CreateCompanyRequest`, uses `get_company_service` and `get_current_user` dependencies, calls `company_service.create_company()`, returns `CompanyResponse` with status 201; implement `GET /{company_id}` endpoint (`get_company`): uses `get_current_company` dependency, calls `company_service.get_company()`, returns `CompanyDetailResponse`; implement `PATCH /{company_id}` endpoint (`update_company`): requires `require_admin_or_above()`, accepts `UpdateCompanyRequest`, calls `company_service.update_company()`, returns `CompanyDetailResponse`
- [X] T043 [US3] Add status endpoints to `backend/modules/companies/router.py`: `POST /{company_id}/activate` (requires `require_owner()`; calls `company_service.activate_company()`), `POST /{company_id}/deactivate` (requires `require_owner()`; accepts `DeactivateRequest`; calls `company_service.deactivate_company()`)
- [X] T044 [US4] Add lifecycle endpoints to `backend/modules/companies/router.py`: `DELETE /{company_id}` (requires `require_owner()`; accepts `DeleteCompanyRequest`; calls `company_service.soft_delete_company()`; returns `DeleteCompanyResponse`), `POST /{company_id}/restore` (requires `require_owner()`; calls `company_service.restore_company()`; returns `RestoreResponse`)
- [X] T045 [US5] Add settings and address endpoints to `backend/modules/companies/router.py`: `PATCH /{company_id}/settings` (requires `require_admin_or_above()`; accepts `UpdateSettingsRequest`; returns `CompanySettingsResponse`), `GET /{company_id}/addresses` (requires membership), `POST /{company_id}/addresses` (requires `require_admin_or_above()`), `PUT /{company_id}/addresses/{address_id}` (requires `require_admin_or_above()`), `DELETE /{company_id}/addresses/{address_id}` (requires `require_admin_or_above()`)
- [X] T046 [US2] Add logo upload endpoint to `backend/modules/companies/router.py`: `POST /{company_id}/logo` (requires `require_admin_or_above()`; accepts `UploadFile`; calls `company_logo_service.validate_file()` then `company_logo_service.upload()`; updates company logo_url via company_service; returns `LogoUploadResponse`)
- [X] T047 Add audit log endpoint to `backend/modules/companies/router.py`: `GET /{company_id}/audit-logs` (requires `require_admin_or_above()`; accepts pagination and filter query params; calls audit log list via service; returns `AuditLogListResponse`)
- [X] T048 [US6] Add SuperAdmin endpoint to `backend/modules/companies/router.py`: `GET /admin/companies` (requires `require_super_admin()`; accepts all filter/sort/pagination params; calls `company_service.list_all_companies()`; returns paginated `CompanyListItem[]`); register this sub-router under a separate prefix or use a dedicated router with `/admin` prefix
- [X] T049 Register companies router in `backend/api/v1/router.py`: `router.include_router(companies_router, prefix="/companies")`; update `backend/modules/companies/__init__.py` to export `CompanyService`, `get_current_company`
- [X] T050 [US1] Create `backend/tests/integration/api/v1/companies/test_create_company.py`: POST with valid data returns 201 with UUID id, POST with duplicate legal name returns 409 COMPANY_NAME_CONFLICT, POST with invalid currency returns 400 VALIDATION_ERROR with field detail, POST with missing email returns 400, POST without auth returns 401, POST verifies audit log record was created, POST verifies CompanyCreated outbox event was created
- [X] T051 [P] [US1] Create `backend/tests/integration/api/v1/companies/test_get_company.py`: GET valid company returns 200 with all fields, GET non-existent returns 404, GET cross-tenant (user from company A requesting company B) returns 403, GET deleted company returns 404, verify sensitive fields masked for non-owner user
- [X] T052 [P] [US2] Create `backend/tests/integration/api/v1/companies/test_update_company.py`: PATCH with valid partial data returns 200 with only changed fields updated, PATCH with duplicate name returns 409, PATCH slug after activation returns 422 SLUG_IMMUTABLE, PATCH currency change without confirmation returns 422 CURRENCY_CHANGE_WARNING, PATCH by manager role returns 403, PATCH by admin succeeds
- [X] T053 [P] [US3] Create `backend/tests/integration/api/v1/companies/test_company_status.py`: activate pending_setup company succeeds, activate company with missing required fields returns 422 COMPANY_INCOMPLETE with field list, deactivate active company succeeds with reason, reactivate inactive company succeeds, invalid transition (pending → inactive) returns 409 INVALID_STATUS_TRANSITION, non-owner deactivation attempt returns 403
- [X] T054 [P] [US4] Create `backend/tests/integration/api/v1/companies/test_delete_restore.py`: soft delete sets status=deleted and deleted_at, deleted company not returned in standard GET, restore within 90 days returns status=inactive with all data intact, restore after 90 days returns 410 COMPANY_PURGED, delete without confirm_delete=true returns 400
- [X] T055 [P] [US5] Create `backend/tests/integration/api/v1/companies/test_company_settings.py`: settings update with known key succeeds, settings update with unknown key returns 400, settings partial merge preserves unmodified keys
- [X] T056 [P] [US2] Create `backend/tests/integration/api/v1/companies/test_company_logo.py`: valid PNG upload succeeds and returns URL, file exceeding 5MB returns 400 LOGO_TOO_LARGE, invalid format returns 400 LOGO_INVALID_FORMAT, SVG with script content returns 400 LOGO_INVALID_CONTENT, unauthenticated request returns 401
- [X] T057 [P] Create `backend/tests/integration/api/v1/companies/test_audit_log.py`: every state-changing operation (create, update, activate, deactivate, delete, restore) produces exactly one audit log entry; audit log entries are not modifiable via API (PATCH/DELETE returns 405); pagination returns correct page/page_size metadata
- [X] T058 [P] [US6] Create `backend/tests/integration/api/v1/companies/test_superadmin_list.py`: superadmin gets all companies, filter by status works, search by legal_name case-insensitive works, non-superadmin request returns 403, include_deleted=true returns deleted companies

---

### Checkpoint 9

**Questions to Verify**:
- Does `POST /api/v1/companies` return 201 with a UUID `id`?
- Does `GET /api/v1/companies/{id}` return 403 for a user from a different company?
- Does `DELETE /api/v1/companies/{id}` result in `status: deleted`?
- Does `POST /api/v1/companies/{id}/restore` after 91 days return 410?
- Does logo upload with a PNG file renamed to `.exe` succeed (magic bytes)?
- Does the audit log test confirm an entry exists after each state change?
- Does `GET /api/v1/admin/companies` return 403 for a non-superadmin?

**Required Tests**: `pytest tests/integration/api/v1/companies/ -v` — all API integration tests pass. `pytest tests/integration/` — no regressions in auth tests.

**Expected Result**: All 14 endpoints functional. All acceptance criteria AC-001 through AC-012 from spec.md are covered by tests.

**Go / No-Go**: GO only if all API integration tests pass and no auth regression detected.

---

**DO NOT IMPLEMENT in Phase 9**:
- Rate limiting configuration (Phase 11)
- Frontend (Phase 10+)
- Performance optimizations
- SuperAdmin suspension endpoint (future — suspension is system-initiated)

---

## Phase 10: Frontend Foundation

**Objective**: Build the frontend data layer — TypeScript types, API client functions, React Query hooks, and `CompanyContext`. No UI components yet.

**Scope**: `frontend/src/types/companies.ts`, `frontend/src/lib/api/companies.ts`, `frontend/src/hooks/companies/`, `frontend/src/contexts/CompanyContext.tsx`.

**Dependencies**: Phase 9 complete (API endpoints available for testing). Existing `frontend/src/lib/api/client.ts`.

**Database Impact**: None.

**API Impact**: None (consuming existing endpoints).

**Frontend Impact**: TypeScript types and hooks available for UI components.

**Files Expected To Change**:
- `frontend/src/types/companies.ts` (new)
- `frontend/src/lib/api/companies.ts` (new)
- `frontend/src/contexts/CompanyContext.tsx` (new)
- `frontend/src/hooks/companies/useCompanies.ts` (new)
- `frontend/src/hooks/companies/useCompany.ts` (new)
- `frontend/src/hooks/companies/useCreateCompany.ts` (new)
- `frontend/src/hooks/companies/useUpdateCompany.ts` (new)
- `frontend/src/hooks/companies/useCompanyStatus.ts` (new)
- `frontend/src/hooks/companies/useDeleteCompany.ts` (new)
- `frontend/src/hooks/companies/useRestoreCompany.ts` (new)
- `frontend/src/hooks/companies/useUploadLogo.ts` (new)
- `frontend/src/hooks/companies/useCompanySettings.ts` (new)
- `frontend/src/hooks/companies/useCompanyAddresses.ts` (new)
- `frontend/src/hooks/companies/useCompanyAuditLog.ts` (new)
- `frontend/src/__tests__/companies/hooks/useCompany.test.ts` (new)
- `frontend/src/__tests__/companies/hooks/useCreateCompany.test.ts` (new)

**Files That Must NOT Change**: `AuthContext.tsx`. Existing auth hooks. Existing API client configuration.

---

### Tasks

- [X] T059 [US1] Create `frontend/src/types/companies.ts` defining TypeScript interfaces matching all backend Pydantic schemas: `Company`, `CompanyDetail`, `CompanyListItem`, `CompanyAddress`, `CompanySettings`, `AuditLogEntry`, `CreateCompanyInput`, `UpdateCompanyInput`, `UpdateSettingsInput`, `DeactivateInput`, `DeleteCompanyInput`, `LogoUploadResponse`, `CompanySummary` (lightweight type for context), `CompanyStatus` union type (`"pending_setup" | "active" | "inactive" | "suspended" | "deleted"`), `AddressType`, `BusinessType`; use strict TypeScript with no `any` types
- [X] T060 [US1] Create `frontend/src/lib/api/companies.ts` defining all API call functions using existing `client.ts` axios/fetch wrapper: `createCompany(data: CreateCompanyInput): Promise<Company>`, `getCompany(id: string): Promise<CompanyDetail>`, `updateCompany(id: string, data: UpdateCompanyInput): Promise<CompanyDetail>`, `activateCompany(id: string): Promise<CompanyDetail>`, `deactivateCompany(id: string, data: DeactivateInput): Promise<CompanyDetail>`, `deleteCompany(id: string, data: DeleteCompanyInput): Promise<{id, status, deleted_at}>`, `restoreCompany(id: string): Promise<CompanyDetail>`, `uploadCompanyLogo(id: string, file: File): Promise<LogoUploadResponse>`, `updateCompanySettings(id: string, settings: Record<string, unknown>): Promise<CompanySettings>`, `listCompanies(): Promise<Company[]>`, `listAdminCompanies(params: AdminListParams): Promise<PaginatedResponse<CompanyListItem>>`, `getCompanyAuditLog(id: string, params: AuditLogParams): Promise<PaginatedResponse<AuditLogEntry>>`, `getCompanyAddresses(id: string): Promise<CompanyAddress[]>`, `createCompanyAddress(id: string, data: CreateAddressInput): Promise<CompanyAddress>`, `updateCompanyAddress(id: string, addressId: string, data: UpdateAddressInput): Promise<CompanyAddress>`, `deleteCompanyAddress(id: string, addressId: string): Promise<void>`
- [X] T061 Create `frontend/src/contexts/CompanyContext.tsx` defining `CompanyContext` with `CompanyContextValue` interface (`activeCompany: CompanySummary | null`, `setActiveCompany(company: CompanySummary): void`, `clearActiveCompany(): void`, `isLoading: boolean`); persist `activeCompany.id` to `localStorage` key `"erp_active_company_id"` for page refresh; clear on `AuthContext` logout event; export `CompanyProvider` and `useCompanyContext()` hook
- [X] T062 [P] [US1] Create `frontend/src/hooks/companies/useCompanies.ts` using TanStack Query `useQuery` with key `['companies']`, calls `listCompanies()`, `staleTime: 5 * 60 * 1000`
- [X] T063 [P] [US1] Create `frontend/src/hooks/companies/useCompany.ts` with key `['company', id]`, calls `getCompany(id)`, enabled only when `id` is defined
- [X] T064 [P] [US1] Create `frontend/src/hooks/companies/useCreateCompany.ts` using `useMutation`, calls `createCompany()`, on success invalidates `['companies']`
- [X] T065 [P] [US2] Create `frontend/src/hooks/companies/useUpdateCompany.ts` using `useMutation`, calls `updateCompany()`, on success invalidates `['company', id]`
- [X] T066 [P] [US3] Create `frontend/src/hooks/companies/useCompanyStatus.ts` exporting `useActivateCompany(id)` and `useDeactivateCompany(id)` mutations with optimistic update: `onMutate` snapshots cache and writes optimistic `status`, `onError` rolls back, `onSettled` invalidates `['company', id]` and `['companies']`
- [X] T067 [P] [US4] Create `frontend/src/hooks/companies/useDeleteCompany.ts` and `useRestoreCompany.ts` mutations; on delete success remove `['company', id]` from cache and invalidate `['companies']`; on restore success invalidate both
- [X] T068 [P] [US2] Create `frontend/src/hooks/companies/useUploadLogo.ts` mutation using `FormData` multipart; on success invalidates `['company', id]`
- [X] T069 [P] [US5] Create `frontend/src/hooks/companies/useCompanySettings.ts` mutation; on success invalidates `['company', id]`
- [X] T070 [P] Create `frontend/src/hooks/companies/useCompanyAddresses.ts` exporting `useCompanyAddresses(id)` query and `useCreateAddress`, `useUpdateAddress`, `useDeleteAddress` mutations; all invalidate `['company', id]` on success
- [X] T071 [P] Create `frontend/src/hooks/companies/useCompanyAuditLog.ts` query with key `['company-audit-log', id, filters]`, `staleTime: 60 * 1000`; accepts `page`, `page_size`, `action`, `actor_id`, `date_from`, `date_to` params
- [X] T072 Create `frontend/src/__tests__/companies/hooks/useCompany.test.ts` and `useCreateCompany.test.ts` using msw mock handlers; test: successful data fetch returns correct type, error state is exposed correctly, mutation invalidates cache on success, optimistic update rolls back on error

---

### Checkpoint 10

**Questions to Verify**:
- Does `npx tsc --noEmit` pass with zero errors on all new TypeScript files?
- Does `useCreateCompany()` mutation return the correct `Company` type on success?
- Does `CompanyContext` restore `activeCompany` from `localStorage` on page refresh?
- Does `useActivateCompany()` apply an optimistic update before the network call completes?
- Do all hook tests pass with msw mocking the API?

**Required Tests**: `npm test -- --testPathPattern=companies/hooks` — all hook tests pass. `npx tsc --noEmit` — zero TypeScript errors.

**Expected Result**: All hooks importable and typed correctly. Context persists and clears correctly. No `any` types.

**Go / No-Go**: GO only if TypeScript compiles cleanly and all hook tests pass.

---

**DO NOT IMPLEMENT in Phase 10**:
- Any UI pages or components (Phase 11)
- Zod validation schemas for forms (Phase 11)
- Admin company page (Phase 11)
- Audit log UI (Phase 12)

---

## Phase 11: Company Management UI

**Objective**: Build all company listing, creation, and detail pages along with the core UI components. Users can create a company and view its details.

**Scope**: Company list page, create wizard, detail page, `CompanyCard`, `CompanyStatusBadge`, `CompanyCreateWizard`, `CompanyStatusActions`.

**Dependencies**: Phase 10 complete. shadcn/ui components available. Existing `(protected)` layout.

**Database Impact**: None.

**API Impact**: None (consuming existing endpoints).

**Frontend Impact**: Three new pages, five new components, new route group.

**Files Expected To Change**:
- `frontend/src/app/(protected)/(companies)/layout.tsx` (new)
- `frontend/src/app/(protected)/(companies)/companies/page.tsx` (new)
- `frontend/src/app/(protected)/(companies)/companies/new/page.tsx` (new)
- `frontend/src/app/(protected)/(companies)/companies/[id]/page.tsx` (new)
- `frontend/src/app/(protected)/(companies)/admin/companies/page.tsx` (new)
- `frontend/src/components/companies/CompanyCard.tsx` (new)
- `frontend/src/components/companies/CompanyStatusBadge.tsx` (new)
- `frontend/src/components/companies/CompanyCreateWizard.tsx` (new)
- `frontend/src/components/companies/CompanyProfileForm.tsx` (new)
- `frontend/src/components/companies/CompanyStatusActions.tsx` (new)
- `frontend/src/components/companies/AdminCompanyTable.tsx` (new)
- `frontend/src/components/layout/Sidebar.tsx` (update: add Companies navigation item)
- `frontend/src/__tests__/companies/CompanyCreateWizard.test.tsx` (new)
- `frontend/src/__tests__/companies/CompanyStatusActions.test.tsx` (new)

**Files That Must NOT Change**: Auth components. `AuthContext.tsx`. Existing page files.

---

### Tasks

- [x] T073 Create `frontend/src/app/(protected)/(companies)/layout.tsx` wrapping children with `<CompanyProvider>`; reads `activeCompany` from context for layout-level company name display in header
- [x] T074 [US1] Create `frontend/src/app/(protected)/(companies)/companies/page.tsx` (`CompanyListPage`): uses `useCompanies()` hook; renders loading skeleton during fetch; renders `CompanyCard` for each company; shows "Create Company" button linking to `/companies/new`; empty state when no companies
- [x] T075 [US1] Create `frontend/src/components/companies/CompanyCard.tsx`: displays `legal_name`, `status` badge, `country`, `default_currency`, `created_at`; links to `/companies/{id}`; accessible (aria-labels on interactive elements)
- [x] T076 [US1] Create `frontend/src/components/companies/CompanyStatusBadge.tsx`: color-coded badge for each `CompanyStatus` value (pending_setup: yellow, active: green, inactive: gray, suspended: red, deleted: dark gray); uses Tailwind CSS classes
- [x] T077 [US1] Create `frontend/src/components/companies/CompanyCreateWizard.tsx`: 4-step wizard using React Hook Form + Zod; Step 1: `legal_name`, `trade_name`, `email`, `business_type`; Step 2: `country`, `default_currency`, `default_timezone`, `default_language`; Step 3: branding (optional, skip button); Step 4: review and submit; on submit calls `useCreateCompany()` mutation; on success redirects to `/companies/{id}`; Zod schemas validate each step independently before allowing Next
- [x] T078 [US1] Create `frontend/src/app/(protected)/(companies)/companies/new/page.tsx` rendering `CompanyCreateWizard` within a page container
- [x] T079 [US1] Create `frontend/src/app/(protected)/(companies)/companies/[id]/page.tsx` (`CompanyDetailPage`): uses `useCompany(id)` hook; displays all company profile fields in read-only card layout; shows `CompanyStatusBadge`; links to settings tabs; shows `CompanyStatusActions` for owner
- [x] T080 [US3] Create `frontend/src/components/companies/CompanyStatusActions.tsx`: conditionally renders Activate/Deactivate buttons based on current status and user role; Deactivate shows confirmation dialog with reason input (React Hook Form, Zod: reason min 10 chars); Delete shows two-step confirmation with reason and `confirm_delete` checkbox; calls respective hooks; shows optimistic status change while request is in flight
- [x] T081 [US6] Create `frontend/src/app/(protected)/(companies)/admin/companies/page.tsx` (`AdminCompanyListPage`): only rendered for superadmin users; uses `useCompanies()` with admin parameters; renders `AdminCompanyTable`; includes search input, status filter dropdown, country filter, pagination controls
- [x] T082 [P] [US6] Create `frontend/src/components/companies/AdminCompanyTable.tsx`: sortable table of companies with columns: legal_name, slug, status, country, owner, created_at; row click navigates to company detail; loading skeleton state
- [x] T083 Update `frontend/src/components/layout/Sidebar.tsx`: add Companies navigation section with link to `/companies`; conditionally show Admin Companies link for superadmin users; highlight active route
- [x] T084 Create `frontend/src/__tests__/companies/CompanyCreateWizard.test.tsx`: step 1 validation prevents progression with empty legal_name, step 2 validates currency code, submit calls mutation, successful submit redirects, failed submit shows error toast
- [x] T085 [P] Create `frontend/src/__tests__/companies/CompanyStatusActions.test.tsx`: activate button shown for inactive company owner, deactivate confirmation dialog opens, reason field is required, confirmation dialog calls deactivate mutation, optimistic status update shown during flight

---

### Checkpoint 11

**Questions to Verify**:
- Can a user navigate to `/companies`, see the list, and click "Create Company"?
- Does the wizard prevent progression from step 1 with empty `legal_name`?
- Does successful company creation redirect to `/companies/{id}`?
- Is the `CompanyStatusBadge` rendering the correct color for each status?
- Do the Activate/Deactivate buttons show/hide correctly based on company status?
- Is the admin companies page invisible to non-superadmin users?
- Does the Sidebar show the Companies navigation item?

**Required Tests**: `npm test -- --testPathPattern=companies` — all component tests pass. Manual walkthrough: create a company end-to-end in the browser against the running backend.

**Expected Result**: Full company creation and detail view works end-to-end. Status toggle works. Admin view hidden from non-admins.

**Go / No-Go**: GO only if create wizard completes end-to-end and status actions work correctly.

---

**DO NOT IMPLEMENT in Phase 11**:
- Settings tabs and forms (Phase 12)
- Audit log page (Phase 12)
- Logo upload component (Phase 12)
- Regional settings form (Phase 12)
- Branding form (Phase 12)

---

## Phase 12: Company Settings UI

**Objective**: Build all company settings pages including profile edit form, regional settings, branding (with logo upload), and preferences. Add the audit log page.

**Scope**: Settings layout, all four settings tab pages, audit log page, all form components.

**Dependencies**: Phase 11 complete. `useUploadLogo`, `useCompanySettings` hooks (Phase 10). All form components use React Hook Form + Zod.

**Database Impact**: None.

**API Impact**: None.

**Frontend Impact**: Six new pages, six new components.

**Files Expected To Change**:
- `frontend/src/app/(protected)/(companies)/companies/[id]/settings/page.tsx` (new — redirect)
- `frontend/src/app/(protected)/(companies)/companies/[id]/settings/profile/page.tsx` (new)
- `frontend/src/app/(protected)/(companies)/companies/[id]/settings/regional/page.tsx` (new)
- `frontend/src/app/(protected)/(companies)/companies/[id]/settings/branding/page.tsx` (new)
- `frontend/src/app/(protected)/(companies)/companies/[id]/settings/preferences/page.tsx` (new)
- `frontend/src/app/(protected)/(companies)/companies/[id]/audit-log/page.tsx` (new)
- `frontend/src/components/companies/CompanySettingsTabs.tsx` (new)
- `frontend/src/components/companies/CompanyProfileForm.tsx` (update: add edit mode)
- `frontend/src/components/companies/CompanyAddressForm.tsx` (new)
- `frontend/src/components/companies/CompanyRegionalSettingsForm.tsx` (new)
- `frontend/src/components/companies/CompanyBrandingForm.tsx` (new)
- `frontend/src/components/companies/CompanyLogoUpload.tsx` (new)
- `frontend/src/components/companies/CompanyPreferencesForm.tsx` (new)
- `frontend/src/components/companies/CompanyAuditLogTable.tsx` (new)
- `frontend/src/__tests__/companies/CompanySettingsTabs.test.tsx` (new)

**Files That Must NOT Change**: Auth components. Existing company list/create/detail pages. Backend files.

---

### Tasks

- [x] T086 Create `frontend/src/components/companies/CompanySettingsTabs.tsx`: tab navigation component with four tabs (Profile, Regional, Branding, Preferences); uses Next.js `usePathname` to highlight active tab; accessible tab navigation with keyboard support; renders as horizontal tab bar above the settings content area
- [x] T087 [US2] Create `frontend/src/components/companies/CompanyProfileForm.tsx`: React Hook Form + Zod; fields: `legal_name`, `trade_name`, `email`, `phone_primary`, `phone_secondary`, `website`, `tax_number`, `registration_number`, `business_category`, `business_type`, `incorporation_date`; submit calls `useUpdateCompany()` mutation; field-level error messages from API's `details[]` array mapped via `setError()`; success toast notification; Zod mirrors backend validation (name min 2, email RFC, phone E.164 optional)
- [x] T088 [US2] Create `frontend/src/components/companies/CompanyAddressForm.tsx`: React Hook Form + Zod; country selector from ISO 3166 list (search-enabled); address_type selector; all address fields; used both in standalone dialog and within profile settings
- [x] T089 [US5] Create `frontend/src/components/companies/CompanyRegionalSettingsForm.tsx`: currency selector (ISO 4217 searchable dropdown — 180+ options); timezone selector (IANA — searchable, grouped by region); language selector (BCP 47 — supported locales); fiscal year start month selector (1–12 with month names); submit calls `useUpdateCompany()` mutation; currency change shows inline warning about historical transactions and requires checkbox confirmation
- [x] T090 [US2] Create `frontend/src/components/companies/CompanyLogoUpload.tsx`: drag-and-drop file input; shows image preview on selection; validates file size < 5MB client-side; validates file type (PNG/JPG/SVG/WebP) client-side; on submit calls `useUploadLogo()` mutation; shows upload progress indicator; on success updates preview with new URL; error state shows rejection reason
- [x] T091 [US2] Create `frontend/src/components/companies/CompanyBrandingForm.tsx`: logo upload section using `CompanyLogoUpload`; primary color hex input with color picker preview; secondary color hex input with color picker preview; tagline text input (max 255 chars with character counter); live preview panel showing current branding configuration
- [x] T092 [US5] Create `frontend/src/components/companies/CompanyPreferencesForm.tsx`: date format selector (6 common formats); decimal separator selector (`.` or `,`); thousands separator selector (`,`, `.`, ` `); invoice prefix text input; PO prefix text input; submit calls `useCompanySettings()` mutation
- [x] T093 Create settings page files: `settings/page.tsx` (server redirect to `settings/profile`), `settings/profile/page.tsx` (renders `CompanySettingsTabs` + `CompanyProfileForm` + address list with `CompanyAddressForm` in dialog), `settings/regional/page.tsx` (renders `CompanySettingsTabs` + `CompanyRegionalSettingsForm`), `settings/branding/page.tsx` (renders `CompanySettingsTabs` + `CompanyBrandingForm`), `settings/preferences/page.tsx` (renders `CompanySettingsTabs` + `CompanyPreferencesForm`)
- [x] T094 Create `frontend/src/app/(protected)/(companies)/companies/[id]/audit-log/page.tsx` (`CompanyAuditLogPage`): uses `useCompanyAuditLog(id, filters)` hook; date range picker for `date_from`/`date_to` filter; action type filter dropdown; pagination controls; renders `CompanyAuditLogTable`
- [x] T095 [P] Create `frontend/src/components/companies/CompanyAuditLogTable.tsx`: table with columns: timestamp, actor, action, details (collapsed JSON viewer for before/after state); pagination; loading skeleton; empty state message
- [x] T096 Create `frontend/src/__tests__/companies/CompanySettingsTabs.test.tsx`: active tab highlighted based on pathname, tab navigation links to correct routes, tab renders correct content component

---

### Checkpoint 12

**Questions to Verify**:
- Can a user update the company legal name and see the change reflected immediately?
- Does the currency change show a warning and require confirmation?
- Can a user upload a logo (PNG, < 5MB) and see it previewed immediately after upload?
- Does the logo upload correctly reject a file > 5MB with a user-visible error?
- Does the regional settings form show the timezone grouped by region?
- Is the audit log paginated correctly with working filters?
- Are all settings tabs accessible via keyboard navigation?

**Required Tests**: `npm test -- --testPathPattern=companies` — all tests pass. Manual end-to-end: update profile, upload logo, set regional settings, view audit log.

**Expected Result**: All settings management functionality works. Logo upload complete with preview. Audit log displays correctly with filtering.

**Go / No-Go**: GO only if all settings forms save correctly and logo upload works end-to-end.

---

**DO NOT IMPLEMENT in Phase 12**:
- Performance tests (Phase 15)
- Security hardening tests (Phase 16)
- Subscription settings (future epic)
- White label / subdomain settings (future epic)

---

## Phase 13: Integration Testing

**Objective**: Execute comprehensive integration test suite. Fix any failures found. Ensure all acceptance criteria (AC-001 to AC-012) pass.

**Scope**: Running and validating all existing integration tests. Adding any missing coverage discovered during this phase.

**Dependencies**: Phases 1–12 complete. Test database seeded with realistic fixture data.

**Database Impact**: Test database only.

**API Impact**: None.

**Frontend Impact**: None.

**Files Expected To Change**: Any test file found to have coverage gaps. `backend/tests/conftest.py` if fixtures need updating. Frontend test files if gaps found.

**Files That Must NOT Change**: All production source files (fix tests, not workarounds).

---

### Tasks

- [x] T097 Run full backend integration test suite: `pytest tests/integration/ -v --tb=short` — document any failures; fix any failures by correcting source code (not by weakening test assertions)
- [x] T098 [P] Run full backend unit test suite: `pytest tests/unit/ -v --cov=backend/modules/companies/ --cov-report=html` — confirm 90%+ branch coverage on all companies module files; document any files below threshold; add missing test cases to reach threshold
- [x] T099 [P] Run full backend security test suite: `pytest tests/security/companies/ -v` — confirm all tenant isolation, permission matrix, sensitive field masking, logo security, and rate limiting tests pass
- [x] T100 Run all frontend tests: `npm test -- --coverage --testPathPattern=companies` — confirm 80%+ coverage on company components and hooks; document any gaps
- [x] T101 Verify all 12 acceptance criteria groups from spec.md §18 are covered by named test cases; create a traceability comment in each test file mapping to its AC number(s); any uncovered AC → add test case in this task
- [x] T102 [P] Run regression tests for Epic 2 (auth): `pytest tests/integration/api/v1/auth/ tests/security/ -v` — zero regressions from Epic 3 changes; if any regression found, fix in production source without weakening auth tests
- [x] T103 [P] Verify domain event outbox entries for all 11 event types: write a test `test_event_outbox_completeness.py` in `tests/security/companies/` that performs each state-changing operation and asserts the correct `event_type` record exists in `event_outbox` with correct `aggregate_id` and non-null `payload`

---

### Checkpoint 13

**Questions to Verify**:
- Do all `pytest tests/integration/api/v1/companies/` tests pass (100% green)?
- Is branch coverage ≥ 90% for all files in `backend/modules/companies/`?
- Do all `pytest tests/security/companies/` tests pass?
- Do all `npm test -- --testPathPattern=companies` tests pass?
- Are all 12 AC groups from spec.md §18 covered by test cases?
- Does `pytest tests/integration/api/v1/auth/` pass with zero regressions?

**Required Tests**: All tests listed in Phase 13 tasks. Generate coverage HTML report. Review for red sections.

**Expected Result**: 100% integration test pass rate. 90%+ backend branch coverage. 80%+ frontend coverage. Zero Epic 2 regressions.

**Go / No-Go**: GO only if all thresholds met and zero regressions found.

---

**DO NOT IMPLEMENT in Phase 13**:
- Performance test execution (Phase 15)
- Security audit report (Phase 16)
- New features or endpoints
- Any refactoring not directly fixing a test failure

---

## Phase 14: Documentation

**Objective**: Complete all developer-facing documentation. Update project context files.

**Scope**: `quickstart.md`, `CLAUDE.md` update, `.env.example` review, API documentation, operational notes.

**Dependencies**: Phases 1–13 complete.

**Database Impact**: None.

**API Impact**: None.

**Frontend Impact**: None.

**Files Expected To Change**:
- `specs/003-companies/quickstart.md` (new)
- `CLAUDE.md` (update Recent Changes and Active Technologies sections)
- `docs/api/companies.md` (new if docs directory exists)
- `backend/modules/companies/README.md` (new — module-level developer guide)

**Files That Must NOT Change**: spec.md, plan.md, tasks.md. All source code. All test files.

---

### Tasks

- [x] T104 Create `specs/003-companies/quickstart.md` documenting: prerequisites (Docker, Python, Node.js versions), setup steps (`docker compose up`, `alembic upgrade head`, `npm install`), how to run backend tests (`pytest tests/`), how to run frontend tests (`npm test`), how to access MinIO console, common development workflows (create company, upload logo, view audit log), how to seed test data, troubleshooting (MinIO connection error, migration failure)
- [x] T105 [P] Update `CLAUDE.md` Recent Changes section to add: `003-companies: Added Companies module — full multi-tenant company lifecycle (CRUD, status management, soft delete/restore, audit logging, domain events, S3 logo storage, company settings, address management)`; update Active Technologies section to add: `python-magic (MIME validation)`, `boto3 (S3-compatible storage)`, `minio (local file storage development)`, `zoneinfo (IANA timezone validation)`
- [x] T106 [P] Create `backend/modules/companies/README.md` documenting: module purpose and scope, layer overview (models/repos/services/schemas/router), key business rules summary, how to add a new settings key to `ALLOWED_SETTINGS`, how to add a new audit event type, how to add a new status transition, known limitations (RBAC simplified until Epic 4), future enhancements reference

---

### Checkpoint 14

**Questions to Verify**:
- Does `quickstart.md` allow a new developer to get the companies module running from scratch by following the steps?
- Does `CLAUDE.md` accurately reflect the current technology additions?
- Does `backend/modules/companies/README.md` explain the `ALLOWED_SETTINGS` extension point?

**Required Tests**: Manual: follow `quickstart.md` steps on a clean environment. Verify each step succeeds as documented.

**Expected Result**: Any developer can follow `quickstart.md` and have the module running with tests passing. No hardcoded values found anywhere.

**Go / No-Go**: GO only if quickstart.md verified working end-to-end on a clean Docker environment.

---

**DO NOT IMPLEMENT in Phase 14**:
- Architecture Decision Records (user must consent: `/sp.adr` command)
- Changelog or release notes (future process)
- External API documentation (Swagger UI is auto-generated by FastAPI)

---

## Phase 15: Performance Validation

**Objective**: Validate all performance NFRs from spec.md §6.1 with realistic data volumes. Fix any failing benchmarks by optimizing queries (never by relaxing thresholds).

**Scope**: Performance test execution. Seed script. EXPLAIN ANALYZE verification. Index review.

**Dependencies**: Phase 13 complete. Test database accessible.

**Database Impact**: 10,000 company records seeded into test database for benchmark tests.

**API Impact**: None.

**Frontend Impact**: None.

**Files Expected To Change**:
- `backend/scripts/seed_companies.py` (new — seed script for 10,000 records)
- `backend/tests/performance/companies/test_company_read_performance.py` (new)
- `backend/tests/performance/companies/test_company_list_performance.py` (new)

**Files That Must NOT Change**: Production source code (fix via queries/indexes, not by relaxing thresholds).

---

### Tasks

- [x] T107 Create `backend/scripts/seed_companies.py` that inserts 10,000 company records with varied statuses, countries, and currencies into the test PostgreSQL database using SQLAlchemy bulk insert; runs in < 60 seconds; idempotent (checks count before seeding); documents seed command in `quickstart.md`
- [x] T108 Create `backend/tests/performance/companies/test_company_read_performance.py` using `pytest-benchmark`; with 10,000 records: `GET /api/v1/companies/{id}` via httpx must complete in < 200ms at p95 (run 50 iterations); `PATCH /api/v1/companies/{id}` with minimal update in < 500ms at p95
- [x] T109 [P] Create `backend/tests/performance/companies/test_company_list_performance.py`; `GET /api/v1/admin/companies?page=1&page_size=25` in < 500ms at p95 with 10,000 records; `GET /api/v1/admin/companies?search=acme` with partial name search in < 1s at p95
- [x] T110 Run `EXPLAIN ANALYZE` on the 5 most frequently used queries (`get_by_id`, `list_by_owner`, `exists_by_name`, `list_all_active`, `audit_log_by_company`) in psql; confirm each uses an index (no Seq Scan on companies or company_audit_logs for any indexed query path); document results in `specs/003-companies/quickstart.md`

---

### Checkpoint 15

**Questions to Verify**:
- Does `GET /companies/{id}` return within 200ms p95 with 10,000 records?
- Does list query return within 500ms p95?
- Does `EXPLAIN ANALYZE` on `get_by_id` show Index Scan (not Seq Scan)?
- Does `EXPLAIN ANALYZE` on `exists_by_name` use the expression index on `lower(legal_name)`?
- Does `POST /companies` complete within 1 second p95 (including uniqueness check)?

**Required Tests**: `pytest tests/performance/companies/ -v --benchmark-only` — all benchmarks within NFR thresholds.

**Expected Result**: All performance NFRs from spec.md §6.1 (NFR-001 through NFR-005) pass. No sequential scans on indexed columns.

**Go / No-Go**: GO only if all benchmarks pass. If any benchmark fails, identify the slow query, add or fix the relevant index, re-run — do NOT relax the threshold.

---

**DO NOT IMPLEMENT in Phase 15**:
- Caching layer (Redis) — not in scope for this epic
- Read replicas — infrastructure concern, not application code
- Query result pagination tuning beyond what already exists

---

## Phase 16: Security Review

**Objective**: Execute all security tests. Perform a manual security audit of the companies module. Document findings. Fix all identified issues before epic closure.

**Scope**: Security test suite execution. Manual code review against OWASP Top 10. Audit log immutability verification at DB level.

**Dependencies**: Phase 13 complete.

**Database Impact**: Verify audit log table permissions at PostgreSQL role level.

**API Impact**: None.

**Frontend Impact**: None.

**Files Expected To Change**:
- `backend/tests/security/companies/test_tenant_isolation.py` (new — if not already created in Phase 9)
- `backend/tests/security/companies/test_company_permissions.py` (new)
- `backend/tests/security/companies/test_sensitive_field_masking.py` (new)
- `backend/tests/security/companies/test_logo_upload_security.py` (new)
- `backend/tests/security/companies/test_rate_limiting.py` (new)

**Files That Must NOT Change**: All production source files (this is a review phase; fixes only if issues found).

---

### Tasks

- [x] T111 Create and run `backend/tests/security/companies/test_tenant_isolation.py`: create two companies (CompanyA, CompanyB) with different owners; verify user_A cannot GET CompanyB, cannot PATCH CompanyB, cannot DELETE CompanyB, cannot GET CompanyB addresses, cannot GET CompanyB audit log; all return 403, never 404 (to prevent information leakage about existence); verify company_id cannot be overridden via request body
- [x] T112 [P] Create and run `backend/tests/security/companies/test_company_permissions.py`: test every role (owner, admin, manager, accountant, sales, inventory) against every endpoint; verify the full permissions matrix from spec.md §8.2 is enforced; each entry in the matrix generates one test case
- [x] T113 [P] Create and run `backend/tests/security/companies/test_sensitive_field_masking.py`: GET company as owner → tax_number and registration_number are unmasked; GET company as manager → both are `"****"`; GET company as accountant → both are unmasked; GET company as sales role → both are `"****"`
- [x] T114 [P] Create and run `backend/tests/security/companies/test_logo_upload_security.py`: valid PNG upload succeeds; PNG file renamed to `.exe` succeeds (magic bytes detect PNG correctly); SVG containing `<script>` tag raises 400 LOGO_INVALID_CONTENT; JPEG with corrupted header raises 400 LOGO_INVALID_CONTENT; multipart request without file field raises 422; file with `.jpg` extension but PDF magic bytes raises 400 LOGO_INVALID_CONTENT; filename with path traversal characters (e.g., `../../etc/passwd.png`) is stored as system-generated UUID name (not original filename)
- [x] T115 [P] Create and run `backend/tests/security/companies/test_rate_limiting.py`: submit 11 `POST /companies` requests from the same user within 1 minute; the 11th request returns 429 with `X-RateLimit-Remaining: 0` and a retry-after indicator; verify the rate limit resets after the window; verify different users have independent rate limit counters
- [x] T116 Verify at the PostgreSQL role level that the application database user cannot `UPDATE` or `DELETE` rows from `company_audit_logs`; execute `UPDATE company_audit_logs SET action='TAMPERED' WHERE id=...` as the application user and verify it is rejected by PostgreSQL with a permission error; document verification steps and result in `specs/003-companies/quickstart.md`

---

### Checkpoint 16

**Questions to Verify**:
- Do all 5 security test files pass with zero failures?
- Does the tenant isolation test confirm 403 (not 404) for cross-tenant reads?
- Are all cells in the permissions matrix from spec.md §8.2 covered by a test?
- Does the PostgreSQL role test confirm the application user cannot UPDATE audit_logs?
- Does logo upload correctly reject JPEG files with corrupted headers?
- Does the rate limiting test confirm the 11th request is rejected?

**Required Tests**: `pytest tests/security/companies/ -v` — 100% pass. Manual: attempt `UPDATE company_audit_logs` as application db user — expect rejection.

**Expected Result**: Zero security test failures. Audit log confirmed immutable at database role level. All permission matrix cells verified.

**Go / No-Go**: GO only if all security tests pass and audit log immutability confirmed at DB level. Any security test failure is a blocker.

---

**DO NOT IMPLEMENT in Phase 16**:
- Row Level Security (RLS) policies (future epic)
- Custom domain / subdomain routing (future epic)
- Penetration testing (external process)
- White label configuration (future epic)

---

## Phase 17: Epic Finalization

**Objective**: Full regression, architecture audit, repository cleanup, and epic closure. This is the gate before the branch is merged to main.

**Scope**: All tests. Code cleanup. CLAUDE.md final update. Branch preparation.

**Dependencies**: Phases 1–16 all complete and all checkpoints GO.

**Database Impact**: None.

**API Impact**: None.

**Frontend Impact**: None.

**Files Expected To Change**:
- `CLAUDE.md` (confirm final state reflects Epic 3 completion)
- Any source file requiring cleanup (unused imports, TODO resolution, dead code)

---

### Tasks

- [x] T117 Run complete backend test suite: `pytest tests/ -v --tb=short --cov=backend/modules/companies/ --cov-report=term` — 100% pass rate; 90%+ branch coverage on companies module; zero regressions in auth tests
- [x] T118 [P] Run complete frontend test suite: `npm test -- --coverage` — 100% pass rate; 80%+ coverage on company components and hooks; zero regressions in auth components
- [x] T119 [P] Run full linting and type checking: `ruff check backend/` (zero errors), `mypy backend/modules/companies/ --ignore-missing-imports` (zero errors), `npx tsc --noEmit` (zero TypeScript errors), `npx eslint frontend/src/` (zero errors)
- [x] T120 Architecture review: manually verify each layer boundary — confirm no `router.py` file contains business logic (SQL queries or business rules), confirm no `repository` file contains if/else business decisions, confirm no `service` file imports `FastAPI`, `Request`, or `Response` types; document finding as PASS or list violations for fixing
- [x] T121 [P] Remove all temporary files, unused imports, commented-out debug code, and TODO comments that were resolved in this epic; verify no `print()` statements in production source files; verify no hardcoded test credentials or secrets in source files; verify no `console.log` in production frontend source
- [x] T122 Verify Definition of Done checklist from spec.md §18 and plan.md §18 — mark each criterion PASS or FAIL with evidence; all 25 criteria must be PASS; document results in a comment on this task
- [x] T123 [P] Confirm all three ADR suggestions from plan.md §19.3 have been either documented via `/sp.adr` or explicitly deferred by the user — do not auto-create ADRs; if not documented, print reminder to user
- [x] T124 Final `CLAUDE.md` review: confirm `Recent Changes` section accurately describes Epic 3 completion; confirm `Active Technologies` section lists all new libraries added; no placeholder text remains

---

### Checkpoint 17 — Epic Closure

**Questions to Verify**:
- Do 100% of backend integration tests pass?
- Do 100% of frontend tests pass?
- Is branch coverage ≥ 90% for `backend/modules/companies/`?
- Is frontend component coverage ≥ 80%?
- Does `ruff check backend/` report zero errors?
- Does `npx tsc --noEmit` report zero errors?
- Does the architecture review confirm no layer boundary violations?
- Are all 25 Definition of Done criteria marked PASS?
- Is `CLAUDE.md` fully up to date?
- Are there no debug statements, hardcoded secrets, or placeholder TODOs in the codebase?

**Required Tests**: All test suites (unit, integration, security, performance, frontend) must run green in sequence.

**Expected Result**: The `003-companies` branch is production-ready and passes all quality gates.

**Go / No-Go**: GO (merge to main) ONLY if every criterion above is PASS. A single failing criterion blocks merge.

---

## Dependencies and Execution Order

### Phase Dependencies

```
Phase 1 (Preparation)
    ↓
Phase 2 (Models)
    ↓
Phase 3 (Migration)
    ↓
Phase 4 (Repositories)
    ↓
Phase 5 (Validators + Exceptions)    ← can start parallel with Phase 4
    ↓
Phase 6 (Schemas)                    ← requires Phase 5
    ↓
Phase 7 (Services)                   ← requires Phases 4, 5, 6
    ↓
Phase 8 (Dependencies)               ← requires Phase 7
    ↓
Phase 9 (API Router)                 ← requires Phases 6, 7, 8
    ↓
Phase 10 (Frontend Foundation)       ← requires Phase 9
    ↓
Phase 11 (Company Management UI)     ← requires Phase 10
    ↓
Phase 12 (Company Settings UI)       ← requires Phase 11
    ↓
Phase 13 (Integration Testing)       ← requires Phases 1–12
    ↓
Phase 14 (Documentation)             ← can parallel with Phase 13
Phase 15 (Performance)               ← can parallel with Phase 14
Phase 16 (Security Review)           ← can parallel with Phase 14
    ↓
Phase 17 (Epic Finalization)         ← requires Phases 13–16
```

### User Story → Phase Mapping

| User Story | Primary Phase | Secondary Phases |
|------------|--------------|-----------------|
| US1: Company Creation | Phase 9 (T042, T050, T051) | Phase 10 (T059–T064), Phase 11 (T074–T079) |
| US2: Profile Management | Phase 9 (T046, T052, T056) | Phase 10 (T065, T068), Phase 12 (T087–T091) |
| US3: Activation/Deactivation | Phase 9 (T043, T053) | Phase 10 (T066), Phase 11 (T080) |
| US4: Soft Delete/Restore | Phase 9 (T044, T054) | Phase 10 (T067) |
| US5: Settings Management | Phase 9 (T045, T055) | Phase 10 (T069–T071), Phase 12 (T089, T092, T093) |
| US6: Listing/Search | Phase 9 (T048, T058) | Phase 10 (T071), Phase 11 (T081, T082) |

### Parallel Opportunities Within Phases

- **Phase 1**: T004 and T005 (event outbox) parallel with T006 (storage client)
- **Phase 4**: T018, T019, T020 (three repositories) all parallel
- **Phase 5**: T023 (exceptions) parallel with T024 (validators)
- **Phase 6**: T027, T028, T029, T030 all parallel (different schema files)
- **Phase 7**: T032, T033, T034 parallel; T035 depends on all three
- **Phase 9**: T050–T058 all parallel (different test files for different endpoints)
- **Phase 10**: T062–T072 all parallel (independent hook files)
- **Phase 11**: T075, T076, T077 parallel (independent components)
- **Phase 16**: T112, T113, T114, T115 all parallel (different security concerns)

---

## Implementation Strategy

### MVP Scope (Minimum Viable Product)

**To deliver US1 (Company Creation) as MVP**:
1. Complete Phases 1–9 (foundation through API router) — these are all required
2. Complete Phase 10 (frontend hooks) and Phase 11 up to T079 (detail page)
3. Validate: user can create a company, view it, and activate it
4. This is a shippable increment — all subsequent stories add on top

### Incremental Delivery Order

| Increment | Phases | Delivers |
|-----------|--------|---------|
| 1 (MVP) | 1–9, 10, 11 partial | Create + View + Activate company |
| 2 | 11 complete | Status management + Admin view |
| 3 | 12 partial | Profile editing + Logo upload |
| 4 | 12 complete | Full settings (regional, branding, preferences, audit log) |
| 5 | 13–17 | Tested, documented, production-ready |

### Claude Code Execution Notes

- Implement exactly ONE phase per session. Do not implement future phases speculatively.
- Each phase's "DO NOT IMPLEMENT" section is a hard boundary.
- If a phase checkpoint fails (Go/No-Go = NO), stop and resolve the blocker before continuing.
- All file paths in tasks are absolute from the repository root.
- Commit after each task group (models, repositories, services) for clean git history.
- Never skip a checkpoint — each is a structural quality gate, not optional verification.

---

## Notes

- `[P]` tasks share no file dependencies and can be implemented simultaneously
- Each User Story phase produces an independently demonstrable feature
- Checkpoints are Go/No-Go gates — do not proceed to the next phase without GO
- All 116 tasks have unique IDs (T001–T124); IDs are in execution order
- Test tasks are included because spec.md mandates audit completeness and security testing
- DO NOT IMPLEMENT sections are enforced — they protect against scope creep
