# Module: Users & Roles (Epic 4)

**Version**: 1.0.0
**Epic**: 004-users-roles
**Status**: Production-ready
**Date**: 2026-07-19

---

## Overview

The Users & Roles module transforms a single-owner company (Epic 3) into a fully collaborative, multi-user, role-based workspace. It provides:

- Company membership management with invitation lifecycle
- A configurable role hierarchy (8 system roles + unlimited custom roles)
- A platform-wide permission registry
- User profile and preferences management
- Ownership transfer with full audit trail
- Complete tenant isolation — no data leakage between companies

All operations are company-scoped. A user can belong to multiple companies with different roles in each.

---

## Architecture

### Module Location

```
backend/modules/users_roles/
├── models/              # SQLAlchemy ORM models
│   ├── company_member.py
│   ├── role.py
│   ├── permission.py
│   ├── role_permission.py
│   ├── user_preference.py
│   └── enums.py
├── repositories/        # Data access layer
│   ├── company_member_repository.py
│   ├── role_repository.py
│   ├── permission_repository.py
│   ├── role_permission_repository.py
│   └── user_preference_repository.py
├── services/            # Business logic layer
│   ├── member_service.py
│   ├── invitation_service.py
│   ├── role_service.py
│   ├── role_seed_service.py
│   ├── ownership_service.py
│   ├── profile_service.py
│   └── preference_service.py
├── schemas/             # Pydantic request/response models
├── router.py            # Members endpoints
├── roles_router.py      # Roles endpoints
├── permissions_router.py # Permissions catalogue
├── profile_router.py    # User profile endpoints
├── preferences_router.py # User preferences endpoints
├── ownership_router.py  # Ownership transfer endpoint
├── dependencies.py      # FastAPI DI factories & auth guards
├── exceptions.py        # Domain exception definitions
├── constants.py         # System roles, permissions, rank values
└── validators.py        # Shared validation utilities
```

### Integration Points

| Dependency | From Module | How Used |
|-----------|------------|----------|
| `users` table | Epic 2 Auth | `company_members.user_id` FK; extended with `avatar_url`, `phone`, `display_name` |
| `companies` table | Epic 3 Companies | `company_members.company_id`, `roles.company_id` FK |
| `company_audit_logs` table | Epic 3 Companies | All member/role mutations write audit events |
| `event_outbox` table | Core / Epic 3 | Domain events written within same transaction |
| `get_current_user()` | Epic 2 Auth | Token validation and user identity |
| `SessionRepository` | Epic 2 Auth | Session revocation on lifecycle state changes |
| `S3StorageClient` / `_NullStorageClient` | Core | Avatar upload (S3 in production; null stub in tests) |
| `CompanyService` | Epic 3 Companies | Hooks `RoleSeedService` on company creation |

---

## Role Hierarchy

The system defines 8 immutable system roles in order of authority:

| Rank | Slug | Name | Description |
|------|------|------|-------------|
| 100 | `owner` | Owner | Company owner with full authority |
| 80 | `admin` | Administrator | Daily administration and user management |
| 60 | `manager` | Manager | Department operations management |
| 55 | `accountant` | Accountant | Financial operations |
| 50 | `salesperson` | Salesperson | Sales operations |
| 45 | `cashier` | Cashier | Point-of-sale operations |
| 42 | `store-keeper` | Store Keeper | Inventory/warehouse operations |
| 20 | `viewer` | Viewer | Read-only access |

Custom roles can be created with any rank between 1 and (actor_rank − 1). System roles are immutable.

### Rank Enforcement Rules

- An actor can only assign roles with rank **strictly less than** their own rank.
- Exception: Owners (rank 100) can manage other Owners (same rank) for demotion.
- An actor cannot change their own role (`CannotModifyOwnRoleError` → HTTP 409).
- Custom role creation requires rank < actor's rank (`InvalidRoleRankError` → HTTP 422).

---

## Permission Model

### Permission Registry (14 Initial Permissions)

| Code | Label | Module | Action |
|------|-------|--------|--------|
| `members.create` | Add Members | members | create |
| `members.read` | View Members | members | read |
| `members.update` | Edit Members | members | update |
| `members.delete` | Remove Members | members | delete |
| `members.manage` | Manage Member Status | members | manage |
| `roles.create` | Create Roles | roles | create |
| `roles.read` | View Roles | roles | read |
| `roles.update` | Edit Roles | roles | update |
| `roles.delete` | Delete Roles | roles | delete |
| `companies.read` | View Company | companies | read |
| `companies.update` | Edit Company | companies | update |
| `companies.manage` | Manage Company | companies | manage |
| `profile.read` | View Profiles | profile | read |
| `profile.update` | Edit Own Profile | profile | update |

