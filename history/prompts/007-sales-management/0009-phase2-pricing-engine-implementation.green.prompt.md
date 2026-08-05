---
id: "0009"
title: "Phase 2 Pricing Engine Implementation"
stage: green
date: 2026-08-02
surface: agent
model: claude-sonnet-4-6
feature: 007-sales-management
branch: 007-sales-management
user: shehla83
command: /sp.implement
labels: ["pricing-engine","7-level-resolution","discount-service","margin-guard","phase2","epic7"]
links:
  spec: specs/007-sales-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/sales/models/pricing.py
  - backend/modules/sales/repositories/pricing.py
  - backend/modules/sales/services/pricing_service.py
  - backend/modules/sales/schemas/pricing.py
  - backend/modules/sales/dependencies.py
  - backend/modules/sales/models/__init__.py
  - backend/modules/sales/repositories/__init__.py
  - backend/modules/sales/router.py
  - backend/migrations/versions/027_sales_pricing.py
  - backend/tests/unit/modules/sales/test_pricing_service.py
  - backend/tests/unit/modules/sales/test_discount_service.py
  - backend/tests/unit/modules/sales/test_margin_guard.py
  - backend/tests/integration/repositories/sales/test_pricing_repositories.py
  - backend/tests/integration/api/v1/sales/test_pricing_api.py
  - frontend/src/app/(protected)/(sales)/pricing/price-lists/page.tsx
  - frontend/src/app/(protected)/(sales)/pricing/customer-prices/page.tsx
  - frontend/src/app/(protected)/(sales)/pricing/discounts/page.tsx
  - frontend/src/lib/api/sales.ts
  - specs/007-sales-management/tasks.md
tests:
  - backend/tests/unit/modules/sales/test_pricing_service.py (14 tests — all 7 levels + qty breaks + ordering)
  - backend/tests/unit/modules/sales/test_discount_service.py (27 tests — scope, stackability, priority)
  - backend/tests/unit/modules/sales/test_margin_guard.py (12 tests — OK/WARN/BLOCK, edge cases)
  - backend/tests/integration/repositories/sales/test_pricing_repositories.py (23 tests — repo CRUD + qty breaks + isolation)
  - backend/tests/integration/api/v1/sales/test_pricing_api.py (25 tests — full CRUD + resolve + margin)
---

## Prompt

/sp.implement

Epic: Epic 7 – Sales Management
Phase 2: "Pricing Engine (P1)"

Implement ONLY this phase. Complete every task (T062–T082) defined in tasks.md for Phase 2.

Requirements covered:
- Backend models (PriceList, PriceEntry, CustomerSpecificPrice, DiscountRule)
- Repositories with quantity break resolution and default flag enforcement
- PricingService with 7-level hierarchy
- DiscountService with stackability logic
- MarginGuardService with warn/block thresholds
- Alembic migration 027_sales_pricing
- Pydantic v2 schemas
- FastAPI API endpoints (price-lists, customer-prices, discount-rules, pricing/resolve, pricing/check-margin)
- Frontend pages: price-lists, customer-prices, discounts
- API client functions in sales.ts
- Unit tests (T077-T079): 53 tests
- Integration tests (T080-T081): 48 tests
- All ruff lint errors resolved
- tasks.md Phase 2 tasks and exit criteria marked [X]

## Response snapshot

Implemented Phase 2 Pricing Engine (P1) for Epic 7 — Sales Management.

**Architecture:**
- 7-level price resolution hierarchy: Manual → Customer-Specific → Customer Group → Customer Category → Active PriceList → Default PriceList → Base Price
- Quantity break resolution: `resolve_for_quantity()` filters `min_qty ≤ ordered_qty`, returns highest qualifying entry
- Single-default invariant: `clear_default()` called before setting `is_default=True`
- Discount stackability: non-stackable rules compete (highest priority wins); stackable rules all combine
- MarginGuard: computes `(unit_price - cost_price) / unit_price × 100`; OK/WARN/BLOCK

**Files created:**
- `backend/modules/sales/models/pricing.py` — 4 ORM models (PriceList, PriceEntry, CustomerSpecificPrice, DiscountRule)
- `backend/modules/sales/repositories/pricing.py` — 4 repositories with qty break and default flag logic
- `backend/modules/sales/services/pricing_service.py` — PricingService, DiscountService, MarginGuardService, PriceListService, CustomerSpecificPriceService, DiscountRuleService
- `backend/modules/sales/schemas/pricing.py` — all Pydantic v2 schemas (fixed id: UUID type for ORM compatibility)
- `backend/migrations/versions/027_sales_pricing.py` — Alembic migration (down_revision=026_sales_customers)
- 5 test files: 101 tests (53 unit + 48 integration)
- 3 frontend pages (price-lists, customer-prices, discounts)
- Sales API client updated with 20+ pricing functions

**Test results:** 256/256 pass (full sales test suite)
**Lint:** All ruff errors resolved

## Outcome

- ✅ Impact: Phase 2 Pricing Engine fully implemented — 7-level price hierarchy, discount engine, and margin guard operational
- 🧪 Tests: 256 passed (53 unit + 48 integration for Phase 2; 155 retained from Phase 0+1); 0 failures
- 📁 Files: 18 files created/modified
- 🔁 Next prompts: /sp.implement Phase 3 — Sales Quotations
- 🧠 Reflection: Schema type bug (id: str vs id: UUID) caught immediately by API integration tests. Ruff noqa placement on wrong line also caught. Both fixed cleanly.

## Evaluation notes (flywheel)

- Failure modes observed: PriceListRead schema used `id: str` — fails when ORM returns UUID object; fixed by using `id: UUID` in all Read schemas
- Graders run and results (PASS/FAIL): pytest 256/256 PASS; ruff PASS
- Prompt variant (if applicable): sp.implement Phase 2
- Next experiment (smallest change to try): Add price list scoping UI (group/category dropdowns) to price-lists frontend page
