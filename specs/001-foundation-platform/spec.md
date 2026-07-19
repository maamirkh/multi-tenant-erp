# Feature Specification: Foundation Platform

**Feature Branch**: `001-foundation-platform`
**Created**: 2026-07-11
**Status**: Implemented
**Epic**: Epic 1 — Foundation Platform

---

## Epic Charter

### Epic Name

Foundation Platform

### Purpose

Create the reusable technical foundation for the DevSphere ERP platform.

This Epic establishes the shared infrastructure upon which every future ERP module will be built. No business functionality shall be implemented in this Epic. The sole deliverable is a stable, well-structured, developer-ready project foundation.

### Business Value

Provide a stable, scalable, maintainable, and production-ready platform that supports rapid development of future ERP modules. Poor architectural foundations compound costs over time; investing in a correct foundation eliminates rework and enables every future team member and module to operate confidently within a consistent structure.

### Goals

- Create the backend foundation using FastAPI and supporting libraries.
- Create the frontend foundation using Next.js with TypeScript.
- Establish the monorepo project structure.
- Configure a Docker-based development environment.
- Configure PostgreSQL as the primary database.
- Configure Alembic for database migrations.
- Prepare Better Auth integration readiness (wiring, not implementation).
- Establish structured JSON logging.
- Establish centralized error handling.
- Establish API standards and versioning strategy.
- Create reusable base models, repositories, and services.
- Create reusable frontend component infrastructure.
- Prepare the project for future SaaS growth.

### In Scope

- Monorepo structure
- Docker and Docker Compose
- FastAPI application setup
- Next.js application setup
- PostgreSQL connection and session management
- Alembic migration configuration
- Configuration and environment variable management
- Structured logging framework
- Centralized exception handling
- Health check endpoints
- API versioning (`/api/v1/`)
- Base SQLAlchemy models
- Base repository pattern
- Base service pattern
- Shared utility modules
- Common response models (Pydantic)
- Project folder structure
- Development tooling configuration
- Code quality tooling (formatting, linting, type checking)

### Out of Scope

- Authentication and Authorization implementation
- Company (Tenant) Management module
- User Management module
- Inventory module
- Purchase module
- Sales module
- Accounting module
- CRM module
- Installments module
- Reports module
- Business rules for any domain
- Business workflows of any kind

### Success Criteria

This Epic is complete when a new developer can clone the repository, execute one setup command (`docker compose up`), start the development environment, and have a fully working project foundation ready for future feature development — with all health checks passing, logging operational, and the base infrastructure verified.

### Dependencies

- Approved `constitution.md` (v1.1.0 or higher)

### Risks

| Risk | Mitigation |
|------|------------|
| Poor architecture decisions creating technical debt | Strict adherence to the Constitution; ADR documentation for all significant decisions |
| Tight coupling between infrastructure layers | Enforce strict layered architecture from the start |
| Inconsistent project structure causing developer confusion | Define and document folder structure in the specification before implementation |
| Weak development standards causing quality drift | Configure and enforce code quality tooling (Black, Ruff, mypy, ESLint) from day one |

---

## Problem Statement

The DevSphere ERP platform requires a technically sound, consistent, and production-grade foundation before any business module can be developed. Without this foundation, each module would be built on inconsistent patterns, leading to maintenance burden, structural debt, and inability to scale across business domains or tenants.

Currently, no project infrastructure exists. A new developer joining the team would have no clear starting point, no consistent patterns to follow, no local development environment to run, and no standards to enforce code quality. This Epic resolves that gap entirely.

The foundation must be architected to support multi-tenancy, SaaS growth, and modular expansion — all from day one — so that future modules can be developed in parallel, independently, and to a consistent quality standard.

---

## Objectives

1. Establish a monorepo project structure with clear separation between backend, frontend, and shared concerns.
2. Provide a one-command Docker development environment that is reproducible across all developer machines.
3. Configure FastAPI as the backend framework with all required infrastructure: routing, middleware, error handling, and logging.
4. Configure Next.js as the frontend framework with TypeScript strict mode, Tailwind CSS, and shadcn/ui component infrastructure.
5. Configure PostgreSQL with SQLAlchemy ORM and Alembic migrations.
6. Define and implement base classes for models, repositories, and services that all future modules must extend.
7. Establish configuration management via environment variables with documented `.env.example` files.
8. Implement structured JSON logging that captures all required observability fields.
9. Implement centralized exception handling that produces consistent, safe error responses.
10. Implement API versioning (`/api/v1/`) as the standard prefix for all future endpoints.
11. Establish code quality tooling (Black, Ruff, mypy, ESLint, Prettier) with enforced configuration.
12. Prepare the codebase structure and wiring points for Better Auth integration in a future Epic.

---

## User Scenarios & Testing

### User Story 1 — New Developer Onboarding (Priority: P1)

A new developer joins the team and needs to set up the complete local development environment and verify that the platform foundation is working correctly.

**Why this priority**: If a developer cannot start the environment, nothing else in this Epic is useful. This scenario validates the entire foundation end-to-end.

**Independent Test**: A developer with only a machine running Docker can clone the repository, run one command, and verify all services are running and healthy.

**Acceptance Scenarios**:

1. **Given** a clean developer machine with Docker and Docker Compose installed, **When** the developer clones the repository and runs `docker compose up`, **Then** all services (backend API, frontend, and database) start without errors.
2. **Given** all services are running, **When** the developer visits the backend health check endpoint, **Then** a JSON response is returned confirming the API and database are operational.
3. **Given** all services are running, **When** the developer visits the frontend application URL, **Then** the Next.js application loads without errors.
4. **Given** the project is running, **When** the developer inspects logs, **Then** structured JSON logs are visible confirming request handling and startup events.

---

### User Story 2 — Module Developer Extending the Foundation (Priority: P2)

