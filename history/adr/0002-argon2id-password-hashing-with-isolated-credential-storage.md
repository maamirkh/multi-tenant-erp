# ADR-0002: Argon2id Password Hashing with Isolated Credential Storage

- **Status:** Accepted
- **Date:** 2026-07-13
- **Feature:** 002-auth-identity
- **Context:** Epic 002 requires secure password storage for the DevSphere ERP platform. Passwords are the primary credential for authentication before MFA or SSO are available. The system must resist offline dictionary attacks (if the DB is compromised), enforce password policies, track password history to prevent reuse, and remain tunable as hardware improves. Credential data must not be accessible to any code path that only needs user identity information (e.g., listing users, populating JWT claims).

## Decision

Implement a **two-part credential storage strategy**:

**Hashing Algorithm: Argon2id**
- Library: `argon2-cffi` (Python CFFI bindings to the reference implementation)
- Parameters: `time_cost=3`, `memory_cost=65536` (64 MB), `parallelism=4` — exceeds OWASP 2024 minimum recommendations
- Hash format: Argon2 encoded string (algorithm identifier + params + salt + hash) — single column, self-describing, forward-compatible with param upgrades
- All parameters configurable via `Settings` without code changes

**Storage Architecture: Separate `user_credentials` Table**
- `user_credentials` table is 1:1 with `users`, but accessed only by `PasswordService` and `UserCredentialRepository`
- Columns: `user_id` (FK), `password_hash` (TEXT), `password_history` (JSONB array of last N hashes), `last_changed_at` (TIMESTAMPTZ)
- `password_history` retains last 5 hashes (configurable via `PASSWORD_HISTORY_COUNT`); new passwords verified against all history entries before acceptance
- No query in the system JOINs `user_credentials` unless the operation explicitly requires credential data

## Consequences

### Positive

- Argon2id is the OWASP-recommended winner of the Password Hashing Competition (2015); memory-hard by design, resistant to GPU/ASIC parallel attacks that defeat bcrypt and PBKDF2
- Self-describing encoded hash format means parameter upgrades can be handled at next login (verify with old params, rehash with new params) — zero-downtime migration path
- Isolated `user_credentials` table enforces single responsibility: identity queries (GET /me, JWT claims, user listings) never fetch or risk accidentally leaking credential data
- Password history in JSONB is simple to extend (increase N, add timestamp per entry) without schema migration
- `last_changed_at` timestamp is available for future password expiry policies without additional schema work
- `argon2-cffi` is actively maintained and uses the C reference implementation — battle-tested, not a pure-Python reimplementation

### Negative

- Argon2id hashing takes 100–300ms per operation with configured params — login endpoint p95 is budgeted at 800ms to account for this (vs. ~50ms for bcrypt)
- Each password history check requires running `argon2.verify()` N times (up to 5) against old hashes — adds ~500ms worst-case on change-password (acceptable; this is not a hot path)
- Separate table adds a JOIN (or second query) on any operation requiring both identity and credential data; `PasswordService` must always fetch credentials explicitly
- `argon2-cffi` requires a C compiler at Docker build time (already satisfied by Python base image; noted for custom slim images)

## Alternatives Considered

### Alternative A: bcrypt (via passlib)
Industry-standard; well-understood; `passlib` provides a stable Python interface.
- **Rejected because**: bcrypt is limited to 72-byte inputs (longer passwords are silently truncated); work factor is CPU-only (vulnerable to GPU attacks); not memory-hard. Argon2id is the current NIST SP 800-63B and OWASP recommendation for new systems.

### Alternative B: scrypt
Memory-hard, similar goals to Argon2id; available in Python stdlib (`hashlib.scrypt`).
- **Rejected because**: Argon2id is more flexible (independent time/memory/parallelism parameters); Argon2id has broader ecosystem support and is the PHC winner. scrypt has no self-describing encoded format, requiring manual parameter serialization.

### Alternative C: PBKDF2-HMAC-SHA256
NIST-approved, FIPS-compliant, available in Python stdlib.
- **Rejected because**: CPU-only; susceptible to GPU/ASIC acceleration. Only relevant if FIPS compliance is required (not a current requirement). Argon2id is strictly stronger for the ERP threat model.

### Alternative D: Credential Fields Embedded in `users` Table
Single table with `password_hash`, `password_history` columns alongside identity fields.
- **Rejected because**: Any query fetching user records (listings, JWT population, audit) would load credential data into memory unnecessarily. Violates Single Responsibility; makes it easy for future developers to accidentally include credential hash in API responses. Separate table enforces isolation at the schema level.

### Alternative E: Password History as Separate `password_history` Table
Row-per-hash with foreign key to `user_credentials`.
- **Rejected because**: JSONB array on `user_credentials` is simpler (no JOIN, no pagination, bounded at N entries), sufficient for the use case, and avoids an additional table for a bounded dataset. If N ever exceeds ~20 entries, a separate table would be reconsidered.

## References

- Feature Spec: `specs/002-auth-identity/spec.md` (Sections 7.5–7.7, NFR-011, FR-039)
- Implementation Plan: `specs/002-auth-identity/plan.md` (Sections: Module Breakdown — PasswordService, Database Strategy — UserCredentials entity, Security Strategy — Argon2id)
- Related ADRs: ADR-0001 (JWT Session Architecture)
- Evaluator Evidence: `history/prompts/002-auth-identity/0002-generate-epic-002-auth-identity-plan.plan.prompt.md`
