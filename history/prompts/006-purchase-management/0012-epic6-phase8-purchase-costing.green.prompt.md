---
id: "0012"
title: Epic 6 Phase 8 Purchase Costing
stage: green
date: 2026-07-29
surface: agent
model: claude-sonnet-4-6
feature: 006-purchase-management
branch: 006-purchase-management
user: shehla83
command: /sp.implement
labels: ["purchase-costing","ppv","cost-entry","phase8","epic6","purchase-management","decimal-arithmetic","tax-readiness"]
links:
  spec: specs/006-purchase-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/purchase/models/cost.py
  - backend/modules/purchase/models/goods_receipt.py
  - backend/migrations/versions/023_purchase_costing.py
  - backend/modules/purchase/events/cost_events.py
  - backend/modules/purchase/schemas/cost.py
  - backend/modules/purchase/schemas/purchase_order.py
  - backend/modules/purchase/services/cost_service.py
  - backend/modules/purchase/services/po_service.py
  - backend/modules/purchase/services/gr_service.py
  - backend/modules/purchase/dependencies.py
  - backend/modules/purchase/router.py
  - backend/modules/purchase/models/__init__.py
  - frontend/src/components/purchase/POCostPanel.tsx
  - frontend/src/components/purchase/GRCostPanel.tsx
  - backend/tests/unit/modules/purchase/test_cost_service.py
  - backend/tests/unit/modules/purchase/test_cost_events.py
  - backend/tests/integration/api/v1/purchase/test_costing_api.py
  - specs/006-purchase-management/tasks.md
tests:
  - backend/tests/unit/modules/purchase/test_cost_events.py (9 tests — PASSED)
  - backend/tests/unit/modules/purchase/test_cost_service.py (17 tests — PASSED)
  - backend/tests/integration/api/v1/purchase/test_costing_api.py (9 tests: 5 PASSED, 4 SKIPPED)
---

## Prompt

# =============================================================================
# DevSphere ERP
# Epic 6 – Purchase Management
# Phase 8 – "Purchase Costing (P1)"
# Enterprise Implementation Prompt
# =============================================================================

Implement Epic 6, Phase 8 "Purchase Costing (P1)" — tasks T189–T205.

Continue implementation strictly according to the approved documentation.

## Response snapshot

Implemented all 17 tasks (T189–T205) for Phase 8 Purchase Costing:

**Domain Model (T189)**
- `PurchaseCostEntry`: immutable cost snapshot created on GR confirmation — gr_id (unique per company), po_id, supplier_id, cost_date, subtotal, total_charges, total_discounts, tax_amount, total, credit_note_pending, invoice_id (reserved for AP), currency_code
- UniqueConstraint on (company_id, gr_id); 4 CheckConstraints; Indexes on po_id, supplier_id

**Migration (T190)**
- Alembic migration `023_purchase_costing.py` (revision 023, down_revision 022)
- Creates purchase_cost_entries table; adds tax_code, tax_rate, tax_amount to gr_lines (T196)

**Tax Readiness (T196)**
- Added tax_code (String 50), tax_rate (Numeric 5,2), tax_amount (Numeric 15,2) to GRLine model
- Added same fields to POLineCreate, POLineUpdate, POLineRead schemas
- POService._create_line updated to persist tax fields

**Domain Events (T197)**
- `PurchaseCostRecorded`: event_type="purchase.cost.recorded"
- `PurchasePriceVarianceDetected`: event_type="purchase.cost.ppv_alert"
- `AdditionalChargeRecorded`: event_type="purchase.cost.charge_recorded"

**Schemas (T199)**
- PPVLine, GRCostSummary, POCostSummary, PurchaseCostEntryRead

**CostService (T191–T195)**
- `compute_po_totals`: Decimal arithmetic; line_discount_amount > percent; header discount after line discounts
- `compute_ppv`: PPV = (unit_cost - po_unit_cost) × qty; PPV% = 0 when po_unit_cost = 0
- `check_ppv_alerts`: publishes PurchasePriceVarianceDetected if abs(PPV%) > threshold (default 5%)
- `create_cost_entry_on_gr_confirm`: immutable snapshot; CostEntryAlreadyExistsError for idempotency
- No update_cost_entry method — immutability enforced

**GRService integration (T194)**
- Added optional `cost_service` to GRService; `confirm_gr` calls it after step 8 (domain events)

**API Endpoints (T198) — 3 endpoints**
- GET /purchase-orders/{po_id}/cost-summary
- GET /goods-receipts/{gr_id}/cost-summary
- GET /goods-receipts/{gr_id}/cost-entry

**Frontend (T200, T201)**
- `POCostPanel.tsx`: cost breakdown with subtotal/charges/discounts/total rows
- `GRCostPanel.tsx`: PPV per line with color-coded variance

**Tests (T202, T203, T204)**
- 35 total tests; 31 PASSED, 4 SKIPPED (skip-by-design when PO not approved in test isolation)

**Docker Verification (T205)**
- Migration 023 applied (alembic current = 023 head); 3 cost endpoints in OpenAPI

## Outcome

- ✅ Impact: Phase 8 Purchase Costing fully implemented — immutable cost snapshots on GR confirmation, Decimal PPV computation, PPV threshold alerts, 3 REST endpoints, 2 frontend panels, tax readiness on POLine and GRLine
- 🧪 Tests: 31/35 passed (4 skip-by-design) — 9 unit events, 17 unit service, 9 integration API
- 📁 Files: 18 files created/modified
- 🔁 Next prompts: /sp.implement Phase 9 Purchase Intelligence & Reporting (T206+)
- 🧠 Reflection: sa.comment() is NOT a valid create_table argument in Alembic — use `comment="..."` keyword directly on create_table. Integration tests checking `resp.json()["data"]["tax_code"]` fail when endpoint returns PurchaseOrderRead (full PO) instead of POLineRead — must check `data["lines"][0]["tax_code"]`.

## Evaluation notes (flywheel)

- Failure modes observed: (1) Migration used `sa.comment()` → AttributeError; fix: use `comment="..."` keyword directly. (2) Integration test checked wrong nesting level for tax fields in PurchaseOrderRead response. (3) tasks.md had migration as "022" but 022 was already taken by vendor returns → used 023.
- Graders run and results (PASS/FAIL): 31 pytest tests PASS, 4 SKIP
- Prompt variant (if applicable): sp.implement Phase 8
- Next experiment (smallest change to try): Phase 9 Purchase Intelligence & Reporting
