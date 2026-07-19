# Feature Specification: Authentication & Identity

**Epic**: `002-auth-identity`
**Feature Branch**: `002-auth-identity`
**Created**: 2026-07-12
**Status**: Draft
**Version**: 1.0.0

---

## 1. Executive Summary

Epic 002 establishes the Authentication and Identity layer for the DevSphere ERP platform. This Epic delivers a production-grade, security-first identity system that gates access to all future ERP modules. It introduces user login, logout, token-based session management, password lifecycle operations, and an auditable authentication event log — all built atop the foundation components delivered in Epic 001.

The system follows a stateless JWT access-token model complemented by opaque refresh tokens persisted server-side, enabling fine-grained session revocation without sacrificing horizontal scalability. All security decisions align with OWASP Authentication Cheat Sheet, NIST SP 800-63B, and enterprise SaaS security standards.

This Epic deliberately excludes Role-Based Access Control (RBAC), company management, permissions, and tenant isolation. Those capabilities will be delivered in subsequent Epics. The identity layer defined here is the single source of truth for **who a user is**; later Epics will determine **what that user may do**.

---

## 2. Business Goals

| # | Goal | Rationale |
|---|------|-----------|
| BG-01 | Protect all ERP data behind authenticated sessions | Prevent unauthorized access to sensitive business information |
| BG-02 | Establish user identity as the platform-wide foundation | Every future Epic references the identity established here |
| BG-03 | Reduce credential-related support burden | Self-service password reset and email verification reduce operational cost |
| BG-04 | Demonstrate enterprise security posture to customers | Security certifications and enterprise sales require documented, auditable auth |
| BG-05 | Enable compliant audit trails | Regulatory environments (SOC2, ISO 27001) require authentication event logs |
| BG-06 | Build extensible auth infrastructure | Future Epics (MFA, SSO, OAuth2) plug into this layer without redesign |

---
### Multi-Tenant Goal

The authentication system MUST be tenant-aware from the initial implementation.

All authentication operations MUST execute within the context of a single tenant.

The authentication architecture MUST support multiple isolated organizations sharing the same application instance while preventing any cross-tenant authentication or data leakage.

## 3. Objectives

- **OBJ-01** — Deliver a complete, self-contained authentication system users can log into on Day 1.
- **OBJ-02** — Implement secure credential storage using Argon2 password hashing.
- **OBJ-03** — Implement JWT access tokens with configurable short expiry (default 15 minutes).
- **OBJ-04** — Implement refresh token rotation with configurable long expiry (default 7 days standard, 30 days with Remember Me).
- **OBJ-05** — Implement account lockout after configurable failed login attempts.
- **OBJ-06** — Implement self-service Forgot Password and Reset Password flows.
- **OBJ-07** — Architect email verification without blocking Day 1 login (architecture-ready, not fully activated).
- **OBJ-08** — Deliver a protected Current User API endpoint as the identity anchor for future Epics.
- **OBJ-09** — Implement authentication middleware that future API routes opt into.
- **OBJ-10** — Produce structured audit log events for all security-significant actions.
- **OBJ-11** — Build frontend Login, Forgot Password, and Reset Password pages with full UX polish.
- **OBJ-12** — Implement client-side session persistence, automatic token refresh, and protected route guards.

---

## 4. Scope

### In Scope

| Area | Included Capabilities |
|------|-----------------------|
| **User Identity** | User entity, email-based identity, display name, account status (active / inactive / locked / deleted) |
| **Authentication** | Email + password login, logout, session validation |
| **Token Management** | JWT access token issuance, refresh token issuance, token rotation, token revocation |
| **Password Security** | Argon2 hashing, complexity enforcement, password history, change password, forgot password, reset password |
| **Session Management** | Session creation, persistence, expiration, revocation, Remember Me extension |
| **Account Lifecycle** | Account status validation on every request; lockout after failed attempts |
| **Email Verification Architecture** | Token generation and verification endpoint; activation trigger deferred to Epic 003 |
| **Authentication Middleware** | FastAPI dependency that validates JWT on protected routes |
| **Current User API** | Authenticated endpoint returning caller's identity |
| **Frontend Auth Pages** | Login, Forgot Password, Reset Password pages |
| **Frontend Session** | Token storage, automatic refresh, protected route guards, logout flow |
| **Audit Logging** | Structured events for login, logout, password change, lockout, token refresh, reset |
| **Security Foundations** | Rate limiting on auth endpoints, brute force protection, secure headers, CSRF strategy |

---

## 5. Out of Scope

The following capabilities are **not** part of Epic 002 and will be addressed in dedicated future Epics:

| Excluded Capability | Future Epic |
|---------------------|-------------|
| Role-Based Access Control (RBAC) | Epic 003 |
| Roles and Permissions | Epic 003 |
| Company / Organization Management | Epic 003 |
| Multi-Tenant Isolation | Epic 003 |
| Company Switching (multi-tenant UI) | Epic 003 |
| User Invitation Flows | Epic 003 |
| Multi-Factor Authentication (MFA) | Future |
| OAuth2 / Social Login (Google, GitHub, Microsoft) | Future |
| SAML / LDAP / Enterprise SSO | Future |
| Magic Links / Passwordless | Future |
| Passkeys / Biometric | Future |
| Device Trust | Future |
| Admin User Management UI | Future |

### Tenant Administration

Tenant provisioning, tenant onboarding, tenant invitation workflows, and tenant management are outside the scope of this Epic.

This Epic only authenticates users that already belong to an existing tenant.

**RBAC, Roles, and Permissions** — Epic 002 establishes *who a user is*. What a user is *allowed to do* is a separate concern. No permission checks, no role assignments, no resource-level authorization will be implemented in this Epic.

**Companies and Tenant Isolation** — The User entity will be designed with `company_id` as a nullable future foreign key to remain schema-compatible with Epic 003, but no tenant resolution logic, company switching, or cross-tenant isolation is implemented here.

**User Invitation** — Administrators inviting new users via email link is a Company Management concern and belongs in Epic 003.

---

## 6. Actors

### Guest (Unauthenticated)

A visitor who has not established an authenticated session. A Guest may:
- Submit login credentials
- Request a password reset link
- Submit a new password using a valid reset token
- Submit an email verification token

A Guest may not access any protected resource.

### Authenticated User

A user who has successfully authenticated and holds a valid JWT access token. An Authenticated User may:
- Access their own identity information (`GET /me`)
- Refresh their session
- Change their password
- Log out (revoke their session)
- Access all future protected ERP features (subject to Epic 003 RBAC)

### System (Internal)

Internal automated processes that emit audit events, expire tokens, and clean up revoked sessions. System actors do not have user-facing identities in this Epic.

### System Administrator *(future — Epic 003)*

A privileged user who can manage other users' accounts. Not implemented in this Epic.

---

## 7. Functional Requirements

### 7.1 User Authentication

| ID | Requirement |
|----|-------------|
| FR-001 | The system MUST authenticate users using an email address and password combination |
| FR-002 | The system MUST reject authentication if the email does not match any active account |
| FR-003 | The system MUST reject authentication if the provided password does not match the stored credential |
| FR-004 | The system MUST issue a signed JWT access token upon successful authentication |
| FR-005 | The system MUST issue an opaque refresh token upon successful authentication |
| FR-006 | The system MUST record a successful login audit event including timestamp, IP address, and user agent |
| FR-007 | The system MUST record a failed login audit event for each failed attempt |
| FR-008 | The system MUST NOT reveal whether an email address exists when authentication fails (anti-enumeration) |

### 7.2 User Logout

| ID | Requirement |
|----|-------------|
| FR-009 | The system MUST allow an authenticated user to log out |
| FR-010 | Logout MUST revoke the current refresh token, making it non-renewable |
| FR-011 | Logout MUST record an audit event |
| FR-012 | The system MAY support a "logout all devices" operation that revokes all refresh tokens for the user |

### 7.3 Token Refresh

| ID | Requirement |
|----|-------------|
| FR-013 | The system MUST accept a valid, non-expired, non-revoked refresh token and issue a new JWT access token |
| FR-014 | Token refresh MUST rotate the refresh token (invalidate old, issue new) |
| FR-015 | Refresh token rotation MUST be atomic — old token is revoked only after new token is successfully stored |
| FR-016 | The system MUST reject expired refresh tokens |
| FR-017 | The system MUST reject revoked refresh tokens |
| FR-018 | The system MUST record a token refresh audit event |

### 7.4 Current User

| ID | Requirement |
|----|-------------|
| FR-019 | The system MUST expose a protected endpoint that returns the authenticated caller's identity |
| FR-020 | The identity response MUST include: user ID, email, display name, account status, email verification status, and created timestamp |
| FR-021 | The identity response MUST NOT include any credential data |

### 7.5 Forgot Password

