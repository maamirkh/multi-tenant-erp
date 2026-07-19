# Tasks: Authentication & Identity (Epic 002)

**Epic**: `002-auth-identity`
**Branch**: `002-auth-identity`
**Input**: `specs/002-auth-identity/spec.md` + `specs/002-auth-identity/plan.md`
**Status**: Ready for Implementation

**Traceability**:
- spec.md §7 (FR-001–FR-075), §8 (NFR-001–NFR-029), §11 (US-01–US-10), §12–§13
- plan.md §1–§17

**User Stories mapped in this file**:

| Label | Story | Priority |
|-------|-------|---------|
| [US1] | US-01 — User Login | P1 |
| [US2] | US-02 — User Logout | P1 |
| [US3] | US-03 — Automatic Token Refresh | P1 |
| [US4] | US-04 — Forgot Password | P2 |
| [US5] | US-05 — Reset Password | P2 |
| [US6] | US-06 — Current User (`GET /me`) | P1 |
| [US7] | US-07 — Remember Me | P2 |
| [US8] | US-08 — Change Password | P2 |
| [US9] | US-09 — Session Expiration Handling | P1 |
| [US10] | US-10 — Session Revocation | P2 |

## Format: `- [ ] [TaskID] [P?] [Story?] Description — file path`

- **[P]** = Can execute in parallel (no dependency on incomplete peer task)
- **[USn]** = User story this task belongs to
- All paths are relative to repository root

---

## Phase 1: Project Preparation

**Purpose**: Add new dependencies, extend configuration, scaffold module directories.
**Spec ref**: plan.md §1 (Technical Context), plan.md §11 Phase 1
**Prerequisite**: Epic 001 foundation complete