A backend developer is building a new ERP module (e.g., Inventory) and needs to extend the base infrastructure to implement their module's models, repositories, and services.

**Why this priority**: The base infrastructure classes are the primary reusable artifact of this Epic. If they are incorrect or incomplete, every future module is affected.

**Independent Test**: A developer can create a new module folder, extend the base model, repository, and service classes, and have a working module scaffold with no duplicate infrastructure code.

**Acceptance Scenarios**:

1. **Given** the base model class exists, **When** a developer creates a new SQLAlchemy model by extending the base, **Then** the new model inherits standard fields (`id`, `company_id`, `created_at`, `updated_at`, `created_by`, `is_deleted`, `deleted_at`) without redeclaration.
2. **Given** the base repository class exists, **When** a developer creates a module repository by extending the base, **Then** standard CRUD operations are available without reimplementation.
3. **Given** the base service class exists, **When** a developer creates a module service by extending the base, **Then** the service has access to dependency injection hooks and standard patterns.
4. **Given** a new module endpoint is registered, **When** it is called without authentication headers, **Then** the authentication wiring point is in place (even if auth is not yet implemented) and the response structure matches the standard error format.

---

### User Story 3 — Frontend Developer Creating Module UI (Priority: P3)

A frontend developer is building the UI for a future ERP module and needs a consistent component foundation to start from.

**Why this priority**: The frontend foundation is important but does not block backend module development; it is parallel work.

**Independent Test**: A developer can create a new page in the Next.js application and use shared layout components, theme tokens, and utility hooks without building them from scratch.

**Acceptance Scenarios**:

1. **Given** the shared component library is initialized, **When** a developer imports a shared layout component, **Then** it renders correctly with the established design system (Tailwind CSS and shadcn/ui).
2. **Given** the TypeScript strict mode is configured, **When** a developer introduces a type error, **Then** the TypeScript compiler reports the error and the build fails.
3. **Given** the API client infrastructure is established, **When** a developer needs to call a backend endpoint, **Then** a typed API client module is available to use rather than raw fetch calls.

---

### Edge Cases

- What happens when a required environment variable is missing at startup? The application must refuse to start and log a clear, descriptive error identifying the missing variable.
- What happens when the database is unreachable at startup? The health check endpoint must report an unhealthy status with a clear message; the application must not crash silently.
- What happens when an unhandled exception occurs in any endpoint? The centralized exception handler must intercept it, log the full context (including request ID, stack trace, tenant, and user), and return a safe, structured error response with no internal details exposed.
- What happens when a developer runs database migrations on an empty database? Alembic must initialize the schema cleanly from the initial migration with no errors.
- What happens when the Docker environment is stopped and restarted? The database state must persist via Docker volumes; no data loss occurs.

---

## Requirements

### Functional Requirements

#### Project Structure and Monorepo

- **FR-001**: The project MUST be organized as a monorepo with a clear top-level structure separating backend, frontend, infrastructure, and specification artifacts.
- **FR-002**: The monorepo MUST include a `backend/` directory containing the FastAPI application.
- **FR-003**: The monorepo MUST include a `frontend/` directory containing the Next.js application.
- **FR-004**: The monorepo MUST include a `docker-compose.yml` at the root for orchestrating all services.
- **FR-005**: The monorepo MUST include `specs/`, `history/`, and `.specify/` directories for Spec-Driven Development artifacts.

#### Docker and Development Environment

- **FR-006**: A single `docker compose up` command MUST start the complete development environment, including the backend API, frontend application, and PostgreSQL database.
- **FR-007**: The Docker Compose configuration MUST define services for: `api` (FastAPI), `web` (Next.js), and `db` (PostgreSQL).
- **FR-008**: The database service MUST use a named Docker volume to persist data between restarts.
- **FR-009**: Environment variables MUST be loaded from a `.env` file; a `.env.example` MUST document all required variables with placeholder values and inline descriptions.
- **FR-010**: Backend source code changes MUST trigger automatic reload without restarting the Docker container (hot reload in development mode).
- **FR-011**: Frontend source code changes MUST trigger automatic reload (Next.js fast refresh) without restarting the Docker container.

#### Backend Application — FastAPI

- **FR-012**: The FastAPI application MUST initialize with a well-defined application factory pattern, separating startup configuration from the ASGI application instance.
- **FR-013**: The API MUST expose all routes under the `/api/v1/` prefix as the standard versioning base.
- **FR-014**: The FastAPI application MUST register CORS middleware configured to allow development origins and be configurable for production origins via environment variables.
- **FR-015**: The FastAPI application MUST include a health check endpoint at `/api/v1/health` that returns the current status of the API and the database connection.
- **FR-016**: The health check endpoint MUST return a structured JSON response including `status`, `database`, `version`, and `timestamp` fields.
- **FR-017**: All API responses MUST follow a consistent envelope structure with `data`, `message`, and `meta` fields for successful responses.
- **FR-018**: The application MUST expose interactive API documentation (Swagger UI and ReDoc) in development mode, disabled in production.

#### Backend Application — Configuration Management

- **FR-019**: All application configuration MUST be loaded through a centralized `Settings` class using environment variables, with no scattered `os.getenv()` calls throughout the codebase.
- **FR-020**: The `Settings` class MUST define required variables with types and validation; missing required variables MUST cause a startup failure with a descriptive error.
- **FR-021**: Configuration MUST support distinct profiles for `development`, `testing`, and `production` environments.

#### Backend Application — Logging

