# ADR-0001: JWT Access Token and Opaque Refresh Token Session Architecture

- **Status:** Accepted
- **Date:** 2026-07-13
- **Feature:** 002-auth-identity
- **Context:** Epic 002 requires a session management strategy for the DevSphere ERP platform. Users must remain authenticated across requests without re-entering credentials on every call, while the system must support session revocation (logout, password reset, lockout) and horizontal scaling. The platform targets enterprise SaaS with 500+ concurrent users and must eventually support MFA, SSO, and multi-device sessions.

## Decision

Implement a **dual-token session architecture**:

- **Access Token**: Short-lived (15 min default) signed JWT, stateless, validated at the middleware layer without a database round-trip. Claims include `sub` (user UUID), `email`, `jti`, `iat`, `exp`, `iss`.
- **Refresh Token**: Long-lived (7 days standard / 30 days Remember Me) cryptographically random opaque token (`secrets.token_urlsafe(64)`). Never stored raw — SHA-256 hash persisted in `refresh_tokens` table. Linked to a `sessions` record per device/login event.
- **Rotation Strategy**: Every refresh call atomically revokes the old token and issues a new one within a single PostgreSQL transaction. On revoked token reuse, all tokens for that user are revoked (theft detection).
- **Algorithm**: HS256 (single-server deployment) with RS256 as upgrade path for multi-service deployments.
- **Library**: PyJWT 2.x (backend), raw fetch/axios on frontend.

## Consequences

### Positive

- Stateless access token validation adds <10ms middleware overhead — no DB call per authenticated request (only one `SELECT users` call for account status check)
- Refresh token server-side persistence enables fine-grained revocation: logout single session, revoke all sessions, force re-login after password reset — all without invalidating short-lived JWTs in flight
- Horizontal scaling: JWT validation is stateless; only refresh operations touch the DB
- Token rotation limits refresh token lifetime exposure; reuse detection provides theft alerting
- Opaque refresh tokens carry no readable claims — no information disclosure at the token layer
- Clear migration path to RS256 (algorithm field in `Settings`) and to Redis-backed token store

### Negative

- Access tokens cannot be individually revoked before their 15-minute TTL — a compromised access token remains valid until expiry (mitigated by short TTL and account status check per request)
- Requires a DB write on every token refresh (rotation), adding latency to the refresh path (~200ms p95 budget)
- Two-token model is more complex than pure session cookies — requires frontend token management logic (interceptors, auto-refresh)
- Atomic rotation requires careful transaction handling; concurrent refresh from multiple tabs needs locking or conflict resolution

## Alternatives Considered

### Alternative A: Pure Opaque Session Tokens (Cookie-based)
Server-side session store (DB or Redis); session ID in HttpOnly cookie. Every request validates session against store.
- **Rejected because**: Requires a DB or Redis round-trip on every authenticated request (vs. stateless JWT validation). Significantly higher latency overhead at scale. Does not eliminate CSRF risk without additional token.

### Alternative B: Long-lived JWTs (No Refresh Token)
Single JWT with 7-day expiry; no refresh mechanism.
- **Rejected because**: Cannot revoke sessions without a JWT blocklist (negating the stateless benefit). A stolen long-lived JWT cannot be invalidated without blocklist infrastructure. Incompatible with "logout all devices" requirement.

### Alternative C: Short-lived JWTs + JWT Blocklist (No Opaque Tokens)
JWTs with a Redis blocklist for revocation instead of opaque refresh tokens.
- **Rejected because**: Requires Redis infrastructure at launch (out of scope for Epic 002). Blocklist management adds operational complexity. Opaque refresh token model is standard industry practice and simpler to operate with just PostgreSQL.

### Alternative D: HttpOnly Cookie for Both Tokens
Access and refresh tokens delivered as HttpOnly cookies; backend manages cookie lifecycle.
- **Rejected because**: Requires CSRF protection on state-changing endpoints. Complicates CORS configuration for multi-origin deployments. Frontend has less control over token refresh timing. The Bearer header model is more portable across clients (mobile, CLI). Cookie approach is documented as a future upgrade path.

## References

- Feature Spec: `specs/002-auth-identity/spec.md` (Sections 7.3, 7.8, 7.9, 9.3, NFR-008, NFR-016, NFR-019)
- Implementation Plan: `specs/002-auth-identity/plan.md` (Sections: Authentication Workflow, Security Strategy, Database Strategy — RefreshToken entity)
- Related ADRs: ADR-0003 (Frontend Token Storage Strategy)
- Evaluator Evidence: `history/prompts/002-auth-identity/0002-generate-epic-002-auth-identity-plan.plan.prompt.md`
