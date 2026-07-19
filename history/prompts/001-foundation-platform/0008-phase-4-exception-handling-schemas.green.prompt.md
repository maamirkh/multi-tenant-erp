---
id: "0008"
title: Phase 4 Exception Handling and Common Schemas
stage: green
date: 2026-07-11
surface: agent
model: claude-sonnet-4-6
feature: 001-foundation-platform
branch: 001-foundation-platform
user: shehla83
command: /sp.implement
labels: ["phase-4", "exceptions", "schemas", "error-handling", "pydantic", "generic", "response-envelope"]
links:
  spec: specs/001-foundation-platform/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/core/exceptions/__init__.py
  - backend/core/exceptions/base.py
  - backend/core/exceptions/handler.py
  - backend/core/schemas/__init__.py
  - backend/core/schemas/response.py
  - backend/core/schemas/pagination.py
  - backend/main.py
  - backend/pyproject.toml
  - specs/001-foundation-platform/tasks.md
tests:
  - black --check . → PASS (24 files)
  - ruff check . → PASS (24 files)
  - mypy . → PASS (24 files, 0 errors)
  - T063: NotFoundException attributes correct, no FastAPI imports → PASS
  - T064: All 6 exception subclasses have correct code + http_status → PASS
  - T065: StandardResponse[str] serializes to {data, message, meta} → PASS
  - T066: ErrorResponse serializes to {error: {code, message, details}} → PASS
---

## Prompt

Implement ONLY Phase 4 (Exception Handling & Common Schemas) from the approved tasks.md.
[Full prompt per /sp.implement invocation — see command args above]

## Response snapshot

Implemented Phase 4 (T056–T066): Exception Handling and Common Schemas.

**Files created (6):**

1. `core/exceptions/__init__.py` — re-exports all 7 exception classes
2. `core/exceptions/base.py` — `ApplicationException(Exception)` hierarchy:
   - Base: `message`, `code`, `details: dict[str, object]`, `http_status`
   - `ValidationException` (VALIDATION_ERROR, 422)
   - `NotFoundException` (NOT_FOUND, 404)
   - `ConflictException` (CONFLICT, 409)
   - `UnauthorizedException` (UNAUTHORIZED, 401)
   - `ForbiddenException` (FORBIDDEN, 403)
   - `InfrastructureException` (INTERNAL_ERROR, 500)
   - Zero FastAPI/HTTP imports
3. `core/exceptions/handler.py` — 3 async FastAPI exception handlers:
   - `application_exception_handler`: extracts code/message/details, logs WARNING (4xx) or ERROR (5xx), returns JSONResponse with ErrorResponse body + X-Request-ID header
   - `validation_exception_handler`: normalises Pydantic RequestValidationError to field-level dict in details
   - `unhandled_exception_handler`: logs full traceback at ERROR, returns generic 500 (includes traceback hint only in ENVIRONMENT=development)
4. `core/schemas/__init__.py` — re-exports all schemas
5. `core/schemas/response.py` — `ResponseMeta`, `StandardResponse[T]`, `ErrorDetail`, `ErrorResponse`
6. `core/schemas/pagination.py` — `PaginatedData[T]`, `PaginatedResponse[T]`, `PaginationParams` with `offset` property

**Files modified (2):**

- `main.py` — registered 3 exception handlers in create_app()
- `pyproject.toml` — added ruff ignore: N818 (spec-mandated Exception suffix names), UP046 (Generic[T] pattern stable with Pydantic v2)

**Architecture decisions:**
- Exception names use `Exception` suffix (not `Error`) per spec mandate; N818 suppressed globally with justification comment
- `Generic[T]` pattern with `BaseModel` used over PEP 695 `class Foo[T]` syntax — UP046 suppressed; PEP 695 with Pydantic v2 is not yet reliably stable
- `type: ignore[arg-type]` applied only to `ApplicationException` and `RequestValidationError` handlers (contravariance); `Exception` handler is correctly typed
- `unhandled_exception_handler` reads `ENVIRONMENT` from `request.app.state.settings` via safe `getattr` chain — never raises itself

## Outcome

- ✅ Impact: Phase 4 complete — consistent error and response contract established for the entire platform.
- 🧪 Tests: 7 validation checks PASS (T063–T066 + 3 bonus schema checks).
- 📁 Files: 6 created, 2 modified (main.py, pyproject.toml), 1 updated (tasks.md).
- 🔁 Next prompts: Implement Phase 5 (Base Repository and Service Patterns) after approval.
- 🧠 Reflection: Placement of `# type: ignore` matters — must be on the line mypy reports the error, not the opening `(` of a multi-line call.

## Evaluation notes (flywheel)

- Failure modes observed: N818/UP046 ruff rules; type: ignore on wrong line; Exception handler doesn't need ignore (it IS Exception type).
- Graders run and results (PASS/FAIL): black PASS, ruff PASS, mypy PASS, T063–T066 all PASS.
- Prompt variant (if applicable): /sp.implement Phase 4.
- Next experiment (smallest change to try): Document N818/UP046 ignores in a single `[tool.ruff.lint.per-file-ignores]` section for per-file targeting.
