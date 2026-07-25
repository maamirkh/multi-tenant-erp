# Inventory Module — Redis Caching Design

**Epic**: 005 – Inventory Management
**Phase**: 11 – Performance & Optimisation
**Date**: 2026-07-25
**Status**: DESIGN COMPLETE — implementation deferred to Cache Epic

---

## 1. Overview

This document defines the Redis caching strategy for the Inventory module's
master data entities. Caching is designed for **read-heavy, infrequently-changing**
data (Categories, Brands, UOM, Attributes) that are accessed on every product
search, lookup, and report query.

**Implementation note**: The cache layer itself (Redis connection, cache service
abstraction) will be built in the Cache Epic. This document captures the design
decisions to guide that implementation.

---

## 2. Cacheable Resources

| Resource | Justification | Estimated Change Frequency |
|----------|--------------|---------------------------|
| Category tree | Loaded on every product create/edit form | Hourly or less |
| Brands list | Loaded on product list and search filters | Daily or less |
| UOM list | Loaded on product create/edit and stock operations | Daily or less |
| Attribute definitions | Loaded on product create/edit | Rarely (on schema change) |
| Attribute sets | Loaded on product create/edit | Rarely |
| Feature flags | Loaded on every inventory request | Rarely |

**Not cached** (too volatile or tenant-specific in ways that make caching complex):
- Stock positions (real-time, changes on every movement)
- Stock movements (append-only, but queried with complex filters)
- Adjustments / Transfers / Alerts (active workflows, frequently changing status)

---

## 3. Cache Key Design

All cache keys are **company-scoped** to maintain multi-tenant isolation.

### Pattern

```
inv:{company_id}:{resource}:{variant}
```

### Key Registry

| Cache Key | Resource | Variant |
|-----------|----------|---------|
| `inv:{company_id}:categories:tree` | Full category tree (flat ordered list) | — |
| `inv:{company_id}:categories:{id}:ancestors` | Ancestor chain for a category | `{id}` = category UUID |
| `inv:{company_id}:brands:active` | All active brands | — |
| `inv:{company_id}:uom:active` | All active UOMs | — |
| `inv:{company_id}:uom:{type}` | UOMs filtered by type | `{type}` = UNIT/WEIGHT/VOLUME/etc. |
| `inv:{company_id}:attr:definitions` | All attribute definitions | — |
| `inv:{company_id}:attr:sets` | All attribute sets | — |
| `inv:{company_id}:feature_flags` | All feature flags for company | — |

### Key Format Notes

- All UUIDs are stored as lowercase strings without dashes: `{company_id}` = `550e8400e29b41d4a716446655440000`
- Keys use `:` as separator (Redis convention)
- No wildcards in key names — invalidation uses SCAN with pattern `inv:{company_id}:*`

---

## 4. TTL Strategy

| Resource | TTL | Rationale |
|----------|-----|-----------|
| Category tree | 1 hour (3600s) | Rarely changes; safe to serve slightly stale |
| Category ancestors | 30 minutes (1800s) | Parent chain changes only on category moves |
| Brands list | 6 hours (21600s) | Very rarely changes in production |
| UOM list | 6 hours (21600s) | Schema changes are infrequent |
| Attribute definitions | 15 minutes (900s) | Admin may add new attributes during onboarding |
| Attribute sets | 15 minutes (900s) | Same as definitions |
| Feature flags | 5 minutes (300s) | Operators may toggle flags; 5 min acceptable lag |

**TTL justification**: The ERP context tolerates bounded staleness. Operations like
stock movements, adjustments, and transfers resolve entity names at display time,
not at write time, so a 1-hour stale category name has no inventory accuracy impact.

---

## 5. Invalidation Strategy

### 5.1 Write-Through Invalidation (recommended)

On every mutating operation (create, update, deactivate, delete), the service layer
explicitly deletes the affected cache key **after** the database commit.

```python
# Pseudocode — to be implemented in Cache Epic
class CategoryService:
    def update_category(self, company_id, category_id, data):
        # 1. Write to DB
        category = self.repo.update(...)
        self.db.commit()
        # 2. Invalidate cache
        self.cache.delete(f"inv:{company_id}:categories:tree")
        self.cache.delete(f"inv:{company_id}:categories:{category_id}:ancestors")
        return category
```

### 5.2 Scope of Invalidation

| Mutation | Keys to Invalidate |
|----------|--------------------|
| Category created/updated/deleted | `inv:{company_id}:categories:tree`, `inv:{company_id}:categories:*:ancestors` |
| Brand created/updated | `inv:{company_id}:brands:active` |
| UOM created/updated | `inv:{company_id}:uom:active`, `inv:{company_id}:uom:{type}` |
| Attribute def created/updated | `inv:{company_id}:attr:definitions` |
| Attribute set created/updated | `inv:{company_id}:attr:sets` |
| Feature flag updated | `inv:{company_id}:feature_flags` |

### 5.3 Company-Wide Flush

When a company is deactivated or migrated:
```
SCAN 0 MATCH inv:{company_id}:* COUNT 100
DEL <matched_keys>
```

---

## 6. Cache Service Interface

```python
# To be implemented in Cache Epic
class InventoryCacheService(Protocol):
    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl_seconds: int) -> None: ...
    def delete(self, key: str) -> None: ...
    def delete_pattern(self, pattern: str) -> int: ...  # returns count deleted
```

---

## 7. Serialisation Format

Cache values are stored as **JSON strings** using the same schema as the API response
(`to_dict()` or Pydantic `.model_dump()`). This allows the cache layer to be
bypassed transparently in tests without schema mismatch.

---

## 8. Cache Miss Strategy

On a cache miss, the service falls through to the database:

```python
async def get_category_tree(self, company_id: UUID) -> list[Category]:
    key = f"inv:{company_id}:categories:tree"
    cached = self.cache.get(key)
    if cached is not None:
        return [Category(**row) for row in cached]
    # Cache miss — load from DB
    categories = self.repo.get_tree(company_id)
    self.cache.set(key, [c.to_dict() for c in categories], ttl_seconds=3600)
    return categories
```

---

## 9. Non-Goals

- **No cache for write operations**: All writes go directly to PostgreSQL.
- **No distributed cache locking**: The TTL-based invalidation is sufficient; cache
  stampede risk is minimal for low-cardinality master data.
- **No L1 in-process cache**: Not implemented to avoid stale data in multi-worker
  deployments (uvicorn multi-process).

---

## 10. Expected Performance Impact

| Resource | Before Cache | After Cache (expected) |
|----------|-------------|----------------------|
| Category tree (10 categories) | ~5ms (1 DB query) | ~0.5ms (Redis GET) |
| Brands list (50 brands) | ~3ms | ~0.3ms |
| Feature flags (18 flags) | ~2ms | ~0.2ms |
| Product search with category resolve | ~8ms | ~6ms (category from cache) |

---

## 11. Implementation Checklist (for Cache Epic)

- [ ] Redis connection via `aioredis` or `redis-py` (match async/sync choice)
- [ ] `InventoryCacheService` concrete implementation
- [ ] Inject `CacheService` via FastAPI Depends (optional — falls back to no-op stub)
- [ ] Add `CacheNullService` stub for test isolation
- [ ] Wire invalidation in CategoryService, BrandService, UOMService, AttributeDefinitionService, FeatureFlagService
- [ ] Add `REDIS_URL` to `.env.example` and Settings
- [ ] Add Redis health check to `/api/v1/inventory/health`
- [ ] Document cache key registry in OpenAPI as `x-cache-ttl` extension