| ID | Requirement |
|----|-------------|
| FR-022 | The system MUST accept an email address and initiate a password reset flow if the email matches an active account |
| FR-023 | The system MUST generate a cryptographically secure, single-use password reset token |
| FR-024 | The system MUST associate the reset token with a short expiry (default: 1 hour) |
| FR-025 | The system MUST deliver the reset token via email (email delivery is mocked/stubbed in this Epic) |
| FR-026 | The system MUST respond identically whether or not the email matches an account (anti-enumeration) |
| FR-027 | The system MUST record a password reset request audit event |

### 7.6 Reset Password

| ID | Requirement |
|----|-------------|
| FR-028 | The system MUST validate the reset token before accepting a new password |
| FR-029 | The system MUST reject expired reset tokens |
| FR-030 | The system MUST reject previously consumed reset tokens |
| FR-031 | Upon successful reset, the system MUST update the stored credential with the new hashed password |
| FR-032 | Upon successful reset, the system MUST invalidate all existing refresh tokens for the user (force re-login) |
| FR-033 | The system MUST record a password reset completion audit event |
| FR-034 | The system MUST enforce the full password complexity policy on the new password |

### 7.7 Change Password

| ID | Requirement |
|----|-------------|
| FR-035 | An authenticated user MUST be able to change their password by providing current password and new password |
| FR-036 | The system MUST verify the current password before accepting the change |
| FR-037 | Upon successful change, the system MUST invalidate all existing refresh tokens (force re-login on other devices) |
| FR-038 | The system MUST enforce the full password complexity policy on the new password |
| FR-039 | The system MUST reject a new password that matches any of the last N passwords (password history) |
| FR-040 | The system MUST record a password change audit event |

### 7.8 Remember Me

| ID | Requirement |
|----|-------------|
| FR-041 | The system MUST support an optional "Remember Me" flag at login time |
| FR-042 | When Remember Me is selected, the refresh token expiry MUST be extended to the configured long-lived duration (default: 30 days) |
| FR-043 | When Remember Me is not selected, the refresh token MUST use the standard expiry (default: 7 days) |
| FR-044 | Access token expiry MUST remain unchanged regardless of Remember Me setting |

### 7.9 Session Expiration

| ID | Requirement |
|----|-------------|
| FR-045 | Access tokens MUST expire after a short configurable window (default: 15 minutes) |
| FR-046 | The system MUST reject expired access tokens with a 401 response |
| FR-047 | Clients MUST use the refresh endpoint to obtain new access tokens before or after expiry |

### 7.10 Account Status Validation

| ID | Requirement |
|----|-------------|
| FR-048 | The system MUST check account status on every authentication attempt |
| FR-049 | The system MUST reject login for locked accounts with a specific error message |
| FR-050 | The system MUST reject login for inactive accounts |
| FR-051 | The system MUST reject login for soft-deleted accounts |
| FR-052 | The system MUST lock an account after N consecutive failed login attempts (default: 5) within a sliding window (default: 15 minutes) |
| FR-053 | A locked account MUST automatically unlock after a configurable lockout duration (default: 30 minutes) |
| FR-054 | The system MUST record an account lockout audit event |

### 7.11 Email Verification Architecture

| ID | Requirement |
|----|-------------|
| FR-055 | The system MUST generate a cryptographically secure email verification token upon user account creation |
| FR-056 | The system MUST expose an endpoint to consume an email verification token and mark the email as verified |
| FR-057 | The verification endpoint MUST reject expired tokens (default expiry: 24 hours) |
| FR-058 | The verification endpoint MUST reject already-consumed tokens |
| FR-059 | The `is_email_verified` flag MUST be included in the Current User response |
| FR-060 | For this Epic, email verification is NOT required to log in (enforcement deferred to Epic 003 or later) |

### 7.12 Authentication Middleware

| ID | Requirement |
|----|-------------|
| FR-061 | The system MUST provide a reusable authentication dependency that FastAPI routes can declare |
| FR-062 | The middleware MUST validate the JWT signature, expiry, and issuer claims |
| FR-063 | The middleware MUST extract the authenticated user's identity and make it available to route handlers |
| FR-064 | The middleware MUST return 401 for missing, malformed, or expired tokens |
| FR-065 | The middleware MUST return 401 for tokens belonging to locked, inactive, or deleted users |
| FR-066 | The middleware MUST be non-breaking for public (unauthenticated) routes |

### 7.13 Protected APIs

| ID | Requirement |
|----|-------------|
| FR-067 | All auth management endpoints (change-password, logout, /me) MUST be protected by the authentication middleware |
| FR-068 | All public auth endpoints (login, refresh, forgot-password, reset-password, verify-email) MUST NOT require an existing token |

### 7.14 Session Revocation

| ID | Requirement |
|----|-------------|
| FR-069 | The system MUST support individual session revocation (single device logout) |
| FR-070 | The system MUST support global session revocation (all devices logout) |
| FR-071 | Revoked refresh tokens MUST be rejected immediately, even if not yet expired |

### 7.15 Audit Logging

| ID | Requirement |
|----|-------------|
| FR-072 | The system MUST emit structured audit events for all security-significant actions |
| FR-073 | Audit events MUST include: event type, user ID (if known), timestamp (UTC), IP address, user agent, request ID, outcome (success/failure), and reason (for failures) |
| FR-074 | Audit events MUST be persisted durably (not in-memory only) |
| FR-075 | Audit events MUST NEVER contain passwords, raw tokens, or any sensitive credential data |

---

## 8. Non-Functional Requirements

### 8.1 Performance

| ID | Requirement |
|----|-------------|
| NFR-001 | Login endpoint MUST respond within 800ms at the 95th percentile under normal load (Argon2 hashing is intentionally slow; this budget accounts for it) |
| NFR-002 | Token refresh MUST respond within 200ms at the 95th percentile |
| NFR-003 | Current User endpoint MUST respond within 100ms at the 95th percentile |
| NFR-004 | Password reset request MUST respond within 300ms (email delivery is async) |
| NFR-005 | Authentication middleware validation MUST add less than 10ms overhead per request |

### 8.2 Availability

| ID | Requirement |
|----|-------------|
| NFR-006 | Authentication endpoints MUST target 99.9% availability (three-nines SLO) |
| NFR-007 | Authentication service degradation MUST be graceful — failed token validation returns 401, not 500 |

### 8.3 Scalability

| ID | Requirement |
|----|-------------|
| NFR-008 | The authentication system MUST be stateless at the access token layer (JWT), enabling horizontal scaling without shared state |
| NFR-009 | Refresh token and session state MUST be stored in the database with appropriate indexing to support high read throughput |
| NFR-010 | The system MUST support at least 500 concurrent authentication requests without degradation |

### 8.4 Security

| ID | Requirement |
|----|-------------|
| NFR-011 | Passwords MUST be hashed using Argon2id with parameters meeting OWASP minimum recommendations |
| NFR-012 | JWT secrets MUST be configurable via environment variables and NEVER hardcoded |
| NFR-013 | Access tokens MUST be short-lived (15 minutes default) to limit breach impact |
| NFR-014 | All auth endpoints MUST be rate-limited to prevent brute force attacks |
| NFR-015 | The system MUST apply account lockout after repeated failed attempts |
| NFR-016 | All token operations MUST be atomic to prevent race conditions in concurrent refresh scenarios |
| NFR-017 | Security headers (Content-Security-Policy, X-Frame-Options, etc.) MUST be set on all responses |
| NFR-018 | All communication MUST use HTTPS in production |

### 8.5 Reliability

| ID | Requirement |
|----|-------------|
| NFR-019 | Token refresh rotation MUST be atomic — partial failures MUST not leave users permanently locked out |
| NFR-020 | Failed audit log writes MUST NOT block authentication operations (best-effort logging with alerting) |
| NFR-021 | Database connection failures MUST return 503 Service Unavailable, not 500 Internal Error |

### 8.6 Maintainability

| ID | Requirement |
|----|-------------|
| NFR-022 | All authentication configuration (token expiry, lockout thresholds, rate limits) MUST be environment-variable driven |
| NFR-023 | The authentication module MUST be self-contained and independently testable |
| NFR-024 | All security-sensitive code paths MUST have unit test coverage >= 90% |
| NFR-025 | The codebase MUST follow the Clean Architecture and Repository Pattern established in Epic 001 |

### 8.7 Auditability

| ID | Requirement |
|----|-------------|
| NFR-026 | Every authentication state transition MUST produce a durable, structured audit record |
| NFR-027 | Audit records MUST be immutable once written |
| NFR-028 | Audit records MUST be queryable by user ID and time range |
| NFR-029 | The system MUST retain audit records for a minimum of 90 days (configurable) |

---

## 9. Authentication Flows

### 9.1 Successful Login Flow

