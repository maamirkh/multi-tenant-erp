# Data Model: Epic 4 — Users & Roles

**Date**: 2026-07-16 | **Branch**: `004-users-roles` | **Status**: Complete

---

## 1. Entity Overview

| Entity | Table Name | Scope | Purpose |
|--------|-----------|-------|---------|
| CompanyMember | `company_members` | Company-scoped | Binds User to Company with role, status, and employee info |
| Role | `roles` | Company-scoped | Named role with rank and system/custom flag |
| Permission | `permissions` | Global | Platform-wide capability catalogue |
| RolePermission | `role_permissions` | Company-scoped (via role) | Many-to-many join between roles and permissions |
| UserPreference | `user_preferences` | User-scoped | Personal display/UX preferences |
| User (extension) | `users` | Global | Add avatar_url, avatar_previous_url, phone |

---

## 2. Entity Definitions

### 2.1 CompanyMember

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| id | UUID | PK, default uuid4 | Unique member identifier |
| company_id | UUID | FK → companies.id, NOT NULL | Owning company |
| user_id | UUID | FK → users.id, NOT NULL | The user account |
| role_id | UUID | FK → roles.id, NOT NULL | Assigned role |
| status | ENUM | NOT NULL, default 'pending_invitation' | Membership lifecycle state |
| employee_id | VARCHAR(50) | NULLABLE, unique per company | Company-assigned employee ID |
| job_title | VARCHAR(100) | NULLABLE | Position title |
| department | VARCHAR(100) | NULLABLE | Department name (free-text) |
| work_phone | VARCHAR(20) | NULLABLE | Work contact number |
| hire_date | DATE | NULLABLE | Employment start date |
| notes | TEXT | NULLABLE | Internal notes about member |
| invited_by | UUID | FK → users.id, NULLABLE | User who created the membership |
| invitation_accepted_at | TIMESTAMP | NULLABLE | When invitation was accepted |
| suspended_reason | TEXT | NULLABLE | Required when status = suspended |
| deletion_reason | TEXT | NULLABLE | Required when status = archived |
| deleted_at | TIMESTAMP | NULLABLE | Soft delete timestamp |
| created_at | TIMESTAMP | NOT NULL, server default | Record creation |
| updated_at | TIMESTAMP | NOT NULL, server default, on update | Last modification |

**Indexes**:
- UNIQUE: `(company_id, user_id)` — one membership per user per company
- UNIQUE: `(company_id, employee_id)` WHERE employee_id IS NOT NULL — unique employee IDs per company
- INDEX: `(company_id, status)` — filtered member listings
- INDEX: `(user_id)` — find all memberships for a user
- INDEX: `(role_id)` — count members per role
- INDEX: `(company_id, department)` — department filtering

**Status Enum Values**: `pending_invitation`, `active`, `inactive`, `suspended`, `locked`, `archived`

**State Transitions**:

| From | To | Trigger | Conditions |
|------|----|---------|------------|
| pending_invitation | active | Invitation accepted | User accepts or already registered |
| active | inactive | Deactivated by admin | Actor rank > target rank |
| active | suspended | Suspended by admin | Actor rank > target rank; reason required |
| active | locked | System lock | Security event or admin action |
| inactive | active | Reactivated by admin | Actor rank > target rank |
| suspended | active | Reinstated by admin | Actor rank > target rank |
| locked | active | Unlocked by admin | Actor rank > target rank |
| active | archived | Soft deleted | Actor rank > target rank; reason required; not last Owner |
| inactive | archived | Soft deleted | Same as above |
| suspended | archived | Soft deleted | Same as above |
| locked | archived | Soft deleted | Same as above |
| archived | active | Restored | Owner/Admin only |

---

### 2.2 Role

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| id | UUID | PK, default uuid4 | Unique role identifier |
| company_id | UUID | FK → companies.id, NOT NULL | Owning company |
| name | VARCHAR(50) | NOT NULL | Display name |
| slug | VARCHAR(50) | NOT NULL | URL-safe identifier |
| description | TEXT | NULLABLE | Role purpose description |
| rank | INTEGER | NOT NULL, CHECK(rank > 0 AND rank <= 100) | Numeric hierarchy value |
| is_system | BOOLEAN | NOT NULL, default FALSE | True for seeded system roles |
| is_active | BOOLEAN | NOT NULL, default TRUE | Soft disable without deletion |
| created_at | TIMESTAMP | NOT NULL, server default | Record creation |
| updated_at | TIMESTAMP | NOT NULL, server default, on update | Last modification |

