# Implementation Plan: Foundation Platform

**Branch**: `001-foundation-platform` | **Date**: 2026-07-11 | **Spec**: [spec.md](./spec.md)

---

## Summary

Epic 1 establishes the complete technical foundation of the DevSphere ERP platform. The implementation creates a monorepo containing a FastAPI backend and a Next.js frontend, orchestrated by Docker Compose, with PostgreSQL as the primary database managed by Alembic. The plan is structured in eight sequential phases, each leaving the project in a verifiable working state. Every phase produces a concrete, testable deliverable, and no phase proceeds until the prior phase is validated. This foundation must be correct from the start — it is the substrate on which every future ERP module will be built.

---

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy, Alembic, Next.js (App Router), Tailwind CSS, shadcn/ui
**Storage**: PostgreSQL 16 LTS (Docker Compose in development; Neon PostgreSQL in production)
**Testing**: pytest + httpx (backend), Jest + React Testing Library (frontend)
**Target Platform**: Linux container (Docker); Developer machines (Windows/macOS/Linux via Docker)
**Project Type**: Web application — separate backend and frontend with API communication
**Performance Goals**: Health check response < 200ms; `docker compose up` completion < 60 seconds; hot reload < 3s (backend), < 5s (frontend)
**Constraints**: No business logic in this Epic; no auth implementation; no cross-module coupling; all secrets via environment variables
**Scale/Scope**: Foundation for multi-tenant SaaS ERP; designed to support 10+ future ERP modules and unlimited tenant growth

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked post-design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Modular Monolith Architecture (§5) | PASS | Backend organized as `core/` + `modules/`; modules directory is empty in this Epic but the structure is established |
| Layered Architecture (§5.3) | PASS | API → Service → Repository → Database; enforced via base class design |
| Repository Pattern (§13) | PASS | `BaseRepository` defined in `core/repositories/`; only repositories touch the database |
| Service Layer Pattern (§14) | PASS | `BaseService` defined in `core/services/`; all business logic lives here |
| Multi-Tenant Readiness (§9) | PASS | `TenantBaseModel` with `company_id`; `BaseRepository` requires `company_id` on all queries |
| Better Auth Readiness (§16) | PASS | Auth hook middleware placeholder + `core/auth/interfaces.py` stubs |
| API Versioning (§32) | PASS | All routes under `/api/v1/` prefix |
| Database — PostgreSQL + Alembic (§17, §18) | PASS | Engine, session, migrations all configured |
| Configuration Management (§20) | PASS | Centralized `Settings` class; no scattered `os.getenv()` |
| Error Handling (§21) | PASS | Centralized exception handler; standard error response schema |
| Logging (§22) | PASS | Structured JSON logging with all required fields |
| Docker (§27) | PASS | `docker compose up` starts all services; hot reload in development |
| Security (§19, NFR-011 to NFR-015) | PASS | No secrets in code; `.env` in `.gitignore`; CORS restricted; non-root containers |
| Code Quality (§24) | PASS | Black, Ruff, mypy (backend); ESLint, Prettier, TypeScript strict (frontend) |
| Testing (§31) | PASS | Unit + integration test infrastructure established |
| No Business Logic | PASS | Zero business functionality implemented in this Epic |

**Constitution Check Result**: ALL GATES PASS — Proceed to implementation.

---

## Project Structure

### Documentation (this feature)

```text
specs/001-foundation-platform/
├── spec.md              — Approved specification
├── plan.md              — This file
├── research.md          — Phase 0 technology decisions and rationale
├── data-model.md        — Phase 1 entity model definitions
├── quickstart.md        — Phase 1 developer quickstart guide
├── contracts/           — Phase 1 API contracts
│   └── health.yaml      — Health check endpoint OpenAPI contract
└── tasks.md             — Phase 2 output (created by /sp.tasks)
```

### Source Code (repository root)