- [x] T001 Add `argon2-cffi>=23.1`, `PyJWT>=2.8`, `slowapi>=0.1.9` to `backend/pyproject.toml` (or `requirements.txt`) and rebuild Docker image
- [x] T002 [P] Add `@tanstack/react-query>=5`, `react-hook-form>=7`, `zod>=3` to `frontend/package.json` and run `npm install`
- [x] T003 [P] Create backend auth module directory skeleton: `backend/modules/auth/__init__.py`, `backend/modules/auth/models/__init__.py`, `backend/modules/auth/repositories/__init__.py`, `backend/modules/auth/schemas/__init__.py`, `backend/modules/auth/services/__init__.py`
- [x] T004 [P] Create frontend auth directory skeleton: `frontend/src/contexts/`, `frontend/src/hooks/`, `frontend/src/lib/auth/`, `frontend/src/lib/api/auth.ts` (empty), `frontend/src/components/auth/`
- [x] T005 Extend `backend/core/config/settings.py` — add all auth settings: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`, `JWT_REMEMBER_ME_EXPIRE_DAYS`, `JWT_ISSUER`, `JWT_AUDIENCE`, `ARGON2_TIME_COST`, `ARGON2_MEMORY_COST`, `ARGON2_PARALLELISM`, `AUTH_LOCKOUT_THRESHOLD`, `AUTH_LOCKOUT_WINDOW_MINUTES`, `AUTH_LOCKOUT_DURATION_MINUTES`, `PASSWORD_MIN_LENGTH`, `PASSWORD_MAX_LENGTH`, `PASSWORD_HISTORY_COUNT`, `AUDIT_LOG_RETENTION_DAYS`
- [x] T006 [P] Create `backend/core/auth/exceptions.py` — define `AuthenticationException` (401), `AccountLockedException` (423), `AccountInactiveException` (403), `TokenExpiredException` (401), `TokenRevokedException` (401), `InvalidTokenException` (400) — all extend `ApplicationException` from `core/exceptions/base.py`
- [x] T007 [P] Add common-passwords blocklist file at `backend/modules/auth/data/common_passwords.txt` (minimum top-10,000 list per spec.md §12.1)
- [x] T008 Add startup validation in `backend/main.py` — assert `settings.JWT_SECRET_KEY` is non-empty and at least 32 characters; raise `RuntimeError` on startup if not

**Phase 1 Checkpoint**: `docker-compose build` succeeds; `python -c "from core.config.settings import get_settings; s=get_settings(); print(s.JWT_SECRET_KEY)"` prints value from `.env`; `npm install` succeeds in frontend.

---

## Phase 2: Database Models

**Purpose**: Create all 7 ORM models for authentication entities.
**Spec ref**: spec.md §10 (Identity Model), plan.md §6 (Database Strategy)
**Depends on**: Phase 1

- [x] T009 Create `backend/modules/auth/models/enums.py` — define `AccountStatus` Python enum (`ACTIVE`, `INACTIVE`, `LOCKED`, `DELETED`) and `AuditEventType` enum (`LOGIN_SUCCESS`, `LOGIN_FAILURE`, `LOGOUT`, `TOKEN_REFRESHED`, `ACCOUNT_LOCKED`, `PASSWORD_CHANGED`, `PASSWORD_RESET_REQUESTED`, `PASSWORD_RESET_COMPLETED`, `EMAIL_VERIFIED`)
- [x] T010 [P] Create `backend/modules/auth/models/user.py` — `User` ORM model extending `BaseModel`; columns: `email` (String, unique, not null), `display_name` (String, not null), `account_status` (Enum AccountStatus, default ACTIVE), `is_email_verified` (Boolean, default False), `failed_login_count` (Integer, default 0), `locked_until` (DateTime nullable), `company_id` (UUID nullable FK placeholder for Epic 003); table name `users`
- [x] T011 Create `backend/modules/auth/models/user_credential.py` — `UserCredentials` ORM model extending `BaseModel`; columns: `user_id` (UUID FK → users.id, unique, not null), `password_hash` (Text, not null), `password_history` (JSONB, default `[]`), `last_changed_at` (DateTime, not null); table name `user_credentials`
- [x] T012 Create `backend/modules/auth/models/session.py` — `Session` ORM model extending `BaseModel`; columns: `user_id` (UUID FK → users.id, not null), `is_revoked` (Boolean, default False), `revoked_at` (DateTime nullable), `ip_address` (String nullable), `user_agent` (Text nullable), `device_info` (JSONB nullable); table name `sessions`
- [x] T013 Create `backend/modules/auth/models/refresh_token.py` — `RefreshToken` ORM model extending `BaseModel`; columns: `user_id` (UUID FK → users.id, not null), `session_id` (UUID FK → sessions.id, not null), `token_hash` (String(64), unique, not null), `expires_at` (DateTime, not null), `is_revoked` (Boolean, default False), `revoked_at` (DateTime nullable), `remember_me` (Boolean, default False), `ip_address` (String nullable), `user_agent` (Text nullable); table name `refresh_tokens`
- [x] T014 Create `backend/modules/auth/models/password_reset_token.py` — `PasswordResetToken` ORM model extending `BaseModel`; columns: `user_id` (UUID FK → users.id, not null), `token_hash` (String(64), unique, not null), `expires_at` (DateTime, not null), `is_consumed` (Boolean, default False), `consumed_at` (DateTime nullable), `ip_address` (String nullable); table name `password_reset_tokens`
- [x] T015 [P] Create `backend/modules/auth/models/email_verification_token.py` — `EmailVerificationToken` ORM model extending `BaseModel`; columns: `user_id` (UUID FK → users.id, not null), `token_hash` (String(64), unique, not null), `expires_at` (DateTime, not null), `is_consumed` (Boolean, default False), `consumed_at` (DateTime nullable); table name `email_verification_tokens`
- [x] T016 Create `backend/modules/auth/models/audit_log.py` — `AuditLog` ORM model extending `BaseModel` (no `updated_at` — append-only); columns: `event_type` (Enum AuditEventType, not null), `user_id` (UUID nullable — no FK constraint, stores value only), `outcome` (String, not null — `SUCCESS`/`FAILURE`), `reason` (String nullable), `ip_address` (String nullable), `user_agent` (Text nullable), `request_id` (String nullable), `metadata` (JSONB nullable); table name `audit_logs`; `__init__` must not include `updated_at` mapping
- [x] T017 Update `backend/modules/auth/models/__init__.py` — export all 7 models and both enums so Alembic autodiscovery imports them

**Phase 2 Checkpoint**: `python -c "from modules.auth.models import User, UserCredentials, Session, RefreshToken, PasswordResetToken, EmailVerificationToken, AuditLog"` executes without error. SQLAlchemy metadata inspection confirms 7 mapped classes.

---

## Phase 3: Alembic Migration

**Purpose**: Create and verify the database migration for all auth tables.
**Spec ref**: plan.md §6 (Migration Strategy), plan.md §14 (Alembic Migration Execution)
**Depends on**: Phase 2

- [x] T018 Create `backend/migrations/versions/002_auth_identity.py` — Alembic migration with `upgrade()` creating tables in dependency order: `users` → `user_credentials` → `sessions` → `refresh_tokens` → `password_reset_tokens` → `email_verification_tokens` → `audit_logs`; include all columns, unique constraints, FK constraints, and indexes from plan.md §6 Indexing Strategy
- [x] T019 Add indexes in `upgrade()`: `UNIQUE (users.email)`, `(users.account_status, users.locked_until)`, `UNIQUE (refresh_tokens.token_hash)`, `(refresh_tokens.user_id, refresh_tokens.is_revoked)`, `(refresh_tokens.expires_at)`, `(sessions.user_id, sessions.is_revoked)`, `UNIQUE (password_reset_tokens.token_hash)`, `(password_reset_tokens.user_id, password_reset_tokens.is_consumed, password_reset_tokens.expires_at)`, `UNIQUE (email_verification_tokens.token_hash)`, `(audit_logs.user_id, audit_logs.created_at DESC)`, `(audit_logs.event_type, audit_logs.created_at DESC)`
- [x] T020 Add `downgrade()` function dropping tables in reverse dependency order (audit_logs → email_verification_tokens → password_reset_tokens → refresh_tokens → sessions → user_credentials → users)
- [x] T021 Run `alembic upgrade head` in Docker Compose dev environment; verify all 7 tables are created in PostgreSQL with correct columns and indexes
- [x] T022 Run `alembic downgrade base` from the `002` state; verify all 7 tables are dropped without error; run `alembic upgrade head` again to confirm idempotency

**Phase 3 Checkpoint**: `alembic current` shows `002_auth_identity` as head; `\dt` in psql shows all 7 auth tables; `\di` confirms all indexes created; downgrade and re-upgrade completes without error.

---

## Phase 4: Repositories

**Purpose**: Implement the data access layer for all auth entities.
**Spec ref**: plan.md §5 (Module Breakdown — Repositories)
**Depends on**: Phase 3

- [x] T023 [P] Create `backend/modules/auth/repositories/user_repository.py` — `UserRepository` extending `BaseRepository[User]`; implement: `find_by_email(email: str) -> User | None`, `update_failed_login_count(user_id, count) -> None`, `lock_account(user_id, locked_until: datetime) -> None`, `unlock_account(user_id) -> None`, `update_account_status(user_id, status: AccountStatus) -> None`; email must be lowercased before lookup
- [x] T023A Create `backend/scripts/create_admin.py` — create an initial administrator account from environment variables (`ADMIN_NAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`); hash password using `PasswordService`; script must be idempotent (running multiple times must not create duplicate admin users)
- [x] T024 Create `backend/modules/auth/repositories/user_credential_repository.py` — `UserCredentialRepository`; implement: `get_by_user_id(user_id: UUID) -> UserCredentials`, `update_password_hash(user_id, new_hash: str, history: list[str], changed_at: datetime) -> None`
- [x] T025 Create `backend/modules/auth/repositories/session_repository.py` — `SessionRepository`; implement: `create_session(user_id, ip_address, user_agent) -> Session`, `get_active_sessions_by_user(user_id) -> list[Session]`, `revoke_session(session_id) -> None`, `revoke_all_by_user(user_id) -> None`
- [x] T026 Create `backend/modules/auth/repositories/refresh_token_repository.py` — `RefreshTokenRepository`; implement: `create(user_id, session_id, token_hash, expires_at, remember_me, ip_address, user_agent) -> RefreshToken`, `find_by_token_hash(token_hash: str) -> RefreshToken | None`, `revoke(token_id: UUID) -> None`, `revoke_all_by_user(user_id: UUID) -> int`, `delete_expired() -> int`, `count_active_by_user(user_id) -> int`; rotation must use a single atomic transaction (SELECT FOR UPDATE → revoke old → INSERT new)
- [x] T027 Create `backend/modules/auth/repositories/password_reset_token_repository.py` — `PasswordResetTokenRepository`; implement: `create(user_id, token_hash, expires_at, ip_address) -> PasswordResetToken`, `find_active_by_token_hash(token_hash: str) -> PasswordResetToken | None`, `mark_consumed(token_id: UUID) -> None`, `invalidate_active_by_user(user_id: UUID) -> None`, `delete_expired() -> int`
- [x] T027A Create `backend/core/auth/device_parser.py` — parse User-Agent into browser, operating system, and device information for session tracking and audit purposes
- [x] T028 [P] Create `backend/modules/auth/repositories/email_verification_token_repository.py` — `EmailVerificationTokenRepository`; implement: `create(user_id, token_hash, expires_at) -> EmailVerificationToken`, `find_active_by_token_hash(token_hash: str) -> EmailVerificationToken | None`, `mark_consumed(token_id: UUID) -> None`, `delete_expired() -> int`
- [x] T029 Create `backend/modules/auth/repositories/audit_log_repository.py` — `AuditLogRepository`; implement: `create(event_type, outcome, user_id, ip_address, user_agent, request_id, reason, metadata) -> AuditLog`; no `update` or `delete` methods; `list_by_user_id(user_id, from_dt, to_dt, limit) -> list[AuditLog]`
- [x] T030 Update `backend/modules/auth/repositories/__init__.py` — export all 7 repository classes
- [x] T030A Create `backend/scripts/cleanup_auth.py` — remove expired refresh tokens, expired password reset tokens, expired email verification tokens, expired sessions, and audit logs older than configured retention period; script intended for scheduled execution (cron)
**Phase 4 Checkpoint**: All repositories instantiate without error when given a valid SQLAlchemy `Session`. `UserRepository.find_by_email()` returns `None` on empty DB (no exception).

---

## Phase 5: Security Layer

**Purpose**: Implement Argon2id password hashing, complexity enforcement, and security headers middleware.
**Spec ref**: spec.md §13.1, §12.1, plan.md §10 (Security Strategy), ADR-0002
**Depends on**: Phase 1

- [x] T031 Create `backend/modules/auth/services/password_service.py` — `PasswordService` extending `BaseService`; implement `hash_password(plain: str) -> str` using `argon2.PasswordHasher` configured with `time_cost`, `memory_cost`, `parallelism` from `Settings`; implement `verify_password(plain: str, hashed: str) -> bool`; plaintext must not be retained after operation
- [x] T031A Create `backend/core/utils/clock.py` — provide centralized UTC time helper (`utc_now()`); replace direct `datetime.utcnow()` usage throughout auth module to improve testability and deterministic unit testing
- [x] T032 Add `_validate_complexity(password: str, email: str) -> None` method to `PasswordService` — enforce: minimum length (default 12), maximum length (128), requires uppercase, lowercase, digit, special character; reject if password equals or contains email address; raise `ValidationException` listing all violations
- [x] T033 Add `_check_common_passwords(password: str) -> None` method to `PasswordService` — load `backend/modules/auth/data/common_passwords.txt` at service init; reject if password appears in list; raise `ValidationException`
- [x] T033A Update Password History logic — retain only the latest `PASSWORD_HISTORY_COUNT` password hashes; automatically delete older password history entries during password updates
- [x] T034 Add `check_password_history(plain: str, history: list[str]) -> None` method to `PasswordService` — verify new password against each hash in history list using `verify_password`; raise `ValidationException("Password was recently used.")` if any match; number of hashes checked governed by `settings.PASSWORD_HISTORY_COUNT`
- [x] T035 Create `backend/core/middleware/security_headers.py` — `SecurityHeadersMiddleware` Starlette middleware class; set on every response: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`, `Content-Security-Policy: default-src 'self'`, `Strict-Transport-Security: max-age=31536000; includeSubDomains`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`
- [x] T036 Register `SecurityHeadersMiddleware` in `backend/main.py` — add after existing middleware registrations; verify it does not interfere with existing health check response

**Phase 5 Checkpoint**: `PasswordService.hash_password("Test@1234567")` returns an Argon2id encoded string; `verify_password("Test@1234567", <hash>)` returns `True`; `verify_password("wrong", <hash>)` returns `False`; health endpoint response includes `X-Frame-Options: DENY` header.

---

## Phase 6: JWT Services

**Purpose**: Implement stateless JWT access token creation and validation.
**Spec ref**: spec.md §13.2, plan.md §5 (Module Breakdown — JWTService), ADR-0001
**Depends on**: Phase 1

- [x] T037 Create `backend/modules/auth/services/jwt_service.py` — `JWTService` (no `BaseService` extension — stateless, no DB dependency); inject `Settings` only; implement `create_access_token(user_id: UUID, email: str, session_id: UUID) -> str` — encodes claims: `sub`, `email`, `iat`, `exp`, `nbf`, `jti` (new UUID), `iss`, `aud`, `typ: "access"`, `sid`; uses `settings.JWT_SECRET_KEY` and `settings.JWT_ALGORITHM`
- [x] T038 Add `decode_access_token(token: str) -> dict` to `JWTService` — calls `jwt.decode()` validating signature, `exp`, `nbf`, `iss`, `aud`; raises `TokenExpiredException` on `ExpiredSignatureError`; raises `AuthenticationException` on any other `JWTError`; returns decoded claims dict
- [x] T039 Add `extract_user_id(claims: dict) -> UUID` and `extract_session_id(claims: dict) -> UUID` helper methods to `JWTService` — parse `sub` and `sid` claims from decoded dict; raise `AuthenticationException` if missing or malformed
- [x] T039A Update `JWTService` validation — support configurable JWT clock skew (`JWT_CLOCK_SKEW_SECONDS`, default 30 seconds) during token validation to tolerate small server time differences

**Phase 6 Checkpoint**: `JWTService.create_access_token(user_id, email, session_id)` returns a valid JWT string; `decode_access_token(<valid_token>)` returns claims dict; `decode_access_token(<expired_token>)` raises `TokenExpiredException`; `decode_access_token("garbage")` raises `AuthenticationException`.

---

## Phase 7: Authentication Services

**Purpose**: Implement all business logic services: TokenService, AuditService, AuthService.
**Spec ref**: spec.md §7 (FR-001–FR-075), plan.md §5 (Module Breakdown — Services), ADR-0001
**Depends on**: Phases 4, 5, 6

### Token Service

- [x] T040 Create `backend/modules/auth/services/token_service.py` — `TokenService` extending `BaseService`; inject `RefreshTokenRepository`, `PasswordResetTokenRepository`, `EmailVerificationTokenRepository`
- [x] T041 [US1][US3] Add `create_refresh_token(user_id, session_id, remember_me, ip, user_agent) -> tuple[str, RefreshToken]` to `TokenService` — generate raw token via `secrets.token_urlsafe(64)`, compute SHA-256 hex hash, set `expires_at` from `remember_me` flag (7 days or 30 days), persist `RefreshToken` record, enforce max 10 active tokens per user (revoke oldest if exceeded); return `(raw_token, record)`
- [x] T042 [US3] Add `rotate_refresh_token(old_token_hash: str, ip, user_agent) -> tuple[str, RefreshToken]` to `TokenService` — within a single DB transaction: look up old token by hash → verify not expired/revoked → atomically mark old token revoked → create new token inheriting `remember_me` flag → return new `(raw_token, record)`; on any failure rollback and raise appropriate exception
- [x] T043 [US4] Add `create_password_reset_token(user_id: UUID, ip: str) -> str` to `TokenService` — invalidate any existing active tokens for user, generate raw token via `secrets.token_urlsafe(32)`, hash it, persist with 1-hour expiry, return raw token
- [x] T044 [US5] Add `consume_password_reset_token(raw_token: str) -> PasswordResetToken` to `TokenService` — hash raw token → find active (not expired, not consumed) record → mark consumed → return record; raise `InvalidTokenException` if not found; raise `TokenExpiredException` if expired
- [x] T045 Add `create_email_verification_token(user_id: UUID) -> str` to `TokenService` — same pattern as reset token; 24-hour expiry; return raw token
- [x] T046 Add `consume_email_verification_token(raw_token: str) -> EmailVerificationToken` to `TokenService` — same pattern as `consume_password_reset_token`

### Audit Service

- [x] T047 Create `backend/modules/auth/services/audit_service.py` — `AuditService` extending `BaseService`; inject `AuditLogRepository`; implement `emit(event_type, outcome, user_id, request, reason, metadata) -> None`; extract `ip_address`, `user_agent`, `request_id` from FastAPI `Request` object; wrap `AuditLogRepository.create()` in try/except — log `ERROR` on failure but never raise; MUST NOT include password, raw token, or hash in any `metadata` argument
- [x] T047A Extend `AuditService` metadata sanitization — automatically remove or mask sensitive fields (`password`, `token`, `refresh_token`, `authorization`, `cookie`, `set-cookie`, `jwt`) before persisting audit metadata

### Auth Service

- [x] T048 Create `backend/modules/auth/services/auth_service.py` — `AuthService` extending `BaseService`; inject `UserRepository`, `UserCredentialRepository`, `SessionRepository`, `PasswordService`, `JWTService`, `TokenService`, `AuditService`
- [x] T049 [US1] Implement `AuthService.login(email, password, remember_me, request) -> LoginResponse` — execute exact login flow from plan.md §7.1: normalize email → find user → check account status (LOCKED/INACTIVE/DELETED → appropriate exception) → verify Argon2 hash → on mismatch: increment failed count, check lockout threshold, emit `LOGIN_FAILURE` audit event, raise `AuthenticationException`; on match: reset failed count, create JWT, create refresh token, create session, emit `LOGIN_SUCCESS` audit event, return `LoginResponse`
- [x] T049A Normalize login identifier before authentication — trim whitespace, apply Unicode normalization (NFKC), convert email to lowercase before lookup; ensure normalization is applied consistently across login, forgot-password, and email verification flows
- [x] T050 [US1] Add auto-unlock logic to `AuthService.login` — if `user.account_status == LOCKED` and `user.locked_until <= utcnow()`, reset status to `ACTIVE`, reset `failed_login_count` to 0, then proceed with normal login flow
- [x] T051 [US2] Implement `AuthService.logout(current_user: CurrentUser, request) -> None` — revoke active refresh tokens for user's current session via `RefreshTokenRepository.revoke_all_by_user()`; revoke session; emit `LOGOUT` audit event (spec.md §7.2 FR-009–FR-011)
- [x] T052 [US3] Implement `AuthService.refresh(raw_refresh_token: str, request) -> RefreshResponse` — hash token → call `TokenService.rotate_refresh_token()` → load user → check account status → create new JWT access token → emit `TOKEN_REFRESHED` audit event → return new `RefreshResponse` (spec.md §7.3 FR-013–FR-018)
- [x] T053 [US6] Implement `AuthService.get_current_user_profile(user_id: UUID) -> UserProfileResponse` — load user from `UserRepository.get_by_id()`; return `UserProfileResponse` (user_id, email, display_name, account_status, is_email_verified, created_at); MUST NOT include credentials (spec.md §7.4 FR-019–FR-021)
- [x] T054 [US4] Implement `AuthService.forgot_password(email: str, request) -> None` — always return successfully regardless of match (anti-enumeration FR-026); if email matches active account: call `TokenService.create_password_reset_token()`, call `send_password_reset_email()` stub, emit `PASSWORD_RESET_REQUESTED` audit event (spec.md §7.5 FR-022–FR-027)
- [x] T055 [US4] Create `backend/modules/auth/services/email_service.py` — `EmailService` stub; implement `send_password_reset_email(email: str, token: str) -> None` that logs the token at `DEBUG` level (never `INFO` or above in production); interface is ready for real SMTP in future Epic
- [x] T056 [US5] Implement `AuthService.reset_password(raw_token: str, new_password: str, request) -> None` — call `TokenService.consume_password_reset_token()` → validate password complexity → check password history → hash new password → update credential → add old hash to history → revoke all refresh tokens for user → emit `PASSWORD_RESET_COMPLETED` audit event (spec.md §7.6 FR-028–FR-034)
- [x] T057 [US8] Implement `AuthService.change_password(current_user: CurrentUser, current_password: str, new_password: str, request) -> None` — verify current password against stored hash → validate new password complexity → check password history → hash new password → update credential → add old hash to history → revoke all refresh tokens for user → emit `PASSWORD_CHANGED` audit event (spec.md §7.7 FR-035–FR-040)
- [x] T058 Add `AuthService.verify_email(raw_token: str) -> None` — call `TokenService.consume_email_verification_token()` → update `user.is_email_verified = True` → emit `EMAIL_VERIFIED` audit event (spec.md §7.11 FR-055–FR-060)

**Phase 7 Checkpoint**: Python REPL (with test DB): `auth_service.login("user@example.com", "wrongpass", False, mock_request)` raises `AuthenticationException`; 5 failures sets `account_status=LOCKED`; correct password returns `LoginResponse` with non-empty `access_token` and `refresh_token`.

---

## Phase 8: API Endpoints

**Purpose**: Implement all Pydantic schemas, the auth FastAPI router, and all 8 endpoints.
**Spec ref**: spec.md §14 (API Reference), plan.md §8 (API Strategy)
**Depends on**: Phase 7

### Pydantic Schemas

- [x] T059 Create `backend/modules/auth/schemas/auth.py` — Pydantic v2 models: `LoginRequest` (email: EmailStr, password: str, remember_me: bool=False), `LoginResponse` (access_token: str, refresh_token: str, token_type: str="bearer", expires_in: int), `RefreshRequest` (refresh_token: str), `RefreshResponse` (access_token: str, refresh_token: str, expires_in: int), `LogoutResponse` (message: str)
- [x] T060 [P] Create `backend/modules/auth/schemas/password.py` — Pydantic v2 models: `ForgotPasswordRequest` (email: EmailStr), `ResetPasswordRequest` (token: str, new_password: str, confirm_password: str) with `@model_validator` asserting `new_password == confirm_password`, `ChangePasswordRequest` (current_password: str, new_password: str, confirm_password: str) with same validator
- [x] T060A Create centralized auth exception mapping — map authentication exceptions to consistent HTTP responses (401 AuthenticationException, 401 TokenExpiredException, 401 TokenRevokedException, 403 AuthorizationException, 409 ConflictException, 422 ValidationException, 423 AccountLockedException)
- [x] T061 [P] Create `backend/modules/auth/schemas/user.py` — Pydantic v2 model: `UserProfileResponse` (user_id: UUID, email: str, display_name: str, account_status: str, is_email_verified: bool, created_at: datetime); must use `model_config = ConfigDict(from_attributes=True)`
- [x] T062 [P] Create `backend/modules/auth/schemas/verify.py` — Pydantic v2 model: `VerifyEmailRequest` (token: str)

### FastAPI Router and Endpoints

- [x] T063 Create `backend/modules/auth/router.py` — FastAPI `APIRouter` with prefix `/auth`, tag `["Authentication"]`; set up SlowAPI `Limiter` using `key_func=get_remote_address`; register rate limit state on the router
- [x] T064 [US1] Add `POST /auth/login` endpoint to router — rate limit: 10/minute per IP (spec.md §13.6); accepts `LoginRequest`; calls `AuthService.login()`; returns `ApiResponse[LoginResponse]`; no auth dependency; handles `AuthenticationException` (401), `AccountLockedException` (423), `AccountInactiveException` (403)
- [x] T065 [US2] Add `POST /auth/logout` endpoint to router — rate limit: 30/minute per IP; protected by `require_authenticated` dependency; calls `AuthService.logout()`; returns 204 No Content; handles `AuthenticationException` (401)
- [x] T066 [US3] Add `POST /auth/refresh` endpoint to router — rate limit: 30/minute per IP (spec.md §13.6); accepts `RefreshRequest`; calls `AuthService.refresh()`; returns `ApiResponse[RefreshResponse]`; no auth dependency; handles `TokenExpiredException` (401), `TokenRevokedException` (401)
- [x] T067 [US6] Add `GET /auth/me` endpoint to router — rate limit: 60/minute per user_id; protected by `require_authenticated` dependency; calls `AuthService.get_current_user_profile()`; returns `ApiResponse[UserProfileResponse]`; handles `AuthenticationException` (401)
- [x] T068 [US4] Add `POST /auth/forgot-password` endpoint to router — rate limit: 3/15 minutes per IP (spec.md §13.6); accepts `ForgotPasswordRequest`; calls `AuthService.forgot_password()`; always returns 200 `{"message": "If this email is registered, a reset link has been sent"}` (anti-enumeration FR-026)
- [x] T069 [US5] Add `POST /auth/reset-password` endpoint to router — rate limit: 5/15 minutes per IP; accepts `ResetPasswordRequest`; calls `AuthService.reset_password()`; returns 200 on success; handles `InvalidTokenException` (400), `TokenExpiredException` (400), `ValidationException` (422)
- [x] T070 [US8] Add `POST /auth/change-password` endpoint to router — rate limit: 5/15 minutes per user_id; protected by `require_authenticated` dependency; accepts `ChangePasswordRequest`; calls `AuthService.change_password()`; returns 200 on success
- [x] T071 Add `POST /auth/verify-email` endpoint to router — rate limit: 10/hour per IP; accepts `VerifyEmailRequest`; calls `AuthService.verify_email()`; returns 200 on success; handles `InvalidTokenException` (400), `TokenExpiredException` (400)
- [x] T071A Add OpenAPI examples — provide request and response examples for every authentication endpoint and schema to improve Swagger/OpenAPI documentation usability
- [x] T072 Register `modules.auth.router` in `backend/api/v1/router.py` — include with prefix `/api/v1` (or whatever the versioned prefix is per Epic 001 pattern)
- [x] T072A Update auth router registration — ensure authentication routes inherit the existing global API version prefix rather than hardcoding `/api/v1`; future API version changes must require no auth route modifications
- [x] T073 Register SlowAPI `Limiter` and its exception handler in `backend/main.py` — attach `slowapi_errors` handler returning 429 with `Retry-After` header

**Phase 8 Checkpoint**: `POST /api/v1/auth/login` with valid seeded user credentials returns 200 with tokens; same endpoint with wrong password returns 401; `GET /api/v1/auth/me` without token returns 401; rate limiter returns 429 after threshold.

---

## Phase 9: Middleware & Authentication Dependencies

**Purpose**: Replace Epic 001 stubs with real JWT-based authentication dependency; wire middleware.
**Spec ref**: spec.md §7.12 (FR-061–FR-066), plan.md §5 (Module Breakdown — core/auth/dependencies.py), plan.md §9 Phase 5
**Depends on**: Phases 6, 7, 8

- [x] T074 Create `backend/core/auth/dependencies.py` — implement real `get_current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser`: extract `Authorization: Bearer <token>` header → call `JWTService.decode_access_token()` → load user from `UserRepository.find_by_id()` → check `account_status` (raise `AccountLockedException` or `AccountInactiveException`) → return populated `CurrentUser(user_id=..., email=..., is_authenticated=True)`; raise `UnauthorizedException` if header missing
- [x] T075 Add `require_authenticated(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser` to `backend/core/auth/dependencies.py` — raises `UnauthorizedException` if `not current_user.is_authenticated`; used as FastAPI dependency on protected endpoints
- [x] T076 Update `backend/core/middleware/auth_hook.py` — replace stub call with call to real `get_current_user` dependency; store result on `request.state.user`; wrap in try/except so auth failure in middleware does not break public routes (only protected routes enforce auth at the endpoint level)
- [x] T077 Update all endpoints in `backend/modules/auth/router.py` — replace any remaining stub dependency references with `require_authenticated` from `core.auth.dependencies`; verify public endpoints (`/login`, `/refresh`, `/forgot-password`, `/reset-password`, `/verify-email`) have NO auth dependency
- [x] T077A Extend request logging context — propagate `request_id`, `session_id`, and `user_id` consistently across authentication services, audit logging, and structured application logs
- [x] T078 Verify `get_current_user_stub` and `require_authenticated_stub` in `backend/core/auth/interfaces.py` are no longer referenced by any production code path; stubs may remain in file for reference but must not be imported in routing or middleware code
- [x] T078A Extend health endpoint diagnostics — verify authentication configuration is successfully loaded and JWT configuration is initialized without exposing sensitive configuration values
- [x] T079 Add `POST /api/v1/auth/login` test user seed — create `backend/tests/fixtures/auth_fixtures.py` with factory function `create_test_user(db: Session) -> tuple[User, str]` that creates a test user with a known password hash; used by integration test suite
- [x] T079A Add CSRF middleware placeholder — introduce extensible middleware hook for future cookie-based authentication support without affecting current JWT Bearer implementation

**Phase 9 Checkpoint**: `GET /api/v1/auth/me` with valid JWT returns 200; `GET /api/v1/auth/me` without token returns 401 with `{"code": "UNAUTHORIZED"}`; `GET /api/v1/health` (Epic 001 endpoint) still returns 200 (no regression); `request.state.user` is populated on authenticated requests.

---

## Phase 10: Frontend Authentication

**Purpose**: Implement token storage abstraction, API client extensions, AuthContext, auth hooks, and all three auth form components.
**Spec ref**: plan.md §5 (Frontend Modules), plan.md §9 (Frontend Strategy), ADR-0003
**Depends on**: Phase 8 API endpoints must be deployed or mocked

### Token Storage & API Client

- [x] T080 Create `frontend/src/lib/auth/tokenStorage.ts` — export `storeTokens(access: string, refresh: string): void`, `getAccessToken(): string | null`, `getRefreshToken(): string | null`, `clearTokens(): void`; access token stored in module-level variable (NOT localStorage); refresh token stored in `localStorage` under key `erp_refresh_token`; JSDoc comment documenting XSS tradeoff per ADR-0003
- [x] T081 Create `frontend/src/lib/api/auth.ts` — export typed functions: `loginApi(email, password, rememberMe): Promise<LoginResponse>`, `logoutApi(): Promise<void>`, `refreshApi(refreshToken): Promise<RefreshResponse>`, `forgotPasswordApi(email): Promise<void>`, `resetPasswordApi(token, password): Promise<void>`, `changePasswordApi(currentPw, newPw): Promise<void>`, `getMeApi(): Promise<UserProfileResponse>`, `verifyEmailApi(token): Promise<void>`; all call existing `apiClient` from `frontend/src/lib/api/client.ts`
- [x] T082 Extend `frontend/src/lib/api/client.ts` — add request interceptor: read access token from `tokenStorage.getAccessToken()` and attach `Authorization: Bearer <token>` header on every outgoing request; add response interceptor: on 401 response with `data.code === "TOKEN_EXPIRED"`, call `refreshApi()` → store new tokens → retry original request once; on refresh failure call `clearTokens()` and dispatch a `session-expired` custom event
- [x] T083 Add TypeScript types to `frontend/src/types/auth.ts` — define: `LoginResponse`, `RefreshResponse`, `UserProfileResponse`, `AuthState`, `AuthContextValue` interfaces matching backend Pydantic schema shapes

### AuthContext and Hooks

- [x] T084 Create `frontend/src/contexts/AuthContext.tsx` — React Context providing `AuthContextValue`; on mount: call `tokenStorage.getRefreshToken()` → if present call `refreshApi()` to hydrate session → call `getMeApi()` → set `user` state; on 401 during hydration: call `clearTokens()`, set `isAuthenticated=false`; export `AuthProvider` wrapper and `useAuthContext` internal hook
- [x] T084A Configure authentication mutations — disable automatic retries (`retry: false`) for login, refresh, logout, forgot-password, reset-password, and change-password mutations to avoid unintended repeated authentication requests
- [x] T085 Create `frontend/src/hooks/useAuth.ts` — consumer hook calling `useAuthContext()`; throws `Error` if used outside `AuthProvider`; exports `{ user, isAuthenticated, isLoading, login, logout }`; `login(email, password, rememberMe)` calls `loginApi()` → `storeTokens()` → `getMeApi()` → sets state → returns; `logout()` calls `logoutApi()` → `clearTokens()` → resets state → `router.push("/login")`
- [x] T086 Create `frontend/src/hooks/useTokenRefresh.ts` — called inside `AuthContext`; reads `expires_in` from last login/refresh response; schedules `setTimeout` at 80% of token lifetime (default 12 min for 15-min tokens); on timer: calls `refreshApi()` → stores new tokens → reschedules; on failure: calls `logout()` + `router.push("/login")`; clears timer on `logout()` or component unmount
- [x] T086A Implement single refresh promise lock in `frontend/src/lib/auth/client.ts` — ensure multiple simultaneous 401 responses trigger only one refresh request while remaining requests await the same Promise; prevent duplicate refresh attempts and race conditions

### Auth Form Components

- [x] T087 [P] Create `frontend/src/components/auth/LoginForm.tsx` — React Hook Form with Zod schema (email: `z.string().email()`, password: `z.string().min(1)`, remember_me: `z.boolean().default(false)`); on submit: calls `useAuth().login()`; displays loading spinner on `isSubmitting`; displays 401 error as "Invalid email or password", 423 as "Account locked until {unlocks_at}", 429 as "Too many attempts, please wait"; disable form during submission; accessible: all fields have `<label>`, aria-describedby on error messages
- [x] T088 [P] Create `frontend/src/components/auth/ForgotPasswordForm.tsx` — React Hook Form with Zod schema (email: `z.string().email()`); on submit: calls `forgotPasswordApi()`; transitions to success state ("If this email is registered, you will receive a reset link.") regardless of API outcome (anti-enumeration); accessible; shows loading state
- [x] T089 [P] Create `frontend/src/components/auth/ResetPasswordForm.tsx` — React Hook Form with Zod schema (new_password: min 12 chars, confirm_password must match); reads `?token=` from URL search params; on submit: calls `resetPasswordApi(token, password)`; on success redirects to `/login` with toast "Password reset successfully. Please log in."; on 400 (invalid/expired token): shows "This reset link is invalid or has expired. Request a new one." with link to `/forgot-password`; password show/hide toggle; accessible
- [x] T089A Update logout flow — clear TanStack Query cache (`queryClient.clear()`) after successful logout to prevent cached authenticated data from leaking across user sessions

**Phase 10 Checkpoint**: `LoginForm` renders without errors; submitting with empty fields shows Zod validation errors without API call; `tokenStorage.storeTokens("a","b")` stores "b" in localStorage["erp_refresh_token"] and keeps "a" in memory only (not in localStorage).

---

## Phase 11: Token Management (Frontend)

**Purpose**: Implement session hydration, auto-refresh lifecycle, and logout flow.
**Spec ref**: spec.md §7.3 (US-03), spec.md §7.8 (US-07), plan.md §9 (Frontend Strategy — Automatic Refresh, Session Persistence)
**Depends on**: Phase 10

- [x] T090 [US3] Wire `useTokenRefresh` into `AuthContext.tsx` — call hook after successful session hydration; confirm timer is cleared on logout (no memory leak); verify timer is NOT started if no valid session exists
- [x] T091 [US9] Add `session-expired` custom event listener in `AuthContext.tsx` — listen for the event dispatched by the `client.ts` response interceptor on refresh failure; call `logout()` on receipt; display toast notification "Your session has expired. Please log in again."
- [x] T092 [US7] Pass `remember_me` flag from `LoginForm` through `useAuth().login()` → `loginApi()` → `POST /auth/login` request body; verify `LoginResponse.expires_in` reflects 30-day token when `remember_me=true` (confirmed via backend integration)
- [x] T093 [US10] Add `logoutAllDevices` action to `useAuth` hook — calls a backend endpoint or calls `logoutApi()` (which revokes all sessions server-side if spec.md §7.2 FR-012 "logout all devices" is implemented); clear local tokens; redirect to login

**Phase 11 Checkpoint**: Login → wait 12 min equivalent (mock timer) → `useTokenRefresh` fires → new tokens stored in memory/localStorage; Logout clears `localStorage["erp_refresh_token"]`; `tokenStorage.getRefreshToken()` returns `null` after logout.

---

## Phase 12: Protected Routing (Frontend)

**Purpose**: Implement route groups, auth layout, and route guards.
**Spec ref**: plan.md §5 (Frontend Modules — Route Guard, Auth Pages), plan.md §9 (Frontend Strategy — Route Protection)
**Depends on**: Phase 10, Phase 11

- [x] T094 Create `frontend/src/app/(auth)/layout.tsx` — minimal centered layout for auth pages (no sidebar, no header); renders `AuthProvider` and a centered card container; applies `min-h-screen flex items-center justify-center bg-gray-50` Tailwind classes
- [x] T095 [US1] Create `frontend/src/app/(auth)/login/page.tsx` — renders `LoginForm` inside the auth card; page title "Sign In — DevSphere ERP"; add `<Link href="/forgot-password">Forgot your password?</Link>`; if `useAuth().isAuthenticated` redirect to `/dashboard`
- [x] T096 [US4] Create `frontend/src/app/(auth)/forgot-password/page.tsx` — renders `ForgotPasswordForm`; page title "Reset Password — DevSphere ERP"; add `<Link href="/login">Back to Sign In</Link>`
- [x] T097 [US5] Create `frontend/src/app/(auth)/reset-password/page.tsx` — reads `searchParams.token`; if token absent: redirect to `/forgot-password`; renders `ResetPasswordForm` with extracted token
- [x] T098 Create `frontend/src/app/(protected)/layout.tsx` — route guard layout; wrap children in `AuthProvider`; inside component: if `isLoading` render full-screen skeleton; if `!isAuthenticated` call `router.replace("/login")`; if `isAuthenticated` render `AppLayout` (from Epic 001) wrapping `{children}`
- [x] T099 [US6] Add `frontend/src/app/(protected)/dashboard/page.tsx` — placeholder protected page; calls `getMeApi()` via TanStack Query; displays `user.display_name` and `user.email`; confirms `/me` endpoint is reachable from a protected route

**Phase 12 Checkpoint**: Navigating to `/dashboard` without being logged in redirects to `/login`; after login, navigating to `/login` redirects to `/dashboard`; logging out from `/dashboard` redirects to `/login`.

---

## Phase 13: Testing

**Purpose**: Comprehensive test suite covering all layers.
**Spec ref**: plan.md §12 (Testing Strategy), spec.md §8 (NFR-024)
**Depends on**: Phases 1–12

### Repository Unit Tests (using real test DB)

- [X] T100 Create `backend/tests/integration/repositories/auth/test_user_repository.py` — test: `find_by_email` returns user; `find_by_email` returns None for unknown; email lookup is case-insensitive; `lock_account` sets status and `locked_until`; `unlock_account` resets status; `update_failed_login_count` updates counter
- [X] T101 [P] Create `backend/tests/integration/repositories/auth/test_refresh_token_repository.py` — test: `create` persists token hash (not raw); `find_by_token_hash` retrieves by hash; `revoke` marks token revoked; `revoke_all_by_user` revokes all; `count_active_by_user` returns correct count; oldest token revoked when limit exceeded
- [X] T102 [P] Create `backend/tests/integration/repositories/auth/test_audit_log_repository.py` — test: `create` persists event; `list_by_user_id` filters by user and time range; attempting to update an audit log raises `AttributeError` (no `update` method exposed)
- [X] T103 [P] Create `backend/tests/integration/repositories/auth/test_session_repository.py` — test: `create_session` returns session; `revoke_all_by_user` marks all revoked; `get_active_sessions_by_user` excludes revoked

### Service Unit Tests (mocked repositories)

- [X] T104 Create `backend/tests/unit/modules/auth/test_password_service.py` — test: `hash_password` returns Argon2 encoded string; `verify_password` correct → True; `verify_password` wrong → False; complexity: password too short raises; no uppercase raises; no special char raises; common password raises; email substring raises; history match raises; history miss passes
- [X] T105 [P] Create `backend/tests/unit/modules/auth/test_jwt_service.py` — test: `create_access_token` returns valid JWT; decoded claims contain `sub`, `exp`, `jti`, `sid`; `decode_access_token` expired token raises `TokenExpiredException`; tampered signature raises `AuthenticationException`; wrong issuer raises `AuthenticationException`
- [X] T106 [P] Create `backend/tests/unit/modules/auth/test_token_service.py` — test: `create_refresh_token` returns raw token and record; raw token not equal to stored hash; `rotate_refresh_token` revokes old and returns new; rotation is atomic (simulate failure mid-transaction); `consume_password_reset_token` marks token consumed; expired token raises `TokenExpiredException`; already-consumed token raises `InvalidTokenException`

### Auth Service Unit Tests (mocked deps)

- [X] T107 Create `backend/tests/unit/modules/auth/test_auth_service_login.py` — test: [US1] valid credentials → LoginResponse with tokens; [US1] wrong password → AuthenticationException; [US1] wrong password × 5 → account locked + AccountLockedException; [US1] unknown email → AuthenticationException (same message, timing consistent); [US1] locked account past expiry → auto-unlock then succeed; [US1] inactive account → AccountInactiveException; [US1] remember_me=True → token expires_in reflects 30 days; [US1] audit event emitted on success; [US1] audit event emitted on failure
- [X] T108 [P] Create `backend/tests/unit/modules/auth/test_auth_service_logout.py` — test: [US2] logout revokes refresh tokens; [US2] logout emits LOGOUT audit event; [US10] already-revoked session returns success (idempotent)
- [X] T109 [P] Create `backend/tests/unit/modules/auth/test_auth_service_refresh.py` — test: [US3] valid refresh token → new access + refresh tokens; [US3] old token marked revoked after rotation; [US3] expired refresh token → TokenExpiredException; [US3] revoked refresh token → TokenRevokedException; [US3] revoked token reuse → all user tokens revoked (theft detection); [US3] audit event emitted
- [X] T110 [P] Create `backend/tests/unit/modules/auth/test_auth_service_password.py` — test: [US4] forgot_password returns None regardless of email match; [US4] matching email generates reset token; [US4] second request invalidates first token; [US5] valid token → password updated, sessions revoked, audit emitted; [US5] expired token → TokenExpiredException; [US5] consumed token → InvalidTokenException; [US8] correct current password → updates; [US8] wrong current password → AuthenticationException; [US8] history violation → ValidationException

### API Integration Tests

- [X] T111 Create `backend/tests/integration/api/v1/auth/test_login.py` — using `httpx.AsyncClient`; test: [US1] POST /login valid → 200 + tokens; [US1] POST /login wrong password → 401 INVALID_CREDENTIALS; [US1] POST /login nonexistent email → 401 INVALID_CREDENTIALS (same response); [US1] POST /login locked account → 423 ACCOUNT_LOCKED with `unlocks_at`; [US1] POST /login email with trailing spaces → 401 (email normalized); [US1] POST /login rate limit (11 req/min) → 429
- [X] T112 [P] Create `backend/tests/integration/api/v1/auth/test_logout.py` — test: [US2] POST /logout authenticated → 204; [US2] former refresh token rejected → 401; [US2] POST /logout no token → 401
- [X] T113 [P] Create `backend/tests/integration/api/v1/auth/test_refresh.py` — test: [US3] POST /refresh valid token → 200 new tokens; [US3] old token rejected → 401; [US3] expired token → 401 TOKEN_EXPIRED; [US3] revoked token → 401 TOKEN_REVOKED; [US3] concurrent refresh (same token × 2 simultaneous) → one succeeds, one returns 401
- [X] T114 [P] Create `backend/tests/integration/api/v1/auth/test_me.py` — test: [US6] GET /me valid JWT → 200 user data; [US6] GET /me no credential field in response; [US6] GET /me expired JWT → 401; [US6] GET /me deleted user → 401
- [X] T115 [P] Create `backend/tests/integration/api/v1/auth/test_forgot_password.py` — test: [US4] POST /forgot-password registered email → 200 (same message); [US4] POST /forgot-password unknown email → 200 (identical message); [US4] rate limit → 429; [US4] reset token generated for registered email (check DB)
- [X] T116 [P] Create `backend/tests/integration/api/v1/auth/test_reset_password.py` — test: [US5] valid token + valid password → 200; [US5] expired token → 400 INVALID_TOKEN; [US5] consumed token → 400; [US5] weak password → 422 VALIDATION_ERROR; [US5] sessions revoked after reset (former refresh token rejected)
- [X] T117 [P] Create `backend/tests/integration/api/v1/auth/test_change_password.py` — test: [US8] correct current + valid new → 200; [US8] wrong current → 403; [US8] history violation → 422; [US8] other-device sessions revoked after change
- [X] T118 [P] Create `backend/tests/integration/api/v1/auth/test_security_headers.py` — test: every auth endpoint response includes `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`; test health endpoint also includes headers (SecurityHeadersMiddleware is global)

### Frontend Component Tests

- [X] T119 Create `frontend/src/__tests__/auth/LoginForm.test.tsx` — test: renders email, password, remember_me, submit; empty form submit shows Zod validation errors without API call; valid submit calls `login()` from `useAuth`; 401 response shows "Invalid email or password" error message; 423 response shows lock message; button disabled during isSubmitting
- [X] T120 [P] Create `frontend/src/__tests__/auth/ForgotPasswordForm.test.tsx` — test: empty email shows validation error; valid email shows success message after submit; success message is identical regardless of API response (anti-enumeration); loading state shows spinner
- [X] T121 [P] Create `frontend/src/__tests__/auth/ResetPasswordForm.test.tsx` — test: password mismatch shows validation error; weak password shows error; valid submit calls `resetPasswordApi`; success redirects to /login; 400 response shows "link invalid" message with re-request link
- [X] T122 [P] Create `frontend/src/__tests__/auth/AuthContext.test.tsx` — test: on mount with stored refresh token calls refresh endpoint; on mount without token sets isAuthenticated=false; login sets user and isAuthenticated=true; logout clears state and localStorage; `session-expired` event triggers logout
- [X] T123 [P] Create `frontend/src/__tests__/auth/tokenStorage.test.ts` — test: `storeTokens` keeps access token OUT of localStorage; `storeTokens` puts refresh token IN localStorage; `clearTokens` removes from both; `getAccessToken` survives page navigation (module-level variable persists in test)

### Security Tests

- [X] T124 Create `backend/tests/security/test_anti_enumeration.py` — test: login with valid email wrong password and login with nonexistent email must both return 401 with identical response body; POST /forgot-password with registered and unregistered email must return identical 200 response body; timing difference < 50ms between matched and unmatched cases
- [X] T125 [P] Create `backend/tests/security/test_account_lockout.py` — test: 4 failed logins → account still active; 5th failed login → account locked (423); correct password on locked account → 423; locked account auto-unlocks after lockout duration; counter resets after successful login
- [X] T126 [P] Create `backend/tests/security/test_password_history.py` — test: password cannot be reused from last 5 (configurable); password NOT in last 5 is accepted; password after 6 changes can be reused
- [X] T127 [P] Create `backend/tests/security/test_replay_attack.py` — test: consumed password reset token rejected; expired password reset token rejected; used refresh token rejected after rotation; second simultaneous refresh with same token → one 200, one 401
- [X] T128 [P] Create `backend/tests/security/test_sensitive_log.py` — test: login with credentials → check all log output (captured via logging fixture) for absence of password string, raw token, or token hash; use `caplog` pytest fixture; verify DEBUG email service stub log does NOT propagate above DEBUG level
- [X] T128A Create `backend/tests/security/test_invalid_jwt.py` — test malformed JWT, invalid signature, unsupported algorithm, `alg=none`, future `iat`, missing `sid`, missing `aud`, missing `iss`, invalid `typ`, and expired `nbf`; verify correct authentication failures without server errors

### Performance / Concurrency Tests

- [X] T129 Create `backend/tests/performance/test_login_performance.py` — measure 10 sequential login requests; assert p95 latency < 800ms; use `time.perf_counter()` with test user seeded DB; note: Argon2 hashing is the bottleneck
- [X] T130 [P] Create `backend/tests/performance/test_refresh_performance.py` — measure 20 sequential refresh requests; assert p95 latency < 200ms
- [X] T131 [P] Create `backend/tests/performance/test_concurrent_refresh.py` — launch 5 concurrent refresh requests with the SAME refresh token using `asyncio.gather`; assert exactly one returns 200 and the rest return 401 (atomic rotation test)

**Phase 13 Checkpoint**: `pytest backend/tests/ -v` passes with ≥90% coverage on `modules/auth/services/` and `core/auth/dependencies.py`; `npm test` passes all frontend auth tests; concurrent refresh test passes (exactly one winner).

---

## Phase 14: Performance & Security Validation

**Purpose**: External validation of security posture, performance targets, and static analysis.
**Spec ref**: spec.md §8 (NFR-001–NFR-029), plan.md §14 (Performance & Security Validation)
**Depends on**: Phase 13

- [X] T132 Run `bandit -r backend/modules/auth/ -ll` and confirm zero HIGH or CRITICAL findings; document any MEDIUM findings in `specs/002-auth-identity/security-review.md` with disposition
- [X] T133 [P] Run `pip-audit` on backend `requirements.txt` / `pyproject.toml`; confirm zero HIGH vulnerabilities in `argon2-cffi`, `PyJWT`, `slowapi`, `fastapi`, `sqlalchemy`; resolve or document any findings
- [X] T134 [P] Run `npm audit --audit-level=high` on frontend `package.json`; confirm zero HIGH vulnerabilities in `@tanstack/react-query`, `react-hook-form`, `zod`; resolve or document any findings
- [X] T135 Verify Argon2id parameters meet OWASP minimums — write and run `backend/tests/security/test_argon2_params.py`: hash a password and parse the encoded string to confirm `m>=19456`, `t>=2`, `p>=1` (per spec.md §13.1); assert hash timing >= 100ms on CI hardware
- [X] T136 [P] Validate JWT claims — write and run `backend/tests/security/test_jwt_claims.py`: decode a created token and assert presence of: `sub`, `iat`, `exp`, `nbf`, `jti`, `iss`, `aud`, `typ`, `sid` (per spec.md §13.2); assert `exp - iat = 900` seconds (15 min)
- [X] T137 [P] Validate refresh token entropy — write and run `backend/tests/security/test_token_entropy.py`: generate 1000 raw refresh tokens; assert no duplicates; assert each has length >= 86 characters (64 bytes base64url); assert `token_hash != raw_token` for each
- [X] T138 Validate security headers on all auth endpoints — run automated check against all 8 endpoints using httpx; assert each of the 7 required headers is present in every response (per spec.md §13.7); fail CI if any header missing
- [X] T139 [P] Validate audit log completeness — run integration scenario: login + refresh + logout + forgot-password + reset-password + change-password; query `audit_logs` table; assert one record per event type with correct `outcome`, non-null `ip_address`, non-null `request_id`, and no password or token in `metadata`
- [X] T140 [P] Validate rate limiting — write `backend/tests/security/test_rate_limits.py`: fire 11 sequential POST /login requests; assert request #11 returns 429 with `Retry-After` header; fire 4 POST /forgot-password requests; assert #4 returns 429
- [X] T140A Validate authentication transaction atomicity — verify login, refresh, password reset, password change, logout, and session revocation operations remain atomic under concurrent execution; ensure no partial database updates occur after simulated failures

**Phase 14 Checkpoint**: All bandit, pip-audit, npm-audit checks pass. Argon2 param test passes. All 7 security headers present on all endpoints. All audit event types logged. Rate limits fire at correct thresholds.

---

## Phase 15: Documentation

**Purpose**: Update environment configuration documentation and developer setup guide.
**Spec ref**: plan.md §14 (Deployment Strategy), plan.md §17 (Definition of Done)
**Depends on**: Phase 8, Phase 12

- [X] T141 Update `.env.example` at repository root — add all auth environment variables from Phase 1 T005 with descriptive comments; include example values (random placeholder strings, NOT real secrets); add comments explaining each setting (token expiry, lockout thresholds, Argon2 params)
- [X] T142 [P] Create `specs/002-auth-identity/quickstart.md` — developer setup guide covering: prerequisite setup (copy `.env.example` to `.env`, generate JWT secret), running `docker-compose up`, running `alembic upgrade head`, seeding a test user (CLI command or SQL snippet), testing login with curl example, running the test suite, and common troubleshooting (wrong JWT secret, migration failures)
- [X] T143 [P] Add API usage examples section to `specs/002-auth-identity/quickstart.md` — include curl examples for: POST /auth/login, POST /auth/refresh, GET /auth/me, POST /auth/forgot-password, POST /auth/reset-password, POST /auth/change-password, POST /auth/logout; show request headers and example response bodies
- [X] T144 Update `CLAUDE.md` at repository root — add Epic 002 to "Recent Changes" section; update "Active Technologies" section to include `argon2-cffi`, `PyJWT`, `slowapi`, `@tanstack/react-query`, `react-hook-form`, `zod`

**Phase 15 Checkpoint**: `cat .env.example | grep JWT_SECRET_KEY` shows the variable with comment; `specs/002-auth-identity/quickstart.md` exists and includes curl login example; CLAUDE.md lists Epic 002 technologies.

---

## Phase 16: Deployment Verification

**Purpose**: Validate the complete system in a Docker Compose environment from a clean state.
**Spec ref**: plan.md §14 (Deployment Strategy), plan.md §17 (Definition of Done — Operational Validation)
**Depends on**: Phases 1–15

- [X] T145 Run `docker-compose build --no-cache` — confirm build succeeds with all new Python and npm packages; resolve any build-time dependency errors
- [X] T146 Run `docker-compose up -d` from clean state — confirm all services start without error; confirm backend logs show "Application startup complete"; confirm no `JWT_SECRET_KEY` startup error (set value in `.env`)
- [X] T147 Run `alembic upgrade head` inside the running backend container — confirm output shows `Running upgrade 001_initial_baseline -> 002_auth_identity`; confirm no errors; query DB to confirm 7 new tables exist
- [X] T148 Seed a test user via CLI or DB insert; verify `GET /api/v1/health` returns 200 (Epic 001 endpoint, no regression); verify `POST /api/v1/auth/login` with seeded credentials returns 200 with `access_token` and `refresh_token`
- [X] T149 Run end-to-end manual login scenario: Login → copy access token → `GET /auth/me` → `POST /auth/refresh` (use refresh token) → `POST /auth/logout` → verify old refresh token rejected with 401; verify `GET /auth/me` with old access token still works until expiry (short TTL)
- [X] T150 Run `alembic downgrade base` inside the running backend container — confirm all 7 auth tables dropped; re-run `alembic upgrade head` — confirm clean re-creation; no data loss errors on fresh migration
- [X] T151 Verify production configuration checklist: `JWT_SECRET_KEY` is >= 32 characters; `ARGON2_MEMORY_COST` >= 19456; `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` = 15; `AUTH_LOCKOUT_THRESHOLD` = 5; all values loaded from environment (not hardcoded); check `docker-compose logs backend | grep -i "secret"` produces no output containing the actual secret value
- [X] T152 Confirm frontend build: `npm run build` in `frontend/` succeeds; `next build` produces no TypeScript errors related to new auth files; no `any` type warnings in auth components

**Phase 16 Checkpoint**: Docker Compose up → health check → login → refresh → logout all succeed. `alembic downgrade base && alembic upgrade head` succeeds. `npm run build` succeeds. Epic 002 is deployable.

---

## Phase 17: Continuous Integration Validation

**Purpose**: Validate automated CI/CD pipeline and release readiness.

**Depends on**: Phase 16

- [X] T153 Configure GitHub Actions backend workflow — run Ruff, MyPy, pytest with coverage, Bandit, pip-audit, migration validation, and Docker build
- [X] T154 [P] Configure GitHub Actions frontend workflow — run ESLint, TypeScript, Jest, npm audit, and Next.js production build
- [X] T155 [P] Configure pull request quality gates — fail CI on coverage below required threshold, failed security scans, failed migrations, or failed builds
- [X] T156 Verify complete CI pipeline from clean checkout — confirm repository builds, migrations execute, backend tests pass, frontend tests pass, security scans pass, and Docker images build successfully

## Dependencies & Execution Order

### Phase Dependencies

| Phase | Depends On | Can Parallelize With |
|-------|-----------|---------------------|
| Phase 1 (Preparation) | Nothing | — |
| Phase 2 (DB Models) | Phase 1 | — |
| Phase 3 (Migration) | Phase 2 | — |
| Phase 4 (Repositories) | Phase 3 | Phase 5 (partially) |
| Phase 5 (Security Layer) | Phase 1 | Phase 4, Phase 6 |
| Phase 6 (JWT Service) | Phase 1 | Phase 4, Phase 5 |
| Phase 7 (Auth Services) | Phases 4, 5, 6 | Phase 10 (frontend scaffolding) |
| Phase 8 (API Endpoints) | Phase 7 | Phase 10, Phase 11 |
| Phase 9 (Middleware) | Phases 6, 7, 8 | — |
| Phase 10 (Frontend Auth) | Phase 8 deployed/mocked | — |
| Phase 11 (Token Mgmt) | Phase 10 | — |
| Phase 12 (Protected Routing) | Phases 10, 11 | — |
| Phase 13 (Testing) | Phases 1–12 | Phases 14, 15 |
| Phase 14 (Security Validation) | Phase 13 | Phase 15 |
| Phase 15 (Documentation) | Phases 8, 12 | Phase 13, Phase 14 |
| Phase 16 (Deployment) | Phases 13, 14, 15 | — |

### User Story → Phase Mapping

| Story | Priority | Implemented In Phases |
|-------|---------|----------------------|
| US-01 Login | P1 | 2, 3, 4, 5, 6, 7, 8, 9, 10, 12 |
| US-02 Logout | P1 | 7, 8, 9, 10 |
| US-03 Token Refresh | P1 | 4, 6, 7, 8, 10, 11 |
| US-04 Forgot Password | P2 | 4, 7, 8, 10 |
| US-05 Reset Password | P2 | 4, 7, 8, 10 |
| US-06 Current User | P1 | 7, 8, 9, 10, 12 |
| US-07 Remember Me | P2 | 7, 8, 10, 11 |
| US-08 Change Password | P2 | 7, 8 |
| US-09 Session Expiration | P1 | 10, 11 |
| US-10 Session Revocation | P2 | 4, 7, 8 |

### Parallel Execution Opportunities

```
CRITICAL PATH (sequential):
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 7 → Phase 8 → Phase 9 → Phase 12 → Phase 16

PARALLELIZABLE (two-dev team split after Phase 1):
Developer A: Phase 2 → Phase 3 → Phase 4 → Phase 7 → Phase 8 → Phase 9 → Phase 13 (backend)
Developer B: Phase 5 → Phase 6 → Phase 10 → Phase 11 → Phase 12 → Phase 13 (frontend)

Within Phase 13 (testing), [P]-tagged tasks can run concurrently:
T100, T101, T102, T103 — all repository tests in parallel
T104, T105, T106 — all unit tests in parallel
T111, T112, T113, T114, T115, T116, T117, T118 — all API integration tests in parallel
T119, T120, T121, T122, T123 — all frontend tests in parallel
T124, T125, T126, T127, T128 — all security tests in parallel
T129, T130, T131 — all performance tests in parallel
```

---

## Requirement Coverage Validation

| spec.md Section | Covered by Tasks |
|----------------|-----------------|
| FR-001–FR-008 (Login) | T049, T050, T064, T107, T111 |
| FR-009–FR-012 (Logout) | T051, T065, T108, T112 |
| FR-013–FR-018 (Refresh) | T041, T042, T052, T066, T109, T113 |
| FR-019–FR-021 (Current User) | T053, T067, T114 |
| FR-022–FR-027 (Forgot Password) | T043, T054, T055, T068, T110, T115 |
| FR-028–FR-034 (Reset Password) | T044, T056, T069, T116 |
| FR-035–FR-040 (Change Password) | T057, T070, T117 |
| FR-041–FR-044 (Remember Me) | T041, T092 |
| FR-045–FR-047 (Session Expiration) | T066, T086, T090, T091 |
| FR-048–FR-054 (Account Lockout) | T049, T050, T125 |
| FR-055–FR-060 (Email Verification) | T015, T028, T045, T046, T058, T071 |
| FR-061–FR-066 (Auth Middleware) | T074, T075, T076 |
| FR-067–FR-068 (Protected/Public APIs) | T064–T071, T077 |
| FR-069–FR-071 (Session Revocation) | T025, T026, T051, T056, T057 |
| FR-072–FR-075 (Audit Logging) | T047, T107–T110, T128, T139 |
| NFR-001–NFR-005 (Performance) | T129, T130, T135 |
| NFR-011 (Argon2id) | T031, T032, T135 |
| NFR-012 (JWT Secret Env Var) | T005, T008 |
| NFR-014 (Rate Limiting) | T063, T073, T140 |
| NFR-015 (Account Lockout) | T049, T050, T125 |
| NFR-016 (Atomic Operations) | T026, T042, T131 |
| NFR-017 (Security Headers) | T035, T036, T118, T138 |
| NFR-024 (Coverage ≥90%) | T104–T131 |
| §12.1 (Password Policy) | T032, T033, T034, T104, T126 |
| §12.2 (Lockout Policy) | T049, T050, T125 |
| §12.4 (Session Rules) | T026, T042 |
| §13.2 (JWT Claims) | T037, T136 |
| §13.3 (Refresh Token Hashing) | T026, T041, T137 |
| §13.6 (Rate Limits by endpoint) | T064–T071, T073, T140 |
| §13.7 (Security Headers) | T035, T036, T118, T138 |

---

## Implementation Summary

### Critical Path

```
T001 → T005 → T008 → T009 → T010–T017 → T018–T022 → T023–T030
→ T031–T036 → T037–T039 → T040–T058 → T059–T073 → T074–T079
→ T080–T099 → T100–T131 → T132–T140 → T141–T144 → T145–T152
```

### Estimated Task Count

| Phase | Task Count |
|-------|-----------|
| Phase 1 (Preparation) | 8 |
| Phase 2 (DB Models) | 9 |
| Phase 3 (Migration) | 5 |
| Phase 4 (Repositories) | 8 |
| Phase 5 (Security Layer) | 6 |
| Phase 6 (JWT Services) | 3 |
| Phase 7 (Auth Services) | 19 |
| Phase 8 (API Endpoints) | 15 |
| Phase 9 (Middleware) | 6 |
| Phase 10 (Frontend Auth) | 10 |
| Phase 11 (Token Management) | 4 |
| Phase 12 (Protected Routing) | 6 |
| Phase 13 (Testing) | 32 |
| Phase 14 (Security Validation) | 9 |
| Phase 15 (Documentation) | 4 |
| Phase 16 (Deployment) | 8 |
| **TOTAL** | **152** |

### Estimated Effort

| Track | Developer Days |
|-------|--------------|
| Backend (Phases 1–9) | 8–10 days |
| Frontend (Phases 10–12) | 4–5 days |
| Testing (Phase 13) | 4–5 days |
| Security/Performance Validation (Phase 14) | 1–2 days |
| Documentation + Deployment (Phases 15–16) | 1–2 days |
| **Total (single developer)** | **18–24 days** |
| **Total (2-developer parallel)** | **10–13 days** |

### Suggested Git Commit Strategy

```
feat(auth): Phase 1 — add auth dependencies and settings
feat(auth): Phase 2 — add auth ORM models (User, UserCredentials, Session, RefreshToken, tokens, AuditLog)
feat(auth): Phase 3 — add Alembic migration 002_auth_identity
feat(auth): Phase 4 — implement auth repositories (UserRepository, RefreshTokenRepository, AuditLogRepository, et al.)
feat(auth): Phase 5 — implement PasswordService with Argon2id and SecurityHeadersMiddleware
feat(auth): Phase 6 — implement JWTService
feat(auth): Phase 7 — implement TokenService, AuditService, AuthService (all flows)
feat(auth): Phase 8 — implement auth router with all 8 endpoints and rate limiting
feat(auth): Phase 9 — replace auth stubs with real get_current_user dependency
feat(auth): Phase 10 — frontend auth (tokenStorage, AuthContext, LoginForm, ForgotPasswordForm, ResetPasswordForm)
feat(auth): Phase 11 — frontend token refresh lifecycle (useTokenRefresh, session hydration)
feat(auth): Phase 12 — frontend route guard and protected route group
test(auth): Phase 13 — comprehensive test suite (repository, service, API, frontend, security)
chore(auth): Phase 14 — security validation (bandit, pip-audit, parameter verification)
docs(auth): Phase 15 — .env.example, quickstart.md, CLAUDE.md update
chore(auth): Phase 16 — deployment verification (Docker, migration, end-to-end)
```

### Suggested Pull Request Strategy

| PR | Scope | Reviewers Must Check |
|----|-------|---------------------|
| PR-1 | Phases 1–3 (foundation + models + migration) | Schema correctness, index completeness, migration rollback |
| PR-2 | Phases 4–6 (repositories + security + JWT) | Argon2 params, token hashing, atomic rotation in T026 |
| PR-3 | Phases 7–9 (services + API + middleware) | Anti-enumeration (T049), audit events, rate limit config, stub replacement |
| PR-4 | Phases 10–12 (frontend) | ADR-0003 token storage compliance, route guard correctness, accessibility |
| PR-5 | Phase 13 (tests) | Coverage ≥90%, security tests pass, concurrent refresh test |
| PR-6 | Phases 14–16 (validation + docs + deploy) | Bandit/audit scans, .env.example completeness, DoD checklist |

### Risk Checkpoints

| Checkpoint | Risk | Mitigation |
|-----------|------|-----------|
| After T022 (migration) | Migration fails on existing data | Run against empty test DB and data-bearing DB before PR-1 merge |
| After T050 (lockout logic) | Permanent lockout on bug | Integration test T125 must pass before PR-3 merge |
| After T052 (refresh rotation) | Concurrent refresh loses sessions | T131 concurrent refresh test must pass before PR-3 merge |
| After T075 (auth dependency) | Existing Epic 001 endpoints broken | Run full Epic 001 test suite as part of Phase 9 CI |
| After T082 (client.ts interceptors) | Infinite refresh loop | T122 AuthContext test covers this; also verify via E2E |

---

## Quality Gates Before Moving to Epic 003

All of the following must pass before Epic 003 begins:

- [ ] `pytest backend/tests/ --cov=modules/auth --cov=core/auth --cov-fail-under=90` — PASS
- [ ] `npm test` — all frontend auth tests PASS
- [ ] `bandit -r backend/modules/auth/ -ll` — zero HIGH/CRITICAL findings
- [ ] `pip-audit` + `npm audit --audit-level=high` — zero HIGH vulnerabilities
- [ ] Security headers present on all 8 auth endpoints — VERIFIED
- [ ] Anti-enumeration verified for login and forgot-password — VERIFIED
- [ ] Account lockout at correct threshold — VERIFIED (T125)
- [ ] Concurrent refresh race condition handled — VERIFIED (T131)
- [ ] Audit logs written for all 9 event types — VERIFIED (T139)
- [ ] Argon2id parameters meet OWASP minimums — VERIFIED (T135)
- [ ] All 7 refresh token token hashes never equal raw tokens — VERIFIED (T137)
- [ ] `alembic downgrade base && alembic upgrade head` — PASS
- [ ] `docker-compose up` + full login/refresh/logout flow — PASS
- [ ] `npm run build` — zero TypeScript errors in auth files — PASS
- [ ] `GET /api/v1/health` still returns 200 (Epic 001 regression) — PASS
- [ ] `.env.example` updated with all new variables — VERIFIED
- [ ] `specs/002-auth-identity/quickstart.md` exists — VERIFIED
- [ ] `CLAUDE.md` updated with Epic 002 technologies — VERIFIED
- [ ] All spec.md FRs (FR-001–FR-075) mapped to passing tests — VERIFIED via coverage report
