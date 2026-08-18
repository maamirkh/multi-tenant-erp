# Developer Quickstart: Epic 9 — CRM

Written at Epic closure (Phase 10, T103). Gives a developer a copy-paste path to exercise the CRM module locally, matching Epic 8's `quickstart.md` structure.

## Prerequisites

- Docker + Docker Compose running (`docker compose ps` shows `api`, `web`, `db`, `minio` healthy)
- Repository checked out on branch `009-crm`

## Module Location

```
backend/modules/crm/
├── models/        # 8 ORM models (Lead, LeadSource, Pipeline, PipelineStage, Opportunity, Activity, CrmAuditLog, CrmFeatureFlag)
├── repositories/   # one per model + audit_log, feature_flag_repository
├── services/       # lead, lead_conversion, lead_source, pipeline, opportunity, activity, customer_360, reporting, audit, feature_flag, permission_check, provisioning
├── schemas/        # Pydantic request/response models
├── events/         # 12 domain events + CRM's own in-process EventBus
├── handlers/        # integration_handlers.py — consumes 2 Sales events
├── router.py         # ~30 endpoints, mounted at /api/v1/companies/{company_id}/crm
├── dependencies.py   # FastAPI DI factories + require_crm_enabled gate
├── constants.py      # 19 crm.* permission codes, feature flag key
└── exceptions.py      # domain exceptions -> typed HTTP responses (no new middleware)

frontend/src/app/(protected)/(crm)/   # 12 pages: dashboard, leads, opportunities, activities, customers/[id], reports, settings
frontend/src/components/crm/
frontend/src/lib/api/crm.ts
```

## Key Architectural Decisions (Read plan.md + research.md First)

- Customer master stays owned by Sales (`modules.sales.services.customer_service.CustomerService`, unmodified) — CRM never writes a `sales_*` table directly (ADR-1/ADR-2).
- Accounting is read-only from CRM (`AccountsReceivableService.get_customer_ledger`/`get_customer_aging`, unmodified) — ADR-3.
- `weighted_value` is computed at read time, not stored (ADR-13) — see research.md Decision 2 if a future load test against the real 10K-row PostgreSQL target ever shows this needs a `GENERATED ALWAYS AS` column.
- Idempotent Lead conversion recalls the original `customer_matched` fact from the audit log rather than assuming it — research.md Decision 1.

## Environment Setup

```bash
# Start Docker services (repo root)
docker compose up -d

# Apply migrations
docker compose exec api alembic upgrade head

# Run CRM-specific tests
docker compose exec api python -m pytest tests/unit/modules/crm tests/integration/repositories/crm tests/integration/api/v1/crm tests/security/crm tests/performance/crm -q

# Run full backend regression (ensure zero cross-Epic regression)
docker compose exec api python -m pytest tests/ -q

# Frontend dev server
docker compose exec web npm run dev
```

## Module Registration (Already Done — Reference Only)

CRM follows the exact same 3-line registration pattern as every prior module:

```python
# backend/api/v1/router.py
from modules.crm.router import router as crm_router
api_router.include_router(
    crm_router,
    prefix="/companies/{company_id}/crm",
    dependencies=[Depends(get_current_company_member), Depends(require_crm_enabled)],
)

# backend/main.py (inside lifespan)
register_crm_integration_handlers()
```

## Feature Flag

CRM is gated by `feature.crm.enabled`, per-company, defaulting to **disabled**. Enable it for local testing via the CRM provisioning/feature-flag service, or directly:

```python
from modules.crm.services.feature_flag_service import CrmFeatureFlagService
# service.enable(company_id) — see modules/crm/services/feature_flag_service.py
```

Every CRM route enforces this gate at router-include time (`require_crm_enabled`), alongside the standard `get_current_company_member` tenant-membership gate.

## RBAC

19 `crm.*` permissions (leads.*, opportunities.*, activities.*, pipeline.*, reports.view — see `modules/crm/constants.py`), enforced inline via `user_has_crm_permission()` (mirrors `user_has_accounting_permission()`'s exact logic shape). No new role is introduced — permissions map onto the existing 8 system roles (owner/admin/manager/accountant/salesperson/cashier/viewer/auditor).

## Testing Strategy Recap

| Level | Location | What |
|---|---|---|
| Unit | `tests/unit/modules/crm/` | State machines, `weighted_value`, customer-matching priority (mocked repo) |
| Repository/Integration | `tests/integration/repositories/crm/` | Tenant isolation ×6 tables, DB constraints, conversion atomicity, cross-module integration, audit/event coverage |
| API | `tests/integration/api/v1/crm/` | Full CRUD + action endpoints, RBAC wiring, feature flag gate, reports |
| Security | `tests/security/crm/` | 152-cell RBAC matrix (`test_rbac.py`) + all 12 SEC-01–SEC-12 cases (`test_tenant_and_security.py`) |
| Performance | `tests/performance/crm/` | 4 spec.md §47 targets — SQLite regression guards, see research.md Decision 2 |

## Critical Invariants to Test First (if extending this module)

- INV-001/INV-002: Lead conversion sets `converted_customer_id` + `converted_opportunity_id` together, atomically, or neither.
- INV-004: `Opportunity.stage_id` must always belong to `Opportunity.pipeline_id`.
- BR-006: every Activity has at least one of `lead_id`/`customer_id`/`opportunity_id`.
- BR-007: a PipelineStage cannot be deactivated while any OPEN Opportunity still occupies it.
- BR-008: at most one default Pipeline per company.

## Live Verification (Executed — T100, Epic-9 Closure Gate)

The full live-Postgres verification protocol (migration 055/056 upgrade/downgrade/upgrade against an isolated real Postgres container, real authenticated HTTP requests across every endpoint group, live tenant-isolation checks, live domain-event and audit-trail observation, and live performance re-confirmation at the literal spec.md §47 row counts) was run once, on request, as this epic's closure-level gate — see `tasks.md`'s "T100 Results" section for the full 14-item breakdown with concrete evidence. It surfaced and fixed one genuine finding: the local dev Postgres database's migration state had drifted from the migration file's own content (see research.md Decision 4) — not a CRM code defect, and specific to that one iterated-on local database, not the migration file itself (proven correct by the isolated-container cycle test). All live-verification test data was cleaned up afterward; the dev database was confirmed back to its pre-verification state.

## Common Pitfalls to Avoid

- Do not add per-record ownership filtering, fuzzy customer matching, campaign management, or any of the other items in tasks.md's "Known Deferred Scope" section — they are explicitly out of Epic 9.
- Do not import a CRM repository directly into `router.py` — always go through a service (Router → Service → Repository discipline, checked by T101/T102's own audit).
- Do not weaken tenant isolation or RBAC to make a cross-module integration easier — see the Defect Handling Process in tasks.md.
