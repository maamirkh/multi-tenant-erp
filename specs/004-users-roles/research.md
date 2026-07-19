# Research: Epic 4 — Users & Roles

**Date**: 2026-07-16 | **Branch**: `004-users-roles` | **Status**: Complete

---

## Summary

No NEEDS CLARIFICATION items existed in the Technical Context. All technology choices and architectural decisions were resolved during the specification and planning phases. This document consolidates the key decisions and their rationale.

---

## Decision 1: Single Role Per Membership

- **Decision**: Each CompanyMember has exactly one role (many:1 relationship)
- **Rationale**: Simplifies permission evaluation, avoids role conflict resolution complexity, aligns with enterprise ERP patterns (SAP, Odoo). A single rank value per member enables deterministic hierarchy enforcement.
- **Alternatives considered**:
  - Multi-role with union permissions (too complex for MVP; conflicts between role ranks)
  - Multi-role with priority ordering (over-engineered; custom roles make this unnecessary)

## Decision 2: System Roles Replicated Per Company

- **Decision**: Each company gets its own copy of the 8 system roles (seeded on company creation)
- **Rationale**: Enables per-company member counts on role entities without cross-company JOINs. Supports future per-company rank customization. Maintains tenant isolation.
- **Alternatives considered**:
  - Global shared system roles (violates tenant isolation; complicates member counts)
  - Hybrid: global definition + company-level override (over-engineered for current scope)

## Decision 3: Permission Registry is Global

- **Decision**: The `permissions` table is not company-scoped; it's a platform-wide catalogue
- **Rationale**: Permissions represent system capabilities (e.g., `members.create`, `roles.update`). These are defined by the platform, not by individual companies. Companies control which permissions are assigned to their roles via `role_permissions`.
- **Alternatives considered**:
  - Company-scoped permissions (would duplicate identical records across companies; no business need for company-specific permission definitions)

## Decision 4: Department as Free-Text Field

- **Decision**: The `department` field on CompanyMember is a VARCHAR, not a FK to a separate entity
- **Rationale**: The spec defines departments as a conceptual model with a "future promotion path" to a full entity. For Epic 4, this avoids premature complexity. The field serves employee information needs without introducing CRUD overhead.
- **Alternatives considered**:
  - Full Department entity with CRUD (premature; spec explicitly defers this)
  - Enum-based department (too rigid for diverse business types)

## Decision 5: Structural Authorization Only

- **Decision**: Epic 4 builds the permission data model but does NOT implement runtime authorization middleware
- **Rationale**: The spec explicitly places authorization engine implementation in a future Epic. Epic 4 provides the foundation (roles, permissions, role-permission mappings) that the future middleware will evaluate against. Rank-based management hierarchy IS enforced in the service layer.
- **Alternatives considered**:
  - Full RBAC middleware in Epic 4 (out of scope per spec; increases blast radius)
  - No permission model at all (would require schema changes in the future Authorization Epic)

## Decision 6: Transactional Outbox for Domain Events

- **Decision**: Domain events (MemberCreated, RoleChanged, etc.) are written to the `event_outbox` table within the same database transaction as the state change
- **Rationale**: Ensures at-least-once delivery semantics without requiring distributed transactions. Follows the pattern established in Epic 3. Future event consumers (notifications, analytics) can read from the outbox.
- **Alternatives considered**:
  - Direct event dispatch (no delivery guarantee; loses events on service crash)
  - Separate event bus (infrastructure overhead not justified at current scale)

## Decision 7: Rank-Based Numeric Hierarchy

- **Decision**: Roles use numeric `rank` values: Owner=100, Admin=80, Manager=60, Accountant=55, Salesperson=50, Cashier=45, Store Keeper=42, Viewer=20
- **Rationale**: Enables simple comparison (`actor.rank > target.rank`) for management hierarchy enforcement. Gaps between values allow future intermediate roles. Custom roles are assigned ranks by the creator (must be < creator's rank).
- **Alternatives considered**:
  - Named hierarchy levels (requires complex tree traversal; less flexible)
  - Permission-based management check (circular dependency; permission evaluation is deferred)

## Decision 8: Avatar Storage via S3-Compatible Storage

- **Decision**: User avatars stored in S3-compatible storage (MinIO dev / AWS S3 prod) reusing Epic 3 patterns
- **Rationale**: Epic 3 established the `core/storage/s3_client.py` for company logos. Same infrastructure handles avatar uploads. Separates binary storage from database.
- **Alternatives considered**:
  - Database BLOB storage (poor performance; violates separation of concerns)
  - Filesystem storage (not scalable; not compatible with container deployments)

---

## Technology Best Practices Applied

| Technology | Best Practice | Application |
|-----------|--------------|-------------|
| SQLAlchemy 2.x async | Mapped column syntax; async session factory | All new models use `Mapped[T]` syntax |
| Pydantic v2 | `model_validator`, `field_validator`; `ConfigDict` | All request/response schemas |
| FastAPI | Dependency injection; APIRouter modularization | `dependencies.py` with `get_*_service()` factories |
| Alembic | Single migration per Epic; revision chain | `004_users_roles.py` migration |
| TanStack Query v5 | Query keys as tuples; stale time per resource type | Cache strategy in plan Section 10.2 |
| React Hook Form + Zod | Schema-driven validation; server error integration | All forms mirror Pydantic schemas |
| PostgreSQL 16 | Composite indexes; partial indexes for soft-delete | Indexes on (company_id, status), (company_id, user_id) |

---

## Integration Patterns

| Integration | Pattern | Source |
|------------|---------|--------|
| Epic 2 Auth → Epic 4 | `get_current_user()` dependency + User table extension | Existing auth module |
| Epic 3 Companies → Epic 4 | FK relationships; audit log reuse; S3 reuse; owner_id sync | Existing companies module |
| Epic 4 → Future Auth Engine | Permission registry + role-permission mapping ready for middleware consumption | Structural foundation only |
| Epic 4 → Future Modules | Permission registration via Alembic migration; `get_current_company_member()` dependency | Documented integration pattern |

---

## Conclusion

All technical decisions have been resolved. No blockers remain. The plan is ready for task decomposition (`/sp.tasks`).