```text
erp-system/                         — Monorepo root
├── backend/                        — FastAPI application
│   ├── core/                       — Platform layer (shared by all modules)
│   │   ├── config/settings.py      — Centralized Settings class
│   │   ├── database/               — Engine, session, base models
│   │   ├── logging/setup.py        — Structured JSON logging
│   │   ├── exceptions/             — Exception hierarchy + global handler
│   │   ├── middleware/             — Request ID, CORS, auth hook
│   │   ├── schemas/                — StandardResponse, ErrorResponse, PaginatedResponse
│   │   ├── repositories/base.py    — BaseRepository (generic, typed, tenant-scoped)
│   │   ├── services/base.py        — BaseService
│   │   ├── utils/                  — UUID, datetime, pagination utilities
│   │   └── auth/interfaces.py      — Auth interface stubs (Better Auth readiness)
│   ├── modules/                    — Empty; future ERP modules go here
│   ├── api/v1/router.py            — Version 1 API router
│   ├── migrations/                 — Alembic migration directory
│   ├── tests/unit/core/            — Core unit tests
│   ├── tests/integration/api/      — API integration tests
│   ├── main.py                     — Application factory + ASGI entrypoint
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .dockerignore
├── frontend/                       — Next.js application
│   ├── src/app/                    — App Router pages and layouts
│   ├── src/components/ui/          — shadcn/ui components
│   ├── src/components/layout/      — AppLayout, Header, Sidebar
│   ├── src/lib/api/                — Typed API client
│   ├── src/types/                  — Global TypeScript types
│   ├── package.json
│   ├── tsconfig.json
│   ├── Dockerfile
│   └── .dockerignore
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

**Structure Decision**: Web application pattern (Option 2 from template). Backend and frontend are separate applications communicating exclusively via HTTP API. The `core/` + `modules/` split within the backend enforces the Modular Monolith architecture mandated by the Constitution.

---

## Complexity Tracking

No Constitution violations. All patterns used are mandated by the Constitution and Specification.

---

## Architecture Validation

### Modular Monolith Compliance

The implementation fully satisfies the Modular Monolith requirement (Constitution §5). The `core/` directory is the platform layer — shared infrastructure accessible by all modules. The `modules/` directory will contain business module vertical slices. In this Epic, `modules/` is scaffolded but empty, which is correct: no business functionality belongs here.

The key architectural quality is that `core/` components are designed for extension, not modification. Future modules extend `BaseModel`, `BaseRepository`, and `BaseService` — they do not change the core layer.

### Repository Pattern Compliance

`BaseRepository` is the only class that touches the database. The method signatures enforce the pattern:
- All data access methods are `def` methods on the repository class, not on services or handlers.
- All tenant-scoped methods require `company_id` as a mandatory parameter.
- Services are the only callers of repositories.

The pattern is enforced architecturally (services receive repository instances via dependency injection) and by code review standards.

### Service Layer Compliance

`BaseService` is the holder of business operations. In this Epic, no concrete services are implemented (because no business logic exists). The base class establishes the injection pattern. Services must remain framework-independent — they must not import from FastAPI's `Request`, `Response`, or `HTTPException`.

### Multi-Tenant Readiness

Multi-tenancy is enforced at two levels:
1. **Data model**: `TenantBaseModel` mandates `company_id` on every business entity.
2. **Data access**: `BaseRepository` methods are designed to require `company_id`. Any attempt to query without scoping fails at the type level.

No tenant data exists yet in this Epic (no `companies` table). The design is correct: the patterns are in place before the data exists.

### Better Auth Readiness

Authentication is out of scope for this Epic, but the implementation prepares three integration points:
1. `core/auth/interfaces.py` — Protocol/abstract definitions for the current user, session, and permission checker. Future services depend on these interfaces, not on Better Auth directly.
2. `core/middleware/auth_hook.py` — A documented pass-through middleware stub that marks the exact insertion point for Better Auth middleware.
3. FastAPI dependency stubs for `get_current_user` and `require_permission` — These return `None` or a no-op in this Epic and will be replaced in the Authentication Epic.

### Implementation Considerations

1. **SQLAlchemy Sync vs. Async**: This implementation uses synchronous SQLAlchemy for simplicity (Spec Assumption 6). If async is needed later, the `core/database/` layer is isolated enough to migrate without touching module code. This is an architectural decision worth an ADR.
2. **BaseRepository Generics**: Python generics with SQLAlchemy require careful design. The `BaseRepository[ModelType]` pattern uses `TypeVar` and `Generic` from the Python `typing` module. This must be validated during implementation.
3. **Pydantic v2 Breaking Changes**: The project mandates Pydantic v2. Several Pydantic v1 patterns (validators, `orm_mode`, `json()`) have changed. All schemas must use Pydantic v2 APIs (`model_validator`, `model_config`, `model_dump()`).

---

## Implementation Strategy

### Guiding Principle: Foundation First, Layer by Layer

The implementation follows strict bottom-up layering. Infrastructure that other components depend on is built first. Each phase produces working, testable software — there are no "skeleton" phases that produce untestable code.

### Why This Order Was Selected

1. **Configuration must be first**: Every other component depends on `Settings`. Without a working `Settings` class, nothing can be initialized.
2. **Logging must be second**: Once configuration is loaded, logging must be active before any other component starts, so that startup events, errors, and lifecycle events are captured.
3. **Database must precede repositories**: `BaseRepository` needs a working SQLAlchemy session. The session needs a working engine. The engine needs a working `DATABASE_URL` from Settings.
4. **Exception handling precedes API**: The exception handler must be registered before any routes are added, so all routes benefit from centralized error handling.
5. **Base patterns precede API router**: The router uses response schemas; schemas must exist before routes.
6. **Docker comes after working code**: It is easier to debug a working application than to debug both the application and Docker simultaneously.
7. **Frontend comes last among core components**: The frontend depends on the API being available to test the API client.

### Risk-Minimizing Development Sequence

Each phase is verified before the next begins. This means that at no point does the team have a half-working system where bugs could originate from multiple untested layers simultaneously.

---

## Implementation Phases

### Phase 0: Monorepo Scaffolding and Root Configuration

**Purpose**: Establish the physical project structure, version control configuration, and root-level infrastructure. This is the blank canvas on which everything else is built.

**Deliverables**:
- `erp-system/` monorepo root with `.gitignore`, `README.md`, `.env.example`
- `backend/` and `frontend/` directories scaffolded
- `specs/`, `history/adr/`, `history/prompts/` directories confirmed (already exist)
- Root-level `.env.example` documenting all environment variables

**Dependencies**: None — this is the first phase.

**Validation**:
- Repository root contains the expected directory structure.
- `.gitignore` includes `.env`, `__pycache__`, `node_modules`, `.next`, `*.pyc`.
- `.env.example` documents all backend and frontend environment variables.
- README.md describes the project and contains setup instructions.

---

### Phase 1: Backend Configuration and Code Quality Tooling

**Purpose**: Establish the Python project configuration, centralized Settings class, and all code quality tooling. After this phase, the backend is a valid Python project with enforced standards.

**Deliverables**:
- `backend/pyproject.toml` with Black, Ruff, mypy configuration
- `backend/core/config/settings.py` — `Settings` class (Pydantic BaseSettings)
- `backend/.env.example` with all backend variables documented
- `backend/main.py` skeleton (imports settings; no routes yet)
- Pre-commit hook configuration (`.pre-commit-config.yaml`)

**Dependencies**: Phase 0 complete.

**Validation**:
- `python -m black --check .` passes with zero errors.
- `python -m ruff check .` passes with zero errors.
- `python -m mypy .` passes with zero type errors.
- `Settings()` raises a clear `ValidationError` when `DATABASE_URL` is missing.
- `Settings()` loads correctly when all required variables are present.

---

### Phase 2: Structured Logging

**Purpose**: Establish structured JSON logging so that all subsequent phases produce observable output. Logging must be operational before the database, middleware, or API layers are initialized.

**Deliverables**:
- `backend/core/logging/setup.py` — JSON formatter and logging configuration
- Logging initialized in `main.py` application factory immediately after settings load
- Development (human-readable) and production (pure JSON) log format modes

**Dependencies**: Phase 1 complete (Settings needed to determine log level and environment).

**Validation**:
- Log output in development mode is human-readable with timestamp, level, logger, message, and request_id fields.
- Log output in production mode (`ENVIRONMENT=production`) is valid JSON, one object per line.
- Log entries do NOT include `DATABASE_URL`, `SECRET_KEY`, or any sensitive environment variable values.
- DEBUG, INFO, WARNING, ERROR, CRITICAL levels all produce correct output.

---

### Phase 3: Database Foundation

**Purpose**: Establish the PostgreSQL connection, SQLAlchemy engine and session management, base model classes, and Alembic migrations. After this phase, the database layer is fully operational.

**Deliverables**:
- `backend/core/database/engine.py` — SQLAlchemy engine configured from `DATABASE_URL`
- `backend/core/database/session.py` — `get_db()` FastAPI dependency
- `backend/core/database/base.py` — SQLAlchemy `DeclarativeBase`
- `backend/core/database/models/base_model.py` — `BaseModel` (id, created_at, updated_at)
- `backend/core/database/models/tenant_base.py` — `TenantBaseModel` (extends BaseModel + company_id, created_by, is_deleted, deleted_at)
- `backend/alembic.ini` — Alembic configuration
- `backend/migrations/env.py` — Alembic environment with autogenerate support
- `backend/migrations/versions/001_initial_baseline.py` — Initial empty migration

**Dependencies**: Phase 2 complete. PostgreSQL running (Docker or local).

**Validation**:
- `alembic upgrade head` runs on a fresh database with zero errors.
- `alembic downgrade base` runs after the upgrade with zero errors.
- `alembic history` shows the initial baseline revision.
- `BaseModel` contains `id` (UUID), `created_at` (TIMESTAMPTZ), `updated_at` (TIMESTAMPTZ).
- `TenantBaseModel` contains all `BaseModel` fields plus `company_id` (UUID FK), `created_by` (UUID FK), `is_deleted` (BOOLEAN), `deleted_at` (TIMESTAMPTZ nullable).
- The database session dependency yields a session and closes it after the request.

---

### Phase 4: Exception Handling

**Purpose**: Establish the application exception hierarchy and the centralized exception handler. After this phase, all errors in the application produce consistent, safe responses.

**Deliverables**:
- `backend/core/exceptions/base.py` — `ApplicationException` and all subclasses (Validation, NotFound, Conflict, Unauthorized, Forbidden, Infrastructure)
- `backend/core/exceptions/handler.py` — Global FastAPI exception handler mapping all exception types to HTTP responses
- `backend/core/schemas/response.py` — `StandardResponse`, `ErrorResponse` Pydantic schemas
- `backend/core/schemas/pagination.py` — `PaginatedResponse`, `PaginationParams` Pydantic schemas
- Exception handler registered in `main.py` application factory

**Dependencies**: Phase 2 complete (logging needed inside the handler). Phase 1 complete (schemas need Pydantic v2).

**Validation**:
- Raising `NotFoundException` from any route produces HTTP 404 with `{"error": {"code": "NOT_FOUND", "message": "...", "details": {}}}`.
- Raising `ValidationException` produces HTTP 422 with `code: "VALIDATION_ERROR"`.
- Raising an unhandled `Exception` produces HTTP 500 with `code: "INTERNAL_ERROR"` and no stack trace in the response body.
- The exception handler logs all exceptions with request_id and full context.
- All response schemas pass Pydantic v2 validation.

---

### Phase 5: Base Repository and Service Patterns

**Purpose**: Implement the `BaseRepository` and `BaseService` classes, establishing the reusable data access and business logic patterns. After this phase, future module developers have complete base classes to extend.

**Deliverables**:
- `backend/core/repositories/base.py` — `BaseRepository[ModelType]` with typed CRUD operations
- `backend/core/services/base.py` — `BaseService` with dependency injection infrastructure
- `backend/core/utils/uuid.py` — UUID generation utilities
- `backend/core/utils/datetime.py` — Timezone-aware timestamp utilities (UTC enforcement)
- `backend/core/utils/pagination.py` — Pagination offset/limit calculation utilities

**Dependencies**: Phase 3 complete (database session needed by repository). Phase 4 complete (exception types used in repository methods).

**Validation**:
- `BaseRepository` is a generic class parameterized by model type: `class BaseRepository(Generic[ModelType])`.
- `create()` persists a new entity and returns the created instance.
- `get_by_id(id, company_id)` returns the entity or raises `NotFoundException`.
- `list(company_id, skip, limit)` returns a tuple of (items, total_count).
- `soft_delete(id, company_id)` sets `is_deleted=True` and `deleted_at` to current UTC timestamp.
- All methods that accept `company_id` filter by it — queries without `company_id` are rejected at the type level.
- UUID utility generates valid UUID4 values.
- Datetime utility returns UTC-aware datetime objects.

---

### Phase 6: Middleware and API Layer

**Purpose**: Implement middleware chain, the FastAPI application factory, auth interface stubs, and the version 1 API router with the health check endpoint. After this phase, the backend is a fully running FastAPI application.

**Deliverables**:
- `backend/core/middleware/request_id.py` — Assigns UUID request_id to every request
- `backend/core/middleware/auth_hook.py` — Documented pass-through placeholder for Better Auth
- `backend/core/auth/interfaces.py` — Protocol definitions for CurrentUser, SessionContext, PermissionChecker
- `backend/api/v1/router.py` — Version 1 API router with health check endpoint
- `backend/main.py` — Complete application factory (create_app()) with all middleware, handlers, and routers registered

**Dependencies**: All prior phases complete.

**Validation**:
- `uvicorn main:app` starts without errors.
- Every request receives a unique `X-Request-ID` header in the response.
- `GET /api/v1/health` returns HTTP 200 with `{"data": {"status": "healthy", "database": "connected", "version": "...", "timestamp": "..."}, ...}`.
- When the database is unreachable, `GET /api/v1/health` returns HTTP 503 with `status: "degraded"`.
- Swagger UI is accessible at `/docs` when `DEBUG=true`.
- All logs include `request_id` matching the response `X-Request-ID` header.

---

### Phase 7: Docker Development Environment

**Purpose**: Containerize the backend and frontend, configure Docker Compose, and validate the one-command development environment. After this phase, the project satisfies the primary success criterion.

**Deliverables**:
- `backend/Dockerfile` — Development image with hot reload
- `backend/.dockerignore`
- `frontend/Dockerfile` — Development image with Next.js fast refresh
- `frontend/.dockerignore`
- `docker-compose.yml` — Orchestrates `db`, `api`, and `web` services with health checks, volumes, and dependency ordering
- `docker-compose.override.yml` (optional) — Development-specific volume mounts and port overrides

**Dependencies**: Phase 6 complete (working backend application).

**Validation**:
- `docker compose up` starts all three services without errors.
- `GET /api/v1/health` returns healthy response from within the Docker network.
- Changes to backend Python files trigger automatic reload within 3 seconds.
- Database data persists when `docker compose down` and `docker compose up` are run sequentially.
- `.env` is NOT included in any Docker image (verified with `docker image inspect`).
- Containers run as non-root users (verified with `docker exec <container> whoami`).

---

### Phase 8: Frontend Foundation

**Purpose**: Establish the Next.js application with TypeScript strict mode, Tailwind CSS, shadcn/ui, shared layout components, and the typed API client. After this phase, the complete project foundation is in place.

**Deliverables**:
- `frontend/` — Next.js application (App Router, TypeScript strict mode)
- `frontend/tsconfig.json` — Strict TypeScript configuration
- `frontend/tailwind.config.ts` — Design tokens and theme configuration
- `frontend/src/components/ui/` — shadcn/ui: Button, Input, Card, Dialog, Toast
- `frontend/src/components/layout/AppLayout.tsx` — Primary layout shell
- `frontend/src/components/layout/Header.tsx` — Header placeholder
- `frontend/src/components/layout/Sidebar.tsx` — Sidebar placeholder
- `frontend/src/lib/api/client.ts` — Typed fetch wrapper
- `frontend/src/lib/api/types.ts` — `StandardResponse<T>`, `PaginatedResponse<T>`, `ApiError` TypeScript types
- `frontend/src/types/index.ts` — Global TypeScript type definitions
- `frontend/.eslintrc.json` and `frontend/.prettierrc` — Code quality configuration

**Dependencies**: Phase 7 complete (Docker environment running; API available for client testing).

**Validation**:
- `tsc --noEmit` passes with zero type errors.
- `eslint .` passes with zero errors.
- `prettier --check .` passes with zero formatting errors.
- The Next.js application loads in the browser with no console errors.
- The `AppLayout` component renders without errors.
- The API client calls `NEXT_PUBLIC_API_URL/api/v1/health` successfully.

---

### Phase 9: Testing Infrastructure and Final Validation

**Purpose**: Implement unit and integration tests for the core platform layer, set up the frontend testing infrastructure, and perform final end-to-end validation. After this phase, the Epic is complete.

**Deliverables**:
- `backend/tests/unit/core/test_settings.py` — Settings validation tests
- `backend/tests/unit/core/test_exceptions.py` — Exception handler mapping tests
- `backend/tests/unit/core/test_logging.py` — Structured log field presence tests
- `backend/tests/unit/core/test_base_repository.py` — BaseRepository CRUD tests (using test database)
- `backend/tests/integration/api/test_health.py` — Health check endpoint integration tests
- `frontend/src/__tests__/AppLayout.test.tsx` — Layout smoke test
- `frontend/jest.config.ts` — Jest and React Testing Library configuration

**Dependencies**: All prior phases complete.

**Validation**:
- All backend unit tests pass: `pytest tests/unit/ -v`
- All backend integration tests pass: `pytest tests/integration/ -v`
- All frontend tests pass: `npm test`
- `pytest --tb=short` produces zero failures and zero errors.
- Code coverage for `core/` modules meets the defined minimum for critical paths.

---

## Component Breakdown

### Component 1: Settings (core/config/settings.py)

**Type**: Configuration
**Depends on**: Nothing (must be self-contained)
**Design**: Pydantic `BaseSettings` subclass with field-level validation. Reads from environment variables automatically. Raises `ValidationError` with a descriptive message when required fields are absent. Provides typed access properties for all configuration values. A singleton instance is created at module import time and shared via FastAPI dependency injection.

**Critical design decision**: Settings must NOT be instantiated multiple times. The pattern is to create one instance at module level and inject it where needed.

---

### Component 2: Structured Logging (core/logging/setup.py)

**Type**: Observability
**Depends on**: Settings (for log level and environment)
**Design**: Python's standard `logging` module with a custom `JSONFormatter` class. In production mode, the formatter serializes log records to JSON with all required fields (timestamp, level, logger, message, request_id, environment). In development mode, a human-readable formatter is used. The `request_id` is stored in a `contextvars.ContextVar` so it is accessible without threading issues in async environments.

---

### Component 3: Database Engine and Session (core/database/)

**Type**: Data Access Infrastructure
**Depends on**: Settings (for DATABASE_URL)
**Design**:
- `engine.py`: Creates a `create_engine()` instance with pool configuration from Settings.
- `base.py`: Defines the `DeclarativeBase` that all ORM models inherit.
- `session.py`: Creates a `sessionmaker` factory and a `get_db()` FastAPI generator dependency that yields a session and ensures `session.close()` is called.
- Pool parameters (`pool_size`, `max_overflow`) are configurable via Settings.

---

### Component 4: BaseModel and TenantBaseModel (core/database/models/)

**Type**: Data Model Foundation
**Depends on**: Database engine and DeclarativeBase
**Design**:
- `BaseModel`: Abstract SQLAlchemy mapped class with `id` (UUID, server default `gen_random_uuid()`), `created_at` (TIMESTAMPTZ, server default `NOW()`), `updated_at` (TIMESTAMPTZ, auto-updated on change).
- `TenantBaseModel`: Extends `BaseModel` adding `company_id` (UUID, non-nullable), `created_by` (UUID, nullable — null until user management exists), `is_deleted` (Boolean, default False), `deleted_at` (TIMESTAMPTZ, nullable).
- Both are `__abstract__ = True` — they do not create database tables themselves.

**Critical design decision**: `company_id` is a UUID column but is NOT a foreign key in this Epic (no `companies` table exists yet). The FK constraint will be added in the Company Management Epic via Alembic migration.

---

### Component 5: Alembic Migration Configuration

**Type**: Database Migration
**Depends on**: BaseModel, TenantBaseModel (for autogenerate to detect models)
**Design**:
- `alembic.ini` points to the migrations directory.
- `migrations/env.py` imports `DeclarativeBase.metadata` for autogenerate support.
- `migrations/env.py` reads `DATABASE_URL` from environment (not hardcoded).
- Initial migration (`001_initial_baseline.py`) is empty — baseline on a clean schema.
- `script.py.mako` template is the standard Alembic template.

---

### Component 6: Application Exception Hierarchy (core/exceptions/)

**Type**: Error Handling
**Depends on**: Nothing (pure Python, no framework dependencies)
**Design**:
- `ApplicationException(Exception)`: Base class with `code: str`, `message: str`, `details: dict`, `http_status: int` attributes.
- Subclasses: `ValidationException(422)`, `NotFoundException(404)`, `ConflictException(409)`, `UnauthorizedException(401)`, `ForbiddenException(403)`, `InfrastructureException(500)`.
- All subclasses provide default values for `code` (e.g., `"NOT_FOUND"`) while allowing override.
- The exception hierarchy is framework-independent — no FastAPI or HTTP imports in `base.py`.

---

### Component 7: Global Exception Handler (core/exceptions/handler.py)

**Type**: Error Handling
**Depends on**: Exception hierarchy, schemas, logging
**Design**:
- Registers with FastAPI via `app.add_exception_handler()`.
- Handles `ApplicationException` subclasses by extracting status code and error details.
- Handles `RequestValidationError` (Pydantic input validation failures) by mapping to `ValidationException`.
- Handles all other `Exception` types by logging the full stack trace and returning a generic `INTERNAL_ERROR` response.
- Always returns `ErrorResponse` JSON regardless of exception type.
- NEVER exposes stack traces, internal paths, or database error messages in the response body when `ENVIRONMENT != "development"`.

---

### Component 8: Common Pydantic Schemas (core/schemas/)

**Type**: API Contract
**Depends on**: Pydantic v2
**Design**:
- `StandardResponse[T]`: Generic success envelope with `data: T`, `message: str`, `meta: ResponseMeta`.
- `ResponseMeta`: `request_id: str`, `timestamp: datetime`.
- `ErrorResponse`: `error: ErrorDetail`.
- `ErrorDetail`: `code: str`, `message: str`, `details: dict`.
- `PaginatedResponse[T]`: `data: PaginatedData[T]`, `message: str`, `meta: ResponseMeta`.
- `PaginatedData[T]`: `items: list[T]`, `total: int`, `page: int`, `page_size: int`, `pages: int`.
- `PaginationParams`: FastAPI dependency for extracting `page` and `page_size` from query parameters.

---

### Component 9: BaseRepository (core/repositories/base.py)

**Type**: Data Access Pattern
**Depends on**: Database session, BaseModel, TenantBaseModel, exception hierarchy
**Design**:
- `BaseRepository(Generic[ModelType])` where `ModelType` is a TypeVar bound to `TenantBaseModel`.
- Constructor receives a `Session` instance.
- Methods:
  - `create(entity: ModelType) -> ModelType`
  - `get_by_id(id: UUID, company_id: UUID) -> ModelType` — raises `NotFoundException` if not found
  - `get_by_id_or_none(id: UUID, company_id: UUID) -> ModelType | None`
  - `list(company_id: UUID, skip: int = 0, limit: int = 20, include_deleted: bool = False) -> tuple[list[ModelType], int]`
  - `update(entity: ModelType) -> ModelType`
  - `soft_delete(id: UUID, company_id: UUID) -> None`
- The `list` method always filters by `is_deleted=False` unless `include_deleted=True`.
- All methods that take `company_id` add a `WHERE company_id = :company_id` clause unconditionally.

---

### Component 10: BaseService (core/services/base.py)

**Type**: Business Logic Pattern
**Depends on**: BaseRepository (receives via injection)
**Design**:
- `BaseService` is a simple base class with an `__init__` that accepts `db: Session`.
- Concrete services extend `BaseService` and declare their repository dependencies in `__init__`.
- `BaseService` does not contain any business logic itself — it is purely an infrastructure pattern.
- Services are instantiated via FastAPI dependency injection using `Depends()`.

---

### Component 11: Utility Modules (core/utils/)

**Type**: Shared Utilities
**Depends on**: Nothing (pure Python)
**Design**:
- `uuid.py`: `generate_uuid() -> UUID` using `uuid.uuid4()`.
- `datetime.py`: `utcnow() -> datetime` returning timezone-aware UTC datetime; `format_iso(dt: datetime) -> str` for ISO 8601 formatting.
- `pagination.py`: `calculate_pages(total: int, page_size: int) -> int`; `calculate_offset(page: int, page_size: int) -> int`.

---

### Component 12: Middleware Chain (core/middleware/)

**Type**: Request Processing
**Depends on**: Logging (request_id context var), Settings (CORS origins)
**Design**:
- `request_id.py`: ASGI middleware that reads `X-Request-ID` header or generates a new UUID; sets it in the `contextvars.ContextVar` for logging; adds it to the response headers.
- `auth_hook.py`: ASGI middleware that is a documented pass-through stub. Contains clear comments marking it as the insertion point for Better Auth middleware. Does not perform any authentication logic.

---

### Component 13: Auth Interface Stubs (core/auth/interfaces.py)

**Type**: Integration Contract
**Depends on**: Nothing
**Design**:
- `CurrentUser` Protocol: Defines the interface that an authenticated user object must satisfy (`id: UUID`, `company_id: UUID`, `email: str`, `is_active: bool`).
- `SessionContext` Protocol: Defines the session context contract.
- `PermissionChecker` Protocol: Defines the `has_permission(permission: str) -> bool` interface.
- FastAPI dependency stubs: `get_current_user_stub()` returns `None` (to be replaced in the Auth Epic); `require_permission_stub(permission: str)` is a no-op.
- All stubs are clearly documented as placeholders.

---

### Component 14: API v1 Router and Health Check (api/v1/router.py)

**Type**: API Layer
**Depends on**: All core components
**Design**:
- `APIRouter` with prefix `/api/v1`.
- Health check endpoint: `GET /api/v1/health` — attempts a lightweight database query (`SELECT 1`); returns healthy or degraded status.
- OpenAPI tags: `["Health"]`.
- The router is the aggregation point for all future module routers.

---

### Component 15: Application Factory (main.py)

**Type**: Application Entrypoint
**Depends on**: All prior components
**Design**:
- `create_app() -> FastAPI`: Creates and configures the FastAPI application instance.
- Initialization sequence:
  1. Load Settings.
  2. Configure logging.
  3. Create FastAPI instance with title, description, version, and docs_url configuration.
  4. Add CORS middleware.
  5. Add request ID middleware.
  6. Add auth hook middleware.
  7. Register exception handlers.
  8. Include API v1 router.
  9. Register startup event (log application started).
  10. Register shutdown event (log application stopped).
- `app = create_app()` at module level for the ASGI server.

---

### Component 16: Frontend Application (frontend/)

**Type**: Frontend Foundation
**Depends on**: Working API (for client testing)
**Design**:
- Next.js App Router with TypeScript strict mode.
- Root `layout.tsx` wraps all pages in `AppLayout`.
- `AppLayout.tsx`: Responsive layout shell with a header slot and sidebar slot. No business content.
- `Header.tsx` and `Sidebar.tsx`: Placeholder components with clear comments indicating future content.
- `lib/api/client.ts`: Generic `apiGet<T>()`, `apiPost<T>()`, `apiPut<T>()`, `apiDelete<T>()` functions wrapping `fetch()`. All prepend `NEXT_PUBLIC_API_URL`. All map error responses to typed `ApiError` objects.
- `lib/api/types.ts`: TypeScript equivalents of backend Pydantic schemas.

---

### Component 17: Docker Configuration

**Type**: Infrastructure
**Depends on**: Working backend and frontend
**Design**:
- `backend/Dockerfile`: Multi-stage; development stage uses full Python image, mounts source volume, runs uvicorn with `--reload`.
- `frontend/Dockerfile`: Multi-stage; development stage uses Node image, mounts source volume, runs `next dev`.
- `docker-compose.yml`:
  - `db`: `postgres:16-alpine`, `POSTGRES_DB/USER/PASSWORD` from env, named volume `postgres_data`, healthcheck via `pg_isready`.
  - `api`: Built from `backend/Dockerfile`, depends_on `db` (condition: service_healthy), mounts `./backend:/app`, ports `8000:8000`.
  - `web`: Built from `frontend/Dockerfile`, depends_on `api`, mounts `./frontend:/app`, ports `3000:3000`.

---

## Dependency Graph

The following directed graph shows which components must be complete before another can begin:

```
Settings
  │
  ├──► Logging
  │       │
  │       ├──► Database Engine/Session
  │       │         │
  │       │         ├──► BaseModel / TenantBaseModel
  │       │         │         │
  │       │         │         ├──► Alembic Configuration
  │       │         │         │
  │       │         │         └──► BaseRepository
  │       │         │                   │
  │       │         │                   └──► BaseService
  │       │         │
  │       │         └──► (used by Health Check)
  │       │
  │       └──► Exception Hierarchy
  │                   │
  │                   ├──► Common Pydantic Schemas
  │                   │         │
  │                   │         └──► Exception Handler
  │                   │
  │                   └──► Exception Handler
  │                               │
  │                               └──► Auth Interface Stubs
  │                                           │
  │                                           └──► Middleware Chain
  │                                                     │
  │                                                     └──► API v1 Router
  │                                                               │
  │                                                               └──► Application Factory (main.py)
  │                                                                           │
  │                                                                           └──► Docker Configuration
  │                                                                                       │
  │                                                                                       └──► Frontend Application
  │
  └──► Utility Modules (independent; can be created alongside Settings)