```
Guest
  |
  +-- POST /auth/login (email, password, remember_me?)
  |
  +-- [Validate email format]
  |
  +-- [Lookup user by email]
  |     +-- Not found --> record failed attempt --> return 401 (generic message)
  |
  +-- [Check account status]
  |     +-- Locked   --> return 423 Account Locked
  |     +-- Inactive --> return 403 Account Inactive
  |     +-- Deleted  --> return 401 (generic message, anti-enumeration)
  |
  +-- [Verify password against Argon2 hash]
  |     +-- Mismatch --> increment failed count --> lockout if threshold --> return 401
  |
  +-- [Reset failed login counter]
  |
  +-- [Issue JWT Access Token (15 min)]
  |
  +-- [Issue Refresh Token (7d standard / 30d remember_me)]
  |
  +-- [Persist Session record]
  |
  +-- [Emit LoginSuccess audit event]
  |
  +-- 200 OK { access_token, refresh_token, token_type, expires_in }

Authenticated User
```

### 9.2 Failed Login Flow

```
Guest
  |
  +-- POST /auth/login (email, wrong_password)
  |
  +-- [Password mismatch verified]
  |
  +-- [Increment failed_login_count for user]
  |
  +-- [Check if failed_count >= lockout_threshold]
  |     +-- YES --> set account status = LOCKED, set locked_until timestamp
  |                 --> emit AccountLocked audit event
  |                 --> return 423 with unlock ETA
  |
  +-- [Emit LoginFailure audit event (no credential data)]
  |
  +-- 401 Unauthorized (generic: "Invalid credentials")
```

### 9.3 Token Refresh Flow

```
Authenticated User (expired access token, valid refresh token)
  |
  +-- POST /auth/refresh (refresh_token)
  |
  +-- [Lookup refresh token in store]
  |     +-- Not found --> return 401
  |
  +-- [Validate token: not expired, not revoked]
  |     +-- Expired  --> delete token --> return 401
  |     +-- Revoked  --> return 401 (possible token theft -- consider alert)
  |
  +-- [Check user account status]
  |     +-- Not active --> revoke token --> return 401/403
  |
  +-- [Atomically: revoke old refresh token + store new refresh token]
  |
  +-- [Issue new JWT Access Token]
  |
  +-- [Emit TokenRefreshed audit event]
  |
  +-- 200 OK { access_token, refresh_token, expires_in }

Authenticated User (new session)
```

### 9.4 Expired Access Token Flow (Client-Side)

```
Authenticated User
  |
  +-- [Client sends request with expired JWT]
  |
  +-- [Auth middleware detects token expiry]
  |
  +-- 401 Unauthorized { code: "TOKEN_EXPIRED" }
  |
  +-- [Client automatically calls POST /auth/refresh]
        +-- Success --> retry original request with new access token
        +-- Refresh also expired/revoked --> redirect to Login page
```

### 9.5 Logout Flow

```
Authenticated User
  |
  +-- POST /auth/logout (with Authorization: Bearer {access_token})
  |
  +-- [Auth middleware validates access token --> extracts user identity]
  |
  +-- [Identify associated refresh token(s) for this session]
  |
  +-- [Revoke refresh token(s)]
  |
  +-- [Emit Logout audit event]
  |
  +-- 204 No Content

Guest (session revoked)
```

### 9.6 Forgot Password / Reset Password Flow

```
Guest
  |
  +-- POST /auth/forgot-password (email)
  |     +-- [Always returns 200 regardless of email match -- anti-enumeration]
  |     +-- [If match: generate reset token, store with 1-hour expiry, send email (stubbed)]
  |     +-- [Emit PasswordResetRequested audit event]
  |
  +-- [User receives email with reset link containing token]
  |
  +-- [User opens Reset Password page]
  |
  +-- POST /auth/reset-password (token, new_password)
        +-- [Validate token: exists, not expired, not consumed]
        |     +-- Invalid --> 400 Bad Request
        +-- [Validate new password complexity]
        +-- [Hash new password with Argon2]
        +-- [Update credential record]
        +-- [Mark reset token as consumed]
        +-- [Revoke ALL existing refresh tokens for user]
        +-- [Emit PasswordResetCompleted audit event]
        +-- 200 OK

[User redirected to Login page]
```

---

## 10. Identity Model

### 10.1 User

The central identity entity representing a person in the system. Each User has a unique immutable identifier, an email address (used as login identifier), a display name, a creation timestamp, and an account status.

**Account Status** is an enumerated state with the following values:
- **ACTIVE** — User can log in normally.
- **INACTIVE** — User has been administratively deactivated. Login is blocked.
- **LOCKED** — Login has been temporarily suspended due to repeated failed attempts. Automatically transitions back to ACTIVE after the lockout window expires.
- **DELETED** — User is soft-deleted. Login is blocked. Record retained for audit purposes.

**Email Verification State** tracks whether the user has confirmed ownership of their email address. This is a boolean flag that defaults to unverified at creation.

### 10.2 User Credential

A separate entity holding the hashed password for a User. Credentials are decoupled from the User entity to:
- Allow future credential types (OAuth token, passkey) without schema changes to the User table
- Enforce strict access control (credential data is never included in any User response)
- Enable password history tracking

The Credential entity holds: the user reference, the hashed password, the hashing algorithm identifier, password-set timestamp, and a reference list of recent password hashes for history enforcement.

### 10.3 Session

Represents an authenticated session established at login. A Session links a User to a device/client context (captured IP, user agent). Sessions are created at login and destroyed at logout or expiry.

### 10.4 Refresh Token

An opaque, cryptographically secure token issued at login and rotated at each refresh. A Refresh Token entity holds:
- The token value (stored hashed server-side)
- Associated user reference
- Associated session reference
- Issued timestamp
- Expiry timestamp
- Revocation status and timestamp
- Whether it was issued with Remember Me
- IP address and user agent at issuance (for anomaly detection in future Epics)

Refresh tokens are single-use and rotate on each use. A consumed token that is presented again indicates a possible replay or theft attempt.

### 10.5 Password Reset Token

A time-limited, single-use token scoped to a specific user and operation. Password Reset Token entities hold:
- Token value (hashed)
- Associated user reference
- Requested-at timestamp
- Expiry timestamp (1 hour from issuance)
- Consumed flag and consumed-at timestamp
- Requesting IP address

Only one active (non-expired, non-consumed) reset token per user is enforced; issuing a new token invalidates any outstanding tokens for the same user.

### 10.6 Email Verification Token

Analogous to the Password Reset Token but scoped to email confirmation. Email Verification Token entities follow the same structural pattern:
- Token value (hashed)
- Associated user reference
- Issued-at timestamp
- Expiry timestamp (24 hours)
- Consumed flag

### 10.7 Audit Event

An immutable record of a security-significant action. Audit Event entities hold:
- Unique event ID
- Event type (enumerated: LOGIN_SUCCESS, LOGIN_FAILURE, LOGOUT, TOKEN_REFRESHED, ACCOUNT_LOCKED, PASSWORD_CHANGED, PASSWORD_RESET_REQUESTED, PASSWORD_RESET_COMPLETED, EMAIL_VERIFIED, etc.)
- User ID (nullable — unknown for pre-authentication events)
- Timestamp (UTC, immutable)
- IP address
- User Agent string
- Request ID (correlation with application logs)
- Outcome (SUCCESS / FAILURE)
- Failure reason code (for failures)
- Additional context (JSON metadata, excluding all sensitive data)

---

## 11. User Stories

### US-01 — User Login (Priority: P1)

**As a** registered ERP user,
**I want to** log in with my email and password,
**So that** I can access the DevSphere ERP platform securely.

**Business Value**: Core access gate to the platform; no ERP functionality is usable without authentication.

**Priority**: P1 — Foundational. Blocks all other user stories.

**Dependencies**: User account must exist (seeded or registered).

**Acceptance Criteria**:

1. **Given** valid credentials and an active account, **When** I submit login, **Then** I receive a JWT access token and a refresh token, and I am redirected to the dashboard.
2. **Given** an incorrect password, **When** I submit login, **Then** I see a generic "Invalid credentials" error and my failed attempt count increments.
3. **Given** a non-existent email, **When** I submit login, **Then** I see the same generic "Invalid credentials" error (anti-enumeration).
4. **Given** a locked account, **When** I submit login, **Then** I see a message indicating my account is temporarily locked and the approximate unlock time.
5. **Given** valid credentials, **When** I successfully log in, **Then** a LoginSuccess audit event is persisted.
6. **Given** malformed email input, **When** I submit login, **Then** I see a validation error before any server request.

**Edge Cases**:
- Login with email containing trailing/leading whitespace (must be trimmed server-side)
- Login with email in different case (must be normalized to lowercase)
- Concurrent login attempts from multiple clients
- Login with expired account credentials (password last-set > max age policy — future extension)

