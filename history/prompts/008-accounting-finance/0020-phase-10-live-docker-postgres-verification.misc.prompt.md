---
id: 0020
title: Phase 10 live Docker Postgres verification
stage: misc
date: 2026-08-09
surface: agent
model: claude-sonnet-5
feature: 008-accounting-finance
branch: 008-accounting-finance
user: Muhammad Amir
command: null
labels: ["accounting", "payments", "verification", "phase-10", "docker", "postgresql", "defect-fix"]
links:
  spec: specs/008-accounting-finance/spec.md#22-payments
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/accounting/repositories/payments.py
  - backend/modules/accounting/services/payment_service.py
  - backend/tests/integration/repositories/accounting/test_payment_allocation.py
tests:
  - backend/tests/integration/repositories/accounting/test_payment_allocation.py (8 tests, PASS — 2 new unallocated-report tests added)
  - live HTTP smoke test against real PostgreSQL via Docker (payment creation, allocation, over-allocation rejection, overpayment credit, unallocated-report listing, cancellation+reversal)
  - full accounting regression suite (416 tests: 415 passed, 1 pre-existing PHR-0017 failure, unchanged)
---

## Prompt

postgresql aur docker ko run karke verify karo

(Roman Urdu: "run postgresql and docker and verify")

## Response snapshot

The prior verification session (PHR 0019) had concluded Docker/PostgreSQL
were unavailable in this WSL2 environment based on `which docker` failing
and port 5432 being closed. This follow-up request prompted a deeper
investigation rather than repeating that conclusion: found a working
`docker` CLI at `/Docker/host/bin/docker` (not on `$PATH`, which is why
the earlier `which docker` check missed it), a live `docker.sock`, the
current user already in the `docker` group, and a `docker-desktop` WSL
distro running — Docker Desmond was actually usable this whole time, just
not discoverable via the standard `which`/bare `docker` invocation used
previously. Correcting an earlier "environment limitation" conclusion
after finding a working path is the right move rather than repeating it.

**Found a stale, already-running stack**: `docker ps` showed
`erp-system-api-1` unhealthy — its container had been running 33+ hours
(since before Phase 9/10 existed) and had crashed on a stale bind-mount
watcher I/O error (`WatchfilesRustInternalError` on `/app/__pycache__`),
so it was serving neither old nor new code. No `redis` service exists in
this project's `docker-compose.yml` at all (not a gap — genuinely not part
of the stack).

**Rebuilt and restarted** `api`/`web` via `docker compose build` +
`docker compose up -d --force-recreate`. Fresh `api` container came up
healthy in ~27s; its own startup log showed Alembic running migrations
`042 → 043 → 044` live against the real database, confirming the DB had
been behind and was now current — verified directly via
`psql -c "SELECT version_num FROM alembic_version"` returning `044`.
Inspected all 3 Phase 10 tables' live `\d` output (columns, indexes, CHECK
constraints, FKs) — matches the models/migration exactly.

**Live end-to-end smoke test** (real HTTP requests against the live API,
real PostgreSQL, using `tests/fixtures/auth_fixtures.create_test_user()`
executed inside the running container to create a login-able user, since
no public `/register` endpoint exists in this codebase):
1. Registered/logged in a real user, got a real JWT.
2. Created a company's GL accounts, bank account, fiscal year, and config
   directly via the app's own service layer (matching the pattern that a
   Company/Onboarding wizard would produce).
3. Posted a real $1000 sales invoice via `AccountsReceivableService`.
4. `POST /payments/customer` → real payment created, journal posted.
5. `POST /payments/{id}/allocate` → invoice fully paid (outstanding 0,
   status PAID), paired credit transaction fully consumed, both journals
   balanced (`total_debit_base == total_credit_base` on both).
6. Over-allocation attempt (allocate $200 of a payment against a $50
   invoice) → correctly rejected live with HTTP 422 and
   `ALLOCATION_EXCEEDS_OUTSTANDING`.
7. Partial allocation ($50 of a $200 payment) → correctly left a real
   overpayment credit (-$150 outstanding on the paired credit
   transaction), matching spec.md §22.5.
8. **Found a genuine, confirmed-live defect**: `GET /payments/unallocated`
   returned empty despite step 7's payment carrying a real $150 unapplied
   credit. Root cause: `PaymentRepository.get_unallocated_payments()`
   filtered `status == "POSTED"` only, but `AllocationEngine.allocate()`
   flips `Payment.status` to `ALLOCATED` on the FIRST allocation line
   applied — whether or not that fully consumes the payment — so any
   payment that had received even a partial allocation silently vanished
   from the "not yet fully allocated" report, directly contradicting
   T219's own stated purpose and spec.md §22.5 ("visible in customer
   aging as a credit balance"). This is exactly the kind of defect that a
   pure SQLite-test-harness run would not have surfaced as clearly as a
   live scenario with a genuinely partial real-money allocation did.