```

**Critical Path** (longest dependency chain, determines minimum duration):

`Settings → Logging → DB Engine → TenantBaseModel → BaseRepository → BaseService → API Router → App Factory → Docker → Frontend`

**Parallel Opportunities**:

- Utility modules can be created in parallel with Logging.
- Exception Hierarchy and Common Schemas can be developed in parallel with Database components.
- Alembic configuration can proceed in parallel with BaseRepository after BaseModel is defined.
- Frontend development can begin as soon as the Docker environment is running.

---

## Folder Creation Order

The following order minimizes the risk of missing `__init__.py` files or circular import issues:

```
Phase 0 (Root):
  erp-system/
  erp-system/backend/
  erp-system/frontend/

Phase 1 (Backend Python package hierarchy):
  backend/core/
  backend/core/config/
  backend/core/config/__init__.py
  backend/core/__init__.py
  backend/__init__.py

Phase 2 (Logging):
  backend/core/logging/
  backend/core/logging/__init__.py

Phase 3 (Database):
  backend/core/database/
  backend/core/database/__init__.py
  backend/core/database/models/
  backend/core/database/models/__init__.py
  backend/migrations/
  backend/migrations/versions/

Phase 4 (Exceptions and Schemas):
  backend/core/exceptions/
  backend/core/exceptions/__init__.py
  backend/core/schemas/
  backend/core/schemas/__init__.py

