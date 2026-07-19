# Research: Foundation Platform (Phase 0 Output)

**Branch**: `001-foundation-platform`
**Date**: 2026-07-11

All technology decisions for this Epic are pre-determined by the approved Constitution (v1.1.0). This research document confirms the selected approaches, documents the rationale, and records alternatives considered.

---

## Decision 1: Python Backend Framework

**Decision**: FastAPI
**Rationale**: Mandated by Constitution §6.2. FastAPI provides automatic OpenAPI documentation, Pydantic v2 integration for schema validation, async support, dependency injection, and a high-quality ecosystem for Python APIs.
**Alternatives Considered**: Django REST Framework (too heavyweight for this use case; ORM coupling reduces flexibility); Flask (lacks built-in validation, dependency injection, and async); Litestar (newer, smaller community).

---

## Decision 2: Python Version

**Decision**: Python 3.12 (latest stable LTS at implementation time)
**Rationale**: 3.12 provides `TypeVar` improvements relevant to `BaseRepository` generic typing, performance improvements, and is the latest LTS with long support window. Pydantic v2 and SQLAlchemy 2.x both support 3.12 fully.
**Alternatives Considered**: 3.11 (still supported but 3.12 is preferred for new projects); 3.13 (not yet LTS at time of writing).

---

## Decision 3: ORM

**Decision**: SQLAlchemy 2.x (synchronous)
**Rationale**: Mandated by Constitution §6.2. SQLAlchemy 2.x with the new declarative syntax provides strong typing support, Alembic integration, and the most mature Python ORM ecosystem. Synchronous mode is chosen for initial simplicity per Spec Assumption 6.
**Alternatives Considered**: SQLAlchemy Async (deferred to future ADR; see plan.md risk analysis); Tortoise ORM (async-first but smaller community); Peewee (simpler but lacks generic typing support needed for BaseRepository).

---

## Decision 4: Schema Validation

**Decision**: Pydantic v2
**Rationale**: Mandated by Constitution §6.2. Pydantic v2 provides a significant performance improvement over v1, stronger TypeScript-like type safety, and is the default for FastAPI. Breaking changes from v1 are accounted for in the implementation plan.
**Alternatives Considered**: Marshmallow (older; less FastAPI-native); dataclasses (insufficient validation).

---

## Decision 5: Database Migration Tool

**Decision**: Alembic
**Rationale**: Mandated by Constitution §6.2. Alembic is the standard migration tool for SQLAlchemy projects, supports autogenerate, and provides both upgrade and downgrade operations.
**Alternatives Considered**: Flyway (Java-native; not Python-idiomatic); manual SQL scripts (no autogenerate, no version tracking).

---

## Decision 6: Frontend Framework

**Decision**: Next.js (App Router, latest stable)
**Rationale**: Mandated by Constitution §6.1. App Router is the current recommended pattern for Next.js and supports Server Components, layouts, and TypeScript natively.
**Alternatives Considered**: Pages Router (deprecated in favor of App Router); Vite + React (no SSR; additional configuration); Remix (smaller community in enterprise context).

---

## Decision 7: TypeScript Configuration

**Decision**: Strict mode (`"strict": true`)
**Rationale**: Mandated by Constitution §6.1 and Spec FR-049. Strict mode enables `strictNullChecks`, `noImplicitAny`, and all other strict checks. This prevents entire classes of runtime errors.
**Alternatives Considered**: Lenient mode (reduces friction but allows type errors to accumulate over time; rejected per Constitution's quality-first engineering philosophy).

---

## Decision 8: CSS Framework

**Decision**: Tailwind CSS with shadcn/ui
**Rationale**: Mandated by Constitution §6.1. Tailwind provides utility-first styling enabling rapid, consistent design. shadcn/ui provides accessible, customizable components built on Radix UI.
**Alternatives Considered**: Material UI (more opinionated; harder to customize for ERP aesthetics); Chakra UI (smaller ecosystem); styled-components (CSS-in-JS has performance tradeoffs).

---

## Decision 9: Docker Strategy

**Decision**: Docker Compose v2 with separate development and production Dockerfiles
**Rationale**: Mandated by Constitution §27. Docker Compose enables single-command local environment startup. Separate dev/prod Dockerfiles allow hot reload in development without compromising production image security and size.
**Alternatives Considered**: Devcontainers (additional tooling; inconsistent support across IDEs); native (non-Docker) setup (violates "works on my machine" principle).

---

## Decision 10: Python Code Quality Tools

**Decision**: Black (formatter) + Ruff (linter, includes isort) + mypy (type checker)
**Rationale**: Mandated by Constitution §24. Black is the unambiguous Python formatter. Ruff replaces flake8, isort, and several other linting tools with a single, fast Rust-based tool. mypy in strict mode enforces complete type coverage.
**Alternatives Considered**: autopep8 (less opinionated than Black); pylint (slower, more verbose than Ruff); Pyright (excellent but mypy is more commonly established in Python projects).

---

## Decision 11: Python Package Management

**Decision**: Poetry with `pyproject.toml`
**Rationale**: Poetry provides deterministic dependency resolution, lock file management, and virtual environment management in a single tool. `pyproject.toml` is the modern Python project metadata standard (PEP 517/518/621).
**Alternatives Considered**: pip + requirements.txt (no lock file determinism; no virtual environment management); pipenv (slower resolver; lower adoption compared to Poetry).

---

## Decision 12: Frontend Package Management

**Decision**: npm with `package-lock.json`
**Rationale**: npm is the default for Next.js projects and is universally available in Node.js installations. The lock file ensures reproducible installs.
**Alternatives Considered**: pnpm (faster, more efficient disk usage; valid alternative; switch via ADR if needed); Yarn (valid alternative; npm is default for Next.js CLI).

---

## Decision 13: Backend Testing Framework

**Decision**: pytest + httpx (for ASGI testing)
**Rationale**: pytest is the standard Python testing framework with the richest ecosystem. httpx provides an `AsyncClient` that works natively with FastAPI's ASGI interface.
**Alternatives Considered**: unittest (pytest is strictly superior for modern Python); requests (not async-compatible with FastAPI's TestClient).

---

## Decision 14: Frontend Testing Framework

**Decision**: Jest + React Testing Library
**Rationale**: Jest is the standard JavaScript testing framework for React projects. React Testing Library encourages testing user behavior rather than implementation details.
**Alternatives Considered**: Vitest (faster but less mature for Next.js projects); Cypress (end-to-end only; not suitable for unit/component tests).

---

## Decision 15: BaseRepository Generics Pattern

**Decision**: `Generic[ModelType]` with TypeVar bound to `TenantBaseModel`
**Rationale**: Python's `typing.Generic` allows `BaseRepository` to be typed per model: `UserRepository(BaseRepository[User])`. This enables full type checking of repository return values in concrete repositories.
**Alternatives Considered**: Untyped base class (eliminates type checking; rejected); Class-level `model_class: Type[ModelType]` attribute (less elegant; more boilerplate in concrete repositories).

---

## Decision 16: Request ID Strategy

**Decision**: `contextvars.ContextVar` for request-scoped request_id
**Rationale**: `ContextVar` is the correct mechanism for request-scoped data in Python async/sync contexts. It avoids threading issues and is accessible throughout the call stack without explicit parameter passing.
**Alternatives Considered**: Thread-local storage (not safe in async contexts); explicit parameter passing (too much boilerplate in logging calls).

---

## Summary: No Unresolved NEEDS CLARIFICATION Items

All technology decisions are pre-determined by the Constitution and Specification. No external research was required to resolve open questions. This research document serves as the rationale record for all implementation decisions.