### Default Role-Permission Matrix

| Permission | owner | admin | manager | accountant | salesperson | cashier | store-keeper | viewer |
|-----------|-------|-------|---------|------------|-------------|---------|-------------|--------|
| members.create | ✓ | ✓ | | | | | | |
| members.read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| members.update | ✓ | ✓ | | | | | | |
| members.delete | ✓ | ✓ | | | | | | |
| members.manage | ✓ | ✓ | | | | | | |
| roles.create | ✓ | ✓ | | | | | | |
| roles.read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| roles.update | ✓ | ✓ | | | | | | |
| roles.delete | ✓ | ✓ | | | | | | |
| companies.read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| companies.update | ✓ | ✓ | | | | | | |
| companies.manage | ✓ | | | | | | | |
| profile.read | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| profile.update | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

---

## API Endpoints

All member and role endpoints are company-scoped. Profile and preferences endpoints are user-scoped.

### Member Endpoints

Base path: `/api/v1/companies/{company_id}/members`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Member | List members (paginated, filterable) |
| POST | `/` | Admin+ | Add a new member |
| GET | `/{member_id}` | Member | Get member details |
| PATCH | `/{member_id}` | Admin+ | Update member role/employee info |
| POST | `/{member_id}/deactivate` | Admin+ | Deactivate (active → inactive) |
| POST | `/{member_id}/reactivate` | Admin+ | Reactivate (inactive/suspended → active) |
| POST | `/{member_id}/suspend` | Admin+ | Suspend with reason |
| POST | `/{member_id}/lock` | Admin+ | Lock account |
| POST | `/{member_id}/archive` | Admin+ | Archive (soft delete) |
| POST | `/{member_id}/restore` | Admin+ | Restore from archive |

### Role Endpoints

Base path: `/api/v1/companies/{company_id}/roles`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Member | List all roles with member counts |
| POST | `/` | Admin+ | Create a custom role |
| GET | `/{role_id}` | Member | Get role details with permissions |
| PATCH | `/{role_id}` | Admin+ | Update custom role |
| DELETE | `/{role_id}` | Admin+ | Delete custom role (no active members) |
| POST | `/{role_id}/permissions` | Admin+ | Assign permissions to role |
| DELETE | `/{role_id}/permissions/{perm_code}` | Admin+ | Remove permission from role |

### Permissions Endpoint

Base path: `/api/v1/permissions`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Authenticated | List all platform permissions |

### Profile Endpoints

Base path: `/api/v1/profile`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Authenticated | Get current user's profile |
| PATCH | `/` | Authenticated | Update display name and/or phone |
| POST | `/avatar` | Authenticated | Upload avatar (JPEG/PNG/WebP, ≤5 MB) |
| DELETE | `/avatar` | Authenticated | Remove current avatar |

### Preferences Endpoints

Base path: `/api/v1/preferences`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Authenticated | Get user preferences |
| PUT | `/` | Authenticated | Update preferences (language, timezone, theme, date format) |

### Ownership Transfer

Base path: `/api/v1/companies/{company_id}`

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/transfer-ownership` | Owner | Transfer company ownership to active member |

---

## Error Taxonomy

| Exception Class | HTTP Status | Error Code | Trigger |
|----------------|-------------|------------|---------|
| `InsufficientRankError` | 403 | `INSUFFICIENT_RANK` | Actor rank too low to perform action |
| `MemberNotFoundError` | 404 | `MEMBER_NOT_FOUND` | Member does not exist in company |
| `RoleNotFoundError` | 404 | `ROLE_NOT_FOUND` | Role does not exist in company |
| `MemberAlreadyExistsError` | 409 | `MEMBER_ALREADY_EXISTS` | Duplicate membership |
| `MemberLimitExceededError` | 409 | `MEMBER_LIMIT_EXCEEDED` | Company member cap reached |
| `InvalidStatusTransitionError` | 409 | `INVALID_STATUS_TRANSITION` | Invalid lifecycle state change |
| `LastOwnerProtectionError` | 409 | `LAST_OWNER_PROTECTION` | Cannot remove/demote the last Owner |
| `CannotModifyOwnRoleError` | 409 | `CANNOT_MODIFY_OWN_ROLE` | Self-role-change prevention |
| `RoleNameConflictError` | 409 | `ROLE_NAME_CONFLICT` | Duplicate role name |
| `RoleHasActiveAssignmentsError` | 409 | `ROLE_HAS_ACTIVE_ASSIGNMENTS` | Cannot delete role with members |
| `CustomRoleLimitExceededError` | 409 | `CUSTOM_ROLE_LIMIT_EXCEEDED` | Company custom role cap reached |
| `EmployeeIdConflictError` | 409 | `EMPLOYEE_ID_CONFLICT` | Duplicate employee ID in company |
| `SystemRoleImmutableError` | 409 | `SYSTEM_ROLE_IMMUTABLE` | Cannot modify system-defined role |
| `AvatarTooLargeError` | 400 | `AVATAR_TOO_LARGE` | File exceeds size limit |
| `AvatarInvalidFormatError` | 400 | `AVATAR_INVALID_FORMAT` | Unsupported image format (by magic bytes) |
| `InvalidRoleRankError` | 422 | `INVALID_ROLE_RANK` | Rank out of allowed range |

---

## Membership Lifecycle

```
pending_invitation → active → inactive → archived
                   ↓        ↗
                  suspended → active
                   ↓
                  locked → active
                   ↓
                  archived → active (restore)