Phase 5 (Base Patterns and Utilities):
  backend/core/repositories/
  backend/core/repositories/__init__.py
  backend/core/services/
  backend/core/services/__init__.py
  backend/core/utils/
  backend/core/utils/__init__.py

Phase 6 (Middleware, Auth Stubs, API):
  backend/core/middleware/
  backend/core/middleware/__init__.py
  backend/core/auth/
  backend/core/auth/__init__.py
  backend/api/
  backend/api/__init__.py
  backend/api/v1/
  backend/api/v1/__init__.py

Phase 7 (Tests):
  backend/tests/
  backend/tests/__init__.py
  backend/tests/unit/
  backend/tests/unit/__init__.py
  backend/tests/unit/core/
  backend/tests/unit/core/__init__.py
  backend/tests/integration/
  backend/tests/integration/__init__.py
  backend/tests/integration/api/
  backend/tests/integration/api/__init__.py

Phase 8 (Modules placeholder):
  backend/modules/
  backend/modules/__init__.py
  backend/modules/.gitkeep

Phase 9 (Frontend — created by Next.js CLI):
  frontend/ (created via `npx create-next-app@latest` with TypeScript and Tailwind options)
  frontend/src/components/layout/
  frontend/src/lib/api/
  frontend/src/types/
  frontend/src/__tests__/
