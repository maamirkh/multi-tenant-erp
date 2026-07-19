# Authentication Quick Start — DevSphere ERP

**Epic**: 002 — Authentication & Identity
**Stack**: FastAPI (backend) · Next.js App Router (frontend) · PostgreSQL 16

This guide takes you from a clean checkout to a running authentication system in under 10 minutes.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Environment Setup](#2-environment-setup)
3. [Start Services](#3-start-services)
4. [Run Database Migrations](#4-run-database-migrations)
5. [Seed a Test User](#5-seed-a-test-user)
6. [Run the Test Suite](#6-run-the-test-suite)
7. [API Usage Examples](#7-api-usage-examples)
8. [Common Troubleshooting](#8-common-troubleshooting)

---

## 1. Prerequisites

| Tool | Minimum Version | Install |
|------|----------------|---------|
| Docker + Docker Compose | 24.x / 2.x | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Python | 3.12+ | [python.org](https://python.org) |
| Node.js | 20 LTS+ | [nodejs.org](https://nodejs.org) |
| Git | any | — |

---

## 2. Environment Setup

### 2.1 Copy the example environment file

```bash
cp .env.example .env
```

### 2.2 Generate required secrets

Generate a **JWT signing secret** (minimum 32 chars; use 64+ in production):

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Paste the output as the value of `JWT_SECRET_KEY` in `.env`.

Generate a **general application secret**:

```bash
openssl rand -hex 32
```

Paste the output as the value of `SECRET_KEY` in `.env`.

### 2.3 Minimum required .env values

```dotenv
# Backend required
DATABASE_URL=postgresql://devsphere:changeme_dev_password@db:5432/devsphere_dev
SECRET_KEY=<your-generated-secret>

# Authentication required
JWT_SECRET_KEY=<your-generated-jwt-secret>

# Frontend required
NEXT_PUBLIC_API_URL=http://localhost:8000
```

> **Security**: Never commit `.env` to version control. The `.gitignore` is pre-configured to exclude it.

---

## 3. Start Services

```bash
docker compose up --build
```

Wait until you see all three services healthy:

```
✓ db    — PostgreSQL ready on :5432
✓ api   — FastAPI ready on :8000
✓ web   — Next.js ready on :3000
```

The frontend is accessible at **http://localhost:3000**.
The backend API at **http://localhost:8000/api/v1**.
The API documentation at **http://localhost:8000/docs** (development mode only).

---

## 4. Run Database Migrations

Migrations run automatically on startup. To run manually (e.g., after adding new migrations):

```bash
# Inside the running api container
docker compose exec api alembic upgrade head

# Or from the host with the backend venv active
cd backend && alembic upgrade head
```

To check the current migration state:

```bash
docker compose exec api alembic current
```

To roll back the last migration:

```bash
docker compose exec api alembic downgrade -1
```

---

## 5. Seed a Test User

No CLI seed command exists yet. Use the Python snippet below inside the `api` container or the backend virtual environment:

```bash
docker compose exec api python - <<'EOF'
from core.config.settings import Settings
from core.database.session import SessionLocal
from modules.auth.models.user import User
from modules.auth.models.user_credential import UserCredentials
from modules.auth.services.password_service import PasswordService
from datetime import datetime, UTC
import uuid

settings = Settings()
db = SessionLocal()

email = "admin@example.com"
password = "DevAdmin@1234!"

existing = db.query(User).filter(User.email == email).first()
if existing:
    print(f"User already exists: {email}")
else:
    user = User(
        email=email,
        display_name="Dev Admin",
        account_status="ACTIVE",
        is_email_verified=True,
    )
    db.add(user)
    db.flush()

    svc = PasswordService(settings)
    creds = UserCredentials(
        user_id=user.id,
        password_hash=svc.hash_password(password),
        password_history=[],
        last_changed_at=datetime.now(UTC),
    )
    db.add(creds)
    db.commit()
    print(f"Created user: {email} / {password}")
    print(f"User ID: {user.id}")

db.close()
EOF
```

---

## 6. Run the Test Suite

### Backend tests

```bash
# All tests
cd backend
pytest

# With coverage report
pytest --cov=modules --cov=core --cov-report=term-missing

# Specific test categories
pytest tests/unit/                       # Unit tests only
pytest tests/integration/                # Integration tests only
pytest tests/security/                   # Security tests only
pytest -m "not slow"                     # Skip slow tests (Argon2 timing)
```

### Frontend tests

```bash
cd frontend
npm test                  # Run all tests (watch mode)
npm test -- --watchAll=false  # Single run (CI mode)
```

### Run everything

```bash
# Backend
cd backend && pytest -q

# Frontend
cd frontend && npx jest --passWithNoTests --forceExit
```

---

## 7. API Usage Examples

All examples assume the API is running at `http://localhost:8000`.

Replace `<ACCESS_TOKEN>` and `<REFRESH_TOKEN>` with values from the login response.

---

### POST /api/v1/auth/login

Authenticate and receive tokens.

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@example.com",
    "password": "DevAdmin@1234!",
    "remember_me": false
  }' | python -m json.tool
```

**Example response** (200 OK):

```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "dGhpcyBpcyBhbiBvcGFxdWUgcmVmcmVzaA...",
    "token_type": "bearer",
    "expires_in": 900
  },
  "message": "Login successful.",
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

**Error responses**:
- `401` — Invalid email or password (`INVALID_CREDENTIALS`)
- `423` — Account locked after 5 failed attempts (`ACCOUNT_LOCKED`)
- `429` — Rate limited (10 requests/minute per IP)

---

### POST /api/v1/auth/refresh

Exchange a valid refresh token for new tokens. The old token is immediately revoked.

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<REFRESH_TOKEN>"}' | python -m json.tool
```

**Example response** (200 OK):

```json
{
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "bmV3UmVmcmVzaFRva2Vu...",
    "token_type": "bearer",
    "expires_in": 900
  },
  "message": "Token refreshed.",
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

---

### GET /api/v1/auth/me

Retrieve the authenticated user's profile.

```bash
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <ACCESS_TOKEN>" | python -m json.tool
```

**Example response** (200 OK):

```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "admin@example.com",
    "display_name": "Dev Admin",
    "account_status": "ACTIVE",
    "is_email_verified": true,
    "created_at": "2026-07-01T10:00:00Z"
  },
  "message": "User profile retrieved.",
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

---

### POST /api/v1/auth/logout

Revoke the current refresh token and invalidate the session.

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<REFRESH_TOKEN>"}' | python -m json.tool
```

**Example response** (200 OK):

```json
{
  "data": null,
  "message": "Logged out successfully.",
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

---

### POST /api/v1/auth/forgot-password

Request a password reset email. Always returns 200 (anti-enumeration).

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com"}' | python -m json.tool
```

**Example response** (200 OK — always):

```json
{
  "data": null,
  "message": "If an account with that email exists, a password reset link has been sent.",
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

> **Note**: In development, the email is logged (not sent) and the reset token is in `STDOUT` of the `api` container. Run `docker compose logs api | grep reset_token` to find it.

---

### POST /api/v1/auth/reset-password

Set a new password using the token from the reset email.

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "token": "<RESET_TOKEN_FROM_EMAIL>",
    "new_password": "MyNewSecure@Pass1",
    "confirm_password": "MyNewSecure@Pass1"
  }' | python -m json.tool
```

**Example response** (200 OK):

```json
{
  "data": null,
  "message": "Password has been reset successfully.",
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

**Error responses**:
- `400` — Invalid or expired token (`INVALID_TOKEN`)
- `422` — Password doesn't meet requirements or confirmation mismatch

---

### POST /api/v1/auth/change-password

Change password while authenticated (requires knowing the current password).

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/change-password \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "DevAdmin@1234!",
    "new_password": "MyUpdated@Pass99",
    "confirm_password": "MyUpdated@Pass99"
  }' | python -m json.tool
```

**Example response** (200 OK):

```json
{
  "data": null,
  "message": "Password changed successfully.",
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

> After a successful password change, all other sessions' refresh tokens are revoked.

---

### POST /api/v1/auth/verify-email

Verify an email address using the token from the verification email.

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{"token": "<EMAIL_VERIFICATION_TOKEN>"}' | python -m json.tool
```

**Example response** (200 OK):

```json
{
  "data": null,
  "message": "Email address verified successfully.",
  "meta": { "request_id": "...", "timestamp": "..." }
}
```

---

### Health Check

Verify the API is running (no authentication required):

```bash
curl -s http://localhost:8000/api/v1/health | python -m json.tool
```

---

## 8. Common Troubleshooting

### "Invalid signature" / 401 on all requests

The `JWT_SECRET_KEY` in your `.env` doesn't match the key used to sign existing tokens. This happens if you regenerate the secret after users have logged in.

**Fix**: Regenerate the secret, restart the `api` service, and have all users log in again:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
# Update JWT_SECRET_KEY in .env
docker compose restart api
```

---

### "Migration failed" on startup

The database schema is out of sync.

**Fix**:

```bash
docker compose exec api alembic history          # See migration chain
docker compose exec api alembic downgrade base   # Roll back all
docker compose exec api alembic upgrade head     # Re-apply all
```

If you suspect data corruption:

```bash
docker compose down -v   # Wipe all data (destructive!)
docker compose up --build
```

---

### "Connection refused" on port 5432

The database isn't ready yet.

**Fix**: Wait for the health check to pass, then retry:

```bash
docker compose ps       # Check service status
docker compose logs db  # Read PostgreSQL logs
```

---

### "Password does not meet requirements"

The password policy enforces:
- Minimum 12 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character (`!@#$%^&*...`)
- Not in the common passwords list
- Not the same as any of the last 5 passwords

---

### "Account locked" (423)

The account has been locked after 5 consecutive failed login attempts within 15 minutes.
Auto-unlock occurs after 30 minutes, or an administrator can unlock manually.

---

### Frontend shows "Session expired"

The access token (15-minute lifetime) has expired and the refresh token rotation failed or was revoked.

**Fix**: Log out and log back in. The `AuthContext` handles token refresh automatically — if you see this message, all tokens have been invalidated (e.g., password was changed on another device).

---

### Test suite fails with "connection refused" or "database error"

Tests use an in-memory SQLite database (no external connection needed). If you see database errors in tests, verify you're running `pytest` from the `backend/` directory where `pyproject.toml` lives:

```bash
cd /path/to/erp-system/backend
pytest
```

---

## Rate Limits (Reference)

| Endpoint | Limit |
|----------|-------|
| POST /auth/login | 10 / minute per IP |
| POST /auth/refresh | 30 / minute per IP |
| POST /auth/logout | 30 / minute per IP |
| GET /auth/me | 60 / minute per IP |
| POST /auth/forgot-password | 3 / 15 minutes per IP |
| POST /auth/reset-password | 5 / 15 minutes per IP |
| POST /auth/change-password | 5 / 15 minutes per user |
| POST /auth/verify-email | 10 / hour per IP |

---

*Generated during Phase 15 (Documentation) of Epic 002 — Authentication & Identity.*
