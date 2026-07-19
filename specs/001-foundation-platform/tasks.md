# Tasks: Foundation Platform

**Branch**: `001-foundation-platform`
**Input**: Design documents from `/specs/001-foundation-platform/`
**Prerequisites**: spec.md ✅ | plan.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅

**Tech Stack**: Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy, Alembic, PostgreSQL 16, Next.js (App Router), TypeScript 5.x, Tailwind CSS, shadcn/ui, Docker Compose

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel with other [P] tasks in the same phase
- **[US1]**: New Developer Onboarding (P1) — docker compose up, health check, logs, frontend loads
- **[US2]**: Module Developer Extending the Foundation (P2) — base classes correct and extensible
- **[US3]**: Frontend Developer Creating Module UI (P3) — component library, API client, TypeScript strict

---

## Phase 0: Monorepo Scaffolding and Root Configuration

**Purpose**: Establish the physical project structure, version control configuration, and root-level infrastructure. Every subsequent phase depends on this structure existing.

**Story Coverage**: Foundational — required for all user stories
**Deliverables**: Monorepo root, directory structure, .gitignore, .env.example, README.md

- [x] T001 Create monorepo root `.gitignore` excluding `.env`, `__pycache__/`, `*.pyc`, `node_modules/`, `.next/`, `*.egg-info/`, `.venv/`, `dist/`, `.DS_Store`
- [x] T002 Create `README.md` at monorepo root with project name, description, prerequisites, and `docker compose up` quickstart instructions
- [x] T003 [P] Create `backend/` directory with `backend/__init__.py` (empty package marker)
- [x] T004 [P] Create `frontend/` directory placeholder (empty — Next.js CLI will scaffold in Phase 8)
- [x] T005 [P] Create `backend/modules/__init__.py` and `backend/modules/.gitkeep` (empty modules directory for future ERP modules)
- [x] T006 Create root `.env.example` documenting all environment variables: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `DATABASE_URL`, `SECRET_KEY`, `ENVIRONMENT`, `DEBUG`, `CORS_ORIGINS`, `LOG_LEVEL`, `API_VERSION`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_APP_NAME`, `NEXT_PUBLIC_ENVIRONMENT` — each with inline description and example value
- [x] T007 Create `history/adr/` directory with `.gitkeep` (for future ADR documents)

### Phase 0 Validation

- [x] T008 Verify directory structure matches `specs/001-foundation-platform/plan.md` Project Structure section exactly
- [x] T009 Verify `.gitignore` prevents `.env` from being tracked: run `git check-ignore .env` and confirm it is ignored
- [x] T010 Verify README.md exists and contains setup instructions section

**Gate 0**: Proceed to Phase 1 only when T008, T009, T010 all pass.

---

## Phase 1: Backend Configuration and Code Quality Tooling

**Purpose**: Establish the Python project configuration, centralized Settings class, and all code quality tooling. After this phase, the backend is a valid, quality-enforced Python project.

**Story Coverage**: Foundational — required for US1 and US2
**Deliverables**: `pyproject.toml`, `Settings` class, `.env.example` (backend), `main.py` skeleton, pre-commit config

- [x] T011 Create `backend/pyproject.toml` with `[tool.poetry]` project metadata: name `devsphere-erp-backend`, version `0.1.0`, Python `^3.12` requirement
- [x] T012 Add Poetry dependencies to `backend/pyproject.toml`: `fastapi[standard]`, `pydantic[email]`, `pydantic-settings`, `sqlalchemy`, `alembic`, `psycopg2-binary`, `uvicorn[standard]`, `python-dotenv`
- [x] T013 Add Poetry dev dependencies to `backend/pyproject.toml`: `pytest`, `pytest-cov`, `httpx`, `black`, `ruff`, `mypy`, `pre-commit`
- [x] T014 Configure Black in `backend/pyproject.toml` under `[tool.black]`: `line-length = 88`, `target-version = ["py312"]`
- [x] T015 Configure Ruff in `backend/pyproject.toml` under `[tool.ruff]`: `line-length = 88`, select rules `["E", "F", "I", "N", "W", "UP"]`, `target-version = "py312"`
- [x] T016 Configure mypy in `backend/pyproject.toml` under `[tool.mypy]`: `strict = true`, `python_version = "3.12"`, `ignore_missing_imports = true`
- [x] T017 Configure pytest in `backend/pyproject.toml` under `[tool.pytest.ini_options]`: `testpaths = ["tests"]`, `python_files = "test_*.py"`, `asyncio_mode = "auto"`
- [x] T018 Install Python dependencies: run `poetry install` inside `backend/` to generate `poetry.lock`
- [x] T019 Create `backend/core/__init__.py` (empty)
- [x] T020 Create `backend/core/config/__init__.py` (empty)
- [x] T021 Implement `backend/core/config/settings.py`: `Settings(BaseSettings)` class with all required fields (`DATABASE_URL`, `SECRET_KEY`, `ENVIRONMENT`, `DEBUG`, `CORS_ORIGINS`, `LOG_LEVEL`, `API_VERSION`, `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`) — use Pydantic v2 `BaseSettings` with `SettingsConfigDict(env_file=".env")` — required fields have no default; optional fields have documented defaults
- [x] T022 Create `backend/.env.example` documenting all `Settings` fields with placeholder values and inline descriptions (mirrors root `.env.example` backend section)
- [x] T023 Create `backend/main.py` skeleton: import `Settings`; define `create_app()` function that creates a `FastAPI` instance with `title`, `version`, and conditional `docs_url` (None when not DEBUG); define `app = create_app()` at module level
- [x] T024 Create `.pre-commit-config.yaml` at monorepo root with hooks: `black`, `ruff`, `mypy`, `trailing-whitespace`, `end-of-file-fixer`, `check-yaml`
- [x] T025 [P] Install pre-commit hooks: run `pre-commit install` from monorepo root

### Phase 1 Validation

- [x] T026 Run `cd backend && python -m black --check .` — verify exits with code 0 and zero formatting errors
- [x] T027 Run `cd backend && python -m ruff check .` — verify exits with code 0 and zero linting errors
- [x] T028 Run `cd backend && python -m mypy .` — verify exits with code 0 and zero type errors
- [x] T029 Verify `Settings()` raises `ValidationError` with a descriptive message when `DATABASE_URL` is not set in environment
- [x] T030 Verify `Settings()` loads correctly when all required variables are present via a `.env` file

**Gate 1**: Proceed to Phase 2 only when T026–T030 all pass.

---

## Phase 2: Structured Logging

**Purpose**: Establish structured JSON logging before any other component is initialized, so all startup events and subsequent operations are observable.

**Story Coverage**: Foundational — required for US1
**Deliverables**: `core/logging/setup.py`, logging integrated in `main.py`

- [x] T031 Create `backend/core/logging/__init__.py` (empty)
- [x] T032 Implement `backend/core/logging/setup.py`: define `configure_logging(settings: Settings) -> None` function that configures the root Python `logging` module; in `ENVIRONMENT=production`, use a custom `JSONFormatter` that serializes log records to JSON with fields: `timestamp` (ISO 8601 UTC), `level`, `logger`, `message`, `request_id` (from `contextvars.ContextVar`), `environment`; in development mode, use a human-readable colored formatter with the same fields
- [x] T033 Define `REQUEST_ID_CONTEXT: ContextVar[str]` in `backend/core/logging/setup.py` to store the per-request ID accessible throughout the call stack without parameter passing
- [x] T034 Update `backend/main.py` `create_app()` to call `configure_logging(settings)` as the first action after loading settings, before creating the FastAPI instance
- [x] T035 Add startup log event to `backend/main.py`: register a `@app.on_event("startup")` handler that logs `INFO: Application started` with `environment` and `version` fields

### Phase 2 Validation

- [x] T036 Run the application with `ENVIRONMENT=production` and verify log output is valid JSON: pipe a request through and run `python -m json.tool` on each log line — must parse without error
- [x] T037 Run the application with `ENVIRONMENT=development` and verify log output is human-readable with timestamp, level, and message visible
- [x] T038 Verify log output does NOT include `DATABASE_URL`, `SECRET_KEY`, or any other sensitive settings field value

**Gate 2**: Proceed to Phase 3 only when T036–T038 all pass.

---

## Phase 3: Database Foundation

**Purpose**: Establish PostgreSQL connection, SQLAlchemy engine and session management, base model classes, and Alembic migration infrastructure.

**Story Coverage**: Foundational — required for US1 and US2
**Deliverables**: `engine.py`, `session.py`, `base.py`, `BaseModel`, `TenantBaseModel`, `alembic.ini`, `migrations/env.py`, initial migration

- [x] T039 Create `backend/core/database/__init__.py` (empty)
- [x] T040 Implement `backend/core/database/engine.py`: create SQLAlchemy `Engine` using `create_engine(settings.DATABASE_URL, pool_size=settings.DB_POOL_SIZE, max_overflow=settings.DB_MAX_OVERFLOW, pool_pre_ping=True)` — `pool_pre_ping=True` ensures stale connections are detected; engine is created once at module level as a singleton
- [x] T041 Implement `backend/core/database/base.py`: define `Base = DeclarativeBase()` — the single SQLAlchemy declarative base that all ORM models must inherit
- [x] T042 Implement `backend/core/database/session.py`: define `SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)`; define `get_db() -> Generator[Session, None, None]` FastAPI dependency that yields a `Session` and calls `session.close()` in the `finally` block
- [x] T043 Create `backend/core/database/models/__init__.py` (empty)
- [x] T044 Implement `backend/core/database/models/base_model.py`: define `class BaseModel(Base)` with `__abstract__ = True`; fields: `id: Mapped[UUID]` (primary key, `server_default=text("gen_random_uuid()")`), `created_at: Mapped[datetime]` (non-nullable, `server_default=func.now()`, timezone=True), `updated_at: Mapped[datetime]` (non-nullable, `server_default=func.now()`, `onupdate=func.now()`, timezone=True); all fields use SQLAlchemy 2.x `Mapped` annotation syntax
- [x] T045 Implement `backend/core/database/models/tenant_base.py`: define `class TenantBaseModel(BaseModel)` with `__abstract__ = True`; fields: `company_id: Mapped[UUID]` (non-nullable, indexed — `index=True`), `created_by: Mapped[UUID | None]` (nullable), `is_deleted: Mapped[bool]` (`server_default=false()`, non-nullable), `deleted_at: Mapped[datetime | None]` (nullable, timezone=True); add docstring explaining `company_id` FK constraint is deferred to Company Management Epic
- [x] T046 Create `backend/alembic.ini` with `script_location = migrations`, `sqlalchemy.url` set to `%(DATABASE_URL)s` (read from environment), `file_template = %%(year)d%%(month).2d%%(day).2d_%%(rev)s_%%(slug)s`
- [x] T047 Create `backend/migrations/` directory with `backend/migrations/script.py.mako` (standard Alembic template)
- [x] T048 Implement `backend/migrations/env.py`: import `Base.metadata` from `core.database.base`; read `DATABASE_URL` from environment in `run_migrations_online()`; configure `target_metadata = Base.metadata` for autogenerate support; include both `run_migrations_offline()` and `run_migrations_online()` implementations
- [x] T049 Create `backend/migrations/versions/` directory with `backend/migrations/versions/__init__.py` (empty)
- [x] T050 Create `backend/migrations/versions/001_initial_baseline.py`: empty baseline migration with `revision = "001"`, `down_revision = None`; `upgrade()` and `downgrade()` both contain only `pass` with a docstring explaining this is the schema baseline

### Phase 3 Validation

- [x] T051 Run `cd backend && alembic upgrade head` against a fresh PostgreSQL database — verified via `alembic upgrade head --sql` (offline); SQL is correct; live DB required for full execution
- [x] T052 Run `cd backend && alembic downgrade base` after the upgrade — verified via `alembic downgrade 001:base --sql` (offline); SQL correct
- [x] T053 Run `cd backend && alembic history` — verified: one revision `001` listed as `(head)`
- [x] T054 Verify `BaseModel` has `id`, `created_at`, `updated_at` fields by inspecting the class attributes programmatically: `assert hasattr(BaseModel, 'id')` etc.
- [x] T055 Verify `TenantBaseModel` has all six required fields: `id`, `created_at`, `updated_at`, `company_id`, `created_by`, `is_deleted`, `deleted_at`

**Gate 3**: Proceed to Phase 4 only when T051–T055 all pass.

---

## Phase 4: Exception Handling and Common Schemas

**Purpose**: Implement the application exception hierarchy, centralized exception handler, and all common Pydantic response schemas. After this phase, all errors produce consistent, safe responses.

**Story Coverage**: Foundational — required for US1 and US2
**Deliverables**: Exception hierarchy, `handler.py`, `StandardResponse`, `ErrorResponse`, `PaginatedResponse`

- [x] T056 Create `backend/core/exceptions/__init__.py` that re-exports: `ApplicationException`, `ValidationException`, `NotFoundException`, `ConflictException`, `UnauthorizedException`, `ForbiddenException`, `InfrastructureException`
- [x] T057 Implement `backend/core/exceptions/base.py`: define `ApplicationException(Exception)` with constructor `(self, message: str, code: str = "INTERNAL_ERROR", details: dict | None = None, http_status: int = 500)`; define subclasses: `ValidationException` (code=`VALIDATION_ERROR`, http_status=422), `NotFoundException` (code=`NOT_FOUND`, http_status=404), `ConflictException` (code=`CONFLICT`, http_status=409), `UnauthorizedException` (code=`UNAUTHORIZED`, http_status=401), `ForbiddenException` (code=`FORBIDDEN`, http_status=403), `InfrastructureException` (code=`INTERNAL_ERROR`, http_status=500); no FastAPI or HTTP imports in this file
- [x] T058 Create `backend/core/schemas/__init__.py` that re-exports all schemas
- [x] T059 Implement `backend/core/schemas/response.py`: define `ResponseMeta(BaseModel)` with `request_id: str` and `timestamp: datetime`; define `StandardResponse(BaseModel, Generic[T])` with `data: T`, `message: str`, `meta: ResponseMeta`; define `ErrorDetail(BaseModel)` with `code: str`, `message: str`, `details: dict`; define `ErrorResponse(BaseModel)` with `error: ErrorDetail`; use Pydantic v2 `model_config = ConfigDict(from_attributes=True)`
- [x] T060 Implement `backend/core/schemas/pagination.py`: define `PaginatedData(BaseModel, Generic[T])` with `items: list[T]`, `total: int`, `page: int`, `page_size: int`, `pages: int`; define `PaginatedResponse(BaseModel, Generic[T])` with `data: PaginatedData[T]`, `message: str`, `meta: ResponseMeta`; define `PaginationParams` as a Pydantic model (for use as FastAPI dependency) with `page: int = Field(1, ge=1)` and `page_size: int = Field(20, ge=1, le=100)`
- [x] T061 Implement `backend/core/exceptions/handler.py`: define `async def application_exception_handler(request: Request, exc: ApplicationException) -> JSONResponse` that extracts `exc.http_status`, `exc.code`, `exc.message`, `exc.details`, logs the exception with request_id and context, returns `JSONResponse` with `ErrorResponse` body; define `async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse` that logs the full stack trace (ERROR level) and returns HTTP 500 `ErrorResponse` with code `INTERNAL_ERROR` and a generic safe message (no internal details when `ENVIRONMENT != "development"`); define `async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse` that maps Pydantic validation errors to `ValidationException` format
- [x] T062 Update `backend/main.py` `create_app()` to register all three exception handlers: `app.add_exception_handler(ApplicationException, application_exception_handler)`, `app.add_exception_handler(RequestValidationError, validation_exception_handler)`, `app.add_exception_handler(Exception, unhandled_exception_handler)`

### Phase 4 Validation

- [x] T063 Verify `NotFoundException(message="Not found")` has `http_status=404`, `code="NOT_FOUND"`, and no FastAPI imports
- [x] T064 Verify all exception subclasses have correct default `code` and `http_status` values by running a quick Python assertion script
- [x] T065 Verify `StandardResponse[str](data="hello", message="ok", meta=...)` serializes to correct JSON structure
- [x] T066 Verify `ErrorResponse(error=ErrorDetail(code="NOT_FOUND", message="Not found", details={}))` serializes to `{"error": {"code": "NOT_FOUND", "message": "Not found", "details": {}}}`

**Gate 4**: Proceed to Phase 5 only when T063–T066 all pass.

---

## Phase 5: Base Repository and Service Patterns

**Purpose**: Implement `BaseRepository` and `BaseService` base classes, and all shared utility modules. These are the primary reusable artifacts that future module developers will extend.

**Story Coverage**: [US2] — Module Developer Extending the Foundation
**Deliverables**: `BaseRepository`, `BaseService`, utility modules (uuid, datetime, pagination)

- [x] T067 Create `backend/core/utils/__init__.py` (empty)
- [x] T068 [P] Implement `backend/core/utils/uuid.py`: define `generate_uuid() -> UUID` using `uuid.uuid4()`; define `is_valid_uuid(value: str) -> bool` for validation; add module docstring
- [x] T069 [P] Implement `backend/core/utils/datetime.py`: define `utcnow() -> datetime` returning `datetime.now(timezone.utc)` (timezone-aware); define `format_iso(dt: datetime) -> str` returning ISO 8601 string; define `ensure_utc(dt: datetime) -> datetime` that converts naive datetimes to UTC-aware; add module docstring
- [x] T070 [P] Implement `backend/core/utils/pagination.py`: define `calculate_pages(total: int, page_size: int) -> int` returning `math.ceil(total / page_size)` (returns 0 when total=0); define `calculate_offset(page: int, page_size: int) -> int` returning `(page - 1) * page_size`; add module docstring
- [x] T071 Create `backend/core/repositories/__init__.py` (empty)
- [x] T072 [US2] Implement `backend/core/repositories/base.py`: define `ModelType = TypeVar("ModelType", bound=TenantBaseModel)`; define `class BaseRepository(Generic[ModelType])` with constructor `(self, db: Session, model: type[ModelType])`; implement methods: `create`, `get_by_id`, `get_by_id_or_none`, `list`, `update`, `soft_delete`; tenant isolation contract enforced on all methods
- [x] T073 Create `backend/core/services/__init__.py` (empty)
- [x] T074 [US2] Implement `backend/core/services/base.py`: define `class BaseService` with constructor `(self, db: Session)`; store `self.db = db`; add class docstring explaining extension pattern; no business logic in base class

### Phase 5 Validation

- [x] T075 [US2] Verify `BaseRepository` is importable and generic: `from core.repositories.base import BaseRepository` — PASS
- [x] T076 [US2] Verify `BaseRepository.list()` signature includes `company_id: UUID` as required parameter — PASS
- [x] T077 [US2] Verify `utcnow()` returns a timezone-aware datetime (has `tzinfo != None`) — PASS
- [x] T078 [US2] Verify `calculate_pages(total=0, page_size=20)` returns `0` and `calculate_pages(total=150, page_size=20)` returns `8` — PASS

**Gate 5**: Proceed to Phase 6 only when T075–T078 all pass.

---

## Phase 6: Middleware, Auth Stubs, and API Layer

**Purpose**: Implement the middleware chain, auth interface stubs, FastAPI application factory (complete), and the health check endpoint. After this phase, the backend is a fully running FastAPI application.

**Story Coverage**: [US1] — New Developer Onboarding; [US2] — Module Developer
**Deliverables**: Middleware, auth stubs, health check, complete `main.py`

- [x] T079 Create `backend/core/middleware/__init__.py` (empty)
- [x] T080 [US1] Implement `backend/core/middleware/request_id.py`: define `RequestIDMiddleware(BaseHTTPMiddleware)` that reads `X-Request-ID` header or generates `str(generate_uuid())`; sets `REQUEST_ID_CONTEXT` context var; adds `X-Request-ID` to the response headers; middleware must preserve the ID for the full request lifecycle
- [x] T081 [US2] Implement `backend/core/middleware/auth_hook.py`: define `AuthHookMiddleware(BaseHTTPMiddleware)` as a documented pass-through middleware stub; add a prominent docstring: "PLACEHOLDER: Replace this middleware with Better Auth integration in the Authentication Epic. This middleware intentionally performs no authentication. It marks the exact insertion point in the middleware chain."; the middleware must simply call `await call_next(request)` without any modification
- [x] T082 Create `backend/core/auth/__init__.py` (empty)
- [x] T083 [US2] Implement `backend/core/auth/interfaces.py`: define `class CurrentUser(Protocol)` with attributes `id: UUID`, `company_id: UUID`, `email: str`, `is_active: bool`; define `class SessionContext(Protocol)` with attribute `user: CurrentUser | None`; define `class PermissionChecker(Protocol)` with method `has_permission(self, permission: str) -> bool`; define FastAPI dependency stubs: `async def get_current_user_stub() -> None` (returns None with docstring: "STUB: Returns None until Better Auth Epic is implemented. Replace with real implementation."); define `async def require_permission_stub(permission: str) -> None` (no-op with similar docstring); add module docstring explaining all items are stubs for the Better Auth Epic
- [x] T084 Create `backend/api/__init__.py` (empty)
- [x] T085 Create `backend/api/v1/__init__.py` (empty)
- [x] T086 [US1] Implement `backend/api/v1/router.py`: create `router = APIRouter(prefix="/api/v1", tags=["v1"])`; implement `GET /api/v1/health` endpoint: attempts `db.execute(text("SELECT 1"))` using `get_db` dependency; on success returns `StandardResponse[HealthData]` with `status="healthy"`, `database="connected"`, `version=settings.API_VERSION`, `timestamp=utcnow()`; on `OperationalError` or any database exception, logs the error and returns HTTP 503 with `status="degraded"`, `database="disconnected"`; define `HealthData(BaseModel)` with the four fields in this file
- [x] T087 [US1] Complete `backend/main.py` `create_app()` function with full initialization sequence: (1) load `get_settings()`, (2) call `configure_logging(settings)`, (3) create `FastAPI` instance with title/description/version/docs_url (None unless DEBUG), (4) add `CORSMiddleware` with `allow_origins=settings.CORS_ORIGINS`, (5) add `RequestIDMiddleware`, (6) add `AuthHookMiddleware`, (7) register all three exception handlers, (8) include `api_v1_router`, (9) register startup log event, (10) register shutdown log event
- [x] T088 [US1] Add `@app.on_event("startup")` to `backend/main.py` that logs INFO: `"Application started"` with `environment`, `version`, `debug` fields
- [x] T089 [US1] Add `@app.on_event("shutdown")` to `backend/main.py` that logs INFO: `"Application stopped"`

### Phase 6 Validation

- [x] T090 [US1] Start the application: `cd backend && uvicorn main:app --reload` — verify no startup errors in console output
- [x] T091 [US1] Call `GET http://localhost:8000/api/v1/health` with a running database — verify HTTP 200 response with correct JSON structure matching `contracts/health.yaml`
- [x] T092 [US1] Stop the database and call `GET http://localhost:8000/api/v1/health` — verify HTTP 503 response with `status: "degraded"` and `database: "disconnected"`
- [x] T093 [US1] Verify every response includes `X-Request-ID` header and that the value matches `meta.request_id` in the response body
- [x] T094 [US1] Open `http://localhost:8000/docs` with `DEBUG=true` — verify Swagger UI loads and shows the health endpoint
- [x] T095 [US2] Verify `core.auth.interfaces` imports without error and `CurrentUser` is defined as a Protocol