```

Valid transitions:

| From | To | Trigger |
|------|----|---------|
| `pending_invitation` | `active` | Invitation accepted |
| `active` | `inactive` | Deactivate |
| `active` | `suspended` | Suspend with reason |
| `active` | `locked` | Lock account |
| `active` | `archived` | Archive (soft delete) |
| `inactive` | `active` | Reactivate |
| `inactive` | `archived` | Archive |
| `suspended` | `active` | Reactivate |
| `suspended` | `archived` | Archive |
| `locked` | `active` | Reactivate |
| `locked` | `archived` | Archive |
| `archived` | `active` | Restore |

All deactivation/suspension/lock/archive operations revoke the member's active sessions.

---

## Configuration Reference

These settings are read from the application `Settings` (`.env` file):

| Setting | Default | Description |
|---------|---------|-------------|
| `MAX_MEMBERS_PER_COMPANY` | 100 | Maximum active members per company |
| `MAX_CUSTOM_ROLES_PER_COMPANY` | 50 | Maximum custom roles per company |
| `USER_AVATAR_MAX_BYTES` | 5242880 | Avatar upload size limit (5 MB) |
| `AVATAR_RETENTION_DAYS` | 30 | Days to retain old avatar files after replacement |

---

## Tenant Isolation

Every repository method includes a `company_id` filter — no query can return data from a different company. The `get_current_company_member` FastAPI dependency enforces that the requesting user has an active membership in the target company before any operation proceeds.

Cross-company access returns HTTP 403 (explicit denial, not 404, to clearly indicate prohibition).

Security invariants validated by `tests/security/users_roles/`:
- Tenant isolation: `test_tenant_isolation.py`
- Rank enforcement: `test_rank_enforcement.py`
- Owner protection: `test_owner_protection.py`
- Avatar upload security: `test_avatar_upload_security.py`

---

## Testing

```bash
# All Epic 4 tests (360 tests)
pytest tests/ -k "users_roles" -v

# Security tests only
pytest tests/security/users_roles/ -v

# Performance tests only
pytest tests/performance/users_roles/ -v

# Integration API tests only
pytest tests/integration/api/v1/users_roles/ -v

# Repository tests only
pytest tests/integration/repositories/users_roles/ -v
```

### Test Coverage by Layer

| Layer | Test Location | Count |
|-------|--------------|-------|
| API Integration | `tests/integration/api/v1/users_roles/` | ~180 tests |
| Repository | `tests/integration/repositories/users_roles/` | ~30 tests |
| Security | `tests/security/users_roles/` | 40 tests |
| Performance | `tests/performance/users_roles/` | 6 tests |

---

## Future Module Integration

When adding a new module (e.g., Inventory) that needs Epic 4 authorization:

1. **Add permissions** via Alembic migration:
   ```sql
   INSERT INTO permissions (id, code, label, module, action, description)
   VALUES (gen_random_uuid(), 'inventory.create', 'Create Inventory Items', 'inventory', 'create', 'Create new inventory records');
   ```

2. **Map to system roles** in the same migration (owner and admin get full access by convention).

3. **Use company member context** in your router:
   ```python
   from modules.users_roles.dependencies import get_current_company_member, require_rank
   from modules.users_roles.constants import ADMIN_RANK

   @router.post("/items", dependencies=[Depends(require_rank(ADMIN_RANK))])
   def create_item(current_member = Depends(get_current_company_member)):
       # current_member.company_id, current_member.role_id available
       ...
   ```

4. **Enforce tenant isolation** by always filtering with `company_id` in your repository queries.
