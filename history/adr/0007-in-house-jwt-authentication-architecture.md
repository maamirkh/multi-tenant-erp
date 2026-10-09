# ADR-0007: In-House JWT Authentication Architecture

- **Status:** Accepted
- **Date:** 2026-10-09
- **Deciders:** Project owner (sole maintainer)
- **Feature:** 012-production-readiness
- **Supersedes:** the planned Constitution §39 foundational ADR "Why Better Auth" (never created)
- **Context:** Constitution v1.2.1 required Better Auth in four places: §6.3, §15 step 2, §16 and §39.

  The platform was instead built from Epic 2 onward with an in-house design:
  - ADR-0001: JWT access token plus opaque refresh token, with a sessions table;
  - ADR-0002: Argon2id password hashing;
  - ADR-0003: frontend token storage.

  No Better Auth dependency exists in `frontend/package.json` or `backend/pyproject.toml`. ADR-0001 never mentions Better Auth or the Constitution. The deviation was acknowledged only in Epic 9A *plan* §3.1, which cannot override the Constitution (§4), so the deviation was never ratified.

  Epic 12 (production readiness) made this a blocking decision, D-11. The owner chose to keep and formally approve the in-house design, subject to an evidence-based security review (`specs/012-production-readiness/clarifications.md` §3.1).

<!-- Significance checklist: Impact ✅ (security/platform), Alternatives ✅, Scope ✅ (every authenticated request) -->

## Decision

Formally approve the existing in-house authentication architecture as the platform's authentication approach.

**Tokens and sessions**
- **Access token:** a PyJWT HS256 JWT with a 15-minute default lifetime. The algorithm is pinned, and the issuer and audience are verified. The `sid` claim binds the token to a server-side session.
- **Refresh token:** opaque and stored only as a SHA-256 hash. It is rotated on every use, and replay of a used token revokes all of the user's refresh tokens.
- **Sessions:** a server-side `sessions` table, user-scoped. Tenant scope is enforced on every request through company membership and permission checks, never inferred from the session.

**Credentials**
- Argon2id hashing with isolated credential storage (ADR-0002), account lockout and password history.
- Password-reset and email-verification tokens are hashed, unique, expiring and single-use.
- Password reset and password change revoke all sessions and refresh tokens. Member deactivation, suspension, locking and archiving revoke sessions too.

**Separation and replaceability**
- Platform administrators use a separate session and token model (Epic 9A).
- Authentication remains behind `backend/core/auth/interfaces.py`, which keeps it "modular and replaceable" as §16 requires.

**Conditions of approval** — Epic 12 MUSTs. Production launch is blocked until all of them pass:
- **SEC-24:** immediate rejection of access tokens from revoked sessions, on every worker and instance, failing closed (G-23).
- **SEC-04/05:** a strict, tested frontend CSP (G-10).
- **SEC-20:** rate limiting consistent across processes (G-05).
- **SEC-26:** no platform-level authority reachable through a tenant token. This includes removing the latent `super_admin` checks on `CurrentUser.roles` (G-25).
- **FR-PRD-032:** real transactional email for reset and verification, with fail-safe behaviour (G-09).

If any of these conditions cannot be met safely within this design, the evidence and the Better Auth trade-offs return to the owner. No authentication migration happens without explicit approval.

**Ownership:** the maintainer owns this component. Authentication dependencies (PyJWT, argon2-cffi) are covered by dependency scanning in CI, and an authentication security review is part of every release.

## Consequences

### Positive

- No migration of users, credentials or sessions before the first production launch.
- Existing API contracts (`/api/v1/auth/*`) are preserved, together with the authentication test suites (77 unit, 56 integration, 31 security) and the 70 cross-tenant/IDOR test files.
- Production risks are fixed inside a design the team already understands and tests.
- The Constitution matches the implementation again.

### Negative

- The team, not a library, maintains authentication security. Future MFA, OAuth or SSO must be built in-house, or brought in through a new ADR and amendment.
- HS256 uses one shared secret. A rotation runbook is required, and every verifier must protect the secret.
- The refresh token stays in `localStorage` (ADR-0003). CSP reduces the token-theft risk but does not remove it. Moving to HttpOnly cookie sessions is deferred, triggered by a security audit or an XSS finding.

## Alternatives Considered

**Alternative A — Adopt Better Auth through a migration-safe rollout.** Rejected.
- Better Auth is a TypeScript framework. It would add a JavaScript authentication runtime with database credentials (the Next.js server or a new service), and FastAPI would have to trust its sessions or tokens.
- The migration would involve:
  - users, credentials and sessions;
  - Argon2id compatibility hooks or forced password resets;
  - invalidating every session at cutover;
  - platform-admin authentication;
  - re-implementing lockout, password history, replay detection and audit;
  - rewriting most authentication tests.
- None of the production gaps above would close on its own: CSP, email, revocation checks and rate limiting would still be needed.

**Alternative B2 — Keep the code but leave the Constitution unchanged.** Rejected. It leaves an unratified violation of §16 and §44 #7.

## Reasoning

The repository evidence shows a mature, heavily tested implementation. Its real production risks are fixable inside it. Switching frameworks would reopen authentication and tenant isolation at the riskiest point, just before launch, without removing those risks. Formal approval plus explicit, tested conditions is the smallest change that is also safe.

## References

- Constitution v2.0.0: §6.3, §15, §16, §39, §40, §50
- Spec: `specs/012-production-readiness/spec.md` (G-22, G-23, G-25; SEC-04, SEC-05, SEC-20, SEC-24, SEC-25, SEC-26; FR-PRD-032)
- Evidence: `specs/012-production-readiness/clarifications.md` §3
- Related ADRs: ADR-0001, ADR-0002, ADR-0003
- Code: `backend/core/auth/dependencies.py`, `backend/core/auth/interfaces.py`, `backend/modules/auth/services/`, `backend/modules/platform_admin/dependencies.py`, `frontend/src/lib/auth/`
