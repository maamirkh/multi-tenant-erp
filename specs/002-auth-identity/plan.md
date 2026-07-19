# Implementation Plan: Authentication & Identity

**Epic**: `002-auth-identity`
**Branch**: `002-auth-identity`
**Date**: 2026-07-13
**Spec**: [`specs/002-auth-identity/spec.md`](./spec.md)
**Status**: Approved for Implementation

---

## Summary

Epic 002 implements a production-grade, security-first authentication and identity layer on top of the Epic 001 foundation platform. The implementation replaces the authentication stubs in `core/auth/interfaces.py` with a complete JWT + refresh token system, introduces six new database entities, and delivers three frontend authentication pages with full session lifecycle management.

The architecture follows Clean Architecture principles with strict layer separation: routers handle HTTP concerns, services encapsulate business logic, repositories own data access, and domain models are framework-agnostic. All components extend the existing `BaseRepository`, `BaseService`, exception hierarchy, and dependency injection patterns from Epic 001.

---

## Technical Context

| Parameter | Value |
|-----------|-------|
| **Language/Version** | Python 3.12+ (backend), TypeScript 5.x (frontend) |
| **Primary Dependencies** | FastAPI, SQLAlchemy 2.x, Alembic, PyJWT, argon2-cffi, slowapi, Next.js 16+, TanStack Query, React Hook Form, Zod |
| **Storage** | PostgreSQL 16 LTS |
| **Testing** | pytest, pytest-asyncio, httpx (backend); Jest, React Testing Library (frontend) |
| **Target Platform** | Linux server (Docker), Next.js on Vercel/Node |
| **Performance Goals** | Login p95 <800ms; Token refresh p95 <200ms; /me p95 <100ms; Auth middleware overhead <10ms |
| **Constraints** | Argon2id hashing is intentionally slow; budget accounts for this. JWT must be stateless. Refresh token rotation must be atomic. |
| **Scale/Scope** | 500+ concurrent auth requests; 90-day audit retention; multi-tenant-aware from Day 1 |

---

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Clean Architecture | PASS | Auth module in `modules/auth/`; layers enforced (router → service → repository) |
| Repository Pattern | PASS | Extends `BaseRepository`; custom repos for token/audit entities |
| BaseService Extension | PASS | `AuthService`, `PasswordService`, `TokenService` extend `BaseService` |
| Exception Hierarchy | PASS | New `AuthenticationException`, `AccountLockedException` extend `ApplicationException` |
| Pydantic v2 Schemas | PASS | All request/response DTOs use Pydantic v2 |
| Alembic Migrations | PASS | Single versioned migration file `002_auth_identity.py` |
| Environment-only Secrets | PASS | JWT secret, Argon2 params, expiry windows all via Settings |
| No Hardcoded Credentials | PASS | Enforced at settings and test fixture level |
| Soft-delete Pattern | PARTIAL | Users use soft-delete; token tables use hard-delete on expiry (justified below) |
| Audit Trail | PASS | Structured `AuditLog` entity for all security events |
| Rate Limiting | PASS | SlowAPI applied at router level on all auth endpoints |
| Security Headers | PASS | Middleware applied at application level |
| Test Coverage ≥90% | REQUIRED | Enforced for all security-sensitive code paths |

**Complexity Justification**:

| Item | Why Needed | Simpler Alternative Rejected Because |
|------|-----------|-------------------------------------|
| Token tables use hard-delete for expired records | Token tables grow unboundedly; expired tokens carry no audit value (expiry itself is the fact) | Soft-delete on tokens would require periodic cleanup + index bloat |
| Separate `UserCredentials` table | Isolates credential data from identity data; credentials have a different lifecycle and access pattern | Embedding in `User` table would violate Single Responsibility and expose credential hash in every user query |
| `AuditLog` is append-only (no soft-delete) | Audit records are immutable by design (SOC2/ISO 27001 compliance) | Soft-delete on audit records would defeat their purpose |

---

## Project Structure

### Documentation (this feature)

```text
specs/002-auth-identity/
├── plan.md              # This file
├── research.md          # Technology decisions and rationale
├── data-model.md        # Entity definitions and relationships
├── quickstart.md        # Developer setup guide
└── tasks.md             # Testable implementation tasks
```

### Source Code Layout

```text
backend/
├── modules/
│   └── auth/
│       ├── __init__.py
│       ├── router.py                          # FastAPI router: /api/v1/auth/*
│       ├── models/
│       │   ├── __init__.py
│       │   ├── user.py                        # User ORM model
│       │   ├── user_credential.py             # UserCredentials ORM model
│       │   ├── session.py                     # Session ORM model
│       │   ├── refresh_token.py               # RefreshToken ORM model
│       │   ├── password_reset_token.py        # PasswordResetToken ORM model
│       │   ├── email_verification_token.py    # EmailVerificationToken ORM model
│       │   └── audit_log.py                   # AuditLog ORM model
│       ├── repositories/
│       │   ├── __init__.py
│       │   ├── user_repository.py
│       │   ├── user_credential_repository.py
│       │   ├── session_repository.py
│       │   ├── refresh_token_repository.py
│       │   ├── password_reset_token_repository.py
│       │   ├── email_verification_token_repository.py
│       │   └── audit_log_repository.py
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── auth.py                        # Login, Refresh, Logout, Token response schemas
│       │   ├── password.py                    # ForgotPassword, ResetPassword, ChangePassword schemas
│       │   └── user.py                        # CurrentUser response schema
│       └── services/
│           ├── __init__.py
│           ├── auth_service.py                # Login, logout, refresh, /me orchestration
│           ├── password_service.py            # Argon2 hashing, password history, complexity
│           ├── jwt_service.py                 # JWT creation and validation
│           ├── token_service.py               # Refresh token and reset token lifecycle
│           └── audit_service.py              # Structured audit event emission
│
├── core/
│   ├── auth/
│   │   ├── interfaces.py                      # EXISTING — CurrentUser, SessionContext (unchanged)
│   │   ├── dependencies.py                    # REPLACE STUBS — real get_current_user, require_authenticated
│   │   └── exceptions.py                      # AuthenticationException, AccountLockedException, etc.
│   ├── middleware/
│   │   ├── auth_hook.py                       # EXISTING — extend to set real CurrentUser on request.state
│   │   └── security_headers.py                # NEW — Content-Security-Policy, X-Frame-Options, etc.
│   └── config/
│       └── settings.py                        # EXTEND — add JWT, Argon2, lockout, rate-limit settings
│
└── migrations/
    └── versions/
        └── 002_auth_identity.py               # Alembic migration: all auth tables

frontend/
├── src/
│   ├── app/
│   │   ├── (auth)/                            # Auth route group — no AppLayout
│   │   │   ├── layout.tsx                     # Minimal centered layout for auth pages
│   │   │   ├── login/
│   │   │   │   └── page.tsx
│   │   │   ├── forgot-password/
│   │   │   │   └── page.tsx
│   │   │   └── reset-password/
│   │   │       └── page.tsx
│   │   └── (protected)/                       # Protected route group — AppLayout + route guard
│   │       └── layout.tsx                     # Wraps existing AppLayout, enforces auth
│   ├── contexts/
│   │   └── AuthContext.tsx                    # Authentication context provider
│   ├── hooks/
│   │   ├── useAuth.ts                         # Auth state, login, logout actions
│   │   └── useTokenRefresh.ts                 # Automatic token refresh timer
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts                      # EXTEND — attach Authorization header, intercept 401
│   │   │   └── auth.ts                        # Auth API functions (login, refresh, logout, etc.)
│   │   └── auth/
│   │       └── tokenStorage.ts                # Encapsulated token read/write (localStorage + memory)
│   └── components/
│       └── auth/
│           ├── LoginForm.tsx
│           ├── ForgotPasswordForm.tsx
│           └── ResetPasswordForm.tsx
```

---

## 1. Purpose

Epic 002 replaces the authentication stubs introduced in Epic 001 with a complete, production-grade identity and session management system. The engineering objective is to:

