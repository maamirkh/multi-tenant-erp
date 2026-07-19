# Quickstart: Epic 4 — Users & Roles

**Date**: 2026-07-16 | **Branch**: `004-users-roles`

---

## Prerequisites

- Epic 2 (Auth) fully implemented and passing tests
- Epic 3 (Companies) fully implemented and passing tests
- Docker Compose running (`docker compose up -d`)
- Database migrated to latest Epic 3 revision

---

## Integration Scenarios

### Scenario 1: Company Creation Seeds Roles

When a new company is created (Epic 3), Epic 4's `RoleSeedService` automatically seeds:
- 8 system roles with predefined ranks
- 14 initial permissions in the global registry (if not already present)
- Role-permission mappings for all system roles

**Integration point**: Epic 3's company creation flow must call `RoleSeedService.seed_company_roles(company_id)` within the same transaction.

---

### Scenario 2: First Member (Owner) Creation

When a company is created, the creating user becomes the first CompanyMember:
- Status: `active`
- Role: `owner` (rank 100)
- `invited_by`: NULL (self-created)

**Integration point**: Epic 3's company creation must create the initial CompanyMember record.

---

### Scenario 3: Adding a New Member

1. Admin+ calls `POST /api/v1/companies/{company_id}/members`
2. Service validates: actor.rank > assigned_role.rank
3. If user exists (by email): creates CompanyMember with status `active`
4. If user does not exist: creates User account (minimal) + CompanyMember with status `pending_invitation`
5. Domain event `MemberCreatedEvent` published to outbox
6. Audit log entry recorded

---

### Scenario 4: Member Lifecycle Transitions

```
POST /api/v1/companies/{company_id}/members/{member_id}/deactivate
POST /api/v1/companies/{company_id}/members/{member_id}/suspend
POST /api/v1/companies/{company_id}/members/{member_id}/lock
POST /api/v1/companies/{company_id}/members/{member_id}/archive
POST /api/v1/companies/{company_id}/members/{member_id}/reactivate
POST /api/v1/companies/{company_id}/members/{member_id}/restore
```

Each transition:
- Validates state machine (invalid transitions return 409 Conflict)
- Checks actor.rank > target.rank (returns 403 if insufficient)
- Revokes target's sessions on deactivate/suspend/lock/archive
- Records audit log with before/after state

---

### Scenario 5: Ownership Transfer

1. Owner calls `POST /api/v1/companies/{company_id}/transfer-ownership`
2. Target must be an active member of the company
3. Within a single transaction:
   - Target's role changed to Owner
   - Former owner's role changed to Admin
   - `companies.owner_id` updated
   - Audit log recorded
   - `OwnershipTransferredEvent` published

---

### Scenario 6: Custom Role Creation

1. Owner/Admin calls `POST /api/v1/companies/{company_id}/roles`
2. Validates: new role rank < creator's rank
3. Validates: role count < MAX_CUSTOM_ROLES_PER_COMPANY
4. Creates role with selected permissions
5. Role immediately available for member assignment

---

### Scenario 7: Profile & Preferences (Self-Service)

- `GET /api/v1/profile` — current user's profile
- `PATCH /api/v1/profile` — update display name, phone
- `POST /api/v1/profile/avatar` — upload avatar (multipart)
- `GET /api/v1/preferences` — current user's preferences
- `PUT /api/v1/preferences` — update language, timezone, theme, date format

These endpoints are NOT company-scoped (personal to the user).

---

### Scenario 8: Future Module Integration

When a future module (e.g., Inventory) integrates with Epic 4:

1. **Add permissions** via Alembic migration:
   ```
   INSERT INTO permissions (id, code, label, module, action)
   VALUES (..., 'inventory.create', 'Create Inventory Items', 'inventory', 'create');
   ```

2. **Map to system roles** via same migration:
   ```
   INSERT INTO role_permissions (id, role_id, permission_id) ...
   ```

3. **Use company member context** in endpoints:
   ```
   current_member = get_current_company_member(company_id)
   # member.role, member.company_id available
   ```

4. **Future**: When authorization middleware exists, add `require_permission('inventory.create')` dependency.

---

## Key API Patterns

| Pattern | Implementation |
|---------|---------------|
| Authentication | `get_current_user()` from Epic 2 auth module |
| Company context | `get_current_company_member(company_id)` from Epic 4 dependencies |
| Rank enforcement | Service layer checks `actor.role.rank > target.role.rank` |
| Tenant isolation | Every repository query includes `WHERE company_id = :company_id` |
| Audit logging | Service calls `audit_repo.log(company_id, action, actor_id, before, after)` |
| Domain events | Written to `event_outbox` within same transaction |
| Error responses | Standard error envelope from `core/exceptions/` |
| Pagination | Cursor-based with `?cursor=&limit=` pattern |

---

## Running the Module

```bash
# Start infrastructure
docker compose up -d

# Run migrations (includes Epic 4 tables + seed data)
alembic upgrade head

# Start backend
uvicorn backend.main:app --reload

# Start frontend
cd frontend && npm run dev
```

---

## Testing

```bash
# All Epic 4 tests
pytest tests/ -k "users_roles" -v

# Unit tests only
pytest tests/unit/modules/users_roles/ -v

# Integration tests only
pytest tests/integration/ -k "users_roles" -v

# Security tests
pytest tests/security/users_roles/ -v
```