**Indexes**:
- UNIQUE: `(company_id, slug)` — unique role slugs per company
- INDEX: `(company_id, is_active)` — active role listings
- INDEX: `(company_id, rank)` — rank-ordered queries

**System Roles (seeded per company)**:

| Name | Slug | Rank | Description |
|------|------|------|-------------|
| Owner | owner | 100 | Company owner with full authority |
| Administrator | admin | 80 | Daily administration and user management |
| Manager | manager | 60 | Department operations management |
| Accountant | accountant | 55 | Financial operations |
| Salesperson | salesperson | 50 | Sales operations |
| Cashier | cashier | 45 | Point-of-sale operations |
| Store Keeper | store-keeper | 42 | Inventory/warehouse operations |
| Viewer | viewer | 20 | Read-only access |

**Validation Rules**:
- System roles cannot be deleted, renamed, or have rank changed
- Custom role rank must be < creator's role rank
- Custom role rank must be > 0 and < 100 (reserved for Owner)
- Maximum 50 custom roles per company (configurable)
- Slug auto-generated from name; must be unique per company

---

### 2.3 Permission

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| id | UUID | PK, default uuid4 | Unique permission identifier |
| code | VARCHAR(100) | UNIQUE, NOT NULL | Dot-notation code (e.g., `members.create`) |
| label | VARCHAR(100) | NOT NULL | Human-readable name |
| module | VARCHAR(50) | NOT NULL | Module group (e.g., `members`, `roles`, `companies`) |
| action | VARCHAR(50) | NOT NULL | Action type (create, read, update, delete, manage) |
| description | TEXT | NULLABLE | Detailed description |
| created_at | TIMESTAMP | NOT NULL, server default | Record creation |

**Indexes**:
- UNIQUE: `(code)` — globally unique permission codes
- INDEX: `(module)` — group by module

**Initial Permissions (14 total)**:

| Code | Label | Module | Action |
|------|-------|--------|--------|
| members.create | Add Members | members | create |
| members.read | View Members | members | read |
| members.update | Edit Members | members | update |
| members.delete | Remove Members | members | delete |
| members.manage | Manage Member Status | members | manage |
| roles.create | Create Roles | roles | create |
| roles.read | View Roles | roles | read |
| roles.update | Edit Roles | roles | update |
| roles.delete | Delete Roles | roles | delete |
| companies.read | View Company | companies | read |
| companies.update | Edit Company | companies | update |
| companies.manage | Manage Company | companies | manage |
| profile.read | View Profiles | profile | read |
| profile.update | Edit Own Profile | profile | update |

---

### 2.4 RolePermission

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| id | UUID | PK, default uuid4 | Unique mapping identifier |
| role_id | UUID | FK → roles.id, NOT NULL, ON DELETE CASCADE | Role |
| permission_id | UUID | FK → permissions.id, NOT NULL | Permission |
| created_at | TIMESTAMP | NOT NULL, server default | When mapping was created |

**Indexes**:
- UNIQUE: `(role_id, permission_id)` — no duplicate mappings
- INDEX: `(permission_id)` — find which roles have a permission

**Default Role-Permission Matrix**:

| Permission | Owner | Admin | Manager | Accountant | Salesperson | Cashier | Store Keeper | Viewer |
|-----------|-------|-------|---------|------------|-------------|---------|-------------|--------|
| members.create | Y | Y | N | N | N | N | N | N |
| members.read | Y | Y | Y | Y | Y | Y | Y | Y |
| members.update | Y | Y | N | N | N | N | N | N |
| members.delete | Y | Y | N | N | N | N | N | N |
| members.manage | Y | Y | N | N | N | N | N | N |
| roles.create | Y | Y | N | N | N | N | N | N |
| roles.read | Y | Y | Y | Y | Y | Y | Y | Y |
| roles.update | Y | Y | N | N | N | N | N | N |
| roles.delete | Y | Y | N | N | N | N | N | N |
| companies.read | Y | Y | Y | Y | Y | Y | Y | Y |
| companies.update | Y | Y | N | N | N | N | N | N |
| companies.manage | Y | N | N | N | N | N | N | N |
| profile.read | Y | Y | Y | Y | Y | Y | Y | Y |
| profile.update | Y | Y | Y | Y | Y | Y | Y | Y |

