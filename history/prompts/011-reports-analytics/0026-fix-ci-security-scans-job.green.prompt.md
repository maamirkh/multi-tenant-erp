---
id: 0026
title: Fix CI Security Scans Job
stage: green
date: 2026-09-30
surface: agent
model: claude-opus-5-5
feature: 011-reports-analytics
branch: 011-reports-analytics
user: Muhammad Amir
command: pehle security scans fix karo
labels: ["ci", "security", "bandit", "pip-audit", "dependencies"]
links:
  spec: specs/011-reports-analytics/spec.md
  ticket: null
  adr: null
  pr: https://github.com/maamirkh/multi-tenant-erp/pull/9
files:
  - .github/workflows/backend.yml
  - backend/pyproject.toml
  - backend/poetry.lock
  - backend/modules/inventory/router.py
  - specs/011-reports-analytics/release-signoff.md
tests:
  - bandit -r modules/ core/ -ll (no --exit-zero) — 0 findings
  - poetry 1.8.3 export --only main + pip-audit --require-hashes --disable-pip — no known vulnerabilities
  - mypy . 0 issues / 1494 files; ruff check + format clean
  - auth integration/unit + argon2 + jwt claims + product image upload — 169 passed
  - tests/security/*.py (top level) — 73 passed
---

## Prompt

pehle security scans fix karo

## Response snapshot

Root causes of the always-failing CI "Security Scans" job (pre-existing since before Epic 11):

1. bandit and pip-audit were not dependencies, so `poetry run` could not find them.
2. The pip-audit flags `--require-hashes=false` and `--severity` do not exist.
3. bandit ran with `--exit-zero`, so it could never fail.

Fixes:

- Added `bandit ^1.9.4` and `pip-audit ^2.10.1` to the dev group. Lock diff: additions only.
- Workflow now runs `poetry export --only main -f requirements.txt` (verified with the CI's Poetry 1.8.3 against the 2.4.1-generated lock), then `pip-audit --require-hashes --disable-pip`. bandit now runs without `--exit-zero`.
- Resolved the findings the working scanners reported:
  - bandit B324: `hashlib.md5(..., usedforsecurity=False)` for the storage-key fingerprint. The hash value is unchanged.
  - anyio 4.14.1 → 4.15.1.
  - cryptography 49.0.0 → 50.0.1.
  - pyjwt 2.13.0 → 2.15.1 (CVE-2026-102274, found once the scan actually ran).

## Outcome

- ✅ Impact: Security Scans runs real checks and passes locally; open items 2 and 3 in release-signoff.md are resolved.
- 🧪 Tests: see the `tests:` front-matter; the full backend suite will run in CI on push.
- 📁 Files: see the `files:` front-matter.
- 🔁 Next prompts: confirm the CI run is green; decide the remaining open items (multi-currency, row drill-down, due_overdue speed).
- 🧠 Reflection: a scanner that cannot run hides real advisories — pyjwt only surfaced after the job was fixed.

## Evaluation notes (flywheel)

- Failure modes observed: the CI Poetry version (1.8.3) differs from the local one (2.4.1); `poetry export` needed verification against the CI version.
- Graders run and results (PASS/FAIL): bandit PASS, pip-audit PASS, mypy/ruff PASS, targeted tests PASS.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): align the CI POETRY_VERSION with the local Poetry 2.x.
