---
id: "0006"
title: Implement Phase 2 Auth Database Models
stage: green
date: 2026-07-13
surface: agent
model: claude-sonnet-4-6
feature: 002-auth-identity
branch: 002-auth-identity
user: shehla83
command: /sp.implement
labels: ["phase-2","database-models","sqlalchemy","orm","auth"]
links:
  spec: specs/002-auth-identity/spec.md
  ticket: null
  adr: history/adr/0002-argon2id-password-hashing-with-isolated-credential-storage.md
  pr: null
files:
  - backend/modules/auth/models/enums.py
  - backend/modules/auth/models/user.py
  - backend/modules/auth/models/user_credential.py
  - backend/modules/auth/models/session.py
  - backend/modules/auth/models/refresh_token.py
  - backend/modules/auth/models/password_reset_token.py
  - backend/modules/auth/models/email_verification_token.py
  - backend/modules/auth/models/audit_log.py
  - backend/modules/auth/models/__init__.py
  - backend/migrations/env.py
  - specs/002-auth-identity/tasks.md
tests:
  - Phase 2 checkpoint: python3 -c "from modules.auth.models import User, UserCredentials, Session, RefreshToken, PasswordResetToken, EmailVerificationToken, AuditLog" → PASS (7 tables registered)
---

## Prompt

# ============================================================
# ERP SaaS Project
# Epic 2 — Authentication & Identity
# Phase 2 — Database Models
# ============================================================

You are implementing ONLY Phase 2 of Epic 2.

Phase 1 has already been completed.

Implement ONLY tasks T009–T017: all Authentication ORM models.

No migrations. No repositories. No business logic.

## Response snapshot

All 9 tasks (T009–T017) implemented. Phase 2 checkpoint passed: 7 tables registered in Base.metadata.

**T009** — `enums.py`: `AccountStatus` (ACTIVE/INACTIVE/LOCKED/DELETED) and `AuditEventType` (9 values: LOGIN_SUCCESS through EMAIL_VERIFIED) as `str, enum.Enum` classes.

**T010** — `user.py`: `User` extends `BaseModel`. Columns: email (String(255), unique), display_name, account_status (PgEnum AccountStatus, default ACTIVE), is_email_verified (Boolean, default false), failed_login_count (Integer, default 0), locked_until (DateTime nullable), company_id (UUID nullable — FK placeholder for Epic 003). Indexes on email (unique), account_status, company_id. Relationships to all 5 child tables.

**T011** — `user_credential.py`: `UserCredentials` extends `BaseModel`. Columns: user_id (UUID FK→users.id CASCADE, unique), password_hash (Text), password_history (JSONB, default []), last_changed_at (DateTime). Unique index on user_id enforces 1:1.

**T012** — `session.py`: `Session` extends `BaseModel`. Columns: user_id (UUID FK→users.id CASCADE), is_revoked (Boolean, default false), revoked_at (DateTime nullable), ip_address (String(45)), user_agent (Text), device_info (JSONB). Indexes on user_id and is_revoked.

**T013** — `refresh_token.py`: `RefreshToken` extends `BaseModel`. Columns: user_id (UUID FK→users.id CASCADE), session_id (UUID FK→sessions.id CASCADE), token_hash (String(64), unique), expires_at (DateTime), is_revoked (Boolean), revoked_at (DateTime nullable), remember_me (Boolean), ip_address, user_agent. Indexes on token_hash (unique), user_id, session_id, expires_at.

**T014** — `password_reset_token.py`: `PasswordResetToken` extends `BaseModel`. Columns: user_id (UUID FK→users.id CASCADE), token_hash (String(64), unique), expires_at (DateTime), is_consumed (Boolean), consumed_at (DateTime nullable), ip_address.

**T015** — `email_verification_token.py`: `EmailVerificationToken` extends `BaseModel`. Columns: user_id (UUID FK→users.id CASCADE), token_hash (String(64), unique), expires_at (DateTime), is_consumed (Boolean), consumed_at (DateTime nullable).

**T016** — `audit_log.py`: `AuditLog` extends `Base` directly (NOT `BaseModel`) to omit `updated_at`. Columns: id (UUID, server gen), created_at (DateTime), event_type (PgEnum AuditEventType), user_id (UUID nullable, NO FK constraint — forensic integrity), outcome (String(16)), reason (String(255) nullable), ip_address, user_agent, request_id, metadata_ (JSONB, mapped to column name "metadata").

**T017** — `models/__init__.py`: exports all 7 models + 2 enums; `import modules.auth.models` in `migrations/env.py` for Alembic autodiscovery.

## Outcome

- ✅ Impact: All 7 auth ORM tables defined. Alembic autodiscovery updated. Phase 2 checkpoint PASS.
- 🧪 Tests: `python3 -c "from modules.auth.models import ..."` → Tables registered: ['audit_logs', 'email_verification_tokens', 'password_reset_tokens', 'refresh_tokens', 'sessions', 'users', 'user_credentials'] → Model count: 7 → PASS
- 📁 Files: 9 new files created + 2 modified (env.py, tasks.md)
- 🔁 Next prompts: `/sp.implement` Phase 3 (T018–T023) — Alembic migration
- 🧠 Reflection: AuditLog correctly inherits from `Base` not `BaseModel` to exclude `updated_at` (append-only table). Circular imports avoided via `TYPE_CHECKING` guards on all back-references. `metadata_` attribute name used in Python to avoid shadowing SQLAlchemy's `metadata`, with `mapped_column("metadata", ...)` preserving DB column name. company_id is nullable UUID (no FK) to allow Epic 003 to add the constraint later without breaking current schema.

## Evaluation notes (flywheel)

- Failure modes observed: Python interpreter not in PATH; resolved by using full path to Poetry virtualenv python3.12.
- Graders run and results (PASS/FAIL): Phase 2 checkpoint PASS — 7 tables registered. No circular import errors. No business logic in models.
- Prompt variant (if applicable): sp.implement with T009–T017 scope restriction
- Next experiment: Run `alembic revision --autogenerate -m "epic_002_auth_models"` after database is running to verify all 7 tables appear in the generated migration diff.
