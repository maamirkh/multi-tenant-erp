---
id: "0007"
title: Epic 6 Phase 3 Approval Engine Implementation
stage: green
date: 2026-07-27
surface: agent
model: claude-sonnet-4-6
feature: 006-purchase-management
branch: 005-inventory-management
user: shehla83
command: sp.implement
labels: ["approval-engine","phase3","purchase-management","epic6","fastapi","sqlalchemy"]
links:
  spec: specs/006-purchase-management/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/modules/purchase/models/approval.py
  - backend/migrations/versions/017_purchase_approval_engine.py
  - backend/modules/purchase/repositories/approval.py
  - backend/modules/purchase/services/approval_service.py
  - backend/modules/purchase/schemas/approval.py
  - backend/modules/purchase/dependencies.py
  - backend/modules/purchase/router.py
  - backend/tests/unit/modules/purchase/test_approval_service.py
  - backend/tests/unit/modules/purchase/test_approval_invariants.py
  - backend/tests/unit/modules/purchase/test_approval_feature_flags.py
  - backend/tests/integration/repositories/purchase/test_approval_repositories.py
  - backend/tests/integration/api/v1/purchase/test_approval_api.py
  - frontend/src/app/(protected)/(purchase)/settings/approval-matrix/page.tsx
  - frontend/src/app/(protected)/(purchase)/approvals/page.tsx
  - frontend/src/app/(protected)/(purchase)/settings/policies/page.tsx
  - specs/006-purchase-management/tasks.md
tests:
  - tests/unit/modules/purchase/test_approval_service.py — 29 passed
  - tests/unit/modules/purchase/test_approval_invariants.py — 8 passed
  - tests/unit/modules/purchase/test_approval_feature_flags.py — 8 passed
  - tests/integration/repositories/purchase/test_approval_repositories.py — 20 passed
  - tests/integration/api/v1/purchase/test_approval_api.py — 27 passed
---

## Prompt

Continuing Epic 6 Phase 3 — "Procurement Foundation — Approval Engine (P1)" implementation.

Tasks T073–T098: Complete approval engine including ORM models (ApprovalMatrix, MatrixRule,
ApprovalLevel, ApprovalRecord, ApprovalDelegate), Alembic migration, repositories with
append-only guard on ApprovalRecord, ApprovalService with route_for_approval/approve/reject/
emergency_bypass/resolve_approver, Pydantic schemas, 20+ API endpoints, frontend pages,
and full test suite.

## Response snapshot

Implemented all 26 Phase 3 tasks (T073–T098):

**Domain Models** (`models/approval.py`): 5 ORM models using TenantBaseModel.
ApprovalRecord enforces append-only at repo layer (NotImplementedError on update/soft_delete).

**Migration** (`017_purchase_approval_engine.py`): Creates approval_matrices, matrix_rules,
approval_levels, approval_records, approval_delegates with FK constraints and company_id indexes.

**Repositories** (`repositories/approval.py`): 5 repositories.
ApprovalDelegateRepository includes `get_active_delegation()` with time-window + document_type filter.

**Service** (`services/approval_service.py`): Full ApprovalService.
- `route_for_approval`: policy flag check → matrix lookup → rule matching (ALWAYS/AMOUNT_RANGE/CATEGORY/DEPARTMENT) → level retrieval; auto-approves when flag OFF, no matrix, no matching rule, or rule has no levels.
- Self-approval prevention: SelfApprovalError when approver_id == requestor_id.
- Immutability: AlreadyActionedError when level already has a terminal record.
- Emergency bypass: level_number=1 + is_emergency_bypass=True (DB CHECK requires >= 1).
- Delegation: resolve_approver returns delegate_id when active delegation exists.

**API** (`router.py`): 20+ Phase 3 endpoints for matrix/rule/level CRUD, approve/reject/bypass actions, delegate management, policy configuration. All endpoints use `company_id: UUID = Path(...)` for tenant isolation and `current_user.user_id`.

**Key fixes applied**:
- Added `ApprovalDelegate` to service model imports (fixed NameError in create_delegate)
- Added auto_approved=True path when matched rule has empty levels list
- Changed emergency_bypass level_number 0→1 (satisfies DB CHECK constraint)
- Fixed test assertion `level_number == 0` → `== 1`
- Fixed test `delegator_id = user_resp.json()["data"]["id"]` → `.get("user_id") or .get("id")`
- Added `company_id = uuid4()` and `rule_id = str(uuid4())` to _make_level() mock helpers

**Tests**: 92/92 passing across all 5 test files.

## Outcome

- ✅ Impact: Phase 3 Approval Engine fully implemented and tested. 26/26 tasks complete.
- 🧪 Tests: 92 passed (45 unit + 20 repository integration + 27 API integration)
- 📁 Files: 16 files created/modified across models, repos, services, schemas, API, frontend, tests
- 🔁 Next prompts: Phase 4 — Purchase Requests (T099+)
- 🧠 Reflection: UUID duality pattern (as_uuid=True for PK, as_uuid=False for FK columns) required careful attention. CurrentUser.user_id vs .id is a recurring footgun that needs checking in every new phase.

## Evaluation notes (flywheel)

- Failure modes observed: Missing model import (ApprovalDelegate), wrong level_number in bypass (DB CHECK), test using wrong field name (user_id vs id), MagicMock missing UUID-typed attributes for Pydantic validation
- Graders run and results (PASS/FAIL): pytest 92/92 PASS
- Prompt variant (if applicable): sp.implement Phase 3
- Next experiment (smallest change to try): Add ApprovalDelegate to a shared import checklist for future phases