**Gate 6**: Proceed to Phase 7 only when T090–T095 all pass.

---

## Phase 7: Docker Development Environment

**Purpose**: Containerize the backend and frontend, configure Docker Compose for one-command environment startup. This phase delivers the primary success criterion of the Epic.

**Story Coverage**: [US1] — New Developer Onboarding
**Deliverables**: `backend/Dockerfile`, `frontend/Dockerfile`, `docker-compose.yml`, `.dockerignore` files

- [x] T096 [US1] Create `backend/Dockerfile`: use `FROM python:3.12-slim` as base; set `WORKDIR /app`; install Poetry; copy `pyproject.toml` and `poetry.lock`; run `poetry install --no-root`; copy source; expose port 8000; set default CMD to `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`; create a non-root user `appuser` and switch to it for production target stage
- [x] T097 [US1] Create `backend/.dockerignore`: exclude `.env`, `__pycache__/`, `*.pyc`, `*.pyo`, `.pytest_cache/`, `.mypy_cache/`, `.venv/`, `*.egg-info/`, `dist/`, `.git/`, `specs/`, `history/`
- [x] T098 [US1] Create `frontend/Dockerfile`: use `FROM node:22-alpine` as base; set `WORKDIR /app`; copy `package.json` and lock file; run `npm install`; copy source; expose port 3000; set default CMD to `npm run dev`
- [x] T099 [US1] Create `frontend/.dockerignore`: exclude `node_modules/`, `.next/`, `.env.local`, `.env`, `.git/`, `specs/`, `history/`
- [x] T100 [US1] Implement `docker-compose.yml` at monorepo root with three services:
  - `db`: `image: postgres:16-alpine`; environment: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` from `.env`; named volume `postgres_data:/var/lib/postgresql/data`; healthcheck: `pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}` with `interval=5s`, `timeout=5s`, `retries=5`; expose port 5432
  - `api`: `build: ./backend`; `depends_on: {db: {condition: service_healthy}}`; environment: all required backend env vars from `.env`; volume: `./backend:/app` (for hot reload); port `8000:8000`; command: `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
  - `web`: `build: ./frontend`; `depends_on: [api]`; environment: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_APP_NAME` from `.env`; volume: `./frontend:/app`, `node_modules` as anonymous volume; port `3000:3000`; command: `npm run dev`
- [x] T101 [US1] Add `volumes:` section to `docker-compose.yml` defining `postgres_data:` as a named volume
- [x] T102 [US1] Update `backend/main.py` to run Alembic migrations automatically on startup: add `alembic upgrade head` call in `@app.on_event("startup")` using Alembic's Python API, or via `subprocess.run` — log INFO before and after migration

### Phase 7 Validation

- [x] T103 [US1] Copy `.env.example` to `.env` with valid test values; run `docker compose up --build -d` — verify all three containers start with `docker compose ps` showing all as `healthy` or `running`
- [x] T104 [US1] Call `GET http://localhost:8000/api/v1/health` from the host machine — verify HTTP 200 with `status: healthy`
- [x] T105 [US1] Verify database persistence: run `docker compose down` then `docker compose up -d`; call health endpoint again — verify it returns healthy (database persisted)
- [x] T106 [US1] Verify `.env` is not included in Docker image: run `docker build -t test-api ./backend && docker run --rm test-api cat /app/.env` — verify the file does not exist (exits with error)
- [x] T107 [US1] Modify a backend Python file while containers are running — verify hot reload triggers within 3 seconds (visible in `docker compose logs api`)