---

### US-02 — User Logout (Priority: P1)

**As an** authenticated ERP user,
**I want to** log out of my session,
**So that** my account is secured when I am finished.

**Business Value**: Security baseline — users must be able to terminate sessions, especially on shared devices.

**Priority**: P1 — Security requirement.

**Dependencies**: US-01 (must be logged in).

**Acceptance Criteria**:

1. **Given** I am authenticated, **When** I click Logout, **Then** my refresh token is revoked and I am redirected to the Login page.
2. **Given** I am logged out, **When** I attempt to use my former refresh token, **Then** I receive a 401 error.
3. **Given** I am logged out, **When** I navigate to a protected route, **Then** I am redirected to the Login page.
4. **Given** I log out, **Then** a Logout audit event is persisted.

**Edge Cases**:
- Logout with an already-expired access token (should still succeed by revoking the refresh token)
- Logout when the refresh token has already been revoked (idempotent — returns success)
- Concurrent logout requests from same client

---

### US-03 — Automatic Token Refresh (Priority: P1)

**As an** authenticated ERP user actively using the platform,
**I want** my session to automatically stay alive as long as I am active,
**So that** I am not disruptively logged out mid-task.

**Business Value**: Prevents frustrating session drops during active work sessions; improves enterprise user experience.

**Priority**: P1 — Core session management.

**Dependencies**: US-01.

**Acceptance Criteria**:

1. **Given** my access token has expired, **When** the client silently calls the refresh endpoint with a valid refresh token, **Then** a new access token is issued and the original request is retried transparently.
2. **Given** my refresh token has also expired, **When** the client attempts refresh, **Then** I am redirected to the Login page.
3. **Given** I use refresh, **Then** my old refresh token is consumed and a new one is issued.
4. **Given** I attempt to reuse an old (already-rotated) refresh token, **Then** the system rejects it with 401.
5. **Given** token refresh succeeds, **Then** a TokenRefreshed audit event is persisted.

**Edge Cases**:
- Concurrent refresh attempts from multiple browser tabs (race condition — one must win; others must gracefully handle the resulting new token)
- Refresh token used on a different IP address than issuance

---

### US-04 — Forgot Password (Priority: P2)

**As a** registered user who has forgotten my password,
**I want to** request a password reset link,
**So that** I can regain access to my account without administrator intervention.

**Business Value**: Reduces support burden; enables autonomous account recovery.

**Priority**: P2.

**Dependencies**: Email delivery architecture (stubbed in this Epic).

**Acceptance Criteria**:

1. **Given** I enter a registered email, **When** I submit the Forgot Password form, **Then** I see a success message ("If this email is registered, a reset link has been sent") and a reset token is generated.
2. **Given** I enter an unregistered email, **When** I submit the Forgot Password form, **Then** I see the identical success message (anti-enumeration).
3. **Given** a reset token is generated, **Then** it expires in 1 hour.
4. **Given** I request a second reset while one is still active, **Then** the previous token is invalidated and a new one is issued.
5. **Given** a reset is requested, **Then** a PasswordResetRequested audit event is persisted.

**Edge Cases**:
- Multiple rapid requests for the same email (rate limiting must apply)
- Request for a locked or inactive account (returns same success message — no hint of status)

---

### US-05 — Reset Password (Priority: P2)

**As a** user who has received a password reset link,
**I want to** set a new password using the link,
**So that** I can regain access to my account.

**Business Value**: Completes the account recovery loop.

**Priority**: P2.

**Dependencies**: US-04.

**Acceptance Criteria**:

1. **Given** a valid, non-expired reset token, **When** I submit a compliant new password, **Then** my password is updated and I am redirected to Login.
2. **Given** an expired reset token, **When** I submit, **Then** I see an error prompting me to request a new reset link.
3. **Given** an already-consumed reset token, **When** I submit, **Then** I see an error.
4. **Given** a password that violates complexity rules, **When** I submit, **Then** I see specific validation errors.
5. **Given** a successful reset, **Then** all my existing sessions are terminated (refresh tokens revoked).
6. **Given** a successful reset, **Then** a PasswordResetCompleted audit event is persisted.

**Edge Cases**:
- Token submitted via direct URL manipulation (missing or garbled)
- Simultaneous reset submissions with the same token

---

### US-06 — Current User (Priority: P1)

**As an** authenticated user or a consuming front-end component,
**I want to** retrieve the current authenticated user's identity,
**So that** the UI can personalize the experience and future API calls can be scoped to the correct user.

**Business Value**: Identity anchor for the entire platform — every future Epic uses this.

**Priority**: P1.

**Dependencies**: US-01, FR-019 to FR-021.

**Acceptance Criteria**:

1. **Given** a valid JWT access token, **When** I call `GET /auth/me`, **Then** I receive user ID, email, display name, status, email verification status, and created timestamp.
2. **Given** an expired or missing token, **When** I call `GET /auth/me`, **Then** I receive 401.
3. **Given** a locked account, **When** I call `GET /auth/me`, **Then** I receive 401/403 with an appropriate code.
4. **Given** a valid request, **Then** the response MUST NOT contain any credential or token data.

**Edge Cases**:
- Token belongs to a since-deleted user (account deleted after token was issued)

---

### US-07 — Remember Me (Priority: P2)

**As a** user on a trusted personal device,
**I want to** opt in to a longer session duration,
**So that** I do not need to log in every day.

**Business Value**: Reduces login friction for trusted, personal-device usage patterns common in desktop ERP environments.

**Priority**: P2.

**Dependencies**: US-01, US-03.

**Acceptance Criteria**:

1. **Given** I log in with Remember Me checked, **When** login succeeds, **Then** my refresh token expires in 30 days.
2. **Given** I log in without Remember Me, **When** login succeeds, **Then** my refresh token expires in 7 days.
3. **Given** I rotate my refresh token (via auto-refresh), **Then** the extended expiry is preserved for the new token's lifetime.

**Edge Cases**:
- Remember Me checked on a shared/public device (UX warning recommended)

---

### US-08 — Change Password (Priority: P2)

**As an** authenticated user,
**I want to** change my current password,
**So that** I can maintain my account security on my own schedule.

**Business Value**: User autonomy over credential security; required for enterprise security policies.

**Priority**: P2.

**Dependencies**: US-01.

**Acceptance Criteria**:

1. **Given** correct current password and compliant new password, **When** I submit change password, **Then** my password is updated.
2. **Given** incorrect current password, **When** I submit, **Then** I receive a 403 error.
3. **Given** a new password that violates complexity, **When** I submit, **Then** I receive specific validation errors.
4. **Given** a new password matching a recent previous password, **When** I submit, **Then** I receive an error.
5. **Given** a successful password change, **Then** all other sessions (other devices) are terminated.
6. **Given** a successful password change, **Then** a PasswordChanged audit event is persisted.

**Edge Cases**:
- Identical current and new password (treated as a history violation)

---

### US-09 — Session Expiration Handling (Priority: P1)

**As a** platform user,
**I want** to be gracefully handled when my session expires,
**So that** I do not lose in-progress work abruptly.

**Business Value**: Enterprise UX — session expiry handling directly impacts productivity.

**Priority**: P1.

**Dependencies**: US-01, US-03.

**Acceptance Criteria**:

1. **Given** my access token has expired, **When** I make a request, **Then** the client transparently attempts refresh before showing an error.
2. **Given** both access and refresh tokens are expired, **When** the client detects this, **Then** I am redirected to Login with an informational message ("Your session has expired. Please log in again.").
3. **Given** I am on a form when expiry is detected, **Then** my form data is preserved where technically feasible.

**Edge Cases**:
- Token expiry occurs mid-form submission
- Clock skew between client and server (server-side expiry is authoritative)

---

### US-10 — Session Revocation (Priority: P2)

**As a** security-conscious user,
**I want to** be able to revoke active sessions,
**So that** compromised or abandoned sessions can be terminated immediately.

**Business Value**: Security incident response — ability to terminate a compromised session is a baseline enterprise requirement.

**Priority**: P2.

**Dependencies**: US-01.

**Acceptance Criteria**:

1. **Given** I log out, **When** the logout succeeds, **Then** my current session's refresh token is revoked immediately.
2. **Given** I change my password, **When** the change succeeds, **Then** all my sessions (except optionally the current one) are revoked.
3. **Given** I reset my password, **When** the reset completes, **Then** all sessions across all devices are revoked.
4. **Given** a revoked refresh token is presented, **Then** a 401 is returned.

**Edge Cases**:
- Revoking a session that has already expired naturally
- Revocation while a refresh is in flight (race condition)

---

## 12. Business Rules

### 12.1 Password Policy

