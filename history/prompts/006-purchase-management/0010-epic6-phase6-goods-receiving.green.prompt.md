---
id: "0010"
title: Epic 6 Phase 6 Goods Receiving P1
stage: green
date: 2026-07-27
surface: agent
model: claude-sonnet-4-6
feature: 006-purchase-management
branch: 006-purchase-management
user: shehla83
command: /sp.implement
labels: ["goods-receiving","gr","phase6","epic6","purchase-management","ppv","over-receipt","tenant-isolation"]
links:
  spec: specs/006-purchase-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/purchase/models/goods_receipt.py
  - backend/modules/purchase/repositories/goods_receipt.py
  - backend/modules/purchase/services/gr_service.py
  - backend/modules/purchase/events/gr_events.py
  - backend/modules/purchase/schemas/goods_receipt.py
  - backend/modules/purchase/dependencies.py
  - backend/modules/purchase/router.py
  - backend/modules/purchase/models/__init__.py
  - frontend/src/app/(protected)/(purchase)/goods-receipts/page.tsx
  - frontend/src/app/(protected)/(purchase)/goods-receipts/new/page.tsx
  - frontend/src/app/(protected)/(purchase)/goods-receipts/[id]/page.tsx
  - backend/tests/unit/modules/purchase/test_gr_service.py
  - backend/tests/unit/modules/purchase/test_gr_events.py
  - backend/tests/integration/repositories/purchase/test_gr_transaction.py
  - backend/tests/integration/api/v1/purchase/test_gr_api.py
  - specs/006-purchase-management/tasks.md
tests:
  - backend/tests/unit/modules/purchase/test_gr_service.py (16 tests — PASSED)
  - backend/tests/unit/modules/purchase/test_gr_events.py (11 tests — PASSED)
  - backend/tests/integration/repositories/purchase/test_gr_transaction.py (15 tests — PASSED)
  - backend/tests/integration/api/v1/purchase/test_gr_api.py (9 tests — PASSED)
---

## Prompt

# =============================================================================
# DevSphere ERP
# Epic 6 – Purchase Management
# Phase 6 – "Goods Receiving (P1)"
# Enterprise Implementation Prompt
# =============================================================================

Implement Epic 6, Phase 6 "Goods Receiving (P1)" — tasks T148–T168.

Continue implementation strictly according to the approved documentation (spec.md, plan.md, tasks.md).

Previously completed: Epics 0–5, Epic 6 Phases 0–5 (supplier master, approval engine, purchase requests, purchase orders).

## Response snapshot

Implemented all 21 tasks (T148–T168) for Phase 6 Goods Receiving:

**Domain Models (T148–T149)**
- `GoodsReceipt` model: DRAFT/CONFIRMED lifecycle, gr_number (unique per company), po_id, supplier_id, received_by/at, delivery_note_number, warehouse_id, landed_cost_ready
- `GRLine` model: gr_id, po_line_id, product_id, quantity_received/rejected, unit_cost, po_unit_cost, ppv_amount/percentage, rejection_reason_id
- Fixed duplicate index bug: `TenantBaseModel` auto-creates `ix_{tablename}_company_id` via `index=True`; removed explicit Index declaration

**Migration (T150)**
- Alembic migration at `backend/migrations/versions/020_purchase_gr.py` (pre-existing)

**Service Layer (T151–T155)**
- `GRService`: create_gr (validates PO status APPROVED/PARTIALLY_RECEIVED), _compute_open_qty (ordered − sum confirmed receipts), _validate_over_receipt (BLOCK/WARN/ALLOW policies), confirm_gr (atomic: PPV compute, status → CONFIRMED, PO auto-status update, domain events), update_gr/replace_lines (immutability guard), _assert_draft
- PPV formula: `ppv_amount = (unit_cost − po_unit_cost) × quantity_received`, `ppv_pct = ppv_amount / (po_unit_cost × qty) × 100` (0 when po_cost=0)

**Repository (T156)**
- `GoodsReceiptRepository`: list_for_company (status/po_id/supplier_id filters), count_for_company, get_by_id_or_none, update_status, list_confirmed_for_po, has_confirmed_gr_for_po
- `GRLineRepository`: list_for_gr, get_by_id_or_none, delete_all_for_gr (soft-delete), get_received_qty_for_po_line
- Critical fix: two-phase UUID query for cross-dialect (PostgreSQL+SQLite) compatibility. Phase 1: fetch confirmed GR IDs as Python UUIDs. Phase 2: convert to `str(uid)` (dashed format = GRLine.gr_id storage) then use IN clause.

**Domain Events (T157)**
- GoodsReceived, GoodsRejected, GoodsPartiallyReceived, OverReceiptDetected — all with `create()` factory, `to_dict()`, correct event_type/aggregate_type

**API Endpoints (T158)**
- 5 endpoints registered: GET /purchase-orders/{po_id}/open-quantities, POST/GET /goods-receipts, GET/PUT /goods-receipts/{gr_id}, PUT /goods-receipts/{gr_id}/lines, POST /goods-receipts/{gr_id}/confirm
- Schemas (T159): GoodsReceiptCreate, GoodsReceiptUpdate, GoodsReceiptRead, GRLineCreate, GRLineRead, GROpenQuantity

**Frontend (T160–T162)**
- GR list page with status filter and table
- GR create form with dynamic line items (po_line_id, qty_received, qty_rejected, unit_cost)
- GR detail page with PPV columns (color-coded), confirm button (DRAFT only)

**Tests (T163–T167)**
- 51 total tests: 16 unit (GRService) + 11 unit (events) + 15 repository integration + 9 API integration
- ALL 51 PASSED

**Docker Verification (T168)**
- API running at http://localhost:8000
- All 5 GR endpoints visible in OpenAPI spec at /openapi.json
- Docker containers: erp-system-api-1, erp-system-web-1, erp-db-standalone, erp-system-minio-1

## Outcome

- ✅ Impact: Phase 6 Goods Receiving fully implemented — GR lifecycle (DRAFT→CONFIRMED), PPV computation, over-receipt policy (BLOCK/WARN/ALLOW), atomic confirmation, multi-tenant isolation, 5 REST endpoints, 3 frontend pages
- 🧪 Tests: 51/51 passed (16 unit GRService, 11 unit events, 15 repository integration, 9 API integration)
- 📁 Files: 15 files created/modified across backend models, repositories, services, events, schemas, router, dependencies, and frontend pages
- 🔁 Next prompts: /sp.implement Phase 7 Vendor Returns (T169–T187)
- 🧠 Reflection: SQLite/PostgreSQL UUID format mismatch required two-phase repository query. TenantBaseModel auto-creates company_id index — explicit Index declaration causes "already exists" error in SQLite integration tests.

## Evaluation notes (flywheel)

- Failure modes observed: (1) Duplicate index `ix_goods_receipts_company_id` from TenantBaseModel auto-index + explicit Index in __table_args__ — caught by integration tests; (2) SQLite UUID format mismatch: Uuid(as_uuid=True) stores 32-char hex, PG_UUID(as_uuid=False) stores dashed str(uuid) — func.cast() subquery failed cross-dialect; fixed with two-phase Python-side conversion.
- Graders run and results (PASS/FAIL): 51 pytest tests — PASS
- Prompt variant (if applicable): sp.implement Phase 6 continuation
- Next experiment (smallest change to try): Phase 7 Vendor Returns using same two-phase UUID pattern where needed