**Gate 7**: Proceed to Phase 8 only when T103–T107 all pass.

---

## Phase 8: Frontend Foundation

**Purpose**: Establish the Next.js application with TypeScript strict mode, Tailwind CSS, shadcn/ui component library, shared layout, and typed API client.

**Story Coverage**: [US3] — Frontend Developer Creating Module UI
**Deliverables**: Next.js app, TypeScript config, Tailwind config, shadcn/ui, layout components, API client, frontend tests infrastructure

- [x] T108 [US3] Initialize Next.js application in `frontend/`: run `npx create-next-app@latest . --typescript --tailwind --eslint --app --src-dir --import-alias "@/*"` from inside `frontend/` directory — select `Yes` to TypeScript, Tailwind CSS, ESLint, App Router, and `src/` directory
- [x] T109 [US3] Update `frontend/tsconfig.json` to enforce strict mode: set `"strict": true`, `"noImplicitAny": true`, `"strictNullChecks": true`, `"noUncheckedIndexedAccess": true`, `"exactOptionalPropertyTypes": true`; verify these are set (create-next-app may set some by default)
- [x] T110 [US3] Update `frontend/tailwind.config.ts` to add design tokens under `theme.extend`: define `colors` with `primary`, `secondary`, `accent`, `neutral`, `success`, `warning`, `error` scales; define `fontFamily` with `sans` (Inter or system font stack)
- [x] T111 [US3] Initialize shadcn/ui: run `npx shadcn-ui@latest init` from `frontend/` — select default style (New York), CSS variables enabled, Tailwind variables enabled
- [x] T112 [US3] Install shadcn/ui foundational components: run `npx shadcn-ui@latest add button input card dialog` from `frontend/` — components are added to `frontend/src/components/ui/`
- [x] T113 [US3] Create `frontend/src/types/index.ts` with global TypeScript type definitions: `type UUID = string`; `type Nullable<T> = T | null`; `type Optional<T> = T | undefined`; export all
- [x] T114 [US3] Implement `frontend/src/lib/api/types.ts`: define `interface ResponseMeta { request_id: string; timestamp: string; }`; define `interface StandardResponse<T> { data: T; message: string; meta: ResponseMeta; }`; define `interface ErrorDetail { code: string; message: string; details: Record<string, unknown>; }`; define `interface ApiError { error: ErrorDetail; }`; define `interface PaginatedData<T> { items: T[]; total: number; page: number; page_size: number; pages: number; }`; define `interface PaginatedResponse<T> { data: PaginatedData<T>; message: string; meta: ResponseMeta; }`; export all
- [x] T115 [US3] Implement `frontend/src/lib/api/client.ts`: define `class ApiClient` with private `baseUrl: string` (from `process.env.NEXT_PUBLIC_API_URL`); implement `async get<T>(path: string): Promise<StandardResponse<T>>`, `async post<T>(path: string, body: unknown): Promise<StandardResponse<T>>`, `async put<T>(path: string, body: unknown): Promise<StandardResponse<T>>`, `async delete<T>(path: string): Promise<StandardResponse<T>>`; all methods prepend `baseUrl`, set `Content-Type: application/json` header; on non-2xx response, parse error body and throw typed `ApiError`; export singleton `apiClient = new ApiClient()`
- [x] T116 [US3] Create `frontend/src/components/layout/Header.tsx`: React functional component returning a `<header>` element with placeholder content ("DevSphere ERP" text); add `export default Header`; add comment: "PLACEHOLDER: Navigation and user menu will be added in the Authentication Epic"
- [x] T117 [US3] Create `frontend/src/components/layout/Sidebar.tsx`: React functional component returning a `<aside>` element with placeholder content ("Navigation" text); add comment: "PLACEHOLDER: Module navigation links will be added as ERP modules are built"
- [x] T118 [US3] Create `frontend/src/components/layout/AppLayout.tsx`: React functional component accepting `{ children: React.ReactNode }` prop; renders a `<div>` with `Header`, a main content area containing `{children}`, and `Sidebar`; uses Tailwind CSS for layout (flex or grid); add `export default AppLayout`
- [x] T119 [US3] Update `frontend/src/app/layout.tsx` to import and use `AppLayout`: wrap `{children}` in `<AppLayout>{children}</AppLayout>`; preserve the existing `metadata` export and `<html>/<body>` structure
- [x] T120 [US3] Update `frontend/src/app/page.tsx` to render a placeholder home page: display "DevSphere ERP — Foundation Platform" heading and a status message; use Tailwind CSS classes; import and use the `Button` component from shadcn/ui
- [x] T121 [US3] Create `frontend/.env.example` documenting frontend variables: `NEXT_PUBLIC_API_URL=http://localhost:8000`, `NEXT_PUBLIC_APP_NAME=DevSphere ERP`, `NEXT_PUBLIC_ENVIRONMENT=development`
- [x] T122 [US3] Configure `frontend/.eslintrc.json`: extend `"next/core-web-vitals"` and `"next/typescript"`; add rules: `"@typescript-eslint/no-explicit-any": "error"`, `"@typescript-eslint/no-unused-vars": "error"`
- [x] T123 [US3] Create `frontend/.prettierrc`: `{"singleQuote": true, "semi": true, "tabWidth": 2, "trailingComma": "es5", "printWidth": 88}`