```

---

## Risk Analysis

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| SQLAlchemy generic typing complexity (BaseRepository) | Medium | Medium | Validate the `Generic[ModelType]` pattern against Python 3.12 typing rules in Phase 5; if problematic, use `Type[ModelType]` parameter approach as fallback |
| Pydantic v2 migration breaking changes | Medium | Low | Refer to Pydantic v2 migration guide; test all schema imports immediately in Phase 4 |
| Docker hot reload performance on Windows/WSL2 | Medium | Low | Document known WSL2 volume mount performance characteristics in README; consider `delegated` volume mounts if needed |
| PostgreSQL not available during development without Docker | Low | Low | All development requires Docker; documented in README; no native database path needed |
| `uuid-ossp` or `pgcrypto` extension for gen_random_uuid() | Low | Low | Verify PostgreSQL 16 built-in `gen_random_uuid()` (available without extensions since PG 13) |

### Architectural Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| BaseRepository too restrictive for future module needs | Low | High | Design `BaseRepository` with override-friendly methods; concrete repos can call `super()` or bypass via direct session access in justified cases |
| Synchronous SQLAlchemy creating bottlenecks at scale | Medium | Medium | Accept risk; document in Assumption 6 of the spec; async migration path is isolated to `core/database/` (see Future Readiness) |
| `company_id` column without FK constraint on base model tables | Low | Low | This is intentional per the design; document clearly in code comments; FK will be added when Company Management Epic is built |
| Circular imports between core modules | Low | High | Strict import order: utils → exceptions → schemas → database → repositories → services → middleware → api; never import upward or sideways |

### Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Developer machine not running Docker or wrong Docker version | Low | Low | Document Docker and Docker Compose v2 as required prerequisites in README |
| `.env` file accidentally committed to git | Low | High | `.env` in `.gitignore` from Phase 0; pre-commit hook validates no `.env` file is staged |
| Environment variable missing from `.env.example` when added to Settings | Medium | Low | Settings validation test (`test_settings.py`) verifies all required variables; CI fails if new variable not in `.env.example` |

---

## Validation Strategy

Each phase has a defined validation gate. A phase is not considered complete until all validation checks pass. The developer or code reviewer verifies these checks before starting the next phase.

### Gate 0 (Phase 0 Complete)

- Repository directory structure matches the spec exactly.
- `.gitignore` is committed and working.
- `.env.example` contains entries for all Settings variables.

### Gate 1 (Phase 1 Complete)

- `black --check .` exits with code 0.
- `ruff check .` exits with code 0.
- `mypy .` exits with code 0.
- Settings unit tests pass (missing variable → ValidationError, full env → correct values).

### Gate 2 (Phase 2 Complete)

- Application starts without errors with only Settings and Logging initialized.
- Log output in development mode is human-readable.
- Log output in production mode is valid JSON (verified with `python -m json.tool`).
- No sensitive fields appear in log output.

### Gate 3 (Phase 3 Complete)

- `alembic upgrade head` succeeds on a fresh database.
- `alembic downgrade base` succeeds after upgrade.
- BaseModel and TenantBaseModel have all required fields per the spec.
- Session dependency correctly yields and closes a session.

### Gate 4 (Phase 4 Complete)

- All exception types can be raised and produce the correct HTTP status code.
- All error responses match the `{error: {code, message, details}}` structure.
- Stack traces are never exposed when `ENVIRONMENT=production`.

### Gate 5 (Phase 5 Complete)

- BaseRepository unit tests pass (create, get, list, update, soft_delete).
- `company_id` is required and applied on all data access methods.
- Soft-deleted records are excluded from `list()` unless `include_deleted=True`.

### Gate 6 (Phase 6 Complete)

- Application starts with `uvicorn main:app --reload`.
- `GET /api/v1/health` returns HTTP 200 (database connected) and HTTP 503 (database disconnected).
- Every response includes `X-Request-ID` header.
- Auth hook middleware is in place (verified by inspecting middleware stack in `/openapi.json`).

### Gate 7 (Phase 7 Complete)

- `docker compose up` starts all three services without errors.
- Health check passes from within Docker network.
- Hot reload works for backend and frontend.
- Database persists across `docker compose down && docker compose up`.

### Gate 8 (Phase 8 Complete)

- `tsc --noEmit` exits with code 0.
- `eslint .` exits with code 0.
- `prettier --check .` exits with code 0.
- Frontend application loads with no console errors.
- API client successfully calls the health endpoint.

### Gate 9 (Phase 9 Complete = Epic Complete)

- All unit tests pass.
- All integration tests pass.
- Frontend smoke test passes.
- All code quality checks pass.
- Epic exit criteria are met (see Exit Criteria below).

---

## Testing Strategy

### Unit Testing (pytest)

**Location**: `backend/tests/unit/core/`
**Framework**: pytest
**Scope**: Individual classes and functions in isolation

| Test File | What is Tested |
|-----------|----------------|
| `test_settings.py` | Missing required variable raises ValidationError; all optional variables have correct defaults; correct values loaded from environment |
| `test_exceptions.py` | Each exception subclass has correct default `code` and `http_status`; exception handler maps each type to correct HTTP status; production mode never includes stack trace in response |
| `test_logging.py` | Log output includes all required fields; sensitive values are absent; request_id is propagated from context var |
| `test_base_repository.py` | `create()` persists entity; `get_by_id()` with matching `company_id` returns entity; `get_by_id()` with wrong `company_id` raises NotFoundException; `list()` excludes soft-deleted records; `soft_delete()` sets is_deleted and deleted_at |
| `test_schemas.py` | StandardResponse serializes correctly; ErrorResponse matches expected structure; PaginatedResponse calculates pages correctly |
| `test_utils.py` | UUID utility returns valid UUID4; datetime utility returns UTC-aware datetime; pagination utility calculates correct offset and page count |

**Test Database**: Unit tests that require database access use a test-specific PostgreSQL database (`DATABASE_URL` pointing to a test database, isolated from the development database). Tests use transactions that are rolled back after each test to ensure isolation.

### Integration Testing (pytest + httpx)

**Location**: `backend/tests/integration/api/`
**Framework**: pytest with `httpx.AsyncClient` or `TestClient` from FastAPI
**Scope**: Full HTTP request/response cycle through the real application

| Test File | What is Tested |
|-----------|----------------|
| `test_health.py` | `GET /api/v1/health` returns 200 with correct schema when database is connected; returns 503 with correct schema when database is unreachable; response includes `X-Request-ID` header; response body `meta.request_id` matches header |
| `test_exception_handler.py` | Endpoint that raises `NotFoundException` returns 404 ErrorResponse; endpoint that raises unhandled Exception returns 500 ErrorResponse without stack trace in production mode |

### Frontend Testing (Jest + React Testing Library)

**Location**: `frontend/src/__tests__/`
**Framework**: Jest + React Testing Library
**Scope**: Component rendering and basic behavior

| Test File | What is Tested |
|-----------|----------------|
| `AppLayout.test.tsx` | `AppLayout` renders without errors; contains header element; contains main content area |

### Manual Verification Checklist

The following manual checks are performed as part of Gate 9:

1. Clone the repository on a fresh machine with Docker.
2. Copy `.env.example` to `.env` and fill in local values.
3. Run `docker compose up`.
4. Verify all three services start without errors.
5. Open browser to `http://localhost:3000` — verify no console errors.
6. Call `http://localhost:8000/api/v1/health` — verify healthy response.
7. Open `http://localhost:8000/docs` — verify Swagger UI appears.
8. Stop the database container.
9. Call health endpoint again — verify 503 degraded response.
10. Restart everything — verify database state persists.
11. Modify a backend Python file — verify hot reload within 3 seconds.
12. Modify a frontend TypeScript file — verify Next.js fast refresh.

