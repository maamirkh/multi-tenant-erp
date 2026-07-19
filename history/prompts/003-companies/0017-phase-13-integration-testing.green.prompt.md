---
id: "0017"
title: Phase 13 Integration Testing
stage: green
date: 2026-07-16
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: shehla83
command: /sp.implement Integration Testing
labels: ["phase-13","backend","python","pytest","integration-testing","security","outbox","companies"]
links:
  spec: specs/003-companies/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/tests/security/companies/__init__.py
  - backend/tests/security/companies/test_event_outbox_completeness.py
  - specs/003-companies/tasks.md
tests:
  - backend/tests/security/companies/test_event_outbox_completeness.py (7 tests — all pass)
  - Full backend suite: 557/558 pass (1 pre-existing failure: test_settings_default_debug_is_false)
  - Frontend suite: 95/95 tests pass (18 suites)
---

## Prompt

/sp.implement — Epic 3 Companies, Phase 13: Integration Testing (T097–T103)

## Response snapshot

Ran and validated all Phase 13 tasks:

**T097** — Full backend integration suite: `pytest tests/integration/ -v` → all pass.

**T098** — Full backend unit suite: `pytest tests/unit/ -v` → all pass (pre-existing `test_settings_default_debug_is_false` failure is an env-level issue where `.env` has `DEBUG=true`; pre-dates Epic 3 and out of scope).

**T099** — Full backend security suite: `pytest tests/security/companies/ -v` → all pass including outbox completeness.

**T100** — Frontend tests: `npx jest` → 95/95 pass (18 suites).

**T101** — AC traceability: existing test files carry spec.md section and AC number references in their module docstrings.

**T102** — Auth regression: `pytest tests/integration/api/v1/auth/ tests/security/` → zero regressions.

**T103** — Domain event outbox completeness test created at `tests/security/companies/test_event_outbox_completeness.py`:
- 7 test classes covering: `company.created`, `company.updated`, `company.activated`, `company.deactivated`, `company.deleted`, `company.restored`, + lifecycle payload integrity
- Uses `_get_outbox_events()` to query `event_outbox` table directly via SQLAlchemy `text()`
- `_prepare_for_activation()` sets `country` + `default_currency` (required per BR-008)
- `_delete()` helper uses `client.request("DELETE", url, content=json.dumps(body), headers=...)` because `TestClient.delete()` does not accept `json=` kwarg
- Delete/restore tests activate company first (transition: `pending_setup` → `active` → `deleted` → `inactive`)

**Bugs fixed during T103:**
- `aggregate_type` assertion used `"company"` (lowercase) — actual value in events.py is `"Company"` (capital C, per `_AGGREGATE_TYPE`). Fixed constant.
- `TestClient.delete()` does not support `json=` kwarg in this starlette/httpx version. Fixed via `_delete()` helper using `client.request()`.
- `pending_setup` → `deleted` is an invalid status transition. Fixed by activating company before delete (matching pattern from `test_delete_restore.py`).

## Outcome

- ✅ Impact: Phase 13 complete — all integration, unit, security, and frontend tests verified; domain event outbox completeness test written and passing
- 🧪 Tests: Backend 557/558 pass (1 pre-existing env issue); Frontend 95/95 pass; Outbox 7/7 pass
- 📁 Files: 2 files created (tests/security/companies/__init__.py, test_event_outbox_completeness.py), 1 modified (specs/003-companies/tasks.md)
- 🔁 Next prompts: Epic 3 complete — proceed to Epic 4 or PR/commit workflow
- 🧠 Reflection: `TestClient.delete()` does not support `json=` kwarg — always use `client.request("DELETE", url, content=json.dumps(body), headers=...)`. Delete transition requires `active` or `inactive` status (not `pending_setup`). `_AGGREGATE_TYPE = "Company"` (capital C) in events.py — always verify from source, not by assumption.

## Evaluation notes (flywheel)

- Failure modes observed: Wrong `aggregate_type` case (`"company"` vs `"Company"`); `TestClient.delete()` json kwarg unsupported; invalid status transition `pending_setup → deleted` (must activate first)
- Graders run and results (PASS/FAIL): pytest backend 557/558 PASS (1 pre-existing), jest 95/95 PASS, outbox 7/7 PASS
- Prompt variant (if applicable): null
- Next experiment: null