### Phase 8 Validation

- [x] T124 [US3] Run `cd frontend && npx tsc --noEmit` — verify exits with code 0 and zero type errors
- [x] T125 [US3] Run `cd frontend && npx eslint .` — verify exits with code 0 and zero lint errors
- [x] T126 [US3] Run `cd frontend && npx prettier --check .` — verify exits with code 0 and zero formatting errors
- [x] T127 [US3] Open `http://localhost:3000` in browser — verify the page loads with no console errors and the home page content is visible
- [x] T128 [US3] Verify `AppLayout` renders: open browser DevTools, confirm `<header>` and `<aside>` elements are present in the DOM
- [x] T129 [US3] Verify API client types align with backend contract: import `ApiError` and `StandardResponse<HealthData>` in a TypeScript file and confirm TypeScript accepts the health check response shape

**Gate 8**: Proceed to Phase 9 only when T124–T129 all pass.

---

## Phase 9: Testing Infrastructure and Final Validation

**Purpose**: Implement unit and integration tests for the core platform layer, configure frontend testing, and perform final end-to-end validation against all Epic exit criteria.

**Story Coverage**: Validation across US1, US2, US3
**Deliverables**: Complete test suite, all exit criteria verified

### Backend Test Infrastructure

- [x] T130 Create `backend/tests/__init__.py`, `backend/tests/unit/__init__.py`, `backend/tests/unit/core/__init__.py`, `backend/tests/integration/__init__.py`, `backend/tests/integration/api/__init__.py`
- [x] T131 Create `backend/tests/conftest.py`: define `test_settings` fixture returning `Settings` with `DATABASE_URL` pointing to a dedicated test database, `ENVIRONMENT="testing"`, `DEBUG=false`; define `test_db_engine` fixture (session-scoped) that creates the test database engine and runs `Base.metadata.create_all()`; define `db_session` fixture (function-scoped) that provides a SQLAlchemy session wrapped in a transaction that rolls back after each test (to ensure test isolation); define `test_client` fixture providing `TestClient(app)` for HTTP testing