1. Implement the full authentication lifecycle: login → session creation → token refresh → logout → revocation.
2. Deliver a secure credential subsystem: Argon2id hashing, password history, complexity enforcement, and self-service recovery.
3. Establish `CurrentUser` as the platform-wide identity anchor that all future Epic services will consume.
4. Wire the frontend with persistent, auto-refreshing sessions and protected route guards.
5. Build an immutable audit trail for all security-significant events.

---

## 2. Scope

### In Scope

| Area | Implementation Deliverable |
|------|---------------------------|
| Auth database entities | 7 ORM models + 1 Alembic migration |
| Authentication APIs | `/auth/login`, `/auth/logout`, `/auth/refresh`, `/auth/me` |
| Password lifecycle APIs | `/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password` |
| Email verification | `/auth/verify-email` endpoint (token consumed; email delivery stubbed) |
| Auth middleware | Real `get_current_user` dependency replacing stubs in `core/auth/` |
| Rate limiting | SlowAPI on all auth endpoints |
| Security headers | Middleware for HSTS, CSP, X-Frame-Options, etc. |
| Audit logging | Structured `AuditLog` records for all security events |
| Frontend auth pages | Login, Forgot Password, Reset Password |
| Frontend session | `AuthContext`, `useAuth`, auto-refresh, route guards |
| Epic 001 stub replacement | `get_current_user_stub` and `require_authenticated_stub` replaced |

### Out of Scope

| Excluded | Deferred To |
|----------|------------|
| RBAC / Permissions | Epic 003 |
| Company / Tenant management | Epic 003 |
| Multi-tenant isolation logic | Epic 003 |
| User invitation flows | Epic 003 |
| MFA (TOTP, SMS) | Future |
| OAuth2 / Social login | Future |
| SAML / LDAP / SSO | Future |
| Admin user management UI | Future |
| Email delivery (real SMTP) | Epic 003 or Infrastructure Epic |

---

## 3. Implementation Principles

| Principle | Application in Epic 002 |
|-----------|------------------------|
| **Clean Architecture** | HTTP concerns stay in routers; business rules in services; SQL in repositories; no cross-layer leakage |
| **Separation of Concerns** | `JWTService` owns token creation/validation only; `PasswordService` owns hashing only; `AuthService` orchestrates |
| **SOLID — Single Responsibility** | Each service, repository, and module has one reason to change |
| **SOLID — Dependency Inversion** | Services depend on repository interfaces, not concrete implementations; FastAPI DI injects all dependencies |
| **Security First** | Argon2id params exceed OWASP minimums; tokens are rotated and hashed at rest; all failures are logged before any error response |
| **Reuse Existing Foundation** | `BaseRepository`, `BaseService`, `ApplicationException`, `Settings`, logging, middleware chain — all reused |
| **Backward Compatibility** | Epic 001 public interface (health checks, router, middleware chain) untouched; only stubs are replaced |
| **Testability** | All services are injectable; repositories accept a `Session` parameter; no static state; no direct DB calls in tests via fixtures |
| **Smallest Viable Change** | No refactoring of Epic 001 code beyond stub replacement; no speculative abstractions |

---

