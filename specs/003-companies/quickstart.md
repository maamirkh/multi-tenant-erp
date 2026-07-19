# Companies Module — Developer Quickstart

## Prerequisites

| Tool | Minimum Version |
|------|----------------|
| Docker Desktop / Docker Engine | 24.x |
| Docker Compose | v2.x (plugin) |
| Python | 3.12+ |
| Node.js | 20 LTS |
| npm | 10+ |

---

## 1. Environment Setup

Copy the example environment file and fill in the required values:

```sh
cp .env.example .env
```

The following variables are required for the Companies module:

```sh
# Database
DATABASE_URL=postgresql://devsphere:changeme_dev_password@db:5432/devsphere_dev

# JWT
JWT_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_urlsafe(64))">

# S3 / MinIO (local dev — defaults work out of the box with Docker Compose)
S3_ENDPOINT=http://minio:9000
S3_BUCKET=devsphere-companies
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_REGION=us-east-1
```

---

## 2. Start All Services

```sh
docker compose up -d
```

This starts:
- `db` — PostgreSQL 16 on port 5432
- `api` — FastAPI backend on port 8000
- `minio` — MinIO S3-compatible storage (API: 9000, Console: 9001)
- `frontend` — Next.js on port 3000

Wait for all services to be healthy:

```sh
docker compose ps
```

---

## 3. Run Database Migrations

```sh
docker compose exec api alembic upgrade head
```

The Companies module adds the following tables:
- `companies`
- `company_addresses`
- `company_audit_logs`
- `event_outbox`

---

## 4. Install Frontend Dependencies

```sh
cd frontend && npm install
```

---

## 5. Running Tests

### Backend — All Tests

```sh
docker compose exec api pytest tests/ -v --tb=short
```

### Backend — Companies Module Only

```sh
docker compose exec api pytest tests/ -k companies -v
```

### Backend — Integration Tests

```sh
docker compose exec api pytest tests/integration/ -v
```

### Backend — Security Tests

```sh
docker compose exec api pytest tests/security/ -v
```

### Backend — With Coverage

```sh
docker compose exec api pytest tests/ --cov=modules/companies/ --cov-report=term-missing
```

### Frontend — All Tests

```sh
cd frontend && npx jest
```

### Frontend — With Coverage

```sh
cd frontend && npx jest --coverage
```

---

## 6. Access MinIO Console