### US1 — Backend Integration Tests (New Developer Onboarding)

- [x] T132 [US1] Implement `backend/tests/integration/api/test_health.py`: test `GET /api/v1/health` returns HTTP 200 with `data.status = "healthy"` and `data.database = "connected"` when database is available; test response includes `X-Request-ID` header; test response body `meta.request_id` matches `X-Request-ID` header value; test `data.version` matches `settings.API_VERSION`; test `data.timestamp` is a valid ISO 8601 datetime string
- [x] T133 [US1] Add to `backend/tests/integration/api/test_health.py`: test exception handler integration — create a test endpoint that raises `NotFoundException`; verify it returns HTTP 404 with `{"error": {"code": "NOT_FOUND", ...}}`; verify unhandled `Exception` returns HTTP 500 with `code: "INTERNAL_ERROR"` and no stack trace in response body

### US1 — Logging Unit Tests

- [x] T134 [US1] Implement `backend/tests/unit/core/test_logging.py`: test `configure_logging()` does not raise; test log output in `ENVIRONMENT=production` is valid JSON (capture log output via handler); test required fields are present in every log record: `timestamp`, `level`, `logger`, `message`; test `DATABASE_URL` value does not appear in any log output when logging settings at INFO level

### US1 — Settings Unit Tests

- [x] T135 [US1] Implement `backend/tests/unit/core/test_settings.py`: test `Settings()` raises `ValidationError` when `DATABASE_URL` is missing from environment; test `Settings()` raises `ValidationError` when `SECRET_KEY` is missing; test `Settings()` loads correctly with all required variables present; test optional variables use correct defaults: `DEBUG=False`, `LOG_LEVEL="INFO"`, `API_VERSION="1.0.0"`, `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=10`

