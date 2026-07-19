# Authentication Architecture

## Status: Fully Implemented (Epic 002)

Epic 002 delivers a production-grade JWT-based authentication system built on
FastAPI + SQLAlchemy + PostgreSQL. The architecture uses stateless access tokens
complemented by opaque refresh tokens persisted server-side.

---

## Architecture Overview

```
HTTP Request
    │
    ├─► SecurityHeadersMiddleware   (7 OWASP headers on every response)
    ├─► RequestIdMiddleware         (X-Request-ID propagation)
    ├─► AuthHookMiddleware          (populates request.state.user)
    │
    ├─► FastAPI Route
    │       └─► require_authenticated (Depends)
    │               └─► get_current_user (Depends)
    │                       ├─► JWTService.decode_access_token()
    │                       ├─► UserRepository.get_by_id_or_none()
    │                       └─► account status checks
    │
    ├─► AuthService (business logic)
    │       ├─► UserRepository
    │       ├─► UserCredentialRepository
    │       ├─► SessionRepository
    │       ├─► PasswordService      (Argon2id)
    │       ├─► JWTService           (HS256 JWT)
    │       ├─► TokenService         (opaque tokens, SHA-256 stored)
    │       └─► AuditService         (structured audit log)
    │
    └─► PostgreSQL (7 auth tables)
```

---

## Key Abstractions (`core/auth/`)

### Value Objects

| Class | Purpose |
|---|---|
| `CurrentUser` | Authenticated principal: `user_id`, `company_id`, `email`, `roles`, `is_authenticated`, `session_id` |
| `SessionContext` | Session metadata; separate from identity |

### FastAPI Dependencies

| Dependency | Behaviour |
|---|---|
| `get_current_user` | Decodes JWT → loads user → checks account status → returns `CurrentUser`; returns unauthenticated value for missing token (optional-auth routes) |
| `require_authenticated` | Wraps `get_current_user`; raises 401 if `is_authenticated == False` |

---

## Authentication Module (`modules/auth/`)

### Models (7 ORM entities)

| Model | Table | Purpose |
|---|---|---|
| `User` | `users` | Identity: email, display_name, account_status, company_id (nullable FK for Epic 003) |
| `UserCredentials` | `user_credentials` | Argon2id hash + password history (JSONB) |
| `Session` | `sessions` | Per-device session record; revocable |
| `RefreshToken` | `refresh_tokens` | SHA-256 hash of opaque token; remember_me flag |
| `PasswordResetToken` | `password_reset_tokens` | Single-use; 1-hour TTL |
| `EmailVerificationToken` | `email_verification_tokens` | Single-use; 24-hour TTL |
| `AuditLog` | `audit_logs` | Append-only; no FK on user_id (forensic integrity) |

### Repositories (7)

`UserRepository`, `UserCredentialRepository`, `SessionRepository`,
`RefreshTokenRepository`, `PasswordResetTokenRepository`,
`EmailVerificationTokenRepository`, `AuditLogRepository`

All extend `BaseRepository` from Epic 001. No raw SQL; all queries via SQLAlchemy ORM.

### Services (6)

| Service | Responsibility |
|---|---|
| `PasswordService` | Argon2id hash/verify, complexity validation, common-password check, history check |
| `JWTService` | HS256 token creation and validation (sub, exp, nbf, iat, jti, iss, aud, sid) |
| `TokenService` | Refresh token rotation (with theft detection), password reset token lifecycle, email verification token lifecycle |
| `AuditService` | Structured event emission; never blocks on failure; sanitizes sensitive fields |
| `EmailService` | Stub — logs reset token at DEBUG; ready for SMTP integration |
| `AuthService` | Orchestrates all auth flows: login, logout, refresh, me, forgot/reset/change password, verify email |

---

## Security Properties

| Property | Implementation |
|---|---|
| Password hashing | Argon2id (m=65536, t=3, p=4) — OWASP compliant |
| Access token | JWT HS256; 15-min TTL; claims: sub, email, iat, exp, nbf, jti, iss, aud, typ, sid |
| Refresh token | `secrets.token_urlsafe(64)` raw; SHA-256 hex stored; 7-day / 30-day (remember_me) |
| Token rotation | Atomic: old token revoked before new issued; theft detected by revoked-token reuse |
| Account lockout | 5 failures / 15-min window → LOCKED; auto-unlock after 30 min |
| Anti-enumeration | Login and forgot-password return identical responses for unknown vs known emails |
| Rate limiting | SlowAPI: 10/min login, 3/15min forgot-password, 30/min refresh, 5/15min reset/change |
| Security headers | 7 OWASP headers on every response (via `SecurityHeadersMiddleware`) |
| Audit logging | 9 event types persisted to `audit_logs`; no passwords/raw tokens in metadata |
| Password history | Last 5 hashes checked on change/reset |
| Session revocation | Per-session and global (all-devices) logout |

---

## Database Schema (Migration 002)

Created by `migrations/versions/002_auth_identity.py` in FK-dependency order:
`users` → `user_credentials` → `sessions` → `refresh_tokens` →
`password_reset_tokens` → `email_verification_tokens` → `audit_logs`

Key indexes:
- `UNIQUE users.email`
- `(users.account_status, users.locked_until)` — lockout queries
- `UNIQUE refresh_tokens.token_hash`
- `(refresh_tokens.user_id, is_revoked)` — active token lookups
- `(audit_logs.user_id, created_at DESC)` — audit trail queries

Multi-tenant readiness: `users.company_id` is a nullable UUID column with index,
FK placeholder for Epic 003 Company/Tenant isolation.

---

## API Endpoints (`/api/v1/auth/`)

| Method | Path | Auth | Rate Limit |
|--------|------|------|-----------|
| POST | `/login` | None | 10/min/IP |
| POST | `/logout` | Required | 30/min/IP |
| POST | `/refresh` | None | 30/min/IP |
| GET | `/me` | Required | 60/min/IP |
| POST | `/forgot-password` | None | 3/15min/IP |
| POST | `/reset-password` | None | 5/15min/IP |
| POST | `/change-password` | Required | 5/15min/user |
| POST | `/verify-email` | None | 10/hr/IP |

---

## Frontend (`frontend/src/`)

| Module | Purpose |
|---|---|
| `lib/auth/tokenStorage.ts` | In-memory access token + localStorage refresh token |
| `lib/api/auth.ts` | Typed API functions for all 8 endpoints |
| `lib/api/client.ts` | Axios interceptors: attach Bearer token, retry on 401, single refresh lock |
| `contexts/AuthContext.tsx` | Session hydration on mount, login/logout state, token refresh wiring |
| `hooks/useAuth.ts` | Consumer hook with login/logout/logoutAllDevices |
| `hooks/useTokenRefresh.ts` | Schedules refresh at 80% token lifetime; clears on unmount |
| `app/(auth)/` | Login, ForgotPassword, ResetPassword pages |
| `app/(protected)/` | Protected route layout with redirect guard |

---

## CI Pipeline (`.github/workflows/`)

- **backend.yml**: lint (Ruff + Black + MyPy) → test (pytest ≥80% global, ≥90% auth) → security (bandit + pip-audit) → migrations (AST check) → docker-build
- **frontend.yml**: lint (ESLint + tsc) → test (Jest) → security (npm audit) → build (Next.js)
- **pr-checks.yml**: conventional commit title, secret scan, TODO/FIXME check

---

*Updated: Epic 002 — Authentication & Identity (Phases 1–17 complete)*