- **FR-022**: All application logging MUST produce structured JSON output, not plain text.
- **FR-023**: Every log entry MUST include the following fields: `timestamp` (ISO 8601 UTC), `level`, `logger`, `message`, `request_id`, `environment`.
- **FR-024**: Request-scoped log entries MUST additionally include: `company_id`, `user_id`, `method`, `path`, `status_code`, `duration_ms`.
- **FR-025**: Logs MUST NOT include sensitive data including passwords, tokens, PII, or secret keys.
- **FR-026**: Log levels MUST follow the standard convention: DEBUG, INFO, WARNING, ERROR, CRITICAL.
- **FR-027**: Log output in development MUST be human-readable (pretty-printed or colored); in production MUST be pure JSON for log aggregation pipelines.

#### Backend Application — Error Handling

- **FR-028**: A centralized exception handler MUST be registered at the FastAPI application level to intercept all unhandled exceptions.
- **FR-029**: All error responses MUST conform to a consistent structure with `error.code`, `error.message`, and `error.details` fields.
- **FR-030**: Internal error details (stack traces, database errors, system paths) MUST NEVER be included in error responses sent to clients in production.
- **FR-031**: Business rule violations MUST return HTTP 4xx responses with appropriate error codes.
- **FR-032**: Infrastructure and unexpected failures MUST return HTTP 5xx responses with a generic, safe message.
- **FR-033**: Every exception MUST be logged with full context including request ID, tenant ID (if available), user ID (if available), and the full stack trace.
- **FR-034**: A custom `ApplicationException` base class MUST be defined for all application-specific exceptions, enabling centralized handling and consistent error code assignment.

#### Backend Application — Database and ORM

- **FR-035**: The SQLAlchemy engine and session factory MUST be configured centrally and initialized at application startup.
- **FR-036**: Database session management MUST use FastAPI dependency injection to provide a session per request and ensure cleanup on completion.
- **FR-037**: All SQLAlchemy models MUST extend a `BaseModel` class that provides the mandatory fields: `id`, `created_at`, `updated_at`.
- **FR-038**: All business entity models MUST extend a `TenantBaseModel` class that extends `BaseModel` and adds the mandatory tenant isolation fields: `company_id`, `created_by`, `is_deleted`, `deleted_at`.
- **FR-039**: Alembic MUST be configured with `autogenerate` support to detect model changes and generate migration files.
- **FR-040**: An initial Alembic migration MUST be created that establishes the baseline schema (empty at this stage — no business tables yet).
- **FR-041**: All Alembic migration files MUST include both `upgrade()` and `downgrade()` functions.

#### Backend Application — Base Patterns

- **FR-042**: A `BaseRepository` class MUST be defined providing generic typed implementations for standard data access operations: create, get by ID (with tenant scope), list (with tenant scope and pagination), update, and soft delete.
- **FR-043**: The `BaseRepository` MUST enforce tenant isolation — all queries MUST accept and apply `company_id` filtering.
- **FR-044**: A `BaseService` class MUST be defined providing common service infrastructure including repository injection and dependency management.
- **FR-045**: Common Pydantic response schemas MUST be defined for: paginated list responses, standard success responses, and standard error responses.
- **FR-046**: Utility modules MUST be established for: UUID generation, timestamp handling, and pagination parameter parsing.

#### Backend Application — Better Auth Readiness

- **FR-047**: The FastAPI application MUST include defined middleware hooks and dependency injection points for future authentication middleware, clearly documented as placeholders for the Better Auth Epic.
- **FR-048**: The project MUST include a `core/auth/` directory stub defining the interface contracts that the authentication layer will fulfill, enabling other layers to depend on the interface without implementation.

#### Frontend Application — Next.js

- **FR-049**: The Next.js application MUST be configured with TypeScript in strict mode (no implicit `any`, strict null checks, full type coverage).
- **FR-050**: Tailwind CSS MUST be configured with the project's design token set (colors, spacing, typography) defined in the Tailwind configuration file.
- **FR-051**: shadcn/ui MUST be initialized and the foundational UI components installed: Button, Input, Card, Dialog, Toast, and Loading Spinner equivalents.
- **FR-052**: A shared application layout component MUST be defined establishing the primary page structure (header placeholder, sidebar placeholder, main content area).
- **FR-053**: A typed API client module MUST be established defining the base fetch wrapper with request/response typing, error handling, and environment-based URL configuration.
- **FR-054**: Environment variables MUST be managed via `.env.local` for development; a `.env.example` MUST document all required frontend variables.
- **FR-055**: ESLint and Prettier MUST be configured and enforced for all frontend TypeScript and TSX files.

#### Code Quality Tooling

- **FR-056**: Backend Python code MUST be formatted with Black and linted with Ruff; configuration files MUST define and enforce these standards.
- **FR-057**: Backend Python code MUST pass type checking with mypy in strict mode; configuration MUST include mypy settings.
- **FR-058**: Frontend TypeScript code MUST be formatted with Prettier and linted with ESLint; configuration files MUST define and enforce these standards.
- **FR-059**: Pre-commit hooks or equivalent automation MUST enforce code quality checks before code can be committed.

---

### Key Entities

- **Settings**: The centralized application configuration object, loaded from environment variables at startup, containing all required configuration keys with types and validation.
- **BaseModel**: The root SQLAlchemy ORM model providing `id`, `created_at`, `updated_at` fields to all database entities.
- **TenantBaseModel**: Extends `BaseModel` to add `company_id`, `created_by`, `is_deleted`, `deleted_at` — mandatory for all business entities.
- **BaseRepository**: The generic typed repository class providing standard tenant-scoped data access operations for any model type.
- **BaseService**: The base class for all service layer implementations, providing dependency injection infrastructure.
- **ApplicationException**: The base custom exception class from which all application-specific exceptions are derived.
- **StandardResponse**: The Pydantic schema for successful API responses, following the `{data, message, meta}` envelope pattern.
- **ErrorResponse**: The Pydantic schema for error API responses, following the `{error: {code, message, details}}` structure.
- **PaginatedResponse**: The Pydantic schema for paginated list responses, including `items`, `total`, `page`, `page_size`, and `pages` fields.