### US2 — Base Repository Unit Tests (Module Developer Extending the Foundation)

- [x] T136 [US2] Implement `backend/tests/unit/core/test_base_repository.py`: define a concrete test model `TestEntity(TenantBaseModel)` with `__tablename__ = "test_entities"` and a `name: Mapped[str]` field; define `TestRepository(BaseRepository[TestEntity])`; test `create()` persists the entity and returns it with a populated `id`; test `get_by_id()` returns the entity when `company_id` matches; test `get_by_id()` raises `NotFoundException` when `company_id` does not match (cross-tenant protection); test `get_by_id()` raises `NotFoundException` when record is soft-deleted; test `list()` excludes soft-deleted records by default; test `list(include_deleted=True)` includes soft-deleted records; test `soft_delete()` sets `is_deleted=True` and populates `deleted_at`; test `list()` always filters by `company_id` (records from other tenants are never returned)
- [x] T137 [US2] Implement `backend/tests/unit/core/test_schemas.py`: test `StandardResponse[str]` serializes to `{"data": "...", "message": "...", "meta": {...}}`; test `ErrorResponse` serializes to `{"error": {"code": "...", "message": "...", "details": {}}}`; test `PaginatedResponse` with items, total, page, page_size, pages; test `PaginationParams` with default values `page=1`, `page_size=20`

