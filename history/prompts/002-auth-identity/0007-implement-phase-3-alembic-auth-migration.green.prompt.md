---
id: "0007"
title: Implement Phase 3 Alembic Auth Migration
stage: green
date: 2026-07-13
surface: agent
model: claude-sonnet-4-6
feature: 002-auth-identity
branch: 002-auth-identity
user: shehla83
command: /sp.implement
labels: ["phase-3","alembic","migration","database","postgresql"]
links:
  spec: specs/002-auth-identity/spec.md
  ticket: null
  adr: history/adr/0001-jwt-access-token-and-opaque-refresh-token-session-architecture.md
  pr: null
files:
  - backend/migrations/versions/002_auth_identity.py
  - specs/002-auth-identity/tasks.md
tests:
  - ast.parse(migration file) → Syntax PASS
  - py_compile 002_auth_identity.py → PASS
  - Module import: revision=002, down_revision=001, upgrade+downgrade callable → PASS
  - T021/T022 (alembic upgrade/downgrade): BLOCKED — Docker Desktop not running
---

## Prompt

# ============================================================
# ERP SaaS Project
# Epic 2 — Authentication & Identity
# Phase 3 — Alembic Migration
# ============================================================

Implement ONLY Phase 3: T018, T019, T020, T021, T022.

Create backend/migrations/versions/002_auth_identity.py with upgrade() and downgrade().

No repositories, services, business logic, or API endpoints.

## Response snapshot

**T018** — `002_auth_identity.py` created. `upgrade()` creates all 7 tables in FK-dependency order: users → user_credentials → sessions → refresh_tokens → password_reset_tokens → email_verification_tokens → audit_logs. Two PostgreSQL ENUM types created first (accountstatus, auditeventtype) using `postgresql.ENUM(..., create_type=False)` + `.create(op.get_bind(), checkfirst=True)`.

**T019** — All required indexes added in upgrade():
- users: ix_users_email (unique), ix_users_account_status, ix_users_company_id
- user_credentials: ix_user_credentials_user_id (unique)
- sessions: ix_sessions_user_id, ix_sessions_is_revoked
- refresh_tokens: ix_refresh_tokens_token_hash (unique), ix_refresh_tokens_user_id, ix_refresh_tokens_session_id, ix_refresh_tokens_expires_at
- password_reset_tokens: ix_password_reset_tokens_token_hash (unique), ix_password_reset_tokens_user_id, ix_password_reset_tokens_expires_at
- email_verification_tokens: ix_email_verification_tokens_token_hash (unique), ix_email_verification_tokens_user_id, ix_email_verification_tokens_expires_at
- audit_logs: ix_audit_logs_event_type, ix_audit_logs_user_id, ix_audit_logs_created_at, ix_audit_logs_outcome

**T020** — `downgrade()` drops tables + indexes in strict reverse order (audit_logs → email_verification_tokens → password_reset_tokens → refresh_tokens → sessions → user_credentials → users), then drops both ENUM types.

**T021/T022** — Cannot execute: Docker Desktop not running in this WSL2 environment. Static checks passed (syntax, py_compile, module import). Manual verification required: start Docker, run `docker compose up -d db`, then `alembic upgrade head` and `alembic downgrade -1`.

**Key design decisions:**
- audit_logs has NO updated_at (append-only), NO user_id FK constraint (forensic integrity)
- Constraint naming: pk_<table>, uq_<table>_<col>, fk_<source>_<target>, ix_<table>_<col>
- All FKs use ON DELETE CASCADE except audit_logs.user_id (intentionally unconstrained)
- ENUM types use `create_type=False` + explicit `.create()` for full lifecycle control

## Outcome

- ✅ Impact: Migration file created with all 7 tables, 18 indexes, 5 FKs, 2 PG ENUMs. Static validation passed.
- 🧪 Tests: Syntax PASS, py_compile PASS, module import PASS. Live DB verification (T021/T022) blocked by Docker not running.
- 📁 Files: 1 created (002_auth_identity.py) + tasks.md updated
- 🔁 Next prompts: Start Docker Desktop → run `alembic upgrade head` to complete T021/T022, then `/sp.implement` Phase 4 (Repositories)
- 🧠 Reflection: Used `postgresql.ENUM(create_type=False)` pattern with explicit `.create(checkfirst=True)` to avoid double-create errors on repeated upgrades. audit_logs inherits from Base directly (no updated_at) — migration matches this exactly. Constraint names follow consistent pk_/uq_/fk_/ix_ convention throughout.

## Evaluation notes (flywheel)

- Failure modes observed: Docker Desktop not available in WSL2 without explicit integration; T021/T022 verification deferred.
- Graders run and results (PASS/FAIL): Syntax PASS, py_compile PASS, import/revision metadata PASS. Live DB: DEFERRED.
- Prompt variant (if applicable): sp.implement Phase 3 with explicit T018-T022 scope
- Next experiment: After Docker is running, execute `alembic upgrade head` then `SELECT table_name FROM information_schema.tables WHERE table_schema='public'` to confirm exactly 7 tables. Then downgrade to 001 and confirm clean state.
