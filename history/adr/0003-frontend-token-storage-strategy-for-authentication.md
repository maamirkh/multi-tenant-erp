# ADR-0003: Frontend Token Storage Strategy for Authentication

- **Status:** Accepted
- **Date:** 2026-07-13
- **Feature:** 002-auth-identity
- **Context:** Epic 002 delivers frontend authentication with two token types: a short-lived JWT access token (15 min) and a long-lived opaque refresh token (7–30 days). The frontend must persist the refresh token across page reloads/browser restarts (session persistence requirement) while minimising the XSS attack surface. The two primary threats are XSS (JavaScript code reading tokens from accessible storage) and CSRF (forged cross-site requests). The strategy must work with a stateless bearer-header authentication model (not cookies) and must not require backend changes to HTTP cookie handling in this Epic.

## Decision

Implement a **split-storage model** with a documented upgrade path:

**Access Token: JavaScript module-level variable (in-memory)**
- Stored as a module-level variable in `tokenStorage.ts`, not in `localStorage` or `sessionStorage`
- Lives only for the duration of the page session; cleared on tab close or page reload
- Attached to every API request via an axios/fetch request interceptor reading from memory
- Never serialized to any persistent browser storage

**Refresh Token: `localStorage`**
- Persisted across page reloads and browser restarts (satisfies session persistence requirement)
- Read on app mount by `AuthContext` to re-hydrate session via `POST /auth/refresh`
- Key: `erp_refresh_token` (namespaced to avoid conflicts)
- Cleared on logout, on refresh failure, and on forced re-authentication events

**Auto-refresh: `useTokenRefresh` hook**
- Schedules `setTimeout` at 80% of access token lifetime (12 min for 15-min tokens)
- On timer expiry: calls `POST /auth/refresh` → stores new access token in memory → reschedules timer
- On refresh failure: calls `logout()`, clears `localStorage`, redirects to `/login`

**Upgrade Path: HttpOnly Cookie (documented, not implemented in this Epic)**
- If XSS risk escalates or a security audit requires it, the backend can `Set-Cookie: refresh_token=<value>; HttpOnly; Secure; SameSite=Strict` and read the cookie implicitly on `POST /auth/refresh`
- This would require: backend cookie-setting on login/refresh, CSRF token on state-changing endpoints, and removal of `localStorage` writes — no frontend token storage changes needed beyond removing the `localStorage.setItem` call
- Tracked as a follow-up security hardening task

## Consequences

### Positive

- Access token in memory eliminates the primary XSS token theft vector: malicious JavaScript injected via XSS cannot read the access token from `document.cookie` or `localStorage`
- Bearer header authentication eliminates CSRF attacks for access token usage (browsers do not auto-send Authorization headers cross-origin)
- Refresh token in `localStorage` enables seamless session persistence across page reloads without requiring backend cookie infrastructure
- `tokenStorage.ts` abstraction layer means switching from `localStorage` to cookies requires changing one file, not all components
- Simple to reason about and debug; no Service Worker or IndexedDB complexity

### Negative

- Refresh token in `localStorage` is readable by any JavaScript on the same origin — a successful XSS attack could steal the refresh token and create new sessions
- Access token is lost on page reload; refresh call on every mount adds ~200ms latency to initial page load
- No native browser mechanism to prevent `localStorage` access from injected scripts (mitigated by CSP headers, which reduce XSS opportunity)
- In-memory access token means concurrent tabs share no auth state — each tab independently manages its own access token and refresh schedule (acceptable for ERP use case)

## Alternatives Considered

### Alternative A: Both Tokens in localStorage
Access and refresh tokens stored in `localStorage`; no in-memory overhead.
- **Rejected because**: Both tokens readable by XSS JavaScript. A compromised access token enables immediate API abuse (within 15-min TTL). Defense-in-depth requires access token to be harder to steal than refresh token.

### Alternative B: Both Tokens in HttpOnly Cookies (Cookie-only)
Backend sets HttpOnly, Secure, SameSite=Strict cookies; frontend never reads tokens.
- **Rejected because**: Requires backend to set and manage cookies (CORS `credentials: "include"`, `Set-Cookie` on login/refresh, `SameSite` policy). Adds CSRF protection requirement (double-submit cookie or synchronizer token). Out of scope for Epic 002 backend work. Documented as upgrade path.

### Alternative C: Access Token in sessionStorage, Refresh Token in localStorage
`sessionStorage` for access (cleared on tab close), `localStorage` for refresh.
- **Rejected because**: `sessionStorage` is still accessible to JavaScript on the same origin — no XSS protection improvement over `localStorage`. In-memory module variable provides stronger isolation than `sessionStorage`.

### Alternative D: Service Worker Token Cache
Service Worker intercepts all fetch calls; stores tokens in an isolated cache inaccessible to page JavaScript.
- **Rejected because**: Adds significant implementation complexity (Service Worker lifecycle, update handling, test infrastructure). Requires HTTPS in development. Premature optimization for an ERP application without a demonstrated XSS threat. Could be adopted later if CSP + in-memory approach proves insufficient.

### Alternative E: Both Tokens in Memory Only (No Persistence)
No `localStorage`; refresh token lives only in memory; user re-authenticates on every page load.
- **Rejected because**: Violates session persistence requirement (FR-042, FR-043). Users of a business ERP application must remain logged in across page reloads and browser restarts. Pure in-memory storage would make the Remember Me feature meaningless.

## References

- Feature Spec: `specs/002-auth-identity/spec.md` (Sections 7.8 Remember Me, NFR-018, FR-041–FR-044)
- Implementation Plan: `specs/002-auth-identity/plan.md` (Sections: Frontend Strategy — Token Storage, Security Strategy — XSS Mitigation, CSRF Considerations)
- Related ADRs: ADR-0001 (JWT Session Architecture)
- Evaluator Evidence: `history/prompts/002-auth-identity/0002-generate-epic-002-auth-identity-plan.plan.prompt.md`