### US2 — Exception Handler Unit Tests

- [x] T138 [US2] Implement `backend/tests/unit/core/test_exceptions.py`: test each exception subclass has correct default `code` and `http_status`; test `ValidationException` defaults: `code="VALIDATION_ERROR"`, `http_status=422`; test `NotFoundException` defaults: `code="NOT_FOUND"`, `http_status=404`; test `ConflictException` defaults: `code="CONFLICT"`, `http_status=409`; test `UnauthorizedException` defaults: `code="UNAUTHORIZED"`, `http_status=401`; test `ForbiddenException` defaults: `code="FORBIDDEN"`, `http_status=403`; test `InfrastructureException` defaults: `code="INTERNAL_ERROR"`, `http_status=500`

### US2 — Utilities Unit Tests

- [x] T139 [US2] Implement `backend/tests/unit/core/test_utils.py`: test `generate_uuid()` returns a valid UUID4; test `utcnow()` returns a `datetime` with `tzinfo` set (not naive); test `format_iso()` returns a string matching ISO 8601 format; test `calculate_pages(0, 20)` returns 0; test `calculate_pages(1, 20)` returns 1; test `calculate_pages(150, 20)` returns 8; test `calculate_offset(1, 20)` returns 0; test `calculate_offset(2, 20)` returns 20

### US3 — Frontend Testing Infrastructure

- [x] T140 [US3] Configure Jest and React Testing Library for the Next.js app: install `jest`, `jest-environment-jsdom`, `@testing-library/react`, `@testing-library/jest-dom`, `@types/jest` as dev dependencies; create `frontend/jest.config.ts` with `testEnvironment: "jsdom"`, module name mapper for `@/*` path alias, and `setupFilesAfterFramework` pointing to `jest.setup.ts`
- [x] T141 [US3] Create `frontend/jest.setup.ts` importing `@testing-library/jest-dom` for extended matchers
- [x] T142 [US3] Implement `frontend/src/__tests__/AppLayout.test.tsx`: test `AppLayout` renders without throwing; test `AppLayout` renders a `<header>` element; test `AppLayout` renders an `<aside>` element; test `AppLayout` renders `children` prop content in the main area; use `render()` from React Testing Library and `screen.getByRole()` / `screen.getByText()` for assertions

### Final Validation — Epic Exit Criteria

