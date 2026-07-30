---
id: "0014"
title: Epic 6 Phase 10 Integration Foundation Import Export Contracts
stage: green
date: 2026-07-30
surface: agent
model: claude-sonnet-4-6
feature: 006-purchase-management
branch: 005-inventory-management
user: shehla83
command: sp.implement
labels: ["phase10","integration","events","openapi","contracts","quickstart","barcode","email","import","export"]
links:
  spec: specs/006-purchase-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/tests/unit/modules/purchase/test_all_events_coverage.py
  - backend/modules/purchase/constants.py
  - backend/modules/purchase/services/po_service.py
  - backend/modules/purchase/router.py
  - specs/006-purchase-management/contracts/events.md
  - specs/006-purchase-management/contracts/purchase-v1.yaml
  - specs/006-purchase-management/quickstart.md
  - backend/tests/integration/api/v1/purchase/test_supplier_import.py
  - backend/tests/integration/api/v1/purchase/test_po_export.py
  - CLAUDE.md
  - specs/006-purchase-management/tasks.md
tests:
  - backend/tests/unit/modules/purchase/test_all_events_coverage.py (68 tests — 33 events × 2: create_factory + json_serialisable)
  - backend/tests/integration/api/v1/purchase/test_supplier_import.py (18 tests — CSV + 10k perf + Excel rejection)
  - backend/tests/integration/api/v1/purchase/test_po_export.py (16 tests — structure + multi-line + errors + isolation)
---

## Prompt

# =============================================================================
# DevSphere ERP
# Epic 6 – Purchase Management
# Phase 10 – "Integration Foundation, Import/Export & Contracts (P1)"
# Enterprise Implementation Prompt
# =============================================================================

Implement ONLY:

Epic 6 / Phase 10 / Phase Name: "Integration Foundation, Import/Export & Contracts (P1)"

Tasks T231–T242: domain event coverage tests, feature flag stubs (email + barcode),
OpenAPI contract generation, events.md contract doc, quickstart.md, import/export tests,
CLAUDE.md update, Docker verification.

## Response snapshot

Implemented all 12 tasks (T231–T242) for Phase 10 Integration Foundation:

**Domain Events (T231+T232):**
- `test_all_events_coverage.py`: 68 tests — 2 per event across all 33 domain events
- Coverage: create_factory + json_serialisable for every event class
- All 33 event_type strings verified unique and present in inventory
- Note: Implementation has 33 events (spec says 32) — all 33 tested and verified

**Feature Flag Stubs (T234+T235):**
- `constants.py`: Added `purchase.po_email_supplier` and `purchase.gr_barcode_scan` feature flag definitions (both default_enabled=False)
- `po_service.py`: Added email stub in `approve_po()` — inline `PurchaseFeatureFlagService` check; logs intent when flag enabled
- `router.py`: Added `GET /goods-receipts/barcode/{barcode}` endpoint — returns 403 if flag disabled, 501 (stub) if enabled

**Contracts (T233+T236+T237):**
- `contracts/events.md`: Full domain event catalogue — 33 events in 6 aggregates, base envelope docs, Epic 5 integration contract, EventBus subscription guide
- `contracts/purchase-v1.yaml`: OpenAPI JSON schema generated from live FastAPI app — 106 purchase endpoints, 155 filtered schemas (~265KB)

**Developer Guide (T238):**
- `quickstart.md`: End-to-end guide covering: auth, supplier CRUD + bulk import, PR workflow, PO workflow (direct + from PR), GR confirmation, RMA lifecycle, reports+KPIs, feature flags, domain event subscription, test commands, error reference

**Tests (T239+T240):**
- `test_supplier_import.py`: 18 tests — CSV valid/error/duplicate/empty, Excel+TXT rejection, auth enforcement, tenant isolation, feature flag gate, 10k row performance (completes in ~33s, well under 60s limit)
- `test_po_export.py`: 16 tests — payload structure (7 required fields), multi-line+charges+total accuracy, 404 on missing PO, 401 unauthenticated, tenant isolation

**CLAUDE.md + Tasks (T241+T242):**
- CLAUDE.md `## Recent Changes` updated with Phase 10 summary
- Docker verified: API healthy, 106 purchase endpoints registered, barcode endpoint returns 401 (correct — unauth)
- tasks.md T231–T242 and Phase 10 exit criteria all marked [X]

**Tests — 102 total Phase 10 tests:**
- 68 unit tests: all 33 domain events × 2 assertions each
- 18 integration tests: supplier import (CSV + perf + Excel rejection)
- 16 integration tests: PO PDF export structure + errors + isolation

## Outcome

- ✅ Impact: Phase 10 complete — integration foundation operational (domain events verified, feature flags stubbed, contracts documented, quickstart ready, 102 tests passing)
- 🧪 Tests: 102 passed (68 unit + 18 import + 16 export); all in local env; Docker verified separately
- 📁 Files: 10 backend/spec files created/modified, tasks.md T231–T242 marked [X]
- 🔁 Next prompt: Phase 11 (Performance, Security & Epic Closure — T243–T255)
- 🧠 Reflection: PO line schema uses `product_description`/`quantity_ordered`/`unit_cost` (not `description`/`quantity`/`unit_price`); POAdditionalCharge requires `description` field (not optional); `create_test_user` returns `(User, str)` not `(User, Company)` — company_id generated as `uuid4()` per test pattern; OpenAPI schema is 810KB full but 265KB filtered to purchase paths only

## Evaluation notes (flywheel)

- Failure modes observed: fixture using wrong return-type assumption for `create_test_user`; PO line/charge schema field name mismatch; sed line-start anchor failing on content-embedded task IDs
- Graders run and results (PASS/FAIL): 102/102 PASS; Docker health+endpoint PASS
- Prompt variant (if applicable): sp.implement Phase 10
- Next experiment (smallest change to try): Phase 11 with security + performance benchmarks