---

### 2.5 UserPreference

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| id | UUID | PK, default uuid4 | Unique preference record |
| user_id | UUID | FK → users.id, UNIQUE, NOT NULL | Owning user (1:1) |
| language | VARCHAR(10) | NOT NULL, default 'en' | Preferred UI language (BCP-47) |
| timezone | VARCHAR(50) | NOT NULL, default 'UTC' | IANA timezone identifier |
| date_format | VARCHAR(20) | NOT NULL, default 'YYYY-MM-DD' | Date display format |
| number_format | VARCHAR(20) | NOT NULL, default 'en-US' | Number formatting locale |
| theme | VARCHAR(10) | NOT NULL, default 'system' | UI theme (light/dark/system) |
| notification_preferences | JSONB | NOT NULL, default '{}' | Future notification settings |
| created_at | TIMESTAMP | NOT NULL, server default | Record creation |
| updated_at | TIMESTAMP | NOT NULL, server default, on update | Last modification |

**Indexes**:
- UNIQUE: `(user_id)` — one preference record per user

**Validation Rules**:
- Language must be a valid BCP-47 tag from supported list
- Timezone must be a valid IANA timezone
- Theme must be one of: `light`, `dark`, `system`
- Date format must be one of: `YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`, `DD-MM-YYYY`

---

### 2.6 User Table Extension

| Field | Type | Constraints | Description |
|-------|------|------------|-------------|
| avatar_url | VARCHAR(500) | NULLABLE | Current avatar S3 URL |
| avatar_previous_url | VARCHAR(500) | NULLABLE | Previous avatar (for rollback) |
| phone | VARCHAR(20) | NULLABLE | Personal phone number |

These columns are added to the existing `users` table via Alembic migration.

---

## 3. Relationships Diagram

```
users (Epic 2)
  │
  ├── 1:many ──→ company_members
  │                    │
  │                    ├── many:1 ──→ roles
  │                    │                │
  │                    │                └── 1:many ──→ role_permissions
  │                    │                                      │
  │                    │                                      └── many:1 ──→ permissions
  │                    │
  │                    └── many:1 ──→ companies (Epic 3)
  │
  └── 1:1 ──→ user_preferences
```

---

## 4. Cascade Rules

| Parent | Child | On Delete | Rationale |
|--------|-------|-----------|-----------|
| companies | company_members | RESTRICT | Cannot delete company with members |
| companies | roles | RESTRICT | Cannot delete company with roles |
| users | company_members | RESTRICT | Cannot hard-delete user with memberships |
| roles | company_members | RESTRICT | Cannot delete role with assigned members |
| roles | role_permissions | CASCADE | Deleting role removes its permission mappings |
| permissions | role_permissions | RESTRICT | Cannot remove permission from catalogue if mapped |
| users | user_preferences | CASCADE | Preference record removed with user |

---

## 5. Configuration Constants

| Constant | Default | Environment Variable | Description |
|----------|---------|---------------------|-------------|
| Max members per company | 10,000 | `COMPANY_MAX_MEMBERS` | Membership limit |
| Max custom roles per company | 50 | `MAX_CUSTOM_ROLES_PER_COMPANY` | Custom role limit |
| Invitation expiry | 7 days | `INVITATION_EXPIRY_DAYS` | Time before invitation expires |
| Avatar max size | 5 MB | `USER_AVATAR_MAX_BYTES` | Upload size limit |
| Avatar retention | 30 days | `AVATAR_RETENTION_DAYS` | Previous avatar kept |
| Member deletion retention | 90 days | `MEMBER_DELETION_RETENTION_DAYS` | Before permanent purge |