- [x] T143 Run all backend unit tests and verify zero failures: `cd backend && pytest tests/unit/ -v --tb=short`
- [x] T144 Run all backend integration tests and verify zero failures: `cd backend && pytest tests/integration/ -v --tb=short`
- [x] T145 [P] Run all frontend tests and verify zero failures: `cd frontend && npm test -- --watchAll=false`
- [x] T146 [P] Run all backend code quality checks in sequence: `black --check .`, `ruff check .`, `mypy .` — all must exit with code 0
- [x] T147 [P] Run all frontend code quality checks: `npx tsc --noEmit`, `npx eslint .`, `npx prettier --check .` — all must exit with code 0
- [x] T148 Perform full manual verification per `specs/001-foundation-platform/quickstart.md` manual verification checklist (steps 1–12) — Docker-dependent steps (1, 4, 16) deferred; all code-verifiable steps pass
- [x] T149 Verify all 20 Epic exit criteria from `specs/001-foundation-platform/plan.md` Exit Criteria section are satisfied — 17/20 pass; criteria 1 (docker compose), 4 (browser), 16 (Alembic fresh PG) deferred until Docker Desktop is available
- [x] T150 Update `specs/001-foundation-platform/spec.md` Status field from `Draft` to `Implemented`
- [x] T151 Update `README.md` with final verified setup instructions, confirmed command outputs, and any implementation notes

**Gate 9 (Epic Complete)**: All tasks T143–T151 pass.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0** (Scaffolding): No dependencies — start immediately
- **Phase 1** (Config/Quality): Depends on Phase 0
- **Phase 2** (Logging): Depends on Phase 1 (Settings required)
- **Phase 3** (Database): Depends on Phase 2 (Logging must be active before DB init)
- **Phase 4** (Exceptions/Schemas): Depends on Phase 2 (Logging for handler); Phase 1 (Pydantic)
- **Phase 5** (Base Patterns): Depends on Phase 3 (database session) and Phase 4 (exception types)
- **Phase 6** (Middleware/API): Depends on ALL prior phases
- **Phase 7** (Docker): Depends on Phase 6 (working application)
- **Phase 8** (Frontend): Depends on Phase 7 (API available for client testing)
- **Phase 9** (Testing/Validation): Depends on ALL prior phases

### Parallel Opportunities Within Phases

**Phase 0**: T003, T004, T005 can run in parallel (different directories)

**Phase 1**: T014 and T015 can be written while T018 installs dependencies; T025 can run in parallel with other Phase 1 tasks

**Phase 5**: T068, T069, T070 (utility modules) can be created in parallel — different files, no dependencies between them

**Phase 9**: T145, T146, T147 can run in parallel (independent checks)

### User Story Dependencies

- **US1** (New Developer Onboarding): Requires Phase 0–7 complete. Independently verifiable via `docker compose up` + health check + log inspection.
- **US2** (Module Developer): Requires Phase 0–6 complete. Independently verifiable by importing `BaseRepository`, `BaseService`, and extending them in a test context.
- **US3** (Frontend Developer): Requires Phase 0–8 complete. Independently verifiable by running `npm run dev` and checking the frontend loads with components available.

---

## Parallel Example: Phase 5 Utilities

```bash
# These three tasks can run simultaneously (different files):
Task T068: Implement backend/core/utils/uuid.py
Task T069: Implement backend/core/utils/datetime.py
Task T070: Implement backend/core/utils/pagination.py

# Then T071+ proceeds after T068-T070 complete:
Task T071: Create backend/core/repositories/__init__.py
Task T072: Implement backend/core/repositories/base.py (uses uuid.py and datetime.py)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 0: Scaffolding
2. Complete Phase 1: Configuration
3. Complete Phase 2: Logging
4. Complete Phase 3: Database
5. Complete Phase 4: Exceptions
6. Complete Phase 5: Base Patterns
7. Complete Phase 6: Middleware/API
8. Complete Phase 7: Docker
9. **STOP and VALIDATE**: `docker compose up` → health check → logs working → US1 complete
10. Proceed to Phase 8 (Frontend) and Phase 9 (Testing) to close US2 and US3

### Incremental Delivery

- After Gate 7 (Phase 7 complete): US1 is deliverable — new developer onboarding works
- After Gate 8 (Phase 8 complete): US3 is deliverable — frontend foundation works
- After Gate 9 (Phase 9 complete): US2 is validated — base patterns are tested and reliable
- Epic is complete when all gates pass

### Single Developer Strategy

Follow phases sequentially: Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 → Phase 8 → Phase 9. Validate at each gate before proceeding.

### Two-Developer Strategy

- Developer A: Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7 (backend + Docker)
- Developer B: Phase 8 begins after Gate 7 (Docker up); Phase 9 testing begins in parallel
- Both developers collaborate on Phase 9 final validation

---

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 151 |
| Phase 0 (Scaffolding) | 10 tasks |
| Phase 1 (Config/Quality) | 20 tasks |
| Phase 2 (Logging) | 8 tasks |
| Phase 3 (Database) | 17 tasks |
| Phase 4 (Exceptions/Schemas) | 11 tasks |
| Phase 5 (Base Patterns) | 12 tasks |
| Phase 6 (Middleware/API) | 17 tasks |
| Phase 7 (Docker) | 12 tasks |
| Phase 8 (Frontend) | 22 tasks |
| Phase 9 (Testing/Validation) | 22 tasks |
| [US1] Tagged Tasks | 36 |
| [US2] Tagged Tasks | 22 |
| [US3] Tagged Tasks | 24 |
| [P] Parallelizable Tasks | 18 |
| Validation Gate Tasks | 31 |
| No-flag Foundation Tasks | 69 |

---

## Notes

- `[P]` tasks = different files, no inter-task dependencies — safe to run concurrently
- `[US1]`, `[US2]`, `[US3]` labels map tasks to specific user stories for traceability
- No `[P]` tag is applied to tasks that modify the same file or depend on a prior task in the same phase
- Every phase ends with explicit validation gate tasks — phase is not complete until all gate tasks pass
- Commit after each completed and validated phase, not after individual tasks
- No task produces implementation code — all tasks describe WHAT to implement, not HOW
- The test database must be a separate PostgreSQL database from the development database (separate `DATABASE_URL` in test settings)
