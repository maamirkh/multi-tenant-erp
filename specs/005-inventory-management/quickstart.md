# Inventory Module — Developer Quickstart

**Epic**: 005-inventory-management
**Branch**: `005-inventory-management`

---

## Overview

The inventory module provides full multi-tenant inventory management including:
- Product Master (CRUD, variants, barcodes, categories, enrichment)
- Warehouse Management (multi-warehouse, zones)
- Stock Ledger (opening stock, movements, positions, snapshots)
- Stock Operations (adjustments, transfers, reservations)
- Inventory Intelligence (low stock alerts, reorder rules)
- Reporting (14 reports, 10 KPIs)
- Domain Events (32 event types via InProcessEventBus)

---

## Prerequisites

```bash
# Python 3.12+, Poetry
cd backend/
poetry install

# Copy environment variables
cp .env.example .env  # Edit DATABASE_URL etc.
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL connection string |
| `SECRET_KEY` | — | JWT signing secret (min 32 chars) |
| `JWT_SECRET_KEY` | — | JWT secret key (min 32 chars) |
| `DB_LOCK_TIMEOUT_SECONDS` | `5` | PostgreSQL lock timeout for stock ops |
| `INVENTORY_FEATURE_FLAGS` | `{}` | JSON dict of feature flag overrides |

---

## Running the Backend

```bash
cd backend/
poetry run uvicorn main:app --reload --port 8000

# API docs available at:
# http://localhost:8000/api/v1/docs
```

---

## Database Migrations

```bash
cd backend/
poetry run alembic upgrade head

# Inventory migrations (in order):
# 005 — inventory_phase0 (base tables)
# 006 — inventory_master_data
# 007 — inventory_products
# 008 — inventory_enrichment
# 009 — inventory_warehouses
# 010 — inventory_stock
# 011 — inventory_adjustments
# 012 — inventory_transfers
# 013 — inventory_alerts
# 014 — inventory_performance_indexes
```

---

## Running Tests

```bash
cd backend/

# All tests
poetry run pytest

# Inventory-specific tests only
poetry run pytest tests/integration/api/v1/inventory/ tests/unit/modules/inventory/ -v

# Phase 12 closure tests
poetry run pytest tests/e2e/inventory/ tests/integration/inventory/ tests/api/inventory/ tests/security/inventory/ -v

# Performance benchmarks
poetry run pytest tests/performance/inventory/ -v

# With coverage
poetry run pytest --cov=modules/inventory --cov-report=html
```

---

## Seeding Test Data

The following script seeds minimal data for manual API testing:

```python
# backend/scripts/seed_inventory_test_data.py  (create if needed)

import uuid
from sqlalchemy.orm import Session
from modules.inventory.models.uom import UOM
from modules.inventory.models.warehouse import Warehouse

COMPANY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

def seed(db: Session) -> None:
    # 1. Create UOM
    uom = UOM(
        id=uuid.uuid4(), company_id=COMPANY_ID,
        code="PC", name="Pieces", uom_type="UNIT", status="active",
    )
    db.add(uom)

    # 2. Create Warehouse
    wh = Warehouse(
        id=uuid.uuid4(), company_id=COMPANY_ID,
        code="MAIN", name="Main Warehouse",
        warehouse_type="MAIN", status="ACTIVE",
    )
    db.add(wh)
    db.commit()
    print(f"UOM: {uom.id}, Warehouse: {wh.id}")
```

---

## Common Use Cases

### Create a Product

```bash
curl -X POST http://localhost:8000/api/v1/companies/{company_id}/inventory/products \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "product_code": "PROD-001",
    "name": "Widget A",
    "product_type": "STANDARD",
    "base_uom_id": "{uom_id}"
  }'
```

### Activate a Product

```bash
curl -X PATCH http://localhost:8000/api/v1/companies/{company_id}/inventory/products/{product_id}/status \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"action": "activate"}'
```

### Record Opening Stock

```bash
curl -X POST http://localhost:8000/api/v1/companies/{company_id}/inventory/stock/opening \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": "{product_id}",
    "warehouse_id": "{warehouse_id}",
    "quantity": "100",
    "unit_cost": "10.00",
    "currency_code": "USD"
  }'