| Rule | Default | Configurable |
|------|---------|-------------|
| Minimum length | 12 characters | Yes |
| Maximum length | 128 characters | Yes |
| Required: at least one uppercase letter | Yes | Yes |
| Required: at least one lowercase letter | Yes | Yes |
| Required: at least one digit | Yes | Yes |
| Required: at least one special character | Yes | Yes |
| Disallow common passwords (top-10,000 list) | Yes | Yes |
| Disallow email address as password | Yes | No |
| Password history (cannot reuse recent N passwords) | Last 5 | Yes (1-24) |

### 12.2 Failed Login & Lockout Policy

| Rule | Default | Configurable |
|------|---------|-------------|
| Max failed attempts before lockout | 5 | Yes |
| Lockout observation window | 15 minutes (sliding) | Yes |
| Lockout duration | 30 minutes | Yes |
| Auto-unlock after duration | Yes | Yes |
| Failed counter reset on success | Yes | No |

### 12.3 Token Expiry Policy

| Token Type | Default Expiry | Remember Me Expiry | Configurable |
|------------|---------------|-------------------|-------------|
| JWT Access Token | 15 minutes | 15 minutes (unchanged) | Yes |
| Refresh Token (standard) | 7 days | — | Yes |
| Refresh Token (remember me) | — | 30 days | Yes |
| Password Reset Token | 1 hour | — | Yes |
| Email Verification Token | 24 hours | — | Yes |

### 12.4 Session Rules

| Rule | Value |
|------|-------|
| Maximum concurrent refresh tokens per user | 10 (excess oldest are revoked) |
| Refresh token rotation | Always rotate on use |
| Refresh token reuse detection | Old token reuse triggers audit alert; optionally revokes all sessions |
| Session inactivity timeout | Governed by refresh token expiry; no separate inactivity timer in this Epic |

### 12.5 Remember Me Rules

- Remember Me extends only the refresh token lifetime.
- Access token lifetime is always 15 minutes regardless.
- The extended lifetime is propagated to rotated tokens for the lifetime of the session.
- Remember Me flag is stored on the refresh token entity for accurate rotation.

### 12.6 Account Status Transitions

| From | Event | To |
|------|-------|----|
| ACTIVE | N consecutive failed logins within window | LOCKED |
| LOCKED | Lockout duration expires | ACTIVE |
| ACTIVE | Administrative deactivation (future Epic) | INACTIVE |
| INACTIVE | Administrative reactivation (future Epic) | ACTIVE |
| ACTIVE / INACTIVE | Administrative deletion (future Epic) | DELETED |

### 12.7 Multi-Tenant Rules

- Every authenticated user MUST belong to exactly one Tenant.
- Authentication MUST occur within the tenant context.
- Users from one tenant MUST NEVER access another tenant's resources.
- Email enumeration across tenants MUST NOT be possible.
- All sessions, refresh tokens, audit events, and security logs MUST include the Tenant ID.

---

## 13. Security Requirements

### 13.1 Password Hashing

- Passwords MUST be hashed using **Argon2id** (preferred variant for side-channel resistance).
- Hashing parameters MUST meet OWASP minimum: `m=19456` (19 MiB), `t=2`, `p=1` or equivalent tuned to achieve >=500ms on target hardware.
- The hashing algorithm identifier MUST be stored with the hash to support future algorithm migration.
- Plaintext passwords MUST be zeroed from memory immediately after hashing.
- Passwords MUST NEVER be logged, stored in plaintext, or included in any response body.

### 13.2 JWT Requirements

- JWTs MUST be signed using a strong algorithm: **HS256** minimum, **RS256** recommended for future inter-service validation.
- JWT claims MUST include:
  - `sub` (user ID)
  - `iat` (issued at)
  - `exp` (expiry)
  - `nbf` (not before)
  - `jti` (unique token ID)
  - `iss` (issuer)
  - `aud` (audience)
  - `typ` (`access` or `refresh`)
  - `sid` (session ID)
  - `tenant_id` (tenant identifier for multi-tenant isolation)
- The tenant_id claim MUST be validated by authentication middleware before any protected resource is accessed.
- The JWT signing secret MUST be a minimum of 256-bit random value.
- JWT secrets MUST be stored exclusively in environment variables; never in source code or configuration files.
- JWTs MUST NOT contain sensitive personal data beyond user ID.
- JWTs MUST NOT contain password hashes, raw tokens, or role data in this Epic.

### 13.3 Refresh Token Security

- Refresh tokens MUST be cryptographically random with minimum 256 bits of entropy.
- Refresh token values MUST be stored **hashed** server-side (SHA-256 minimum), not in plaintext.
- The raw token is only ever seen by the client; the server stores only the hash.
- Token rotation MUST be atomic (database transaction) to prevent double-use in concurrent scenarios.

### 13.4 Transport Security

- All communication between client and server MUST use HTTPS (TLS 1.2 minimum, TLS 1.3 recommended).
- HTTP requests MUST be redirected to HTTPS in production.
- HSTS header MUST be set: `Strict-Transport-Security: max-age=31536000; includeSubDomains`.

### 13.5 Cookie Strategy

- Refresh tokens MAY be stored as HTTP-Only, Secure, SameSite=Strict cookies in browser environments as a defense-in-depth measure.
- If using cookies, CSRF token protection MUST be implemented using the Double Submit Cookie pattern or equivalent.
- Access tokens MUST NOT be stored in cookies (to avoid automatic inclusion in cross-site requests).
- The initial implementation will use Authorization Bearer headers; cookie strategy is a configuration option.

### 13.6 Rate Limiting

| Endpoint | Limit | Window | Action on Breach |
|----------|-------|--------|-----------------|
| POST /auth/login | 10 requests | 1 minute per IP | 429 Too Many Requests |
| POST /auth/forgot-password | 3 requests | 15 minutes per IP | 429 Too Many Requests |
| POST /auth/reset-password | 5 requests | 15 minutes per IP | 429 Too Many Requests |
| POST /auth/refresh | 30 requests | 1 minute per IP | 429 Too Many Requests |

### 13.7 Security Headers

All responses MUST include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy` (baseline, tightened in future Epics)
- `Strict-Transport-Security` (HTTPS environments)

### 13.8 Replay Protection

- JWT access tokens include a unique `jti` claim. In this Epic, revocation is time-based only (access tokens are short-lived). Future Epics may add a token revocation list.
- Refresh tokens are single-use and rotated, providing inherent replay protection.
- Password reset tokens are single-use and immediately consumed on use.

### 13.9 Brute Force Protection

- Account lockout (Section 12.2) provides the primary defense.
- Rate limiting (Section 13.6) provides secondary defense at the IP level.
- Both mechanisms operate independently and simultaneously.

### 13.10 Sensitive Data Protection

- Passwords MUST NEVER appear in: logs, API responses, audit events, error messages, or database plaintext fields.
- Tokens (JWT, refresh, reset) MUST NEVER appear in: server-side logs, audit event payloads, or error responses (only codes/references).
- Email addresses in audit logs MAY be partially masked (e.g., `s****@example.com`) in high-security environments.

### 13.11 OWASP Alignment

This Epic addresses the following OWASP Top 10 and ASVS categories:
- **A01 Broken Access Control** — Auth middleware on all protected routes.
- **A02 Cryptographic Failures** — Argon2id, TLS, token hashing.
- **A07 Identification and Authentication Failures** — Lockout, rate limiting, rotation, complex passwords.
- **A09 Security Logging and Monitoring Failures** — Structured audit events for all auth actions.

---

### 13.12 Authentication Flow

Login

↓

Validate Tenant

↓

Validate User

↓

Verify Password

↓

Generate Access Token

↓

Generate Refresh Token

↓

Store Refresh Token

↓

Create Session

↓

Write Audit Log

↓

Return Tokens

## 14. Database Requirements

The authentication module consists of the following services:

- AuthService
- PasswordService
- TokenService
- SessionService
- AuditService
- EmailService

### 14.1 Entities (Conceptual)

#### Users

The primary identity record for each person in the system. Contains immutable identity attributes (ID, email, created date) and mutable profile attributes (display name, account status, email verification state, lockout metadata). Each User MUST belong to exactly one Tenant.
Email uniqueness MUST be enforced per Tenant, not globally. The email field must be unique and indexed for lookup performance. Account status and lockout metadata must support indexed queries for high-frequency middleware validation.

#### UserCredentials

Stores the hashed password for a User. Separated from the User entity to enforce the principle of least privilege — the credential record is never included in standard user queries. Tracks: hashed password, hash algorithm identifier, last-changed timestamp, and a rolling list of recent password hashes for history enforcement. One credential record per User.

#### RefreshTokens

Stores hashed refresh token values and their associated metadata. Each record links to a User and optionally to a Session. Contains: hashed token, user reference, issued-at timestamp, expiry timestamp, revocation status, revoked-at timestamp, Remember Me flag, and client metadata (IP, user agent). Indexed by token hash for O(1) lookup. Expired and revoked tokens should be periodically purged.

#### PasswordResetTokens

Short-lived, single-use tokens for the forgot/reset password flow. Contains: hashed token, user reference, requested-at timestamp, expiry timestamp, consumed flag, and consumed-at timestamp. One active token per user at a time (prior tokens invalidated on new request). Indexed by token hash.

#### EmailVerificationTokens

Analogous to PasswordResetTokens but scoped to email confirmation. Contains the same structural fields. Indexed by token hash.

#### Sessions

Represents the context of a login event. Links to User and is associated with zero or more RefreshTokens. Contains: session ID, user reference, created-at timestamp, last-active timestamp, client metadata (IP, user agent at creation). Sessions are created on login and terminated on logout or expiry. Supports the "logout all devices" operation.

#### AuditLogs

Immutable event log for security actions. Contains: event ID, event type (enumerated), user ID (nullable), timestamp (UTC), IP address, user agent, request ID, outcome (SUCCESS/FAILURE), failure reason code, and a JSON metadata blob for extended context. Write-only from the application perspective; reads only for audit and security review purposes. Indexed by user ID and timestamp.

#### Tenant

Represents an isolated organization within the ERP.

Contains:

- Tenant ID
- Name
- Slug
- Status
- Created Date

This entity already exists conceptually in the platform and is referenced by authentication.

### 14.2 Relationships

```text
Tenant (Future Epic)
    │
    └───────────────┐
                    │
                    ▼
                  User (N:1)
                    │
      ┌─────────────┼──────────────────────────────────────┐
      │             │              │            │          │
      ▼             ▼              ▼            ▼          ▼
