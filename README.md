# DevSphere ERP

**Enterprise Multi-Tenant SaaS ERP Platform**

DevSphere ERP is a modular, multi-tenant Enterprise Resource Planning platform designed to serve any Small-to-Medium Enterprise (SME) business domain. Built on a clean, extensible foundation, it supports rapid development of ERP modules across industries.

---

## Prerequisites

| Tool | Minimum Version | Purpose |
|------|-----------------|---------|
| Docker Desktop | 4.x | Container runtime |
| Docker Compose | v2.x | Multi-service orchestration |
| Git | 2.x | Source control |

> **All development runs inside Docker.** No local Python or Node.js installation required.

---

## Quick Start

### 1. Clone the repository

```bash
git clone <repository-url> erp-system
cd erp-system
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and set the required values (see comments in `.env.example`).

### 3. Start the development environment

```bash
docker compose up
```

All three services will start:

| Service | URL | Purpose |
|---------|-----|---------|
| Backend API | http://localhost:8000 | FastAPI application |
| Frontend | http://localhost:3000 | Next.js application |
| PostgreSQL | localhost:5432 | Database (internal) |

### 4. Verify the platform is running

```bash
# Check backend health
curl http://localhost:8000/api/v1/health

# Expected response:
# {"data": {"status": "healthy", "database": "connected", ...}, ...}
```

Open http://localhost:3000 in a browser to verify the frontend loads.

---

## Development Workflow

### Hot Reload

Both services support automatic reload on file changes:

- **Backend**: Edit any `.py` file → uvicorn reloads within 3 seconds
- **Frontend**: Edit any `.tsx`/`.ts` file → Next.js fast refreshes

### Running Tests

```bash
# Backend unit tests
docker compose exec api pytest tests/unit/ -v

# Backend integration tests
docker compose exec api pytest tests/integration/ -v

# Frontend tests
docker compose exec web npm test
```

### Running Code Quality Checks

```bash
# Backend
docker compose exec api black --check .
docker compose exec api ruff check .
docker compose exec api mypy .

# Frontend
docker compose exec web npx tsc --noEmit
docker compose exec web npx eslint .
docker compose exec web npx prettier --check .
```

### Database Migrations

```bash
# Apply migrations
docker compose exec api alembic upgrade head

# Create a new migration
docker compose exec api alembic revision --autogenerate -m "describe_change"

# Rollback one step
docker compose exec api alembic downgrade -1
```

---

## Project Structure

```
erp-system/
├── backend/                    # FastAPI application
│   ├── core/                   # Platform layer (shared infrastructure)
│   │   ├── config/             # Settings and configuration
│   │   ├── database/           # Engine, session, base models
│   │   ├── exceptions/         # Exception hierarchy and global handler
│   │   ├── logging/            # Structured JSON logging
│   │   ├── middleware/         # Request ID, CORS, auth hook
│   │   ├── repositories/       # BaseRepository (tenant-scoped)
│   │   ├── schemas/            # Common Pydantic response schemas
│   │   ├── services/           # BaseService
│   │   └── utils/              # UUID, datetime, pagination utilities
│   ├── modules/                # Business ERP modules (one directory per module)
│   ├── api/v1/                 # API version 1 router
│   ├── migrations/             # Alembic migration files
│   └── tests/                  # Backend tests (unit + integration)
├── frontend/                   # Next.js application (App Router)
│   └── src/
│       ├── app/                # Pages and layouts
│       ├── components/         # UI and layout components
│       ├── lib/api/            # Typed API client
│       └── types/              # TypeScript type definitions
├── specs/                      # Spec-Driven Development artifacts
│   └── 001-foundation-platform/ # Epic 1 specification, plan, tasks
├── history/                    # ADRs and Prompt History Records
│   ├── adr/                    # Architecture Decision Records
│   └── prompts/                # Prompt History Records
├── docker-compose.yml          # Development environment orchestration
├── .env.example                # Environment variable documentation
└── README.md                   # This file
```

---

## Environment Variables

See `.env.example` for the full list of required and optional environment variables with descriptions.

**Minimum required variables to get started:**

| Variable | Example | Description |
|----------|---------|-------------|
| `POSTGRES_DB` | `devsphere_dev` | PostgreSQL database name |
| `POSTGRES_USER` | `devsphere` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `changeme` | PostgreSQL password |
| `DATABASE_URL` | `postgresql://...` | Full database connection URL |
| `SECRET_KEY` | `<32+ char string>` | Application secret key |
| `ENVIRONMENT` | `development` | Runtime environment |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL for frontend |

---

## Architecture

DevSphere ERP uses a **Modular Monolith** architecture:

- **Backend (FastAPI)**: Layered architecture with API → Service → Repository → Database
- **Frontend (Next.js)**: App Router with TypeScript strict mode and shadcn/ui components
- **Database (PostgreSQL)**: Multi-tenant with `company_id` isolation on all business entities
- **Migrations (Alembic)**: All schema changes via version-controlled migrations

See `specs/001-foundation-platform/` for the full specification, architecture plan, and implementation details.

---

## Adding a New ERP Module

1. Create `backend/modules/<module-name>/` with the standard vertical slice structure
2. Extend `TenantBaseModel` for your entities
3. Extend `BaseRepository` for data access
4. Extend `BaseService` for business logic
5. Register your router in `backend/api/v1/router.py`
6. Create an Alembic migration for new tables

---

## Stopping the Environment

```bash
# Stop all services (data preserved)
docker compose down

# Stop and remove all data (full reset)
docker compose down -v
```

---

## Documentation

- **Specification**: `specs/001-foundation-platform/spec.md`
- **Architecture Plan**: `specs/001-foundation-platform/plan.md`
- **Developer Quickstart**: `specs/001-foundation-platform/quickstart.md`
- **Architecture Decisions**: `history/adr/`
- **Project Constitution**: `.specify/memory/constitution.md`