---

## Milestones

### Milestone 1: Backend Foundation Operational

**Target**: End of Phase 3
**Completion Criteria**:
- Settings class configured and validated.
- Structured logging operational.
- PostgreSQL database connected and Alembic migrations running.
- `BaseModel` and `TenantBaseModel` defined.
- All code quality tools passing.

---

### Milestone 2: Core Platform Layer Complete

**Target**: End of Phase 6
**Completion Criteria**:
- Exception handling centralized and tested.
- Base patterns (BaseRepository, BaseService) defined.
- FastAPI application starts successfully.
- `GET /api/v1/health` returns correct responses.
- Auth integration stubs in place.
- All middleware registered and functional.

---

### Milestone 3: One-Command Development Environment

**Target**: End of Phase 7
**Completion Criteria**:
- `docker compose up` starts all services.
- Health check passes from within Docker network.
- Hot reload working for backend.
- Database persistence confirmed.
- Primary Epic success criterion met.

---

### Milestone 4: Full Foundation Complete

**Target**: End of Phase 9 (Epic Complete)
**Completion Criteria**:
- Frontend foundation operational.
- All unit and integration tests passing.
- All code quality checks passing.
- All acceptance criteria in the spec checked off.
- Epic exit criteria met.

---

## Exit Criteria

Epic 1 is complete when ALL of the following conditions are true:

1. `docker compose up` starts all services without errors on a clean machine.
2. `GET /api/v1/health` returns HTTP 200 with `status: healthy` and `database: connected`.
3. `GET /api/v1/health` returns HTTP 503 with `status: degraded` when the database is unavailable.
4. The Next.js application loads in the browser with zero console errors.
5. `black --check .` passes with zero errors on all backend code.
6. `ruff check .` passes with zero errors on all backend code.
7. `mypy .` passes with zero type errors on all backend code.
8. `eslint .` passes with zero errors on all frontend code.
9. `prettier --check .` passes with zero errors on all frontend code.
10. `tsc --noEmit` passes with zero type errors on all frontend code.
11. All unit tests pass: `pytest tests/unit/ -v`.
12. All integration tests pass: `pytest tests/integration/ -v`.
13. All frontend tests pass: `npm test`.
14. `BaseModel`, `TenantBaseModel`, `BaseRepository`, `BaseService`, `ApplicationException` and all subclasses are defined.
15. Auth hook middleware and `core/auth/interfaces.py` stubs are in place and documented.
16. Alembic initial baseline migration runs successfully on a fresh database and supports downgrade.
17. All `.env.example` files document every environment variable used in the application.
18. No secrets, tokens, or credentials appear in any committed file.
19. `README.md` contains complete setup, development, and testing instructions.
20. Every public class and module in `core/` has a docstring.