---

## Non-Functional Requirements

### Performance

- **NFR-001**: The backend API MUST respond to health check requests in under 200 milliseconds under normal conditions.
- **NFR-002**: The `docker compose up` command MUST bring all services to a running state within 60 seconds on a standard developer machine.
- **NFR-003**: Hot reload of backend code changes MUST complete within 3 seconds.
- **NFR-004**: The frontend application MUST perform a full hot reload in under 5 seconds for typical file changes.

### Reliability

- **NFR-005**: The health check endpoint MUST reliably report database connectivity status; a database failure MUST be reported within 5 seconds.
- **NFR-006**: The application MUST handle startup failures gracefully, logging the cause and exiting with a non-zero exit code rather than crashing silently.
- **NFR-007**: No unhandled exception in any request should cause the application process to crash; all exceptions must be intercepted by the centralized handler.

### Maintainability

- **NFR-008**: All code MUST pass configured linting, formatting, and type checking tools with zero warnings or errors.
- **NFR-009**: Folder structure and module organization MUST be consistent and self-explanatory; a new developer MUST be able to locate any concern without searching.
- **NFR-010**: All base classes and utility modules MUST include clear docstrings describing their purpose, parameters, and usage contract.

### Security

- **NFR-011**: No secrets, credentials, database URLs, or API keys MUST appear in source code or committed files.
- **NFR-012**: The `.env` file MUST be listed in `.gitignore`; only `.env.example` (with placeholder values) may be committed.
- **NFR-013**: CORS configuration MUST restrict allowed origins; wildcard origins (`*`) MUST only be used in controlled development mode and MUST be overridden via environment variable for production.
- **NFR-014**: Docker containers MUST NOT run as root; a non-root user MUST be configured in production-targeted Dockerfiles.
- **NFR-015**: `.dockerignore` files MUST prevent `.env`, secret files, and development artifacts from being included in Docker images.

### Scalability

- **NFR-016**: The base patterns (BaseRepository, BaseService, BaseModel) MUST be designed generically enough to support any future business module without modification to the base classes themselves.
- **NFR-017**: The database session management MUST support connection pooling configuration to handle future load increases.

---

## Technical Requirements

### Backend Technical Stack

| Concern | Requirement |
|---------|-------------|
| Framework | FastAPI (latest stable) |
| Language | Python (latest stable LTS) |
| ORM | SQLAlchemy |
| Schema Validation | Pydantic v2 |
| Migrations | Alembic |
| Logging | Python standard logging with structured JSON formatter |
| Type Checking | mypy (strict mode) |
| Formatter | Black |
| Linter | Ruff |
| Package Management | Poetry or pip with pinned versions |

### Frontend Technical Stack

| Concern | Requirement |
|---------|-------------|
| Framework | Next.js (latest stable, App Router) |
| Language | TypeScript (strict mode) |
| Styling | Tailwind CSS |
| UI Components | shadcn/ui |
| Formatter | Prettier |
| Linter | ESLint |
| Package Management | npm or pnpm with lock file committed |

### Infrastructure

| Concern | Requirement |
|---------|-------------|
| Containerization | Docker |
| Local Orchestration | Docker Compose v2 |
| Database | PostgreSQL (latest stable LTS) |

---

## Architecture Overview

The Foundation Platform establishes a **Modular Monolith** architecture compliant with the Constitution (§5). The backend and frontend are separate applications within a monorepo, communicating exclusively via HTTP API. All future ERP modules are built as vertical slices within the backend `modules/` directory, each following the mandated layered pattern.

### Architectural Layers (Backend)

The request flow enforces a strict unidirectional hierarchy:

```
Client Request
     ↓
  API Router (routes/)            — Input validation, middleware, versioning
     ↓
  Service Layer (services/)       — Business logic, orchestration
     ↓
  Repository Layer (repositories/)  — Data access, tenant scoping
     ↓
  Database (PostgreSQL)
```

No layer may bypass or reach across this hierarchy. Services call repositories. Repositories call the database. Routers call services. This pattern is enforced through the base class design and code review standards.

### Platform vs. Module Separation

The `core/` directory contains the platform layer, shared by all modules. The `modules/` directory contains business module vertical slices, each independently organized. No module may import from another module's internal layers.

---

## Folder Structure

### Monorepo Root

```
erp-system/
├── backend/                    — FastAPI application
├── frontend/                   — Next.js application
├── specs/                      — Spec-Driven Development specifications
│   └── 001-foundation-platform/
│       └── spec.md
├── history/                    — ADRs and Prompt History Records
│   ├── adr/
│   └── prompts/
├── .specify/                   — Specify templates, scripts, constitution
│   ├── memory/
│   │   └── constitution.md
│   ├── templates/
│   └── scripts/
├── docker-compose.yml          — Development orchestration
├── .env.example                — Root environment variable documentation
├── .gitignore
└── README.md
```

### Backend Structure