## 4. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND (Next.js 16+ / React 19)                              │
│                                                                  │
│  Auth Pages          Protected Pages                            │
│  /login              /(protected)/**                            │
│  /forgot-password    Route Guard (layout.tsx)                   │
│  /reset-password     AuthContext Provider                       │
│           │                    │                                │
│           └────────────────────┘                                │
│                      │                                          │
│              API Client (axios/fetch)                           │
│              ├── Attach Bearer token (interceptor)              │
│              └── 401 → trigger refresh → retry                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS (JSON)
┌────────────────────────────▼────────────────────────────────────┐
│  API LAYER (FastAPI)                                             │
│                                                                  │
│  SecurityHeadersMiddleware                                       │
│  RequestIDMiddleware (Epic 001)                                  │
│  AuthHookMiddleware (extended)                                   │
│                                                                  │
│  /api/v1/auth/  ──── AuthRouter                                 │
│                       └── Rate limiter (SlowAPI)                │
│                       └── Pydantic request validation           │
│                       └── FastAPI Dependency Injection          │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  APPLICATION SERVICES (modules/auth/services/)                   │
│                                                                  │
│  AuthService          PasswordService     JWTService            │
│  ├── login()          ├── hash()          ├── create_access()   │
│  ├── logout()         ├── verify()        ├── create_refresh()  │
│  ├── refresh()        ├── check_history() └── decode()          │
│  ├── me()             └── enforce_policy()                      │
│  ├── forgot_password()                                           │
│  └── reset_password() TokenService        AuditService          │
│                        ├── create_reset() └── emit()            │
│                        ├── consume_reset()                       │
│                        └── rotate_refresh()                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  REPOSITORIES (modules/auth/repositories/)                       │
│                                                                  │
│  UserRepository           RefreshTokenRepository                │
│  UserCredentialRepository PasswordResetTokenRepository          │
│  SessionRepository        EmailVerificationTokenRepository      │
│                           AuditLogRepository                    │
│                                                                  │
│  All extend BaseRepository — SQLAlchemy 2.x core queries        │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│  DATABASE (PostgreSQL 16 LTS)                                    │
│                                                                  │
│  users                    refresh_tokens                        │
│  user_credentials         password_reset_tokens                 │
│  sessions                 email_verification_tokens             │
│                           audit_logs                            │
└─────────────────────────────────────────────────────────────────┘
```

**Layer Responsibilities**:

| Layer | Responsibility |
|-------|---------------|
| **Frontend Pages** | Render auth UI; delegate all logic to hooks and API client |
| **AuthContext** | Single source of truth for auth state (user, isAuthenticated, isLoading) |
| **API Client** | Attach JWT, intercept 401, trigger refresh, retry request |
| **FastAPI Router** | Parse HTTP request, call service, serialize response, apply rate limits |
| **Middleware** | Cross-cutting: request ID, security headers, auth hook |
| **Services** | Business rules, orchestration, exception generation |
| **Repositories** | SQL queries; no business logic; always scoped by tenant |
| **Database** | Persist state; enforce constraints; generate UUIDs server-side |

---

## 5. Module Breakdown

### Backend Modules

#### `modules/auth/services/auth_service.py` — `AuthService`
- Orchestrates the complete login workflow: email lookup → status check → password verify → lockout evaluation → token issuance → session creation → audit emit
- Implements logout: token revocation → session update → audit emit
- Implements token refresh: token lookup → validation → atomic rotation → new JWT issuance → audit emit
- Implements `/me`: JWT extraction → user lookup → response serialization
- Depends on: `UserRepository`, `SessionRepository`, `PasswordService`, `JWTService`, `TokenService`, `AuditService`

#### `modules/auth/services/password_service.py` — `PasswordService`
- Wraps `argon2-cffi` for Argon2id hashing and verification
- Enforces password complexity policy (length, uppercase, lowercase, digit, special character)
- Implements password history check: hashes new password against last N stored hashes
- Implements change password: current password verification → history check → hash → credential update → session revocation
- Implements forgot/reset password: token generation → token storage → (stubbed) email delivery → token consumption → credential update
- Depends on: `UserCredentialRepository`, `TokenService`, `AuditService`

#### `modules/auth/services/jwt_service.py` — `JWTService`
- Stateless service; no repository dependency
- Creates signed JWT access tokens with claims: `sub` (user_id), `email`, `jti` (JWT ID), `iat`, `exp`, `iss`
- Validates JWT: signature, expiry, issuer — raises `AuthenticationException` on any failure
- Reads secret and algorithm from `Settings`; never stores secrets as class state

#### `modules/auth/services/token_service.py` — `TokenService`
- Generates cryptographically secure opaque refresh tokens via `secrets.token_urlsafe(64)`
- Stores SHA-256 hash of refresh token (raw token never persisted)
- Implements atomic rotation: within a single database transaction, mark old token revoked and insert new token record
- Generates cryptographically secure password reset tokens (32 bytes)
- Generates email verification tokens
- Depends on: `RefreshTokenRepository`, `PasswordResetTokenRepository`, `EmailVerificationTokenRepository`

#### `modules/auth/services/audit_service.py` — `AuditService`
- Emits structured `AuditLog` records for every security-significant event
- Non-blocking: audit write failures log a warning but do not raise exceptions or block the caller
- Event types: `LOGIN_SUCCESS`, `LOGIN_FAILURE`, `LOGOUT`, `TOKEN_REFRESHED`, `ACCOUNT_LOCKED`, `PASSWORD_CHANGED`, `PASSWORD_RESET_REQUESTED`, `PASSWORD_RESET_COMPLETED`, `EMAIL_VERIFIED`
- Captures: `user_id`, `event_type`, `ip_address`, `user_agent`, `request_id`, `outcome`, `reason`, `metadata`
- Depends on: `AuditLogRepository`

#### `core/auth/dependencies.py` — Real Auth Dependencies
- Replaces `get_current_user_stub` and `require_authenticated_stub` from Epic 001
- `get_current_user(request)`: extracts `Authorization: Bearer <token>` header → calls `JWTService.decode()` → loads user from `UserRepository` → checks account status → returns `CurrentUser`
- `require_authenticated(request)`: calls `get_current_user`; raises `UnauthorizedException` if not authenticated
- Wired into `AuthHookMiddleware` to populate `request.state.user` for downstream services

#### `core/auth/exceptions.py` — Auth Exception Classes
Extends `ApplicationException` with:
- `AuthenticationException` (401) — invalid credentials, invalid token
- `AccountLockedException` (423) — account locked with unlock ETA
- `AccountInactiveException` (403) — account inactive or deleted
- `TokenExpiredException` (401) — token expired
- `TokenRevokedException` (401) — token revoked
- `InvalidTokenException` (400) — malformed or consumed one-time token

#### `modules/auth/repositories/` — Repository Layer
All auth repositories extend `BaseRepository` where applicable. Token repositories implement custom methods suited to their entity:
- `UserRepository`: `find_by_email()`, `update_failed_login_count()`, `lock_account()`, `unlock_account()`
- `UserCredentialRepository`: `get_by_user_id()`, `update_password_hash()`, `add_to_history()`
- `SessionRepository`: `create_session()`, `get_active_by_user()`, `revoke_session()`, `revoke_all_by_user()`
- `RefreshTokenRepository`: `find_by_token_hash()`, `revoke()`, `revoke_all_by_user()`, `delete_expired()`
- `PasswordResetTokenRepository`: `find_by_token_hash()`, `mark_consumed()`, `delete_expired()`
- `AuditLogRepository`: `create()`, `list_by_user_id()` (append-only; no update/delete methods)

#### `modules/auth/router.py` — Auth Router
- Registered at `/api/v1/auth/`
- Applies SlowAPI rate limiting per endpoint
- Public endpoints: `POST /login`, `POST /refresh`, `POST /forgot-password`, `POST /reset-password`, `POST /verify-email`
- Protected endpoints: `POST /logout`, `POST /change-password`, `GET /me`
- Thin: delegates entirely to service; converts exceptions to HTTP responses via global exception handler

### Frontend Modules

#### `contexts/AuthContext.tsx`
- React Context providing: `{ user, isAuthenticated, isLoading, login, logout, refreshToken }`
- Wraps the application root; all protected pages consume via `useAuth()`
- On mount: reads stored tokens → calls `/me` to hydrate user state → sets `isLoading = false`
- On login: stores tokens → sets user state
- On logout: clears tokens → calls logout API → resets state

#### `hooks/useAuth.ts`
- Consumer hook for `AuthContext`; throws if used outside provider
- Exposes typed auth state and actions to components

#### `hooks/useTokenRefresh.ts`
- Schedules automatic access token refresh at 80% of token lifetime (12 minutes for 15-minute tokens)
- Uses `setTimeout` in browser; cleared on logout or unmount
- On refresh failure: clears state, redirects to login

#### `lib/auth/tokenStorage.ts`
- Encapsulates all token I/O; no component writes tokens directly
- Access token: stored in memory (`React.useRef` / module-level variable) to prevent XSS access
- Refresh token: stored in `localStorage` (HttpOnly cookie preferred but requires backend coordination — see Security Strategy)
- Exposes: `storeTokens()`, `getAccessToken()`, `getRefreshToken()`, `clearTokens()`

#### `lib/api/client.ts` (extended from Epic 001)
- Request interceptor: reads access token from `tokenStorage` and attaches `Authorization: Bearer <token>`
- Response interceptor: on 401 with `code: TOKEN_EXPIRED`, calls refresh endpoint → retries original request once → on refresh failure, calls `AuthContext.logout()`

#### `app/(auth)/` — Auth Route Group
- Separate Next.js route group with a minimal centered layout (no sidebar, no header)
- `login/page.tsx`: Renders `LoginForm` inside an auth card layout
- `forgot-password/page.tsx`: Renders `ForgotPasswordForm`
- `reset-password/page.tsx`: Reads `?token=` from URL params, renders `ResetPasswordForm`

#### `app/(protected)/layout.tsx` — Route Guard
- Server component that reads auth state; if not authenticated, redirects to `/login`
- Client-side guard via `useAuth()` for SPA navigation

#### Auth Form Components
- `LoginForm.tsx`: React Hook Form + Zod validation; email/password fields; remember_me checkbox; error display; loading state
- `ForgotPasswordForm.tsx`: Email field; success confirmation state (masked to prevent enumeration)
- `ResetPasswordForm.tsx`: New password + confirm; token extracted from URL param; success redirect to login

---

## 6. Database Strategy

### Entity Overview

| Entity | Table Name | Primary Purpose |
|--------|-----------|----------------|
| User | `users` | Identity anchor; account status; lockout metadata |
| UserCredentials | `user_credentials` | Argon2id hash + password history; isolated from User |
| Session | `sessions` | Active session metadata per device/login event |
| RefreshToken | `refresh_tokens` | Hashed opaque tokens; rotation lifecycle |
| PasswordResetToken | `password_reset_tokens` | Single-use reset tokens with 1-hour expiry |
| EmailVerificationToken | `email_verification_tokens` | Single-use verification tokens with 24-hour expiry |
| AuditLog | `audit_logs` | Immutable, append-only security event log |

### Entity Relationships

```
users ──────────────────────── user_credentials  (1:1)
users ──────────────────────── sessions          (1:N)
users ──────────────────────── refresh_tokens    (1:N)
users ──────────────────────── password_reset_tokens (1:N, only active matters)
users ──────────────────────── email_verification_tokens (1:1 active)
users ──────────────────────── audit_logs        (1:N, nullable user_id for pre-auth events)
sessions ───────────────────── refresh_tokens    (1:1)
```

### Key Design Decisions

**`users` table**:
- Extends `BaseModel` (id, created_at, updated_at) — NOT `TenantBaseModel`; users exist before company assignment
- `company_id` is nullable UUID FK (forward-compatible with Epic 003 tenant resolution)
- `account_status` enum: `active`, `inactive`, `locked`, `deleted`
- `failed_login_count` and `locked_until` stored on user for lockout logic
- Email column: unique index; lowercase-normalized at service layer before write

**`user_credentials` table**:
- Separate from `users` to prevent credential hash from appearing in any user listing query
- `password_hash` stores Argon2id encoded string (algorithm params embedded)
- `password_history` JSONB column stores array of last N hashes (default: last 5)
- `last_changed_at` timestamp enables future password expiry policies

**`sessions` table**:
- One session per login event; linked to a single refresh token
- `device_info` JSONB captures user-agent parsed fields (browser, OS)
- `ip_address` INET type in PostgreSQL
- `is_revoked` flag; `revoked_at` timestamp

**`refresh_tokens` table**:
- `token_hash` column (SHA-256 of raw token, hex-encoded); never stores raw token
- `expires_at` indexed for expired token cleanup
- `is_revoked` flag; set atomically during rotation
- Hard-delete of expired rows via scheduled cleanup (no soft-delete)

**`password_reset_tokens` / `email_verification_tokens`**:
- Same pattern: `token_hash`, `expires_at`, `is_consumed`, `consumed_at`
- Hard-delete of expired rows; only one active token per user per type enforced at service layer

**`audit_logs` table**:
- Append-only; no `updated_at`; no soft-delete
- `user_id` nullable (pre-authentication events don't have a user)
- `metadata` JSONB for event-specific details (e.g., lockout threshold reached)
- Indexed on `(user_id, created_at)` for time-range queries

### Indexing Strategy

| Table | Index | Purpose |
|-------|-------|---------|
| `users` | `UNIQUE (email)` | Login lookup; anti-enumeration guard |
| `users` | `(account_status, locked_until)` | Lockout expiry queries |
| `refresh_tokens` | `UNIQUE (token_hash)` | O(1) token lookup on refresh |
| `refresh_tokens` | `(user_id, is_revoked)` | Revoke all by user |
| `refresh_tokens` | `(expires_at)` | Expired token cleanup |
| `sessions` | `(user_id, is_revoked)` | Active session listing |
| `password_reset_tokens` | `UNIQUE (token_hash)` | O(1) token lookup |
| `password_reset_tokens` | `(user_id, is_consumed, expires_at)` | Active token lookup |
| `audit_logs` | `(user_id, created_at DESC)` | Time-range audit queries |
| `audit_logs` | `(event_type, created_at DESC)` | Event-type filtering |

### Migration Strategy

- Single Alembic migration file: `002_auth_identity.py`
- Creates all 7 tables in dependency order (users → credentials → sessions/tokens → audit_logs)
- All migrations are idempotent (`CREATE TABLE IF NOT EXISTS` pattern via Alembic `op`)
- Rollback: `downgrade()` drops tables in reverse dependency order
- Executed via `alembic upgrade head` in Docker entrypoint; same as Epic 001

### Token Lifecycle

```
RefreshToken lifecycle:
  Created at login → Active → Rotated (revoked + new created atomically) → Expired or Revoked

PasswordResetToken lifecycle:
  Created at forgot-password → Pending (1hr) → Consumed or Expired → Hard-deleted

EmailVerificationToken lifecycle:
  Created at user creation → Pending (24hr) → Consumed → Hard-deleted
```

---

## 7. Authentication Workflow

### 7.1 Login Sequence

```
Client                       AuthRouter            AuthService        DB
  │                               │                     │              │
  │─── POST /auth/login ─────────▶│                     │              │
  │     {email, password,         │                     │              │
  │      remember_me?}            │                     │              │
  │                               │─── login() ────────▶│              │
  │                               │                     │─ find_by_email ▶│
  │                               │                     │◀─ user / None ──│
  │                               │               [Not found]            │
  │                               │                     │─ emit LoginFailure │
  │◀── 401 "Invalid credentials" ─│◀────────────────────│              │
  │                               │               [Found: check status]  │
  │                               │                     │ [Locked] → 423 │
  │                               │                     │ [Inactive] → 403 │
  │                               │               [Active: verify password] │
  │                               │                     │─ verify_hash() │
  │                               │               [Mismatch]            │
  │                               │                     │─ increment_failed_count │
  │                               │                     │ [Threshold reached] → lock_account │
  │                               │                     │─ emit LoginFailure / AccountLocked │
  │◀── 401 "Invalid credentials" ─│◀────────────────────│              │
  │                               │               [Match: issue tokens] │
  │                               │                     │─ reset_failed_count │
  │                               │                     │─ create JWT access token │
  │                               │                     │─ create opaque refresh token │
  │                               │                     │─ hash refresh token │
  │                               │                     │─ create Session record │
  │                               │                     │─ store RefreshToken record │
  │                               │                     │─ emit LoginSuccess │
  │◀── 200 {access_token, ────────│◀────────────────────│              │
  │         refresh_token,        │                     │              │
  │         token_type,           │                     │              │
  │         expires_in}           │                     │              │
```

### 7.2 Token Refresh Sequence

```
Client                       AuthRouter            AuthService        TokenService   DB
  │                               │                     │                 │            │
  │─── POST /auth/refresh ───────▶│                     │                 │            │
  │     {refresh_token}           │                     │                 │            │
  │                               │─── refresh() ──────▶│                 │            │
  │                               │                     │─ hash(token) ───▶            │
  │                               │                     │─ find_by_hash ──────────────▶│
  │                               │                     │◀─ token record / None ───────│
  │                               │               [Not found / Revoked / Expired]      │
  │◀── 401 Unauthorized ──────────│◀────────────────────│                 │            │
  │                               │               [Valid: check user status]           │
  │                               │                     │─ get_user() ────────────────▶│
  │                               │               [Inactive/Locked] → 401/403          │
  │                               │               [Active: atomic rotation]            │
  │                               │                     │─ BEGIN TRANSACTION           │
  │                               │                     │─ revoke old token ──────────▶│
  │                               │                     │─ create new token ──────────▶│
  │                               │                     │─ COMMIT                      │
  │                               │                     │─ create new JWT              │
  │                               │                     │─ emit TokenRefreshed         │
  │◀── 200 {access_token, ────────│◀────────────────────│                 │            │
  │         refresh_token,        │                     │                 │            │
  │         expires_in}           │                     │                 │            │
```

### 7.3 Authenticated Request Sequence

```
Client                  SecurityMiddleware      AuthDependency        UserRepository
  │                           │                      │                     │
  │─ GET /api/v1/*** ────────▶│                      │                     │
  │  Authorization: Bearer JWT│                      │                     │
  │                           │─ next() ────────────▶│                     │
  │                           │               [get_current_user called]    │
  │                           │                      │─ extract Bearer ─▶  │
  │                           │                      │─ JWTService.decode()│
  │                           │               [Invalid/Expired] → 401      │
  │                           │               [Valid: load user]           │
  │                           │                      │─ find_by_id() ─────▶│
  │                           │               [Locked/Inactive] → 401/403  │
  │                           │               [Active] ──────────────────▶ route handler
```

### 7.4 Logout Sequence

```
Client                       AuthRouter            AuthService        DB
  │                               │                     │              │
  │─── POST /auth/logout ────────▶│                     │              │
  │     Authorization: Bearer JWT │                     │              │
  │                               │─ require_auth dep ─▶│              │
  │                               │                     │─ get CurrentUser │
  │                               │─── logout() ───────▶│              │
  │                               │                     │─ find active sessions │
  │                               │                     │─ revoke refresh tokens │
  │                               │                     │─ revoke sessions │
  │                               │                     │─ emit Logout event │
  │◀── 204 No Content ────────────│◀────────────────────│              │
```

### 7.5 Password Reset Sequence

```
Client                       AuthRouter            AuthService / TokenService   DB   EmailService
  │                               │                           │                  │       │
  │─── POST /forgot-password ────▶│                           │                  │       │
  │     {email}                   │                           │                  │       │
  │                               │─── forgot_password() ────▶│                  │       │
  │                               │                           │─ find_by_email ─▶│       │
  │                               │                   [Not found: still 200]     │       │
  │                               │                   [Found: generate token]    │       │
  │                               │                           │─ secrets.token_urlsafe │  │
  │                               │                           │─ hash token ────▶│       │
  │                               │                           │─ store reset token │     │
  │                               │                           │─ emit ResetRequested │   │
  │                               │                           │─ send_email() (stub) ───▶│
  │◀── 200 (always) ──────────────│◀──────────────────────────│                  │       │
  │                               │                           │                  │       │
  │─── POST /reset-password ─────▶│                           │                  │       │
  │     {token, new_password}     │                           │                  │       │
  │                               │─── reset_password() ─────▶│                  │       │
  │                               │                           │─ hash token ──── find ─▶│
  │                               │               [Not found/Expired/Consumed] → 400    │
  │                               │               [Valid: update credentials]    │       │
  │                               │                           │─ complexity check         │
  │                               │                           │─ history check ──────────▶│
  │                               │                           │─ update_password_hash ───▶│
  │                               │                           │─ mark_token_consumed ────▶│
  │                               │                           │─ revoke_all_refresh_tokens▶│
  │                               │                           │─ emit ResetCompleted      │
  │◀── 200 OK ─────────────────── │◀──────────────────────────│                  │       │
```

---

## 8. API Strategy

### Endpoint Classification

| Classification | Endpoints | Middleware Applied |
|---------------|-----------|-------------------|
| **Public** | `POST /login`, `POST /refresh`, `POST /forgot-password`, `POST /reset-password`, `POST /verify-email` | Rate limiter only |
| **Protected** | `POST /logout`, `POST /change-password`, `GET /me` | Rate limiter + `require_authenticated` dependency |

### Authentication Middleware Implementation

The `get_current_user` FastAPI dependency (in `core/auth/dependencies.py`) implements:

1. Extract `Authorization: Bearer <token>` header
2. Call `JWTService.decode(token)` — raises `AuthenticationException` on any JWT error
3. Extract `user_id` from JWT claims (`sub` field)
4. Load user from `UserRepository.get_by_id()` — database hit on every protected request
5. Check `account_status` — raise `AccountLockedException` or `AccountInactiveException` as appropriate
6. Return populated `CurrentUser` object
7. `AuthHookMiddleware` stores `CurrentUser` on `request.state.user`

**Database hit per request**: One `SELECT` on `users` per authenticated request. This is intentional — it ensures real-time account status enforcement (lockout, deactivation). Acceptable at target scale; cache layer added in future if needed.

### Rate Limiting Strategy (SlowAPI)

| Endpoint | Limit | Window | Key |
|----------|-------|--------|-----|
| `POST /login` | 5 requests | 15 minutes | IP |
| `POST /forgot-password` | 3 requests | 1 hour | IP |
| `POST /reset-password` | 5 requests | 1 hour | IP |
| `POST /refresh` | 20 requests | 1 minute | IP |
| `POST /change-password` | 5 requests | 15 minutes | user_id |
| `GET /me` | 60 requests | 1 minute | user_id |

### Exception Handling

All exceptions are caught by the Epic 001 global exception handler, which maps `ApplicationException` subclasses to structured `ErrorResponse` JSON with `code`, `message`, and optional `details`. No stack traces are returned to clients.

Auth-specific error codes returned to clients:

| Code | HTTP Status | Trigger |
|------|------------|---------|
| `INVALID_CREDENTIALS` | 401 | Login failure (email not found or password mismatch — same response) |
| `ACCOUNT_LOCKED` | 423 | Account locked; response includes `unlocks_at` ISO timestamp |
| `ACCOUNT_INACTIVE` | 403 | Account is inactive or pending |
| `TOKEN_EXPIRED` | 401 | JWT or refresh token expired |
| `TOKEN_REVOKED` | 401 | Refresh token already revoked |
| `INVALID_TOKEN` | 400 | Malformed or consumed reset/verify token |
| `UNAUTHORIZED` | 401 | No token provided on protected endpoint |

### Response Standardization

All responses use the Epic 001 `ApiResponse[T]` envelope:
```json
{
  "success": true,
  "data": { ... },
  "message": null,
  "request_id": "uuid"
}
```

Token responses include `access_token`, `refresh_token`, `token_type: "bearer"`, `expires_in` (seconds).

### Versioning

All auth endpoints are under `/api/v1/auth/`. Version prefix follows Epic 001 API versioning strategy. Breaking changes require a new version path.

---

## 9. Frontend Strategy

### Token Storage

| Token | Storage | Rationale |
|-------|---------|-----------|
| Access Token | In-memory (module-level variable) | Short-lived (15min); in-memory prevents XSS token theft from localStorage |
| Refresh Token | `localStorage` | Survives page reload; longer-lived; HttpOnly cookie requires backend CORS/cookie config |

**Note on HttpOnly cookies**: The preferred production strategy for refresh tokens is HttpOnly cookies, which eliminates XSS risk entirely. This requires the backend to `Set-Cookie` on login and read the cookie on refresh. If this approach is adopted, it is a backend-coordinated change tracked as a follow-up task. For this Epic, `localStorage` is used with clear documentation of the tradeoff.

### Login Flow

```
LoginForm
  │
  ├── React Hook Form + Zod schema validation (client-side)
  │
  ├── POST /api/v1/auth/login
  │     └── On success:
  │           ├── tokenStorage.storeTokens(access, refresh)
  │           ├── AuthContext.setUser(user from /me response)
  │           └── router.push('/dashboard')
  │     └── On error:
  │           ├── 401 → show "Invalid email or password"
  │           ├── 423 → show "Account locked. Try again at {unlocks_at}"
  │           └── 429 → show "Too many attempts. Please wait."
```

### Forgot Password Flow

```
ForgotPasswordForm
  ├── POST /api/v1/auth/forgot-password
  ├── Always show success confirmation (anti-enumeration)
  └── "If this email exists, you'll receive a reset link shortly."
```

### Reset Password Flow

```
ResetPasswordForm (page receives ?token= URL param)
  ├── React Hook Form + Zod (new password + confirm match)
  ├── POST /api/v1/auth/reset-password
  │     └── On success → redirect to /login with success toast
  │     └── On 400 (invalid/expired token) → show error, offer re-request
```

### Route Protection

Protected routes are under `app/(protected)/` route group. `layout.tsx` in this group:
1. Reads auth state from `AuthContext`
2. If `isLoading`: renders a full-screen skeleton/spinner
3. If `!isAuthenticated`: `router.replace('/login')`
4. If `isAuthenticated`: renders children

### Automatic Token Refresh

`useTokenRefresh` hook:
- Called once inside `AuthContext` provider
- Reads `expires_in` from last successful login/refresh response
- Schedules `setTimeout` at 80% of token lifetime (default: 12 minutes)
- On timer: calls `POST /auth/refresh` with stored refresh token
- On success: updates access token in memory, reschedules timer
- On failure: calls `logout()`, redirects to `/login`

### Session Persistence

On app mount (`AuthContext` `useEffect`):
1. Check `localStorage` for refresh token
2. If present: POST `/auth/refresh` to hydrate session (validates token is still alive)
3. On success: store new access token in memory, set user state
4. On failure: clear `localStorage`, user proceeds as unauthenticated

### Loading States

Every form uses React Hook Form `formState.isSubmitting` to disable the submit button during API calls. `AuthContext` exposes `isLoading` (true during session hydration on mount) to prevent flash of unauthenticated content.

---

## 10. Security Strategy

### Argon2id Password Hashing

- Library: `argon2-cffi` (Python bindings to argon2 reference implementation)
- Parameters: time_cost=3, memory_cost=64MB, parallelism=4 — meets OWASP 2024 recommendations
- Parameters are stored encoded in the hash string itself; future-proof for parameter upgrades
- `PasswordService.hash()` is the only code path that creates credential hashes; no other module hashes passwords

### JWT Implementation

- Library: `PyJWT` with RS256 algorithm (asymmetric keys preferred; HS256 acceptable for single-server)
- Claims: `sub` (user UUID string), `email`, `jti` (UUID), `iat`, `exp`, `iss` (configurable issuer)
- Secret: loaded from `Settings.JWT_SECRET_KEY`; validated non-empty at startup
- Access tokens are never persisted; verification is stateless
- `JWTService.decode()` validates signature, expiry, and issuer in one call; partial validation is not possible

### Refresh Token Rotation

- Raw token: `secrets.token_urlsafe(64)` (384 bits of entropy)
- Stored value: SHA-256 hex digest of raw token — raw token is ephemeral; never written to DB
- Rotation is performed inside a single SQLAlchemy transaction: `UPDATE (revoke old) + INSERT (new)` — both succeed or both roll back
- On revoked token reuse (possible theft): revoke all tokens for the user, emit audit event, return 401

### Password History

- Last N hashes stored in `user_credentials.password_history` JSONB array (default N=5)
- On password change: verify new password against each historical hash using `argon2.verify()`
- Old hashes are not re-hashed with current parameters (acceptable; they are comparison-only)

### Account Lockout

- Failed login counter: `users.failed_login_count` incremented on every mismatch
- Threshold reached: `account_status = locked`, `locked_until = now() + 30min`
- Locked account check runs before password verification (prevent timing oracle)
- Auto-unlock: `locked_until` compared at login; if expired, status reset to `active`
- Counter reset on successful login

### Rate Limiting

- SlowAPI (Starlette-compatible wrapper for `slowapi`/`limits`)
- Storage backend: in-memory for development; Redis-compatible in production
- Rate limit hit returns 429 with `Retry-After` header
- Rate limiting is a defense layer supplementing account lockout — both must be present

### Security Headers Middleware

New `SecurityHeadersMiddleware` in `core/middleware/security_headers.py` sets on every response:
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy: default-src 'self'` (relaxed as needed per Next.js requirements)
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`

### Audit Logging

- All writes happen after the primary operation succeeds (fire-and-forget best-effort)
- Failed audit writes log `ERROR` level but do not propagate
- Audit records are committed in a separate `Session` to ensure independence from primary transaction
- Audit log table has no `UPDATE` or `DELETE` permissions granted to the application DB user (enforced at PostgreSQL level)

### CSRF Considerations

- Auth endpoints use `Authorization: Bearer` header for authentication, not cookies
- Bearer header tokens are not automatically sent by browsers, making CSRF attacks ineffective
- If `HttpOnly` cookie approach is adopted for refresh tokens: CSRF token required on state-changing endpoints

### XSS Mitigation

- Access token in memory (not localStorage) eliminates primary XSS token theft vector
- Content-Security-Policy header limits script execution sources
- All user-supplied input is validated by Pydantic v2 before reaching business logic
- Pydantic email validation normalizes email to lowercase before storage

---

## 11. Implementation Phases

### Phase 1 — Infrastructure & Configuration

**Objective**: Extend Epic 001 settings and middleware; add new dependencies.

**Deliverables**:
- Add `pyproject.toml`/`requirements` entries: `argon2-cffi`, `PyJWT`, `slowapi`
- Extend `Settings` with auth config: `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, `JWT_REFRESH_TOKEN_EXPIRE_DAYS`, `JWT_REMEMBER_ME_EXPIRE_DAYS`, `ARGON2_TIME_COST`, `ARGON2_MEMORY_COST`, `ARGON2_PARALLELISM`, `AUTH_LOCKOUT_THRESHOLD`, `AUTH_LOCKOUT_WINDOW_MINUTES`, `AUTH_LOCKOUT_DURATION_MINUTES`, `PASSWORD_HISTORY_COUNT`, `AUDIT_LOG_RETENTION_DAYS`
- Create `core/auth/exceptions.py` with auth exception hierarchy
- Create `core/middleware/security_headers.py`
- Register `SecurityHeadersMiddleware` in `main.py`

**Dependencies**: Epic 001 complete.

---

### Phase 2 — Database Models & Migration

**Objective**: Create all 7 ORM models and the Alembic migration.

**Deliverables**:
- `modules/auth/models/user.py` — `User` ORM model
- `modules/auth/models/user_credential.py` — `UserCredentials` ORM model
- `modules/auth/models/session.py` — `Session` ORM model
- `modules/auth/models/refresh_token.py` — `RefreshToken` ORM model
- `modules/auth/models/password_reset_token.py` — `PasswordResetToken` ORM model
- `modules/auth/models/email_verification_token.py` — `EmailVerificationToken` ORM model
- `modules/auth/models/audit_log.py` — `AuditLog` ORM model
- `migrations/versions/002_auth_identity.py` — complete migration with `upgrade()` and `downgrade()`
- `alembic upgrade head` verified in Docker Compose environment

**Dependencies**: Phase 1.

---

### Phase 3 — Repositories

**Objective**: Implement data access layer for all auth entities.

**Deliverables**:
- All 7 repository classes in `modules/auth/repositories/`
- Unit tests for each repository using test database fixtures
- `UserRepository.find_by_email()` with timing-safe behavior
- `RefreshTokenRepository` atomic rotation support (transaction-aware)
- `AuditLogRepository` with append-only enforcement

**Dependencies**: Phase 2.

---

### Phase 4 — Services

**Objective**: Implement all business logic services.

**Deliverables**:
- `JWTService`: create and decode JWT access tokens
- `PasswordService`: Argon2id hash/verify, complexity enforcement, history check
- `TokenService`: refresh token lifecycle, reset token lifecycle, email verification token lifecycle
- `AuditService`: emit all event types
- `AuthService`: login, logout, refresh, me, forgot-password, reset-password, change-password flows
- Unit tests for all services with mocked repositories
- Integration tests for complete auth flows

**Dependencies**: Phase 3.

---

### Phase 5 — Auth Dependencies & Middleware

**Objective**: Replace Epic 001 stubs with real auth dependency.

**Deliverables**:
- `core/auth/dependencies.py`: real `get_current_user` and `require_authenticated` implementations
- Update `AuthHookMiddleware` to call real dependency and populate `request.state.user`
- Verify existing health check and other Epic 001 endpoints remain unaffected
- Tests: protected endpoint returns 401 without token; returns 200 with valid token

**Dependencies**: Phase 4.

---

### Phase 6 — Auth API Router

**Objective**: Wire all auth endpoints.

**Deliverables**:
- `modules/auth/router.py` with all 8 endpoints
- Pydantic schemas for all request/response types
- SlowAPI rate limiters applied
- Router registered in `api/v1/router.py`
- API integration tests (using `httpx.AsyncClient`) for all endpoints covering happy path and key error cases

**Dependencies**: Phase 5.

---

### Phase 7 — Frontend Authentication

**Objective**: Deliver auth pages, context, and session management.

**Deliverables**:
- `tokenStorage.ts` — token read/write abstraction
- `lib/api/auth.ts` — typed auth API functions
- Extend `lib/api/client.ts` — request/response interceptors
- `AuthContext.tsx` and `useAuth.ts`
- `useTokenRefresh.ts` — auto-refresh timer
- `app/(auth)/` route group and three auth pages with form components
- `app/(protected)/layout.tsx` route guard
- Frontend component tests for LoginForm, ForgotPasswordForm, ResetPasswordForm
- E2E test: login → access protected page → refresh → logout

**Dependencies**: Phase 6.

---

### Phase 8 — Integration, Security Validation & Hardening

**Objective**: Validate complete system; run security checks; fix gaps.

**Deliverables**:
- End-to-end auth flow manual validation (login → refresh → logout)
- Security header validation (browser DevTools + automated check)
- Rate limiter integration tests
- Account lockout integration test
- Password history integration test
- Audit log completeness validation
- Performance validation: login p95, refresh p95, /me p95 within budgets
- Bandit security scan on backend auth code
- Dependency vulnerability scan (`pip-audit`, `npm audit`)
- Final Docker Compose smoke test

**Dependencies**: Phase 7.

---

## 12. Testing Strategy

### Backend Unit Tests

Located in `backend/tests/unit/modules/auth/`:

| What | Tool | Coverage Target |
|------|------|----------------|
| `JWTService` — token creation, decode, expiry, invalid signature | pytest | 100% |
| `PasswordService` — hash, verify, complexity rules, history | pytest | 100% |
| `TokenService` — token generation, hashing, rotation logic | pytest | 100% |
| `AuthService` — login (happy + 5 failure paths), logout, refresh, reset | pytest | ≥90% |
| `AuditService` — event emission, failure isolation | pytest | ≥90% |
| Exception classes — correct HTTP status codes | pytest | 100% |

### Repository Tests

Located in `backend/tests/integration/repositories/auth/`:

| What | Tool | Approach |
|------|------|---------|
| `UserRepository` — CRUD, find_by_email, lockout ops | pytest + real DB | Test database (Docker) |
| `RefreshTokenRepository` — create, find_by_hash, revoke, revoke_all | pytest + real DB | Transactional rollback per test |
| `AuditLogRepository` — append-only, time-range query | pytest + real DB | |
| All other auth repositories | pytest + real DB | |

### API Integration Tests

Located in `backend/tests/integration/api/v1/auth/`:

| Scenario | Expected Outcome |
|----------|-----------------|
| Login with valid credentials | 200, tokens returned |
| Login with wrong password (1–4 times) | 401, counter incremented |
| Login with wrong password (5th time) | 423, account locked |
| Login with locked account | 423 immediately |
| Refresh with valid token | 200, new tokens, old token revoked |
| Refresh with expired token | 401 |
| Refresh with revoked token | 401 |
| Logout | 204, token revoked |
| GET /me with valid JWT | 200, user data |
| GET /me with expired JWT | 401 |
| Forgot password (existing email) | 200 |
| Forgot password (non-existing email) | 200 (same response) |
| Reset password with valid token | 200 |
| Reset password with expired token | 400 |
| Reset password with consumed token | 400 |
| Change password (correct current) | 200, sessions revoked |
| Change password (wrong current) | 401 |
| Rate limit exceeded on /login | 429 |

### Frontend Tests

| What | Tool |
|------|------|
| `LoginForm` — validation, submit, error display | React Testing Library + Jest |
| `ForgotPasswordForm` — submit, success state | React Testing Library + Jest |
| `ResetPasswordForm` — password match, submit | React Testing Library + Jest |
| `AuthContext` — state transitions, token storage | Jest (mocked API) |
| `useTokenRefresh` — timer scheduling | Jest (fake timers) |
| Route guard — redirect when unauthenticated | React Testing Library |

### Security Tests

| Test | Tool |
|------|------|
| Bandit static analysis on auth module | `bandit -r backend/modules/auth/` |
| Dependency vulnerability scan | `pip-audit`, `npm audit` |
| Password hash strength verification | Custom test asserting argon2 params |
| Anti-enumeration: login and forgot-password timing uniformity | pytest |
| Replay attack: reuse consumed reset token | pytest integration test |
| Concurrent refresh race condition | pytest with threading |

### Coverage Goals

| Scope | Target |
|-------|--------|
| `modules/auth/services/` | ≥90% line coverage |
| `core/auth/dependencies.py` | ≥90% line coverage |
| `modules/auth/repositories/` | ≥85% line coverage (DB-backed) |
| Frontend auth components | ≥80% line coverage |

---

## 13. Performance Strategy

### JWT Validation

- `JWTService.decode()` is a pure cryptographic operation; no I/O
- HS256 validation: ~0.1ms; RS256: ~1ms — both well within 10ms middleware budget
- No caching needed for access token validation (stateless by design)

### Argon2 Performance

- Argon2id with configured params takes 100–300ms per hash operation
- Login p95 budget is 800ms — accounts for Argon2 + DB + token creation
- `PasswordService.hash()` is called only on login and password change; not on token refresh or `/me`
- Params can be tuned via `Settings`; increased memory/time improves security at cost of throughput

### Connection Pooling

- SQLAlchemy connection pool configured via Epic 001 `engine.py`
- Pool size tuned for auth-heavy workloads: `pool_size=10`, `max_overflow=20`
- All auth repository operations use the request-scoped `Session` injected via FastAPI DI

### Token Lookup Performance

- Refresh token lookup is O(1): `SELECT WHERE token_hash = $1` using `UNIQUE` index
- Password reset token lookup: same pattern
- No full-table scans on auth hot paths

### Database Indexing

Covered in Database Strategy section. Key indexes:
- `UNIQUE (users.email)` — O(1) login lookup
- `UNIQUE (refresh_tokens.token_hash)` — O(1) refresh lookup
- `(audit_logs.user_id, created_at DESC)` — time-range audit queries

### Refresh Token Rotation — Concurrency

- Atomic transaction protects against duplicate refresh: first writer wins; second sees revoked token and returns 401
- No distributed lock required at target scale (PostgreSQL row-level locking is sufficient)
- Race condition handling: if rotation transaction fails, old token remains valid; client can retry

### API Response Time Targets

| Endpoint | p95 Target | Bottleneck |
|----------|-----------|-----------|
| `POST /login` | 800ms | Argon2 hashing |
| `POST /refresh` | 200ms | 2 DB writes (rotation) |
| `GET /me` | 100ms | 1 DB read |
| `POST /forgot-password` | 300ms | Email stub + 1 DB write |

### Caching Strategy

Authentication endpoints intentionally avoid response caching.

- `/login`
- `/refresh`
- `/logout`
- `/logout-all`
- `/change-password`

MUST return:
- The `/me` endpoint MAY use private client-side caching for a very short duration (maximum 30 seconds) but MUST NOT be cached by shared proxies.

---

## 14. Deployment Strategy

### Environment Variables

All auth configuration via environment variables (added to `.env.example`):

```
# JWT
JWT_SECRET_KEY=<min-32-char-random-string>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
JWT_REMEMBER_ME_EXPIRE_DAYS=30

# Argon2
ARGON2_TIME_COST=3
ARGON2_MEMORY_COST=65536
ARGON2_PARALLELISM=4

# Account lockout
AUTH_LOCKOUT_THRESHOLD=5
AUTH_LOCKOUT_WINDOW_MINUTES=15
AUTH_LOCKOUT_DURATION_MINUTES=30

# Password policy
PASSWORD_MIN_LENGTH=8
PASSWORD_HISTORY_COUNT=5

# Audit
AUDIT_LOG_RETENTION_DAYS=90
```

### Docker

- No new Dockerfile changes required; Epic 001 Dockerfile is sufficient
- New Python packages added to `pyproject.toml` and installed in the existing build stage
- `argon2-cffi` requires C compiler at build time (already satisfied in Python base image)

### Docker Compose

- No new services required for this Epic (no Redis for rate limiting in dev — in-memory SlowAPI)
- Rate limiting in production: add Redis service to `docker-compose.yml` and configure SlowAPI storage

### Alembic Migration Execution

- Migration runs automatically via `CMD` in Docker entrypoint: `alembic upgrade head && uvicorn main:app`
- Migration is idempotent; safe to re-run
- Migration order: `001_initial_baseline` → `002_auth_identity` (Alembic dependency chain)

### Production Secrets

- `JWT_SECRET_KEY` must be generated with sufficient entropy: `python -c "import secrets; print(secrets.token_urlsafe(64))"`
- Secret rotation: change `JWT_SECRET_KEY` → all existing access tokens become invalid → users refresh → if refresh token valid, new access token issued
- Refresh tokens are stored as hashes; changing the raw token secret does not invalidate them (they are opaque)
- DB credentials and JWT secret managed via Docker secrets or Kubernetes secrets in production

### Secret Rotation Strategy

Authentication secrets MUST support planned rotation without requiring application code changes.

- JWT signing keys SHOULD support key versioning (`kid` header) for future seamless rotation.
- New signing keys MUST be deployed before old keys are retired.
- Refresh token secrets (if used) SHOULD support dual-validation during migration.
- Password hashing parameters MAY be upgraded over time using lazy rehash during successful login.

### Health Checks

- Epic 001 health check endpoint (`GET /health`) remains unchanged
- Health check does not require authentication
- Add DB connectivity check in existing health endpoint (already present in Epic 001 if implemented)

### Logging & Monitoring

- All auth service operations log at `DEBUG` level with structured fields (via Epic 001 logging setup)
- Login failures log at `WARNING` level
- Account lockouts log at `WARNING` level
- Audit service failures log at `ERROR` level
- Sensitive data (passwords, raw tokens) must never appear in any log line

### Metrics

The authentication module SHOULD expose operational metrics suitable for Prometheus.

Recommended metrics:

- auth_login_total
- auth_login_failed_total
- auth_refresh_total
- auth_refresh_failed_total
- auth_lockout_total
- auth_password_reset_total
- auth_password_change_total
- auth_active_sessions
- auth_token_rotation_total

### Rollback Considerations

- Alembic `downgrade()` in `002_auth_identity.py` drops all auth tables in safe dependency order
- Rolling back `002_auth_identity.py` restores Epic 001 stub behavior
- Zero-downtime rollback: deploy Epic 001 image → run `alembic downgrade 001_initial_baseline`
- Data loss: rollback destroys all user accounts and sessions created under Epic 002

### Backup Considerations

Authentication data is business-critical.

Production deployments SHOULD include:

- Daily PostgreSQL backups
- Point-in-Time Recovery (PITR)
- Backup encryption
- Periodic restore testing

---

## 15. Risks

### Technical Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|------------|-----------|
| Argon2 params too slow for login p95 budget | Medium — login SLO missed | Low | Benchmark during Phase 4; tunable via `Settings` without code change |
| Atomic refresh token rotation race condition under load | Medium — duplicate sessions | Low | PostgreSQL `SERIALIZABLE` transaction for rotation; integration test with concurrent requests |
| In-memory rate limiting loses state on process restart | Low — brief rate limit bypass window | High (dev only) | Acceptable in development; Redis-backed in production (documented) |

### Security Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|------------|-----------|
| JWT secret committed to repository | Critical — all tokens forgeable | Low | Pre-commit hook blocks `.env` commits; secret validated non-empty at startup |
| Refresh token not hashed at rest | High — DB compromise exposes active sessions | Very Low | `TokenService` always hashes before write; raw token is ephemeral |
| XSS attack steals refresh token from localStorage | Medium — session hijack | Medium | Document risk; access token in memory reduces impact; HttpOnly cookie migration path documented |
| Timing oracle on email enumeration | Low — email existence disclosure | Low | Login and forgot-password always compute Argon2 (dummy hash if user not found); uniform response time |

### Performance Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|------------|-----------|
| `SELECT users WHERE id = ?` on every authenticated request | Medium — latency at scale | Low | Single indexed PK lookup; acceptable at 500 concurrent requests; cache layer if needed |
| `audit_logs` table unbounded growth | Low — disk usage | Medium | `AUDIT_LOG_RETENTION_DAYS` config; add cleanup job in Epic 003 |

### Deployment Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|------------|-----------|
| Migration fails mid-deploy | High — partial schema state | Low | Test migration against staging DB before production; Alembic transaction wraps DDL |
| Rollback destroys user data | High | Low | Take DB snapshot before migration in production; rollback procedure documented |

### Business Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|------------|-----------|
| Weak administrator-created passwords | Medium | Medium | Enforce same password policy for all account creation paths |
| User account sharing | Medium | Medium | Future device management and session monitoring |
| Email delivery delays | Medium | Medium | Resend option and retry queue |

### Migration Risks

| Risk | Impact | Probability | Mitigation |
|------|--------|------------|-----------|
| Epic 001 integration tests break due to stub replacement | Low — CI fails | Medium | Run existing Epic 001 test suite before stub replacement; add auth fixtures to conftest.py |

---

## 16. Dependencies

### Internal Dependencies

| Dependency | Usage |
|-----------|-------|
| Epic 001 `BaseRepository` | Extended by all auth repositories |
| Epic 001 `BaseService` | Extended by all auth services |
| Epic 001 `ApplicationException` hierarchy | Extended by auth exception classes |
| Epic 001 `Settings` | Extended with auth configuration |
| Epic 001 `RequestIDMiddleware` | Request ID captured in audit logs |
| Epic 001 `ApiResponse` schema | All auth endpoint responses wrapped |
| Epic 001 `get_db` dependency | Session injection into auth services |
| Epic 001 `AuthHookMiddleware` | Extended to set real `CurrentUser` |
| Epic 001 `core/auth/interfaces.py` | `CurrentUser`, `SessionContext` classes reused unchanged |

### External Dependencies (New)

| Package | Version | Purpose |
|---------|---------|---------|
| `argon2-cffi` | ≥23.1 | Argon2id password hashing |
| `PyJWT` | ≥2.8 | JWT creation and validation |
| `slowapi` | ≥0.1.9 | FastAPI-compatible rate limiting |
| `@tanstack/react-query` | ≥5.x | Frontend API state management |
| `react-hook-form` | ≥7.x | Frontend form state and validation |
| `zod` | ≥3.x | Frontend schema validation |

### Future Dependencies

| Future Epic/Feature | Dependency |
|--------------------|-----------|
| Epic 003 (RBAC & Company Management) | Consumes `CurrentUser.user_id`; populates `CurrentUser.company_id`; replaces stub in `BaseRepository` |
| MFA | Plugs into login flow post-password-verification; new auth factor step |
| OAuth2 / SSO | New `AuthenticationProvider` implementation; `CurrentUser` interface unchanged |
| Redis (Production Rate Limiting) | SlowAPI storage backend swap; no application code changes |
| Email Service (Real SMTP) | Replace `send_email()` stub with real provider; interface is already defined |
| Multi-Tenant Company Isolation | CurrentUser gains tenant context; authorization layer consumes tenant_id without changing authentication |
---

## 17. Definition of Done

### Implementation Complete

- [ ] All 7 database models created and Alembic migration verified
- [ ] All 7 repositories implemented with custom query methods
- [ ] `JWTService`, `PasswordService`, `TokenService`, `AuditService`, `AuthService` implemented
- [ ] `core/auth/dependencies.py` replaces stubs; `AuthHookMiddleware` updated
- [ ] All 8 auth endpoints implemented and registered
- [ ] All 3 frontend auth pages implemented
- [ ] `AuthContext`, `useAuth`, `useTokenRefresh`, token storage, API interceptors implemented
- [ ] Route guard protecting all `(protected)` pages

### Quality Gates

- [ ] Backend test suite passes (`pytest`)
- [ ] Backend security-sensitive test coverage ≥ 90% (`pytest --cov`)
- [ ] Frontend test suite passes (`npm test`)
- [ ] No `bandit` HIGH or CRITICAL findings in auth module
- [ ] No HIGH vulnerabilities in `pip-audit` or `npm audit`
- [ ] All Epic 001 existing tests still pass (no regression)

### Security Validation

- [ ] Login anti-enumeration verified: identical responses for found/not-found email
- [ ] Forgot-password anti-enumeration verified
- [ ] Account lockout triggers at correct threshold
- [ ] Locked account auto-unlocks after configured duration
- [ ] Refresh token rotation is atomic (concurrent test passes)
- [ ] Consumed reset token rejected on reuse
- [ ] Expired reset token rejected
- [ ] Security headers present on all responses
- [ ] No secrets or credential data appear in any log line
- [ ] Audit logs created for all security events (verified per event type)

### Penetration Test Checklist

Before Epic completion the following attacks MUST be verified manually or through automated testing:

- SQL Injection
- JWT Tampering
- Replay Attack
- Brute Force Login
- CSRF (if cookies enabled)
- XSS token exposure
- Broken Authentication
- IDOR on `/me`
- Password Reset Replay
- Refresh Token Replay

### Operational Validation

- [ ] `docker-compose up` starts cleanly with new auth config
- [ ] `alembic upgrade head` runs cleanly from empty database
- [ ] `alembic downgrade base` runs cleanly (rollback verified)
- [ ] Login → use protected endpoint → refresh → logout flow works end-to-end
- [ ] Remember Me extends refresh token expiry correctly
- [ ] `/me` endpoint returns correct user data
- [ ] Health check endpoint still returns 200 (no regression)
- [ ] Login endpoint load-tested with 500 concurrent users
- [ ] Refresh endpoint load-tested under concurrent rotation scenarios
- [ ] No memory leak detected during 1-hour authentication stress test

### Documentation

- [ ] `.env.example` updated with all new auth variables and comments
- [ ] `specs/002-auth-identity/quickstart.md` covers developer setup for auth
- [ ] PHR created for this planning session

---

*This document is the authoritative implementation roadmap for Epic 002. It must be read alongside `spec.md` (requirements) and updated if significant implementation decisions change during execution.*