Open [http://localhost:9001](http://localhost:9001) in a browser.

Default credentials (development only):
- **Username**: `minioadmin`
- **Password**: `minioadmin`

The bucket `devsphere-companies` is created automatically on first logo upload.

To browse uploaded logos: MinIO Console → Object Browser → `devsphere-companies`

---

## 7. Common Development Workflows

### Create a Company

```sh
# 1. Register and log in to get an access token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "dev@example.com", "password": "yourpassword"}'

# 2. Create a company (use token from step 1)
curl -X POST http://localhost:8000/api/v1/companies \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"legal_name": "Acme Corp", "email": "contact@acme.com"}'
```

### Activate a Company

Activation requires `country` and `default_currency` to be set first (BR-008):

```sh
# Patch required fields
curl -X PATCH http://localhost:8000/api/v1/companies/<id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"country": "US", "default_currency": "USD"}'

# Activate
curl -X POST http://localhost:8000/api/v1/companies/<id>/activate \
  -H "Authorization: Bearer <token>"
```

### Upload a Company Logo

```sh
curl -X POST http://localhost:8000/api/v1/companies/<id>/logo \
  -H "Authorization: Bearer <token>" \
  -F "file=@/path/to/logo.png"
```

Allowed types: PNG, JPEG, SVG, WebP. Maximum size: 2 MB (configurable via `COMPANY_LOGO_MAX_BYTES`).

### View Audit Log

```sh
curl http://localhost:8000/api/v1/companies/<id>/audit-log \
  -H "Authorization: Bearer <token>"
```

### Soft Delete and Restore

```sh
# Delete (must be active or inactive)
curl -X DELETE http://localhost:8000/api/v1/companies/<id> \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Closing account", "confirm_delete": true}'

# Restore (within retention window — default 30 days)
curl -X POST http://localhost:8000/api/v1/companies/<id>/restore \
  -H "Authorization: Bearer <token>"
```

---

## 8. Seeding Test Data (Performance Baseline)

The seed script inserts 10,000 company records with varied statuses, countries, and currencies for performance benchmarking. It is idempotent — running it again when 10,000 rows already exist is a no-op.

```sh
# Requires at least one user to exist in the users table
docker compose exec api python scripts/seed_companies.py --count 10000
```

Typical runtime: ~5 seconds (500 records per chunk via psycopg2 `executemany`).

To reset: truncate the companies table and re-run:

```sh
docker compose exec db psql -U devsphere -d devsphere_dev -c "TRUNCATE companies CASCADE;"
docker compose exec api python scripts/seed_companies.py
```

A legacy manual seed approach (small datasets):

```sh
# Seed 5 test companies via the API (run inside the container)
docker compose exec api python - <<'EOF'
import httpx, json

BASE = "http://localhost:8000/api/v1"
# Assumes a test user already exists
token = httpx.post(f"{BASE}/auth/login",
    json={"email": "dev@example.com", "password": "yourpassword"}).json()["data"]["access_token"]
headers = {"Authorization": f"Bearer {token}"}

for i in range(1, 6):
    r = httpx.post(f"{BASE}/companies", headers=headers,
        json={"legal_name": f"Seed Company {i}", "email": f"seed{i}@example.com"})
    print(r.status_code, r.json()["data"]["id"])
EOF
```

---

## 9. Troubleshooting

### MinIO Connection Error

**Symptom**: Logo upload returns 500 with "Could not connect to the endpoint URL".

**Cause**: MinIO container not running, or `S3_ENDPOINT` points to wrong host.

**Fix**:
```sh
docker compose up -d minio
docker compose ps minio   # verify health
# Inside the container, the endpoint must be http://minio:9000 (service name, not localhost)
```

### Migration Failure

**Symptom**: `alembic upgrade head` fails with "relation already exists" or "column not found".

**Fix**:
```sh
# Check current revision
docker compose exec api alembic current

# If stuck in a bad state, reset to base (WARNING: destroys all data)
docker compose exec api alembic downgrade base
docker compose exec api alembic upgrade head
```

For production: never run `downgrade base`. Identify and fix the specific migration instead.

### 422 Unprocessable Entity on Company Create

Company creation requires at minimum `legal_name` (2+ characters) and `email` (valid RFC address). Check the `details` field in the response body for field-level errors.

### 409 on Company Activation

Ensure `country` (ISO 3166-1 alpha-2) and `default_currency` (ISO 4217) are set before calling `/activate`. See BR-008 in `spec.md §5.5`.

### 409 INVALID_STATUS_TRANSITION on Delete

The delete endpoint only accepts companies in `active` or `inactive` status. A company in `pending_setup` must be activated (or manually updated) first.

---

## 10. Query Performance Reference

The following queries were verified against PostgreSQL 16 using `EXPLAIN ANALYZE` with 10,000 company rows (seeded via `scripts/seed_companies.py`):

| Query | Index Used | Planning | Execution | Result |
|-------|-----------|----------|-----------|--------|
| `get_by_id` | `pk_companies` (PK btree on `id`) | 2.6ms | 0.09ms | Index Scan ✓ |
| `list_by_owner` | `ix_companies_owner_id` (btree on `owner_id`) | 2.8ms | 3.7ms | Index Scan ✓ |
| `exists_by_name` | `ix_companies_lower_legal_name` (unique btree on `lower(legal_name)`) | 3.6ms | 0.2ms | Index Scan ✓ |
| `list_all_active` | `ix_companies_status` (btree on `status`) | 2.6ms | 3.0ms | Index Scan ✓ |
| `audit_log_by_company` | `ix_company_audit_logs_company_id` (btree on `company_id`) | 1.6ms | 0.06ms | Index Scan ✓ |

No sequential scans on `companies` or `company_audit_logs` for any of the above paths with 10,000 rows.

**Verification commands** (run against the real PostgreSQL container):

```sh
COMPANY_ID=$(docker compose exec -T db psql -U devsphere -d devsphere_dev -t \
  -c "SELECT id FROM companies LIMIT 1;" | tr -d ' \n')
OWNER_ID=$(docker compose exec -T db psql -U devsphere -d devsphere_dev -t \
  -c "SELECT id FROM users LIMIT 1;" | tr -d ' \n')

docker compose exec db psql -U devsphere -d devsphere_dev <<SQL
EXPLAIN ANALYZE SELECT * FROM companies WHERE id = '$COMPANY_ID'::uuid;
EXPLAIN ANALYZE SELECT 1 FROM companies WHERE LOWER(legal_name) = LOWER('Seed Company 000001');
EXPLAIN ANALYZE SELECT * FROM companies WHERE status = 'active' AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 25;
EXPLAIN ANALYZE SELECT * FROM company_audit_logs WHERE company_id = '$COMPANY_ID'::uuid ORDER BY created_at DESC LIMIT 25;
SQL
```

---

## 11. Audit Log DB Permissions

The application database user (`devsphere`) has `INSERT`-only access to `company_audit_logs`. `UPDATE` and `DELETE` are denied at the PostgreSQL role level to prevent tampering.

Verification:
```sql
-- Connect as the application user
UPDATE company_audit_logs SET action = 'TAMPERED' WHERE id = '...';
-- Expected: ERROR: permission denied for table company_audit_logs
```