```
backend/
├── core/
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py         — Centralized Settings class
│   ├── database/
│   │   ├── __init__.py
│   │   ├── engine.py           — SQLAlchemy engine and session factory
│   │   ├── base.py             — SQLAlchemy declarative base
│   │   ├── session.py          — Session dependency for FastAPI
│   │   └── models/
│   │       ├── base_model.py   — BaseModel (id, timestamps)
│   │       └── tenant_base.py  — TenantBaseModel (+ company_id, soft delete)
│   ├── logging/
│   │   ├── __init__.py
│   │   └── setup.py            — Structured JSON logging configuration
│   ├── exceptions/
│   │   ├── __init__.py
│   │   ├── base.py             — ApplicationException and hierarchy
│   │   └── handler.py          — Global FastAPI exception handler
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── request_id.py       — Request ID injection middleware
│   │   └── auth_hook.py        — Placeholder hook for future Better Auth
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── response.py         — StandardResponse, ErrorResponse
│   │   └── pagination.py       — PaginatedResponse, PaginationParams
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── base.py             — BaseRepository (generic, typed)
│   ├── services/
│   │   ├── __init__.py
│   │   └── base.py             — BaseService
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── uuid.py             — UUID generation utilities
│   │   ├── datetime.py         — Timezone-aware timestamp utilities
│   │   └── pagination.py       — Pagination calculation utilities
│   └── auth/
│       ├── __init__.py
│       └── interfaces.py       — Auth interface stubs and contracts
├── modules/                    — Empty in this Epic; future modules added here
├── api/
│   ├── __init__.py
│   └── v1/
│       ├── __init__.py
│       └── router.py           — v1 API router; includes health check endpoint
├── migrations/                 — Alembic migration directory
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_baseline.py
├── tests/
│   ├── unit/
│   │   └── core/
│   └── integration/
│       └── api/
├── main.py                     — Application factory, ASGI entrypoint
├── alembic.ini                 — Alembic configuration
├── pyproject.toml              — Python project, Black, Ruff, mypy config
├── Dockerfile                  — Backend Docker image
└── .dockerignore
```

### Frontend Structure

```
frontend/
├── src/
│   ├── app/                    — Next.js App Router pages
│   │   ├── layout.tsx          — Root layout
│   │   ├── page.tsx            — Root page (placeholder)
│   │   └── globals.css         — Global styles
│   ├── components/
│   │   ├── ui/                 — shadcn/ui installed components
│   │   └── layout/
│   │       ├── AppLayout.tsx   — Primary application layout
│   │       ├── Header.tsx      — Header placeholder
│   │       └── Sidebar.tsx     — Sidebar placeholder
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts       — Base typed API client (fetch wrapper)
│   │   │   └── types.ts        — Shared API response types
│   │   └── utils.ts            — shadcn/ui utility (cn function)
│   └── types/
│       └── index.ts            — Global TypeScript type definitions
├── public/                     — Static assets
├── .env.example                — Frontend environment variable documentation
├── tailwind.config.ts          — Tailwind CSS configuration with design tokens
├── tsconfig.json               — TypeScript strict mode configuration
├── next.config.ts              — Next.js configuration
├── .eslintrc.json              — ESLint configuration
├── .prettierrc                 — Prettier configuration
├── package.json
├── Dockerfile                  — Frontend Docker image
└── .dockerignore
```

---

## Backend Architecture

### Application Factory

The FastAPI application MUST be created via an application factory function (`create_app()`) in `main.py`. This factory is responsible for:

1. Loading configuration via the `Settings` class.
2. Configuring structured logging.
3. Registering middleware (request ID, CORS, auth hook).
4. Registering global exception handlers.
5. Including the versioned API router.
6. Registering startup and shutdown lifecycle events.

This pattern separates the application creation from the ASGI server entrypoint, enabling testability and clean lifecycle management.

### Configuration Layer

The `Settings` class in `core/config/settings.py` is the single source of truth for all application configuration. It uses Pydantic BaseSettings for automatic environment variable loading and type coercion. It validates all required variables at startup and refuses to start if any are missing. No code outside the `core/config/` module may access environment variables directly.

### Database Layer

The database layer in `core/database/` provides:

- **Engine**: A SQLAlchemy engine instance configured from the `DATABASE_URL` setting, with connection pool settings.
- **Session Factory**: A session factory providing per-request database sessions.
- **FastAPI Dependency**: A `get_db()` dependency injection function that yields a session and ensures proper cleanup.
- **Base Models**: `BaseModel` and `TenantBaseModel` defining the mandatory field sets per the Constitution (§17).

### Repository Layer

The `BaseRepository` class in `core/repositories/base.py` is a generic, typed class providing:

- `create(entity)` — persist a new entity.
- `get_by_id(id, company_id)` — retrieve an entity by ID, scoped to tenant.
- `list(company_id, skip, limit, filters)` — retrieve a paginated list, scoped to tenant.
- `update(id, company_id, data)` — update an entity, scoped to tenant.
- `soft_delete(id, company_id)` — mark an entity as deleted, scoped to tenant.
- `hard_delete(id, company_id)` — physically delete (restricted to authorized administrative operations only).

All repository methods that access business data MUST require `company_id` as a mandatory parameter.

### Service Layer

The `BaseService` class in `core/services/base.py` provides constructor injection pattern for repository dependencies and standard service initialization patterns. Concrete services extend `BaseService` and implement business operations. Services must not contain HTTP logic, SQL queries, or framework-specific code.

### Exception Hierarchy

```
ApplicationException (base)
├── ValidationException      — Business rule violations (422)
├── NotFoundException        — Resource not found (404)
├── ConflictException        — Duplicate or conflicting state (409)
├── UnauthorizedException    — Missing or invalid authentication (401)
├── ForbiddenException       — Insufficient permissions (403)
└── InfrastructureException  — System-level failures (500)
```

The global exception handler maps each exception type to its HTTP status code and error response schema.

### Middleware Chain

Request processing passes through the following middleware in order:

1. **Request ID Middleware**: Assigns a unique request ID to every incoming request for logging correlation.
2. **CORS Middleware**: Configured with allowed origins, methods, and headers from environment settings.
3. **Auth Hook Middleware** (placeholder): A defined hook point where Better Auth middleware will be inserted in a future Epic.

### API Versioning

All API routes are served under the `/api/v1/` prefix. The `api/v1/router.py` file is the aggregator for all version 1 routes. Future modules register their routers here. Future API versions create a parallel `api/v2/` structure.

### Health Check Response

The health check endpoint at `/api/v1/health` returns:

- HTTP 200 with `status: healthy` and `database: connected` when all systems are operational.
- HTTP 503 with `status: degraded` and `database: disconnected` when the database is unreachable.

