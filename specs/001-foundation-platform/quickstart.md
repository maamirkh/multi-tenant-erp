# Developer Quickstart: Foundation Platform

**Branch**: `001-foundation-platform`
**Updated**: 2026-07-11

This guide walks a new developer through setting up and verifying the DevSphere ERP Foundation Platform.

---

## Prerequisites

| Tool | Minimum Version | Purpose |
|------|-----------------|---------|
| Docker Desktop | 4.x | Container runtime |
| Docker Compose | v2.x | Multi-service orchestration |
| Git | 2.x | Source control |

No other tools are required for local development. All dependencies run inside Docker.

---

## Initial Setup

### 1. Clone the Repository

```bash
git clone <repository-url> erp-system
cd erp-system
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` and fill in the required values. At minimum, set:

```env
# Required — change the password to something secure
POSTGRES_PASSWORD=devpassword

# Required — generate a secure random string
SECRET_KEY=your-secret-key-here-minimum-32-chars

# These defaults work for local development
ENVIRONMENT=development
DEBUG=true
```

### 3. Start the Development Environment

```bash
docker compose up
```

This command builds all images (first run takes 2–3 minutes) and starts three services:

| Service | Port | URL |
|---------|------|-----|
| Backend API | 8000 | http://localhost:8000 |
| Frontend | 3000 | http://localhost:3000 |
| PostgreSQL | 5432 | (internal; exposed for tools) |

---

## Verification

Once all services are running, verify the platform:

### Check Backend Health

```bash
curl http://localhost:8000/api/v1/health
```

Expected response:

```json
{
  "data": {
    "status": "healthy",
    "database": "connected",
    "version": "1.0.0",
    "timestamp": "2026-07-11T10:00:00.000Z"
  },
  "message": "Platform is operational.",
  "meta": {
    "request_id": "...",
    "timestamp": "..."
  }
}
```

### Check Frontend

Open http://localhost:3000 in a browser. The application shell should load with no console errors.

### View API Documentation

Open http://localhost:8000/docs in a browser. Swagger UI displays all available endpoints.

---

## Development Workflow

### Hot Reload

Both services support automatic reload on file changes:

- **Backend**: Edit any `.py` file in `backend/` → the uvicorn server reloads within 3 seconds.
- **Frontend**: Edit any `.tsx` or `.ts` file in `frontend/src/` → Next.js fast refresh updates the browser within seconds.

### Running Database Migrations

Migrations run automatically on startup. To run them manually:

```bash
docker compose exec api alembic upgrade head
```

To create a new migration after model changes:

```bash
docker compose exec api alembic revision --autogenerate -m "describe_the_change"
```

### Running Backend Tests

```bash
docker compose exec api pytest tests/ -v
```

### Running Frontend Tests

```bash
docker compose exec web npm test
```

### Running Code Quality Checks

```bash
# Backend
docker compose exec api black --check .
docker compose exec api ruff check .
docker compose exec api mypy .

# Frontend
docker compose exec web eslint .
docker compose exec web prettier --check .
docker compose exec web npx tsc --noEmit
```

---

## Project Structure Reference

```
erp-system/
├── backend/
│   ├── core/               — Platform infrastructure (do not modify without a plan)
│   │   ├── config/         — Settings and configuration
│   │   ├── database/       — Engine, session, base models
│   │   ├── exceptions/     — Exception hierarchy and handler
│   │   ├── logging/        — Structured logging setup
│   │   ├── middleware/     — Request ID, CORS, auth hook
│   │   ├── repositories/   — BaseRepository
│   │   ├── schemas/        — Common Pydantic response schemas
│   │   ├── services/       — BaseService
│   │   └── utils/          — Shared utilities
│   ├── modules/            — Business modules go here (one directory per module)
│   ├── api/v1/             — API version 1 router
│   ├── migrations/         — Alembic migration files
│   └── tests/              — Backend tests
├── frontend/
│   ├── src/
│   │   ├── app/            — Next.js App Router pages
│   │   ├── components/     — Shared UI and layout components
│   │   ├── lib/api/        — Typed API client
│   │   └── types/          — TypeScript types
│   └── src/__tests__/      — Frontend tests
├── specs/                  — Spec-Driven Development artifacts
├── history/                — ADRs and Prompt History Records
└── docker-compose.yml
```

---

## Adding a New Module

To add a new ERP module (after this Epic is complete):

1. Create `backend/modules/<module-name>/` with the standard vertical slice structure.
2. Extend `TenantBaseModel` for your entities.
3. Extend `BaseRepository` for your data access class.
4. Extend `BaseService` for your business logic class.
5. Register your module's router in `backend/api/v1/router.py`.
6. Create an Alembic migration for your new tables.

Refer to the spec and plan for the full module structure.

---

## Stopping the Environment

```bash
# Stop all services (data is preserved)
docker compose down

# Stop all services and remove volumes (data is deleted)
docker compose down -v
```

---

## Troubleshooting

| Symptom | Likely Cause | Resolution |
|---------|-------------|------------|
| `docker compose up` fails with "port already in use" | Port 8000 or 3000 is occupied | Stop the conflicting process or change port mapping in `docker-compose.yml` |
| Health check returns `database: disconnected` | PostgreSQL not ready yet | Wait for `db` service to complete initialization (check `docker compose logs db`) |
| Backend hot reload not triggering | WSL2 file watch issue | Ensure source is on the WSL2 filesystem, not `/mnt/c/` or `/mnt/d/` |
| `mypy` type errors on startup | Missing type stub | Install the relevant `types-*` package via Poetry in `pyproject.toml` |
| Frontend shows blank page | `.env` missing `NEXT_PUBLIC_API_URL` | Copy `.env.example` and verify all variables are set |