UserCredential   Session     RefreshToken   AuditLog   UserRole (Future Epic)
     (1:1)         (1:N)         (1:N)        (1:N)          (1:N)
                      │
                      ▼
               RefreshToken
                    (1:N)

User
 ├── PasswordResetToken     (1:N, typically 1 active)
 └── EmailVerificationToken (1:N, typically 1 active)
```

### Cardinality Summary

| Relationship | Cardinality |
|--------------|-------------|
| Tenant → User *(Future Epic)* | 1:N |
| User → UserCredential | 1:1 |
| User → Session | 1:N |
| Session → RefreshToken | 1:N |
| User → RefreshToken | 1:N |
| User → PasswordResetToken | 1:N (typically one active) |
| User → EmailVerificationToken | 1:N (typically one active) |
| User → AuditLog | 1:N |
| User → UserRole *(Future Epic)* | 1:N |

### 14.3 Data Lifecycle

| Entity | Creation | Retention | Deletion |
|--------|----------|-----------|----------|
| Tenant *(Future Epic)* | Tenant provisioning | Indefinite | Soft-delete only |
| User | Account provisioning | Indefinite (soft-delete) | Soft-delete only |
| UserCredential | Account provisioning | With User | With User |
| Session | Successful login | Until logout or expiry | Purged on scheduled cleanup |
| RefreshToken | Successful login or token rotation | Until revoked or expired | Purged after 7 days of being both expired and revoked |
| PasswordResetToken | Forgot Password request | Until consumed or expired | Purged after 24 hours of expiry |
| EmailVerificationToken | Account provisioning | Until consumed or expired | Purged after 48 hours of expiry |
| AuditLog | Authentication or security event | Minimum 90 days (configurable; archival supported) | Never deleted by the application (append-only) |

#### Lifecycle Notes

- Users are never physically deleted by the application; soft-delete preserves referential integrity and audit history.
- Refresh Tokens are rotated on every successful refresh. Previous tokens become immediately invalid.
- Only one active Password Reset Token should exist per user. Issuing a new token invalidates any previous active token.
- Only one active Email Verification Token should exist per user. Issuing a new token invalidates any previous active token.
- Sessions are automatically terminated when their associated Refresh Token expires or is revoked.
- Audit Logs are immutable and append-only. Records may be archived according to organizational retention policies but must never be modified.
- Tenant lifecycle management will be implemented in a future Epic and follows the same soft-delete strategy as Users.

### 14.4 Audit Event Types

The authentication subsystem MUST generate immutable audit events for all security-significant actions.

| Event Type | Description |
|------------|-------------|
| LOGIN_SUCCESS | User successfully authenticated |
| LOGIN_FAILED | Login failed due to invalid credentials |
| ACCOUNT_LOCKED | Account temporarily locked after failed attempts |
| ACCOUNT_UNLOCKED | Account automatically unlocked after lockout period |
| PASSWORD_CHANGED | Authenticated user changed password |
| PASSWORD_RESET_REQUESTED | Password reset initiated |
| PASSWORD_RESET_COMPLETED | Password successfully reset |
| EMAIL_VERIFICATION_SENT | Verification email generated |
| EMAIL_VERIFIED | Email successfully verified |
| TOKEN_REFRESHED | Refresh token successfully rotated |
| TOKEN_REVOKED | Refresh token revoked |
| SESSION_CREATED | New authenticated session established |
| SESSION_REVOKED | Session terminated |
| LOGOUT | Current session terminated |
| LOGOUT_ALL | All user sessions revoked |

Each audit record SHOULD include:

- Event ID
- UTC Timestamp
- User ID (nullable)
- Request ID
- IP Address
- User Agent
- Outcome (SUCCESS / FAILURE)
- Failure Reason Code (if applicable)

---

---

## 15. Authentication Flow Diagrams

### 15.1 Login Flow

```text
┌────────────┐
│   Browser  │
└─────┬──────┘
      │
      │ POST /api/v1/auth/login
      ▼
┌────────────┐
│ FastAPI API│
└─────┬──────┘
      │
      │ Validate Request
      ▼
┌──────────────────────┐
│ User Repository      │
└─────┬────────────────┘
      │
      │ Load User
      ▼
┌──────────────────────┐
│ Password Verification│
└─────┬────────────────┘
      │
      │ Success
      ▼
┌──────────────────────┐
│ Generate JWT         │
│ Generate Refresh     │
│ Create Session       │
└─────┬────────────────┘
      │
      ▼
 Return Tokens
      │
      ▼
 Browser Stores Tokens
```

---

### 15.2 Token Refresh Flow

```text
Access Token Expired
        │
        ▼
POST /api/v1/auth/refresh
        │
        ▼
Validate Refresh Token
        │
        ▼
Rotate Refresh Token
        │
        ▼
Generate New Access Token
        │
        ▼
Return New Tokens
```

---

### 15.3 Logout Flow

```text
User Clicks Logout
        │
        ▼
POST /api/v1/auth/logout
        │
        ▼
Revoke Refresh Token
        │
        ▼
Terminate Session
        │
        ▼
Clear Client Tokens
        │
        ▼
Redirect to Login
```

---

## 16. API Requirements

The following is the high-level endpoint inventory for this Epic. Detailed request/response models, status codes, and OpenAPI contracts will be defined in the `contracts/` documentation.
Every protected endpoint MUST validate Tenant ID before processing the request.

### 16.1 Public Endpoints (No Authentication Required)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/login` | Authenticate with email and password; returns tokens |
| `POST` | `/api/v1/auth/refresh` | Exchange refresh token for new access token |
| `POST` | `/api/v1/auth/forgot-password` | Initiate password reset flow |
| `POST` | `/api/v1/auth/reset-password` | Complete password reset with token and new password |
| `POST` | `/api/v1/auth/verify-email` | Consume email verification token |

### 16.2 Protected Endpoints (JWT Required)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/logout` | Revoke current session (single device) |
| `POST` | `/api/v1/auth/logout-all` | Revoke all sessions for the current user |
| `GET` | `/api/v1/auth/me` | Return current authenticated user's identity |
| `POST` | `/api/v1/auth/change-password` | Change password for authenticated user |

### 16.3 Versioning

All endpoints are versioned under `/api/v1/`. Future breaking changes will introduce `/api/v2/`.

---

## 17. Frontend Requirements

### 17.1 Login Page (`/login`)

- **Layout**: Centered card form, DevSphere ERP branding, responsive (mobile-friendly).
- **Fields**: Email address (validated client-side), Password (masked, toggleable visibility).
- **Remember Me**: Checkbox, defaulting to unchecked.
- **Actions**: "Log In" submit button, "Forgot your password?" link.
- **Loading State**: Button disabled with spinner during API call.
- **Error States**:
  - Invalid credentials: Inline error below form ("Invalid email or password").
  - Account locked: Inline error with unlock time estimate.
  - Network error: Toast notification ("Connection error. Please try again.").
  - Rate limited: Inline error ("Too many attempts. Please wait and try again.").
- **Success**: Redirect to dashboard (or originally intended route) with access token stored in memory and refresh token in secure storage.
- **Accessibility**: WCAG 2.1 AA compliance; keyboard navigable; ARIA labels on all form fields.