---

## Frontend Architecture

### App Router Structure

The Next.js application uses the App Router. The root `layout.tsx` establishes the application shell including global styles, font loading, and the `AppLayout` component. All future module pages are nested within this layout.

### Component Architecture

Components are organized into two tiers:

1. **UI Components** (`components/ui/`): shadcn/ui installed components. These MUST NOT be modified directly; custom variants are created as separate components.
2. **Layout Components** (`components/layout/`): Application-specific layout components (AppLayout, Header, Sidebar) that establish the overall page structure for future module pages.

### API Client

The typed API client in `lib/api/client.ts` provides a base fetch wrapper that prepends the `NEXT_PUBLIC_API_URL` to all requests, with TypeScript generics for typed request and response handling, error intercepting that maps API error responses to typed `ApiError` objects, and consistent handling of error states. No page or component may call `fetch()` or any HTTP library directly; all API calls go through this client.

### Type Safety

TypeScript strict mode is non-negotiable. `tsconfig.json` MUST enable `"strict": true`, `"noImplicitAny": true`, `"strictNullChecks": true`, and `"noUncheckedIndexedAccess": true`. Any suppression of type errors requires a justifying code comment and is subject to code review scrutiny.

---

## Shared Components

The following elements are shared across backend and frontend concerns:

- **API Response Contracts**: The `StandardResponse`, `ErrorResponse`, and `PaginatedResponse` Pydantic schemas on the backend have corresponding TypeScript type definitions on the frontend, ensuring contract alignment.
- **Environment Configuration Pattern**: Both backend and frontend follow the same `.env.example` documentation convention.
- **Error Structure**: The error response shape (`{error: {code, message, details}}`) is defined in both backend (Pydantic) and frontend (TypeScript) to ensure consumer-producer alignment.

---

## Configuration Strategy

### Backend Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | Application secret for cryptographic operations |
| `ENVIRONMENT` | Yes | `development`, `testing`, or `production` |
| `DEBUG` | No | Enables debug mode and Swagger UI; default `false` |
| `CORS_ORIGINS` | No | Comma-separated list of allowed CORS origins |
| `LOG_LEVEL` | No | Minimum log level; default `INFO` |
| `API_VERSION` | No | Current API version string; default `1.0.0` |
| `DB_POOL_SIZE` | No | Database connection pool size; default `5` |
| `DB_MAX_OVERFLOW` | No | Maximum connection overflow; default `10` |

### Frontend Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend API base URL |
| `NEXT_PUBLIC_APP_NAME` | No | Application display name; default `DevSphere ERP` |
| `NEXT_PUBLIC_ENVIRONMENT` | No | Frontend environment identifier |

All variables are documented in their respective `.env.example` files. No variable may be added to the codebase without a corresponding entry in `.env.example` with a descriptive comment.

---

## Docker Strategy

### Docker Compose Services

| Service | Purpose |
|---------|---------|
| `db` | PostgreSQL database |
| `api` | FastAPI backend application |
| `web` | Next.js frontend application |

### Service Dependencies

- `api` depends on `db` being healthy (healthcheck via `pg_isready`).
- `web` depends on `api` being available.

### Volume Strategy

- A named Docker volume (`postgres_data`) persists the database across container restarts.
- Backend source is mounted as a volume in development mode to enable hot reload.
- Frontend source is mounted as a volume in development mode to enable Next.js fast refresh.

### Dockerfile Strategy

- **Development Dockerfiles**: Based on full language runtime images; mount source as volume; run with hot reload.
- **Production Dockerfiles** (scaffolded for future use): Multi-stage builds; minimal final image; run as non-root user.
- `.dockerignore` files for both backend and frontend MUST exclude: `.env`, `node_modules/`, `__pycache__/`, `.git/`, `specs/`, `history/`.

---

## Database Strategy

### Database Initialization

The PostgreSQL database is initialized via Docker Compose. Alembic manages all schema state after initial container startup.

### Migration Strategy

- All schema changes occur exclusively through Alembic migrations.
- The initial migration establishes the migration history baseline on an empty schema.
- Future module migrations are added as sequential Alembic revisions.
- Every migration file MUST include both `upgrade()` and `downgrade()` functions.

### Tenant Isolation in the Data Layer

While no business tables exist in this Epic, the `TenantBaseModel` establishes the mandatory `company_id` field contract that all future business tables inherit. Repositories enforce this contract by requiring `company_id` on all tenant-scoped operations.

### Connection Management

SQLAlchemy connection pooling is configured with sensible defaults, overridable via environment variables. The database session is provided per request via FastAPI dependency injection and closed automatically after each request completes.

---

## Logging Strategy

### Log Format

All production log output MUST be valid JSON objects, one per line, suitable for consumption by log aggregation tools. Every log entry MUST include: `timestamp` (ISO 8601 UTC), `level`, `logger`, `message`, `request_id`, `environment`. Request-scoped entries additionally include: `company_id`, `user_id`, `method`, `path`, `status_code`, `duration_ms`.

Development mode MAY use a more readable format (colorized, aligned) while preserving the same fields.

### Logging Levels

| Level | Usage |
|-------|-------|
| DEBUG | Detailed developer diagnostic information |
| INFO | Standard operational events |
| WARNING | Recoverable conditions that warrant attention |
| ERROR | Failures affecting a specific operation |
| CRITICAL | System-level failures requiring immediate attention |

### What to Log

- Application startup and shutdown events.
- All incoming HTTP requests (method, path, status, duration, request ID).
- All unhandled exceptions with full stack trace and request context.
- Database connection events.
- Configuration loading events.

### What NOT to Log

- Passwords, tokens, or credentials in any form.
- Full database connection strings.
- PII beyond what is operationally required.
- Internal memory addresses or raw system internals.