---

## Future Readiness

### For Authentication (Epic 2 — Better Auth)

The following foundation components directly support the Authentication Epic:

- `core/auth/interfaces.py` — Protocol definitions (`CurrentUser`, `SessionContext`, `PermissionChecker`) are already defined. The Auth Epic implements concrete classes that satisfy these protocols.
- `core/middleware/auth_hook.py` — The exact insertion point for Better Auth middleware is documented and in place. The Auth Epic replaces the pass-through stub with real authentication middleware.
- `get_current_user_stub()` and `require_permission_stub()` — FastAPI dependencies already wired in the API layer. The Auth Epic replaces these stubs with real implementations.
- `TenantBaseModel.company_id` — The field is defined and the pattern is enforced. As soon as the Auth Epic provides a real current user, `company_id` can be populated from the session.

### For Company Management (Epic 3)

- `TenantBaseModel` defines `company_id` as a column. The Company Management Epic creates the `companies` table and adds the FK constraint via Alembic migration.
- `BaseRepository` enforces `company_id` on all queries. Once real companies exist, this enforcement becomes meaningful.

### For User Management (Epic 4)

- `TenantBaseModel.created_by` is a nullable UUID column. The User Management Epic creates the `users` table and adds the FK constraint via Alembic migration.
- `CurrentUser` protocol in `core/auth/interfaces.py` defines the shape that the user management system will produce.

### For ERP Modules (Epics 5+)

- The `modules/` directory is ready for vertical slice additions.
- `BaseModel`, `TenantBaseModel`, `BaseRepository`, `BaseService` are complete and tested.
- A module developer extends these base classes and registers their router with `api/v1/router.py`.
- No modification to `core/` is required for adding new modules.

### For SaaS Growth

- The stateless API design supports horizontal scaling immediately.
- Connection pooling configuration is environment-variable-driven and can be tuned without code changes.
- The structured logging format is ready for Grafana Loki, Datadog, or any log aggregation tool.
- The `Settings` class pattern supports adding new configuration values for future SaaS features (subscription plans, feature toggles, usage limits) without restructuring.

Architectural Decisions Required During Implementation

If any of the following change during implementation, create an ADR before proceeding:

- Folder Structure
- Database Strategy
- Docker Strategy
- Dependency Injection Pattern
- Repository Pattern
- Logging Strategy
- Authentication Integration Strategy

---

*This plan is the authoritative implementation roadmap for Epic 1 — Foundation Platform.*
*All tasks derived from this plan MUST comply with this plan, the approved spec, and the DevSphere ERP Constitution.*