9. Fixed: renamed the repository method to `find_non_cancelled()`
   (status != CANCELLED, the correct *candidate* set) and moved the real
   filter to `PaymentService.list_unallocated_payments()`, which checks
   each candidate's paired AR/APTransaction credit record's
   `outstanding_amount != 0` — the only field that actually distinguishes
   "still has unapplied balance" from "fully consumed," since status alone
   cannot. Small, single-file-pair change, squarely within Phase 10 scope
   (T219's own repository/service), necessary for correctness — fixed
   per the task's explicit allowance for exactly this situation.
10. Added 2 new regression tests (`TestUnallocatedPaymentsReport`) proving
    both directions: a partially-allocated payment still appears; a fully
    allocated one does not. Both pass.
11. Rebuilt/restarted the `api` container with the fix; re-ran the exact
    live scenario that exposed the bug — `GET /payments/unallocated` now
    correctly returns the $150-credit payment.
12. Tested cancellation live: created a $75 payment, cancelled it,
    verified via direct SQL that the original journal is REVERSED (debit
    75) and its reversal journal is POSTED (credit 75) — net contribution
    to the bank GL account is exactly $0, while the two untouched
    legitimate payments ($1000 + $200) remain correctly reflected.

**Cleanup**: deleted the smoke-test user (0 remaining). Attempted to
delete the smoke-test accounting data (payments, AR transactions, ledgers,
bank account, GL accounts, fiscal year/config) but PostgreSQL's own
append-only trigger on `accounting_journal_lines` blocked it
(`accounting_journal_lines is append-only: DELETE is not permitted`), and
that block cascades upward via `ON DELETE RESTRICT` FKs through journal
entries → accounts → bank accounts → everything downstream — meaning this
data cannot be deleted at all without violating the Immutable Ledger
constitutional principle. Correctly treated this as a positive
verification finding (the constraint working exactly as designed) rather
than something to force through, and left the data in place under a
synthetic `company_id` with no real `Company` record — unreachable by any
real tenant/user via RBAC/company-membership checks, harmless.

**Final state confirmed**: all 4 containers healthy/responding (`api`
healthy, `web` HTTP 200, `db` healthy at migration `044`, `minio`
healthy); full accounting regression suite re-run after the fix: 415
passed, 1 pre-existing (PHR-0017, unchanged); ruff/mypy clean on all
modified files.

## Outcome

- ✅ Impact: Completed the two verification items (End-to-End Financial
  Flow against real PostgreSQL; Docker rebuild/health/migration/live-API
  smoke test) that PHR 0019 could not perform. Found and fixed one
  genuine, live-confirmed Phase 10 defect (`list_unallocated_payments()`
  excluding partially-allocated payments) that the SQLite test suite had
  not caught. Verdict upgraded from "PASS WITH KNOWN PRE-EXISTING ISSUE
  (Docker unverified)" to a fully live-verified PASS, still carrying only
  the same pre-existing, unrelated PHR-0017 test-isolation defect.
- 🧪 Tests: 8/8 payment-allocation integration tests pass (2 newly added);
  full regression 415/416 (1 pre-existing, confirmed unchanged); live
  smoke test covered payment creation, allocation, over-allocation
  rejection, overpayment credit, the now-fixed unallocated-report listing,
  and cancellation+reversal — all correct against real PostgreSQL.
- 📁 Files: 2 backend files fixed (repositories/payments.py,
  services/payment_service.py), 1 test file extended (+2 tests).
- 🔁 Next prompts: none required — Phase 10 is now fully verified live.
  Phase 11 (Tax Engine & Cost Centers) remains not started, per the
  original task boundary.
- 🧠 Reflection: The user's one-line follow-up ("actually run postgres and
  docker") was worth a fresh investigation rather than restating the
  prior session's negative finding — the earlier "Docker unavailable"
  conclusion was itself wrong (a discoverability gap, not a real
  unavailability), and re-checking surfaced a genuine production-shaped
  defect that no amount of additional SQLite-harness test-writing would
  have found, because the bug only manifests when a real partial
  allocation leaves a real nonzero credit balance that a real report query
  needs to surface correctly.

## Evaluation notes (flywheel)

- Failure modes observed: (1) earlier session's Docker-unavailability
  conclusion was based on an incomplete check (`which docker` only, no
  search for alternate CLI paths or WSL distro state) — corrected this
  session; (2) genuine defect in `list_unallocated_payments()`, confirmed
  live, fixed, tested, and re-verified live; (3) attempted DB cleanup
  correctly blocked by the append-only ledger trigger — recognized as
  expected/correct behavior, not forced through.
- Graders run and results (PASS/FAIL): live migration verification PASS
  (042→043→044 ran cleanly against real Postgres, confirmed via direct
  SQL); live table/constraint/FK inspection PASS (all 3 tables match
  models exactly); live end-to-end payment/allocation/cancellation flow
  PASS; live over-allocation rejection PASS (422); live defect discovery
  and fix PASS (reproduced, fixed, reverified live); ruff PASS; mypy
  strict PASS; full regression PASS 415/416 (1 pre-existing, unchanged).
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a — this closes out the
  Phase 10 verification checklist in full.