---

## Error Handling Strategy

### Centralized Handler

A single global exception handler is registered at the FastAPI application level. This handler receives all unhandled exceptions, determines the exception type, maps it to an HTTP status code and error code, logs the full exception with context, and returns the standard `ErrorResponse` schema.

### Error Code Taxonomy

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 422 | Input validation failure |
| `NOT_FOUND` | 404 | Requested resource does not exist |
| `CONFLICT` | 409 | Resource already exists or conflicting state |
| `UNAUTHORIZED` | 401 | Authentication required or invalid |
| `FORBIDDEN` | 403 | Authenticated user lacks permission |
| `INTERNAL_ERROR` | 500 | Unexpected server-side failure |
| `SERVICE_UNAVAILABLE` | 503 | Dependent service unavailable |

Error codes MUST be stable across API versions. New codes may be added; existing codes MUST NOT change meaning or status mapping.

---

## API Standards

### Versioning

- All endpoints follow the pattern: `/api/v1/{resource}`
- Version prefix is mandatory for every endpoint.
- Breaking changes result in a new version prefix (`/api/v2/`).

### Resource Naming

- Resources are named with plural nouns in lowercase: `/api/v1/companies`, `/api/v1/users`.
- Nested resources use the parent's ID: `/api/v1/companies/{company_id}/users`.

### HTTP Methods

| Operation | Method |
|-----------|--------|
| List | GET |
| Create | POST |
| Read | GET |
| Update | PUT (full) / PATCH (partial) |
| Delete | DELETE |

### Response Envelope

**Success**:

```json
{
  "data": {},
  "message": "Operation completed successfully.",
  "meta": {
    "request_id": "...",
    "timestamp": "..."
  }
}
```

**Paginated Success**:

```json
{
  "data": {
    "items": [],
    "total": 150,
    "page": 1,
    "page_size": 20,
    "pages": 8
  },
  "message": "Items retrieved successfully.",
  "meta": {
    "request_id": "...",
    "timestamp": "..."
  }
}
```

**Error**:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "The requested resource could not be found.",
    "details": {}
  }
}
```

### Documentation

All endpoints MUST be documented with OpenAPI metadata: summary, description, request schema, response schemas, and error responses. Swagger UI and ReDoc are available in development mode only.

---

## Coding Standards

### Backend (Python)

| Standard | Tool | Configuration |
|----------|------|---------------|
| Code Formatting | Black | `pyproject.toml` — line length 88 |
| Linting | Ruff | `pyproject.toml` — PEP 8 and flake8-compatible rules |
| Type Checking | mypy | `pyproject.toml` — strict mode |
| Import Ordering | Ruff (isort-compatible) | `pyproject.toml` |
| Docstrings | Google style | All public classes, functions, and modules |

Rules:

- All functions and methods MUST have type annotations.
- All public classes and functions MUST have docstrings.
- No `# type: ignore` without a justifying comment.
- No unused imports.
- No circular imports.

### Frontend (TypeScript)

| Standard | Tool | Configuration |
|----------|------|---------------|
| Code Formatting | Prettier | `.prettierrc` — single quotes, semicolons, 2-space indent |
| Linting | ESLint | `.eslintrc.json` — Next.js recommended rules with strict additions |
| Type Checking | TypeScript Compiler | `tsconfig.json` — strict mode |

Rules:

- No `any` types without a justifying comment.
- All React components MUST have explicit return type annotations.
- No inline styles; use Tailwind CSS classes exclusively.
- Component files use PascalCase; utility files use camelCase.

---

## Testing Strategy

### Backend Testing

**Unit Tests** (`tests/unit/`):

- Test `BaseRepository` methods using a test database or mock session.
- Test `Settings` class validation with missing and invalid environment variables.
- Test exception handler mapping for each exception type.
- Test structured log output includes all required fields.

**Integration Tests** (`tests/integration/`):

- Test the health check endpoint returns correct status with a live test database.
- Test the health check endpoint returns degraded status when the database is unreachable.
- Test that unhandled exceptions return the standard error response structure.

### Frontend Testing

At this foundational stage, frontend testing infrastructure MUST be set up:

- Testing framework configuration (Jest and React Testing Library) MUST be installed and configured.
- A smoke test verifying the root layout renders without errors MUST be in place.

### Test Infrastructure

- A separate test database configuration MUST be provided via a test-specific `DATABASE_URL`.
- Test database setup and teardown MUST be automated within the test fixture infrastructure.
- All tests MUST pass with zero failures before a pull request may be merged.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: A new developer can set up the complete development environment in under 5 minutes from cloning the repository to having all services operational.
- **SC-002**: The backend health check endpoint responds in under 200 milliseconds under normal operating conditions.
- **SC-003**: All code quality tools (formatting, linting, type checking) pass with zero errors on the initial codebase.
- **SC-004**: All unit and integration tests pass with zero failures.
- **SC-005**: The development environment starts reliably and consistently across any developer machine with Docker installed, with zero "works on my machine" failures.
- **SC-006**: A backend developer can create a new module by extending the base classes with zero boilerplate duplication of infrastructure code.
- **SC-007**: A frontend developer can create a new page using the established layout and component foundation with no custom infrastructure work required.
- **SC-008**: Every unhandled exception produces a structured log entry with all required context fields and a safe, consistent error response to the client.

---

## Acceptance Criteria

### Environment Setup

- [ ] `docker compose up` starts all services (api, web, db) without errors.
- [ ] `GET /api/v1/health` returns HTTP 200 with `status: healthy` and `database: connected`.
- [ ] The Next.js application is accessible in the browser with no console errors.
- [ ] All structured log entries appear in the Docker Compose log output in the correct format.
- [ ] Environment variables are loaded correctly from `.env` file with no hardcoded values in source.

