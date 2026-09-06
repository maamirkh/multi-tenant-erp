---
id: 0008
title: Auth freshness and migration preflight
stage: plan
date: 2026-08-19
surface: agent
model: claude-opus-5
feature: 009a-platform-admin
branch: 009a-platform-admin
user: Muhammad Amir
command: /sp.plan
labels: ["platform-admin", "plan", "correction", "authentication", "migration-safety"]
links:
  spec: specs/009a-platform-admin/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - specs/009a-platform-admin/plan.md
 - specs/009a-platform-admin/research.md
 - specs/009a-platform-admin/data-model.md
 - specs/009a-platform-admin/quickstart.md
 - history/prompts/009a-platform-admin/0008-auth-freshness-and-migration-preflight.plan.prompt.md
tests:
 - none (planning-only correction pass; no code, migrations, or tests written)
---

## Prompt

Perform ONE FINAL TARGETED CORRECTION PASS on the existing Epic 9A `plan.md`.

[Two corrections, with an explicit preserve-list and a mandated seven-pattern stale-statement search:
**Correction 1** — reactivation must require true re-authentication; old refresh credentials must not bypass the suspension invalidation watermark. The plan compared `Company.access_invalidated_at` against the access token's `iat`, but a pre-suspension refresh credential redeemed after reactivation mints a token with a fresh `iat > access_invalidated_at`, restoring access without any login. Required an authentication-freshness concept that survives refresh (`auth_time` semantics: set on login, carried unchanged across refresh), with mandatory repository verification of existing claims, refresh/session structure, how refresh reconstructs claims, the smallest backward-compatible way to retain original authentication time, and whether a JWT claim, a Session field, or both are needed — explicitly "Do NOT assume the mechanism from this prompt." 11 required guarantees, explicit multi-device semantics, an access-token-issuance vs authentication-event distinction, and 6 named test cases A–F.
**Correction 2** — migration 057 must handle pre-existing suspended companies safely. The CHECK constraint requires `pre_suspension_status IS NOT NULL` when `status='suspended'`, but 057 adds the column as NULL; the plan silently assumed no such row exists. Required an explicit preflight that fails loudly with operator remediation rather than guessing, backfilling, or weakening the constraint, plus 4 migration tests.
Full verbatim text in the conversation transcript for this turn.]

## Response snapshot

**Did not run `setup-plan.sh`** (would `cp` the template over `plan.md`). Verified auth internals before choosing any mechanism, as instructed.

**Decisive repository finding (third pass)**: `AuthService.login()` calls `self._session_repo.create_session(...)` → a **new `Session` row** with a new `created_at`. `AuthService.refresh()` calls `rotate_refresh_token(...)` then `create_access_token(session_id=new_record.session_id)` → **reuses the existing session and never creates one**. Therefore `Session.created_at` *is already* the authentication-event timestamp the correction asks for: it advances only on a genuine login, survives unlimited refreshes unchanged, is server-generated (`BaseModel`, `server_default=func.now()`, documented immutable after INSERT), and is reachable via the already-signed `sid` claim surfaced as `CurrentUser.session_id`.

**Mechanism selected**: compare `Session.created_at <= Company.access_invalidated_at` at the company-access boundary. This required **neither a new JWT claim nor a new Session column**, and — notably — allowed *removing* the `CurrentUser.token_issued_at` plumbing the previous correction pass had added, so Epic 9A now makes **zero** changes to `get_current_user()`, `CurrentUser`, or the JWT payload. The prompt's suggested `auth_time` claim was evaluated and rejected as strictly worse: it changes the token format, requires both login and refresh to populate it correctly, and is more tamper-exposed than a value that lives in the database rather than the token.

Added an explicit issuance-vs-authentication table (`iat` advances on refresh and is never an authorization input; `Session.created_at` advances only on login and is), §10.3.1 documenting per-device multi-device semantics as a matrix (each device recovers independently, and only by a real login; one device re-authenticating never restores another), and test cases A–F with case B called out as the specific regression guard that must fail if anyone re-keys the check to `iat`.

**Correction 2**: added §33.1 with the concrete preflight — query `companies WHERE status='suspended'` before creating the constraint; zero rows → proceed; any rows → raise naming the affected companies and the remediation options, having altered nothing. Documented *why* guessing is unacceptable: `status='suspended'` records where a company *is*, never where it *was*, so fabricating a restore target would make `suspended → pre-suspension status` non-deterministic — the exact defect ADR-12 exists to prevent. Added 4 migration tests including "no arbitrary state is invented" and a real-PostgreSQL up/down/up cycle.

**Propagated** to §3.1 findings, §9.3, §10.2–§10.4, §26, §28 (3 new threats), §31, §32, §33/§33.1, §36, ADR-6, ADR-12, §38 (3 new risks incl. "someone later simplifies the check back to `iat`"), §40 (3 new resolved unknowns), §42 (5 new/revised checklist lines). Synced `research.md` Decision 1 (now records the third fact and 5 rejected alternatives), `data-model.md` (watermark semantics + preflight + explicit "no auth-schema change"), and `quickstart.md` (step 8 is now the refresh-bypass check, plus the multi-device matrix).

Ran the mandated seven-pattern stale search — all clean; the single remaining match is a threat-table row *describing* the mitigation. ADR count unchanged at 13; migration sequence unchanged at `057`–`061` (content-only change inside `057`).

## Outcome

- ✅ Impact: closed a real authentication bypass (a pre-suspension refresh credential could have silently restored access to a reactivated tenant with no login), and removed an unstated assumption that could have corrupted lifecycle state on any database with a pre-existing suspended company. The auth fix also *reduced* the change footprint — the universal auth path is now completely untouched by this Epic.
- 🧪 Tests: N/A (planning). Strategy gained mandatory cases A–F for authentication freshness/cross-tenant/multi-device, plus 4 migration-preflight cases.
- 📁 Files: `plan.md` (1096→1190), `research.md` (84→88), `data-model.md` (258→262), `quickstart.md` (124→125). `spec.md`/`constitution.md` untouched.
- 🔁 Next prompts: `/sp.tasks` (not started, per instruction).
- 🧠 Reflection: the instruction not to assume the prompt's mechanism paid off twice over — the repository already contained the exact primitive needed (`Session.created_at`), so the correct fix was smaller than both the flawed design it replaced *and* the design the prompt proposed. Worth noting the previous pass introduced the `iat` flaw while fixing a different one; the general lesson is that "token was minted recently" and "the human authenticated recently" are distinct properties that JWT `iat` conflates by default.

## Evaluation notes (flywheel)

- Failure modes observed: one stale artifact (`research.md` Decision 1 still described the `token_issued_at`/`iat` mechanism) survived the plan.md edits and was caught only by the cross-artifact sweep — reinforcing that the sweep must cover supporting artifacts, not just `plan.md`.
- Graders run and results (PASS/FAIL): seven-pattern stale search — PASS; ADR numbering integrity — PASS (13, sequential); migration sequence unchanged — PASS; §42 cross-check — PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