```

### Check Stock Position

```bash
curl http://localhost:8000/api/v1/companies/{company_id}/inventory/stock/positions/warehouse/{warehouse_id} \
  -H "Authorization: Bearer {token}"
```

### Search Products

```bash
curl "http://localhost:8000/api/v1/companies/{company_id}/inventory/products?query=widget&page_size=20" \
  -H "Authorization: Bearer {token}"
```

### Get KPI Dashboard

```bash
curl http://localhost:8000/api/v1/companies/{company_id}/inventory/kpis \
  -H "Authorization: Bearer {token}"
```

---

## Feature Flags

Feature flags control optional inventory behaviours:

| Flag Key | Default | Description |
|----------|---------|-------------|
| `inventory.enabled` | `true` | Master switch for the inventory module |
| `inventory.adjustment_approval_required` | `false` | Require approval for inventory adjustments |
| `inventory.low_stock_alerts_enabled` | `true` | Enable automatic low stock alert generation |
| `inventory.auto_reorder_enabled` | `false` | Enable automatic reorder suggestions |

Toggle via API:
```bash
curl -X PUT http://localhost:8000/api/v1/companies/{company_id}/inventory/feature-flags/inventory.adjustment_approval_required \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

---

## API Endpoints Reference

All endpoints are prefixed: `/api/v1/companies/{company_id}/inventory/`

| Category | Endpoints |
|----------|-----------|
| Feature Flags | GET/PUT `/feature-flags` |
| Categories | CRUD `/categories` |
| Brands | CRUD `/brands` |
| UOM | CRUD `/uom`, conversions `/uom-conversions` |
| Attributes | CRUD `/attributes`, `/attribute-sets` |
| Tags | CRUD `/tags` |
| Reason Codes | CRUD `/reason-codes` |
| Custom Fields | CRUD `/custom-fields` |
| Products | CRUD `/products`, status `/products/{id}/status`, import `/products/import` |
| Warehouses | CRUD `/warehouses`, zones `/warehouses/{id}/zones` |
| Stock | Opening `/stock/opening`, positions `/stock/positions`, movements `/stock/movements` |
| Reservations | Reserve `/stock/reserve`, release `/stock/release` |
| Snapshots | CRUD `/stock/snapshots` |
| Adjustments | CRUD `/adjustments`, workflow `/adjustments/{id}/submit`, `/approve`, `/reject` |
| Transfers | CRUD `/stock-transfers`, dispatch/receive/cancel |
| Alerts | List `/alerts`, check `/alerts/check`, reorder rules `/reorder-rules` |
| Reports | 14 reports under `/reports/`, KPIs under `/kpis` |

---

## Architecture Overview

```
modules/inventory/
├── models/          # SQLAlchemy ORM models (TenantBaseModel subclasses)
├── schemas/         # Pydantic request/response schemas
├── repositories/    # Data access layer (Repository pattern)
├── services/        # Business logic (Service layer)
├── domain_events.py # 32 domain event dataclasses
├── events.py        # InProcessEventBus, get_event_bus(), set_event_bus()
├── router.py        # FastAPI route handlers
├── dependencies.py  # Dependency injection factories
└── constants.py     # Feature flags, module constants
```

### Key Design Decisions

1. **Multi-tenancy**: Every query includes `WHERE company_id = ?` via repository pattern
2. **Soft delete**: `is_deleted=True` + `deleted_at` on all entities (no hard deletes)
3. **Immutable ledger**: `stock_movements` is append-only — no UPDATE/DELETE endpoints
4. **Domain events**: All writes publish domain events via `InProcessEventBus`
5. **Performance**: 8 composite/partial indexes in migration 014

---

## Troubleshooting

### Migration fails with "relation already exists"
```bash
poetry run alembic stamp head  # Mark current state without running
poetry run alembic upgrade head
```

### SQLite vs PostgreSQL differences in tests
Tests use SQLite in-memory. Some PostgreSQL-specific features (GIN indexes, JSONB) are stubbed. Performance benchmarks are calibrated for SQLite scale.

### EventBus not capturing events in tests
ProductService uses its own internal bus. Use `set_event_bus()` for warehouse/stock/adjustment/transfer/alert events. Product events require injecting the bus into ProductService directly.

### Feature flag not taking effect
Feature flags are per-company. Ensure you're querying the correct `company_id`.