### 17.2 Forgot Password Page (`/forgot-password`)

- **Layout**: Centered card form, single email field.
- **Fields**: Email address.
- **Actions**: "Send Reset Link" button, "Back to Login" link.
- **Loading State**: Button disabled with spinner.
- **Result State**: Regardless of email match, display: "If an account with this email exists, a reset link has been sent. Check your inbox."
- **Error States**: Validation errors (invalid email format), rate limiting message.

### 17.3 Reset Password Page (`/reset-password?token=...`)

- **Layout**: Centered card form.
- **Fields**: New Password (with strength indicator), Confirm New Password.
- **Token Handling**: Token extracted from URL query parameter; validated before form is shown.
- **Invalid Token State**: If token is missing, expired, or invalid — show error message with link to Forgot Password.
- **Loading State**: Button disabled with spinner.
- **Validation**: Real-time password strength feedback, confirmation match check.
- **Success**: Redirect to Login with success notification ("Password updated. Please log in.").

### 17.4 Protected Route Guard

- All routes except `/login`, `/forgot-password`, and `/reset-password` MUST be protected.
- Unauthenticated access to a protected route MUST redirect to `/login` with the intended route stored for post-login redirect.
- Route guard MUST check for a valid access token (or trigger refresh) before rendering.

### 17.5 Session Persistence

- Access tokens MUST be stored in memory only (not localStorage, not cookies by default) to mitigate XSS token theft.
- Refresh tokens MAY be stored in HttpOnly cookies (server-set) or in localStorage with documented tradeoffs.
- Tenant information MUST be restored together with the authenticated session after page refresh.
- The initial implementation will use in-memory access tokens and localStorage refresh tokens with documentation of the XSS tradeoff.
- On page reload, the client MUST attempt to refresh the access token using the persisted refresh token before redirecting to login.

### 17.6 Automatic Token Refresh

- The HTTP client layer (API client) MUST intercept 401 responses with `code: TOKEN_EXPIRED`.
- On token expiry, the client MUST queue the original request, attempt token refresh, and retry on success.
- Multiple concurrent 401 responses MUST result in a single refresh attempt (request queuing with shared promise).
- If refresh fails, all queued requests MUST be rejected and the user redirected to Login.

### 17.7 Logout Flow

- Logout MUST call the logout API endpoint to revoke the server-side session.
- On completion (success or network failure), the client MUST clear all token storage and redirect to `/login`.
- The frontend MUST prevent access to any cached user data after logout.

---

---

## 18. Authentication State Machine

The authentication lifecycle follows the state transitions below.

```text
                +------------------+
                | UNAUTHENTICATED  |
                +------------------+
                          |
                          | Login Success
                          ▼
                +------------------+
                | AUTHENTICATED    |
                +------------------+
                          |
                          | Access Token Expires
                          ▼
                +------------------+
                | TOKEN REFRESH    |
                +------------------+
                  |            |
        Success   |            | Failure
                  ▼            ▼
        +----------------+   +------------------+
        | AUTHENTICATED  |   | UNAUTHENTICATED  |
        +----------------+   +------------------+
                  |
                  | Logout
                  ▼
        +------------------+
        | UNAUTHENTICATED  |
        +------------------+
```

### State Descriptions

| State | Description |
|--------|-------------|
| UNAUTHENTICATED | No valid authenticated session exists. |
| AUTHENTICATED | User has a valid access token. |
| TOKEN REFRESH | Client requests a new access token using a valid refresh token. |
| LOGGED OUT | Session revoked and client credentials cleared. |

## 19. Validation Rules

### 19.1 Email Validation

- MUST be a valid email format (RFC 5321 compatible).
- MUST be normalized to lowercase before storage and lookup.
- Leading/trailing whitespace MUST be stripped.
- Maximum length: 254 characters (RFC 5321).
- MUST NOT accept email addresses containing HTML tags or script content.

### 19.2 Password Validation

- Minimum length: 12 characters.
- Maximum length: 128 characters.
- MUST contain at least one uppercase letter (A-Z).
- MUST contain at least one lowercase letter (a-z).
- MUST contain at least one digit (0-9).
- MUST contain at least one special character from the set: `!@#$%^&*()_+-=[]{}|;':",.<>?/`.
- MUST NOT be the user's email address.
- MUST NOT appear in the common password list.
- MUST NOT match any of the last 5 stored password hashes.
- Validation errors MUST be specific (e.g., "Password must contain at least one uppercase letter") not generic.

### 19.3 Token Validation

- Reset and verification tokens MUST be URL-safe base64 strings of at least 43 characters (representing >=256 bits).
- Tokens MUST be compared using constant-time comparison to prevent timing attacks.
- Tokens MUST be validated for: existence, non-expiry, non-consumption, user ownership.

### 19.4 Authorization Header Validation

- MUST follow the format: `Authorization: Bearer {token}`.
- Missing header on protected route: 401.
- Malformed header (wrong scheme, empty token): 401.
- Valid header with invalid JWT (tampered, wrong signature): 401.
- Valid header with expired JWT: 401 with `code: TOKEN_EXPIRED`.

### 19.5 Request Size Limits

- Login request body: 1 KB maximum.
- All auth request bodies: 4 KB maximum.
- Requests exceeding limits: 413 Request Entity Too Large.

---

## 20. Error Scenarios

| Scenario | Expected Behavior | HTTP Status | Error Code |
|----------|------------------|-------------|------------|
| Invalid email format at login | Client-side validation before submit | — | — |
| Incorrect password | Generic "Invalid credentials" error | 401 | `INVALID_CREDENTIALS` |
| Unregistered email | Same generic response as wrong password | 401 | `INVALID_CREDENTIALS` |
| Locked account | "Account temporarily locked. Try again at {time}" | 423 | `ACCOUNT_LOCKED` |
| Inactive account | "Your account is inactive. Contact support." | 403 | `ACCOUNT_INACTIVE` |
| Deleted account | Same as unregistered (anti-enumeration) | 401 | `INVALID_CREDENTIALS` |
| Expired access token | 401 with specific code for client detection | 401 | `TOKEN_EXPIRED` |
| Missing Authorization header | "Authentication required" | 401 | `AUTH_REQUIRED` |
| Malformed JWT | "Invalid token" | 401 | `INVALID_TOKEN` |
| Expired refresh token | "Session expired. Please log in again." | 401 | `REFRESH_TOKEN_EXPIRED` |
| Revoked refresh token | "Session terminated." | 401 | `REFRESH_TOKEN_REVOKED` |
| Expired reset token | "Reset link has expired. Please request a new one." | 400 | `RESET_TOKEN_EXPIRED` |
| Consumed reset token | "Reset link has already been used." | 400 | `RESET_TOKEN_CONSUMED` |
| Invalid reset token | "Invalid reset link." | 400 | `INVALID_TOKEN` |
| Password complexity failure | Specific field-level validation errors | 422 | `VALIDATION_ERROR` |
| Password history violation | "Cannot reuse a recent password" | 422 | `PASSWORD_HISTORY_VIOLATION` |
| Incorrect current password (change) | "Current password is incorrect" | 403 | `INVALID_CREDENTIALS` |
| Rate limit exceeded | "Too many requests. Try again in {seconds} seconds." | 429 | `RATE_LIMITED` |
| Clock skew (JWT iat in future) | "Invalid token" (configurable leeway of 60 seconds) | 401 | `INVALID_TOKEN` |
| Network failure (client-side) | Toast: "Connection error. Please try again." | — | — |
| Database unavailable | "Service temporarily unavailable." | 503 | `SERVICE_UNAVAILABLE` |
| Scenario                       | Expected Behavior              | HTTP |
| ------------------------------ | ------------------------------ | ---- |
| Tenant mismatch                | Access denied                  | 403  |
| User belongs to another tenant | Generic authentication failure | 401  |


---

## 21. Success Criteria

### Measurable Outcomes

| ID | Criterion | Measurement Method |
|----|-----------|-------------------|
| SC-001 | Users can complete the full login flow in under 3 seconds on standard broadband | End-to-end browser timing in integration test |
| SC-002 | Login endpoint handles 500 concurrent authentication requests without error | Load test with 500 VUs |
| SC-003 | Token refresh completes in under 200ms at p95 under normal load | API latency monitoring |
| SC-004 | Account lockout activates within 5 consecutive failed attempts within the configured window | Automated test case |
| SC-005 | A locked account cannot log in even with correct credentials | Automated test case |
| SC-006 | A consumed or expired reset token is rejected 100% of the time | Automated test case with replay |
| SC-007 | Passwords are never present in any log output, API response, or error message | Log inspection run on full test suite execution |
| SC-008 | JWT access tokens expire and trigger automatic refresh without user disruption | Browser-level integration test |
| SC-009 | All functional requirements (FR-001 to FR-075) have corresponding passing automated tests | Test suite run with FR coverage |
| SC-010 | Backend authentication module test coverage >= 90% | Coverage report |
| SC-011 | All quality gates pass: black, ruff, mypy (backend); tsc, eslint, prettier (frontend) | CI pipeline execution |
| SC-012 | All authentication API endpoints return structured error responses conforming to the platform error schema | Contract test run |
| SC-013 | Password Forgot and Reset flows work end-to-end with stubbed email delivery | Integration test |
| SC-014 | Logout revokes the session; subsequent use of the refresh token returns 401 | Automated test case |
| SC-015 | All security-significant auth events produce durable audit records | Database query validation post-test-run |