### Backend Foundation

- [ ] `BaseModel` includes `id`, `created_at`, `updated_at` fields.
- [ ] `TenantBaseModel` includes all `BaseModel` fields plus `company_id`, `created_by`, `is_deleted`, `deleted_at`.
- [ ] `BaseRepository` provides `create`, `get_by_id`, `list`, `update`, `soft_delete` methods with `company_id` required on all tenant-scoped operations.
- [ ] `BaseService` is defined and extensible for future modules.
- [ ] `ApplicationException` and all exception subclasses are defined and mapped.
- [ ] The centralized exception handler returns the standard `ErrorResponse` for all exception types.
- [ ] All error responses match the `{error: {code, message, details}}` structure exactly.
- [ ] `Settings` class fails to initialize and logs a descriptive error when any required environment variable is missing.
- [ ] Alembic is configured and the initial baseline migration runs successfully on a fresh database.
- [ ] Auth hook middleware is in place as a documented placeholder.

### Frontend Foundation

- [ ] TypeScript strict mode is configured and enforced; `tsc --noEmit` passes with zero errors.
- [ ] shadcn/ui is initialized and foundational components (Button, Input, Card) are importable and render correctly.
- [ ] The `AppLayout` component renders the application shell with header and sidebar placeholders.
- [ ] The typed API client is defined and directs calls to the URL from `NEXT_PUBLIC_API_URL`.
- [ ] ESLint and Prettier pass with zero errors on all source files.

### Code Quality

- [ ] `black --check .` passes with zero formatting errors on backend code.
- [ ] `ruff check .` passes with zero linting errors on backend code.
- [ ] `mypy .` passes with zero type errors on backend code.
- [ ] `eslint .` passes with zero errors on frontend code.
- [ ] `prettier --check .` passes with zero formatting errors on frontend code.

### Testing

- [ ] All unit tests pass with zero failures.
- [ ] All integration tests pass with zero failures.
- [ ] Frontend testing infrastructure (Jest, React Testing Library) is configured and the smoke test passes.

### Documentation

- [ ] `README.md` at the monorepo root explains setup, available commands, and project structure.
- [ ] `.env.example` files exist at both `backend/` and `frontend/` levels with all variables documented.
- [ ] Every base class and public module has a docstring explaining its purpose and usage.

---

## Assumptions

1. Docker and Docker Compose v2 are available on all developer machines; no native (non-Docker) setup path is required for this Epic.
2. The PostgreSQL version is 16 LTS; this is consistent with the planned Neon PostgreSQL deployment target.
3. Python version is the latest stable LTS release available at implementation time (3.12 or higher).
4. Node.js version is the latest LTS available at implementation time (22 or higher).
5. The Next.js App Router is the selected router pattern (not Pages Router).
6. SQLAlchemy is used in synchronous mode initially for simplicity; async migration is deferred to a future ADR if performance requirements demand it.
7. Better Auth is not configured or wired at implementation level in this Epic; only structural hooks and interface stubs are required.
8. No business tables (companies, users, inventory, etc.) are created in this Epic; the schema is empty beyond Alembic's version tracking table.
9. API documentation (Swagger/ReDoc) is available in development mode only; production configuration disables it.
10. The `SECRET_KEY` is used for general cryptographic operations; its specific usage with Better Auth is deferred to the Authentication Epic.

---

## Constraints

1. No business logic of any kind may be implemented in this Epic.
2. No authentication or authorization implementation may be included; only structural readiness hooks.
3. The technology stack is fixed per the Constitution (§6) and may not be changed without a documented ADR and Constitution amendment.
4. All code must comply with the Constitution's Non-Negotiable Rules (§44).
5. No dependencies may be added without documented justification.
6. The spec, plan, and tasks hierarchy must be followed; no implementation work may begin until the plan and tasks are approved.
7. All multi-tenant isolation patterns must be in place from the start, even though no tenant data exists yet.

---

## Future Expansion Considerations

1. **Authentication Epic**: The auth hook middleware placeholder and `core/auth/interfaces.py` stub provide clean injection points for Better Auth integration without touching existing infrastructure.

2. **Module Development**: The `modules/` directory and the base class design allow any number of future modules to be added without modifying platform code. Each module follows the established vertical slice pattern.

3. **Multi-Tenancy**: The `TenantBaseModel` and `BaseRepository` patterns are designed for multi-tenancy from the start. As soon as the Company Management module is built, real tenant isolation is immediately enforced.

4. **SaaS Readiness**: The configuration-based feature toggle pattern (Constitution §11) is supported by the centralized `Settings` class design; adding feature toggle storage per tenant is a future module concern.

5. **API Evolution**: The `/api/v1/` versioning prefix enables a future `/api/v2/` to coexist without breaking existing consumers.

6. **Observability**: The structured logging infrastructure is designed for future integration with Grafana, Prometheus, Sentry, or Datadog by changing the log output destination via configuration alone.

7. **Async Upgrade Path**: If performance profiling reveals that synchronous SQLAlchemy is a bottleneck, the database layer is isolated enough that migration to `AsyncSession` is a contained change within `core/database/`.

8. **Horizontal Scaling**: The stateless API design (no server-side session state, tenant context via injected credentials) enables horizontal scaling by adding API instances behind a load balancer without architectural changes.

9. **Internationalization**: All timestamps are stored in UTC. No locale-specific formatting exists in business logic. The frontend configuration supports future i18n framework integration without structural changes.

10. **Testing Infrastructure Growth**: The testing setup established in this Epic (unit/integration split, test database fixture, coverage tooling) is extensible to end-to-end testing and performance testing in future Epics.

---

*This specification is the authoritative document for Epic 1 — Foundation Platform.*
*All plans and tasks derived from this specification MUST comply with its requirements and with the DevSphere ERP Constitution (v1.1.0).*
