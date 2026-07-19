---
id: "0022"
title: Docker startup debug and env fixes
stage: misc
date: 2026-07-16
surface: agent
model: claude-sonnet-4-6
feature: 003-companies
branch: 003-companies
user: shehla83
command: /sp.implement (continued session)
labels: ["docker","debugging","env","dependencies","poetry","dockerfile"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/pyproject.toml
  - backend/poetry.lock
  - backend/Dockerfile
  - backend/.env
  - backend/modules/companies/repositories/company_audit_log_repository.py
  - .env (root)
tests:
  - "597/598 tests pass (1 pre-existing failure: test_settings_default_debug_is_false)"
---

## Prompt

User asked (across multiple messages):
1. Check which .env files are needed for frontend and backend, explain root .env files, remove unnecessary ones
2. Run the full project and check for issues, resolving any found
3. Docker Desktop can run the project for testing?
4. After running: backend shows uvicorn error with traceback ending at `import_from_string(self.app)` — diagnose and fix

## Response snapshot

**Issues found and fixed:**

1. **`JWT_SECRET_KEY` missing from root `.env`** → Pydantic "Field required" on Docker startup. Added generated key.
2. **`tzdata` missing from `pyproject.toml`** → `zoneinfo` returns empty set on Windows; `America/New_York` validation fails. Added `tzdata = ">=2024.1"`.
3. **`boto3` missing from `pyproject.toml`** → `core/storage/s3_client.py` imports boto3 at module level; runtime would fail. Added `boto3 = ">=1.26"`.
4. **Unused `# type: ignore[override]`** in `company_audit_log_repository.py` → mypy error. Removed comments.
5. **`curl: not found` in Docker healthcheck** → `python:3.12-slim` has no curl. Added `apt-get install -y curl` to both `development` and `production` Dockerfile stages.
6. **Regenerated `poetry.lock`** to include boto3 and tzdata.

**.env structure established:**
- Root `.env` → used by Docker Compose (contains `@db`, `@minio` hostnames)
- `backend/.env` → used for local dev (contains `@localhost` hostnames)
- `frontend/.env.example` → template for frontend devs
- `backend/.env.example` → DELETED (outdated, redundant)

**Final state:**
- All 4 containers healthy: `api (healthy)`, `db (healthy)`, `minio (healthy)`, `web (up)`
- API health check: `{"status": "healthy", "checks": {"database": "ok", "auth_config": "ok"}}`
- 597/598 tests passing (1 pre-existing failure unrelated to this session)

## Outcome

- ✅ Impact: Docker stack fully operational; uvicorn import error resolved by adding missing dependencies and curl
- 🧪 Tests: 597/598 pass; 1 pre-existing failure (test_settings_default_debug_is_false - DEBUG=true in .env overrides default)
- 📁 Files: pyproject.toml, poetry.lock, Dockerfile, .env (root), backend/.env, company_audit_log_repository.py
- 🔁 Next prompts: Create PR for Epic 003, begin Epic 004
- 🧠 Reflection: Missing system-level packages (curl, tzdata) in slim Docker images are a common footgun — should be caught in Dockerfile review

## Evaluation notes (flywheel)

- Failure modes observed: Missing deps not caught by tests (boto3 masked by null client); slim Docker image missing curl for healthcheck
- Graders run and results (PASS/FAIL): pytest 597/598 PASS
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Add a Dockerfile lint step to pre-commit that verifies healthcheck deps are installed