---

## Non Functional Requirements

Login Response Time:
<300ms (excluding database cold start)

Token Refresh:
<100ms

Password Hashing:
500ms maximum

Availability:
99.9%

Concurrent Logins:
500 simultaneous users

Concurrent Refresh Requests:
1000/minute

## 22. Risks

### 22.1 Security Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Refresh token theft via XSS | Medium | High | Short-lived access tokens; HttpOnly cookie option; CSP headers |
| Refresh token replay from concurrent requests | Low | Medium | Atomic rotation in database transaction; detect and alert on double-use |
| Timing attack on password comparison | Low | High | Argon2id built-in timing safety; constant-time token comparison |
| Credential stuffing via leaked password lists | High | High | Rate limiting, lockout, common password list enforcement |
| JWT secret compromise | Low | Critical | Environment variable only; rotation procedure documented |
| Audit log tampering | Low | High | Append-only design; future: WORM storage or external audit sink |

### 22.2 Operational Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Email delivery failure for password reset | Medium | Medium | Retry mechanism in email stub; user-facing resend option |
| Database unavailability blocking all auth | Low | Critical | Health endpoint reflects DB state; circuit breaker pattern recommended |
| Argon2 hashing too slow for burst login traffic | Low | Medium | Tune Argon2 parameters on target hardware; async hashing if needed |
| Refresh token table growth (high volume) | Medium | Low | Background job to purge expired/revoked tokens; indexed expiry column |

### 22.3 Implementation Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| SQLite test suite incompatibility with auth-specific SQL | Low | Medium | Epic 001 already established SQLite compatibility layer |
| Next.js middleware complexity for route protection | Low | Low | Use Next.js Middleware API (middleware.ts); well-established patterns |
| Concurrent refresh race condition | Medium | Medium | Explicit database-level locking or optimistic concurrency on token records |

---

## 23. Dependencies
 - Tenant resolution middleware from the platform foundation will be reused by the authentication layer.

### 23.1 Internal — Epic 001 (Foundation Platform)

The following Epic 001 components are consumed directly and MUST NOT be modified:

| Component | How Used in Epic 002 |
|-----------|---------------------|
| `BaseRepository` | `UserRepository`, `RefreshTokenRepository`, `AuditLogRepository` extend it |
| `BaseService` | `AuthService`, `PasswordService`, `TokenService` extend it |
| `ApplicationException` and subclasses | Auth-specific exceptions extend these (`UnauthorizedException`, `ForbiddenException`) |
| `get_db` dependency | Used in all auth route handlers |
| `get_settings()` | Auth configuration fields (token secrets, expiry, lockout thresholds) added |
| Database engine and session factory | No changes required |
| Logging infrastructure | Structured auth audit events use the established logging pattern |
| Request ID middleware | `request_id` included in all audit events |
| Docker Compose | No changes required; auth services use the existing PostgreSQL container |
| Next.js frontend foundation | Auth pages built using the existing `AppLayout`, component library, and API client |
| Health endpoint | No changes required |

### 23.2 External

| Dependency | Purpose | Notes |
|-----------|---------|-------|
| Email delivery service | Send password reset and verification emails | Stubbed/mocked in this Epic; integration is future work |
| Argon2 library (`argon2-cffi` or equivalent) | Password hashing | New dependency added in this Epic |
| PyJWT or `python-jose` | JWT signing and validation | New dependency |
| `slowapi` or equivalent | Rate limiting for FastAPI | New dependency |

---

## 24. Future Extension Points

This Epic is designed to be extended without redesign. The following capabilities can be added in future Epics with minimal structural changes:

| Extension | Hook Point |
|-----------|-----------|
| **Multi-Factor Authentication (MFA)** | Post-login "pending MFA" state in session; second factor endpoint |
| **Time-Based OTP (TOTP)** | MFA method implementation on top of MFA hook |
| **Google / GitHub / Microsoft OAuth2** | New credential type in `UserCredential`; OAuth2 callback handler |
| **SAML / LDAP Enterprise SSO** | New identity provider adapter; maps external identity to internal User |
| **Magic Links** | New token type analogous to `PasswordResetToken`; login via link |
| **Passkeys (WebAuthn)** | New credential type; challenge-response flow |
| **Device Trust** | Additional claims on `RefreshToken`; device registration flow |
| **Biometric Authentication** | Client-side biometric unlocks locally-stored credential; server-side unchanged |
| **Immediate Access Token Revocation** | Token revocation blocklist checked in auth middleware |
| **Admin User Management** | Uses identity layer unchanged; adds admin-scoped endpoints (Epic 003+) |
| **Audit Log Export / SIEM Integration** | AuditLog entity format is already structured for external ingestion |
| Extension              | Hook Point      |
| ---------------------- | --------------- |
| Organization Switching | Tenant Resolver |


---

## 25. Glossary
 - Tenant

A logically isolated organization that owns users, roles, permissions, data, and sessions inside the shared ERP platform.

| Term | Definition |
|------|-----------|
| **Access Token** | A short-lived JWT presented by a client to prove authentication for API requests. Valid for 15 minutes by default. |
| **Argon2id** | A modern, memory-hard password hashing algorithm recommended by OWASP for credential storage. Resistant to GPU and ASIC brute-force attacks. |
| **Audit Event** | An immutable, structured log record of a security-significant action, retained for compliance and incident investigation. |
| **Authentication** | The process of verifying the identity of a user — confirming *who* they are. Distinct from Authorization. |
| **Authorization** | The process of determining *what* an authenticated identity is permitted to do. Not implemented in this Epic. |
| **Brute Force Protection** | A combination of rate limiting and account lockout designed to prevent automated credential guessing attacks. |
| **Credential** | A secret (in this system: a password hash) used to verify a user's claimed identity. |
| **CSRF** | Cross-Site Request Forgery — an attack that tricks a browser into making unintended authenticated requests. Mitigated via SameSite cookies and/or CSRF tokens. |
| **Email Verification** | The process of confirming that a user owns the email address they registered with, by clicking a time-limited link. |
| **Forgot Password** | A self-service flow allowing a user to initiate a password reset by providing their registered email address. |
| **HttpOnly Cookie** | A browser cookie that cannot be accessed by JavaScript, used to store tokens securely against XSS attacks. |
| **Identity** | The set of attributes that uniquely identify a user within the system (ID, email, display name). |
| **JWT** | JSON Web Token — a signed, compact token format used as a stateless access token. Contains claims about the bearer's identity and session. |
| **Lockout** | A temporary suspension of login capability after a configured number of consecutive failed authentication attempts. |
| **OWASP** | The Open Web Application Security Project; a non-profit producing security guidance including the Top 10 and Authentication Cheat Sheet. |
| **Password History** | A record of previous password hashes maintained to prevent users from recycling recent passwords. |
| **Rate Limiting** | Restricting the number of requests a client can make within a time window, to prevent brute force and denial-of-service attacks. |
| **Refresh Token** | A long-lived, opaque, single-use token used to obtain new access tokens without re-entering credentials. Stored hashed server-side. |
| **Remember Me** | An optional user preference to extend the refresh token's lifespan for sessions on trusted devices. |
| **Reset Token** | A short-lived, single-use cryptographic token delivered via email to authorize a password reset operation. |
| **Session** | The server-side record of an authenticated login event, linking a user to their refresh token(s) and client context. |
| **Session Revocation** | Invalidating an active session by marking its associated refresh tokens as revoked. |
| **Soft Delete** | Marking a record as deleted without removing it from the database, preserving it for audit and referential integrity. |
| **TOTP** | Time-Based One-Time Password; a form of MFA where a time-synchronized code is required at login. Not in scope for this Epic. |
| **Token Rotation** | The practice of issuing a new refresh token and invalidating the old one on each use, limiting the window of opportunity for a stolen token. |
| **XSS** | Cross-Site Scripting — an attack that injects malicious scripts into a web page, potentially stealing tokens from JavaScript-accessible storage. |

---

*This specification is the authoritative source of truth for Epic 002 — Authentication & Identity. No implementation work should begin until this document is reviewed and approved. Changes to scope must be reflected in this document and reviewed before proceeding.*
