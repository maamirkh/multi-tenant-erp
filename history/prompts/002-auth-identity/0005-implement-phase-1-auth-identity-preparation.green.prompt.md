---
id: "0005"
title: Implement Phase 1 Auth Identity Preparation
stage: green
date: 2026-07-13
surface: agent
model: claude-sonnet-4-6
feature: 002-auth-identity
branch: 002-auth-identity
user: shehla83
command: /sp.implement
labels: ["phase-1","preparation","dependencies","configuration","exceptions","auth"]
links:
  spec: specs/002-auth-identity/spec.md
  ticket: null
  adr: history/adr/0001-jwt-access-token-and-opaque-refresh-token-session-architecture.md
  pr: null
files:
  - backend/pyproject.toml
  - frontend/package.json
  - frontend/package-lock.json
  - backend/modules/auth/__init__.py
  - backend/modules/auth/models/__init__.py
  - backend/modules/auth/repositories/__init__.py
  - backend/modules/auth/schemas/__init__.py
  - backend/modules/auth/services/__init__.py
  - backend/modules/auth/data/common_passwords.txt
  - frontend/src/contexts/.gitkeep
  - frontend/src/lib/auth/.gitkeep
  - frontend/src/components/auth/.gitkeep
  - frontend/src/lib/api/auth.ts
  - backend/core/config/settings.py
  - backend/core/auth/__init__.py
  - backend/core/auth/exceptions.py
  - backend/main.py
  - .env.example
  - specs/002-auth-identity/tasks.md
tests:
  - none (Phase 1 is preparation only — no business logic implemented)
---

## Prompt

# ============================================================
# ERP SaaS Project
# Epic 2 — Authentication & Identity
# Phase 1 — Preparation & Foundation
# ============================================================

You are implementing ONLY Phase 1 of Epic 2.

Read and follow:
- Constitution
- spec.md
- plan.md
- tasks.md

Follow Spec-Driven Development strictly.

Do NOT skip any Phase 1 task.
Do NOT implement anything from Phase 2 or later.

Implement ONLY tasks T001–T008.

## Response snapshot

Phase 1 (T001–T008) fully implemented. No business logic was introduced.

**T001** — `backend/pyproject.toml`: added `argon2-cffi>=23.1`, `pyjwt[crypto]>=2.8`, `slowapi>=0.1.9` to `[tool.poetry.dependencies]`.

**T002** — `frontend/package.json`: added `@tanstack/react-query^5.0.0`, `react-hook-form^7.0.0`, `zod^3.0.0`; ran `npm install` (3 packages added, 878 audited).

**T003** — Created `backend/modules/auth/` skeleton with `__init__.py` in root, `models/`, `repositories/`, `schemas/`, `services/` subdirectories plus `data/` directory.

**T004** — Created `frontend/src/contexts/`, `frontend/src/lib/auth/`, `frontend/src/components/auth/` directories; created empty `frontend/src/lib/api/auth.ts` placeholder.

**T005** — Extended `backend/core/config/settings.py` with 17 typed auth settings across 5 groups: JWT (8 fields), Argon2id (3), Account Lockout (3), Password Policy (3), Audit Log (1). All use pydantic Field with validation constraints.

**T006** — Created `backend/core/auth/exceptions.py` with 6 exception classes all extending `ApplicationException`: `AuthenticationException` (401), `AccountLockedException` (423), `AccountInactiveException` (403), `TokenExpiredException` (401), `TokenRevokedException` (401), `InvalidTokenException` (400).

**T007** — Created `backend/modules/auth/data/common_passwords.txt` with ~350 common passwords covering numeric sequences, keyboard walks, dictionary words, and common substitutions.

**T008** — Added `_validate_auth_configuration(settings)` function in `backend/main.py`, called as first action in `on_startup()`. Raises `RuntimeError` if `JWT_SECRET_KEY` is missing or < 32 characters.

**.env.example** — Updated with all 17 auth environment variables with descriptive comments, safe placeholder values, and grouped sections.

**tasks.md** — T001–T008 marked `[x]`.

## Outcome

- ✅ Impact: Phase 1 complete — project is prepared for Epic 002 implementation. Auth module skeleton, typed config, exception hierarchy, common-passwords list, and startup validation all in place.
- 🧪 Tests: None — Phase 1 is preparation only; tests are deferred to Phase 13.
- 📁 Files: 18 files created or modified across backend, frontend, config, and docs.
- 🔁 Next prompts: `/sp.implement` Phase 2 (T009–T023) — SQLAlchemy User model and UserCredentials model
- 🧠 Reflection: Strict phase boundary maintained — zero business logic implemented. All settings use pydantic Field constraints to fail-fast on misconfiguration. ARGON2_MEMORY_COST enforces OWASP minimum (19456 KiB) at settings load time.

## Evaluation notes (flywheel)

- Failure modes observed: T002 npm install required `--legacy-peer-deps` due to peer conflict between react-hook-form and React 19; resolved cleanly.
- Graders run and results (PASS/FAIL): Phase boundary check PASS — no models/repos/services/routes created.
- Prompt variant (if applicable): sp.implement with explicit T001–T008 scope restriction
- Next experiment: Verify `python -c "from core.config.settings import get_settings; print(get_settings().JWT_SECRET_KEY)"` raises ValidationError without .env to confirm required field enforcement.
